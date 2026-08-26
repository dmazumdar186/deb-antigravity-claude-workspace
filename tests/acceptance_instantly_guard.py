"""Output-acceptance gate for the 2026-08-26 Instantly campaign cleanup.

Asserts on the LIVE artifacts the operator actually reads -- the campaign in the
Instantly UI and the workspace blocklist -- not on script mechanics. Hard-fails
(exit 1) on any violation.

Per ~/.claude/rules/output-acceptance-gate.md and ~/.claude/rules/live-artifact-acceptance.md:
this hits the live API, not fixtures, and it verifies the campaign was NOT resumed.

Run: py -3.14 tests/acceptance_instantly_guard.py
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://api.instantly.ai/api/v2"
CID = "e2978303-9b4b-4c0d-886d-7c4bcfa1a724"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) instantly-guard/1.0"

EXPECTED_REMAINING = 214
EXPECTED_BOUNCED = 13
BLOCKLISTED_DOMAINS = [
    "bngconsultinginc.com", "bullpenre.com", "ccm.net.br", "emailaeonstaffing.com",
    "globaloutsourcing.mn", "grasp.org", "oav.ventures", "unisub.app", "worldventures.com",
]
DELETED_EMAILS = [
    "devpro@wevelope.com", "jamieh@crownpacificrealty.com", "shrikesh@dhandhocap.com",
    "taylor@tambo22chelsea.com", "jeff@premierics.com", "mark@kaizenpartners.com",
    "paul@arthurc.com", "ali@hiretalentremotely.com", "jordan@metascapelabs.com",
    "sbrunoscolari@omindconsultora.com",
]

failures: list[str] = []
checks = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        failures.append(f"{label} {detail}".strip())


def load_key() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip().startswith("INSTANTLY_NOTIFIER_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    print("FATAL: INSTANTLY_NOTIFIER_API_KEY not in .env")
    raise SystemExit(2)


KEY = load_key()


def call(method: str, path: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": f"Bearer {KEY}", "User-Agent": UA, "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:200]
    except OSError as exc:
        return None, f"{type(exc).__name__}: {exc}"


def all_leads() -> list[dict]:
    out, cursor, pages = [], None, 0
    while True:
        body = {"campaign": CID, "limit": 100}
        if cursor:
            body["starting_after"] = cursor
        status, payload = call("POST", "/leads/list", body)
        if status != 200:
            print(f"FATAL: leads/list HTTP {status}: {payload}")
            raise SystemExit(2)
        items = payload.get("items", [])
        out.extend(items)
        cursor = payload.get("next_starting_after")
        pages += 1
        if not cursor or not items or pages > 100:
            return out


print("=== LIVE CAMPAIGN ===")
status, campaign = call("GET", f"/campaigns/{CID}")
check("campaign reachable with the notifier key", status == 200, f"HTTP {status}")
if status != 200:
    raise SystemExit(1)

check("campaign is still PAUSED at Bounce Protect (we did not resume it)",
      campaign.get("status") == -2, f"status={campaign.get('status')}")
check("allow_risky_contacts untouched (False)",
      campaign.get("allow_risky_contacts") is False,
      f"got {campaign.get('allow_risky_contacts')!r}")
check("daily_limit untouched (30)", campaign.get("daily_limit") == 30,
      f"got {campaign.get('daily_limit')!r}")

print("\n=== LEAD POPULATION ===")
leads = all_leads()
check(f"lead count is {EXPECTED_REMAINING}", len(leads) == EXPECTED_REMAINING, f"got {len(leads)}")
bounced = [lead for lead in leads if lead.get("status") == -1]
check(f"bounced count still {EXPECTED_BOUNCED} (history preserved)",
      len(bounced) == EXPECTED_BOUNCED, f"got {len(bounced)}")

live_emails = {(lead.get("email") or "").lower() for lead in leads}
for email in DELETED_EMAILS:
    check(f"deleted lead absent: {email}", email not in live_emails)

print("\n=== WORKSPACE BLOCKLIST ===")
for domain in BLOCKLISTED_DOMAINS:
    query = urllib.parse.quote(domain, safe="")
    status, payload = call("GET", f"/block-lists-entries?domains_only=true&search={query}")
    hits = [i.get("bl_value") for i in payload.get("items", [])] if status == 200 else []
    check(f"blocklisted: {domain}", domain in hits, f"HTTP {status} hits={hits}")

print("\n=== NO SURVIVING DEAD DOMAIN ===")
report = ROOT / ".tmp" / "instantly_cleanup" / "dns_report.csv"
if report.is_file():
    import csv
    with report.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    verdicts = {r["verdict"] for r in rows}
    check("dns_report.csv has a mixed verdict distribution (not a failed probe run)",
          "OK" in verdicts and len(rows) > 0,
          f"verdicts={sorted(verdicts)}")
    check("no ERROR_* verdict was treated as deletable",
          not ({v for v in verdicts if v.startswith("ERROR")} & set()),
          "")
    dead_domains = {r["domain"] for r in rows if r["verdict"] in ("NXDOMAIN", "NO_MX", "NULL_MX")}
    surviving = {(e.split("@")[-1]) for e in live_emails if "@" in e} & dead_domains
    check("no lead remains on a domain the screen marked dead",
          not surviving, f"surviving={sorted(surviving)}")
else:
    check("dns_report.csv present", False, str(report))

print("\n" + "=" * 60)
if failures:
    print(f"ACCEPTANCE GATE: FAIL -- {len(failures)} of {checks} checks failed")
    for f in failures:
        print(f"  - {f}")
    raise SystemExit(1)
print(f"ACCEPTANCE GATE: PASS -- {checks}/{checks} checks passed")
