"""Tests for anthropic_watch.

Covers:
  - Firecrawl retry on 429 / 5xx / timeout with backoff
  - Non-retryable HTTP errors raise immediately
  - Missing API key raises immediately (no retry, no spend)
  - fetch_all swallows per-source exceptions (one broken source doesn't kill run)
  - run.py --dry-run exits 0, prints per-source counts, makes no Claude call

Tests use monkeypatch to replace `urllib.request.urlopen` with stubs so no real
HTTP traffic flies. FIRECRAWL_BASE_BACKOFF_S is shrunk to ~0 to keep tests fast.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from execution.personal_workflows.anthropic_watch import fetch as fetch_mod


# Replace sleep with no-op so retries are instant.
@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(fetch_mod.time, "sleep", lambda _s: None)


class _FakeResp:
    def __init__(self, body: dict):
        self._body = json.dumps(body).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _http_error(code: int, msg: str = "err") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="http://x", code=code, msg=msg, hdrs=None, fp=io.BytesIO(b""),
    )


# ----------------------------------------------------------------------------
# _firecrawl_scrape — retry logic
# ----------------------------------------------------------------------------

def test_firecrawl_no_api_key_raises(monkeypatch):
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="FIRECRAWL_API_KEY"):
        fetch_mod._firecrawl_scrape("https://x")


def test_firecrawl_success_first_try(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fake")
    calls = []

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        return _FakeResp({"success": True, "data": {"markdown": "# Hello"}})

    monkeypatch.setattr(fetch_mod.urllib.request, "urlopen", fake_urlopen)
    out = fetch_mod._firecrawl_scrape("https://x")
    assert out == "# Hello"
    assert len(calls) == 1


def test_firecrawl_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fake")
    attempts = {"n": 0}

    def fake_urlopen(req, timeout):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise _http_error(429, "too many requests")
        return _FakeResp({"success": True, "data": {"markdown": "ok"}})

    monkeypatch.setattr(fetch_mod.urllib.request, "urlopen", fake_urlopen)
    out = fetch_mod._firecrawl_scrape("https://x")
    assert out == "ok"
    assert attempts["n"] == 3


def test_firecrawl_retries_on_5xx(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fake")
    attempts = {"n": 0}

    def fake_urlopen(req, timeout):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise _http_error(503, "service unavailable")
        return _FakeResp({"success": True, "data": {"markdown": "ok"}})

    monkeypatch.setattr(fetch_mod.urllib.request, "urlopen", fake_urlopen)
    assert fetch_mod._firecrawl_scrape("https://x") == "ok"
    assert attempts["n"] == 2


def test_firecrawl_does_not_retry_on_4xx_other(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fake")
    attempts = {"n": 0}

    def fake_urlopen(req, timeout):
        attempts["n"] += 1
        raise _http_error(401, "unauthorized")

    monkeypatch.setattr(fetch_mod.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(urllib.error.HTTPError):
        fetch_mod._firecrawl_scrape("https://x")
    assert attempts["n"] == 1  # fail fast


def test_firecrawl_exhausts_retries_on_persistent_429(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fake")
    attempts = {"n": 0}

    def fake_urlopen(req, timeout):
        attempts["n"] += 1
        raise _http_error(429, "still rate-limited")

    monkeypatch.setattr(fetch_mod.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(urllib.error.HTTPError):
        fetch_mod._firecrawl_scrape("https://x")
    assert attempts["n"] == fetch_mod.FIRECRAWL_MAX_ATTEMPTS


def test_firecrawl_retries_on_timeout(monkeypatch):
    import socket
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fake")
    attempts = {"n": 0}

    def fake_urlopen(req, timeout):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise socket.timeout("timed out")
        return _FakeResp({"success": True, "data": {"markdown": "ok"}})

    monkeypatch.setattr(fetch_mod.urllib.request, "urlopen", fake_urlopen)
    assert fetch_mod._firecrawl_scrape("https://x") == "ok"
    assert attempts["n"] == 2


def test_firecrawl_success_false_not_retried(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fake")
    attempts = {"n": 0}

    def fake_urlopen(req, timeout):
        attempts["n"] += 1
        return _FakeResp({"success": False, "error": "bad url"})

    monkeypatch.setattr(fetch_mod.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="firecrawl scrape failed"):
        fetch_mod._firecrawl_scrape("https://x")
    assert attempts["n"] == 1


# ----------------------------------------------------------------------------
# fetch_all — one broken source doesn't kill the run
# ----------------------------------------------------------------------------

def test_fetch_all_swallows_per_source_exception(monkeypatch):
    monkeypatch.setattr(fetch_mod, "ALL_FETCHERS", {
        "good": lambda: [{"url": "u", "title": "t", "source": "good", "published": None, "raw_excerpt": "x"}],
        "bad": lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    })
    results = fetch_mod.fetch_all()
    assert len(results["good"]) == 1
    assert results["bad"] == []


# ----------------------------------------------------------------------------
# Front-door synthetic: run.py --dry-run
# ----------------------------------------------------------------------------

def test_front_door_dry_run_exits_zero(monkeypatch, tmp_path):
    """--dry-run is the operator's "is the watcher alive" check.

    The synthetic monkeypatches fetch_all to return fixture data so the test
    runs without any real network call. We assert exit 0 and per-source lines
    in stdout.
    """
    # Patch fetch_all on the imported module to return fixture data.
    fixture_items = {
        "anthropic-news": [{"url": "u1", "title": "t1", "source": "anthropic-news", "published": None, "raw_excerpt": "x"}],
        "github-claude-code": [],
    }

    import execution.personal_workflows.anthropic_watch.run as run_mod
    monkeypatch.setattr(run_mod.fetch_mod, "fetch_all", lambda only=None: fixture_items)

    # Redirect stdout into a buffer so we can assert on it.
    captured = io.StringIO()
    monkeypatch.setattr(sys, "stdout", captured)

    # Build args
    monkeypatch.setattr(sys, "argv", ["run.py", "--dry-run"])

    rc = run_mod.main()
    assert rc == 0
    out = captured.getvalue()
    assert "anthropic-news: 1 items" in out
    assert "github-claude-code: 0 items" in out
