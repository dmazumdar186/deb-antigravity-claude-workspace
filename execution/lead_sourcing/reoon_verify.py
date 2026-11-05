"""Verify the email column of a leads CSV with Reoon (power mode) and write a copy with Reoon columns.

description: Reads a CSV, verifies each unique email with Reoon's single-verify API (power mode,
             SMTP-level), caches results per email, and writes the CSV back out with reoon_status,
             reoon_score, reoon_catch_all, reoon_safe and a send_bucket column:
             main (safe, score >= 90) | catchall (catch_all) | drop (everything else).
             Default is a dry count (no API call, no credits): how many emails would be verified.
             --live spends credits, capped by --max-verify (default 500).
inputs: --src CSV with an `email` column; --live; --max-verify N; env REOON_API_KEY (or REOON_TOKEN) or .env
        (key needed only for --live / --balance).
outputs: dry run: stdout count only. --live: --out CSV (formula-safe cells); cache .tmp/reoon/cache.jsonl
         (one row per verified email); one JSON row per live run in .tmp/reoon_ledger.jsonl.

Usage:
    python3 execution/lead_sourcing/reoon_verify.py --src leads.csv                       # dry count, free
    python3 execution/lead_sourcing/reoon_verify.py --src leads.csv --out leads_verified.csv --live [--max-verify 500]
    python3 execution/lead_sourcing/reoon_verify.py --balance

See also: directives/lead_sourcing/reoon_verify.md
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from execution.modules.pipeline_utils import csv_safe_row  # noqa: E402

CACHE = ROOT / ".tmp" / "reoon" / "cache.jsonl"
LEDGER = ROOT / ".tmp" / "reoon_ledger.jsonl"
CREDITS_PER_EMAIL = 1  # power mode spends one instant credit per verified email
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


def append_ledger(row: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Reoon power-mode verify. Dry count by default; --live spends credits.")
    ap.add_argument("--src", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--balance", action="store_true", help="print account balance (free call)")
    ap.add_argument("--live", action="store_true", help="actually verify (spends one credit per uncached email)")
    ap.add_argument("--max-verify", type=int, default=500, help="ceiling on emails verified per live run")
    a = ap.parse_args(argv)
    if a.balance:
        r = requests.get(f"{API}/check-account-balance/", params={"key": api_key()}, timeout=20)
        print(r.text)
        return 0
    if not a.src:
        ap.error("--src is required")
    if a.max_verify < 1:
        ap.error("--max-verify must be >= 1")
    if a.live and not a.out:
        ap.error("--out is required with --live")
    with open(a.src, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print(f"{a.src}: no rows; nothing to do")
        return 0
    cache = load_cache()
    pending = sorted({r["email"].strip().lower() for r in rows if r.get("email")} - set(cache))
    todo = pending[: a.max_verify]
    over = len(pending) - len(todo)
    print(f"{len(rows)} rows, {len(pending)} uncached emails ({len(cache)} cached); "
          f"{len(todo)} to verify under --max-verify {a.max_verify}, est. {len(todo) * CREDITS_PER_EMAIL} credits")
    if over:
        print(f"WARNING: {over} uncached emails exceed --max-verify {a.max_verify}; they stay unverified "
              f"(bucket drop) until a re-run", file=sys.stderr)
    if not a.live:
        print("DRY RUN: no Reoon calls made, 0 credits spent. Re-run with --live --out <csv> to verify.")
        return 0

    key = api_key()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    errors = 0

    def work(email: str) -> None:
        nonlocal errors
        res = verify_one(email, key)
        with _LOCK:
            cache[email] = res
            if res["status"] != "error":
                with open(CACHE, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(res) + "\n")
            else:
                errors += 1

    try:
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            list(ex.map(work, todo))
    finally:
        append_ledger({"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "src": str(a.src),
                       "n_verified": len(todo), "n_errors": errors,
                       "credits_est": len(todo) * CREDITS_PER_EMAIL})

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
            w.writerow(csv_safe_row({**r, "reoon_status": res.get("status", ""), "reoon_score": res.get("score", ""),
                                     "reoon_catch_all": res.get("catch_all", ""), "reoon_safe": res.get("safe", ""),
                                     "send_bucket": b}))
    print("buckets:", counts)
    if errors:
        print(f"WARNING: {errors} emails errored (not cached; re-run retries them)", file=sys.stderr)
    if over:
        print(f"INCOMPLETE: {over} emails not verified (over --max-verify); exit 3", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
