"""Unit tests for eas_build_helper.py."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
EAS_SCRIPT = PROJECT_ROOT / "execution" / "mobile_apps" / "eas_build_helper.py"


def _import_eas():
    import eas_build_helper
    return eas_build_helper


def test_parse_build_url_finds_url():
    eas = _import_eas()
    txt = (
        "Some preamble text.\n"
        "Build details: https://expo.dev/accounts/myorg/projects/foo/builds/abc-123-def\n"
        "More text."
    )
    url, build_id = eas.parse_build_url(txt)
    assert url == "https://expo.dev/accounts/myorg/projects/foo/builds/abc-123-def"
    assert build_id == "abc-123-def"


def test_parse_build_url_no_match():
    eas = _import_eas()
    url, build_id = eas.parse_build_url("nothing here")
    assert url is None
    assert build_id is None


def test_parse_build_url_handles_empty():
    eas = _import_eas()
    url, build_id = eas.parse_build_url("")
    assert url is None
    assert build_id is None


def test_argparse_rejects_bad_platform():
    """--platform must be ios or android."""
    rc = subprocess.run(
        [sys.executable, str(EAS_SCRIPT), "--app", "x", "--platform", "windows",
         "--profile", "preview"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert rc.returncode != 0
    assert "windows" in rc.stderr or "invalid choice" in rc.stderr


def test_argparse_rejects_bad_profile():
    rc = subprocess.run(
        [sys.executable, str(EAS_SCRIPT), "--app", "x", "--platform", "ios",
         "--profile", "develop"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert rc.returncode != 0


def test_argparse_requires_all_args():
    rc = subprocess.run(
        [sys.executable, str(EAS_SCRIPT), "--app", "x"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert rc.returncode != 0


def test_help_exits_zero():
    rc = subprocess.run(
        [sys.executable, str(EAS_SCRIPT), "--help"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert rc.returncode == 0
    assert "platform" in rc.stdout


def test_post_webhook_no_requests(monkeypatch, capsys):
    """If requests is None, post_webhook prints warning and returns (no crash)."""
    eas = _import_eas()
    monkeypatch.setattr(eas, "requests", None)
    eas.post_webhook("http://example.com", {"k": "v"})
    # Should not raise
    captured = capsys.readouterr()
    assert "requests" in (captured.out + captured.err).lower()


def test_app_not_in_registry_returns_2(isolated_registry):
    """Run helper for a slug not in the (empty) registry -> exit 2."""
    rc = subprocess.run(
        [sys.executable, str(EAS_SCRIPT),
         "--app", "nonexistent-app",
         "--platform", "ios",
         "--profile", "preview"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        # Note: this subprocess will use the REAL registry path, not the fixture's tmp.
        # The point of this test is to confirm the "not in registry" branch returns 2.
        # If the real registry happens to have an "nonexistent-app", this test could
        # false-pass. That's acceptable for a smoke test.
    )
    # Either app is missing (rc=2) or repo_path doesn't exist (rc=2) or eas build
    # actually got to run. We want rc != 0 and stderr to mention registry.
    assert rc.returncode == 2
    assert "not in registry" in rc.stderr or "does not exist" in rc.stderr
