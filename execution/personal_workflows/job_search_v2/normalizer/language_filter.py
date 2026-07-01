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
import re
import sys
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR.parent.parent.parent))

from execution.personal_workflows.job_search_v2.contracts import NormalizedJob  # noqa: E402

logger = logging.getLogger("normalizer.language_filter")

ACCEPT_LANGS = {"en", "fr"}

# Gender / diversity markers that are NOT language content. German job titles
# carry "(m/w/d)", French ones carry "(H/F)" or "M/W", inclusive ones "(all
# genders)" — none of these tell us the POSTING language. They wreck langdetect
# on short titles (e.g. "Staff AI Engineer - M/W" in Paris detected as German).
# Strip them before detection. (Removed " m/w/d" from DE_TELLS for the same
# reason — it marks the German *market*, but the operator accepts English-
# language jobs located in Germany; the description-level detection decides.)
_GENDER_MARKER_RE = re.compile(
    r"""
    \(\s*(?:all\s+genders?|divers|gn|[mwfdhx](?:\s*/\s*[mwfdhx]){1,3})\s*\)  # (m/w/d), (all genders), (gn)
    | \b[mwfh](?:\s*/\s*[mwfdhx]){1,3}\b   # standalone m/w/d, h/f, m/w
    | \(\s*[mwfh]\s*/\s*[mwfh]\s*\)        # (h/f), (f/m)
    | \ball\s+genders?\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _strip_gender_markers(s: str) -> str:
    return _GENDER_MARKER_RE.sub(" ", s)


# Substring tells for languages we explicitly want to reject. Catches cases
# where langdetect under-confidence fails open. These are language-specific
# stopwords.
#
# HARD CONSTRAINT (audit 2026-06-24): every tell here MUST NOT appear in normal
# English or French job text. The first cut included " per ", " con ", " una ",
# " uno ", " del ", " als ", " im ", " ein ", " bij ", " ook ", " het " — all of
# which collide with English/French ("90k per year", "pros and cons", etc.) and
# silently dropped valid English descriptions from RemoteOK / WeWorkRemotely.
# Removed. Only high-specificity multi-char stopwords with no EN/FR collision
# remain. If a tell could plausibly appear in an English sentence, it does not
# belong here — let langdetect (>=60 char, >=0.85 conf) make that call instead.
DE_TELLS = (" und ", " mit ", " für ", " der ", " die ", " das ", " bei ", " sind ", " sich ", " sowie ", " unseren ", " unserem ", " standort ", "traineeprogramm", "produktmanager", " gmbh")
NL_TELLS = (" een ", " voor ", " naar ", " maar ", " moet ")
IT_TELLS = (" della ", " degli ", " nella ", " sono ", " sulla ", " nel ", " che ")
# ES_TELLS audit 2026-07-01: removed " para " (appears in English "data para
# model" / "parametric" contexts) and " entre " (French: "entre autres", "entre
# les deux"). Both were silently dropping valid EN/FR rows every day — ~3-8/day
# per run_log stats since 2026-06-24. Kept only high-specificity Spanish stopwords
# with no EN/FR collision. Rule: if a tell could plausibly appear in an English
# OR French sentence, it does NOT belong here — let langdetect decide.
ES_TELLS = (" los ", " las ", " sus ", " sobre ", " donde ", " porque ", " tambien ", " también ")
NON_EN_FR_TELLS = DE_TELLS + NL_TELLS + IT_TELLS + ES_TELLS


def classify_language(title: str, description_snippet: str) -> tuple[bool, str]:
    """Return (kept, reason). Reason is 'accept:<lang>' or 'reject:<lang>'."""
    # Strip gender/diversity markers first — they are not language content and
    # break detection on short titles.
    title = _strip_gender_markers(title)
    description_snippet = _strip_gender_markers(description_snippet)

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

    # CRITICAL: langdetect is unreliable on short text. "Staff AI Engineer" gets
    # mis-detected as German; "Product Owner Secteur Immobilier" (French) as
    # German. So we only let langdetect REJECT when there is enough text to be
    # reliable (a real description, >= 60 chars). For short title-only samples,
    # the tell-word screen above is the authoritative gate — if no foreign tell
    # fired, we ACCEPT (English + French dominate the keyword searches, so a
    # tell-free short title is almost certainly EN/FR). This errs toward keeping
    # borderline-English titles rather than dropping real matches.
    LANGDETECT_MIN_CHARS = 60

    if len(sample) < LANGDETECT_MIN_CHARS:
        return True, "accept:short_no_foreign_tell"

    try:
        from langdetect import detect_langs, DetectorFactory  # type: ignore
        DetectorFactory.seed = 42  # deterministic
        langs = detect_langs(sample)
    except Exception as exc:  # noqa: BLE001 — langdetect surface
        logger.warning("language_filter: detect failed (%s) — defaulting to accept", exc)
        return True, "accept:detect_error"

    if not langs:
        return True, "accept:no_detection"

    # Enough text + a real detection. Top language must be EN or FR with
    # high confidence to keep; reject only on a CONFIDENT non-EN/FR call.
    top = langs[0]
    if top.lang in ACCEPT_LANGS:
        return True, f"accept:{top.lang}"
    # Top is non-EN/FR. Only reject if confident; otherwise check top-2 for EN/FR.
    if top.prob >= 0.85:
        return False, f"reject:{top.lang}"
    for candidate in langs[:2]:
        if candidate.lang in ACCEPT_LANGS:
            return True, f"accept:{candidate.lang}_low_conf"
    return False, f"reject:{top.lang}_low_conf"


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
