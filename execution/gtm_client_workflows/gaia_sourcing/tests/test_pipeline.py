"""
Pipeline tests beyond the L6/L7 unit suite.

Every test here runs with ZERO network. The layers that call an LLM are tested
through their pure functions (prompt construction, assembly, compliance) rather
than by mocking a response, because what matters about those layers is what
they refuse to do, and that is decidable without a model.

Run from `execution/`:
    py -m pytest gtm_client_workflows/gaia_sourcing/tests/ -q
"""

from __future__ import annotations

import re
from datetime import date

import pytest

from gtm_client_workflows.gaia_sourcing.core.config import (
    GDPR_ART14_NOTICE,
    OPT_OUT_LINE,
)
from gtm_client_workflows.gaia_sourcing.core.contracts import (
    Claim,
    GateResult,
    Person,
    RawDocument,
    ValidatedClaim,
)
from gtm_client_workflows.gaia_sourcing.layers import (
    adversarial,
    contact,
    linkcheck,
    messages,
)
from gtm_client_workflows.gaia_sourcing.roles import (
    OFF_LIMITS,
    ROLE1,
    ROLE2,
    is_client_side,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DOC_TEXT = (
    "Sean O'Brien is a Chartered Engineer (CEng MIEI) with 14 years of "
    "experience in structural design. He led the Eurocode 2 design of the "
    "Ossory Pedestrian Bridge and is based in our Dublin office."
)


@pytest.fixture
def doc() -> RawDocument:
    return RawDocument(
        doc_id="doc_1",
        url="https://example.ie/people/sean-obrien",
        source_type="company_bio",
        fetched_at=date(2026, 8, 19),
        content_text=DOC_TEXT,
        http_status=200,
        title="Sean O'Brien",
    )


@pytest.fixture
def person() -> Person:
    return Person(
        person_id="sean_obrien",
        full_name="Sean O'Brien",
        current_title="Senior Structural Engineer",
        current_employer="Example Consulting Engineers",
        location="Ireland",
        doc_ids=["doc_1"],
    )


def _claim(dim: str, assertion: str, quote: str, confidence: str = "direct") -> ValidatedClaim:
    return ValidatedClaim(
        claim_id="clm_" + dim,
        subject_person_id="sean_obrien",
        dimension=dim,
        assertion=assertion,
        evidence_quote=quote,
        source_doc_id="doc_1",
        source_url="https://example.ie/people/sean-obrien",
        confidence=confidence,
        quote_verified=True,
    )


@pytest.fixture
def claims() -> list[ValidatedClaim]:
    return [
        _claim("chartership", "Chartered with Engineers Ireland.",
               "Chartered Engineer (CEng MIEI)"),
        _claim("years_experience", "14 years of experience.",
               "14 years of experience"),
        _claim("technical_skill", "Eurocode 2 design experience.",
               "led the Eurocode 2 design"),
    ]


# ---------------------------------------------------------------------------
# L8 blindness. The reason the second pass is worth paying for.
# ---------------------------------------------------------------------------


def test_adversarial_prompt_leaks_no_tier_letter(person, claims, doc):
    """The critique prompt must not disclose the first pass's verdict.

    If pass 2 can see that pass 1 said "Tier A", it agrees. A sycophantic
    second opinion costs money and buys nothing, so blindness is structural
    here: build_user_prompt takes no tier and no gate results at all.
    """
    prompt = adversarial.build_user_prompt(person, claims, ROLE1, {"doc_1": doc})

    # No verdict vocabulary at all.
    for banned in ("tier a", "tier b", "tier c", "tier:", "gate passed",
                   "gates passed", "all gates", "excluded", "shortlisted",
                   "recommended", "verdict"):
        assert banned not in prompt.lower(), (
            "adversarial prompt leaked '" + banned + "' -- pass 2 is no longer blind"
        )

    # And no bare tier letter presented as a grade.
    assert not re.search(r"\btier\b", prompt, re.I)


def test_adversarial_build_user_prompt_signature_cannot_receive_tier():
    """Blindness is enforced by the signature, not by a prompt instruction.

    A future edit that starts passing gate results into the prompt builder
    should fail this test rather than silently making pass 2 agreeable.
    """
    import inspect

    params = set(inspect.signature(adversarial.build_user_prompt).parameters)
    assert params == {"person", "claims", "spec", "corpus"}


def test_demotion_is_deterministic_and_one_step():
    assert adversarial._demote("A") == "B"
    assert adversarial._demote("B") == "C"
    assert adversarial._demote("C") == "C"  # floor, never EXCLUDED by a model


@pytest.mark.parametrize(
    "finding",
    [
        "Candidate appears to be based in Northern Ireland, not the Republic.",
        "There is no evidence of chartership with Engineers Ireland.",
        "This is a different discipline -- the bio describes highway drainage.",
        "Recently promoted, joined only this year.",
    ],
)
def test_material_findings_trigger_demotion(finding):
    assert adversarial._MATERIAL_RE.search(finding), (
        "a material finding that does not demote is a finding with no effect"
    )


def test_immaterial_finding_does_not_demote():
    assert not adversarial._MATERIAL_RE.search(
        "The bio does not state which software packages the candidate uses."
    )


# ---------------------------------------------------------------------------
# I6 -- legal text is injected, never generated
# ---------------------------------------------------------------------------


def test_assemble_injects_legal_strings_verbatim():
    seq = messages.assemble(
        "Short note.", "A subject", "A body about a bridge.", "A nudge."
    )
    assert seq.gdpr_notice == GDPR_ART14_NOTICE
    assert seq.opt_out_line == OPT_OUT_LINE
    assert GDPR_ART14_NOTICE in seq.email_body
    assert OPT_OUT_LINE in seq.email_body
    ok, problems = messages.compliance_ok(seq)
    assert ok, problems


def test_compliance_rejects_a_paraphrased_notice():
    """A paraphrased Article 14 notice is a non-compliant Article 14 notice."""
    seq = messages.assemble("Note.", "Subject", "Body.", "Nudge.")
    # A realistic paraphrase: one word changed, meaning apparently preserved.
    # That is exactly the edit a model makes and exactly the edit that must fail.
    paraphrased = GDPR_ART14_NOTICE.replace("legitimate interest", "legitimate interests")
    assert paraphrased != GDPR_ART14_NOTICE, "the tamper must actually change the text"
    tampered = seq.model_copy(update={"gdpr_notice": paraphrased})
    ok, problems = messages.compliance_ok(tampered)
    assert not ok
    assert any("altered" in p for p in problems)


def test_compliance_rejects_a_body_missing_the_opt_out():
    seq = messages.assemble("Note.", "Subject", "Body.", "Nudge.")
    stripped = seq.model_copy(
        update={"email_body": seq.email_body.replace(OPT_OUT_LINE, "")}
    )
    ok, problems = messages.compliance_ok(stripped)
    assert not ok


@pytest.mark.parametrize(
    "phrase",
    [
        "an exciting opportunity",
        "I'd love to connect",
        "I came across your profile",
        "hope this email finds you well",
    ],
)
def test_template_phrasings_are_stripped(phrase):
    """These mark a message as automated on sight, so they never survive."""
    cleaned = messages._clean("Hello. " + phrase + " about a bridge.")
    assert phrase.lower() not in cleaned.lower()


def test_vendor_self_reference_is_stripped():
    """I7 -- the candidate must never see the tooling vendor's name."""
    cleaned = messages._clean(
        "I work with Prodcraft on this search. We think you would suit the role."
    )
    assert "prodcraft" not in cleaned.lower()


# ---------------------------------------------------------------------------
# I5 -- contact-label honesty
# ---------------------------------------------------------------------------


def test_unknown_upstream_status_degrades_downward():
    """An upstream status we do not recognise must never become 'verified'.

    Prospeo can add a status string at any time. Mapping the unknown to the
    weakest label is the only safe direction: a guess presented as verified
    is how a consultant emails a mailbox that does not exist.
    """
    assert contact._STATUS_MAP.get("SOME_NEW_STATUS", "pattern_guess") == "pattern_guess"
    for upstream, label in contact._STATUS_MAP.items():
        assert label in ("verified", "catch_all", "pattern_guess")
        if label == "verified":
            assert upstream in ("VERIFIED", "VALID"), (
                upstream + " must not map to 'verified'"
            )


def test_pattern_fallback_is_never_labelled_verified(person):
    rec = contact._pattern_fallback(person, "example.ie")
    assert rec.email_status == "pattern_guess"
    assert rec.email is not None
    assert "verified" not in (rec.email_provider or "").lower()


def test_no_contact_is_status_none(person):
    rec = contact._no_contact(person, "no lookup key")
    assert rec.email is None
    assert rec.email_status == "none"


# ---------------------------------------------------------------------------
# L12 -- Irish surname handling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "page_text,name,expected",
    [
        ("Sean O'Brien, Director", "Sean O'Brien", True),
        ("Sean O Brien, Director", "Sean O'Brien", True),
        ("Sean OBrien, Director", "Sean O'Brien", True),
        ("Profile of Sean Brien", "Sean O'Brien", True),
        ("Aoife Mac Eoin heads the team", "Aoife Mac Eoin", True),
        ("Niamh Ni Chuinn, Associate", "Niamh Ni Chuinn", True),
        ("Murphy Construction Ltd", "Michael Murphy", False),
        ("Our people page lists many engineers", "Sean O'Brien", False),
    ],
)
def test_page_mentions_name(page_text, name, expected):
    assert linkcheck.page_mentions_name(page_text, name) is expected


def test_surname_alone_is_not_a_match():
    """"Murphy" appears on most Irish company pages; it cannot identify anyone."""
    assert not linkcheck.page_mentions_name("Contact Murphy today", "Michael Murphy")


# ---------------------------------------------------------------------------
# Off-limits and client-side classification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("employer", ["TOBIN Consulting Engineers", "AtkinsRéalis",
                                      "Atkins Realis", "atkins"])
def test_client_employers_are_off_limits(employer):
    assert any(o in employer.lower() for o in OFF_LIMITS)


@pytest.mark.parametrize(
    "employer,expected",
    [
        ("Transport Infrastructure Ireland", True),
        ("Cork City Council", True),
        ("National Transport Authority", True),
        ("Iarnrod Eireann", True),
        # Word-boundary matters: a bare "cie" substring matches these two.
        ("Agencies Ltd", False),
        ("Learned Societies Group", False),
        ("Roughan & O'Donovan", False),
    ],
)
def test_client_side_classification(employer, expected):
    assert is_client_side(employer) is expected


# ---------------------------------------------------------------------------
# Role specs -- the gates are the contract
# ---------------------------------------------------------------------------


def test_both_roles_have_every_hard_gate():
    for spec in (ROLE1, ROLE2):
        ids = {g.gate_id for g in spec.hard_gates}
        assert ids == {"chartered", "located_ie", "discipline", "seniority", "not_client"}


def test_role2_does_not_allow_grade_inference():
    """Role 2's sources state years explicitly, so the stricter gate is free."""
    gate = [g for g in ROLE2.hard_gates if g.gate_id == "seniority"][0]
    assert gate.params["allow_grade_inference"] is False
    assert gate.params["min_years"] == 10


def test_target_counts_match_the_brief():
    assert ROLE1.target_count == 10
    assert ROLE2.target_count == 5


# ---------------------------------------------------------------------------
# Regressions for two bugs found on 2026-08-19 during the first full run
# ---------------------------------------------------------------------------


def test_empty_parse_is_not_cached_as_a_valid_document(tmp_path, monkeypatch):
    """A 200 that yields no text is a failed fetch, not an empty document.

    An Coimisiun Pleanala publishes many image-only scanned PDFs: 1.1 MB of
    JPEG with no text layer. Cached as ok:true they became zero-length
    documents whose content hash is the SHA of the empty string, so 51
    distinct sources collapsed onto one doc_id. Nothing false shipped -- the
    validator fails closed against an empty document -- but the drop then
    reads as a hallucination instead of "this source was never readable".
    """
    from gtm_client_workflows.gaia_sourcing.core import cache

    class FakeResp:
        status_code = 200
        headers = {"Content-Type": "application/pdf"}
        content = b"%PDF-1.4 image only, no text layer"

    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(cache, "_throttle", lambda url: None)
    monkeypatch.setattr(cache.requests, "get", lambda *a, **k: FakeResp())
    # Whitespace only -- what PyMuPDF returns for an image-only scan.
    monkeypatch.setattr(cache, "_pdf_to_text", lambda raw: "      ")

    assert cache.fetch("https://example.ie/scan.pdf") is None

    metas = list(tmp_path.glob("*.meta.json"))
    assert len(metas) == 1
    import json as _json

    meta = _json.loads(metas[0].read_text(encoding="utf-8"))
    assert meta["ok"] is False
    assert meta["error"] == "empty_after_parse"


@pytest.mark.parametrize(
    "assertion,expected",
    [
        ("Susie Coyle is an Associate Director at Jacobs.", "Jacobs"),
        ("Aidan Foley is employed as a Senior Engineer with Transport "
         "Infrastructure Ireland.", "Transport Infrastructure Ireland"),
        ("She is a Director of Roughan & O Donovan.", "Roughan & O Donovan"),
        # Not an employer -- must not be mistaken for one.
        ("He holds a degree in civil engineering.", None),
    ],
)
def test_employer_comes_from_the_witness_own_words(assertion, expected):
    """The filename names the submitting PARTY, not the witness's employer.

    An oral-hearing document is titled "No.02 - TII - Witness Statement of
    Aidan Foley", but the witness is usually that party's consultant. Reading
    the party as the employer files half the transport pool as client-side and
    drops them from the shortlist for being the wrong kind of right person.
    """
    from gtm_client_workflows.gaia_sourcing.run import _employer_from_claim

    assert _employer_from_claim(assertion) == expected


# ---------------------------------------------------------------------------
# L5 subject confirmation -- the bug that zeroed an entire role
# ---------------------------------------------------------------------------


def _fake_call(payload):
    def _call(**kwargs):
        return payload, {"provider": "test", "model": "test", "cost_eur": 0.0,
                         "input_tokens": 0, "output_tokens": 0,
                         "cache_read_tokens": 0, "cache_write_tokens": 0}
    return _call


_GOOD_CLAIM = {
    "dimension": "statutory_process",
    "assertion": "Gave evidence at the oral hearing.",
    "evidence_quote": "I gave evidence at the oral hearing on 12 March",
    "confidence": "direct",
}


def test_known_subject_survives_a_missing_confirmation_echo(monkeypatch, doc, person):
    """A model that omits an optional field it was handed must not cost claims.

    On the 2026-08-19 run every one of the 19 oral-hearing statements returned
    good claims and no `subject_confirmed_name`, because the subject had been
    supplied in the prompt and the model saw no reason to repeat it. The guard
    treated the omission as "could not identify the subject" and discarded all
    of them, so Role 2 delivered zero candidates from a working source.
    """
    from gtm_client_workflows.gaia_sourcing.layers import extract as E

    monkeypatch.setattr(E, "call_role", _fake_call({"claims": [_GOOD_CLAIM]}))
    claims, hints = E.extract_from_document(person, doc)

    assert len(claims) == 1
    assert hints is not None
    assert hints["confirmed_name"] == person.full_name


def test_contradictory_confirmation_still_drops_everything(monkeypatch, doc, person):
    """An echo naming somebody else means the model read a different person."""
    from gtm_client_workflows.gaia_sourcing.layers import extract as E

    monkeypatch.setattr(
        E, "call_role",
        _fake_call({"subject_confirmed_name": "Aoife Kavanagh", "claims": [_GOOD_CLAIM]}),
    )
    claims, hints = E.extract_from_document(person, doc)

    assert claims == []
    assert hints is None


def test_subject_absent_from_the_document_drops_everything(monkeypatch, doc, person):
    """The deterministic check: the surname must actually be in the source."""
    from gtm_client_workflows.gaia_sourcing.core.contracts import Person
    from gtm_client_workflows.gaia_sourcing.layers import extract as E

    stranger = Person(person_id="x", full_name="Fionnuala Considine", doc_ids=["doc_1"])
    monkeypatch.setattr(E, "call_role", _fake_call({"claims": [_GOOD_CLAIM]}))
    claims, hints = E.extract_from_document(stranger, doc)

    assert claims == []
    assert hints is None


def test_unknown_subject_still_requires_a_name(monkeypatch, doc):
    """When identifying the author IS the task, no name means no subject."""
    from gtm_client_workflows.gaia_sourcing.core.contracts import Person
    from gtm_client_workflows.gaia_sourcing.layers import extract as E

    anon = Person(person_id="anon", full_name="UNKNOWN", doc_ids=["doc_1"])
    monkeypatch.setattr(E, "call_role", _fake_call({"claims": [_GOOD_CLAIM]}))
    claims, hints = E.extract_from_document(anon, doc)

    assert claims == []
    assert hints is None


# ---------------------------------------------------------------------------
# Source quality -- what may become a citation on a card
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        # Lead databases rank well for "<name> <firm>" and carry enough
        # engineering boilerplate to pass a keyword gate. The first run of the
        # technical-evidence plugin cited this exact page as evidence of a
        # candidate's design experience.
        "https://prospeo.io/c/barrett-mahony-consulting-engineers",
        "https://rocketreach.co/john-murphy-email",
        "https://www.zoominfo.com/p/Jane-Doe/123",
        "https://www.linkedin.com/in/someone",
        # Already extracted directly; re-finding it via search adds nothing
        # and produces duplicate claims.
        "https://ocsc.ie/people/",
        "https://www.barrettmahony.com/practice/team",
    ],
)
def test_blocked_sources_never_become_citations(url):
    from gtm_client_workflows.gaia_sourcing.sources import technical_evidence as T

    assert T._BLOCKED_SOURCE.search(url), url + " must never be cited"


@pytest.mark.parametrize(
    "url",
    [
        "https://www.acei.ie/wp-content/uploads/2026/06/ACEI_2026-yearbook.pdf",
        "https://www.engineersireland.ie/Engineers-Journal/second-generation-eurocodes",
        "https://arrow.tudublin.ie/engschcivcon/42/",
        "https://www.barrettmahony.com/projects/samuel-hayes-footbridge",
    ],
)
def test_legitimate_technical_sources_are_allowed(url):
    from gtm_client_workflows.gaia_sourcing.sources import technical_evidence as T

    assert not T._BLOCKED_SOURCE.search(url), url + " is a legitimate source"


def test_harvest_refuses_a_blocked_url_without_fetching(monkeypatch):
    """The block is re-checked at fetch time, after any redirect."""
    from gtm_client_workflows.gaia_sourcing.sources import technical_evidence as T

    calls = []
    monkeypatch.setattr(T, "fetch", lambda *a, **k: calls.append(a) or None)
    doc = T.TechDoc(url="https://prospeo.io/c/some-firm", person_id="p",
                    full_name="Sean O'Brien")
    assert T.harvest([doc]) == []
    assert calls == [], "a blocked URL must not even be fetched"


# ---------------------------------------------------------------------------
# Client-side detection must survive accents and mojibake
# ---------------------------------------------------------------------------

_FFFD = chr(0xFFFD)


@pytest.mark.parametrize(
    'employer',
    [
        'Iarnrod Eireann',
        'Iarnród Éireann',
        # What a cp1252-misread PDF actually yields. On the 2026-08-19 run this
        # exact string put a Programme Manager at the national rail operator
        # into the delivered shortlist instead of the SPEC 2.3 sidebar.
        'Programme Manager in the Capital Investments division of Iarnr' + _FFFD + 'd ' + _FFFD + 'ireann',
        'Uisce Éireann',
        'An Coimisiún Pleanála',
    ],
)
def test_client_side_survives_accents_and_mojibake(employer):
    assert is_client_side(employer) is True


@pytest.mark.parametrize(
    'employer',
    ['Jacobs', 'Agencies Ltd', "O'Connor Sutton Cronin",
     'Barrett Mahony Consulting Engineers', 'Horganlynch'],
)
def test_consultancies_are_not_client_side(employer):
    assert is_client_side(employer) is False
