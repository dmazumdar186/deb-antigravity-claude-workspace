"""
description: Continue the 2 Nov 2026 DM_ EventAV/Fitout/DMC campaigns on the new GTM-pipeline copy: create one 10 Nov 2026 campaign per source campaign that still has NOT-contacted leads, move those leads across (no new lead slots used), tag, and optionally activate. Leads already mid-sequence stay in the 2 Nov campaign and finish the old sequence. Default prints the plan only.
inputs: execution/lead_sourcing/prodcraft_campaign/copy_gtm.json (approved=True required for --apply); env INSTANTLY_API_KEY; flags --apply, --activate (requires --apply), --only SUBSTR
outputs: stdout plan; with --apply: Instantly campaigns + lead moves; state .tmp/gtm_campaign/launch_state.json
usage:
    python3 execution/lead_sourcing/prodcraft_campaign/launch_gtm.py                 # plan only
    python3 execution/lead_sourcing/prodcraft_campaign/launch_gtm.py --apply          # drafts + move leads + tag
    python3 execution/lead_sourcing/prodcraft_campaign/launch_gtm.py --apply --activate
Directive: directives/lead_sourcing/prodcraft_campaign.md (section "GTM v3")
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
from execution.lead_sourcing.recruiter_campaign.launch import html, tidy  # noqa: E402

API = "https://api.instantly.ai/api/v2"
TAG = "cebb93b4-b98d-4948-bd99-43b0495fa93f"  # Deb_Oct 6 26 (same inboxes as the 2 Nov campaigns)
COPY = Path(__file__).with_name("copy_gtm.json")
STATE = ROOT / ".tmp/gtm_campaign/launch_state.json"
SRC_RE = re.compile(r"^DM_(EventAV|Fitout|DMC) - (US|UK) - (Personalized|NoPersonalization) - 2 Nov 2026$")
NEW_DATE = "10 Nov 2026"
# Same windows as the 2 Nov v2 settings: US 09:00-13:00 Chicago, UK 08:00-12:00 Isle_of_Man (= London clock;
# Instantly's enum has no Europe/London).
SCHED = {"US": ("09:00", "13:00", "America/Chicago"), "UK": ("08:00", "12:00", "Europe/Isle_of_Man")}


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


def sources() -> list[dict]:
    items, after = [], None
    while True:
        p = {"limit": 100, "search": "2 Nov 2026"}
        if after:
            p["starting_after"] = after
        j = req("GET", "/campaigns", params=p)
        items += j.get("items", [])
        after = j.get("next_starting_after")
        if not after:
            break
    src = [c for c in items if SRC_RE.match(c["name"])]
    an = {x["campaign_id"]: x for x in req("GET", "/campaigns/analytics", params={"ids": [c["id"] for c in src]})} if src else {}
    out = []
    for c in src:
        niche, country, pers = SRC_RE.match(c["name"]).groups()
        a = an.get(c["id"], {})
        untouched = max(0, int(a.get("leads_count") or 0) - int(a.get("contacted_count") or 0))
        out.append(dict(src_id=c["id"], src_name=c["name"], src_status=c["status"], niche=niche, country=country,
                        pers=pers, untouched=untouched, name=f"DM_{niche} - {country} - {pers} - {NEW_DATE}"))
    return sorted(out, key=lambda x: x["name"])


def payload(p: dict, copy: dict) -> dict:
    c = copy[p["niche"]]
    s1 = c["step1_personalized" if p["pers"] == "Personalized" else "step1_nopersonalization"]
    fr, to, tz = SCHED[p["country"]]
    steps = [{"type": "email", "delay": 2, "delay_unit": "days",
              "variants": [{"subject": tidy(s), "body": html(s1)} for s in c["subjects"]]},
             {"type": "email", "delay": 2, "delay_unit": "days", "variants": [{"subject": "", "body": html(c["step2"])}]},
             {"type": "email", "delay": 1, "delay_unit": "days", "variants": [{"subject": "", "body": html(c["step3"])}]}]
    return {"name": p["name"], "sequences": [{"steps": steps}],
            "campaign_schedule": {"schedules": [{"name": f"{p['country']} office hours", "timing": {"from": fr, "to": to},
                                                 "days": {"0": False, "1": True, "2": True, "3": True, "4": True,
                                                          "5": True, "6": False}, "timezone": tz}]},
            "email_tag_list": [TAG], "daily_limit": 30, "text_only": True, "first_email_text_only": True,
            "open_tracking": False, "link_tracking": False, "stop_on_reply": True, "stop_on_auto_reply": False,
            "prioritize_new_leads": True, "insert_unsubscribe_header": True, "match_lead_esp": True,
            "stop_for_company": True, "allow_risky_contacts": False, "disable_bounce_protect": False}


def wait_job(job_id: str) -> dict:
    for _ in range(120):
        j = req("GET", f"/background-jobs/{job_id}")
        if j.get("status") in ("success", "completed", "failed", "error"):
            return j
        time.sleep(5)
    return {"status": "timeout", "id": job_id}


def campaign_leads(cid: str) -> list[dict]:
    out, after = [], None
    while True:
        body = {"campaign": cid, "limit": 100}
        if after:
            body["starting_after"] = after
        j = req("POST", "/leads/list", json=body)
        out += j.get("items", [])
        after = j.get("next_starting_after")
        if not after:
            return out


def was_contacted(lead: dict) -> bool:
    return bool(lead.get("timestamp_last_contact") or lead.get("last_step_id") or lead.get("email_reply_count")
                or lead.get("status") not in (1, None))


def audit(st: dict, fix: bool) -> int:
    """Leads in the new 10 Nov campaigns that were already emailed by the 2 Nov campaign (2026-11-10: the
    NOT_CONTACTED move filter let some through). --fix-contacted moves them back so nobody gets two first emails."""
    bad_total = 0
    for name, rec in st.items():
        leads = campaign_leads(rec["id"])
        bad = [l for l in leads if was_contacted(l)]
        bad_total += len(bad)
        src = campaign_leads(rec["src_id"])
        src_fresh = sum(1 for l in src if not was_contacted(l))
        print(f"{name}: {len(leads)} leads, {len(bad)} already contacted | source keeps {len(src)}, "
              f"{src_fresh} never contacted")
        if fix and bad:
            job = req("POST", "/leads/move", json={"campaign": rec["id"], "ids": [l["id"] for l in bad],
                                                    "to_campaign_id": rec["src_id"]})
            res = wait_job(job.get("id", "")) if job.get("id") else job
            print(f"  moved back {len(bad)} -> source: {res.get('status')}")
    return bad_total


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Continue 2 Nov EventAV/Fitout/DMC campaigns on GTM copy (plan-only default)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--activate", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--audit", action="store_true", help="list already-contacted leads in the new campaigns")
    ap.add_argument("--fix-contacted", action="store_true", help="move already-contacted leads back to the source")
    a = ap.parse_args(argv)
    if a.activate and not a.apply:
        ap.error("--activate requires --apply")
    copy = json.loads(COPY.read_text())
    st = json.loads(STATE.read_text()) if STATE.exists() else {}
    if a.audit or a.fix_contacted:
        n_bad = audit(st, a.fix_contacted)
        print(f"already-contacted leads in new campaigns: {n_bad}")
        return
    if a.activate and audit(st, False):
        sys.exit("refusing to activate: run --fix-contacted first")
    plans = [p for p in sources() if p["untouched"] > 0 and a.only in p["name"]]
    if not a.apply:
        print(f"PLAN ONLY. copy approved={copy.get('approved')}")
        for p in plans:
            rec = st.get(p["name"], {})
            print(f"{p['name']} <- {p['src_name']} (status {p['src_status']}) | move {p['untouched']} not-contacted leads | "
                  f"{'active' if rec.get('active') else 'moved' if rec.get('moved') else 'created' if 'id' in rec else 'todo'}")
        print(f"total leads to move: {sum(p['untouched'] for p in plans)}")
        return
    if not copy.get("approved"):
        sys.exit("copy_gtm.json not approved; rebuild with build_copy_gtm.py --approved after sign-off + red-team PASS")
    STATE.parent.mkdir(parents=True, exist_ok=True)
    for p in plans:
        rec = st.setdefault(p["name"], {"src_id": p["src_id"]})
        if "id" not in rec:
            found = [c for c in req("GET", "/campaigns", params={"search": p["name"], "limit": 100}).get("items", [])
                     if c.get("name") == p["name"]]
            rec["id"] = found[0]["id"] if found else req("POST", "/campaigns", json=payload(p, copy))["id"]
            STATE.write_text(json.dumps(st, indent=1))
        if not rec.get("tagged"):
            req("POST", "/custom-tags/toggle-resource", json={"tag_ids": [TAG], "resource_ids": [rec["id"]],
                                                              "resource_type": 2, "assign": True})
            rec["tagged"] = True
            STATE.write_text(json.dumps(st, indent=1))
        if not rec.get("moved"):
            job = req("POST", "/leads/move", json={"campaign": p["src_id"], "filter": "FILTER_VAL_NOT_CONTACTED",
                                                    "to_campaign_id": rec["id"], "check_duplicates": True,
                                                    "skip_invalid_emails": True})
            res = wait_job(job.get("id", "")) if job.get("id") else job
            rec.update(moved=res.get("status") in ("success", "completed"), move_job=res)
            STATE.write_text(json.dumps(st, indent=1))
            if not rec["moved"]:
                sys.exit(f"{p['name']}: lead move did not complete: {json.dumps(res)[:300]}")
        if a.activate and not rec.get("active"):
            req("POST", f"/campaigns/{rec['id']}/activate")
            rec["active"] = True
            STATE.write_text(json.dumps(st, indent=1))
        print(p["name"], "moved" if rec.get("moved") else "-", "active" if rec.get("active") else "draft")


if __name__ == "__main__":
    main()
