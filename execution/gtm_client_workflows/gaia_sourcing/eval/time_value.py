"""
Shortlist Check time-value (deliverables/gaia_poc_check/PLAN.md, "Quantified
value"). Pure, deterministic, no model call and no stage read -- every
number here is arithmetic over inputs the caller supplies.

Every default in `Assumptions` is exactly that: a number Keith can change on
a call. None of them is measured; they are stated as assumptions on the
Keith-facing page (`render/check_page.py`) rather than presented as fact.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Assumptions:
    """Editable inputs behind every number in this module. Defaults are
    PLAN.md's stated placeholders, not measurements -- see the module
    docstring."""

    minutes_per_manual_check: float = 15.0
    names_per_week: float = 40.0
    hourly_cost_eur: float = 45.0
    # Code-review fix 2026-09-11 (item e): the operator's OWN note about
    # the 20 August delivery ("4 emails were written to people the brief
    # could never place"), not a count this module derives from anything
    # -- there is no "emails sent" field anywhere in the cache. Kept as an
    # editable assumption, same as the three above, so a future run's
    # caller can correct it without touching code; run_check reads it via
    # `august_list(a=assumptions)` instead of a hard-coded default.
    emails_written: int = 4


def hours_for(names: int, a: Assumptions) -> float:
    """Consultant hours spent manually checking `names` candidates."""
    return round(names * a.minutes_per_manual_check / 60.0, 2)


def weekly(a: Assumptions) -> dict:
    """Hours and euros the manual check burns in a normal week, at
    `a.names_per_week` names/week."""
    hours = hours_for(a.names_per_week, a)
    eur_per_week = round(hours * a.hourly_cost_eur, 2)
    eur_per_month = round(eur_per_week * 52.0 / 12.0, 2)
    return {
        "hours_per_week": hours,
        "eur_per_week": eur_per_week,
        "eur_per_month": eur_per_month,
    }


def august_list(
    names: int = 13, emails_written: int = 4, a: Assumptions | None = None
) -> dict:
    """The 20 August delivery's own numbers: consultant hours spent on a
    list where every name later proved wrong for the brief, and how many of
    those went as far as an email to someone who could never be placed on
    it. `calls_that_would_have_been_wrong` is every name on the list --
    a manual check has no way to catch a wrong candidate before the call
    that phones them."""
    a = a or Assumptions()
    return {
        "consultant_hours_spent": hours_for(names, a),
        "calls_that_would_have_been_wrong": names,
        "emails_to_unplaceable": emails_written,
    }
