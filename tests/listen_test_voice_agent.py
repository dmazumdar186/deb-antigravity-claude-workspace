"""
description: Operator-facing listen-test helper for the Vapi dental voice agent. Opens the live
widget in the default browser, waits for the operator to complete a call, then pulls that call
from the Vapi REST API and grades it through the same audit_vapi_calls.py rules. Returns the
verdict + transcript so the operator can verify v0.4.0 end-to-end in one command.

This closes gap #1 from the 2026-06-27 13:20 incident handoff: there was no automation that
let the operator drive a real call and get a structured verdict without manually pulling logs.

inputs (env, from .env):
    VAPI_API_KEY          required
    VAPI_ASSISTANT_ID     required
    WORKER_URL            optional (default https://vapi-dental-fr.debanjan186.workers.dev)

CLI:
    --no-browser          skip auto-opening the widget (useful when the operator already has it open)
    --wait-seconds N      max seconds to wait for a new call (default 300 = 5 min)
    --poll-interval N     seconds between polls (default 10)

outputs:
    stdout: open-browser line, then a live transcript dump + audit verdict
    exit code: 0 if the captured call passes, 1 if it fails the audit, 2 if no call captured
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    # Stream may not support reconfigure on all platforms. Output is best-effort cosmetic.
    pass

try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_vapi_calls import grade_call, fetch_calls  # type: ignore[import-not-found]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--wait-seconds", type=int, default=300)
    ap.add_argument("--poll-interval", type=int, default=10)
    args = ap.parse_args()

    api_key = os.environ.get("VAPI_API_KEY")
    assistant_id = os.environ.get("VAPI_ASSISTANT_ID")
    worker_url = os.environ.get("WORKER_URL", "https://vapi-dental-fr.debanjan186.workers.dev")

    if not api_key or not assistant_id:
        print("VAPI_API_KEY and VAPI_ASSISTANT_ID required", file=sys.stderr)
        return 2

    # 1. Snapshot a baseline wall-clock; new calls must have startedAt > this.
    #    (call_id alone is unreliable: fetch_calls returns the top N by recency, so
    #    polling can resurface an older call as "different from baseline_id".)
    baseline = datetime.now(timezone.utc)
    print(f"baseline timestamp: {baseline.isoformat()}")

    # 2. Open the widget.
    if not args.no_browser:
        print(f"opening widget: {worker_url}")
        webbrowser.open(worker_url)
    else:
        print(f"please open the widget yourself: {worker_url}")
    print()
    print(">> place a test call now: book a consultation, give a name, dictate digits, pick a slot.")
    print(f">> waiting up to {args.wait_seconds}s for a new call to land in Vapi history...")
    print()

    # 3. Poll for a new call.
    deadline = time.time() + args.wait_seconds
    new_call = None
    while time.time() < deadline:
        try:
            calls = fetch_calls(api_key, assistant_id, 3)
        except urllib.error.HTTPError as exc:
            print(f"  (poll error: HTTP {exc.code})", file=sys.stderr)
            time.sleep(args.poll_interval)
            continue
        for c in calls:
            started = c.get("startedAt")
            if not started:
                continue
            try:
                t = datetime.fromisoformat(started.replace("Z", "+00:00"))
            except ValueError:
                continue
            if t > baseline and (c.get("status") in ("ended", "completed")
                                  or c.get("endedReason")):
                new_call = c
                break
        if new_call:
            break
        remaining = int(deadline - time.time())
        print(f"  ...no new call yet ({remaining}s left)")
        time.sleep(args.poll_interval)

    if not new_call:
        print("\nno new call captured within window. exit 2.")
        return 2

    # 4. Grade.
    print()
    print(f"captured call_id={new_call.get('id')}")
    print(f"  startedAt={new_call.get('startedAt')}")
    print(f"  endedAt  ={new_call.get('endedAt')}")
    print(f"  endedReason={new_call.get('endedReason')}")
    print()
    print("transcript:")
    print(new_call.get("transcript") or "(no transcript)")
    print()

    verdict = grade_call(new_call)
    print(f"audit verdict: {verdict['severity']}")
    for f in verdict["findings"]:
        print(f"  - {f}")
    print()
    if verdict["severity"] == "FAIL":
        print("FAIL -- this call would not pass production gate. See findings above.")
        return 1
    if verdict["severity"] == "WARN":
        print("WARN -- caller experience degraded; not blocking but investigate.")
        return 0
    print("PASS -- call meets production gate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
