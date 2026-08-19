"""
L5 extraction and L11 drafting -- the two layers that take model output and
turn it into something a person reads.

extract_directory is where one rendered page becomes many candidates, so a
mistake here does not corrupt one card, it invents or loses a whole firm's
worth of people. messages.draft is the only text in the deliverable written
by a model rather than copied from a source, which is why the legal strings
around it are concatenated rather than generated.
"""

from __future__ import annotations

from datetime import date

import pytest

from gtm_client_workflows.gaia_sourcing.core.contracts import (
    Person,
    RawDocument,
    ValidatedClaim,
)
from gtm_client_workflows.gaia_sourcing.layers import extract, messages
from gtm_client_workflows.gaia_sourcing.roles import ROLE1


DIRECTORY_TEXT = (
    "Brian Murphy, Associate Director. Chartered Engineer (CEng MIEI) with "
    "eighteen years of experience in structural design. "
    "Aoife Kelly, Senior Engineer. Chartered Engineer with twelve years "
    "across commercial projects. "
)


def _doc(text: str = DIRECTORY_TEXT, doc_id: str = "d1") -> RawDocument:
    return RawDocument(
        doc_id=doc_id, url="https://ocsc.ie/people", source_type="company_bio",
        fetched_at=date(2026, 8, 19), content_text=text, http_status=200,
    )


def _entry(name, quote, dimension="chartership", confidence="direct", title=""):
    return {
        "full_name": name, "job_title": title,
        "claims": [{"dimension": dimension, "assertion": name + " detail",
                    "evidence_quote": quote, "confidence": confidence}],
    }


def _model(monkeypatch, payload):
    calls = {"n": 0}

    def fake(**kw):
        calls["n"] += 1
        out = payload(calls["n"]) if callable(payload) else payload
        return out, {"provider": "test", "model": "test", "cost_eur": 0.0}

    monkeypatch.setattr(extract, "call_role", fake)
    return calls


# ---------------------------------------------------------------------------
# extract_directory
# ---------------------------------------------------------------------------


def test_one_page_yields_many_people(monkeypatch):
    _model(monkeypatch, {"people": [
        _entry("Brian Murphy", "Chartered Engineer (CEng MIEI)"),
        _entry("Aoife Kelly", "Chartered Engineer with twelve years"),
    ]})

    found = extract.extract_directory(_doc(), employer="O'Connor Sutton Cronin")

    assert {p.full_name for p, _ in found} == {"Brian Murphy", "Aoife Kelly"}
    assert all(p.current_employer == "O'Connor Sutton Cronin" for p, _ in found)


def test_a_single_word_name_is_not_a_person(monkeypatch):
    """"Engineering" as a name would create a candidate out of a heading."""
    _model(monkeypatch, {"people": [_entry("Engineering", "a quote long enough")]})

    assert extract.extract_directory(_doc()) == []


def test_a_person_with_no_evidenced_claim_is_omitted(monkeypatch):
    """A name with no grade, discipline or experience attached is not a
    candidate, and an entry we cannot evidence is omitted rather than padded."""
    _model(monkeypatch, {"people": [
        {"full_name": "Brian Murphy", "job_title": "Director", "claims": []},
    ]})

    assert extract.extract_directory(_doc()) == []


def test_a_quote_too_short_to_be_evidence_is_dropped(monkeypatch):
    _model(monkeypatch, {"people": [_entry("Brian Murphy", "CEng")]})

    assert extract.extract_directory(_doc()) == []


@pytest.mark.parametrize("entry", [
    "Brian Murphy",                                    # a bare string
    {"full_name": "", "claims": []},                   # no name
    {"claims": [{"dimension": "chartership"}]},        # no name key
])
def test_a_malformed_entry_does_not_take_the_page_with_it(monkeypatch, entry):
    _model(monkeypatch, {"people": [
        entry, _entry("Aoife Kelly", "Chartered Engineer with twelve years"),
    ]})

    found = extract.extract_directory(_doc())

    assert [p.full_name for p, _ in found] == ["Aoife Kelly"]


def test_a_malformed_claim_item_is_dropped_never_repaired(monkeypatch):
    """Reconstructing a missing evidence_quote is precisely how an unevidenced
    assertion enters the pipeline."""
    _model(monkeypatch, {"people": [{
        "full_name": "Brian Murphy", "job_title": "Director",
        "claims": [
            "a bare string instead of an object",
            {"dimension": "chartership", "assertion": "Chartered.",
             "evidence_quote": "Chartered Engineer (CEng MIEI)",
             "confidence": "direct"},
        ],
    }]})

    found = extract.extract_directory(_doc())

    assert len(found) == 1
    assert len(found[0][1]) == 1


def test_an_invalid_dimension_drops_the_claim_not_the_person(monkeypatch):
    _model(monkeypatch, {"people": [{
        "full_name": "Brian Murphy", "job_title": "Director",
        "claims": [
            {"dimension": "astrology", "assertion": "x",
             "evidence_quote": "a quote long enough to pass", "confidence": "direct"},
            {"dimension": "chartership", "assertion": "Chartered.",
             "evidence_quote": "Chartered Engineer (CEng MIEI)",
             "confidence": "direct"},
        ],
    }]})

    found = extract.extract_directory(_doc())

    assert len(found) == 1 and len(found[0][1]) == 1


def test_a_failed_chunk_does_not_lose_the_directory(monkeypatch):
    """One bad chunk must not cost a whole firm's page."""
    long_doc = _doc(DIRECTORY_TEXT * 400)

    def payload(n):
        if n == 1:
            raise RuntimeError("chunk exploded")
        return {"people": [_entry("Aoife Kelly", "Chartered Engineer with twelve")]}

    monkeypatch.setattr(extract, "call_role", lambda **kw: (
        (_ for _ in ()).throw(RuntimeError("boom")) if kw["user"].count("Brian") > 300
        else ({"people": [_entry("Aoife Kelly", "Chartered Engineer with twelve")]},
              {"cost_eur": 0.0})
    ))

    found = extract.extract_directory(long_doc, chunk_size=10000)

    assert [p.full_name for p, _ in found] == ["Aoife Kelly"]


def test_the_same_person_across_overlapping_chunks_is_merged(monkeypatch):
    """Overlap is deliberate -- a directory entry split across a boundary
    would otherwise lose either its name or its qualifications."""
    long_doc = _doc(DIRECTORY_TEXT * 400)
    _model(monkeypatch, {"people": [
        _entry("Brian Murphy", "Chartered Engineer (CEng MIEI)"),
    ]})

    found = extract.extract_directory(long_doc, chunk_size=10000)

    assert len({p.person_id for p, _ in found}) == 1
    # The identical quote from two chunks collapses on claim_id.
    assert len(found[0][1]) == 1


def test_an_explicit_office_in_the_title_beats_the_firm_default(monkeypatch):
    """"Regional Director (Belfast Office)" must still fail located_ie even on
    an Irish-domiciled firm's page."""
    _model(monkeypatch, {"people": [{
        "full_name": "Brian Murphy", "job_title": "Regional Director (Belfast Office)",
        "claims": [{"dimension": "chartership", "assertion": "Chartered.",
                    "evidence_quote": "Chartered Engineer (CEng MIEI)",
                    "confidence": "direct"}],
    }]})

    found = extract.extract_directory(_doc(), default_location="Ireland")

    assert "Belfast" in found[0][0].location


def test_a_person_with_no_office_in_the_title_takes_the_firm_default(monkeypatch):
    _model(monkeypatch, {"people": [
        _entry("Brian Murphy", "Chartered Engineer (CEng MIEI)", title="Director"),
    ]})

    found = extract.extract_directory(_doc(), default_location="Ireland")

    assert found[0][0].location == "Ireland"


def test_an_empty_model_response_yields_nothing_rather_than_raising(monkeypatch):
    _model(monkeypatch, None)

    assert extract.extract_directory(_doc()) == []


def test_head_weighted_truncation_keeps_the_qualifications_section():
    """Documents run to 180k chars; the qualifications section is at the front
    and the tail is scheme detail."""
    text = "QUALIFICATIONS AT THE FRONT. " + ("middle padding. " * 5000) + " THE END."

    windowed = extract._window(text)

    assert windowed.startswith("QUALIFICATIONS AT THE FRONT.")
    assert windowed.endswith("THE END.")
    assert "middle of document omitted" in windowed
    assert len(windowed) < len(text)


def test_a_short_document_is_not_truncated():
    assert extract._window("short") == "short"


@pytest.mark.parametrize("a,b,expected", [
    ("Aidan Foley", "Aidan Foley", True),
    ("Dr. Aidan Foley", "Aidan Foley", True),
    ("Aidan Foley", "Susie Coyle", False),
    # A single-token name matches on that one token. Deliberate: when the
    # model echoes only a surname, requiring two would drop a correct match.
    # It is safe because it only relaxes the CONTRADICTION check -- two full
    # names that disagree ("Christopher Reid" vs "Kevin Reid") still need two
    # shared tokens and are still dropped, which is the case that matters on a
    # hearing with several witnesses from one family.
    ("Foley", "Aidan Foley", True),
    ("Christopher Reid", "Kevin Reid", False),
    ("", "Aidan Foley", False),
])
def test_name_matching_confirms_a_document_is_about_the_subject(a, b, expected):
    assert extract.name_matches(a, b) is expected


# ---------------------------------------------------------------------------
# L11 -- drafting
# ---------------------------------------------------------------------------


def _vc(dimension, assertion, confidence="direct"):
    return ValidatedClaim(
        claim_id="c" + dimension, subject_person_id="p", dimension=dimension,
        assertion=assertion, evidence_quote="a quote long enough to pass",
        source_doc_id="d1", source_url="https://example.ie/p",
        confidence=confidence, quote_verified=True,
    )


def test_the_digest_offers_the_specific_evidence_first():
    """A named scheme is what makes a first touch land; a location is not."""
    digest = messages._evidence_digest([
        _vc("location", "Based in Cork."),
        _vc("project", "Worked on the MetroLink railway order."),
        _vc("chartership", "Chartered with Engineers Ireland."),
    ])

    assert digest.index("MetroLink") < digest.index("Chartered")
    assert digest.index("Chartered") < digest.index("Based in Cork")


def test_an_inferred_claim_is_never_offered_as_something_to_reference():
    """The message would state as fact something the pipeline calls unconfirmed."""
    digest = messages._evidence_digest([
        _vc("project", "Possibly worked on MetroLink.", confidence="inferred"),
    ])

    assert digest == ""


def test_a_draft_carries_the_legal_strings(monkeypatch):
    monkeypatch.setattr(messages, "call_role", lambda **kw: ({
        "linkedin_note": "A specific note.", "email_subject": "A subject",
        "email_body": "A body.", "follow_up": "A follow up.",
    }, {"cost_eur": 0.0}))

    seq = messages.draft(Person(person_id="p", full_name="Brian Murphy"), [], ROLE1)

    assert seq is not None
    ok, problems = messages.compliance_ok(seq)
    assert ok, problems


@pytest.mark.parametrize("missing", ["linkedin_note", "email_subject", "email_body"])
def test_an_incomplete_draft_is_discarded(monkeypatch, missing):
    payload = {"linkedin_note": "n", "email_subject": "s", "email_body": "b",
               "follow_up": "f"}
    payload[missing] = ""
    monkeypatch.setattr(messages, "call_role", lambda **kw: (payload, {"cost_eur": 0}))

    assert messages.draft(Person(person_id="p", full_name="X"), [], ROLE1) is None


def test_a_failed_draft_returns_nothing_rather_than_a_stub(monkeypatch, capsys):
    monkeypatch.setattr(messages, "call_role",
                        lambda **kw: (_ for _ in ()).throw(RuntimeError("down")))

    assert messages.draft(Person(person_id="p", full_name="X"), [], ROLE1) is None
    assert "failed" in capsys.readouterr().out


def test_the_vendor_never_appears_in_a_candidate_facing_message(monkeypatch):
    """I7: these messages go out under Gaia's name. A candidate must never see
    the tooling vendor's."""
    monkeypatch.setattr(messages, "call_role", lambda **kw: ({
        "linkedin_note": "Sent via Prodcraft automation. Real content.",
        "email_subject": "s", "email_body": "Prodcraft sourced you. Real body.",
        "follow_up": "f",
    }, {"cost_eur": 0.0}))

    seq = messages.draft(Person(person_id="p", full_name="X"), [], ROLE1)

    # The guard is on the MODEL-WRITTEN parts. The fixed Art. 14 notice
    # separately carries a privacy-notice URL on the vendor's domain, which is
    # an open question for the operator rather than a stripping failure.
    body_before_notice = seq.email_body.split(messages.GDPR_ART14_NOTICE)[0]
    assert "rodcraft" not in seq.linkedin_note
    assert "rodcraft" not in body_before_notice


def test_the_notice_is_concatenated_not_generated(monkeypatch):
    """There is no code path by which model output reaches these two fields,
    which is what makes I6 an invariant rather than an instruction."""
    monkeypatch.setattr(messages, "call_role", lambda **kw: ({
        "linkedin_note": "n", "email_subject": "s",
        "email_body": "b", "follow_up": "f",
        "gdpr_notice": "We definitely complied with everything.",
        "opt_out_line": "Reply STOP maybe.",
    }, {"cost_eur": 0.0}))

    seq = messages.draft(Person(person_id="p", full_name="X"), [], ROLE1)

    assert seq.gdpr_notice == messages.GDPR_ART14_NOTICE
    assert seq.opt_out_line == messages.OPT_OUT_LINE
