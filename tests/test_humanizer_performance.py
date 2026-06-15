"""
Performance tests for humanizer.py. Measures wall-clock thresholds.
Real Gemini call only if GEMINI_API_KEY is set.
"""
from __future__ import annotations

import concurrent.futures
import os
import subprocess
import sys
import time
from pathlib import Path

WORKSPACE = Path(r"C:/Users/deban/OneDrive/Documents/AntiGravity Project Space")
SCRIPT = str(WORKSPACE / "execution" / "content" / "humanizer.py")
PY = sys.executable

sys.path.insert(0, str(WORKSPACE / "execution" / "content"))
sys.path.insert(0, str(WORKSPACE / "execution" / "modules"))

from dotenv import load_dotenv
load_dotenv(str(WORKSPACE / ".env"))

PASS_COUNT = 0
FAIL_COUNT = 0
FAILURES = []


def run(name, fn):
    global PASS_COUNT, FAIL_COUNT
    try:
        fn()
        print(f"PASS  {name}")
        PASS_COUNT += 1
    except Exception as exc:
        print(f"FAIL  {name}")
        print(f"      {exc}")
        FAIL_COUNT += 1
        FAILURES.append((name, str(exc)))


def _cli(*args, stdin_text=None):
    return subprocess.run(
        [PY, SCRIPT, *args],
        input=stdin_text, capture_output=True, text=True,
        encoding="utf-8", errors="replace", cwd=str(WORKSPACE),
    )


def test_perf_dry_run_500chars():
    text = "This is a test. " * 32  # ~512 chars
    start = time.perf_counter()
    r = _cli("--text", text, "--dry-run")
    elapsed = time.perf_counter() - start
    assert r.returncode == 0
    assert elapsed < 10.0, f"dry-run took {elapsed:.2f}s (threshold: 10s)"
    print(f"      dry-run 500ch: {elapsed:.3f}s (< 10s OK)")


def test_perf_pre_pass_5000chars():
    from humanizer import _rules_pre_pass, load_voice, DEFAULT_VOICE
    voice = load_voice(DEFAULT_VOICE)
    text = ("Certainly! I'd be happy to delve into this robust framework. " * 50)[:5000]
    start = time.perf_counter()
    cleaned, flags = _rules_pre_pass(text, voice)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, f"pre_pass on 5000ch took {elapsed:.4f}s (threshold: 1s)"
    print(f"      pre_pass 5000ch: {elapsed:.4f}s (< 1s OK)")


def test_perf_pre_pass_adversarial():
    from humanizer import _rules_pre_pass, load_voice, DEFAULT_VOICE
    voice = load_voice(DEFAULT_VOICE)
    # 100x "Certainly! " -- tests for catastrophic backtracking
    text = "Certainly! " * 100
    start = time.perf_counter()
    cleaned, flags = _rules_pre_pass(text, voice)
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"adversarial pre_pass took {elapsed:.4f}s (threshold: 2s)"
    print(f"      adversarial pre_pass (100x Certainly!): {elapsed:.4f}s (< 2s OK)")


def test_perf_real_gemini_300chars():
    import pytest as _pytest
    if not os.environ.get("GEMINI_API_KEY"):
        _pytest.skip("GEMINI_API_KEY not set")
    text = "Certainly! I'd be happy to explain how this comprehensive system leverages robust synergies."
    start = time.perf_counter()
    r = _cli("--text", text, "--tier", "gemini")
    elapsed = time.perf_counter() - start
    if r.returncode != 0:
        # Gemini free-tier 429 is environmental — skip, don't fail
        stderr_low = (r.stderr or "").lower()
        for m in ("resource_exhausted", "exceeded your current quota", "free_tier_requests", "quota exceeded"):
            if m in stderr_low:
                _pytest.skip(f"Gemini free-tier quota exhausted: {m}")
    assert r.returncode == 0, f"Gemini call failed: {r.stderr}"
    assert elapsed < 30.0, f"Gemini 300ch call took {elapsed:.2f}s (threshold: 30s)"
    print(f"      Gemini real call 300ch: {elapsed:.2f}s (< 30s OK)")


def test_perf_cost_estimate_1000chars():
    """For a ~1000-char text input, estimated cost should be reasonable (< $0.05 with full voice profile)."""
    # The voice profile adds ~950 tokens of context — that's correct, just account for it.
    from humanizer import _build_humanize_prompt, _rules_pre_pass, load_voice, DEFAULT_VOICE, _TIER_COST_PER_M
    voice = load_voice(DEFAULT_VOICE)
    text = "This is a test sentence with some AI-tells. " * 20  # ~880 chars
    pre_cleaned, flags = _rules_pre_pass(text, voice)
    system_p, user_p = _build_humanize_prompt(pre_cleaned, voice, flags, "generic")
    estimated_input_tokens = (len(system_p) + len(user_p)) // 4 + 200
    prices = _TIER_COST_PER_M.get("default", {"input": 3.0, "output": 15.0})
    cost = (estimated_input_tokens * prices["input"] + 200 * prices["output"]) / 1_000_000
    assert 0.0 < cost < 0.05, f"Cost estimate ${cost:.6f} outside expected range for default tier"
    print(f"      estimated cost for ~1000ch: ${cost:.6f} (< $0.05 OK)")


def test_perf_concurrent_dry_runs():
    text_a = "AI generated text A with certainly and delve."
    text_b = "AI generated text B with leverage and robust frameworks."

    def run_dry(text):
        return _cli("--text", text, "--dry-run")

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        fa = ex.submit(run_dry, text_a)
        fb = ex.submit(run_dry, text_b)
        ra = fa.result(timeout=30)
        rb = fb.result(timeout=30)

    assert ra.returncode == 0, f"Concurrent dry-run A failed: {ra.stderr}"
    assert rb.returncode == 0, f"Concurrent dry-run B failed: {rb.stderr}"
    print("      two concurrent dry-runs: both exit 0, no collision")


if __name__ == "__main__":
    run("perf 1: dry-run 500ch < 10s", test_perf_dry_run_500chars)
    run("perf 2: pre_pass 5000ch < 1s", test_perf_pre_pass_5000chars)
    run("perf 3: adversarial pre_pass (100x Certainly!) < 2s", test_perf_pre_pass_adversarial)
    run("perf 4: real Gemini 300ch < 30s", test_perf_real_gemini_300chars)
    run("perf 5: cost estimate for 1000ch < $0.05", test_perf_cost_estimate_1000chars)
    run("perf 6: two concurrent dry-runs, no collision", test_perf_concurrent_dry_runs)

    print(f"\n{'='*50}")
    print(f"Results: {PASS_COUNT} passed, {FAIL_COUNT} failed")
    if FAILURES:
        print("\nFailed tests:")
        for name, err in FAILURES:
            print(f"  FAIL  {name}")
            print(f"        {err}")
    import sys as _sys
    _sys.exit(0 if FAIL_COUNT == 0 else 1)
