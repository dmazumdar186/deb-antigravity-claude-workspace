"""True-positive regression tests for the workspace-native SAST rules added 2026-08-26.

A guardrail that has only ever been shown NOT to fire on good code is unverified:
"no findings" is equally consistent with "the rule is broken". These build a
synthetic workspace containing the exact bug each rule exists to catch, and assert
the rule finds it -- and that it leaves the correct form alone.

Run: py -3.14 -m pytest tests/test_workspace_sast_rules.py -q
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SAST_PATH = ROOT / "execution" / "infrastructure" / "workspace_sast.py"

_spec = importlib.util.spec_from_file_location("workspace_sast", SAST_PATH)
sast = importlib.util.module_from_spec(_spec)
sys.modules["workspace_sast"] = sast
_spec.loader.exec_module(sast)


@pytest.fixture
def fake_workspace(monkeypatch, tmp_path):
    """Point the rules at an isolated tree instead of the real repo."""
    monkeypatch.setattr(sast, "WORKSPACE_ROOT", tmp_path)
    return tmp_path


# ── probe-failure-as-verdict ─────────────────────────────────────────────────

BAD_TIMEOUT_TO_NO_MX = '''
import dns.resolver

def screen(domain):
    try:
        return "OK"
    except dns.resolver.LifetimeTimeout:
        return "NO_MX"
'''

BAD_BROAD_CATCH_TO_DEAD = '''
def check(host):
    try:
        return probe(host)
    except Exception:
        verdict = "dead"
        return verdict
'''

BAD_CONNECTION_ERROR_TO_NOT_FOUND = '''
import requests

def lookup(url):
    try:
        return requests.get(url).json()
    except ConnectionError:
        return "not_found"
'''

GOOD_ERROR_PREFIXED = '''
import dns.resolver

def screen(domain):
    try:
        return "OK"
    except dns.resolver.LifetimeTimeout:
        return "ERROR_TIMEOUT"
    except dns.resolver.NoNameservers:
        return "ERROR_SERVFAIL"
    except Exception:
        return "UNKNOWN"
'''

GOOD_AUTHORITATIVE_NEGATIVE = '''
import dns.resolver

def screen(domain):
    try:
        return "OK"
    except dns.resolver.NXDOMAIN:
        return "NXDOMAIN"
    except dns.resolver.NoAnswer:
        return "NO_MX"
'''


@pytest.mark.parametrize("name,source", [
    ("timeout_to_no_mx.py", BAD_TIMEOUT_TO_NO_MX),
    ("broad_catch_to_dead.py", BAD_BROAD_CATCH_TO_DEAD),
    ("conn_error_to_not_found.py", BAD_CONNECTION_ERROR_TO_NOT_FOUND),
])
def test_probe_rule_fires_on_true_positive(fake_workspace, name, source):
    (fake_workspace / name).write_text(source, encoding="utf-8")
    findings = sast._rule_probe_failure_as_verdict()
    assert len(findings) == 1, f"expected 1 finding in {name}, got {findings}"
    assert findings[0]["rule_id"] == "probe-failure-as-verdict"
    assert findings[0]["severity"] == "high"
    assert findings[0]["file"].endswith(name)


@pytest.mark.parametrize("name,source", [
    ("error_prefixed.py", GOOD_ERROR_PREFIXED),
    ("authoritative.py", GOOD_AUTHORITATIVE_NEGATIVE),
])
def test_probe_rule_silent_on_correct_code(fake_workspace, name, source):
    (fake_workspace / name).write_text(source, encoding="utf-8")
    assert sast._rule_probe_failure_as_verdict() == []


def test_probe_rule_does_not_flag_generic_status_words(fake_workspace):
    """A test harness printing FAIL from an except block is not this bug.
    This carve-out is why the rule can run at `high` without wedging pre-push."""
    (fake_workspace / "harness.py").write_text(
        'def run():\n'
        '    try:\n'
        '        go()\n'
        '    except Exception:\n'
        '        status = "FAIL"\n'
        '        return status\n',
        encoding="utf-8",
    )
    assert sast._rule_probe_failure_as_verdict() == []


def test_probe_rule_flags_the_shipped_guard_if_it_regressed(fake_workspace):
    """Guard against the specific regression: someone adds ERROR_TIMEOUT to the
    deletion set by renaming it to a negative verdict."""
    (fake_workspace / "regressed_guard.py").write_text(
        'import dns.resolver\n'
        'def classify(d):\n'
        '    try:\n'
        '        return "OK"\n'
        '    except dns.resolver.LifetimeTimeout:\n'
        '        return "NXDOMAIN"\n',
        encoding="utf-8",
    )
    findings = sast._rule_probe_failure_as_verdict()
    assert len(findings) == 1
    assert "NXDOMAIN" in findings[0]["message"]


# ── py-launcher-shebang ──────────────────────────────────────────────────────

def test_shebang_rule_fires_on_bare_python(fake_workspace):
    (fake_workspace / "bare.py").write_text(
        "#!/usr/bin/env python\nprint('hi')\n", encoding="utf-8")
    findings = sast._rule_py_launcher_shebang()
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "py-launcher-shebang"
    assert findings[0]["line"] == 1


def test_shebang_rule_silent_on_version_pinned(fake_workspace):
    (fake_workspace / "pinned.py").write_text(
        "#!/usr/bin/env python3.14\nprint('hi')\n", encoding="utf-8")
    assert sast._rule_py_launcher_shebang() == []


def test_shebang_rule_silent_on_no_shebang(fake_workspace):
    (fake_workspace / "clean.py").write_text("print('hi')\n", encoding="utf-8")
    assert sast._rule_py_launcher_shebang() == []


# ── registration ─────────────────────────────────────────────────────────────

def test_both_rules_are_registered():
    assert "probe-failure-as-verdict" in sast._NATIVE_RULES
    assert "py-launcher-shebang" in sast._NATIVE_RULES


def test_shipped_guard_is_clean_under_the_probe_rule():
    """The rule's origin artifact must itself pass."""
    findings = [f for f in sast._rule_probe_failure_as_verdict()
                if "instantly_guard" in f["file"]]
    assert findings == []
