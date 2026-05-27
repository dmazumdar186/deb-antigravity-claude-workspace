"""Unit tests for app_store_research.py."""

import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RESEARCH_SCRIPT = PROJECT_ROOT / "execution" / "mobile_apps" / "app_store_research.py"


def _import_asr():
    import app_store_research
    return app_store_research


def test_search_url_appstore():
    asr = _import_asr()
    u = asr.search_url("appstore", "meditation timer")
    assert "apps.apple.com" in u
    assert "meditation" in u


def test_search_url_playstore():
    asr = _import_asr()
    u = asr.search_url("playstore", "habit tracker")
    assert "play.google.com" in u
    assert "habit" in u


def test_search_url_invalid_store():
    asr = _import_asr()
    with pytest.raises(ValueError, match="unknown store"):
        asr.search_url("bogus", "query")


def test_argparse_rejects_bad_store():
    rc = subprocess.run(
        [sys.executable, str(RESEARCH_SCRIPT),
         "--query", "test", "--store", "bogus"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert rc.returncode != 0
    assert "invalid choice" in rc.stderr or "bogus" in rc.stderr


def test_help_exits_zero():
    rc = subprocess.run(
        [sys.executable, str(RESEARCH_SCRIPT), "--help"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert rc.returncode == 0
    assert "query" in rc.stdout


def test_parse_listings_appstore():
    asr = _import_asr()
    md = """
# Search Results

Top apps for meditation:

[Calm Meditation](https://apps.apple.com/us/app/calm/id123)
A great meditation app for sleep.
Rated 4.8 out of 5 stars.

[Headspace](https://apps.apple.com/us/app/headspace/id456)
Mindfulness made simple.
4.7 stars.

[Some Random Page](https://example.com/not-an-app)
Should be filtered out.
"""
    results = asr.parse_listings(md, "appstore", limit=10)
    assert len(results) == 2
    assert any("Calm" in r["name"] for r in results)
    assert any("Headspace" in r["name"] for r in results)
    # Non-app URLs filtered
    assert not any("example.com/not-an-app" in r["url"] for r in results)


def test_parse_listings_playstore():
    asr = _import_asr()
    md = """
[Habit Tracker Pro](https://play.google.com/store/apps/details?id=com.habit.pro)
Track your habits.
[Random Link](https://play.google.com/store/something-else)
"""
    results = asr.parse_listings(md, "playstore", limit=10)
    assert len(results) == 1
    assert "Habit Tracker Pro" in results[0]["name"]


def test_parse_listings_respects_limit():
    asr = _import_asr()
    md = "\n".join(
        f"[App {i}](https://apps.apple.com/us/app/foo/id{i})"
        for i in range(20)
    )
    results = asr.parse_listings(md, "appstore", limit=5)
    assert len(results) == 5


def test_parse_listings_dedupes_urls():
    asr = _import_asr()
    md = """
[App A](https://apps.apple.com/us/app/foo/id1)
[App A again](https://apps.apple.com/us/app/foo/id1)
[App B](https://apps.apple.com/us/app/bar/id2)
"""
    results = asr.parse_listings(md, "appstore", limit=10)
    urls = [r["url"] for r in results]
    assert len(urls) == len(set(urls)), "URLs should be deduplicated"


def test_require_env_missing(monkeypatch):
    asr = _import_asr()
    monkeypatch.delenv("FAKE_FC_KEY_XYZ", raising=False)
    with pytest.raises(SystemExit, match="FAKE_FC_KEY_XYZ"):
        asr.require_env("FAKE_FC_KEY_XYZ")
