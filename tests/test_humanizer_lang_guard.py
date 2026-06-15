"""Per-field langdetect guard on humanizer output.

Per ~/.claude/rules/eval-first.md: every LLM output field needs a language
check so a French input never comes back accidentally English. The guard:
  - Skips when text is too short to detect reliably (no false positives)
  - Skips when --no-lang-guard is passed
  - WARNs by default; --strict-lang turns mismatch into exit code 3
  - Honors --lang CODE to force a target language
"""
from __future__ import annotations

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from execution.content import humanizer as mod  # noqa: E402


# ----------------------------------------------------------------------------
# _detect_lang
# ----------------------------------------------------------------------------

FR_LONG = (
    "Bonjour, je m'appelle Debanjan et je travaille comme chef de produit. "
    "J'aime construire des systèmes simples et fiables."
)
EN_LONG = (
    "Hello, I am a product manager and I enjoy building simple, reliable systems "
    "that actually solve customer problems day to day."
)


def test_detect_lang_french():
    assert mod._detect_lang(FR_LONG) == "fr"


def test_detect_lang_english():
    assert mod._detect_lang(EN_LONG) == "en"


def test_detect_lang_too_short_returns_none():
    assert mod._detect_lang("hi") is None


def test_detect_lang_empty():
    assert mod._detect_lang("") is None
    assert mod._detect_lang(None) is None


# ----------------------------------------------------------------------------
# _check_language_match
# ----------------------------------------------------------------------------

def test_match_when_languages_agree():
    ok, msg = mod._check_language_match(FR_LONG, FR_LONG, force_lang=None)
    assert ok is True and msg is None


def test_mismatch_input_fr_output_en():
    ok, msg = mod._check_language_match(FR_LONG, EN_LONG, force_lang=None)
    assert ok is False
    assert "fr" in msg and "en" in msg


def test_force_lang_matches():
    ok, msg = mod._check_language_match(EN_LONG, FR_LONG, force_lang="fr")
    assert ok is True and msg is None


def test_force_lang_mismatch():
    ok, msg = mod._check_language_match(FR_LONG, EN_LONG, force_lang="fr")
    assert ok is False
    assert "fr" in msg and "en" in msg


def test_force_lang_short_output_skipped():
    """Output too short to detect reliably — force passes silently."""
    ok, _ = mod._check_language_match(FR_LONG, "hi", force_lang="fr")
    assert ok is True


def test_short_input_skips_guard():
    """Input too short to detect — guard is a no-op."""
    ok, msg = mod._check_language_match("hi", FR_LONG, force_lang=None)
    assert ok is True and msg is None


def test_equivalent_pair_does_not_flap():
    """langdetect sometimes confuses en/ca on short / borderline text. Treat as equal."""
    # Simulate by passing strings that the equivalence map covers.
    # _LANG_EQUIV contains ("en","ca") etc., so we can test the predicate directly.
    assert ("en", "ca") in mod._LANG_EQUIV
    assert ("fr", "ca") in mod._LANG_EQUIV
