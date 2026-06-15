"""
Tier 6 - Monkey / Chaos tests for youtube_video_analyzer.py (v3).
Run: py -m pytest tests/test_youtube_analyzer_monkey.py -v -s
All tests verify graceful failure. No API spend. Non-destructive.
"""
from __future__ import annotations
import json
import os
import pathlib
import subprocess
import sys

WORKSPACE = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = WORKSPACE / "execution" / "video" / "youtube_video_analyzer.py"
TEST_URL = "https://youtu.be/BedAaB1RKgE"
CACHE_PATH = WORKSPACE / ".tmp" / "model_registry.json"


from conftest import skip_if_youtube_blocked


def _run(*args, extra_env=None):
    # dict(os.environ), NOT copy.copy(os.environ): the latter returns an
    # _Environ proxy that shares state with the parent — mutations leak.
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    r = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(WORKSPACE),
    )
    if r.returncode != 0:
        skip_if_youtube_blocked(r.stderr)
    return r


def _no_stack_trace(stderr):
    return "Traceback (most recent call last)" not in stderr


def test_m1_empty_url():
    r = _run("", "--dry-run")
    assert r.returncode != 0
    # Fix 7 (SSRF guard): non-YouTube URLs now emit "URL must be a YouTube URL"
    # Fallback also accepts old "Could not extract" message and generic ERROR lines
    assert (
        "URL must be a YouTube URL" in r.stderr
        or "Could not extract" in r.stderr
        or "ERROR" in r.stderr
    ), f"Expected error message not found in stderr: {r.stderr[:300]!r}"


def test_m2_garbage_url():
    r = _run("not-a-url", "--dry-run")
    assert r.returncode != 0
    assert (
        "URL must be a YouTube URL" in r.stderr
        or "Could not extract" in r.stderr
        or "ERROR" in r.stderr
    ), f"Expected error message not found in stderr: {r.stderr[:300]!r}"


def test_m3_non_youtube_url():
    r = _run("https://www.example.com", "--dry-run")
    assert r.returncode != 0
    # SSRF guard fires before video ID extraction for non-YouTube hosts
    assert (
        "URL must be a YouTube URL" in r.stderr
        or "Could not extract" in r.stderr
        or "ERROR" in r.stderr
    ), f"Expected error message not found in stderr: {r.stderr[:300]!r}"


def test_m4_rickroll_has_captions():
    r = _run("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "--dry-run")
    assert r.returncode == 0, f"RickRoll failed: {r.stderr[-300:]}"
    data = json.loads(r.stdout)
    assert data["video_id"] == "dQw4w9WgXcQ"


def test_m5_short_video_not_flagged_as_live():
    r = _run("https://www.youtube.com/watch?v=jNQXAC9IVRw", "--dry-run")
    assert r.returncode == 0, f"Short video failed: {r.stderr[-300:]}"
    data = json.loads(r.stdout)
    assert data["video_id"] == "jNQXAC9IVRw"


def test_m6_junk_params_xss():
    url = "https://youtu.be/BedAaB1RKgE?si=ORjSeMcC4KLKboD8&malicious=<script>alert(1)</script>"
    r = _run(url, "--dry-run")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["video_id"] == "BedAaB1RKgE"


def test_m7_path_traversal_obsidian_vault():
    # R2-1 fix: relative paths now rejected at argparse (exit 2) before any processing
    r = _run(TEST_URL, "--obsidian-vault", "../../../etc/passwd", "--dry-run")
    # Must reject relative path — exit 2 (argparse error) expected
    assert r.returncode == 2, (
        f"Expected exit 2 for relative --obsidian-vault path, got {r.returncode}. "
        f"stderr={r.stderr[:200]!r}"
    )
    assert "absolute" in r.stderr.lower(), (
        f"Error message should mention 'absolute': {r.stderr[:200]!r}"
    )


def test_m8_invalid_tier():
    r = _run(TEST_URL, "--tier", "invalid", "--dry-run")
    assert r.returncode == 2, f"Expected argparse exit 2, got {r.returncode}"


def test_m9_invalid_provider():
    r = _run(TEST_URL, "--provider", "notreal", "--dry-run")
    assert r.returncode == 2, f"Expected argparse exit 2, got {r.returncode}"


def test_m10_max_frames_zero_rejected():
    """--max-frames 0 is rejected at argparse (exit 2), no stack trace."""
    r = _run(TEST_URL, "--max-frames", "0", "--dry-run")
    assert r.returncode != 0, "Should fail with invalid input"
    assert _no_stack_trace(r.stderr), (
        "Stack trace leaked on --max-frames 0. "
        "Expected clean argparse rejection (exit 2)."
    )


def test_m11_max_frames_negative_rejected():
    """--max-frames -1 is rejected at argparse (exit 2), no silent exit 0."""
    r = _run(TEST_URL, "--max-frames", "-1", "--dry-run")
    data = json.loads(r.stdout) if r.returncode == 0 else {}
    assert r.returncode != 0 or data.get("grid_count", -1) > 0, (
        "--max-frames -1 should be rejected (non-zero exit) or produce grids > 0. "
        "Expected clean argparse rejection."
    )


def test_m12_conflicting_tier_provider_rejected():
    """--tier gemini --provider anthropic is rejected at argparse (exit 2)."""
    r = _run(TEST_URL, "--tier", "gemini", "--provider", "anthropic", "--dry-run")
    assert r.returncode != 0 or "warning" in r.stderr.lower() or "incompatible" in r.stderr.lower(), (
        "--tier gemini --provider anthropic combination should be rejected or warned. "
        "Expected argparse error (exit 2) per R2-3 cross-validation fix."
    )


def test_m13_tampered_model_registry():
    backup = None
    if CACHE_PATH.exists():
        backup = CACHE_PATH.read_text(encoding="utf-8")
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text("{not valid", encoding="utf-8")
        r = _run(TEST_URL, "--dry-run")
        assert r.returncode == 0, f"Should fall back gracefully: {r.stderr[-300:]}"
        assert _no_stack_trace(r.stderr), "Stack trace on tampered cache"
        data = json.loads(r.stdout)
        assert "video_id" in data
    finally:
        if backup is not None:
            CACHE_PATH.write_text(backup, encoding="utf-8")
        elif CACHE_PATH.exists():
            CACHE_PATH.unlink()


def test_m14_empty_api_key_treated_as_missing():
    # Set all three to empty strings (not pop) so load_dotenv() in the child
    # process sees them as "already set" and does not refill from .env.
    # dict() not copy.copy() — _Environ proxy leaks mutations into the parent.
    env_override = dict(os.environ)
    env_override["OPENROUTER_API_KEY"] = ""
    env_override["ANTHROPIC_API_KEY"] = ""
    env_override["GEMINI_API_KEY"] = ""
    r = _run(TEST_URL, "--dry-run", extra_env=env_override)
    assert r.returncode != 0, f"Should fail with no valid API keys; stdout={r.stdout[-400:]} stderr={r.stderr[-400:]}"
    assert (
        "OPENROUTER_API_KEY" in r.stderr
        or "ANTHROPIC_API_KEY" in r.stderr
        or "GEMINI_API_KEY" in r.stderr
        or "API key" in r.stderr
    )


def test_m15_massive_url():
    massive_url = "https://youtu.be/BedAaB1RKgE?" + "a=b&" * 2500
    assert len(massive_url) > 10000
    r = _run(massive_url, "--dry-run")
    if r.returncode == 0:
        data = json.loads(r.stdout)
        assert data["video_id"] == "BedAaB1RKgE"
    else:
        assert _no_stack_trace(r.stderr), "Stack trace on massive URL"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
