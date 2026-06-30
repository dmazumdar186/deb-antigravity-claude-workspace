"""Wire prodcraft.fyi (registered at Porkbun) to the Cloudflare Pages project 'prodcraft'.

Two halves:
  1. Cloudflare side: add prodcraft.fyi + www.prodcraft.fyi as custom domains on the
     Pages project. Uses the wrangler OAuth token (personal account debanjan186), NOT the
     .env CLOUDFLARE_API_TOKEN (which is the AM-locked account — forbidden).
  2. Porkbun side: point DNS at prodcraft.pages.dev — ALIAS at apex, CNAME for www.
     Removes Porkbun's default parking records first. Uses PORKBUN_* keys from .env.

Safe to re-run (idempotent: skips domains/records that already exist correctly).

Usage:
    py execution/personal_workflows/portfolio_site/scripts/wire_domain.py [--apply]
Without --apply it's a dry run (prints planned actions, makes no changes).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[4]
ENV_FILE = WORKSPACE / ".env"
WRANGLER_CFG = Path(os.environ["APPDATA"]) / "xdg.config" / ".wrangler" / "config" / "default.toml"

PERSONAL_ACCOUNT = "1bd372ca60ff5733565863799237e83b"   # debanjan186 — confirmed non-AM
AM_ACCOUNT = "26e5b8612be35e5d23a9186fcf5288d0"         # forbidden (lockdown)
PROJECT = "prodcraft"
DOMAIN = "prodcraft.fyi"
PAGES_TARGET = "prodcraft.pages.dev"

APPLY = "--apply" in sys.argv


def load_env() -> dict:
    env = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def wrangler_oauth_token() -> str:
    for line in WRANGLER_CFG.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("oauth_token"):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("FATAL: no oauth_token in wrangler config; run `wrangler whoami` first")


def cf_api(method: str, path: str, token: str, body: dict | None = None) -> dict:
    url = f"https://api.cloudflare.com/client/v4{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


def porkbun_api(path: str, env: dict, extra: dict | None = None) -> dict:
    url = f"https://api.porkbun.com/api/json/v3{path}"
    body = {"apikey": env["PORKBUN_API_KEY"], "secretapikey": env["PORKBUN_SECRET_KEY"]}
    if extra:
        body.update(extra)
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


def add_pages_domain(token: str, name: str) -> None:
    existing = cf_api("GET", f"/accounts/{PERSONAL_ACCOUNT}/pages/projects/{PROJECT}/domains", token)
    names = [d.get("name") for d in existing.get("result", [])] if existing.get("success") else []
    if name in names:
        print(f"  CF: custom domain {name} already attached — skip")
        return
    if not APPLY:
        print(f"  CF: WOULD add custom domain {name}")
        return
    r = cf_api("POST", f"/accounts/{PERSONAL_ACCOUNT}/pages/projects/{PROJECT}/domains", token, {"name": name})
    if r.get("success"):
        print(f"  CF: added custom domain {name}")
    else:
        print(f"  CF: FAILED to add {name}: {r.get('errors')}")


def wire_porkbun(env: dict) -> None:
    rec = porkbun_api(f"/dns/retrieve/{DOMAIN}", env)
    if rec.get("status") != "SUCCESS":
        print(f"  Porkbun: retrieve FAILED: {rec}")
        return
    records = rec.get("records", [])

    # Records that conflict with our apex ALIAS / www CNAME (Porkbun parking defaults)
    apex_host = DOMAIN
    www_host = f"www.{DOMAIN}"
    conflict_types = {"A", "AAAA", "ALIAS", "CNAME"}
    to_delete = [
        r for r in records
        if r.get("name") in (apex_host, www_host) and r.get("type") in conflict_types
    ]
    for r in to_delete:
        label = f"{r.get('type')} {r.get('name')} -> {r.get('content')}"
        if not APPLY:
            print(f"  Porkbun: WOULD delete parking record [{label}]")
            continue
        d = porkbun_api(f"/dns/delete/{DOMAIN}/{r['id']}", env)
        print(f"  Porkbun: deleted [{label}] -> {d.get('status')}")

    # Create apex ALIAS + www CNAME -> pages.dev
    targets = [("", "ALIAS"), ("www", "CNAME")]
    for sub, rtype in targets:
        host = DOMAIN if sub == "" else f"{sub}.{DOMAIN}"
        # skip if a correct record already exists
        good = any(
            r.get("name") == host and r.get("type") == rtype and r.get("content") == PAGES_TARGET
            for r in records
        )
        if good:
            print(f"  Porkbun: {rtype} {host} -> {PAGES_TARGET} already correct — skip")
            continue
        if not APPLY:
            print(f"  Porkbun: WOULD create {rtype} {host or DOMAIN} -> {PAGES_TARGET}")
            continue
        c = porkbun_api(f"/dns/create/{DOMAIN}", env,
                        {"type": rtype, "name": sub, "content": PAGES_TARGET, "ttl": "600"})
        print(f"  Porkbun: created {rtype} {host or DOMAIN} -> {PAGES_TARGET} -> {c.get('status')} {c.get('message','')}")


def main() -> int:
    env = load_env()
    if env.get("CLOUDFLARE_ACCOUNT_ID") == AM_ACCOUNT:
        print("NOTE: .env CLOUDFLARE_* is the AM-locked account — NOT used. Using wrangler OAuth instead.")
    token = wrangler_oauth_token()

    # sanity: confirm the OAuth token is on the personal account
    who = cf_api("GET", "/accounts", token)
    accts = [a.get("id") for a in who.get("result", [])] if who.get("success") else []
    if PERSONAL_ACCOUNT not in accts:
        print(f"FATAL: wrangler OAuth token does not see personal account {PERSONAL_ACCOUNT}. Accounts: {accts}")
        return 2
    if AM_ACCOUNT in accts:
        print("NOTE: OAuth token can see AM account too — we only ever target the personal account/project.")

    mode = "APPLY" if APPLY else "DRY-RUN (no changes; pass --apply to execute)"
    print(f"=== Wiring {DOMAIN} -> Pages project '{PROJECT}' [{mode}] ===")
    print("[1/2] Cloudflare Pages custom domains")
    add_pages_domain(token, DOMAIN)
    add_pages_domain(token, f"www.{DOMAIN}")
    print("[2/2] Porkbun DNS")
    wire_porkbun(env)
    print("=== done ===")
    if not APPLY:
        print("Re-run with --apply to execute.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
