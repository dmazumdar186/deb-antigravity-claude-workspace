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
    {"id": "1", "name": "Ann Lee", "company": "Acme", "title": "VP Sales", "email": "ann@acme.io", "website_summary": "", "phone": "555"},
    {"id": "2", "name": "Bob Roy", "company": "Beta", "title": "SDR", "email": "bob@beta.io", "website_summary": "x" * 5000},
    {"id": "3", "name": "Cy Dee", "company": "Gamma", "title": "Head RevOps", "email": "cy@g.io", "website_summary": "n"},
]

CANNED = {
    "qualify": ([
        {"icp_fit": {"score": 3}, "reach_out": {"noul": 0.9}, "persona": _ch("economic_buyer"),
         "timing_ok": {"noul": 0.9}, "enough_context": {"noul": 0.8}, "role_fit": {"noul": 0.9}, "likely_buyer": {"noul": 0.9}, "company_fit": {"noul": 0.9}, "seniority": {"score": 4}},
        {"icp_fit": {"score": 0}, "reach_out": {"noul": 0.1}, "persona": _ch("user"),
         "timing_ok": {"noul": 0.9}, "enough_context": {"noul": 0.2}, "role_fit": {"noul": 0.1}, "likely_buyer": {"noul": 0.1}, "company_fit": {"noul": 0.1}, "seniority": {"score": 0}},
        {"icp_fit": {"score": 2}, "reach_out": {"noul": 0.5}, "persona": _ch("champion"),
         "timing_ok": {"noul": 0.9}, "enough_context": {"noul": 0.8}, "role_fit": {"noul": 0.6}, "likely_buyer": {"noul": 0.5}, "company_fit": {"noul": 0.6}, "seniority": {"score": 2}},
    ], ["go", "skip", "hold"]),
    "signals": ([
        {"funding_recent": {"noul": 0.9}, "hiring_outbound": {"noul": 0.1}, "new_budget_owner": {"noul": 0.1},
         "current_role_buys": {"noul": 0.1}, "signal_strength": {"score": 3}},
        {"funding_recent": {"noul": 0.1}, "hiring_outbound": {"noul": 0.1}, "new_budget_owner": {"noul": 0.1},
         "current_role_buys": {"noul": 0.1}, "signal_strength": {"score": 1}},
        {"funding_recent": {"noul": 0.1}, "hiring_outbound": {"noul": 0.1}, "new_budget_owner": {"noul": 0.1},
         "current_role_buys": {"noul": 0.1}, "signal_strength": {"score": 0}},
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
         "remove_request": {"noul": 0.0}},
        {"intent": _ch("unsubscribe"), "sentiment": {"score": 0}, "needs_human": {"noul": 0.1},
         "remove_request": {"noul": 0.95}},
        {"intent": _ch("question", 0.3), "sentiment": {"score": 1}, "needs_human": {"noul": 0.9},
         "remove_request": {"noul": 0.0}},
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
    rc = jev_leads.main([scenario, "--input", str(inp), "--output", str(out),
                         "--cache", str(tmp_path / "cache.json"), *extra])
    return rc, (json.loads(out.read_text()) if out.exists() else None)


@pytest.mark.parametrize("scenario", list(CANNED))
def test_scenarios(tmp_path, patched, scenario):
    answers, expected = CANNED[scenario]
    patched["answers"] = answers
    rc, data = _run(tmp_path, scenario)
    assert rc == 0
    assert [r["jev_decision"] for r in data["rows"]] == expected
    assert data["summary"]["rows"] == 3 and data["validation"] is None
    if scenario in ("qualify", "signals", "suppress"):
        lead = patched["states"][1]["lead"]
        assert len(lead["website_summary"]) == 1200 and "website_summary" not in patched["states"][0]["lead"]
        assert "phone" not in patched["states"][0]["lead"]


def test_diff(tmp_path, patched):
    snap = _write_csv(tmp_path / "snap.csv", [
        {"email": "ann@acme.io", "name": "Ann Lee", "company": "Acme", "title": "Director Sales"},
        {"email": "bob@beta.io", "name": "Bob Roy", "company": "Beta", "title": "SDR"},
    ])
    patched["answers"] = [
        {"change_type": _ch("promotion_same_company"), "new_budget_owner": {"noul": 0.9},
         "current_role_buys": {"noul": 0.9}, "now_worth_contacting": {"noul": 0.9}},
        {"change_type": _ch("none"), "new_budget_owner": {"noul": 0.2}, "current_role_buys": {"noul": 0.9},
         "now_worth_contacting": {"noul": 0.2}},
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


def _res(answers):
    return JevResult(answers=answers, cost_usd=0.0001, model="jev")


def _qs(s):
    return jev_leads.build_questions(s, {})


def test_fields_allowlist_and_denylist(tmp_path, patched):
    patched["answers"] = CANNED["qualify"][0]
    rc, _ = _run(tmp_path, "qualify", ["--fields", "title,company,phone,email"])
    assert rc == 0
    assert set(patched["states"][0]["lead"]) == {"title", "company", "email"}
    rc, _ = _run(tmp_path, "hygiene")
    assert "email" in patched["states"][0]["lead"] and "title" in patched["states"][0]["lead"]


def test_partial_answer_flags_review():
    a = dict(CANNED["hygiene"][0][0])
    a.pop("row_usable")
    out = jev_leads.decide_row(_res(a), "hygiene", _qs("hygiene"), 0.6)
    assert out["jev_review"] is True and out["jev_error"] == "partial_answer:row_usable"


def test_hold_is_review():
    out = jev_leads.decide_row(_res(CANNED["qualify"][0][2]), "qualify", _qs("qualify"), 0.6)
    assert out["jev_decision"] == "hold" and out["jev_review"] is True


def test_fit_score_and_cutoffs():
    q = _qs("qualify")
    hi = jev_leads.decide_row(_res(CANNED["qualify"][0][0]), "qualify", q, 0.6)
    assert hi["jev_fit"] == 91 and hi["jev_decision"] == "go"
    out = jev_leads.decide_row(_res(CANNED["qualify"][0][0]), "qualify", q, 0.6, {"fit_cutoffs": {"go": 95}})
    assert out["jev_decision"] == "hold"
    # skip blocked when fit clears the hold cutoff
    a = {**CANNED["qualify"][0][1], "role_fit": {"noul": 0.9}, "likely_buyer": {"noul": 0.9},
         "company_fit": {"noul": 0.9}, "seniority": {"score": 4}}
    assert jev_leads.decide_row(_res(a), "qualify", q, 0.6)["jev_decision"] == "hold"


def test_md_sorted_by_fit(tmp_path, patched):
    patched["answers"] = [CANNED["qualify"][0][1], CANNED["qualify"][0][2], CANNED["qualify"][0][0]]
    md = tmp_path / "o.md"
    rc, _ = _run(tmp_path, "qualify", ["--md", str(md)])
    assert rc == 0
    body = [ln for ln in md.read_text().splitlines() if ln.startswith("| ") and ln[2].isdigit()]
    assert [ln.split("|")[1].strip() for ln in body] == ["3", "2", "1"]


def test_replies_remove_request_overrides():
    a = {**CANNED["replies"][0][0], "remove_request": {"noul": 0.9}}
    assert jev_leads.decide_row(_res(a), "replies", _qs("replies"), 0.6)["jev_decision"] == "unsubscribe"
    assert {"referral", "objection"} <= set(_qs("replies")["intent"]["criteria"])


def test_diff_same_job_reworded_ignored():
    q = _qs("diff")
    a = {"change_type": _ch("same_job_reworded"), "new_budget_owner": {"noul": 0.9},
         "current_role_buys": {"noul": 0.9}, "now_worth_contacting": {"noul": 0.9}}
    assert jev_leads.decide_row(_res(a), "diff", q, 0.6)["jev_decision"] == "ignore"


def test_diff_matches_any_key_and_keeps_column(tmp_path, patched):
    snap = _write_csv(tmp_path / "snap.csv", [
        {"email": "", "linkedin_url": "https://linkedin.com/in/ann/", "name": "Ann Lee", "company": "Acme",
         "title": "Director Sales"},
        {"email": "", "linkedin_url": "", "name": "bob  roy", "company": "Beta", "title": "SDR"},
    ])
    leads = [{"id": "1", "name": "Ann Lee", "company": "Acme", "title": "VP Sales",
              "linkedin_url": "https://linkedin.com/in/ann"},
             {"id": "2", "name": "Bob Roy", "company": "Beta", "title": "SDR", "linkedin_url": ""}]
    rows = jev_leads.diff_rows(leads, jev_leads.load_rows(snap))
    assert [(r["id"], r["jev_diff"]) for r in rows] == [("1", "changed")]
    patched["answers"] = [{"change_type": _ch("promotion_same_company"), "new_budget_owner": {"noul": 0.9},
                           "current_role_buys": {"noul": 0.9}, "now_worth_contacting": {"noul": 0.9}}]
    inp = tmp_path / "new.json"
    inp.write_text(json.dumps(leads))
    out_csv = tmp_path / "d.csv"
    rc = jev_leads.main(["diff", "--input", str(inp), "--snapshot", str(snap), "--output",
                         str(tmp_path / "o.json"), "--csv-out", str(out_csv), "--cache", "none"])
    assert rc == 0
    with open(out_csv, encoding="utf-8") as fh:
        assert list(csv.DictReader(fh))[0]["jev_diff"] == "changed"
    assert "linkedin_url" not in patched["states"][0]["lead"]["new"]


def test_cache_hits_and_anonymous_key(tmp_path, patched):
    patched["answers"] = CANNED["suppress"][0]
    rc, data = _run(tmp_path, "suppress")
    assert rc == 0 and data["summary"]["cache_hits"] == 0 and patched["n"] == 1
    rc, data = _run(tmp_path, "suppress")
    assert data["summary"]["cache_hits"] == 3 and data["summary"]["cost_usd"] == 0
    assert all(r["jev_cached"] for r in data["rows"]) and patched["n"] == 1
    s1 = {"lead": {"name": "A", "email": "a@x", "title": "VP", "company": "X"}}
    s2 = {"lead": {"name": "B", "email": "b@x", "title": "VP", "company": "X"}}
    assert jev_leads.cache_key(s1, "qualify") == jev_leads.cache_key(s2, "qualify")
    assert jev_leads.cache_key(s1, "hygiene") != jev_leads.cache_key(s2, "hygiene")


def test_factcheck_and_message_score(tmp_path, patched):
    q = _qs("factcheck")
    mk = lambda sup, creepy: _res({"supported": _ch(sup), "sounds_creepy": {"noul": creepy}})  # noqa: E731
    assert jev_leads.decide_row(mk("supported", 0.1), "factcheck", q, 0.6)["jev_decision"] == "send"
    assert jev_leads.decide_row(mk("unsupported", 0.1), "factcheck", q, 0.6)["jev_decision"] == "fix"
    assert jev_leads.decide_row(mk("contradicted", 0.1), "factcheck", q, 0.6)["jev_decision"] == "block"
    q = _qs("message_score")
    good = {"about_them": {"score": 3}, "pitches_first_line": {"noul": 0.1},
            "reads_as_template": {"noul": 0.1}, "clear_ask": {"noul": 0.9}}
    assert jev_leads.decide_row(_res(good), "message_score", q, 0.6)["jev_decision"] == "send"
    bad = {**good, "reads_as_template": {"noul": 0.9}}
    assert jev_leads.decide_row(_res(bad), "message_score", q, 0.6)["jev_decision"] == "revise"
    st = jev_leads.row_state({"name": "A", "draft": "Saw your raise", "news": "raised B"}, "factcheck", {})
    assert st["first_line"] == "Saw your raise" and st["source"]["news"] == "raised B"


def test_load_rows_edge_cases(tmp_path):
    bom = tmp_path / "b.csv"
    bom.write_bytes("\ufeffid,name\n1,Ann\n2,Bob,extra\n".encode("utf-8"))
    rows = jev_leads.load_rows(bom)
    assert rows[0] == {"id": "1", "name": "Ann"} and rows[1]["name"] == "Bob"
    st = jev_leads.row_state(rows[1], "qualify", {})
    assert st["lead"] == {"name": "Bob"}  # ragged extra cell (key None) is dropped
    bad = tmp_path / "d.json"
    bad.write_text(json.dumps({"items": []}))
    with pytest.raises(ValueError):
        jev_leads.load_rows(bad)
    st = jev_leads.row_state({"title": "VP", "news": {"a": 1}, "job_posts": ["SDR"], "company_size": 50},
                             "qualify", {})
    assert st["lead"]["news"] == '{"a": 1}' and st["lead"]["job_posts"] == '["SDR"]'
    assert st["lead"]["company_size"] == 50


def test_validate_zero_warns(tmp_path, patched, capsys):
    patched["answers"] = CANNED["qualify"][0]
    labels = _write_csv(tmp_path / "labels.csv", [{"id": "zzz", "label": "go"}])
    rc, data = _run(tmp_path, "qualify", ["--validate", str(labels)])
    assert rc == 0 and data["validation"]["scored"] == 0
    assert "scored 0 rows" in capsys.readouterr().err


def test_client_429_retries_once(monkeypatch):
    from execution.modules import jev_client as jc

    class R:
        def __init__(self, code):
            self.status_code, self.headers, self.text = code, {"retry-after": "30"}, "rate"

        def json(self):
            return {"answers": {"x": {"noul": 1.0}}}

    seq, sleeps = [R(429), R(200)], []
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setattr(jc.requests, "post", lambda *a, **k: seq.pop(0))
    monkeypatch.setattr(jc.time, "sleep", sleeps.append)
    assert jc.decide("s", {"x": jc.noul("q", "t", "f")}).ok and sleeps == [5.0]
    seq[:] = [R(429), R(429)]
    r = jc.decide("s", {"x": jc.noul("q", "t", "f")})
    assert not r.ok and r.error.startswith("HTTP 429") and len(sleeps) == 2
