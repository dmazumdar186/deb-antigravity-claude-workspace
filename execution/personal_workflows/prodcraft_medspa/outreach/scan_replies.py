"""
scan_replies.py
description: Poll Gmail for replies to `sent` outreach rows, classify each with
    prompts/classify_reply.md, and drive outreach/state_machine.py transitions
    (remove -> dnc + takedown, bounce -> undeliverable + cancel other touches, ooo -> push
    next_touch_at, positive/neutral/negative -> sent->replied, negative then -> closed_lost).
    Per the 2026-09-16 operator decision, a positive or neutral reply (or any reply asking for a
    call) posts a Telegram alert via common.notify.reply() and the operator takes over manually
    from there; this script itself never auto-replies.
inputs: CLI: [--mock] [--store {local,supabase}] [--store-root PATH] [--since-days 14].
outputs: Store mutations via state_machine.transition / store.update_outreach /
    store.upsert_business; a Telegram reply alert for positive/neutral (or wants_call) replies;
    stdout stat line {"script":"scan_replies","checked":n,"positive":n,"neutral":n,"negative":n,
    "bounce":n,"ooo":n,"remove":n,"takedowns":[...]}.

Mock classification note (per CONTRACTS.md): common.llm.call(mock=True) always returns the SAME
fixture per prompt name (prompts/fixtures/llm/classify_reply.txt is fixed to one "positive,
wants_call" response), so it cannot distinguish the six different fixture replies in
outreach/fixtures/inbox/. In --mock mode this module therefore classifies with
`_mock_classify()`, a deterministic keyword matcher that implements EXACTLY the same rule order
as prompts/classify_reply.md (remove -> bounce -> ooo -> sentiment), so each of the six fixture
replies lands in its own distinct sentiment bucket. The LIVE path (mock=False) always calls the
real LLM via common.llm.call("classify_reply", ...) and never uses this keyword fallback; its
full envelope (model_id, prompt_sha256, usage, mock) is persisted onto the row's `notes` JSON
under "llm_classify" (merged alongside any other notes keys, e.g. daily_queue's "llm").

Idempotency: each row's `notes.seen_reply_ids` records every Gmail message_id already processed
for that row, so scanning the same reply twice (a second cron tick before the row leaves `sent`,
e.g. for a bounce/ooo reply which does not change status) does not re-notify or re-classify it.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from execution.personal_workflows.prodcraft_medspa.common import config, llm, store as store_mod  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.outreach import (  # noqa: E402
    _store_helpers,
    gmail_reader,
    state_machine,
)
from execution.personal_workflows.prodcraft_medspa.scripts._stage_runner import reject_mock_with_supabase  # noqa: E402

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
LLM_FIXTURES_ROOT = PROMPTS_DIR / "fixtures"
PKG_FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures"  # outreach/fixtures (inbox/*.json)

# Same trigger words as prompts/classify_reply.md rule 1, checked in the same order.
_REMOVE_KEYWORDS = (
    "unsubscribe",
    "don't contact",
    "do not contact",
    "take down",
    "takedown",
    "remove",
    "delete",
    "stop",
)
_BOUNCE_KEYWORDS = (
    "mailer-daemon",
    "undeliverable",
    "delivery failed",
    "delivery status notification",
    "550",
    "permanent failure",
)
_OOO_KEYWORDS = ("out of office", "on vacation", "auto-reply", "automatic reply", "currently away")
_NEGATIVE_KEYWORDS = ("not interested", "no thanks", "pass on this", "not a fit")
_CALL_KEYWORDS = ("call this week", "hop on a call", "quick call", "jump on a call", "schedule a call", "when can we talk")


def _mock_classify(reply_text: str, from_header: str = "") -> dict:
    """Deterministic keyword classifier mirroring prompts/classify_reply.md exactly, for --mock."""
    haystack = f"{from_header}\n{reply_text}".lower()

    if any(kw in haystack for kw in _REMOVE_KEYWORDS):
        return {
            "sentiment": "remove",
            "wants_call": False,
            "remove_request": True,
            "summary": "Owner asked to remove the preview and stop contact.",
            "suggested_next_step": "takedown",
        }
    if any(kw in haystack for kw in _BOUNCE_KEYWORDS):
        return {
            "sentiment": "bounce",
            "wants_call": False,
            "remove_request": False,
            "summary": "Delivery failure notice — mailbox does not exist.",
            "suggested_next_step": "wait",
        }
    if any(kw in haystack for kw in _OOO_KEYWORDS):
        return {
            "sentiment": "ooo",
            "wants_call": False,
            "remove_request": False,
            "summary": "Automatic out-of-office reply.",
            "suggested_next_step": "wait",
        }
    if any(kw in haystack for kw in _NEGATIVE_KEYWORDS):
        return {
            "sentiment": "negative",
            "wants_call": False,
            "remove_request": False,
            "summary": "Owner declined, not interested at this time.",
            "suggested_next_step": "close",
        }
    wants_call = any(kw in haystack for kw in _CALL_KEYWORDS)
    if wants_call:
        return {
            "sentiment": "positive",
            "wants_call": True,
            "remove_request": False,
            "summary": "Owner is interested and wants to book a call.",
            "suggested_next_step": "book_call",
        }
    return {
        "sentiment": "neutral",
        "wants_call": False,
        "remove_request": False,
        "summary": "Owner replied with a question, no clear decision yet.",
        "suggested_next_step": "answer_question",
    }


def _excerpt(text: str, limit: int = 300) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _reply_message_key(reply: dict) -> str:
    """A stable key identifying this exact inbound message, for the `seen_reply_ids` guard."""
    message_id = reply.get("message_id")
    if message_id:
        return str(message_id)
    return f"{reply.get('thread_id', '')}|{reply.get('received_at', '')}"


def _load_notes(notes_raw: Any) -> dict:
    if not notes_raw:
        return {}
    try:
        notes = json.loads(notes_raw)
    except (TypeError, ValueError):
        return {}
    return notes if isinstance(notes, dict) else {}


def _already_seen(outreach_row: dict, message_key: str) -> bool:
    return message_key in (_load_notes(outreach_row.get("notes")).get("seen_reply_ids") or [])


def _merge_notes(notes_raw: Any, *, llm_classify: dict | None, message_key: str) -> str:
    """Merge (never overwrite) this reply's `llm_classify` envelope and `seen_reply_ids` entry
    into the row's existing `notes` JSON, so daily_queue's own "llm"/"lint_violations" keys and
    any previously-seen reply ids survive."""
    notes = _load_notes(notes_raw)
    if llm_classify is not None:
        notes["llm_classify"] = llm_classify
    seen = list(notes.get("seen_reply_ids") or [])
    if message_key not in seen:
        seen.append(message_key)
    notes["seen_reply_ids"] = seen
    return json.dumps(notes)


def _envelope_for_notes(envelope: dict | None) -> dict | None:
    if envelope is None:
        return None
    return {
        "model_id": envelope.get("model_id"),
        "prompt_sha256": envelope.get("prompt_sha256"),
        "usage": envelope.get("usage"),
        "mock": envelope.get("mock"),
    }


def _send_reply_notification(st: Any, updated_row: dict, business: dict, classification: dict, thread_id: str) -> None:
    """Notify the operator of a positive/neutral (or wants_call) reply; record notified_at only
    on a confirmed send, else log reply_notify_failed but keep the row (so the dashboard shows
    it happened, just without a working notification)."""
    from execution.personal_workflows.prodcraft_medspa.common import notify

    preview_id = updated_row.get("preview_id")
    preview = st.get_row("previews", preview_id) if preview_id else None

    ok = False
    try:
        ok = notify.reply(
            business_name=business.get("name") or business.get("business_name") or "Unknown business",
            owner_name=business.get("owner_name") or "Owner",
            owner_email=business.get("owner_email") or "",
            sentiment=classification["sentiment"],
            summary=classification.get("summary", ""),
            suggested_next_step=classification.get("suggested_next_step", ""),
            wants_call=bool(classification.get("wants_call")),
            gmail_thread_id=thread_id or "",
            preview_url=(preview or {}).get("subdomain_url", ""),
        )
    except Exception as exc:  # noqa: BLE001 — a notify failure must never break the scan
        st.log_event(
            "outreach", updated_row["id"], "reply_notify_error", {"error": f"{type(exc).__name__}: {exc}"}
        )

    if ok:
        st.update_outreach(updated_row["id"], {"notified_at": _now_iso()})
    else:
        st.log_event(
            "outreach", updated_row["id"], "reply_notify_failed", {"sentiment": classification["sentiment"]}
        )


def _handle_reply(
    st: Any,
    outreach_row: dict,
    reply: dict,
    classification: dict,
    today: date,
    *,
    envelope: dict | None,
    message_key: str,
) -> str:
    """Apply the state_machine transition for one classified reply. Returns the sentiment bucket."""
    sentiment = classification["sentiment"]
    excerpt = _excerpt(reply.get("body_text", ""))
    thread_id = reply.get("thread_id") or outreach_row.get("gmail_thread_id")
    llm_classify = _envelope_for_notes(envelope)
    notes = _merge_notes(outreach_row.get("notes"), llm_classify=llm_classify, message_key=message_key)

    if classification.get("remove_request") or sentiment == "remove":
        state_machine.transition(
            st,
            outreach_row,
            "dnc",
            reply_sentiment="remove",
            reply_excerpt=excerpt,
            replied_at=reply.get("received_at"),
            gmail_thread_id=thread_id,
            notes=notes,
        )
        return "remove"

    if sentiment == "bounce":
        st.update_outreach(
            outreach_row["id"],
            {
                "reply_sentiment": "bounce",
                "reply_excerpt": excerpt,
                "gmail_thread_id": thread_id,
                "notes": notes,
            },
        )
        st.log_event("outreach", outreach_row["id"], "bounce_detected", {"excerpt": excerpt})
        business = st.get_business(outreach_row["business_id"])
        if business:
            st.upsert_business({**business, "email_status": "undeliverable"})
        state_machine._cancel_other_touches(  # noqa: SLF001 — same package, documented internal helper
            st, outreach_row.get("business_id"), outreach_row.get("id"), "closed_lost"
        )
        return "bounce"

    if sentiment == "ooo":
        current_next = outreach_row.get("next_touch_at")
        base = datetime.fromisoformat(current_next).date() if current_next else today
        pushed = base + timedelta(days=4)
        st.update_outreach(
            outreach_row["id"],
            {"next_touch_at": pushed.isoformat(), "gmail_thread_id": thread_id, "notes": notes},
        )
        st.log_event("outreach", outreach_row["id"], "ooo_push", {"next_touch_at": pushed.isoformat()})
        return "ooo"

    # positive / neutral / negative -> sent -> replied
    summary = classification.get("summary", "")
    suggested_next_step = classification.get("suggested_next_step", "")
    updated_row = state_machine.transition(
        st,
        outreach_row,
        "replied",
        reply_sentiment=sentiment,
        reply_excerpt=excerpt,
        replied_at=reply.get("received_at"),
        gmail_thread_id=thread_id,
        reply_summary=summary,
        reply_suggested_next_step=suggested_next_step,
        notes=notes,
    )

    wants_call = bool(classification.get("wants_call"))
    if sentiment in ("positive", "neutral") or wants_call:
        business = st.get_business(outreach_row.get("business_id")) or {}
        _send_reply_notification(st, updated_row, business, classification, thread_id)

    if sentiment == "negative":
        # sent->replied already happened above; close the row out unless the state machine no
        # longer allows replied->closed_lost, in which case leave it replied and log why.
        try:
            state_machine.transition(st, updated_row, "closed_lost")
        except state_machine.IllegalTransition as exc:
            st.log_event("outreach", updated_row["id"], "closed_lost_skipped", {"reason": str(exc)})

    return sentiment


def scan(st: Any, settings: Any, *, mock: bool, since_days: int, today: date | None = None) -> dict:
    today = today or date.today()
    sent_rows = [r for r in _store_helpers.list_all(st, "outreach") if r.get("status") == "sent"]

    counts = {"positive": 0, "neutral": 0, "negative": 0, "bounce": 0, "ooo": 0, "remove": 0}
    takedowns: list[str] = []
    checked = 0

    if mock:
        inbox = gmail_reader.load_mock_inbox(PKG_FIXTURES_ROOT)
        replies_by_email = {r.get("owner_email"): r for r in inbox}
    else:
        replies_by_email = {}

    for row in sent_rows:
        business = st.get_business(row.get("business_id"))
        owner_email = (business or {}).get("owner_email")

        if mock:
            reply = replies_by_email.get(owner_email)
            if not reply:
                continue
            replies = [reply]
        else:
            thread_id = row.get("gmail_thread_id")
            if not thread_id and not owner_email:
                continue
            # search_replies matches on gmail_thread_id (whole thread, any sender) as well as
            # owner_email, so a reply from a different address in the same thread is caught.
            replies = gmail_reader.search_replies(
                owner_email=owner_email or "", since_days=since_days, settings=settings, thread_id=thread_id
            )
            if not replies:
                continue
            replies = replies[-1:]  # only the newest inbound message this pass

        for reply in replies:
            message_key = _reply_message_key(reply)
            if _already_seen(row, message_key):
                continue  # already classified and (if applicable) notified on a prior scan

            checked += 1
            envelope = None
            if mock:
                classification = _mock_classify(reply.get("body_text", ""), reply.get("from", ""))
            else:
                our_last_email = row.get("draft_body") or ""
                envelope = llm.call(
                    "classify_reply",
                    PROMPTS_DIR / "classify_reply.md",
                    {"reply_text": reply.get("body_text", ""), "our_last_email": our_last_email},
                    model="claude-sonnet-5",
                    mock=False,
                    fixtures_root=LLM_FIXTURES_ROOT,
                )
                classification = json.loads(envelope["text"])

            bucket = _handle_reply(st, row, reply, classification, today, envelope=envelope, message_key=message_key)
            counts[bucket if bucket in counts else "neutral"] = counts.get(bucket, 0) + 1
            if bucket == "remove":
                takedowns.append(row.get("business_id"))

    return {
        "script": "scan_replies",
        "checked": checked,
        **counts,
        "takedowns": takedowns,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan Gmail for replies to sent outreach rows")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--store", choices=["local", "supabase"], default=None)
    parser.add_argument("--store-root", default=None)
    parser.add_argument("--since-days", type=int, default=14)
    args = parser.parse_args()

    settings = config.bootstrap()
    store_kind = reject_mock_with_supabase(parser, args)  # --mock implies local; never supabase
    st = store_mod.get_store(kind=store_kind, root=args.store_root)

    try:
        stats = scan(st, settings, mock=args.mock, since_days=args.since_days)
    except Exception as exc:  # noqa: BLE001 — top-level failure must reach the error channel
        from execution.personal_workflows.prodcraft_medspa.common import notify

        notify.error("prodcraft_medspa.scan_replies", f"{type(exc).__name__}: {exc}")
        raise

    print(json.dumps(stats))


if __name__ == "__main__":
    main()
