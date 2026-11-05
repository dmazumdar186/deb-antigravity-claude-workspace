"""Shared helper for read-only front-door synthetics (tests/front_door_*.py).

Each probe is a single GET/OPTIONS with no side effects and no spend (no LLM
call, no Telegram ping, no KV/R2 write). Default mode is an offline --check
that prints the plan and exits 0; a live request needs --live.
"""
from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request


def probe(site_url: str, method: str, path: str, expect_status: int,
          expect_body: str = "", expect_header: str = "") -> list[str]:
    """Run one live read-only probe; return a list of failure strings."""
    if not site_url.startswith(("https://", "http://127.0.0.1", "http://localhost")):
        return [f"refusing non-https URL {site_url!r}"]
    req = urllib.request.Request(site_url.rstrip("/") + path, method=method,
                                 headers={"User-Agent": "prodcraft-front-door/1"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 - scheme checked above
            status, headers, body = resp.status, resp.headers, resp.read(65536)
    except urllib.error.HTTPError as exc:
        status, headers, body = exc.code, exc.headers, exc.read(65536)
    except (urllib.error.URLError, TimeoutError) as exc:
        return [f"{method} {path}: unreachable ({exc})"]
    fails = []
    if status != expect_status:
        fails.append(f"{method} {path}: HTTP {status}, expected {expect_status}")
    if expect_body and expect_body not in body.decode("utf-8", "replace"):
        fails.append(f"{method} {path}: body missing {expect_body!r}")
    if expect_header and not headers.get(expect_header):
        fails.append(f"{method} {path}: header {expect_header} missing")
    return fails


def main(name: str, default_url: str, checks: list[dict]) -> int:
    ap = argparse.ArgumentParser(description=f"Front-door synthetic: {name}")
    ap.add_argument("--live", action="store_true", help="hit the live URL (read-only probes)")
    ap.add_argument("--url", default=os.environ.get("SITE_URL", default_url))
    args = ap.parse_args()
    if not args.live:
        for c in checks:
            print(f"[{name}] --check (offline): would probe {c['method']} "
                  f"{args.url or '<SITE_URL>'}{c['path']} expect {c['expect_status']}")
        return 0
    if not args.url:
        print(f"[{name}] no SITE_URL set; pass --url or SITE_URL", file=sys.stderr)
        return 2
    fails: list[str] = []
    for c in checks:
        fails += probe(args.url, **c)
    for f in fails:
        print(f"FAIL [{name}] {f}", file=sys.stderr)
    if not fails:
        print(f"PASS [{name}] {len(checks)} probe(s) against {args.url}")
    return 1 if fails else 0
