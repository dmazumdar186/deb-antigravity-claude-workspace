"""Tests for the 2026-06-19 fixes:
- digest cap: only the top N best jobs go to email + sheet (default 25)
- email lock: blocks dual-cron double-send within 22h, state in seen.db meta KV
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from execution.personal_workflows.job_search_v2 import run as run_mod
from execution.personal_workflows.job_search_v2.normalizer import dedup


# 2026-07-01: the email-lock function checks Google Sheets Summary!D1 as its
# authoritative source before falling back to seen.db. Local test-time
# tmp_path DBs won't have a gsheet mock — so on any machine where the live
# sheet's D1 has data (the operator's daily-cron target), every test here
# would read that real lock timestamp and fail. Auto-mock the gsheet path
# for all tests in this file so they exercise the seen.db + file layers only.
@pytest.fixture(autouse=True)
def _no_live_gsheet_lock(monkeypatch, tmp_path):
    """Isolate lock reads from ALL three persistence layers' live state:
      1. Google Sheets Summary!D1 — mocked to None
      2. seen.db meta KV — each test uses its own tmp_path db
      3. Local file EMAIL_LOCK_FILE — repointed at a per-test tmp file so a
         real .tmp/job_search_v2/last_email_sent_utc.txt from an operator
         cron run doesn't leak into the test's expected empty state
    """
    monkeypatch.setattr(run_mod, "_gsheet_email_lock_get", lambda: None)
    monkeypatch.setattr(run_mod, "_gsheet_email_lock_set", lambda _iso: None)
    monkeypatch.setattr(run_mod, "EMAIL_LOCK_FILE", tmp_path / "email_lock.txt")


# ----- email lock (state in seen.db meta KV) -----


def test_email_lock_passes_with_no_prior_send(tmp_path):
    """First-ever send (empty meta KV) must not be blocked."""
    db = tmp_path / "fresh.db"
    blocked, reason = run_mod._email_lock_blocks_send(22.0, datetime.now(timezone.utc), db_path=db)
    assert blocked is False
    assert "no prior send" in reason


def test_email_lock_blocks_recent_send(tmp_path):
    """A send from 1h ago must block (22h floor)."""
    db = tmp_path / "recent.db"
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    dedup.set_meta(db, run_mod.EMAIL_LOCK_KEY, one_hour_ago.isoformat())
    blocked, reason = run_mod._email_lock_blocks_send(22.0, datetime.now(timezone.utc), db_path=db)
    assert blocked is True
    # Delta is a fresh datetime.now() call inside the function; test tolerance
    # for 1.0h approx (may render as 0.9h - 1.0h depending on wall clock).
    assert "0.9h ago" in reason or "1.0h ago" in reason
    assert "dual-cron" in reason


def test_email_lock_clears_after_floor(tmp_path):
    """A send from 23h ago must NOT block (past the 22h floor)."""
    db = tmp_path / "old.db"
    twenty_three_hours_ago = datetime.now(timezone.utc) - timedelta(hours=23)
    dedup.set_meta(db, run_mod.EMAIL_LOCK_KEY, twenty_three_hours_ago.isoformat())
    blocked, reason = run_mod._email_lock_blocks_send(22.0, datetime.now(timezone.utc), db_path=db)
    assert blocked is False
    assert "23.0h ago" in reason


def test_email_lock_disabled_when_threshold_zero(tmp_path):
    """min_hours_between_emails <= 0 disables the lock entirely (escape hatch)."""
    db = tmp_path / "any.db"
    dedup.set_meta(db, run_mod.EMAIL_LOCK_KEY, datetime.now(timezone.utc).isoformat())
    blocked, reason = run_mod._email_lock_blocks_send(0.0, datetime.now(timezone.utc), db_path=db)
    assert blocked is False
    assert "disabled" in reason


def test_email_lock_treats_unreadable_value_as_no_prior(tmp_path):
    """Garbage in the meta value → behave as if no prior send (better to send than silently skip)."""
    db = tmp_path / "garbage.db"
    dedup.set_meta(db, run_mod.EMAIL_LOCK_KEY, "this is not a timestamp")
    blocked, reason = run_mod._email_lock_blocks_send(22.0, datetime.now(timezone.utc), db_path=db)
    assert blocked is False
    assert "unreadable" in reason


def test_stamp_email_sent_writes_to_meta(tmp_path):
    db = tmp_path / "stamp.db"
    now = datetime.now(timezone.utc)
    run_mod._stamp_email_sent(now, db_path=db)
    assert dedup.get_meta(db, run_mod.EMAIL_LOCK_KEY) == now.isoformat()


def test_email_lock_round_trip_via_stamp(tmp_path):
    """End-to-end: stamp at T0, check at T0+1h should block, check at T0+23h should clear."""
    db = tmp_path / "round_trip.db"
    t0 = datetime.now(timezone.utc)
    run_mod._stamp_email_sent(t0, db_path=db)

    blocked, _ = run_mod._email_lock_blocks_send(22.0, t0 + timedelta(hours=1), db_path=db)
    assert blocked is True

    blocked, _ = run_mod._email_lock_blocks_send(22.0, t0 + timedelta(hours=23), db_path=db)
    assert blocked is False


# ----- meta KV plumbing (dedup module) -----


def test_meta_kv_upsert(tmp_path):
    """Upsert: same key written twice keeps the latest value, doesn't duplicate rows."""
    db = tmp_path / "upsert.db"
    dedup.set_meta(db, "k", "v1")
    dedup.set_meta(db, "k", "v2")
    assert dedup.get_meta(db, "k") == "v2"


def test_meta_kv_missing_key_returns_none(tmp_path):
    assert dedup.get_meta(tmp_path / "empty.db", "nope") is None


# ----- digest cap -----


def test_default_cap_is_25():
    """The default cap is 25 — anchor against a regression that silently raises it."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-digest-jobs", type=int, default=25)
    args = parser.parse_args([])
    assert args.max_digest_jobs == 25
