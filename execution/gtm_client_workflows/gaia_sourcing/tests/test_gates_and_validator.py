"""
Adversarial fixtures + validator tests (SPEC.md section 14).

"If these don't fail correctly, nothing else matters."

Zero network. Every fixture is a real-shaped document excerpt; the two ACP
witness-statement fixtures are verbatim text pulled from live public PDFs on
pleanala.ie (see tests/fixtures/ for provenance).
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

# Import the package by path so the tests run without workspace install.
PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG.parents[2]))

from gtm_client_workflows.gaia_sourcing.core.contracts import (  # noqa: E402
    Claim,
    HardGate,
    JobSpec,
    Person,
    RawDocument,
    ValidatedClaim,
)
from gtm_client_workflows.gaia_sourcing.layers import gates  # noqa: E402
from gtm_client_workflows.gaia_sourcing.layers.validator import (  # noqa: E402
    normalize,
    validate_all,
    validate_claim,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_N = 0


def vclaim(dimension: str, assertion: str, quote: str, confidence: str = "direct"):
    global _N
    _N += 1
    return ValidatedClaim(
        claim_id="c" + str(_N),
        subject_person_id="p1",
        dimension=dimension,
        assertion=assertion,
        evidence_quote=quote,
        source_doc_id="d1",
        source_url="https://www.pleanala.ie/example.pdf",
        confidence=confidence,
        quote_verified=True,
    )


def person(**kw):
    base = dict(person_id="p1", full_name="Test Person")
    base.update(kw)
    return Person(**base)


def role_transport() -> JobSpec:
    return JobSpec(
        role_id="role2",
        title="Transport Major Projects Manager",
        client="Gaia Talent",
        end_client="AtkinsRealis",
        locations=["Cork"],
        target_count=5,
        primary_signal_dimension="statutory_process",
        off_limits_employers=["tobin", "atkinsrealis"],
        hard_gates=[
            HardGate(gate_id="chartered", description="CEng", check="chartered"),
            HardGate(gate_id="located_ie", description="IE", check="located_ie"),
            HardGate(
                gate_id="discipline",
                description="transport",
                check="discipline",
                params={
                    "include": ["transport", "highway", "road", "rail", "infrastructure"],
                    "exclude": ["mechanical and electrical", "m&e", "building services"],
                },
            ),
            HardGate(
                gate_id="seniority",
                description=">=10y",
                check="seniority_years",
                params={"min_years": 10},
            ),
            HardGate(
                gate_id="not_client",
                description="not client",
                check="not_client",
                params={"off_limits": ["tobin", "atkinsrealis", "atkins realis"]},
            ),
        ],
    )


def gate(results, gid):
    return next(r for r in results if r.gate_id == gid)


# ---------------------------------------------------------------------------
# The validator -- the single most important function in the repo
# ---------------------------------------------------------------------------


def _doc(text: str) -> dict[str, RawDocument]:
    return {
        "d1": RawDocument(
            doc_id="d1",
            url="https://www.pleanala.ie/example.pdf",
            source_type="acp_witness_statement",
            fetched_at=date(2026, 8, 19),
            content_text=text,
            http_status=200,
        )
    }


REAL_QUOTE = (
    "I have over 26 years post graduate experience and I am a Senior "
    "Associate Director of Highways in Jacobs."
)
REAL_DOC = (
    "1. QUALIFICATIONS AND ROLE IN THE PROPOSED PROJECT\n"
    "1 In accordance with Section 39(1)(a) of the Transport (Railway "
    "Infrastructure) Act 2001 as amended. I confirm that " + REAL_QUOTE + " I "
    "hold a Bachelor of Engineering (Hons) degree in Civil Engineering from "
    "Greenwich University London, I am a Chartered Member and Fellow of the "
    "Institution of Engineers of Ireland (Engineers Ireland).\n"
    "A number of these projects included the preparation of the roads order "
    "documentation (EIAR and CPO)."
)


def test_validator_accepts_verbatim_quote():
    c = Claim(
        claim_id="c",
        subject_person_id="p1",
        dimension="years_experience",
        assertion="Over 26 years post graduate experience",
        evidence_quote=REAL_QUOTE,
        source_doc_id="d1",
        source_url="https://www.pleanala.ie/example.pdf",
        confidence="direct",
    )
    assert validate_claim(c, _doc(REAL_DOC)) is True


def test_validator_rejects_fabricated_quote():
    """The hallucination case. A fluent, plausible, invented sentence."""
    c = Claim(
        claim_id="c",
        subject_person_id="p1",
        dimension="technical_skill",
        assertion="Expert in Tekla Structural Designer",
        evidence_quote=(
            "I have extensive experience with Tekla Structural Designer and "
            "Eurocode compliant design."
        ),
        source_doc_id="d1",
        source_url="https://www.pleanala.ie/example.pdf",
        confidence="direct",
    )
    assert validate_claim(c, _doc(REAL_DOC)) is False


def test_validator_rejects_paraphrase():
    """Near-miss paraphrase must fail. This is the subtle, dangerous case."""
    c = Claim(
        claim_id="c",
        subject_person_id="p1",
        dimension="years_experience",
        assertion="26 years experience",
        # Same meaning, different words -- must NOT pass.
        evidence_quote="I have more than 26 years of postgraduate experience",
        source_doc_id="d1",
        source_url="https://www.pleanala.ie/example.pdf",
        confidence="direct",
    )
    assert validate_claim(c, _doc(REAL_DOC)) is False


def test_validator_survives_pdf_punctuation_mangling():
    """PDF extraction turns apostrophes and dashes into other codepoints.

    A true quote must still match, or every claim gets dropped and the
    system delivers nothing.
    """
    mangled = REAL_DOC.replace("post graduate", "post‑graduate")
    c = Claim(
        claim_id="c",
        subject_person_id="p1",
        dimension="years_experience",
        assertion="Over 26 years",
        evidence_quote="over 26 years post-graduate experience",
        source_doc_id="d1",
        source_url="https://www.pleanala.ie/example.pdf",
        confidence="direct",
    )
    assert validate_claim(c, _doc(mangled)) is True


def test_validator_rejects_missing_source_doc():
    c = Claim(
        claim_id="c",
        subject_person_id="p1",
        dimension="employer",
        assertion="Works at Jacobs",
        evidence_quote="Senior Associate Director of Highways in Jacobs",
        source_doc_id="does-not-exist",
        source_url="https://www.pleanala.ie/example.pdf",
        confidence="direct",
    )
    assert validate_claim(c, _doc(REAL_DOC)) is False


def test_validate_all_reports_drop_rate(tmp_path):
    good = Claim(
        claim_id="c1", subject_person_id="p1", dimension="employer",
        assertion="Jacobs", evidence_quote="Senior Associate Director of Highways in Jacobs",
        source_doc_id="d1", source_url="https://www.pleanala.ie/example.pdf",
        confidence="direct",
    )
    bad = Claim(
        claim_id="c2", subject_person_id="p1", dimension="technical_skill",
        assertion="Tekla", evidence_quote="I am an expert in Tekla and Robot analysis",
        source_doc_id="d1", source_url="https://www.pleanala.ie/example.pdf",
        confidence="direct",
    )
    kept, stats = validate_all([good, bad], _doc(REAL_DOC), tmp_path / "drops.jsonl")
    assert stats["claims_kept"] == 1
    assert stats["claims_dropped"] == 1
    assert stats["drop_rate"] == 0.5
    assert all(c.quote_verified for c in kept)
    assert (tmp_path / "drops.jsonl").read_text(encoding="utf-8").count("\n") == 1


def test_normalize_cannot_invent_a_match():
    """Normalisation must not be so aggressive it creates false positives."""
    assert normalize("chartered engineer") not in normalize("not a chartered surveyor")


# ---------------------------------------------------------------------------
# Adversarial gate fixtures (SPEC.md section 14 table)
# ---------------------------------------------------------------------------


def test_fixture_real_jacobs_engineer_passes_all_gates():
    """The known-good case, from a real public ACP witness statement."""
    claims = [
        vclaim("chartership", "Chartered Member and Fellow of Engineers Ireland",
               "I am a Chartered Member and Fellow of the Institution of Engineers of Ireland"),
        vclaim("location", "Works on Irish schemes, based in Ireland",
               "Level crossings XC187 Fantstown and XC201 Thomastown are in County Limerick"),
        vclaim("sector", "Highways and major roads",
               "Senior Associate Director of Highways in Jacobs"),
        vclaim("years_experience", "Over 26 years post graduate experience",
               "I have over 26 years post graduate experience"),
        vclaim("employer", "Jacobs", "Senior Associate Director of Highways in Jacobs"),
        vclaim("statutory_process", "Prepared EIAR and CPO documentation",
               "included the preparation of the roads order documentation (EIAR and CPO)"),
        vclaim("statutory_process", "Gave evidence at ACP oral hearing",
               "Cork Line Level Crossings Oral Hearing Brief of Evidence"),
    ]
    spec = role_transport()
    res = gates.run_gates(person(current_employer="Jacobs"), claims, spec)
    assert gates.all_passed(res), [r for r in res if not r.passed]
    assert gates.assign_tier(claims, res, spec) == "A"


def test_fixture_uk_based_engineer_fails_location():
    claims = [
        vclaim("chartership", "CEng", "I am a Chartered Engineer, CEng MIEI"),
        vclaim("location", "Based in London", "Based in our London office"),
        vclaim("sector", "Highways", "highway design and road schemes"),
        vclaim("years_experience", "15 years", "I have 15 years experience"),
    ]
    res = gates.run_gates(person(location="London, United Kingdom"), claims, role_transport())
    assert gate(res, "located_ie").passed is False


def test_fixture_northern_ireland_flagged_separately():
    """Belfast is not the Republic -- different chartership/contract regime."""
    claims = [
        vclaim("chartership", "CEng", "I am a Chartered Engineer, CEng MIEI"),
        vclaim("location", "Belfast based", "based in Belfast, Northern Ireland"),
        vclaim("sector", "Transport", "transport planning and road design"),
        vclaim("years_experience", "20 years", "I have 20 years experience"),
    ]
    res = gates.run_gates(person(), claims, role_transport())
    g = gate(res, "located_ie")
    assert g.passed is False
    assert "Northern Ireland" in (g.note or "")


def test_fixture_non_chartered_20_years_fails_chartership():
    """Seniority must never compensate for a missing hard gate (I3)."""
    claims = [
        vclaim("location", "Dublin", "based in Dublin, Ireland"),
        vclaim("sector", "Transport", "major road and transport infrastructure"),
        vclaim("years_experience", "20 years", "I have 20 years experience"),
    ]
    res = gates.run_gates(person(), claims, role_transport())
    assert gate(res, "chartered").passed is False
    assert gates.all_passed(res) is False


def test_fixture_uk_chartership_only_does_not_satisfy_gate():
    """MICE/MIStructE is not Engineers Ireland chartership."""
    claims = [
        vclaim("chartership", "MICE", "I am a Chartered Member of the Institution of Civil Engineers (MICE)"),
        vclaim("location", "Dublin", "based in Dublin, Ireland"),
        vclaim("sector", "Transport", "major road schemes"),
        vclaim("years_experience", "20 years", "I have 20 years experience"),
    ]
    res = gates.run_gates(person(), claims, role_transport())
    g = gate(res, "chartered")
    assert g.passed is False
    assert "non-Irish institution" in (g.note or "")


def test_fixture_wrong_discipline_me_fails():
    claims = [
        vclaim("chartership", "CEng", "I am a Chartered Engineer CEng MIEI"),
        vclaim("location", "Cork", "based in Cork, Ireland"),
        vclaim("sector", "M&E", "mechanical and electrical building services design"),
        vclaim("years_experience", "18 years", "I have 18 years experience"),
    ]
    res = gates.run_gates(person(), claims, role_transport())
    assert gate(res, "discipline").passed is False


def test_fixture_current_client_employee_excluded():
    """Sourcing from the client is a fireable offence in recruitment."""
    claims = [
        vclaim("chartership", "CEng", "I am a Chartered Engineer CEng MIEI"),
        vclaim("location", "Cork", "based in Cork, Ireland"),
        vclaim("sector", "Transport", "major road and transport projects"),
        vclaim("years_experience", "20 years", "I have 20 years experience"),
        vclaim("employer", "AtkinsRealis", "Project Director at AtkinsRealis"),
    ]
    res = gates.run_gates(person(current_employer="AtkinsRealis"), claims, role_transport())
    assert gate(res, "not_client").passed is False


def test_fixture_tobin_employee_excluded():
    claims = [
        vclaim("chartership", "CEng", "I am a Chartered Engineer CEng MIEI"),
        vclaim("location", "Galway", "based in Galway, Ireland"),
        vclaim("sector", "Transport", "road infrastructure design"),
        vclaim("years_experience", "20 years", "20 years experience"),
        vclaim("employer", "TOBIN", "Senior Engineer at TOBIN Consulting Engineers"),
    ]
    res = gates.run_gates(person(current_employer="TOBIN Consulting Engineers"), claims, role_transport())
    assert gate(res, "not_client").passed is False


def test_fixture_too_junior_fails_seniority():
    claims = [
        vclaim("chartership", "CEng", "I am a Chartered Engineer CEng MIEI"),
        vclaim("location", "Cork", "based in Cork, Ireland"),
        vclaim("sector", "Transport", "transport infrastructure projects"),
        vclaim("years_experience", "6 years", "I have 6 years experience"),
    ]
    res = gates.run_gates(person(), claims, role_transport())
    g = gate(res, "seniority")
    assert g.passed is False
    assert "6 years" in (g.note or "")


def test_fixture_zero_evidence_produces_no_passes():
    """A profile with nothing extractable must fail, not be invented into shape."""
    res = gates.run_gates(person(), [], role_transport())
    assert gates.all_passed(res) is False
    assert all(not r.passed for r in res if r.gate_id != "not_client")


def test_inferred_claims_cannot_satisfy_a_gate():
    """Only 'direct' claims count. Inferred renders under Unknowns only."""
    claims = [
        vclaim("chartership", "Probably chartered",
               "He is a senior engineer at a large consultancy", confidence="inferred"),
        vclaim("location", "Dublin", "based in Dublin, Ireland"),
        vclaim("sector", "Transport", "road schemes"),
        vclaim("years_experience", "20 years", "20 years experience"),
    ]
    res = gates.run_gates(person(), claims, role_transport())
    assert gate(res, "chartered").passed is False


# ---------------------------------------------------------------------------
# Tiering
# ---------------------------------------------------------------------------


def _passing_claims() -> list[ValidatedClaim]:
    return [
        vclaim("chartership", "CEng MIEI", "I am a Chartered Engineer, CEng MIEI"),
        vclaim("location", "Cork", "based in Cork, Ireland"),
        vclaim("sector", "Transport", "major transport infrastructure schemes"),
        vclaim("years_experience", "20 years", "I have 20 years experience"),
    ]


def test_tier_c_when_primary_signal_unevidenced():
    spec = role_transport()
    claims = _passing_claims()
    res = gates.run_gates(person(), claims, spec)
    assert gates.all_passed(res)
    assert gates.assign_tier(claims, res, spec) == "C"


def test_tier_b_with_one_primary_signal():
    spec = role_transport()
    claims = _passing_claims() + [
        vclaim("statutory_process", "EIAR", "preparation of the EIAR for the scheme")
    ]
    res = gates.run_gates(person(), claims, spec)
    assert gates.assign_tier(claims, res, spec) == "B"


def test_tier_excluded_when_any_gate_fails():
    spec = role_transport()
    claims = [c for c in _passing_claims() if c.dimension != "chartership"]
    res = gates.run_gates(person(), claims, spec)
    assert gates.assign_tier(claims, res, spec) == "EXCLUDED"


def test_extract_years_ignores_implausible_numbers():
    assert gates.extract_years("the 2024 years of the scheme") is None
    assert gates.extract_years("over 26 years post graduate experience") == 26
    assert gates.extract_years("no numbers here") is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
