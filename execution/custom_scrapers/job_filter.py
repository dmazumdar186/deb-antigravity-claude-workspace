"""
job_filter.py
description: Pure filter for French PM/PO job listings. Normalizes titles and companies, detects language, applies include/exclude keyword rules, and annotates each job with pass/fail status. No API calls, no DB access.
inputs: List of RawJob dicts (JSON file via --input) and config/job_tracker.json (loaded automatically).
outputs: List of CandidateJob dicts written to --output JSON file.
"""

import sys
import argparse
import re
from pathlib import Path
from dotenv import load_dotenv; load_dotenv()

# ---------------------------------------------------------------------------
# sys.path shim — ensures imports work when run as:
#   py execution/custom_scrapers/job_filter.py --input ... --output ...
# from the project root.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from langdetect import detect, DetectorFactory, LangDetectException  # noqa: E402
DetectorFactory.seed = 0

from execution.personal_workflows._jt_utils import (  # noqa: E402
    normalize_title,
    normalize_company,
    compute_job_hash,
    now_iso,
    load_jt_config,
    load_json,
    save_json,
)


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

_ALLOWED_LANGS = {"fr", "en"}


def detect_language(text: str) -> str | None:
    """Detect language of *text*; returns 'fr', 'en', or None.

    Returns None when:
    - text is empty or whitespace-only
    - LangDetectException is raised
    - detected language is not 'fr' or 'en'
    """
    if not text or not text.strip():
        return None
    try:
        lang = detect(text)
        return lang if lang in _ALLOWED_LANGS else None
    except LangDetectException:
        return None


# ---------------------------------------------------------------------------
# Exclude-term → reason mapping
# ---------------------------------------------------------------------------

# Each entry: (set_of_whole-word_tokens, reason_string)
# Order matters: first match wins.
_EXCLUDE_RULES: list[tuple[set[str], str]] = [
    ({"junior", "jr"}, "rejected:junior"),
    ({"stage", "stagiaire"}, "rejected:stage"),
    ({"alternance", "alternant", "alternante"}, "rejected:alternance"),
    ({"apprenti", "apprentie", "apprentissage"}, "rejected:apprenti"),
    ({"intern", "internship", "trainee"}, "rejected:intern"),
    ({"assistant"}, "rejected:assistant"),
    ({"graduate", "entry-level", "entry level"}, "rejected:graduate"),
]

# Pre-compiled whole-word patterns per rule (cache at module load time)
# We match against the already-normalized title (accent-stripped, lowercase).
# "entry level" (two words) needs special handling as a phrase.
_EXCLUDE_PATTERNS: list[tuple[re.Pattern, str]] = []
for _tokens, _reason in _EXCLUDE_RULES:
    # Build a single alternation pattern for this rule's tokens
    # Sort longest first to avoid partial shadowing
    _alts = sorted(_tokens, key=len, reverse=True)
    _pattern_str = r"(?<![a-z0-9])(?:" + "|".join(re.escape(t) for t in _alts) + r")(?![a-z0-9])"
    _EXCLUDE_PATTERNS.append((re.compile(_pattern_str, re.IGNORECASE), _reason))


def _matches_any_include(title_normalized: str, include: list[str]) -> bool:
    """Return True if any include keyword appears in title_normalized (substring match)."""
    for kw in include:
        kw_norm = normalize_title(kw)
        if kw_norm in title_normalized:
            return True
    return False


def is_kept_title(
    title_normalized: str,
    include: list[str],
    exclude: list[str],
) -> tuple[bool, str]:
    """Apply exclude rules then include rules to a normalized title.

    Returns (kept: bool, reason: str).
    Reason values:
      'accepted'
      'rejected:junior' | 'rejected:stage' | 'rejected:alternance' |
      'rejected:apprenti' | 'rejected:intern' | 'rejected:assistant' |
      'rejected:graduate' | 'rejected:not_pm'

    Note: the *exclude* parameter from config is accepted for API compatibility
    but actual exclude matching uses the pre-compiled _EXCLUDE_PATTERNS which
    covers all the config-listed exclude tokens with correct reason mapping.
    """
    # 1. Check exclude patterns (whole-word)
    for pattern, reason in _EXCLUDE_PATTERNS:
        if pattern.search(title_normalized):
            return (False, reason)

    # 2. Require at least one include keyword
    if not _matches_any_include(title_normalized, include):
        return (False, "rejected:not_pm")

    return (True, "accepted")


# ---------------------------------------------------------------------------
# Main filter function
# ---------------------------------------------------------------------------

def filter_jobs(raw_jobs: list[dict], config: dict) -> list[dict]:
    """Filter a list of RawJob dicts into CandidateJob dicts.

    Returns ALL jobs (kept and rejected) — caller can split on passed_filters.
    Each output dict conforms to the CandidateJob schema.
    """
    include_kws = config.get("title_keywords_include", [])
    exclude_kws = config.get("title_keywords_exclude", [])
    allowed_langs = set(config.get("languages_allowed", ["fr", "en"]))

    candidate_jobs: list[dict] = []

    for raw in raw_jobs:
        title = raw.get("title", "")
        company_name = raw.get("company_name", "")
        location = raw.get("location")

        title_normalized = normalize_title(title)
        company_normalized = normalize_company(company_name)
        job_hash = compute_job_hash(company_normalized, title_normalized, location)

        # Language detection on title + first 400 chars of description
        snippet = raw.get("description_snippet", "") or ""
        lang_text = title + " " + snippet[:400]
        language = detect_language(lang_text)

        # Title filter
        kept, filter_reason = is_kept_title(title_normalized, include_kws, exclude_kws)

        # Language gate (only applied when title passed)
        if kept and language not in allowed_langs:
            kept = False
            filter_reason = "rejected:language"

        candidate: dict = {
            # RawJob fields (pass-through)
            "board": raw.get("board", ""),
            "source_url": raw.get("source_url", ""),
            "title": title,
            "company_name": company_name,
            "location": location,
            "posted_at": raw.get("posted_at"),
            "description_snippet": snippet,
            "raw_extracted_at": raw.get("raw_extracted_at", now_iso()),
            # CandidateJob additions
            "job_hash": job_hash,
            "title_normalized": title_normalized,
            "company_normalized": company_normalized,
            "language": language,
            "passed_filters": kept,
            "filter_reason": filter_reason,
        }
        candidate_jobs.append(candidate)

    return candidate_jobs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Filter raw job listings into annotated CandidateJob records.",
    )
    parser.add_argument(
        "--input",
        required=True,
        metavar="RAW_JOBS_JSON",
        help="Path to a JSON file containing a list of RawJob dicts.",
    )
    parser.add_argument(
        "--output",
        required=True,
        metavar="CANDIDATE_JOBS_JSON",
        help="Path to write the filtered CandidateJob dicts as JSON.",
    )
    parser.add_argument(
        "--config",
        metavar="CONFIG_JSON",
        default=None,
        help="Optional path to job_tracker.json. Defaults to config/job_tracker.json in project root.",
    )
    args = parser.parse_args()

    config = load_jt_config(args.config)
    raw_jobs = load_json(args.input)
    results = filter_jobs(raw_jobs, config)
    save_json(results, args.output)

    kept = sum(1 for j in results if j["passed_filters"])
    print(f"Filtered {len(raw_jobs)} jobs → {kept} passed, {len(results) - kept} rejected. Written to {args.output}")
