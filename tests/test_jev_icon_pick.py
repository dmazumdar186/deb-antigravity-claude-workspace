"""Offline tests for execution/mobile_apps/jev_icon_pick.py (Jev is monkeypatched)."""
from __future__ import annotations

import json

from execution.mobile_apps import jev_icon_pick as m
from execution.modules import jev_client
from execution.modules.jev_client import JevResult


def _fake(prefer: str, calls: list):
    def decide(state, questions, **kw):
        opts = questions["icon"]["criteria"]
        calls.append(list(opts))
        assert len(opts) <= m.BATCH_MAX and "none" in opts
        if prefer in opts:
            probs = {prefer: 0.9, "none": 0.1}
        else:
            probs = {"none": 0.8, next(iter(opts)): 0.2}
        best = max(probs, key=probs.get)
        return JevResult(answers={"icon": {"choice": best, "confidence": probs[best],
                                           "probabilities": probs}}, cost_usd=0.0001)
    return decide


def test_single_batch(monkeypatch):
    calls: list = []
    monkeypatch.setattr(jev_client, "decide", _fake("droplet", calls))
    icons = {k: m.DEFAULT_ICONS[k] for k in list(m.DEFAULT_ICONS)[:20]}
    r = m.pick_icon("drink more water", icons)
    assert r["icon"] == "droplet" and len(calls) == 1 and r["error"] is None


def test_two_stage_over_40(monkeypatch):
    calls: list = []
    monkeypatch.setattr(jev_client, "decide", _fake("moon", calls))
    assert len(m.DEFAULT_ICONS) > 40
    r = m.pick_icon("sleep early", m.DEFAULT_ICONS)
    assert len(calls) == len(m.plan_batches(list(m.DEFAULT_ICONS))) + 1
    assert r["icon"] == "moon" and r["alternatives"][0]["icon"] == "moon"
    assert abs(r["cost"] - 0.0001 * len(calls)) < 1e-9


def test_min_confidence_gives_none(monkeypatch):
    def decide(state, questions, **kw):
        return JevResult(answers={"icon": {"choice": "smile", "confidence": 0.3,
                                           "probabilities": {"smile": 0.3, "meh": 0.25, "none": 0.45}}})
    monkeypatch.setattr(jev_client, "decide", decide)
    r = m.pick_icon("hmm", {"smile": "happy", "meh": "neutral"}, min_confidence=0.4)
    assert r["icon"] == "none"


def test_error_fails_open(monkeypatch):
    monkeypatch.setattr(jev_client, "decide", lambda *a, **k: JevResult(error="HTTP 500"))
    r = m.pick_icon("x y z", {"a": "b"})
    assert r["icon"] is None and "500" in r["error"]


def test_plan_batches():
    b = m.plan_batches([str(i) for i in range(100)])
    assert [len(x) for x in b] == [39, 39, 22]


def test_bench_math():
    rows = [{"text": "a", "expected": "x", "predicted": "x", "top": ["x"], "latency_ms": 100, "cost": 0.1},
            {"text": "b", "expected": ["y", "z"], "predicted": "q", "top": ["q", "z"], "latency_ms": 300, "cost": 0.1},
            {"text": "c", "expected": "none", "predicted": "w", "top": ["w"], "latency_ms": 200, "cost": 0.1},
            {"text": "d", "expected": "none", "predicted": "none", "top": [], "latency_ms": 0, "cost": 0.1}]
    s = m.score_bench(rows)
    assert s["accuracy"] == 0.5 and s["top3"] == 0.75 and s["mean_latency_ms"] == 150.0
    assert len(s["mismatches"]) == 2 and abs(s["cost_usd"] - 0.4) < 1e-9


def test_regex_baseline():
    assert m.regex_pick("drink more water")[0] == "droplet"
    assert m.regex_pick("asdf qwerty") == []


def test_bench_file_shape():
    data = json.loads(m.DEFAULT_BENCH.read_text(encoding="utf-8"))["cases"]
    assert len(data) == 24
    assert sum(1 for c in data if c.get("mode") == "mood") == 4
    assert sum(1 for c in data if c["expected"] == "none") == 2
    for c in data:
        for e in (c["expected"] if isinstance(c["expected"], list) else [c["expected"]]):
            assert e == "none" or e in m.DEFAULT_ICONS
