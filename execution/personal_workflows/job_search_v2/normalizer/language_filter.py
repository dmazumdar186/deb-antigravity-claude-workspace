"""
description: Language filter for NormalizedJobs. Drops jobs whose title +
    description sample is NOT in English or French. Operator hard constraint
    (2026-06-24): "I don't want jobs to me which is in any other language
    apart from English and French."
inputs:
    - list[NormalizedJob]
outputs:
    - (kept, stats) where stats = {requested, kept, rejected, by_reason}

Detection: langdetect.detect_langs on f"{title}. {description_snippet[:400]}".
Falls back to ACCEPT on detection failure (too-short titles) to avoid
silently dropping borderline rows. Edge case logged.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR.parent.parent.parent))

from execution.personal_workflows.job_search_v2.contracts import NormalizedJob  # noqa: E402

logger = logging.getLogger("normalizer.language_filter")

ACCEPT_LANGS = {"en", "fr"}
# Substring tells for languages we explicitly want to reject. Catches cases
# where langdetect under-confidence fails open. These are language-specific
# stopwords that don't appear in EN/FR text.
DE_TELLS = (" und ", " mit ", " für ", " der ", " die ", " das ", " bei ", " m/w/d", " (m/w/d)", " im ", " ein ", " auch ", " sind ", " sich ", " sowie ")
NL_TELLS = (" een ", " voor ", " naar ", " bij ", " over ", " ook ", " als ", " het ", " maar ", " moet ")
IT_TELLS = (" del ", " della ", " che ", " sono ", " per ", " sulla ", " con ", " nel ", " nella ", " degli ", " uno ", " una ")
ES_TELLS = (" del ", " los ", " las ", " una ", " uno ", " con ", " sus ", " para ", " sobre ", " entre ", " donde ")
NON_EN_FR_TELLS = DE_TELLS + NL_TELLS + IT_TELLS + ES_TELLS


def classify_language(title: str, description_snippet: str) -> tuple[bool, str]:
    """Return (kept, reason). Reason is 'accept:<lang>' or 'reject:<lang>'."""
    # Quick substring screen first — catches DE/NL/IT/ES tells that langdetect
    # might miss on short samples. Adds " " padding to avoid mid-word matches.
    haystack_low = f" {title.lower()}. {description_snippet[:400].lower()} "
    for tell in NON_EN_FR_TELLS:
        if tell in haystack_low:
            # Identify which family
            if tell in DE_TELLS:
                return False, "reject:de_tell"
            if tell in NL_TELLS:
                return False, "reject:nl_tell"
            if tell in IT_TELLS:
                return False, "reject:it_tell"
            if tell in ES_TELLS:
                return False, "reject:es_tell"

    sample = f"{title}. {description_snippet[:400]}".strip()
    if len(sample) < 12:
        # Too short to detect reliably — pass through (accept). The title-only
        # gate above already runs.
        return True, "accept:too_short"

    try:
        from langdetect import detect_langs, DetectorFactory  # type: ignore
        DetectorFactory.seed = 42  # deterministic
        langs = detect_langs(sample)
    except Exception as exc:  # noqa: BLE001 — langdetect surface
        logger.warning("language_filter: detect failed (%s) — defaulting to accept", exc)
        return True, "accept:detect_error"

    if not langs:
        return True, "accept:no_detection"

    # Top language must be EN or FR with confidence ≥ 0.7. Otherwise reject.
    top = langs[0]
    if top.lang in ACCEPT_LANGS and top.prob >= 0.7:
        return True, f"accept:{top.lang}"
    if top.lang in ACCEPT_LANGS:
        # Low confidence — check if any of top-2 is EN/FR
        for candidate in langs[:2]:
            if candidate.lang in ACCEPT_LANGS and candidate.prob >= 0.4:
                return True, f"accept:{candidate.lang}_low_conf"
        return False, f"reject:{top.lang}_low_conf"
    return False, f"reject:{top.lang}"


def filter_by_language(jobs: list[NormalizedJob]) -> tuple[list[NormalizedJob], dict]:
    kept: list[NormalizedJob] = []
    by_reason: dict[str, int] = {}
    for job in jobs:
        ok, reason = classify_language(job.title, job.description_snippet)
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
    logger.info("language_filter: %s", stats)
    return kept, stats
