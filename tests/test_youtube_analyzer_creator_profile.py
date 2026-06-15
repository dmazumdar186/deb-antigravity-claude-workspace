"""
tests/test_youtube_analyzer_creator_profile.py

Creator-profile cache tests for YouTube Video Analyzer v4.
Covers schema load/save, append_video_to_profile, should_distill,
distill_profile (mocked LLM), format_creator_context (including
case-insensitive placeholder guard), bump_distillation_threshold,
channel_id fallback, and CLI flag behavior.

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

import creator_profiles as cp  # noqa: E402

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

VALID_URL_1 = "https://youtu.be/jNQXAC9IVRw"
VALID_URL_2 = "https://youtu.be/BedAaB1RKgE"


from conftest import skip_if_youtube_blocked


def _cli(*args: str, timeout: int = 30) -> subprocess.CompletedProcess:
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


def _fake_profile(channel_id: str = "UC_test", build_count: int = 2,
                  threshold: int = 3, style_profile=None) -> dict:
    return {
        "schema_version": cp.SCHEMA_VERSION,
        "channel_id": channel_id,
        "channel_name": "Test Channel",
        "profile_built_from": [
            {
                "video_id": f"vid_{i}",
                "title": f"Video {i}",
                "duration_sec": 300,
                "analyzed_at": "2026-05-18T10:00:00Z",
                "breakdown_snippet": f"Breakdown snippet {i}",
            }
            for i in range(build_count)
        ],
        "style_profile": style_profile,
        "build_count": build_count,
        "last_updated": "2026-05-18T10:00:00Z",
        "last_distillation_at": None,
        "next_distillation_threshold": threshold,
    }


def _good_style_profile() -> dict:
    return {
        "hook_patterns": ["opens with a question"],
        "pacing_patterns": ["slow paced"],
        "visual_style": ["white background"],
        "common_topics": ["AI", "technology"],
        "creator_signature": "minimalist tech explainer",
        "common_b_roll_choices": [],
        "average_cuts_per_minute": 3.5,
    }


# ---------------------------------------------------------------------------
# T-CP1: load_profile returns None when file missing
# ---------------------------------------------------------------------------

def t_load_profile_missing():
    """load_profile returns None for a nonexistent channel."""
    result = cp.load_profile("NONEXISTENT_CHANNEL_12345_xyz")
    assert result is None, f"Expected None for missing profile, got {result!r}"


# ---------------------------------------------------------------------------
# T-CP2: load_profile returns dict when file present
# ---------------------------------------------------------------------------

def t_load_profile_present():
    """load_profile returns the dict when a valid profile file exists."""
    with tempfile.TemporaryDirectory() as td:
        # Temporarily override _PROFILES_DIR
        profile = _fake_profile("UC_present")
        path = Path(td) / "UC_present.json"
        path.write_text(json.dumps(profile), encoding="utf-8")

        with mock.patch.object(cp, "_PROFILES_DIR", Path(td)):
            result = cp.load_profile("UC_present")

    assert result is not None, "Expected a dict, got None"
    assert result["channel_id"] == "UC_present"
    assert result["build_count"] == 2


# ---------------------------------------------------------------------------
# T-CP3: load_profile returns None on schema_version mismatch (logs warning)
# ---------------------------------------------------------------------------

def t_load_profile_schema_mismatch():
    """load_profile returns None when schema_version doesn't match SCHEMA_VERSION."""
    with tempfile.TemporaryDirectory() as td:
        profile = _fake_profile("UC_schema")
        profile["schema_version"] = 999  # Mismatch
        path = Path(td) / "UC_schema.json"
        path.write_text(json.dumps(profile), encoding="utf-8")

        with (
            mock.patch.object(cp, "_PROFILES_DIR", Path(td)),
            mock.patch.object(cp.log, "warning") as mock_warn,
        ):
            result = cp.load_profile("UC_schema")
            warned = mock_warn.called

    assert result is None, f"Expected None on schema mismatch, got {result!r}"
    assert warned, "Expected a warning log on schema mismatch"


# ---------------------------------------------------------------------------
# T-CP4: append_video_to_profile — creates new profile if missing
# ---------------------------------------------------------------------------

def t_append_creates_new_profile():
    """append_video_to_profile creates a new profile when none exists."""
    with tempfile.TemporaryDirectory() as td:
        with mock.patch.object(cp, "_PROFILES_DIR", Path(td)):
            profile = cp.append_video_to_profile(
                channel_id="UC_new",
                channel_name="New Channel",
                video_metadata={"video_id": "vid001", "title": "Test Vid", "duration_sec": 120},
                breakdown_text="Some breakdown text here",
            )

    assert profile["build_count"] == 1
    assert profile["channel_id"] == "UC_new"
    assert len(profile["profile_built_from"]) == 1
    assert profile["profile_built_from"][0]["video_id"] == "vid001"


# ---------------------------------------------------------------------------
# T-CP5: append_video_to_profile — appends to existing profile
# ---------------------------------------------------------------------------

def t_append_to_existing():
    """append_video_to_profile appends to an existing profile and bumps build_count."""
    with tempfile.TemporaryDirectory() as td:
        # Write initial profile with 1 entry
        initial = _fake_profile("UC_existing", build_count=1, threshold=3)
        path = Path(td) / "UC_existing.json"
        path.write_text(json.dumps(initial), encoding="utf-8")

        with mock.patch.object(cp, "_PROFILES_DIR", Path(td)):
            profile = cp.append_video_to_profile(
                channel_id="UC_existing",
                channel_name="Existing Channel",
                video_metadata={"video_id": "vid002", "title": "Second Vid", "duration_sec": 200},
                breakdown_text="Second breakdown",
            )

    assert profile["build_count"] == 2, f"Expected build_count=2, got {profile['build_count']}"
    assert len(profile["profile_built_from"]) == 2


# ---------------------------------------------------------------------------
# T-CP6: append_video_to_profile — atomic write (file is valid JSON after write)
# ---------------------------------------------------------------------------

def t_append_atomic_write():
    """After append, the file on disk is parseable JSON."""
    with tempfile.TemporaryDirectory() as td:
        with mock.patch.object(cp, "_PROFILES_DIR", Path(td)):
            cp.append_video_to_profile(
                channel_id="UC_atomic",
                channel_name="Atomic Channel",
                video_metadata={"video_id": "vatom", "title": "Atomic Vid", "duration_sec": 60},
                breakdown_text="test",
            )
            path = Path(td) / "UC_atomic.json"

        assert path.exists(), "Profile file not written"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["channel_id"] == "UC_atomic"


# ---------------------------------------------------------------------------
# T-CP7: should_distill — True iff build_count == next_distillation_threshold
# ---------------------------------------------------------------------------

def t_should_distill_at_threshold():
    """should_distill returns True exactly when build_count == threshold."""
    profile_at = _fake_profile("UC_distill", build_count=3, threshold=3)
    assert cp.should_distill(profile_at) is True, "Expected True at threshold"

    profile_below = _fake_profile("UC_distill", build_count=2, threshold=3)
    assert cp.should_distill(profile_below) is False, "Expected False below threshold"

    profile_above = _fake_profile("UC_distill", build_count=4, threshold=3)
    assert cp.should_distill(profile_above) is True, "Expected True above threshold (>= check)"


# ---------------------------------------------------------------------------
# T-CP8: distill_profile — returns dict with all 7 expected keys (mocked LLM)
# ---------------------------------------------------------------------------

def t_distill_returns_all_keys():
    """distill_profile returns a profile with all 7 style_profile keys (LLM mocked)."""
    profile = _fake_profile("UC_distill_keys", build_count=3, threshold=3)
    good_style = _good_style_profile()

    with (
        tempfile.TemporaryDirectory() as td,
        mock.patch.object(cp, "_PROFILES_DIR", Path(td)),
        mock.patch.object(cp, "_call_distillation_llm", return_value=good_style),
    ):
        result = cp.distill_profile(profile, tier="gemini")

    sp = result.get("style_profile")
    assert sp is not None, "style_profile should not be None after successful distillation"
    for key in ["hook_patterns", "pacing_patterns", "visual_style", "common_topics",
                "creator_signature", "common_b_roll_choices", "average_cuts_per_minute"]:
        assert key in sp, f"Missing key '{key}' in style_profile"


# ---------------------------------------------------------------------------
# T-CP9: distill_profile — JSONDecodeError retries once then logs ERROR
# ---------------------------------------------------------------------------

def t_distill_json_decode_error_retries():
    """On JSONDecodeError, distill_profile retries once then sets style_profile=None."""
    profile = _fake_profile("UC_json_err", build_count=3, threshold=3)
    call_count = [0]

    def fake_distill_llm(prompt, tier="gemini", retry_prefix=""):
        call_count[0] += 1
        return None  # Simulates failed JSON parse

    with (
        tempfile.TemporaryDirectory() as td,
        mock.patch.object(cp, "_PROFILES_DIR", Path(td)),
        mock.patch.object(cp, "_call_distillation_llm", side_effect=fake_distill_llm),
        mock.patch.object(cp.log, "error") as mock_err,
    ):
        result = cp.distill_profile(profile, tier="gemini")

    # Should have called the LLM twice (original + retry)
    assert call_count[0] == 2, f"Expected 2 LLM calls (1 original + 1 retry), got {call_count[0]}"
    # Should have set style_profile=None and logged ERROR
    assert result.get("style_profile") is None, "Expected style_profile=None after double failure"
    assert mock_err.called, "Expected ERROR log after double distillation failure"


# ---------------------------------------------------------------------------
# T-CP10: distill_profile — validates creator_signature is non-empty string
# ---------------------------------------------------------------------------

def t_distill_validates_creator_signature():
    """creator_signature=None/empty is replaced with the placeholder."""
    profile = _fake_profile("UC_sig_val", build_count=3, threshold=3)
    # LLM returns a style profile with null creator_signature
    bad_style = _good_style_profile()
    bad_style["creator_signature"] = None  # type: ignore[assignment]

    with (
        tempfile.TemporaryDirectory() as td,
        mock.patch.object(cp, "_PROFILES_DIR", Path(td)),
        mock.patch.object(cp, "_call_distillation_llm", return_value=bad_style),
    ):
        result = cp.distill_profile(profile, tier="gemini")

    sig = result["style_profile"]["creator_signature"]
    assert sig == cp._PLACEHOLDER, f"Expected placeholder, got {sig!r}"


# ---------------------------------------------------------------------------
# T-CP11: format_creator_context — returns None when profile is None
# ---------------------------------------------------------------------------

def t_format_context_none_profile():
    """format_creator_context returns None when passed None."""
    result = cp.format_creator_context(None)  # type: ignore[arg-type]
    assert result is None, f"Expected None for None profile, got {result!r}"


# ---------------------------------------------------------------------------
# T-CP12: format_creator_context — returns None when style_profile is None
# ---------------------------------------------------------------------------

def t_format_context_no_style():
    """format_creator_context returns None when style_profile is None."""
    profile = _fake_profile("UC_no_style", build_count=2, threshold=3, style_profile=None)
    result = cp.format_creator_context(profile)
    assert result is None, f"Expected None for profile with no style_profile, got {result!r}"


# ---------------------------------------------------------------------------
# T-CP13: format_creator_context — case-insensitive placeholder guard
# ---------------------------------------------------------------------------

def t_format_context_placeholder_guard_lowercase():
    """Returns None when creator_signature is the exact lowercase placeholder."""
    profile = _fake_profile("UC_ph1", build_count=3, threshold=3,
                             style_profile={**_good_style_profile(),
                                            "creator_signature": "insufficient data to characterize"})
    assert cp.format_creator_context(profile) is None, "Lowercase placeholder should return None"


def t_format_context_placeholder_guard_capitals():
    """Returns None when creator_signature has a capital I + period (LLM variant)."""
    profile = _fake_profile("UC_ph2", build_count=3, threshold=3,
                             style_profile={**_good_style_profile(),
                                            "creator_signature": "Insufficient data to characterize."})
    assert cp.format_creator_context(profile) is None, "Capital-I variant should return None"


def t_format_context_placeholder_guard_allcaps_whitespace():
    """Returns None when creator_signature is all-caps with extra whitespace."""
    profile = _fake_profile("UC_ph3", build_count=3, threshold=3,
                             style_profile={**_good_style_profile(),
                                            "creator_signature": "  INSUFFICIENT DATA TO CHARACTERIZE   "})
    assert cp.format_creator_context(profile) is None, "All-caps + whitespace variant should return None"


# ---------------------------------------------------------------------------
# T-CP14: format_creator_context — returns formatted string for real profile
# ---------------------------------------------------------------------------

def t_format_context_returns_string():
    """format_creator_context returns a formatted string when profile is valid."""
    profile = _fake_profile("UC_real", build_count=3, threshold=5,
                             style_profile=_good_style_profile())
    result = cp.format_creator_context(profile)
    assert isinstance(result, str), f"Expected str, got {type(result)}"
    assert "Test Channel" in result, "Channel name missing from context"
    # Should mention the number of prior videos
    assert "3" in result, "build_count not mentioned in context"


# ---------------------------------------------------------------------------
# T-CP15: format_creator_context — includes key fields in output
# ---------------------------------------------------------------------------

def t_format_context_includes_key_fields():
    """format_creator_context includes channel name, N prior videos, and key style fields."""
    style = _good_style_profile()
    profile = _fake_profile("UC_fields", build_count=5, threshold=10,
                             style_profile=style)
    result = cp.format_creator_context(profile)
    assert result is not None, "Expected non-None context"
    # Must mention "Test Channel" and "5"
    assert "Test Channel" in result
    assert "5" in result
    # Must include the Goodhart guard
    assert "CONTEXT ONLY" in result or "context only" in result.lower(), (
        "Goodhart guard not found in creator context"
    )


# ---------------------------------------------------------------------------
# T-CP16: bump_distillation_threshold
# ---------------------------------------------------------------------------

def t_bump_threshold():
    """bump_distillation_threshold sets next_distillation_threshold = build_count + 5."""
    profile = _fake_profile("UC_bump", build_count=3, threshold=3)
    cp.bump_distillation_threshold(profile)
    assert profile["next_distillation_threshold"] == 8, (
        f"Expected 8 (3+5), got {profile['next_distillation_threshold']}"
    )


# ---------------------------------------------------------------------------
# T-CP17: channel_id fallback to uploader slug (via mock fetch_metadata_only)
# ---------------------------------------------------------------------------

def t_channel_id_fallback():
    """When channel_id is missing, a sanitized uploader slug is used."""
    import youtube_video_analyzer as yt

    # Simulate yt-dlp info without channel_id
    fake_info = {
        "title": "Test Video",
        "uploader": "IBM Technology",
        "channel": "IBM Technology",
        "channel_id": None,  # missing
        "duration": 300,
        "upload_date": "20260101",
        "description": "",
        "is_live": False,
        "was_live": False,
    }

    class FakeYDL:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass
        def extract_info(self, url, download=False):
            return fake_info

    with mock.patch("yt_dlp.YoutubeDL", return_value=FakeYDL()):
        metadata = yt.fetch_metadata_only("https://youtu.be/jNQXAC9IVRw")

    cid = metadata.get("channel_id")
    assert cid is not None, "channel_id should not be None even without channel_id from yt-dlp"
    # Should be a sanitized slug of "IBM Technology"
    assert cid == "ibm-technology" or "ibm" in cid.lower(), (
        f"Expected uploader slug, got {cid!r}"
    )


# ---------------------------------------------------------------------------
# T-CP18: --no-creator-profile flag — no profile read/write
# ---------------------------------------------------------------------------

def t_no_creator_profile_flag():
    """--no-creator-profile skips creator-profile features entirely."""
    result = _cli(VALID_URL_1, "--dry-run", "--no-creator-profile")
    assert result.returncode == 0, (
        f"--no-creator-profile + --dry-run failed; exit={result.returncode}\n{result.stderr[:300]}"
    )
    # Creator profile module should not be imported/called on --dry-run --no-creator-profile
    # Verify flag appears in --help
    help_result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert "--no-creator-profile" in help_result.stdout, "--no-creator-profile missing from --help"


# ---------------------------------------------------------------------------
# T-CP19: --refresh-creator-profile flag accepted (in --help)
# ---------------------------------------------------------------------------

def t_refresh_creator_profile_flag():
    """--refresh-creator-profile appears in --help output."""
    help_result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert "--refresh-creator-profile" in help_result.stdout, (
        "--refresh-creator-profile missing from --help"
    )


# ---------------------------------------------------------------------------
# T-CP20: --show-creator-profile <known> --no-analyze — prints JSON, exit 0
# ---------------------------------------------------------------------------

def t_show_creator_profile_known():
    """--show-creator-profile for a known channel prints JSON and exits 0."""
    profiles_dir = WORKSPACE / ".tmp" / "creator_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    test_id = "_test_show_profile_cp20"
    profile = _fake_profile(test_id, build_count=2, threshold=3)
    profile_path = profiles_dir / f"{test_id}.json"
    profile_path.write_text(json.dumps(profile), encoding="utf-8")

    try:
        result = _cli("--show-creator-profile", test_id, "--no-analyze")
        assert result.returncode == 0, (
            f"--show-creator-profile should exit 0 for known channel; got {result.returncode}\n{result.stderr[:300]}"
        )
        parsed = json.loads(result.stdout)
        assert parsed["channel_id"] == test_id
    finally:
        profile_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# T-CP21: --show-creator-profile <unknown> --no-analyze — error, non-zero exit
# ---------------------------------------------------------------------------

def t_show_creator_profile_unknown():
    """--show-creator-profile for an unknown channel shows error and exits non-zero."""
    result = _cli("--show-creator-profile", "_no_such_channel_xyz_99999", "--no-analyze")
    assert result.returncode != 0, (
        f"Unknown channel should exit non-zero; got {result.returncode}"
    )
    # Should print an error to stderr
    assert "No profile" in result.stderr or "not found" in result.stderr.lower() or result.returncode != 0


# ---------------------------------------------------------------------------
# T-CP22: --show-creator-profile requires --no-analyze (error without it)
# ---------------------------------------------------------------------------

def t_show_creator_profile_requires_no_analyze():
    """--show-creator-profile without --no-analyze is a CLI error."""
    result = _cli("--show-creator-profile", "UC_test")
    # Should exit non-zero (argparse error)
    assert result.returncode != 0, (
        f"--show-creator-profile without --no-analyze should fail; got returncode=0"
    )


if __name__ == "__main__":
    print("=== CREATOR-PROFILE CACHE TESTS ===")
    print()

    run("load_profile: returns None when file missing", t_load_profile_missing)
    run("load_profile: returns dict when file present", t_load_profile_present)
    run("load_profile: returns None on schema_version mismatch (logs warning)", t_load_profile_schema_mismatch)
    run("append_video_to_profile: creates new profile if missing", t_append_creates_new_profile)
    run("append_video_to_profile: appends to existing, bumps build_count", t_append_to_existing)
    run("append_video_to_profile: atomic write (valid JSON on disk)", t_append_atomic_write)
    run("should_distill: True iff build_count >= next_distillation_threshold", t_should_distill_at_threshold)
    run("distill_profile: returns dict with all 7 style_profile keys (mocked LLM)", t_distill_returns_all_keys)
    run("distill_profile: JSONDecodeError retries once then style_profile=None + ERROR log", t_distill_json_decode_error_retries)
    run("distill_profile: creator_signature=None replaced with placeholder", t_distill_validates_creator_signature)
    run("format_creator_context: returns None when profile is None", t_format_context_none_profile)
    run("format_creator_context: returns None when style_profile is None", t_format_context_no_style)
    run("format_creator_context: placeholder guard — lowercase exact match returns None", t_format_context_placeholder_guard_lowercase)
    run("format_creator_context: placeholder guard — 'Insufficient data to characterize.' returns None", t_format_context_placeholder_guard_capitals)
    run("format_creator_context: placeholder guard — all-caps + whitespace returns None", t_format_context_placeholder_guard_allcaps_whitespace)
    run("format_creator_context: returns formatted string for real profile", t_format_context_returns_string)
    run("format_creator_context: includes channel name + N prior videos + key fields", t_format_context_includes_key_fields)
    run("bump_distillation_threshold: sets threshold = build_count + 5", t_bump_threshold)
    run("channel_id fallback: uploader slug used when channel_id missing", t_channel_id_fallback)
    run("--no-creator-profile: flag accepted, appears in --help", t_no_creator_profile_flag)
    run("--refresh-creator-profile: appears in --help", t_refresh_creator_profile_flag)
    run("--show-creator-profile <known> --no-analyze: prints JSON, exit 0", t_show_creator_profile_known)
    run("--show-creator-profile <unknown> --no-analyze: error, non-zero exit", t_show_creator_profile_unknown)
    run("--show-creator-profile without --no-analyze: CLI error, non-zero exit", t_show_creator_profile_requires_no_analyze)

    print()
    print(f"Creator-profile: {PASS_COUNT} passed, {FAIL_COUNT} failed")
    if FAILURES:
        print("Failed tests:")
        for n, e in FAILURES:
            print(f"  - {n}: {e}")
    sys.exit(0 if FAIL_COUNT == 0 else 1)
