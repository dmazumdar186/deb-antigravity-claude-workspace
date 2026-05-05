#!/usr/bin/env python3
"""
test_reply_classifier.py
description: Tests the reply classifier module with both mock and real LLM calls.
inputs: OPENROUTER_API_KEY in .env (for real mode)
outputs: pytest results
usage: pytest tests/test_reply_classifier.py
"""

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "execution"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from modules.reply_classifier import classify, classify_mock

MOCK_COMPATIBLE = 7  # first N cases are designed for keyword-matching mock classifier

SAMPLE_REPLIES = [
    # --- Original 7 cases (mock-compatible) ---
    {
        "body": "I'm ready to sell. Call me at 832-555-0199, my number is best after 5pm.",
        "expected": "hot_positive",
        "label": "hot lead with phone number",
    },
    {
        "body": "Yes, I've been thinking about selling. What's the process?",
        "expected": "positive",
        "label": "interested seller",
    },
    {
        "body": "Not interested, please remove me from your list.",
        "expected": "negative",
        "label": "opt-out request",
    },
    {
        "body": "I am currently out of the office and will return on Monday.",
        "expected": "neutral",
        "label": "out-of-office auto-reply",
    },
    {
        "body": "Tell me more about your offer. Can you call me this week?",
        "expected": "positive",
        "label": "wants a call",
    },
    {
        "body": "Stop emailing me. I'm not selling anything.",
        "expected": "negative",
        "label": "hostile refusal",
    },
    {
        "body": "I want to sell now. Schedule a call with me.",
        "expected": "hot_positive",
        "label": "hot lead ready to sell",
    },
    # --- Ambiguous intent ---
    {
        "body": "Maybe. Depends on the price.",
        "expected": "neutral",
        "label": "ambiguous — no clear intent",
    },
    {
        "body": "Not sure yet, let me think about it.",
        "expected": "neutral",
        "label": "ambiguous leaning neutral",
    },
    # --- Multi-signal conflict ---
    {
        "body": "Not interested right now, but call me in 6 months.",
        "expected": "neutral",
        "accept": ["negative", "neutral", "positive"],
        "label": "future interest — deferred, not rejection",
    },
    {
        "body": "I'm interested but I'm not ready to sell yet. Maybe next year.",
        "expected": "positive",
        "label": "positive but not ready",
    },
    # --- Very short replies ---
    {
        "body": "Yes",
        "expected": "positive",
        "label": "one-word yes",
    },
    {
        "body": "No",
        "expected": "negative",
        "label": "one-word no",
    },
    {
        "body": "?",
        "expected": "neutral",
        "label": "question mark only",
    },
    {
        "body": "Ok",
        "expected": "neutral",
        "accept": ["neutral", "positive"],
        "label": "one-word ok",
    },
    # --- Hostile / profanity ---
    {
        "body": "Get lost. Stop spamming my inbox.",
        "expected": "negative",
        "label": "hostile spam complaint",
    },
    {
        "body": "Who the hell is this? I never asked for this email.",
        "expected": "negative",
        "label": "hostile who-is-this",
    },
    # --- Forward / delegation ---
    {
        "body": "Forwarding this to my business partner. He handles these decisions.",
        "expected": "neutral",
        "accept": ["neutral", "positive"],
        "label": "forwarding to partner — delegation without explicit interest",
    },
    {
        "body": "CC'ing my accountant on this. We'd need to look at the numbers.",
        "expected": "positive",
        "label": "cc-ing accountant",
    },
    # --- Spanish / bilingual (Houston market) ---
    {
        "body": "No me interesa, gracias.",
        "expected": "negative",
        "label": "spanish not interested",
    },
    {
        "body": "Si, llamame por favor. Quiero saber mas.",
        "expected": "positive",
        "label": "spanish interested",
    },
    # --- Questions without clear intent ---
    {
        "body": "How did you get my email?",
        "expected": "neutral",
        "label": "questioning source",
    },
    {
        "body": "What company is this?",
        "expected": "neutral",
        "label": "asking who we are",
    },
    # --- Pricing / valuation questions ---
    {
        "body": "How much is my business worth? I might be open to selling.",
        "expected": "positive",
        "label": "valuation question with interest",
    },
    {
        "body": "What kind of offers have you seen for car washes in Houston?",
        "expected": "neutral",
        "label": "market research question — no explicit interest",
    },
    # --- Conditional interest ---
    {
        "body": "If the price is right, I'd consider it. But only if above $2M.",
        "expected": "positive",
        "label": "conditional with price floor",
    },
    # --- Already sold / not applicable ---
    {
        "body": "Too late, sold the business last month.",
        "expected": "negative",
        "accept": ["negative", "neutral"],
        "label": "already sold — ambiguous between negative/neutral",
    },
    {
        "body": "I'm under contract with another broker already.",
        "expected": "negative",
        "label": "already with another broker",
    },
    # --- Phone number in negative context (trap case) ---
    {
        "body": "Don't call me at 555-0199 again. Remove me now.",
        "expected": "negative",
        "label": "phone in negative context — must NOT be hot_positive",
    },
    # --- Auto-reply / bounce variants ---
    {
        "body": "This mailbox is not monitored. Please contact info@example.com.",
        "expected": "neutral",
        "label": "unmonitored mailbox",
    },
    {
        "body": "Delivery Status Notification (Failure): message not delivered.",
        "expected": "neutral",
        "label": "bounce notification",
    },
    # --- Enthusiastic hot lead ---
    {
        "body": "Yes! My number is 713-555-0888. Ready to talk today.",
        "expected": "hot_positive",
        "label": "enthusiastic with phone number",
    },
]


class TestMockClassifier:
    @pytest.mark.parametrize(
        "case",
        SAMPLE_REPLIES[:MOCK_COMPATIBLE],
        ids=[c["label"] for c in SAMPLE_REPLIES[:MOCK_COMPATIBLE]],
    )
    def test_mock_classification(self, case):
        result = classify_mock(case["body"])
        assert result == case["expected"], f"got={result}"


class TestRealClassifier:
    @pytest.mark.parametrize(
        "case",
        SAMPLE_REPLIES,
        ids=[c["label"] for c in SAMPLE_REPLIES],
    )
    def test_real_classification(self, case):
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            pytest.skip("OPENROUTER_API_KEY not set")
        result = classify(case["body"], mock=False)
        accept = case.get("accept", [case["expected"]])
        assert result in accept, f"expected one of {accept}, got={result}"


class TestClassifierMalformedOutput:
    """Test that classify_real() handles edge-case LLM responses."""

    @pytest.mark.parametrize(
        "raw_output,expected",
        [
            ("positive.", "positive"),
            (" positive\n", "positive"),
            ("POSITIVE", "positive"),
            ("negative!", "negative"),
            ("hot_positive,", "hot_positive"),
            ("The answer is neutral", "neutral"),
            ("", "neutral"),
            ("maybe", "neutral"),
            ("I think positive", "neutral"),  # "I" is not in VALID_CLASSES
        ],
    )
    def test_malformed_output_handling(self, raw_output, expected, monkeypatch):
        """Mock chat_completion to return malformed strings, verify robust parsing."""
        import modules.llm_client as llm_mod

        monkeypatch.setattr(llm_mod, "chat_completion", lambda **kwargs: raw_output)
        from modules.reply_classifier import classify_real

        result = classify_real("test body")
        assert result == expected, f"input={raw_output!r}, expected={expected}, got={result}"
