"""
description: Free Instantly lead slots by deleting leads that FINISHED their sequence, only in campaigns tagged Deb*/Debanjan (never any other campaign), after a full CSV backup. Default is a dry run (no deletes).
inputs: env INSTANTLY_API_KEY; flags --apply (perform deletes), --max N (hard cap on leads deleted per run, required with --apply),
        --exclude REGEX (campaign names to skip; default skips the 2 Nov and 10 Nov 2026 campaigns being measured),
        --tags (comma list of tag-label prefixes; default "Deb")
outputs: .tmp/instantly_prune/backup_<ts>.csv (every candidate lead, all fields, written BEFORE any delete),
         .tmp/instantly_prune/ledger.jsonl (one row per run), stdout per-campaign counts
usage:
    python3 execution/lead_sourcing/instantly_prune_finished.py                    # dry run: counts + backup only
    python3 execution/lead_sourcing/instantly_prune_finished.py --apply --max 3000
Directive: directives/lead_sourcing/instantly_prune_finished.md

Safety rules (operator 2026-11-10: "just from campaigns under Deb or Debanjan, nothing else, never touch other campaigns"):
- A campaign is in scope only if a Deb*/Debanjan custom tag is assigned to the campaign itself (tag mapping, resource_type 2).
- A lead is deleted only if: it belongs to an in-scope campaign (re-checked on the lead record), status == 3 (completed),
  email_reply_count == 0, and no interest status set. Repliers, interested, unsubscribed, bounced and active leads stay.
- Deletes use DELETE /leads with campaign_id + explicit ids + status 3, so the API itself cannot widen the scope.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
from execution.modules.pipeline_utils import csv_safe_row  # noqa: E402

API = "https://api.instantly.ai/api/v2"
OUT = ROOT / ".tmp" / "instantly_prune"
DEFAULT_EXCLUDE = r"2 Nov 2026|10 Nov 2026"


def req(method: str, path: str, **kw):
    key = os.environ.get("INSTANTLY_API_KEY", "").strip()
    if not key:
        sys.exit("INSTANTLY_API_KEY not set")
    for a in range(5):
        try:
            r = requests.request(method, API + path, headers={"Authorization": "Bearer " + key}, timeout=90, **kw)
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
    raise RuntimeError(f"{method} {path}: gave up after retries")


def paged(path: str, params: dict | None = None) -> list[dict]:
    out, after = [], None
    while True:
        p = dict(params or {}, limit=100)
        if after:
            p["starting_after"] = after
        j = req("GET", path, params=p)
        out += j.get("items", [])
        after = j.get("next_starting_after")
        if not after:
            return out


def scoped_campaigns(prefixes: list[str], exclude: str) -> dict[str, dict]:
    tags = {t["id"]: t["label"] for t in paged("/custom-tags")}
    mine = {i: l for i, l in tags.items() if any(l.startswith(p) for p in prefixes)}
    camp_tags: dict[str, set[str]] = {}
    for m in paged("/custom-tag-mappings"):
        if m.get("tag_id") in mine and m.get("resource_type") == 2:
            camp_tags.setdefault(m["resource_id"], set()).add(mine[m["tag_id"]])
    names = {c["id"]: c["name"] for c in paged("/campaigns")}
    return {cid: {"name": names.get(cid, "?"), "tags": sorted(t), "excluded": bool(re.search(exclude, names.get(cid, "")))}
            for cid, t in camp_tags.items() if cid in names}


def finished_leads(cid: str) -> list[dict]:
    out, after = [], None
    while True:
        body = {"campaign": cid, "filter": "FILTER_VAL_COMPLETED", "limit": 100}
        if after:
            body["starting_after"] = after
        j = req("POST", "/leads/list", json=body)
        out += j.get("items", [])
        after = j.get("next_starting_after")
        if not after:
            return out


def deletable(lead: dict, cid: str) -> bool:
    return (lead.get("campaign") == cid and lead.get("status") == 3 and not lead.get("email_reply_count")
            and lead.get("lt_interest_status") in (None, ""))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Delete finished, never-replied leads in Deb-tagged campaigns (dry run default)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--max", type=int, default=0, help="hard cap on deletes this run (required with --apply)")
    ap.add_argument("--exclude", default=DEFAULT_EXCLUDE)
    ap.add_argument("--tags", default="Deb")
    a = ap.parse_args(argv)
    if a.apply and a.max <= 0:
        ap.error("--apply needs --max N")
    OUT.mkdir(parents=True, exist_ok=True)
    camps = scoped_campaigns([p.strip() for p in a.tags.split(",") if p.strip()], a.exclude)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    plan, backup = [], []
    for cid, c in sorted(camps.items(), key=lambda kv: kv[1]["name"]):
        if c["excluded"]:
            print(f"skip (excluded) {c['name']}")
            continue
        leads = finished_leads(cid)
        ok = [l for l in leads if deletable(l, cid)]
        print(f"{len(ok):5d} deletable / {len(leads):5d} finished | {c['name']} [{','.join(c['tags'])}]")
        if ok:
            plan.append((cid, c["name"], [l["id"] for l in ok]))
            backup += [dict(l, campaign_name=c["name"]) for l in ok]
    total = sum(len(ids) for *_, ids in plan)
    bpath = OUT / f"backup_{ts}.csv"
    if backup:
        cols = sorted({k for l in backup for k in l})
        with open(bpath, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for l in backup:
                w.writerow(csv_safe_row({k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in l.items()}))
    print(f"in-scope campaigns {len(camps)} | deletable leads {total} | backup {bpath.relative_to(ROOT) if backup else '-'}")
    deleted = 0
    if a.apply:
        budget = a.max
        for cid, name, ids in plan:
            for i in range(0, len(ids), 50):  # the bulk DELETE removes at most 50 leads per call (2026-11-10)
                chunk = ids[i:i + 50][:budget]
                if not chunk:
                    break
                n = int(req("DELETE", "/leads", json={"campaign_id": cid, "ids": chunk, "status": 3}).get("count") or 0)
                deleted += n
                budget -= len(chunk)
                if n != len(chunk):
                    print(f"WARN {name}: asked {len(chunk)}, deleted {n}", file=sys.stderr)
            if budget <= 0:
                break
        print(f"deleted {deleted} leads (cap {a.max})")
    with open(OUT / "ledger.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": ts, "apply": a.apply, "campaigns": len(camps), "deletable": total, "deleted": deleted,
                             "backup": str(bpath.relative_to(ROOT)) if backup else ""}) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
