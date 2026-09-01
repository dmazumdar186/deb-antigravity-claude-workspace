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


# ── the pre-filter must never hide a real finding ────────────────────────────

def test_negative_hint_is_a_superset_of_the_rule_vocabulary():
    """_NEGATIVE_HINT gates the expensive AST parse. If it ever stops matching
    something `negative_vocab` would flag, the rule silently goes blind on that
    word -- a guardrail that fails open. This pins the two together.
    """
    vocab_tokens = [
        "dead", "invalid", "nxdomain", "no_mx", "nomx", "null_mx", "nullmx",
        "not_found", "notfound", "bounced", "unreachable", "nonexistent",
        "does_not_exist", "doesnotexist", "undeliverable", "disposable",
    ]
    missed = [t for t in vocab_tokens if not sast._NEGATIVE_HINT.search(t)]
    assert not missed, (
        f"_NEGATIVE_HINT does not match {missed} -- the pre-filter would skip "
        f"files containing them and the rule would never fire")


def test_prefilter_does_not_suppress_a_true_positive(fake_workspace):
    """End-to-end proof the gate lets a real finding through."""
    (fake_workspace / "gated.py").write_text(BAD_TIMEOUT_TO_NO_MX, encoding="utf-8")
    findings = sast._rule_probe_failure_as_verdict()
    assert len(findings) == 1, "pre-filter swallowed a true positive"


def test_prefilter_skips_files_with_no_except(fake_workspace):
    (fake_workspace / "no_except.py").write_text(
        'STATUS = "dead"\nprint(STATUS)\n', encoding="utf-8")
    assert sast._rule_probe_failure_as_verdict() == []


# ── legacy-model-pin + haiku-banned on .claude/skills (added 2026-08-27) ─────

import subprocess


def _git_tracked_workspace(root: Path) -> None:
    """legacy-model-pin walks `git ls-files`, so the fixture needs a repo + index."""
    subprocess.run(["git", "init", "-q"], cwd=root, check=True,
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    subprocess.run(["git", "add", "-N", "."], cwd=root, check=True,
                   capture_output=True, text=True, encoding="utf-8", errors="replace")


LEGACY_PIN_SHAPES = {
    "a.py": 'DEFAULT_MODEL = "claude-sonnet-4-6"\n',
    "b.py": 'model: str = "anthropic/claude-sonnet-4.6",\n',
    "c.py": 'r = client.messages.create(model="claude-sonnet-4-20250514")\n',
    "d.py": 'model="claude-3-5-haiku-20241022",\n',
    "e.json": '{"anthropic_model": "claude-sonnet-4-6"}\n',
    "f.ts": "const MODEL = 'claude-opus-4-7';\n",
    "g.py": 'LEGACY_MODEL = "claude-sonnet-4-6"  # legacy default still used at runtime\n',
}


def test_legacy_pin_fires_on_every_known_shape(fake_workspace):
    for name, body in LEGACY_PIN_SHAPES.items():
        (fake_workspace / name).write_text(body, encoding="utf-8")
    _git_tracked_workspace(fake_workspace)
    hits = {f["file"] for f in sast._rule_legacy_model_pin()}
    assert hits == set(LEGACY_PIN_SHAPES), hits


def test_legacy_pin_ignores_pricing_rows_and_the_5_series(fake_workspace):
    (fake_workspace / "ok.py").write_text(
        'PRICING = {"claude-sonnet-4-6": {"input": 3.0}}  # historical cost lookups\n'
        'MODEL = "claude-sonnet-5"\nJUDGE_MODEL = "claude-fable-5-1"\n', encoding="utf-8")
    _git_tracked_workspace(fake_workspace)
    assert sast._rule_legacy_model_pin() == []


def test_legacy_pin_only_sees_tracked_files(fake_workspace):
    (fake_workspace / "u.py").write_text('MODEL = "claude-sonnet-4-6"\n', encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=fake_workspace, check=True,
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert sast._rule_legacy_model_pin() == []  # untracked: by design (pre-push runs post-commit)


def test_haiku_rule_scans_skills_but_not_the_rest_of_dot_claude(fake_workspace):
    skill = fake_workspace / ".claude" / "skills" / "foo" / "run.py"
    skill.parent.mkdir(parents=True)
    skill.write_text('client.messages.create(model="claude-haiku-4-5-20251001")\n', encoding="utf-8")
    other = fake_workspace / ".claude" / "watch" / "x.py"
    other.parent.mkdir(parents=True)
    other.write_text('MODEL = "claude-haiku-4-5-20251001"\n', encoding="utf-8")
    hits = {f["file"] for f in sast._rule_haiku_banned()}
    assert hits == {".claude/skills/foo/run.py"}, hits


def test_haiku_rule_catches_the_3_5_family_too(fake_workspace):
    (fake_workspace / "execution").mkdir()
    (fake_workspace / "execution" / "old.py").write_text(
        'model="claude-3-5-haiku-20241022"\n', encoding="utf-8")
    assert [f["line"] for f in sast._rule_haiku_banned()] == [1]


def test_model_guardrails_are_registered():
    assert "legacy-model-pin" in sast._NATIVE_RULES
    assert "haiku-banned" in sast._NATIVE_RULES
