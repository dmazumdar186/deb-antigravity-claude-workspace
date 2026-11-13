#!/usr/bin/env python3
"""
description: Build a draft Instantly campaign shell: union inboxes from existing account tags into one sending tag (additive), create named campaigns (skip if they exist) with a placeholder or JSON sequence, never activate. Default dry run.
inputs: --tag, --account-tags, --name (repeatable), --daily-limit, --update-sequence-from <json>, --apply, --check
outputs: stdout inbox table + campaign readback; Instantly POST /custom-tags, /custom-tags/toggle-resource, /campaigns, PATCH /campaigns/{id} with --apply
"""

import argparse, json, os, subprocess, sys, time

API = "https://api.instantly.ai/api/v2"
PLACEHOLDER = "PLACEHOLDER - copy pending partner approval - do not activate"
DAYS = {"0": False, "1": True, "2": True, "3": True, "4": True, "5": True, "6": False}


def req(method, path, body=None, params=None):
    """curl, not requests: Cloudflare 403s some python clients."""
    key = os.environ.get("INSTANTLY_API_KEY", "").strip()
    if not key:
        sys.exit("INSTANTLY_API_KEY not set")
    url = (
        API
        + path
        + ("?" + "&".join(f"{k}={v}" for k, v in params.items()) if params else "")
    )
    cmd = [
        "curl",
        "-sS",
        "-X",
        method,
        url,
        "-H",
        "Authorization: Bearer " + key,
        "-w",
        "\n%{http_code}",
    ]
    if body is not None:
        cmd += ["-H", "Content-Type: application/json", "--data", json.dumps(body)]
    for a in range(5):
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=90).stdout
        text, _, code = out.rpartition("\n")
        code = int(code or 0)
        if code == 429 or code >= 500 or code == 0:
            time.sleep(2**a * 2)
            continue
        if code >= 400:
            raise RuntimeError(f"{method} {path} {code} {text[:400]}")
        return json.loads(text) if text.strip() else {}
    raise RuntimeError(f"{method} {path}: gave up")


def paged(path, params=None):
    params, items = dict(params or {}, limit=100), []
    while True:
        r = req("GET", path, params=params)
        items += r.get("items", [])
        if not r.get("next_starting_after") or not r.get("items"):
            return items
        params["starting_after"] = r["next_starting_after"]


def sequence(src):
    if src:
        steps = json.load(open(src))[
            "steps"
        ]  # [{"delay":0,"variants":[{"subject":..,"body":..}]}]
    else:
        steps = [
            {"delay": d, "variants": [{"subject": PLACEHOLDER, "body": PLACEHOLDER}]}
            for d in (0, 3, 5)
        ]
    return [{"steps": [dict(type="email", delay_unit="days", **s) for s in steps]}]


def payload(name, tag_id, limit, seq, tz):
    return {
        "name": name,
        "sequences": seq,
        "email_tag_list": [tag_id],
        "daily_limit": limit,
        "campaign_schedule": {
            "schedules": [
                {
                    "name": "Weekdays",
                    "timing": {"from": "08:00", "to": "16:30"},
                    "days": DAYS,
                    "timezone": tz,
                }
            ]
        },
        "text_only": True,
        "first_email_text_only": True,
        "open_tracking": False,
        "link_tracking": False,
        "insert_unsubscribe_header": True,
        "stop_on_reply": True,
        "stop_on_auto_reply": False,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument(
        "--account-tags", default="", help="comma-separated existing account tag labels"
    )
    ap.add_argument("--name", action="append", default=[])
    ap.add_argument("--daily-limit", type=int, default=290)
    ap.add_argument("--timezone", default="America/Dawson", help="Instantly timezone enum; America/Los_Angeles, Vancouver, Tijuana, Santa_Isabel are rejected")
    ap.add_argument("--update-sequence-from")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true", help="read-only report")
    a = ap.parse_args()
    live = a.apply and not a.check
    tags = {t["label"]: t["id"] for t in paged("/custom-tags")}
    accts = {}

    def tagged(tag_id):  # account tag mappings use the inbox email as resource_id
        if not tag_id:
            return []
        rows = paged("/accounts", {"tag_ids": tag_id})
        accts.update({x["email"]: x for x in rows})
        return sorted(x["email"] for x in rows)

    want = []
    for lab in filter(None, (s.strip() for s in a.account_tags.split(","))):
        got = tagged(tags.get(lab))
        print(
            f"[{lab}] {len(got)} inboxes, {sum(accts[e].get('daily_limit') or 0 for e in got)}/day"
        )
        for e in got:
            x = accts[e]
            print(
                f"  {e} limit={x.get('daily_limit')} status={x.get('status')} warmup={x.get('warmup_status')} score={x.get('stat_warmup_score')}"
            )
        want += [e for e in got if e not in want]
    tid = tags.get(a.tag)
    if not tid and live:
        tid = req("POST", "/custom-tags", {"label": a.tag})["id"]
    print(f"tag {a.tag} id={tid or '(would create)'}")
    have = set(tagged(tid))
    todo = [e for e in want if e not in have]
    print(f"tag mapping: {len(want) - len(todo)} already, {len(todo)} to add")
    if live and todo:
        req(
            "POST",
            "/custom-tags/toggle-resource",
            {
                "tag_ids": [tid],
                "resource_ids": todo,
                "resource_type": 1,
                "assign": True,
            },
        )
    camps = {c["name"]: c for c in paged("/campaigns")}
    seq = sequence(a.update_sequence_from)
    for n in a.name:
        c = camps.get(n)
        if not c:
            print(f"create {n}" + ("" if live else " (dry run)"))
            if live:
                c = req("POST", "/campaigns", payload(n, tid, a.daily_limit, seq, a.timezone))
        elif a.update_sequence_from:
            if c.get("status") not in (0, 2):
                sys.exit(
                    f"{n} status {c.get('status')} is not draft/paused; refusing to edit"
                )
            print(f"update sequence {n}" + ("" if live else " (dry run)"))
            if live:
                req("PATCH", f"/campaigns/{c['id']}", {"sequences": seq})
        if c:
            c = req("GET", f"/campaigns/{c['id']}")
            leads = req("POST", "/leads/list", {"campaign": c["id"], "limit": 1}).get(
                "items", []
            )
            print(
                json.dumps(
                    {
                        k: c.get(k)
                        for k in (
                            "id",
                            "name",
                            "status",
                            "email_tag_list",
                            "open_tracking",
                            "link_tracking",
                            "text_only",
                            "insert_unsubscribe_header",
                            "stop_on_reply",
                            "stop_on_auto_reply",
                            "daily_limit",
                            "campaign_schedule",
                        )
                    }
                    | {
                        "steps": len(c["sequences"][0]["steps"]),
                        "has_leads": bool(leads),
                    }
                )
            )
            if c.get("status") not in (0, 2):
                sys.exit(f"ALERT {n} status {c.get('status')} is not draft/paused")


if __name__ == "__main__":
    main()
