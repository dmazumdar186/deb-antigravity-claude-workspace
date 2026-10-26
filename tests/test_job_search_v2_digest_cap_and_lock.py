"""Tests for the 2026-06-19 fixes:
- digest cap: --max-digest-jobs defaults to 0 = unlimited (2026-10-26: every new job is a row)
- digest body: ONE table (Company | Job title | Location | Link) and nothing else
- email lock: blocks dual-cron double-send within 22h, state in seen.db meta KV
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from execution.personal_workflows.job_search_v2 import run as run_mod
from execution.personal_workflows.job_search_v2.contracts import (
    ContractType, JobSource, JobTier, NormalizedJob, RankedJob, RemoteMode,
)
from execution.personal_workflows.job_search_v2.normalizer import dedup
from execution.personal_workflows.job_search_v2.notifier import email as email_mod


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


def test_default_cap_is_unlimited():
    """2026-10-26 operator order: the table lists EVERY new job. Default 0 = no cap."""
    import argparse
    import inspect
    src = inspect.getsource(run_mod.main)
    assert '"--max-digest-jobs", type=int, default=0' in src
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-digest-jobs", type=int, default=0)
    assert parser.parse_args([]).max_digest_jobs == 0


# ----- digest body: one table, nothing else -----


def _job(title, company, url, location="Paris", source_id="1"):
    return NormalizedJob(
        source=JobSource.WTTJ,
        source_id=source_id,
        url=url,
        canonical_url=url,
        title=title,
        company=company,
        location=location,
        description_snippet="",
        posted_at=None,
        contract_type=ContractType.CDI,
        remote_mode=RemoteMode.UNKNOWN,
        fetched_at=datetime.now(timezone.utc),
        content_hash=hashlib.sha256(source_id.encode()).hexdigest(),
        fingerprint="",
    )


def _ranked(job, score):
    return RankedJob(
        content_hash=job.content_hash, score=score, tier=JobTier.B,
        reasoning="t", rubric_version="t", ranker_model="t",
    )


@pytest.fixture
def three_jobs():
    jobs = [
        _job("Product Manager", "Acme", "https://example.com/jobs/1", "Paris", "1"),
        _job("Senior PM", "Globex", "https://example.com/jobs/2?utm=x", "Lyon", "2"),
        _job("AI Product Owner", "Initech", "https://example.com/jobs/3", "Remote", "3"),
    ]
    ranked = {j.content_hash: _ranked(j, s) for j, s in zip(jobs, (0.4, 0.9, 0.7))}
    return jobs, ranked


def test_plain_body_is_exactly_one_table(three_jobs):
    jobs, ranked = three_jobs
    subject, body = email_mod.build_digest(jobs, {}, "sheet-id", ranked_by_hash=ranked)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert subject == f"Job Search — 3 new jobs for {today}"
    lines = body.splitlines()
    assert lines[0] == "| Company | Job title | Location | Link |"
    assert lines[1] == "| --- | --- | --- | --- |"
    rows = lines[2:]
    assert len(rows) == 3
    # zero non-table lines: every line is a pipe row
    assert all(ln.startswith("| ") and ln.endswith(" |") for ln in lines)
    assert all(ln.strip() for ln in lines)
    for junk in ("Top 5", "Per source", "Tier breakdown", "Full sheet", "Verification", "sheet-id"):
        assert junk not in body
    # sorted by score desc: Globex 0.9, Initech 0.7, Acme 0.4
    assert [r.split(" | ")[0].lstrip("| ") for r in rows] == ["Globex", "Initech", "Acme"]
    assert "https://example.com/jobs/2?utm=x" in rows[0]


def test_html_body_is_exactly_one_table(three_jobs):
    jobs, ranked = three_jobs
    _, _, html_body = email_mod.build_message(jobs, ranked_by_hash=ranked)
    assert html_body.count("<table") == 1 and html_body.count("</table>") == 1
    assert html_body.strip().startswith("<table") and html_body.strip().endswith("</table>")
    assert html_body.count("<th>") == 4
    for h in ("Company", "Job title", "Location", "Link"):
        assert f"<th>{h}</th>" in html_body
    assert html_body.count("<tr>") == 4  # header + 3 rows
    assert '<a href="https://example.com/jobs/2?utm=x">example.com/jobs/2</a>' in html_body


def test_pipe_in_company_name_is_escaped_and_html_escaped():
    j = _job("PM <Data>", "Foo | Bar & Co", "https://example.com/j/1", "Paris\n  Nord", "1")
    _, body, html_body = email_mod.build_message([j])
    rows = body.splitlines()[2:]
    assert len(rows) == 1
    assert "Foo \\| Bar & Co" in rows[0]
    assert rows[0].count(" | ") == 3  # still exactly four cells
    assert "Paris Nord" in rows[0]
    assert "Foo | Bar &amp; Co" in html_body
    assert "PM &lt;Data&gt;" in html_body


def test_zero_jobs_sends_no_email(monkeypatch):
    monkeypatch.setenv("GMAIL_SMTP_USER", "u@example.com")
    monkeypatch.setenv("GMAIL_SMTP_APP_PASSWORD", "pw")
    monkeypatch.setenv("GMAIL_NOTIFY_TO", "u@example.com")

    def _boom(*_a, **_k):
        raise AssertionError("SMTP must not be contacted when n == 0")

    monkeypatch.setattr(email_mod.smtplib, "SMTP", _boom)
    stats = {}
    sent, subject, body = email_mod.send_digest([], stats, dry_run=False)
    assert sent is False
    assert stats["email_skipped"] == "no new jobs"
    assert subject.startswith("Job Search — 0 new jobs for ")
    assert body.splitlines()[2:] == []


def test_send_builds_multipart_alternative(three_jobs, monkeypatch):
    jobs, ranked = three_jobs
    monkeypatch.setenv("GMAIL_SMTP_USER", "u@example.com")
    monkeypatch.setenv("GMAIL_SMTP_APP_PASSWORD", "pw")
    monkeypatch.setenv("GMAIL_NOTIFY_TO", "u@example.com")
    captured = {}

    class _FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, *a): pass
        def send_message(self, msg): captured["msg"] = msg

    monkeypatch.setattr(email_mod.smtplib, "SMTP", _FakeSMTP)
    stats = {}
    sent, _, _ = email_mod.send_digest(jobs, stats, ranked_by_hash=ranked)
    assert sent is True and stats["email_error"] == ""
    msg = captured["msg"]
    assert msg.get_content_type() == "multipart/alternative"
    parts = {p.get_content_type(): p.get_payload(decode=True).decode("utf-8") for p in msg.get_payload()}
    assert set(parts) == {"text/plain", "text/html"}
    assert len(parts["text/plain"].splitlines()) == 5
    assert parts["text/html"].count("<tr>") == 4
