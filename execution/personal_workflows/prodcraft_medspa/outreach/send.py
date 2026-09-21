"""
send.py
description: Send drafted outreach emails via the Gmail API (users.messages.send). Per the
    operator's 2026-09-16 decision, the pipeline runs with no human in the loop until a prospect
    replies positive or neutral — so sending is automated here (previously "human sends" via
    gmail_drafts.py drafts). Sends only rows in status `drafted` that passed lint, whose business
    is not do_not_contact, whose preview is approved/live and not takedown, respects the daily cap
    (outreach.daily_queue.effective_cap, the Phase-0 warmup-ramped cap) counted across all touches
    sent today, the bounce halt
    (outreach.daily_queue.halt_reason), and never sends to a business that already has another
    outreach row in a replied/terminal status (replied, call_booked, closed_won, closed_lost, dnc).
inputs: CLI: [--date YYYY-MM-DD] [--mock] [--store {local,supabase}] [--store-root PATH]
    [--recipient-override EMAIL] [--limit N]. Env PRODCRAFT_RECIPIENT_OVERRIDE is used when
    --recipient-override is not passed. `--mock` writes a .eml file under
    .tmp/prodcraft_medspa/sent/ instead of calling the Gmail API and records a fake message id
    `mock-<uuid>`.
outputs: stdout JSON stat line {"script":"send","in":n,"sent":n,"cap":n,"dropped":{"cap_reached":n,
    ...}}; with --stats instead {"script":"send","stats":"sends_vs_cap","days":[...],"sent":n,"cap":n,
    "line":"..."} (trailing 7 days, nothing sent).
    Original stat-line detail: {"script":"send","in":n,"sent":n,"cap":n,"dropped":{"cap_reached":n,
    "halted":n,"lint_failed":n,"dnc":n,"preview_not_approved":n,"preview_not_public":n,
    "already_replied":n,"no_email":n,"gmail_error":n}}. `cap` is the Phase-0 warmup-ramped cap
    (daily_queue.effective_cap; plain phase0.cap under --mock). `preview_not_public` counts rows
    dropped because a LIVE send (not --mock, no --recipient-override) found the row's preview
    publish_mode != "r2" or its subdomain_url host not ending in config.preview_host_suffix — an
    operator dry-run via --recipient-override bypasses this guard (prints a WARNING). Every sent
    message carries a `List-Unsubscribe: <mailto:...>` header alongside the body's plain-text
    opt-out line. Store mutations: outreach status drafted->sent (via state_machine.transition,
    which sets sent_at and increments phase0.sends for touch 1), gmail_message_id/gmail_thread_id
    patches, `test_recipient` patch when --recipient-override is used, and a `sent` events row per
    send.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
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
        # item 1 (round-2 audit): --recipient-override also bypasses the preview-host guard below
        # (a dry-run to the operator's own inbox has no business checking the PROSPECT-facing
        # preview host) — printed unmistakably so a scrollback/CI log never hides that the guard
        # was skipped this run.
        print("WARNING: --recipient-override bypasses the preview-host guard (preview_not_public check skipped)")
    else:
        print("LIVE RECIPIENTS: real prospects will receive mail")


def _preview_host_ok(preview_row: dict | None, preview_host_suffix: str) -> bool:
    """item 1 (round-2 audit): a live send (no --recipient-override) may only go out for a row
    whose preview is actually publicly reachable — `publish_mode == "r2"` (not "local"/"mock")
    AND its host ends with `config.preview_host_suffix`. A preview built --publish-mode local (or
    still under a mock run's synthetic "mock" publish_mode) is never public, so sending its link to
    a real prospect would hand them a dead/inaccessible URL."""
    if not preview_row:
        return False
    if preview_row.get("publish_mode") != "r2":
        return False
    host = (preview_row.get("subdomain_url") or "").split("//", 1)[-1].split("/", 1)[0]
    return bool(host) and host.endswith(preview_host_suffix)


def _parse_date(value: str | None) -> date:
    # Round-4 item C: default to the UTC calendar day — `_sent_today_count` buckets `sent_at`
    # by UTC, so a local `date.today()` near midnight west of UTC would count the wrong day.
    if not value:
        return datetime.now(timezone.utc).date()
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


# item 18 (CRITICAL, round-3 Hormozi lens): item 1's lint fix means a touch-2 draft with the
# `[[LOOM URL]]` operator placeholder now PASSES lint (rule 6 no longer trips on it). Nothing in
# send.py used to look at `notes.needs_operator_input` at all — without this guard, a live email
# containing the literal text "[[LOOM URL]]" would go out to a real prospect the moment
# daily_queue.py flags a row needs_operator_input (or a placeholder just never gets filled in).
_UNRESOLVED_TOKEN_RE = re.compile(r"\[\[[^\[\]]*\]\]|\{\{[^{}]*\}\}")


def _needs_operator_input(row: dict) -> bool:
    """True when this drafted row must never be sent as-is: `notes.needs_operator_input` was
    explicitly flagged (e.g. daily_queue.py's lint-failure escalation, item 2), OR its rendered
    subject/body still carries an unresolved `[[...]]`/`{{...}}` token (the `[[LOOM URL]]`
    placeholder with no `notes.loom_url` set, or any stray unrendered template variable)."""
    if bool(_parse_notes(row).get("needs_operator_input")):
        return True
    full_text = f"{row.get('draft_subject') or ''}\n{row.get('draft_body') or ''}"
    return bool(_UNRESOLVED_TOKEN_RE.search(full_text))


def _find_preview(st: Any, row: dict) -> dict | None:
    preview_id = row.get("preview_id")
    if not preview_id:
        return None
    for p in _store_helpers.previews_for_business(st, row.get("business_id")):
        if p.get("id") == preview_id:
            return p
    return None


def _preview_ok(preview_row: dict | None) -> bool:
    """The row's preview must exist, be approved/live, and not be under takedown."""
    if not preview_row:
        return False
    return preview_row.get("status") in ("approved", "live") and not preview_row.get("takedown")


def _business_has_replied_or_terminal_row(st: Any, business_id: str | None, exclude_outreach_id: str | None) -> bool:
    if not business_id:
        return False
    for r in _store_helpers.outreach_for_business(st, business_id):
        if r.get("id") == exclude_outreach_id:
            continue
        if r.get("status") in _TERMINAL_OR_REPLIED_STATUSES:
            return True
    return False


def _release_claim(st: Any, outreach_id: str) -> None:
    """Best-effort rollback of an `outreach.claim_row(..., "sent")` claim whose send never
    actually happened (HeaderInjectionError or any other pre-send exception). Never raises —
    a failed rollback just leaves the row `sent`-but-undelivered for an operator to notice via
    `send_failed`/`send_skipped` events, which is strictly better than crashing the whole batch."""
    try:
        st.claim_row("outreach", outreach_id, "sent", "drafted")
    except Exception as exc:  # noqa: BLE001 — rollback is best-effort; log, never raise
        print(f"[send] could not release claim on outreach {outreach_id}: {exc}", file=sys.stderr)


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


SENDS_VS_CAP_DAYS = 7


def sends_vs_cap(st: Any, today: date, *, mock: bool = False, days: int = SENDS_VS_CAP_DAYS) -> dict:
    """Round-4 weekly number "Sends vs cap": per UTC calendar day over the trailing `days`
    (ending `today`, inclusive), the sends across all touches (`_sent_today_count`, the same
    counter the cap check uses) against that day's effective cap (`daily_queue.effective_cap`,
    the warmup-ramped Phase-0 cap; plain `phase0.cap` under `mock`). Ramp logic is NOT
    duplicated here: the cap for each past day is whatever `effective_cap` says for that date.
    Returns {"days": [{"date", "sent", "cap"}, ...] oldest first, "sent": total, "cap": total,
    "window_days": days}.
    """
    from datetime import timedelta

    per_day: list[dict] = []
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        per_day.append(
            {
                "date": day.isoformat(),
                "sent": _sent_today_count(st, day),
                "cap": int(daily_queue.effective_cap(st, day, mock=mock)),
            }
        )
    return {
        "days": per_day,
        "sent": sum(d["sent"] for d in per_day),
        "cap": sum(d["cap"] for d in per_day),
        "window_days": days,
    }


def format_sends_vs_cap(summary: dict) -> str:
    """One Telegram-safe line (plain hyphens, no U+2014), e.g.
    `sends vs cap (7d): 12/35, per day 2/5 2/5 2/5 2/5 2/5 1/5 1/5`."""
    per_day = " ".join(f"{d['sent']}/{d['cap']}" for d in summary.get("days", []))
    return (
        f"sends vs cap ({summary.get('window_days', SENDS_VS_CAP_DAYS)}d): "
        f"{summary.get('sent', 0)}/{summary.get('cap', 0)}, per day {per_day or 'n/a'}"
    )


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
        # item 2 (round-2 audit): CAN-SPAM-adjacent good practice — a machine-readable opt-out
        # header alongside the body's plain-text opt-out line lint_draft.py already requires.
        message["List-Unsubscribe"] = f"<mailto:{authenticated_address}?subject=unsubscribe>"
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
    message["List-Unsubscribe"] = f"<mailto:{authenticated_address}?subject=unsubscribe>"
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
        "preview_not_public": 0,
        "already_claimed": 0,
        "live_recipients_not_enabled": 0,
        "needs_operator_input": 0,
    }
    live_recipients = not bool(recipient_override)

    # item 8 (round-3 major): an unset or misnamed PRODCRAFT_RECIPIENT_OVERRIDE resolves to ""
    # which main() already turns into None — indistinguishable in-process from an operator who
    # deliberately never set an override because they WANT live sends. In CI specifically, that
    # ambiguity must resolve to "refuse," not "send live": a second explicit repo variable,
    # PRODCRAFT_LIVE_RECIPIENTS, must equal "true" before a github-actions run with no
    # --recipient-override is allowed to reach a real prospect.
    if (
        not recipient_override
        and os.environ.get("PRODCRAFT_ENV") == "github-actions"
        and (os.environ.get("PRODCRAFT_LIVE_RECIPIENTS") or "").strip().lower() != "true"
    ):
        dropped["live_recipients_not_enabled"] = 1
        print(
            "SEND BLOCKED: PRODCRAFT_ENV=github-actions with no --recipient-override requires "
            "the repo variable PRODCRAFT_LIVE_RECIPIENTS=true to send live"
        )
        from execution.personal_workflows.prodcraft_medspa.common import notify

        notify.error(
            "prodcraft_medspa.send",
            "live sends blocked: PRODCRAFT_LIVE_RECIPIENTS is not 'true' in github-actions",
            1,
        )
        return {
            "script": "send",
            "in": 0,
            "sent": 0,
            "dropped": dropped,
            "recipient_override": False,
            "live_recipients": True,
            "cap": 0,
        }

    _print_recipient_banner(recipient_override)
    preview_host_suffix = str(
        st.get_config("preview_host_suffix", ".preview.prodcraft.fyi") or ".preview.prodcraft.fyi"
    )
    # item 1: the guard only applies to a genuinely live send (not --mock, no
    # --recipient-override) — a --mock run never reaches a real prospect (it writes a .eml file),
    # and an operator dry-run (--recipient-override) never reaches a real prospect either (WARNING
    # already printed above by _print_recipient_banner), so both are exempt by design.
    preview_guard_active = not mock and not recipient_override
    # item 3: warmup-ramped cap (never applies under --mock; see daily_queue.effective_cap).
    # Computed early (pure, cheap) so every return path — including the two early-exit gates
    # below — can report it in the stat line, not just the happy path.
    cap = daily_queue.effective_cap(st, today, mock=mock)

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
            "cap": cap,
        }

    from execution.personal_workflows.prodcraft_medspa.common import notify

    halt = daily_queue.halt_reason(st, today)
    if halt:
        print(f"SEND HALTED: {halt}")
        dropped["halted"] = in_count
        # item 12 (Dario lens, round-3): a bounce-rate halt used to return silently — a real
        # production hazard (undeliverable mail piling up) with no operator signal at all.
        notify.once_per_day(st, "send_halted", "prodcraft_medspa.send", f"SEND HALTED: {halt}", today)
        return {
            "script": "send",
            "in": in_count,
            "sent": 0,
            "dropped": dropped,
            "recipient_override": bool(recipient_override),
            "live_recipients": live_recipients,
            "cap": cap,
        }

    # item 12 (Dario lens, round-3): a day with nothing queued to send is either fine (nothing
    # due) or a sign the pipeline upstream stalled — either way the operator should know, once
    # per day, rather than reading a silent "0 sent" in a cron log.
    if in_count == 0:
        notify.once_per_day(
            st, "send_zero_candidates", "prodcraft_medspa.send",
            "0 candidates, nothing to send today", today,
        )

    # Deterministic processing order (oldest-due first), mirroring LocalStore.queue()'s ordering.
    candidate_rows.sort(key=lambda r: (r.get("next_touch_at") or "", r.get("created_at") or ""))

    sent_count = 0
    sent_today_at_start = _sent_today_count(st, today)
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
        if _needs_operator_input(row):
            dropped["needs_operator_input"] += 1
            st.log_event(
                "outreach", row["id"], "send_skipped", {"reason": "needs_operator_input"}
            )
            continue
        preview_row = _find_preview(st, row)
        if not _preview_ok(preview_row):
            dropped["preview_not_approved"] += 1
            continue
        if preview_guard_active and not _preview_host_ok(preview_row, preview_host_suffix):
            dropped["preview_not_public"] += 1
            st.log_event(
                "outreach",
                row["id"],
                "send_dropped",
                {
                    "reason": "preview_not_public",
                    "publish_mode": (preview_row or {}).get("publish_mode"),
                    "subdomain_url": (preview_row or {}).get("subdomain_url"),
                },
            )
            continue
        if _business_has_replied_or_terminal_row(st, business_id, row.get("id")):
            dropped["already_replied"] += 1
            continue
        owner_email = business.get("owner_email")
        if not owner_email:
            dropped["no_email"] += 1
            continue
        # item 6 (round-3 major): re-read the sent-today count immediately before each send
        # instead of decrementing an in-memory counter computed once at the top of the run — two
        # concurrent `send.py` processes sharing one Store would otherwise each decrement their
        # own stale copy and together double the day's cap.
        # The fresh store count is combined with this run's own tally (max of the two): the
        # store count catches a concurrent process, the tally catches this process's own sends
        # whose sent_at is stamped with the wall clock rather than the `today` being enforced.
        used_today = max(_sent_today_count(st, today), sent_today_at_start + sent_count)
        if max(0, cap - used_today) <= 0:
            dropped["cap_reached"] += 1
            continue

        # item 11 (round-3 critical, Dario lens): claim the row atomically before sending — the
        # actual compare-and-set that prevents a concurrent second process from sending the SAME
        # row twice. A failed claim means another process (or another pass) already sent it.
        if not st.claim_row("outreach", row["id"], "drafted", "sent"):
            dropped["already_claimed"] += 1
            st.log_event("outreach", row["id"], "send_skipped", {"reason": "claim_failed"})
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
            # item 11: the claim above already flipped this row to `sent` in the store even
            # though no email went out — release the claim so a retry can pick it up, instead of
            # leaving a falsely-"sent" row with no message ever delivered.
            _release_claim(st, row["id"])
            continue
        except Exception as exc:  # noqa: BLE001 — one bad send must not abort the whole batch
            dropped["gmail_error"] += 1
            st.log_event(
                "outreach", row["id"], "send_failed", {"error": f"{type(exc).__name__}: {exc}"}
            )
            _release_claim(st, row["id"])
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

    if sent_count == 0 and dropped["preview_not_approved"] > 0:
        # C5: a silent zero-send day must page the operator, not sit quietly in a cron log.
        from execution.personal_workflows.prodcraft_medspa.common import notify

        notify.error(
            "prodcraft_medspa.send",
            f"0 sent: {dropped['preview_not_approved']} candidates have unapproved previews; "
            "approve them in the dashboard or with preview/approve.py",
            1,
        )

    if dropped["needs_operator_input"] > 0:
        # item 18 (CRITICAL, round-3 Hormozi lens): a row held back here (a stale placeholder or
        # a lint-escalated flag) needs an operator to fill in the missing piece (e.g.
        # notes.loom_url) and redraft — once per day, not once per row/run.
        notify.once_per_day(
            st,
            "send_needs_operator_input",
            "prodcraft_medspa.send",
            f"{dropped['needs_operator_input']} drafted row(s) held back: needs_operator_input "
            "(unresolved placeholder or a lint-escalated flag) — fill in the missing value "
            "(e.g. notes.loom_url) and redraft",
            today,
        )

    return {
        "script": "send",
        "in": in_count,
        "sent": sent_count,
        "dropped": dropped,
        "recipient_override": bool(recipient_override),
        "live_recipients": live_recipients,
        "cap": cap,
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
        "--stats",
        action="store_true",
        help="Print the trailing-7-day sends-vs-cap summary (sends_vs_cap) as one JSON line and "
        "exit without sending anything (round-4 weekly number; also reported by fit_weights.py).",
    )
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

    if args.stats:
        # Round-4 item B: the weekly cron reads this; a failure here must page, same as run_send.
        try:
            summary = sends_vs_cap(st, today, mock=args.mock)
        except Exception as exc:  # noqa: BLE001 — top-level failure must reach the error channel
            from execution.personal_workflows.prodcraft_medspa.common import notify

            notify.error("prodcraft_medspa.send", f"--stats: {type(exc).__name__}: {exc}")
            raise
        print(json.dumps({"script": "send", "stats": "sends_vs_cap", **summary, "line": format_sends_vs_cap(summary)}))
        return

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
