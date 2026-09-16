"""
send.py
description: Send drafted outreach emails via the Gmail API (users.messages.send). Per the
    operator's 2026-09-16 decision, the pipeline runs with no human in the loop until a prospect
    replies positive or neutral — so sending is automated here (previously "human sends" via
    gmail_drafts.py drafts). Sends only rows in status `drafted` that passed lint, whose business
    is not do_not_contact, whose preview is approved/live and not takedown, respects the daily cap
    (outreach.daily_queue._queue_cap) counted across all touches sent today, the bounce halt
    (outreach.daily_queue.halt_reason), and never sends to a business that already has another
    outreach row in a replied/terminal status (replied, call_booked, closed_won, closed_lost, dnc).
inputs: CLI: [--date YYYY-MM-DD] [--mock] [--store {local,supabase}] [--store-root PATH]
    [--recipient-override EMAIL] [--limit N]. Env PRODCRAFT_RECIPIENT_OVERRIDE is used when
    --recipient-override is not passed. `--mock` writes a .eml file under
    .tmp/prodcraft_medspa/sent/ instead of calling the Gmail API and records a fake message id
    `mock-<uuid>`.
outputs: stdout JSON stat line {"script":"send","in":n,"sent":n,"dropped":{"cap_reached":n,
    "halted":n,"lint_failed":n,"dnc":n,"preview_not_approved":n,"already_replied":n,"no_email":n,
    "gmail_error":n}}. Store mutations: outreach status drafted->sent (via state_machine.transition,
    which sets sent_at and increments phase0.sends for touch 1), gmail_message_id/gmail_thread_id
    patches, `test_recipient` patch when --recipient-override is used, and a `sent` events row per
    send.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import uuid
from datetime import date, datetime
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from execution.personal_workflows.prodcraft_medspa.common import config, store as store_mod  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.outreach import (  # noqa: E402
    _store_helpers,
    daily_queue,
    gmail_drafts,
    state_machine,
)
from execution.personal_workflows.prodcraft_medspa.scripts._stage_runner import (  # noqa: E402
    reject_mock_with_supabase,
)

# Any of these on ANOTHER outreach row for the same business means "do not send this row" —
# the prospect already replied (any sentiment that led to a real conversation) or the deal is
# terminal one way or another.
_TERMINAL_OR_REPLIED_STATUSES = {"replied", "call_booked", "closed_won", "closed_lost", "dnc"}


def _parse_date(value: str | None) -> date:
    if not value:
        return date.today()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise SystemExit(f"--date must be YYYY-MM-DD, got {value!r}") from None


def _parse_notes(row: dict) -> dict:
    raw = row.get("notes")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        # Malformed notes must never crash the sender; treat as "no lint info" (fail open on the
        # notes parse itself — the actual lint gate below is what protects CAN-SPAM compliance).
        return {}


def _lint_failed(row: dict) -> bool:
    return bool(_parse_notes(row).get("lint_violations"))


def _preview_ok(st: Any, row: dict) -> bool:
    """The row's preview must exist, be approved/live, and not be under takedown."""
    preview_id = row.get("preview_id")
    if not preview_id:
        return False
    for p in _store_helpers.previews_for_business(st, row.get("business_id")):
        if p.get("id") == preview_id:
            return p.get("status") in ("approved", "live") and not p.get("takedown")
    return False


def _business_has_replied_or_terminal_row(st: Any, business_id: str | None, exclude_outreach_id: str | None) -> bool:
    if not business_id:
        return False
    for r in _store_helpers.outreach_for_business(st, business_id):
        if r.get("id") == exclude_outreach_id:
            continue
        if r.get("status") in _TERMINAL_OR_REPLIED_STATUSES:
            return True
    return False


def _sent_today_count(st: Any, today: date) -> int:
    """Count sends across ALL touches today, for the daily cap."""
    today_str = today.isoformat()
    count = 0
    for r in _store_helpers.list_all(st, "outreach"):
        sent_at = r.get("sent_at")
        if not sent_at:
            continue
        try:
            sent_date = datetime.fromisoformat(str(sent_at).replace("Z", "+00:00")).date()
        except ValueError:
            continue
        if sent_date.isoformat() == today_str:
            count += 1
    return count


def send_email(
    *,
    to_email: str,
    subject: str,
    body: str,
    sender_name: str,
    settings: Any,
    mock: bool,
    business_id: str | None = None,
) -> dict:
    """Send one email via users.messages.send. In --mock mode, writes a .eml file instead."""
    if mock:
        out_dir = settings.TMP / "sent"
        out_dir.mkdir(parents=True, exist_ok=True)
        eml_path = out_dir / f"{business_id or 'sent'}_{uuid.uuid4().hex[:8]}.eml"
        eml_content = f"To: {to_email}\nSubject: {subject}\nFrom: {sender_name}\n\n{body}\n"
        eml_path.write_text(eml_content, encoding="utf-8")
        return {
            "gmail_message_id": f"mock-{uuid.uuid4().hex}",
            "gmail_thread_id": None,
            "eml_path": str(eml_path),
        }

    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise ImportError(
            "Sending live requires google-api-python-client. "
            "Install with: pip install google-api-python-client"
        ) from exc

    creds = gmail_drafts._get_credentials(settings)
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    message = MIMEText(body)
    message["To"] = to_email
    message["Subject"] = subject
    message["From"] = sender_name
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")

    sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return {"gmail_message_id": sent["id"], "gmail_thread_id": sent.get("threadId"), "eml_path": None}


def run_send(
    st: Any,
    settings: Any,
    *,
    today: date,
    mock: bool,
    recipient_override: str | None = None,
    limit: int | None = None,
) -> dict:
    dropped = {
        "cap_reached": 0,
        "halted": 0,
        "lint_failed": 0,
        "dnc": 0,
        "preview_not_approved": 0,
        "already_replied": 0,
        "no_email": 0,
        "gmail_error": 0,
    }

    candidate_rows = list(_store_helpers.outreach_by_status(st, "drafted"))
    in_count = len(candidate_rows)

    halt = daily_queue.halt_reason(st, today)
    if halt:
        print(f"SEND HALTED: {halt}")
        dropped["halted"] = in_count
        return {"script": "send", "in": in_count, "sent": 0, "dropped": dropped}

    cap = daily_queue._queue_cap(st)
    remaining_cap = max(0, cap - _sent_today_count(st, today))

    # Deterministic processing order (oldest-due first), mirroring LocalStore.queue()'s ordering.
    candidate_rows.sort(key=lambda r: (r.get("next_touch_at") or "", r.get("created_at") or ""))

    sent_count = 0
    for row in candidate_rows:
        if limit is not None and sent_count >= limit:
            break

        business_id = row.get("business_id")
        business = st.get_business(business_id) if business_id else None

        if business is None or business.get("do_not_contact"):
            dropped["dnc"] += 1
            continue
        if _lint_failed(row):
            dropped["lint_failed"] += 1
            continue
        if not _preview_ok(st, row):
            dropped["preview_not_approved"] += 1
            continue
        if _business_has_replied_or_terminal_row(st, business_id, row.get("id")):
            dropped["already_replied"] += 1
            continue
        owner_email = business.get("owner_email")
        if not owner_email:
            dropped["no_email"] += 1
            continue
        if remaining_cap <= 0:
            dropped["cap_reached"] += 1
            continue

        to_email = recipient_override or owner_email
        subject = row.get("draft_subject") or ""
        if recipient_override:
            subject = f"[TEST to {owner_email}] {subject}"
        body = row.get("draft_body") or ""
        sender = st.get_config("sender", {}) or {}

        try:
            result = send_email(
                to_email=to_email,
                subject=subject,
                body=body,
                sender_name=sender.get("name") or "",
                settings=settings,
                mock=mock,
                business_id=business_id,
            )
        except Exception as exc:  # noqa: BLE001 — one bad send must not abort the whole batch
            dropped["gmail_error"] += 1
            st.log_event(
                "outreach", row["id"], "send_failed", {"error": f"{type(exc).__name__}: {exc}"}
            )
            continue

        patch: dict[str, Any] = {
            "gmail_message_id": result["gmail_message_id"],
            "gmail_thread_id": result.get("gmail_thread_id"),
        }
        if recipient_override:
            patch["test_recipient"] = to_email
        st.update_outreach(row["id"], patch)
        row.update(patch)

        state_machine.transition(st, row, "sent")
        st.log_event(
            "outreach",
            row["id"],
            "sent",
            {"gmail_message_id": result["gmail_message_id"], "to": to_email},
        )

        sent_count += 1
        remaining_cap -= 1

    return {"script": "send", "in": in_count, "sent": sent_count, "dropped": dropped}


def main() -> None:
    parser = argparse.ArgumentParser(description="Send drafted outreach emails via Gmail API")
    parser.add_argument("--date", default=None)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--store", choices=["local", "supabase"], default=None)
    parser.add_argument("--store-root", default=None)
    parser.add_argument(
        "--recipient-override",
        default=None,
        help="Send every message to this address instead of owner_email (operator dry-run to "
        "their own inbox); subject is prefixed '[TEST to <original owner_email>] ' and the row "
        "records test_recipient. Falls back to env PRODCRAFT_RECIPIENT_OVERRIDE.",
    )
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    settings = config.bootstrap()
    reject_mock_with_supabase(parser, args)  # --mock + --store supabase is a hard error
    store_kind = args.store or ("local" if args.mock else settings.store_kind)
    st = store_mod.get_store(kind=store_kind, root=args.store_root)
    today = _parse_date(args.date)
    recipient_override = args.recipient_override or os.environ.get("PRODCRAFT_RECIPIENT_OVERRIDE")

    try:
        stats = run_send(
            st,
            settings,
            today=today,
            mock=args.mock,
            recipient_override=recipient_override,
            limit=args.limit,
        )
    except Exception as exc:  # noqa: BLE001 — top-level failure must reach the error channel
        from execution.personal_workflows.prodcraft_medspa.common import notify

        notify.error("prodcraft_medspa.send", f"{type(exc).__name__}: {exc}")
        raise

    print(json.dumps(stats))


if __name__ == "__main__":
    main()
