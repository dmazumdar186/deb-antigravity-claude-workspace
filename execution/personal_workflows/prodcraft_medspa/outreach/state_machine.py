"""
state_machine.py
description: Explicit outreach status state machine (CONTRACTS.md "Outreach state machine" section,
    implemented exactly) — legal transitions, next-touch creation, dnc cascade, phase0 counters.
inputs: Imported by daily_queue.py/scan_replies.py/advance.py; also runnable directly for --help.
outputs: transition() mutates the Store (update_outreach / upsert_outreach / upsert_business /
    update_preview / set_config) and logs an `events` row for every call; no stdout/network beyond that.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from execution.personal_workflows.prodcraft_medspa.outreach import _store_helpers

STATES = (
    "queued",
    "drafted",
    "sent",
    "replied",
    "call_booked",
    "closed_won",
    "closed_lost",
    "dnc",
)

# Every legal (from, to) pair EXCEPT the "*->dnc" wildcard, which is checked separately
# (any state, including terminal ones, may transition to dnc — a remove request or a
# discovered do-not-contact business can arrive at any point in the lifecycle).
TRANSITIONS: set[tuple[str, str]] = {
    ("queued", "drafted"),
    ("drafted", "sent"),
    ("drafted", "queued"),  # sanctioned "redraft": a lint/QA rejection sends a draft back to the
                             # front of the queue instead of leaving it stuck in "drafted" (round-2
                             # audit finding — see redraft() below).
    ("sent", "replied"),
    ("sent", "queued"),  # side effect: creates the touch+1 row; see _create_next_touch
    ("sent", "closed_lost"),
    ("replied", "call_booked"),
    ("replied", "closed_lost"),
    ("call_booked", "closed_won"),
    ("call_booked", "closed_lost"),
}

DEFAULT_TOUCH_DAYS = [0, 3, 7, 12]
MAX_TOUCH = 4


class IllegalTransition(Exception):
    """Raised for any (from, to) pair not in TRANSITIONS and not '*->dnc'."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _touch_days(store: Any) -> list[int]:
    days = store.get_config("touch_days", DEFAULT_TOUCH_DAYS)
    return list(days) if days else list(DEFAULT_TOUCH_DAYS)


def next_touch_date(sent_date: date, touch: int, touch_days: list[int] | None = None) -> date:
    """The date the NEXT touch (touch + 1) is due, given `touch` was just sent on `sent_date`.

    Gap = touch_days[touch] - touch_days[touch - 1] (0-indexed list, 1-indexed `touch`), so with
    the default [0, 3, 7, 12]: touch 1 -> +3d, touch 2 -> +4d, touch 3 -> +5d. `touch` must be
    1..MAX_TOUCH-1 (there is no touch 5).
    """
    days = touch_days or DEFAULT_TOUCH_DAYS
    if touch < 1 or touch >= len(days):
        raise ValueError(f"next_touch_date: touch must be 1..{len(days) - 1}, got {touch}")
    gap = days[touch] - days[touch - 1]
    return sent_date + timedelta(days=gap)


def _increment_phase0(store: Any, field: str, *, set_passed_at: int | None = None) -> None:
    phase0 = dict(
        store.get_config(
            "phase0",
            {"passed": False, "sends": 0, "calls_booked": 0, "queue_cap_locked": 5, "queue_cap_open": 20},
        )
        or {}
    )
    phase0[field] = int(phase0.get(field, 0) or 0) + 1
    if set_passed_at is not None and phase0.get(field, 0) >= set_passed_at:
        phase0["passed"] = True
    store.set_config("phase0", phase0)


def _create_next_touch(store: Any, outreach_row: dict, **fields: Any) -> dict:
    touch = int(outreach_row.get("touch") or 1)
    if touch >= MAX_TOUCH:
        raise IllegalTransition(f"sent -> queued: touch {touch} has no next touch (max is {MAX_TOUCH})")

    sent_at_raw = outreach_row.get("sent_at") or _now_iso()
    sent_date = datetime.fromisoformat(sent_at_raw.replace("Z", "+00:00")).date()
    next_at = next_touch_date(sent_date, touch, _touch_days(store))

    new_row = {
        "business_id": outreach_row.get("business_id"),
        "preview_id": outreach_row.get("preview_id"),
        "audit_id": outreach_row.get("audit_id"),
        "touch": touch + 1,
        "status": "queued",
        "gap_primary": outreach_row.get("gap_primary"),
        "next_touch_at": next_at.isoformat(),
        "draft_subject": outreach_row.get("draft_subject"),  # prev_subject source for touch 2+
    }
    new_row.update(fields)
    created = store.upsert_outreach(new_row)
    store.log_event(
        "outreach",
        created["id"],
        f"status:sent->queued(touch {touch + 1})",
        {"from_outreach_id": outreach_row.get("id"), "next_touch_at": next_at.isoformat()},
    )
    return created


def _cancel_other_touches(store: Any, business_id: str | None, keep_outreach_id: str | None, to_status: str) -> list[str]:
    """Set every other non-terminal outreach row for this business to `to_status`. Returns ids touched."""
    if not business_id:
        return []
    touched: list[str] = []
    for row in _store_helpers.outreach_for_business(store, business_id):
        if row.get("id") == keep_outreach_id:
            continue
        if row.get("status") in ("closed_won", "closed_lost", "dnc"):
            continue
        store.update_outreach(row["id"], {"status": to_status})
        store.log_event("outreach", row["id"], f"status:{row.get('status')}->{to_status}", {"reason": "cascade"})
        touched.append(row["id"])
    return touched


def _default_takedown_fn(store: Any) -> Callable[[dict], dict]:
    """Builds the real takedown callable: preview/takedown.py's take_down_preview(), the actual
    unpublish (R2 prefix delete + Worker /remove call), never just a status flip. `mock` is
    inferred from the store implementation (LocalStore -> mock; anything else, e.g. SupabaseStore
    -> live) so a live DNC actually reaches R2/the Worker without every caller having to plumb a
    --mock flag through to the state machine."""

    def _run(preview_row: dict) -> dict:
        from execution.personal_workflows.prodcraft_medspa.common import config as config_mod
        from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore
        from execution.personal_workflows.prodcraft_medspa.preview.takedown import take_down_preview

        settings = config_mod.bootstrap()
        return take_down_preview(store, preview_row, mock=isinstance(store, LocalStore), tmp_root=settings.TMP)

    return _run


def _takedown_one_preview(store: Any, preview_row: dict, takedown_fn: Callable[[dict], dict]) -> None:
    """Idempotent: a preview already marked takedown is never handed to `takedown_fn` again (so
    two `dnc` transitions, or a `dnc` after a manual takedown, call the real unpublish path at
    most once), but a `takedown_requested` event is still logged every time for the audit trail."""
    preview_id = preview_row.get("id")
    if preview_row.get("status") == "takedown" or preview_row.get("takedown") is True:
        store.log_event("preview", preview_id, "takedown_requested", {"reason": "dnc", "outcome": "already_takendown"})
        return
    try:
        result = takedown_fn(preview_row)
        outcome = {
            k: result.get(k) for k in ("r2_objects_deleted", "outreach_closed", "status")
        } if isinstance(result, dict) else None
        store.log_event("preview", preview_id, "takedown_requested", {"reason": "dnc", "outcome": "ok", "result": outcome})
    except Exception as exc:  # noqa: BLE001 — a takedown failure (R2/Worker outage) must not block dnc itself;
        # logged (both here and via events) so it's never silently swallowed, matching
        # python-hardening.md rule 5.
        print(f"[state_machine] dnc takedown failed for preview {preview_id}: {exc}", file=sys.stderr)
        store.log_event("preview", preview_id, "takedown_requested", {"reason": "dnc", "outcome": "error", "error": str(exc)})


def _apply_dnc(store: Any, outreach_row: dict, *, takedown_fn: Callable[[dict], dict] | None = None, **fields: Any) -> dict:
    frm = outreach_row.get("status")
    patch = dict(fields)
    patch["status"] = "dnc"
    updated = store.update_outreach(outreach_row["id"], patch)
    store.log_event("outreach", outreach_row["id"], f"status:{frm}->dnc", {"fields": fields})

    business_id = outreach_row.get("business_id")
    _cancel_other_touches(store, business_id, outreach_row.get("id"), "dnc")

    if business_id:
        business = store.get_business(business_id)
        if business:
            store.upsert_business({**business, "do_not_contact": True})
            store.log_event("business", business_id, "do_not_contact:true", {})

    # Takedown is no longer a bare status flip left for a later script (scripts/daily.py) to
    # maybe do — it happens right here so a dnc/remove request can never leave a preview live
    # (round-2 trust/safety finding). take_down_preview() itself is idempotent-safe to call
    # again from daily.py's later pass; _takedown_one_preview()'s own guard just avoids the
    # redundant R2/Worker round-trip when we already know the preview is down.
    resolved_takedown_fn = takedown_fn or _default_takedown_fn(store)
    preview_id = outreach_row.get("preview_id")
    if preview_id:
        preview_row = store.get_row("previews", preview_id)
        if preview_row is not None:
            _takedown_one_preview(store, preview_row, resolved_takedown_fn)
        else:
            # preview row not found under this store (e.g. deleted already) — not fatal to dnc,
            # but worth a log line rather than a silent no-op.
            print(f"[state_machine] dnc: preview {preview_id} not found for takedown", file=sys.stderr)
    elif business_id:
        for p in _store_helpers.previews_for_business(store, business_id):
            _takedown_one_preview(store, p, resolved_takedown_fn)

    return updated


def transition(
    store: Any, outreach_row: dict, to: str, *, takedown_fn: Callable[[dict], dict] | None = None, **fields: Any
) -> dict:
    """Apply one legal state transition to `outreach_row` and return the resulting row.

    `fields` are extra columns to patch (sentiment, notes, sent_at, ...) alongside the status
    change. Every call logs an `events` row. Raises IllegalTransition for anything not in
    TRANSITIONS (dnc is always legal from any state, including terminal ones).

    `takedown_fn`, meaningful only for `to == "dnc"`, overrides the real takedown callable
    (preview/takedown.py's take_down_preview by default) — tests inject a stub here instead of
    hitting R2/the Worker.
    """
    frm = outreach_row.get("status")
    if frm not in STATES:
        raise IllegalTransition(f"unknown source state {frm!r}")
    if to not in STATES:
        raise IllegalTransition(f"unknown target state {to!r}")

    if to == "dnc":
        return _apply_dnc(store, outreach_row, takedown_fn=takedown_fn, **fields)

    if (frm, to) not in TRANSITIONS:
        raise IllegalTransition(f"{frm} -> {to} is not a legal transition")

    if frm == "sent" and to == "queued":
        return _create_next_touch(store, outreach_row, **fields)

    patch = dict(fields)
    patch["status"] = to
    if to == "sent":
        patch.setdefault("sent_at", fields.get("sent_at") or _now_iso())
    if to == "replied":
        patch.setdefault("replied_at", fields.get("replied_at") or _now_iso())

    updated = store.update_outreach(outreach_row["id"], patch)
    store.log_event("outreach", outreach_row["id"], f"status:{frm}->{to}", {"fields": fields})

    # phase0 counters (CONTRACTS.md D7 / panel-pass Karpathy #3): touch-1 sends and calls booked.
    if frm == "drafted" and to == "sent" and int(outreach_row.get("touch") or 0) == 1:
        _increment_phase0(store, "sends")
    if frm == "replied" and to == "call_booked":
        _increment_phase0(store, "calls_booked", set_passed_at=1)

    if to == "closed_lost":
        # A lost touch-4 (or any lost prospect) frees its preview to expire naturally — no
        # forced takedown (that's reserved for dnc/remove), just an event for the dashboard.
        store.log_event("outreach", outreach_row["id"], "closed_lost", {"touch": outreach_row.get("touch")})

    return updated


def redraft(store: Any, outreach_id: str, reason: str) -> dict:
    """Sanctioned `drafted -> queued` helper ("redraft"): a lint/QA rejection or an operator
    "start this one over" sends a drafted-but-not-yet-sent row back to the front of the queue
    instead of leaving it stuck in `drafted` with no legal way out. Raises `KeyError` if
    `outreach_id` doesn't exist, and `IllegalTransition` if the row isn't currently `drafted`."""
    row = store.get_row("outreach", outreach_id)
    if row is None:
        raise KeyError(f"outreach {outreach_id} not found")
    return transition(store, row, "queued", reason=reason)
