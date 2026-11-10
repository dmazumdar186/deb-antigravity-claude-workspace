"""
description: Restore leads deleted by instantly_prune_finished.py into a lead LIST (never a campaign), so they count as "in workspace" again and no campaign emails them. Selects from the prune backup CSVs; default dry run.
inputs: env INSTANTLY_API_KEY; --only-never-contacted (default on: leads with no timestamp_last_contact, i.e. the 7 stop_for_company leads deleted on 2026-11-10); --list-name; --apply
outputs: stdout selection; with --apply: an Instantly lead list (created once, id cached in .tmp/instantly_prune/restore_state.json) and the leads added to it
usage:
    python3 execution/lead_sourcing/instantly_restore_leads.py              # dry run
    python3 execution/lead_sourcing/instantly_restore_leads.py --apply
Directive: directives/lead_sourcing/instantly_prune_finished.md
"""
from __future__ import annotations

import argparse
import csv
import glob
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
OUT = ROOT / ".tmp" / "instantly_prune"
STATE = OUT / "restore_state.json"


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


def unguard(v: str) -> str:
    return v[1:] if isinstance(v, str) and len(v) > 1 and v[0] == "'" and v[1] in "=+-@\t\r" else v


def main() -> int:
    ap = argparse.ArgumentParser(description="Restore pruned leads into a lead list (dry run default)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--list-name", default="Restored - stopped for company (do not contact)")
    a = ap.parse_args()
    leads: dict[str, dict] = {}
    for f in sorted(glob.glob(str(OUT / "backup_*.csv"))):
        with open(f, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                leads[r["id"]] = {k: unguard(v) for k, v in r.items()}
    sel = [r for r in leads.values() if not r.get("timestamp_last_contact")]
    for r in sel:
        print(f"{r['email']} | {r.get('company_name', '')} | from {r.get('campaign_name')} | {r.get('status_summary')}")
    print(f"selected {len(sel)} never-contacted leads (of {len(leads)} backed up)")
    if not a.apply or not sel:
        return 0
    st = json.loads(STATE.read_text()) if STATE.exists() else {}
    if "list_id" not in st:
        found = [x for x in req("GET", "/lead-lists", params={"limit": 100}).get("items", []) if x.get("name") == a.list_name]
        st["list_id"] = found[0]["id"] if found else req("POST", "/lead-lists", json={"name": a.list_name})["id"]
        STATE.write_text(json.dumps(st, indent=1))
    payload = [{"email": r["email"], "first_name": r.get("first_name", ""), "last_name": r.get("last_name", ""),
                "company_name": r.get("company_name", ""), "website": r.get("website", ""),
                "custom_variables": {"restored_from": r.get("campaign_name", ""), "restored_reason": "stop_for_company"}}
               for r in sel]
    res = req("POST", "/leads/add", json={"list_id": st["list_id"], "leads": payload, "skip_if_in_workspace": True})
    print({k: res.get(k) for k in ("leads_uploaded", "skipped_count", "in_blocklist", "duplicated_leads", "invalid_email_count")})
    st["restored"] = sorted(set(st.get("restored", [])) | {r["email"] for r in sel})
    STATE.write_text(json.dumps(st, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
