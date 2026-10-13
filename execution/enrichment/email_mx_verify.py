#!/usr/bin/env python3
"""
email_mx_verify.py
description: Keyless email pre-verification: syntax, MX record (DNS-over-HTTPS via dns.google, works behind
             proxies that swallow local MX answers), role-address and disposable-domain flags. No SMTP probe
             (port 25 is blocked in cloud sessions) so a "mx_ok" result means the domain accepts mail, not that
             the mailbox exists. Use million_verifier.py for mailbox-level checks when the key is available.
inputs:  --input CSV/JSON with an Email/email column; --output; --column (default auto)
outputs: same rows + email_status (mx_ok | no_mx | bad_syntax | role | disposable) + mx_host; summary on stdout
usage:   python3 execution/enrichment/email_mx_verify.py --input .tmp/yoga_csv/"Yoga Teachers with Email.csv" --output .tmp/yoga_verified.csv
"""
import argparse
import csv
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

import requests

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@([A-Za-z0-9\-]+\.)+[A-Za-z]{2,}$")
ROLE = {"info", "contact", "hello", "bonjour", "admin", "support", "noreply", "no-reply", "webmaster", "postmaster",
        "sales", "office", "team", "accueil", "secretariat", "communication", "reservation", "inscription"}
DISPOSABLE = {"mailinator.com", "yopmail.com", "guerrillamail.com", "10minutemail.com", "temp-mail.org", "tempmail.com"}
DOH = "https://dns.google/resolve"


@lru_cache(maxsize=None)
def mx_host(domain: str) -> str:
    """Return the best MX host for a domain ('' if none). Falls back to an A record (implicit MX)."""
    for rtype in ("MX", "A"):
        try:
            resp = requests.get(DOH, params={"name": domain, "type": rtype}, timeout=10)
            resp.raise_for_status()
            answers = [a for a in resp.json().get("Answer", []) if a.get("type") == (15 if rtype == "MX" else 1)]
        except (requests.RequestException, ValueError):
            continue
        if answers:
            if rtype == "MX":
                best = min(answers, key=lambda a: int(a["data"].split()[0]))
                return best["data"].split()[-1].rstrip(".")
            return f"A:{answers[0]['data']}"
    return ""


def verify(email: str) -> tuple[str, str]:
    email = (email or "").strip()
    if not EMAIL_RE.match(email):
        return "bad_syntax", ""
    local, domain = email.rsplit("@", 1)
    domain = domain.lower()
    if domain in DISPOSABLE:
        return "disposable", ""
    host = mx_host(domain)
    if not host:
        return "no_mx", ""
    if local.lower() in ROLE:
        return "role", host
    return "mx_ok", host


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--column", default="")
    a = ap.parse_args()
    src = Path(a.input)
    if src.suffix == ".json":
        rows = json.loads(src.read_text(encoding="utf-8"))
    else:
        with open(src, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    col = a.column or next((k for k in rows[0] if k.lower() == "email"), "email")
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda r: verify(r.get(col, "")), rows))
    counts: dict[str, int] = {}
    for r, (status, host) in zip(rows, results):
        r["email_status"], r["mx_host"] = status, host
        counts[status] = counts.get(status, 0) + 1
    out = Path(a.output)
    if out.suffix == ".json":
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"{k:12s} {v}")
    print(f"wrote {out} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
