"""
daily.py
description: The operator's morning command. Runs outreach.advance -> outreach.scan_replies ->
    preview.takedown (for any business scan_replies flags for takedown) -> outreach.daily_queue
    --create-drafts -> outreach.send, and prints the resulting queue + send stat. Sending is
    automated per the operator's 2026-09-16 decision (no human in the loop until a prospect
    replies positive or neutral); pass --no-send to keep the old draft-only behaviour. Each stage
    is a subprocess CLI per CONTRACTS.md; a missing module (another agent's package not built yet
    in this checkout) is a reported stage failure, not a crash. After the store is opened,
    common.config_validate.assert_valid_config() runs over the live config (same key subset as
    scripts/run_metro.py's own check) — an invalid value exits 1 with common.notify.error("daily",
    ...) before any stage runs (round-2 audit item 8).
inputs: CLI: [--date D] [--mock] [--store {local,supabase}] [--store-root P] [--replies-only]
    [--phase0-status] [--no-send] [--recipient-override EMAIL] [--limit N]. Env: whatever the
    invoked stage subprocesses need (unset is fine with --mock); PRODCRAFT_RECIPIENT_OVERRIDE is
    read by outreach.send itself if --recipient-override is not passed.
outputs: stdout: per-stage results + the daily queue + the send stat (or the phase0 gate state
    with --phase0-status); common.notify.error("daily", ...) on any stage failure.
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
from execution.personal_workflows.prodcraft_medspa.common.config_validate import assert_valid_config  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.common.store import get_store  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.outreach import state_machine  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.scripts._stage_runner import (  # noqa: E402
    common_store_args,
    reject_mock_with_supabase,
    run_module,
)


def _build_validation_cfg(store: Any) -> dict[str, Any]:
    """item 8 (round-2 audit): the same subset of `config` keys
    scripts/run_metro.py's build_validation_cfg() assembles — daily.py owns its own copy rather
    than importing run_metro.py (a sibling CLI script, not a shared library module) purely to
    validate config before running today's stages. Missing keys resolve to None (get_config's own
    default), which config_validate.validate_config() treats as "not configured" and never flags."""
    return {
        "queue_pick": store.get_config("queue_pick"),
        "email_policy": store.get_config("email_policy"),
        "preview_publish_mode": store.get_config("preview_publish_mode"),
        "min_score": store.get_config("min_score"),
        "live_send_confirmed": store.get_config("live_send_confirmed"),
        "preview_host_suffix": store.get_config("preview_host_suffix"),
        "auto_approve_previews": store.get_config("auto_approve_previews"),
        "phase0": store.get_config("phase0"),
    }


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
    parser.add_argument(
        "--no-send",
        action="store_true",
        help="stop after daily_queue --create-drafts; skip outreach.send (pre-2026-09-16 draft-only behaviour)",
    )
    parser.add_argument(
        "--recipient-override",
        dest="recipient_override",
        default=None,
        help="passed through to outreach.send: send every message to this address instead of owner_email",
    )
    parser.add_argument("--limit", type=int, default=None, help="passed through to outreach.send")
    args = parser.parse_args()

    store_kind = reject_mock_with_supabase(parser, args)
    store = get_store(kind=store_kind, root=args.store_root)

    # item 8 (round-2 audit): fail loudly on a mistyped/out-of-range config value before running
    # any stage, rather than letting it silently degrade a stage hours into the morning run.
    try:
        assert_valid_config(_build_validation_cfg(store))
    except ValueError as exc:
        print(f"[daily] {exc}", file=sys.stderr)
        notify.error("daily", f"invalid config: {exc}", 1)
        sys.exit(1)

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

    # item 10 (round-3 critical, trust lens): runs after EVERY scan pass, --replies-only included
    # — catches a business that is do_not_contact/closed_lost but whose preview was never
    # actually taken down (a takedown call that failed, a crash mid-flow, a manual patch that
    # bypassed state_machine). This is a sweep, not a per-business step, so failures inside it are
    # reported (notify.once_per_day, per preview) but never abort the rest of daily.py's run.
    try:
        reconcile_stat = state_machine.reconcile_takedowns(store, mock=args.mock)
        print(f"[daily] reconcile_takedowns: {json.dumps(reconcile_stat)}", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 — a reconcile failure must not abort the rest of daily.py
        print(f"[daily] reconcile_takedowns failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        notify.error("daily.reconcile_takedowns", f"{type(exc).__name__}: {exc}", 1)

    queue_result: dict[str, Any] | None = None
    send_result: dict[str, Any] | None = None
    if not args.replies_only:
        queue_result = run_step(
            "daily_queue",
            "outreach.daily_queue",
            ["--date", run_date, "--create-drafts"] + common_store_args(args),
        )
        results.append(queue_result)
        print("\n--- daily_queue output ---")
        print(queue_result["stdout"].strip() or "(no output)")

        if not args.no_send:
            send_args = ["--date", run_date] + common_store_args(args)
            if args.recipient_override:
                send_args += ["--recipient-override", args.recipient_override]
            if args.limit is not None:
                send_args += ["--limit", str(args.limit)]
            send_result = run_step("send", "outreach.send", send_args)
            results.append(send_result)
            print("\n--- send output ---")
            # item 20 (round-3, pipeline-auditor lens): send.py's RECIPIENT OVERRIDE banner,
            # its "bypasses the preview-host guard" WARNING, and any "SEND BLOCKED: ..." line
            # are all printed to stdout, not carried in the final JSON `stat` line — printing
            # only `stat` (as this used to) silently dropped every one of those from the cron
            # log. Print the full captured stdout the same way the daily_queue step above does.
            print(send_result["stdout"].strip() or "(no output)")

    any_failed = any(not r["ok"] for r in results)
    # send_result is None when --replies-only/--no-send skipped the step, and its "stat" is None
    # when outreach.send printed no final JSON line (e.g. an argparse error on a bad --date).
    send_stat = (send_result or {}).get("stat") or {}
    print(
        json.dumps(
            {
                "script": "daily",
                "date": run_date,
                "replies_only": args.replies_only,
                "no_send": args.no_send,
                "takedowns_run": len(takedown_ids),
                "sent": send_stat.get("sent"),
                # outreach.send.py's C2 live-send-gate fields, passed through so a caller reading
                # only daily.py's own final line (not the "--- send output ---" block above) can
                # still tell a dry-run from a live-recipient run.
                "recipient_override": send_stat.get("recipient_override"),
                "live_recipients": send_stat.get("live_recipients"),
                "any_failed": any_failed,
            }
        )
    )

    if any_failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
