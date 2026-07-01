"""
description: Contract-type filter for NormalizedJobs. Runs AFTER title_filter and
    AFTER normalize.py has already mapped contract_type_raw -> ContractType.
    Drops INTERNSHIP outright. Drops UNKNOWN only when the source is one that
    DOES expose contract type for FR jobs (france_travail / linkedin_gmail /
    wttj_algolia-FR) — there an UNKNOWN means missing data, not legitimate gap.
    For DE / BE / CH jobs from the same sources, UNKNOWN is kept (those source
    payloads legitimately can't tell us the contract).
inputs:
    - list[NormalizedJob]
outputs:
    - (kept, stats) where stats = {requested, kept, rejected, by_reason}
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR.parent.parent.parent))

from execution.personal_workflows.job_search_v2.contracts import (  # noqa: E402
    ContractType,
    JobSource,
    NormalizedJob,
)
from execution.personal_workflows.job_search_v2.profile import loader as profile_loader  # noqa: E402

logger = logging.getLogger("normalizer.contract_filter")

# Allowlist of final contract types that survive to the digest / sheet.
ACCEPT_TYPES = {ContractType.CDI, ContractType.CDD, ContractType.FREELANCE}

# 2026-07-01 audit fix: profile.json Track B lists contract types the
# ContractType enum maps to UNKNOWN — "Fractional", "Advisory", "Mission",
# "Contract", "Indépendant". Without this expansion, a valid Track B role
# labelled "Fractional AI Advisor" from a FR-aware source gets dropped as
# reject:unknown_from_fr_source because the enum shrank the label to UNKNOWN.
# We check the RAW contract label (pre-enum-mapping) against profile-declared
# accepted labels. If it matches, keep the job even if enum is UNKNOWN.
def _profile_accepted_contract_labels() -> set[str]:
    """Cached set of profile.tracks[].contract_types, lowercased."""
    return profile_loader.get_accepted_contract_labels()

# Sources whose APIs DO expose contract type for FR jobs. An UNKNOWN here means
# the data was missing in the payload — drop it. The same sources fetching
# DE/BE/CH may legitimately return contract=Unknown (the upstream API for those
# countries doesn't carry the field) — keep those.
FR_AWARE_SOURCES = {
    JobSource.FRANCE_TRAVAIL,
    JobSource.LINKEDIN_GMAIL,
    JobSource.WTTJ_ALGOLIA,
}

# Location substrings that mark a job as non-FR. When a FR_AWARE_SOURCES job
# resolves to one of these, we tolerate Unknown (the upstream data was sparse
# because the country isn't its primary jurisdiction).
NON_FR_LOCATION_MARKERS = [
    "germany", "deutschland",
    "berlin", "munich", "münchen", "hamburg", "frankfurt", "köln", "cologne",
    "düsseldorf", "stuttgart",
    "belgium", "belgique", "belgië", "belgie",
    "brussels", "bruxelles", "brussel", "antwerp", "anvers", "antwerpen",
    "ghent", "gent", "gand", "liege", "liège", "charleroi", "leuven", "louvain", "namur",
    "switzerland", "suisse", "schweiz", "svizzera",
    "geneva", "genève", "geneve", "genf",
    "zurich", "zürich", "lausanne", "bern", "berne", "basel", "bâle", "lugano",
    "winterthur", "zug",
]


def _is_non_fr_location(job: NormalizedJob) -> bool:
    haystack = f"{job.location} {job.description_snippet[:300]}".lower()
    return any(marker in haystack for marker in NON_FR_LOCATION_MARKERS)


def classify_contract(job: NormalizedJob) -> tuple[bool, str]:
    """Return (kept, reason).

    Order of checks:
      1. Enum in ACCEPT_TYPES  -> accept.
      2. Enum == INTERNSHIP    -> hard reject (operator profile).
      3. contract_type_raw contains any profile-declared contract label
         (Fractional, Advisory, Mission, etc.) -> accept, even if the enum
         resolves to UNKNOWN. Closes the 2026-07-01 audit gap where profile-
         valid Track B contracts were silently dropped.
      4. UNKNOWN + FR-aware source + FR location -> reject (missing data).
      5. UNKNOWN + non-FR                       -> keep (source doesn't
         expose the field for that country).
    """
    ct = job.contract_type
    if ct in ACCEPT_TYPES:
        return True, f"accept:{ct.value}"
    if ct == ContractType.INTERNSHIP:
        return False, "reject:internship"

    # Profile-driven contract acceptance. NormalizedJob does NOT preserve the
    # raw contract label (it's stripped by normalization to the enum), so we
    # pattern-match on the title + first 400 chars of description instead.
    # This is looser than checking the raw label but has no schema-change
    # blast radius. Terms like "fractional advisory" or "freelance mission"
    # in the title or JD reliably signal a Track B contract even when the
    # enum resolves to UNKNOWN.
    profile_ok = _profile_accepted_contract_labels()
    if profile_ok:
        haystack = f"{job.title} {job.description_snippet[:400]}".lower()
        title_lower = job.title.lower()
        # Require the label to appear as a whole word / phrase — NOT a raw
        # substring. Both branches use whitespace-padded containment so a
        # profile label "mission" cannot match "Omission Specialist" via a
        # bare substring hit. Multi-word phrases still match (their inner
        # whitespace is preserved on both sides of the padded check).
        for label in profile_ok:
            if not label or len(label) < 4:
                continue
            padded = f" {label} "
            if padded in f" {haystack} " or padded in f" {title_lower} ":
                return True, f"accept:profile_label:{label[:30]}"

    # UNKNOWN with no profile-label rescue.
    if job.source in FR_AWARE_SOURCES and not _is_non_fr_location(job):
        return False, "reject:unknown_from_fr_source"
    return True, "accept:unknown_non_fr"


def filter_by_contract(jobs: list[NormalizedJob]) -> tuple[list[NormalizedJob], dict]:
    kept: list[NormalizedJob] = []
    by_reason: dict[str, int] = {}
    for job in jobs:
        ok, reason = classify_contract(job)
        key = reason.split(":", 1)[-1] if ":" in reason else reason
        by_reason[key] = by_reason.get(key, 0) + 1
        if ok:
            kept.append(job)
    stats = {
        "requested": len(jobs),
        "kept": len(kept),
        "rejected": len(jobs) - len(kept),
        "by_reason": by_reason,
    }
    logger.info("contract_filter: %s", stats)
    return kept, stats
