"""
Tests for integrations/recruit_crm.py. Zero network: every HTTP round trip
goes through a FakeSession whose `.request()` returns canned FakeResponses,
matching the real `requests.Session.request(method, url, headers=, params=,
json=, timeout=)` signature the client calls.
"""

from __future__ import annotations

import json as json_mod

import pytest

from gtm_client_workflows.gaia_sourcing.core.contracts import (
    CandidateCard,
    ContactRecord,
    Evaluation,
    GateResult,
    MovabilitySignal,
    ValidatedClaim,
)
from gtm_client_workflows.gaia_sourcing.integrations import recruit_crm as rc


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, headers=None, text=""):
        self.status_code = status_code
        self._json = {} if json_data is None else json_data
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._json


class FakeSession:
    """Serves canned responses in order. `responses` entries may be a
    FakeResponse or a callable(method, url, **kw) -> FakeResponse for cases
    that need to inspect the call (e.g. retry-then-succeed).
    """

    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls: list[dict] = []

    def request(self, method, url, headers=None, params=None, json=None, timeout=None):
        self.calls.append(
            {"method": method, "url": url, "headers": headers, "params": params,
             "json": json, "timeout": timeout}
        )
        resp = self.responses.pop(0)
        return resp(method, url, headers=headers, params=params, json=json,
                     timeout=timeout) if callable(resp) else resp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _card(pid="jd", tier="A", email_status="verified", email="j@x.ie",
          linkedin=None, role_id="role1"):
    claim = ValidatedClaim(
        claim_id="c1", subject_person_id=pid, dimension="chartership",
        assertion="Jane is chartered.",
        evidence_quote="Jane Doe is a Chartered Engineer (CEng MIEI)",
        source_doc_id="d1", source_url="https://example.ie/p", confidence="direct",
        quote_verified=True,
    )
    evaluation = Evaluation(
        person_id=pid, role_id=role_id, tier=tier,
        gates=[GateResult(gate_id="chartered", passed=True, note=None)],
        strengths=["Chartered with Engineers Ireland"],
    )
    contact = ContactRecord(
        person_id=pid, email=email, email_status=email_status,
        linkedin_url=linkedin,
    )
    mov = MovabilitySignal(person_id=pid, assessment="medium", rationale="Four years static.")
    card = CandidateCard(
        person_id=pid, full_name="Jane Doe", current_title="Senior Engineer",
        current_employer="Punch Consulting Engineers", location="Galway",
        role_id=role_id, tier=tier, claims=[claim], evaluation=evaluation,
        contact=contact, movability=mov,
    )
    return card, contact, mov


@pytest.fixture
def audit_path(tmp_path):
    return tmp_path / "audit.jsonl"


def _audit_lines(path):
    if not path.exists():
        return []
    return [json_mod.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# card_to_payload / evidence_note
# ---------------------------------------------------------------------------


def test_verified_email_is_included_in_the_payload():
    card, contact, _ = _card(email_status="verified", email="jane@punch.ie")
    payload = rc.card_to_payload(card, contact)
    assert payload["email"] == "jane@punch.ie"


def test_catch_all_email_is_included_in_the_payload():
    card, contact, _ = _card(email_status="catch_all", email="jane@punch.ie")
    payload = rc.card_to_payload(card, contact)
    assert payload["email"] == "jane@punch.ie"


def test_pattern_guess_email_is_omitted_from_the_payload():
    card, contact, _ = _card(email_status="pattern_guess", email="jane.doe@punch.ie")
    payload = rc.card_to_payload(card, contact)
    assert "email" not in payload


def test_no_email_status_is_omitted_from_the_payload():
    card, contact, _ = _card(email_status="none", email=None)
    payload = rc.card_to_payload(card, contact)
    assert "email" not in payload


def test_payload_carries_name_title_employer_location_and_source():
    card, contact, _ = _card()
    payload = rc.card_to_payload(card, contact, source="Prodcraft sourcing")
    assert payload["first_name"] == "Jane"
    assert payload["last_name"] == "Doe"
    assert payload["position"] == "Senior Engineer"
    assert payload["current_organization"] == "Punch Consulting Engineers"
    assert payload["city"] == "Galway"
    assert payload["candidate_source"] == "Prodcraft sourcing"


def test_evidence_note_carries_tier_gates_evidence_status_movability_and_art14():
    card, contact, mov = _card(email_status="pattern_guess", email="jane.doe@punch.ie")
    note = rc.evidence_note(card, contact, mov)
    assert "Tier A" in note
    assert "chartered: PASS" in note
    assert "Chartered Engineer (CEng MIEI)" in note  # verbatim quote survives
    assert "pattern_guess" in note
    assert "medium" in note and "Four years static." in note
    from gtm_client_workflows.gaia_sourcing.core.config import PRIVACY_NOTICE_URL
    assert "Art. 14 notice: " + PRIVACY_NOTICE_URL in note
    assert "outreach must include it" in note


# ---------------------------------------------------------------------------
# Dry-run: writes nothing, audits everything
# ---------------------------------------------------------------------------


def test_dry_run_never_calls_the_session_for_a_write(audit_path):
    card, contact, _ = _card()
    session = FakeSession([FakeResponse(200, {"data": []})])  # find_candidate lookup
    client = rc.RecruitCRMClient(live=False, session=session, audit_path=audit_path)

    result = client.upsert_candidate(card, contact)

    assert result["action"] == "created"
    assert result["candidate_id"] is None  # nothing was really created
    # The only session.request call was the dedupe GET; POST never happened.
    assert len(session.calls) == 1
    assert session.calls[0]["method"] == "GET"


def test_dry_run_logs_the_intended_write_to_the_audit_file(audit_path):
    card, contact, _ = _card()
    session = FakeSession([FakeResponse(200, {"data": []})])
    client = rc.RecruitCRMClient(live=False, session=session, audit_path=audit_path)

    client.upsert_candidate(card, contact)

    lines = _audit_lines(audit_path)
    writes = [l for l in lines if l.get("dry_run") is True]
    assert len(writes) == 1
    assert writes[0]["kind"] == "create"
    assert writes[0]["payload"]["first_name"] == "Jane"


def test_dry_run_note_and_attach_are_never_attempted_with_no_real_id(audit_path):
    from gtm_client_workflows.gaia_sourcing.integrations.recruit_crm import sync_delivery, SyncReport

    card, contact, mov = _card(role_id="role1")
    session = FakeSession([FakeResponse(200, {"data": []})])
    client = rc.RecruitCRMClient(live=False, session=session, audit_path=audit_path)

    report = sync_delivery([card], {card.person_id: contact}, {card.person_id: mov},
                            client, job_ids={"role1": "job-slug-1"})

    assert report.created == 1
    assert any("dry-run" in line for line in report.lines)
    # Only the one dedupe GET happened; no note/attach network call.
    assert len(session.calls) == 1


# ---------------------------------------------------------------------------
# Live requires a key
# ---------------------------------------------------------------------------


def test_live_requires_a_non_empty_api_key(monkeypatch, audit_path):
    monkeypatch.setattr(rc, "secret", lambda name, required=True: "")
    with pytest.raises(RuntimeError, match="RECRUIT_CRM_API_KEY"):
        rc.RecruitCRMClient(live=True, api_key=None, session=FakeSession([]),
                             audit_path=audit_path)


def test_live_with_an_explicit_api_key_does_not_raise(audit_path):
    client = rc.RecruitCRMClient(live=True, api_key="a-real-key",
                                  session=FakeSession([]), audit_path=audit_path)
    assert client.live is True


def test_the_api_key_never_appears_in_the_audit_log(audit_path):
    card, contact, _ = _card(email_status="verified", linkedin=None)
    session = FakeSession([
        FakeResponse(200, {"data": []}),           # find_candidate
        FakeResponse(201, {"slug": "cand-1"}),     # create
    ])
    client = rc.RecruitCRMClient(live=True, api_key="super-secret-token",
                                  session=session, audit_path=audit_path)

    client.upsert_candidate(card, contact)

    raw = audit_path.read_text(encoding="utf-8")
    assert "super-secret-token" not in raw


# ---------------------------------------------------------------------------
# Dedupe: finds existing by email, only fills empty fields
# ---------------------------------------------------------------------------


def test_dedupe_finds_existing_candidate_by_email(audit_path):
    card, contact, _ = _card(email_status="verified", email="jane@punch.ie")
    session = FakeSession([FakeResponse(200, {"data": [{"slug": "existing-1", "email": "jane@punch.ie"}]})])
    client = rc.RecruitCRMClient(live=True, api_key="k", session=session, audit_path=audit_path)

    existing = client.find_candidate(email="jane@punch.ie")

    assert existing["slug"] == "existing-1"
    assert session.calls[0]["params"] == {"email": "jane@punch.ie"}


def test_dedupe_with_neither_email_nor_linkedin_skips_the_lookup(audit_path):
    session = FakeSession([])
    client = rc.RecruitCRMClient(live=True, api_key="k", session=session, audit_path=audit_path)

    assert client.find_candidate() is None
    assert session.calls == []


def test_upsert_only_fills_empty_fields_on_an_existing_record(audit_path):
    """An existing record with SOME fields already set must keep them.

    `position` and `city` already exist on the CRM record (perhaps a
    consultant edited them); the patch must contain only the fields Recruit
    CRM has empty (`current_organization`, `candidate_source`) -- never
    overwrite the consultant's own data.
    """
    card, contact, _ = _card(email_status="verified", email="jane@punch.ie")
    existing = {
        "slug": "existing-1",
        "email": "jane@punch.ie",
        "position": "Consultant-edited title",  # already set -- must survive
        "city": "Galway",                        # already set -- must survive
        "current_organization": "",               # empty -- fair game
    }
    session = FakeSession([
        FakeResponse(200, {"data": [existing]}),   # find_candidate
        FakeResponse(200, {"slug": "existing-1"}),  # PUT update
    ])
    client = rc.RecruitCRMClient(live=True, api_key="k", session=session, audit_path=audit_path)

    result = client.upsert_candidate(card, contact)

    assert result["action"] == "updated"
    put_call = session.calls[1]
    assert put_call["method"] == "PUT"
    assert "position" not in put_call["json"]
    assert "city" not in put_call["json"]
    assert put_call["json"]["current_organization"] == "Punch Consulting Engineers"


def test_upsert_skips_the_write_when_the_existing_record_has_every_field(audit_path):
    card, contact, _ = _card(email_status="verified", email="jane@punch.ie")
    full_payload = rc.card_to_payload(card, contact)
    existing = {"slug": "existing-1", "email": "jane@punch.ie", **full_payload}
    session = FakeSession([FakeResponse(200, {"data": [existing]})])
    client = rc.RecruitCRMClient(live=True, api_key="k", session=session, audit_path=audit_path)

    result = client.upsert_candidate(card, contact)

    assert result["action"] == "skipped"
    assert len(session.calls) == 1  # only the dedupe GET -- no PUT sent


# ---------------------------------------------------------------------------
# Refuse a live write with nothing to dedupe on
# ---------------------------------------------------------------------------


def test_live_refuses_a_candidate_with_no_email_and_no_linkedin(audit_path):
    card, contact, _ = _card(email_status="none", email=None, linkedin=None)
    session = FakeSession([])
    client = rc.RecruitCRMClient(live=True, api_key="k", session=session, audit_path=audit_path)

    with pytest.raises(rc.NoDedupeKey):
        client.upsert_candidate(card, contact)
    assert session.calls == []  # refused before any network call


def test_dry_run_does_not_refuse_a_candidate_with_no_dedupe_key(audit_path):
    """The guardrail is a LIVE-write safety rail; dry-run has no duplication
    risk, so the intended write still lands in the audit log for review."""
    card, contact, _ = _card(email_status="none", email=None, linkedin=None)
    client = rc.RecruitCRMClient(live=False, session=FakeSession([]), audit_path=audit_path)

    result = client.upsert_candidate(card, contact)

    assert result["action"] == "created"


# ---------------------------------------------------------------------------
# Write cap
# ---------------------------------------------------------------------------


def test_write_cap_is_enforced(audit_path):
    card, contact, _ = _card(email_status="verified", email="jane@punch.ie")
    session = FakeSession([
        FakeResponse(200, {"data": []}),
        FakeResponse(201, {"slug": "c1"}),
    ])
    client = rc.RecruitCRMClient(live=True, api_key="k", session=session,
                                  audit_path=audit_path, max_writes_per_run=1)
    client.upsert_candidate(card, contact)  # 1st write: fine

    with pytest.raises(rc.WriteCapExceeded):
        client.add_note("c1", "second write, over the cap")


def test_write_cap_exceeded_propagates_out_of_sync_delivery(audit_path):
    """Same shape as core.providers.CostCeilingExceeded: never contained
    per-item, unlike an ordinary write failure."""
    card1, contact1, mov1 = _card(pid="p1", email="p1@x.ie")
    card2, contact2, mov2 = _card(pid="p2", email="p2@x.ie")
    session = FakeSession([
        FakeResponse(200, {"data": []}), FakeResponse(201, {"slug": "c1"}),
    ])
    client = rc.RecruitCRMClient(live=True, api_key="k", session=session,
                                  audit_path=audit_path, max_writes_per_run=1)

    with pytest.raises(rc.WriteCapExceeded):
        rc.sync_delivery(
            [card1, card2], {"p1": contact1, "p2": contact2},
            {"p1": mov1, "p2": mov2}, client, job_ids={},
        )


# ---------------------------------------------------------------------------
# 429 retry then success
# ---------------------------------------------------------------------------


def test_429_is_retried_and_then_succeeds(monkeypatch, audit_path):
    monkeypatch.setattr(rc.time, "sleep", lambda s: None)
    session = FakeSession([
        FakeResponse(429, headers={"Retry-After": "0"}),
        FakeResponse(200, {"data": [{"slug": "found-1"}]}),
    ])
    client = rc.RecruitCRMClient(live=True, api_key="k", session=session, audit_path=audit_path)

    result = client.find_candidate(email="jane@punch.ie")

    assert result["slug"] == "found-1"
    assert len(session.calls) == 2


def test_a_5xx_that_never_recovers_raises_after_max_retries(monkeypatch, audit_path):
    monkeypatch.setattr(rc.time, "sleep", lambda s: None)
    session = FakeSession([FakeResponse(503) for _ in range(10)])
    client = rc.RecruitCRMClient(live=True, api_key="k", session=session,
                                  audit_path=audit_path, max_retries=2)

    with pytest.raises(rc.RecruitCRMError):
        client.find_candidate(email="jane@punch.ie")
    assert len(session.calls) == 3  # 1 + max_retries


# ---------------------------------------------------------------------------
# Per-item containment inside a batch
# ---------------------------------------------------------------------------


def test_one_candidates_error_does_not_cost_the_batch(audit_path):
    good_card, good_contact, good_mov = _card(pid="good", email="good@x.ie")
    bad_card, bad_contact, bad_mov = _card(pid="bad", email="bad@x.ie")

    session = FakeSession([
        FakeResponse(200, {"data": []}), FakeResponse(500),  # bad: fails after retries=0
        FakeResponse(200, {"data": []}), FakeResponse(201, {"slug": "good-1"}),
    ])
    client = rc.RecruitCRMClient(live=True, api_key="k", session=session,
                                  audit_path=audit_path, max_retries=0)

    report = rc.sync_delivery(
        [bad_card, good_card], {"bad": bad_contact, "good": good_contact},
        {"bad": bad_mov, "good": good_mov}, client, job_ids={},
    )

    assert report.errors == 1
    assert report.created == 1
    assert any("ERROR" in line for line in report.lines)


def test_a_missing_contact_record_is_skipped_not_errored(audit_path):
    card, _, mov = _card(pid="p1")
    client = rc.RecruitCRMClient(live=False, session=FakeSession([]), audit_path=audit_path)

    report = rc.sync_delivery([card], {}, {"p1": mov}, client, job_ids={})

    assert report.skipped == 1
    assert report.errors == 0


def test_no_configured_job_id_skips_attach_but_still_counts_as_created(audit_path):
    card, contact, mov = _card(pid="p1", role_id="role1", email="p1@x.ie")
    session = FakeSession([
        FakeResponse(200, {"data": []}),
        FakeResponse(201, {"slug": "c1"}),
        FakeResponse(200, {}),  # add_note
    ])
    client = rc.RecruitCRMClient(live=True, api_key="k", session=session, audit_path=audit_path)

    report = rc.sync_delivery([card], {"p1": contact}, {"p1": mov}, client, job_ids={})

    assert report.created == 1
    assert any("attach_to_job skipped" in line for line in report.lines)
