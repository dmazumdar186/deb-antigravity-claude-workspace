"""Offline tests for execution/gtm_icp_filters/jev_leads.py (Jev is monkeypatched)."""
from __future__ import annotations

import csv
import json

import pytest

from execution.gtm_icp_filters import jev_leads
from execution.modules.jev_client import JevResult


def _ch(v, c=0.9):
    return {"choice": v, "confidence": c, "probabilities": {v: c}}


def _write_csv(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return path


LEADS = [
    {"id": "1", "name": "Ann Lee", "company": "Acme", "title": "VP Sales", "email": "ann@acme.io", "notes": ""},
    {"id": "2", "name": "Bob Roy", "company": "Beta", "title": "SDR", "email": "bob@beta.io", "notes": "x" * 5000},
    {"id": "3", "name": "Cy Dee", "company": "Gamma", "title": "Head RevOps", "email": "cy@g.io", "notes": "n"},
]

CANNED = {
    "qualify": ([
        {"icp_fit": {"score": 3}, "reach_out": {"noul": 0.9}, "persona": _ch("economic_buyer"),
         "timing_ok": {"noul": 0.9}, "enough_context": {"noul": 0.8}},
        {"icp_fit": {"score": 0}, "reach_out": {"noul": 0.1}, "persona": _ch("user"),
         "timing_ok": {"noul": 0.9}, "enough_context": {"noul": 0.2}},
        {"icp_fit": {"score": 2}, "reach_out": {"noul": 0.5}, "persona": _ch("champion"),
         "timing_ok": {"noul": 0.9}, "enough_context": {"noul": 0.8}},
    ], ["go", "skip", "hold"]),
    "signals": ([
        {"funding_recent": {"noul": 0.9}, "hiring_outbound": {"noul": 0.1}, "job_change": {"noul": 0.1},
         "promotion_same_company": {"noul": 0.1}, "signal_strength": {"score": 3}},
        {"funding_recent": {"noul": 0.1}, "hiring_outbound": {"noul": 0.1}, "job_change": {"noul": 0.1},
         "promotion_same_company": {"noul": 0.1}, "signal_strength": {"score": 1}},
        {"funding_recent": {"noul": 0.1}, "hiring_outbound": {"noul": 0.1}, "job_change": {"noul": 0.1},
         "promotion_same_company": {"noul": 0.1}, "signal_strength": {"score": 0}},
    ], ["contact", "watch", "none"]),
    "hygiene": ([
        {q: {"noul": 0.9} for q in ("first_name_clean", "company_name_clean", "title_is_person_title",
                                    "email_looks_work", "row_usable")},
        {"first_name_clean": {"noul": 0.2}, "company_name_clean": {"noul": 0.9},
         "title_is_person_title": {"noul": 0.9}, "email_looks_work": {"noul": 0.9}, "row_usable": {"noul": 0.8}},
        {q: {"noul": 0.1} for q in ("first_name_clean", "company_name_clean", "title_is_person_title",
                                    "email_looks_work", "row_usable")},
    ], ["clean", "fix", "drop"]),
    "suppress": ([
        {"relation": _ch("customer"), "do_not_contact": {"noul": 0.2}},
        {"relation": _ch("none"), "do_not_contact": {"noul": 0.1}},
        {"relation": _ch("partner"), "do_not_contact": {"noul": 0.9}},
    ], ["suppress", "allow", "suppress"]),
    "replies": ([
        {"intent": _ch("meeting_requested"), "sentiment": {"score": 2}, "needs_human": {"noul": 0.9},
         "unsubscribe": {"noul": 0.0}},
        {"intent": _ch("unsubscribe"), "sentiment": {"score": 0}, "needs_human": {"noul": 0.1},
         "unsubscribe": {"noul": 0.95}},
        {"intent": _ch("question", 0.3), "sentiment": {"score": 1}, "needs_human": {"noul": 0.9},
         "unsubscribe": {"noul": 0.0}},
    ], ["meeting_requested", "unsubscribe", "review"]),
    "inbound": ([
        {"real_buyer": {"noul": 0.9}, "spam": {"noul": 0.0}, "competitor": {"noul": 0.0},
         "urgency": {"score": 2}, "budget_signal": {"noul": 0.8}, "route": _ch("sales")},
        {"real_buyer": {"noul": 0.1}, "spam": {"noul": 0.9}, "competitor": {"noul": 0.0},
         "urgency": {"score": 0}, "budget_signal": {"noul": 0.0}, "route": _ch("ignore")},
        {"real_buyer": {"noul": 0.6}, "spam": {"noul": 0.0}, "competitor": {"noul": 0.0},
         "urgency": {"score": 1}, "budget_signal": {"noul": 0.2}, "route": _ch("nurture")},
    ], ["sales", "ignore", "nurture"]),
}


@pytest.fixture
def patched(monkeypatch):
    calls: dict = {"n": 0}
    monkeypatch.setattr(jev_leads.jev_client, "available", lambda: True)
    monkeypatch.setattr(jev_leads.jev_client, "append_ledger", lambda *a, **k: None)

    def fake(states, questions, **kw):
        calls["n"] += 1
        calls["states"], calls["questions"] = states, questions
        return [JevResult(answers=a, cost_usd=0.0001, model="jev") for a in calls["answers"][: len(states)]]

    monkeypatch.setattr(jev_leads.jev_client, "decide_many", fake)
    return calls


def _run(tmp_path, scenario, extra=()):
    inp = _write_csv(tmp_path / "in.csv", LEADS)
    out = tmp_path / "out.json"
    rc = jev_leads.main([scenario, "--input", str(inp), "--output", str(out), *extra])
    return rc, (json.loads(out.read_text()) if out.exists() else None)


@pytest.mark.parametrize("scenario", list(CANNED))
def test_scenarios(tmp_path, patched, scenario):
    answers, expected = CANNED[scenario]
    patched["answers"] = answers
    rc, data = _run(tmp_path, scenario)
    assert rc == 0
    assert [r["jev_decision"] for r in data["rows"]] == expected
    assert data["summary"]["rows"] == 3 and data["validation"] is None
    lead = patched["states"][1]["lead"]
    assert len(lead["notes"]) == 1200 and "notes" not in patched["states"][0]["lead"]


def test_diff(tmp_path, patched):
    snap = _write_csv(tmp_path / "snap.csv", [
        {"email": "ann@acme.io", "name": "Ann Lee", "company": "Acme", "title": "Director Sales"},
        {"email": "bob@beta.io", "name": "Bob Roy", "company": "Beta", "title": "SDR"},
    ])
    patched["answers"] = [
        {"change_type": _ch("promotion_same_company"), "now_worth_contacting": {"noul": 0.9}},
        {"change_type": _ch("none"), "now_worth_contacting": {"noul": 0.2}},
    ]
    rc, data = _run(tmp_path, "diff", ["--snapshot", str(snap)])
    assert rc == 0
    assert [r["id"] for r in data["rows"]] == ["1", "3"]
    assert [r["jev_decision"] for r in data["rows"]] == ["contact", "ignore"]
    st = patched["states"][0]["lead"]
    assert st["old"]["title"] == "Director Sales" and st["new"]["title"] == "VP Sales"
    assert patched["states"][1]["lead"]["old"] is None


def test_error_row(tmp_path, monkeypatch, patched):
    monkeypatch.setattr(jev_leads.jev_client, "decide_many",
                        lambda states, q, **k: [JevResult(error="HTTP 500")] * len(states))
    rc, data = _run(tmp_path, "qualify")
    assert rc == 0
    r = data["rows"][0]
    assert r["jev_review"] is True and r["jev_error"] == "HTTP 500"
    assert data["summary"]["errors"] == 3


def test_dry_run_no_calls(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(jev_leads.jev_client, "available", lambda: False)
    monkeypatch.setattr(jev_leads.jev_client, "decide_many", lambda *a, **k: pytest.fail("called"))
    monkeypatch.setattr(jev_leads.jev_client, "append_ledger", lambda *a, **k: pytest.fail("ledger"))
    rc, data = _run(tmp_path, "qualify", ["--dry-run"])
    assert rc == 0 and data["summary"]["rows"] == 3
    assert '"questions"' in capsys.readouterr().out


def test_missing_key(tmp_path, monkeypatch):
    monkeypatch.setattr(jev_leads.jev_client, "available", lambda: False)
    rc, _ = _run(tmp_path, "qualify")
    assert rc == 2


def test_bad_input(tmp_path, patched):
    assert jev_leads.main(["qualify", "--input", str(tmp_path / "nope.csv")]) == 1


def test_validate(tmp_path, patched):
    patched["answers"] = CANNED["qualify"][0]
    labels = _write_csv(tmp_path / "labels.csv", [{"id": "1", "label": "go"}, {"id": "2", "label": "skip"},
                                                  {"id": "3", "label": "go"}])
    rc, data = _run(tmp_path, "qualify", ["--validate", str(labels)])
    assert rc == 0
    v = data["validation"]
    assert v["scored"] == 3 and v["correct"] == 2 and v["accuracy"] == pytest.approx(0.6667, abs=1e-3)
    assert v["mismatches"][0]["id"] == "3"


def test_only_pass(tmp_path, patched):
    patched["answers"] = CANNED["qualify"][0]
    out_csv = tmp_path / "pass.csv"
    rc, _ = _run(tmp_path, "qualify", ["--csv-out", str(out_csv), "--only-pass"])
    assert rc == 0
    with open(out_csv, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["id"] for r in rows] == ["1"] and "jev_decision" in rows[0] and "name" in rows[0]


def test_icp_context_compact(tmp_path, patched):
    patched["answers"] = CANNED["suppress"][0]
    icp = jev_leads.WORKSPACE / "execution/gtm_icp_filters/icp_profiles/example_b2b_saas.json"
    rc, _ = _run(tmp_path, "suppress", ["--icp", str(icp)])
    assert rc == 0
    assert set(patched["states"][0]["context"]) == {"customers", "competitors", "exclusions"}
    assert "none" in patched["questions"]["relation"]["criteria"]
