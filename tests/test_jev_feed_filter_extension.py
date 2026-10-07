"""Validate the Jev feed filter Chrome extension manifest and run its offline Node smoke test."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

EXT = Path(__file__).resolve().parent.parent / "execution" / "infrastructure" / "jev_feed_filter_extension"


def _manifest() -> dict:
    return json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))


def test_manifest_is_mv3_and_files_exist() -> None:
    m = _manifest()
    assert m["manifest_version"] == 3
    for key in ("name", "version", "permissions", "host_permissions", "background", "content_scripts", "action"):
        assert key in m, key
    assert {"storage", "activeTab"} <= set(m["permissions"])
    assert "https://openrouter.ai/*" in m["host_permissions"]
    refs = [m["background"]["service_worker"], m["action"]["default_popup"], m["options_page"], "jev_api.js"]
    for cs in m["content_scripts"]:
        refs += cs["js"]
    for ref in refs:
        assert (EXT / ref).is_file(), ref
    matches = {u for cs in m["content_scripts"] for u in cs["matches"]}
    assert "https://x.com/*" in matches and "<all_urls>" in matches


def test_offline_smoke() -> None:
    if not shutil.which("node"):
        pytest.skip("node not installed")
    proc = subprocess.run(
        ["node", "test/smoke.mjs", "--offline"], cwd=EXT, capture_output=True,
        encoding="utf-8", errors="replace", timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SKIPPED (--offline)" in proc.stdout
