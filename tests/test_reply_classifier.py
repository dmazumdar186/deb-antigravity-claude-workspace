#!/usr/bin/env python3
"""
test_reply_classifier.py
description: Tests the reply classifier module with both mock and real Claude Haiku calls.
inputs: ANTHROPIC_API_KEY in .env (for real mode)
outputs: Pass/fail results to stdout
usage: py tests/test_reply_classifier.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "execution"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from modules.reply_classifier import classify, classify_mock

SAMPLE_REPLIES = [
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
]


def run_mock_tests():
    print("=== Mock Classifier Tests ===")
    passed = 0
    for case in SAMPLE_REPLIES:
        result = classify_mock(case["body"])
        status = "PASS" if result == case["expected"] else "FAIL"
        if status == "PASS":
            passed += 1
        print(f"  [{status}] {case['label']}: expected={case['expected']}, got={result}")
    print(f"  Mock: {passed}/{len(SAMPLE_REPLIES)} passed\n")
    return passed == len(SAMPLE_REPLIES)


def run_real_tests():
    print("=== Real Claude Classifier Tests ===")
    passed = 0
    for case in SAMPLE_REPLIES:
        result = classify(case["body"], mock=False)
        status = "PASS" if result == case["expected"] else "FAIL"
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
