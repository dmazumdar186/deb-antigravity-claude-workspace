#!/usr/bin/env python3
"""
test_reply_classifier.py
description: Tests the reply classifier module with both mock and real LLM calls.
inputs: OPENROUTER_API_KEY in .env (for real mode)
outputs: Pass/fail results to stdout
usage: py tests/test_reply_classifier.py
"""

import os
import sys
from pathlib import Path

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
        "expected": "negative",
        "accept": ["negative", "positive", "neutral"],
        "label": "future interest — inherently ambiguous",
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


def run_mock_tests():
    """Mock classifier only tested against the original keyword-compatible cases."""
    mock_cases = SAMPLE_REPLIES[:MOCK_COMPATIBLE]
    print(f"=== Mock Classifier Tests ({len(mock_cases)} keyword-compatible cases) ===")
    passed = 0
    for case in mock_cases:
        result = classify_mock(case["body"])
        status = "PASS" if result == case["expected"] else "FAIL"
        if status == "PASS":
            passed += 1
        print(f"  [{status}] {case['label']}: expected={case['expected']}, got={result}")
    print(f"  Mock: {passed}/{len(mock_cases)} passed\n")
    return passed == len(mock_cases)


def run_real_tests():
    """Real LLM classifier tested against the full 32-case golden set."""
    print(f"=== Real Claude Classifier Tests ({len(SAMPLE_REPLIES)} golden set cases) ===")
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("  SKIPPED — OPENROUTER_API_KEY not set in .env")
        print("  To enable: add your key from openrouter.ai to .env\n")
        return True

    passed = 0
    for case in SAMPLE_REPLIES:
        result = classify(case["body"], mock=False)
        accept = case.get("accept", [case["expected"]])
        status = "PASS" if result in accept else "FAIL"
        if status == "PASS":
            passed += 1
        print(f"  [{status}] {case['label']}: expected={case['expected']}, got={result}")
    print(f"  Real: {passed}/{len(SAMPLE_REPLIES)} passed\n")
    return passed == len(SAMPLE_REPLIES)


if __name__ == "__main__":
    mock_ok = run_mock_tests()
    real_ok = run_real_tests()

    if mock_ok and real_ok:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
        sys.exit(1)
