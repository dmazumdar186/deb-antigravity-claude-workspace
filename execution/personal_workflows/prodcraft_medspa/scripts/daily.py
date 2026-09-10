"""
daily.py
description: The operator's morning command. Runs outreach.advance -> outreach.scan_replies ->
    preview.takedown (for any business scan_replies flags for takedown) -> outreach.daily_queue
    --create-drafts, and prints the resulting queue. Each stage is a subprocess CLI per
    CONTRACTS.md; a missing module (another agent's package not built yet in this checkout) is a
    reported stage failure, not a crash.
inputs: CLI: [--date D] [--mock] [--store {local,supabase}] [--store-root P] [--replies-only]
    [--phase0-status]. Env: whatever the invoked stage subprocesses need (unset is fine with --mock).
outputs: stdout: per-stage results + the daily queue (or the phase0 gate state with
    --phase0-status); common.notify.error("daily", ...) on any stage failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from execution.personal_workflows.prodcraft_medspa.common import notify  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.common.store import get_store  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.scripts._stage_runner import (  # noqa: E402
    common_store_args,
    run_module,
)


def _extract_takedown_ids(scan_stat: dict[str, Any] | None) -> list[str]:
    """Best-effort extraction of business ids scan_replies flagged for takedown.

    Assumption (outreach.scan_replies is another agent's package and its exact stat shape is not
    fixed by CONTRACTS.md beyond the {"script", "in", "out", "dropped"} minimum): a top-level
    "takedowns" list of business ids, falling back to `dropped.takedown` if scan_replies instead
    reports it as a drop-reason bucket. Absence of either key means "no takedowns this run", not
    an error.
    """
    if not scan_stat:
        return []
    if isinstance(scan_stat.get("takedowns"), list):
        return [str(x) for x in scan_stat["takedowns"]]
    dropped = scan_stat.get("dropped")
    if isinstance(dropped, dict) and isinstance(dropped.get("takedown"), list):
        return [str(x) for x in dropped["takedown"]]
    return []


def run_step(name: str, module: str, args: list[str]) -> dict[str, Any]:
    print(f"\n=== {name} ===", file=sys.stderr)
    result = run_module(module, args)
    if result["ok"]:
        print(f"[daily] {name} OK: {json.dumps(result['stat'])}", file=sys.stderr)
    else:
        msg = f"step '{name}' ({module}) failed: {result['error']}"
        print(f"[daily] {msg}", file=sys.stderr)
        notify.error("daily", msg, count=1)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=None, help="YYYY-MM-DD, default today")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--store", choices=["local", "supabase"], default=None)
    parser.add_argument("--store-root", dest="store_root", default=None)
    parser.add_argument(
        "--replies-only",
        action="store_true",
        help="advance + scan_replies + takedowns only, no drafts (used by the 30-minute cron)",
    )
    parser.add_argument("--phase0-status", action="store_true", help="print the phase0 gate state and exit")
    args = parser.parse_args()

    store = get_store(kind=args.store, root=args.store_root) if args.store_root else get_store(kind=args.store)

    if args.phase0_status:
        phase0 = store.get_config("phase0", default={})
        print(json.dumps({"script": "daily", "phase0": phase0}, indent=2))
        return

    run_date = args.date or date.today().isoformat()
    base = ["--date", run_date] + common_store_args(args)
    results: list[dict[str, Any]] = []

    advance_result = run_step("advance", "outreach.advance", base)
    results.append(advance_result)

    scan_result = run_step("scan_replies", "outreach.scan_replies", common_store_args(args))
    results.append(scan_result)

    takedown_ids = _extract_takedown_ids(scan_result.get("stat"))
    for business_id in takedown_ids:
        td_result = run_step(
            f"takedown({business_id})",
            "preview.takedown",
            ["--business-id", business_id] + common_store_args(args),
        )
        results.append(td_result)
    if not takedown_ids:
        print("[daily] no takedowns flagged by scan_replies this run", file=sys.stderr)

    queue_result: dict[str, Any] | None = None
    if not args.replies_only:
        queue_result = run_step(
            "daily_queue",
            "outreach.daily_queue",
            ["--date", run_date, "--create-drafts"] + common_store_args(args),
        )
        results.append(queue_result)
        print("\n--- daily_queue output ---")
        print(queue_result["stdout"].strip() or "(no output)")

    any_failed = any(not r["ok"] for r in results)
    print(
        json.dumps(
            {
                "script": "daily",
                "date": run_date,
                "replies_only": args.replies_only,
                "takedowns_run": len(takedown_ids),
                "any_failed": any_failed,
            }
        )
    )

    if any_failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
