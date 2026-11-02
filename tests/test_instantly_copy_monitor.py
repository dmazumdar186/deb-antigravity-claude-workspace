"""Offline unit tests for the pure decision logic in execution/infrastructure/instantly_copy_monitor.py."""
from __future__ import annotations

import random

from execution.infrastructure import instantly_copy_monitor as m


# ---- render ---------------------------------------------------------------------------

def test_render_nested_merge_field_inside_spintax():
    rng = random.Random(1)
    for _ in range(20):
        out = m.render("{{RANDOM | open for collaborating {{firstName}} | hi {{companyName}} team}}", rng)
        assert out in ("open for collaborating Mark", "hi Northbridge team")
        out2 = m.render("I pulled three {{location}} owner profiles {{RANDOM | for you | today}}", rng)
        assert out2 in ("I pulled three Dallas owner profiles for you", "I pulled three Dallas owner profiles today")


def test_render_merge_fields_case_sensitive_and_unknown_empty():
    rng = random.Random(1)
    assert m.render("{{location}}/{{Location}}/{{sendingAccountFirstName}}/{{boothSize}}", rng) == "Dallas/Lyon/Deb/"


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
    assert got[0][0] == {"sent": 100, "positive": 1, "human": 1, "unsub": 0}
    assert got[0][1] == {"sent": 90, "positive": 0, "human": 2, "unsub": 1}


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
    return {0: {v: {"sent": s, "positive": p, "human": h, "unsub": u} for v, (s, p, h, u) in enumerate(arms)}}


def test_loser_disabled_when_clear():
    d = m.decide_campaign({0: [False, False]}, _cells((500, 15, 20, 0), (500, 1, 5, 0)))
    assert d["action"]["variant"] == 1 and d["action"]["reason"] == "loser"


def test_no_loser_below_400_sent():
    d = m.decide_campaign({0: [False, False]}, _cells((500, 15, 20, 0), (399, 0, 0, 0)))
    assert d["action"] is None


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


def test_complaints_need_200_sent():
    d = m.decide_campaign({0: [False, False]}, _cells((199, 0, 5, 5), (199, 0, 0, 0)))
    assert d["action"] is None


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
