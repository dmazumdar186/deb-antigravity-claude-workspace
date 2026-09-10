"""
notify.py
description: Telegram error-channel notifier. Every script's top-level failure calls error().
inputs: --sample (CLI); env TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, PRODCRAFT_ENV.
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


def main() -> None:
    """description: CLI entry — send a sample wire-up check message.
    inputs: --sample
    outputs: stdout True/False of the send result.
    """
    parser = argparse.ArgumentParser(description="Telegram error-channel notifier")
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Send 'prodcraft_medspa / local / sample wire-up check / 1' and print the result",
    )
    args = parser.parse_args()

    if args.sample:
        ok = error("prodcraft_medspa", "sample wire-up check", 1)
        print(ok)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
