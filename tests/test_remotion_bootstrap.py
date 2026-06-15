"""Unit tests for execution/video/remotion_bootstrap.py.

Covers the pure / in-process helpers — anything that does NOT require running
`npm create-video` or `npm install` (those are minute-scale and require Node).
The operator runs the full bootstrap manually as the front-door synthetic;
these tests catch the things that fail silently across versions.

Covered:
  - validate_slug: positive + reserved + invalid
  - humanize_slug
  - find_project
  - load_registry on missing / present file
  - write_registry_atomic (no torn writes, lock guarded)
  - apply_overlay: file copy + placeholder substitution + .template-version
  - tsc_compile_check: soft-skip when npx missing; pass-through when present
"""
from __future__ import annotations

import importlib.util
import json
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

WORKSPACE = Path(__file__).resolve().parents[1]
_BS_PATH = WORKSPACE / "execution" / "video" / "remotion_bootstrap.py"
_spec = importlib.util.spec_from_file_location("remotion_bootstrap", _BS_PATH)
bs = importlib.util.module_from_spec(_spec)
sys.modules["remotion_bootstrap"] = bs
_spec.loader.exec_module(bs)


# ----------------------------------------------------------------------------
# validate_slug
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("slug", ["a", "abc", "abc-def", "abc_def", "a1", "demo01"])
def test_validate_slug_accepts(slug):
    bs.validate_slug(slug)  # no exception


@pytest.mark.parametrize("slug", ["", "A", "abc..def", "../etc", "x" * 60, "-abc", "abc-"])
def test_validate_slug_rejects(slug):
    with pytest.raises(ValueError):
        bs.validate_slug(slug)


def test_validate_slug_reserved_requires_force():
    with pytest.raises(ValueError, match="reserved"):
        bs.validate_slug("_template")
    bs.validate_slug("_template", force=True)  # force lets it through


# ----------------------------------------------------------------------------
# humanize_slug
# ----------------------------------------------------------------------------

def test_humanize_slug_basic():
    assert bs.humanize_slug("hello_world") == "Hello World"
    assert bs.humanize_slug("alpha-beta") == "Alpha Beta"


def test_humanize_slug_single_word():
    assert bs.humanize_slug("demo") == "Demo"


# ----------------------------------------------------------------------------
# find_project
# ----------------------------------------------------------------------------

def test_find_project_found():
    reg = {"projects": [{"slug": "alpha"}, {"slug": "beta"}]}
    assert bs.find_project(reg, "beta") == {"slug": "beta"}


def test_find_project_not_found():
    reg = {"projects": [{"slug": "alpha"}]}
    assert bs.find_project(reg, "beta") is None


def test_find_project_empty_registry():
    assert bs.find_project({}, "x") is None
    assert bs.find_project({"projects": []}, "x") is None


# ----------------------------------------------------------------------------
# load_registry / write_registry_atomic
# ----------------------------------------------------------------------------

def test_load_registry_missing_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(bs, "REGISTRY_PATH", tmp_path / "registry.json")
    reg = bs.load_registry()
    assert reg == {"schema_version": 1, "projects": []}


def test_load_registry_existing(tmp_path, monkeypatch):
    path = tmp_path / "registry.json"
    path.write_text(json.dumps({"schema_version": 1, "projects": [{"slug": "x"}]}), encoding="utf-8")
    monkeypatch.setattr(bs, "REGISTRY_PATH", path)
    reg = bs.load_registry()
    assert reg["projects"] == [{"slug": "x"}]


def test_write_registry_atomic_creates_file(tmp_path, monkeypatch):
    path = tmp_path / "registry.json"
    monkeypatch.setattr(bs, "REGISTRY_PATH", path)
    bs.write_registry_atomic({"schema_version": 1, "projects": [{"slug": "alpha"}]})
    assert path.exists()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["projects"][0]["slug"] == "alpha"


def test_write_registry_atomic_cleans_tmp(tmp_path, monkeypatch):
    """No .tmp.* files should remain after a successful write."""
    path = tmp_path / "registry.json"
    monkeypatch.setattr(bs, "REGISTRY_PATH", path)
    bs.write_registry_atomic({"schema_version": 1, "projects": []})
    leftovers = list(tmp_path.glob("registry.json.tmp.*"))
    assert leftovers == []


def test_write_registry_atomic_lock_serializes_writes(tmp_path, monkeypatch):
    """Concurrent writes from two threads must not corrupt the registry."""
    path = tmp_path / "registry.json"
    monkeypatch.setattr(bs, "REGISTRY_PATH", path)

    def writer(slug):
        bs.write_registry_atomic({"schema_version": 1, "projects": [{"slug": slug}]})

    t1 = threading.Thread(target=writer, args=("a",))
    t2 = threading.Thread(target=writer, args=("b",))
    t1.start(); t2.start(); t1.join(); t2.join()

    # File must be parseable JSON (not half-written) and contain exactly one of a/b.
    loaded = json.loads(path.read_text(encoding="utf-8"))
    slugs = {p["slug"] for p in loaded.get("projects", [])}
    assert slugs <= {"a", "b"} and len(slugs) == 1


# ----------------------------------------------------------------------------
# apply_overlay
# ----------------------------------------------------------------------------

def _make_overlay_fixture(root: Path) -> Path:
    overlay = root / "overlay"
    overlay.mkdir()
    # project.json with placeholders + default values
    (overlay / "project.json").write_text(json.dumps({
        "slug": "{{SLUG}}",
        "title": "{{TITLE}}",
        "fps": 30,
        "width": 1280,
        "height": 720,
        "duration_in_frames": 100,
    }), encoding="utf-8")
    # .template-version with marker
    (overlay / ".template-version").write_text("PINNED_AT_BOOTSTRAP\n", encoding="utf-8")
    # nested file to exercise the recursive copy
    (overlay / "src").mkdir()
    (overlay / "src" / "Root.tsx").write_text("export const Root = () => null;\n", encoding="utf-8")
    return overlay


def test_apply_overlay_copies_files_and_substitutes(tmp_path, monkeypatch):
    overlay = _make_overlay_fixture(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(bs, "OVERLAY_DIR", overlay)

    bs.apply_overlay(
        project, slug="my_slug", title="My App",
        fps=60, width=1920, height=1080, duration_in_frames=900,
        upstream_sha="abc123",
    )

    # project.json substituted + values updated
    data = json.loads((project / "project.json").read_text(encoding="utf-8"))
    assert data["slug"] == "my_slug"
    assert data["title"] == "My App"
    assert data["fps"] == 60
    assert data["width"] == 1920 and data["height"] == 1080
    assert data["duration_in_frames"] == 900

    # .template-version SHA injected
    assert (project / ".template-version").read_text(encoding="utf-8").strip() == "abc123"

    # Nested file copied
    assert (project / "src" / "Root.tsx").exists()


# ----------------------------------------------------------------------------
# tsc_compile_check
# ----------------------------------------------------------------------------

def test_tsc_skipped_when_npx_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(bs.shutil, "which", lambda _name: None)
    ok, msg = bs.tsc_compile_check(tmp_path)
    assert ok is True
    assert "skip" in msg


def test_tsc_returns_ok_on_zero_exit(tmp_path, monkeypatch):
    monkeypatch.setattr(bs.shutil, "which", lambda _name: r"C:\fake\npx.cmd")
    fake = MagicMock(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(bs.subprocess, "run", lambda *a, **kw: fake)
    ok, msg = bs.tsc_compile_check(tmp_path)
    assert ok is True
    assert "OK" in msg


def test_tsc_reports_failure_on_nonzero(tmp_path, monkeypatch):
    monkeypatch.setattr(bs.shutil, "which", lambda _name: r"C:\fake\npx.cmd")
    fake = MagicMock(returncode=2, stdout="", stderr="Error TS2305: Module has no exported member 'X'\n")
    monkeypatch.setattr(bs.subprocess, "run", lambda *a, **kw: fake)
    ok, msg = bs.tsc_compile_check(tmp_path)
    assert ok is False
    assert "tsc --noEmit failed" in msg
    assert "TS2305" in msg


def test_tsc_soft_skips_on_invocation_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(bs.shutil, "which", lambda _name: r"C:\fake\npx.cmd")
    def _raise(*a, **kw):
        raise OSError("spawn failed")
    monkeypatch.setattr(bs.subprocess, "run", _raise)
    ok, msg = bs.tsc_compile_check(tmp_path)
    # Bootstrap shouldn't fail just because tsc spawning failed at the OS level.
    assert ok is True
    assert "skip" in msg
