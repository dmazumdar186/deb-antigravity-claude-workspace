"""
test_notify.py
description: Tests for common/notify.py — no-env no-op behavior, no network calls.
inputs: N/A (pytest).
outputs: N/A (pytest).
"""

from __future__ import annotations

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
