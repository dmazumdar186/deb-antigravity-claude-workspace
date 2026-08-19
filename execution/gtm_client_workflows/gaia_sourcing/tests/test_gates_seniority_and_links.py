"""
The two deterministic layers a candidate's place on the list depends on.

L7's seniority check decides whether someone clears the experience bar, and it
has to read years out of prose written by other people -- "over 26 years post
graduate experience", "eighteen years", "since 2004". L12 decides what the
card says about a link, and the difference between "dead" and "could not be
checked" is the difference between a card the client trusts and one they stop
believing.
"""

from __future__ import annotations

import pytest

from gtm_client_workflows.gaia_sourcing.core.contracts import Person, ValidatedClaim
from gtm_client_workflows.gaia_sourcing.layers import gates, linkcheck
from gtm_client_workflows.gaia_sourcing.roles import ROLE1, ROLE2


def _vc(dimension, assertion, quote, confidence="direct"):
    return ValidatedClaim(
        claim_id="c" + dimension + quote[:6], subject_person_id="p",
        dimension=dimension, assertion=assertion, evidence_quote=quote,
        source_doc_id="d1", source_url="https://example.ie/p",
        confidence=confidence, quote_verified=True,
    )


# ---------------------------------------------------------------------------
# Reading years out of prose
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text,expected", [
    ("over 26 years post graduate experience", 26),
    ("18 years of experience", 18),
    ("has 8 years' experience", 8),
    ("30+ years experience", 30),
    # Witness statements and bios routinely spell the number out.
    ("eighteen years of experience", 18),
    ("twenty five years experience", 25),
    ("thirty years of experience in transport", 30),
    ("twelve years across commercial projects", 12),
])
def test_years_are_read_from_prose(text, expected):
    assert gates.extract_years(text) == expected


@pytest.mark.parametrize("text", [
    "graduated in 2024",             # a four-digit year is not a duration
    "the N6 scheme opened in 1999",
    "no numbers here at all",
    "",
])
def test_an_implausible_number_is_not_a_length_of_service(text):
    """Bounded at 60 so a stray four-digit year cannot satisfy the gate."""
    assert gates.extract_years(text) is None


def test_the_largest_plausible_figure_wins():
    """A bio often names both a total and a figure for one specialism."""
    assert gates.extract_years("8 years in bridges, 22 years overall") == 22


def test_a_worded_number_beats_a_smaller_digit():
    assert gates.extract_years("2 years here, twenty years in total") == 20


# ---------------------------------------------------------------------------
# Grade inference -- opt-in per role, and it must say so on the card
# ---------------------------------------------------------------------------


def _person(title=None):
    return Person(person_id="p", full_name="Brian Murphy", current_title=title,
                  current_employer="Punch Consulting Engineers")


def test_a_senior_grade_can_stand_in_for_a_stated_number_of_years():
    """Staff-directory bios state a GRADE, not a number. An Associate Director
    at an engineering consultancy is necessarily well past eight years."""
    result = gates.check_seniority(
        _person("Associate Director"), [], {"min_years": 8,
                                            "allow_grade_inference": True})

    assert result.passed is True
    assert result.note, "an inference must be disclosed on the card"


def test_the_inference_is_disclosed_rather_than_silently_counted():
    result = gates.check_seniority(
        _person("Technical Director"), [], {"min_years": 8,
                                            "allow_grade_inference": True})

    assert "infer" in (result.note or "").lower() or "grade" in (result.note or "").lower()


def test_role_2_does_not_allow_the_inference():
    """Witness statements open with a mandatory qualifications section that
    states years explicitly, so the stricter gate goes on the richer evidence."""
    result = gates.check_seniority(
        _person("Associate Director"), [], {"min_years": 10,
                                            "allow_grade_inference": False})

    assert result.passed is False


def test_a_grade_reachable_inside_eight_years_is_not_enough():
    """Deliberately excludes "Senior Engineer", reachable at about five years."""
    result = gates.check_seniority(
        _person("Senior Engineer"), [], {"min_years": 8,
                                         "allow_grade_inference": True})

    assert result.passed is False


def test_a_stated_number_below_the_bar_fails_even_with_a_senior_grade():
    """The evidenced number wins over the inference. A recently-promoted
    director who states six years is a six-year engineer."""
    claims = [_vc("years_experience", "Six years of experience.",
                  "I have 6 years of experience")]

    result = gates.check_seniority(
        _person("Associate Director"), claims,
        {"min_years": 8, "allow_grade_inference": True})

    assert result.passed is False


def test_an_inferred_claim_cannot_carry_the_seniority_gate():
    claims = [_vc("years_experience", "About twenty years.",
                  "roughly twenty years in the sector", confidence="inferred")]

    result = gates.check_seniority(_person(), claims, {"min_years": 8})

    assert result.passed is False


# ---------------------------------------------------------------------------
# L12 -- what a card is allowed to say about a link
# ---------------------------------------------------------------------------


def _head(monkeypatch, alive, status):
    monkeypatch.setattr(linkcheck, "head_ok",
                        lambda url, timeout=20: (alive, status))


def _body(monkeypatch, text):
    from datetime import date

    from gtm_client_workflows.gaia_sourcing.core.contracts import RawDocument

    monkeypatch.setattr(linkcheck, "fetch", lambda url: RawDocument(
        doc_id="d1", url="https://example.ie/p", source_type="company_bio",
        fetched_at=date(2026, 8, 19), content_text=text, http_status=200,
    ) if text is not None else None)


def test_a_live_page_that_still_names_the_person_matches(monkeypatch):
    _head(monkeypatch, True, 200)
    _body(monkeypatch, "Brian Murphy is an Associate Director here.")

    check = linkcheck.check_url("https://punch.ie/team/brian", "Brian Murphy")

    assert check.alive is True and check.name_matched is True


def test_a_live_page_that_no_longer_names_them_is_flagged_not_hidden(monkeypatch):
    """They may have moved on, which is a thing a consultant must know before
    opening a conversation."""
    _head(monkeypatch, True, 200)
    _body(monkeypatch, "Our team page. Aoife Kelly is an Associate Director.")

    check = linkcheck.check_url("https://punch.ie/team/brian", "Brian Murphy")

    assert check.name_matched is False
    assert "may have moved on" in check.note


def test_an_unreadable_body_is_recorded_as_unknown_not_as_matched(monkeypatch):
    """Asserting a match we did not perform is the failure this layer exists
    to prevent."""
    _head(monkeypatch, True, 200)
    _body(monkeypatch, None)

    check = linkcheck.check_url("https://punch.ie/team/brian.pdf", "Brian Murphy")

    assert check.alive is True
    assert check.name_matched is None
    assert "not readable" in check.note


def test_a_link_with_no_name_to_check_is_only_checked_for_liveness(monkeypatch):
    _head(monkeypatch, True, 200)

    def explode(url):
        raise AssertionError("must not fetch a body when no name was supplied")

    monkeypatch.setattr(linkcheck, "fetch", explode)

    assert linkcheck.check_url("https://pleanala.ie/x.pdf").alive is True


def test_evidence_links_are_checked_for_liveness_only(monkeypatch):
    """An ACP case bundle can serve the same URL for several people, so a name
    check there produces false alarms rather than signal."""
    _head(monkeypatch, True, 200)
    names_checked = []

    real = linkcheck.check_url

    def spy(url, full_name=None):
        names_checked.append(full_name)
        return linkcheck.LinkCheck(url=url, alive=True, http_status=200)

    monkeypatch.setattr(linkcheck, "check_url", spy)

    linkcheck.check_person("p", "Brian Murphy", "https://punch.ie/team/brian",
                           ["https://pleanala.ie/a.pdf", "https://pleanala.ie/b.pdf"])

    assert names_checked == ["Brian Murphy", None, None]


def test_a_url_serving_as_both_profile_and_evidence_is_checked_once(monkeypatch):
    _head(monkeypatch, True, 200)
    _body(monkeypatch, "Brian Murphy")

    report = linkcheck.check_person("p", "Brian Murphy", "https://punch.ie/x",
                                    ["https://punch.ie/x", "https://punch.ie/y"])

    assert len(report.checks) == 2


@pytest.mark.parametrize("page,expected", [
    ("Brian Murphy, Associate Director", True),
    ("Seán Ó Briain leads the team", False),          # different person
    ("Murphy is our director", False),                # surname alone is too weak
    ("B. Murphy, Associate Director", True),          # initialised forename
])
def test_name_matching_on_a_page_needs_more_than_a_surname(page, expected):
    assert linkcheck.page_mentions_name(page, "Brian Murphy") is expected


def test_the_match_is_token_based_and_says_so():
    """A deliberate looseness with a known cost.

    The check is "surname present AND at least one other token present",
    anywhere on the page, because pages write "Sean O'Brien", "Seán Ó Briain"
    and "S. O'Brien" for one person and an exact-string match would flag all
    three as gone. The cost is a false POSITIVE on a multi-person page that
    happens to carry both tokens separately -- "Brian Kelly" alongside "Sarah
    Murphy" reads as "Brian Murphy".

    That direction is the safe one to be wrong in: a false positive withholds
    a warning, while a false negative would print "they may have moved on"
    across perfectly good cards and teach the reader to ignore the notice.
    """
    assert linkcheck.page_mentions_name(
        "S. Murphy and Brian Kelly work here", "Brian Murphy") is True


def test_a_one_word_name_can_never_match_a_page():
    assert linkcheck.page_mentions_name("Cher is here", "Cher") is False
