"""
Tests for eval/outcomes.py -- outreach outcome tracking and template
rotation weights. Zero network, zero LLM.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from gtm_client_workflows.gaia_sourcing.eval.outcomes import (
    MAX_TEMPLATE_WEIGHT,
    MIN_TEMPLATE_WEIGHT,
    Outcome,
    load_outcomes,
    record_outcome,
    template_weights,
    weekly_report,
)


def test_record_outcome_appends_and_load_outcomes_reads_it_back(tmp_path):
    path = tmp_path / "outcomes.jsonl"
    record_outcome("alice", "t1", "high", "sent", by="consultant_a", path=path)
    record_outcome("alice", "t1", "high", "reply", by="alice", path=path)

    rows = load_outcomes(path)
    assert [r.event for r in rows] == ["sent", "reply"]
    assert rows[0].person_id == "alice"
    assert rows[0].template_id == "t1"


def test_record_outcome_rejects_an_unknown_event(tmp_path):
    with pytest.raises(ValidationError):
        record_outcome("alice", "t1", "high", "smoke_signal", path=tmp_path / "o.jsonl")


def test_load_outcomes_missing_file_is_empty(tmp_path):
    assert load_outcomes(tmp_path / "nope.jsonl") == []


def test_load_outcomes_logs_and_skips_a_malformed_line(tmp_path, capsys):
    path = tmp_path / "outcomes.jsonl"
    record_outcome("alice", "t1", "high", "sent", by="consultant_a", path=path)
    with path.open("a", encoding="utf-8") as fh:
        fh.write("not json at all\n")
    record_outcome("bob", "t1", "high", "sent", by="consultant_a", path=path)

    rows = load_outcomes(path)

    assert [r.person_id for r in rows] == ["alice", "bob"]
    assert "skipping malformed line" in capsys.readouterr().out


def _mk(person, template, bucket, event, when):
    return Outcome(
        person_id=person, template_id=template, movability_bucket=bucket,
        event=event, at=datetime(2026, 9, when, tzinfo=timezone.utc), by="x",
    )


def test_weekly_report_rates_by_template_id():
    rows = [
        _mk("p1", "t1", "high", "sent", 1),
        _mk("p2", "t1", "high", "sent", 1),
        _mk("p3", "t1", "high", "sent", 1),
        _mk("p4", "t1", "high", "sent", 1),
        _mk("p1", "t1", "high", "reply", 2),
        _mk("p2", "t1", "high", "reply", 2),
        _mk("p1", "t1", "high", "conversation", 3),
        _mk("p5", "t2", "low", "sent", 1),
        _mk("p6", "t2", "low", "sent", 1),
    ]
    report = weekly_report(outcomes=rows)["by_template_id"]

    assert report["t1"]["sent"] == 4
    assert report["t1"]["reply_rate"] == pytest.approx(0.5)
    assert report["t1"]["conversation_rate"] == pytest.approx(0.25)

    assert report["t2"]["sent"] == 2
    assert report["t2"]["reply_rate"] == pytest.approx(0.0)
    assert report["t2"]["conversation_rate"] == pytest.approx(0.0)


def test_weekly_report_rates_by_movability_bucket():
    rows = [
        _mk("p1", "t1", "high", "sent", 1),
        _mk("p2", "t1", "high", "sent", 1),
        _mk("p1", "t1", "high", "reply", 2),
        _mk("p3", "t2", "low", "sent", 1),
    ]
    report = weekly_report(outcomes=rows)["by_movability_bucket"]
    assert report["high"]["sent"] == 2
    assert report["high"]["reply_rate"] == pytest.approx(0.5)
    assert report["low"]["sent"] == 1
    assert report["low"]["reply_rate"] == pytest.approx(0.0)


def test_weekly_report_surfaces_a_reply_with_no_recorded_send():
    # Incomplete data (draft mailed outside the tracked flow, say) must be
    # surfaced with null rates, not silently dropped or divided by zero.
    rows = [_mk("p1", "t3", "unknown", "reply", 1)]
    report = weekly_report(outcomes=rows)["by_template_id"]
    assert report["t3"] == {"sent": 0, "reply_rate": None, "conversation_rate": None}


def test_template_weights_bounded_and_never_zero():
    rows = (
        [_mk(f"p{i}", "t_good", "high", "sent", 1) for i in range(10)]
        + [_mk(f"p{i}", "t_good", "high", "reply", 2) for i in range(10)]
        + [_mk(f"p{i}", "t_good", "high", "conversation", 3) for i in range(10)]
        + [_mk(f"q{i}", "t_bad", "low", "sent", 1) for i in range(10)]
    )
    weights = template_weights(["t_good", "t_bad", "t_new"], outcomes=rows)

    # 100% reply rate AND 100% conversation rate -> top-scored, clamped to max.
    assert weights["t_good"] == pytest.approx(MAX_TEMPLATE_WEIGHT)
    assert weights["t_bad"] == pytest.approx(MIN_TEMPLATE_WEIGHT)   # 0% conversion, never 0.0
    assert weights["t_new"] == pytest.approx(MAX_TEMPLATE_WEIGHT)   # no data yet -> not starved

    for w in weights.values():
        assert MIN_TEMPLATE_WEIGHT <= w <= MAX_TEMPLATE_WEIGHT
        assert w > 0.0


def test_template_weights_empty_pool_is_empty_dict():
    assert template_weights([]) == {}


def test_record_outcome_never_overwrites_prior_lines(tmp_path):
    path = tmp_path / "outcomes.jsonl"
    for i in range(5):
        record_outcome(f"p{i}", "t1", "medium", "draft", path=path)
    assert len(load_outcomes(path)) == 5
