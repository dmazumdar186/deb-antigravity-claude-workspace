"""
description: Create (draft), fill and tag the DM_Recruitment Candidate Outreach campaigns in Instantly from the recruiter_leads.py CSVs. Default prints the plan only (no API call); --apply writes drafts; --apply --activate also starts them.
inputs: .tmp/recruiters/campaigns/*.csv (+ catchall/); execution/lead_sourcing/recruiter_campaign/copy.json (operator-approved copy; required for --apply); env INSTANTLY_API_KEY (only with --apply); flags --apply, --activate, --only, --skip-catchall, --min-total
outputs: stdout plan (default); with --apply: Instantly campaigns + .tmp/recruiters/launch_state.json
usage:
    python3 execution/lead_sourcing/recruiter_campaign/launch.py                     # plan only, no network
    python3 execution/lead_sourcing/recruiter_campaign/launch.py --apply             # drafts + leads + tag
    python3 execution/lead_sourcing/recruiter_campaign/launch.py --apply --activate
Directive: directives/lead_sourcing/recruiter_campaign.md

copy.json shape: {"subjects": [...], "step1_personalized": "...", "step1_nopersonalization": "...",
                  "step2": "...", "step3": "..."}  (paragraphs separated by blank lines; {{specialty}} is available
                  in personalized step 1; spintax {{RANDOM|a|b}} on every line)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")
API = "https://api.instantly.ai/api/v2"
TAG = "cebb93b4-b98d-4948-bd99-43b0495fa93f"  # Deb_Oct 6 26 (same 12 inboxes as the 2 Nov campaigns)
SRC = ROOT / ".tmp/recruiters/campaigns"
STATE = ROOT / ".tmp/recruiters/launch_state.json"
COPY_PATH = Path(__file__).with_name("copy.json")
DATE = "10 Nov 2026"
LOC_LABEL = {"NewYork": "New York", "NewJersey": "New Jersey", "Boston": "Boston", "Houston": "Houston"}
# Each location sends 09:00-13:00 in its own office hours (operator 2026-11-10). Instantly's timezone enum has no
# America/New_York; America/Detroit is the same Eastern clock (incl. DST).
SCHED = {"NewYork": ("09:00", "13:00", "America/Detroit"), "NewJersey": ("09:00", "13:00", "America/Detroit"),
         "Boston": ("09:00", "13:00", "America/Detroit"), "Houston": ("09:00", "13:00", "America/Chicago")}


def req(method: str, path: str, **kw):
    key = os.environ.get("INSTANTLY_API_KEY", "").strip()
    if not key:
        sys.exit("INSTANTLY_API_KEY not set (needed only with --apply)")
    for a in range(4):
        try:
            r = requests.request(method, API + path, headers={"Authorization": "Bearer " + key}, timeout=60, **kw)
        except requests.RequestException as exc:
            print(f"network error on {path}: {exc.__class__.__name__}; retrying", file=sys.stderr)
            time.sleep(2 ** a * 2)
            continue
        if r.status_code == 429:
            time.sleep(2 ** a * 2)
            continue
        if r.status_code >= 400:
            raise RuntimeError(f"{method} {path} {r.status_code} {r.text[:400]}")
        return r.json() if r.text else {}
    raise RuntimeError(f"{method} {path}: gave up after retries")


SPIN = re.compile(r"\{\{RANDOM\s*\|((?:[^{}]|\{\{[a-zA-Z_]+\}\})*)\}\}")


def tidy(t: str) -> str:
    return SPIN.sub(lambda m: "{{RANDOM|" + "|".join(o.strip() for o in m.group(1).split("|")) + "}}", t)


def html(t: str) -> str:
    return "".join(f"<div>{p}</div><div><br /></div>" for p in tidy(t).split("\n\n")).removesuffix("<div><br /></div>")


def plan() -> list[dict]:
    out = []
    for f in sorted(SRC.glob("Recruitment_*.csv")) + sorted((SRC / "catchall").glob("Recruitment_*.csv")):
        _, loc, pers, *rest = f.stem.split("_")
        ca = bool(rest)
        # Operator 2026-11-10: one campaign per location x personalization (both segments, same copy).
        name = f"DM_Recruitment - {LOC_LABEL[loc]} - {pers}{' CatchAll' if ca else ''} - {DATE}"
        out.append(dict(file=f, name=name, pers=pers, catchall=ca, loc=loc))
    return out


def payload(p: dict, copy: dict) -> dict:
    c = copy
    s1 = c["step1_personalized" if p["pers"] == "Personalized" else "step1_nopersonalization"]
    fr, to, tz = SCHED[p["loc"]]
    steps = [{"type": "email", "delay": 2, "delay_unit": "days",
              "variants": [{"subject": tidy(s), "body": html(s1)} for s in c["subjects"]]},
             {"type": "email", "delay": 2, "delay_unit": "days", "variants": [{"subject": "", "body": html(c["step2"])}]},
             {"type": "email", "delay": 1, "delay_unit": "days", "variants": [{"subject": "", "body": html(c["step3"])}]}]
    return {"name": p["name"], "sequences": [{"steps": steps}],
            "campaign_schedule": {"schedules": [{"name": f"{LOC_LABEL[p['loc']]} office hours", "timing": {"from": fr, "to": to},
                                                 "days": {"0": False, "1": True, "2": True, "3": True, "4": True,
                                                          "5": True, "6": False}, "timezone": tz}]},
            "email_tag_list": [TAG], "daily_limit": 30, "text_only": True, "first_email_text_only": True,
            "open_tracking": False, "link_tracking": False, "stop_on_reply": True, "stop_on_auto_reply": False,
            "prioritize_new_leads": True, "insert_unsubscribe_header": True, "match_lead_esp": True,
            "stop_for_company": True, "allow_risky_contacts": False, "disable_bounce_protect": False}


def unguard(v: str) -> str:
    return v[1:] if isinstance(v, str) and len(v) > 1 and v[0] == "'" and v[1] in "=+-@\t\r" else v


def leads(f: Path) -> list[dict]:
    with open(f, encoding="utf-8", newline="") as fh:
        rows = [{k: unguard(v) for k, v in r.items()} for r in csv.DictReader(fh)]
    return [{"email": r["email"], "first_name": r["first_name"], "last_name": r["last_name"],
             "company_name": r["company_name"], "website": r["website"],
             "custom_variables": {"specialty": r["specialty"], "title": r["title"], "city": r["city"],
                                  "location": r["location"], "segment": r["segment"]}} for r in rows]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="DM_Recruitment Instantly launcher (plan-only by default)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--activate", action="store_true", help="also start campaigns; requires --apply")
    ap.add_argument("--only", default="", help="substring filter on campaign name")
    ap.add_argument("--skip-catchall", action="store_true", help="leave the CatchAll campaigns out of this run")
    ap.add_argument("--min-total", type=int, default=3000,
                    help="launch gate: Reoon-safe main leads across all locations must reach this (operator 2026-11-10)")
    a = ap.parse_args(argv)
    if a.activate and not a.apply:
        ap.error("--activate requires --apply")
    st = json.loads(STATE.read_text()) if STATE.exists() else {}
    plans = [p for p in plan() if a.only in p["name"] and not (a.skip_catchall and p["catchall"])]
    copy = json.loads(COPY_PATH.read_text()) if COPY_PATH.exists() else None
    if not a.apply:
        total = sum(len(leads(p["file"])) for p in plans if not p["catchall"])
        print(f"main leads total {total} (gate {a.min_total}: {'OK' if total >= a.min_total else 'BLOCKED'})")
        print("PLAN ONLY (no Instantly calls)." + ("" if copy else " copy.json missing: copy not approved yet."))
        for p in plans:
            rec = st.get(p["name"], {})
            new = len([x for x in leads(p["file"]) if x["email"].lower() not in set(rec.get("sent_emails", []))])
            print(f"{p['name']} | {p['file'].name} | leads={len(leads(p['file']))} new={new} | "
                  f"{'active' if rec.get('active') else 'created' if 'id' in rec else 'todo'}")
        return
    if not copy:
        sys.exit("copy.json missing: write the operator-approved copy first")
    if not copy.get("approved"):
        sys.exit("copy.json not operator-approved; rebuild with build_copy.py --angle H --approved after sign-off")
    main_total = sum(len(leads(p["file"])) for p in plan() if not p["catchall"])
    if main_total < a.min_total:
        sys.exit(f"launch gate: {main_total} main leads < --min-total {a.min_total}; source more before launching")
    for p in plans:
        rec = st.setdefault(p["name"], {})
        if "id" not in rec:
            # Guard against a duplicate draft when a retried POST already succeeded server-side.
            found = [c for c in req("GET", "/campaigns", params={"search": p["name"], "limit": 100}).get("items", [])
                     if c.get("name") == p["name"]]
            rec["id"] = found[0]["id"] if found else req("POST", "/campaigns", json=payload(p, copy))["id"]
            STATE.write_text(json.dumps(st, indent=1))
        # Incremental (operator 2026-11-10: start now, add leads later): only emails not yet sent to this campaign
        # are uploaded; a re-run after a rebuild tops the running campaign up. skip_if_in_workspace still dedupes.
        L = leads(p["file"])
        done = set(rec.get("sent_emails", []))
        new = [x for x in L if x["email"].lower() not in done]
        if new:
            res = {}
            for i in range(0, len(new), 500):
                r = req("POST", "/leads/add", json={"campaign_id": rec["id"], "skip_if_in_workspace": True,
                                                     "leads": new[i:i + 500]})
                for k in ("leads_uploaded", "skipped_count", "in_blocklist", "duplicated_leads", "invalid_email_count"):
                    res[k] = res.get(k, 0) + int(r.get(k) or 0)
                done.update(x["email"].lower() for x in new[i:i + 500])
                rec["sent_emails"] = sorted(done)
                STATE.write_text(json.dumps(st, indent=1))
            prev = rec.get("uploaded", {})
            rec["uploaded"] = {k: prev.get(k, 0) + v for k, v in res.items()}
            rec["expected"] = len(done)
            STATE.write_text(json.dumps(st, indent=1))
            accounted = sum(res.values())
            if accounted < len(new):  # fail loud: a lead neither uploaded nor reported skipped/invalid
                sys.exit(f"{p['name']}: {len(new)} leads sent, only {accounted} accounted for: {res}")
        if "tagged" not in rec:
            req("POST", "/custom-tags/toggle-resource", json={"tag_ids": [TAG], "resource_ids": [rec["id"]],
                                                              "resource_type": 2, "assign": True})
            rec["tagged"] = True
            STATE.write_text(json.dumps(st, indent=1))
        if a.activate and not rec.get("active"):
            req("POST", f"/campaigns/{rec['id']}/activate")
            rec["active"] = True
            STATE.write_text(json.dumps(st, indent=1))
        print(p["name"], rec.get("expected"), rec.get("uploaded"), "active" if rec.get("active") else "draft")


if __name__ == "__main__":
    main()
