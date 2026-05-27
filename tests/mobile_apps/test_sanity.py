"""Sanity tests: every script compiles, --help works, imports are clean,
and registry.json (if present) matches schema."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MOBILE_APPS_DIR = PROJECT_ROOT / "execution" / "mobile_apps"

SCRIPTS = [
    "bootstrap_mobile_app.py",
    "eas_build_helper.py",
    "play_console_tester_gate.py",
    "testflight_invite.py",
    "mobile_app_canary.py",
    "app_store_research.py",
]


@pytest.mark.parametrize("script", SCRIPTS)
def test_py_compile(script):
    rc = subprocess.run(
        [sys.executable, "-m", "py_compile", str(MOBILE_APPS_DIR / script)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert rc.returncode == 0, f"compile failed: {rc.stderr}"


@pytest.mark.parametrize("script", SCRIPTS)
def test_help_flag(script):
    rc = subprocess.run(
        [sys.executable, str(MOBILE_APPS_DIR / script), "--help"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=30,
    )
    assert rc.returncode == 0, f"--help failed for {script}: {rc.stderr}"
    assert ("usage:" in rc.stdout.lower()) or ("usage:" in rc.stderr.lower())


@pytest.mark.parametrize("module", [
    "bootstrap_mobile_app",
    "eas_build_helper",
    "play_console_tester_gate",
    "testflight_invite",
    "mobile_app_canary",
    "app_store_research",
])
def test_import_clean(module):
    """Import each module — must not run main() or touch network/registry."""
    code = (
        f"import sys; sys.path.insert(0, r'{MOBILE_APPS_DIR}');"
        f" import {module}; print('OK')"
    )
    rc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=15,
    )
    assert rc.returncode == 0, f"import failed: {rc.stderr}"
    assert "OK" in rc.stdout


def test_registry_schema_if_present():
    """If registry.json exists, it must be valid JSON with the expected shape."""
    reg = MOBILE_APPS_DIR / "registry.json"
    if not reg.exists():
        pytest.skip("registry.json not yet created")
    parsed = json.loads(reg.read_text(encoding="utf-8"))
    assert isinstance(parsed.get("schema_version"), int)
    assert isinstance(parsed.get("apps"), list)
    for app in parsed["apps"]:
        assert isinstance(app, dict)
        assert "slug" in app
