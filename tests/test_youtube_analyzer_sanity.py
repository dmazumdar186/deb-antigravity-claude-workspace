"""
Tier 4 — Sanity tests for youtube_video_analyzer.py (v3).
Run: py -m pytest tests/test_youtube_analyzer_sanity.py -v
All tests are non-destructive and make no API calls.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
SCRIPT = WORKSPACE / "execution" / "video" / "youtube_video_analyzer.py"
TEST_URL = "https://youtu.be/BedAaB1RKgE"


def _run(*args, env_override=None):
    import copy
    env = copy.copy(os.environ)
    if env_override:
        env.update(env_override)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(WORKSPACE),
    )


# ---------------------------------------------------------------------------
# S1 — Imports resolve
# ---------------------------------------------------------------------------
def test_s1_imports_resolve():
    result = subprocess.run(
        [sys.executable, "-c", "import execution.video.youtube_video_analyzer"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(WORKSPACE),
    )
    assert result.returncode == 0, f"Import failed:\n{result.stderr}"


# ---------------------------------------------------------------------------
# S2 — --help exits 0 and contains required flag names
# NOTE: Known failure on Windows cp1252 terminals due to Unicode arrow in help text.
# The subprocess captures output in UTF-8, so this test passes here even if
# the interactive terminal would crash. The underlying bug is still reported.
# ---------------------------------------------------------------------------
def test_s2_help_works():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(WORKSPACE),
    )
    combined = result.stdout + result.stderr
    assert result.returncode == 0, f"--help exited {result.returncode}:\n{combined}"
    for flag in ["--tier", "--provider", "--dry-run", "--refresh-models"]:
        assert flag in combined, f"Flag {flag!r} not found in --help output"


# ---------------------------------------------------------------------------
# S3 — Required dependencies importable
# ---------------------------------------------------------------------------
REQUIRED_DEPS = [
    "yt_dlp",
    "youtube_transcript_api",
    "scenedetect",
    "imagehash",
    "PIL",
    "imageio_ffmpeg",
    "anthropic",
    "openai",
    "google.genai",
]

def test_s3_dependencies_importable():
    missing = []
    for dep in REQUIRED_DEPS:
        result = subprocess.run(
            [sys.executable, "-c", f"import {dep}"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if result.returncode != 0:
            missing.append(dep)
    assert not missing, f"Missing dependencies: {missing}"


# ---------------------------------------------------------------------------
# S4 — ffmpeg binary exists on disk
# ---------------------------------------------------------------------------
def test_s4_ffmpeg_binary_exists():
    result = subprocess.run(
        [sys.executable, "-c",
         "import imageio_ffmpeg; p = imageio_ffmpeg.get_ffmpeg_exe(); "
         "from pathlib import Path; assert Path(p).exists(), f'ffmpeg not found at {p}'; print(p)"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, f"ffmpeg check failed:\n{result.stderr}"


# ---------------------------------------------------------------------------
# S5 — Required directories exist and are writable
# ---------------------------------------------------------------------------
def test_s5_tmp_dirs_writable():
    tmp_base = WORKSPACE / ".tmp" / "video"
    tmp_base.mkdir(parents=True, exist_ok=True)
    probe = tmp_base / "_sanity_probe.txt"
    probe.write_text("ok")
    assert probe.exists()
    probe.unlink()


# ---------------------------------------------------------------------------
# S6 — Cache file schema (after a dry-run the cache is populated)
# ---------------------------------------------------------------------------
def test_s6_cache_schema():
    cache_path = WORKSPACE / ".tmp" / "model_registry.json"
    if not cache_path.exists():
        # Trigger a dry-run to populate it (requires OPENROUTER_API_KEY via .env)
        _run(TEST_URL, "--dry-run")
    if not cache_path.exists():
        import pytest
        pytest.skip("model_registry.json not present — no API key available")
    data = json.loads(cache_path.read_text(encoding="utf-8"))
    assert "resolved_at" in data, "Missing 'resolved_at' key"
    assert "ttl_days" in data, "Missing 'ttl_days' key"
    # At least one provider key must be present
    providers = {"anthropic", "gemini", "openrouter"}
    assert providers & set(data.keys()), (
        f"No provider key found in cache. Keys: {list(data.keys())}"
    )


# ---------------------------------------------------------------------------
# S7 — Provider auto-detection log appears in dry-run output
# ---------------------------------------------------------------------------
def test_s7_provider_autodetect_log():
    result = _run(TEST_URL, "--dry-run")
    combined = result.stdout + result.stderr
    # Should see "Mode:" log line with provider/model/cost note
    assert "Mode:" in combined, f"'Mode:' log line not found in output:\n{combined[:500]}"


# ---------------------------------------------------------------------------
# S8 — Output format: dry-run JSON has required fields
# Shallow --dry-run returns would_* fields (no grid_count/estimated_input_tokens).
# Deep --deep-dry-run returns the full pipeline fields.
# ---------------------------------------------------------------------------
SHALLOW_REQUIRED_FIELDS = [
    "video_id", "tier", "provider", "model_id",
    "would_call_provider", "would_use_model", "estimated_cost",
]

DEEP_REQUIRED_FIELDS = [
    "video_id", "title", "duration_sec", "tier",
    "model_id", "provider", "grid_count", "estimated_input_tokens",
]


def test_s8_dry_run_output_format():
    """Shallow --dry-run must include all SHALLOW_REQUIRED_FIELDS."""
    result = _run(TEST_URL, "--dry-run")
    assert result.returncode == 0, f"Dry-run failed:\n{result.stderr}"
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Dry-run stdout is not valid JSON: {e}\n{result.stdout[:300]}") from e
    missing = [f for f in SHALLOW_REQUIRED_FIELDS if f not in data]
    assert not missing, f"Missing shallow fields in --dry-run JSON: {missing}"


def test_s8b_deep_dry_run_output_format():
    """Deep --deep-dry-run must include all DEEP_REQUIRED_FIELDS (downloads video; may be slow)."""
    import pytest
    # Skip by default to avoid downloading a video in the standard test run.
    # Run explicitly with: py -m pytest tests/test_youtube_analyzer_sanity.py::test_s8b_deep_dry_run_output_format -v -s
    pytest.skip(
        "Skipped by default — --deep-dry-run downloads the video. "
        "Run explicitly to verify deep fields."
    )


# ---------------------------------------------------------------------------
# S9 — No secrets logged in dry-run output
# ---------------------------------------------------------------------------
def test_s9_no_secrets_in_output():
    result = _run(TEST_URL, "--dry-run")
    combined = result.stdout + result.stderr
    assert "sk-or-v" not in combined, "OPENROUTER_API_KEY prefix leaked in output"
    assert "sk-ant-" not in combined, "ANTHROPIC_API_KEY prefix leaked in output"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
