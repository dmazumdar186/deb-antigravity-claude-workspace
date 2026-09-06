"""
description: SourceJob -> NormalizedJob mapper for job_digest. Generic (no country
    literals): location text is only whitespace/case cleaned, never rewritten into
    a specific city/region the way the operator's internal job pipeline does for
    Paris/Île-de-France.
inputs: list[SourceJob]
outputs: list[NormalizedJob] with content_hash + canonical_url filled in; batch_normalize
    additionally performs in-batch cross-source dedup by content_hash, merging
    also_seen_on so a job posted on two sources is only shown once.

Ported from the operator's internal job pipeline's normalizer. The only
intentional divergence: that pipeline rewrites location text to a canonical
"Paris" / "Île-de-France" literal (operator-specific). job_digest is shared across
arbitrary countries/cities from Profile, so this module keeps location normalization
generic — trim + collapse whitespace only. City/country matching happens later in
filters.py against registry aliases + profile.locations.cities.
"""

from __future__ import annotations

import logging
import re
import unicodedata

from ..contracts import (
    ContractType,
    NormalizedJob,
    RemoteMode,
    SourceJob,
    canonicalize_url,
    compute_content_hash,
)

logger = logging.getLogger("job_digest.normalizer.normalize")

_WHITESPACE_RE = re.compile(r"\s+")


def _fold_key(s: str) -> str:
    """Lowercase + strip diacritics + collapse whitespace, for the cross-
    source near-duplicate key (title, company) — two sources posting the
    same role under a URL-varying link (a UTM-tagged aggregator copy vs. the
    original) hash differently by content_hash (which includes canonical_url)
    but fold to the same (title, company) pair.
    """
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return _WHITESPACE_RE.sub(" ", s.strip().lower())


def _normalize_location(raw: str) -> str:
    """Generic cleanup only: collapse internal whitespace, trim, empty -> 'Unknown'.

    No country/city literals here by design (see module docstring) — this stays
    usable for any Profile's countries/cities without a code change.
    """
    if not raw or not raw.strip():
        return "Unknown"
    return _WHITESPACE_RE.sub(" ", raw).strip()


def _normalize_contract(raw: str) -> ContractType:
    s = (raw or "").strip().lower()
    if not s:
        return ContractType.UNKNOWN
    # Internship/apprentice first so "stage" / "alternance" don't get caught by
    # the broader "contract" / "permanent" rules below.
    if (
        "stage" in s or "alternance" in s
        or "apprenti" in s or "praktikum" in s or "werkstudent" in s
        or "stagista" in s
        or re.search(r"\bintern(s|ship|ships)?\b", s)
    ):
        return ContractType.INTERNSHIP
    if (
        "cdi" in s or "permanent" in s
        or "indéterminée" in s or "indeterminee" in s
        or "full_time" in s or "full-time" in s
        or "unbefristet" in s
        or "vast contract" in s or "vaste" in s
        or "tempo indeterminato" in s
    ):
        return ContractType.CDI
    if (
        "cdd" in s or "fixed-term" in s or "fixed term" in s
        or "déterminée" in s or "determinee" in s
        or "befristet" in s
        or "bepaalde duur" in s
        or "tempo determinato" in s
    ):
        return ContractType.CDD
    if (
        "freelance" in s or "indep" in s or "contract" in s or "mission" in s
        or "selbständig" in s or "selbstaendig" in s
        or "indépendant" in s or "independant" in s
        or "zzp" in s
    ):
        return ContractType.FREELANCE
    return ContractType.UNKNOWN


# A bare location field that names no city/region — "Remote", "Anywhere",
# "Worldwide", "Remote (EU)", "Télétravail" — is decisive on its own: RemoteOK
# and WeWorkRemotely both put exactly this kind of string in location_raw for
# every listing, so this must be checked before the ambiguous description
# heuristics below (C3: was misclassifying every such job as HYBRID, which
# then got dropped by filters._location_keeps since HYBRID != REMOTE).
_LOCATION_REMOTE_RE = re.compile(
    r"^\s*(?:"
    r"100%\s*(?:remote|t[eé]l[eé]travail)\b(?:\s*.*)?"
    r"|work\s*from\s*anywhere\b(?:\s*.*)?"
    r"|remote\b(?:\s*.*)?"
    r"|anywhere\b(?:\s*.*)?"
    r"|worldwide\b(?:\s*[\(\-–—:,]\s*[^)]*\)?)?"
    r"|global\b(?:\s*[\(\-–—:,]\s*[^)]*\)?)?"
    r"|fully\s*remote\b(?:\s*[\(\-–—:,]\s*[^)]*\)?)?"
    r"|t[eé]l[eé]travail\b(?:\s*[\(\-–—:,]\s*[^)]*\)?)?"
    r")\s*$",
    re.IGNORECASE,
)
_LOCATION_HYBRID_RE = re.compile(r"\bhybrid(e)?\b", re.IGNORECASE)
_LOCATION_ONSITE_RE = re.compile(r"\b(on[- ]?site|on-site|onsite|pr[eé]sentiel)\b", re.IGNORECASE)


def _detect_remote(location_raw: str, description_snippet: str) -> RemoteMode:
    loc = (location_raw or "").strip()

    # 1. Location string first: a bare "Remote"/"Anywhere"/"Worldwide"/
    #    "Remote (EU)"/"Télétravail" is decisive regardless of the description.
    if _LOCATION_REMOTE_RE.match(loc):
        return RemoteMode.REMOTE
    if _LOCATION_HYBRID_RE.search(loc):
        return RemoteMode.HYBRID
    if _LOCATION_ONSITE_RE.search(loc):
        return RemoteMode.ONSITE

    # 2. Fall back to the combined location+description heuristic.
    s = f"{location_raw} {description_snippet}".lower()
    if "full remote" in s or "100% remote" in s or "télétravail total" in s or "télétravail complet" in s:
        return RemoteMode.REMOTE
    if "hybrid" in s or "hybride" in s or "télétravail partiel" in s:
        return RemoteMode.HYBRID
    if "on site" in s or "on-site" in s or "présentiel" in s:
        return RemoteMode.ONSITE
    if "remote" in s or "télétravail" in s:
        return RemoteMode.HYBRID  # default when the word appears but not qualified
    return RemoteMode.UNKNOWN


def to_normalized(src: SourceJob) -> NormalizedJob:
    """Map one SourceJob to a NormalizedJob. Pure function, no I/O."""
    canonical = canonicalize_url(str(src.url))
    return NormalizedJob(
        source=src.source,
        source_id=src.source_id,
        url=src.url,
        canonical_url=canonical,
        title=src.title,
        company=src.company,
        location=_normalize_location(src.location_raw),
        description_snippet=src.description_snippet,
        posted_at=src.posted_at,
        contract_type=_normalize_contract(src.contract_type_raw),
        contract_type_raw=src.contract_type_raw,
        remote_mode=_detect_remote(src.location_raw, src.description_snippet),
        fetched_at=src.fetched_at,
        content_hash=compute_content_hash(src.title, src.company, canonical),
    )


def _merge_also_seen(existing: NormalizedJob, other: NormalizedJob) -> NormalizedJob:
    """Fold `other`'s source (and its own also_seen_on) into `existing`'s
    also_seen_on, without duplicates and without ever adding existing's own
    source to its own list."""
    also_seen = list(existing.also_seen_on)
    changed = False
    for source in (other.source, *other.also_seen_on):
        if source != existing.source and source not in also_seen:
            also_seen.append(source)
            changed = True
    if not changed:
        return existing
    return existing.model_copy(update={"also_seen_on": also_seen})


def batch_normalize(jobs: list[SourceJob]) -> list[NormalizedJob]:
    """Map a batch of SourceJobs to NormalizedJobs, then dedup in two passes:

    1. Exact dedup by content_hash (title+company+canonical_url) — the same
       posting fetched twice (e.g. re-run overlap, or a source paginating
       over the same job).
    2. Cross-source near-duplicate merge by folded (title, company) — the
       SAME job posted on two different sources (e.g. LinkedIn + WTTJ) almost
       always carries a different URL and so a different content_hash, but
       names the same role at the same company. The first-seen row is kept;
       every later row with the same folded (title, company) contributes its
       source to `also_seen_on` instead of appearing as a separate digest row.
    """
    by_hash: dict[str, NormalizedJob] = {}
    for src in jobs:
        nj = to_normalized(src)
        if nj.content_hash in by_hash:
            by_hash[nj.content_hash] = _merge_also_seen(by_hash[nj.content_hash], nj)
        else:
            by_hash[nj.content_hash] = nj

    by_title_company: dict[tuple[str, str], NormalizedJob] = {}
    for nj in by_hash.values():
        key = (_fold_key(nj.title), _fold_key(nj.company))
        if key in by_title_company:
            by_title_company[key] = _merge_also_seen(by_title_company[key], nj)
        else:
            by_title_company[key] = nj

    result = list(by_title_company.values())
    logger.info(
        "normalize: %d src -> %d normalized (hash dedup + cross-source title/company merge applied)",
        len(jobs), len(result),
    )
    return result
