"""Offline unit tests for the pure decision logic in execution/infrastructure/instantly_copy_monitor.py."""
from __future__ import annotations

import json
import random

import pytest

from execution.infrastructure import instantly_copy_monitor as m

# ---- render ---------------------------------------------------------------------------

def test_render_nested_merge_field_inside_spintax():
    rng = random.Random(1)
    for _ in range(20):
        out = m.render("{{RANDOM | open for collaborating {{firstName}} | hi {{companyName}} team}}", rng)
        assert out in ("open for collaborating Mark", "hi Northbridge team")
        out2 = m.render("I pulled three {{location}} owner profiles {{RANDOM | for you | today}}", rng)
        assert out2 in ("I pulled three Dallas owner profiles for you", "I pulled three Dallas owner profiles today")


def test_render_merge_fields_case_sensitive_and_unknown_neutral():
    rng = random.Random(1)
    assert m.render("{{location}}/{{Location}}/{{sendingAccountFirstName}}/{{boothSize}}", rng) == "Dallas/Lyon/Deb/booth size"
    assert m.render("your {{lead_source}} and {{companyURL}}", rng) == "your lead source and company url"


def test_render_bare_spintax_and_nested_spintax():
    rng = random.Random(3)
    for _ in range(20):
        assert m.render("{{a|b}}", rng) in ("a", "b")
        assert m.render("{{RANDOM | x {{RANDOM | y | z}} | w}}", rng) in ("x y", "x z", "w")


def test_render_html_to_text():
    rng = random.Random(1)
    assert m.render("<div>Hi {{firstName}},</div><div><br /></div><div>Q&amp;A</div>", rng) == "Hi Mark,\n\nQ&A"


# ---- gate -----------------------------------------------------------------------------

def test_gate_verdict_rules():
    assert m.gate_verdict([0.6, 0.5, 0.7], [0.2, 0.3, 0.1])["pass"]
    assert not m.gate_verdict([0.5, 0.5], [0.1, 0.1])["pass"]          # mean human < 0.55
    assert not m.gate_verdict([0.9, 0.9, 0.35], [0.1, 0.1, 0.1])["pass"]  # min human < 0.40
    assert not m.gate_verdict([0.9, 0.9], [0.5, 0.4])["pass"]          # mean ai_tells > 0.40
    assert not m.gate_verdict([], [])["pass"]


def test_spearman():
    assert abs(m.spearman([1, 2, 3, 4], [10, 20, 30, 40]) - 1.0) < 1e-9
    assert abs(m.spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1.0) < 1e-9
    assert m.spearman([1, 1, 1], [1, 2, 3]) == 0.0
    assert -1.0 <= m.spearman([1, 2, 2, 3], [1, 3, 2, 4]) <= 1.0


# ---- parsing / classification -----------------------------------------------------------

def test_parse_step_key():
    assert m.parse_step_key("0_0_1") == (0, 0, 1)
    assert m.parse_step_key("0_2") is None
    assert m.parse_step_key(None) is None
    assert m.parse_step_key("a_b_c") is None


def test_effective_kind_low_conf_interested_is_other():
    assert m.effective_kind("interested", 0.45) == ("other", True)
    assert m.effective_kind("interested", 0.8) == ("interested", False)
    assert m.effective_kind("not_interested", 0.3) == ("not_interested", True)


def test_aggregate_metrics():
    rows = [{"step": "0", "variant": "0", "sent": 100}, {"step": "0", "variant": "1", "sent": 90}]
    reps = [{"step": "0_0_0", "kind": "interested"}, {"step": "0_0_1", "kind": "unsubscribe_or_complaint"},
            {"step": "0_0_1", "kind": "out_of_office"}, {"step": "0_0_1", "kind": "other"},
            {"step": "1_0_0", "kind": "interested"}, {"step": "bad", "kind": "interested"}]
    got = m.aggregate_metrics(rows, reps)
    assert got[0][0] == {"sent": 100, "positive": 1, "human": 1, "unsub": 0, "auto": 0}
    assert got[0][1] == {"sent": 90, "positive": 0, "human": 2, "unsub": 1, "auto": 1}


def test_strip_quoted():
    t = "Not interested.\n\nThanks\n\nOn Tue, Oct 6, 2026 at 12:09 PM Deb <d@x.com> wrote:\n> Hi"
    assert m.strip_quoted(t) == "Not interested.\n\nThanks"


# ---- bandit ---------------------------------------------------------------------------

def test_p_best_deterministic_and_sums_to_one():
    a = m.p_best([(10, 500), (2, 500)])
    assert a == m.p_best([(10, 500), (2, 500)])
    assert abs(sum(a) - 1.0) < 1e-9 and a[0] > 0.95
    assert m.p_best([(1, 10)]) == [1.0]


def _cells(*arms):
    return {0: {v: {"sent": s, "positive": p, "human": h, "unsub": u, "auto": 0} for v, (s, p, h, u) in enumerate(arms)}}


def test_loser_disabled_when_clear():
    d = m.decide_campaign({0: [False, False]}, _cells((500, 15, 20, 0), (500, 1, 5, 0)))
    assert d["action"]["variant"] == 1 and d["action"]["reason"] == "loser"


def test_no_loser_below_180_sent():
    d = m.decide_campaign({0: [False, False]}, _cells((500, 15, 20, 0), (179, 0, 0, 0)))
    assert d["action"] is None
    d = m.decide_campaign({0: [False, False]}, _cells((180, 15, 20, 0), (180, 0, 0, 0)))
    assert d["action"]["variant"] == 1 and d["action"]["reason"] == "loser"


def test_no_loser_when_unclear():
    d = m.decide_campaign({0: [False, False]}, _cells((500, 6, 10, 0), (500, 5, 9, 0)))
    assert d["action"] is None


def test_fallback_metric_human_minus_unsub():
    metric, arms = m.step_metric(_cells((500, 2, 10, 3), (500, 1, 1, 4))[0], [0, 1])
    assert metric == "human-unsub" and arms == [(7, 500), (0, 500)]
    metric, arms = m.step_metric(_cells((500, 4, 10, 0), (500, 1, 1, 0))[0], [0, 1])
    assert metric == "positive" and arms == [(4, 500), (1, 500)]


def test_complaints_beat_loser_and_one_action_only():
    state = {0: [False, False], 1: [False, False]}
    metrics = {0: _cells((500, 15, 20, 0), (500, 1, 5, 0))[0],
               1: _cells((250, 0, 3, 2), (250, 0, 1, 0))[0]}
    d = m.decide_campaign(state, metrics)
    assert d["action"]["reason"] == "complaints" and d["action"]["step"] == 1 and d["action"]["variant"] == 0


def test_complaints_need_150_sent():
    d = m.decide_campaign({0: [False, False]}, _cells((149, 0, 5, 5), (149, 0, 0, 0)))
    assert d["action"] is None
    d = m.decide_campaign({0: [False, False]}, _cells((150, 0, 5, 2), (150, 0, 0, 0)))
    assert d["action"]["reason"] == "complaints" and d["action"]["variant"] == 0   # 2/150 = 1.33% > 0.75%
    d = m.decide_campaign({0: [False, False]}, _cells((150, 0, 5, 1), (150, 0, 0, 0)))
    assert d["action"] is None   # 1/150 = 0.67% <= 0.75%


def test_never_disable_last_active_arm():
    d = m.decide_campaign({0: [True, False]}, _cells((500, 0, 0, 0), (500, 0, 10, 10)))
    assert d["action"] is None and d["held"]


def test_disabled_arms_ignored_for_loser():
    # Arm 0 disabled; arms 1 and 2 active, arm 2 clear loser.
    d = m.decide_campaign({0: [True, False, False]}, _cells((10, 0, 0, 0), (600, 20, 25, 0), (600, 2, 4, 0)))
    assert d["action"]["variant"] == 2
    assert (0, 0) not in d["pbest"]


def test_apply_disable_preserves_everything_else():
    seq = [{"steps": [{"type": "email", "delay": 2, "variants": [{"subject": "a", "body": "b"},
                                                                   {"subject": "c", "body": "d", "v_disabled": False}]}]}]
    new = m.apply_disable(seq, 0, 1)
    assert new[0]["steps"][0]["variants"][1]["v_disabled"] is True
    assert "v_disabled" not in seq[0]["steps"][0]["variants"][1] or seq[0]["steps"][0]["variants"][1]["v_disabled"] is False
    new[0]["steps"][0]["variants"][1]["v_disabled"] = False
    assert new == seq


def test_flag_inboxes():
    rows = [{"email_account": "a@x", "sent": 60, "bounced": 3}, {"email_account": "a@x", "sent": 60, "bounced": 3},
            {"email_account": "b@x", "sent": 99, "bounced": 20}, {"email_account": "c@x", "sent": 200, "bounced": 8}]
    flags = m.flag_inboxes(rows)
    assert [f["email"] for f in flags] == ["a@x"]


def test_unsent_arm_gets_no_p_best():
    d = m.decide_campaign({0: [False, False, False]}, _cells((282, 0, 0, 0), (187, 1, 1, 0), (0, 0, 0, 0)))
    assert (0, 2) not in d["pbest"] and (0, 0) in d["pbest"] and d["action"] is None


def test_aggregate_metrics_subtracts_baseline_sent():
    rows = [{"step": "0", "variant": "0", "sent": 500}, {"step": "0", "variant": "1", "sent": 40}]
    agg = m.aggregate_metrics(rows, [], {"0_0": 450, "0_1": 0, "2_0": 9})
    assert agg[0][0]["sent"] == 50 and agg[0][1]["sent"] == 40
    assert m.aggregate_metrics(rows, [], {"0_0": 900})[0][0]["sent"] == 0


def test_thresholds_operator_order():
    assert m.DECISION_MIN_SENT == 180 and m.COMPLAINT_MIN_SENT == 150 and m.COMPLAINT_MAX_RATE == 0.0075
    assert m.LOSER_BEST_P == 0.90 and m.LOSER_WORST_P == 0.05


# ---- family pooling ---------------------------------------------------------------------

STD = {0: {"control": 0, "B": 1, "C": 2}, 1: {"old": 0, "new": 1}, 2: {"old": 0, "new": 1}}
GB = {0: {"control": 0, "legacy": 1, "B": 2, "C": 3}, 1: {"old": 0, "legacy": 1, "new": 2}, 2: {"old": 0, "legacy": 1, "new": 2}}


def _cell(sent, pos=0, human=0, unsub=0, auto=0):
    return {"sent": sent, "positive": pos, "human": human, "unsub": unsub, "auto": auto}


def _member(cid, roles, state, step0):
    return {"campaign_id": cid, "name": cid, "roles": roles, "state": state, "metrics": {0: step0}}


def test_campaign_roles_from_config_and_fallback():
    t = {"roles": {"0": {"control": 0, "B": 1}, "1": {"old": 0, "new": 1}}}
    assert m.campaign_roles(t) == {0: {"control": 0, "B": 1}, 1: {"old": 0, "new": 1}}
    assert m.campaign_roles({}, {0: [False, False]}) == {0: {"vA": 0, "vB": 1}}


def test_pool_family_sums_by_role_incl_gb_layout():
    a = _member("a", STD, {0: [False] * 3, 1: [False] * 2, 2: [False] * 2},
                {0: _cell(100, 1, 2, 0, 1), 1: _cell(90, 2, 3, 1, 0), 2: _cell(80, 0, 1, 0, 2)})
    gb = _member("gb", GB, {0: [False, True, False, False], 1: [False, True, False], 2: [False, True, False]},
                 {0: _cell(50, 1, 1), 1: _cell(5), 2: _cell(40, 1, 1, 0, 1), 3: _cell(30, 0, 0, 1)})
    pool = m.pool_family([a, gb])
    c = pool["cells"][0]
    assert list(c) == ["control", "legacy", "B", "C"]
    assert c["control"]["sent"] == 150 and c["control"]["positive"] == 2 and c["control"]["n"] == 2
    assert c["B"]["sent"] == 130 and c["B"]["positive"] == 3 and c["B"]["auto"] == 1
    assert c["C"]["sent"] == 110 and c["C"]["unsub"] == 1 and c["C"]["auto"] == 2
    assert c["legacy"]["n"] == 1 and c["legacy"]["active"] == 0 and c["legacy"]["sent"] == 5
    assert pool["state"][0] == {"control": False, "legacy": True, "B": False, "C": False}
    assert pool["state"][1] == {"old": False, "legacy": True, "new": False}


def test_role_disabled_everywhere_is_not_an_arm():
    gb = _member("gb", GB, {0: [False, True, False, False]},
                 {0: _cell(300, 6, 8), 1: _cell(300, 0, 0), 2: _cell(300, 6, 8), 3: _cell(300, 6, 8)})
    d = m.decide_family([gb])
    assert ("legacy" not in [k for (_s, k) in d["pbest"]]) and d["action"] is None


def test_family_decision_pools_across_campaigns():
    # Per campaign C trails but each campaign alone is under 180 sent; pooled (3 x 100) it is decidable.
    st = {0: [False] * 3}
    mem = [_member(f"c{i}", STD, st, {0: _cell(100, 2, 5), 1: _cell(100, 6, 8), 2: _cell(100, 0, 1)}) for i in range(3)]
    for x in mem:
        assert m.decide_campaign(x["state"], x["metrics"])["action"] is None
    d = m.decide_family(mem)
    assert d["action"]["arm"] == "C" and d["action"]["reason"] == "loser" and d["action"]["step"] == 0
    assert [t["variant"] for t in d["plan"]["targets"]] == [2, 2, 2]


def test_family_cross_campaign_apply_uses_each_campaigns_index():
    st_std, st_gb = {0: [False] * 3}, {0: [False, True, False, False]}
    mem = [_member("std", STD, st_std, {0: _cell(200, 6, 8), 1: _cell(200, 12, 14), 2: _cell(200, 0, 1)}),
           _member("gb", GB, st_gb, {0: _cell(200, 6, 8), 1: _cell(0), 2: _cell(200, 12, 14), 3: _cell(200, 0, 1)})]
    d = m.decide_family(mem)
    assert d["action"]["arm"] == "C"
    assert {t["campaign_id"]: t["variant"] for t in d["plan"]["targets"]} == {"std": 2, "gb": 3}


def test_family_last_arm_guard_holds_campaign():
    # In campaign "solo" only C is active at step 1, so C must be held there but disabled elsewhere.
    mem = [_member("a", STD, {0: [False] * 3}, {0: _cell(200, 6, 8), 1: _cell(200, 14, 16), 2: _cell(200, 0, 1)}),
           _member("solo", STD, {0: [True, True, False]}, {0: _cell(0), 1: _cell(0), 2: _cell(200, 0, 1)})]
    d = m.decide_family(mem)
    assert [t["campaign_id"] for t in d["plan"]["targets"]] == ["a"]
    assert d["plan"]["held"] == ["solo"] and any("solo" in h for h in d["held"])


def test_family_candidate_with_no_target_is_held_not_actioned():
    mem = [_member("a", STD, {0: [False, False, True]}, {0: _cell(200, 6, 8), 1: _cell(200, 14, 16), 2: _cell(200, 0, 1)}),
           _member("solo", STD, {0: [True, True, False]}, {0: _cell(0), 1: _cell(0), 2: _cell(200, 0, 1)})]
    d = m.decide_family(mem)
    assert d["action"] is None and any("role C" in h for h in d["held"])


def test_family_one_change_per_run_complaint_first():
    st = {0: [False] * 3, 1: [False] * 2}
    metrics = {0: {0: _cell(200, 6, 8), 1: _cell(200, 6, 8), 2: _cell(200, 0, 1)},
               1: {0: _cell(200, 0, 5, 3), 1: _cell(200, 0, 1)}}
    d = m.decide_family([{"campaign_id": "a", "name": "a", "roles": STD, "state": st, "metrics": metrics}])
    assert d["action"]["reason"] == "complaints" and d["action"]["arm"] == "old" and d["action"]["step"] == 1


# ---- apply idempotency (E3 offline) -------------------------------------------------------

def test_eval_apply_idempotency_passes():
    ok, why = m.eval_apply_idempotency()
    assert ok, why


def test_apply_role_disable_minimal_patch_and_idempotent():
    seq = [{"steps": [{"variants": [{"subject": "a", "body": "x"}, {"subject": "b", "body": "y"}, {"subject": "c", "body": "z"}]}]}]
    api = m.MockInstantly({"k": {"status": 1, "sequences": seq}})
    plan = {"targets": [{"campaign_id": "k", "name": "k", "variant": 2}], "held": [], "already": []}
    out = m.apply_role_disable(api, plan, 0)
    assert out[0]["status"] == "disabled" and len(api.patches) == 1
    assert m.sequence_diff(seq, api.patches[0][1]) == [(0, "steps", 0, "variants", 2, "v_disabled")]
    out2 = m.apply_role_disable(api, plan, 0)
    assert out2[0]["status"] == "already" and len(api.patches) == 1


# ---- E1 determinism on a recorded snapshot ------------------------------------------------

def _snapshot():
    tests = [{"campaign_id": f"r{i}", "name": f"rec {i}", "family": "recruitment", "started": "2026-11-02",
              "roles": {"0": {"control": 0, "B": 1, "C": 2}, "1": {"old": 0, "new": 1}, "2": {"old": 0, "new": 1}},
              "baseline_sent": {"0_0": 50}} for i in range(2)]
    tests.append({"campaign_id": "y", "name": "yoga", "family": "yoga_fr", "started": "2026-11-02",
                  "roles": {"0": {"control": 0, "B": 1, "C": 2}}})
    tests.append({"campaign_id": "p", "name": "paused", "family": "yoga_fr", "started": "2026-11-02"})
    seq3 = [{"steps": [{"variants": [{}, {}, {}]}, {"variants": [{}, {}]}, {"variants": [{}, {}]}]}]
    rows = [{"step": str(s), "variant": str(v), "sent": n} for s, v, n in
            [(0, 0, 250), (0, 1, 200), (0, 2, 200), (1, 0, 150), (1, 1, 150), (2, 0, 10), (2, 1, 9)]]
    camps = {t["campaign_id"]: {"status": 1, "sequences": seq3, "step_rows": rows} for t in tests[:3]}
    camps["p"] = {"status": 2, "sequences": seq3}
    replies = {"r0": [{"step": "0_0_1", "kind": "interested"}, {"step": "0_0_2", "kind": "out_of_office"},
                      {"step": "0_1_1", "kind": "unsubscribe_or_complaint"}] + [{"step": "0_0_1", "kind": "interested"}] * 9,
               "r1": [{"step": "0_0_0", "kind": "not_interested"}] + [{"step": "0_0_0", "kind": "interested"}] * 2,
               "y": [], "p": []}
    return {"tests": tests, "campaigns": camps}, replies


def test_e1_compute_and_report_deterministic_on_recorded_snapshot():
    snap, replies = _snapshot()
    a, b = m.compute(snap, replies), m.compute(snap, replies)
    assert m.actions_of(a) == m.actions_of(b)
    ra, rb = m.report_body(a, live=False, detail=True), m.report_body(b, live=False, detail=True)
    assert ra == rb
    rec = a["families"]["recruitment"]["decision"]["pool"]["cells"][0]
    assert rec["control"]["sent"] == 400 and rec["B"]["positive"] == 10 and rec["C"]["auto"] == 1
    assert a["families"]["yoga_fr"]["skipped"] == ["paused (status 2)"]
    assert m.actions_of(a)[0][:4] == ("recruitment", 0, "C", "loser")
    text = "\n".join(ra)
    assert "## Family: recruitment (2 active campaigns)" in text and "| 1 | C | 2 |" in text and "Would disable step 1 role C" in text


# ---- scorecard + ledger -------------------------------------------------------------------

def test_grade_bands():
    assert [m.grade(x) for x in (1.0, 0.9, 0.89, 0.75, 0.6, 0.4, 0.39, 0.0)] == ["A", "A", "B", "B", "C", "D", "F", "F"]


def test_role_block_uplift_positive_and_human_fallback():
    cells = {"control": _cell(1000, 5, 20), "B": _cell(1000, 10, 25), "C": _cell(1000, 2, 10)}
    b = m.role_block(cells)
    assert b["uplift_metric"] == "positive" and b["best_new_role"] == "B"
    assert abs(b["best_new_vs_control_uplift"] - 1.0) < 1e-9 and b["p_new_beats_control"] > 0.85
    low = m.role_block({"control": _cell(500, 1, 10), "B": _cell(500, 1, 15), "C": _cell(500, 0, 5)})
    assert low["uplift_metric"] == "human" and low["best_new_role"] == "B" and abs(low["best_new_vs_control_uplift"] - 0.5) < 1e-9
    assert m.role_block({"control": _cell(0), "B": _cell(0)})["best_new_vs_control_uplift"] is None


def _row(date, pos_b=10, sent=1000, low=0.1, run=100.0, live=True):
    pool = {"cells": {0: {"control": _cell(sent, 5, 20, 2, 9), "B": _cell(sent, pos_b, 25, 1, 10), "C": _cell(sent, 2, 10, 0, 6)}}}
    st = m.RunStats(jev_calls=10, replies=10, low_conf=int(low * 10))
    return m.ledger_row({"recruitment": {"pool": pool, "campaigns": 8}}, run, live=live,
                        today=m.dt.date.fromisoformat(date), started=["2026-11-02"], decisions=0, stats=st)


def test_ledger_row_shape_and_scorecard_values():
    r = _row("2026-11-09")
    assert r["type"] == "monitor" and r["technical"]["days_since_start"] == 7
    assert r["families"]["recruitment"]["campaigns"] == 8 and r["overall"]["totals"]["sent"] == 3000
    v = m.scorecard_values(r, {"type": "validate", "spearman": {"human": 0.31}})
    assert v["pos_rate_best_new"] == 0.01 and v["unsub_rate"] == 3 / 3000 and v["auto_rate"] == 25 / 3000
    assert v["spearman_human"] == 0.31 and v["jev_errors"] == 0 and v["run_seconds"] == 100.0


def test_nearest_row_window():
    rows = [{"type": "monitor", "live": True, "date": d} for d in ("2026-11-01", "2026-11-02", "2026-11-03", "2026-11-05")]
    today = m.dt.date(2026, 11, 9)
    assert m.nearest_row(rows, today)["date"] == "2026-11-02"            # 7 days back
    assert m.nearest_row(rows[2:], today)["date"] == "2026-11-03"        # 6 days back
    assert m.nearest_row(rows[3:], today) is None                        # 4 days back -> n/a
    assert m.nearest_row([{"type": "validate", "date": "2026-11-02"}], today) is None
    assert m.nearest_row([{"type": "monitor", "live": True, "date": "2026-11-02", "error": "x"}], today) is None
    # Only live monitor rows are a baseline: dry runs (live false / missing) are ignored.
    assert m.nearest_row([{"type": "monitor", "live": False, "date": "2026-11-02"}], today) is None
    assert m.nearest_row([{"type": "monitor", "date": "2026-11-02"}], today) is None


def test_scorecard_lines_delta_and_grade():
    old, new = _row("2026-11-02", pos_b=8), _row("2026-11-09", pos_b=10)
    hist = [old, {"type": "validate", "date": "2026-11-02", "spearman": {"human": 0.31}}]
    lines, g = m.scorecard_lines(new, hist, m.dt.date(2026, 11, 9))
    text = "\n".join(lines)
    assert "| Positive reply rate, step 1 best new role | >= 1.00% | 1.00% | +0.20 pp | ✅ |" in text
    assert g == "A" and "9/9" in text
    lines2, _ = m.scorecard_lines(new, [], m.dt.date(2026, 11, 9))
    assert "| Human-score Spearman (latest validate) | >= +0.25 | n/a | n/a | n/a |" in "\n".join(lines2)


def test_ledger_append_and_load(tmp_path):
    p = tmp_path / "sub" / "ledger.jsonl"
    m.append_ledger({"type": "monitor", "date": "2026-11-02"}, p)
    m.append_ledger({"type": "eval", "date": "2026-11-02"}, p)
    with p.open("a", encoding="utf-8") as fh:
        fh.write("not json\n")
    rows = m.load_ledger(p)
    assert [r["type"] for r in rows] == ["monitor", "eval"] and all("ts" in r for r in rows)
    assert m.load_ledger(tmp_path / "missing.jsonl") == []


def test_label_fixture_redacted_and_short():
    import json
    import re
    rows = json.loads((m.LABEL_FIXTURE).read_text(encoding="utf-8"))
    assert len(rows) >= 50 and all(set(r) == {"kind", "preview"} for r in rows)
    kinds = set(m.Q_KIND["kind"]["criteria"])
    for r in rows:
        assert len(r["preview"]) <= 160
        assert not re.search(r"[\w.+-]+@[\w-]+\.\w", r["preview"])
        assert not re.search(r"\d{3}[ -]?\d{3}[ -]?\d{3,4}", r["preview"])
        assert r["kind"] in kinds


# ---- copy sync ----------------------------------------------------------------------------

def test_sync_to_html_matches_copy_lab_html():
    from execution.infrastructure import instantly_copy_sync as sync
    assert sync.to_html("a\n\nb\n\nc") == "<div>a</div><div><br /></div><div>b</div><div><br /></div><div>c</div>"
    assert sync.to_html("only") == "<div>only</div>"


def test_sync_wanted_uses_roles_and_drift():
    from execution.infrastructure import instantly_copy_sync as sync
    copies = {f"rec_{k}": {"id": f"rec_{k}", "subject": f"S{k}" if k.startswith("s1") else "", "body": f"{k} p1\n\n{k} p2"}
              for k in ("s1_B", "s1_C", "s2", "s3")}
    test = {"family": "rec", "roles": {"0": {"control": 0, "legacy": 1, "B": 2, "C": 3},
                                       "1": {"old": 0, "legacy": 1, "new": 2}, "2": {"old": 0, "legacy": 1, "new": 2}}}
    want = sync.wanted(test, copies)
    assert set(want) == {(0, 2), (0, 3), (1, 2), (2, 2)} and want[(0, 3)][0] == "Ss1_C"
    seq = [{"steps": [{"variants": [{"subject": "ctl", "body": "x"} for _ in range(4)]},
                      {"variants": [{} for _ in range(3)]}, {"variants": [{} for _ in range(3)]}]}]
    assert len(sync.drift(seq, want)) == 4
    fixed = sync.patched(seq, want)
    assert sync.drift(fixed, want) == [] and fixed[0]["steps"][0]["variants"][0] == {"subject": "ctl", "body": "x"}


# ---- 2026-11-02 audit fixes -----------------------------------------------------------------

class _Resp:
    def __init__(self, status, payload):
        self.status_code, self._payload, self.text = status, payload, json.dumps(payload)

    def json(self):
        return self._payload


class _Session:
    """Fake requests.Session: pops queued (status, payload) responses, records every call."""

    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def request(self, method, url, params=None, json=None, timeout=None):
        self.calls.append((method, url, dict(params or {})))
        return _Resp(*self.responses.pop(0))


def _client(responses, monkeypatch):
    monkeypatch.setattr(m, "RETRY_429_S", 0)
    monkeypatch.setattr(m, "EMAILS_GAP_S", 0)
    api = m.Instantly("k")
    api.s = _Session(responses)
    return api


# 1. analytics/steps without start_date; new-variant rows kept
def test_step_analytics_has_no_start_date_and_new_variant_rows_are_kept(monkeypatch):
    rows = [{"step": "0", "variant": "0", "sent": 96}, {"step": "0", "variant": "1", "sent": 5},
            {"step": "0", "variant": "2", "sent": 4}]
    api = _client([(200, rows)], monkeypatch)
    got = api.step_analytics("cid")
    assert "start_date" not in api.s.calls[0][2] and api.s.calls[0][2] == {"campaign_id": "cid"}
    agg = m.aggregate_metrics(got, [], {"0_0": 91})
    assert agg[0][0]["sent"] == 5 and agg[0][1]["sent"] == 5 and agg[0][2]["sent"] == 4


# 2. reply / send window: only replies to outbound sent on/after `started`
def _rep(step, ts, thread="t1"):
    return {"step": step, "timestamp_email": ts, "thread_id": thread}


def _sent(step, ts, thread="t1", camp="c"):
    return {"step": step, "ue_type": 1, "timestamp_email": ts, "thread_id": thread, "campaign_id": camp}


def test_outbound_for_latest_matching_step_before_reply():
    thread = [_sent("0_0_0", "2026-10-15T01:00:00.000Z"), _sent("0_1_0", "2026-10-20T01:00:00.000Z"),
              _sent("0_1_0", "2026-11-03T01:00:00.000Z"), _sent("0_1_0", "2026-11-09T01:00:00.000Z")]
    got = m.outbound_for(_rep("0_1_0", "2026-11-04T09:00:00.000Z"), thread)
    assert got == m.dt.datetime(2026, 11, 3, 1, tzinfo=m.dt.timezone.utc)
    assert m.outbound_for(_rep("0_2_0", "2026-11-04T09:00:00.000Z"), thread) is None


def test_attribute_replies_excludes_pre_test_sends_and_counts_unattributed():
    threads = {
        "old": [_sent("0_0_0", "2026-10-20T01:00:00.000Z", "old")],     # control send before the test
        "new": [_sent("0_0_0", "2026-11-03T01:00:00.000Z", "new")],     # control send during the test
        "none": [_sent("0_1_0", "2026-11-03T01:00:00.000Z", "none")],   # no outbound for the reply's step
    }
    looked = []

    def lookup(tid):
        looked.append(tid)
        return threads.get(tid)

    emails = [_rep("0_0_0", "2026-11-04T00:00:00Z", "old"), _rep("0_0_0", "2026-11-04T00:00:00Z", "new"),
              _rep("0_0_0", "2026-11-04T00:00:00Z", "none"), _rep("0_0_1", "2026-11-04T00:00:00Z", "x"),
              _rep(None, "2026-11-04T00:00:00Z", "y"), _rep("0_0_0", "2026-11-04T00:00:00Z", "budget-spent"),
              {"step": "0_0_0", "timestamp_email": "2026-11-04T00:00:00Z"}]
    kept, counts = m.attribute_replies(emails, "2026-11-02", {"0_0": 91, "0_1": 0}, lookup)
    assert [e["thread_id"] for e in kept] == ["new", "x"]                  # slot 0_1 has no pre-test sends: no lookup
    assert counts == {"pre_test": 1, "unattributed": 4, "budget_exhausted": 1}
    assert "x" not in looked
    # Without a baseline every reply is looked up.
    kept2, _ = m.attribute_replies([_rep("0_0_1", "2026-11-04T00:00:00Z", "new")], "2026-11-02", None, lookup)
    assert kept2 == [] and looked[-1] == "new"


def test_aggregate_after_attribution_does_not_credit_control_with_old_replies():
    rows = [{"step": "0", "variant": "0", "sent": 191}, {"step": "0", "variant": "1", "sent": 100}]
    emails = [dict(_rep("0_0_0", "2026-11-04T00:00:00Z", "old"), kind="interested"),
              dict(_rep("0_0_1", "2026-11-04T00:00:00Z", "b"), kind="interested")]
    kept, _ = m.attribute_replies(emails, "2026-11-02", {"0_0": 91},
                                  lambda tid: [_sent("0_0_0", "2026-10-20T00:00:00Z", tid)])
    agg = m.aggregate_metrics(rows, kept, {"0_0": 91})
    assert agg[0][0]["positive"] == 0 and agg[0][1]["positive"] == 1


def test_thread_sent_cached_and_budget_bounded(monkeypatch):
    monkeypatch.setattr(m, "MAX_THREAD_LOOKUPS", 2)
    api = _client([(200, {"items": [_sent("0_0_0", "2026-11-03T00:00:00Z", "a")]}), (200, {"items": []})], monkeypatch)
    assert len(api.thread_sent("a", "c", "f")) == 1 and len(api.thread_sent("a", "c", "f")) == 1   # cached: one call
    assert api.s.calls[0][2] == {"search": "thread:a", "email_type": "sent", "limit": 100, "campaign_id": "c"}
    assert api.thread_sent("b", "c", "f") == [] and api.thread_sent("x", "c", "f") is None         # budget spent
    assert len(api.s.calls) == 2


def test_thread_lookup_post_filter_discards_foreign_thread_and_campaign(monkeypatch):
    # An ignored `search` would return account-wide sends: only this thread + campaign survive.
    items = [_sent("0_0_0", "2026-11-03T00:00:00Z", "a", "c"), _sent("0_0_0", "2026-11-03T00:00:00Z", "zz", "c"),
             _sent("0_0_0", "2026-11-03T00:00:00Z", "a", "other"), {"step": "0_0_0", "ue_type": 1}]
    api = _client([(200, {"items": items})], monkeypatch)
    m.STATS.reset()
    got = api.thread_sent("a", "c", "f")
    assert got == [items[0]] and m.STATS.thread_items_foreign == 3
    # Pure path too: a lookup returning only another lead's send (pre-test) cannot attribute the reply.
    foreign = lambda tid: [_sent("0_0_0", "2026-10-20T00:00:00Z", "zz", "c")]
    kept, counts = m.attribute_replies([_rep("0_0_0", "2026-11-04T00:00:00Z", "a")], "2026-11-02", {"0_0": 9},
                                       foreign, campaign_id="c")
    assert kept == [] and counts == {"pre_test": 0, "unattributed": 1, "budget_exhausted": 0}
    other_camp = lambda tid: [_sent("0_0_0", "2026-11-03T00:00:00Z", tid, "other")]
    kept, counts = m.attribute_replies([_rep("0_0_0", "2026-11-04T00:00:00Z", "a")], "2026-11-02", {"0_0": 9},
                                       other_camp, campaign_id="c")
    assert kept == [] and counts["unattributed"] == 1


def test_thread_budget_is_per_family_and_reset_per_run(monkeypatch):
    monkeypatch.setattr(m, "MAX_THREAD_LOOKUPS", 1)
    api = _client([(200, {"items": []})] * 4, monkeypatch)
    assert api.thread_sent("a", "c1", "big") == [] and api.thread_sent("b", "c1", "big") is None   # big spent
    assert api.thread_sent("x", "c2", "small") == []                                               # own budget
    api.reset_lookup_budget()
    assert api.thread_sent("a", "c1", "big") == []          # cached: no call
    assert api.thread_sent("b", "c1", "big") == []          # fresh budget after reset
    assert len(api.s.calls) == 3


def test_fetch_snapshot_attributes_and_counts(monkeypatch):
    class Api:
        def campaign(self, cid):
            return {"status": 1, "sequences": []}

        def step_analytics(self, cid):
            return []

        def received_emails(self, cid, started):
            return [_rep("0_0_0", "2026-11-04T00:00:00Z", "old"), _rep("0_0_1", "2026-11-04T00:00:00Z", "b")]

        def thread_sent(self, tid, campaign_id=None, family=""):
            seen.append((tid, campaign_id, family))
            return [_sent("0_0_0", "2026-10-20T00:00:00Z", tid, campaign_id)]

    seen = []
    m.STATS.reset()
    snap = m.fetch_snapshot(Api(), [{"campaign_id": "c", "family": "fam", "started": "2026-11-02",
                                     "baseline_sent": {"0_0": 5}}])
    c = snap["campaigns"]["c"]
    assert [e["thread_id"] for e in c["emails"]] == ["b"]
    assert c["attribution"] == {"pre_test": 1, "unattributed": 0, "budget_exhausted": 0}
    assert m.STATS.replies_pre_test == 1 and seen == [("old", "c", "fam")]


# 3. grade needs business data and >= 7/9 measurable
def test_scorecard_grade_rule():
    assert m.scorecard_grade(5, 5, 0) == "n/a (5/9 measurable)"
    assert m.scorecard_grade(6, 6, 1) == "n/a (6/9 measurable)"
    assert m.scorecard_grade(7, 7, 0) == "n/a (7/9 measurable)"
    assert m.scorecard_grade(7, 7, 1) == "A" and m.scorecard_grade(5, 8, 2) == "C"


def test_scorecard_no_business_data_is_not_graded():
    row = _row("2026-11-09", sent=0)
    lines, g = m.scorecard_lines(row, [{"type": "validate", "date": "2026-11-02", "spearman": {"human": 0.31}}],
                                 m.dt.date(2026, 11, 9))
    assert g.startswith("n/a (") and "Grade n/a" in "\n".join(lines)


# 4. ledger hygiene
def _args(**kw):
    import argparse
    base = {"config": "cfg.json", "live": False, "detail": False, "record": False}
    base.update(kw)
    return argparse.Namespace(**base)


def _stub_monitor(monkeypatch, written, *, fail=None):
    monkeypatch.setattr(m, "load_config", lambda p: {"tests": [], "tag_ids": []})
    monkeypatch.setattr(m, "instantly_client", lambda: object())
    monkeypatch.setattr(m, "inbox_section", lambda api, tags: [])
    monkeypatch.setattr(m, "load_ledger", lambda *a: [])
    monkeypatch.setattr(m, "_write_out", lambda kind, text: None)
    monkeypatch.setattr(m, "append_ledger", lambda row, *a: written.append(row))

    def run(api, cfg, live, detail):
        if fail:
            raise fail
        return [], {"families": {}, "started": ["2026-11-02"]}
    monkeypatch.setattr(m, "run_monitor", run)


def test_monitor_appends_ledger_only_when_live(monkeypatch):
    written = []
    _stub_monitor(monkeypatch, written)
    assert m.cmd_monitor(_args(live=False)) == 0 and written == []
    assert m.cmd_monitor(_args(live=True)) == 0 and written[0]["type"] == "monitor" and written[0]["live"] is True


def test_validate_and_eval_have_record_flag():
    assert m.parse_args(["validate"]).record is False and m.parse_args(["validate", "--record"]).record is True
    assert m.parse_args(["eval"]).record is False and m.parse_args(["eval", "--record"]).record is True


def test_committed_ledger_is_scrubbed():
    rows = m.load_ledger()
    assert rows and all(r["type"] != "monitor" or r.get("live") is True for r in rows)
    assert all(r.get("record") is True for r in rows if r["type"] in ("validate", "eval"))


# 5. apply loop and monitor failure path
def test_apply_role_disable_malformed_campaign_fails_one_target_only():
    good = [{"steps": [{"variants": [{"subject": "a"}, {"subject": "b"}, {"subject": "c"}]}]}]
    api = m.MockInstantly({"bad": {"status": 1, "sequences": [{"steps": "oops"}]},
                           "bad2": {"status": 1, "sequences": [{"steps": [{"variants": 5}]}]},
                           "ok": {"status": 1, "sequences": good}})
    plan = {"targets": [{"campaign_id": c, "name": c, "variant": 2} for c in ("bad", "bad2", "ok")],
            "held": [], "already": []}
    out = m.apply_role_disable(api, plan, 0)
    assert [o["status"] for o in out] == ["failed", "failed", "disabled"]
    assert "unexpected campaign shape" in out[0]["why"] and "TypeError" in out[1]["why"]


def test_monitor_unexpected_exception_writes_technical_row_if_live_and_reraises(monkeypatch):
    written = []
    _stub_monitor(monkeypatch, written, fail=KeyError("steps"))
    with pytest.raises(KeyError):
        m.cmd_monitor(_args(live=False))
    assert written == []
    with pytest.raises(KeyError):
        m.cmd_monitor(_args(live=True))
    assert written[0]["error"].startswith("KeyError") and "technical" in written[0] and "families" not in written[0]
    assert written[0]["live"] is True and written[0]["type"] == "monitor"


# 6. sync
def _sync():
    from execution.infrastructure import instantly_copy_sync as sync
    return sync


def test_sync_to_html_strips_outer_whitespace():
    sync = _sync()
    assert sync.to_html("\n\nHi\n\nBye\n\n") == sync.to_html("Hi\n\nBye") == "<div>Hi</div><div><br /></div><div>Bye</div>"


def test_sync_to_html_escapes_and_line_breaks():
    sync = _sync()
    assert sync.to_html("Q&A <b>\nline 2\n\nnext") == "<div>Q&amp;A &lt;b&gt;<br />line 2</div><div><br /></div><div>next</div>"
    assert sync.to_html("« Bonjour » l'été \"x\"") == "<div>« Bonjour » l'été \"x\"</div>"


def test_sync_live_copy_has_no_escapable_chars():
    # The committed copy converts identically before/after the escape fix (11/11 in sync stays true).
    for c in json.loads(m.DEFAULT_COPY.read_text(encoding="utf-8")):
        body = c.get("body") or ""
        assert not any(ch in body for ch in "&<>")
        assert "\n" not in body.replace("\n\n", "")


STD_ROLES = {"0": {"control": 0, "B": 1, "C": 2}, "1": {"old": 0, "new": 1}, "2": {"old": 0, "new": 1}}


def _copies():
    return {f"rec_{k}": {"id": f"rec_{k}", "subject": "S", "body": "b"} for k in ("s1_B", "s1_C", "s2", "s3")}


def _seq3():
    return [{"steps": [{"delay": 2, "variants": [{"subject": "x", "body": "y"} for _ in range(3)]},
                       {"delay": 3, "variants": [{} for _ in range(2)]}, {"delay": 4, "variants": [{} for _ in range(2)]}]}]


def test_sync_skips_inactive_and_reports_config_errors():
    sync = _sync()
    api = m.MockInstantly({"paused": {"status": 2, "sequences": _seq3()}, "live": {"status": 1, "sequences": _seq3()},
                           "short": {"status": 1, "sequences": [{"steps": [{"variants": [{}]}]}]}})
    line, ok = sync.sync_one(api, {"campaign_id": "paused", "name": "P", "family": "rec", "roles": STD_ROLES}, _copies(), False)
    assert ok and line.startswith("skipped  P (status 2)")
    line, ok = sync.sync_one(api, {"campaign_id": "live", "name": "N", "family": "rec"}, _copies(), False)
    assert not ok and "no `roles`" in line
    line, ok = sync.sync_one(api, {"campaign_id": "live", "name": "N", "family": "zzz", "roles": STD_ROLES}, _copies(), False)
    assert not ok and "no id 'zzz_s1_B'" in line
    line, ok = sync.sync_one(api, {"campaign_id": "short", "name": "S", "family": "rec", "roles": STD_ROLES}, _copies(), False)
    assert not ok and "lacks a wanted slot" in line
    line, ok = sync.sync_one(api, {"campaign_id": "live", "name": "N", "family": "rec", "roles": STD_ROLES}, _copies(), True)
    assert ok and line.startswith("updated  N") and len(api.patches) == 1


def test_sync_untouched_checks_step_level_fields():
    sync = _sync()
    want = {(0, 1): ("S", "b"), (0, 2): ("S", "b"), (1, 1): ("S", "b"), (2, 1): ("S", "b")}
    before = _seq3()
    after = sync.patched(before, want)
    assert sync.untouched(before, after, want)
    after[0]["steps"][1]["delay"] = 9
    assert not sync.untouched(before, after, want)
    after2 = sync.patched(before, want)
    after2[0]["steps"][0]["variants"][0]["subject"] = "changed control"
    assert not sync.untouched(before, after2, want)


# 7. paging guards and 5xx retry
def test_received_emails_stops_on_repeating_cursor(monkeypatch):
    page = (200, {"items": [{"ue_type": 2, "timestamp_email": "2026-11-03T00:00:00Z"}], "next_starting_after": "same"})
    api = _client([page] * 5, monkeypatch)
    out = api.received_emails("c", "2026-11-02")
    assert len(api.s.calls) == 2 and len(out) == 2


def test_received_emails_page_cap(monkeypatch):
    monkeypatch.setattr(m, "MAX_PAGES", 3)
    pages = [(200, {"items": [{"ue_type": 2, "timestamp_email": "2026-11-03"}], "next_starting_after": f"c{i}"})
             for i in range(10)]
    api = _client(pages, monkeypatch)
    api.received_emails("c", "2026-11-02")
    assert len(api.s.calls) == 3


def test_req_retries_5xx_then_succeeds_and_bounds_retries(monkeypatch):
    m.STATS.reset()
    api = _client([(502, {}), (503, {}), (200, {"ok": 1})], monkeypatch)
    assert api.get("/x") == {"ok": 1} and m.STATS.api_retries == 2
    api = _client([(500, {})] * 5, monkeypatch)
    with pytest.raises(m.ApiError):
        api.get("/x")
    assert len(api.s.calls) == m.MAX_429_RETRIES + 1
    api = _client([(404, {})], monkeypatch)
    with pytest.raises(m.ApiError):
        api.get("/x")
    assert len(api.s.calls) == 1


# 8. malformed config JSON -> exit 2, no traceback
def test_malformed_config_exits_2(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert m.main(["--config", str(bad), "monitor"]) == 2
    assert "Config error" in capsys.readouterr().err
    assert _sync().main(["--config", str(bad)]) == 2
    assert "Config error" in capsys.readouterr().err
    assert _sync().main(["--config", str(m.DEFAULT_CONFIG), "--copy", str(bad)]) == 2


# 9. missing baseline_sent -> warning in the family section
def test_missing_baseline_warns_in_family_section():
    snap, replies = _snapshot()
    snap["tests"][2].pop("baseline_sent", None)
    text = "\n".join(m.report_body(m.compute(snap, replies), live=False))
    fam = text.split("## Family: yoga_fr")[1]
    assert "- Warning: yoga: no baseline_sent, sends are lifetime totals" in fam
    assert "Warning" not in text.split("## Family: yoga_fr")[0]


def test_unattributed_count_reported_per_family():
    snap, replies = _snapshot()
    snap["campaigns"]["r0"]["attribution"] = {"pre_test": 2, "unattributed": 3}
    text = "\n".join(m.report_body(m.compute(snap, replies), live=False))
    assert "Unattributed replies (excluded from counts): 3" in text.split("## Family: yoga_fr")[0]


# 10. overall block labelled
def test_overall_block_labelled_cross_family():
    r = _row("2026-11-09")
    assert r["overall"]["label"] == "cross-family (reporting only)"
    assert "replies_unattributed" in r["technical"] and "replies_pre_test" in r["technical"]


# 11. attribution guard: incomplete attribution holds every loser and base-role complaint decision
def _guard_members(c_unsub=0, ctrl_unsub=0):
    state = {0: [False, False, False]}
    cells = {0: {0: {"sent": 300, "positive": 6, "human": 10, "unsub": ctrl_unsub, "auto": 3},
                 1: {"sent": 300, "positive": 12, "human": 15, "unsub": 0, "auto": 3},
                 2: {"sent": 300, "positive": 0, "human": 2, "unsub": c_unsub, "auto": 3}}}
    roles = {0: {"control": 0, "B": 1, "C": 2}}
    return [{"campaign_id": f"c{i}", "name": f"c{i}", "roles": roles, "state": state, "metrics": cells} for i in range(2)]


def test_unattributed_holds_every_loser_action():
    assert m.decide_family(_guard_members())["action"]["arm"] == "C"            # baseline: C loses
    d = m.decide_family(_guard_members(), unattributed=1)
    assert d["action"] is None and d["plan"] is None
    assert any("role C (loser): attribution incomplete (1 unattributed)" in h for h in d["held"])
    # control as the would-be loser is held too
    ctrl_loses = _guard_members()
    for mm in ctrl_loses:
        mm["metrics"][0][0]["positive"], mm["metrics"][0][2]["positive"] = 0, 6
    assert m.decide_family(ctrl_loses)["action"]["arm"] == "control"
    assert m.decide_family(ctrl_loses, unattributed=2)["action"] is None


def test_budget_exhaustion_holds_decisions():
    d = m.decide_family(_guard_members(), unattributed=0, budget_exhausted=3)
    assert d["action"] is None and any("thread-lookup budget exhausted for 3" in h for h in d["held"])


def test_complaint_on_new_role_proceeds_but_base_role_complaint_held_when_incomplete():
    d = m.decide_family(_guard_members(c_unsub=5), unattributed=4)
    assert d["action"]["arm"] == "C" and d["action"]["reason"] == "complaints"
    d2 = m.decide_family(_guard_members(ctrl_unsub=5), unattributed=4)
    assert d2["action"] is None
    assert any("role control (complaints): attribution incomplete (4 unattributed)" in h for h in d2["held"])
    assert m.decide_family(_guard_members(ctrl_unsub=5))["action"]["arm"] == "control"


def test_compute_passes_family_attribution_to_guard():
    snap, replies = _snapshot()
    base = m.actions_of(m.compute(snap, replies))
    snap["campaigns"]["r1"]["attribution"] = {"pre_test": 0, "unattributed": 1, "budget_exhausted": 0}
    res = m.compute(snap, replies)
    assert not any(a[0] == "recruitment" for a in m.actions_of(res))
    assert [a for a in base if a[0] != "recruitment"] == m.actions_of(res)
    text = "\n".join(m.report_body(res, live=False))
    rec = text.split("## Family: yoga_fr")[0]
    if any(a[0] == "recruitment" for a in base):
        assert "attribution incomplete (1 unattributed)" in rec


# 12. per-arm eligibility: warming-up arms neither block nor get disabled
def _elig_members(ctrl_sent, ctrl_pos=0, c_pos=0):
    state = {0: [False, False, False]}
    cells = {0: {0: _cell(ctrl_sent, ctrl_pos, ctrl_pos), 1: _cell(300, 12, 15), 2: _cell(300, c_pos, max(c_pos, 2))}}
    return [{"campaign_id": "c1", "name": "c1", "roles": {0: {"control": 0, "B": 1, "C": 2}}, "state": state,
             "metrics": cells}]


def test_b_vs_c_decided_while_control_has_zero_sends():
    d = m.decide_family(_elig_members(0))
    assert d["action"]["arm"] == "C" and d["action"]["reason"] == "loser"
    assert (0, "control") not in d["pbest"] and (0, "B") in d["pbest"] and (0, "C") in d["pbest"]
    lines = m.family_lines("f", {"members": _elig_members(0), "skipped": [], "decision": d}, live=False)
    assert any("| 1 | control |" in ln and "warming up (0/180)" in ln for ln in lines)


def test_control_never_disabled_while_under_180():
    # Control is clearly worst on raw rates but has 179 sends: B vs C is unclear -> no action, control untouched.
    d = m.decide_family(_elig_members(179, ctrl_pos=0, c_pos=11))
    assert d["action"] is None and all(c["arm"] != "control" for c in m.decide_arms(
        d["pool"]["state"], d["pool"]["cells"])["candidates"])
    # With a clear leader, the under-180 control is still skipped: the loser is C, not control.
    d1 = m.decide_family(_elig_members(179, ctrl_pos=0, c_pos=2))
    assert d1["action"]["arm"] == "C" and (0, "control") not in d1["pbest"]
    # At 180 control becomes eligible and is the lowest P(best).
    d2 = m.decide_family(_elig_members(180, ctrl_pos=0, c_pos=2))
    assert d2["action"]["arm"] == "control"


def test_single_eligible_arm_no_decision():
    d = m.decide_campaign({0: [False, False]}, _cells((500, 15, 20, 0), (179, 0, 0, 0)))
    assert d["action"] is None and d["pbest"] == {}


# 13. scorecard business metrics need >= 50 post-baseline sends
def test_scorecard_business_metrics_need_50_sends():
    v = m.scorecard_values(_row("2026-11-09", sent=16), None)          # roles 16 each, totals 48
    assert all(v[k] is None for k in m.BUSINESS_METRICS)
    v = m.scorecard_values(_row("2026-11-09", sent=20), None)          # totals 60, roles 20
    assert v["unsub_rate"] is not None and v["auto_rate"] is not None
    assert v["pos_rate_best_new"] is None and v["uplift"] is None
    v = m.scorecard_values(_row("2026-11-09", sent=50), None)
    assert all(v[k] is not None for k in m.BUSINESS_METRICS)
