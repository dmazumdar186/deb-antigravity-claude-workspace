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


# ---------------------------------------------------------------------------
# Third cut (2026-09-11) -- the Richard Kiernan exhibit
# ---------------------------------------------------------------------------


def test_a_mid_word_acei_fragment_does_not_pass_located_ie():
    """The windowed quote "ulting Engineers of Ireland (ACEI) and was awar"
    starts mid-word, so the word-boundary-anchored "consulting engineers of
    ireland" strip never fired and the fragment passed as Republic residence.
    It is a fragment of an organisation's name and says nothing about where
    anyone lives."""
    claims = [_vc(
        "location", "Richard Kiernan is based in Ireland",
        "ulting Engineers of Ireland (ACEI) and was awar",
    )]
    # person.location is the legacy unstamped "Ireland" locate --force clears;
    # leave it None here so only the claim is under test.
    result = gates.check_located_ie(_person("Richard Kiernan"), claims, {})
    assert result.passed is False


def test_detail_pane_always_keeps_the_first_verbatim_quote():
    """Three long second-opinion findings used to eat the whole word budget
    and the pane printed "No verbatim evidence fits here" for every card, so
    the dossier shipped with zero evidence claims. The first quote is the
    evidence contract and is never dropped for budget."""
    from gtm_client_workflows.gaia_sourcing.render import render as R

    class _Spec:
        primary_signal_dimension = "technical_skill"
        role_id = "role1"

    long_finding = " ".join(["word"] * 80)
    ev = {"tier": "B", "adversarial_findings": [long_finding] * 3}
    claims = [{
        "dimension": "employer", "assertion": "X works at Firm",
        "evidence_quote": "X is a Senior Structural Engineer at Firm",
        "source_url": "https://example.ie/x", "confidence": "direct",
    }]
    pane = R._detail_cell({"person_id": "p1", "full_name": "X",
                           "current_employer": "Firm"},
                          claims, ev, {"email_status": "verified"}, {}, {},
                          _Spec())
    assert '<div class="claim"><blockquote>' in pane
    assert "No verbatim evidence fits here" not in pane
    # And the findings themselves are clipped rather than printed in full.
    assert long_finding not in pane
    assert "Second opinion:" in pane
    assert "+1 more second-opinion finding" in pane


def test_second_opinions_never_evict_the_email_honesty_line():
    """Code review on the third cut: findings sat ahead of the email-status
    warning, so the pop-from-end trim dropped "treat it as a guess" first."""
    from gtm_client_workflows.gaia_sourcing.render import render as R

    class _Spec:
        primary_signal_dimension = "technical_skill"
        role_id = "role1"

    ev = {"tier": "B", "adversarial_findings": [" ".join(["word"] * 80)] * 3}
    pane = R._detail_cell({"person_id": "p1", "full_name": "X",
                           "current_employer": "Firm"},
                          [], ev, {"email": "x@firm.ie",
                                   "email_status": "pattern_guess"}, {}, {},
                          _Spec())
    assert "guess" in pane.lower()
    assert R._wc(pane) <= R.DETAIL_WORD_CAP


def test_unstamped_belfast_location_still_excludes():
    """Provenance gates what can pass, never what can exclude: an unstamped
    "Regional Director (Belfast Office)" location must still fail."""
    p = Person(person_id="p", full_name="Jane Doe",
               current_title="Regional Director (Belfast Office)",
               current_employer="ABC Consulting",
               location="Regional Director (Belfast Office)")
    result = gates.check_located_ie(p, [], {})
    assert result.passed is False
    assert "Northern Ireland" in (result.note or "")

    london = Person(person_id="p", full_name="Jane Doe", current_title=None,
                    current_employer="ABC Consulting", location="London")
    assert gates.check_located_ie(london, [], {}).passed is False


def test_a_firm_default_pass_says_so_on_the_card():
    stamped = Person(person_id="p", full_name="Jane Doe", current_title=None,
                     current_employer="ABC Consulting", location="Dublin, Ireland",
                     location_source="firm_default")
    result = gates.check_located_ie(stamped, [], {})
    assert result.passed is True
    assert "only listed office" in (result.note or "")


def test_an_unstamped_person_location_is_not_a_residence_basis():
    """Three of four third-cut cards passed located_ie on Person.location
    alone: "Limerick" inferred from "University of Hospital Limerick
    Project", "Dublin" from "University College Dublin". Without a
    location_source stamp the field is the extraction model's inference,
    not evidence, so it must not carry the gate."""
    p = Person(person_id="p", full_name="Jane Doe", current_title=None,
               current_employer="ABC Consulting", location="Limerick")
    assert getattr(p, "location_source", None) is None
    result = gates.check_located_ie(p, [], {})
    assert result.passed is False

    stamped = Person(person_id="p", full_name="Jane Doe", current_title=None,
                     current_employer="ABC Consulting", location="Limerick",
                     location_source="firm_default")
    assert gates.check_located_ie(stamped, [], {}).passed is True


def test_org_strip_never_eats_a_complete_adjacent_residence_token():
    """Anneal-review finding on the third cut: the fragment strip must not
    swallow a whole preceding word, or "Cork engineers of Ireland branch
    chair" loses its county and a real residence reads as a miss."""
    cleaned = gates._clean_residence_haystack("Cork engineers of Ireland branch chair")
    assert "Cork" in cleaned
    assert "engineers of Ireland" not in cleaned
    assert "Engineers of Ireland" not in gates._clean_residence_haystack(
        "ulting Engineers of Ireland (ACEI) and was awar")


# ---------------------------------------------------------------------------
# Third audit (2026-09-11) -- Alcaras / Clyne / McBeath / Healy exhibits
# ---------------------------------------------------------------------------


def test_employer_recovered_from_own_text_in_both_shapes():
    from gtm_client_workflows.gaia_sourcing.layers.extract import employer_from_own_text
    firm, quote = employer_from_own_text(
        "JOHN ALCARAS BSc CEng MIEI. Lead / Senior Structural Engineer at "
        "Arcadis. Arcadis University of the Philippines. Dublin, County Dublin")
    assert firm == "Arcadis" and quote == "Lead / Senior Structural Engineer at Arcadis"
    firm, quote = employer_from_own_text(
        "Senior Structural Engineer. J.A. Gorman Consulting Engineers Ltd. Jan 2014 - Present")
    assert firm == "J.A. Gorman Consulting Engineers Ltd"
    assert quote in "Senior Structural Engineer. J.A. Gorman Consulting Engineers Ltd. Jan 2014 - Present"
    assert employer_from_own_text("Chartered Engineer with 10 years at the University of Limerick") is None


def test_spaced_and_dotted_chartership_forms_are_recognised():
    assert gates._CENG_RE.search("C. Eng, B. Eng, M.S.c, MIStructE, MIEI.")
    assert gates._FIEI_ALONE_RE.search("CEng., F.I.E.I.")


def test_inferred_employer_quote_naming_the_person_counts_for_grade():
    claims = [_vc("employer", "Mark Clyne is Head of Design at J.A. Gorman",
                  "Mark Clyne. Head of Design, Chartered Structural Engineer.",
                  confidence="inferred")]
    grade = gates._grade_of(_person("Mark Clyne", "Senior Chartered Structural Engineer"), claims)
    assert grade is not None and grade[0] == "director"
    # The same inferred quote about somebody else does not count.
    other = [_vc("employer", "x", "Someone Else. Head of Design.", confidence="inferred")]
    grade = gates._grade_of(_person("Mark Clyne", "Senior Structural Engineer"), other)
    assert grade[0] == "senior_engineer"


def test_firm_default_cannot_carry_a_brief_that_requires_direct_evidence():
    stamped = Person(person_id="p", full_name="Jane Doe", current_title=None,
                     current_employer="ABC Consulting", location="Dublin, Ireland",
                     location_source="firm_default")
    assert gates.check_located_ie(stamped, [], {"require_direct_evidence": True}).passed is False
    assert gates.check_located_ie(stamped, [], {}).passed is True


def test_arcadis_reads_as_a_consultancy():
    ok, _ = gates.employer_reads_as_consultancy("Arcadis", [], {})
    assert ok is True


def test_shouted_names_and_truncated_titles_are_tidied_for_display():
    from gtm_client_workflows.gaia_sourcing.render import render as R
    assert R._display_name("JOHN ALCARAS BSc CEng MIEI") == "John Alcaras"
    assert R._display_name("SEAN O'BRIEN-MCCARTHY") == "Sean O'Brien-McCarthy"
    assert R._display_name("Kate FitzGerald CEng MIEI") == "Kate FitzGerald"
    assert R._display_title("Lead / Senior Structural Engineer ...") == "Lead / Senior Structural Engineer"


def test_employer_recovery_rejects_membership_and_lowercase_captures():
    from gtm_client_workflows.gaia_sourcing.layers.extract import employer_from_own_text
    assert employer_from_own_text(
        "He is a Fellow of Engineers Ireland, speaks at Croke Park events.") is None
    assert employer_from_own_text("engineer at several irish firms") is None
    assert employer_from_own_text("Director at our dublin office") is None


def test_bare_name_strips_postnominals_for_the_grade_scan():
    assert gates._bare_name("JOHN ALCARAS BSc CEng MIEI") == "john alcaras"
    assert gates._bare_name("Kate FitzGerald") == "kate fitzgerald"


def test_inferred_grade_scan_stops_at_the_sentence_end():
    claims = [_vc("employer", "x",
                  "Mark Clyne, Senior Engineer. John Smith, Director of Everything.",
                  confidence="inferred")]
    grade = gates._grade_of(_person("Mark Clyne", None), claims)
    assert grade[0] == "senior_engineer"


def test_dotted_miei_counts_as_engineers_ireland_membership():
    claims = [_vc("chartership", "x", "Michael Shortall C.Eng., M.I.E.I.")]
    assert gates.check_chartered(_person("Michael Shortall"), claims, {}).passed is True
