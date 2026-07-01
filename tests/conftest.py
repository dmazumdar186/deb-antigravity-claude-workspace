"""
conftest.py
Pytest configuration for the AntiGravity Project Space test suite.
Inserts the project root into sys.path so that execution.* imports resolve
when tests are run from the project root or from the tests/ directory.

Also exposes a shared `skip_if_youtube_blocked()` helper for YT-analyzer
tests (yt-dlp anti-bot blocks are environmental — must skip, not fail).
"""

import sys
from pathlib import Path

# Project root is one level above this file (tests/ -> project_root/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# 2026-07-01: exclude legacy tests from collection. tests/_archived_v1/*
# import from execution/personal_workflows/job_search/ (v1, deleted when v2
# replaced it in 2026-06). Kept in-tree as historical audit only.
collect_ignore_glob = ["_archived_v1/*"]


_YT_BLOCK_MARKERS = (
    "Sign in to confirm",
    "exporting youtube cookies",
    "HTTP Error 429",
    "Sign in to verify",
    "Please sign in",
    "confirm you're not a bot",
    "ERROR: [youtube]",
    "Unable to download webpage",
    "Got error: <urlopen error",
    "Failed to extract any player",
    "This video is unavailable",
)


def skip_if_youtube_blocked(stderr):
    """If stderr looks like a yt-dlp anti-bot / rate-limit, skip the test.

    Cumulative blocking under a full pytest session also surfaces as exit code 1
    without a recognizable marker — under that condition, the YT_LIVE=1 gate
    (see _skip_if_no_yt_live) is the senior-engineer default to keep CI green
    without masking real bugs.
    """
    import pytest
    if not stderr:
        return
    low = stderr.lower()
    for m in _YT_BLOCK_MARKERS:
        if m.lower() in low:
            pytest.skip(f"yt-dlp blocked by YouTube (environmental): {m}")


def _skip_if_no_yt_live():
    """Module-level gate for YT-live tests. Opt-in via env: YT_LIVE=1."""
    import os
    import pytest
    if os.environ.get("YT_LIVE", "") != "1":
        pytest.skip("YT_LIVE!=1 — yt-dlp/YouTube live path is environmental; set YT_LIVE=1 to exercise")


def skip_if_upstream_exhausted(exc):
    """Convert known free-tier-quota / no-credits exceptions into pytest skips."""
    import pytest
    s = str(exc)
    markers = (
        "RESOURCE_EXHAUSTED",
        "exceeded your current quota",
        "Insufficient credits",
        "402",
        "free_tier_requests",
        "rate limit",
        "Quota exceeded",
    )
    low = s.lower()
    for m in markers:
        if m.lower() in low:
            pytest.skip(f"upstream quota/credits exhausted (environmental): {m}")
