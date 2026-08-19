"""
L8 / L9 / L10 -- the layers whose output is a claim about our own confidence.

These three share a failure mode that unit tests on their happy paths cannot
see: when the upstream call fails, each is capable of producing an answer that
LOOKS like a finding. An adversarial pass that errored is not an adversarial
pass that found nothing. A Prospeo miss is not an unverified address. A
movability model that returned nothing is not "low".

Every test here replaces the network call with a fake, so the assertion is
about what the layer says when the world misbehaves.
"""

from __future__ import annotations

import pytest

from gtm_client_workflows.gaia_sourcing.core.contracts import (
    GateResult,
    Person,
    ValidatedClaim,
)
from gtm_client_workflows.gaia_sourcing.layers import adversarial, contact, movability
from gtm_client_workflows.gaia_sourcing.roles import ROLE1, ROLE2


def _vc(pid: str, dimension: str, assertion: str, quote: str,
        confidence: str = "direct") -> ValidatedClaim:
    return ValidatedClaim(
        claim_id=pid + dimension + quote[:6],
        subject_person_id=pid,
        dimension=dimension,
        assertion=assertion,
        evidence_quote=quote,
        source_doc_id="d1",
        source_url="https://example.ie/p",
        confidence=confidence,
        quote_verified=True,
    )


@pytest.fixture
def person() -> Person:
    return Person(
        person_id="sc",
        full_name="Susie Coyle",
        current_title="Associate Director",
        current_employer="Jacobs",
    )


# ===========================================================================
# L9 -- contact. I5: verified / catch_all / pattern_guess / none never collapse.
# ===========================================================================


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(contact.time, "sleep", lambda *_: None)


def _prospeo(monkeypatch, payload, status="ok"):
    monkeypatch.setattr(contact, "_post", lambda url, body, timeout=60: (payload, status))


def _hit(email: str, upstream: str, revealed: bool = True) -> dict:
    return {
        "person": {
            "email": {"email": email, "status": upstream, "revealed": revealed,
                      "verification_method": "SMTP"},
            "linkedin_url": "https://www.linkedin.com/in/susie-coyle",
        }
    }


@pytest.mark.parametrize("upstream,expected", [
    ("VERIFIED", "verified"),
    ("VALID", "verified"),
    ("ACCEPT_ALL", "catch_all"),
    ("CATCH_ALL", "catch_all"),
    ("RISKY", "catch_all"),
    ("UNKNOWN", "pattern_guess"),
    ("UNVERIFIED", "pattern_guess"),
])
def test_upstream_statuses_map_to_four_distinct_labels(
    monkeypatch, person, upstream, expected
):
    _prospeo(monkeypatch, _hit("susie.coyle@jacobs.com", upstream))
    assert contact.enrich(person).email_status == expected


def test_an_unrecognised_upstream_status_degrades_downward(monkeypatch, person):
    """A label we do not understand must never be read as confirmation.

    Sending on a mislabelled address and bouncing at 5%+ hands the client a
    domain-reputation liability, which is exactly the kind of thing an MD
    remembers.
    """
    _prospeo(monkeypatch, _hit("susie.coyle@jacobs.com", "SOME_NEW_STATUS_2027"))

    rec = contact.enrich(person)

    assert rec.email_status == "pattern_guess"
    assert rec.email_status != "verified"


@pytest.mark.parametrize("email,revealed", [
    ("susie.*****@jacobs.com", True),   # masked by the provider
    ("susie.coyle@jacobs.com", False),  # withheld pending an unlock
])
def test_a_masked_address_is_not_an_address(monkeypatch, person, email, revealed):
    """It is reported as no-hit rather than shipped as something to send to."""
    _prospeo(monkeypatch, _hit(email, "VERIFIED", revealed=revealed))

    rec = contact.enrich(person)

    assert rec.email is None or "*" not in rec.email
    assert rec.email_status != "verified"


def test_a_provider_miss_falls_back_to_a_labelled_guess(monkeypatch, person):
    """A miss arrives as HTTP 400 NO_MATCH -- a normal outcome, not an outage."""
    _prospeo(monkeypatch, None, status="no_match")

    rec = contact.enrich(person)

    assert rec.email == "susie.coyle@jacobs.com"
    assert rec.email_status == "pattern_guess"
    assert "pattern inference" in (rec.email_provider or "")


def test_a_provider_outage_never_produces_a_confident_label(monkeypatch, person):
    _prospeo(monkeypatch, None, status="error")

    assert contact.enrich(person).email_status == "pattern_guess"


def test_no_employer_means_no_guess_at_all(monkeypatch):
    """Guessing a domain we have never resolved compounds one guess with another."""
    _prospeo(monkeypatch, None, status="no_match")
    nobody = Person(person_id="x", full_name="Anon Person")

    rec = contact.enrich(nobody)

    assert rec.email is None
    assert rec.email_status == "none"


def test_a_single_word_name_is_not_split_into_a_guess(monkeypatch):
    _prospeo(monkeypatch, None, status="no_match")
    mono = Person(person_id="x", full_name="Cher", current_employer="Jacobs")

    rec = contact.enrich(mono)

    assert rec.email is None and rec.email_status == "none"


def test_accents_reduce_to_an_ascii_local_part(monkeypatch):
    _prospeo(monkeypatch, None, status="no_match")
    p = Person(person_id="mo", full_name="Máire Ó Briain", current_employer="Jacobs")

    assert contact.enrich(p).email == "maire.briain@jacobs.com"


def test_linkedin_is_the_recommended_first_channel(monkeypatch, person):
    """I8. Emailing someone at their employer's mailbox about leaving that
    employer is monitored mail and poor tradecraft."""
    _prospeo(monkeypatch, _hit("susie.coyle@jacobs.com", "VERIFIED"))

    rec = contact.enrich(person)

    assert rec.recommended_first_channel == "linkedin"
    assert "LinkedIn first" in rec.channel_rationale


def test_a_catch_all_says_a_non_reply_is_uninformative(monkeypatch, person):
    """The label has to carry its own operating instruction to be useful."""
    _prospeo(monkeypatch, _hit("susie.coyle@jacobs.com", "ACCEPT_ALL"))

    assert "NOT confirmed deliverable" in contact.enrich(person).channel_rationale


def test_the_layer_never_asserts_linkedin_liveness(monkeypatch, person):
    """L12 owns liveness. L9 claiming it would be an unchecked assertion."""
    _prospeo(monkeypatch, _hit("susie.coyle@jacobs.com", "VERIFIED"))

    assert contact.enrich(person).linkedin_live is False


def test_a_hit_and_a_miss_are_counted_separately(monkeypatch, person):
    before = contact.run_stats()
    _prospeo(monkeypatch, _hit("susie.coyle@jacobs.com", "VERIFIED"))
    contact.enrich(person)
    _prospeo(monkeypatch, None, status="no_match")
    contact.enrich(person)

    after = contact.run_stats()
    assert after["hits"] == before["hits"] + 1
    assert after["no_match"] == before["no_match"] + 1


@pytest.mark.parametrize("employer,domain", [
    ("Jacobs", "jacobs.com"),
    ("jacobs engineering", "jacobs.com"),   # fuzzy, both directions
    ("Arup", "arup.com"),
    ("A Firm We Have Never Fetched", None),
])
def test_employer_domain_lookup(employer, domain):
    assert contact._employer_domain(employer) == domain


def test_employer_domains_are_derived_from_the_live_firm_list():
    """A standalone copy of this table drifted the moment company_bios was
    corrected, and a stale domain silently turns a real lookup into a guess."""
    from gtm_client_workflows.gaia_sourcing.sources.company_bios import FIRMS

    for firm in FIRMS:
        assert contact._EMPLOYER_DOMAINS[firm.name.lower()] == firm.domain


@pytest.mark.parametrize("url,expected", [
    ("https://www.jacobs.com/team/x", "jacobs.com"),
    ("https://arup.com/", "arup.com"),
    (None, None),
])
def test_domain_of(url, expected):
    assert contact.domain_of(url) == expected


# ===========================================================================
# L10 -- movability. "unknown" is the default, not the fallback.
# ===========================================================================


def _judge(monkeypatch, out):
    monkeypatch.setattr(
        movability, "call_role",
        lambda **kw: (out, {"provider": "test", "model": "test", "cost_eur": 0.0}),
    )


def test_a_failed_call_yields_unknown_not_a_guess(monkeypatch, person):
    def boom(**kw):
        raise RuntimeError("judge unavailable")

    monkeypatch.setattr(movability, "call_role", boom)

    sig = movability.assess(person, [], ROLE2)

    assert sig.assessment == "unknown"
    assert "treat it as unknown" in sig.rationale


def test_an_empty_result_yields_unknown(monkeypatch, person):
    _judge(monkeypatch, None)
    assert movability.assess(person, [], ROLE2).assessment == "unknown"


def test_a_confident_assessment_with_no_signals_is_downgraded(monkeypatch, person):
    """"A movability field that always returns a confident answer is a
    movability field nobody believes." Downgraded here rather than shipped."""
    _judge(monkeypatch, {"assessment": "high", "signals": [], "rationale": "Feels open."})

    assert movability.assess(person, [], ROLE2).assessment == "unknown"


def test_an_assessment_outside_the_enum_becomes_unknown(monkeypatch, person):
    _judge(monkeypatch, {"assessment": "very high", "signals": ["four years static"],
                         "rationale": "x"})

    assert movability.assess(person, [], ROLE2).assessment == "unknown"


@pytest.mark.parametrize("tenure", [0, -3, "eighteen", None])
def test_a_non_positive_tenure_is_recorded_as_unknown(monkeypatch, person, tenure):
    _judge(monkeypatch, {"assessment": "medium", "signals": ["s"], "rationale": "r",
                         "tenure_months_current": tenure})

    assert movability.assess(person, [], ROLE2).tenure_months_current is None


def test_a_real_signal_survives(monkeypatch, person):
    _judge(monkeypatch, {"assessment": "medium",
                         "signals": ["Four years in the same grade."],
                         "rationale": "Static for four years.",
                         "tenure_months_current": 48})

    sig = movability.assess(person, [], ROLE2)

    assert sig.assessment == "medium"
    assert sig.tenure_months_current == 48


def test_geographic_friction_is_computed_in_code_not_asked_of_the_model(person):
    """The single most actionable movability fact for a Cork role filled from
    Dublin, so it is deterministic rather than left to the model to remember."""
    claims = [_vc("sc", "location", "She is based in Dublin.", "based in Dublin")]

    note = movability.geographic_friction(person, claims, ROLE2)

    assert note is not None
    assert "Dublin" in note and "Cork" in note
    assert "relocate or commute" in note


def test_no_friction_when_the_candidate_is_already_in_the_roles_city(person):
    claims = [_vc("sc", "location", "She is based in Cork.", "based in Cork")]

    assert movability.geographic_friction(person, claims, ROLE2) is None


def test_no_friction_when_location_was_never_evidenced(person):
    assert movability.geographic_friction(person, [], ROLE2) is None


def test_friction_reaches_the_card_even_when_the_model_omits_it(monkeypatch, person):
    """A deterministic note the model forgot must not be lost."""
    _judge(monkeypatch, {"assessment": "medium", "signals": ["Four years static."],
                         "rationale": "Static for four years."})
    claims = [_vc("sc", "location", "She is based in Dublin.", "based in Dublin")]

    sig = movability.assess(person, claims, ROLE2)

    assert any("Cork" in s for s in sig.signals)
    assert "Cork" in sig.rationale


def test_friction_survives_a_failed_call(monkeypatch, person):
    monkeypatch.setattr(
        movability, "call_role",
        lambda **kw: (_ for _ in ()).throw(RuntimeError("down")),
    )
    claims = [_vc("sc", "location", "She is based in Dublin.", "based in Dublin")]

    sig = movability.assess(person, claims, ROLE2)

    assert sig.assessment == "unknown"
    assert any("Cork" in s for s in sig.signals)


# ===========================================================================
# L8 -- adversarial. A failed review must never read as a clean one.
# ===========================================================================


def _gates() -> list[GateResult]:
    return [GateResult(gate_id="chartered", passed=True)]


def test_a_failed_critique_says_review_incomplete(monkeypatch, person):
    """An adversarial pass that failed is NOT an adversarial pass that found
    nothing. The card must say so rather than imply a clean second opinion."""
    monkeypatch.setattr(
        adversarial, "call_role",
        lambda **kw: (_ for _ in ()).throw(RuntimeError("judge down")),
    )

    ev = adversarial.critique(person, [], ROLE2, {}, _gates(), "B")

    assert any("REVIEW INCOMPLETE" in f for f in ev.adversarial_findings)
    assert ev.tier == "B", "a failed review must not silently demote either"


def test_an_unparseable_critique_says_review_incomplete(monkeypatch, person):
    monkeypatch.setattr(adversarial, "call_role", lambda **kw: (None, {}))

    ev = adversarial.critique(person, [], ROLE2, {}, _gates(), "A")

    assert any("REVIEW INCOMPLETE" in f for f in ev.adversarial_findings)


def test_findings_returned_as_objects_are_flattened_not_dropped(monkeypatch, person):
    """One dict-shaped finding raised AttributeError and cost that candidate
    their entire second opinion -- the card then said REVIEW INCOMPLETE over a
    formatting detail. Unlike a claim, a finding carries no evidence contract
    to break, so the worst case is a clumsy sentence and the best case is a
    real objection that would otherwise have been lost."""
    monkeypatch.setattr(adversarial, "call_role", lambda **kw: ({
        "adversarial_findings": [
            {"finding": "No Eurocode evidence.", "severity": "minor"},
            "A plain string finding.",
            None,
            42,
        ],
        "unknowns": [], "strengths": [], "severity": "minor",
    }, {}))

    ev = adversarial.critique(person, [], ROLE2, {}, _gates(), "B")

    assert any("No Eurocode evidence." in f for f in ev.adversarial_findings)
    assert "A plain string finding." in ev.adversarial_findings
    assert all(isinstance(f, str) and f for f in ev.adversarial_findings)


def test_a_declared_material_severity_demotes_one_step(monkeypatch, person):
    monkeypatch.setattr(adversarial, "call_role", lambda **kw: ({
        "adversarial_findings": ["Something serious."], "unknowns": [],
        "strengths": [], "severity": "material",
    }, {}))

    assert adversarial.critique(person, [], ROLE2, {}, _gates(), "A").tier == "B"


def test_a_material_phrase_demotes_even_when_the_model_calls_it_minor(
    monkeypatch, person
):
    """I3: the model's severity is advisory. Demotion is deterministic so
    tiering stays reproducible."""
    monkeypatch.setattr(adversarial, "call_role", lambda **kw: ({
        "adversarial_findings": ["Appears to be based in Belfast."],
        "unknowns": [], "strengths": [], "severity": "minor",
    }, {}))

    assert adversarial.critique(person, [], ROLE2, {}, _gates(), "A").tier == "B"


def test_strengths_are_capped_so_a_card_cannot_become_a_sales_sheet(
    monkeypatch, person
):
    monkeypatch.setattr(adversarial, "call_role", lambda **kw: ({
        "adversarial_findings": [], "unknowns": [],
        "strengths": ["s1", "s2", "s3", "s4", "s5", "s6"], "severity": "none",
    }, {}))

    assert len(adversarial.critique(person, [], ROLE2, {}, _gates(), "B").strengths) == 4


def test_not_verified_lines_come_from_the_evidence_gap_not_the_models_mood():
    """Generated from what the evidence set actually lacks, so the section
    cannot quietly shrink when a model feels confident."""
    lines = adversarial.unverified_lines([], ROLE1, [])

    assert any("chartership not evidenced" in ln for ln in lines)
    assert any("Years of experience not stated" in ln for ln in lines)
    assert any("Eurocode" in ln for ln in lines)
    assert any("notice period" in ln for ln in lines)


def test_not_verified_names_the_right_primary_signal_per_role():
    r1 = adversarial.unverified_lines([], ROLE1, [])
    r2 = adversarial.unverified_lines([], ROLE2, [])

    assert any("Eurocode" in ln for ln in r1)
    assert any("Oral Hearing" in ln for ln in r2)


def test_an_evidenced_dimension_stops_claiming_it_is_missing():
    claims = [_vc("sc", "chartership", "Chartered.", "Chartered Engineer CEng MIEI")]

    lines = adversarial.unverified_lines(claims, ROLE1, [])

    assert not any("chartership not evidenced" in ln for ln in lines)


def test_an_inferred_claim_does_not_count_as_evidence_of_the_dimension():
    claims = [_vc("sc", "chartership", "Probably chartered.",
                  "listed among the senior engineers", confidence="inferred")]

    assert any("chartership not evidenced" in ln
               for ln in adversarial.unverified_lines(claims, ROLE1, []))


def test_inferred_claims_render_as_possible_and_unconfirmed():
    claims = [
        _vc("sc", "technical_skill", "Uses Tekla.", "modelled in Tekla",
            confidence="inferred"),
        _vc("sc", "chartership", "Chartered.", "Chartered Engineer CEng"),
    ]

    lines = adversarial.inferred_claim_lines(claims)

    assert lines == ["Possible, unconfirmed: Uses Tekla."]


# ---------------------------------------------------------------------------
# A string is iterable, and that is the entire bug
# ---------------------------------------------------------------------------


from gtm_client_workflows.gaia_sourcing.core.contracts import as_list  # noqa: E402


SHATTERED = '["His delivered project list and stated expertise.", "Second."]'


def test_a_json_encoded_list_is_parsed_not_walked_character_by_character():
    """Two delivered cards rendered their open-questions section as ONE BULLET
    PER CHARACTER -- 1651 and 1885 of them -- because the model returned the
    whole field as a JSON-encoded string and `for item in value` walks a str.

    Every space vanished too: a lone space fails the `if text` check, so the
    text was not merely mangled, it was unrecoverable from the stored output.
    """
    out = adversarial._lines(SHATTERED)

    assert out == ["His delivered project list and stated expertise.", "Second."]
    assert not any(len(x) == 1 for x in out)


def test_a_plain_sentence_is_one_finding_not_many_letters():
    assert adversarial._lines("A single finding, unencoded.") == [
        "A single finding, unencoded."]


@pytest.mark.parametrize("value,expected", [
    (None, []),
    ([], []),
    (["a", "b"], ["a", "b"]),
    ('["a", "b"]', ["a", "b"]),
    ("plain string", ["plain string"]),
    ('"just a json string"', ["just a json string"]),
    ("[malformed json", ["[malformed json"]),
    (42, [42]),
])
def test_as_list_coercion(value, expected):
    assert as_list(value) == expected


def test_movability_signals_survive_the_same_shape(monkeypatch, person):
    """The identical hazard lived here too: a signals field returned as a
    string would have produced one 'signal' per character."""
    _judge(monkeypatch, {"assessment": "medium",
                         "signals": '["Four years in the same grade."]',
                         "rationale": "Static."})

    sig = movability.assess(person, [], ROLE2)

    assert sig.signals == ["Four years in the same grade."]
    assert sig.assessment == "medium"


def test_a_critique_returned_as_a_string_still_produces_readable_findings(
    monkeypatch, person
):
    """End to end: the card must never show a wall of single letters."""
    monkeypatch.setattr(adversarial, "call_role", lambda **kw: ({
        "adversarial_findings": SHATTERED,
        "unknowns": '["Where is he based day to day?"]',
        "strengths": "Named design-code evidence.",
        "severity": "minor",
    }, {}))

    ev = adversarial.critique(person, [], ROLE2, {}, _gates(), "B")

    assert all(len(f) > 2 for f in ev.adversarial_findings)
    assert all(len(u) > 2 for u in ev.unknowns)
    assert ev.strengths == ["Named design-code evidence."]
