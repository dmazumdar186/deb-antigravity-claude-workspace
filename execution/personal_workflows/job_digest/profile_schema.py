"""
description: profile.yaml schema + loader for job_digest. Every user-facing parameter lives here.
inputs: path to profile.yaml
outputs: validated Profile object; ProfileError with ALL problems listed (never just the first)

Rules enforced (from the operator's spec, 2026-09-06):
- 1..3 roles, each with a title; synonyms optional.
- 1..5 countries, mandatory, ISO2, each must exist in registry.COUNTRIES.
- cities optional, free text, matched fuzzily against location strings.
- candidate.email mandatory, syntactically valid.
- timezone must be a valid IANA zone; defaults to the first country's zone.
- languages default to the union of the selected countries' languages.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from . import registry

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

Seniority = Literal["any", "junior", "mid", "senior", "lead"]
Contract = Literal["permanent", "fixed_term", "freelance"]
Tier = Literal["A", "B", "C"]


class ProfileError(ValueError):
    """Raised with a human-readable, multi-line list of every validation problem."""


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(..., min_length=2, max_length=80)
    email: str

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        if not _EMAIL_RE.match(v):
            raise ValueError(f"{v!r} is not a valid email address")
        return v.lower()


class Role(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(..., min_length=3, max_length=80, description="e.g. 'Sales Manager'")
    synonyms: list[str] = Field(default_factory=list, max_length=10, description="Other titles that mean the same job.")
    seniority: Seniority = "any"

    @property
    def all_titles(self) -> list[str]:
        return [self.title, *self.synonyms]


class Locations(BaseModel):
    model_config = ConfigDict(extra="forbid")
    countries: list[str] = Field(..., min_length=1, max_length=5, description="ISO2 codes, 1 to 5.")
    cities: list[str] = Field(default_factory=list, max_length=10, description="Optional. If set, only jobs in these cities (or remote) are kept.")
    remote_ok: bool = True

    @field_validator("countries")
    @classmethod
    def _countries(cls, v: list[str]) -> list[str]:
        out, bad = [], []
        for c in v:
            c = c.strip().upper()
            if c not in registry.COUNTRIES:
                bad.append(c)
            elif c not in out:
                out.append(c)
        if bad:
            raise ValueError(f"unsupported country code(s) {bad}; supported: {', '.join(registry.SUPPORTED_ISO2)}")
        return out

    @field_validator("cities")
    @classmethod
    def _cities(cls, v: list[str]) -> list[str]:
        return [c.strip() for c in v if c and c.strip()]


class Exclude(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title_substrings: list[str] = Field(default_factory=lambda: ["intern", "internship", "stagiaire", "alternance", "trainee", "graduate program"])
    companies: list[str] = Field(default_factory=list)


class Digest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_jobs: int = Field(40, ge=5, le=100)
    hour_local: int = Field(9, ge=0, le=23)
    timezone: str | None = None  # filled from first country if None
    min_tier: Tier = "B"
    min_hours_between_emails: float = Field(20.0, ge=1.0, le=48.0)

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"{v!r} is not a valid IANA timezone (e.g. 'Europe/Paris', 'Asia/Kolkata')")
        return v


class Screening(BaseModel):
    """What the ranker knows about the candidate. Free text + optional skill lists."""
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(..., min_length=40, max_length=4000, description="3-10 sentences: what you do, years, domains, what you want next.")
    skills: list[str] = Field(default_factory=list, max_length=60)
    must_have: list[str] = Field(default_factory=list, max_length=20, description="Keywords a job MUST mention (any of).")
    nice_to_have: list[str] = Field(default_factory=list, max_length=40)


class Sheet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    candidate: Candidate
    roles: list[Role] = Field(..., min_length=1, max_length=3)
    locations: Locations
    languages: list[str] | None = None  # ISO 639-1; None -> derived from countries
    contracts: list[Contract] = Field(default_factory=lambda: ["permanent", "fixed_term"], min_length=1)
    exclude: Exclude = Field(default_factory=Exclude)
    digest: Digest = Field(default_factory=Digest)
    screening: Screening
    sheet: Sheet = Field(default_factory=Sheet)

    @model_validator(mode="after")
    def _fill_defaults(self) -> "Profile":
        if self.digest.timezone is None:
            self.digest.timezone = registry.get(self.locations.countries[0]).timezone
        if not self.languages:
            # H3: an explicit `languages: []` in profile.yaml must derive from
            # countries the same as an omitted/null field — an empty list here
            # previously made _language_keeps() reject every job it could
            # positively identify a language for (empty list contains nothing).
            self.languages = registry.languages_for(self.locations.countries)
        else:
            self.languages = [lang.strip().lower() for lang in self.languages if lang.strip()]
        return self

    # ----- derived views used by every downstream layer -----
    @property
    def keywords(self) -> list[str]:
        out: list[str] = []
        for r in self.roles:
            for t in r.all_titles:
                if t.lower() not in {o.lower() for o in out}:
                    out.append(t)
        return out

    @property
    def sources(self) -> list[str]:
        return registry.sources_for(self.locations.countries)

    @property
    def countries(self) -> list[registry.Country]:
        return [registry.get(c) for c in self.locations.countries]


def _format_errors(exc: ValidationError) -> str:
    lines = []
    for e in exc.errors():
        loc = ".".join(str(p) for p in e["loc"]) or "<root>"
        lines.append(f"  - {loc}: {e['msg']}")
    return "profile.yaml has {} problem(s):\n{}".format(len(lines), "\n".join(lines))


def load_profile(path: str | Path) -> Profile:
    p = Path(path)
    if not p.exists():
        raise ProfileError(f"profile not found: {p}")
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ProfileError(f"profile.yaml is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ProfileError("profile.yaml must be a mapping at the top level")
    try:
        return Profile.model_validate(raw)
    except ValidationError as exc:
        raise ProfileError(_format_errors(exc)) from exc


def validate_file(path: str | Path) -> list[str]:
    """Return [] if valid, else the list of problem lines. Never raises."""
    try:
        load_profile(path)
        return []
    except ProfileError as exc:
        return str(exc).splitlines()
