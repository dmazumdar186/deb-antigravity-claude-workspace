"""Tests for rosy_origami: per-section language guard + Tavily 429 graceful drop.

Covers the two audit gaps:
  - composer.check_section_language: warns on language mismatch, silent on match
  - generate_demo._fetch_tavily_news: 429 / quota errors return [] with stderr
    warning instead of aborting the newsletter
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

WORKSPACE = Path(__file__).resolve().parents[3]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))


def _load(name: str, relpath: str):
    spec = importlib.util.spec_from_file_location(name, WORKSPACE / relpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


composer = _load("rosy_composer", "execution/content/rosy_origami/composer.py")


# ----------------------------------------------------------------------------
# composer.check_section_language
# ----------------------------------------------------------------------------

FR_TEXT = (
    "Bonjour à toutes et à tous, voici notre nouvelle infolettre du mois. "
    "Nous avons rassemblé les nouvelles importantes pour la communauté."
)
EN_TEXT = (
    "Hello everyone, this is our community newsletter for the month. We've "
    "gathered the most important news for all our members across the city."
)


def test_lang_guard_silent_on_match():
    ok, msg = composer.check_section_language("intro", FR_TEXT, ["fr"])
    assert ok is True and msg is None


def test_lang_guard_silent_when_in_multi_lang_set():
    """Tenant declares ['en', 'fr']; either is acceptable."""
    ok, _ = composer.check_section_language("intro", EN_TEXT, ["en", "fr"])
    assert ok is True
    ok, _ = composer.check_section_language("intro", FR_TEXT, ["en", "fr"])
    assert ok is True


def test_lang_guard_warns_on_mismatch():
    ok, msg = composer.check_section_language("intro", EN_TEXT, ["fr"])
    assert ok is False
    assert "intro" in msg
    assert "en" in msg and "fr" in msg


def test_lang_guard_silent_when_text_too_short():
    """Sections under MIN_LANGDETECT_CHARS skip — detection is unreliable."""
    ok, _ = composer.check_section_language("closing", "Hi.", ["fr"])
    assert ok is True


def test_lang_guard_silent_when_allowed_langs_none():
    ok, _ = composer.check_section_language("intro", FR_TEXT, None)
    assert ok is True


def test_lang_guard_silent_when_allowed_langs_empty():
    ok, _ = composer.check_section_language("intro", FR_TEXT, [])
    assert ok is True


def test_lang_guard_silent_when_text_empty():
    ok, _ = composer.check_section_language("intro", "", ["fr"])
    assert ok is True


# ----------------------------------------------------------------------------
# generate_demo._fetch_tavily_news graceful 429 handling
# ----------------------------------------------------------------------------

def _import_generate_demo(monkeypatch):
    """Load generate_demo with subprocess + heavy imports stubbed so the
    module is importable in a unit-test context."""
    # Stub anything that would try to actually run at import time.
    import types as _types
    fake_tavily = _types.ModuleType("tavily")
    fake_tavily.TavilyClient = MagicMock()
    monkeypatch.setitem(sys.modules, "tavily", fake_tavily)
    return _load("rosy_generate_demo", "execution/content/rosy_origami/generate_demo.py")


def test_tavily_returns_empty_when_no_api_key(monkeypatch, capsys):
    gd = _import_generate_demo(monkeypatch)
    # The function loads .env into os.environ at call time via its own
    # _load_env helper, so monkeypatch.delenv alone is insufficient. Force
    # an empty value (the function's truthiness check treats "" as missing).
    monkeypatch.setenv("TAVILY_API_KEY", "")
    # Also stub _load_env so it doesn't repopulate from disk.
    monkeypatch.setattr(gd, "_load_env", lambda: None, raising=False)
    items = gd.fetch_news("Indian Paris", days=7)
    assert items == []
    err = capsys.readouterr().err
    assert "TAVILY_API_KEY" in err


def test_tavily_429_returns_empty_with_warn(monkeypatch, capsys):
    gd = _import_generate_demo(monkeypatch)
    monkeypatch.setenv("TAVILY_API_KEY", "fake")

    class _FakeClient:
        def __init__(self, *_a, **_k): pass
        def search(self, **_kw):
            raise RuntimeError("HTTP 429: rate limit exceeded")

    # Patch the imported TavilyClient inside the function's local namespace.
    monkeypatch.setattr(sys.modules["tavily"], "TavilyClient", _FakeClient)
    items = gd.fetch_news("Indian Paris", days=7)
    assert items == [], "Tavily 429 must drop the section, not abort"
    err = capsys.readouterr().err
    assert "quota" in err.lower() or "rate-limit" in err.lower() or "rate limit" in err.lower()
    assert "omitted" in err


def test_tavily_generic_error_returns_empty_with_warn(monkeypatch, capsys):
    gd = _import_generate_demo(monkeypatch)
    monkeypatch.setenv("TAVILY_API_KEY", "fake")

    class _FakeClient:
        def __init__(self, *_a, **_k): pass
        def search(self, **_kw):
            raise ConnectionError("DNS lookup failed")

    monkeypatch.setattr(sys.modules["tavily"], "TavilyClient", _FakeClient)
    items = gd.fetch_news("Indian Paris", days=7)
    assert items == []
    err = capsys.readouterr().err
    assert "omitted" in err


def test_tavily_empty_query_returns_empty(monkeypatch):
    gd = _import_generate_demo(monkeypatch)
    monkeypatch.setenv("TAVILY_API_KEY", "fake")
    items = gd.fetch_news("", days=7)
    assert items == []
