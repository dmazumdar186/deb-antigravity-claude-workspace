"""Offline tests for jev_skill_pick (no network)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from execution.infrastructure import jev_skill_pick as P  # noqa: E402
from execution.modules import jev_client as jev  # noqa: E402

MENU = {"gmail": "email ops", "gmail-label": "label inbox", "humanizer": "rewrite text"}


def _res(choice, conf, probs):
    return jev.JevResult(answers={"skill": {"choice": choice, "confidence": conf, "probabilities": probs}},
                         cost_usd=0.0001, latency_ms=40)


def _paths(tmp_path):
    out = {}
    for n in MENU:
        d = tmp_path / n
        d.mkdir()
        (d / "SKILL.md").write_text(f"---\nname: {n}\ndescription: x\n---\nBODY-{n} " + "y" * 2000)
        out[n] = d / "SKILL.md"
    return out


def test_score_bench_math():
    rows = [{"expected": "a", "skill": "a", "top": ["a"]},
            {"expected": "b", "skill": "c", "top": ["c", "d", "b"]},
            {"expected": "none", "skill": "x", "top": ["x", "y", "z", "none"]},
            {"expected": "none", "skill": "none", "top": []}]
    s = P.score_bench(rows)
    assert s["accuracy"] == 0.5 and s["top3_accuracy"] == 0.75 and len(s["mismatches"]) == 2
    assert P.score_bench([])["accuracy"] == 0.0


def test_high_confidence_single_stage(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(P, "LEDGER", tmp_path / "l.jsonl")
    monkeypatch.setattr(jev, "decide", lambda s, q, **k: calls.append(q) or _res("gmail-label", 0.9, {"gmail-label": 0.9}))
    r = P.pick("tidy inbox", menu=MENU, paths={})
    assert r["skill"] == "gmail-label" and r["stage2"] is None and len(calls) == 1
    assert (tmp_path / "l.jsonl").read_text().count("jev_skill_pick") == 1


def test_low_confidence_two_stage(monkeypatch, tmp_path):
    paths = _paths(tmp_path)
    seen = []

    def fake(state, q, **k):
        seen.append(q["skill"]["criteria"])
        if len(seen) == 1:
            return _res("gmail", 0.4, {"gmail": 0.4, "gmail-label": 0.35, "humanizer": 0.2, "none": 0.05})
        return _res("gmail-label", 0.8, {})

    monkeypatch.setattr(P, "LEDGER", tmp_path / "l.jsonl")
    monkeypatch.setattr(jev, "decide", fake)
    r = P.pick("tidy inbox", top_k=2, menu=MENU, paths=paths)
    assert r["shortlist"] == ["gmail", "gmail-label"]
    assert set(seen[1]) == {"gmail", "gmail-label", "none"}
    assert seen[1]["gmail"].startswith("BODY-gmail") and len(seen[1]["gmail"]) == P.BODY_CHARS
    assert r["stage1_skill"] == "gmail" and r["skill"] == "gmail-label" and r["stage2"]["changed"]
    assert r["path"] == str(paths["gmail-label"])


def test_error_fails_open(monkeypatch, tmp_path):
    monkeypatch.setattr(P, "LEDGER", tmp_path / "l.jsonl")
    monkeypatch.setattr(jev, "decide", lambda s, q, **k: jev.JevResult(error="HTTP 500"))
    r = P.pick("x", menu=MENU, paths={})
    assert r["skill"] == "none" and r["error"] and r["stage2"] is None and r["path"] is None


def test_path_resolution_real_skill():
    assert P.skill_path("gmail-label") == ".claude/skills/gmail-label/SKILL.md"
    assert P.skill_path("none") is None and P.skill_path("no-such-skill") is None


def test_bench_spec_labels_exist():
    names = set(P.skill_paths())
    cases = P.load_bench()
    assert len(cases) == 20 and sum(c["expected"] == "none" for c in cases) == 3
    assert all(c["expected"] in names for c in cases if c["expected"] != "none")
