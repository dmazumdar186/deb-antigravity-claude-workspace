"""
Unit tests for job_search_notify.py — Gmail SMTP daily summary email.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from execution.personal_workflows.job_search_notify import _build_body, send_run_summary  # noqa: E402


SAMPLE_SUMMARY = {
    "run_id": "run_20260609_180000",
    "run_at": "2026-06-09T18:00:00+00:00",
    "discovered": 205,
    "after_keyword_filter": 108,
    "after_dedup": 102,
    "llm_dropped": 2,
    "written_per_tab": {"PM": 89, "AI PM": 26, "AI Automation": 2,
                        "AI Mobile": 0, "AI Process": 0, "AI Consultant": 7},
}


# ---------------------------------------------------------------------------
# _build_body
# ---------------------------------------------------------------------------

def test_build_body_subject_plural():
    subject, _ = _build_body(SAMPLE_SUMMARY, "SHEET_X")
    assert subject == "Job Search — 124 new jobs added today"


def test_build_body_subject_singular():
    summary = {**SAMPLE_SUMMARY, "written_per_tab": {"PM": 1}}
    subject, _ = _build_body(summary, "SHEET_X")
    assert subject == "Job Search — 1 new job added today"


def test_build_body_subject_zero():
    summary = {**SAMPLE_SUMMARY, "written_per_tab": {}}
    subject, _ = _build_body(summary, "SHEET_X")
    assert subject == "Job Search — 0 new jobs added today"


def test_build_body_includes_per_tab_breakdown():
    _, body = _build_body(SAMPLE_SUMMARY, "SHEET_X")
    assert "PM" in body
    assert "89" in body
    assert "AI Consultant" in body
    assert "7" in body


def test_build_body_includes_sheet_link_when_id_given():
    _, body = _build_body(SAMPLE_SUMMARY, "SHEET_X")
    assert "https://docs.google.com/spreadsheets/d/SHEET_X/edit" in body


def test_build_body_omits_sheet_link_when_id_missing():
    _, body = _build_body(SAMPLE_SUMMARY, None)
    assert "docs.google.com" not in body


def test_build_body_includes_pipeline_counters():
    _, body = _build_body(SAMPLE_SUMMARY, "SHEET_X")
    assert "Raw discovered" in body
    assert "205" in body
    assert "After dedup" in body
    assert "102" in body
    assert "LLM-dropped" in body


# ---------------------------------------------------------------------------
# send_run_summary
# ---------------------------------------------------------------------------

def test_send_run_summary_skips_when_user_missing(monkeypatch):
    monkeypatch.delenv("GMAIL_SMTP_USER", raising=False)
    monkeypatch.setenv("GMAIL_SMTP_APP_PASSWORD", "x")
    assert send_run_summary(SAMPLE_SUMMARY) is False


def test_send_run_summary_skips_when_password_missing(monkeypatch):
    monkeypatch.setenv("GMAIL_SMTP_USER", "u@x.com")
    monkeypatch.delenv("GMAIL_SMTP_APP_PASSWORD", raising=False)
    assert send_run_summary(SAMPLE_SUMMARY) is False


def test_send_run_summary_sends_when_creds_present(monkeypatch):
    monkeypatch.setenv("GMAIL_SMTP_USER", "sender@x.com")
    monkeypatch.setenv("GMAIL_SMTP_APP_PASSWORD", "app-pass-16-chars")
    monkeypatch.setenv("GMAIL_NOTIFY_TO", "to@x.com")
    monkeypatch.setenv("SHEETS_SPREADSHEET_ID", "SID")

    smtp_instance = MagicMock()
    smtp_cm = MagicMock()
    smtp_cm.__enter__ = MagicMock(return_value=smtp_instance)
    smtp_cm.__exit__ = MagicMock(return_value=False)
    with patch("smtplib.SMTP", return_value=smtp_cm) as mock_smtp:
        out = send_run_summary(SAMPLE_SUMMARY)
    assert out is True
    mock_smtp.assert_called_once_with("smtp.gmail.com", 587, timeout=30)
    smtp_instance.starttls.assert_called_once()
    smtp_instance.login.assert_called_once_with("sender@x.com", "app-pass-16-chars")
    args, _ = smtp_instance.sendmail.call_args
    assert args[0] == "sender@x.com"
    assert args[1] == ["to@x.com"]
    raw_message = args[2]
    # Subject contains an em-dash → MIMEText auto-encodes it as RFC2047
    # ('=?utf-8?q?Job_Search_=E2=80=94_124...?='). Parse to decode.
    import email
    parsed = email.message_from_string(raw_message)
    from email.header import decode_header, make_header
    subject = str(make_header(decode_header(parsed["Subject"])))
    assert "Job Search" in subject
    assert "124" in subject
    # Body is base64-encoded under Content-Transfer-Encoding; decode it
    body = parsed.get_payload(decode=True).decode("utf-8")
    assert "124" in body


def test_send_run_summary_returns_false_on_smtp_error(monkeypatch):
    monkeypatch.setenv("GMAIL_SMTP_USER", "u@x.com")
    monkeypatch.setenv("GMAIL_SMTP_APP_PASSWORD", "p")
    monkeypatch.setenv("GMAIL_NOTIFY_TO", "to@x.com")
    with patch("smtplib.SMTP", side_effect=ConnectionError("network down")):
        assert send_run_summary(SAMPLE_SUMMARY) is False


def test_send_run_summary_defaults_to_in_use_user(monkeypatch):
    """If GMAIL_NOTIFY_TO is unset, send to GMAIL_SMTP_USER."""
    monkeypatch.setenv("GMAIL_SMTP_USER", "self@x.com")
    monkeypatch.setenv("GMAIL_SMTP_APP_PASSWORD", "p")
    monkeypatch.delenv("GMAIL_NOTIFY_TO", raising=False)
    smtp_instance = MagicMock()
    smtp_cm = MagicMock()
    smtp_cm.__enter__ = MagicMock(return_value=smtp_instance)
    smtp_cm.__exit__ = MagicMock(return_value=False)
    with patch("smtplib.SMTP", return_value=smtp_cm):
        send_run_summary(SAMPLE_SUMMARY)
    args, _ = smtp_instance.sendmail.call_args
    assert args[1] == ["self@x.com"]
