"""Unit tests for the cv_optimizer_v2 front-door synthetic.

Patches urllib.request.urlopen so no real HTTP traffic is required for the
test suite. The live invocation is reserved for the operator's manual gate
(`py …/tests/front_door.py --runs 5`).
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock

import pytest

WORKSPACE = Path(__file__).resolve().parents[1]
_FD_PATH = WORKSPACE / "execution" / "personal_workflows" / "cv_optimizer_v2" / "tests" / "front_door.py"
_spec = importlib.util.spec_from_file_location("cv_v2_front_door", _FD_PATH)
fd = importlib.util.module_from_spec(_spec)
sys.modules["cv_v2_front_door"] = fd
_spec.loader.exec_module(fd)


def _resp(status: int, body: str):
    m = MagicMock()
    m.status = status
    m.read.return_value = body.encode("utf-8")
    m.__enter__ = MagicMock(return_value=m)
    m.__exit__ = MagicMock(return_value=False)
    return m


def _http_error(code: int, body: str = ""):
    return urllib.error.HTTPError(
        url="http://x", code=code, msg="x", hdrs=None, fp=io.BytesIO(body.encode("utf-8")),
    )


# ----------------------------------------------------------------------------
# check_worker_health
# ----------------------------------------------------------------------------

def test_health_passes_on_ok(monkeypatch):
    payload = {
        "status": "ok",
        "version": "v2.1",
        "secrets_present": {"gemini": True},
        "prompt_fingerprint": "abc",
        "schema_fingerprint": "def",
        "timestamp": "2026-06-15T00:00:00Z",
    }
    monkeypatch.setattr(fd.urllib.request, "urlopen",
                        lambda req, timeout: _resp(200, json.dumps(payload)))
    ok, msg = fd.check_worker_health()
    assert ok is True
    assert "ok" in msg
    assert "v2.1" in msg


def test_health_does_not_fail_on_degraded(monkeypatch):
    """`degraded` surfaces the cause to the operator — must not become a hard fail."""
    payload = {
        "status": "degraded",
        "version": "v2.1",
        "secrets_present": {"gemini": False},
        "prompt_fingerprint": "abc",
        "schema_fingerprint": "def",
        "timestamp": "2026-06-15T00:00:00Z",
    }
    monkeypatch.setattr(fd.urllib.request, "urlopen",
                        lambda req, timeout: _resp(200, json.dumps(payload)))
    ok, msg = fd.check_worker_health()
    assert ok is True
    assert "degraded" in msg


def test_health_fails_on_http_500(monkeypatch):
    def raise_500(req, timeout):
        raise _http_error(500, "boom")
    monkeypatch.setattr(fd.urllib.request, "urlopen", raise_500)
    ok, msg = fd.check_worker_health()
    assert ok is False
    assert "500" in msg


def test_health_fails_on_unreachable(monkeypatch):
    def raise_url(req, timeout):
        raise urllib.error.URLError("dns failure")
    monkeypatch.setattr(fd.urllib.request, "urlopen", raise_url)
    ok, msg = fd.check_worker_health()
    assert ok is False
    assert "URLError" in msg or "dns" in msg.lower()


def test_health_fails_on_missing_keys(monkeypatch):
    """If the Worker contract regresses (e.g. missing `prompt_fingerprint`), fail."""
    payload = {"status": "ok"}  # missing required keys
    monkeypatch.setattr(fd.urllib.request, "urlopen",
                        lambda req, timeout: _resp(200, json.dumps(payload)))
    ok, msg = fd.check_worker_health()
    assert ok is False
    assert "missing keys" in msg


def test_health_fails_on_non_json(monkeypatch):
    monkeypatch.setattr(fd.urllib.request, "urlopen",
                        lambda req, timeout: _resp(200, "<html>oops</html>"))
    ok, msg = fd.check_worker_health()
    assert ok is False
    assert "non-JSON" in msg


def test_health_fails_on_unknown_status(monkeypatch):
    payload = {
        "status": "wat",
        "secrets_present": {},
        "prompt_fingerprint": "x",
        "schema_fingerprint": "y",
        "timestamp": "2026-06-15T00:00:00Z",
    }
    monkeypatch.setattr(fd.urllib.request, "urlopen",
                        lambda req, timeout: _resp(200, json.dumps(payload)))
    ok, msg = fd.check_worker_health()
    assert ok is False
    assert "unexpected status" in msg


# ----------------------------------------------------------------------------
# check_pages_reachable
# ----------------------------------------------------------------------------

def test_pages_passes_on_200(monkeypatch):
    monkeypatch.setattr(fd.urllib.request, "urlopen",
                        lambda req, timeout: _resp(200, ""))
    ok, _ = fd.check_pages_reachable()
    assert ok is True


def test_pages_passes_on_405_head_not_allowed(monkeypatch):
    """Cloudflare Pages sometimes returns 405 on HEAD — page is still reachable."""
    def raise_405(req, timeout):
        raise _http_error(405)
    monkeypatch.setattr(fd.urllib.request, "urlopen", raise_405)
    ok, msg = fd.check_pages_reachable()
    assert ok is True
    assert "405" in msg


def test_pages_fails_on_500(monkeypatch):
    def raise_500(req, timeout):
        raise _http_error(500)
    monkeypatch.setattr(fd.urllib.request, "urlopen", raise_500)
    ok, _ = fd.check_pages_reachable()
    assert ok is False


def test_pages_fails_when_unreachable(monkeypatch):
    def raise_url(req, timeout):
        raise urllib.error.URLError("dns")
    monkeypatch.setattr(fd.urllib.request, "urlopen", raise_url)
    ok, msg = fd.check_pages_reachable()
    assert ok is False
    assert "unreachable" in msg.lower()


# ----------------------------------------------------------------------------
# run_once + main
# ----------------------------------------------------------------------------

def test_run_once_passes_when_both_checks_ok(monkeypatch):
    monkeypatch.setattr(fd, "check_worker_health", lambda: (True, "ok"))
    monkeypatch.setattr(fd, "check_pages_reachable", lambda: (True, "ok"))
    assert fd.run_once(include_optimize=False) is True


def test_run_once_fails_when_either_check_fails(monkeypatch):
    monkeypatch.setattr(fd, "check_worker_health", lambda: (True, "ok"))
    monkeypatch.setattr(fd, "check_pages_reachable", lambda: (False, "x"))
    assert fd.run_once(include_optimize=False) is False

    monkeypatch.setattr(fd, "check_worker_health", lambda: (False, "x"))
    monkeypatch.setattr(fd, "check_pages_reachable", lambda: (True, "ok"))
    assert fd.run_once(include_optimize=False) is False
