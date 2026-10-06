"""Offline tests for execution/crm_and_pm/jev_inquiry_triage.py (Jev is monkeypatched)."""
from __future__ import annotations

import csv
import json

import pytest

from execution.crm_and_pm import jev_inquiry_triage as t
from execution.modules import jev_client
from execution.modules.jev_client import JevResult


def _res(cat: str, conf: float, needs_human: float = 0.1, urgency: float = 1.0,
         probs: dict | None = None) -> JevResult:
    probs = probs or {cat: conf}
    return JevResult(answers={
        "category": {"choice": cat, "confidence": conf, "probabilities": probs},
        "urgency": {"score": urgency},
        "needs_human": {"noul": needs_human},
    }, cost_usd=0.00001)


INQ = [
    {"id": "1", "subject": "Charged twice", "body": "You billed me twice this month."},
    {"id": "2", "subject": "??", "body": "it doesn't work and also where is my invoice"},
    {"id": "3", "subject": "Refund now", "body": "I want my money back or I call my lawyer."},
    {"id": "4", "subject": "win prize", "body": "click here"},
]
CANNED = [
    _res("billing", 0.92, needs_human=0.1, urgency=0.3),
    _res("bug", 0.45, needs_human=0.3, probs={"bug": 0.45, "billing": 0.4}),
    _res("billing", 0.9, needs_human=0.85, urgency=2.0),
    _res("spam", 0.7, needs_human=0.05),
]


@pytest.fixture
def patched(monkeypatch):
    calls = {}

    def fake(states, questions, **kw):
        calls["states"] = states
        calls["questions"] = questions
        return CANNED[: len(states)]

    monkeypatch.setattr(jev_client, "decide_many", fake)
    return calls


def test_routing_rules(patched):
    rows = t.triage(INQ, t.DEFAULT_CATEGORIES, min_confidence=0.6)
    by_id = {r["id"]: r for r in rows}
    assert by_id["1"]["route"] == "automation" and by_id["1"]["category"] == "billing"
    assert by_id["1"]["urgency_label"] == "can wait"
    assert by_id["2"]["route"] == "human"            # low confidence
    assert by_id["3"]["route"] == "human"            # needs_human >= 0.5
    assert by_id["3"]["urgency_label"] == "blocking right now"
    assert by_id["4"]["route"] == "human"            # spam below 0.8
    assert set(patched["questions"]) == {"category", "urgency", "needs_human"}
    assert patched["questions"]["category"]["type"] == "choice"


def test_threshold_tuning(patched):
    rows = t.triage(INQ[:2], t.DEFAULT_CATEGORIES, min_confidence=0.4)
    assert rows[1]["route"] == "automation"


def test_error_result_routes_human(monkeypatch):
    monkeypatch.setattr(jev_client, "decide_many",
                        lambda states, q, **kw: [JevResult(error="HTTP 500")])
    row = t.triage(INQ[:1], t.DEFAULT_CATEGORIES)[0]
    assert row["route"] == "human" and row["error"] == "HTTP 500" and row["category"] == ""


def test_parse_categories():
    cats = t.parse_categories("billing,refund=money back requests")
    assert cats["billing"] == t.DEFAULT_CATEGORIES["billing"]
    assert cats["refund"] == "money back requests"
    assert t.parse_categories("") == t.DEFAULT_CATEGORIES


def test_validate_math(tmp_path):
    rows = [{"id": "1", "category": "billing", "confidence": 0.9},
            {"id": "2", "category": "bug", "confidence": 0.5},
            {"id": "3", "category": "spam", "confidence": 0.7},
            {"id": "9", "category": "question", "confidence": 0.8}]  # unlabelled: ignored
    labels = {"1": "billing", "2": "billing", "3": "spam"}
    v = t.validate(rows, labels)
    assert (v["scored"], v["correct"]) == (3, 2)
    assert v["accuracy"] == pytest.approx(2 / 3)
    assert v["mismatches"] == [{"id": "2", "expected": "billing", "got": "bug", "confidence": 0.5}]


def test_cli_end_to_end(patched, tmp_path):
    inp = tmp_path / "inq.json"
    inp.write_text(json.dumps(INQ), encoding="utf-8")
    labels = tmp_path / "labels.csv"
    with open(labels, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "category"])
        w.writerows([["1", "billing"], ["2", "bug"], ["3", "complaint"], ["4", "spam"]])
    csv_out = tmp_path / "out.csv"
    rc = t.main(["--input", str(inp), "--validate", str(labels), "--csv-out", str(csv_out)])
    assert rc == 0
    out = json.loads((tmp_path / "inq.json.triage.json").read_text(encoding="utf-8"))
    assert out["summary"]["count"] == 4
    assert out["summary"]["by_route"] == {"automation": 1, "human": 3}
    assert out["validation"]["accuracy"] == pytest.approx(0.75)
    assert csv_out.exists()
