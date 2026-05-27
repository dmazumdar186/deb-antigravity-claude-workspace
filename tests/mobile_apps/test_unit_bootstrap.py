"""Unit tests for bootstrap_mobile_app.py."""

import json
import os
import stat
import sys
from pathlib import Path

import pytest


def _import_bma():
    import bootstrap_mobile_app
    return bootstrap_mobile_app


# ---------- validate_slug ----------

@pytest.mark.parametrize("slug", [
    "my-app",
    "app",
    "my-cool-app-2",
    "a1-b2",
    "abc123",
])
def test_validate_slug_valid(slug):
    bma = _import_bma()
    bma.validate_slug(slug)  # should not raise


@pytest.mark.parametrize("slug", [
    "My-App",       # uppercase
    "my app",       # space
    "-leading",     # leading hyphen
    "trailing-",    # trailing hyphen
    "double--dash", # consecutive hyphens
    "",             # empty
    "../etc",       # path traversal chars
    "with/slash",
    "with\\back",
    "with.dot",
    "_under",
    "UPPER",
])
def test_validate_slug_invalid(slug):
    bma = _import_bma()
    with pytest.raises(ValueError):
        bma.validate_slug(slug)


# ---------- resolve_app_dir ----------

def test_resolve_app_dir_normal_slug(isolated_mobile_apps_base):
    bma = _import_bma()
    p = bma.resolve_app_dir("my-app")
    assert p.is_relative_to(isolated_mobile_apps_base.resolve())
    assert p.name == "my-app"


def test_resolve_app_dir_rejects_traversal(isolated_mobile_apps_base, monkeypatch):
    """If somehow a slug bypasses validate_slug (e.g. internal call), resolve_app_dir
    must still refuse path escape."""
    bma = _import_bma()
    # Direct call to resolve_app_dir bypassing validate_slug — should still refuse.
    with pytest.raises(ValueError, match="Path-traversal"):
        # The argument is interpreted as a path component containing ../..; resolve()
        # will collapse it and the containment check should fail.
        bma.resolve_app_dir("../../escape")


# ---------- replace_slug_in_tree ----------

def test_replace_slug_in_tree_text_files(tmp_path):
    bma = _import_bma()
    # Build a small tree
    (tmp_path / "a.json").write_text('{"name": "{{APP_SLUG}}"}\n', encoding="utf-8")
    (tmp_path / "b.md").write_text("# {{APP_SLUG}}\n", encoding="utf-8")
    (tmp_path / "c.txt").write_text("no placeholder here\n", encoding="utf-8")
    # Binary file with a high byte that would crash cp1252
    (tmp_path / "icon.png").write_bytes(b"\x89PNG\r\n\x9d\x00")
    # .git dir should be skipped entirely
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]\nname = {{APP_SLUG}}\n", encoding="utf-8")

    n = bma.replace_slug_in_tree(tmp_path, "my-cool-app")
    assert n == 2  # only a.json and b.md were modified
    assert "my-cool-app" in (tmp_path / "a.json").read_text(encoding="utf-8")
    assert "my-cool-app" in (tmp_path / "b.md").read_text(encoding="utf-8")
    # .git file should be untouched
    assert "{{APP_SLUG}}" in (git_dir / "config").read_text(encoding="utf-8")
    # Binary file should still be binary, unchanged
    assert (tmp_path / "icon.png").read_bytes().startswith(b"\x89PNG")


def test_replace_slug_in_tree_binary_skipped(tmp_path):
    """Binary file with high byte 0x9d (cp1252-incompatible) must not crash."""
    bma = _import_bma()
    (tmp_path / "blob.bin").write_bytes(b"\x00\x9d\xff\xfe garbage")
    # No exception expected
    n = bma.replace_slug_in_tree(tmp_path, "any-slug")
    assert n == 0


# ---------- _rmtree_force ----------

def test_rmtree_force_handles_readonly(tmp_path):
    """Create a dir with a read-only file (simulating .git/objects/pack on Windows).
    _rmtree_force must succeed without raising."""
    bma = _import_bma()
    target = tmp_path / "victim"
    target.mkdir()
    ro_file = target / "readonly.txt"
    ro_file.write_text("locked", encoding="utf-8")
    os.chmod(ro_file, stat.S_IREAD)  # remove write permission

    bma._rmtree_force(target)
    assert not target.exists()


# ---------- registry IO ----------

def test_load_registry_default_when_missing(tmp_path, monkeypatch):
    bma = _import_bma()
    missing = tmp_path / "nope.json"
    monkeypatch.setattr(bma, "REGISTRY_PATH", missing, raising=False)
    data = bma.load_registry()
    assert data == {"schema_version": 1, "apps": []}


def test_write_registry_atomic_uses_tmp_rename(isolated_registry, monkeypatch):
    bma = _import_bma()
    data = {"schema_version": 1, "apps": [{"slug": "x", "repo_path": "/tmp/x"}]}
    bma.write_registry_atomic(data)
    # File exists, parses, content matches
    parsed = json.loads(isolated_registry.read_text(encoding="utf-8"))
    assert parsed == data
    # .tmp file is gone (renamed)
    tmp_partner = isolated_registry.with_suffix(".json.tmp")
    assert not tmp_partner.exists()


def test_find_app_returns_match_or_none(isolated_registry, sample_app_entry):
    bma = _import_bma()
    reg = {"schema_version": 1, "apps": [sample_app_entry]}
    assert bma.find_app(reg, "fixture-app") == sample_app_entry
    assert bma.find_app(reg, "no-such-app") is None
    assert bma.find_app({"apps": []}, "anything") is None
