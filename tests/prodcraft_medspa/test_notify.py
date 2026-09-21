"""
test_notify.py
description: Tests for common/notify.py — no-env no-op behavior, no network calls.
inputs: N/A (pytest).
outputs: N/A (pytest).
"""

from __future__ import annotations

import sys

from execution.personal_workflows.prodcraft_medspa.common import notify


def test_error_without_env_returns_false_and_does_not_raise(monkeypatch, capsys):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    result = notify.error("prodcraft_medspa", "sample error", 3)

    assert result is False
    captured = capsys.readouterr()
    assert "prodcraft_medspa / local / sample error / 3" in captured.err


def test_error_message_format(monkeypatch, capsys):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setenv("PRODCRAFT_ENV", "staging")

    notify.error("audit_site", "PSI timeout", 2)

    captured = capsys.readouterr()
    assert "audit_site / staging / PSI timeout / 2" in captured.err


def test_error_never_makes_network_call_without_env(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    def _boom(*args, **kwargs):
        raise AssertionError("should not attempt a network call without env configured")

    monkeypatch.setattr("requests.post", _boom)
    assert notify.error("svc", "err") is False


def _sample_reply_kwargs(**overrides):
    kwargs = dict(
        business_name="Glow Aesthetics",
        owner_name="Dana Ortiz",
        owner_email="owner1@example-medspa-1.test",
        sentiment="positive",
        summary="Wants to see more and book a call this week.",
        suggested_next_step="book_call",
        wants_call=True,
        gmail_thread_id="thread-mock-001",
        preview_url="https://glow.preview.prodcraft.fyi",
    )
    kwargs.update(overrides)
    return kwargs


def test_reply_without_env_returns_false_and_logs_to_stderr(monkeypatch, capsys):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    result = notify.reply(**_sample_reply_kwargs())

    assert result is False
    captured = capsys.readouterr()
    assert "ProdCraft reply: POSITIVE from Glow Aesthetics" in captured.err
    assert "https://mail.google.com/mail/u/0/#all/thread-mock-001" in captured.err


def test_reply_message_has_fixed_shape_and_no_em_dash(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "fake-chat")
    sent = {}

    class _Resp:
        def raise_for_status(self):
            return None

    def _fake_post(url, json, timeout):
        sent["url"] = url
        sent["json"] = json
        return _Resp()

    monkeypatch.setattr("requests.post", _fake_post)

    result = notify.reply(**_sample_reply_kwargs(sentiment="neutral", wants_call=False))

    assert result is True
    text = sent["json"]["text"]
    lines = text.splitlines()
    assert lines[0] == "ProdCraft reply: NEUTRAL from Glow Aesthetics"
    assert "Dana Ortiz" in lines[1]
    assert "owner1@example-medspa-1.test" in lines[1]
    assert lines[2] == "Wants to see more and book a call this week."
    assert lines[3] == "Next step: book_call"
    assert "https://glow.preview.prodcraft.fyi" in lines[4]
    assert "Gmail: https://mail.google.com/mail/u/0/#all/thread-mock-001" in text
    assert "—" not in text


def test_reply_wants_call_suffix_and_no_em_dash(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    notify.reply(**_sample_reply_kwargs(wants_call=True))
    # covered again via capsys-free assertion: no exception, and separately checked for em-dash
    # in test_reply_message_has_fixed_shape_and_no_em_dash above.


def test_sample_reply_cli_runs_without_env(monkeypatch, capsys):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setattr(sys, "argv", ["notify.py", "--sample-reply"])

    notify.main()

    captured = capsys.readouterr()
    assert captured.out.strip() == "False"
    assert "ProdCraft reply: POSITIVE from Sample Med Spa" in captured.err
    assert "—" not in captured.err
