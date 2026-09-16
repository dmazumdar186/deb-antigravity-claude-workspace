"""
approve.py
description: CLI counterpart of the dashboard's Previews tab approve button. Moves `previews` rows from
    `review` to `approved` (the only status besides `live` that outreach.daily_queue enqueues), logging an
    `events` row per transition, exactly like dashboard/functions/api/previews/[id]/status.ts. Used for a
    Phase 0 run without the dashboard deployed, and by scripts/run_metro.py --auto-approve (implied by --mock)
    so the mock chain exercises the queue end to end. In production a human reviews each preview first
    (.claude/rules/automation-boundaries.md: the final creative asset is human-picked); this script is that
    human's tool, not a replacement for the look.
inputs: --preview-id ID (one preview) | --metro X --all-review (every review-status, non-takedown preview
    whose business is in X and not do_not_contact). --mock, --store {local,supabase}, --store-root PATH.
outputs: `previews.status` = approved, `events` rows (entity=preview, event=status:review->approved),
    stdout JSON stat line {"script":"approve","in":n,"out":n,"dropped":{...}}.

Two paths reach `approve_preview()`, and both must stay in lockstep since it's the single place
that decides a preview is safe to link to a prospect:
  1. Human path (this script's CLI): an operator runs `preview.approve` by hand after actually
     looking at each preview in the dashboard (--preview-id) or after reviewing a whole batch
     (--metro --all-review, plus --yes-i-reviewed-them against a live Supabase store). This is the
     default, always-safe path per .claude/rules/automation-boundaries.md.
  2. Automated opt-in path (`scripts/preview_gate.py`): runs Playwright acceptance checks against
     each review-status preview's built output and, only when config.auto_approve_previews is
     `true` (default `false` — an explicit operator opt-in), calls this module's
     `approve_preview()` directly for previews that pass. A failing preview is never auto-rejected
     by that path — it stays in `review` with a `gate_failed` event so a human still looks. With
     `auto_approve_previews` left at its default, preview_gate.py only records gate results and
     changes no preview's status; the daily workflow runs it after every metro so results are never
     more than a day stale, but a human still has to flip the config (or approve manually) before
     anything moves.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))  # repo root, for direct-script execution

from execution.personal_workflows.prodcraft_medspa.common import config, notify  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.common.store import Store, get_store  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.scripts._stage_runner import (  # noqa: E402
    reject_mock_with_supabase,
)

APPROVABLE_FROM = ("review",)


def approve_preview(store: Store, preview: dict, *, actor: str) -> str | None:
    """Approve one preview row. Returns None on success, else a drop_reason string (nothing is silent)."""
    status = preview.get("status")
    if preview.get("takedown"):
        return "takedown"
    if status == "approved":
        return "already_approved"
    if status not in APPROVABLE_FROM:
        return f"status_{status}"
    business = store.get_business(preview["business_id"]) if preview.get("business_id") else None
    if business and business.get("do_not_contact"):
        return "do_not_contact"
    store.update_preview(preview["id"], {"status": "approved"})
    store.log_event(
        "preview",
        preview["id"],
        "status:review->approved",
        {"actor": actor, "host": (preview.get("subdomain_url") or "").replace("https://", "")},
    )
    return None


def candidates_for_metro(store: Store, metro: str) -> list[dict]:
    business_ids = {b["id"] for b in store.find_businesses(metro=metro)}
    rows = store.list_rows("previews", status="review")
    # takedown rows are kept as candidates so approve_preview() reports them as a drop, never a silent skip
    return [p for p in rows if p.get("business_id") in business_ids]


def run(store: Store, *, preview_id: str | None, metro: str | None, actor: str) -> dict:
    if preview_id:
        row = store.get_row("previews", preview_id)
        targets = [row] if row else []
        if not row:
            return {"script": "approve", "in": 0, "out": 0, "dropped": {"not_found": 1}, "preview_ids": []}
    else:
        targets = candidates_for_metro(store, metro or "")

    dropped: dict[str, int] = {}
    approved_ids: list[str] = []
    for preview in targets:
        reason = approve_preview(store, preview, actor=actor)
        if reason:
            dropped[reason] = dropped.get(reason, 0) + 1
        else:
            approved_ids.append(preview["id"])
    return {"script": "approve", "in": len(targets), "out": len(approved_ids), "dropped": dropped, "preview_ids": approved_ids}


def main(argv: list[str] | None = None) -> None:
    config.bootstrap()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--preview-id", default=None)
    target.add_argument("--metro", default=None, help="approve every review-status preview in this metro (needs --all-review)")
    parser.add_argument("--all-review", action="store_true", help="required with --metro: confirms the bulk approve")
    parser.add_argument("--actor", default="cli", help="recorded in the events payload (cli|run_metro|dashboard)")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--store", choices=["local", "supabase"], default=None)
    parser.add_argument("--store-root", dest="store_root", default=None)
    parser.add_argument(
        "--yes-i-reviewed-them",
        dest="yes_i_reviewed_them",
        action="store_true",
        help="Required in addition to --all-review for a LIVE bulk approve (--metro against a "
        "Supabase store): confirms a human actually reviewed every preview about to be approved. "
        "Not required against a local store. run_metro.py never passes this flag — its own "
        "--auto-approve is local-store only, so it can never trigger a live bulk approve here.",
    )
    args = parser.parse_args(argv)

    if args.metro and not args.all_review:
        parser.error("--metro requires --all-review (bulk approve is deliberate, not a default)")

    store_kind = reject_mock_with_supabase(parser, args)
    if args.metro and store_kind == "supabase" and not args.yes_i_reviewed_them:
        parser.error(
            "a live bulk approve (--metro against --store supabase) also requires "
            "--yes-i-reviewed-them — this is deliberate friction so run_metro's automated "
            "--auto-approve (local-store only) can never reach a live approve through this path"
        )
    store = get_store(kind=store_kind, root=args.store_root)
    try:
        stat = run(store, preview_id=args.preview_id, metro=args.metro, actor=args.actor)
    except Exception as exc:  # noqa: BLE001 — top-level error channel per CONTRACTS.md
        notify.error("preview.approve", f"{type(exc).__name__}: {exc}", count=1)
        raise
    print(json.dumps(stat))


if __name__ == "__main__":
    main()
