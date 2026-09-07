"""
description: Offline tests for normalizer/state.py (seen.json dedup + email lock).
inputs: tmp_path fixtures only — no network, no real files outside pytest's tmp dir.
outputs: pytest assertions
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..normalizer.state import State
from ._helpers import make_normalized_job


def test_filter_new_and_mark_seen_roundtrip(tmp_path: Path) -> None:
    state = State(tmp_path)
    job = make_normalized_job(title="Sales Manager")

    assert state.filter_new([job]) == [job]

    state.mark_seen([job])
    state.save()

    reloaded = State(tmp_path)
    assert reloaded.filter_new([job]) == []


def test_save_is_atomic_and_readable(tmp_path: Path) -> None:
    state = State(tmp_path)
    job = make_normalized_job(title="Sales Manager")
    state.mark_seen([job])
    state.save()

    seen_path = tmp_path / "seen.json"
    assert seen_path.exists()
    data = json.loads(seen_path.read_text(encoding="utf-8"))
    assert job.content_hash in data
    # no leftover temp files from the atomic write
    assert not list(tmp_path.glob(".seen.json.*.tmp"))


def test_ttl_sweep_expires_old_entries(tmp_path: Path) -> None:
    state = State(tmp_path)
    old_hash = "a" * 64
    old_iso = (datetime.now(timezone.utc) - timedelta(days=61)).isoformat()
    (tmp_path / "seen.json").write_text(json.dumps({old_hash: old_iso}), encoding="utf-8")

    reloaded = State(tmp_path)
    reloaded.save(ttl_days=60)

    data = json.loads((tmp_path / "seen.json").read_text(encoding="utf-8"))
    assert old_hash not in data


def test_email_lock_ok_when_no_lock_file(tmp_path: Path) -> None:
    state = State(tmp_path)
    assert state.email_lock_ok(min_hours=20.0) is True


def test_email_lock_blocks_within_window_then_releases(tmp_path: Path) -> None:
    state = State(tmp_path)
    state.set_email_lock()

    assert state.email_lock_ok(min_hours=20.0) is False
    assert state.email_lock_ok(min_hours=0.0) is True

    # Simulate an old lock by writing a timestamp far in the past.
    old_iso = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    (tmp_path / "email_lock.txt").write_text(old_iso, encoding="utf-8")
    assert state.email_lock_ok(min_hours=20.0) is True
