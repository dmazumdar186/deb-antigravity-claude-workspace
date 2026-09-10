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
