"""Verify the email column of a leads CSV with Reoon (power mode) and write a copy with Reoon columns.

description: Reads a CSV, verifies each unique email with Reoon's single-verify API (power mode,
             SMTP-level), caches results per email, and writes the CSV back out with reoon_status,
             reoon_score, reoon_catch_all, reoon_safe and a send_bucket column:
             main (safe, score >= 90) | catchall (catch_all) | drop (everything else).
inputs: --src CSV with an `email` column; env REOON_API_KEY (or REOON_TOKEN) or .env.
outputs: --out CSV; cache .tmp/reoon/cache.jsonl (one row per verified email).

Usage:
    python3 execution/lead_sourcing/reoon_verify.py --src leads.csv --out leads_verified.csv
    python3 execution/lead_sourcing/reoon_verify.py --balance

See also: directives/lead_sourcing/reoon_verify.md
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".tmp" / "reoon" / "cache.jsonl"
API = "https://emailverifier.reoon.com/api/v1"
_LOCK = threading.Lock()


def api_key() -> str:
    for name in ("REOON_API_KEY", "REOON_TOKEN"):
        if os.environ.get(name):
            return os.environ[name].strip()
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            if k.strip() in ("REOON_API_KEY", "REOON_TOKEN") and v.strip():
                return v.strip()
    sys.exit("REOON_API_KEY / REOON_TOKEN not set")


def load_cache() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if CACHE.exists():
        for line in CACHE.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            out[row["email"]] = row
    return out


def verify_one(email: str, key: str) -> dict:
    for attempt in range(4):
        try:
            r = requests.get(f"{API}/verify", params={"email": email, "key": key, "mode": "power"}, timeout=90)
            if r.status_code == 429:
                time.sleep(2 ** attempt * 2)
                continue
            r.raise_for_status()
            d = r.json()
            if d.get("status") in (None, "error"):
                raise ValueError(str(d)[:200])
            return {"email": email, "status": d.get("status", ""), "score": d.get("overall_score", ""),
                    "catch_all": bool(d.get("is_catch_all")), "safe": bool(d.get("is_safe_to_send")),
                    "role": bool(d.get("is_role_account"))}
        except (requests.RequestException, ValueError) as exc:
            if attempt == 3:
                return {"email": email, "status": "error", "score": "", "catch_all": False, "safe": False,
                        "role": False, "error": str(exc)[:200]}
            time.sleep(2 ** attempt * 2)
    return {"email": email, "status": "error", "score": "", "catch_all": False, "safe": False, "role": False}


def bucket(res: dict) -> str:
    score = res.get("score")
    if res.get("status") == "safe" and isinstance(score, int) and score >= 90 and not res.get("role"):
        return "main"
    if res.get("status") == "catch_all" or res.get("catch_all"):
        return "catchall"
    return "drop"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--balance", action="store_true")
    a = ap.parse_args()
    key = api_key()
    if a.balance:
        r = requests.get(f"{API}/check-account-balance/", params={"key": key}, timeout=20)
        print(r.text)
        return
    if not a.src or not a.out:
        ap.error("--src and --out are required")
    with open(a.src, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    cache = load_cache()
    todo = sorted({r["email"].strip().lower() for r in rows if r.get("email")} - set(cache))
    print(f"{len(rows)} rows, {len(todo)} emails to verify ({len(cache)} cached)")
    CACHE.parent.mkdir(parents=True, exist_ok=True)

    def work(email: str) -> None:
        res = verify_one(email, key)
        with _LOCK:
            cache[email] = res
            if res["status"] != "error":
                with open(CACHE, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(res) + "\n")

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        list(ex.map(work, todo))

    fields = list(rows[0].keys()) + ["reoon_status", "reoon_score", "reoon_catch_all", "reoon_safe", "send_bucket"]
    counts: dict[str, int] = {}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            res = cache.get(r.get("email", "").strip().lower(), {})
            b = bucket(res) if res else "drop"
            counts[b] = counts.get(b, 0) + 1
            w.writerow({**r, "reoon_status": res.get("status", ""), "reoon_score": res.get("score", ""),
                        "reoon_catch_all": res.get("catch_all", ""), "reoon_safe": res.get("safe", ""),
                        "send_bucket": b})
    print("buckets:", counts)


if __name__ == "__main__":
    main()
