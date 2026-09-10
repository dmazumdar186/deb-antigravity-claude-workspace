"""
RADAR_CONTRACTS.md section C -- the two seniority-gate additions.

1. `_years_subject_is_person` / `require_subject_is_person`: a years figure
   only counts when the sentence it comes from is about the PERSON, not the
   firm. Opt-in (default off) so every pre-existing seniority test -- many of
   which use bare quotes like "20 years experience" with no pronoun or name
   at all -- keeps passing unchanged.
2. `require_corroboration` on the grade-inference branch of check_seniority:
   a title-only grade still passes (this gate is a floor, never a silent
   exclusion for an evidence gap), but the note says so plainly when nothing
   corroborates it.
"""

from __future__ import annotations

from gtm_client_workflows.gaia_sourcing.core.contracts import Person, ValidatedClaim
from gtm_client_workflows.gaia_sourcing.layers import gates


def _vc(dimension, assertion, quote, doc_id="d1", confidence="direct"):
    return ValidatedClaim(
        claim_id="c" + dimension + doc_id + quote[:6], subject_person_id="p",
        dimension=dimension, assertion=assertion, evidence_quote=quote,
        source_doc_id=doc_id, source_url="https://example.ie/p",
        confidence=confidence, quote_verified=True,
    )


def _person(title=None, full_name="Jane Doe"):
    return Person(person_id="p", full_name=full_name, current_title=title,
                  current_employer="ABC Consulting")


# ---------------------------------------------------------------------------
# _years_subject_is_person
# ---------------------------------------------------------------------------


def test_a_firm_subject_sentence_does_not_name_the_person():
    quote = "ABC Consulting has provided structural engineering since 1985."
    assert gates._years_subject_is_person(quote, _person()) is False


def test_a_first_person_pronoun_is_the_person():
    assert gates._years_subject_is_person("I have 3 years of experience", _person()) is True


def test_a_third_person_pronoun_is_the_person():
    assert gates._years_subject_is_person("She has 3 years of experience", _person()) is True


def test_the_persons_own_name_in_the_quote_is_the_person():
    quote = "Jane Doe has 3 years of experience at the firm."
    assert gates._years_subject_is_person(quote, _person(full_name="Jane Doe")) is True


# ---------------------------------------------------------------------------
# check_seniority: the firm-sentence fixture from RADAR_CONTRACTS.md
# ---------------------------------------------------------------------------


def test_firm_level_years_are_ignored_and_the_persons_own_figure_fails_the_floor():
    """ABC Consulting has provided structural engineering since 1985 (40
    years, firm-subject) + person's own quote of 3 years -> with the subject
    check on, the 40 is never counted and the floor fails on the real 3."""
    claims = [
        _vc("years_experience",
            "ABC Consulting has 40 years of combined experience.",
            "ABC Consulting has provided structural engineering since 1985, "
            "giving it 40 years of experience in the sector."),
        _vc("years_experience", "I have 3 years of experience.",
            "I have 3 years of experience in structural engineering."),
    ]

    result = gates.check_seniority(
        _person(), claims, {"min_years": 8, "require_subject_is_person": True}
    )

    assert result.passed is False
    assert "3 years" in (result.note or "")


def test_without_the_opt_in_the_firm_figure_still_wins_old_behaviour():
    """Existing behaviour is unchanged when the param is absent -- the same
    two claims, without require_subject_is_person, take the larger (wrong)
    40-year figure and pass. This pins the pre-existing behaviour so a
    regression in the opt-in wiring shows up as a DIFFERENT test breaking,
    not a silent behaviour change to the default path."""
    claims = [
        _vc("years_experience",
            "ABC Consulting has 40 years of combined experience.",
            "ABC Consulting has provided structural engineering since 1985, "
            "giving it 40 years of experience in the sector."),
        _vc("years_experience", "I have 3 years of experience.",
            "I have 3 years of experience in structural engineering."),
    ]

    result = gates.check_seniority(_person(), claims, {"min_years": 8})

    assert result.passed is True


def test_check_seniority_ceiling_also_ignores_a_firm_subject_years_claim():
    claims = [
        _vc("years_experience",
            "ABC Consulting has 40 years of combined experience.",
            "ABC Consulting has provided structural engineering since 1985, "
            "giving it 40 years of experience in the sector."),
        _vc("years_experience", "I have 3 years of experience.",
            "I have 3 years of experience in structural engineering."),
    ]

    result = gates.check_seniority_ceiling(
        _person(), claims, {"max_years": 18, "require_subject_is_person": True}
    )

    assert result.passed is True, "3 years is well under the ceiling once 40 is discarded"


# ---------------------------------------------------------------------------
# require_corroboration
# ---------------------------------------------------------------------------


def test_default_false_keeps_the_existing_single_title_note():
    result = gates.check_seniority(
        _person("Associate Director"), [], {"min_years": 8, "allow_grade_inference": True}
    )

    assert result.passed is True
    assert "inferred from grade" in (result.note or "").lower()


def test_require_corroboration_true_with_no_second_source_still_passes_but_flags_it():
    result = gates.check_seniority(
        _person("Associate Director"), [],
        {"min_years": 8, "allow_grade_inference": True, "require_corroboration": True},
    )

    assert result.passed is True
    assert result.note == "grade from one title only; confirm"


def test_require_corroboration_true_with_a_years_claim_present_passes_normally():
    """A years_experience claim exists (even an unparseable one) -- that
    alone corroborates the inferred grade."""
    claims = [_vc("years_experience", "Some years stated.",
                  "has worked here for quite a while now")]

    result = gates.check_seniority(
        _person("Associate Director"), claims,
        {"min_years": 8, "allow_grade_inference": True, "require_corroboration": True},
    )

    assert result.passed is True
    assert result.note != "grade from one title only; confirm"


def test_require_corroboration_true_with_a_second_independent_source_passes_normally():
    """The title says Associate Director; a SEPARATE employer-dimension claim
    (a different doc_id) independently says the same -- two sources, not
    one."""
    claims = [_vc("employer", "Associate Director at ABC Consulting.",
                  "I am an Associate Director in ABC Consulting", doc_id="d2")]

    result = gates.check_seniority(
        _person("Associate Director"), claims,
        {"min_years": 8, "allow_grade_inference": True, "require_corroboration": True},
    )

    assert result.passed is True
    assert result.note != "grade from one title only; confirm"
