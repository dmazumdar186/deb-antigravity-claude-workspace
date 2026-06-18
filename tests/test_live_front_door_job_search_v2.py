"""Unit tests for tests/live_front_door_job_search_v2.py — the evaluator must
reject runs below the floor, accept runs above it, and refuse to grade fixture-only
or stale data as 'live green' per the 2026-06-18 front-door tightening.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import importlib.util
import sys
from pathlib import Path

# Load the module by file path (no package).
_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "live_front_door_job_search_v2",
    _HERE / "live_front_door_job_search_v2.py",
)
mod = importlib.util.module_from_spec(_spec)
sys.modules["live_front_door_job_search_v2"] = mod
_spec.loader.exec_module(mod)


def _run(run_id_dt: datetime, total: int, per_source: dict, mode: str = "live") -> dict:
    return {
        "run_id": run_id_dt.strftime("%Y%m%dT%H%M%S") + "-abcdef",
        "mode": mode,
        "total_fetched": total,
        "per_source": per_source,
    }


def test_pass_when_floor_cleared():
    now = datetime.now(timezone.utc)
    runs = [_run(now, total=300, per_source={"france_travail": 2, "wttj_algolia": 200, "linkedin_guest_api": 98})]
    ok, _ = mod.evaluate(runs, fetch_floor=5, nonzero_sources_floor=2, max_age_hours=25, window=1)
    assert ok is True


def test_fail_when_total_fetched_below_floor():
    now = datetime.now(timezone.utc)
    runs = [_run(now, total=3, per_source={"france_travail": 2, "wttj_algolia": 1})]
    ok, lines = mod.evaluate(runs, fetch_floor=5, nonzero_sources_floor=2, max_age_hours=25, window=1)
    assert ok is False
    assert any("total_fetched=3 < floor=5" in l for l in lines)


def test_fail_when_single_source_carries_everything():
    """non_zero_sources floor catches the "1 source returns 300, all others return 0"
    failure mode that masks source-mix collapse."""
    now = datetime.now(timezone.utc)
    runs = [_run(now, total=300, per_source={"wttj_algolia": 300, "linkedin_guest_api": 0, "france_travail": 0})]
    ok, lines = mod.evaluate(runs, fetch_floor=5, nonzero_sources_floor=2, max_age_hours=25, window=1)
    assert ok is False
    assert any("non_zero_sources=1 < floor=2" in l for l in lines)


def test_fail_when_no_live_runs_in_log():
    """A run log with only fixture runs MUST NOT grade green — the rule was born
    specifically because fixture-only synthetics misled the operator."""
    now = datetime.now(timezone.utc)
    runs = [_run(now, total=999, per_source={"france_travail": 999}, mode="fixture")]
    ok, lines = mod.evaluate(runs, fetch_floor=5, nonzero_sources_floor=2, max_age_hours=25, window=1)
    assert ok is False
    assert any("no live runs" in l for l in lines)


def test_fail_when_most_recent_live_is_stale():
    """A cron that hasn't fired in > max_age_hours → DEGRADED (cron may have stopped)."""
    two_days_ago = datetime.now(timezone.utc) - timedelta(hours=50)
    runs = [_run(two_days_ago, total=300, per_source={"a": 200, "b": 100})]
    ok, lines = mod.evaluate(runs, fetch_floor=5, nonzero_sources_floor=2, max_age_hours=25, window=1)
    assert ok is False
    assert any("Cron may have stopped" in l for l in lines)


def test_window_evaluates_multiple_recent_runs():
    """window > 1 checks the last N runs; one failing run is enough to fail the whole check."""
    now = datetime.now(timezone.utc)
    runs = [
        _run(now - timedelta(hours=1), total=300, per_source={"a": 200, "b": 100}),
        _run(now, total=2, per_source={"a": 2}),  # below floor
    ]
    ok, _ = mod.evaluate(runs, fetch_floor=5, nonzero_sources_floor=2, max_age_hours=25, window=2)
    assert ok is False


def test_empty_run_log_is_degraded_not_crash():
    ok, lines = mod.evaluate([], fetch_floor=5, nonzero_sources_floor=2, max_age_hours=25, window=1)
    assert ok is False
    assert any("no live runs" in l for l in lines)
