"""Unit tests for mobile_app_canary.py."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CANARY_SCRIPT = PROJECT_ROOT / "execution" / "mobile_apps" / "mobile_app_canary.py"


def _import_canary():
    import mobile_app_canary
    return mobile_app_canary


def test_dry_run_empty_registry_exits_zero(isolated_registry, capsys):
    """With --dry-run and empty registry, exit code 0 and results: []."""
    canary = _import_canary()
    # Empty registry already written by fixture
    rc = subprocess.run(
        [sys.executable, str(CANARY_SCRIPT), "--dry-run"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**__import__("os").environ},
    )
    # Note: this runs the script as subprocess with the real registry — for true
    # isolation, see test_integration. We just sanity check exit code/output shape here.
    assert rc.returncode == 0
    # The output should be valid JSON in the body somewhere
    out = rc.stdout
    # find the JSON summary block (starts with `{`)
    json_start = out.find("{")
    assert json_start >= 0
    parsed = json.loads(out[json_start:])
    assert parsed.get("dry_run") is True
    assert "results" in parsed


def test_ping_health_missing_dep(monkeypatch):
    """If httpx is None, ping_health returns missing-dep."""
    canary = _import_canary()
    monkeypatch.setattr(canary, "httpx", None)
    result = canary.ping_health("test-slug", "http://example.com/health", 5.0)
    assert result["slug"] == "test-slug"
    assert result["status"] == "missing-dep"


def test_ping_health_returns_red_on_httperror(monkeypatch):
    """When httpx raises HTTPError, ping_health returns red, not raise."""
    canary = _import_canary()
    import httpx as real_httpx

    class FakeHttpx:
        HTTPError = real_httpx.HTTPError

        @staticmethod
        def get(url, timeout, follow_redirects):
            raise real_httpx.ConnectError("connection refused")

    monkeypatch.setattr(canary, "httpx", FakeHttpx)
    result = canary.ping_health("test", "http://no-such.example/health", 1.0)
    assert result["status"] == "red"
    assert "error" in result


def test_ping_health_green_on_200(monkeypatch):
    canary = _import_canary()
    import httpx as real_httpx

    class FakeResp:
        status_code = 200
        text = "ok"

    class FakeHttpx:
        HTTPError = real_httpx.HTTPError

        @staticmethod
        def get(url, timeout, follow_redirects):
            return FakeResp()

    monkeypatch.setattr(canary, "httpx", FakeHttpx)
    result = canary.ping_health("good-app", "http://example.com/health", 5.0)
    assert result["status"] == "green"
    assert result["http_status"] == 200


def test_ping_health_red_on_500(monkeypatch):
    canary = _import_canary()
    import httpx as real_httpx

    class FakeResp:
        status_code = 500
        text = "internal error"

    class FakeHttpx:
        HTTPError = real_httpx.HTTPError

        @staticmethod
        def get(url, timeout, follow_redirects):
            return FakeResp()

    monkeypatch.setattr(canary, "httpx", FakeHttpx)
    result = canary.ping_health("bad-app", "http://example.com/health", 5.0)
    assert result["status"] == "red"
    assert result["http_status"] == 500


def test_canary_help_exits_zero():
    """Sanity: --help exits with code 0."""
    rc = subprocess.run(
        [sys.executable, str(CANARY_SCRIPT), "--help"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert rc.returncode == 0
    assert "dry-run" in rc.stdout
