"""
daily_queue.py
description: Build and print today's manual-send outreach queue — enqueue new touch-1 rows,
    select today's capped queue (Phase 0 gate + bounce-rate halt), generate + lint drafts, and
    optionally create Gmail drafts.
inputs: CLI: [--date YYYY-MM-DD] [--mock] [--store {local,supabase}] [--store-root PATH]
    [--create-drafts] [--variant a|b|c|auto].
outputs: stdout: the queue table, then a JSON stat line:
    {"script":"daily_queue","date":...,"cap":n,"halted":bool,"enqueued":n,"queued_today":n,
    "drafted":n,"lint_failed":n,"gmail_drafts":n,"llm_cost_usd":x}. Store mutations: new
    touch-1 outreach rows, draft_subject/draft_body/template_variant patches, status
    queued->drafted, gmail_draft_id patches.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from execution.personal_workflows.prodcraft_medspa.common import config, store as store_mod  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.outreach import (  # noqa: E402
    _store_helpers,
    draft_email,
    gmail_drafts,
    lint_draft,
    state_machine,
)

BOUNCE_WINDOW_DAYS = 30
BOUNCE_RATE_HALT = 0.02
DEFAULT_PHASE0 = {"passed": False, "sends": 0, "calls_booked": 0, "queue_cap_locked": 5, "queue_cap_open": 20}


def _parse_date(value: str | None) -> date:
    if not value:
        return date.today()
    return datetime.strptime(value, "%Y-%m-%d").date()


def enqueue_new_touch1(st: Any, today: date) -> int:
    """Enqueue touch-1 rows for every business with an approved/live preview, a deliverable
    email, not do_not_contact, and no outreach row yet."""
    businesses = {
        b["id"]: b for b in st.find_businesses(do_not_contact=False, has_email=True) if not b.get("is_chain")
    }
    existing_touch1_business_ids = {
        r["business_id"] for r in _store_helpers.list_all(st, "outreach") if int(r.get("touch") or 0) == 1
    }

    latest_eligible_preview: dict[str, dict] = {}
    for p in _store_helpers.list_all(st, "previews"):
        if p.get("business_id") not in businesses:
            continue
        if p.get("status") not in ("approved", "live") or p.get("takedown"):
            continue
        current = latest_eligible_preview.get(p["business_id"])
        if current is None or (p.get("created_at") or "") > (current.get("created_at") or ""):
            latest_eligible_preview[p["business_id"]] = p

    enqueued = 0
    for business_id, business in businesses.items():
        if business_id in existing_touch1_business_ids:
            continue
        preview = latest_eligible_preview.get(business_id)
        if not preview:
            continue
        audit = st.latest_audit(business_id)
        if not audit:
            continue
        gaps = audit.get("gaps") or []
        gap_primary = gaps[0]["signal"] if gaps else None

        st.upsert_outreach(
            {
                "business_id": business_id,
                "preview_id": preview["id"],
                "audit_id": audit["id"],
                "touch": 1,
                "status": "queued",
                "next_touch_at": today.isoformat(),
                "gap_primary": gap_primary,
            }
        )
        st.log_event("business", business_id, "outreach_enqueued", {"touch": 1})
        enqueued += 1
    return enqueued


def _queue_cap(st: Any) -> int:
    phase0 = st.get_config("phase0", DEFAULT_PHASE0) or DEFAULT_PHASE0
    return int(phase0.get("queue_cap_open", 20)) if phase0.get("passed") else int(phase0.get("queue_cap_locked", 5))


def halt_reason(st: Any, today: date) -> str | None:
    """Rolling BOUNCE_WINDOW_DAYS bounce rate over BOUNCE_RATE_HALT halts the queue."""
    window_start = today - timedelta(days=BOUNCE_WINDOW_DAYS)
    sent_rows = []
    for r in _store_helpers.list_all(st, "outreach"):
        sent_at = r.get("sent_at")
        if not sent_at:
            continue
        try:
            sent_date = datetime.fromisoformat(str(sent_at).replace("Z", "+00:00")).date()
        except ValueError:
            continue
        if sent_date >= window_start:
            sent_rows.append(r)

    if not sent_rows:
        return None
    bounces = sum(1 for r in sent_rows if r.get("reply_sentiment") == "bounce")
    rate = bounces / len(sent_rows)
    if rate > BOUNCE_RATE_HALT:
        return (
            f"bounce rate {rate:.1%} ({bounces}/{len(sent_rows)}) over trailing "
            f"{BOUNCE_WINDOW_DAYS} days exceeds {BOUNCE_RATE_HALT:.0%} threshold"
        )
    return None


def _print_table(rows: list[dict], st: Any) -> None:
    header = f"{'business':<28} {'owner':<14} {'touch':<5} {'score':<5} {'gap':<28} preview"
    print(header)
    print("-" * len(header))
    for row in rows:
        business = st.get_business(row.get("business_id")) or {}
        audit = st.latest_audit(row.get("business_id")) or {}
        print(
            f"{(business.get('name') or '')[:28]:<28} "
            f"{(business.get('owner_first') or 'there')[:14]:<14} "
            f"{row.get('touch', ''):<5} "
            f"{audit.get('total_score', ''):<5} "
            f"{(row.get('gap_primary') or '')[:28]:<28} "
            f"{row.get('draft_subject') and '(has preview link in body)' or ''}"
        )


def run_daily_queue(
    st: Any,
    settings: Any,
    *,
    today: date,
    mock: bool,
    create_drafts: bool,
    variant: str,
) -> dict:
    enqueued = enqueue_new_touch1(st, today)

    halted = halt_reason(st, today)
    if halted:
        print(f"QUEUE HALTED: {halted}")
        return {
            "script": "daily_queue",
            "date": today.isoformat(),
            "cap": _queue_cap(st),
            "halted": True,
            "enqueued": enqueued,
            "queued_today": 0,
            "drafted": 0,
            "lint_failed": 0,
            "gmail_drafts": 0,
            "llm_cost_usd": 0.0,
        }

    cap = _queue_cap(st)
    selected = st.queue(today, cap)

    drafted = 0
    lint_failed = 0
    llm_cost_usd = 0.0

    for row in selected:
        if row.get("status") != "queued" or row.get("draft_subject"):
            continue

        business = st.get_business(row["business_id"])
        if not business:
            continue
        audit_row = st.latest_audit(row["business_id"])
        preview_row = None
        if row.get("preview_id"):
            for p in _store_helpers.previews_for_business(st, row["business_id"]):
                if p.get("id") == row.get("preview_id"):
                    preview_row = p
                    break

        rendered = draft_email.render_draft(
            st,
            settings,
            outreach_row=row,
            business=business,
            audit_row=audit_row,
            preview_row=preview_row,
            variant=variant,
            mock=mock,
        )
        if rendered.get("llm"):
            llm_cost_usd += rendered["llm"].get("cost_usd", 0.0)

        sender = st.get_config("sender", {"name": "", "physical_address": "", "signature": ""}) or {}
        lint_result = lint_draft.lint(
            rendered["subject"],
            rendered["body"],
            touch=int(row.get("touch") or 1),
            sender_name=sender.get("name"),
            sender_physical_address=sender.get("physical_address"),
        )

        patch = {
            "draft_subject": rendered["subject"],
            "draft_body": rendered["body"],
            "template_variant": rendered.get("variant"),
        }

        if lint_result["violations"]:
            lint_failed += 1
            patch["notes"] = json.dumps({"lint_violations": lint_result["violations"]})
            st.update_outreach(row["id"], patch)
            st.log_event("outreach", row["id"], "lint_failed", {"violations": lint_result["violations"]})
            continue

        if lint_result.get("needs_operator_input"):
            patch["notes"] = json.dumps({"needs_operator_input": True})

        st.update_outreach(row["id"], patch)
        row.update(patch)
        state_machine.transition(st, {**row, "status": "queued"}, "drafted")
        row["status"] = "drafted"
        drafted += 1

    gmail_draft_count = 0
    if create_drafts:
        for row in selected:
            if row.get("status") != "drafted" or row.get("gmail_draft_id"):
                continue
            business = st.get_business(row["business_id"])
            if not business or not business.get("owner_email"):
                continue
            sender = st.get_config("sender", {}) or {}
            result = gmail_drafts.create_draft(
                to_email=business["owner_email"],
                subject=row.get("draft_subject") or "",
                body=row.get("draft_body") or "",
                sender_name=sender.get("name") or "",
                settings=settings,
                mock=mock,
                business_id=business["id"],
            )
            st.update_outreach(row["id"], {"gmail_draft_id": result["gmail_draft_id"]})
            gmail_draft_count += 1

    _print_table(selected, st)

    return {
        "script": "daily_queue",
        "date": today.isoformat(),
        "cap": cap,
        "halted": False,
        "enqueued": enqueued,
        "queued_today": len(selected),
        "drafted": drafted,
        "lint_failed": lint_failed,
        "gmail_drafts": gmail_draft_count,
        "llm_cost_usd": round(llm_cost_usd, 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and print today's manual-send outreach queue")
    parser.add_argument("--date", default=None)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--store", choices=["local", "supabase"], default=None)
    parser.add_argument("--store-root", default=None)
    parser.add_argument("--create-drafts", action="store_true")
    parser.add_argument("--variant", choices=["a", "b", "c", "auto"], default="auto")
    args = parser.parse_args()

    settings = config.bootstrap()
    store_kind = args.store or ("local" if args.mock else settings.store_kind)
    st = store_mod.get_store(kind=store_kind, root=args.store_root)
    today = _parse_date(args.date)

    try:
        stats = run_daily_queue(
            st,
            settings,
            today=today,
            mock=args.mock,
            create_drafts=args.create_drafts,
            variant=args.variant,
        )
    except Exception as exc:  # noqa: BLE001 — top-level failure must reach the error channel
        from execution.personal_workflows.prodcraft_medspa.common import notify

        notify.error("prodcraft_medspa.daily_queue", f"{type(exc).__name__}: {exc}")
        raise

    print(json.dumps(stats))


if __name__ == "__main__":
    main()
