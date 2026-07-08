"""
test_reply_classifier.py
description: Deterministic-layer tests for reply_classifier.py. Every OOO/auto-reply string MUST classify auto_reply_or_OOO without LLM. Every stop/unsubscribe string MUST classify negative. Positive strings are LLM-dependent — marked XFAIL in dry-run.
"""

from __future__ import annotations

import pytest

from reply_classifier import classify


OOO_STRINGS = [
    "I am out of the office until Monday and will return your message then.",
    "Auto-reply: currently on vacation, back next week.",
    "This is an automatic reply. I am on leave until further notice.",
    "Je suis absent jusqu'au 15 juillet. Réponse automatique.",
    "En congés cette semaine, de retour le 20.",
]

STOP_STRINGS = [
    "Please unsubscribe me from your list.",
    "Remove me from your mailing list, thanks.",
    "Do not email me again.",
    "Stop contacting me, I am not interested.",
    "Désinscrivez-moi de votre liste.",
]

POSITIVE_STRINGS = [
    "Yes, tell me more about the offer — how does pricing work?",
    "Interested. Could we jump on a call this week?",
    "Sounds good. Ready to sign if the numbers work.",
    "Yes — call me at +33 6 12 34 56 78 tomorrow.",
    "Interested in learning more. What are next steps?",
]


@pytest.mark.parametrize("body", OOO_STRINGS)
def test_ooo_classified_as_auto_reply(body: str):
    result = classify(body, dry_run=True)
    assert result["class"] == "auto_reply_or_OOO", f"got {result['class']} for {body!r}"
    assert result["confidence"] >= 0.9


@pytest.mark.parametrize("body", STOP_STRINGS)
def test_stop_classified_as_negative(body: str):
    result = classify(body, dry_run=True)
    assert result["class"] == "negative", f"got {result['class']} for {body!r}"
    assert result["confidence"] >= 0.9


@pytest.mark.xfail(reason="Positive classification is LLM-dependent; dry-run returns neutral. XFAIL until live LLM wired in.", strict=False)
@pytest.mark.parametrize("body", POSITIVE_STRINGS)
def test_positive_classified_as_positive_or_hot(body: str):
    result = classify(body, dry_run=True)
    assert result["class"] in ("positive", "hot"), f"got {result['class']} for {body!r}"


def test_empty_body_returns_neutral():
    result = classify("", dry_run=True)
    assert result["class"] == "neutral"
    assert result["confidence"] == 0.0


def test_phone_number_hot_pattern():
    """Hot phone-number pattern is deterministic and should fire in dry-run."""
    result = classify("Please call me at +33 6 12 34 56 78 tomorrow.", dry_run=True)
    assert result["class"] == "hot"
