"""
Brief-level filters added after the client's 2026-09-10 feedback:
"a lot of the candidates were too senior and some were not based in Ireland".

Two deterministic gates carry the fix -- a seniority CEILING (the old gate was
a floor only, and a Director title alone cleared it) and a residence rule that
no longer accepts "worked on an Irish scheme" as proof of living in Ireland.
The last test is the regression that matters: the CSV we actually delivered
on 2026-08-20 must fail the Role 1 ceiling on every Director / Associate
Director row, because that is exactly what the client complained about.
"""

from __future__ import annotations

import csv

import pytest

from gtm_client_workflows.gaia_sourcing.core.config import WORKSPACE_ROOT
from gtm_client_workflows.gaia_sourcing.core.contracts import (
    HardGate, JobSpec, LocationRule, Person, SeniorityBand, ValidatedClaim,
)
from gtm_client_workflows.gaia_sourcing.layers import gates
from gtm_client_workflows.gaia_sourcing.roles import ROLE1, ROLE2

DELIVERED_CSV = WORKSPACE_ROOT / "deliverables" / "gaia_2026-08-20" / "candidates.csv"


def _vc(dimension, assertion, quote, confidence="direct", cid=None):
    return ValidatedClaim(
        claim_id=cid or ("c_" + dimension + "_" + str(abs(hash(quote)) % 10000)),
        subject_person_id="p", dimension=dimension, assertion=assertion,
        evidence_quote=quote, source_doc_id="d1",
        source_url="https://example.ie/profile", confidence=confidence,
        quote_verified=True,
    )


def _person(title=None, location=None):
    return Person(person_id="p", full_name="Test Person", current_title=title,
                  current_employer="Example Consulting", location=location)


def _gate(spec: JobSpec, gate_id: str) -> HardGate:
    return next(g for g in spec.hard_gates if g.gate_id == gate_id)


# ---------------------------------------------------------------------------
# Seniority ceiling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("title,expected", [
    ("Civil / Structural Director", "director"),
    ("Technical Director", "director"),
    ("Head of Structures", "director"),
    ("Transport Planner and Director", "director"),
    ("Civil / Structural Associate Director", "associate_director"),
    ("Senior Associate Director of Highways", "associate_director"),
    ("Associate", "principal_or_associate"),
    ("Principal Engineer", "principal_or_associate"),
    ("Senior Structural Engineer", "senior_engineer"),
    ("Senior Engineer", "senior_engineer"),
    ("Structural Engineer", "engineer"),
    ("Graduate Structural Engineer", "graduate"),
])
def test_grade_ladder_reads_irish_consultancy_titles(title, expected):
    grade, basis = gates._grade_of(_person(title), [])
    assert grade == expected
    assert basis == "person.title"


def test_director_fails_role1_ceiling():
    res = gates.check_seniority_ceiling(
        _person("Civil / Structural Director"), [], _gate(ROLE1, "seniority_ceiling").params
    )
    assert res.passed is False
    assert "above the brief ceiling" in (res.note or "")


def test_senior_engineer_passes_role1_ceiling():
    res = gates.check_seniority_ceiling(
        _person("Senior Structural Engineer"), [], _gate(ROLE1, "seniority_ceiling").params
    )
    assert res.passed is True


def test_associate_director_passes_role2_but_fails_role1():
    p = _person("Associate Director")
    assert gates.check_seniority_ceiling(p, [], _gate(ROLE2, "seniority_ceiling").params).passed
    assert not gates.check_seniority_ceiling(p, [], _gate(ROLE1, "seniority_ceiling").params).passed


def test_explicit_years_above_max_fails():
    claims = [_vc("years_experience", "22 years", "has over 22 years' experience in structures")]
    res = gates.check_seniority_ceiling(
        _person("Senior Structural Engineer"), claims, {"max_grade": "principal_or_associate", "max_years": 18}
    )
    assert res.passed is False
    assert "22 years" in (res.note or "")


def test_unknown_grade_passes_with_note_never_invents():
    res = gates.check_seniority_ceiling(_person(None), [], {"max_grade": "senior_engineer"})
    assert res.passed is True
    assert "not evidenced" in (res.note or "")


def test_grade_read_from_employer_claim_when_title_missing():
    claims = [_vc("employer", "Director at Jacobs", "I am a Technical Director in Jacobs Engineering Ireland")]
    res = gates.check_seniority_ceiling(_person(None), claims, {"max_grade": "associate_director"})
    assert res.passed is False


def test_excluded_title_pattern_fails_and_bad_regex_is_ignored():
    params = {"exclude_title_patterns": ["(", r"\bpartner\b"]}
    assert gates.check_seniority_ceiling(_person("Partner"), [], params).passed is False
    assert gates.check_seniority_ceiling(_person("Senior Engineer"), [], params).passed is True


def test_empty_params_is_a_no_op_ceiling():
    assert gates.check_seniority_ceiling(_person("Managing Director"), [], {}).passed is True


# ---------------------------------------------------------------------------
# Residence rule
# ---------------------------------------------------------------------------

STRICT = {"require_direct_evidence": True, "counties": []}
CORK = {"require_direct_evidence": True, "counties": ["Cork"]}


def _scheme_only():
    return [_vc("statutory_process", "Gave evidence on N6",
                "gave evidence at the oral hearing for the N6 Galway City Ring Road for TII")]


def test_scheme_only_evidence_passes_lenient_but_fails_strict():
    lenient = gates.check_located_ie(_person(), _scheme_only(), {})
    assert lenient.passed is True and "Confirm" in (lenient.note or "")
    strict = gates.check_located_ie(_person(), _scheme_only(), STRICT)
    assert strict.passed is False
    assert "scheme work only" in (strict.note or "")


def test_scheme_only_with_pass_with_note_stays_loud():
    res = gates.check_located_ie(
        _person(), _scheme_only(), {**STRICT, "treat_unknown_as": "pass_with_note"}
    )
    assert res.passed is True and res.note


def test_direct_cork_evidence_passes_strict_and_county():
    claims = [_vc("location", "Based in Cork", "I am based in our Cork office")]
    assert gates.check_located_ie(_person(), claims, STRICT).passed is True
    assert gates.check_located_ie(_person(), claims, CORK).passed is True


def test_commuter_town_counts_for_its_county():
    claims = [_vc("location", "Lives in Midleton", "I live in Midleton, Co. Cork")]
    assert gates.check_located_ie(_person(), claims, CORK).passed is True


@pytest.mark.parametrize("quote", [
    "I am based in Belfast and lead the Northern Ireland team",
    "I joined the London office in 2015",
])
def test_belfast_and_london_fail_strict(quote):
    claims = [_vc("location", "Where based", quote)]
    assert gates.check_located_ie(_person(), claims, STRICT).passed is False


def test_dublin_fails_cork_county_list_unless_relocation_signal():
    claims = [_vc("location", "Based in Dublin", "I am based in our Dublin office")]
    res = gates.check_located_ie(_person(), claims, CORK)
    assert res.passed is False
    assert "target county" in (res.note or "")
    relocating = claims + [_vc("project", "Relocation", "and I am relocating to Cork next year")]
    res2 = gates.check_located_ie(
        _person(), relocating, {**CORK, "allow_relocation_signal": True}
    )
    assert res2.passed is True and "Relocation" in (res2.note or "")


def test_no_params_keeps_old_behaviour_for_existing_specs():
    """Backwards compatibility: an absent params dict is the pre-2026-09-10 gate."""
    claims = [_vc("employer", "Works for TII", "employed by Transport Infrastructure Ireland")]
    assert gates.check_located_ie(_person(), claims, {}).passed is True


# ---------------------------------------------------------------------------
# Delivery composition guard + regression on the delivered CSV
# ---------------------------------------------------------------------------


def test_composition_guard_names_each_violation():
    cards = [
        {"full_name": "A Director", "current_title": "Civil / Structural Director", "location": "Dublin"},
        {"full_name": "B London", "current_title": "Senior Structural Engineer", "location": "London"},
        {"full_name": "C Fine", "current_title": "Senior Structural Engineer", "location": "Galway"},
    ]
    v = gates.composition_violations(cards, ROLE1)
    assert len(v) == 2
    assert any("A Director" in x and "ceiling" in x for x in v)
    assert any("B London" in x and "Republic of Ireland" in x for x in v)


def test_composition_guard_is_empty_for_a_spec_without_bands():
    spec = ROLE1.model_copy(update={"seniority_band": None, "location_rule": None})
    cards = [{"full_name": "X", "current_title": "Managing Director", "location": "London"}]
    assert gates.composition_violations(cards, spec) == []


# ---------------------------------------------------------------------------
# Title-based seniority-FLOOR acceptance (client feedback 2026-09-11: 21
# Role 1 people failed ONLY the 8-year floor with a directory title that
# already names the brief's target grade and states no years).
# ---------------------------------------------------------------------------

ROLE1_ACCEPT = {"min_years": 8, "accept_titles_for_floor": ["senior", "lead", "associate", "principal"]}


@pytest.mark.parametrize("title", [
    "Senior Structural Engineer",
    "Senior Structural Engineer CEng MIEI",
    "Lead / Senior Structural Engineer",
    "Civil / Structural Associate",
])
def test_floor_accepts_title_with_no_years_evidence(title):
    res = gates.check_seniority(_person(title), [], ROLE1_ACCEPT)
    assert res.passed is True
    assert "years not stated" in (res.note or "")
    assert "title accepted for the floor" in (res.note or "")
    assert "confirm years on first call" in (res.note or "")


def test_floor_title_acceptance_matches_from_employer_claim_when_no_title():
    claims = [_vc("employer", "Senior role", "I work as a Senior Structural Engineer at Example Consulting")]
    res = gates.check_seniority(_person(None), claims, ROLE1_ACCEPT)
    assert res.passed is True
    assert res.basis != "person.title"


def test_floor_not_accepted_when_param_absent():
    """Without accept_titles_for_floor, the same title still fails the floor --
    the existing allow_grade_inference mechanism does not catch 'Senior
    Structural Engineer' (it is reachable at ~5 years, deliberately excluded
    from _SENIOR_GRADE_RE)."""
    res = gates.check_seniority(
        _person("Senior Structural Engineer"), [], {"min_years": 8, "allow_grade_inference": True}
    )
    assert res.passed is False


def test_floor_years_evidence_still_wins_over_title_acceptance():
    """A years figure below the minimum must still fail, even with a
    matching title -- accept_titles_for_floor is a NO-EVIDENCE fallback
    only, never an override of stated years."""
    claims = [_vc("years_experience", "5 years", "I have 5 years of experience")]
    res = gates.check_seniority(_person("Senior Structural Engineer"), claims, ROLE1_ACCEPT)
    assert res.passed is False
    assert "5 years" in (res.note or "")


def test_role2_unaffected_by_title_acceptance_default():
    """Role 2's own spec leaves accept_titles_for_floor empty -- unaffected."""
    params = _gate(ROLE2, "seniority").params
    assert params.get("accept_titles_for_floor") == []
    res = gates.check_seniority(_person("Senior Transport Engineer"), [], params)
    assert res.passed is False


# ---------------------------------------------------------------------------
# Employer sector gate (client feedback 2026-09-11: "Senior Structural
# Engineer at Nokia" passed discipline on the word "structural" alone).
# ---------------------------------------------------------------------------


def _employer_person(employer):
    return Person(person_id="p", full_name="Test Person", current_title="Senior Structural Engineer",
                  current_employer=employer, location="Dublin")


def test_nokia_fails_employer_sector():
    params = _gate(ROLE1, "employer_sector").params
    res = gates.check_employer_sector(_employer_person("Nokia"), [], params)
    assert res.passed is False
    assert "Nokia" in (res.note or "")
    assert "does not read as an engineering consultancy" in (res.note or "")


def test_firms_entry_passes_employer_sector():
    params = _gate(ROLE1, "employer_sector").params
    res = gates.check_employer_sector(_employer_person("O'Connor Sutton Cronin"), [], params)
    assert res.passed is True


def test_pattern_match_passes_employer_sector():
    params = _gate(ROLE1, "employer_sector").params
    res = gates.check_employer_sector(_employer_person("Lally Chartered Engineers"), [], params)
    assert res.passed is True


def test_empty_employer_passes_with_note():
    params = _gate(ROLE1, "employer_sector").params
    res = gates.check_employer_sector(_employer_person(None), [], params)
    assert res.passed is True
    assert res.note == "employer not stated"


def test_off_limits_employer_fails_even_though_it_reads_as_consultancy():
    params = _gate(ROLE1, "employer_sector").params
    res = gates.check_employer_sector(_employer_person("AtkinsRealis"), [], params)
    assert res.passed is False


def test_tii_passes_for_role2_only():
    # Plain "TII" -- not "Transport Infrastructure Ireland", which contains
    # "Infrastructure" and would pass the shape pattern on "structur" alone
    # regardless of role, defeating the point of this test.
    role2_params = _gate(ROLE2, "employer_sector").params
    assert gates.check_employer_sector(_employer_person("TII"), [], role2_params).passed is True
    role1_params = _gate(ROLE1, "employer_sector").params
    assert gates.check_employer_sector(_employer_person("TII"), [], role1_params).passed is False


def test_composition_guard_flags_nokia_card():
    cards = [
        {"full_name": "Nokia Person", "current_title": "Senior Structural Engineer",
         "current_employer": "Nokia", "location": "Dublin"},
        {"full_name": "Fine Person", "current_title": "Senior Structural Engineer",
         "current_employer": "O'Connor Sutton Cronin", "location": "Galway"},
    ]
    v = gates.composition_violations(cards, ROLE1)
    assert any("Nokia Person" in x for x in v)
    assert not any("Fine Person" in x for x in v)


# ---------------------------------------------------------------------------
# CLI override -- --accept-senior-titles / --no-accept-senior-titles
# ---------------------------------------------------------------------------


def _override_args(**kw):
    base = dict(
        max_grade=None, max_years=None, min_years=None, counties=None,
        strict_location=False, lenient_location=False, accept_senior_titles=None,
        accept_senior_titles_role2=None,
    )
    base.update(kw)
    import argparse
    return argparse.Namespace(**base)


def test_cli_accept_senior_titles_flips_role1_only_by_default():
    """2026-09-11 adversarial-audit fix (item 5): --accept-senior-titles used
    to apply to BOTH roles unconditionally, silently giving Role 2 (which
    never opts in on its own -- witness statements state years explicitly)
    the same title-floor override as Role 1. It now only ever touches a role
    that already carries a non-empty accept_titles_for_floor of its own."""
    from gtm_client_workflows.gaia_sourcing import run as R

    snapshot = {
        spec.role_id: [dict(g.params) for g in spec.hard_gates]
        for spec in (ROLE1, ROLE2)
    }
    try:
        R._apply_brief_overrides(_override_args(accept_senior_titles=True))
        r1 = next(g for g in ROLE1.hard_gates if g.gate_id == "seniority")
        r2 = next(g for g in ROLE2.hard_gates if g.gate_id == "seniority")
        assert r1.params["accept_titles_for_floor"]
        assert r2.params["accept_titles_for_floor"] == []

        R._apply_brief_overrides(_override_args(accept_senior_titles=False))
        assert r1.params["accept_titles_for_floor"] == []
        assert r2.params["accept_titles_for_floor"] == []
    finally:
        for spec in (ROLE1, ROLE2):
            for gate, params in zip(spec.hard_gates, snapshot[spec.role_id]):
                gate.params.clear()
                gate.params.update(params)


def test_cli_accept_senior_titles_role2_is_a_separate_explicit_opt_in():
    from gtm_client_workflows.gaia_sourcing import run as R

    snapshot = {
        spec.role_id: [dict(g.params) for g in spec.hard_gates]
        for spec in (ROLE1, ROLE2)
    }
    try:
        r1_before = dict(next(g for g in ROLE1.hard_gates
                              if g.gate_id == "seniority").params)
        R._apply_brief_overrides(_override_args(accept_senior_titles_role2=True))
        r1 = next(g for g in ROLE1.hard_gates if g.gate_id == "seniority")
        r2 = next(g for g in ROLE2.hard_gates if g.gate_id == "seniority")
        # Role 1 untouched by the Role-2-only flag.
        assert r1.params["accept_titles_for_floor"] == r1_before["accept_titles_for_floor"]
        assert r2.params["accept_titles_for_floor"]

        R._apply_brief_overrides(_override_args(accept_senior_titles_role2=False))
        assert r2.params["accept_titles_for_floor"] == []
    finally:
        for spec in (ROLE1, ROLE2):
            for gate, params in zip(spec.hard_gates, snapshot[spec.role_id]):
                gate.params.clear()
                gate.params.update(params)


@pytest.mark.skipif(not DELIVERED_CSV.exists(), reason="deliverable not present")
def test_every_delivered_role1_director_is_now_excluded():
    """The client's complaint, as a regression: every Role 1 row we shipped
    that carries a Director / Associate Director title must fail the ceiling."""
    with DELIVERED_CSV.open(encoding="utf-8-sig") as fh:  # the CSV carries a BOM
        rows = [r for r in csv.DictReader(fh) if r["role"] == ROLE1.title or "structural" in r["role"].lower()]
    assert rows, "no Role 1 rows found in the delivered CSV"
    directors = [r for r in rows if "director" in r["current_title"].lower()]
    assert len(directors) == len(rows) == 10, (len(directors), len(rows))
    params = _gate(ROLE1, "seniority_ceiling").params
    for r in directors:
        res = gates.check_seniority_ceiling(_person(r["current_title"]), [], params)
        assert res.passed is False, r["full_name"] + " / " + r["current_title"]
