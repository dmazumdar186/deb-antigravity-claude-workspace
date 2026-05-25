#!/usr/bin/env python3
"""
setup_telegram_webhook.py
description: Provision/rotate Telegram bot webhook + Cloudflare TELEGRAM_WEBHOOK_SECRET so Telegram POSTs incoming messages to the worker with X-Telegram-Bot-Api-Secret-Token auth. Idempotent.
inputs: env: TELEGRAM_BOT_TOKEN (.env or shell), optional TELEGRAM_WEBHOOK_SECRET_OVERRIDE; CLI: --info, --delete, --dry-run, --worker-url, --no-cloudflare
outputs: Writes Cloudflare secret via `npx wrangler secret put`; calls Telegram Bot API setWebhook/getWebhookInfo; prints masked secret + webhook URL.
usage:
    py execution/infrastructure/setup_telegram_webhook.py --info
    py execution/infrastructure/setup_telegram_webhook.py --dry-run
    py execution/infrastructure/setup_telegram_webhook.py
"""

import argparse
import os
import secrets
import subprocess
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT / ".env")

WRANGLER_DIR = ROOT / "execution" / "infrastructure" / "api-proxy"
DEFAULT_WORKER_URL = "https://accessory-masters-api.accessory-masters.workers.dev/api/webhook/telegram"
SECRET_NAME = "TELEGRAM_WEBHOOK_SECRET"
ALLOWED_UPDATES = ["message", "edited_message"]


def mask(value: str) -> str:
    if not value or len(value) < 4:
        return "****"
    return f"****{value[-4:]}"


def telegram_api(bot_token: str, method: str, payload: dict | None = None) -> dict:
    url = f"https://api.telegram.org/bot{bot_token}/{method}"
    resp = requests.post(url, json=payload or {}, timeout=15)
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method} failed: {data}")
    return data


def set_webhook(bot_token: str, worker_url: str, secret: str) -> dict:
    return telegram_api(
        bot_token,
        "setWebhook",
        {
            "url": worker_url,
            "secret_token": secret,
            "allowed_updates": ALLOWED_UPDATES,
            "drop_pending_updates": True,
        },
    )


def get_webhook_info(bot_token: str) -> dict:
    return telegram_api(bot_token, "getWebhookInfo")


def delete_webhook(bot_token: str) -> dict:
    return telegram_api(bot_token, "deleteWebhook", {"drop_pending_updates": True})


def push_cloudflare_secret(name: str, value: str) -> None:
    print(f"Pushing {name} to Cloudflare via wrangler...")
    result = subprocess.run(
        ["npx", "wrangler", "secret", "put", name],
        input=value,
        cwd=str(WRANGLER_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=(sys.platform == "win32"),
    )
    if result.returncode != 0:
        print(f"wrangler stderr: {result.stderr}", file=sys.stderr)
        raise RuntimeError(f"wrangler secret put {name} failed (exit {result.returncode})")
    print(f"  ✓ {name} = {mask(value)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[3])
    parser.add_argument("--info", action="store_true", help="Print current Telegram webhook info and exit.")
    parser.add_argument("--delete", action="store_true", help="Delete the Telegram webhook (does not touch Cloudflare).")
    parser.add_argument("--dry-run", action="store_true", help="Print actions but don't call Telegram or wrangler.")
    parser.add_argument("--worker-url", default=DEFAULT_WORKER_URL, help="Override the worker webhook URL.")
    parser.add_argument("--no-cloudflare", action="store_true", help="Skip the wrangler secret push.")
    args = parser.parse_args()

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("ERROR: TELEGRAM_BOT_TOKEN not in .env or environment.", file=sys.stderr)
        print("Get one from @BotFather on Telegram, then put it in .env.", file=sys.stderr)
        return 1

    if args.info:
        info = get_webhook_info(bot_token)
        print("Current Telegram webhook:")
        for k, v in info.get("result", {}).items():
            print(f"  {k}: {v}")
        return 0

    if args.delete:
        if args.dry_run:
            print("[DRY RUN] Would delete the Telegram webhook.")
            return 0
        result = delete_webhook(bot_token)
        print(f"deleteWebhook → {result}")
        return 0

    # Generate/rotate the shared secret.
    override = os.environ.get("TELEGRAM_WEBHOOK_SECRET_OVERRIDE")
    secret = override or secrets.token_urlsafe(32)
    if override:
        print(f"Using override secret: {mask(secret)}")
    else:
        print(f"Generated new secret: {mask(secret)}")

    if args.dry_run:
        print(f"[DRY RUN] Would push {SECRET_NAME} to Cloudflare and call setWebhook with url={args.worker_url}")
        return 0

    if not args.no_cloudflare:
        push_cloudflare_secret(SECRET_NAME, secret)
    else:
        print("Skipping Cloudflare secret push (--no-cloudflare).")
        print(f"You must set {SECRET_NAME}={mask(secret)} on Cloudflare yourself before Telegram requests will be accepted.")

    print(f"Calling Telegram setWebhook → {args.worker_url}")
    set_result = set_webhook(bot_token, args.worker_url, secret)
    print(f"setWebhook → {set_result}")

    info = get_webhook_info(bot_token)
    print("Resulting webhook info:")
    for k, v in info.get("result", {}).items():
        print(f"  {k}: {v}")

    print()
    print("Next steps:")
    print("  1. Set TELEGRAM_CHAT_ID_HIGH_PRIORITY and TELEGRAM_CHAT_ID_REGULAR on Cloudflare via wrangler secret put.")
    print("  2. Set TELEGRAM_AUTHORIZED_USERS to comma-separated user IDs for Alex + Simon.")
    print("  3. From Telegram, message the bot /status — it should reply with last-7-day metrics.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
