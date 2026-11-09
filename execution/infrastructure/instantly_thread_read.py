"""
instantly_thread_read.py
description: Read-only Instantly v2 lookup — find campaigns by name and dump every email (sent + received) for a lead/search term, so a reply can be read before drafting a response. GET only; never sends, replies or mutates.
inputs: --search <address term> and/or --campaign-id <id>, --received-only, --grep <local filter on name/body>, --campaign <name substring> (optional), --out <path> (default .tmp/instantly_threads/<search>.json). Env: INSTANTLY_API_KEY.
outputs: JSON file with matched campaigns + emails (oldest first); a plain-text thread printed to stdout.

See also: directives/infrastructure/instantly_thread_read.md
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
BASE = "https://api.instantly.ai/api/v2"
MAX_PAGES = 20          # ceiling: 20 pages x 100 = 2,000 items per list
EMAILS_GAP_S = 3.2      # /emails is limited to 20 req/min


def _get(path: str, key: str, params: dict) -> dict:
    for attempt in range(4):
        r = requests.get(f"{BASE}{path}", headers={"Authorization": f"Bearer {key}"},
                         params=params, timeout=30)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 ** (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()
    return {}


def _paginate(path: str, key: str, params: dict, gap: float = 0.0) -> list[dict]:
    items, after = [], None
    for _ in range(MAX_PAGES):
        p = dict(params, limit=100)
        if after:
            p["starting_after"] = after
        data = _get(path, key, p)
        items += data.get("items", []) or []
        after = data.get("next_starting_after")
        if not after:
            break
        time.sleep(gap)
    return items


def _text(e: dict) -> str:
    body = e.get("body") or {}
    if isinstance(body, str):
        return body
    t = body.get("text") or ""
    if not t and body.get("html"):
        t = re.sub(r"<br\s*/?>|</p>|</div>", "\n", body["html"], flags=re.I)
        t = html.unescape(re.sub(r"<[^>]+>", "", t))
    return t.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--search", default="", help="Instantly server-side search (matches addresses)")
    ap.add_argument("--campaign-id", default="", help="restrict /emails to one campaign id")
    ap.add_argument("--received-only", action="store_true", help="only replies we received")
    ap.add_argument("--grep", default="", help="local case-insensitive filter on name/address/body")
    ap.add_argument("--campaign", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    load_dotenv(ROOT / ".env")
    key = os.environ.get("INSTANTLY_API_KEY")
    if not key:
        print("INSTANTLY_API_KEY missing", file=sys.stderr)
        return 2

    camps = _paginate("/campaigns", key, {"search": a.campaign}) if a.campaign else []
    if not (a.search or a.campaign_id):
        print("need --search or --campaign-id", file=sys.stderr)
        return 2
    params: dict = {}
    if a.search:
        params["search"] = a.search
    if a.campaign_id:
        params["campaign_id"] = a.campaign_id
    if a.received_only:
        params["email_type"] = "received"
    emails = _paginate("/emails", key, params, gap=EMAILS_GAP_S)
    if a.grep:
        g = a.grep.lower()
        emails = [e for e in emails if g in json.dumps(e, ensure_ascii=False).lower()]
    if camps:
        ids = {c["id"] for c in camps}
        emails = [e for e in emails if e.get("campaign_id") in ids] or emails
    emails.sort(key=lambda e: e.get("timestamp_email") or e.get("timestamp_created") or "")

    out = Path(a.out) if a.out else ROOT / ".tmp" / "instantly_threads" / (
        re.sub(r"[^\w.-]+", "_", a.search or a.grep or a.campaign_id) + ".json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"campaigns": camps, "emails": emails}, indent=1), encoding="utf-8")

    for c in camps:
        print(f"CAMPAIGN {c.get('id')} | {c.get('name')} | status={c.get('status')}")
    print(f"{len(emails)} emails -> {out}")
    for e in emails:
        direction = "IN " if e.get("ue_type") == 2 or e.get("email_type") == "received" else "OUT"
        print("=" * 70)
        print(f"{direction} {e.get('timestamp_email')} | from {e.get('from_address_email')} "
              f"-> {e.get('to_address_email_list')} | step {e.get('step')} | {e.get('subject')}")
        print(_text(e)[:3000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
