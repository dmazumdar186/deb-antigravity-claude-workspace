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
from datetime import date, datetime, timezone
from email.message import EmailMessage
from email.policy import default as _email_policy_default
from email.utils import formataddr
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from execution.personal_workflows.prodcraft_medspa.common import config, store as store_mod  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.outreach import (  # noqa: E402
    _store_helpers,
    daily_queue,
    gmail_drafts,
    lint_draft,
    state_machine,
)
from execution.personal_workflows.prodcraft_medspa.scripts._stage_runner import (  # noqa: E402
    reject_mock_with_supabase,
)

MOCK_AUTHENTICATED_ADDRESS = "mock@example.test"

# Any of these on ANOTHER outreach row for the same business means "do not send this row" —
# the prospect already replied (any sentiment that led to a real conversation) or the deal is
# terminal one way or another.
_TERMINAL_OR_REPLIED_STATUSES = {"replied", "call_booked", "closed_won", "closed_lost", "dnc"}


class HeaderInjectionError(ValueError):
    """Raised when `to_email` or `subject` carries a CR/LF (M2 — email header injection)."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _mask_email(address: str) -> str:
    """Mask an email address for the startup banner: `deb@example.com` -> `d*b@example.com`."""
    local, sep, domain = address.partition("@")
    if not sep:
        return "***"
    if len(local) <= 2:
        masked_local = (local[0] + "*") if local else "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def _print_recipient_banner(recipient_override: str | None) -> None:
    """C2: an unmistakable one-line banner every run starts with, so a live-recipient run is
    never mistaken for a safe dry run in a scrollback or a CI log."""
    if recipient_override:
        print(f"RECIPIENT OVERRIDE ACTIVE -> {_mask_email(recipient_override)}")
    else:
        print("LIVE RECIPIENTS: real prospects will receive mail")


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
    """Count sends across ALL touches today, for the daily cap.

    Item 10: compared in UTC — `sent_at` is always stored as a UTC ISO string (state_machine's
    `_now_iso()`), so a naive local `.date()` would mis-bucket a late-evening manual run near
    midnight in any timezone west of UTC. `today` is compared as a UTC calendar date too.
    """
    today_str = today.isoformat()
    count = 0
    for r in _store_helpers.list_all(st, "outreach"):
        sent_at = r.get("sent_at")
        if not sent_at:
            continue
        try:
            sent_dt = datetime.fromisoformat(str(sent_at).replace("Z", "+00:00"))
        except ValueError:
            continue
        if sent_dt.tzinfo is None:
            sent_dt = sent_dt.replace(tzinfo=timezone.utc)
        if sent_dt.astimezone(timezone.utc).date().isoformat() == today_str:
            count += 1
    return count


def _reject_header_injection(to_email: str, subject: str) -> None:
    """M2: a CR/LF in `to_email` or `subject` could inject extra MIME headers (e.g. a forged
    Bcc). Reject outright rather than let EmailMessage silently fold/strip it."""
    for label, value in (("to_email", to_email), ("subject", subject)):
        if "\r" in (value or "") or "\n" in (value or ""):
            raise HeaderInjectionError(f"{label} contains a CR or LF (possible header injection)")


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
    """Send one email via users.messages.send. In --mock mode, writes a .eml file instead.

    M1/M2: built with `email.message.EmailMessage`/`policy=email.policy.default` (which raises
    on embedded header-injection-shaped content itself, as a second line of defense behind
    `_reject_header_injection`), `From` is `formataddr((sender_name, authenticated_address))`
    where `authenticated_address` comes from `users().getProfile()` live, or
    MOCK_AUTHENTICATED_ADDRESS ("mock@example.test") under --mock.
    """
    _reject_header_injection(to_email, subject)

    if mock:
        authenticated_address = MOCK_AUTHENTICATED_ADDRESS
        out_dir = settings.TMP / "sent"
        out_dir.mkdir(parents=True, exist_ok=True)
        eml_path = out_dir / f"{business_id or 'sent'}_{uuid.uuid4().hex[:8]}.eml"
        message = EmailMessage(policy=_email_policy_default)
        message["To"] = to_email
        message["Subject"] = subject
        message["From"] = formataddr((sender_name, authenticated_address))
        message.set_content(body)
        eml_path.write_bytes(message.as_bytes())
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
    profile = service.users().getProfile(userId="me").execute()
    authenticated_address = profile.get("emailAddress") or ""

    message = EmailMessage(policy=_email_policy_default)
    message["To"] = to_email
    message["Subject"] = subject
    message["From"] = formataddr((sender_name, authenticated_address))
    message.set_content(body)
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
        "live_send_not_confirmed": 0,
        "header_injection": 0,
    }
    live_recipients = not bool(recipient_override)
    _print_recipient_banner(recipient_override)

    candidate_rows = list(_store_helpers.outreach_by_status(st, "drafted"))
    in_count = len(candidate_rows)

    # C2 live-send gate: absent an operator dry-run (--recipient-override), NOTHING sends until
    # the operator has explicitly run `send.py --confirm-live-sends` (which also validates
    # config.sender.physical_address — see lint_draft.sender_address_is_valid). This applies to
    # BOTH live and --mock runs by design: --mock is meant to rehearse the exact real pipeline
    # including this safety gate, so a fresh mock store starts unconfirmed too (documented here
    # and in the CLI --confirm-live-sends help).
    live_send_confirmed = bool(st.get_config("live_send_confirmed", False))
    if not recipient_override and not live_send_confirmed:
        print(
            "SEND BLOCKED: config.live_send_confirmed is false and no --recipient-override was "
            "given. Confirm with: python3 -m execution.personal_workflows.prodcraft_medspa."
            "outreach.send --confirm-live-sends [--mock] [--store ...] [--store-root ...]"
        )
        dropped["live_send_not_confirmed"] = in_count
        from execution.personal_workflows.prodcraft_medspa.common import notify

        notify.error(
            "prodcraft_medspa.send", "live sends blocked: config.live_send_confirmed is false", 1
        )
        return {
            "script": "send",
            "in": in_count,
            "sent": 0,
            "dropped": dropped,
            "recipient_override": bool(recipient_override),
            "live_recipients": live_recipients,
        }

    halt = daily_queue.halt_reason(st, today)
    if halt:
        print(f"SEND HALTED: {halt}")
        dropped["halted"] = in_count
        return {
            "script": "send",
            "in": in_count,
            "sent": 0,
            "dropped": dropped,
            "recipient_override": bool(recipient_override),
            "live_recipients": live_recipients,
        }

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
        except HeaderInjectionError as exc:
            dropped["header_injection"] += 1
            st.log_event(
                "outreach", row["id"], "send_failed", {"error": f"HeaderInjectionError: {exc}"}
            )
            continue
        except Exception as exc:  # noqa: BLE001 — one bad send must not abort the whole batch
            dropped["gmail_error"] += 1
            st.log_event(
                "outreach", row["id"], "send_failed", {"error": f"{type(exc).__name__}: {exc}"}
            )
            continue

        # C1: the email is already out the door at this point — a failure recording it in the
        # store must NEVER cause a re-send. Record everything we can; on failure, log
        # `send_recorded_failed` with the gmail message id and force at least a minimal
        # update_outreach so the row shows `sent` (the state_machine side-effects — phase0
        # counters, the `status:...->sent` event — are best-effort past this point). Only
        # re-raise if even that minimal patch fails, after printing the message id so it is
        # never lost.
        gmail_message_id = result["gmail_message_id"]
        try:
            patch: dict[str, Any] = {
                "gmail_message_id": gmail_message_id,
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
                {"gmail_message_id": gmail_message_id, "to": to_email},
            )
        except Exception as exc:  # noqa: BLE001 — a recording failure must never trigger a re-send
            try:
                st.log_event(
                    "outreach",
                    row["id"],
                    "send_recorded_failed",
                    {"gmail_message_id": gmail_message_id, "error": f"{type(exc).__name__}: {exc}"},
                )
            except Exception:  # noqa: BLE001 — even the failure-log call must not crash the batch
                print(
                    f"[send] could not log send_recorded_failed for gmail_message_id="
                    f"{gmail_message_id}",
                    file=sys.stderr,
                )
            try:
                st.update_outreach(
                    row["id"],
                    {"status": "sent", "sent_at": _now_iso(), "gmail_message_id": gmail_message_id},
                )
            except Exception:
                print(
                    f"[send] FAILED to record sent status after a real send; gmail_message_id="
                    f"{gmail_message_id} was sent but the store was not updated — reconcile "
                    f"manually.",
                    file=sys.stderr,
                )
                raise

        sent_count += 1
        remaining_cap -= 1

    if sent_count == 0 and dropped["preview_not_approved"] > 0:
        # C5: a silent zero-send day must page the operator, not sit quietly in a cron log.
        from execution.personal_workflows.prodcraft_medspa.common import notify

        notify.error(
            "prodcraft_medspa.send",
            f"0 sent: {dropped['preview_not_approved']} candidates have unapproved previews; "
            "approve them in the dashboard or with preview/approve.py",
            1,
        )

    return {
        "script": "send",
        "in": in_count,
        "sent": sent_count,
        "dropped": dropped,
        "recipient_override": bool(recipient_override),
        "live_recipients": live_recipients,
    }


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
    parser.add_argument(
        "--confirm-live-sends",
        action="store_true",
        help="Validate config.sender.physical_address (lint_draft.sender_address_is_valid) and, "
        "if valid, set config.live_send_confirmed=True (logged as event live_send_confirmed, "
        "actor cli) before proceeding — required once before any run without "
        "--recipient-override is allowed to send anything (C2 live-send gate).",
    )
    args = parser.parse_args()

    settings = config.bootstrap()
    store_kind = reject_mock_with_supabase(parser, args)  # --mock + --store supabase is a hard error
    st = store_mod.get_store(kind=store_kind, root=args.store_root)
    today = _parse_date(args.date)
    recipient_override = (
        args.recipient_override or os.environ.get("PRODCRAFT_RECIPIENT_OVERRIDE") or ""
    ).strip() or None

    if args.confirm_live_sends:
        sender_cfg = st.get_config("sender", {}) or {}
        address_valid, reason = lint_draft.sender_address_is_valid(sender_cfg.get("physical_address"))
        if not address_valid:
            parser.error(
                f"--confirm-live-sends: config.sender.physical_address is invalid ({reason}); "
                "fix it before confirming live sends"
            )
        st.set_config("live_send_confirmed", True)
        st.log_event("config", "live_send_confirmed", "live_send_confirmed", {"actor": "cli"})
        print("live_send_confirmed set to True (actor: cli)")

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

    # C2: a scheduled GitHub Actions run must go RED, not quietly no-op, if it reaches send.py
    # unconfirmed and without a dry-run override — a green "0 sent" workflow run would hide the
    # fact that the operator never confirmed live sending.
    if (
        os.environ.get("PRODCRAFT_ENV") == "github-actions"
        and not recipient_override
        and not bool(st.get_config("live_send_confirmed", False))
    ):
        sys.exit(1)


if __name__ == "__main__":
    main()
