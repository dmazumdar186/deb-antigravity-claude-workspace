"""
description: Single source of truth for profile.json. All screens (title,
    contract, language, location filters) read from THIS module so a profile
    edit propagates everywhere automatically. Prior form: each filter had a
    hardcoded list that could silently drift from profile.json (audit
    2026-07-01 pipeline-auditor exhibit: profile listed "Fractional AI
    Builder" but title_filter's RELEVANCE_ANCHORS did not, so the pipeline
    silently dropped every job matching that profile-declared title).

inputs:
    - execution/personal_workflows/job_search_v2/profile/profile.json

outputs (via getter functions — cached at import time):
    - get_targeted_title_substrings() -> list[str]  (lowercased)
    - get_anti_title_substrings()     -> list[str]  (lowercased)
    - get_hard_filter_titles()        -> list[str]  (lowercased)
    - get_hard_filter_descriptions()  -> list[str]  (lowercased)
    - get_accepted_contract_labels()  -> set[str]   (lowercased)
    - get_preferred_locations()       -> list[str]  (lowercased)
    - get_ok_remote_locations()       -> list[str]  (lowercased)
    - get_blocked_countries()         -> list[str]  (lowercased)
    - get_profile_age_days()          -> int | None

Caching: profile.json is read ONCE at import and cached in a module-level
dict. Test hooks can force a reload via reset_cache() if needed.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("profile_loader")

PROFILE_PATH = Path(__file__).resolve().parent / "profile.json"

# Sentinel meaning "profile hasn't been loaded yet."
_CACHE: dict | None = None


def _load() -> dict:
    """Read profile.json once, cache the result. Returns {} on any failure so
    downstream getters return empty lists rather than crashing — the pipeline
    stays operational on the hardcoded fallbacks in each filter."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    if not PROFILE_PATH.exists():
        logger.warning("profile_loader: %s missing — every getter returns empty; filters fall back to hardcoded lists.", PROFILE_PATH)
        _CACHE = {}
        return _CACHE
    try:
        _CACHE = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("profile_loader: %s unreadable (%s) — every getter returns empty.", PROFILE_PATH, exc)
        _CACHE = {}
    return _CACHE


def reset_cache() -> None:
    """Force the next _load() to re-read the file. For tests only."""
    global _CACHE
    _CACHE = None


def get_targeted_title_substrings() -> list[str]:
    """Union of Track A + Track B targeted_titles, lowercased, whitespace-
    stripped. These are additive to each filter's hardcoded RELEVANCE list —
    any title in profile.json is guaranteed to be accepted by title_filter.
    """
    data = _load()
    out: list[str] = []
    for track in data.get("tracks", []) or []:
        for t in track.get("targeted_titles", []) or []:
            s = (t or "").strip().lower()
            if s:
                out.append(s)
    return out


def get_anti_title_substrings() -> list[str]:
    """Union of Track A + Track B anti_titles, lowercased. These are
    additive to each filter's hardcoded REJECT list."""
    data = _load()
    out: list[str] = []
    for track in data.get("tracks", []) or []:
        for t in track.get("anti_titles", []) or []:
            s = (t or "").strip().lower()
            if s:
                out.append(s)
    return out


def get_hard_filter_titles() -> list[str]:
    """profile.hard_filters.skip_title_substrings — always-reject regardless
    of track. Applied before the relevance allowlist."""
    data = _load()
    hf = data.get("hard_filters", {}) or {}
    return [s.lower() for s in hf.get("skip_title_substrings", []) or [] if s]


def get_hard_filter_descriptions() -> list[str]:
    """profile.hard_filters.skip_description_substrings — always-reject if
    the description contains any of these."""
    data = _load()
    hf = data.get("hard_filters", {}) or {}
    return [s.lower() for s in hf.get("skip_description_substrings", []) or [] if s]


def get_accepted_contract_labels() -> set[str]:
    """Union of Track A + Track B contract_types, lowercased. Used by
    contract_filter to broaden acceptance beyond the ContractType enum's
    {CDI, CDD, FREELANCE} — profile also accepts Fractional / Advisory /
    Mission / Contract / Indépendant, which the enum maps to UNKNOWN.
    """
    data = _load()
    out: set[str] = set()
    for track in data.get("tracks", []) or []:
        for c in track.get("contract_types", []) or []:
            s = (c or "").strip().lower()
            if s:
                out.add(s)
    return out


def get_preferred_locations() -> list[str]:
    """profile.locations.preferred, lowercased."""
    data = _load()
    locs = data.get("locations", {}) or {}
    return [s.lower() for s in locs.get("preferred", []) or [] if s]


def get_ok_remote_locations() -> list[str]:
    """profile.locations.ok_remote, lowercased."""
    data = _load()
    locs = data.get("locations", {}) or {}
    return [s.lower() for s in locs.get("ok_remote", []) or [] if s]


def get_blocked_countries() -> list[str]:
    """profile.locations.blocked_countries, lowercased."""
    data = _load()
    locs = data.get("locations", {}) or {}
    return [s.lower() for s in locs.get("blocked_countries", []) or [] if s]


def get_profile_age_days() -> int | None:
    """How stale is profile.json? Returns None if generated_at is missing.
    Used by acceptance gate to WARN when the profile is older than 60 days —
    the ranker is optimizing for the operator's PRIOR preferences."""
    data = _load()
    gen = data.get("generated_at")
    if not gen:
        return None
    try:
        dt = datetime.fromisoformat(gen.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        return max(0, delta.days)
    except (ValueError, TypeError):
        return None
