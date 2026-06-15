"""Regression tests for the four workspace_sast.py native rules.

Each rule gets fixture-driven positive (should flag) and negative (should NOT
flag) cases. Tests use monkeypatch.setattr to redirect WORKSPACE_ROOT at a
tmp fixture tree per rule.

Rules covered:
  - exit-criteria-missing
  - subprocess-encoding
  - haiku-banned
  - environ-copy
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# Load the SAST module by file path (it lives in execution/, not on sys.path).
_HERE = Path(__file__).resolve().parent
_WORKSPACE = _HERE.parent
_SAST_PATH = _WORKSPACE / "execution" / "infrastructure" / "workspace_sast.py"
_spec = importlib.util.spec_from_file_location("workspace_sast", _SAST_PATH)
sast = importlib.util.module_from_spec(_spec)
sys.modules["workspace_sast"] = sast
_spec.loader.exec_module(sast)


@pytest.fixture
def fixture_root(tmp_path, monkeypatch):
    """Redirect WORKSPACE_ROOT at tmp_path for one test."""
    monkeypatch.setattr(sast, "WORKSPACE_ROOT", tmp_path)
    return tmp_path


# -------------------------------------------------------------------------
# exit-criteria-missing
# -------------------------------------------------------------------------

def _make_directive(root: Path, name: str, body: str) -> Path:
    d = root / "directives" / "personal_workflows"
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(body, encoding="utf-8")
    return p


def test_exit_criteria_flags_missing(fixture_root):
    # 40-line directive without ## Exit Criteria
    body = "# Sample\n\n" + "\n".join(f"line {i}" for i in range(50))
    _make_directive(fixture_root, "missing.md", body)
    findings = sast._rule_exit_criteria_missing()
    rule_files = {f["file"] for f in findings if f["rule_id"] == "exit-criteria-missing"}
    assert any("missing.md" in p for p in rule_files), findings


def test_exit_criteria_accepts_present(fixture_root):
    body = "# Sample\n\n" + "\n".join(f"line {i}" for i in range(50)) + "\n\n## Exit Criteria\n- foo\n"
    _make_directive(fixture_root, "present.md", body)
    findings = sast._rule_exit_criteria_missing()
    assert all("present.md" not in f["file"] for f in findings)


def test_exit_criteria_skips_short_stub(fixture_root):
    body = "# Tiny stub\nSome paragraph only."  # < 30 lines
    _make_directive(fixture_root, "stub.md", body)
    findings = sast._rule_exit_criteria_missing()
    assert all("stub.md" not in f["file"] for f in findings)


def test_exit_criteria_skips_underscore_template(fixture_root):
    body = "# Template\n" + "\n".join(f"line {i}" for i in range(50))
    _make_directive(fixture_root, "_TEMPLATE.md", body)
    findings = sast._rule_exit_criteria_missing()
    assert all("_TEMPLATE.md" not in f["file"] for f in findings)


# -------------------------------------------------------------------------
# subprocess-encoding
# -------------------------------------------------------------------------

def _make_py(root: Path, name: str, body: str) -> Path:
    d = root / "execution" / "x"
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(body, encoding="utf-8")
    return p


def test_subprocess_encoding_flags_missing(fixture_root):
    body = 'import subprocess\nsubprocess.run(["echo"], text=True)\n'
    _make_py(fixture_root, "bad.py", body)
    findings = sast._rule_subprocess_encoding()
    flagged = {f["file"] for f in findings if f["rule_id"] == "subprocess-encoding"}
    assert any("bad.py" in p for p in flagged), findings


def test_subprocess_encoding_accepts_with_encoding(fixture_root):
    body = 'import subprocess\nsubprocess.run(["echo"], text=True, encoding="utf-8")\n'
    _make_py(fixture_root, "ok.py", body)
    findings = sast._rule_subprocess_encoding()
    assert all("ok.py" not in f["file"] for f in findings)


def test_subprocess_encoding_ignores_call_without_trigger(fixture_root):
    # No text=True / capture_output=True → no encoding requirement
    body = 'import subprocess\nsubprocess.run(["echo"])\n'
    _make_py(fixture_root, "nokw.py", body)
    findings = sast._rule_subprocess_encoding()
    assert all("nokw.py" not in f["file"] for f in findings)


def test_subprocess_encoding_handles_multiline(fixture_root):
    body = (
        "import subprocess\n"
        "subprocess.run(\n"
        "    ['echo'],\n"
        "    capture_output=True,\n"
        "    encoding='utf-8',\n"
        ")\n"
    )
    _make_py(fixture_root, "multi.py", body)
    findings = sast._rule_subprocess_encoding()
    assert all("multi.py" not in f["file"] for f in findings)


# -------------------------------------------------------------------------
# haiku-banned
# -------------------------------------------------------------------------

def test_haiku_banned_flags_active_use(fixture_root):
    body = 'MODEL = "anthropic/claude-haiku-4.5"\n'
    _make_py(fixture_root, "uses.py", body)
    findings = sast._rule_haiku_banned()
    flagged = {f["file"] for f in findings if f["rule_id"] == "haiku-banned"}
    assert any("uses.py" in p for p in flagged), findings


def test_haiku_banned_ignores_ban_marker_on_same_line(fixture_root):
    body = '"claude-haiku-4-5"  # banned per model-tier.md\n'
    _make_py(fixture_root, "marked.py", body)
    findings = sast._rule_haiku_banned()
    assert all("marked.py" not in f["file"] for f in findings)


def test_haiku_banned_ignores_ban_marker_on_previous_line(fixture_root):
    body = (
        "# Haiku 4.5 banned per model-tier.md (2026-06-14); kept for legacy lookups.\n"
        '"claude-haiku-4-5": {"input": 0.80},\n'
    )
    _make_py(fixture_root, "prev_marker.py", body)
    findings = sast._rule_haiku_banned()
    assert all("prev_marker.py" not in f["file"] for f in findings)


def test_haiku_banned_skips_am_locked_path(fixture_root):
    d = fixture_root / "execution" / "gtm_client_workflows"
    d.mkdir(parents=True)
    p = d / "accessory_masters_x.py"
    p.write_text('MODEL = "anthropic/claude-haiku-4.5"\n', encoding="utf-8")
    findings = sast._rule_haiku_banned()
    assert all("accessory_masters" not in f["file"] for f in findings)


def test_haiku_banned_skips_templates(fixture_root):
    d = fixture_root / "execution"
    d.mkdir(parents=True, exist_ok=True)
    (d / "_TEMPLATE.py").write_text('MODEL = "anthropic/claude-haiku-4.5"\n', encoding="utf-8")
    findings = sast._rule_haiku_banned()
    assert all("_TEMPLATE.py" not in f["file"] for f in findings)


# -------------------------------------------------------------------------
# environ-copy
# -------------------------------------------------------------------------

def test_environ_copy_flags_active(fixture_root):
    body = "import copy, os\nenv = copy.copy(os.environ)\n"
    _make_py(fixture_root, "envbad.py", body)
    findings = sast._rule_environ_copy()
    flagged = {f["file"] for f in findings if f["rule_id"] == "environ-copy"}
    assert any("envbad.py" in p for p in flagged), findings


def test_environ_copy_flags_deepcopy(fixture_root):
    body = "import copy, os\nenv = copy.deepcopy(os.environ)\n"
    _make_py(fixture_root, "envdeep.py", body)
    findings = sast._rule_environ_copy()
    flagged = {f["file"] for f in findings if f["rule_id"] == "environ-copy"}
    assert any("envdeep.py" in p for p in flagged), findings


def test_environ_copy_accepts_dict(fixture_root):
    body = "import os\nenv = dict(os.environ)\n"
    _make_py(fixture_root, "envok.py", body)
    findings = sast._rule_environ_copy()
    assert all("envok.py" not in f["file"] for f in findings)


def test_environ_copy_skips_comment(fixture_root):
    body = "# avoid: env = copy.copy(os.environ) — pollutes parent env\nimport os\nenv = dict(os.environ)\n"
    _make_py(fixture_root, "envcomment.py", body)
    findings = sast._rule_environ_copy()
    assert all("envcomment.py" not in f["file"] for f in findings)


def test_environ_copy_skips_am_locked(fixture_root):
    d = fixture_root / "execution" / "gtm_client_workflows"
    d.mkdir(parents=True)
    p = d / "accessory_masters_y.py"
    p.write_text("import copy, os\nenv = copy.copy(os.environ)\n", encoding="utf-8")
    findings = sast._rule_environ_copy()
    assert all("accessory_masters" not in f["file"] for f in findings)
