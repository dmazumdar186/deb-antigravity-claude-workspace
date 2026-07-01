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
import re
import sys
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR.parent.parent.parent))

from execution.personal_workflows.job_search_v2.contracts import NormalizedJob  # noqa: E402
from execution.personal_workflows.job_search_v2.profile import loader as profile_loader  # noqa: E402

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

# Word-boundary intern matcher. Catches "Intern", "Interns", "Internship(s)"
# anywhere in the title — suffix ("AI Automation Intern"), parenthetical
# ("AI Engineer (Intern)"), or prefix ("Intern - Product"). The \b guards make
# sure "internal", "international", "alternance" do NOT trip it (audit
# 2026-06-24: bare-substring "intern" matched "internal"; bare "internship"
# missed "Intern" at end-of-title). This regex closes both gaps.
_INTERN_RE = re.compile(r"\bintern(s|ship|ships)?\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# RELEVANCE ALLOWLIST (2026-06-24 — the core fix)
#
# The prior filter was REJECT-ONLY: it blocked known-bad words and let
# EVERYTHING else through to the fallback PM tab. That is why "Consultant
# Cybersécurité", "Directeur SEO", "Chef de mission comptable" (accounting),
# "Property & Facility Manager", "Directeur de projet SI" all landed in the
# PM tab — none of them contain a banned word.
#
# A job must now POSITIVELY match one of Debanjan's two tracks (from CV +
# Malt + GitHub) or it is rejected as `not_relevant`. These are lowercased
# substring anchors; each is specific enough that a generic role word alone
# ("consultant", "directeur", "manager", "engineer") does NOT pass — it must
# be paired with a product/AI/automation domain.
# ---------------------------------------------------------------------------
RELEVANCE_ANCHORS = [
    # --- Track A: Product Management ---
    "product manager", "product owner", "product lead", "lead product",
    "head of product", "product director", "director of product",
    "vp product", "vp of product", "chief product", "cpo",
    "product management", "group product manager", "staff product manager",
    "principal product manager", "senior product manager",
    "chef de produit", "responsable produit", "directeur produit",
    "directrice produit", "gestionnaire de produit", "directeur de produit",
    # --- Track A: AI-flavoured PM ---
    "ai product", "ai pm", "genai product", "llm product", "ml product",
    "machine learning product", "ai/ml product",
    "product manager ai", "product manager - ai", "product manager (ai",
    # --- Track B: AI automation / builder / consultant ---
    "ai automation", "automatisation ia", "ai engineer", "ai consultant",
    "consultant ia", "consultant ai", "ai developer", "ai builder",
    "ai architect", "ai solutions", "ai specialist", "ai lead", "head of ai",
    "machine learning engineer", "ml engineer", "mlops", "llm engineer",
    "generative ai", "prompt engineer", "ingénieur ia", "ingenieur ia",
    # --- Track B: mobile / Claude Code ---
    "react native", "claude code", "mobile ai",
]


def _profile_targeted_title_substrings() -> list[str]:
    """profile.json Track A + B targeted_titles, unioned with RELEVANCE_ANCHORS.

    Additive: hardcoded RELEVANCE_ANCHORS stays as the fallback layer; the
    profile-derived list is unioned on top. Any title in profile.json is
    automatically accepted, closing the sync gap the 2026-07-01 pipeline-
    auditor flagged (profile said "Fractional AI Builder", filter didn't).
    """
    return profile_loader.get_targeted_title_substrings()


def _profile_hard_reject_substrings() -> list[str]:
    """profile.hard_filters.skip_title_substrings + Track A/B anti_titles.

    These override the relevance allowlist — a title that matches ANY of
    these gets rejected regardless of whether it also matches a targeted
    title. Prevents "Junior AI Product Manager" from being rescued by the
    "AI Product Manager" anchor when the operator's profile says junior
    is hard-reject.
    """
    return profile_loader.get_hard_filter_titles() + profile_loader.get_anti_title_substrings()


def _has_relevance_anchor(t: str) -> bool:
    # Union: hardcoded anchors + profile-declared targeted_titles.
    if any(a in t for a in RELEVANCE_ANCHORS):
        return True
    for anchor in _profile_targeted_title_substrings():
        if anchor in t:
            return True
    return False


def classify_title(title: str) -> tuple[bool, str]:
    """Return (kept, reason). reason='accept...' if kept, else 'reject:<reason_key>'.

    Two-gate logic:
      1. Hard reject (internship/alternance/junior) — overrides everything.
      2. Relevance allowlist — the title MUST positively match one of the two
         tracks, otherwise reject as `not_relevant`. This is what stops
         accounting / SEO / cybersecurity / facilities roles from leaking into
         the PM fallback tab.
      3. Project-manager exclusion — if the title says "project manager"
         (≠ product) AND has no other relevance anchor, reject.
    """
    t = (title or "").lower().strip()
    if not t:
        return False, "reject:empty_title"

    # Gate 1: hard rejects (contract-type / seniority) override everything.
    # Intern check uses a word-boundary regex (not substring) so it catches
    # "Intern" as a suffix / parenthetical without matching "internal".
    if _INTERN_RE.search(t):
        return False, "reject:internship_or_alternance"
    for reason, substrs in REJECT_SUBSTRINGS.items():
        if reason not in HARD_REJECT_REASONS:
            continue
        if any(s in t for s in substrs):
            return False, f"reject:{reason}"

    # Gate 1b: profile-driven hard rejects. Any substring the operator
    # explicitly listed in hard_filters.skip_title_substrings OR any track's
    # anti_titles wins over the relevance allowlist.
    #
    # Word-boundary match: short profile terms like "intern" and "junior"
    # otherwise trip on "International" / "junior-friendly" — the same class
    # the built-in _INTERN_RE guards against for the hardcoded intern check.
    # Multi-word phrases ("chef de projet", "graduate program") are matched
    # as literal substrings since they're already distinctive.
    for hard in _profile_hard_reject_substrings():
        if not hard:
            continue
        if " " in hard:
            # Multi-word phrase — literal substring match is safe.
            if hard in t:
                return False, f"reject:profile_hard:{hard[:30]}"
        else:
            # Single word — require word boundary. Escape regex special chars.
            if re.search(rf"\b{re.escape(hard)}\b", t):
                return False, f"reject:profile_hard:{hard[:30]}"

    has_anchor = _has_relevance_anchor(t)

    # Gate 3: project-manager exclusion. "AI Project Manager" / "Chef de
    # projet" are a different role. Reject UNLESS a genuine product/AI anchor
    # also appears (e.g. "Product Manager / Project Manager").
    pm_project_hit = any(s in t for s in REJECT_SUBSTRINGS["project_manager"])
    if pm_project_hit and not has_anchor:
        return False, "reject:project_manager"

    # Gate 2: relevance allowlist. No anchor → not his profile.
    if not has_anchor:
        return False, "reject:not_relevant"

    return True, ("accept:rescued" if pm_project_hit else "accept")


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
