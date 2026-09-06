"""
description: Tests for scripts/package_job_digest.py — the standalone-bundle builder.
inputs: none (builds the zip into a tmp dist dir; never touches the real dist/)
outputs: pytest results
"""
from __future__ import annotations

import importlib.util
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_PATH = REPO_ROOT / "scripts" / "package_job_digest.py"


def _load_package_module():
    spec = importlib.util.spec_from_file_location("package_job_digest", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["package_job_digest"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def pkg_mod():
    return _load_package_module()


def test_builds_expected_tree(pkg_mod, tmp_path, monkeypatch):
    dist_dir = tmp_path / "dist"
    zip_path = pkg_mod.build(dist_dir=dist_dir, zip_name="job-digest-skill.zip")

    assert zip_path == dist_dir / "job-digest-skill.zip"
    assert zip_path.exists()

    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())

    assert "job-digest/SKILL.md" in names
    assert "job-digest/CHANGELOG.md" in names
    assert "job-digest/README.md" in names
    assert "job-digest/engine/requirements.txt" in names
    assert any(n.startswith("job-digest/engine/job_digest/") for n in names)
    assert "job-digest/engine/job_digest/registry.py" in names
    assert "job-digest/engine/job_digest/profile_schema.py" in names

    # tests/, __pycache__/, .tmp/ must never be bundled
    assert not any("/engine/job_digest/tests/" in n for n in names)
    assert not any("__pycache__" in n for n in names)
    assert not any("/.tmp/" in n for n in names)


def test_blocklist_catches_planted_literal(pkg_mod, tmp_path, monkeypatch):
    # Plant a blocklisted literal into a copy of the engine source tree and point the
    # module at it, so the real engine source is never modified.
    fake_engine = tmp_path / "fake_engine"
    fake_engine.mkdir()
    (fake_engine / "__init__.py").write_text("", encoding="utf-8")
    (fake_engine / "oops.py").write_text(
        f"# contact: {pkg_mod._TEST_MARKER}\n", encoding="utf-8"
    )

    fake_skill = tmp_path / "fake_skill"
    fake_skill.mkdir()
    (fake_skill / "SKILL.md").write_text("---\nname: job-digest\n---\n", encoding="utf-8")
    (fake_skill / "CHANGELOG.md").write_text("# changelog\n", encoding="utf-8")

    monkeypatch.setattr(pkg_mod, "ENGINE_SRC", fake_engine)
    monkeypatch.setattr(pkg_mod, "SKILL_SRC", fake_skill)
    monkeypatch.setattr(pkg_mod, "README_FRIEND", fake_engine / "templates" / "README_FRIEND.md")

    dist_dir = tmp_path / "dist2"
    with pytest.raises(SystemExit) as exc_info:
        pkg_mod.build(dist_dir=dist_dir, zip_name="job-digest-skill.zip")

    assert exc_info.value.code == 2
    assert not (dist_dir / "job-digest-skill.zip").exists()


def test_blocklist_clean_bundle_succeeds(pkg_mod, tmp_path, monkeypatch):
    fake_engine = tmp_path / "clean_engine"
    fake_engine.mkdir()
    (fake_engine / "__init__.py").write_text("", encoding="utf-8")
    (fake_engine / "clean.py").write_text("# nothing personal here\n", encoding="utf-8")

    fake_skill = tmp_path / "clean_skill"
    fake_skill.mkdir()
    (fake_skill / "SKILL.md").write_text("---\nname: job-digest\n---\n", encoding="utf-8")
    (fake_skill / "CHANGELOG.md").write_text("# changelog\n", encoding="utf-8")

    monkeypatch.setattr(pkg_mod, "ENGINE_SRC", fake_engine)
    monkeypatch.setattr(pkg_mod, "SKILL_SRC", fake_skill)
    monkeypatch.setattr(pkg_mod, "README_FRIEND", fake_engine / "templates" / "README_FRIEND.md")

    dist_dir = tmp_path / "dist3"
    zip_path = pkg_mod.build(dist_dir=dist_dir, zip_name="job-digest-skill.zip")
    assert zip_path.exists()
