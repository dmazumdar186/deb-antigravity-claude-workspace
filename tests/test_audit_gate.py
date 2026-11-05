"""
test_audit_gate.py
description: Unit tests for execution/infrastructure/audit_gate.py, its hook wrapper and pre-push step.
inputs: none (temp key, ledger, transcript root and git repos; no network, no LLM).
outputs: pytest results.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "execution" / "infrastructure"))

import audit_gate as ag  # noqa: E402

SCRIPT = ROOT / "execution" / "infrastructure" / "audit_gate.py"
HOOK_SH = ROOT / ".claude" / "hooks" / "audit-gate.sh"
STEP = ROOT / ".githooks" / "pre-push.d" / "audit-gate"


@pytest.fixture(autouse=True)
def _iso(tmp_path, monkeypatch):
    monkeypatch.setenv("REDTEAM_KEY_FILE", str(tmp_path / "keys" / "hmac.key"))
    monkeypatch.setenv("REDTEAM_TRANSCRIPT_ROOT", str(tmp_path / "projects"))
    monkeypatch.setenv("AUDIT_DIR", str(tmp_path / "audits"))
    monkeypatch.setenv("AUDIT_HOOK", "1")


def git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q")
    git(r, "config", "user.email", "t@t")
    git(r, "config", "user.name", "t")
    commit(r, {"execution/a.py": "print(1)\n"})
    return r


def commit(r, files):
    for k, v in files.items():
        p = r / k
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(v)
    git(r, "add", "-A")
    git(r, "commit", "-qm", "c")
    return git(r, "rev-parse", "HEAD")


def payload(tmp_path, repo, report, agent_type="pipeline-auditor", aid="abc123", handback=True):
    d = tmp_path / "projects" / "x" / "subagents"
    d.mkdir(parents=True, exist_ok=True)
    tp = d / f"agent-{aid}.jsonl"
    content = ([{"type": "tool_use", "name": "SubagentHandback", "input": {"message": report}}]
               if handback else [{"type": "text", "text": report}])
    tp.write_text(json.dumps({"type": "assistant", "agentId": aid,
                              "message": {"role": "assistant", "id": "m1",
                                          "content": content}}) + "\n")
    return {"agent_id": aid, "agent_type": agent_type, "agent_transcript_path": str(tp),
            "cwd": str(repo)}


def run_hook(monkeypatch, p):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(p)))
    return ag.main(["subagent-hook"])


def report(verdict, sha):
    return f"## Audit Report: x\n\n**Verdict: {verdict}**\n**Audited commit: {sha}**\n"


def ledger(tmp_path):
    f = tmp_path / "audits" / "audits.jsonl"
    return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []


def test_pass_recorded_from_handback(tmp_path, repo, monkeypatch):
    sha = git(repo, "rev-parse", "HEAD")
    assert run_hook(monkeypatch, payload(tmp_path, repo, report("PASS", sha))) == 0
    rows = ledger(tmp_path)
    assert len(rows) == 1 and rows[0]["commit"] == sha
    assert rows[0]["tree_sha"] == git(repo, "rev-parse", "HEAD^{tree}")
    assert ag.check(sha, repo) == (True, [])


def test_short_sha_and_plain_text(tmp_path, repo, monkeypatch):
    sha = git(repo, "rev-parse", "HEAD")
    run_hook(monkeypatch, payload(tmp_path, repo, report("PASS", sha[:10]), handback=False))
    assert ledger(tmp_path)[0]["commit"] == sha


@pytest.mark.parametrize("v", ["WARNINGS", "FAIL"])
def test_non_pass_ignored(tmp_path, repo, monkeypatch, v):
    run_hook(monkeypatch, payload(tmp_path, repo, report(v, git(repo, "rev-parse", "HEAD"))))
    assert ledger(tmp_path) == []


def test_mixed_verdicts_ignored(tmp_path, repo, monkeypatch):
    sha = git(repo, "rev-parse", "HEAD")
    run_hook(monkeypatch, payload(tmp_path, repo, report("PASS", sha) + "Verdict: FAIL\n"))
    assert ledger(tmp_path) == []


@pytest.mark.parametrize("t", ["general-purpose", "redteam-lens", "", "pipeline-auditor-x"])
def test_only_pipeline_auditor(tmp_path, repo, monkeypatch, t):
    run_hook(monkeypatch, payload(tmp_path, repo, report("PASS", git(repo, "rev-parse", "HEAD")),
                                  agent_type=t))
    assert ledger(tmp_path) == []


def test_plugin_prefixed_auditor(tmp_path, repo, monkeypatch):
    run_hook(monkeypatch, payload(tmp_path, repo, report("PASS", git(repo, "rev-parse", "HEAD")),
                                  agent_type="plug:pipeline-auditor"))
    assert len(ledger(tmp_path)) == 1


def test_transcript_outside_root_ignored(tmp_path, repo, monkeypatch):
    p = payload(tmp_path, repo, report("PASS", git(repo, "rev-parse", "HEAD")))
    monkeypatch.setenv("REDTEAM_TRANSCRIPT_ROOT", str(tmp_path / "elsewhere"))
    run_hook(monkeypatch, p)
    assert ledger(tmp_path) == []


def test_missing_commit_or_unknown_sha(tmp_path, repo, monkeypatch):
    run_hook(monkeypatch, payload(tmp_path, repo, "**Verdict: PASS**\n"))
    run_hook(monkeypatch, payload(tmp_path, repo, report("PASS", "deadbeef" * 5)))
    assert ledger(tmp_path) == []


def test_tampered_and_unsigned_rows_ignored(tmp_path, repo, monkeypatch):
    sha = git(repo, "rev-parse", "HEAD")
    sha2 = commit(repo, {"execution/b.py": "x=2\n"})
    run_hook(monkeypatch, payload(tmp_path, repo, report("PASS", sha)))
    f = tmp_path / "audits" / "audits.jsonl"
    row = json.loads(f.read_text())
    row["commit"], row["tree_sha"] = sha2, git(repo, "rev-parse", "HEAD^{tree}")
    unsigned = {k: v for k, v in row.items() if k != "mac"}
    f.write_text(json.dumps(row) + "\n" + json.dumps(unsigned) + "\n")
    assert ag.check(sha2, repo)[0] is False


def test_exempt_followup_passes_code_change_fails(tmp_path, repo, monkeypatch):
    sha = git(repo, "rev-parse", "HEAD")
    run_hook(monkeypatch, payload(tmp_path, repo, report("PASS", sha)))
    s2 = commit(repo, {"HANDOFF.md": "h\n", "docs/reference/x.md": "d\n",
                       ".claude/notes/general.md": "n\n", ".claude/jev/state.json": "{}\n"})
    assert ag.check(s2, repo) == (True, [])
    s3 = commit(repo, {"execution/a.py": "print(2)\n", "directives/x.md": "y\n"})
    ok, bad = ag.check(s3, repo)
    assert not ok and bad == ["directives/x.md", "execution/a.py"]


def test_no_audit_lists_files(repo):
    ok, bad = ag.check("HEAD", repo)
    assert not ok and "execution/a.py" in bad


def test_cli_check_exit_codes(tmp_path, repo):
    env = dict(os.environ)
    r = subprocess.run([sys.executable, str(SCRIPT), "check", "HEAD", "--repo", str(repo)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    assert r.returncode == 1 and "execution/a.py" in r.stdout
    r = subprocess.run([sys.executable, str(SCRIPT), "check", "nope", "--repo", str(repo)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    assert r.returncode == 2


def test_hook_refuses_without_env(tmp_path, repo, monkeypatch):
    monkeypatch.delenv("AUDIT_HOOK")
    p = payload(tmp_path, repo, report("PASS", git(repo, "rev-parse", "HEAD")))
    assert run_hook(monkeypatch, p) == 2
    assert ledger(tmp_path) == []


def _sh(cmd, inp, env, cwd=None):
    return subprocess.run(cmd, input=inp, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env, cwd=cwd)


def test_wrapper_records_and_fails_open(tmp_path, repo):
    env = dict(os.environ)
    env.pop("AUDIT_HOOK", None)
    env["CLAUDE_PROJECT_DIR"] = str(ROOT)
    p = payload(tmp_path, repo, report("PASS", git(repo, "rev-parse", "HEAD")))
    r = _sh(["bash", str(HOOK_SH)], json.dumps(p), env)
    assert r.returncode == 0 and r.stdout == "" and len(ledger(tmp_path)) == 1
    r = _sh(["bash", str(HOOK_SH)], "not json{", env)
    assert r.returncode == 0 and r.stdout == ""
    env["CLAUDE_PROJECT_DIR"] = str(tmp_path / "missing")
    r = _sh(["bash", str(HOOK_SH)], json.dumps(p), env)
    assert r.returncode == 0 and r.stdout == "" and "missing" in r.stderr


def test_prepush_step_blocks_main_only(tmp_path, repo, monkeypatch):
    sha = git(repo, "rev-parse", "HEAD")
    env = dict(os.environ)
    # The step runs from the workspace root (as pre-push does); GIT_DIR points git at the temp repo.
    env["GIT_DIR"] = str(repo / ".git")
    line = f"refs/heads/x {sha} refs/heads/main {'0' * 40}\n"
    r = _sh(["sh", str(STEP), sys.executable], line, env, cwd=ROOT)
    assert r.returncode == 1 and "PUSH BLOCKED" in r.stderr
    r = _sh(["sh", str(STEP), sys.executable], line.replace("heads/main", "heads/feat"), env, ROOT)
    assert r.returncode == 0
    run_hook(monkeypatch, payload(tmp_path, repo, report("PASS", sha)))
    r = _sh(["sh", str(STEP), sys.executable], line, env, cwd=ROOT)
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("text,want", [
    ("**Verdict: PASS**", True), ("Verdict: PASS", True), ("**Verdict**: PASS", True),
    ("- **Verdict:** **PASS**", True),
    ("**Verdict: PASS / FAIL / WARNINGS**", False), ("Verdict: PASS (with warnings)", False),
    ("Verdict: FAIL\nVerdict: PASS", False), ("Verdict: PASS\nVerdict: PASS", False),
    ("Verdict: WARNINGS", False),
])
def test_verdict_strictness(text, want):
    assert (ag.parse_report(text)[0] == "PASS") is want


@pytest.mark.parametrize("line", ["**Audited commit**: abcdef1234", "**Audited commit: abcdef1234**",
                                  "Audited commit: `abcdef1234`"])
def test_commit_forms(line):
    assert ag.parse_report(line)[1] == "abcdef1234"


def test_head_lines_ignored_and_prefix_equal_shas_merge():
    full = "abcdef1234" + "0" * 30
    text = f"HEAD: 1111111111\nAudited commit: abcdef1234\n**Audited commit**: {full}\n"
    assert ag.parse_report(text)[1] == full
    assert ag.parse_report("Audited commit: abcdef1\nAudited commit: 1234567")[1] is None


def _merge_setup(tmp_path, repo, monkeypatch, conflict=False, manual=False):
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-qb", "feat")
    a = commit(repo, {"execution/a.py": "print('feat')\n" if conflict else "print(1)\n",
                      "execution/f.py": "f=1\n"})
    git(repo, "checkout", "-q", "-")
    b = commit(repo, {"execution/a.py": "print('main')\n" if conflict else "print(1)\n",
                      "execution/m.py": "m=1\n"})
    for s in (a, b):
        run_hook(monkeypatch, payload(tmp_path, repo, report("PASS", s), aid=f"a{s[:8]}"))
    if conflict:
        subprocess.run(["git", "-C", str(repo), "merge", "-q", "feat"], capture_output=True)
        commit(repo, {"execution/a.py": "print('both')\n"})
    else:
        git(repo, "merge", "-q", "--no-ff", "--no-commit", "feat")
        if manual:
            (repo / "execution" / "evil.py").write_text("x=1\n")
            git(repo, "add", "-A")
        git(repo, "commit", "-qm", "merge")
    return git(repo, "rev-parse", "HEAD"), base


def test_clean_merge_of_audited_parents_passes(tmp_path, repo, monkeypatch):
    m, _ = _merge_setup(tmp_path, repo, monkeypatch)
    assert ag.check(m, repo) == (True, [])


def test_merge_with_manual_change_denied(tmp_path, repo, monkeypatch):
    m, _ = _merge_setup(tmp_path, repo, monkeypatch, manual=True)
    assert ag.check(m, repo)[0] is False


def test_conflicted_merge_denied(tmp_path, repo, monkeypatch):
    m, _ = _merge_setup(tmp_path, repo, monkeypatch, conflict=True)
    assert ag.check(m, repo)[0] is False


def test_merge_with_unaudited_parent_denied(tmp_path, repo, monkeypatch):
    m, _ = _merge_setup(tmp_path, repo, monkeypatch)
    (tmp_path / "audits" / "audits.jsonl").write_text(
        (tmp_path / "audits" / "audits.jsonl").read_text().splitlines()[0] + "\n")
    assert ag.check(m, repo)[0] is False


def test_merge_denied_on_old_git(tmp_path, repo, monkeypatch):
    m, _ = _merge_setup(tmp_path, repo, monkeypatch)
    monkeypatch.setattr(ag, "merge_tree_supported", lambda _r: False)
    assert ag.check(m, repo)[0] is False


def test_notes_exempt_md_only():
    assert ag.is_exempt(".claude/notes/general.md")
    assert not ag.is_exempt(".claude/notes/run.py")


def test_handback_preferred_over_preamble(tmp_path, repo, monkeypatch):
    sha = git(repo, "rev-parse", "HEAD")
    p = payload(tmp_path, repo, report("PASS", sha))
    p["last_assistant_message"] = "Wrapping up the audit now."
    run_hook(monkeypatch, p)
    assert ledger(tmp_path)[0]["text_from"] == "agent_transcript_path"


def test_prepush_last_line_without_newline(tmp_path, repo):
    sha = git(repo, "rev-parse", "HEAD")
    env = dict(os.environ, GIT_DIR=str(repo / ".git"))
    r = _sh(["sh", str(STEP), sys.executable], f"refs/heads/x {sha} refs/heads/main {'0' * 40}",
            env, cwd=ROOT)
    assert r.returncode == 1 and "PUSH BLOCKED" in r.stderr


def test_prepush_fails_closed_without_python(tmp_path, repo):
    sha = git(repo, "rev-parse", "HEAD")
    env = dict(os.environ, GIT_DIR=str(repo / ".git"))
    line = f"refs/heads/x {sha} refs/heads/main {'0' * 40}\n"
    r = _sh(["sh", str(STEP), ""], line, env, cwd=ROOT)
    assert r.returncode == 1 and "fail closed" in r.stderr
    r = _sh(["sh", str(STEP), ""], line.replace("heads/main", "heads/f"), env, cwd=ROOT)
    assert r.returncode == 0


def test_full_prepush_blocks_main_when_sast_missing(tmp_path, repo):
    """The audit step runs before (and regardless of) the SAST early exits."""
    hooks = repo / ".githooks"
    (hooks / "pre-push.d").mkdir(parents=True)
    (hooks / "pre-push").write_text((ROOT / ".githooks" / "pre-push").read_text())
    (hooks / "pre-push.d" / "audit-gate").write_text(STEP.read_text())
    sha = commit(repo, {"x.txt": "1\n"})  # no workspace_sast.py, no audit_gate.py in this repo
    line = f"refs/heads/x {sha} refs/heads/main {'0' * 40}\n"
    r = _sh(["sh", str(hooks / "pre-push")], line, dict(os.environ), cwd=repo)
    assert r.returncode == 1 and "fail closed" in r.stderr
    r = _sh(["sh", str(hooks / "pre-push")], line.replace("heads/main", "heads/f"),
            dict(os.environ), cwd=repo)
    assert r.returncode == 0


def _side_audited_merges(tmp_path, repo, monkeypatch, n, main_side=True):
    base = git(repo, "rev-parse", "HEAD")
    for i in range(n):
        git(repo, "checkout", "-qb", f"s{i}", *([] if main_side else [base]))
        s = commit(repo, {f"execution/s{i}.py": f"s={i}\n"})
        git(repo, "checkout", "-q", "-")
        t = commit(repo, {f"execution/t{i}.py": f"t={i}\n"}) if main_side else s
        for c in (s, t):
            run_hook(monkeypatch, payload(tmp_path, repo, report("PASS", c), aid=f"a{c[:10]}"))
        git(repo, "merge", "-q", "--no-ff", "-m", f"m{i}", f"s{i}")
    return git(repo, "rev-parse", "HEAD")


def test_ladder_depth16_fast(tmp_path, repo, monkeypatch):
    m = _side_audited_merges(tmp_path, repo, monkeypatch, 16)
    t0 = time.monotonic()
    ag.check(m, repo)
    assert time.monotonic() - t0 < 5


def test_merge_chain_66_fast_and_bounded(tmp_path, repo, monkeypatch):
    m = _side_audited_merges(tmp_path, repo, monkeypatch, 66, main_side=False)
    t0 = time.monotonic()
    ok, bad = ag.check(m, repo)
    assert time.monotonic() - t0 < 5 and ok is False and bad


def test_budget_exhaustion_denies_with_message(tmp_path, repo, monkeypatch):
    m, _ = _merge_setup(tmp_path, repo, monkeypatch)
    monkeypatch.setattr(ag, "MAX_GIT_CALLS", 2)
    ok, bad = ag.check(m, repo)
    assert ok is False and "too complex" in bad[0]


def test_symlink_never_exempt(tmp_path, repo, monkeypatch):
    sha = git(repo, "rev-parse", "HEAD")
    run_hook(monkeypatch, payload(tmp_path, repo, report("PASS", sha)))
    (repo / "docs").mkdir()
    os.symlink("../execution/a.py", repo / "docs" / "link.md")
    s2 = commit(repo, {})
    ok, bad = ag.check(s2, repo)
    assert not ok and bad == ["docs/link.md"]
