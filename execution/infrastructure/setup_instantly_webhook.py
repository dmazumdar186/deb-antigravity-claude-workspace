#!/usr/bin/env python3
"""
setup_instantly_webhook.py
description: Provision/rotate Instantly v2 webhook + Cloudflare INSTANTLY_WEBHOOK_SECRET so reply_received events POST to the worker with X-Webhook-Secret auth.
inputs: env: INSTANTLY_API_KEY (.env), optional INSTANTLY_WEBHOOK_SECRET_OVERRIDE; CLI: --list, --dry-run, --worker-url, --no-cloudflare
outputs: Writes Cloudflare secret via `npx wrangler secret put`; calls Instantly v2 webhooks API (list/delete/create); prints masked secret + new webhook id.
usage:
    py execution/infrastructure/setup_instantly_webhook.py --list
    py execution/infrastructure/setup_instantly_webhook.py --dry-run
    py execution/infrastructure/setup_instantly_webhook.py
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
DEFAULT_WORKER_URL = "https://accessory-masters-api.accessory-masters.workers.dev/api/webhook/reply"
INSTANTLY_API_BASE = "https://api.instantly.ai/api/v2"
EVENT_TYPE = "reply_received"
WEBHOOK_NAME = "accessory-masters reply webhook"
SECRET_NAME = "INSTANTLY_WEBHOOK_SECRET"
HEADER_NAME = "X-Webhook-Secret"


def mask(value: str) -> str:
    if not value or len(value) < 4:
        return "****"
    return f"****{value[-4:]}"


def list_webhooks(api_key: str) -> list[dict]:
    items: list[dict] = []
    cursor: str | None = None
    for _ in range(10):
        params = {"limit": 100}
        if cursor:
            params["starting_after"] = cursor
        r = requests.get(
            f"{INSTANTLY_API_BASE}/webhooks",
            headers={"Authorization": f"Bearer {api_key}"},
            params=params,
            timeout=30,
        )
        if not r.ok:
            raise RuntimeError(f"Instantly list webhooks failed: {r.status_code} {r.text[:300]}")
        data = r.json()
        items.extend(data.get("items") or [])
        cursor = data.get("next_starting_after")
        if not cursor:
            break
    return items


def delete_webhook(api_key: str, webhook_id: str) -> None:
    r = requests.delete(
        f"{INSTANTLY_API_BASE}/webhooks/{webhook_id}",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    if not r.ok:
        raise RuntimeError(f"Instantly delete webhook {webhook_id} failed: {r.status_code} {r.text[:300]}")


def create_webhook(api_key: str, target_url: str, secret: str) -> dict:
    body = {
        "target_hook_url": target_url,
        "event_type": EVENT_TYPE,
        "headers": {HEADER_NAME: secret},
        "name": WEBHOOK_NAME,
    }
    r = requests.post(
        f"{INSTANTLY_API_BASE}/webhooks",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=30,
    )
    if not r.ok:
        raise RuntimeError(f"Instantly create webhook failed: {r.status_code} {r.text[:600]}")
    return r.json()


def push_cloudflare_secret(value: str) -> None:
    if not WRANGLER_DIR.exists():
        raise RuntimeError(f"wrangler dir not found: {WRANGLER_DIR}")
    proc = subprocess.run(
        ["npx", "wrangler", "secret", "put", SECRET_NAME],
        cwd=str(WRANGLER_DIR),
        input=value + "\n",
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        shell=(sys.platform == "win32"),
    )
    if proc.returncode != 0:
        raise RuntimeError(f"wrangler secret put failed:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}")
    print(f"  cloudflare: set {SECRET_NAME} ({mask(value)})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure Instantly webhook + Cloudflare secret.")
    parser.add_argument("--list", action="store_true", help="List existing Instantly webhooks and exit.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without making changes.")
    parser.add_argument("--worker-url", default=DEFAULT_WORKER_URL, help="Worker URL receiving reply_received events.")
    parser.add_argument("--no-cloudflare", action="store_true", help="Skip the wrangler secret put step (Instantly-only).")
    args = parser.parse_args()

    api_key = os.environ.get("INSTANTLY_API_KEY")
    if not api_key:
        print("ERROR: INSTANTLY_API_KEY not set in .env", file=sys.stderr)
        return 1

    if args.list:
        try:
            webhooks = list_webhooks(api_key)
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        print(f"Found {len(webhooks)} webhook(s):")
        for w in webhooks:
            print(f"  - id={w.get('id')} event={w.get('event_type')} url={w.get('target_hook_url')}")
        return 0

    override = os.environ.get("INSTANTLY_WEBHOOK_SECRET_OVERRIDE")
    secret = override if override else secrets.token_urlsafe(32)
    source = "override" if override else "generated"
    print(f"Secret: {mask(secret)} ({source})")
    print(f"Worker URL: {args.worker_url}")

    if args.dry_run:
        print("DRY RUN — no changes made.")
        return 0

    try:
        existing = list_webhooks(api_key)
    except Exception as e:
        print(f"ERROR listing webhooks: {e}", file=sys.stderr)
        return 1

    target_path = args.worker_url.rstrip("/")
    to_delete = [w for w in existing if (w.get("target_hook_url") or "").rstrip("/") == target_path]
    print(f"Existing webhooks pointing at this URL: {len(to_delete)}")
    for w in to_delete:
        wid = w.get("id")
        try:
            delete_webhook(api_key, wid)
            print(f"  deleted webhook {wid}")
        except Exception as e:
            print(f"  WARN: could not delete {wid}: {e}", file=sys.stderr)

    if not args.no_cloudflare:
        try:
            push_cloudflare_secret(secret)
        except Exception as e:
            print(f"ERROR setting Cloudflare secret: {e}", file=sys.stderr)
            print("ABORTING — would leave Instantly pointed at a worker that rejects all calls.", file=sys.stderr)
            return 1

    try:
        created = create_webhook(api_key, args.worker_url, secret)
    except Exception as e:
        print(f"ERROR creating Instantly webhook: {e}", file=sys.stderr)
        return 1

    print(f"  instantly: created webhook id={created.get('id')} event={created.get('event_type')}")
    print("Done. Secret (last 4):", mask(secret))
    return 0


if __name__ == "__main__":
    sys.exit(main())
