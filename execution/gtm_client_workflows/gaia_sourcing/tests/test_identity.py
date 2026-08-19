"""
Who someone works for, and how their name is spelled on the card.

Both of these reached the client-facing artifact wrong, and neither failed
loudly. The delivered pool map carried four Role 2 candidates whose employer
was a division, a scheme or a city -- "Environment", "Tunnels and Underground
Infrastructure", "MetroLink", "Dublin" -- and the client-side sidebar named
the national rail operator as "Iarnr'd ireann", a misspelling the source
document never contained.

Every case below is taken verbatim from the 2026-08-19 run.
"""

from __future__ import annotations

import pytest

from gtm_client_workflows.gaia_sourcing import run as R
from gtm_client_workflows.gaia_sourcing.render.render import repair

FFFD = "�"


# ---------------------------------------------------------------------------
# The employer is not whatever follows the last preposition
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("assertion,expected", [
    # "Employed by X as <title> of <division>". The last preposition points at
    # the DIVISION, and four delivered candidates carried one as an employer.
    ("Employed by Jacobs as Senior Associate Director of Environment", "Jacobs"),
    ("Employed by Jacobs as European Head of Technology, Tunnel Ventilation "
     "and Fire Life Safety for Tunnels and Underground Infrastructure", "Jacobs"),
    ("Employed by Transport Infrastructure Ireland (TII) as Head of Land & "
     "Property Services", "Transport Infrastructure Ireland (TII)"),
    # The possessive names the employer; the tail names the scheme.
    ("Employed as TII's Project Director for MetroLink", "TII"),
    # A possessive division tail reduces to the firm.
    ("Colin Wyllie is an Associate Director in Jacobs' Transport Planning team",
     "Jacobs"),
    # The shape the "last preposition wins" rule was written for still works.
    ("Senior Associate Director of Highways in Jacobs", "Jacobs"),
    ("Susie Coyle is an Associate Director at Jacobs.", "Jacobs"),
    ("I am an Associate Director in Jacobs", "Jacobs"),
    ("She is a Director of Roughan & O Donovan.", "Roughan & O Donovan"),
    ("Programme Manager in the Capital Investments division of Iarnrod Eireann",
     "Iarnrod Eireann"),
    # An initialism in brackets is part of the name, not a terminator.
    ("Bryn Coldrick is a Senior Consultant with Archaeological Management "
     "Solutions (AMS)", "Archaeological Management Solutions (AMS)"),
])
def test_employer_is_read_from_the_strongest_cue(assertion, expected):
    assert R._employer_from_claim(assertion) == expected


@pytest.mark.parametrize("assertion", [
    # A city is where someone works, not who they work for.
    "Currently leader of the Arup maritime engineering team in Dublin.",
    "Rouslan Taskov is a Director based in the Dublin office",
    "He leads the Structures team",
    "He holds a degree in civil engineering.",
])
def test_a_place_or_an_org_chart_position_is_not_an_employer(assertion):
    assert R._employer_from_claim(assertion) is None


@pytest.mark.parametrize("raw,expected", [
    ("Jacobs' Transport Planning team", "Jacobs"),
    ("Jacobs", "Jacobs"),
    ("Dublin", None),
    ("Ireland", None),
    ("Environment", "Environment"),   # rejected upstream, not by shape
    ("the Dublin office", None),
    ("A", None),
    ("One Two Three Four Five Six Seven", None),
])
def test_employer_name_cleaning(raw, expected):
    assert R._clean_employer_name(raw) == expected


def test_the_employment_verb_is_matched_at_the_start_of_a_sentence():
    """Claims routinely open with it. A lowercase-only literal matched almost
    none of them -- the same flag omission that killed acp.name_from_text."""
    assert R._employer_from_claim("Employed by Jacobs as a Director") == "Jacobs"
    assert R._employer_from_claim("employed by Jacobs as a Director") == "Jacobs"


def test_the_capture_itself_is_not_case_folded():
    """A blanket re.I would fold [A-Z] too, and any lowercase run after the
    verb would be captured as an organisation."""
    assert R._employer_from_claim("employed by the same team as her colleague") is None


# ---------------------------------------------------------------------------
# The identity that reaches the card
# ---------------------------------------------------------------------------


def _one_person(tmp_path, monkeypatch, employer_hint, claims):
    monkeypatch.setattr(R, "RUN_DIR", tmp_path)
    monkeypatch.setattr(R, "DOCS", tmp_path / "docs.jsonl")
    R.save("extract", {
        "persons": {"p": {
            "person_id": "p", "full_name": "Test Person", "current_title": None,
            "current_employer": employer_hint, "location": None, "doc_ids": ["d1"],
            "linkedin_url": None, "role_id": "role2_transport_major_projects_manager",
            "source": "acp_witness_statement",
        }},
        "claims": [], "extracted_doc_ids": ["d1"],
    })
    R.save("validate", {"claims": [
        {"claim_id": "c" + str(i), "subject_person_id": "p", "dimension": "employer",
         "assertion": a, "evidence_quote": "a quote long enough to pass",
         "source_doc_id": "d1", "source_url": "https://example.ie/p",
         "confidence": "direct", "quote_verified": True}
        for i, a in enumerate(claims)
    ], "stats": {}})
    persons, _, _ = R._persons_and_claims()
    return persons["p"].current_employer


def test_every_employer_claim_is_tried_not_only_the_first(tmp_path, monkeypatch):
    """The first claim is often the one naming a city or a past employer.
    Stopping there fell back to the model hint, which is how "Dublin" reached
    the employer field on a delivered pool map."""
    got = _one_person(tmp_path, monkeypatch, "Dublin", [
        "Currently leader of the Arup maritime engineering team in Dublin.",
        "Employed by Arup as a Maritime Engineer",
    ])

    assert got == "Arup"


def test_an_unusable_model_hint_is_dropped_rather_than_printed(tmp_path, monkeypatch):
    """The L5 hint is a guess with no evidence contract behind it. Unfiltered
    it supplied "Environment", "Tunnels and Underground Infrastructure" and
    "Dublin" as employers."""
    assert _one_person(tmp_path, monkeypatch, "Dublin", []) is None
    assert _one_person(tmp_path, monkeypatch, "the Dublin office", []) is None


def test_a_usable_model_hint_still_survives(tmp_path, monkeypatch):
    assert _one_person(tmp_path, monkeypatch, "Jacobs", []) == "Jacobs"


# ---------------------------------------------------------------------------
# Mojibake: repair what is recoverable, show what is not
# ---------------------------------------------------------------------------


def test_a_lost_fada_is_not_turned_into_an_apostrophe():
    """"between two letters" is not the rule -- a mis-decoded fada is between
    two letters too. Blanket substitution printed the national rail operator
    as "Iarnr'd", inventing a misspelling the source never contained."""
    got = repair("Iarnr" + FFFD + "d " + FFFD + "ireann")

    assert got == "Iarnród Éireann"
    assert "’" not in got


def test_a_mis_decoded_apostrophe_is_still_repaired():
    """Printing U+FFFD on a card that promises verbatim quotes undermines the
    one thing the card promises."""
    assert repair("Michael O" + FFFD + "Reilly") == "Michael O’Reilly"


@pytest.mark.parametrize("raw,expected", [
    ("An Coimisi" + FFFD + "n Plean" + FFFD + "la", "An Coimisiún Pleanála"),
    ("An Bord Plean" + FFFD + "la", "An Bord Pleanála"),
])
def test_known_irish_bodies_are_restored_by_name(raw, expected):
    assert repair(raw) == expected


def test_an_unrecoverable_corruption_stays_visible():
    """There is no general way to recover which letter a U+FFFD used to be.
    An unexplained corruption should look corrupted rather than be silently
    papered over with a plausible guess."""
    assert repair("Se" + FFFD + "n Murphy") == "Se" + FFFD + "n Murphy"


def test_clean_text_is_untouched():
    assert repair("Iarnród Éireann") == "Iarnród Éireann"
    assert repair("") == ""


# ---------------------------------------------------------------------------
# Two more from the second delivered run
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw", [
    "Ireland and the Netherlands",
    "Dublin and Cork",
    "Ireland & UK",
])
def test_several_places_joined_together_are_still_just_places(raw):
    """From "worked on projects around the coast of Ireland and the
    Netherlands". A single place was rejected; a list of them was not, and it
    reached a delivered card as an employer."""
    assert R._clean_employer_name(raw) is None


def test_a_firm_whose_name_contains_a_place_still_survives():
    """The rejection is for names that are ONLY places."""
    assert R._clean_employer_name("Cork City Consulting Engineers") is not None
    assert R._clean_employer_name("Roughan & O Donovan") == "Roughan & O Donovan"
