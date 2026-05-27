"""
conftest.py for tests/mobile_apps
Provides shared fixtures: isolated registry path, repo root on sys.path,
and helpers to import the 6 mobile_apps scripts cleanly.
"""

import importlib
import json
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MOBILE_APPS_DIR = PROJECT_ROOT / "execution" / "mobile_apps"

# Ensure project root is on sys.path
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
# Also expose the mobile_apps dir so we can `import bootstrap_mobile_app`
if str(MOBILE_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(MOBILE_APPS_DIR))


@pytest.fixture
def isolated_registry(tmp_path, monkeypatch):
    """Point REGISTRY_PATH (in every script module) at a tmp file.
    Returns the tmp Path. Reload modules so they pick up the new path.
    """
    reg_path = tmp_path / "registry.json"
    reg_path.write_text(
        json.dumps({"schema_version": 1, "apps": []}, indent=2),
        encoding="utf-8",
    )

    # Import and patch each script module's REGISTRY_PATH
    modules = [
        "bootstrap_mobile_app",
        "eas_build_helper",
        "play_console_tester_gate",
        "testflight_invite",
        "mobile_app_canary",
    ]
    for name in modules:
        if name in sys.modules:
            mod = sys.modules[name]
        else:
            mod = importlib.import_module(name)
        monkeypatch.setattr(mod, "REGISTRY_PATH", reg_path, raising=False)

    return reg_path


@pytest.fixture
def isolated_mobile_apps_base(tmp_path, monkeypatch):
    """Point bootstrap_mobile_app.MOBILE_APPS_BASE + TEMPLATE_DIR at tmp dirs
    so we never touch the real C:/Users/deban/dev/mobile-apps tree.
    """
    base = tmp_path / "mobile-apps"
    base.mkdir()
    template = base / "_template"
    template.mkdir()
    # Minimal template scaffold: a few text files containing the slug placeholder
    (template / "package.json").write_text(
        '{"name": "{{APP_SLUG}}", "version": "0.0.1"}\n', encoding="utf-8"
    )
    (template / "app.json").write_text(
        '{"expo": {"slug": "{{APP_SLUG}}"}}\n', encoding="utf-8"
    )
    (template / "README.md").write_text(
        "# {{APP_SLUG}}\nA template.\n", encoding="utf-8"
    )
    # And a binary-ish file that should be skipped
    (template / "icon.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x9d\x00")

    import bootstrap_mobile_app as bma
    monkeypatch.setattr(bma, "MOBILE_APPS_BASE", base, raising=False)
    monkeypatch.setattr(bma, "TEMPLATE_DIR", template, raising=False)
    return base


@pytest.fixture
def sample_app_entry():
    return {
        "slug": "fixture-app",
        "repo_path": "C:/tmp/fixture-app",
        "ios_bundle_id": "com.example.fixture",
        "android_package": "com.example.fixture",
        "eas_project_id": None,
        "last_build_sha": None,
        "health_url": None,
        "play_tester_gate_started_at": None,
        "play_tester_count_manual": None,
        "created_at": "2026-05-27T00:00:00+00:00",
    }
