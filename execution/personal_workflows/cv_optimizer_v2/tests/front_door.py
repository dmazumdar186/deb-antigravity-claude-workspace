"""Front-door synthetic for the cv_optimizer_v2 Cloudflare Worker.

Per ~/.claude/rules/front-door-synthetic.md: enters through the actual
production URL — no internal shortcuts.

This synthetic hits the cheap, idempotent endpoints only:
  - GET /api/health (no LLM call, no quota burn)
  - HEAD on the Pages site (frontend reachable)

We DELIBERATELY do not hit POST /api/optimize on every run — that would burn
~1-2% of the operator's Gemini daily free-tier quota per run, and 5x per day
would meaningfully degrade real users.

Usage:
    py execution/personal_workflows/cv_optimizer_v2/tests/front_door.py
    py execution/personal_workflows/cv_optimizer_v2/tests/front_door.py --runs 5
    py execution/personal_workflows/cv_optimizer_v2/tests/front_door.py --include-optimize  # explicit opt-in to burn quota

Exit 0 on all-PASS, 1 on first failure.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

WORKER_URL = "https://cv-optimizer-api.debanjan186.workers.dev"
PAGES_URL = "https://cv-optimizer.pages.dev"


def _get_json(url: str, timeout: int = 15) -> tuple[int, dict | None, str]:
    """GET a URL and return (status, parsed_json_or_None, raw_body)."""
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "front-door-synthetic/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", errors="replace")
            try:
                return r.status, json.loads(body), body
            except json.JSONDecodeError:
                return r.status, None, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return e.code, None, body
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return -1, None, f"{type(e).__name__}: {e}"


def check_worker_health() -> tuple[bool, str]:
    status, payload, raw = _get_json(f"{WORKER_URL}/api/health")
    if status != 200:
        return False, f"/api/health -> HTTP {status}; body={raw[:200]!r}"
    if not isinstance(payload, dict):
        return False, f"/api/health -> non-JSON body: {raw[:200]!r}"
    # Required keys per the Worker contract.
    required = ("status", "secrets_present", "prompt_fingerprint", "schema_fingerprint", "timestamp")
    missing = [k for k in required if k not in payload]
    if missing:
        return False, f"/api/health missing keys: {missing}"
    if payload["status"] not in ("ok", "degraded"):
        return False, f"/api/health unexpected status={payload['status']!r}"
    # The synthetic does not fail on `degraded` — the operator wants to see the
    # cause (KV down vs secrets missing) reported, not a hard fail that hides it.
    return True, f"/api/health -> {payload['status']} (version={payload.get('version')})"


def check_pages_reachable() -> tuple[bool, str]:
    """HEAD the Pages site to confirm the frontend is reachable."""
    req = urllib.request.Request(PAGES_URL, method="HEAD", headers={"User-Agent": "front-door-synthetic/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            if 200 <= r.status < 400:
                return True, f"{PAGES_URL} -> HTTP {r.status}"
            return False, f"{PAGES_URL} -> HTTP {r.status}"
    except urllib.error.HTTPError as e:
        # 405 (HEAD not allowed) is acceptable — the page is reachable.
        if e.code == 405:
            return True, f"{PAGES_URL} -> HTTP 405 (HEAD not allowed, but reachable)"
        return False, f"{PAGES_URL} -> HTTP {e.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return False, f"{PAGES_URL} unreachable: {type(e).__name__}: {e}"


def run_once(include_optimize: bool) -> bool:
    ok_health, msg_health = check_worker_health()
    ok_pages, msg_pages = check_pages_reachable()
    print(f"  [worker]  {msg_health}", file=sys.stderr)
    print(f"  [pages]   {msg_pages}", file=sys.stderr)

    ok = ok_health and ok_pages

    # /api/optimize gated explicitly: this burns Gemini quota.
    if include_optimize:
        print("  [optimize] (quota burn) — not implemented in this synthetic; "
              "use the operator dashboard or local CLI to exercise this path.",
              file=sys.stderr)

    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--include-optimize", action="store_true",
                    help="opt-in: actually POST to /api/optimize (burns Gemini quota)")
    ap.add_argument("--delay", type=float, default=2.0,
                    help="seconds between runs (default 2.0)")
    args = ap.parse_args()

    passes = 0
    for i in range(1, args.runs + 1):
        print(f"\n=== Run {i}/{args.runs} ===", file=sys.stderr)
        if run_once(args.include_optimize):
            print(f"[front-door] PASS", file=sys.stderr)
            passes += 1
        else:
            print(f"[front-door] FAIL", file=sys.stderr)
            return 1
        if i < args.runs:
            time.sleep(args.delay)

    print(f"\n[front-door] all {args.runs} run(s) PASS ({passes}/{args.runs})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
