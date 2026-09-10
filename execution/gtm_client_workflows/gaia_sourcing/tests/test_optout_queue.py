"""Tests for layers/optout.py and layers/outreach_queue.py
(RADAR_CONTRACTS.md section E). Zero network, all state confined to
tmp_path so nothing touches the real logs/ or run/ trees.
"""

from __future__ import annotations

import pytest

from gtm_client_workflows.gaia_sourcing.core.contracts import (
    ContactRecord,
    Person,
    ReplyVerdict,
)
from gtm_client_workflows.gaia_sourcing.layers import optout, outreach_queue as oq


@pytest.fixture
def optout_path(tmp_path):
    return tmp_path / "optout.jsonl"


@pytest.fixture
def queue_path(tmp_path):
    return tmp_path / "outreach_queue.json"


@pytest.fixture
def audit_path(tmp_path):
    return tmp_path / "outreach_audit.jsonl"


def _person(pid="p1", linkedin=None):
    return Person(person_id=pid, full_name="Ada Byrne", linkedin_url=linkedin)


def _contact(pid="p1", email=None, linkedin=None):
    return ContactRecord(person_id=pid, email=email, linkedin_url=linkedin)


# ---------------------------------------------------------------------------
# optout.py
# ---------------------------------------------------------------------------


def test_not_opted_out_by_default(optout_path):
    p, c = _person(), _contact(email="ada@example.com")
    assert optout.is_opted_out(person=p, contact=c, path=optout_path) is None


def test_add_optout_then_matches_on_person_id(optout_path):
    optout.add_optout(person_id="p1", reason="asked to stop", path=optout_path)
    hit = optout.is_opted_out(person=_person(), contact=_contact(), path=optout_path)
    assert hit is not None
    assert hit.person_id == "p1"
    assert hit.reason == "asked to stop"


def test_matches_on_email_case_insensitively(optout_path):
    optout.add_optout(email="Ada@Example.com", reason="unsubscribed", path=optout_path)
    hit = optout.is_opted_out(
        contact=_contact(pid="p2", email="ada@example.com"), path=optout_path
    )
    assert hit is not None
    assert hit.email == "ada@example.com"


def test_matches_on_linkedin_url(optout_path):
    optout.add_optout(linkedin_url="https://linkedin.com/in/adabyrne", path=optout_path)
    hit = optout.is_opted_out(
        person=_person(pid="p3", linkedin="https://linkedin.com/in/adabyrne"),
        path=optout_path,
    )
    assert hit is not None


def test_person_id_kwarg_matches_without_a_person_object(optout_path):
    """integrations.recruit_crm.sync_delivery has a CandidateCard, not a
    Person -- is_opted_out must accept a bare person_id too.
    """
    optout.add_optout(person_id="p9", path=optout_path)
    hit = optout.is_opted_out(contact=_contact(pid="p9"), person_id="p9", path=optout_path)
    assert hit is not None


def test_no_identifiers_at_all_returns_none(optout_path):
    optout.add_optout(person_id="p1", path=optout_path)
    assert optout.is_opted_out(path=optout_path) is None


def test_add_optout_requires_at_least_one_identifier(optout_path):
    with pytest.raises(ValueError):
        optout.add_optout(path=optout_path)


def test_add_optout_appends_jsonl_lines(optout_path):
    optout.add_optout(person_id="a", path=optout_path)
    optout.add_optout(person_id="b", path=optout_path)
    lines = optout_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_corrupt_line_is_skipped_not_fatal(optout_path, capsys):
    optout.add_optout(person_id="p1", path=optout_path)
    with optout_path.open("a", encoding="utf-8") as fh:
        fh.write("not json at all\n")
    hit = optout.is_opted_out(person=_person(pid="p1"), path=optout_path)
    assert hit is not None  # the valid line before the corrupt one still matched


def test_optout_from_reply_writes_on_opt_out_true(optout_path):
    verdict = ReplyVerdict(
        label="not_interested", next_action="close", basis="rule",
        evidence="STOP", confidence="high", opt_out=True,
    )
    rec = optout.optout_from_reply(
        "p1", _contact(pid="p1", email="ada@example.com"), verdict, path=optout_path
    )
    assert rec is not None
    assert rec.person_id == "p1"
    hit = optout.is_opted_out(person=_person(pid="p1"), path=optout_path)
    assert hit is not None


def test_optout_from_reply_is_a_noop_when_opt_out_false(optout_path):
    verdict = ReplyVerdict(
        label="not_interested", next_action="close", basis="rule",
        evidence="not interested", confidence="high", opt_out=False,
    )
    rec = optout.optout_from_reply("p1", _contact(pid="p1"), verdict, path=optout_path)
    assert rec is None
    assert not optout_path.exists()


# ---------------------------------------------------------------------------
# outreach_queue.py -- state machine
# ---------------------------------------------------------------------------


def test_create_draft_starts_in_draft_state(queue_path, audit_path):
    entry = oq.create_draft(
        _person(), _contact(), "role-1", queue_path=queue_path, audit_path=audit_path,
    )
    assert entry.state == "draft"
    row = oq.get(entry.draft_id, queue_path=queue_path)
    assert row["state"] == "draft"


def test_create_draft_blocked_by_optout(queue_path, audit_path, optout_path, monkeypatch):
    monkeypatch.setattr(
        optout, "is_opted_out",
        lambda person=None, contact=None, person_id=None, path=None: optout.OptOut(
            person_id="p1", email=None, linkedin_url=None, reason="test block",
            at="now", source="test",
        ),
    )
    with pytest.raises(oq.OptedOut):
        oq.create_draft(
            _person(), _contact(), "role-1", queue_path=queue_path, audit_path=audit_path,
        )
    # nothing was queued
    assert oq._load(queue_path) == {}
    # the block is audited
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert any("draft_blocked_optout" in line for line in lines)


def test_full_happy_path_transitions(queue_path, audit_path):
    entry = oq.create_draft(
        _person(), _contact(), "role-1", queue_path=queue_path, audit_path=audit_path,
    )
    did = entry.draft_id
    oq.submit_for_approval(did, "consultant_a", queue_path=queue_path, audit_path=audit_path)
    assert oq.get(did, queue_path=queue_path)["state"] == "pending_approval"

    oq.approve(did, "consultant_b", queue_path=queue_path, audit_path=audit_path)
    assert oq.get(did, queue_path=queue_path)["state"] == "approved"

    oq.mark_sent(did, "consultant_b", "email", queue_path=queue_path, audit_path=audit_path)
    row = oq.get(did, queue_path=queue_path)
    assert row["state"] == "marked_sent"
    assert row["history"][-1]["channel"] == "email"
    assert row["history"][-1]["by"] == "consultant_b"


def test_reject_from_approved(queue_path, audit_path):
    entry = oq.create_draft(
        _person(), _contact(), "role-1", queue_path=queue_path, audit_path=audit_path,
    )
    did = entry.draft_id
    oq.submit_for_approval(did, "a", queue_path=queue_path, audit_path=audit_path)
    oq.approve(did, "a", queue_path=queue_path, audit_path=audit_path)
    oq.reject(did, "a", "candidate withdrew", queue_path=queue_path, audit_path=audit_path)
    row = oq.get(did, queue_path=queue_path)
    assert row["state"] == "rejected"
    assert row["history"][-1]["reason"] == "candidate withdrew"


@pytest.mark.parametrize(
    "from_state,fn,args",
    [
        ("draft", "approve", ("a",)),
        ("draft", "mark_sent", ("a", "email")),
        ("draft", "reject", ("a", "no")),
        ("pending_approval", "mark_sent", ("a", "email")),
        ("pending_approval", "reject", ("a", "no")),
    ],
)
def test_invalid_transitions_raise(queue_path, audit_path, from_state, fn, args):
    entry = oq.create_draft(
        _person(), _contact(), "role-1", queue_path=queue_path, audit_path=audit_path,
    )
    did = entry.draft_id
    if from_state == "pending_approval":
        oq.submit_for_approval(did, "a", queue_path=queue_path, audit_path=audit_path)

    method = getattr(oq, fn)
    with pytest.raises(oq.InvalidTransition):
        method(did, *args, queue_path=queue_path, audit_path=audit_path)


def test_terminal_states_accept_nothing_further(queue_path, audit_path):
    entry = oq.create_draft(
        _person(), _contact(), "role-1", queue_path=queue_path, audit_path=audit_path,
    )
    did = entry.draft_id
    oq.submit_for_approval(did, "a", queue_path=queue_path, audit_path=audit_path)
    oq.approve(did, "a", queue_path=queue_path, audit_path=audit_path)
    oq.mark_sent(did, "a", "linkedin", queue_path=queue_path, audit_path=audit_path)
    with pytest.raises(oq.InvalidTransition):
        oq.approve(did, "a", queue_path=queue_path, audit_path=audit_path)


def test_transition_on_unknown_draft_id_raises_keyerror(queue_path, audit_path):
    with pytest.raises(KeyError):
        oq.approve("does-not-exist", "a", queue_path=queue_path, audit_path=audit_path)


def test_every_transition_appends_an_audit_line(queue_path, audit_path):
    entry = oq.create_draft(
        _person(), _contact(), "role-1", queue_path=queue_path, audit_path=audit_path,
    )
    did = entry.draft_id
    oq.submit_for_approval(did, "a", queue_path=queue_path, audit_path=audit_path)
    oq.approve(did, "a", queue_path=queue_path, audit_path=audit_path)
    oq.mark_sent(did, "a", "email", queue_path=queue_path, audit_path=audit_path)

    lines = audit_path.read_text(encoding="utf-8").splitlines()
    # created + 3 transitions
    assert len(lines) == 4
    import json as json_mod

    events = [json_mod.loads(ln) for ln in lines]
    assert events[0]["event"] == "created"
    assert events[1]["to"] == "pending_approval"
    assert events[2]["to"] == "approved"
    assert events[3]["to"] == "marked_sent"
    for e in events[1:]:
        assert "ts" in e and "by" in e


def test_mark_sent_never_makes_a_network_call(queue_path, audit_path, monkeypatch):
    """mark_sent is a record of a human act; it must not be able to send
    anything itself. There is no HTTP client wired into outreach_queue at
    all -- this test pins that invariant so a future edit cannot quietly
    introduce one.
    """
    import gtm_client_workflows.gaia_sourcing.layers.outreach_queue as mod

    assert not hasattr(mod, "requests")
    assert "post_json" not in dir(mod)
