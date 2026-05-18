"""
test_digest_window.py
description: Proves the 7-day digest window logic — jobs enter, stay visible, expire after
    mark_expired(), and re-inserting the same job_hash on day 8 does NOT reset first_seen_at
    or reactivate the status.
inputs: pytest tmp_path fixture; freezegun for time control.
outputs: pytest pass/fail.
"""

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
from freezegun import freeze_time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution.personal_workflows.job_tracker_db import (
    init_db,
    upsert_company,
    upsert_job,
    mark_expired,
    query_active_within_window,
)
from execution.personal_workflows._jt_utils import now_iso, normalize_company

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_DAY_0 = "2026-05-14T08:00:00+00:00"
_DAY_3 = "2026-05-17T08:00:00+00:00"
_DAY_8 = "2026-05-22T08:00:00+00:00"

_COMPANY = {
    "name": "TestCo SA",
    "name_normalized": normalize_company("TestCo SA"),
}

_JOB = {
    "job_hash": "abc123def456abc123def456abc123def456abc1",  # 40-char SHA-1-like
    "title": "Senior Product Manager",
    "title_normalized": "senior product manager",
    "location": "Paris, France",
    "language": "en",
    "board": "wttj",
    "source_url": "https://www.welcometothejungle.com/fr/jobs/test-pm",
    "description_snippet": "Lead the product vision for TestCo's core platform.",
}


def _make_db(tmp_path: Path) -> "sqlite3.Connection":
    """Return a fresh in-tmp-file DB (avoids :memory: isolation issues across connections)."""
    db_path = tmp_path / "test_job_tracker.db"
    return init_db(db_path), db_path


# ---------------------------------------------------------------------------
# Test 1 — Day 0: insert + query surfaces the job
# ---------------------------------------------------------------------------

def test_day0_insert_visible(tmp_path):
    """Insert a job on day 0; it should appear in a 7-day window query."""
    db_path = tmp_path / "jt.db"
    with freeze_time(_DAY_0):
        conn = init_db(db_path)
        company_id = upsert_company(conn, **_COMPANY)
        upsert_job(conn, company_id=company_id, **_JOB)
        rows = query_active_within_window(conn, 7)
        conn.close()

    assert len(rows) == 1, f"Expected 1 active job on day 0, got {len(rows)}"
    assert rows[0]["title"] == _JOB["title"]
    assert rows[0]["company_name"] == _COMPANY["name"]


# ---------------------------------------------------------------------------
# Test 2 — Day 3: job still in window
# ---------------------------------------------------------------------------

def test_day3_still_visible(tmp_path):
    """A job inserted on day 0 is still in the 7-day window on day 3."""
    db_path = tmp_path / "jt.db"

    with freeze_time(_DAY_0):
        conn = init_db(db_path)
        company_id = upsert_company(conn, **_COMPANY)
        upsert_job(conn, company_id=company_id, **_JOB)
        conn.close()

    with freeze_time(_DAY_3):
        conn = init_db(db_path)
        rows = query_active_within_window(conn, 7)
        conn.close()

    assert len(rows) == 1, f"Expected 1 active job on day 3, got {len(rows)}"


# ---------------------------------------------------------------------------
# Test 3 — Day 8: expired after mark_expired()
# ---------------------------------------------------------------------------

def test_day8_expired_after_mark(tmp_path):
    """After mark_expired() on day 8, a day-0 job falls outside the window → 0 rows."""
    db_path = tmp_path / "jt.db"

    with freeze_time(_DAY_0):
        conn = init_db(db_path)
        company_id = upsert_company(conn, **_COMPANY)
        upsert_job(conn, company_id=company_id, **_JOB)
        conn.close()

    with freeze_time(_DAY_8):
        conn = init_db(db_path)
        expired_count = mark_expired(conn, window_days=7)
        rows = query_active_within_window(conn, 7)
        conn.close()

    assert expired_count >= 1, "mark_expired() should have flipped at least 1 row"
    assert len(rows) == 0, f"Expected 0 active jobs after expiry on day 8, got {len(rows)}"


# ---------------------------------------------------------------------------
# Test 4 — Day 8: re-insert same job_hash (repost) keeps first_seen_at, stays expired
# ---------------------------------------------------------------------------

def test_day8_reinsert_same_hash_stays_expired(tmp_path):
    """Re-upserting the same job_hash on day 8 must not reset first_seen_at or reactivate."""
    db_path = tmp_path / "jt.db"

    with freeze_time(_DAY_0):
        conn = init_db(db_path)
        company_id = upsert_company(conn, **_COMPANY)
        upsert_job(conn, company_id=company_id, **_JOB)
        conn.close()

    with freeze_time(_DAY_8):
        conn = init_db(db_path)
        mark_expired(conn, window_days=7)

        # Re-upsert same hash (simulates same job reappearing on a board)
        job_id, is_new = upsert_job(conn, company_id=company_id, **_JOB)
        assert is_new is False, "Re-upsert of existing job_hash must return is_new=False"

        # first_seen_at must still be day 0, not day 8
        row = conn.execute(
            "SELECT first_seen_at, status, last_seen_at FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()

        assert row["first_seen_at"].startswith("2026-05-14"), (
            f"first_seen_at was reset — expected 2026-05-14…, got {row['first_seen_at']}"
        )
        # status stays 'expired' — upsert_job only updates last_seen_at, not status
        assert row["status"] == "expired", (
            f"Status should remain 'expired' after re-upsert, got '{row['status']}'"
        )
        # last_seen_at should be day 8
        assert row["last_seen_at"].startswith("2026-05-22"), (
            f"last_seen_at not updated to day 8: {row['last_seen_at']}"
        )

        # Query should still return 0 (job is expired)
        rows = query_active_within_window(conn, 7)
        conn.close()

    assert len(rows) == 0, "Expired re-upserted job must not appear in window query"


# ---------------------------------------------------------------------------
# Test 5 — Two jobs same company both surface on day 0
# ---------------------------------------------------------------------------

def test_two_jobs_same_company_both_visible(tmp_path):
    """Two jobs at the same company share a company_id and both appear in the digest window."""
    db_path = tmp_path / "jt.db"

    job_a = {**_JOB, "job_hash": "aaaaaa1111111111111111111111111111111111", "title": "Senior PM", "title_normalized": "senior pm"}
    job_b = {
        **_JOB,
        "job_hash": "bbbbbb2222222222222222222222222222222222",
        "title": "Senior Product Owner",
        "title_normalized": "senior product owner",
        "source_url": "https://www.welcometothejungle.com/fr/jobs/test-po",
    }

    with freeze_time(_DAY_0):
        conn = init_db(db_path)
        company_id = upsert_company(conn, **_COMPANY)

        id_a, new_a = upsert_job(conn, company_id=company_id, **job_a)
        id_b, new_b = upsert_job(conn, company_id=company_id, **job_b)

        assert new_a is True
        assert new_b is True

        # Both should share the same company_id
        row_a = conn.execute("SELECT company_id FROM jobs WHERE id = ?", (id_a,)).fetchone()
        row_b = conn.execute("SELECT company_id FROM jobs WHERE id = ?", (id_b,)).fetchone()
        assert row_a["company_id"] == row_b["company_id"] == company_id, (
            "Both jobs must reference the same company_id"
        )

        rows = query_active_within_window(conn, 7)
        conn.close()

    assert len(rows) == 2, f"Expected 2 active jobs for same company, got {len(rows)}"
    company_ids = {r["company_id"] for r in rows}
    assert company_ids == {company_id}, "Both rows must share a single company_id"
