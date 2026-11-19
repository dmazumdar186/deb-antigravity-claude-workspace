"""
notify.py
description: Telegram notifier. Operator order 2026-11-19: "any telegram alert should only come
    from positive replies for my campaigns only, nothing else ever". reply() posts the
    human-takeover alert ONLY when sentiment == "positive"; every other sentiment (neutral,
    negative, remove, ...) is logged to stderr. error() (every script's top-level failure path)
    and weekly_report() (scripts/fit_weights.py's summary) never post: stderr/run log only.
inputs: --sample / --sample-reply (CLI); env TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, PRODCRAFT_ENV.
outputs: A Telegram sendMessage call for positive replies only; otherwise a stderr log line and
    False return (no opt-in flag restores other alerts: "nothing else ever").
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[4] / ".env")

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def once_per_day(store: Any, dedupe_key: str, service: str, message: str, today: Any) -> None:
    """Post `error(service, message)` at most once per calendar day per `dedupe_key`, tracked in
    `store.get_config('notify_dedupe', {})` — a small `{dedupe_key: last_notified_date_iso}` dict
    on the SAME Store every caller already reads/writes. Used wherever a real production hazard
    (a bounce halt, a zero-send day, a failed takedown) needs to page the operator without
    spamming the same alert on every re-run of the same day (round-3 audit items 12/14).
    `today` may be a `date` or an ISO string; only `.isoformat()`/`str()` matters.
    """
    today_str = today.isoformat() if hasattr(today, "isoformat") else str(today)
    dedupe = dict(store.get_config("notify_dedupe", {}) or {})
    if dedupe.get(dedupe_key) == today_str:
        return
    error(service, message, 1)
    dedupe[dedupe_key] = today_str
    store.set_config("notify_dedupe", dedupe)


def _is_ci_env(environment: str | None) -> bool:
    """item 4 (round-3 major): stderr in `PRODCRAFT_ENV == 'github-actions'` is a PERSISTED CI
    log, not a transient console — the full `error` text (which can carry an owner name, owner
    email, or business name via a caller's f-string) must never land there. Checks the resolved
    `environment` (what actually gets printed/posted), not the raw env var, so a caller that
    explicitly passes `environment=...` is honored the same way."""
    return (environment or os.environ.get("PRODCRAFT_ENV") or "local") == "github-actions"


def error(service: str, error: str, count: int = 1, environment: str | None = None) -> bool:
    """Log `service / environment / error / count` to stderr. Never posts to Telegram
    (operator order 2026-11-19: Telegram carries positive campaign replies only). Always returns
    False. Under PRODCRAFT_ENV=github-actions the error text is redacted, since that stderr is a
    persisted CI log.
    """
    env = environment or os.environ.get("PRODCRAFT_ENV") or "local"
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    line1 = f"{service} / {env} / {error} / {count}"
    text = f"{line1}\n{timestamp}"
    stderr_text = f"{service} / {env} / [redacted for CI log] / {count}" if _is_ci_env(env) else text

    print(f"[notify.error, not posted: Telegram is positive-replies-only] {stderr_text}", file=sys.stderr)
    return False


def reply(
    business_name: str,
    owner_name: str,
    owner_email: str,
    sentiment: str,
    summary: str,
    suggested_next_step: str,
    wants_call: bool,
    gmail_thread_id: str,
    preview_url: str,
    environment: str | None = None,
) -> bool:
    """Post the human-takeover alert for a POSITIVE reply to the Telegram channel. Any other
    sentiment (neutral, negative, remove, bounce, ooo) is logged to stderr only and returns False
    (operator order 2026-11-19: positive campaign replies only, nothing else ever).

    Fixed, scannable shape (7 lines, no em-dash anywhere):
        ProdCraft reply: <SENTIMENT> from <business>
        Owner: <owner name> <<owner email>>
        <one-line summary>
        Next step: <suggested_next_step>[ (wants call)]
        Preview: <preview_url>
        Gmail: https://mail.google.com/mail/u/0/#all/<thread_id>
        <environment> / <UTC timestamp>

    Returns True on a successful send, False on any failure or missing config (in which case
    the message is also printed to stderr so it isn't lost).
    """
    env = environment or os.environ.get("PRODCRAFT_ENV") or "local"
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    call_suffix = " (wants call)" if wants_call else ""
    gmail_link = f"https://mail.google.com/mail/u/0/#all/{gmail_thread_id}"
    lines = [
        f"ProdCraft reply: {sentiment.upper()} from {business_name}",
        f"Owner: {owner_name} <{owner_email}>",
        summary,
        f"Next step: {suggested_next_step}{call_suffix}",
        f"Preview: {preview_url}",
        f"Gmail: {gmail_link}",
        f"{env} / {timestamp}",
    ]
    text = "\n".join(lines)
    # item 4 (round-3 major): stderr is a persisted CI log under github-actions — never print the
    # full `text` (owner name/email, business name, reply summary) there. `outreach_id` isn't a
    # parameter of reply(); gmail_thread_id is the closest non-PII identifier an operator can use
    # to look the row up, so it stands in for it here.
    stderr_text = (
        f"prodcraft_medspa.reply / {sentiment} / thread={gmail_thread_id or 'n/a'}"
        if _is_ci_env(env)
        else text
    )

    if (sentiment or "").strip().lower() != "positive":
        print(f"[notify.reply, not posted: only positive replies go to Telegram] {stderr_text}", file=sys.stderr)
        return False

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print(f"[notify.reply, no-op: Telegram not configured] {stderr_text}", file=sys.stderr)
        return False

    try:
        import requests

        resp = requests.post(
            TELEGRAM_API.format(token=token),
            json={"chat_id": chat_id, "text": text},
            timeout=20,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001 -- notify must never raise; log and report failure instead
        print(f"[notify.reply failed: {exc}] {stderr_text}", file=sys.stderr)
        return False


def weekly_report(lines: list[str], environment: str | None = None) -> bool:
    """Log a compact weekly fit_weights summary to stderr. Never posts to Telegram (operator
    order 2026-11-19: positive campaign replies only). Always returns False.

    7-line max total (mirrors reply()'s fixed shape): up to 6 content `lines` plus one trailing
    `<environment> / <UTC timestamp>` line appended here. A longer `lines` list is truncated
    rather than raising, since a summary is better than a failed send. No line may contain
    U+2014 (em-dash), enforced by the caller (scripts/fit_weights.py), not here.
    """
    env = environment or os.environ.get("PRODCRAFT_ENV") or "local"
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    text = "\n".join(lines[:6] + [f"{env} / {timestamp}"])

    print(f"[notify.weekly_report, not posted: Telegram is positive-replies-only] {text}", file=sys.stderr)
    return False


def main() -> None:
    """description: CLI entry — local wire-up check that never posts to Telegram.
    inputs: --sample, --sample-reply
    outputs: stderr log of what would be sent; stdout False (nothing posted).
    """
    parser = argparse.ArgumentParser(description="Telegram notifier")
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Log 'prodcraft_medspa / local / sample wire-up check / 1' to stderr (never posted)",
    )
    parser.add_argument(
        "--sample-reply",
        action="store_true",
        help="Log one synthetic reply() alert to stderr (never posted: a sample is not a real positive reply)",
    )
    args = parser.parse_args()

    if args.sample:
        ok = error("prodcraft_medspa", "sample wire-up check", 1)
        print(ok)
        return

    if args.sample_reply:
        ok = reply(
            business_name="Sample Med Spa",
            owner_name="Jordan Sample",
            owner_email="jordan@sample-medspa.test",
            sentiment="sample",  # not "positive": a wire-up sample must never reach Telegram
            summary="Sample reply for the wire-up check, no real prospect involved.",
            suggested_next_step="book_call",
            wants_call=True,
            gmail_thread_id="thread-sample-001",
            preview_url="https://sample-medspa.preview.prodcraft.fyi",
        )
        print(ok)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
