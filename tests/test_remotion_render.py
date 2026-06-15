"""Unit tests for execution/video/remotion_render.py.

Tests the pure / in-process helpers and mocked subprocess paths.
Does NOT require Node.js, npm, or an actual Remotion project.
Always runs (no REMOTION_LIVE gate).

Covered:
  - validate_slug: accepts valid, rejects invalid / traversal
  - validate_out_path: accepts in-workspace, rejects out-of-workspace
  - pick_composition: parses id from Root.tsx, falls back to 'Scene'
  - default_out_path: uses .tmp/remotion-renders/<slug>-<ts>.mp4
  - render(): missing registry entry errors cleanly
  - render(): missing project dir errors cleanly
  - render(): missing node_modules errors cleanly
  - render(): mocked subprocess — verifies command shape and timeout arg
  - render(): path-traversal slug rejected before subprocess is called
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Load module under test ────────────────────────────────────────────────────

WORKSPACE = Path(__file__).resolve().parents[1]
_RR_PATH = WORKSPACE / "execution" / "video" / "remotion_render.py"
_spec = importlib.util.spec_from_file_location("remotion_render", _RR_PATH)
rr = importlib.util.module_from_spec(_spec)
sys.modules["remotion_render"] = rr
_spec.loader.exec_module(rr)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_registry(tmp_path, monkeypatch):
    """Patch REGISTRY_PATH + PROJECTS_DIR to a temp directory."""
    reg_path = tmp_path / "registry.json"
    projects_dir = tmp_path / "remotion-projects"
    projects_dir.mkdir()
    monkeypatch.setattr(rr, "REGISTRY_PATH", reg_path)
    monkeypatch.setattr(rr, "PROJECTS_DIR", projects_dir)
    return tmp_path, reg_path, projects_dir


def _write_registry(reg_path: Path, projects: list[dict]) -> None:
    reg_path.write_text(
        json.dumps({"schema_version": 1, "projects": projects}),
        encoding="utf-8",
    )


def _make_project(projects_dir: Path, slug: str) -> Path:
    """Create a minimal project skeleton sufficient for render() pre-checks."""
    proj = projects_dir / slug
    proj.mkdir()
    nm = proj / "node_modules"
    nm.mkdir()
    src = proj / "src"
    src.mkdir()
    root_tsx = src / "Root.tsx"
    root_tsx.write_text(
        '<Composition id="MyScene" component={MyComp} />\n',
        encoding="utf-8",
    )
    return proj


# ── validate_slug ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("slug", ["a", "abc", "abc-def", "abc_def", "a1", "demo01", "_smoketest"])
def test_validate_slug_accepts(slug, tmp_registry):
    _, _, projects_dir = tmp_registry
    # Should not raise; returned path must be inside PROJECTS_DIR
    result = rr.validate_slug(slug)
    assert result.is_relative_to(projects_dir)


@pytest.mark.parametrize("slug", ["", "A", "ABC", "../etc", "x" * 60, "-abc", "abc-"])
def test_validate_slug_rejects(slug):
    with pytest.raises(ValueError, match="Invalid slug|Path-traversal"):
        rr.validate_slug(slug)


def test_validate_slug_traversal_rejected(tmp_registry):
    """Slug that contains path separator bytes after regex pass must still be caught."""
    _, _, projects_dir = tmp_registry
    # On Windows, a slug like 'a/b' is caught by SLUG_RE first (slash not allowed),
    # but we also explicitly check after resolve.
    with pytest.raises(ValueError):
        rr.validate_slug("../secrets")


# ── validate_out_path ─────────────────────────────────────────────────────────

def test_validate_out_path_accepts_relative_under_workspace(monkeypatch):
    # Patch ROOT to tmp so we don't need the real workspace
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setattr(rr, "ROOT", Path(td))
        inside = str(Path(td) / "subdir" / "out.mp4")
        result = rr.validate_out_path(inside)
        assert result == Path(inside).resolve()


def test_validate_out_path_rejects_outside_workspace(monkeypatch):
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setattr(rr, "ROOT", Path(td))
        outside = "C:/Windows/System32/evil.mp4"
        with pytest.raises(ValueError, match="resolves outside"):
            rr.validate_out_path(outside)


# ── pick_composition ──────────────────────────────────────────────────────────

def test_pick_composition_from_src_root_tsx(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "Root.tsx").write_text(
        '<Composition id="MyAwesomeScene" />\n', encoding="utf-8"
    )
    assert rr.pick_composition(tmp_path) == "MyAwesomeScene"


def test_pick_composition_from_top_level_root_tsx(tmp_path):
    (tmp_path / "Root.tsx").write_text(
        "<Composition id={'TopLevel'} />\n", encoding="utf-8"
    )
    assert rr.pick_composition(tmp_path) == "TopLevel"


def test_pick_composition_fallback_to_scene(tmp_path):
    # No Root.tsx at all → should return 'Scene'
    assert rr.pick_composition(tmp_path) == "Scene"


# ── default_out_path ──────────────────────────────────────────────────────────

def test_default_out_path_shape():
    p = rr.default_out_path("myslug")
    assert p.suffix == ".mp4"
    assert "myslug" in p.name
    assert p.parent.name == "remotion-renders"


# ── render() error paths (mocked) ────────────────────────────────────────────

def test_render_unknown_slug_returns_2(tmp_registry):
    _, reg_path, _ = tmp_registry
    _write_registry(reg_path, [])          # empty registry
    code = rr.render("unknown", composition=None, out=None, frames=None)
    assert code == 2


def test_render_missing_project_dir_returns_2(tmp_registry):
    _, reg_path, projects_dir = tmp_registry
    # Registered but project dir not created
    _write_registry(reg_path, [{"slug": "myvid"}])
    code = rr.render("myvid", composition=None, out=None, frames=None)
    assert code == 2


def test_render_missing_node_modules_returns_2(tmp_registry):
    _, reg_path, projects_dir = tmp_registry
    proj = projects_dir / "myvid"
    proj.mkdir()
    # No node_modules
    _write_registry(reg_path, [{"slug": "myvid"}])
    code = rr.render("myvid", composition=None, out=None, frames=None)
    assert code == 2


def test_render_path_traversal_slug_returns_2(tmp_registry, monkeypatch):
    """Path-traversal slug must be rejected before any subprocess call."""
    called = []
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **kw: called.append(a) or MagicMock(returncode=0),
    )
    code = rr.render("../evil", composition=None, out=None, frames=None)
    assert code == 2
    assert called == [], "subprocess.run must not be called on invalid slug"


def test_render_command_shape(tmp_registry, monkeypatch, tmp_path):
    """When all pre-checks pass, verify the subprocess command shape."""
    _, reg_path, projects_dir = tmp_registry
    proj = _make_project(projects_dir, "myvid")
    _write_registry(reg_path, [{"slug": "myvid"}])

    # Default out path will be under RENDERS_DIR; patch it to tmp_path
    render_out = tmp_path / "remotion-renders"
    render_out.mkdir()
    monkeypatch.setattr(rr, "RENDERS_DIR", render_out)

    captured: list[dict] = []

    def fake_run(cmd, **kwargs):
        captured.append({"cmd": cmd, "kwargs": kwargs})
        # Simulate a successful render by creating the output file
        out_arg = kwargs.get("cwd") and None   # out is positional in cmd list
        # Find the output path from the cmd list (3rd positional after 'render' and comp)
        out_file = Path(cmd[4])   # index: npx remotion render <comp> <out> ...
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_bytes(b"\x00" * 1024)   # non-empty file
        return MagicMock(returncode=0)

    monkeypatch.setattr("subprocess.run", fake_run)

    code = rr.render("myvid", composition=None, out=None, frames="0-29")
    assert code == 0

    assert len(captured) == 1
    cmd = captured[0]["cmd"]
    assert "npx" in cmd[0]
    assert "remotion" in cmd
    assert "render" in cmd
    assert "--frames" in cmd
    assert "0-29" in cmd
    assert "--concurrency" in cmd

    # Verify timeout is set
    assert captured[0]["kwargs"].get("timeout") == rr.RENDER_TIMEOUT_S

    # Verify encoding hardening (rule #1)
    assert captured[0]["kwargs"].get("encoding") == "utf-8"
    assert captured[0]["kwargs"].get("errors") == "replace"
