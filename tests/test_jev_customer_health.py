"""Offline tests for execution/gtm_icp_filters/jev_customer_health.py (Jev is monkeypatched)."""
from __future__ import annotations

from datetime import date

import pytest

from execution.gtm_icp_filters import jev_customer_health as h
from execution.modules import jev_client
from execution.modules.jev_client import JevResult


def _res(health: str, conf: float, churn: float, exp: float = 0.1, reason: str = "none") -> JevResult:
    return JevResult(answers={
        "health": {"choice": health, "confidence": conf, "probabilities": {health: conf}},
        "churn_90d": {"noul": churn},
        "expansion": {"noul": exp},
        "reason": {"choice": reason, "confidence": 0.9},
    }, cost_usd=0.00004)


CUSTOMERS = [
    {"id": "a", "name": "A", "mrr": "100", "notes": "fine"},
    {"id": "b", "name": "B", "mrr": "$1,000", "cancel_intent": "wants out"},
    {"id": "c", "name": "C", "mrr": "500"},
    {"id": "d", "name": "D"},
]
CANNED = [
    _res("healthy", 0.95, 0.05, exp=0.8),
    _res("at_risk", 0.9, 0.7, reason="explicit_cancel_intent"),
    _res("needs_attention", 0.4, 0.5, reason="low_usage"),
    JevResult(error="HTTP 500: boom"),
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


def test_normalize_columns():
    raw = {"Customer_ID": "x1", "Company": "Acme", "MRR": "$1,250.50", "signup_date": "2026-01-06",
           "last_active": "2026-10-01", "Payment_Failed": "yes", "NPS": "7", "seats": "12", "empty": ""}
    c = h.normalize(raw, 0, today=date(2026, 10, 6))
    assert c["id"] == "x1" and c["name"] == "Acme"
    assert c["mrr"] == 1250.5 and c["nps"] == 7
    assert c["tenure_days"] == 273 and c["last_login_days"] == 5
    assert c["payment_failed"] is True
    assert c["seats"] == "12" and "empty" not in c
    assert h.normalize({}, 4)["id"] == "5"


def test_priority_math():
    assert h.priority(0.7, 1000) == 700.0
    assert h.priority(0.5, "$200") == 100.0
    assert h.priority(None, 100) == 0.0
    assert h.priority(0.5, None) == 0.0


def test_score_sort_review_and_errors(patched):
    custs = [h.normalize(c, i) for i, c in enumerate(CUSTOMERS)]
    rows = h.score_customers(custs, min_confidence=0.55)
    assert [r["id"] for r in rows] == ["b", "c", "a", "d"]
    by = {r["id"]: r for r in rows}
    assert by["b"]["priority"] == 700.0 and not by["b"]["review"]
    assert by["c"]["review"] is True
    assert by["d"]["error"] and by["d"]["review"] and by["d"]["priority"] == 0.0
    assert set(patched["questions"]) == {"health", "churn_90d", "expansion", "reason"}
    s = h.summarize(rows, 1.0)
    assert s["mrr_at_risk"] == 955.0 and s["expansion_candidates"] == ["a"]
    assert s["errors"] == 1 and s["review"] == 2


def test_md_list_order(patched, tmp_path):
    rows = h.score_customers([h.normalize(c, i) for i, c in enumerate(CUSTOMERS)])
    lines = h.reach_out_lines(rows, top=20)
    assert len(lines) == 2  # healthy and errored rows are left off
    assert lines[0].startswith("1. **B**") and "explicit_cancel_intent" in lines[0]
    assert "(review)" in lines[1]
    assert len(h.reach_out_lines(rows, top=1)) == 1
    md = tmp_path / "out.md"
    h.write_md(rows, md, 20, h.summarize(rows, 0.1))
    assert "Reach out this week" in md.read_text(encoding="utf-8")


def test_validate_accuracy(tmp_path):
    rows = [{"id": "1", "health": "healthy", "confidence": 0.9},
            {"id": "2", "health": "at_risk", "confidence": 0.6},
            {"id": "3", "health": "churning", "confidence": 0.8}]
    p = tmp_path / "labels.csv"
    p.write_text("id,health\n1,healthy\n2,needs_attention\n", encoding="utf-8")
    v = h.validate(rows, h.load_labels(p))
    assert v["scored"] == 2 and v["correct"] == 1 and v["accuracy"] == 0.5
    assert v["mismatches"][0]["id"] == "2"


def test_cli_end_to_end(patched, tmp_path, monkeypatch):
    monkeypatch.setattr(jev_client, "available", lambda: True)
    monkeypatch.setattr(jev_client, "append_ledger", lambda e, *a, **k: None)
    inp = tmp_path / "c.csv"
    inp.write_text("id,name,mrr\na,A,100\nb,B,1000\n", encoding="utf-8")
    md = tmp_path / "r.md"
    assert h.main(["--input", str(inp), "--md", str(md), "--csv-out", str(tmp_path / "o.csv")]) == 0
    assert (tmp_path / "c.csv.health.json").exists() and md.exists()


def test_dry_run_no_calls(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(jev_client, "decide_many", lambda *a, **k: pytest.fail("called Jev"))
    inp = tmp_path / "c.json"
    inp.write_text('[{"id": "a", "mrr": 5}]', encoding="utf-8")
    assert h.main(["--input", str(inp), "--dry-run"]) == 0
    assert '"customers": 1' in capsys.readouterr().out
