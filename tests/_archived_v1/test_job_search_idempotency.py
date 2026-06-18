"""
Unit tests for the Stage 0 idempotency helper: already_ran_today_utc().

Verifies the design switch from a 23h sliding window to a calendar-day check.
The calendar-day check still blocks the dual 07:00+08:00 UTC cron pair from
double-running, but releases the lock at UTC midnight so a manual mid-day run
doesn't silently block the next day's scheduled cron.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from execution.personal_workflows.job_search_sheet import already_ran_today_utc  # noqa: E402


def _utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def test_none_last_run_proceeds():
    """No prior run recorded → not 'already ran today' → proceed."""
    now = _utc(2026, 6, 10, 7, 0, 0)
    assert already_ran_today_utc(None, now) is False


def test_same_utc_day_blocks_dual_cron():
    """Real scenario: 07:00 UTC ran, 08:00 UTC must skip — same UTC date."""
    first_run = _utc(2026, 6, 10, 7, 0, 5)
    second_run = _utc(2026, 6, 10, 8, 0, 5)
    assert already_ran_today_utc(first_run, second_run) is True


def test_next_utc_day_proceeds_even_if_under_23h():
    """The 23h-sliding-window bug we fixed: manual run Day-N 22:00 UTC then
    Day-N+1 07:00 UTC scheduled cron. Only 9h elapsed, but it's a NEW UTC day,
    so the cron MUST run. Old window check would have skipped this."""
    last = _utc(2026, 6, 9, 22, 0, 0)
    now = _utc(2026, 6, 10, 7, 0, 0)
    assert (now - last) < timedelta(hours=23)  # confirms old check would have blocked
    assert already_ran_today_utc(last, now) is False


def test_manual_midday_does_not_block_next_day_cron():
    """The exact bug from prod: manual run at 16:43 UTC, next cron 07:00 UTC
    (14:17h later). Under 23h → old check would skip. New check: different
    UTC day → runs."""
    last = _utc(2026, 6, 9, 16, 43, 0)
    next_cron = _utc(2026, 6, 10, 7, 0, 0)
    assert already_ran_today_utc(last, next_cron) is False


def test_run_seconds_before_utc_midnight_then_just_after():
    """Boundary: 23:59:59 UTC vs 00:00:01 UTC next day — separate UTC dates."""
    last = _utc(2026, 6, 9, 23, 59, 59)
    now = _utc(2026, 6, 10, 0, 0, 1)
    assert already_ran_today_utc(last, now) is False


def test_many_days_ago_proceeds():
    """No matter how stale, different UTC date → proceed."""
    last = _utc(2026, 1, 1, 12, 0, 0)
    now = _utc(2026, 6, 10, 12, 0, 0)
    assert already_ran_today_utc(last, now) is False


def test_same_instant_blocks():
    """Edge case: exact same timestamp (would be the run itself). Same date → True."""
    when = _utc(2026, 6, 10, 7, 0, 0)
    assert already_ran_today_utc(when, when) is True
