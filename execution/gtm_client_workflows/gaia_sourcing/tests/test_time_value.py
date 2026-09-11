"""eval/time_value.py -- pure arithmetic, no model, no stage read."""

from __future__ import annotations

from gtm_client_workflows.gaia_sourcing.eval.time_value import (
    Assumptions,
    august_list,
    hours_for,
    weekly,
)


def test_hours_for_default_assumptions():
    a = Assumptions()
    assert hours_for(4, a) == 1.0  # 4 * 15 / 60


def test_hours_for_rounds_to_two_dp():
    a = Assumptions(minutes_per_manual_check=10)
    assert hours_for(1, a) == 0.17  # 10/60 = 0.1666...


def test_weekly_default_assumptions():
    a = Assumptions()
    out = weekly(a)
    assert out["hours_per_week"] == 10.0  # 40 * 15 / 60
    assert out["eur_per_week"] == 450.0  # 10 * 45
    assert out["eur_per_month"] == round(450.0 * 52 / 12, 2)


def test_weekly_is_editable_via_assumptions():
    a = Assumptions(minutes_per_manual_check=30, names_per_week=10, hourly_cost_eur=50)
    out = weekly(a)
    assert out["hours_per_week"] == 5.0
    assert out["eur_per_week"] == 250.0


def test_august_list_defaults():
    out = august_list()
    assert out["consultant_hours_spent"] == 3.25  # 13 * 15 / 60
    assert out["calls_that_would_have_been_wrong"] == 13
    assert out["emails_to_unplaceable"] == 4


def test_august_list_custom_counts_and_assumptions():
    a = Assumptions(minutes_per_manual_check=20)
    out = august_list(names=5, emails_written=2, a=a)
    assert out["consultant_hours_spent"] == round(5 * 20 / 60, 2)
    assert out["calls_that_would_have_been_wrong"] == 5
    assert out["emails_to_unplaceable"] == 2


def test_every_number_is_deterministic_no_randomness():
    a = Assumptions()
    assert weekly(a) == weekly(a)
    assert august_list(a=a) == august_list(a=a)
