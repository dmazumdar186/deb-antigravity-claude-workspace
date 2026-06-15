"""
tests/test_youtube_analyzer_batch.py

Batch mode tests for YouTube Video Analyzer v4.
Covers URL collection, --urls-file parsing, URL validation,
sequential vs parallel modes, result dict shape, exit codes,
below-threshold notice, and batch summary file.

Uses the workspace run() harness pattern. No pytest required.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import types
import unittest.mock as mock
from pathlib import Path

WORKSPACE = Path(r"C:/Users/deban/OneDrive/Documents/AntiGravity Project Space")
SCRIPT = WORKSPACE / "execution" / "video" / "youtube_video_analyzer.py"

sys.path.insert(0, str(WORKSPACE / "execution" / "video"))
sys.path.insert(0, str(WORKSPACE / "execution" / "modules"))

from dotenv import load_dotenv
load_dotenv(str(WORKSPACE / ".env"))

PASS_COUNT = 0
FAIL_COUNT = 0
FAILURES: list[tuple[str, str]] = []


def run(name: str, fn):
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
# Helpers
# ---------------------------------------------------------------------------

VALID_URL_1 = "https://youtu.be/jNQXAC9IVRw"   # Me at the zoo
VALID_URL_2 = "https://youtu.be/BedAaB1RKgE"   # IBM MCP/ADK video


from conftest import skip_if_youtube_blocked


def _cli(*args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run the analyzer script with the given args; short timeout for dry-run tests."""
    r = subprocess.run(
        [sys.executable, str(SCRIPT)] + list(args),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
    )
    if r.returncode != 0:
        skip_if_youtube_blocked(r.stderr)
    return r


def _make_urls_file(lines: list[str]) -> Path:
    """Write lines to a temp file and return its path."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    )
    tmp.write("\n".join(lines) + "\n")
    tmp.flush()
    tmp.close()
    return Path(tmp.name)


# ---------------------------------------------------------------------------
# Import the module for direct unit tests
# ---------------------------------------------------------------------------

import youtube_video_analyzer as yt  # noqa: E402


# ---------------------------------------------------------------------------
# T-B1: URL collection — positional only
# ---------------------------------------------------------------------------

def t_positional_only():
    """Both positional URLs appear in all_urls before batch dispatch."""
    # Validate upfront: 2 valid URLs → all_urls should have 2 entries.
    # We test via dry-run: both URLs are accepted (exit 0) since validation
    # happens before the dry-run shortcut.
    result = _cli(VALID_URL_1, VALID_URL_2, "--dry-run")
    # With 2 URLs in --dry-run mode, the shallow dry-run uses all_urls[0]
    # and exits 0 (no batch dispatch in dry-run).
    assert result.returncode == 0, (
        f"positional 2 URLs + --dry-run should exit 0; got {result.returncode}\n{result.stderr[:300]}"
    )


# ---------------------------------------------------------------------------
# T-B2: URL collection — --urls-file only
# ---------------------------------------------------------------------------

def t_urls_file_only():
    """--urls-file alone (no positional URLs) is accepted."""
    f = _make_urls_file([VALID_URL_1, VALID_URL_2])
    try:
        result = _cli("--urls-file", str(f), "--dry-run")
        assert result.returncode == 0, (
            f"--urls-file only + --dry-run should exit 0; got {result.returncode}\n{result.stderr[:300]}"
        )
    finally:
        f.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# T-B3: URL collection — composable (positional + --urls-file)
# ---------------------------------------------------------------------------

def t_urls_file_composable():
    """Positional URL + --urls-file combine into a single URL list."""
    f = _make_urls_file([VALID_URL_2])
    try:
        # Pass VALID_URL_1 as positional and VALID_URL_2 via file.
        # Both end up in all_urls → 2 URLs total → batch.
        # In --dry-run mode, only first URL is used for the shallow output,
        # but the CLI must accept both without erroring.
        result = _cli(VALID_URL_1, "--urls-file", str(f), "--dry-run")
        assert result.returncode == 0, (
            f"positional + --urls-file + --dry-run should exit 0; got {result.returncode}\n{result.stderr[:300]}"
        )
    finally:
        f.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# T-B4: --urls-file parsing — comments stripped
# ---------------------------------------------------------------------------

def t_urls_file_comments_stripped():
    """Lines starting with '#' are skipped; valid URLs are kept."""
    f = _make_urls_file([
        "# This is a comment",
        VALID_URL_1,
        "# Another comment",
        VALID_URL_2,
    ])
    try:
        result = _cli("--urls-file", str(f), "--dry-run")
        assert result.returncode == 0, (
            f"Comment-stripping failed; exit={result.returncode}\n{result.stderr[:300]}"
        )
    finally:
        f.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# T-B5: --urls-file parsing — blank lines ignored
# ---------------------------------------------------------------------------

def t_urls_file_blank_lines():
    """Blank lines in the URL file are ignored."""
    f = _make_urls_file([
        "",
        VALID_URL_1,
        "",
        "",
        VALID_URL_2,
        "",
    ])
    try:
        result = _cli("--urls-file", str(f), "--dry-run")
        assert result.returncode == 0, (
            f"Blank-line stripping failed; exit={result.returncode}\n{result.stderr[:300]}"
        )
    finally:
        f.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# T-B6: --urls-file parsing — trailing whitespace stripped
# ---------------------------------------------------------------------------

def t_urls_file_trailing_whitespace():
    """URLs with trailing spaces/tabs are accepted."""
    f = _make_urls_file([
        VALID_URL_1 + "   ",
        VALID_URL_2 + "\t",
    ])
    try:
        result = _cli("--urls-file", str(f), "--dry-run")
        assert result.returncode == 0, (
            f"Trailing whitespace stripping failed; exit={result.returncode}\n{result.stderr[:300]}"
        )
    finally:
        f.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# T-B7: URL validation — malformed URL fails BEFORE processing (fail-fast)
# ---------------------------------------------------------------------------

def t_malformed_url_fails_fast():
    """A malformed URL in a batch fails the WHOLE batch before any processing."""
    result = _cli("https://not-youtube.com/watch?v=abc123", "--dry-run")
    # Malformed = non-YouTube host — parser.error() is called, exit non-zero
    assert result.returncode != 0, (
        f"Malformed URL should fail fast; got returncode=0\n{result.stdout[:200]}"
    )


# ---------------------------------------------------------------------------
# T-B8: URL validation — invalid video ID fails before processing
# ---------------------------------------------------------------------------

def t_invalid_video_id_fails_fast():
    """A YouTube-looking URL with no extractable video ID fails upfront."""
    result = _cli("https://www.youtube.com/results?search_query=test", "--dry-run")
    assert result.returncode != 0, (
        f"URL with no video ID should fail fast; got returncode=0\n{result.stdout[:200]}"
    )


# ---------------------------------------------------------------------------
# T-B9: Single URL stays on the single-URL path (NOT batch mode)
# ---------------------------------------------------------------------------

def t_single_url_not_batch():
    """Single URL invocation preserves v3 behavior (no BATCH SUMMARY printed)."""
    result = _cli(VALID_URL_1, "--dry-run")
    assert result.returncode == 0, (
        f"Single URL --dry-run failed; exit={result.returncode}\n{result.stderr[:300]}"
    )
    # Single-URL path should NOT print a BATCH SUMMARY block
    assert "BATCH SUMMARY" not in result.stdout, (
        "Single-URL path printed BATCH SUMMARY — should not be in batch mode"
    )


# ---------------------------------------------------------------------------
# T-B10: Batch mode activates iff len(urls) > 1
# ---------------------------------------------------------------------------

def t_batch_mode_threshold():
    """Verify batch mode activates iff urls > 1 (via direct code inspection)."""
    # The main() function calls _run_batch only when len(all_urls) > 1.
    # We verify this by checking the source code directly.
    src = SCRIPT.read_text(encoding="utf-8")
    assert "len(all_urls) == 1" in src or "len(all_urls) > 1" in src, (
        "Expected conditional 'len(all_urls) == 1' or '> 1' not found in main()"
    )
    # The _run_batch function must exist
    assert "_run_batch" in src, "_run_batch function not found in script"


# ---------------------------------------------------------------------------
# T-B11: _run_batch result dict shape
# ---------------------------------------------------------------------------

def t_result_dict_shape():
    """Per-URL result dict from _run_batch has the expected keys."""
    # Import and call _analyze_single_url with a mocked provider to check shape.
    required_keys = {"url", "video_id", "status", "breakdown_path", "tokens_used", "cost", "error"}

    # Build a minimal args namespace
    args = types.SimpleNamespace(
        dry_run=False,
        deep_dry_run=False,
        no_creator_profile=True,
        refresh_creator_profile=False,
        max_frames=24,
        keep_source=False,
        refresh_transcript=False,
        parallel=1,
    )

    # Mock the full pipeline so no real network calls happen
    fake_metadata = {
        "title": "Test Video",
        "channel": "Test Channel",
        "channel_id": "UC_test123",
        "duration_sec": 60,
        "upload_date": "20260101",
        "description": "",
        "video_id": "jNQXAC9IVRw",
    }
    fake_structured = {
        "hook": "test hook",
        "pacing_cuts": [{"timestamp": "00:01", "what_changes": "cut"}] * 3,
        "visual_storytelling": "test visual",
        "transcript_highlights": [{"timestamp": "00:05", "quote": "q"}] * 3,
        "content_ideas": ["idea1", "idea2", "idea3"],
    }

    with (
        mock.patch.object(yt, "fetch_metadata_only", return_value=fake_metadata),
        mock.patch.object(yt, "analyze_with_gemini", return_value=fake_structured),
        mock.patch.object(yt, "write_outputs", return_value=(Path("/tmp/breakdown.md"), None)),
        mock.patch.object(yt.Path, "read_text", return_value="breakdown content"),
    ):
        result = yt._analyze_single_url(
            VALID_URL_2,
            provider="gemini-direct",
            tier="gemini",
            model_id="gemini-2.5-flash",
            vault_path_obj=None,
            args=args,
            creator_profiles_mod=None,
        )

    missing = required_keys - set(result.keys())
    assert not missing, f"Result dict missing keys: {missing}"


# ---------------------------------------------------------------------------
# T-B12: Batch summary aggregation (via mock)
# ---------------------------------------------------------------------------

def t_batch_summary_aggregation():
    """_run_batch aggregates successes and failures correctly."""
    args = types.SimpleNamespace(
        dry_run=False,
        deep_dry_run=False,
        no_creator_profile=True,
        refresh_creator_profile=False,
        max_frames=24,
        keep_source=False,
        refresh_transcript=False,
        parallel=1,
    )

    # Mock _analyze_single_url to return predetermined results
    call_count = [0]

    def fake_analyze(url, *a, **kw):
        call_count[0] += 1
        if call_count[0] == 1:
            return {
                "url": url, "video_id": "abc", "status": "ok",
                "breakdown_path": "/tmp/abc.md", "tokens_used": 1000,
                "cost": "~$0.001", "error": None,
                "channel_id": "UC_abc", "channel_name": "Chan A",
            }
        else:
            return {
                "url": url, "video_id": None, "status": "error",
                "breakdown_path": None, "tokens_used": 0,
                "cost": "~$0.000", "error": "no captions",
                "channel_id": None, "channel_name": None,
            }

    with mock.patch.object(yt, "_analyze_single_url", side_effect=fake_analyze):
        exit_code = yt._run_batch(
            [VALID_URL_1, VALID_URL_2],
            args,
            provider="gemini-direct",
            tier="gemini",
            model_id="gemini-2.5-flash",
            vault_path_obj=None,
            creator_profiles_mod=None,
        )

    # 1 success + 1 failure → exit code 2 (partial)
    assert exit_code == 2, f"Expected exit_code=2 for partial batch, got {exit_code}"


# ---------------------------------------------------------------------------
# T-B13: Exit code 0 on all-success
# ---------------------------------------------------------------------------

def t_exit_code_all_success():
    """_run_batch returns 0 when all URLs succeed."""
    args = types.SimpleNamespace(
        dry_run=False,
        deep_dry_run=False,
        no_creator_profile=True,
        refresh_creator_profile=False,
        max_frames=24,
        keep_source=False,
        refresh_transcript=False,
        parallel=1,
    )

    def fake_ok(url, *a, **kw):
        return {
            "url": url, "video_id": "xyz", "status": "ok",
            "breakdown_path": "/tmp/xyz.md", "tokens_used": 500,
            "cost": "~$0.000", "error": None,
            "channel_id": "UC_xyz", "channel_name": "Chan X",
        }

    with mock.patch.object(yt, "_analyze_single_url", side_effect=fake_ok):
        exit_code = yt._run_batch(
            [VALID_URL_1, VALID_URL_2],
            args,
            provider="gemini-direct",
            tier="gemini",
            model_id="gemini-2.5-flash",
            vault_path_obj=None,
            creator_profiles_mod=None,
        )

    assert exit_code == 0, f"Expected exit_code=0 for all-success batch, got {exit_code}"


# ---------------------------------------------------------------------------
# T-B14: Exit code 1 on all-fail
# ---------------------------------------------------------------------------

def t_exit_code_all_fail():
    """_run_batch returns 1 when all URLs fail."""
    args = types.SimpleNamespace(
        dry_run=False,
        deep_dry_run=False,
        no_creator_profile=True,
        refresh_creator_profile=False,
        max_frames=24,
        keep_source=False,
        refresh_transcript=False,
        parallel=1,
    )

    def fake_fail(url, *a, **kw):
        return {
            "url": url, "video_id": None, "status": "error",
            "breakdown_path": None, "tokens_used": 0,
            "cost": "~$0.000", "error": "no captions",
            "channel_id": None, "channel_name": None,
        }

    with mock.patch.object(yt, "_analyze_single_url", side_effect=fake_fail):
        exit_code = yt._run_batch(
            [VALID_URL_1, VALID_URL_2],
            args,
            provider="gemini-direct",
            tier="gemini",
            model_id="gemini-2.5-flash",
            vault_path_obj=None,
            creator_profiles_mod=None,
        )

    assert exit_code == 1, f"Expected exit_code=1 for all-fail batch, got {exit_code}"


# ---------------------------------------------------------------------------
# T-B15: Below-threshold notice appears in summary
# ---------------------------------------------------------------------------

def t_below_threshold_notice():
    """When build_count < next_distillation_threshold, a NOTE is printed."""
    args = types.SimpleNamespace(
        dry_run=False,
        deep_dry_run=False,
        no_creator_profile=False,  # profiles enabled
        refresh_creator_profile=False,
        max_frames=24,
        keep_source=False,
        refresh_transcript=False,
        parallel=1,
    )

    # Fake creator_profiles module
    fake_cp = types.ModuleType("creator_profiles")
    fake_profile = {
        "channel_id": "UC_test",
        "channel_name": "Test Channel",
        "build_count": 1,
        "next_distillation_threshold": 3,
        "profile_built_from": [],
        "style_profile": None,
        "schema_version": 1,
        "last_updated": "2026-01-01T00:00:00Z",
        "last_distillation_at": None,
    }
    fake_cp.load_profile = mock.MagicMock(return_value=fake_profile)

    def fake_ok(url, *a, **kw):
        return {
            "url": url, "video_id": "abc", "status": "ok",
            "breakdown_path": "/tmp/abc.md", "tokens_used": 500,
            "cost": "~$0.000", "error": None,
            "channel_id": "UC_test", "channel_name": "Test Channel",
        }

    import io
    captured = io.StringIO()

    with (
        mock.patch.object(yt, "_analyze_single_url", side_effect=fake_ok),
        mock.patch("builtins.print", side_effect=lambda *a, **kw: captured.write(" ".join(str(x) for x in a) + "\n")),
    ):
        yt._run_batch(
            [VALID_URL_1],
            args,
            provider="gemini-direct",
            tier="gemini",
            model_id="gemini-2.5-flash",
            vault_path_obj=None,
            creator_profiles_mod=fake_cp,
        )

    output = captured.getvalue()
    assert "NOTE" in output or "threshold" in output.lower(), (
        f"Below-threshold notice not found in batch output.\nOutput:\n{output[:600]}"
    )


# ---------------------------------------------------------------------------
# T-B16: Batch summary written to .tmp/video/_batch_{run_id}/summary.md
# ---------------------------------------------------------------------------

def t_batch_summary_file_written():
    """_run_batch writes a summary.md to .tmp/video/_batch_{run_id}/."""
    args = types.SimpleNamespace(
        dry_run=False,
        deep_dry_run=False,
        no_creator_profile=True,
        refresh_creator_profile=False,
        max_frames=24,
        keep_source=False,
        refresh_transcript=False,
        parallel=1,
    )

    def fake_ok(url, *a, **kw):
        return {
            "url": url, "video_id": "summary_test", "status": "ok",
            "breakdown_path": "/tmp/summary_test.md", "tokens_used": 100,
            "cost": "~$0.000", "error": None,
            "channel_id": "UC_sum", "channel_name": "Sum Channel",
        }

    with mock.patch.object(yt, "_analyze_single_url", side_effect=fake_ok):
        yt._run_batch(
            [VALID_URL_1, VALID_URL_2],
            args,
            provider="gemini-direct",
            tier="gemini",
            model_id="gemini-2.5-flash",
            vault_path_obj=None,
            creator_profiles_mod=None,
        )

    # Find the most recent batch summary dir
    batch_dirs = sorted(
        (WORKSPACE / ".tmp" / "video").glob("_batch_*/summary.md"),
        key=lambda p: p.stat().st_mtime,
    )
    assert batch_dirs, "No _batch_*/summary.md found under .tmp/video/"
    summary_content = batch_dirs[-1].read_text(encoding="utf-8")
    assert "Batch Analysis Summary" in summary_content or "Batch" in summary_content, (
        f"summary.md doesn't look like a batch summary: {summary_content[:200]}"
    )


# ---------------------------------------------------------------------------
# T-B17: --parallel N flag accepted by CLI
# ---------------------------------------------------------------------------

def t_parallel_flag_accepted():
    """--parallel N is accepted without error (verified via --help and --dry-run)."""
    help_result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert "--parallel" in help_result.stdout, "--parallel flag not in --help output"

    dry_result = _cli(VALID_URL_1, "--dry-run", "--parallel", "2")
    assert dry_result.returncode == 0, (
        f"--parallel 2 + --dry-run failed; exit={dry_result.returncode}\n{dry_result.stderr[:300]}"
    )


if __name__ == "__main__":
    print("=== BATCH MODE TESTS ===")
    print()

    run("URL collection: positional only (2 URLs accepted)", t_positional_only)
    run("URL collection: --urls-file only accepted", t_urls_file_only)
    run("URL collection: positional + --urls-file composable", t_urls_file_composable)
    run("--urls-file: comment lines stripped", t_urls_file_comments_stripped)
    run("--urls-file: blank lines ignored", t_urls_file_blank_lines)
    run("--urls-file: trailing whitespace stripped", t_urls_file_trailing_whitespace)
    run("URL validation: malformed URL fails fast (non-YouTube host)", t_malformed_url_fails_fast)
    run("URL validation: invalid video ID fails fast", t_invalid_video_id_fails_fast)
    run("Single URL: no BATCH SUMMARY printed (backward compat)", t_single_url_not_batch)
    run("Batch mode: activates iff len(urls) > 1", t_batch_mode_threshold)
    run("Result dict: all required keys present", t_result_dict_shape)
    run("Batch summary: partial failure -> exit code 2", t_batch_summary_aggregation)
    run("Exit code: 0 on all-success", t_exit_code_all_success)
    run("Exit code: 1 on all-fail", t_exit_code_all_fail)
    run("Below-threshold notice: appears in summary when build_count < threshold", t_below_threshold_notice)
    run("Batch summary file: written to .tmp/video/_batch_{run_id}/summary.md", t_batch_summary_file_written)
    run("--parallel N: flag accepted by CLI", t_parallel_flag_accepted)

    print()
    print(f"Batch: {PASS_COUNT} passed, {FAIL_COUNT} failed")
    if FAILURES:
        print("Failed tests:")
        for n, e in FAILURES:
            print(f"  - {n}: {e}")
    sys.exit(0 if FAIL_COUNT == 0 else 1)
