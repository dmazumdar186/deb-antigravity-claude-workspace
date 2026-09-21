"""
description: Typed contracts (Pydantic v2) shared by every layer of job_search_v2.
inputs: imported by sources/, normalizer/, ranker/, notifier/, eval/
outputs: SourceJob, NormalizedJob, RankedJob, JobSource, JobTier — single source of truth.

The whole point of v2 is that no untyped dict crosses a layer boundary. If a future
contributor wants to add a field, they add it here, and every layer breaks loudly
at the boundary instead of silently dropping fields downstream.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class JobSource(str, Enum):
    """Enum so we cannot typo a source name across the pipeline."""

    FRANCE_TRAVAIL = "france_travail"
    WTTJ = "wttj"
    WTTJ_ALGOLIA = "wttj_algolia"
    APEC = "apec"
    LINKEDIN_GMAIL = "linkedin_gmail"
    LINKEDIN_GUEST_API = "linkedin_guest_api"
    INDEED_GMAIL = "indeed_gmail"
    HELLOWORK_GMAIL = "hellowork_gmail"
    HELLOWORK = "hellowork"  # public web scrape (search → JobPosting JSON-LD)
    JOBGETHER_GMAIL = "jobgether_gmail"
    REMOTEOK = "remoteok"
    WEWORKREMOTELY = "weworkremotely"
    FIXTURE = "fixture"  # used by tests/synthetic only


class ContractType(str, Enum):
    CDI = "CDI"
    CDD = "CDD"
    FREELANCE = "Freelance"
    INTERNSHIP = "Internship"
    UNKNOWN = "Unknown"


class RemoteMode(str, Enum):
    REMOTE = "Remote"
    HYBRID = "Hybrid"
    ONSITE = "Onsite"
    UNKNOWN = "Unknown"


class SourceJob(BaseModel):
    """Raw job from one source, before normalization.

    Each source adapter MUST return list[SourceJob]. Anything looser is rejected
    at the boundary, which is the entire reason this layer exists.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    source: JobSource
    source_id: str = Field(..., description="The source's internal job ID.")
    url: HttpUrl
    title: str
    company: str
    location_raw: str = Field("", description="Source's own location string; FR PM cares about Paris vs Île-de-France granularity.")
    description_snippet: str = Field("", max_length=2000)
    posted_at: datetime | None = Field(None, description="Source's posted timestamp; tz-aware if known, else None.")
    contract_type_raw: str = Field("", description="Source's own contract field; normalized later.")
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("source_id", "title", "company")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v.strip()


class NormalizedJob(BaseModel):
    """Post-normalization: cleaned, typed, ready for dedup + ranking."""

    model_config = ConfigDict(frozen=True)

    source: JobSource
    source_id: str
    url: HttpUrl
    canonical_url: str = Field(..., description="URL with tracking params stripped, lowercased host, used for dedup.")
    title: str
    company: str
    location: str = Field(..., description="Normalized: 'Paris', 'Île-de-France', or original if neither.")
    description_snippet: str
    posted_at: datetime | None
    contract_type: ContractType
    # 2026-07-01 data-flow auditor: preserve the raw label so downstream
    # filters can check it directly instead of pattern-matching on title.
    # Defaults to "" so existing serialized JSONL still parses. Populated
    # from SourceJob.contract_type_raw in normalize.py.
    contract_type_raw: str = Field(default="", description="Original contract label from source, pre-enum. Empty if source didn't expose it.")
    remote_mode: RemoteMode
    fetched_at: datetime
    content_hash: str = Field(..., description="SHA256(title|company|canonical_url) — exact-match dedup key.")
    also_seen_on: list[JobSource] = Field(default_factory=list)
    # 2026-09-10 dedup-fingerprint fix: fuzzy cross-source dedup key, SHA256 of
    # normalized(title)|normalized(company). Defaults to "" so pre-existing
    # serialized JSONL (written before this field existed) still parses.
    fingerprint: str = Field(default="", description="SHA256(norm_title|norm_company) — fuzzy cross-source dedup key.")

    @field_validator("content_hash")
    @classmethod
    def _hash_shape(cls, v: str) -> str:
        if len(v) != 64:
            raise ValueError("content_hash must be a 64-char hex sha256")
        return v


class JobTier(str, Enum):
    A = "A"  # top match — apply now
    B = "B"  # promising — review
    C = "C"  # weak fit — skim
    SKIP = "SKIP"  # below threshold


class RankedJob(BaseModel):
    """LLM-judge output. Attached alongside the NormalizedJob it scored."""

    model_config = ConfigDict(frozen=True)

    content_hash: str = Field(..., description="Joins back to NormalizedJob.content_hash.")
    score: float = Field(..., ge=0.0, le=1.0)
    tier: JobTier
    reasoning: str = Field(..., max_length=800)
    rubric_version: str = Field(..., description="Tag the rubric revision that produced the score.")
    ranker_model: str = Field(..., description="e.g. 'claude-fable-5' or 'gemini-2.5-flash'.")
    ranked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ----- helpers shared across layers -----


def compute_content_hash(title: str, company: str, canonical_url: str) -> str:
    """Stable SHA256 over (title, company, canonical_url). Same on every machine.

    Why these three: title+company catches reposts at the same URL; canonical_url
    catches identical postings cross-source; together they collide only when the
    job is actually the same.
    """
    payload = "|".join((title.strip().lower(), company.strip().lower(), canonical_url.strip().lower()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gh_src", "gh_jid", "fbclid", "gclid", "mc_eid", "mc_cid",
    "ref", "refsrc", "trk", "trkCampaign", "lipi",
    # 2026-09-10 dedup-fingerprint fix: common job-board tracking/session params
    # that vary per impression/click for what is otherwise the identical posting.
    # Deliberately NOT adding `q` — that's a query param some boards use to
    # identify the job itself, not tracking.
    "refId", "trackingId", "position", "pageNum", "originalSubdomain",
    "origin", "campaign", "xkcb", "xpse", "vjs", "advn", "sjdu",
    "utm_id", "mkt_tok", "_hsenc", "_hsmi", "hsCtaTracking",
    "itm_source", "itm_medium",
})
_TRACKING_PARAMS_LOWER = frozenset(p.lower() for p in _TRACKING_PARAMS)


def canonicalize_url(url: str) -> str:
    """Strip tracking params + lowercase host. Used as the URL dedup key.

    Boundary at the function: caller passes a string (HttpUrl or raw); we return
    a string the dedup layer treats as the canonical key. Kept in contracts.py
    because both the source layer (when building NormalizedJob) and the dedup
    layer (when matching) need byte-identical results.
    """
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

    parts = urlsplit(str(url))
    cleaned_query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=False) if k.lower() not in _TRACKING_PARAMS_LOWER])
    # 2026-09-10 dedup-fingerprint fix: strip a trailing "/" on path and
    # fragment so "/jobs/1" and "/jobs/1/" canonicalize identically.
    path = parts.path[:-1] if parts.path.endswith("/") and len(parts.path) > 1 else parts.path
    fragment = parts.fragment[:-1] if parts.fragment.endswith("/") and len(parts.fragment) > 1 else parts.fragment
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, cleaned_query, fragment))


# ----- fingerprint: fuzzy cross-source dedup -----

# Gender-marker variants seen on FR/DE/EN job boards, checked (case-insensitively,
# after accent-stripping) as literal substrings once punctuation is stripped to
# a single space. Longest-first so e.g. "h/f/x" doesn't get partially eaten by
# a shorter "h/f" removal leaving a stray "/x".
_GENDER_MARKERS = sorted(
    [
        "h/f/x", "f/m/x", "m/f/d", "m/w/d", "w/m/d", "x/f/m",
        "h/f", "f/h", "m/w", "w/m", "m/f", "f/m",
        "all genders",
    ],
    key=len,
    reverse=True,
)

_LEGAL_SUFFIXES = frozenset({
    "sas", "sa", "sarl", "sasu", "eurl", "gmbh", "ag", "ltd", "inc", "llc",
    "bv", "nv", "plc", "group", "groupe",
})

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def _strip_accents(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _normalize_title(title: str) -> str:
    s = _strip_accents(title).lower()
    for marker in _GENDER_MARKERS:
        s = s.replace(f"({marker})", " ").replace(marker, " ")
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    # Contract / location suffixes boards bolt onto the same posting
    # ("Product Manager - CDI", "Product Manager (CDI) Paris") are not part of
    # the job identity; drop them when they trail the title.
    s = _TRAILING_CONTRACT_RE.sub("", s).strip()
    return s


_TRAILING_CONTRACT_RE = re.compile(r"(\s+(cdi|cdd|freelance|full\s*time|temps\s+plein|permanent))+$")


def _normalize_company(company: str) -> str:
    s = _strip_accents(company).lower().strip()
    # Recruiter marker: leading "via " or trailing " via <x>".
    if s.startswith("via "):
        s = s[4:].strip()
    s = re.sub(r"\s+via\s+\S+.*$", "", s).strip()
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    tokens = [t for t in s.split(" ") if t and t not in _LEGAL_SUFFIXES]
    return " ".join(tokens)


def compute_fingerprint(title: str, company: str) -> str:
    """SHA256 of normalized(title)|normalized(company) — a fuzzy cross-source
    dedup key that survives gender-marker suffixes, accents, punctuation,
    legal-entity suffixes, and recruiter "via X" wrapping that make the exact
    content_hash miss the same posting seen from two different boards.

    If company is empty/"unknown"/"confidential" (after normalization), the
    fingerprint is title-only (paired with the literal "|_" so it can never
    collide with a real normalized empty-string company).
    """
    norm_title = _normalize_title(title)
    norm_company = _normalize_company(company)
    if norm_company in ("", "unknown", "confidential"):
        payload = f"{norm_title}|_"
    else:
        payload = f"{norm_title}|{norm_company}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
