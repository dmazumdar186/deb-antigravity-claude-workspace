"""
description: Title filter for NormalizedJobs. Drops jobs whose title indicates
    Project Management (not Product), apprenticeships, internships, or junior/
    graduate gates that the operator's PM-search keywords leak in via fuzzy match.
inputs:
    - list[NormalizedJob]
outputs:
    - (kept, stats) where stats = {requested, kept, rejected, by_reason}

Why this exists: LinkedIn's jobs-guest search fuzzy-matches "product manager"
to "project manager"; WTTJ's Algolia index leaks "Alternance Product Manager"
into the FR results. The operator does NOT want those rows. Doing the reject
HERE (between dedup and location) means the dedup DB still records them so they
don't keep re-surfacing, but they never reach the sheet or digest.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR.parent.parent.parent))

from execution.personal_workflows.job_search_v2.contracts import NormalizedJob  # noqa: E402

logger = logging.getLogger("normalizer.title_filter")

# Substring matches (NOT word-boundary) so "AI Project Manager" or "Project
# Manager (Junior)" both trip. Lowercased before match.
REJECT_SUBSTRINGS: dict[str, list[str]] = {
    "project_manager": [
        "project manager", "project management",
        "chef de projet", "chef de projets",
        "projektmanager", "projekt manager", "projektleiter",
        "projectmanager", "project leider",
    ],
    "internship_or_alternance": [
        "alternance", "apprenti", "apprentice", "apprenticeship",
        "stagiaire", "stage h/f", "stage f/h", "stage de fin",
        "internship", "intern -", "intern,", "intern (",
        "praktikum", "werkstudent",
        "stagista",
    ],
    "junior_or_graduate": [
        "graduate program", "graduate trainee", "trainee program",
        "junior product manager",
    ],
}

# Tokens that ALWAYS keep the job even if a bad substring matched. Example: if
# the title is "Product Manager / Project Manager", we want to keep it — the
# real role IS Product, and the cross-listing of project is incidental. But:
# "Alternance Product Manager" is rejected outright — alternance is a hard
# contract-type override the operator doesn't want regardless.
PRODUCT_RESCUE_TOKENS = [
    "product manager", "senior product manager", "lead product manager",
    "principal product manager", "staff product manager",
    "head of product", "vp product", "vp of product",
    "chief product officer",
    "chef de produit", "directeur produit", "directrice produit",
    "produktmanager", "productmanager",
    "responsable produit", "product owner", "product lead",
    "ai product manager", "ai/ml product manager",
    "generative ai product manager", "genai product manager",
    "ml product manager",
    # AI-engineering titles operator explicitly tracks in dedicated tabs.
    "ai automation engineer", "ai automation specialist",
    "ai automation consultant", "automation product manager",
    "ai mobile", "mobile ai engineer", "mobile ai developer",
    "ai process automation", "process automation ai",
    "ai consultant", "ai strategy consultant",
    "ai transformation consultant", "ai solutions consultant",
    "ai advisor",
]

# Reasons that CANNOT be rescued (override the PRODUCT_RESCUE rule). The
# operator doesn't want apprenticeship/internship contracts even if the role
# title also says "Product Manager".
HARD_REJECT_REASONS = {"internship_or_alternance", "junior_or_graduate"}


def classify_title(title: str) -> tuple[bool, str]:
    """Return (kept, reason). reason='accept' if kept, else 'reject:<reason_key>'."""
    t = (title or "").lower().strip()
    if not t:
        return False, "reject:empty_title"

    hit_reason: str | None = None
    for reason, substrs in REJECT_SUBSTRINGS.items():
        for s in substrs:
            if s in t:
                hit_reason = reason
                break
        if hit_reason:
            break

    if hit_reason is None:
        return True, "accept"

    # Apprenticeship / internship reasons are never rescued.
    if hit_reason in HARD_REJECT_REASONS:
        return False, f"reject:{hit_reason}"

    # For project_manager / junior_or_graduate: rescue if the title ALSO
    # carries a clear PM/AI-role token.
    for rescue in PRODUCT_RESCUE_TOKENS:
        if rescue in t and rescue not in ("project manager", "project management"):
            return True, "accept:rescued"

    return False, f"reject:{hit_reason}"


def filter_by_title(jobs: list[NormalizedJob]) -> tuple[list[NormalizedJob], dict]:
    """Partition jobs by title classifier. Returns (kept, stats).

    stats = {
        "requested": int,
        "kept": int,
        "rejected": int,
        "by_reason": {"project_manager": int, ...}
    }
    """
    kept: list[NormalizedJob] = []
    by_reason: dict[str, int] = {}
    for job in jobs:
        ok, reason = classify_title(job.title)
        # Track by short reason key (strip the "reject:" / "accept:" prefix).
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
    logger.info("title_filter: %s", stats)
    return kept, stats
