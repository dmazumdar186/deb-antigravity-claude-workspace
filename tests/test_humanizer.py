"""Tests for execution/content/humanizer.py — deterministic pre-pass, voice loader,
platform post-process, and CLI contract. Uses the same run(label, fn) harness as
test_youtube_analyzer_unit.py. No LLM calls: all live-API tests use --dry-run."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(r"C:/Users/deban/OneDrive/Documents/AntiGravity Project Space")
sys.path.insert(0, str(WORKSPACE / "execution" / "content"))
sys.path.insert(0, str(WORKSPACE / "execution" / "modules"))

from dotenv import load_dotenv

load_dotenv(str(WORKSPACE / ".env"))

# Import the functions under test
from humanizer import (
    _rules_pre_pass,
    _platform_post_process,
    load_voice,
    DEFAULT_VOICE,
    VOICES_DIR,
)

# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------

PASS_COUNT = 0
FAIL_COUNT = 0
FAILURES: list[tuple[str, str]] = []


def run(name: str, fn) -> None:
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


# ---------------------------------------------------------------------------
# Pre-pass tests (deterministic, no LLM)
# ---------------------------------------------------------------------------

def test_strips_certainly():
    voice = load_voice(DEFAULT_VOICE)
    cleaned, _ = _rules_pre_pass("Certainly! Here is the answer.", voice)
    assert "Certainly" not in cleaned, f"Expected 'Certainly' stripped, got: {cleaned!r}"


def test_strips_certainly_no_space():
    voice = load_voice(DEFAULT_VOICE)
    cleaned, _ = _rules_pre_pass("Certainly!Here is the answer.", voice)
    assert "Certainly" not in cleaned, f"'Certainly' should be stripped, got: {cleaned!r}"


def test_strips_id_be_happy_to():
    voice = load_voice(DEFAULT_VOICE)
    cleaned, _ = _rules_pre_pass("I'd be happy to help you with that.", voice)
    assert "I'd be happy to" not in cleaned, f"'I'd be happy to' should be stripped, got: {cleaned!r}"


def test_strips_closing_fluff():
    voice = load_voice(DEFAULT_VOICE)
    cleaned, _ = _rules_pre_pass("Here is the answer. I hope this helps!", voice)
    assert "I hope this helps" not in cleaned, f"Closing fluff should be stripped, got: {cleaned!r}"


def test_strips_let_me_know():
    voice = load_voice(DEFAULT_VOICE)
    cleaned, _ = _rules_pre_pass("Done. Let me know if you have any questions.", voice)
    assert "Let me know if" not in cleaned, f"'Let me know if' closing should be stripped"


def test_replaces_em_dashes():
    voice = load_voice(DEFAULT_VOICE)
    cleaned, _ = _rules_pre_pass("This is great — or is it?", voice)
    assert "—" not in cleaned, f"Em-dash should be replaced, got: {cleaned!r}"
    assert "-" in cleaned, f"Em-dash should become ' - ', got: {cleaned!r}"


def test_keep_em_dashes():
    voice = load_voice(DEFAULT_VOICE)
    cleaned, _ = _rules_pre_pass("This is great — or is it?", voice, keep_em_dashes=True)
    assert "—" in cleaned, f"Em-dash should be preserved with keep_em_dashes=True, got: {cleaned!r}"


def test_flags_banned_vocab_delve():
    voice = load_voice(DEFAULT_VOICE)
    _, flags = _rules_pre_pass("Let me delve into this topic.", voice)
    found = any("delve" in f for f in flags)
    assert found, f"Expected 'delve' flagged, got flags: {flags}"


def test_flags_banned_vocab_leverage():
    voice = load_voice(DEFAULT_VOICE)
    _, flags = _rules_pre_pass("We can leverage this approach.", voice)
    found = any("leverage" in f for f in flags)
    assert found, f"Expected 'leverage' flagged, got flags: {flags}"


def test_flags_banned_vocab_robust():
    voice = load_voice(DEFAULT_VOICE)
    _, flags = _rules_pre_pass("This is a robust framework.", voice)
    found = any("robust" in f for f in flags)
    assert found, f"Expected 'robust' flagged, got flags: {flags}"


def test_flags_triple_parallel():
    voice = load_voice(DEFAULT_VOICE)
    _, flags = _rules_pre_pass(
        "This is not just a tool, but a system, and even a philosophy.", voice
    )
    found = any("triple-parallel" in f for f in flags)
    assert found, f"Expected triple-parallel flagged, got flags: {flags}"


def test_flags_hedges():
    voice = load_voice(DEFAULT_VOICE)
    _, flags = _rules_pre_pass("It's worth noting that this approach works.", voice)
    found = any("hedge" in f for f in flags)
    assert found, f"Expected hedge flagged, got flags: {flags}"


def test_empty_text_returns_empty():
    voice = load_voice(DEFAULT_VOICE)
    cleaned, flags = _rules_pre_pass("", voice)
    assert cleaned == "", f"Empty input should return empty, got: {cleaned!r}"
    assert flags == [], f"Empty input should return no flags, got: {flags}"


def test_whitespace_only_returns_empty():
    voice = load_voice(DEFAULT_VOICE)
    cleaned, flags = _rules_pre_pass("   ", voice)
    assert flags == [], f"Whitespace input should return no flags, got: {flags}"


def test_no_false_positive_flags():
    voice = load_voice(DEFAULT_VOICE)
    clean_text = "This is a direct message. Let me know what you think."
    # "Let me know" is in voice.lexicon.uses — should NOT be flagged as banned
    _, flags = _rules_pre_pass(clean_text, voice)
    # no banned vocab in the clean_text (delve, leverage, etc.)
    banned_flags = [f for f in flags if "banned-vocab" in f and
                    any(bw in f for bw in ["delve", "leverage", "robust", "comprehensive"])]
    assert not banned_flags, f"No banned vocab should be flagged for clean text, got: {banned_flags}"


# ---------------------------------------------------------------------------
# Voice loader tests
# ---------------------------------------------------------------------------

def test_load_voice_debanjan():
    voice = load_voice("debanjan")
    assert isinstance(voice, dict), "load_voice should return a dict"
    assert "name" in voice
    assert "display_name" in voice
    assert "traits" in voice
    assert "lexicon" in voice
    assert "examples" in voice


def test_load_voice_has_examples():
    voice = load_voice("debanjan")
    examples = voice.get("examples", [])
    assert len(examples) >= 5, f"Expected >= 5 examples, got {len(examples)}"


def test_load_voice_has_avoids():
    voice = load_voice("debanjan")
    avoids = voice.get("lexicon", {}).get("avoids", [])
    assert len(avoids) > 0, "Voice should have avoids list"


def test_load_voice_nonexistent_raises():
    raised = False
    try:
        load_voice("this_voice_does_not_exist_xyz")
    except SystemExit:
        raised = True
    assert raised, "load_voice with nonexistent name should raise SystemExit"


def test_load_voice_schema_fields():
    voice = load_voice("debanjan")
    required_keys = {"name", "display_name", "description", "traits", "lexicon", "examples"}
    missing = required_keys - set(voice.keys())
    assert not missing, f"Voice profile missing keys: {missing}"


def test_template_exists():
    template_path = VOICES_DIR / "_template.json"
    assert template_path.exists(), f"Template not found at {template_path}"


# ---------------------------------------------------------------------------
# Platform post-process tests
# ---------------------------------------------------------------------------

def test_linkedin_strips_bold():
    result = _platform_post_process("This is **bold text** here.", "linkedin", None)
    assert "**" not in result, f"LinkedIn should strip **bold**, got: {result!r}"
    assert "bold text" in result, f"Bold content should remain: {result!r}"


def test_linkedin_strips_headings():
    result = _platform_post_process("# My Heading\nBody text.", "linkedin", None)
    assert "#" not in result, f"LinkedIn should strip # headings, got: {result!r}"
    assert "My Heading" in result, f"Heading content should remain: {result!r}"


def test_linkedin_strips_italic():
    result = _platform_post_process("This is *italic* text.", "linkedin", None)
    assert "*italic*" not in result, f"LinkedIn should strip *italic*, got: {result!r}"


def test_tweet_hard_cap():
    long_text = "a" * 300
    result = _platform_post_process(long_text, "tweet", None)
    assert len(result) <= 280, f"Tweet should be <= 280 chars, got {len(result)}"


def test_tweet_custom_max_length():
    long_text = "b" * 300
    result = _platform_post_process(long_text, "tweet", 100)
    assert len(result) <= 100, f"Tweet with custom cap should be <= 100 chars, got {len(result)}"


def test_tweet_no_truncation_if_short():
    short_text = "Short tweet."
    result = _platform_post_process(short_text, "tweet", None)
    assert result == short_text, f"Short tweet should not be modified, got: {result!r}"


def test_email_preserves_structure():
    email_text = "Hi,\n\nHere is point 1.\nHere is point 2.\n\nThanks."
    result = _platform_post_process(email_text, "email", None)
    assert "\n" in result, f"Email should preserve newlines, got: {result!r}"


def test_generic_minimal_changes():
    text = "A simple sentence."
    result = _platform_post_process(text, "generic", None)
    assert result == text, f"Generic should not change simple text, got: {result!r}"


def test_generic_max_length():
    long_text = "x" * 200
    result = _platform_post_process(long_text, "generic", 50)
    assert len(result) <= 50, f"Generic max_length should cap output, got {len(result)}"


def test_slack_strips_headings():
    result = _platform_post_process("## My Heading\nMessage body.", "slack", None)
    assert "#" not in result, f"Slack should strip headings, got: {result!r}"


# R10-3: Regression guard — single-sentence opener must not eat substantive content
def test_prepass_preserves_content_in_single_sentence_opener():
    """
    R10 unit regression: pre-pass must NOT strip the entire sentence when the
    AI-tell opener and the substantive content are combined in one sentence.
    Bug history: RE_OPENING_FLUFF used [^.!]* (unbounded), consuming the whole
    sentence on single-sentence inputs like "I'd be happy to <content>."
    Fix R10-1: bounded to [^.!]{0,40} so only short courtesy phrases match.
    """
    voice = load_voice(DEFAULT_VOICE)
    input_text = "I'd be happy to delve into this comprehensive analysis of distributed databases."
    cleaned, _ = _rules_pre_pass(input_text, voice)
    assert "distributed" in cleaned.lower() or "database" in cleaned.lower() or "analysis" in cleaned.lower(), \
        f"Content stripped from pre-pass (R10 regression): {cleaned!r}"


# ---------------------------------------------------------------------------
# CLI tests (subprocess)
# ---------------------------------------------------------------------------

SCRIPT = str(WORKSPACE / "execution" / "content" / "humanizer.py")
PY = sys.executable  # use the same Python that's running the tests


def _run_cli(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess:
    cmd = [PY, SCRIPT, *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        input=input_text,
        cwd=str(WORKSPACE),
    )


def test_cli_help_exits_0():
    result = _run_cli("--help")
    assert result.returncode == 0, f"--help should exit 0, got {result.returncode}"


def test_cli_help_contains_voice():
    result = _run_cli("--help")
    assert "--voice" in result.stdout, f"--help should mention --voice"


def test_cli_help_contains_platform():
    result = _run_cli("--help")
    assert "--platform" in result.stdout, f"--help should mention --platform"


def test_cli_help_contains_tier():
    result = _run_cli("--help")
    assert "--tier" in result.stdout, f"--help should mention --tier"


def test_cli_dry_run_exits_0():
    result = _run_cli(
        "--text", "Certainly! I'd be happy to delve into this comprehensive analysis.",
        "--dry-run",
    )
    assert result.returncode == 0, (
        f"--dry-run should exit 0\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_cli_dry_run_no_live_llm():
    """Dry-run should mention DRY-RUN in stdout (the stub message) rather than real output."""
    result = _run_cli(
        "--text", "Certainly! I'd be happy to delve into this.",
        "--dry-run",
    )
    assert "DRY-RUN" in result.stdout or result.returncode == 0, (
        f"Dry-run should exit 0\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_cli_dry_run_cost_in_stderr():
    result = _run_cli(
        "--text", "Certainly! I'd be happy to delve into this comprehensive analysis.",
        "--dry-run",
    )
    # Cost estimate should appear in stderr log
    assert "cost" in result.stderr.lower() or "token" in result.stderr.lower(), (
        f"Dry-run should print cost estimate to stderr\nstderr: {result.stderr}"
    )


def test_cli_nonexistent_voice_exits_nonzero():
    result = _run_cli(
        "--text", "Some text here.",
        "--voice", "this_voice_does_not_exist_xyz",
        "--dry-run",
    )
    assert result.returncode != 0, (
        f"Nonexistent voice should exit non-zero, got {result.returncode}"
    )


def test_cli_nonexistent_voice_clear_error():
    result = _run_cli(
        "--text", "Some text here.",
        "--voice", "this_voice_does_not_exist_xyz",
        "--dry-run",
    )
    combined = result.stdout + result.stderr
    assert "not found" in combined.lower() or "available" in combined.lower(), (
        f"Should have clear error message, got:\n{combined}"
    )


def test_cli_empty_text_exits_0():
    result = _run_cli("--text", "", "--dry-run")
    assert result.returncode == 0, (
        f"Empty text should exit 0 (graceful)\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_cli_show_diff_flag():
    """--show-diff with --dry-run should print BEFORE/AFTER to stderr."""
    result = _run_cli(
        "--text", "Certainly! I'd be happy to delve into this.",
        "--dry-run",
        "--show-diff",
    )
    assert result.returncode == 0
    has_diff = "BEFORE" in result.stderr or "AFTER" in result.stderr
    assert has_diff, f"--show-diff should print before/after to stderr\nstderr: {result.stderr}"


def test_cli_platform_choices():
    """All supported platforms should be accepted without error."""
    for platform in ["linkedin", "email", "slack", "tweet", "generic"]:
        result = _run_cli(
            "--text", "A simple test sentence.",
            "--platform", platform,
            "--dry-run",
        )
        assert result.returncode == 0, (
            f"--platform {platform} should exit 0, got {result.returncode}\nstderr: {result.stderr}"
        )


def test_cli_stdin_input():
    """Stdin input should work when no --text or --file provided."""
    result = _run_cli("--dry-run", input_text="Certainly! Let me delve into this.")
    assert result.returncode == 0, (
        f"Stdin input should exit 0\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Pre-pass tests
    run("pre_pass: strips Certainly!", test_strips_certainly)
    run("pre_pass: strips Certainly! (no space)", test_strips_certainly_no_space)
    run("pre_pass: strips I'd be happy to", test_strips_id_be_happy_to)
    run("pre_pass: strips closing fluff (I hope this helps)", test_strips_closing_fluff)
    run("pre_pass: strips Let me know if closing", test_strips_let_me_know)
    run("pre_pass: replaces em-dashes", test_replaces_em_dashes)
    run("pre_pass: keep_em_dashes=True preserves dashes", test_keep_em_dashes)
    run("pre_pass: flags banned vocab (delve)", test_flags_banned_vocab_delve)
    run("pre_pass: flags banned vocab (leverage)", test_flags_banned_vocab_leverage)
    run("pre_pass: flags banned vocab (robust)", test_flags_banned_vocab_robust)
    run("pre_pass: flags triple-parallel", test_flags_triple_parallel)
    run("pre_pass: flags hedges", test_flags_hedges)
    run("pre_pass: empty text returns empty + no flags", test_empty_text_returns_empty)
    run("pre_pass: whitespace-only returns no flags", test_whitespace_only_returns_empty)
    run("pre_pass: no false positive flags on clean text", test_no_false_positive_flags)
    run("pre_pass: R10 single-sentence opener does not eat content", test_prepass_preserves_content_in_single_sentence_opener)

    # Voice loader tests
    run("voice: load_voice(debanjan) returns dict", test_load_voice_debanjan)
    run("voice: debanjan has >= 5 examples", test_load_voice_has_examples)
    run("voice: debanjan has avoids list", test_load_voice_has_avoids)
    run("voice: nonexistent voice raises SystemExit", test_load_voice_nonexistent_raises)
    run("voice: schema has all required fields", test_load_voice_schema_fields)
    run("voice: _template.json exists", test_template_exists)

    # Platform post-process tests
    run("platform: linkedin strips **bold**", test_linkedin_strips_bold)
    run("platform: linkedin strips # headings", test_linkedin_strips_headings)
    run("platform: linkedin strips *italic*", test_linkedin_strips_italic)
    run("platform: tweet hard caps at 280", test_tweet_hard_cap)
    run("platform: tweet custom max_length", test_tweet_custom_max_length)
    run("platform: tweet no truncation if short", test_tweet_no_truncation_if_short)
    run("platform: email preserves newlines", test_email_preserves_structure)
    run("platform: generic minimal changes", test_generic_minimal_changes)
    run("platform: generic max_length caps output", test_generic_max_length)
    run("platform: slack strips headings", test_slack_strips_headings)

    # CLI tests
    run("cli: --help exits 0", test_cli_help_exits_0)
    run("cli: --help contains --voice", test_cli_help_contains_voice)
    run("cli: --help contains --platform", test_cli_help_contains_platform)
    run("cli: --help contains --tier", test_cli_help_contains_tier)
    run("cli: --dry-run exits 0", test_cli_dry_run_exits_0)
    run("cli: --dry-run no live LLM", test_cli_dry_run_no_live_llm)
    run("cli: --dry-run cost in stderr", test_cli_dry_run_cost_in_stderr)
    run("cli: nonexistent voice exits non-zero", test_cli_nonexistent_voice_exits_nonzero)
    run("cli: nonexistent voice shows clear error", test_cli_nonexistent_voice_clear_error)
    run("cli: empty text exits 0 (graceful)", test_cli_empty_text_exits_0)
    run("cli: --show-diff prints before/after to stderr", test_cli_show_diff_flag)
    run("cli: all platform choices accepted", test_cli_platform_choices)
    run("cli: stdin input works", test_cli_stdin_input)

    print(f"\n{'='*50}")
    print(f"Results: {PASS_COUNT} passed, {FAIL_COUNT} failed")
    if FAILURES:
        print("\nFailed tests:")
        for name, err in FAILURES:
            print(f"  FAIL  {name}")
            print(f"        {err}")
    sys.exit(0 if FAIL_COUNT == 0 else 1)
