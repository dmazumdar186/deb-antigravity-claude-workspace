"""
notify.py
description: Telegram notifier. error() is the error-channel notifier every script's top-level
    failure calls. reply() posts the human-takeover alert scan_replies.py sends the moment a
    prospect replies positive or neutral (or asks for a call) — the operator's cue to step in
    manually per the 2026-09-16 operator decision. weekly_report() posts scripts/fit_weights.py's
    compact weekly summary (or "not enough data yet" message) on the same transport.
inputs: --sample / --sample-reply (CLI); env TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, PRODCRAFT_ENV.
outputs: A Telegram sendMessage call; stderr log line and False return when env is unset (no-op, no crash).
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[4] / ".env")

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def error(service: str, error: str, count: int = 1, environment: str | None = None) -> bool:
    """Post `service / environment / error / count` to the Telegram error channel.

    Returns True on a successful send, False on any failure or missing config
    (in which case the message is also printed to stderr so it isn't lost).
    """
    env = environment or os.environ.get("PRODCRAFT_ENV") or "local"
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    line1 = f"{service} / {env} / {error} / {count}"
    text = f"{line1}\n{timestamp}"

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print(f"[notify.error, no-op — Telegram not configured] {text}", file=sys.stderr)
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
    except Exception as exc:  # noqa: BLE001 — notify must never raise; log and report failure instead
        print(f"[notify.error failed: {exc}] {text}", file=sys.stderr)
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
    """Post the human-takeover alert for a positive/neutral reply to the Telegram channel.

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

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print(f"[notify.reply, no-op: Telegram not configured] {text}", file=sys.stderr)
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
        print(f"[notify.reply failed: {exc}] {text}", file=sys.stderr)
        return False


def weekly_report(lines: list[str], environment: str | None = None) -> bool:
    """Post a compact weekly fit_weights summary to the Telegram error channel.

    7-line max total (mirrors reply()'s fixed shape): up to 6 content `lines` plus one trailing
    `<environment> / <UTC timestamp>` line appended here. A longer `lines` list is truncated
    rather than raising, since a summary is better than a failed send. No line may contain
    U+2014 (em-dash) per the workspace's Telegram formatting convention — enforced by the caller
    (scripts/fit_weights.py), not here. Same transport/env/no-op behavior as error()/reply().
    """
    env = environment or os.environ.get("PRODCRAFT_ENV") or "local"
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    text = "\n".join(lines[:6] + [f"{env} / {timestamp}"])

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print(f"[notify.weekly_report, no-op: Telegram not configured] {text}", file=sys.stderr)
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
        print(f"[notify.weekly_report failed: {exc}] {text}", file=sys.stderr)
        return False


def main() -> None:
    """description: CLI entry — send a sample wire-up check message.
    inputs: --sample, --sample-reply
    outputs: stdout True/False of the send result.
    """
    parser = argparse.ArgumentParser(description="Telegram notifier")
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Send 'prodcraft_medspa / local / sample wire-up check / 1' and print the result",
    )
    parser.add_argument(
        "--sample-reply",
        action="store_true",
        help="Send one synthetic reply() notification (synthetic names only) and print the result",
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
            sentiment="positive",
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
