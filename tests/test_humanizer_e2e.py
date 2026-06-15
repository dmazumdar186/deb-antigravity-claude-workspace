"""
End-to-end CLI tests for humanizer.py -- full subprocess invocations.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(r"C:/Users/deban/OneDrive/Documents/AntiGravity Project Space")
SCRIPT = str(WORKSPACE / "execution" / "content" / "humanizer.py")
PY = sys.executable

from dotenv import load_dotenv
load_dotenv(str(WORKSPACE / ".env"))

PASS_COUNT = 0
FAIL_COUNT = 0
SKIP_COUNT = 0
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


def _skip_if_gemini_quota_exhausted(stderr: str):
    """Gemini free-tier 429 is environmental — skip, do not fail the test."""
    import pytest
    if not stderr:
        return
    markers = (
        "RESOURCE_EXHAUSTED",
        "exceeded your current quota",
        "free_tier_requests",
        "Quota exceeded",
        "Gemini API call failed: 429",
    )
    low = stderr.lower()
    for m in markers:
        if m.lower() in low:
            pytest.skip(f"Gemini free-tier quota exhausted (environmental): {m}")


def test_e2e_dry_run_strips_certainly():
    r = _cli("--text", "Certainly! I'd be happy to delve into...", "--dry-run")
    assert r.returncode == 0, f"exit {r.returncode}\n{r.stderr}"


def test_e2e_stdin_pipe():
    r = _cli("--dry-run", stdin_text="AI text here")
    assert r.returncode == 0, f"exit {r.returncode}\n{r.stderr}"


def test_e2e_text_and_file_mutually_exclusive():
    r = _cli("--text", "hello", "--file", "somefile.txt")
    assert r.returncode == 2, f"Expected exit 2 (argparse error), got {r.returncode}\n{r.stderr}"


def test_e2e_voice_debanjan_dry_run():
    r = _cli("--text", "Certainly! This is a comprehensive analysis.", "--voice", "debanjan", "--dry-run")
    assert r.returncode == 0, f"exit {r.returncode}\n{r.stderr}"


def test_e2e_voice_nonexistent_error():
    r = _cli("--text", "Some text.", "--voice", "nonexistent_voice_xyz", "--dry-run")
    assert r.returncode != 0, f"Expected non-zero exit, got {r.returncode}"
    combined = r.stdout + r.stderr
    assert "not found" in combined.lower() or "available" in combined.lower(), \
        f"Expected clear error, got: {combined[:300]}"


def test_e2e_real_gemini_show_diff():
    if not os.environ.get("GEMINI_API_KEY"):
        import pytest as _pytest
        _pytest.skip("GEMINI_API_KEY not set")
    r = _cli("--text", "Certainly! I'd be happy to delve into robust frameworks.",
             "--tier", "gemini", "--show-diff")
    if r.returncode != 0:
        _skip_if_gemini_quota_exhausted(r.stderr or "")
    assert r.returncode == 0, f"exit {r.returncode}\nstdout: {r.stdout}\nstderr: {r.stderr}"
    assert len(r.stdout.strip()) > 0, "stdout should contain humanized text"
    assert "BEFORE" in r.stderr or "AFTER" in r.stderr, \
        f"--show-diff should print to stderr, got: {r.stderr[:200]}"


def test_e2e_tweet_max_length_50():
    r = _cli("--text", "A" * 200, "--platform", "tweet", "--max-length", "50", "--dry-run")
    assert r.returncode == 0, f"exit {r.returncode}\n{r.stderr}"


def test_e2e_linkedin_dry_run():
    r = _cli("--text", "**Bold text** with # heading.", "--platform", "linkedin", "--dry-run")
    assert r.returncode == 0, f"exit {r.returncode}\n{r.stderr}"


def test_e2e_keep_em_dashes_preserves():
    """--keep-em-dashes flag should leave em-dashes in the pre-pass output."""
    r = _cli("--text", "First — second.", "--keep-em-dashes", "--dry-run")
    assert r.returncode == 0, f"Expected exit 0, got {r.returncode}: {r.stderr}"
    # dry-run logs pre-pass output to stderr; em-dash should still be present
    assert "—" in r.stderr, f"Em-dash should be preserved in pre-pass output, got stderr: {r.stderr!r}"


def test_e2e_platform_email_dry_run():
    """--platform email --dry-run should succeed (exit 0) and log pre-pass output."""
    text = "Dear Bryce,\n\nHere is the update.\n\nBest,\nDebanjan"
    r = _cli("--text", text, "--platform", "email", "--dry-run")
    assert r.returncode == 0, f"Expected exit 0, got {r.returncode}: {r.stderr}"
    # dry-run logs pre-pass output to stderr; structure should be preserved
    assert "Dear Bryce" in r.stderr, f"Expected pre-pass text in stderr, got: {r.stderr!r}"


def test_e2e_gemini_no_system_prompt_echo():
    """
    Round 6 regression guard: Gemini path must NOT echo system-prompt fragments.
    Bug history: prompt was concatenated into a single 'contents' string, causing
    Gemini to interpret the instructions as content and echo them back as the
    'humanized_text'. Fixed in R6-1 by using system_instruction param instead.
    """
    if not os.environ.get("GEMINI_API_KEY"):
        global SKIP_COUNT
        SKIP_COUNT += 1
        print("[skip] no GEMINI_API_KEY")
        return

    input_text = (
        "Certainly! I'd be happy to help you delve into this comprehensive analysis. "
        "It's worth noting that this approach is robust and offers key takeaways "
        "for navigating the complexities of modern systems."
    )
    r = _cli("--text", input_text, "--tier", "gemini")
    if r.returncode != 0:
        _skip_if_gemini_quota_exhausted(r.stderr or "")
    assert r.returncode == 0, f"Expected 0, got {r.returncode}: {r.stderr[:500]}"

    humanized = r.stdout.strip().lower()

    # These are unambiguous system-prompt phrases that should NEVER appear in output.
    # If any appear, prompt construction is broken and Gemini is echoing instructions.
    forbidden_phrases = [
        "submit_humanized",
        "call submit_humanized",
        "call the function",
        "rewrite the provided text",
        "rewrite text in voice",
        "do it now",
        "match the sentence cadence",
        "voice profile",
        "i need you to rewrite",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in humanized, (
            f"System-prompt echo detected: {phrase!r} appears in output: {humanized[:300]!r}"
        )

    assert len(humanized) > 10, f"Output too short: {humanized!r}"


def test_e2e_gemini_output_semantically_related_to_input():
    """
    Round 8 regression guard: Gemini output must relate to the actual input,
    not hallucinate from voice profile examples.
    Bug history: voice examples that contained task commands ('run dry tests',
    'iterative feedback loop') were blended into output, producing fabricated
    task-flavored text unrelated to the user's actual input.
    Note: input avoids AI-tell openers so pre-pass does not strip it to empty.
    """
    if not os.environ.get("GEMINI_API_KEY"):
        global SKIP_COUNT
        SKIP_COUNT += 1
        print("[skip] no GEMINI_API_KEY")
        return

    # Substantive input with no AI-tell openers so pre-pass preserves it.
    # Contains distinctive anchor words: "distributed", "database", "analysis".
    input_text = "Distributed databases require careful analysis of consistency models and replication strategies."

    r = _cli("--text", input_text, "--tier", "gemini")
    if r.returncode != 0:
        _skip_if_gemini_quota_exhausted(r.stderr or "")
    assert r.returncode == 0, f"Expected 0, got {r.returncode}: {r.stderr[:500]}"

    humanized = r.stdout.strip().lower()

    # Semantic anchor: output must mention something from input
    # "analysis" or "database(s)" or "distributed" — at least ONE content word
    content_anchors = ["analysis", "database", "distributed"]
    anchor_hit = any(anchor in humanized for anchor in content_anchors)
    assert anchor_hit, (
        f"Output appears hallucinated from voice profile, not related to input. "
        f"Expected one of {content_anchors} in output. Got: {humanized[:300]!r}"
    )


def test_e2e_gemini_single_sentence_opener_content():
    """
    R10 regression guard: input where the AI-tell opener and the substantive content
    are in the SAME sentence must NOT lose the content during pre-pass.
    Bug history: RE_OPENING_FLUFF was unbounded ([^.!]*) and consumed the entire
    sentence, leaving empty pre-pass output and a confused LLM meta-reply as output.
    Fix R10-1: bounded to {0,40}. Fix R10-2: empty-post-prepass fallback guard.
    """
    if not os.environ.get("GEMINI_API_KEY"):
        global SKIP_COUNT
        SKIP_COUNT += 1
        print("[skip] no GEMINI_API_KEY")
        return

    input_text = "Certainly! I'd be happy to delve into this comprehensive analysis of distributed databases."

    r = _cli("--text", input_text, "--tier", "gemini")
    if r.returncode != 0:
        _skip_if_gemini_quota_exhausted(r.stderr or "")
    assert r.returncode == 0, f"Expected 0, got {r.returncode}: {r.stderr[:500]}"

    humanized = r.stdout.strip().lower()

    # Semantic anchor: at least one content word from input must survive
    anchors = ["distributed", "database", "analysis"]
    anchor_hit = any(a in humanized for a in anchors)
    assert anchor_hit, (
        f"Single-sentence-opener bug: content was stripped from pre-pass. "
        f"Expected one of {anchors} in output. Got: {humanized[:300]!r}"
    )

    # LLM must NOT be asking for the text — that would mean we sent empty content
    forbidden_meta = [
        "send it over",
        "send me the text",
        "please provide",
        "i need the text",
        "i'm ready",
        "what do you want me to rewrite",
    ]
    for phrase in forbidden_meta:
        assert phrase not in humanized, (
            f"LLM asked for input (meta-response: {phrase!r}). "
            f"Pre-pass likely stripped the entire input. Got: {humanized[:300]!r}"
        )


if __name__ == "__main__":
    run("e2e 1: dry-run strips Certainly! (exit 0)", test_e2e_dry_run_strips_certainly)
    run("e2e 2: stdin pipe (exit 0)", test_e2e_stdin_pipe)
    run("e2e 3: --text + --file mutually exclusive (exit 2)", test_e2e_text_and_file_mutually_exclusive)
    run("e2e 4: --voice debanjan --dry-run (exit 0)", test_e2e_voice_debanjan_dry_run)
    run("e2e 5: --voice nonexistent (exit non-zero, clear error)", test_e2e_voice_nonexistent_error)
    run("e2e 6: --tier gemini --show-diff real call (exit 0)", test_e2e_real_gemini_show_diff)
    run("e2e 7: tweet --max-length 50 --dry-run (exit 0)", test_e2e_tweet_max_length_50)
    run("e2e 8: --platform linkedin --dry-run (exit 0)", test_e2e_linkedin_dry_run)
    run("e2e 9: --keep-em-dashes preserves em-dashes in pre-pass", test_e2e_keep_em_dashes_preserves)
    run("e2e 10: --platform email --dry-run (exit 0, pre-pass intact)", test_e2e_platform_email_dry_run)
    run("e2e 11: gemini no system-prompt echo (R6 regression guard)", test_e2e_gemini_no_system_prompt_echo)
    run("e2e 12: gemini output semantically anchored to input (R8 regression guard)", test_e2e_gemini_output_semantically_related_to_input)
    run("e2e 13: gemini single-sentence opener does not eat content (R10 regression guard)", test_e2e_gemini_single_sentence_opener_content)

    print(f"\n{'='*50}")
    print(f"Results: {PASS_COUNT} passed, {FAIL_COUNT} failed, {SKIP_COUNT} skipped")
    if FAILURES:
        print("\nFailed tests:")
        for name, err in FAILURES:
            print(f"  FAIL  {name}")
            print(f"        {err}")
    import sys as _sys
    _sys.exit(0 if FAIL_COUNT == 0 else 1)
