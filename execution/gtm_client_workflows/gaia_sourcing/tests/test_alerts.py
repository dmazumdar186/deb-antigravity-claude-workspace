"""Tests for core/alerts.py (RADAR_CONTRACTS.md section E "Error channel").
Zero network: post_json is monkeypatched, never actually called.
"""

from __future__ import annotations

from gtm_client_workflows.gaia_sourcing.core import alerts


def test_posts_the_exact_fixed_shape(monkeypatch):
    monkeypatch.setattr(alerts, "secret", lambda name, required=True: "https://hooks.example.com/x")

    captured = {}

    def fake_post_json(url, payload, timeout):
        captured["url"] = url
        captured["payload"] = payload
        captured["timeout"] = timeout
        return True, 200

    monkeypatch.setattr(alerts, "post_json", fake_post_json)

    ok = alerts.alert("gaia_sourcing", "production", "prospeo timeout", 3)

    assert ok is True
    assert captured["url"] == "https://hooks.example.com/x"
    assert set(captured["payload"].keys()) == {"service", "environment", "error", "count", "at"}
    assert captured["payload"]["service"] == "gaia_sourcing"
    assert captured["payload"]["environment"] == "production"
    assert captured["payload"]["error"] == "prospeo timeout"
    assert captured["payload"]["count"] == 3
    assert isinstance(captured["payload"]["at"], str) and captured["payload"]["at"]
    assert captured["timeout"] == 10


def test_count_defaults_to_one(monkeypatch):
    monkeypatch.setattr(alerts, "secret", lambda name, required=True: "https://hooks.example.com/x")
    captured = {}
    monkeypatch.setattr(
        alerts, "post_json",
        lambda url, payload, timeout: (captured.update(payload) or (True, 200)),
    )
    alerts.alert("svc", "env", "err")
    assert captured["count"] == 1


def test_noops_with_a_log_line_when_env_var_absent(monkeypatch, capsys):
    monkeypatch.setattr(alerts, "secret", lambda name, required=True: "")

    called = {"n": 0}
    monkeypatch.setattr(alerts, "post_json", lambda *a, **kw: called.__setitem__("n", called["n"] + 1))

    ok = alerts.alert("gaia_sourcing", "production", "boom", 1)

    assert ok is False
    assert called["n"] == 0  # post_json never invoked
    out = capsys.readouterr().out
    assert "ALERT_WEBHOOK_URL" in out
    assert "NOT sent" in out


def test_looks_up_the_configured_env_var_name(monkeypatch):
    """CONFIG.alert_webhook_env is settable; alert() must look up whatever
    name it currently holds, not a hardcoded string.
    """
    from gtm_client_workflows.gaia_sourcing.core.config import CONFIG

    monkeypatch.setattr(CONFIG, "alert_webhook_env", "MY_CUSTOM_WEBHOOK")
    seen_names = []

    def fake_secret(name, required=True):
        seen_names.append(name)
        return ""

    monkeypatch.setattr(alerts, "secret", fake_secret)
    alerts.alert("svc", "env", "err")
    assert seen_names == ["MY_CUSTOM_WEBHOOK"]


def test_never_raises_when_post_json_fails(monkeypatch):
    monkeypatch.setattr(alerts, "secret", lambda name, required=True: "https://hooks.example.com/x")
    monkeypatch.setattr(alerts, "post_json", lambda url, payload, timeout: (False, 500))
    ok = alerts.alert("svc", "env", "err")
    assert ok is False


def test_never_raises_when_post_json_itself_raises(monkeypatch):
    monkeypatch.setattr(alerts, "secret", lambda name, required=True: "https://hooks.example.com/x")

    def boom(url, payload, timeout):
        raise RuntimeError("network exploded")

    monkeypatch.setattr(alerts, "post_json", boom)
    ok = alerts.alert("svc", "env", "err")  # must not raise
    assert ok is False
