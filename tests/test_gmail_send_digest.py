"""Tests for execution/google/gmail_send_digest.py.

Covers:
  - _plain_text_fallback: tag strip, script/style drop, entity decode, paragraph preservation
  - send_digest happy path (single attempt)
  - send_digest transient retry on SMTPServerDisconnected / SMTPConnectError
  - send_digest fail-fast on SMTPAuthenticationError (no retry)
  - send_digest fail-fast when credentials missing (no SMTP call)
  - send_digest exhaustion after SMTP_MAX_ATTEMPTS

All SMTP traffic is patched via unittest.mock — no real connection. Sleep
shrunk to a no-op.
"""
from __future__ import annotations

import smtplib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

WORKSPACE = Path(__file__).resolve().parents[1]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from execution.google import gmail_send_digest as mod  # noqa: E402


@pytest.fixture(autouse=True)
def _patch_sleep(monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)


@pytest.fixture(autouse=True)
def _patch_env_recipient(monkeypatch):
    monkeypatch.setenv("GMAIL_SMTP_USER", "sender@example.com")
    monkeypatch.setenv("GMAIL_SMTP_APP_PASSWORD", "app-pass-16-chars")
    monkeypatch.setenv("JOB_TRACKER_RECIPIENT", "recipient@example.com")


# ----------------------------------------------------------------------------
# _plain_text_fallback
# ----------------------------------------------------------------------------

def test_plain_strips_tags():
    assert mod._plain_text_fallback("<p>Hello <b>world</b></p>") == "Hello world"


def test_plain_drops_script_block():
    html = "<p>Real text</p><script>alert('xss')</script><p>more</p>"
    out = mod._plain_text_fallback(html)
    assert "alert" not in out
    assert "Real text" in out
    assert "more" in out


def test_plain_drops_style_block():
    html = "<style>body{color:red}</style><p>Visible</p>"
    out = mod._plain_text_fallback(html)
    assert "color:red" not in out
    assert "Visible" in out


def test_plain_decodes_entities():
    # &nbsp; -> \xa0 (non-breaking space); &amp; -> &; &#160; -> \xa0
    out = mod._plain_text_fallback("<p>A&nbsp;&amp;&nbsp;B</p>")
    assert "&amp;" not in out and "&nbsp;" not in out
    assert "&" in out and "A" in out and "B" in out
    assert mod._plain_text_fallback("<p>&#160;X</p>").strip().endswith("X")


def test_plain_drops_html_comments():
    out = mod._plain_text_fallback("<p>visible</p><!-- hidden -->")
    assert "hidden" not in out
    assert "visible" in out


def test_plain_drops_cdata():
    out = mod._plain_text_fallback("<p>visible</p><![CDATA[hidden]]>")
    assert "hidden" not in out
    assert "visible" in out


def test_plain_preserves_paragraph_break():
    html = "<p>line one</p><p>line two</p>"
    out = mod._plain_text_fallback(html)
    assert "line one" in out and "line two" in out
    assert "\n" in out  # paragraph break survived


def test_plain_handles_br():
    out = mod._plain_text_fallback("first<br>second<br/>third")
    assert "first" in out and "second" in out and "third" in out
    assert out.count("\n") >= 2


def test_plain_empty():
    assert mod._plain_text_fallback("") == ""
    assert mod._plain_text_fallback(None) == ""


# ----------------------------------------------------------------------------
# send_digest — happy path & failure modes
# ----------------------------------------------------------------------------

def _mock_smtp_ok():
    """Return a MagicMock that supports `with smtplib.SMTP(...) as s:` semantics."""
    instance = MagicMock()
    instance.__enter__ = MagicMock(return_value=instance)
    instance.__exit__ = MagicMock(return_value=False)
    factory = MagicMock(return_value=instance)
    return factory, instance


def test_send_digest_happy_path():
    factory, server = _mock_smtp_ok()
    with patch.object(mod.smtplib, "SMTP", factory):
        ok, err = mod.send_digest("<p>hi</p>", subject="s", recipient="r@x.com")
    assert ok is True and err is None
    server.login.assert_called_once()
    server.send_message.assert_called_once()


def test_send_digest_no_recipient(monkeypatch):
    monkeypatch.delenv("JOB_TRACKER_RECIPIENT", raising=False)
    ok, err = mod.send_digest("<p>hi</p>", subject="s")
    assert ok is False
    assert "recipient" in err.lower()


def test_send_digest_no_credentials(monkeypatch):
    monkeypatch.delenv("GMAIL_SMTP_USER", raising=False)
    monkeypatch.delenv("GMAIL_SMTP_APP_PASSWORD", raising=False)
    ok, err = mod.send_digest("<p>hi</p>", subject="s", recipient="r@x.com")
    assert ok is False
    assert "smtp credentials missing" in err.lower()


def test_send_digest_retries_on_disconnect_then_succeeds():
    factory, server = _mock_smtp_ok()
    server.send_message.side_effect = [smtplib.SMTPServerDisconnected("boom"), None]
    with patch.object(mod.smtplib, "SMTP", factory):
        ok, err = mod.send_digest("<p>hi</p>", subject="s", recipient="r@x.com")
    assert ok is True and err is None
    assert server.send_message.call_count == 2


def test_send_digest_retries_on_connect_error():
    factory, server = _mock_smtp_ok()
    server.send_message.side_effect = [smtplib.SMTPConnectError(421, "try later"), None]
    with patch.object(mod.smtplib, "SMTP", factory):
        ok, err = mod.send_digest("<p>hi</p>", subject="s", recipient="r@x.com")
    assert ok is True
    assert server.send_message.call_count == 2


def test_send_digest_failfast_on_auth_error():
    factory, server = _mock_smtp_ok()
    server.send_message.side_effect = smtplib.SMTPAuthenticationError(535, "bad app password")
    with patch.object(mod.smtplib, "SMTP", factory):
        ok, err = mod.send_digest("<p>hi</p>", subject="s", recipient="r@x.com")
    assert ok is False
    assert "SMTPAuthenticationError" in err
    # No retry — auth never retried.
    assert server.send_message.call_count == 1


def test_send_digest_failfast_on_quota_error():
    # Non-auth SMTPException (e.g. recipient refused) shouldn't retry.
    factory, server = _mock_smtp_ok()
    server.send_message.side_effect = smtplib.SMTPRecipientsRefused({})
    with patch.object(mod.smtplib, "SMTP", factory):
        ok, err = mod.send_digest("<p>hi</p>", subject="s", recipient="r@x.com")
    assert ok is False
    assert "SMTPException" in err
    assert server.send_message.call_count == 1


def test_send_digest_exhausts_attempts():
    factory, server = _mock_smtp_ok()
    server.send_message.side_effect = smtplib.SMTPServerDisconnected("persistent")
    with patch.object(mod.smtplib, "SMTP", factory):
        ok, err = mod.send_digest("<p>hi</p>", subject="s", recipient="r@x.com")
    assert ok is False
    assert "SMTPServerDisconnected" in err
    assert f"{mod.SMTP_MAX_ATTEMPTS} attempts" in err
    assert server.send_message.call_count == mod.SMTP_MAX_ATTEMPTS


def test_send_digest_retries_on_oserror():
    factory, server = _mock_smtp_ok()
    server.send_message.side_effect = [OSError("connection reset"), None]
    with patch.object(mod.smtplib, "SMTP", factory):
        ok, err = mod.send_digest("<p>hi</p>", subject="s", recipient="r@x.com")
    assert ok is True
    assert server.send_message.call_count == 2
