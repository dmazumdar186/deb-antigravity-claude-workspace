"""
description: Move named Instantly campaigns to another tag: set the sending-inbox tag (email_tag_list) to exactly that tag and swap the campaign tag, then read back. Default is a dry run.
inputs: env INSTANTLY_API_KEY; --to-tag LABEL; --from-tag LABEL (campaign tag to unassign); --state FILE... (launch_state.json files whose campaign ids to retag); --apply
outputs: stdout before/after per campaign; Instantly PATCH /campaigns/{id} and /custom-tags/toggle-resource with --apply
usage:
    python3 execution/lead_sourcing/instantly_retag_campaigns.py --to-tag "Deb_16 Oct 26" --from-tag "Deb_Oct 6 26" \
        --state .tmp/recruiters/launch_state.json .tmp/gtm_campaign/launch_state.json [--apply]
Directive: directives/lead_sourcing/recruiter_campaign.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
API = "https://api.instantly.ai/api/v2"


def req(method: str, path: str, **kw):
    key = os.environ.get("INSTANTLY_API_KEY", "").strip()
    if not key:
        sys.exit("INSTANTLY_API_KEY not set")
    for a in range(5):
        try:
            r = requests.request(method, API + path, headers={"Authorization": "Bearer " + key}, timeout=60, **kw)
        except requests.RequestException as exc:
            print(f"network error {path}: {exc.__class__.__name__}; retry", file=sys.stderr)
            time.sleep(2 ** a)
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 ** a * 2)
            continue
        if r.status_code >= 400:
            raise RuntimeError(f"{method} {path} {r.status_code} {r.text[:300]}")
        return r.json() if r.text else {}
    raise RuntimeError(f"{method} {path}: gave up")


def main() -> int:
    ap = argparse.ArgumentParser(description="Retag campaigns (sending-inbox tag + campaign tag); dry run default")
    ap.add_argument("--to-tag", required=True)
    ap.add_argument("--from-tag", required=True)
    ap.add_argument("--state", nargs="+", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    tags = {t["label"]: t["id"] for t in req("GET", "/custom-tags", params={"limit": 100}).get("items", [])}
    if a.to_tag not in tags or a.from_tag not in tags:
        sys.exit(f"unknown tag; have {sorted(tags)}")
    to_id, from_id = tags[a.to_tag], tags[a.from_tag]
    camps = {}
    for f in a.state:
        for name, rec in json.loads(Path(f).read_text()).items():
            camps[name] = rec["id"]
    for name, cid in sorted(camps.items()):
        c = req("GET", f"/campaigns/{cid}")
        before = c.get("email_tag_list")
        if a.apply:
            req("PATCH", f"/campaigns/{cid}", json={"email_tag_list": [to_id]})
            req("POST", "/custom-tags/toggle-resource", json={"tag_ids": [from_id], "resource_ids": [cid],
                                                              "resource_type": 2, "assign": False})
            req("POST", "/custom-tags/toggle-resource", json={"tag_ids": [to_id], "resource_ids": [cid],
                                                              "resource_type": 2, "assign": True})
            after = req("GET", f"/campaigns/{cid}").get("email_tag_list")
            ok = after == [to_id]
            print(f"{'OK ' if ok else 'BAD'} {name}: inbox tag {before} -> {after}")
            if not ok:
                return 1
        else:
            print(f"DRY {name}: inbox tag {before} -> [{to_id}] ({a.to_tag}); campaign tag {a.from_tag} -> {a.to_tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
