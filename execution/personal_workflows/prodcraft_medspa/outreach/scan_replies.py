"""
scan_replies.py
description: Poll Gmail for replies to `sent` outreach rows, classify each with
    prompts/classify_reply.md, and drive outreach/state_machine.py transitions
    (remove -> dnc + takedown + Telegram notify, bounce -> undeliverable + cancel other touches,
    ooo -> push next_touch_at, positive/neutral/negative -> sent->replied, negative then ->
    closed_lost + do_not_contact + a preview takedown via the same real unpublish path as remove
    — round-4 audit (Dario lens): the preview watermark promises "Reply 'no' and this preview
    comes down", so a negative reply IS an opt-out; negative and remove differ only in Telegram
    routing/classification, not in what happens to the business). Per the 2026-09-16 operator decision, a positive or neutral reply (or
    any reply asking for a call) posts a Telegram alert via common.notify.reply() and the operator
    takes over manually from there; this script itself never auto-replies. A remove reply also
    posts the same alert (sentiment forced to "remove") and stamps the row's
    `notes.remove_source` ("keyword" under --mock's deterministic matcher, "llm" on the live
    classifier path) so an operator auditing a takedown knows which classifier flagged it.
inputs: CLI: [--mock] [--store {local,supabase}] [--store-root PATH] [--since-days 14].
outputs: Store mutations via state_machine.transition / store.update_outreach /
    store.upsert_business; a Telegram reply alert for positive/neutral/remove (or wants_call)
    replies; stdout stat line {"script":"scan_replies","checked":n,"positive":n,"neutral":n,
    "negative":n,"bounce":n,"ooo":n,"remove":n,"takedowns":[...]}.

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
import os
import re
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
_CALL_KEYWORDS = (
    "call this week", "hop on a call", "quick call", "jump on a call", "schedule a call", "when can we talk",
    "let's talk",  # gap pass: fixtures/replies_gold.jsonl id p05
)
# Gap pass (after round 4): a bare "no" is a decline, never `neutral` (CONTRACTS.md, prompt rule 4).
# Matched against the reply's first non-empty line with punctuation stripped, so "No.", "Nope!",
# "No thank you" and "no, thanks" all count; a longer sentence starting with "no" does not.
_BARE_NO_RE = re.compile(r"^(no|nope|nah|no thanks|no thank you|not for us|hard pass|pass)$")

# Model the live classifier runs on (one place, so a pin sweep changes it once).
CLASSIFY_MODEL = "claude-fable-5-1"

# Gap pass: the mock inbox directory can be pointed at a test-owned folder of *.json replies
# (tests/prodcraft_medspa/test_suite_tiers.sh seeds a negative reply for a sent row this way).
MOCK_INBOX_DIR_ENV = "PRODCRAFT_MOCK_INBOX_DIR"


def _is_bare_no(reply_text: str) -> bool:
    for line in (reply_text or "").splitlines():
        stripped = re.sub(r"[^a-z' ]+", " ", line.lower()).strip()
        stripped = re.sub(r"\s+", " ", stripped)
        if not stripped:
            continue
        return bool(_BARE_NO_RE.match(stripped))
    return False


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
    if any(kw in haystack for kw in _NEGATIVE_KEYWORDS) or _is_bare_no(reply_text):
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


def _merge_notes(
    notes_raw: Any, *, llm_classify: dict | None, message_key: str, extra: dict | None = None
) -> str:
    """Merge (never overwrite) this reply's `llm_classify` envelope, `seen_reply_ids` entry, and
    any `extra` fields (e.g. item 7's `remove_source`) into the row's existing `notes` JSON, so
    daily_queue's own "llm"/"lint_violations" keys and any previously-seen reply ids survive."""
    notes = _load_notes(notes_raw)
    if llm_classify is not None:
        notes["llm_classify"] = llm_classify
    seen = list(notes.get("seen_reply_ids") or [])
    if message_key not in seen:
        seen.append(message_key)
    notes["seen_reply_ids"] = seen
    if extra:
        notes.update(extra)
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


def _takedown_previews_for_negative(st: Any, outreach_row: dict) -> list[str]:
    """Round-4 audit (Dario lens): a `negative` reply is an opt-out. The preview watermark
    promises "Reply 'no' and this preview comes down", so the prospect who said no must never be
    emailed again: stamp `businesses.do_not_contact = True`, close every other non-terminal
    outreach row for the business to `dnc` (no orphan touch-2/3/4 row is drafted, dropped at
    send and then counted by daily_queue._drafted_pending_count, losing a cap slot), and take
    down every non-takendown preview via the SAME real unpublish path state_machine.py's dnc
    flow uses (preview/takedown.py's `take_down_preview()`, default `dnc=True` -> R2 prefix
    delete + Worker /remove + the business flag + the outreach cascade).

    negative and remove now differ only in Telegram routing/classification (`reply_sentiment`
    "negative" vs "remove", `closed_lost` vs `dnc` on the replying row); the business-level
    outcome is identical. Idempotent: a preview already marked takedown is skipped, and when no
    preview exists at all the flag + cascade still happen here directly.
    Returns the list of preview ids actually taken down."""
    from execution.personal_workflows.prodcraft_medspa.common import config as config_mod
    from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore
    from execution.personal_workflows.prodcraft_medspa.preview.takedown import take_down_preview

    business_id = outreach_row.get("business_id")
    preview_id = outreach_row.get("preview_id")
    previews: list[dict] = []
    if preview_id:
        p = st.get_row("previews", preview_id)
        if p is not None:
            previews = [p]
    elif business_id:
        previews = [
            p for p in _store_helpers.previews_for_business(st, business_id) if not p.get("takedown")
        ]

    settings = config_mod.bootstrap()
    taken_down: list[str] = []
    for preview_row in previews:
        if preview_row.get("status") == "takedown" or preview_row.get("takedown") is True:
            st.log_event(
                "preview", preview_row.get("id"), "takedown_requested",
                {"reason": "negative_reply", "outcome": "already_takendown"},
            )
            continue
        try:
            take_down_preview(st, preview_row, mock=isinstance(st, LocalStore), tmp_root=settings.TMP)
            st.log_event(
                "preview", preview_row.get("id"), "takedown_requested",
                {"reason": "negative_reply", "outcome": "ok"},
            )
            taken_down.append(preview_row.get("id"))
        except Exception as exc:  # noqa: BLE001 — a takedown failure must not block closed_lost itself
            print(
                f"[scan_replies] negative-reply takedown failed for preview {preview_row.get('id')}: {exc}",
                file=sys.stderr,
            )
            st.log_event(
                "preview", preview_row.get("id"), "takedown_requested",
                {"reason": "negative_reply", "outcome": "error", "error": str(exc)},
            )
            # item 14 (round-3, Dario lens): page the operator, once per preview per day.
            state_machine._notify_takedown_failure(  # noqa: SLF001 — same package, documented internal helper
                st, preview_row.get("id"), f"negative-reply takedown failed: {exc}"
            )

    # The opt-out must hold even when there was no live preview to take down (or the takedown
    # raised before it reached the business row): stamp + cascade directly, patch-by-id
    # (never a full-row upsert, see the bounce path) so a concurrent writer is not clobbered.
    if business_id:
        business = st.get_business(business_id)
        if business and not business.get("do_not_contact"):
            st.update_row("businesses", business_id, {"do_not_contact": True})
            st.log_event("business", business_id, "do_not_contact", {"reason": "negative_reply"})
        state_machine._cancel_other_touches(  # noqa: SLF001 — same package, documented internal helper
            st, business_id, outreach_row.get("id"), "dnc"
        )

    return taken_down


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
        # item 7 (round-2 audit): remove_source records whether this classification came from the
        # --mock deterministic keyword matcher (`_mock_classify`, envelope is None) or the live
        # LLM classifier (envelope set) — an operator auditing a takedown wants to know which.
        remove_source = "keyword" if envelope is None else "llm"
        notes_with_source = _merge_notes(
            outreach_row.get("notes"),
            llm_classify=llm_classify,
            message_key=message_key,
            extra={"remove_source": remove_source},
        )
        updated_row = state_machine.transition(
            st,
            outreach_row,
            "dnc",
            reply_sentiment="remove",
            reply_excerpt=excerpt,
            replied_at=reply.get("received_at"),
            gmail_thread_id=thread_id,
            notes=notes_with_source,
        )
        # item 7: a remove request also pages the operator, same Telegram channel as a
        # positive/neutral reply — sentiment is forced to "remove" regardless of what the
        # classifier's own `sentiment` field said, so the alert is never mislabeled.
        business = st.get_business(outreach_row.get("business_id")) or {}
        _send_reply_notification(st, updated_row, business, {**classification, "sentiment": "remove"}, thread_id)
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
            # round-4 item D: patch by id (mirrors preview/takedown.py) instead of round-tripping
            # the whole row through upsert_business(), which would overwrite any column another
            # process wrote between the read above and this write (lost update).
            st.update_row("businesses", business["id"], {"email_status": "undeliverable"})
        state_machine._cancel_other_touches(  # noqa: SLF001 — same package, documented internal helper
            st, outreach_row.get("business_id"), outreach_row.get("id"), "closed_lost"
        )
        return "bounce"

    if sentiment == "ooo":
        current_next = outreach_row.get("next_touch_at")
        base = datetime.fromisoformat(current_next).date() if current_next else today
        # item 9 (round-3 minor): a stale next_touch_at in the past (a row overdue when the OOO
        # reply arrives) must push from TODAY, not compound off a date that's already gone by.
        pushed = max(base, today) + timedelta(days=4)
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
        # item 15 (round-3, Sutskever lens): a negative classification takes down the preview
        # on the LLM's (or --mock's keyword matcher's) word alone, with no operator-visible
        # signal — a misclassification here silently kills a live preview. Notify the same
        # Telegram channel as positive/neutral/remove, with the classification's provenance
        # (mirrors "remove_source": "llm" on the live path, "keyword" under --mock) folded into
        # the summary so an operator scanning the channel can tell how much to trust it.
        provenance = "keyword" if envelope is None else "llm"
        business = st.get_business(outreach_row.get("business_id")) or {}
        _send_reply_notification(
            st,
            updated_row,
            business,
            {**classification, "summary": f"{summary} (classified by: {provenance})"},
            thread_id,
        )
        # sent->replied already happened above; close the row out unless the state machine no
        # longer allows replied->closed_lost, in which case leave it replied and log why.
        try:
            updated_row = state_machine.transition(st, updated_row, "closed_lost")
            # round-4 audit (Dario lens): a negative reply is an opt-out — the watermark promised
            # "Reply 'no' and this preview comes down". Same real unpublish path as dnc/remove,
            # plus `businesses.do_not_contact = True` and the sibling-outreach cascade to `dnc`.
            _takedown_previews_for_negative(st, updated_row)
        except state_machine.IllegalTransition as exc:
            st.log_event("outreach", updated_row["id"], "closed_lost_skipped", {"reason": str(exc)})

    return sentiment


def _mark_seen_on_row(st: Any, row: dict, message_key: str) -> dict:
    """Record `message_key` in one row's `notes.seen_reply_ids` without classifying/transitioning
    it (item 3 — every sibling row for the same business must know a message was already
    handled, or a later scan would reclassify it against whichever sibling processes it next)."""
    merged_notes = _merge_notes(row.get("notes"), llm_classify=None, message_key=message_key)
    updated = st.update_outreach(row["id"], {"notes": merged_notes})
    row["notes"] = merged_notes
    return updated


def scan(st: Any, settings: Any, *, mock: bool, since_days: int, today: date | None = None) -> dict:
    today = today or date.today()
    sent_rows = [r for r in _store_helpers.list_all(st, "outreach") if r.get("status") == "sent"]

    counts = {"positive": 0, "neutral": 0, "negative": 0, "bounce": 0, "ooo": 0, "remove": 0}
    takedowns: list[str] = []
    checked = 0

    if mock:
        inbox_override = os.environ.get(MOCK_INBOX_DIR_ENV)
        inbox = gmail_reader.load_mock_inbox(PKG_FIXTURES_ROOT, inbox_dir=Path(inbox_override) if inbox_override else None)
        replies_by_email = {r.get("owner_email"): r for r in inbox}
    else:
        replies_by_email = {}

    # item 3 (round-3 critical): a business can have MULTIPLE `sent` rows at once — touch 1
    # stays `sent` forever unless replied, while advance.py/daily_queue.py create touch 2+ as a
    # SEPARATE row without ever changing touch 1's status. gmail_reader.search_replies(owner_email)
    # matches by owner_email (and, previously, by each row's own thread_id via an OR), so the
    # SAME inbound message was returned once per sibling row and classified/notified N times.
    # Fix: group by business and process each business's replies once per pass, not once per row.
    rows_by_business: dict[Any, list[dict]] = {}
    for row in sent_rows:
        rows_by_business.setdefault(row.get("business_id"), []).append(row)

    for business_id, biz_rows in rows_by_business.items():
        biz_rows.sort(key=lambda r: (int(r.get("touch") or 1), r.get("created_at") or ""))
        business = st.get_business(business_id) if business_id else None
        owner_email = (business or {}).get("owner_email")

        if mock:
            reply = replies_by_email.get(owner_email)
            replies = [reply] if reply else []
        else:
            if not owner_email and not any(r.get("gmail_thread_id") for r in biz_rows):
                continue
            # Fetched ONCE per business, not once per sibling row: owner_email alone already
            # matches every thread that business's replies could be in (search_replies' own
            # owner_email fallback), so a per-row thread_id fetch only ever re-returned the same
            # messages under a different row. It already excludes our own outbound messages
            # (SENT label / From == us) and returns EVERY inbound message, not just the newest —
            # idempotency is `notes.seen_reply_ids` below, not a `[-1:]` truncation (code-review
            # C3: that truncation could silently drop an unseen reply behind a newer one).
            replies = gmail_reader.search_replies(
                owner_email=owner_email or "", since_days=since_days, settings=settings, thread_id=None
            )
            if not replies:
                continue

        # A business's active outreach can only leave `status: sent` once per scan pass (once
        # the first reply this pass moves ITS target row off `sent`, every further unseen
        # message for this same business is recorded as seen on every sibling row — idempotency
        # — but not re-classified/re-transitioned this pass).
        business_left_sent = False

        for reply in replies:
            message_key = _reply_message_key(reply)

            # Route to the specific sibling this message actually replied to (matched by
            # gmail_thread_id) when we can tell; otherwise the earliest-touch row still `sent`.
            target_row = None
            reply_thread_id = reply.get("thread_id")
            if reply_thread_id:
                for r in biz_rows:
                    if r.get("gmail_thread_id") == reply_thread_id:
                        target_row = r
                        break
            if target_row is None:
                target_row = biz_rows[0]

            if _already_seen(target_row, message_key):
                continue  # already classified and (if applicable) notified on a prior scan

            if business_left_sent:
                for r in biz_rows:
                    _mark_seen_on_row(st, r, message_key)
                continue

            checked += 1
            envelope = None
            try:
                if mock:
                    classification = _mock_classify(reply.get("body_text", ""), reply.get("from", ""))
                else:
                    our_last_email = target_row.get("draft_body") or ""
                    envelope = llm.call(
                        "classify_reply",
                        PROMPTS_DIR / "classify_reply.md",
                        {"reply_text": reply.get("body_text", ""), "our_last_email": our_last_email},
                        model=CLASSIFY_MODEL,
                        mock=False,
                        fixtures_root=LLM_FIXTURES_ROOT,
                    )
                    classification = json.loads(envelope["text"])
            except Exception as exc:  # noqa: BLE001 — item 13: one malformed LLM response (bad
                # JSON, missing/garbage fields) must never abort the whole scan pass. Log it,
                # page the operator, and mark the message seen on every sibling row so it isn't
                # retried into an infinite notify loop — an operator investigating `classify_error`
                # events can always re-run scan_replies by hand once the cause is fixed.
                from execution.personal_workflows.prodcraft_medspa.common import notify

                st.log_event(
                    "outreach",
                    target_row["id"],
                    "classify_error",
                    {"error": f"{type(exc).__name__}: {exc}", "message_key": message_key},
                )
                notify.error(
                    "prodcraft_medspa.scan_replies",
                    f"classify_error on business {business_id}: {type(exc).__name__}: {exc}",
                    1,
                )
                for r in biz_rows:
                    _mark_seen_on_row(st, r, message_key)
                continue

            bucket = _handle_reply(st, target_row, reply, classification, today, envelope=envelope, message_key=message_key)
            key = bucket if bucket in counts else "neutral"  # compute once — fixes the C3 key-mismatch bug
            counts[key] = counts.get(key, 0) + 1
            if bucket == "remove":
                takedowns.append(business_id)
            if bucket not in ("bounce", "ooo"):
                business_left_sent = True

            # Mark this message seen on every OTHER sibling row too (item 3), so a later scan
            # never reclassifies it against a row that never itself changed status.
            for r in biz_rows:
                if r.get("id") != target_row.get("id"):
                    _mark_seen_on_row(st, r, message_key)

            # Refresh `target_row` (and its slot in biz_rows) from the store so a further unseen
            # message this same pass (bounce/ooo keep looping) merges its seen_reply_ids on top
            # of what THIS reply's classification/transition just wrote, instead of a stale
            # pre-loop copy that would silently clobber it.
            refreshed = st.get_row("outreach", target_row["id"])
            if refreshed is not None:
                for i, r in enumerate(biz_rows):
                    if r.get("id") == target_row.get("id"):
                        biz_rows[i] = refreshed
                        break

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
