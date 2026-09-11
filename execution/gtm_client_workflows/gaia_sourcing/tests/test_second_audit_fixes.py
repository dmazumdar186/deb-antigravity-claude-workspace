"""
Second adversarial audit (2026-09-11) -- targeted regression tests for the
seven findings fixed in this pass. Each test is named after, and quotes, the
exact fixture the finding specified so a future regression is unambiguous
about which finding it broke.
"""

from __future__ import annotations

from datetime import date

from gtm_client_workflows.gaia_sourcing.core.contracts import Person, ValidatedClaim
from gtm_client_workflows.gaia_sourcing.layers import gates
from gtm_client_workflows.gaia_sourcing.layers.extract import _find_location_quote
from gtm_client_workflows.gaia_sourcing.layers.identity import has_identity_corroboration


def _vc(dimension, assertion, quote, doc_id="d1", confidence="direct"):
    return ValidatedClaim(
        claim_id="c" + dimension + doc_id + quote[:8], subject_person_id="p",
        dimension=dimension, assertion=assertion, evidence_quote=quote,
        source_doc_id=doc_id, source_url="https://example.ie/p",
        confidence=confidence, quote_verified=True,
    )


def _person(full_name="Jane Doe", title=None):
    return Person(person_id="p", full_name=full_name, current_title=title,
                  current_employer="ABC Consulting")


# ---------------------------------------------------------------------------
# Item 2 -- "across the UK and Ireland" can never be a residence basis
# ---------------------------------------------------------------------------


def test_across_the_uk_and_ireland_is_not_residence_evidence():
    claims = [_vc(
        "location", "Jane Doe has worked across the UK and Ireland.",
        "having worked across the UK and Ireland for over a decade",
    )]
    result = gates.check_located_ie(_person(), claims, {})
    assert result.passed is False


def test_uk_alone_is_caught_by_non_ie_re():
    assert gates._NON_IE_RE.search("based across the UK") is not None


# ---------------------------------------------------------------------------
# Item 3 -- institution-name "Ireland" never counts as residence, and
# pipeline-authored claims contribute only their quote
# ---------------------------------------------------------------------------


def test_pipeline_authored_assertion_is_ignored_only_the_quote_counts():
    """A claim shaped like stage_locate's own default-location claim (the
    assertion literally says "<Name> is based in Ireland") must not let that
    ASSERTION satisfy the gate -- only its evidence_quote, which here names
    no Irish location at all, is evaluated."""
    claims = [_vc(
        "location", "Jane Doe is based in Ireland",
        "the firm has offices across several counties",
    )]
    result = gates.check_located_ie(_person(), claims, {})
    assert result.passed is False


def test_engineers_ireland_org_name_alone_does_not_pass_located_ie():
    claims = [_vc(
        "location", "Jane Doe is a chartered member",
        "Jane Doe is an Engineers Ireland Chartered Engineer",
    )]
    result = gates.check_located_ie(_person(), claims, {})
    assert result.passed is False


def test_find_location_quote_rejects_an_institution_name_fragment():
    """The audit's exhibit: "Alan Lambe is an Engineers Ireland Chartered
    Engineer" must yield no location claim at all."""
    text = "Alan Lambe is an Engineers Ireland Chartered Engineer with 20 years experience."
    assert _find_location_quote(text, "Alan Lambe", None) is None


def test_find_location_quote_accepts_a_real_office_statement():
    text = "Our office is in Cork, Ireland and has been since 1998."
    quote = _find_location_quote(text, "Someone", "Cork")
    assert quote is not None
    assert "cork" in quote.lower()


def test_find_location_quote_never_starts_mid_word():
    """A slice that used to begin "...cts is an Engineers Ireland..." (a
    fragment of "products is an Engineers Ireland...") must never be
    returned as a quote."""
    text = "Our range of products is an Engineers Ireland approved supplier list."
    assert _find_location_quote(text, "Nobody Here", None) is None


# ---------------------------------------------------------------------------
# Item 4 -- bare "engineer"/"engineering" is not identity corroboration
# ---------------------------------------------------------------------------


def test_a_goosechase_page_naming_bare_engineer_is_rejected():
    """The audit's exhibit: a uwaterloo GooseChase treasure-hunt page for
    "Andrew Cross" must not corroborate a structural engineer of the same
    name just because it happens to say "engineer" somewhere."""
    window = "Andrew Cross joined the GooseChase hunt as a software engineer for team Waterloo"
    assert has_identity_corroboration(window, employer="Engineering Solutions") is False


def test_an_ocsc_bio_block_naming_structural_is_accepted():
    window = "Andrew Cross is a structural engineer with O'Connor Sutton Cronin"
    assert has_identity_corroboration(window, employer="O'Connor Sutton Cronin") is True


def test_founder_and_startup_now_contradict():
    window = "Jane Doe, founder and CEO of a fintech startup, engineer by training"
    assert has_identity_corroboration(window, employer="ABC Consulting") is False


# ---------------------------------------------------------------------------
# Item 5 -- education claims (graduation year) as a years-of-experience
# estimate for the seniority ceiling
# ---------------------------------------------------------------------------


def test_graduation_year_far_above_ceiling_fails():
    """The audit's own fixture: "graduated from UCD in 2005" against a
    max_years of 18 -- current year minus 2005 is comfortably >= 2 years
    over the ceiling for any test run in this decade."""
    this_year = date.today().year
    grad_year = this_year - 21  # ~21 years' experience implied
    claims = [_vc(
        "education", "Jane Doe graduated from UCD in " + str(grad_year),
        "Jane Doe graduated from UCD in " + str(grad_year)
        + " with a degree in civil engineering",
    )]
    result = gates.check_seniority_ceiling(_person(), claims, {"max_years": 18})
    assert result.passed is False
    assert str(grad_year) in (result.note or "")


def test_graduation_year_just_over_ceiling_passes_with_a_note():
    this_year = date.today().year
    grad_year = this_year - 19  # ~19 years -- 1 year over an 18-year ceiling
    claims = [_vc(
        "education", "Jane Doe qualified in " + str(grad_year),
        "Jane Doe qualified in " + str(grad_year) + " as a chartered engineer",
    )]
    result = gates.check_seniority_ceiling(_person(), claims, {"max_years": 18})
    assert result.passed is True
    assert result.note


# ---------------------------------------------------------------------------
# Item 6 -- render honesty
# ---------------------------------------------------------------------------


def test_msg_cell_shows_real_compliance_reason_not_the_privacy_line():
    from gtm_client_workflows.gaia_sourcing.render import render as R

    cell = R._msg_cell({"dropped": "Art. 14 notice missing from the email body."}, True)
    assert "Withheld until the privacy notice is live" not in cell
    assert "failed the compliance check" in cell
    assert "Art. 14 notice missing" in cell


def test_msg_cell_shows_model_returned_nothing():
    from gtm_client_workflows.gaia_sourcing.render import render as R

    cell = R._msg_cell({"dropped": "model returned nothing"}, True)
    assert "model returned nothing" in cell


def test_msg_cell_still_shows_the_privacy_line_when_notice_is_actually_down():
    from gtm_client_workflows.gaia_sourcing.render import render as R

    cell = R._msg_cell(None, False)
    assert "Withheld until the privacy notice is live" in cell


def test_detail_pane_renders_seniority_and_located_ie_notes_as_confirm_lines():
    from gtm_client_workflows.gaia_sourcing.render import render as R

    class _Spec:
        primary_signal_dimension = "technical_skill"
        role_id = "role1"

    ev = {
        "tier": "B",
        "gates": [
            {"gate_id": "seniority_ceiling", "passed": True,
             "note": "grade not evidenced; confirm on first call"},
            {"gate_id": "located_ie", "passed": True,
             "note": "Ireland evidenced alongside other jurisdictions -- confirm "
                      "current base in the first call."},
        ],
    }
    pane = R._detail_cell({"person_id": "p1", "full_name": "X",
                           "current_employer": "Firm"},
                          [], ev, {"email_status": "verified"}, {}, {}, _Spec())
    assert "Confirm on first call" in pane
    assert "grade not evidenced" in pane


def test_detail_pane_renders_non_incomplete_adversarial_findings():
    from gtm_client_workflows.gaia_sourcing.render import render as R

    class _Spec:
        primary_signal_dimension = "technical_skill"
        role_id = "role1"

    ev = {"tier": "B", "adversarial_findings": ["Recently promoted, confirm tenure."]}
    pane = R._detail_cell({"person_id": "p1", "full_name": "X",
                           "current_employer": "Firm"},
                          [], ev, {"email_status": "verified"}, {}, {}, _Spec())
    assert "Second opinion: Recently promoted, confirm tenure." in pane
