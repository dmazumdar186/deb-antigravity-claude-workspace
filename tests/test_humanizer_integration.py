"""
Integration tests for humanizer.py -- components wired together, no LLM calls except
a single real Gemini probe (free tier). Run from workspace root.
"""
from __future__ import annotations

import os
import subprocess
import sys
import json
from pathlib import Path

WORKSPACE = Path(r"C:/Users/deban/OneDrive/Documents/AntiGravity Project Space")
sys.path.insert(0, str(WORKSPACE / "execution" / "content"))
sys.path.insert(0, str(WORKSPACE / "execution" / "modules"))

from dotenv import load_dotenv
load_dotenv(str(WORKSPACE / ".env"))

from humanizer import (
    _rules_pre_pass,
    _build_humanize_prompt,
    _auto_detect_provider,
    load_voice,
    VOICES_DIR,
    DEFAULT_VOICE,
)

PASS_COUNT = 0
FAIL_COUNT = 0
SKIP_COUNT = 0
FAILURES = []
SKIPS = []


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


def test_pre_pass_flows_into_prompt():
    voice = load_voice(DEFAULT_VOICE)
    # Input: opening fluff followed by a sentence containing banned vocab.
    # "Certainly!" is stripped; the second sentence with ‘delve’ and ‘robust’ survives.
    raw = "Certainly! This is a robust way to delve into the topic."
    pre_cleaned, flags = _rules_pre_pass(raw, voice)
    assert "Certainly" not in pre_cleaned, "opener should be stripped"
    assert pre_cleaned.strip(), "body sentence should survive stripping"
    system_p, user_p = _build_humanize_prompt(pre_cleaned, voice, flags, "generic")
    assert pre_cleaned in user_p, "pre-cleaned text must appear in user prompt"
    assert "TEXT TO HUMANIZE" in user_p
    assert "VOICE PROFILE" in user_p
    assert len(flags) > 0, f"expected banned-vocab flags, got: {flags}"
    for f in flags:
        assert f in user_p, f"flag not in prompt: {f}"


def test_prompt_includes_platform_note():
    voice = load_voice(DEFAULT_VOICE)
    cleaned, flags = _rules_pre_pass("Some AI text.", voice)
    for platform in ["linkedin", "slack", "tweet", "email", "generic"]:
        _, user_p = _build_humanize_prompt(cleaned, voice, flags, platform)
        assert "PLATFORM NOTE" in user_p, f"platform note missing for {platform}"


def test_all_voice_files_parse():
    voice_files = list(VOICES_DIR.glob("*.json"))
    assert len(voice_files) >= 2, "Expected at least debanjan.json and _template.json"
    for vf in voice_files:
        data = json.loads(vf.read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"{vf.name} must be a JSON object"


def test_auto_detect_provider_gemini_tier():
    has_gemini = bool(os.environ.get("GEMINI_API_KEY"))
    if not has_gemini:
        raise AssertionError("GEMINI_API_KEY not set")
    provider = _auto_detect_provider("gemini")
    assert provider == "gemini-direct", f"Expected gemini-direct, got {provider}"


def test_auto_detect_provider_default_tier_or():
    has_or = bool(os.environ.get("OPENROUTER_API_KEY"))
    if not has_or:
        raise AssertionError("OPENROUTER_API_KEY not set")
    provider = _auto_detect_provider("default")
    assert provider == "openrouter", f"Expected openrouter, got {provider}"


def test_resolve_model_gemini():
    from model_registry import resolve_model
    model_id = resolve_model("gemini", "default", allow_network=True)
    assert isinstance(model_id, str) and len(model_id) > 0
    assert "gemini" in model_id.lower(), f"Expected gemini model, got: {model_id}"


def test_resolve_model_openrouter_offline():
    from model_registry import resolve_model, LAST_KNOWN_GOOD
    model_id = resolve_model("openrouter", "default", allow_network=False)
    assert isinstance(model_id, str) and len(model_id) > 0


def test_real_gemini_llm_call():
    has_gemini = bool(os.environ.get("GEMINI_API_KEY"))
    if not has_gemini:
        raise AssertionError("GEMINI_API_KEY not set")
    from humanizer import _call_llm_humanize, _build_humanize_prompt, _rules_pre_pass
    voice = load_voice(DEFAULT_VOICE)
    raw = "Certainly! I’d be happy to delve into this comprehensive topic."
    pre_cleaned, flags = _rules_pre_pass(raw, voice)
    system_p, user_p = _build_humanize_prompt(pre_cleaned, voice, flags, "generic")
    result = _call_llm_humanize(system_p, user_p, "gemini", dry_run=False)
    assert isinstance(result, str) and len(result.strip()) > 0, f"Empty result: {result!r}"
    assert "DRY-RUN" not in result


def test_stdin_subprocess():
    SCRIPT = str(WORKSPACE / "execution" / "content" / "humanizer.py")
    PY = sys.executable
    result = subprocess.run(
        [PY, SCRIPT, "--dry-run"],
        input="Certainly! Let me delve into this.",
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(WORKSPACE),
    )
    assert result.returncode == 0, f"stdin pipe failed: {result.stderr}"


def test_file_input_subprocess():
    import tempfile
    SCRIPT = str(WORKSPACE / "execution" / "content" / "humanizer.py")
    PY = sys.executable
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("This is a test sentence.")
        tmp = f.name
    try:
        result = subprocess.run(
            [PY, SCRIPT, "--file", tmp, "--dry-run"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(WORKSPACE),
        )
        assert result.returncode == 0, f"--file input failed: {result.stderr}"
    finally:
        Path(tmp).unlink(missing_ok=True)


if __name__ == "__main__":
    run("integration: pre_pass -> prompt build round-trip", test_pre_pass_flows_into_prompt)
    run("integration: prompt includes platform note", test_prompt_includes_platform_note)
    run("integration: all voice JSON files parse cleanly", test_all_voice_files_parse)
    run("integration: auto_detect_provider gemini tier", test_auto_detect_provider_gemini_tier)
    run("integration: auto_detect_provider default -> openrouter", test_auto_detect_provider_default_tier_or)
    run("integration: resolve_model gemini default", test_resolve_model_gemini)
    run("integration: resolve_model openrouter offline fallback", test_resolve_model_openrouter_offline)
    run("integration: real Gemini LLM call (free)", test_real_gemini_llm_call)
    run("integration: stdin -> script -> stdout", test_stdin_subprocess)
    run("integration: --file input -> script -> stdout", test_file_input_subprocess)

    print(f"\n{'='*50}")
    print(f"Results: {PASS_COUNT} passed, {FAIL_COUNT} failed, {SKIP_COUNT} skipped")
    if FAILURES:
        print("\nFailed tests:")
        for name, err in FAILURES:
            print(f"  FAIL  {name}")
            print(f"        {err}")
    import sys as _sys
    _sys.exit(0 if FAIL_COUNT == 0 else 1)
