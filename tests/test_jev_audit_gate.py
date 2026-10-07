"""Offline tests for execution/infrastructure/jev_audit_gate.py and its Stop-hook integration."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from execution.infrastructure import jev_audit_gate as gate  # noqa: E402
from execution.modules import jev_client  # noqa: E402

PASS_REPORT = ("## Anneal review\n| Severity | File:Line | Issue |\n|---|---|---|\n| LOW | a.py:3 | nit |\n"
               "Tests: `pytest` 12 passed\n**Verdict: PASS**")
FAIL_REPORT = "| HIGH | b.py:9 | missing timeout |\n**Verdict: FAIL**"


def _answers(verdict="pass", conf=0.9, evidence=2.6, scope=0.9, sc=0.9, uc=0.1, sev="low"):
    return {
        "verdict": {"choice": verdict, "confidence": conf},
        "worst_severity": {"choice": sev, "confidence": 0.9},
        "evidence": {"score": evidence},
        "scope_covered": {"noul": scope},
        "self_consistent": {"noul": sc},
        "unverified_claims": {"noul": uc},
    }


@pytest.fixture(autouse=True)
def _tmp_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "LOG_PATH", tmp_path / "log.jsonl")
    monkeypatch.setattr(gate, "LEDGER_PATH", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(gate, "CONFIG_PATH", tmp_path / "config.json")


def _stub(monkeypatch, **kw):
    err = kw.pop("error", None)
    res = jev_client.JevResult(error=err) if err else jev_client.JevResult(answers=_answers(**kw))
    calls = []

    def fake(state, questions, **_):
        calls.append((state, questions))
        return res
    monkeypatch.setattr(jev_client, "decide", fake)
    return calls


def test_accept(monkeypatch):
    calls = _stub(monkeypatch)
    r = gate.gate_report(PASS_REPORT)
    assert r.decision == "accept" and r.reasons == []
    assert set(calls[0][1]) == {"verdict", "worst_severity", "evidence", "scope_covered",
                                "self_consistent", "unverified_claims", "is_audit"}


def test_review_weak_evidence_and_hedges(monkeypatch):
    _stub(monkeypatch, evidence=0.4, uc=0.9)
    r = gate.gate_report("everything should work. Verdict: PASS")
    assert r.decision == "review"
    assert any(x.startswith("evidence=") for x in r.reasons)
    assert any(x.startswith("unverified_claims=") for x in r.reasons)


def test_scope_only_checked_with_asked_for(monkeypatch):
    calls = _stub(monkeypatch, scope=0.2)
    assert gate.gate_report(PASS_REPORT).decision == "accept"
    r = gate.gate_report(PASS_REPORT, asked_for="check timeouts and encoding")
    assert r.decision == "review" and r.reasons[0].startswith("scope_covered=")
    assert calls[-1][0]["asked_for"] == "check timeouts and encoding"


def test_reject_fail_and_inconsistent(monkeypatch):
    _stub(monkeypatch, verdict="fail", conf=0.3)
    assert gate.gate_report(FAIL_REPORT).decision == "reject"
    _stub(monkeypatch, sc=0.2)
    assert gate.gate_report(PASS_REPORT).decision == "reject"


def test_jev_error_is_review(monkeypatch):
    _stub(monkeypatch, error="HTTP 500")
    r = gate.gate_report(PASS_REPORT)
    assert r.decision == "review" and r.reasons == ["jev unavailable"]


def test_config_override(monkeypatch, tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({"audit_gate": {"min_evidence": 3.0}}), encoding="utf-8")
    _stub(monkeypatch, evidence=2.6)
    assert gate.load_cfg(tmp_path / "config.json")["min_evidence"] == 3.0
    assert gate.gate_report(PASS_REPORT).decision == "review"


def _write_transcript(path: Path) -> Path:
    evs = [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t1", "name": "Agent", "input": {"description": "anneal review"}}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": [{"type": "text", "text": PASS_REPORT}]}]}},
        {"type": "user", "message": {"content": "[Subagent hand-back] " + FAIL_REPORT}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "All done, shipped."}]}},
    ]
    path.write_text("\n".join(json.dumps(e) for e in evs) + "\n", encoding="utf-8")
    return path


def test_extract_reports(tmp_path):
    reps = gate.extract_reports(_write_transcript(tmp_path / "t.jsonl"), last=5)
    assert [r["label"] for r in reps] == ["anneal review", "hand-back"]
    assert "Verdict: PASS" in reps[0]["text"] and reps[1]["text"].startswith("| HIGH")
    assert len(gate.extract_reports(tmp_path / "t.jsonl", last=1)) == 1


def test_cli_exit_codes(monkeypatch, tmp_path, capsys):
    rp = tmp_path / "r.md"
    rp.write_text(PASS_REPORT, encoding="utf-8")
    _stub(monkeypatch)
    assert gate.main(["gate", "--report", str(rp)]) == 0
    _stub(monkeypatch, evidence=0.5)
    assert gate.main(["gate", "--report", str(rp), "--json"]) == 1
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1])["decision"] == "review"
    _stub(monkeypatch, verdict="fail")
    assert gate.main(["gate", "--report", str(rp)]) == 3
    assert gate.main(["gate"]) == 2
    assert gate.main(["gate", "--report", str(tmp_path / "missing.md")]) == 2


def test_transcript_cli_and_dry_run(monkeypatch, tmp_path, capsys):
    t = _write_transcript(tmp_path / "t.jsonl")

    def boom(*a, **k):
        raise AssertionError("dry-run must not call Jev")
    monkeypatch.setattr(jev_client, "decide", boom)
    assert gate.main(["transcript", "--path", str(t), "--dry-run"]) == 0
    assert "2 hand-back report(s)" in capsys.readouterr().out

    def by_text(state, questions, **_):
        fail = "FAIL" in state["audit_report"]
        return jev_client.JevResult(answers=_answers(verdict="fail" if fail else "pass"))
    monkeypatch.setattr(jev_client, "decide", by_text)
    assert gate.main(["transcript", "--path", str(t), "--json"]) == 3
    out = json.loads(capsys.readouterr().out)
    assert out["worst"] == "reject" and [r["decision"] for r in out["results"]] == ["accept", "reject"]


HOOK = ROOT / ".claude" / "hooks" / "verdict-table-check.sh"


@pytest.mark.skipif(shutil.which("bash") is None or shutil.which("timeout") is None, reason="needs bash")
def test_hook_appends_gate_warning(tmp_path):
    """Stub `py` on PATH: gate invocations print a fixed review JSON, everything else runs real python."""
    t = _write_transcript(tmp_path / "t.jsonl")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fixed = json.dumps({"worst": "review", "n": 2, "results": [
        {"decision": "review", "reasons": ["evidence=0.50 < 2.0"]}, {"decision": "accept", "reasons": []}]})
    stub = bindir / "py"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        f'case "$*" in *jev_audit_gate.py*) echo \'{fixed}\'; exit 1;; esac\n'
        f'exec "{sys.executable}" "$@"\n', encoding="utf-8")
    stub.chmod(0o755)
    env = {**os.environ, "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
           "CLAUDE_TRANSCRIPT_PATH": str(t)}
    out = subprocess.run(["bash", str(HOOK)], env=env, capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=30, cwd=str(ROOT))
    assert out.returncode == 0
    payload = json.loads(out.stdout)
    ctx = payload["hookSpecificOutput"]["additionalContext"]
    assert "Jev audit gate:** 1 of 2" in ctx and "evidence=0.50" in ctx
    assert "Shipped-claim detected" in ctx  # existing logic kept intact
    assert payload["hookSpecificOutput"]["hookEventName"] == "Stop"


def test_non_audit_handback_is_skipped(monkeypatch):
    from execution.modules import jev_client
    from execution.modules.jev_client import JevResult

    def decide(state, questions, **kw):
        return JevResult(answers={
            "verdict": {"choice": "pass", "confidence": 0.9},
            "worst_severity": {"choice": "none"},
            "evidence": {"score": 0.0},
            "scope_covered": {"noul": 0.2}, "self_consistent": {"noul": 0.9},
            "unverified_claims": {"noul": 0.9}, "is_audit": {"noul": 0.12},
        })
    monkeypatch.setattr(jev_client, "decide", decide)
    r = gate.gate_report("I built the feature, tests pass, nothing committed.")
    assert r.decision == "skip" and "not an audit report" in r.reasons[0]
