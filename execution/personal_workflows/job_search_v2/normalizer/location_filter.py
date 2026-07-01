"""
description: Location filter for NormalizedJobs. Reads accept + reject patterns from
    config/job_search_v2.json and partitions jobs into (kept, rejected). The orchestrator
    calls this between dedup and notify so the daily digest only contains location-matching jobs.
inputs:
    - list[NormalizedJob]
    - config dict (loaded from config/job_search_v2.json) — optional, defaults to FR-locked
outputs:
    - (kept_jobs, rejected_count, by_reason: dict) — pure function, no I/O.

Why this exists: LinkedIn job-alert emails frequently surface non-FR roles (the user's
alerts default to "Senior PM" globally). Rejecting at notify time is gentler than
rejecting at source (the audit trail of "what we saw and dropped" stays intact in
the dedup DB and per-run JSONL).
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR.parent.parent.parent))

from execution.personal_workflows.job_search_v2.contracts import NormalizedJob  # noqa: E402
from execution.personal_workflows.job_search_v2.profile import loader as profile_loader  # noqa: E402

logger = logging.getLogger("normalizer.location_filter")

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "job_search_v2.json"


def load_config(path: Path = DEFAULT_CONFIG) -> dict:
    """Load the v2 config. Returns a sane FR-locked default if the file is missing."""
    if not path.exists():
        logger.warning("location_filter: config %s missing — falling back to FR-locked default", path)
        return {
            "target_locations": {
                "accept_patterns": ["paris", "île-de-france", "ile-de-france", "france", "remote (france)"],
                "reject_patterns_priority": [],
            }
        }
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("location_filter: failed to read %s (%s) — using FR-locked default", path, exc)
        return {
            "target_locations": {
                "accept_patterns": ["paris", "île-de-france", "ile-de-france", "france", "remote (france)"],
                "reject_patterns_priority": [],
            }
        }


def matches(haystack: str, accept: list[str], reject_priority: list[str]) -> tuple[bool, str]:
    """Return (kept, reason).

    Rule:
      1. If any reject_priority pattern matches → drop. Reason: 'reject:<pattern>'.
         (Priority because a job tagged 'Berlin, Germany' should not be saved by
         the word 'remote' co-occurring in the description.)
      2. Else if any accept pattern matches → keep. Reason: 'accept:<pattern>'.
      3. Else → drop. Reason: 'no_match'.
    """
    h = haystack.lower()

    for pat in reject_priority:
        if pat.lower() in h:
            return False, f"reject:{pat}"

    for pat in accept:
        if pat.lower() in h:
            return True, f"accept:{pat}"

    return False, "no_match"


def _profile_augmented_patterns(
    config_accept: list[str],
    config_reject: list[str],
) -> tuple[list[str], list[str]]:
    """Union the config-declared accept/reject patterns with profile.json's
    locations. Additive: config stays as the primary source, profile
    contributes extra terms so a profile edit propagates automatically.

    2026-07-01 pipeline-auditor gap: prior form read only from
    config/job_search_v2.json, silently ignoring profile.locations.preferred /
    ok_remote / blocked_countries. A profile change to add "Berlin remote" or
    block "United Kingdom" had zero effect unless the operator also updated
    the config JSON — two sources of truth, guaranteed to drift.
    """
    prof_preferred = profile_loader.get_preferred_locations()
    prof_ok_remote = profile_loader.get_ok_remote_locations()
    prof_blocked = profile_loader.get_blocked_countries()

    # Accept: union in a stable order; preserve config priority by putting
    # config patterns first.
    accept_seen: set[str] = set()
    accept_out: list[str] = []
    for p in list(config_accept) + prof_preferred + prof_ok_remote:
        key = p.strip().lower()
        if key and key not in accept_seen:
            accept_seen.add(key)
            accept_out.append(p)

    # Reject: union with the same dedup pattern.
    reject_seen: set[str] = set()
    reject_out: list[str] = []
    for p in list(config_reject) + prof_blocked:
        key = p.strip().lower()
        if key and key not in reject_seen:
            reject_seen.add(key)
            reject_out.append(p)

    return accept_out, reject_out


def filter_by_location(
    jobs: list[NormalizedJob],
    config: dict | None = None,
) -> tuple[list[NormalizedJob], dict]:
    """Partition jobs by location target. Returns (kept, stats).

    stats = {
        "total_in": int,
        "kept": int,
        "rejected": int,
        "by_reason": {"reject:germany": int, "no_match": int, ...}
    }

    Sources of truth (unioned):
      1. config/job_search_v2.json target_locations.{accept,reject}_patterns
      2. profile.json locations.{preferred, ok_remote, blocked_countries}
    """
    if config is None:
        config = load_config()

    tl = config.get("target_locations", {})
    config_accept = tl.get("accept_patterns", [])
    config_reject = tl.get("reject_patterns_priority", [])
    accept, reject = _profile_augmented_patterns(config_accept, config_reject)

    kept: list[NormalizedJob] = []
    by_reason: dict[str, int] = {}

    for job in jobs:
        # haystack = normalized location + first 300 chars of description.
        # The description often carries the city when location field is generic ("Île-de-France").
        haystack = f"{job.location} {job.description_snippet[:300]}"
        ok, reason = matches(haystack, accept, reject)
        by_reason[reason] = by_reason.get(reason, 0) + 1
        if ok:
            kept.append(job)

    stats = {
        "total_in": len(jobs),
        "kept": len(kept),
        "rejected": len(jobs) - len(kept),
        "by_reason": by_reason,
    }
    logger.info("location_filter: %s", stats)
    return kept, stats
