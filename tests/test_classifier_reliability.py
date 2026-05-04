"""
test_classifier_reliability.py
description: Runs the classifier golden set 3x to measure consistency. Flags fragile cases.
inputs: OPENROUTER_API_KEY in .env (skips all tests if missing).
outputs: pytest results + printed reliability report.
"""

import os
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "execution"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

SKIP_REASON = "OPENROUTER_API_KEY not set — skipping reliability tests"
HAS_API_KEY = bool(os.environ.get("OPENROUTER_API_KEY", ""))

from modules.reply_classifier import classify
from test_reply_classifier import SAMPLE_REPLIES

RUNS = 3


def _classify_n_times(body: str, n: int) -> list[str]:
    return [classify(body, mock=False) for _ in range(n)]


@pytest.mark.skipif(not HAS_API_KEY, reason=SKIP_REASON)
class TestClassifierReliability:

    @pytest.fixture(scope="class", autouse=True)
    def _run_all_classifications(self, request):
        """Run the full golden set RUNS times and store results on the class."""
        results = {}
        for case in SAMPLE_REPLIES:
            runs = _classify_n_times(case["body"], RUNS)
            results[case["label"]] = {
                "expected": case["expected"],
                "runs": runs,
                "consistent": len(set(runs)) == 1,
                "all_correct": all(r == case["expected"] for r in runs),
                "any_correct": any(r == case["expected"] for r in runs),
            }
        request.cls.results = results
        _print_report(results)

    def test_pass_at_3_capability(self):
        """At least 1 of 3 runs returns the expected classification (capability check)."""
        failures = []
        for label, data in self.results.items():
            if not data["any_correct"]:
                failures.append(
                    f"  {label}: expected={data['expected']}, got={data['runs']}"
                )
        if failures:
            pytest.fail(
                f"pass@3 failures — classifier never returned expected class:\n"
                + "\n".join(failures)
            )

    def test_pass_cubed_reliability(self):
        """All 3 runs return the expected classification (reliability check)."""
        failures = []
        for label, data in self.results.items():
            if not data["all_correct"]:
                failures.append(
                    f"  {label}: expected={data['expected']}, got={data['runs']}"
                )
        total = len(self.results)
        reliable = total - len(failures)
        rate = reliable / total * 100 if total else 0

        if failures:
            msg = (
                f"pass^3 reliability: {reliable}/{total} ({rate:.0f}%)\n"
                f"Inconsistent cases:\n" + "\n".join(failures)
            )
            if rate < 70:
                pytest.fail(msg)
            else:
                pytest.xfail(msg)

    def test_consistency(self):
        """Flag cases where the classifier gives different answers across runs."""
        inconsistent = [
            f"  {label}: {data['runs']}"
            for label, data in self.results.items()
            if not data["consistent"]
        ]
        total = len(self.results)
        consistent = total - len(inconsistent)

        if inconsistent:
            msg = (
                f"Consistency: {consistent}/{total} cases stable across {RUNS} runs\n"
                f"Unstable cases:\n" + "\n".join(inconsistent)
            )
            if consistent / total < 0.7:
                pytest.fail(msg)
            else:
                pytest.xfail(msg)


def _print_report(results: dict):
    print(f"\n{'='*70}")
    print(f"CLASSIFIER RELIABILITY REPORT ({RUNS} runs per case)")
    print(f"{'='*70}")
    print(f"{'Label':<45} {'Expected':<14} {'Runs':<30} {'Status'}")
    print(f"{'-'*45} {'-'*14} {'-'*30} {'-'*8}")

    consistent_count = 0
    correct_count = 0

    for label, data in results.items():
        runs_str = ", ".join(data["runs"])
        if data["all_correct"]:
            status = "PASS"
            correct_count += 1
            consistent_count += 1
        elif data["consistent"]:
            status = "WRONG"
            consistent_count += 1
        else:
            status = "FLAKY"

        short_label = label[:44]
        print(f"  {short_label:<44} {data['expected']:<14} {runs_str:<30} {status}")

    total = len(results)
    print(f"\n  Consistent: {consistent_count}/{total} ({consistent_count/total*100:.0f}%)")
    print(f"  All-correct: {correct_count}/{total} ({correct_count/total*100:.0f}%)")
    any_correct = sum(1 for d in results.values() if d["any_correct"])
    print(f"  Any-correct: {any_correct}/{total} ({any_correct/total*100:.0f}%)")
    print(f"{'='*70}\n")
