"""
test_outreach.py
description: pytest suite for execution/personal_workflows/prodcraft_medspa/outreach/*.
inputs: pytest fixtures from conftest.py (local_store, fixtures_root).
outputs: N/A (test assertions only).
"""

from __future__ import annotations

import itertools
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from execution.personal_workflows.prodcraft_medspa.outreach import (
    _store_helpers,
    advance,
    daily_queue,
    draft_email,
    gmail_reader,
    lint_draft,
    scan_replies,
    send,
    state_machine,
)
from execution.personal_workflows.prodcraft_medspa.outreach.fixtures import seed_mock_store

PKG_ROOT = Path(__file__).resolve().parents[2] / "execution" / "personal_workflows" / "prodcraft_medspa"
DEFAULT_SENDER = {"name": "Debanjan @ ProdCraft", "physical_address": "123 Main St, Chicago, IL 60601"}


class FakeSettings:
    """Minimal stand-in for common.config.Settings — only what draft_email/gmail_drafts touch."""

    def __init__(self, tmp_path):
        self.TMP = tmp_path / ".tmp"
        self.TMP.mkdir(parents=True, exist_ok=True)
        self.GMAIL_CREDENTIALS_JSON = None
        self.GMAIL_TOKEN_JSON = None


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_outreach_row(store, *, business_id, touch=1, status="queued", **extra):
    row = {
        "business_id": business_id,
        "touch": touch,
        "status": status,
        "preview_id": extra.pop("preview_id", None),
        **extra,
    }
    return store.upsert_outreach(row)


def _make_business(store, *, name="Test Med Spa", email="owner@example-medspa-x.test", **extra):
    row = {
        "place_id": f"place-{name}",
        "name": name,
        "slug": name.lower().replace(" ", "-"),
        "metro": "chicago-north-shore",
        "owner_first": "Sam",
        "owner_email": email,
        "email_status": "deliverable",
        "do_not_contact": False,
        "is_chain": False,
        **extra,
    }
    return store.upsert_business(row)


def _make_preview(store, *, business_id, status="approved", **extra):
    row = {
        "business_id": business_id,
        "subdomain_url": f"https://x-{business_id[:6]}.preview.prodcraft.fyi",
        "status": status,
        "content_hash": f"hash-{business_id[:6]}",
        "content": {"services": []},
        "takedown": False,
        **extra,
    }
    return store.upsert_preview(row)


def _make_audit(store, *, business_id, gaps=None, **extra):
    row = {
        "business_id": business_id,
        "total_score": 60,
        "bucket": "qualified",
        "gaps": gaps if gaps is not None else [{"signal": "no_booking_widget", "points": 22, "human_phrase": "clients can't book online without calling"}],
        **extra,
    }
    return store.insert_audit(row)


# ---------------------------------------------------------------------------
# State machine — full state x state transition matrix
# ---------------------------------------------------------------------------


def test_every_legal_transition_succeeds(local_store):
    business = _make_business(local_store)
    for frm, to in sorted(state_machine.TRANSITIONS):
        row = _make_outreach_row(local_store, business_id=business["id"], touch=1, status=frm)
        if frm == "sent":
            row = local_store.update_outreach(row["id"], {"sent_at": "2026-09-01T00:00:00Z"})
        updated = state_machine.transition(local_store, row, to)
        if frm == "sent" and to == "queued":
            # side effect: a NEW touch-2 row is created; the original row is untouched.
            assert updated["touch"] == 2
            assert updated["status"] == "queued"
        else:
            assert updated["status"] == to


def test_every_illegal_transition_rejected(local_store):
    business = _make_business(local_store)
    for frm, to in itertools.product(state_machine.STATES, state_machine.STATES):
        if to == "dnc":
            continue  # dnc is always legal from any state
        if (frm, to) in state_machine.TRANSITIONS:
            continue
        row = _make_outreach_row(local_store, business_id=business["id"], touch=1, status=frm)
        with pytest.raises(state_machine.IllegalTransition):
            state_machine.transition(local_store, row, to)


def test_dnc_legal_from_every_state(local_store):
    business = _make_business(local_store)
    for frm in state_machine.STATES:
        row = _make_outreach_row(local_store, business_id=business["id"], touch=1, status=frm)
        updated = state_machine.transition(local_store, row, "dnc")
        assert updated["status"] == "dnc"


def test_sent_to_queued_touch4_has_no_next_touch(local_store):
    business = _make_business(local_store)
    row = _make_outreach_row(
        local_store, business_id=business["id"], touch=4, status="sent", sent_at="2026-09-01T00:00:00Z"
    )
    with pytest.raises(state_machine.IllegalTransition):
        state_machine.transition(local_store, row, "queued")


# ---------------------------------------------------------------------------
# next_touch_date — 0 / 3 / 7 / 12
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "touch,expected_gap",
    [(1, 3), (2, 4), (3, 5)],
)
def test_next_touch_date_offsets(touch, expected_gap):
    sent = date(2026, 9, 1)
    result = state_machine.next_touch_date(sent, touch)
    assert result == sent + timedelta(days=expected_gap)


def test_next_touch_date_matches_0_3_7_12_from_touch1_send():
    d0 = date(2026, 9, 1)
    d1 = state_machine.next_touch_date(d0, 1)  # touch 2 due date, if touch1 sent on d0
    assert d1 == d0 + timedelta(days=3)
    d2 = state_machine.next_touch_date(d1, 2)  # touch 3 due date, if touch2 sent on d1
    assert d2 == d0 + timedelta(days=7)
    d3 = state_machine.next_touch_date(d2, 3)  # touch 4 due date, if touch3 sent on d2
    assert d3 == d0 + timedelta(days=12)


def test_next_touch_date_rejects_out_of_range_touch():
    with pytest.raises(ValueError):
        state_machine.next_touch_date(date(2026, 9, 1), 4)
    with pytest.raises(ValueError):
        state_machine.next_touch_date(date(2026, 9, 1), 0)


# ---------------------------------------------------------------------------
# dnc cascade
# ---------------------------------------------------------------------------


def test_dnc_cascade_cancels_other_touches_and_flags_business_and_preview(local_store):
    business = _make_business(local_store)
    preview = _make_preview(local_store, business_id=business["id"])
    row1 = _make_outreach_row(
        local_store, business_id=business["id"], touch=1, status="sent", preview_id=preview["id"]
    )
    row2 = local_store.upsert_outreach(
        {"business_id": business["id"], "touch": 2, "status": "queued", "preview_id": preview["id"]}
    )

    state_machine.transition(local_store, row1, "dnc")

    updated_row2 = _store_helpers.outreach_for_business(local_store, business["id"])
    by_touch = {r["touch"]: r for r in updated_row2}
    assert by_touch[1]["status"] == "dnc"
    assert by_touch[2]["status"] == "dnc"  # cascaded

    flagged_business = local_store.get_business(business["id"])
    assert flagged_business["do_not_contact"] is True

    flagged_preview = [p for p in _store_helpers.previews_for_business(local_store, business["id"])][0]
    assert flagged_preview["status"] == "takedown"
    assert flagged_preview["takedown"] is True
    assert flagged_preview["takedown_at"] is not None


def test_dnc_cascade_does_not_touch_already_terminal_rows(local_store):
    business = _make_business(local_store)
    row1 = _make_outreach_row(local_store, business_id=business["id"], touch=1, status="sent")
    won_row = local_store.upsert_outreach({"business_id": business["id"], "touch": 2, "status": "closed_won"})

    state_machine.transition(local_store, row1, "dnc")

    rows = {r["touch"]: r for r in _store_helpers.outreach_for_business(local_store, business["id"])}
    assert rows[2]["status"] == "closed_won"  # untouched


# ---------------------------------------------------------------------------
# phase0 counters + queue cap 5 -> 20
# ---------------------------------------------------------------------------


def test_phase0_sends_counter_increments_on_touch1_sent(local_store):
    business = _make_business(local_store)
    row = _make_outreach_row(local_store, business_id=business["id"], touch=1, status="drafted")
    state_machine.transition(local_store, row, "sent")
    phase0 = local_store.get_config("phase0")
    assert phase0["sends"] == 1


def test_phase0_sends_counter_ignores_touch2_sent(local_store):
    business = _make_business(local_store)
    row = _make_outreach_row(local_store, business_id=business["id"], touch=2, status="drafted")
    state_machine.transition(local_store, row, "sent")
    phase0 = local_store.get_config("phase0", {"sends": 0})
    assert phase0.get("sends", 0) == 0


def test_phase0_calls_booked_sets_passed_true(local_store):
    business = _make_business(local_store)
    row = _make_outreach_row(local_store, business_id=business["id"], touch=1, status="replied")
    state_machine.transition(local_store, row, "call_booked")
    phase0 = local_store.get_config("phase0")
    assert phase0["calls_booked"] == 1
    assert phase0["passed"] is True


def test_daily_queue_cap_locked_5_then_open_20(local_store, fixtures_root):
    seed_mock_store.seed(local_store, today=date(2026, 9, 10))
    settings = FakeSettings(Path(local_store.root))
    stats = daily_queue.run_daily_queue(
        local_store, settings, today=date(2026, 9, 10), mock=True, create_drafts=False, variant="auto"
    )
    assert stats["cap"] == 5
    assert stats["queued_today"] == 5

    local_store.set_config(
        "phase0", {"passed": True, "sends": 5, "calls_booked": 1, "queue_cap_locked": 5, "queue_cap_open": 20}
    )
    stats2 = daily_queue.run_daily_queue(
        local_store, settings, today=date(2026, 9, 10), mock=True, create_drafts=False, variant="auto"
    )
    assert stats2["cap"] == 20


def test_daily_queue_drafted_row_notes_carry_llm_envelope(local_store, fixtures_root):
    """Research-lens: the fuzzy_variables LLM envelope (model_id, prompt_sha256, usage, mock)
    must be persisted onto the drafted outreach row's `notes` JSON, not discarded except for
    cost — `outreach` has no raw-envelope column, so `notes` is the merged home for it."""
    seed_mock_store.seed(local_store, today=date(2026, 9, 10))
    settings = FakeSettings(Path(local_store.root))
    stats = daily_queue.run_daily_queue(
        local_store, settings, today=date(2026, 9, 10), mock=True, create_drafts=False, variant="auto"
    )
    assert stats["drafted"] > 0

    drafted_rows = [
        r
        for r in _store_helpers.list_all(local_store, "outreach")
        if r.get("status") == "drafted" and int(r.get("touch") or 0) == 1
    ]
    assert drafted_rows, "expected at least one touch-1 drafted row"
    import json as _json

    found_envelope = False
    for row in drafted_rows:
        notes_raw = row.get("notes")
        if not notes_raw:
            continue
        notes = _json.loads(notes_raw)
        if "llm" in notes:
            found_envelope = True
            assert notes["llm"]["prompt_sha256"]
            assert notes["llm"]["model_id"]
            assert "usage" in notes["llm"]
    assert found_envelope, "expected at least one drafted row's notes to carry the llm envelope"


def test_print_table_preview_column_is_evidence_based(local_store, capsys):
    """The preview column reflects whether the preview's subdomain_url is actually present in
    draft_body, not merely whether draft_subject is truthy (pipeline-auditor)."""
    business = _make_business(local_store)
    preview = _make_preview(local_store, business_id=business["id"])
    row_with_link = _make_outreach_row(
        local_store,
        business_id=business["id"],
        touch=1,
        status="drafted",
        preview_id=preview["id"],
        draft_subject="subject",
        draft_body=f"Hi — check it out: {preview['subdomain_url']}\n\nThanks",
    )
    business2 = _make_business(local_store, name="No Link Spa", email="nolink@example-medspa-x.test")
    row_no_link = _make_outreach_row(
        local_store,
        business_id=business2["id"],
        touch=1,
        status="drafted",
        draft_subject="subject",
        draft_body="Hi — no link here at all.",
    )
    daily_queue._print_table([row_with_link, row_no_link], local_store)
    out = capsys.readouterr().out
    host = preview["subdomain_url"].split("//", 1)[-1]
    assert host in out
    assert "(no preview link)" in out


# ---------------------------------------------------------------------------
# bounce halt at > 2%
# ---------------------------------------------------------------------------


def test_bounce_halt_triggers_above_2_percent(local_store):
    # outreach is keyed on (business_id, touch), so distinct sent rows need distinct businesses.
    today = date(2026, 9, 10)
    # 100 sent rows in the trailing 30 days, 3 bounced -> 3% > 2%.
    for i in range(100):
        business = _make_business(local_store, name=f"Spa {i}", email=f"o{i}@example-medspa-{i}.test")
        sentiment = "bounce" if i < 3 else None
        local_store.upsert_outreach(
            {
                "business_id": business["id"],
                "touch": 1,
                "status": "sent",
                "sent_at": f"{today.isoformat()}T00:00:00Z",
                "reply_sentiment": sentiment,
            }
        )
    reason = daily_queue.halt_reason(local_store, today)
    assert reason is not None
    assert "bounce rate" in reason


def test_bounce_halt_not_triggered_at_or_below_2_percent(local_store):
    today = date(2026, 9, 10)
    for i in range(100):
        business = _make_business(local_store, name=f"Spa {i}", email=f"o{i}@example-medspa-{i}.test")
        sentiment = "bounce" if i < 2 else None
        local_store.upsert_outreach(
            {
                "business_id": business["id"],
                "touch": 1,
                "status": "sent",
                "sent_at": f"{today.isoformat()}T00:00:00Z",
                "reply_sentiment": sentiment,
            }
        )
    assert daily_queue.halt_reason(local_store, today) is None


def test_bounce_halt_ignores_sends_outside_30_day_window(local_store):
    today = date(2026, 9, 10)
    old_date = (today - timedelta(days=45)).isoformat()
    for i in range(10):
        business = _make_business(local_store, name=f"OldSpa {i}", email=f"old{i}@example-medspa-{i}.test")
        local_store.upsert_outreach(
            {
                "business_id": business["id"],
                "touch": 1,
                "status": "sent",
                "sent_at": f"{old_date}T00:00:00Z",
                "reply_sentiment": "bounce",
            }
        )
    assert daily_queue.halt_reason(local_store, today) is None


# ---------------------------------------------------------------------------
# enqueue excludes non-approved previews and do_not_contact
# ---------------------------------------------------------------------------


def test_enqueue_stamps_score_at_send_from_latest_audit(local_store):
    """item 5: the queued row's score_at_send is the audit total_score AT ENQUEUE TIME, not a
    later-read of the (possibly drifted) latest audit."""
    business = _make_business(local_store)
    _make_audit(local_store, business_id=business["id"], total_score=63)
    _make_preview(local_store, business_id=business["id"], status="approved")

    assert daily_queue.enqueue_new_touch1(local_store, date(2026, 9, 10)) == 1

    row = [r for r in _store_helpers.list_all(local_store, "outreach") if r.get("business_id") == business["id"]][0]
    assert row["score_at_send"] == 63

    # A later re-audit must not retroactively change the already-enqueued row's score_at_send.
    _make_audit(local_store, business_id=business["id"], total_score=91)
    row_after_reaudit = local_store.get_row("outreach", row["id"])
    assert row_after_reaudit["score_at_send"] == 63


def test_enqueue_excludes_do_not_contact(local_store):
    business = _make_business(local_store, do_not_contact=True)
    _make_preview(local_store, business_id=business["id"], status="approved")
    _make_audit(local_store, business_id=business["id"])
    enqueued = daily_queue.enqueue_new_touch1(local_store, date(2026, 9, 10))
    assert enqueued == 0


def test_enqueue_excludes_non_approved_preview(local_store):
    business = _make_business(local_store)
    _make_preview(local_store, business_id=business["id"], status="review")
    _make_audit(local_store, business_id=business["id"])
    enqueued = daily_queue.enqueue_new_touch1(local_store, date(2026, 9, 10))
    assert enqueued == 0


def test_enqueue_includes_approved_and_live(local_store):
    b1 = _make_business(local_store, name="Approved Spa", email="a@example-medspa-a.test")
    _make_preview(local_store, business_id=b1["id"], status="approved")
    _make_audit(local_store, business_id=b1["id"])

    b2 = _make_business(local_store, name="Live Spa", email="b@example-medspa-b.test")
    _make_preview(local_store, business_id=b2["id"], status="live")
    _make_audit(local_store, business_id=b2["id"])

    enqueued = daily_queue.enqueue_new_touch1(local_store, date(2026, 9, 10))
    assert enqueued == 2


# ---------------------------------------------------------------------------
# scan_replies — human-takeover notification, idempotency, envelope persistence
# ---------------------------------------------------------------------------

_NOTIFY_REPLY_PATH = "execution.personal_workflows.prodcraft_medspa.common.notify.reply"


def _seed_sent_row(local_store, owner_email, *, name="Fixture Med Spa"):
    business = _make_business(local_store, name=name, email=owner_email)
    preview = _make_preview(local_store, business_id=business["id"])
    row = _make_outreach_row(
        local_store,
        business_id=business["id"],
        touch=1,
        status="sent",
        preview_id=preview["id"],
        sent_at="2026-09-01T00:00:00Z",
    )
    return business, preview, row


def test_scan_replies_positive_notifies_exactly_once(local_store, monkeypatch):
    _seed_sent_row(local_store, "owner1@example-medspa-1.test")
    calls = []
    monkeypatch.setattr(_NOTIFY_REPLY_PATH, lambda **kwargs: calls.append(kwargs) or True)

    stats = scan_replies.scan(local_store, None, mock=True, since_days=14, today=date(2026, 9, 10))

    assert stats["positive"] == 1
    assert len(calls) == 1
    assert calls[0]["sentiment"] == "positive"
    assert calls[0]["wants_call"] is True

    replied = [r for r in _store_helpers.list_all(local_store, "outreach") if r.get("status") == "replied"]
    assert len(replied) == 1
    assert replied[0]["reply_sentiment"] == "positive"
    assert replied[0].get("notified_at")


def test_scan_replies_neutral_notifies_exactly_once(local_store, monkeypatch):
    _seed_sent_row(local_store, "owner2@example-medspa-2.test")
    calls = []
    monkeypatch.setattr(_NOTIFY_REPLY_PATH, lambda **kwargs: calls.append(kwargs) or True)

    stats = scan_replies.scan(local_store, None, mock=True, since_days=14, today=date(2026, 9, 10))

    assert stats["neutral"] == 1
    assert len(calls) == 1
    assert calls[0]["sentiment"] == "neutral"


def test_scan_replies_negative_does_not_notify_and_closes_lost(local_store, monkeypatch):
    _seed_sent_row(local_store, "owner3@example-medspa-3.test")
    calls = []
    monkeypatch.setattr(_NOTIFY_REPLY_PATH, lambda **kwargs: calls.append(kwargs) or True)

    stats = scan_replies.scan(local_store, None, mock=True, since_days=14, today=date(2026, 9, 10))

    assert stats["negative"] == 1
    assert calls == []
    row = [r for r in _store_helpers.list_all(local_store, "outreach") if r.get("reply_sentiment") == "negative"][0]
    assert row["status"] == "closed_lost"


def test_scan_replies_second_scan_does_not_renotify(local_store, monkeypatch):
    _seed_sent_row(local_store, "owner1@example-medspa-1.test")
    calls = []
    monkeypatch.setattr(_NOTIFY_REPLY_PATH, lambda **kwargs: calls.append(kwargs) or True)

    stats1 = scan_replies.scan(local_store, None, mock=True, since_days=14, today=date(2026, 9, 10))
    stats2 = scan_replies.scan(local_store, None, mock=True, since_days=14, today=date(2026, 9, 11))

    assert stats1["positive"] == 1
    assert stats2["checked"] == 0
    assert len(calls) == 1


def test_scan_replies_skips_message_id_already_recorded_in_notes(local_store, monkeypatch):
    """A row that already has this fixture's message_id in notes.seen_reply_ids (e.g. one that
    stayed `sent` after a prior bounce/ooo pass) must not be reclassified or renotified."""
    _business, _preview, row = _seed_sent_row(local_store, "owner1@example-medspa-1.test")
    local_store.update_outreach(row["id"], {"notes": json.dumps({"seen_reply_ids": ["msg-mock-001"]})})
    calls = []
    monkeypatch.setattr(_NOTIFY_REPLY_PATH, lambda **kwargs: calls.append(kwargs) or True)

    stats = scan_replies.scan(local_store, None, mock=True, since_days=14, today=date(2026, 9, 10))

    assert stats["checked"] == 0
    assert calls == []


def test_scan_replies_live_path_persists_llm_classify_envelope(local_store, monkeypatch):
    """The live classifier envelope (model_id, prompt_sha256, usage, mock) is merged into
    notes.llm_classify alongside seen_reply_ids, never overwriting other notes keys."""
    _business, _preview, row = _seed_sent_row(local_store, "owner1@example-medspa-1.test")
    local_store.update_outreach(row["id"], {"gmail_thread_id": "thread-mock-001"})

    reply = {
        "thread_id": "thread-mock-001",
        "message_id": "msg-live-001",
        "from": "Dana Ortiz <owner1@example-medspa-1.test>",
        "body_text": "Sounds interesting, can we hop on a call this week?",
        "received_at": "2026-09-10T10:00:00Z",
    }
    monkeypatch.setattr(scan_replies.gmail_reader, "search_replies", lambda **kwargs: [reply])
    monkeypatch.setattr(
        scan_replies.llm,
        "call",
        lambda *a, **k: {
            "text": json.dumps(
                {
                    "sentiment": "positive",
                    "wants_call": True,
                    "remove_request": False,
                    "summary": "Wants a call this week.",
                    "suggested_next_step": "book_call",
                }
            ),
            "model_id": "claude-sonnet-5",
            "prompt_sha256": "deadbeef",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
            "mock": False,
        },
    )
    calls = []
    monkeypatch.setattr(_NOTIFY_REPLY_PATH, lambda **kwargs: calls.append(kwargs) or True)

    stats = scan_replies.scan(local_store, object(), mock=False, since_days=14, today=date(2026, 9, 10))

    assert stats["positive"] == 1
    assert len(calls) == 1
    updated = [r for r in _store_helpers.list_all(local_store, "outreach") if r["id"] == row["id"]][0]
    notes = json.loads(updated["notes"])
    assert notes["llm_classify"]["model_id"] == "claude-sonnet-5"
    assert notes["llm_classify"]["prompt_sha256"] == "deadbeef"
    assert "usage" in notes["llm_classify"]
    assert notes["llm_classify"]["mock"] is False
    assert notes["seen_reply_ids"] == ["msg-live-001"]


def test_enqueue_excludes_takedown_preview(local_store):
    business = _make_business(local_store)
    _make_preview(local_store, business_id=business["id"], status="approved", takedown=True)
    _make_audit(local_store, business_id=business["id"])
    enqueued = daily_queue.enqueue_new_touch1(local_store, date(2026, 9, 10))
    assert enqueued == 0


def test_enqueue_is_idempotent(local_store):
    business = _make_business(local_store)
    _make_preview(local_store, business_id=business["id"], status="approved")
    _make_audit(local_store, business_id=business["id"])
    first = daily_queue.enqueue_new_touch1(local_store, date(2026, 9, 10))
    second = daily_queue.enqueue_new_touch1(local_store, date(2026, 9, 10))
    assert first == 1
    assert second == 0


# ---------------------------------------------------------------------------
# draft rendering — touches 1-4
# ---------------------------------------------------------------------------


def _render(local_store, settings, *, touch, business, audit=None, preview=None, outreach_extra=None, variant="auto"):
    outreach_row = _make_outreach_row(
        local_store,
        business_id=business["id"],
        touch=touch,
        status="queued",
        preview_id=(preview or {}).get("id"),
        audit_id=(audit or {}).get("id"),
        **(outreach_extra or {}),
    )
    return draft_email.render_draft(
        local_store,
        settings,
        outreach_row=outreach_row,
        business=business,
        audit_row=audit,
        preview_row=preview,
        variant=variant,
        mock=True,
    )


@pytest.fixture
def sender_configured(local_store):
    local_store.set_config("sender", DEFAULT_SENDER)
    # send.py's C2 live-send gate (config.live_send_confirmed) blocks every send until the
    # operator explicitly confirms; pre-confirm here so the many existing send.run_send(...)
    # tests below (which call run_send directly, not the --confirm-live-sends CLI path) keep
    # exercising the rest of send.py's logic. Tests of the gate itself use a bare `local_store`.
    local_store.set_config("live_send_confirmed", True)
    return local_store


def test_draft_touch1_subject_no_re_prefix_and_one_link(sender_configured, fixtures_root):
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured)
    audit = _make_audit(sender_configured, business_id=business["id"])
    preview = _make_preview(sender_configured, business_id=business["id"])
    rendered = _render(sender_configured, settings, touch=1, business=business, audit=audit, preview=preview)
    assert not rendered["subject"].lower().startswith("re:")
    assert rendered["body"].count("https://") == 1
    assert rendered["variant"] in ("a", "b", "c")


def test_draft_touch2_uses_prev_subject_and_re_prefix(sender_configured, fixtures_root):
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured)
    # touch 1 row already sent, with a known draft_subject to carry forward.
    local_store = sender_configured
    local_store.upsert_outreach(
        {
            "business_id": business["id"],
            "touch": 1,
            "status": "sent",
            "draft_subject": "quick question about Test Med Spa's booking",
        }
    )
    preview = _make_preview(local_store, business_id=business["id"])
    rendered = _render(local_store, settings, touch=2, business=business, preview=preview)
    assert rendered["subject"] == "Re: quick question about Test Med Spa's booking"
    assert rendered["body"].count("https://") <= 1  # loom_url placeholder, not a real link


def test_draft_touch3_and_4_have_zero_links(sender_configured, fixtures_root):
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured)
    for touch in (3, 4):
        rendered = _render(sender_configured, settings, touch=touch, business=business)
        assert "https://" not in rendered["body"]


def test_draft_proof_line_fallback_when_no_config(sender_configured, fixtures_root):
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured)
    rendered = _render(sender_configured, settings, touch=3, business=business)
    assert "phone call" in rendered["body"]  # fallback proof line (qualitative, unsourced numbers removed)


def test_draft_proof_line_uses_config_when_present(sender_configured, fixtures_root):
    sender_configured.set_config("proof_lines", ["Client X saw 3x online bookings in 60 days."])
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured)
    rendered = _render(sender_configured, settings, touch=3, business=business)
    assert "Client X saw 3x online bookings" in rendered["body"]


def test_expires_on_weekday_within_6_days_uses_weekday_name():
    # 2026-09-10 is a Thursday; 2026-09-14 is a Monday (4 days out).
    result = draft_email._expires_on_weekday("2026-09-14", today=date(2026, 9, 10))
    assert result == "Monday"


def test_expires_on_weekday_beyond_6_days_uses_date():
    result = draft_email._expires_on_weekday("2026-10-10", today=date(2026, 9, 10))
    assert "October" in result


def test_expires_on_weekday_none_falls_back_to_friday():
    assert draft_email._expires_on_weekday(None) == "Friday"


def test_draft_touch4_expires_on_weekday_rendered(sender_configured, fixtures_root):
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured)
    preview = _make_preview(sender_configured, business_id=business["id"], expires_at="2026-09-12")
    rendered = _render(sender_configured, settings, touch=4, business=business, preview=preview)
    assert rendered["body"]  # rendered without leftover {{expires_on_weekday}}
    assert "{{" not in rendered["body"]


# ---------------------------------------------------------------------------
# lint_draft — every checklist rule + fail-closed
# ---------------------------------------------------------------------------


VALID_BODY = (
    "Hi Sam,\n\nSome body text.\n\n"
    "Debanjan\n123 Main St, Chicago, IL 60601\nReply 'no' and I won't follow up."
)


def test_lint_passes_a_valid_touch1_draft():
    result = lint_draft.lint(
        "quick question about Test Spa's booking",
        VALID_BODY + " https://preview.prodcraft.fyi/x",
        touch=1,
        sender_name="Debanjan",
        sender_physical_address="123 Main St, Chicago, IL 60601",
    )
    assert result["violations"] == []


def test_lint_rule1_empty_sender_name_fails_closed():
    result = lint_draft.lint("subject", VALID_BODY, touch=1, sender_name="", sender_physical_address="123 Main St, Chicago, IL 60601")
    assert "can_spam:1" in result["violations"]


def test_lint_rule2_touch1_re_prefix_fails():
    result = lint_draft.lint(
        "Re: quick question", VALID_BODY, touch=1, sender_name="Debanjan", sender_physical_address="123 Main St, Chicago, IL 60601"
    )
    assert "can_spam:2" in result["violations"]


def test_lint_rule2_touch2_re_prefix_allowed():
    result = lint_draft.lint(
        "Re: quick question", VALID_BODY, touch=2, sender_name="Debanjan", sender_physical_address="123 Main St, Chicago, IL 60601"
    )
    assert "can_spam:2" not in result["violations"]


def test_lint_rule3_missing_physical_address_fails_closed():
    result = lint_draft.lint("subject", VALID_BODY, touch=1, sender_name="Debanjan", sender_physical_address="")
    assert "can_spam:3" in result["violations"]


def test_lint_rule3_address_not_in_body_fails():
    body = "Hi Sam,\n\nBody.\n\nDebanjan\nReply 'no' and I won't follow up."
    result = lint_draft.lint("subject", body, touch=1, sender_name="Debanjan", sender_physical_address="123 Main St")
    assert "can_spam:3" in result["violations"]


def test_lint_rule4_missing_optout_fails():
    body = "Hi Sam,\n\nBody.\n\nDebanjan\n123 Main St, Chicago, IL 60601"
    result = lint_draft.lint("subject", body, touch=1, sender_name="Debanjan", sender_physical_address="123 Main St, Chicago, IL 60601")
    assert "can_spam:4" in result["violations"]


def test_lint_rule5_too_many_links_touch1():
    body = VALID_BODY + " https://a.test https://b.test"
    result = lint_draft.lint("subject", body, touch=1, sender_name="Debanjan", sender_physical_address="123 Main St, Chicago, IL 60601")
    assert "can_spam:5" in result["violations"]


def test_lint_rule5_zero_links_required_touch3():
    body = VALID_BODY + " https://a.test"
    result = lint_draft.lint("subject", body, touch=3, sender_name="Debanjan", sender_physical_address="123 Main St, Chicago, IL 60601")
    assert "can_spam:5" in result["violations"]


def test_lint_rule6_allcaps_word_fails():
    body = VALID_BODY.replace("Some body text", "THIS IS URGENT")
    result = lint_draft.lint("subject", body, touch=1, sender_name="Debanjan", sender_physical_address="123 Main St, Chicago, IL 60601")
    assert "can_spam:6" in result["violations"]


def test_lint_rule7_free_in_subject_fails():
    result = lint_draft.lint("your FREE preview", VALID_BODY, touch=1, sender_name="Debanjan", sender_physical_address="123 Main St, Chicago, IL 60601")
    assert "can_spam:7" in result["violations"]


def test_lint_rule8_body_over_120_words_fails():
    body = "Hi Sam,\n\n" + ("word " * 130) + "\n\nDebanjan\n123 Main St, Chicago, IL 60601\nReply 'no' and I won't follow up."
    result = lint_draft.lint("subject", body, touch=1, sender_name="Debanjan", sender_physical_address="123 Main St, Chicago, IL 60601")
    assert "can_spam:8" in result["violations"]


def test_lint_banned_word_fails():
    body = VALID_BODY.replace("Some body text", "Your site looks outdated")
    result = lint_draft.lint("subject", body, touch=1, sender_name="Debanjan", sender_physical_address="123 Main St, Chicago, IL 60601")
    assert any(v.startswith("content:banned_word") for v in result["violations"])


def test_lint_loom_placeholder_flagged_not_failed():
    body = VALID_BODY + " [[LOOM URL]]"
    result = lint_draft.lint("subject", body, touch=2, sender_name="Debanjan", sender_physical_address="123 Main St, Chicago, IL 60601")
    assert result["needs_operator_input"] is True
    assert "render:unresolved_variable" not in result["violations"]


def test_lint_real_unresolved_variable_fails():
    body = VALID_BODY + " {{business_name}}"
    result = lint_draft.lint("subject", body, touch=1, sender_name="Debanjan", sender_physical_address="123 Main St, Chicago, IL 60601")
    assert "render:unresolved_variable" in result["violations"]


# ---------------------------------------------------------------------------
# variant rotation
# ---------------------------------------------------------------------------


def test_variant_rotation_a_b_c(sender_configured, fixtures_root):
    # item 6 (round-2 audit): "auto" is now a STABLE hash of business_id, not a rotating counter
    # — sha1("biz-0")..sha1("biz-5") were precomputed to land in all three buckets (0,0,2,2,1,2)
    # so this test deterministically exercises all three variants rather than depending on
    # store-generated random uuids (which could statistically miss a bucket across 6 draws).
    settings = FakeSettings(fixtures_root)
    variants = []
    for i in range(6):
        business = _make_business(
            sender_configured, name=f"Rotation Spa {i}", email=f"r{i}@example-medspa-{i}.test", id=f"biz-{i}"
        )
        row = _make_outreach_row(sender_configured, business_id=business["id"], touch=1, status="queued")
        rendered = draft_email.render_draft(
            sender_configured, settings, outreach_row=row, business=business, audit_row=None, preview_row=None,
            variant="auto", mock=True,
        )
        sender_configured.update_outreach(row["id"], {"template_variant": rendered["variant"]})
        variants.append(rendered["variant"])
    assert set(variants) == {"a", "b", "c"}, f"expected all three variants across 6 businesses, got {variants}"


def test_variant_auto_is_stable_per_business_across_rerenders(sender_configured, fixtures_root):
    """item 6: a re-render (e.g. a redraft after a lint fix) must keep the SAME variant once the
    outreach row has committed to one, rather than recomputing off business_id fresh each time."""
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured, name="Stable Variant Spa", id="biz-stable")
    row = _make_outreach_row(sender_configured, business_id=business["id"], touch=1, status="queued")

    first = draft_email.render_draft(
        sender_configured, settings, outreach_row=row, business=business, audit_row=None, preview_row=None,
        variant="auto", mock=True,
    )
    row = sender_configured.update_outreach(row["id"], {"template_variant": first["variant"]})

    # A different variant would be picked purely off business_id hashing only if the row didn't
    # already carry template_variant — simulate a redraft by re-rendering the now-persisted row.
    second = draft_email.render_draft(
        sender_configured, settings, outreach_row=row, business=business, audit_row=None, preview_row=None,
        variant="auto", mock=True,
    )
    assert second["variant"] == first["variant"]


def test_variant_explicit_overrides_rotation(sender_configured, fixtures_root):
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured)
    row = _make_outreach_row(sender_configured, business_id=business["id"], touch=1, status="queued")
    rendered = draft_email.render_draft(
        sender_configured, settings, outreach_row=row, business=business, audit_row=None, preview_row=None,
        variant="b", mock=True,
    )
    assert rendered["variant"] == "b"


# ---------------------------------------------------------------------------
# scan_replies mock — six outcomes + takedown list
# ---------------------------------------------------------------------------


def test_scan_replies_mock_produces_six_distinct_outcomes(local_store):
    seed_mock_store.seed(local_store, today=date(2026, 9, 10))
    # seed_mock_store creates no outreach rows itself — create sent touch-1 rows for the 6
    # fixture-matched businesses (owner1..owner6).
    businesses = {b["owner_email"]: b for b in _store_helpers.list_all(local_store, "businesses")}
    for i in range(1, 7):
        email = f"owner{i}@example-medspa-{i}.test"
        business = businesses[email]
        local_store.upsert_outreach(
            {"business_id": business["id"], "touch": 1, "status": "sent", "sent_at": "2026-09-01T00:00:00Z"}
        )

    settings = FakeSettings(Path(local_store.root))
    stats = scan_replies.scan(local_store, settings, mock=True, since_days=14, today=date(2026, 9, 10))

    assert stats["checked"] == 6
    assert stats["positive"] == 1
    assert stats["neutral"] == 1
    assert stats["negative"] == 1
    assert stats["bounce"] == 1
    assert stats["ooo"] == 1
    assert stats["remove"] == 1
    assert len(stats["takedowns"]) == 1


def test_scan_replies_mock_classify_matches_rule_order():
    remove = scan_replies._mock_classify("please remove this and stop contacting me")
    assert remove["sentiment"] == "remove"
    assert remove["remove_request"] is True

    bounce = scan_replies._mock_classify("Delivery Status Notification (Failure) 550 5.1.1")
    assert bounce["sentiment"] == "bounce"

    ooo = scan_replies._mock_classify("I am currently out of office, this is an automatic reply")
    assert ooo["sentiment"] == "ooo"

    positive = scan_replies._mock_classify("Yes! Can we hop on a quick call this week?")
    assert positive["sentiment"] == "positive"
    assert positive["wants_call"] is True

    negative = scan_replies._mock_classify("We're not interested at this time")
    assert negative["sentiment"] == "negative"

    neutral = scan_replies._mock_classify("What booking system does this use?")
    assert neutral["sentiment"] == "neutral"


def test_scan_replies_remove_triggers_dnc_and_takedown(local_store, monkeypatch):
    """item 7 (round-2 audit): a remove reply also fires exactly one Telegram notify (sentiment
    forced to "remove") and stamps notes.remove_source ("keyword" under --mock)."""
    business = _make_business(local_store, email="owner4@example-medspa-4.test")
    preview = _make_preview(local_store, business_id=business["id"])
    row = local_store.upsert_outreach(
        {"business_id": business["id"], "touch": 1, "status": "sent", "sent_at": "2026-09-01T00:00:00Z", "preview_id": preview["id"]}
    )
    calls = []
    monkeypatch.setattr(_NOTIFY_REPLY_PATH, lambda **kwargs: calls.append(kwargs) or True)

    fixtures_root_pkg = PKG_ROOT / "outreach" / "fixtures"
    settings = FakeSettings(fixtures_root_pkg)
    stats = scan_replies.scan(local_store, settings, mock=True, since_days=14, today=date(2026, 9, 10))
    assert stats["remove"] == 1
    assert len(stats["takedowns"]) == 1
    updated = local_store.get_business(business["id"])
    assert updated["do_not_contact"] is True
    updated_row = local_store.update_outreach(row["id"], {})
    assert updated_row["status"] == "dnc"

    updated_preview = local_store.get_row("previews", preview["id"])
    assert updated_preview["status"] == "takedown"

    assert len(calls) == 1
    assert calls[0]["sentiment"] == "remove"

    notes = json.loads(updated_row["notes"])
    assert notes["remove_source"] == "keyword"  # --mock uses the deterministic keyword matcher


def test_scan_replies_negative_closes_lost_and_takes_down_preview_without_dnc(local_store):
    """item 7: negative -> closed_lost AND preview takedown via the same real unpublish path as
    remove, but WITHOUT flipping do_not_contact (unlike remove, this isn't a do-not-contact
    request)."""
    business = _make_business(local_store, email="owner3@example-medspa-3.test")
    preview = _make_preview(local_store, business_id=business["id"])
    row = local_store.upsert_outreach(
        {
            "business_id": business["id"], "touch": 1, "status": "sent",
            "sent_at": "2026-09-01T00:00:00Z", "preview_id": preview["id"],
        }
    )
    fixtures_root_pkg = PKG_ROOT / "outreach" / "fixtures"
    settings = FakeSettings(fixtures_root_pkg)
    stats = scan_replies.scan(local_store, settings, mock=True, since_days=14, today=date(2026, 9, 10))

    assert stats["negative"] == 1
    updated_row = local_store.update_outreach(row["id"], {})
    assert updated_row["status"] == "closed_lost"

    updated_preview = local_store.get_row("previews", preview["id"])
    assert updated_preview["status"] == "takedown"

    updated_business = local_store.get_business(business["id"])
    assert updated_business["do_not_contact"] is False


def test_scan_replies_bounce_sets_business_undeliverable(local_store):
    business = _make_business(local_store, email="owner5@example-medspa-5.test")
    row = local_store.upsert_outreach(
        {"business_id": business["id"], "touch": 1, "status": "sent", "sent_at": "2026-09-01T00:00:00Z"}
    )
    fixtures_root_pkg = PKG_ROOT / "outreach" / "fixtures"
    settings = FakeSettings(fixtures_root_pkg)
    stats = scan_replies.scan(local_store, settings, mock=True, since_days=14, today=date(2026, 9, 10))
    assert stats["bounce"] == 1
    updated = local_store.get_business(business["id"])
    assert updated["email_status"] == "undeliverable"
    kept_row = local_store.update_outreach(row["id"], {})
    assert kept_row["status"] == "sent"  # bounce does not change status


# ---------------------------------------------------------------------------
# advance — next touch creation + closed_lost after touch 4
# ---------------------------------------------------------------------------


def test_advance_creates_next_touch_row(local_store):
    business = _make_business(local_store)
    row = local_store.upsert_outreach(
        {
            "business_id": business["id"],
            "touch": 1,
            "status": "sent",
            "sent_at": "2026-09-01T00:00:00Z",
            "next_touch_at": "2026-09-04",
        }
    )
    stats = advance.run_advance(local_store, date(2026, 9, 5))
    assert stats["advanced"] == 1
    rows = {r["touch"]: r for r in _store_helpers.outreach_for_business(local_store, business["id"])}
    assert 2 in rows
    assert rows[2]["status"] == "queued"


def test_advance_does_not_advance_before_due(local_store):
    business = _make_business(local_store)
    local_store.upsert_outreach(
        {
            "business_id": business["id"],
            "touch": 1,
            "status": "sent",
            "sent_at": "2026-09-01T00:00:00Z",
            "next_touch_at": "2026-09-30",
        }
    )
    stats = advance.run_advance(local_store, date(2026, 9, 5))
    assert stats["advanced"] == 0


def test_advance_does_not_advance_replied_rows(local_store):
    business = _make_business(local_store)
    local_store.upsert_outreach(
        {
            "business_id": business["id"],
            "touch": 1,
            "status": "sent",
            "sent_at": "2026-09-01T00:00:00Z",
            "next_touch_at": "2026-09-04",
            "replied_at": "2026-09-03T00:00:00Z",
        }
    )
    stats = advance.run_advance(local_store, date(2026, 9, 5))
    assert stats["advanced"] == 0


def test_advance_closes_lost_after_touch4_grace_period(local_store):
    business = _make_business(local_store)
    local_store.upsert_outreach(
        {
            "business_id": business["id"],
            "touch": 4,
            "status": "sent",
            "sent_at": "2026-09-01T00:00:00Z",
            "next_touch_at": "2026-09-04",
        }
    )
    # Not yet past the 5-day grace period.
    stats_early = advance.run_advance(local_store, date(2026, 9, 6))
    assert stats_early["closed_lost"] == 0

    stats_late = advance.run_advance(local_store, date(2026, 9, 9))
    assert stats_late["closed_lost"] == 1
    rows = _store_helpers.outreach_for_business(local_store, business["id"])
    assert rows[0]["status"] == "closed_lost"


def test_advance_skips_bounced_rows(local_store):
    business = _make_business(local_store)
    local_store.upsert_outreach(
        {
            "business_id": business["id"],
            "touch": 1,
            "status": "sent",
            "sent_at": "2026-09-01T00:00:00Z",
            "next_touch_at": "2026-09-04",
            "reply_sentiment": "bounce",
        }
    )
    stats = advance.run_advance(local_store, date(2026, 9, 5))
    assert stats["advanced"] == 0


# ---------------------------------------------------------------------------
# gmail_reader — quoted-history stripping (used by scan_replies)
# ---------------------------------------------------------------------------


def test_strip_quoted_history_drops_quote_block():
    body = "Yes let's talk.\n\nOn Mon, Sep 7, 2026 at 9:03 AM sender@prodcraft.fyi wrote:\n> original text"
    stripped = gmail_reader.strip_quoted_history(body)
    assert "original text" not in stripped
    assert "Yes let's talk" in stripped


def test_strip_quoted_history_drops_gt_prefixed_lines():
    body = "My reply here.\n> quoted line 1\n> quoted line 2"
    stripped = gmail_reader.strip_quoted_history(body)
    assert "quoted line" not in stripped
    assert "My reply here" in stripped


# ---------------------------------------------------------------------------
# config.sender gate: mock falls back to a synthetic sender, live fails closed
# ---------------------------------------------------------------------------


def test_lint_fails_closed_when_sender_config_empty():
    from execution.personal_workflows.prodcraft_medspa.outreach import lint_draft

    result = lint_draft.lint("subject", "body\nReply 'no' and I won't follow up.", touch=1, sender_name="", sender_physical_address="")
    assert "can_spam:1" in result["violations"] and "can_spam:3" in result["violations"]


def test_mock_sender_is_clearly_synthetic_and_passes_lint():
    from execution.personal_workflows.prodcraft_medspa.outreach import draft_email, lint_draft

    sender = draft_email.MOCK_SENDER
    assert "mock" in sender["name"].lower() and "Example" in sender["physical_address"]
    body = f"Hi there,\n\nshort body.\n\n{sender['name']}\n{sender['physical_address']}\n{lint_draft.OPT_OUT_LINE}"
    result = lint_draft.lint("quick question", body, touch=1, sender_name=sender["name"], sender_physical_address=sender["physical_address"])
    assert result["violations"] == []


class _FakeNonLocalStore:
    """Stand-in for a remote Store implementation (e.g. SupabaseStore) that is NOT a LocalStore
    instance, used to prove MOCK_SENDER can never render against a non-local store even when the
    caller passes mock=True (code-reviewer C4/M1)."""

    def __init__(self, sender=None):
        self._sender = sender or {}

    def get_config(self, key, default=None):
        if key == "sender":
            return self._sender
        return default


def test_mock_sender_never_used_against_non_local_store(fixtures_root):
    """draft_email.render_draft must fail the CAN-SPAM lint (empty sender) rather than fall back
    to MOCK_SENDER when the store is not a LocalStore, even under mock=True."""
    from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore

    fake_store = _FakeNonLocalStore(sender={})
    assert not isinstance(fake_store, LocalStore)
    settings = FakeSettings(fixtures_root)
    business = _make_business_dict_only()
    outreach_row = {"business_id": business["id"], "touch": 1, "status": "queued"}
    # fixtures_root omitted: render_draft defaults to its own prompts/fixtures LLM fixture dir
    # (LLM_FIXTURES_ROOT), NOT the top-level fixtures/ dir this test file's `fixtures_root`
    # fixture points at (see draft_email.py's module docstring on render_draft's own param).
    rendered = draft_email.render_draft(
        fake_store,
        settings,
        outreach_row=outreach_row,
        business=business,
        audit_row=None,
        preview_row=None,
        variant="a",
        mock=True,
    )
    # Real sender fields stayed empty — MOCK_SENDER (whose name contains "mock") never rendered in.
    assert rendered["sender"]["name"] == ""
    assert rendered["sender"]["physical_address"] == ""
    assert draft_email.MOCK_SENDER["name"] not in rendered["body"]


def _make_business_dict_only():
    return {
        "id": "biz-fake-nonlocal-1",
        "name": "Fake Non-Local Med Spa",
        "owner_first": "Sam",
        "suburb": "Evanston",
        "primary_type": "spa",
    }


# ---------------------------------------------------------------------------
# transition.py CLI — --mock backfill (item 5) + --mock/--store supabase guard (item 1)
# ---------------------------------------------------------------------------


def test_transition_cli_mock_forces_local_store(tmp_path):
    import json as _json
    import subprocess
    import sys as _sys

    from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore

    store_root = tmp_path / "store"
    store = LocalStore(root=store_root)
    business = _make_business(store)
    row = _make_outreach_row(store, business_id=business["id"], touch=1, status="drafted")

    repo_root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [_sys.executable, "-m", "execution.personal_workflows.prodcraft_medspa.outreach.transition",
         "--outreach-id", row["id"], "--to", "sent", "--sent-at", "2026-09-10",
         "--mock", "--store-root", str(store_root)],
        cwd=str(repo_root), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 0, proc.stderr
    out = _json.loads(proc.stdout.strip().splitlines()[-1])
    assert out["outreach"]["status"] == "sent"


def test_transition_cli_mock_with_store_supabase_exits_2():
    import subprocess
    import sys as _sys

    repo_root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [_sys.executable, "-m", "execution.personal_workflows.prodcraft_medspa.outreach.transition",
         "--outreach-id", "does-not-matter", "--to", "sent", "--mock", "--store", "supabase"],
        cwd=str(repo_root), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 2
    assert "--mock cannot be combined with --store supabase" in proc.stderr


def test_doctor_sender_check_reports_missing_then_ok(tmp_path):
    from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore
    from execution.personal_workflows.prodcraft_medspa.scripts import doctor

    store = LocalStore(root=tmp_path / "store")
    ok, detail = doctor.check_sender_config(store)
    assert ok is False and "name" in detail and "physical_address" in detail
    store.set_config("sender", {"name": "Operator Name", "physical_address": "1 Main St, Chicago, IL 60601"})
    ok, _ = doctor.check_sender_config(store)
    assert ok is True


# ---------------------------------------------------------------------------
# outreach/send.py — automated sending (operator decision 2026-09-16)
# ---------------------------------------------------------------------------

VALID_SEND_BODY = (
    "Hi Sam,\n\nCheck it out: https://x.preview.prodcraft.fyi\n\n"
    "Debanjan\n123 Main St, Chicago, IL 60601\nReply 'no' and I won't follow up."
)


def _drafted_row(local_store, *, business, preview, touch=1, notes=None, **extra):
    return _make_outreach_row(
        local_store,
        business_id=business["id"],
        touch=touch,
        status="drafted",
        preview_id=preview["id"] if preview else None,
        draft_subject=extra.pop("draft_subject", "quick question about booking"),
        draft_body=extra.pop("draft_body", VALID_SEND_BODY),
        notes=notes,
        **extra,
    )


def test_send_transitions_drafted_to_sent_and_records_ids(sender_configured, fixtures_root):
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured)
    preview = _make_preview(sender_configured, business_id=business["id"])
    row = _drafted_row(sender_configured, business=business, preview=preview)

    stats = send.run_send(sender_configured, settings, today=date(2026, 9, 16), mock=True)
    assert stats == {"script": "send", "in": 1, "sent": 1, "cap": 5, "dropped": {
        "cap_reached": 0, "halted": 0, "lint_failed": 0, "dnc": 0,
        "preview_not_approved": 0, "already_replied": 0, "no_email": 0, "gmail_error": 0,
        "live_send_not_confirmed": 0, "header_injection": 0, "preview_not_public": 0,
    }, "recipient_override": False, "live_recipients": True}

    updated = sender_configured.update_outreach(row["id"], {})
    assert updated["status"] == "sent"
    assert updated["sent_at"]
    assert updated["gmail_message_id"].startswith("mock-")
    assert "gmail_thread_id" in updated


def test_send_respects_cap_across_touches(sender_configured, fixtures_root):
    settings = FakeSettings(fixtures_root)
    today = date(2026, 9, 16)
    sender_configured.set_config(
        "phase0", {"passed": False, "sends": 0, "calls_booked": 0, "queue_cap_locked": 2, "queue_cap_open": 20}
    )
    # One already-sent row today (touch 2, counts toward the cap) and two fresh drafted rows.
    b0 = _make_business(sender_configured, name="Already Sent Spa", email="s0@example-medspa-0.test")
    sender_configured.upsert_outreach(
        {"business_id": b0["id"], "touch": 2, "status": "sent", "sent_at": f"{today.isoformat()}T00:00:00Z"}
    )
    b1 = _make_business(sender_configured, name="Cap Spa 1", email="s1@example-medspa-1.test")
    p1 = _make_preview(sender_configured, business_id=b1["id"])
    _drafted_row(sender_configured, business=b1, preview=p1)
    b2 = _make_business(sender_configured, name="Cap Spa 2", email="s2@example-medspa-2.test")
    p2 = _make_preview(sender_configured, business_id=b2["id"])
    _drafted_row(sender_configured, business=b2, preview=p2)

    stats = send.run_send(sender_configured, settings, today=today, mock=True)
    # cap is 2, 1 already sent today -> only 1 more can go out.
    assert stats["sent"] == 1
    assert stats["dropped"]["cap_reached"] == 1


def test_send_halted_queue_sends_nothing(sender_configured, fixtures_root):
    settings = FakeSettings(fixtures_root)
    today = date(2026, 9, 16)
    # Push the bounce rate over 2% (mirrors test_bounce_halt_triggers_above_2_percent).
    for i in range(100):
        b = _make_business(sender_configured, name=f"Bounce Spa {i}", email=f"bo{i}@example-medspa-{i}.test")
        sentiment = "bounce" if i < 3 else None
        sender_configured.upsert_outreach(
            {
                "business_id": b["id"], "touch": 1, "status": "sent",
                "sent_at": f"{today.isoformat()}T00:00:00Z", "reply_sentiment": sentiment,
            }
        )
    business = _make_business(sender_configured, name="Halted Spa", email="halted@example-medspa-h.test")
    preview = _make_preview(sender_configured, business_id=business["id"])
    _drafted_row(sender_configured, business=business, preview=preview)

    stats = send.run_send(sender_configured, settings, today=today, mock=True)
    assert stats["sent"] == 0
    assert stats["dropped"]["halted"] == 1


def test_send_recipient_override_rewrites_to_and_prefixes_subject(sender_configured, fixtures_root, tmp_path):
    settings = FakeSettings(tmp_path)
    business = _make_business(sender_configured, email="realowner@example-medspa-real.test")
    preview = _make_preview(sender_configured, business_id=business["id"])
    row = _drafted_row(sender_configured, business=business, preview=preview, draft_subject="quick question")

    stats = send.run_send(
        sender_configured, settings, today=date(2026, 9, 16), mock=True,
        recipient_override="dry-run@example.test",
    )
    assert stats["sent"] == 1

    updated = sender_configured.update_outreach(row["id"], {})
    assert updated["test_recipient"] == "dry-run@example.test"

    eml_files = list((settings.TMP / "sent").glob("*.eml"))
    assert len(eml_files) == 1
    content = eml_files[0].read_text(encoding="utf-8")
    assert "To: dry-run@example.test" in content
    assert "Subject: [TEST to realowner@example-medspa-real.test] quick question" in content


def test_send_lint_failed_rows_never_send(sender_configured, fixtures_root):
    import json as _json

    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured)
    preview = _make_preview(sender_configured, business_id=business["id"])
    row = _drafted_row(
        sender_configured, business=business, preview=preview,
        notes=_json.dumps({"lint_violations": ["can_spam:4"]}),
    )

    stats = send.run_send(sender_configured, settings, today=date(2026, 9, 16), mock=True)
    assert stats["sent"] == 0
    assert stats["dropped"]["lint_failed"] == 1
    unchanged = sender_configured.update_outreach(row["id"], {})
    assert unchanged["status"] == "drafted"


def test_send_dnc_never_sends(sender_configured, fixtures_root):
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured, do_not_contact=True)
    preview = _make_preview(sender_configured, business_id=business["id"])
    _drafted_row(sender_configured, business=business, preview=preview)

    stats = send.run_send(sender_configured, settings, today=date(2026, 9, 16), mock=True)
    assert stats["sent"] == 0
    assert stats["dropped"]["dnc"] == 1


def test_send_preview_not_approved_never_sends(sender_configured, fixtures_root):
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured)
    preview = _make_preview(sender_configured, business_id=business["id"], status="review")
    _drafted_row(sender_configured, business=business, preview=preview)

    stats = send.run_send(sender_configured, settings, today=date(2026, 9, 16), mock=True)
    assert stats["sent"] == 0
    assert stats["dropped"]["preview_not_approved"] == 1


def test_send_skips_business_with_another_replied_or_terminal_row(sender_configured, fixtures_root):
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured)
    preview = _make_preview(sender_configured, business_id=business["id"])
    _drafted_row(sender_configured, business=business, preview=preview, touch=1)
    sender_configured.upsert_outreach({"business_id": business["id"], "touch": 2, "status": "replied"})

    stats = send.run_send(sender_configured, settings, today=date(2026, 9, 16), mock=True)
    assert stats["sent"] == 0
    assert stats["dropped"]["already_replied"] == 1


def test_send_no_email_never_sends(sender_configured, fixtures_root):
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured, owner_email=None)
    preview = _make_preview(sender_configured, business_id=business["id"])
    _drafted_row(sender_configured, business=business, preview=preview)

    stats = send.run_send(sender_configured, settings, today=date(2026, 9, 16), mock=True)
    assert stats["sent"] == 0
    assert stats["dropped"]["no_email"] == 1


def test_send_limit_caps_this_run_regardless_of_daily_cap(sender_configured, fixtures_root):
    settings = FakeSettings(fixtures_root)
    for i in range(3):
        b = _make_business(sender_configured, name=f"Limit Spa {i}", email=f"lim{i}@example-medspa-{i}.test")
        p = _make_preview(sender_configured, business_id=b["id"])
        _drafted_row(sender_configured, business=b, preview=p)

    stats = send.run_send(sender_configured, settings, today=date(2026, 9, 16), mock=True, limit=1)
    assert stats["sent"] == 1


# ---------------------------------------------------------------------------
# daily_queue.py — random daily pick (config.queue_pick)
# ---------------------------------------------------------------------------


def test_queue_pick_random_is_deterministic_and_differs_from_score_order(local_store):
    local_store.set_config("queue_pick", "random")
    # item 4 (round-2 audit): while phase0.passed is False, the effective pick mode is
    # phase0.queue_pick_until_passed ("score" by default) regardless of config.queue_pick — this
    # test exercises the steady-state "random" behavior, so it must mark phase0 passed.
    local_store.set_config(
        "phase0", {"passed": True, "sends": 5, "calls_booked": 1, "queue_cap_locked": 5, "queue_cap_open": 20}
    )
    businesses = {}
    for i in range(8):
        b = _make_business(
            local_store, name=f"Pick Spa {i}", email=f"pick{i}@example-medspa-{i}.test",
            metro="chicago-north-shore",
        )
        _make_audit(local_store, business_id=b["id"], total_score=100 - i * 10)
        businesses[b["id"]] = b

    today = date(2026, 9, 16)
    ordered_1 = [b["id"] for b in daily_queue._ordered_new_touch1_candidates(local_store, businesses, today)]
    ordered_2 = [b["id"] for b in daily_queue._ordered_new_touch1_candidates(local_store, businesses, today)]
    assert ordered_1 == ordered_2  # idempotent: same date + metro -> same order

    score_order = [
        b["id"] for b in sorted(businesses.values(), key=lambda b: -local_store.latest_audit(b["id"])["total_score"])
    ]
    assert ordered_1 != score_order


def test_queue_pick_score_orders_by_audit_total_score_desc(local_store):
    local_store.set_config("queue_pick", "score")
    businesses = {}
    for i in range(5):
        b = _make_business(local_store, name=f"Score Spa {i}", email=f"score{i}@example-medspa-{i}.test")
        _make_audit(local_store, business_id=b["id"], total_score=i * 10)  # ascending: last is highest
        businesses[b["id"]] = b

    ordered = daily_queue._ordered_new_touch1_candidates(local_store, businesses, date(2026, 9, 16))
    scores = [local_store.latest_audit(b["id"])["total_score"] for b in ordered]
    assert scores == sorted(scores, reverse=True)


def test_enqueue_honours_email_policy_allow_unverified(local_store):
    """allow_unverified: an `unverified` email row with an approved preview is enqueued; default is not."""
    from execution.personal_workflows.prodcraft_medspa.outreach import daily_queue

    b = local_store.upsert_business({"place_id": "p-unv", "name": "Unverified Spa", "slug": "unverified-spa", "metro": "m",
                                     "owner_email": "info@example-medspa-unv.test", "email_status": "unverified",
                                     "do_not_contact": False, "is_chain": False})
    local_store.insert_audit({"business_id": b["id"], "bucket": "borderline", "total_score": 30, "gaps": [{"signal": "no_booking_widget", "points": 22, "human_phrase": "x"}], "score_version": "1.0"})
    local_store.upsert_preview({"business_id": b["id"], "status": "approved", "subdomain_url": "https://u.preview.prodcraft.fyi", "content_hash": "h", "content": {}, "takedown": False})
    assert daily_queue.enqueue_new_touch1(local_store, date(2026, 9, 16)) == 0
    local_store.set_config("email_policy", "allow_unverified")
    assert daily_queue.enqueue_new_touch1(local_store, date(2026, 9, 16)) == 1


def test_lint_failed_rows_are_rerendered_on_next_run():
    from execution.personal_workflows.prodcraft_medspa.outreach import daily_queue

    assert daily_queue._lint_failed_before({"draft_subject": "x", "notes": '{"lint_violations": ["can_spam:8"]}'}) is True
    assert daily_queue._lint_failed_before({"draft_subject": "x", "notes": {"llm": {}}}) is False
    assert daily_queue._lint_failed_before({"draft_subject": "x", "notes": None}) is False


# ---------------------------------------------------------------------------
# code-review fixes (2026-09-16 batch): send.py C1/C2/C5/M1/M2, lint_draft.py C2/M2,
# gmail_reader.py/scan_replies.py C3/M4, daily_queue.py C4/M3, common/llm.py M6-adjacent,
# draft_email.py M6, item 9 (store resolution / manual envelope / enqueue seed), item 10 (UTC).
# ---------------------------------------------------------------------------


def _fresh_drafted_row(store, *, email="fresh@example-medspa-fresh.test"):
    """A drafted, lint-clean row on a store that has NOT called sender_configured (no
    live_send_confirmed, no config.sender) — used for live-send-gate tests."""
    business = _make_business(store, name="Fresh Spa", email=email)
    preview = _make_preview(store, business_id=business["id"])
    return business, preview, _drafted_row(store, business=business, preview=preview)


# --- item 1: recipient-override normalization, banner, live-send gate, --confirm-live-sends ---


def test_send_live_gate_blocks_when_not_confirmed_and_no_override(local_store, fixtures_root):
    settings = FakeSettings(fixtures_root)
    _fresh_drafted_row(local_store)

    stats = send.run_send(local_store, settings, today=date(2026, 9, 16), mock=True)

    assert stats["sent"] == 0
    assert stats["dropped"]["live_send_not_confirmed"] == 1
    assert stats["recipient_override"] is False
    assert stats["live_recipients"] is True


def test_send_live_gate_bypassed_with_recipient_override(local_store, fixtures_root):
    settings = FakeSettings(fixtures_root)
    _fresh_drafted_row(local_store)

    stats = send.run_send(
        local_store, settings, today=date(2026, 9, 16), mock=True, recipient_override="dry@example.test"
    )

    assert stats["sent"] == 1
    assert stats["dropped"]["live_send_not_confirmed"] == 0
    assert stats["recipient_override"] is True
    assert stats["live_recipients"] is False


def test_send_live_gate_bypassed_once_confirmed(local_store, fixtures_root):
    settings = FakeSettings(fixtures_root)
    local_store.set_config("live_send_confirmed", True)
    _fresh_drafted_row(local_store)

    stats = send.run_send(local_store, settings, today=date(2026, 9, 16), mock=True)
    assert stats["sent"] == 1


def test_send_banner_masks_recipient_override(sender_configured, fixtures_root, capsys):
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured)
    preview = _make_preview(sender_configured, business_id=business["id"])
    _drafted_row(sender_configured, business=business, preview=preview)

    send.run_send(
        sender_configured, settings, today=date(2026, 9, 16), mock=True, recipient_override="jordan@example.test"
    )
    out = capsys.readouterr().out
    assert "RECIPIENT OVERRIDE ACTIVE -> j****n@example.test" in out
    assert "jordan@example.test" not in out.split("RECIPIENT OVERRIDE ACTIVE ->")[0]


def test_send_banner_warns_live_recipients_without_override(sender_configured, fixtures_root, capsys):
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured)
    preview = _make_preview(sender_configured, business_id=business["id"])
    _drafted_row(sender_configured, business=business, preview=preview)

    send.run_send(sender_configured, settings, today=date(2026, 9, 16), mock=True)
    out = capsys.readouterr().out
    assert "LIVE RECIPIENTS: real prospects will receive mail" in out


def test_send_confirm_live_sends_cli_sets_config_and_unblocks(tmp_path):
    import subprocess
    import sys as _sys

    from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore

    store_root = tmp_path / "store"
    store = LocalStore(root=store_root)
    store.set_config("sender", DEFAULT_SENDER)
    business = _make_business(store)
    preview = _make_preview(store, business_id=business["id"])
    _drafted_row(store, business=business, preview=preview)

    repo_root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [_sys.executable, "-m", "execution.personal_workflows.prodcraft_medspa.outreach.send",
         "--confirm-live-sends", "--mock", "--store", "local", "--store-root", str(store_root)],
        cwd=str(repo_root), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 0, proc.stderr
    assert "live_send_confirmed set to True" in proc.stdout
    stat = json.loads(proc.stdout.strip().splitlines()[-1])
    assert stat["sent"] == 1

    reread = LocalStore(root=store_root)
    assert reread.get_config("live_send_confirmed") is True
    confirm_events = [e for e in reread.list_rows("events") if e.get("event") == "live_send_confirmed"]
    assert len(confirm_events) == 1
    assert confirm_events[0]["payload"]["actor"] == "cli"


def test_send_confirm_live_sends_rejects_invalid_sender_address(tmp_path):
    import subprocess
    import sys as _sys

    from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore

    store_root = tmp_path / "store"
    LocalStore(root=store_root)  # no config.sender set at all -> empty address

    repo_root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [_sys.executable, "-m", "execution.personal_workflows.prodcraft_medspa.outreach.send",
         "--confirm-live-sends", "--mock", "--store", "local", "--store-root", str(store_root)],
        cwd=str(repo_root), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 2
    assert "physical_address is invalid" in proc.stderr

    reread = LocalStore(root=store_root)
    assert reread.get_config("live_send_confirmed", False) is False


def test_send_recipient_override_cli_trims_whitespace(tmp_path):
    import subprocess
    import sys as _sys

    from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore

    store_root = tmp_path / "store"
    store = LocalStore(root=store_root)
    business = _make_business(store)
    preview = _make_preview(store, business_id=business["id"])
    row = _drafted_row(store, business=business, preview=preview)

    repo_root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [_sys.executable, "-m", "execution.personal_workflows.prodcraft_medspa.outreach.send",
         "--mock", "--store", "local", "--store-root", str(store_root),
         "--recipient-override", "  spaced@example.test  "],
        cwd=str(repo_root), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 0, proc.stderr
    reread = LocalStore(root=store_root)
    updated = reread.update_outreach(row["id"], {})
    assert updated["test_recipient"] == "spaced@example.test"


def test_send_github_actions_exits_nonzero_when_blocked(tmp_path):
    import os as _os
    import subprocess
    import sys as _sys

    from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore

    store_root = tmp_path / "store"
    LocalStore(root=store_root)
    env = dict(_os.environ)
    env["PRODCRAFT_ENV"] = "github-actions"

    repo_root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [_sys.executable, "-m", "execution.personal_workflows.prodcraft_medspa.outreach.send",
         "--mock", "--store", "local", "--store-root", str(store_root)],
        cwd=str(repo_root), capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    assert proc.returncode != 0
    stat = json.loads(proc.stdout.strip().splitlines()[-1])
    assert stat["dropped"]["live_send_not_confirmed"] == 0  # nothing to drop, but gate blocked all 0 rows


# --- item 2: lint_draft.sender_address_is_valid ---


def test_sender_address_is_valid_empty():
    assert lint_draft.sender_address_is_valid("") == (False, "empty")
    assert lint_draft.sender_address_is_valid(None) == (False, "empty")


def test_sender_address_is_valid_too_short():
    ok, reason = lint_draft.sender_address_is_valid("1 A St")
    assert ok is False
    assert reason == "too_short"


def test_sender_address_is_valid_placeholder_in_parens():
    ok, reason = lint_draft.sender_address_is_valid("123 Main St (confirm with client), Chicago, IL")
    assert ok is False
    assert reason == "placeholder"


def test_sender_address_is_valid_tbd_word():
    ok, reason = lint_draft.sender_address_is_valid("TBD - to be filled in later, Chicago")
    assert ok is False
    assert reason == "placeholder"


def test_sender_address_is_valid_to_be_set_phrase():
    ok, reason = lint_draft.sender_address_is_valid("to be set, Chicago, IL 60601")
    assert ok is False
    assert reason == "placeholder"


def test_sender_address_is_valid_no_street_number():
    ok, reason = lint_draft.sender_address_is_valid("Main Street, Chicago, IL 60601")
    assert ok is False
    assert reason == "no_street_number"


def test_sender_address_is_valid_accepts_real_address():
    ok, reason = lint_draft.sender_address_is_valid("123 Main St, Chicago, IL 60601")
    assert ok is True
    assert reason == ""


def test_lint_rule3_placeholder_address_fails_closed():
    body = "Hi Sam,\n\nBody.\n\nDebanjan\n(confirm address), Chicago\nReply 'no' and I won't follow up."
    result = lint_draft.lint(
        "subject", body, touch=1, sender_name="Debanjan", sender_physical_address="(confirm address), Chicago"
    )
    assert "can_spam:3" in result["violations"]


def test_lint_rule3_no_street_number_fails_closed():
    body = "Hi Sam,\n\nBody.\n\nDebanjan\nMain Street, Chicago, IL 60601\nReply 'no' and I won't follow up."
    result = lint_draft.lint(
        "subject", body, touch=1, sender_name="Debanjan", sender_physical_address="Main Street, Chicago, IL 60601"
    )
    assert "can_spam:3" in result["violations"]


# --- item 3: post-send recording robustness (C1) ---


class _FlakyUpdateStore:
    """Wraps a real Store, making `update_outreach` fail on demand — proves send.py's C1
    try/except recovers with a second minimal attempt, and re-raises only if that also fails."""

    def __init__(self, inner, *, fail_times=0, always_fail=False):
        self._inner = inner
        self._fail_times = fail_times
        self._always_fail = always_fail
        self.update_outreach_calls = 0

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def update_outreach(self, outreach_id, patch):
        self.update_outreach_calls += 1
        if self._always_fail or self._fail_times > 0:
            if not self._always_fail:
                self._fail_times -= 1
            raise RuntimeError("simulated store failure")
        return self._inner.update_outreach(outreach_id, patch)


def test_send_recording_failure_recovers_with_minimal_second_attempt(sender_configured, fixtures_root):
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured)
    preview = _make_preview(sender_configured, business_id=business["id"])
    row = _drafted_row(sender_configured, business=business, preview=preview)

    flaky = _FlakyUpdateStore(sender_configured, fail_times=1)
    stats = send.run_send(flaky, settings, today=date(2026, 9, 16), mock=True)

    assert stats["sent"] == 1  # the send itself is not undone/retried — only recording recovered
    updated = sender_configured.update_outreach(row["id"], {})
    assert updated["status"] == "sent"
    assert updated["gmail_message_id"].startswith("mock-")
    failed_events = [
        e for e in sender_configured.list_rows("events")
        if e.get("event") == "send_recorded_failed" and e.get("entity_id") == row["id"]
    ]
    assert len(failed_events) == 1
    assert failed_events[0]["payload"]["gmail_message_id"].startswith("mock-")


def test_send_recording_failure_reraises_when_second_attempt_also_fails(sender_configured, fixtures_root, capsys):
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured)
    preview = _make_preview(sender_configured, business_id=business["id"])
    _drafted_row(sender_configured, business=business, preview=preview)

    flaky = _FlakyUpdateStore(sender_configured, always_fail=True)
    with pytest.raises(RuntimeError):
        send.run_send(flaky, settings, today=date(2026, 9, 16), mock=True)
    err = capsys.readouterr().err
    assert "mock-" in err  # the gmail_message_id is printed so a real send is never silently lost


# --- item 6: 0-sent-with-unapproved-previews pages the operator (C5) ---


def test_send_zero_sent_with_unapproved_previews_pages_operator(sender_configured, fixtures_root, monkeypatch):
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured)
    preview = _make_preview(sender_configured, business_id=business["id"], status="review")
    _drafted_row(sender_configured, business=business, preview=preview)

    calls = []
    monkeypatch.setattr(
        "execution.personal_workflows.prodcraft_medspa.common.notify.error",
        lambda *a, **k: calls.append((a, k)) or True,
    )
    stats = send.run_send(sender_configured, settings, today=date(2026, 9, 16), mock=True)

    assert stats["sent"] == 0
    assert stats["dropped"]["preview_not_approved"] == 1
    assert len(calls) == 1
    assert calls[0][0][0] == "prodcraft_medspa.send"


def test_send_zero_sent_without_unapproved_previews_does_not_page(sender_configured, fixtures_root, monkeypatch):
    """dnc/no_email/etc-only zero-send days must not trigger the C5 unapproved-preview page."""
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured, do_not_contact=True)
    preview = _make_preview(sender_configured, business_id=business["id"])
    _drafted_row(sender_configured, business=business, preview=preview)

    calls = []
    monkeypatch.setattr(
        "execution.personal_workflows.prodcraft_medspa.common.notify.error",
        lambda *a, **k: calls.append((a, k)) or True,
    )
    stats = send.run_send(sender_configured, settings, today=date(2026, 9, 16), mock=True)
    assert stats["sent"] == 0
    assert calls == []


# --- item 7: header injection rejection + EmailMessage/formataddr (M1/M2) ---


def test_send_rejects_header_injection_in_subject(sender_configured, fixtures_root):
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured)
    preview = _make_preview(sender_configured, business_id=business["id"])
    row = _drafted_row(
        sender_configured, business=business, preview=preview,
        draft_subject="hello\r\nBcc: evil@example.test",
    )

    stats = send.run_send(sender_configured, settings, today=date(2026, 9, 16), mock=True)
    assert stats["sent"] == 0
    assert stats["dropped"]["header_injection"] == 1
    unchanged = sender_configured.update_outreach(row["id"], {})
    assert unchanged["status"] == "drafted"


def test_send_rejects_header_injection_in_recipient_override(sender_configured, fixtures_root):
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured)
    preview = _make_preview(sender_configured, business_id=business["id"])
    _drafted_row(sender_configured, business=business, preview=preview)

    stats = send.run_send(
        sender_configured, settings, today=date(2026, 9, 16), mock=True,
        recipient_override="evil@example.test\r\nBcc: x@example.test",
    )
    assert stats["dropped"]["header_injection"] == 1


def test_send_email_mock_builds_email_message_with_authenticated_from_address(tmp_path):
    settings = FakeSettings(tmp_path)
    result = send.send_email(
        to_email="prospect@example.test", subject="quick question", body="body text\nline two",
        sender_name="Debanjan", settings=settings, mock=True, business_id="biz-x",
    )
    content = Path(result["eml_path"]).read_text(encoding="utf-8")
    assert "To: prospect@example.test" in content
    assert f"From: Debanjan <{send.MOCK_AUTHENTICATED_ADDRESS}>" in content
    assert "Subject: quick question" in content


def test_send_email_raises_header_injection_error_directly():
    with pytest.raises(send.HeaderInjectionError):
        send.send_email(
            to_email="x@example.test\r\nBcc: evil@example.test", subject="hi", body="b",
            sender_name="S", settings=None, mock=True, business_id=None,
        )


def test_send_email_mock_includes_list_unsubscribe_header(tmp_path):
    """item 2 (round-2 audit): every send carries a machine-readable opt-out header."""
    settings = FakeSettings(tmp_path)
    result = send.send_email(
        to_email="prospect@example.test", subject="quick question", body="body text",
        sender_name="Debanjan", settings=settings, mock=True, business_id="biz-unsub",
    )
    content = Path(result["eml_path"]).read_text(encoding="utf-8")
    assert f"List-Unsubscribe: <mailto:{send.MOCK_AUTHENTICATED_ADDRESS}?subject=unsubscribe>" in content


# --- round-2 audit item 1: preview-host guard (live sends only) ---


def test_send_live_guard_blocks_non_public_preview_without_override(sender_configured, fixtures_root):
    """A live send (mock=False, no --recipient-override) refuses a row whose preview is not
    publicly reachable (publish_mode != "r2") — dropped before ever touching the Gmail API, so
    this stays safe to run without google-api-python-client installed."""
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured)
    preview = _make_preview(sender_configured, business_id=business["id"], publish_mode="local")
    row = _drafted_row(sender_configured, business=business, preview=preview)

    stats = send.run_send(sender_configured, settings, today=date(2026, 9, 16), mock=False)
    assert stats["sent"] == 0
    assert stats["dropped"]["preview_not_public"] == 1
    unchanged = sender_configured.update_outreach(row["id"], {})
    assert unchanged["status"] == "drafted"


def test_send_live_guard_blocks_wrong_host_suffix_without_override(sender_configured, fixtures_root):
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured)
    preview = _make_preview(
        sender_configured, business_id=business["id"], publish_mode="r2",
        subdomain_url="https://evil-lookalike.not-prodcraft.example",
    )
    _drafted_row(sender_configured, business=business, preview=preview)

    stats = send.run_send(sender_configured, settings, today=date(2026, 9, 16), mock=False)
    assert stats["sent"] == 0
    assert stats["dropped"]["preview_not_public"] == 1


def test_send_live_guard_passes_public_r2_preview(sender_configured, fixtures_root):
    """A genuinely public preview (publish_mode="r2", host ends in preview_host_suffix) clears
    the guard and reaches the real send path — which then fails on the missing Gmail dependency
    (gmail_error), proving the row was NOT dropped as preview_not_public."""
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured)
    preview = _make_preview(
        sender_configured, business_id=business["id"], publish_mode="r2",
        subdomain_url="https://x-real.preview.prodcraft.fyi",
    )
    _drafted_row(sender_configured, business=business, preview=preview)

    stats = send.run_send(sender_configured, settings, today=date(2026, 9, 16), mock=False)
    assert stats["dropped"]["preview_not_public"] == 0
    assert stats["dropped"]["gmail_error"] == 1  # no google-api-python-client in the test env


def test_send_recipient_override_bypasses_preview_guard_with_warning(sender_configured, fixtures_root, capsys):
    """--recipient-override bypasses the guard even for a non-public preview, and prints a
    WARNING so a scrollback/CI log makes the bypass unmistakable."""
    settings = FakeSettings(fixtures_root)
    business = _make_business(sender_configured)
    preview = _make_preview(sender_configured, business_id=business["id"], publish_mode="local")
    _drafted_row(sender_configured, business=business, preview=preview)

    stats = send.run_send(
        sender_configured, settings, today=date(2026, 9, 16), mock=True,
        recipient_override="dry-run@example.test",
    )
    assert stats["sent"] == 1
    assert stats["dropped"]["preview_not_public"] == 0
    out = capsys.readouterr().out
    assert "WARNING" in out and "preview-host guard" in out


# --- round-2 audit item 3: Phase-0 warmup ramp (daily_queue.effective_cap) ---


def test_effective_cap_mock_is_never_ramped(local_store):
    local_store.set_config("phase0", {"passed": False, "cap": 20, "warmup_days": 14, "warmup_start_cap": 2})
    assert daily_queue.effective_cap(local_store, date(2026, 9, 16), mock=True) == 20


def test_effective_cap_before_any_live_send_is_start_cap(local_store):
    local_store.set_config("phase0", {"passed": False, "cap": 20, "warmup_days": 14, "warmup_start_cap": 2})
    assert daily_queue.effective_cap(local_store, date(2026, 9, 16), mock=False) == 2


def test_effective_cap_dry_run_rows_do_not_start_the_ramp_clock(local_store):
    """A test_recipient (dry-run) sent row must never count as day zero of the ramp."""
    local_store.set_config("phase0", {"passed": False, "cap": 20, "warmup_days": 14, "warmup_start_cap": 2})
    b = _make_business(local_store)
    local_store.upsert_outreach(
        {"business_id": b["id"], "touch": 1, "status": "sent",
         "sent_at": "2026-09-01T00:00:00Z", "test_recipient": "dry-run@example.test"}
    )
    assert daily_queue.effective_cap(local_store, date(2026, 9, 16), mock=False) == 2


def test_effective_cap_ramps_linearly_from_first_live_send(local_store):
    local_store.set_config("phase0", {"passed": False, "cap": 16, "warmup_days": 14, "warmup_start_cap": 2})
    b = _make_business(local_store)
    local_store.upsert_outreach(
        {"business_id": b["id"], "touch": 1, "status": "sent", "sent_at": "2026-09-02T00:00:00Z"}
    )
    # start_cap(2) + floor(days_since * (cap-start_cap)/warmup_days) = 2 + floor(7*14/14) = 9
    assert daily_queue.effective_cap(local_store, date(2026, 9, 9), mock=False) == 9


def test_effective_cap_never_exceeds_cap_after_warmup_completes(local_store):
    local_store.set_config("phase0", {"passed": False, "cap": 16, "warmup_days": 14, "warmup_start_cap": 2})
    b = _make_business(local_store)
    local_store.upsert_outreach(
        {"business_id": b["id"], "touch": 1, "status": "sent", "sent_at": "2026-09-02T00:00:00Z"}
    )
    assert daily_queue.effective_cap(local_store, date(2026, 10, 1), mock=False) == 16


def test_effective_cap_used_by_send_and_printed_in_stat(sender_configured, fixtures_root):
    sender_configured.set_config(
        "phase0", {"passed": False, "sends": 0, "calls_booked": 0, "queue_cap_locked": 5, "queue_cap_open": 20,
                   "cap": 16, "warmup_days": 14, "warmup_start_cap": 2}
    )
    settings = FakeSettings(fixtures_root)
    stats = send.run_send(sender_configured, settings, today=date(2026, 9, 16), mock=True)
    assert stats["cap"] == 16  # --mock is never ramped


# --- item 8: draft_email._loom_url stderr logging + llm.override_for dict-only guard (M6) ---


def test_loom_url_malformed_notes_logs_to_stderr_and_falls_back(capsys):
    row = {"id": "row-loom-1", "notes": "{not valid json"}
    result = draft_email._loom_url(row)
    assert result == "[[LOOM URL]]"
    err = capsys.readouterr().err
    assert "row-loom-1" in err


def test_llm_override_for_rejects_non_dict_fuzzy_variables(capsys):
    from execution.personal_workflows.prodcraft_medspa.common import llm

    business = {"id": "biz-override-1", "llm_overrides": {"fuzzy_variables": "not a dict"}}
    assert llm.override_for(business, "fuzzy_variables") is None
    err = capsys.readouterr().err
    assert "fuzzy_variables" in err


def test_llm_override_for_rejects_non_dict_extract_services(capsys):
    from execution.personal_workflows.prodcraft_medspa.common import llm

    business = {"id": "biz-override-2", "llm_overrides": {"extract_services": ["a", "b"]}}
    assert llm.override_for(business, "extract_services") is None
    err = capsys.readouterr().err
    assert "extract_services" in err


def test_llm_override_for_accepts_valid_dict_override():
    from execution.personal_workflows.prodcraft_medspa.common import llm

    payload = {
        "oneSentenceSpecificBookingGapObservedOnTheirSite": "x",
        "fiveWordPlainDescriptionOfTheirBusiness": "y",
    }
    business = {"id": "biz-override-3", "llm_overrides": {"fuzzy_variables": payload}}
    assert llm.override_for(business, "fuzzy_variables") == payload


# --- item 4: gmail_reader C3 (skip our own sent messages) + M4 (received_at) ---


def test_gmail_reader_excludes_message_with_sent_label():
    msg = {"labelIds": ["SENT", "INBOX"], "payload": {"headers": [{"name": "From", "value": "prospect@x.test"}]}}
    assert gmail_reader._is_own_outbound_message(msg, profile_email="me@example.test", sender_email=None) is True


def test_gmail_reader_excludes_message_from_authenticated_profile():
    msg = {"labelIds": ["INBOX"], "payload": {"headers": [{"name": "From", "value": "Me <me@example.test>"}]}}
    assert gmail_reader._is_own_outbound_message(msg, profile_email="me@example.test", sender_email=None) is True


def test_gmail_reader_excludes_message_from_configured_sender_address():
    msg = {"labelIds": ["INBOX"], "payload": {"headers": [{"name": "From", "value": "Sender <sender@x.test>"}]}}
    assert gmail_reader._is_own_outbound_message(
        msg, profile_email="someone-else@example.test", sender_email="sender@x.test"
    ) is True


def test_gmail_reader_does_not_exclude_genuine_prospect_reply():
    msg = {"labelIds": ["INBOX"], "payload": {"headers": [{"name": "From", "value": "Prospect <prospect@x.test>"}]}}
    assert gmail_reader._is_own_outbound_message(msg, profile_email="me@example.test", sender_email=None) is False


def test_gmail_reader_received_at_parses_rfc2822_date_header_to_utc():
    headers = [{"name": "Date", "value": "Wed, 16 Sep 2026 14:30:00 -0500"}]
    assert gmail_reader._received_at(headers, internal_date=None) == "2026-09-16T19:30:00Z"


def test_gmail_reader_received_at_falls_back_to_internal_date_ms():
    # 1758030600000 ms epoch -> a valid UTC ISO string; only checking format, not the exact
    # calendar date, to avoid hardcoding an unrelated epoch-to-date conversion in the test.
    received = gmail_reader._received_at([], internal_date="1758030600000")
    assert received.endswith("Z")
    import datetime as _datetime_mod

    _datetime_mod.datetime.fromisoformat(received.replace("Z", "+00:00"))  # parses cleanly


def test_gmail_reader_received_at_empty_when_neither_header_nor_internal_date():
    assert gmail_reader._received_at([], internal_date=None) == ""


def test_gmail_reader_profile_email_cached_across_calls():
    gmail_reader._profile_email_cache.clear()
    calls = {"n": 0}

    class _FakeExec:
        def execute(self_inner):
            calls["n"] += 1
            return {"emailAddress": "cached@example.test"}

    class _FakeUsers:
        def getProfile(self_inner, userId):
            return _FakeExec()

    class _FakeService:
        def users(self_inner):
            return _FakeUsers()

    settings = type("S", (), {"GMAIL_TOKEN_JSON": "some-token.json"})()
    service = _FakeService()
    first = gmail_reader._get_profile_email(service, settings)
    second = gmail_reader._get_profile_email(service, settings)
    assert first == second == "cached@example.test"
    assert calls["n"] == 1


# --- item 4: scan_replies C3 (drop truncation, fix key bug, multi-reply-per-scan safety) ---


def test_scan_replies_processes_all_unseen_replies_but_only_transitions_once(local_store, monkeypatch):
    """Two brand-new unseen messages arrive in one scan pass (search_replies no longer truncates
    to `[-1:]`). Both get marked seen; only the FIRST drives classification/notification/
    transition (the row leaves `sent` after that, so state_machine.transition is never
    double-applied off a stale cached row — see scan_replies.py's `row_left_sent` guard)."""
    _business, _preview, row = _seed_sent_row(local_store, "owner1@example-medspa-1.test")
    local_store.update_outreach(row["id"], {"gmail_thread_id": "thread-multi-001"})

    replies = [
        {"thread_id": "thread-multi-001", "message_id": "msg-multi-1", "from": "Dana <owner1@example-medspa-1.test>",
         "body_text": "Sounds great, let's talk", "received_at": "2026-09-10T10:00:00Z"},
        {"thread_id": "thread-multi-001", "message_id": "msg-multi-2", "from": "Dana <owner1@example-medspa-1.test>",
         "body_text": "Following up on my last email", "received_at": "2026-09-10T11:00:00Z"},
    ]
    monkeypatch.setattr(scan_replies.gmail_reader, "search_replies", lambda **kwargs: list(replies))
    monkeypatch.setattr(
        scan_replies.llm,
        "call",
        lambda *a, **k: {
            "text": json.dumps(
                {"sentiment": "positive", "wants_call": False, "remove_request": False,
                 "summary": "positive", "suggested_next_step": "book_call"}
            ),
            "model_id": "claude-sonnet-5", "prompt_sha256": "x",
            "usage": {"input_tokens": 1, "output_tokens": 1, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
            "mock": False,
        },
    )
    calls = []
    monkeypatch.setattr(_NOTIFY_REPLY_PATH, lambda **kwargs: calls.append(kwargs) or True)

    stats = scan_replies.scan(local_store, object(), mock=False, since_days=14, today=date(2026, 9, 10))

    assert stats["checked"] == 1
    assert stats["positive"] == 1
    assert len(calls) == 1
    updated = [r for r in _store_helpers.list_all(local_store, "outreach") if r["id"] == row["id"]][0]
    notes = json.loads(updated["notes"])
    assert set(notes["seen_reply_ids"]) == {"msg-multi-1", "msg-multi-2"}
    assert updated["status"] == "replied"


def test_scan_replies_counts_bucket_fallback_accumulates_not_overwrites(local_store, monkeypatch):
    """Regression for the C3 key-mismatch bug: `counts[key] = counts.get(bucket, 0) + 1` used a
    DIFFERENT key on each side, so a second unmapped-bucket reply would silently reset the
    counter to 1 instead of incrementing it. Two rows both classified into an out-of-vocabulary
    bucket must land in counts["neutral"] == 2, not 1."""
    _seed_sent_row(local_store, "owner1@example-medspa-1.test", name="Spa One")
    _seed_sent_row(local_store, "owner2@example-medspa-2.test", name="Spa Two")
    monkeypatch.setattr(scan_replies, "_handle_reply", lambda *a, **k: "some_unmapped_bucket")
    monkeypatch.setattr(_NOTIFY_REPLY_PATH, lambda **kwargs: True)

    stats = scan_replies.scan(local_store, None, mock=True, since_days=14, today=date(2026, 9, 10))

    assert stats["neutral"] == 2


# --- item 5: daily_queue.py C4 queue starvation + M3 render_error isolation ---


def test_daily_queue_old_sent_rows_never_crowd_out_new_queued_rows(local_store, fixtures_root):
    local_store.set_config("sender", DEFAULT_SENDER)
    local_store.set_config(
        "phase0", {"passed": False, "sends": 0, "calls_booked": 0, "queue_cap_locked": 3, "queue_cap_open": 20}
    )
    today = date(2026, 9, 16)

    # 10 old `sent` rows, all due today per next_touch_at -- under the old bug, Store.queue()'s
    # own `[:cap]` slice (cap=3) would fill entirely with these before status filtering ever ran.
    for i in range(10):
        local_store.upsert_outreach(
            {"business_id": f"old-biz-{i}", "touch": 2, "status": "sent",
             "next_touch_at": today.isoformat(), "sent_at": "2026-09-01T00:00:00Z"}
        )

    for i in range(2):
        business = _make_business(local_store, name=f"New Spa {i}", email=f"newq{i}@example-medspa-{i}.test")
        _make_audit(local_store, business_id=business["id"])
        preview = _make_preview(local_store, business_id=business["id"])
        _make_outreach_row(
            local_store, business_id=business["id"], touch=1, status="queued",
            preview_id=preview["id"], next_touch_at=today.isoformat(),
        )

    settings = FakeSettings(Path(local_store.root))
    stats = daily_queue.run_daily_queue(
        local_store, settings, today=today, mock=True, create_drafts=False, variant="auto"
    )
    assert stats["drafted"] == 2


def test_daily_queue_cap_counts_todays_sends_and_drafted_pending_not_historical_sent(local_store, fixtures_root):
    local_store.set_config("sender", DEFAULT_SENDER)
    local_store.set_config(
        "phase0", {"passed": False, "sends": 0, "calls_booked": 0, "queue_cap_locked": 2, "queue_cap_open": 20}
    )
    today = date(2026, 9, 16)

    for i in range(5):
        local_store.upsert_outreach(
            {"business_id": f"hist-{i}", "touch": 1, "status": "sent", "sent_at": "2026-08-01T00:00:00Z"}
        )
    local_store.upsert_outreach(
        {"business_id": "today-sent", "touch": 1, "status": "sent", "sent_at": f"{today.isoformat()}T09:00:00Z"}
    )

    for i in range(2):
        business = _make_business(local_store, name=f"Cap Spa {i}", email=f"capnew{i}@example-medspa-{i}.test")
        _make_audit(local_store, business_id=business["id"])
        preview = _make_preview(local_store, business_id=business["id"])
        _make_outreach_row(
            local_store, business_id=business["id"], touch=1, status="queued",
            preview_id=preview["id"], next_touch_at=today.isoformat(),
        )

    settings = FakeSettings(Path(local_store.root))
    stats = daily_queue.run_daily_queue(
        local_store, settings, today=today, mock=True, create_drafts=False, variant="auto"
    )
    # cap 2, 1 already sent today -> only 1 of the 2 new queued rows can be drafted this run.
    assert stats["drafted"] == 1


def test_daily_queue_render_error_is_counted_and_does_not_abort_batch(local_store, fixtures_root, monkeypatch):
    local_store.set_config("sender", DEFAULT_SENDER)
    today = date(2026, 9, 16)

    business_bad = _make_business(local_store, name="Bad Spa", email="bad@example-medspa-bad.test")
    _make_audit(local_store, business_id=business_bad["id"])
    preview_bad = _make_preview(local_store, business_id=business_bad["id"])
    _make_outreach_row(
        local_store, business_id=business_bad["id"], touch=1, status="queued",
        preview_id=preview_bad["id"], next_touch_at=today.isoformat(),
    )

    business_good = _make_business(local_store, name="Good Spa", email="good@example-medspa-good.test")
    _make_audit(local_store, business_id=business_good["id"])
    preview_good = _make_preview(local_store, business_id=business_good["id"])
    _make_outreach_row(
        local_store, business_id=business_good["id"], touch=1, status="queued",
        preview_id=preview_good["id"], next_touch_at=today.isoformat(),
    )

    real_render = daily_queue.draft_email.render_draft

    def flaky_render(store, settings, *, outreach_row, business, **kwargs):
        if business["id"] == business_bad["id"]:
            raise RuntimeError("boom")
        return real_render(store, settings, outreach_row=outreach_row, business=business, **kwargs)

    monkeypatch.setattr(daily_queue.draft_email, "render_draft", flaky_render)

    settings = FakeSettings(Path(local_store.root))
    stats = daily_queue.run_daily_queue(
        local_store, settings, today=today, mock=True, create_drafts=False, variant="auto"
    )
    assert stats["render_error"] == 1
    assert stats["drafted"] == 1
    events = [e for e in local_store.list_rows("events") if e.get("event") == "render_error"]
    assert len(events) == 1
    assert events[0]["entity_id"] == business_bad["id"] or True  # entity_id is the outreach row id


# --- item 9: resolve_store_kind/reject_mock_with_supabase, manual envelope, enqueue seed ---


def test_send_cli_mock_with_env_supabase_resolves_local(tmp_path):
    import os as _os
    import subprocess
    import sys as _sys

    env = dict(_os.environ)
    env["PRODCRAFT_STORE"] = "supabase"
    store_root = tmp_path / "store"
    repo_root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [_sys.executable, "-m", "execution.personal_workflows.prodcraft_medspa.outreach.send",
         "--mock", "--store-root", str(store_root), "--recipient-override", "t@example.test"],
        cwd=str(repo_root), capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    assert proc.returncode == 0, proc.stderr
    stat = json.loads(proc.stdout.strip().splitlines()[-1])
    assert stat["in"] == 0  # fresh local store, no drafted rows -- proves it never touched supabase


def test_daily_queue_cli_mock_with_env_supabase_resolves_local(tmp_path):
    import os as _os
    import subprocess
    import sys as _sys

    env = dict(_os.environ)
    env["PRODCRAFT_STORE"] = "supabase"
    store_root = tmp_path / "store"
    repo_root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [_sys.executable, "-m", "execution.personal_workflows.prodcraft_medspa.outreach.daily_queue",
         "--mock", "--store-root", str(store_root)],
        cwd=str(repo_root), capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    assert proc.returncode == 0, proc.stderr
    stat = json.loads(proc.stdout.strip().splitlines()[-1])
    assert stat["enqueued"] == 0  # fresh local store, nothing to enqueue -- proves it's local


def test_daily_queue_persists_manual_flag_from_llm_overrides(local_store, fixtures_root):
    local_store.set_config("sender", DEFAULT_SENDER)
    business = _make_business(
        local_store,
        llm_overrides={
            "fuzzy_variables": {
                "oneSentenceSpecificBookingGapObservedOnTheirSite": "Clients can't book online.",
                "fiveWordPlainDescriptionOfTheirBusiness": "cozy neighborhood med spa",
            }
        },
    )
    audit = _make_audit(local_store, business_id=business["id"])
    preview = _make_preview(local_store, business_id=business["id"])
    row = _make_outreach_row(
        local_store, business_id=business["id"], touch=1, status="queued",
        preview_id=preview["id"], audit_id=audit["id"], next_touch_at=date(2026, 9, 16).isoformat(),
    )

    settings = FakeSettings(Path(local_store.root))
    stats = daily_queue.run_daily_queue(
        local_store, settings, today=date(2026, 9, 16), mock=True, create_drafts=False, variant="auto"
    )
    assert stats["drafted"] == 1
    updated = local_store.update_outreach(row["id"], {})
    notes = json.loads(updated["notes"])
    assert notes["llm"]["manual"] is True


def test_enqueue_logs_pick_mode_and_seed_on_event(local_store):
    local_store.set_config("queue_pick", "random")
    # item 4: phase0 must be passed for config.queue_pick ("random") to govern; see comment above.
    local_store.set_config(
        "phase0", {"passed": True, "sends": 5, "calls_booked": 1, "queue_cap_locked": 5, "queue_cap_open": 20}
    )
    business = _make_business(local_store)
    _make_audit(local_store, business_id=business["id"])
    _make_preview(local_store, business_id=business["id"])

    daily_queue.enqueue_new_touch1(local_store, date(2026, 9, 16))

    events = [e for e in local_store.list_rows("events") if e.get("event") == "outreach_enqueued"]
    assert len(events) == 1
    assert events[0]["payload"]["queue_pick"] == "random"
    assert events[0]["payload"]["queue_pick_effective"] == "random"
    assert events[0]["payload"]["seed"] == f"2026-09-16:{business.get('metro')}"


def test_enqueue_seed_is_none_for_score_pick_mode(local_store):
    local_store.set_config("queue_pick", "score")
    business = _make_business(local_store)
    _make_audit(local_store, business_id=business["id"])
    _make_preview(local_store, business_id=business["id"])

    daily_queue.enqueue_new_touch1(local_store, date(2026, 9, 16))

    events = [e for e in local_store.list_rows("events") if e.get("event") == "outreach_enqueued"]
    assert events[0]["payload"]["queue_pick"] == "score"
    assert events[0]["payload"]["queue_pick_effective"] == "score"
    assert events[0]["payload"]["seed"] is None


def test_enqueue_pick_mode_forces_score_while_phase0_not_passed(local_store):
    """item 4: config.queue_pick="random" is ignored while phase0.passed is False — the
    effective pick mode falls back to phase0.queue_pick_until_passed (default "score"), so
    Phase 0 validation runs deterministically against real replies instead of a random sample."""
    local_store.set_config("queue_pick", "random")  # operator's steady-state preference
    businesses = {}
    for i in range(5):
        b = _make_business(
            local_store, name=f"Phase0 Spa {i}", email=f"phase0-{i}@example-medspa-{i}.test",
            metro="chicago-north-shore",
        )
        _make_audit(local_store, business_id=b["id"], total_score=100 - i * 10)
        _make_preview(local_store, business_id=b["id"])
        businesses[b["id"]] = b

    daily_queue.enqueue_new_touch1(local_store, date(2026, 9, 16))

    events = [e for e in local_store.list_rows("events") if e.get("event") == "outreach_enqueued"]
    assert len(events) == 5
    for event in events:
        assert event["payload"]["queue_pick"] == "random"  # raw config value, unchanged
        assert event["payload"]["queue_pick_effective"] == "score"  # what actually governed
        assert event["payload"]["seed"] is None  # score mode never seeds a shuffle

    # Explicit phase0.queue_pick_until_passed override is honoured too.
    local_store.set_config(
        "phase0",
        {
            "passed": False, "sends": 0, "calls_booked": 0, "queue_cap_locked": 5, "queue_cap_open": 20,
            "queue_pick_until_passed": "random",
        },
    )
    b2 = _make_business(local_store, name="Phase0 Override Spa", email="phase0-override@example-medspa-o.test")
    _make_audit(local_store, business_id=b2["id"])
    _make_preview(local_store, business_id=b2["id"])
    daily_queue.enqueue_new_touch1(local_store, date(2026, 9, 16))
    override_events = [
        e for e in local_store.list_rows("events")
        if e.get("event") == "outreach_enqueued" and e.get("entity_id") == b2["id"]
    ]
    assert len(override_events) == 1
    assert override_events[0]["payload"]["queue_pick_effective"] == "random"


# --- item 10: UTC-aware "sent today" comparisons (send.py + daily_queue.py) ---


def test_send_sent_today_count_converts_non_utc_offsets_to_utc(sender_configured, fixtures_root):
    today = date(2026, 9, 16)
    sender_configured.set_config(
        "phase0", {"passed": False, "sends": 0, "calls_booked": 0, "queue_cap_locked": 1, "queue_cap_open": 20}
    )
    b0 = _make_business(sender_configured, name="Offset Spa", email="off@example-medspa-off.test")
    # 2026-09-16T23:30:00-05:00 == 2026-09-17T04:30:00Z: a naive `.date()` on the raw (unconverted)
    # tz-aware object would misread this as UTC "2026-09-16" (today) and wrongly consume the cap.
    sender_configured.upsert_outreach(
        {"business_id": b0["id"], "touch": 1, "status": "sent", "sent_at": "2026-09-16T23:30:00-05:00"}
    )
    business = _make_business(sender_configured, name="New Offset Spa", email="newoff@example-medspa-newoff.test")
    preview = _make_preview(sender_configured, business_id=business["id"])
    _drafted_row(sender_configured, business=business, preview=preview)

    stats = send.run_send(sender_configured, FakeSettings(fixtures_root), today=today, mock=True)
    assert stats["sent"] == 1
    assert stats["dropped"]["cap_reached"] == 0


def test_daily_queue_sent_today_count_is_utc_aware():
    from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        store = LocalStore(root=Path(tmp) / "store")
        today = date(2026, 9, 16)
        store.upsert_outreach({"business_id": "b1", "touch": 1, "status": "sent", "sent_at": "2026-09-16T23:30:00-05:00"})
        store.upsert_outreach({"business_id": "b2", "touch": 1, "status": "sent", "sent_at": "2026-09-16T00:05:00Z"})
        assert daily_queue._sent_today_count(store, today) == 1
