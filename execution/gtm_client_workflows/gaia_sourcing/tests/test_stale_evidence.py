"""Tests for stale-evidence computation (layers/contact.py) and its
enforcement in integrations.recruit_crm.sync_delivery, plus that module's
opt-out check (RADAR_CONTRACTS.md section E). Zero network.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from gtm_client_workflows.gaia_sourcing.core.contracts import (
    CandidateCard,
    ContactRecord,
    Evaluation,
    MovabilitySignal,
    Person,
    RawDocument,
)
from gtm_client_workflows.gaia_sourcing.core.config import CONFIG
from gtm_client_workflows.gaia_sourcing.layers import contact, optout
from gtm_client_workflows.gaia_sourcing.integrations import recruit_crm as rc


def _doc(fetched_at: date, doc_id="d1") -> RawDocument:
    return RawDocument(
        doc_id=doc_id,
        url="https://example.ie/team/" + doc_id,
        source_type="company_bio",
        fetched_at=fetched_at,
        content_text="Some engineer bio text long enough to be plausible.",
        http_status=200,
    )


# ---------------------------------------------------------------------------
# evidence_age_days -- pure function
# ---------------------------------------------------------------------------


def test_no_docs_returns_none():
    assert contact.evidence_age_days("p1", []) is None


def test_age_computed_from_the_newest_doc():
    old = _doc(date.today() - timedelta(days=90), "old")
    new = _doc(date.today() - timedelta(days=5), "new")
    age = contact.evidence_age_days("p1", [old, new])
    assert age == 5


def test_age_zero_for_a_document_fetched_today():
    assert contact.evidence_age_days("p1", [_doc(date.today())]) == 0


# ---------------------------------------------------------------------------
# enrich() wiring -- ContactRecord.evidence_age_days / .stale
# ---------------------------------------------------------------------------


def _person(pid="p1"):
    return Person(person_id=pid, full_name="Nora Kelly", current_employer=None)


def test_enrich_without_docs_carries_no_age(monkeypatch):
    monkeypatch.setattr(contact, "_post", lambda url, body, timeout=60: (None, "no_match"))
    rec = contact.enrich(_person())
    assert rec.evidence_age_days is None
    assert rec.stale is False


def test_enrich_flags_stale_past_the_configured_ceiling(monkeypatch):
    monkeypatch.setattr(contact, "_post", lambda url, body, timeout=60: (None, "no_match"))
    old_doc = _doc(date.today() - timedelta(days=CONFIG.max_evidence_age_days + 1))
    rec = contact.enrich(_person(), employer_docs=[old_doc])
    assert rec.evidence_age_days == CONFIG.max_evidence_age_days + 1
    assert rec.stale is True


def test_enrich_not_stale_within_the_ceiling(monkeypatch):
    monkeypatch.setattr(contact, "_post", lambda url, body, timeout=60: (None, "no_match"))
    fresh_doc = _doc(date.today() - timedelta(days=1))
    rec = contact.enrich(_person(), employer_docs=[fresh_doc])
    assert rec.evidence_age_days == 1
    assert rec.stale is False


def test_stale_flag_survives_every_fallback_path(monkeypatch):
    """_no_contact and _pattern_fallback are the other two return points in
    enrich() -- both must carry the same age/stale values as the main path.
    """
    old_doc = _doc(date.today() - timedelta(days=CONFIG.max_evidence_age_days + 10))

    # Path 1: no lookup key at all -> _no_contact
    rec1 = contact.enrich(Person(person_id="p1", full_name="X"), employer_docs=[old_doc])
    assert rec1.stale is True
    assert rec1.evidence_age_days == CONFIG.max_evidence_age_days + 10

    # Path 2: no_match from Prospeo, no domain -> _pattern_fallback -> _no_contact
    monkeypatch.setattr(contact, "_post", lambda url, body, timeout=60: (None, "no_match"))
    rec2 = contact.enrich(_person(), employer_docs=[old_doc])
    assert rec2.stale is True

    # Path 3: no_match from Prospeo, WITH a resolvable domain -> _pattern_fallback guess
    p3 = Person(person_id="p3", full_name="Nora Kelly", current_employer="Jacobs")
    rec3 = contact.enrich(p3, employer_docs=[old_doc])
    assert rec3.email_status == "pattern_guess"
    assert rec3.stale is True
    assert rec3.evidence_age_days == CONFIG.max_evidence_age_days + 10


# ---------------------------------------------------------------------------
# integrations.recruit_crm.sync_delivery -- stale + opt-out gates
# ---------------------------------------------------------------------------


def _card(pid="p1", role_id="role-1"):
    return CandidateCard(
        person_id=pid,
        full_name="Nora Kelly",
        current_title="Senior Engineer",
        current_employer="Jacobs",
        location="Dublin",
        role_id=role_id,
        tier="A",
        claims=[],
        evaluation=Evaluation(person_id=pid, role_id=role_id, tier="A", gates=[]),
        contact=ContactRecord(person_id=pid),
        movability=MovabilitySignal(person_id=pid),
        outreach=None,
    )


class _RecordingClient:
    """Stands in for RecruitCRMClient: records whether upsert_candidate was
    ever called, without needing a real session/HTTP layer.
    """

    live = False

    def __init__(self):
        self.calls = []

    def upsert_candidate(self, card, contact, evidence_summary=""):
        self.calls.append(card.person_id)
        return {"action": "created", "candidate_id": "crm-" + card.person_id}

    def add_note(self, candidate_id, text):
        return None

    def attach_to_job(self, candidate_id, job_id, stage=None):
        return None


def test_stale_contact_blocks_sync_by_default():
    card = _card()
    stale_contact = ContactRecord(
        person_id="p1", evidence_age_days=999, stale=True,
    )
    client = _RecordingClient()
    report = rc.sync_delivery([card], {"p1": stale_contact}, {}, client, {})
    assert client.calls == []
    assert report.skipped == 1
    assert "stale" in report.lines[0].lower()


def test_allow_stale_true_permits_sync():
    card = _card()
    stale_contact = ContactRecord(person_id="p1", evidence_age_days=999, stale=True)
    client = _RecordingClient()
    report = rc.sync_delivery(
        [card], {"p1": stale_contact}, {}, client, {}, allow_stale=True,
    )
    assert client.calls == ["p1"]
    assert report.created == 1


def test_fresh_contact_is_not_blocked():
    card = _card()
    fresh_contact = ContactRecord(person_id="p1", evidence_age_days=2, stale=False)
    client = _RecordingClient()
    report = rc.sync_delivery([card], {"p1": fresh_contact}, {}, client, {})
    assert client.calls == ["p1"]
    assert report.created == 1


def test_opted_out_candidate_blocks_sync(monkeypatch):
    # Monkeypatch the symbol sync_delivery actually calls: rc.optout.is_opted_out.
    monkeypatch.setattr(
        rc.optout, "is_opted_out",
        lambda person=None, contact=None, person_id=None, path=None, rows=None: optout.OptOut(
            person_id="p1", email=None, linkedin_url=None,
            reason="asked to stop", at="now", source="test",
        ),
    )
    card = _card()
    fresh_contact = ContactRecord(person_id="p1", evidence_age_days=1, stale=False)
    client = _RecordingClient()
    report = rc.sync_delivery([card], {"p1": fresh_contact}, {}, client, {})
    assert client.calls == []
    assert report.skipped == 1
    assert "opted out" in report.lines[0].lower()


def test_not_opted_out_candidate_syncs(monkeypatch):
    monkeypatch.setattr(rc.optout, "is_opted_out", lambda **kw: None)
    card = _card()
    fresh_contact = ContactRecord(person_id="p1", evidence_age_days=1, stale=False)
    client = _RecordingClient()
    report = rc.sync_delivery([card], {"p1": fresh_contact}, {}, client, {})
    assert client.calls == ["p1"]
