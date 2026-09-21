"""
run.py's `_apply_brief_overrides` mutates ROLE1/ROLE2's hard_gates params in
place (CLI --max-grade/--max-years/--min-years/--counties/--strict-location/
--lenient-location). It must ALSO update spec.seniority_band/spec.
location_rule to match, because layers.gates.composition_violations and
eval/scorecard's post-hoc judge of the delivered set read those two fields
directly -- not the hard_gates params the individual gate checks use -- so a
brief correction that only touched hard_gates would leave the "did this
violate the brief" check judging against the OLD brief while the gates ran
the new one. Same fix as layers/recut.py's `_apply_overrides` (see
test_modal_radar.py's matching tests).

Every test snapshots and restores ROLE1/ROLE2's mutable fields, because
`_apply_brief_overrides` is deliberately a module-global mutation (it must
run before the real pipeline stages, per run.py's own docstring) and this
suite must not leak state between tests or files.
"""

from __future__ import annotations

import argparse

import pytest

from gtm_client_workflows.gaia_sourcing import run as R
from gtm_client_workflows.gaia_sourcing.layers import gates
from gtm_client_workflows.gaia_sourcing.roles import ROLE1, ROLE2


def _args(**kw) -> argparse.Namespace:
    base = dict(
        max_grade=None, max_years=None, min_years=None, counties=None,
        strict_location=False, lenient_location=False,
    )
    base.update(kw)
    return argparse.Namespace(**base)


@pytest.fixture(autouse=True)
def _restore_roles():
    """Snapshot ROLE1/ROLE2's mutable fields and restore after every test."""
    snapshot = {}
    for spec in (ROLE1, ROLE2):
        snapshot[spec.role_id] = (
            spec.seniority_band.model_copy(deep=True) if spec.seniority_band else None,
            spec.location_rule.model_copy(deep=True) if spec.location_rule else None,
            [dict(g.params) for g in spec.hard_gates],
        )
    yield
    for spec in (ROLE1, ROLE2):
        band, loc, params_list = snapshot[spec.role_id]
        spec.seniority_band = band
        spec.location_rule = loc
        for gate, params in zip(spec.hard_gates, params_list):
            gate.params.clear()
            gate.params.update(params)


def test_max_grade_override_also_updates_seniority_band():
    R._apply_brief_overrides(_args(max_grade="senior_engineer"))
    assert ROLE1.seniority_band.max_grade == "senior_engineer"
    assert ROLE2.seniority_band.max_grade == "senior_engineer"
    # And the hard_gates param stays in lockstep, as before.
    gate = next(g for g in ROLE1.hard_gates if g.check == "seniority_ceiling")
    assert gate.params["max_grade"] == "senior_engineer"


def test_years_overrides_update_seniority_band():
    R._apply_brief_overrides(_args(max_years=5, min_years=2))
    assert ROLE1.seniority_band.max_years == 5
    assert ROLE1.seniority_band.min_years == 2


def test_counties_and_strict_location_update_location_rule():
    R._apply_brief_overrides(_args(counties="Cork,Kerry", strict_location=True))
    assert ROLE1.location_rule.counties == ["Cork", "Kerry"]
    assert ROLE1.location_rule.require_direct_evidence is True
    assert ROLE1.location_rule.treat_unknown_as == "fail"


def test_lenient_location_relaxes_location_rule():
    R._apply_brief_overrides(_args(lenient_location=True))
    assert ROLE1.location_rule.require_direct_evidence is False


def test_no_touched_flags_is_a_no_op():
    before = ROLE1.seniority_band.model_dump()
    R._apply_brief_overrides(_args())
    assert ROLE1.seniority_band.model_dump() == before


def test_composition_violations_judges_the_overridden_brief_not_the_old_one():
    """The behavioural point: after overriding to senior_engineer, a
    delivered Principal must show up as a composition violation -- because
    composition_violations reads spec.seniority_band, which must now reflect
    the override the gates just enforced.
    """
    R._apply_brief_overrides(_args(max_grade="senior_engineer"))
    card = {
        "full_name": "Some Principal", "current_title": "Principal Engineer",
        "location": "Dublin, Ireland",
    }
    violations = gates.composition_violations([card], ROLE1)
    assert any("Principal Engineer" in v for v in violations)
