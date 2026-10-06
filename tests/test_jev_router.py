"""Offline tests for the Jev router hook (no network)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from execution.infrastructure import jev_router as R  # noqa: E402
from execution.modules import jev_client as jev  # noqa: E402


def _fake(tier, tconf, skill="none", sconf=0.0, error=None):
    def _decide(state, questions, **kw):
        if error:
            return jev.JevResult(error=error)
        return jev.JevResult(answers={
            "tier": {"type": "choice", "choice": tier, "confidence": tconf, "probabilities": {}},
            "skill": {"type": "choice", "choice": skill, "confidence": sconf, "probabilities": {}},
        }, cost_usd=0.00001, input_tokens=100, latency_ms=50)
    return _decide


def _hook(monkeypatch, tmp_path, prompt, fake, enabled=True, key="sk-or-test"):
    monkeypatch.setattr(jev, "decide", fake)
    monkeypatch.setattr(jev, "api_key", lambda: key)
    monkeypatch.setattr(R, "enabled", lambda: enabled)
    monkeypatch.setattr(R, "TMP", tmp_path)
    monkeypatch.setattr(R, "LOG_PATH", tmp_path / "log.jsonl")
    monkeypatch.setattr(R, "MENU_CACHE", tmp_path / "menu.json")
    return R.run_hook(json.dumps({"prompt": prompt, "session_id": "s"}))


def test_bulk_routes_to_sonnet_subagent(monkeypatch, tmp_path):
    out = _hook(monkeypatch, tmp_path, "find the file path where the router lives", _fake("bulk", 0.95))
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "claude-sonnet-5-5" in ctx and "sub-agent" in ctx
    assert "haiku" not in ctx.lower()


def test_standard_routes_to_opus(monkeypatch, tmp_path):
    out = _hook(monkeypatch, tmp_path, "write a directive for the new script", _fake("standard", 0.9))
    assert "claude-opus-5-5" in out


def test_hard_stays_inline_on_fable(monkeypatch, tmp_path):
    out = _hook(monkeypatch, tmp_path, "design the retry architecture for the pipeline", _fake("hard", 0.9))
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "inline" in ctx and "claude-fable-5-1" in ctx


def test_skill_match_injects_skill_and_no_blind_handoff(monkeypatch, tmp_path):
    out = _hook(monkeypatch, tmp_path, "label my gmail inbox please", _fake("bulk", 0.8, "gmail-label", 0.99))
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "`gmail-label`" in ctx and "Skill tool" in ctx
    assert "Delegate the work to ONE sub-agent" not in ctx


def test_low_confidence_defers_to_agent(monkeypatch, tmp_path):
    out = _hook(monkeypatch, tmp_path, "do the thing with the stuff somehow", _fake("standard", 0.3))
    assert "unclear" in out and "claude-opus-5-5" not in out


def test_fail_open_on_error_and_when_off(monkeypatch, tmp_path):
    assert _hook(monkeypatch, tmp_path, "anything long enough here", _fake("bulk", 0.9, error="HTTP 500")) == ""
    assert _hook(monkeypatch, tmp_path, "anything long enough here", _fake("bulk", 0.9), enabled=False) == ""
    assert _hook(monkeypatch, tmp_path, "anything long enough here", _fake("bulk", 0.9), key="") == ""


def test_slash_commands_and_short_prompts_skip(monkeypatch, tmp_path):
    assert _hook(monkeypatch, tmp_path, "/jev status", _fake("bulk", 0.9)) == ""
    assert _hook(monkeypatch, tmp_path, "ok", _fake("bulk", 0.9)) == ""


def test_config_routes_never_name_haiku():
    cfg = R.load_config()
    for route in cfg["routes"].values():
        assert "haiku" not in route["model"].lower()
    assert {cfg["routes"][t]["model"] for t in ("bulk", "standard", "hard")} == {
        "claude-sonnet-5-5", "claude-opus-5-5", "claude-fable-5-1"}


def test_skills_menu_reads_frontmatter(monkeypatch, tmp_path):
    sk = tmp_path / "skills" / "demo"
    sk.mkdir(parents=True)
    (sk / "SKILL.md").write_text("---\nname: demo\ndescription: Demo skill does X.\n---\n# body\n", encoding="utf-8")
    hidden = tmp_path / "skills" / "hidden"
    hidden.mkdir()
    (hidden / "SKILL.md").write_text("---\nname: hidden\ndescription: op only\ndisable-model-invocation: true\n---\n", encoding="utf-8")
    monkeypatch.setattr(R, "SKILLS_DIR", tmp_path / "skills")
    monkeypatch.setattr(R, "MENU_CACHE", tmp_path / "menu.json")
    monkeypatch.setattr(R, "TMP", tmp_path)
    assert R.skills_menu() == {"demo": "Demo skill does X."}
