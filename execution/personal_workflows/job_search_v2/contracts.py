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
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class JobSource(str, Enum):
    """Enum so we cannot typo a source name across the pipeline."""

    FRANCE_TRAVAIL = "france_travail"
    WTTJ = "wttj"
    APEC = "apec"
    LINKEDIN_GMAIL = "linkedin_gmail"
    INDEED_GMAIL = "indeed_gmail"
    HELLOWORK_GMAIL = "hellowork_gmail"
    JOBGETHER_GMAIL = "jobgether_gmail"
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
    remote_mode: RemoteMode
    fetched_at: datetime
    content_hash: str = Field(..., description="SHA256(title|company|canonical_url) — exact-match dedup key.")
    also_seen_on: list[JobSource] = Field(default_factory=list)

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
    ranker_model: str = Field(..., description="e.g. 'claude-sonnet-4-6' or 'gemini-2.5-flash'.")
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
})


def canonicalize_url(url: str) -> str:
    """Strip tracking params + lowercase host. Used as the URL dedup key.

    Boundary at the function: caller passes a string (HttpUrl or raw); we return
    a string the dedup layer treats as the canonical key. Kept in contracts.py
    because both the source layer (when building NormalizedJob) and the dedup
    layer (when matching) need byte-identical results.
    """
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

    parts = urlsplit(str(url))
    cleaned_query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=False) if k.lower() not in _TRACKING_PARAMS])
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, cleaned_query, ""))
