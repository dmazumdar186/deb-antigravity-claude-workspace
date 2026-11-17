"""
description: Build Instantly campaigns from segment/tier lead CSVs and a copy JSON: filter, dedupe against the whole workspace, create or update DRAFT campaigns, upload leads, tag, read back. Plan by default; --apply writes drafts; --activate (with --apply --i-mean-it) starts them.
inputs: --campaigns <plan.json> (tag_id, timezone, window, allow_list, drop_list, leads_dir, state, contacted_window_days, campaigns[{name, id?, segment, tier, daily_limit, daily_max_leads}]); --copy <copy.json> ({"approved": bool, "segments"|"verticals": {seg: {"steps": [{subject, body, delay}]}}}); env INSTANTLY_API_KEY; flags --leads-dir, --tag, --apply, --activate, --i-mean-it, --check
outputs: stdout plan / read-back JSON; with --apply: Instantly draft campaigns + leads + campaign tag; state JSON at plan["state"]
usage:
    python3 execution/lead_sourcing/list_campaign_launch.py --campaigns P.json --copy C.json            # plan: filters + workspace dedupe, no writes
    python3 execution/lead_sourcing/list_campaign_launch.py --campaigns P.json --copy C.json --check    # read back campaigns + inboxes only
    python3 execution/lead_sourcing/list_campaign_launch.py --campaigns P.json --copy C.json --apply    # drafts + leads + tag (never activates)
    python3 execution/lead_sourcing/list_campaign_launch.py --campaigns P.json --copy C.json --apply --activate --i-mean-it
Directive: directives/lead_sourcing/list_campaign_launch.md

Lead CSV files: <leads_dir>/<segment>_<bucket>.csv with columns first_name, last_name, email, company_casual,
website, email_tier, personalization_type, first_line. Merge tags available in copy: {{firstName}}, {{lastName}},
{{companyName}}, {{first_line}}, {{company}}. Instantly v2 step.delay = days before the NEXT step.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:  # cloud has env vars only; .env is optional
    pass
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "infrastructure"))
from instantly_campaign_shell import paged, req  # noqa: E402  (curl client; Cloudflare 403s some python clients)

DAYS = {"0": False, "1": True, "2": True, "3": True, "4": True, "5": True, "6": False}
DRAFT_OK = (0, 2)  # draft, paused
COMPANY_CAP = 2


def dom(v: str) -> str:
    v = (v or "").strip().lower()
    v = re.sub(r"^https?://", "", v).split("/")[0]
    return v.removeprefix("www.")


def body_html(text: str) -> str:
    """Plain text -> Instantly editor HTML: one <div> per line, a blank line becomes <div><br /></div>."""
    return "".join("<div><br /></div>" if not ln.strip() else f"<div>{ln}</div>" for ln in text.strip().split("\n"))


def html_text(h: str) -> str:
    h = h.replace("<div><br /></div>", "\n").replace("<br />", "\n").replace("<br>", "\n")
    return re.sub(r"<[^>]+>", "\n", h).replace("\n\n", "\n").strip()


def leads_post(body: dict) -> list[dict]:
    """POST /leads/list, fully paginated (starting_after)."""
    body, items = dict(body, limit=100), []
    while True:
        r = req("POST", "/leads/list", body)
        items += r.get("items", [])
        if not r.get("next_starting_after") or not r.get("items"):
            return items
        body["starting_after"] = r["next_starting_after"]


def load_rows(plan: dict, leads_dir: Path) -> tuple[dict, dict]:
    allow = {dom(r["website"]) for r in csv.DictReader(open(plan["allow_list"], encoding="utf-8"))}
    drop = json.loads(Path(plan["drop_list"]).read_text()) if plan.get("drop_list") else {}
    drop_dom = {dom(d) for d in drop.get("domains", [])}
    drop_names = {n.strip().lower() for n in drop.get("names", [])}
    segs = {c["segment"] for c in plan["campaigns"]}
    rows, skips = {}, {}
    for seg in sorted(segs):
        for f in sorted(leads_dir.glob(f"{seg}_*.csv")):
            for r in csv.DictReader(open(f, encoding="utf-8", newline="")):
                key = (seg, r["email_tier"])
                sk = skips.setdefault(key, {})
                names = {r.get("company_casual", "").strip().lower(), r.get("company_display", "").strip().lower()}
                d = dom(r["website"])
                reason = None
                if r.get("personalization_type", "").strip() in ("", "none") or not r.get("first_line", "").strip():
                    reason = "no personalization"
                elif d not in allow:
                    reason = "not on batch list"
                elif d in drop_dom or dom(r["email"].split("@")[-1]) in drop_dom or names & drop_names:
                    reason = "drop list"
                if reason:
                    sk[reason] = sk.get(reason, 0) + 1
                    continue
                rows.setdefault(key, []).append(r)
    return rows, skips


def lead_payload(r: dict) -> dict:
    return {"email": r["email"].strip(), "first_name": r["first_name"].strip(), "last_name": r["last_name"].strip(),
            "company_name": r["company_casual"].strip(), "website": r["website"].strip(),
            "custom_variables": {"first_line": r["first_line"].strip(), "company": r["company_casual"].strip()}}


def camp_payload(c: dict, plan: dict, steps: list[dict], tag: str) -> dict:
    fr, to = plan.get("window", ["08:00", "16:30"])
    seq = [{"steps": [{"type": "email", "delay": int(s["delay"]), "delay_unit": "days",
                       "variants": [{"subject": s.get("subject", ""), "body": body_html(s["body"])}]} for s in steps]}]
    return {"name": c["name"], "sequences": seq, "email_tag_list": [tag], "daily_limit": c["daily_limit"],
            **({"daily_max_leads": c["daily_max_leads"]} if c.get("daily_max_leads") else {}),
            "campaign_schedule": {"schedules": [{"name": "Weekdays", "timing": {"from": fr, "to": to}, "days": DAYS,
                                                 "timezone": plan.get("timezone", "America/Dawson")}]},
            "text_only": True, "first_email_text_only": True, "open_tracking": False, "link_tracking": False,
            "insert_unsubscribe_header": True, "stop_on_reply": True, "stop_on_auto_reply": False,
            "stop_for_company": True}


def render(text: str, lead: dict) -> str:
    pl = lead.get("payload") or {}
    v = {"firstName": lead.get("first_name") or pl.get("firstName", ""), "lastName": lead.get("last_name") or "",
         "companyName": lead.get("company_name") or "", **{k: str(x) for k, x in pl.items()}}
    return re.sub(r"\{\{(\w+)\}\}", lambda m: v.get(m.group(1), m.group(0)), text)


def readback(c: dict, cid: str) -> dict:
    x = req("GET", f"/campaigns/{cid}")
    L = leads_post({"campaign": cid})
    steps = x["sequences"][0]["steps"]
    s1 = steps[0]["variants"][0]
    prev = None
    if L:
        prev = {"to": L[0]["email"], "subject": render(s1["subject"], L[0]), "body": render(html_text(s1["body"]), L[0])}
    sched = x.get("campaign_schedule", {}).get("schedules", [{}])[0]
    return {"name": x["name"], "id": cid, "status": x.get("status"), "leads": len(L),
            "settings": {k: x.get(k) for k in ("email_tag_list", "daily_limit", "daily_max_leads", "text_only",
                                               "first_email_text_only", "open_tracking", "link_tracking",
                                               "insert_unsubscribe_header", "stop_on_reply", "stop_for_company")}
            | {"schedule": {"timing": sched.get("timing"), "days": sched.get("days"), "timezone": sched.get("timezone")},
               "step_delays": [s.get("delay") for s in steps],
               "step_subjects": [s["variants"][0]["subject"] for s in steps]},
            "preview_step1": prev}


def inbox_health(tag: str) -> list[dict]:
    return [{"email": a["email"], "status": a.get("status"), "warmup_status": a.get("warmup_status"),
             "warmup_score": a.get("stat_warmup_score"), "daily_limit": a.get("daily_limit")}
            for a in sorted(paged("/accounts", {"tag_ids": tag}), key=lambda a: a["email"])]


def main(argv=None):
    ap = argparse.ArgumentParser(description="List-driven Instantly campaign launcher (plan-only by default)")
    ap.add_argument("--campaigns", required=True, help="plan JSON (see module docstring)")
    ap.add_argument("--copy", required=True, help="copy JSON with steps per segment")
    ap.add_argument("--leads-dir", help="override plan leads_dir")
    ap.add_argument("--tag", help="override plan tag_id (Instantly custom tag id)")
    ap.add_argument("--check", action="store_true", help="read back campaigns + inboxes only")
    ap.add_argument("--apply", action="store_true", help="create/update drafts, upload leads, tag")
    ap.add_argument("--activate", action="store_true", help="start campaigns (requires --apply --i-mean-it)")
    ap.add_argument("--i-mean-it", action="store_true")
    a = ap.parse_args(argv)
    if a.activate and not (a.apply and a.i_mean_it):
        ap.error("--activate requires --apply and --i-mean-it")
    plan = json.loads(Path(a.campaigns).read_text())
    copy = json.loads(Path(a.copy).read_text())
    segcopy = copy.get("segments") or copy.get("verticals") or {}
    tag = a.tag or plan["tag_id"]
    state_p = Path(plan["state"])
    st = json.loads(state_p.read_text()) if state_p.exists() else {}
    st.setdefault("campaigns", {})
    save = lambda: state_p.write_text(json.dumps(st, indent=1, ensure_ascii=False))
    if a.activate and not copy.get("approved"):
        sys.exit("copy JSON approved != true: the copy has not cleared its gate; refusing to activate")
    for c in plan["campaigns"]:
        if c["segment"] not in segcopy or len(segcopy[c["segment"]]["steps"]) < 1:
            sys.exit(f"copy JSON has no steps for segment {c['segment']}")

    camps = {x["name"]: x for x in paged("/campaigns")}
    for c in plan["campaigns"]:
        c["id"] = c.get("id") or st["campaigns"].get(c["name"], {}).get("id") or camps.get(c["name"], {}).get("id")
    targets = {c["id"] for c in plan["campaigns"] if c.get("id")}

    if a.check:
        out = {"campaigns": [readback(c, c["id"]) if c.get("id") else {"name": c["name"], "id": None}
                             for c in plan["campaigns"]], "inboxes": inbox_health(tag)}
        print(json.dumps(out, indent=1, ensure_ascii=False))
        bad = [x["name"] for x in out["campaigns"] if x.get("id") and x["status"] not in DRAFT_OK and not a.activate]
        if bad:
            print(f"NOTE: not draft/paused: {bad}", file=sys.stderr)
        return

    # ---- filter + dedupe ----
    rows, skips = load_rows(plan, Path(a.leads_dir or plan["leads_dir"]))
    ws = leads_post({})  # every lead in the workspace (campaigns + lead lists)
    lists = paged("/lead-lists")
    seen_ids = {x.get("id") for x in ws}
    for lst in lists:  # belt and braces: lead-list members, in case the global listing omits them
        ws += [x for x in leads_post({"list_id": lst["id"]}) if x.get("id") not in seen_ids]
    cutoff = datetime.now(timezone.utc) - timedelta(days=int(plan.get("contacted_window_days", 90)))
    other_emails, recent_dom, in_target = set(), set(), {}
    for x in ws:
        e = (x.get("email") or "").strip().lower()
        if x.get("campaign") in targets:
            in_target.setdefault(x["campaign"], {})[e] = x
            continue
        other_emails.add(e)
        ts = x.get("timestamp_last_contact")
        if ts and datetime.fromisoformat(ts.replace("Z", "+00:00")) >= cutoff:
            recent_dom.add(dom(e.split("@")[-1]))
    todo, per_company, resync = {}, {}, {}
    for c in plan["campaigns"]:
        key = (c["segment"], c["tier"])
        sk = skips.setdefault(key, {})
        keep, already = [], in_target.get(c.get("id"), {})
        for r in rows.get(key, []):
            e = r["email"].strip().lower()
            d = dom(r["website"])
            per_company.setdefault(d, set()).add(e)
            if e in already:
                sk["already in this campaign"] = sk.get("already in this campaign", 0) + 1
                want = lead_payload(r)["custom_variables"]
                have = already[e].get("payload") or {}
                if any(str(have.get(k, "")) != v for k, v in want.items()):  # CSV fixed after upload: upsert vars
                    resync.setdefault(c["name"], []).append((already[e]["id"], want))
            elif e in other_emails:
                sk["already in workspace"] = sk.get("already in workspace", 0) + 1
            elif d in recent_dom or dom(e.split("@")[-1]) in recent_dom:
                sk["domain contacted <=90d"] = sk.get("domain contacted <=90d", 0) + 1
            else:
                keep.append(r)
        todo[c["name"]] = keep
    over = {d: len(v) for d, v in per_company.items() if len(v) > COMPANY_CAP}
    if over:
        sys.exit(f"company cap {COMPANY_CAP} violated in input: {dict(list(over.items())[:10])}")
    print(f"workspace leads scanned {len(ws)} across {len(camps)} campaigns + {len(lists)} lead lists; "
          f"domains contacted in window {len(recent_dom)}")
    for c in plan["campaigns"]:
        k = (c["segment"], c["tier"])
        print(f"{c['name']} | id={c.get('id') or 'new'} | eligible={len(rows.get(k, []))} upload={len(todo[c['name']])} "
              f"resync_vars={len(resync.get(c['name'], []))} "
              f"| skipped={skips.get(k, {})}")
    st["filter"] = {c["name"]: {"eligible": len(rows.get((c["segment"], c["tier"]), [])),
                                "to_upload": len(todo[c["name"]]), "skipped": skips.get((c["segment"], c["tier"]), {})}
                    for c in plan["campaigns"]}
    if not a.apply:
        print("PLAN ONLY (no writes).")
        return

    # ---- apply: drafts, leads, tag ----
    for c in plan["campaigns"]:
        rec = st["campaigns"].setdefault(c["name"], {})
        body = camp_payload(c, plan, segcopy[c["segment"]]["steps"], tag)
        if c.get("id"):
            cur = req("GET", f"/campaigns/{c['id']}")
            if cur.get("status") not in DRAFT_OK:
                sys.exit(f"{c['name']} status {cur.get('status')} is not draft/paused; refusing to edit")
            req("PATCH", f"/campaigns/{c['id']}", {k: v for k, v in body.items() if k != "name"})
        else:
            c["id"] = req("POST", "/campaigns", body)["id"]
        rec["id"] = c["id"]
        save()
        for lid, cv in resync.get(c["name"], []):
            req("PATCH", f"/leads/{lid}", {"custom_variables": cv})
            rec.setdefault("vars_resynced", []).append(lid)
            save()
        new = [lead_payload(r) for r in todo[c["name"]]]
        res = rec.setdefault("uploaded", {})
        for i in range(0, len(new), 500):
            r = req("POST", "/leads/add", {"campaign_id": c["id"], "skip_if_in_workspace": True,
                                           "leads": new[i:i + 500]})
            got = {k: int(r.get(k) or 0) for k in ("leads_uploaded", "skipped_count", "in_blocklist",
                                                   "duplicated_leads", "invalid_email_count")}
            for k, v in got.items():
                res[k] = res.get(k, 0) + v
            save()
            if sum(got.values()) < len(new[i:i + 500]):
                sys.exit(f"{c['name']}: {len(new[i:i + 500])} leads sent, only {sum(got.values())} accounted: {got}")
        req("POST", "/custom-tags/toggle-resource", {"tag_ids": [tag], "resource_ids": [c["id"]],
                                                     "resource_type": 2, "assign": True})
        rec["tagged"] = True
        save()
        if a.activate:
            cur = req("GET", f"/campaigns/{c['id']}")
            if cur.get("status") not in (0, 1, 2):
                sys.exit(f"{c['name']} unexpected status {cur.get('status')}; refusing to activate")
            if not leads_post({"campaign": c["id"]}):
                sys.exit(f"{c['name']} has 0 leads; refusing to activate")
            if cur.get("status") != 1:
                req("POST", f"/campaigns/{c['id']}/activate")
            rec["activated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            save()
    st["readback"] = [readback(c, c["id"]) for c in plan["campaigns"]]
    st["inboxes"] = inbox_health(tag)
    st["read_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    save()
    print(json.dumps(st["readback"], indent=1, ensure_ascii=False))
    want = (1,) if a.activate else DRAFT_OK
    bad = [x["name"] for x in st["readback"] if x["status"] not in want]
    if bad:
        sys.exit(f"ALERT read-back status not in {want}: {bad}")


if __name__ == "__main__":
    main()
