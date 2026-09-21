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
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from execution.personal_workflows.prodcraft_medspa.common import config, config_validate, store as store_mod  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.outreach import (  # noqa: E402
    _store_helpers,
    draft_email,
    gmail_drafts,
    lint_draft,
    state_machine,
)
from execution.personal_workflows.prodcraft_medspa.scripts._stage_runner import (  # noqa: E402
    reject_mock_with_supabase,
)

BOUNCE_WINDOW_DAYS = 30
BOUNCE_RATE_HALT = 0.02
DEFAULT_PHASE0 = {
    "passed": False,
    "sends": 0,
    "calls_booked": 0,
    "queue_cap_locked": 5,
    "queue_cap_open": 20,
    "queue_pick_until_passed": "score",
}


def _parse_date(value: str | None) -> date:
    if not value:
        return date.today()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        # one-line usage error instead of a traceback surfacing through daily.py's stderr
        raise SystemExit(f"--date must be YYYY-MM-DD, got {value!r}") from None


def _score_for_business(st: Any, business_id: str) -> float:
    audit = st.latest_audit(business_id)
    return float((audit or {}).get("total_score") or 0)


def _pick_mode(st: Any) -> str:
    """Effective queue-pick strategy (round-2 audit item 4). While `config.phase0.passed` is
    False, ALWAYS use `config.phase0.queue_pick_until_passed` (default "score") regardless of
    `config.queue_pick` — Phase 0 (validating the pipeline against real replies) must not drift
    into a low-signal random sample just because the operator's steady-state preference is
    "random". Once phase0 has passed, `config.queue_pick` governs as before. Matches the contract
    already documented under "Outreach state machine" in CONTRACTS.md."""
    phase0 = st.get_config("phase0", DEFAULT_PHASE0) or DEFAULT_PHASE0
    if not phase0.get("passed"):
        return str(phase0.get("queue_pick_until_passed", "score") or "score").strip().lower()
    return str(st.get_config("queue_pick", "random") or "random").strip().lower()


def _ordered_new_touch1_candidates(st: Any, businesses: dict, today: date) -> list[dict]:
    """Order businesses eligible for a new touch-1 enqueue per the effective pick mode
    (`_pick_mode` — `config.phase0.queue_pick_until_passed` until phase0 passes, then
    `config.queue_pick`).

    `"score"` orders by latest audit total_score desc (the old implicit behaviour). `"random"`
    shuffles per metro with `random.Random(f"{today}:{metro}")` so a rerun on the same
    date reproduces the identical order/selection (idempotent) — the operator wants ~5 random
    picks per day rather than always the same highest-score businesses. This ordering only
    matters when there are more eligible candidates than the daily cap: `enqueue_new_touch1`
    itself enqueues every eligible business (uncapped), but insertion order here becomes the
    `created_at` tie-break `LocalStore.queue()`/`SupabaseStore.queue()` use to pick today's
    capped batch.
    """
    pick_mode = _pick_mode(st)
    rows = list(businesses.values())
    if pick_mode == "score":
        rows.sort(key=lambda b: _score_for_business(st, b["id"]), reverse=True)
        return rows

    by_metro: dict[str, list[dict]] = {}
    for b in rows:
        by_metro.setdefault(b.get("metro") or "", []).append(b)
    ordered: list[dict] = []
    for metro in sorted(by_metro):
        group = by_metro[metro]
        random.Random(f"{today.isoformat()}:{metro}").shuffle(group)
        ordered.extend(group)
    return ordered


def _email_policy(st: Any) -> str:
    return str(st.get_config("email_policy", "deliverable_only") or "deliverable_only")


def _has_email_filter(st: Any):
    """Store-level prefilter: only `deliverable` matches has_email=True, so under allow_unverified the
    prefilter is dropped and `_email_ok` decides per business (mirrors preview/build_preview.py)."""
    return None if _email_policy(st) == "allow_unverified" else True


def _email_ok(st: Any, business: dict) -> bool:
    allowed = ("deliverable", "unverified") if _email_policy(st) == "allow_unverified" else ("deliverable",)
    return bool(business.get("owner_email")) and business.get("email_status") in allowed


def _enqueue_seed(pick_mode: str, today: date, business: dict) -> str | None:
    """The exact seed string `_ordered_new_touch1_candidates` used to order this business's
    metro group, for research-lens auditability on the `outreach_enqueued` event (item 9).
    `None` under `"score"` mode, which has no randomness to seed."""
    if pick_mode != "random":
        return None
    return f"{today.isoformat()}:{business.get('metro') or ''}"


def enqueue_new_touch1(st: Any, today: date) -> int:
    """Enqueue touch-1 rows for every business with an approved/live preview, a deliverable
    email, not do_not_contact, and no outreach row yet. Enqueue order follows `config.queue_pick`
    (see `_ordered_new_touch1_candidates`)."""
    pick_mode = _pick_mode(st)
    raw_queue_pick = (st.get_config("queue_pick", "random") or "random").strip().lower()
    businesses = {
        b["id"]: b
        for b in st.find_businesses(do_not_contact=False, has_email=_has_email_filter(st))
        if not b.get("is_chain") and _email_ok(st, b)
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
    for business in _ordered_new_touch1_candidates(st, businesses, today):
        business_id = business["id"]
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
                # item 5 (round-2 audit): the audit total_score AT ENQUEUE TIME — a score can
                # drift (re-audit, manual patch) between queueing and sending, so a later read of
                # `total_score` off the latest audit isn't necessarily what this row was queued
                # on. Column added by migration 0004; this is the write side.
                "score_at_send": audit.get("total_score"),
                # item 16 (round-3, Sutskever lens): previously stamped only on the
                # outreach_enqueued event, unreadable by fit_weights.py without a store/events
                # join. Column added by migration 0005; this is the write side.
                "queue_pick_effective": pick_mode,
            }
        )
        st.log_event(
            "business",
            business_id,
            "outreach_enqueued",
            {
                "touch": 1,
                # item 4: `queue_pick` is the raw config value (what the operator configured);
                # `queue_pick_effective` is what actually governed THIS enqueue (may differ from
                # `queue_pick` while phase0 hasn't passed yet — see _pick_mode()).
                "queue_pick": raw_queue_pick,
                "queue_pick_effective": pick_mode,
                "seed": _enqueue_seed(pick_mode, today, business),
            },
        )
        enqueued += 1
    return enqueued


def _queue_cap(st: Any) -> int:
    phase0 = st.get_config("phase0", DEFAULT_PHASE0) or DEFAULT_PHASE0
    return int(phase0.get("queue_cap_open", 20)) if phase0.get("passed") else int(phase0.get("queue_cap_locked", 5))


def _first_live_send_date(st: Any) -> date | None:
    """Earliest `sent` outreach row with no `test_recipient` (round-2 audit item 3) — the
    operator's own dry-run sends to their inbox never count as the warmup ramp's day zero."""
    earliest: date | None = None
    for r in _store_helpers.list_all(st, "outreach"):
        if r.get("status") != "sent" or r.get("test_recipient"):
            continue
        sent_at = r.get("sent_at")
        if not sent_at:
            continue
        try:
            d = datetime.fromisoformat(str(sent_at).replace("Z", "+00:00")).date()
        except ValueError:
            continue
        if earliest is None or d < earliest:
            earliest = d
    return earliest


def effective_cap(st: Any, today: date, mock: bool = False) -> int:
    """Round-2 audit item 3: the Phase-0 warmup ramp. Effective cap = min(phase0.cap,
    phase0.warmup_start_cap + floor(days_since_first_live_send * (cap - start_cap) /
    warmup_days)); before any live send, the cap is `phase0.warmup_start_cap`.

    `--mock` (and any run passing `mock=True`) is NEVER subject to the ramp — it returns the
    plain `phase0.cap` (falling back to `_queue_cap()`'s locked/open value when `phase0.cap`
    isn't configured), so the mock chain's day-one DoD (4 sends) is unaffected. Dry-run rows
    (`test_recipient` set) are excluded from "first live send" by `_first_live_send_date` so an
    operator dry-run to their own inbox never starts the ramp clock. Used by both
    `run_daily_queue` (drafting cap) and `outreach/send.py` (sending cap) — printed as `cap` in
    both scripts' stat lines.
    """
    phase0 = st.get_config("phase0", DEFAULT_PHASE0) or DEFAULT_PHASE0
    cap = int(phase0.get("cap") or _queue_cap(st))
    if mock:
        return cap

    start_cap = int(phase0.get("warmup_start_cap", config_validate.PHASE0_WARMUP_START_CAP_DEFAULT))
    warmup_days = int(phase0.get("warmup_days", config_validate.PHASE0_WARMUP_DAYS_DEFAULT))

    first_live = _first_live_send_date(st)
    if first_live is None:
        return min(cap, start_cap)
    if warmup_days <= 0:
        return cap

    days_since = max(0, (today - first_live).days)
    ramped = start_cap + (days_since * (cap - start_cap)) // warmup_days
    return max(start_cap, min(cap, ramped))


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


def _notes_dict(row: dict) -> dict:
    notes = row.get("notes")
    if isinstance(notes, str):
        try:
            notes = json.loads(notes)
        except ValueError:
            return {}
    return notes if isinstance(notes, dict) else {}


def _lint_failed_before(row: dict) -> bool:
    return bool(_notes_dict(row).get("lint_violations"))


# item 2 (round-3 critical): after this many consecutive lint failures a row stops being
# re-selected every day (it would otherwise eat the whole warmup cap forever, starving fresh
# businesses out of ever being drafted) and instead waits for an operator to look at it.
LINT_FAIL_LIMIT = 3


def _needs_operator_input(row: dict) -> bool:
    """True while a row is parked for the operator. The flag self-clears for the render path once
    the missing input has been supplied (notes.loom_url set) unless the row is also parked for
    LINT_FAIL_LIMIT consecutive lint failures; a successful re-render then writes it False."""
    notes = _notes_dict(row)
    if not notes.get("needs_operator_input"):
        return False
    lint_parked = int(notes.get("lint_fail_count") or 0) >= LINT_FAIL_LIMIT
    if notes.get("loom_url") and not lint_parked:
        return False
    return True


def _preview_evidence(row: dict, st: Any) -> str:
    """Evidence-based preview column: the preview's host if its subdomain_url is actually
    present in the rendered draft body, else an explicit "(no preview link)" — never inferred
    merely from draft_subject truthiness (a draft can exist with a broken/missing preview link)."""
    preview_id = row.get("preview_id")
    body = row.get("draft_body") or ""
    if not preview_id or not body:
        return "(no preview link)"
    preview = None
    for p in _store_helpers.previews_for_business(st, row.get("business_id")):
        if p.get("id") == preview_id:
            preview = p
            break
    subdomain_url = (preview or {}).get("subdomain_url") or ""
    if subdomain_url and subdomain_url in body:
        return subdomain_url.split("//", 1)[-1].split("/", 1)[0]
    return "(no preview link)"


def _sent_today_count(st: Any, today: date) -> int:
    """Count outreach rows sent today, compared in UTC (item 10 — `sent_at` is always a UTC ISO
    string; a naive local `.date()` comparison would mis-bucket a late-evening manual run)."""
    today_str = today.isoformat()
    count = 0
    for r in _store_helpers.list_all(st, "outreach"):
        sent_at = r.get("sent_at")
        if not sent_at:
            continue
        try:
            sent_dt = datetime.fromisoformat(str(sent_at).replace("Z", "+00:00"))
        except ValueError:
            continue
        if sent_dt.tzinfo is None:
            sent_dt = sent_dt.replace(tzinfo=timezone.utc)
        if sent_dt.astimezone(timezone.utc).date().isoformat() == today_str:
            count += 1
    return count


def _drafted_pending_count(st: Any) -> int:
    """Rows already `drafted` (consumed a cap slot, not yet sent) — counted regardless of date
    since the automated pipeline sends them the same run/day they were drafted.

    item 18(b) (round-3, Hormozi lens): a row `notes.needs_operator_input == True` (an unresolved
    placeholder, e.g. a touch-2 with no `notes.loom_url` set, or a lint-escalated flag) is stuck
    in `drafted` forever — send.py refuses it every day until an operator fixes it and redrafts.
    Counting it here would permanently eat one cap slot from every future day's fresh drafting,
    which is exactly the starvation bug item 2 already fixed for `queued` rows. Excluded from
    this count so it never again crowds out a business that CAN actually be sent.
    """
    return sum(
        1
        for r in _store_helpers.list_all(st, "outreach")
        if r.get("status") == "drafted" and not _needs_operator_input(r)
    )


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
            f"{_preview_evidence(row, st)}"
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
            "cap": effective_cap(st, today, mock=mock),
            "halted": True,
            "enqueued": enqueued,
            "queued_today": 0,
            "drafted": 0,
            "lint_failed": 0,
            "render_error": 0,
            "gmail_drafts": 0,
            "llm_cost_usd": 0.0,
        }

    cap = effective_cap(st, today, mock=mock)
    # C4 queue-starvation fix: `Store.queue(today, cap)` returns a MIX of `queued` and `sent`
    # rows (both are "due" per next_touch_at), capped and ordered BEFORE any status filtering —
    # so historical `sent` rows due for a future touch can crowd the top-`cap` slice and starve
    # out genuinely new `queued` rows from ever being drafted. Fix: over-fetch every due row
    # (queued+sent, uncapped), filter to `queued` only, THEN cap — and cap against how much of
    # today's budget is actually still free (today's real sends + rows already `drafted` and
    # awaiting send today), not against `Store.queue()`'s own naive slice.
    consumed_today = _sent_today_count(st, today) + _drafted_pending_count(st)
    remaining_today = max(0, cap - consumed_today)
    all_due = st.queue(today, len(_store_helpers.list_all(st, "outreach")) + 1)
    # item 2 (round-3 critical): a row flagged needs_operator_input (LINT_FAIL_LIMIT consecutive
    # lint failures) is excluded from the selectable set entirely — it stays `queued` (an
    # operator can still find/fix it) but never crowds out a fresh business's first draft again.
    selected = [
        r for r in all_due if r.get("status") == "queued" and not _needs_operator_input(r)
    ][:remaining_today]

    drafted = 0
    lint_failed = 0
    render_errors = 0
    llm_cost_usd = 0.0

    for row in selected:
        if row.get("status") != "queued":
            continue
        # A row that already has a draft is skipped UNLESS its last render failed lint: after the operator
        # fixes the cause (sender config, an override, a template) the next run must retry, or the row
        # would sit in `queued` forever with no path out (found on the first live run, 2026-09-16).
        # Keyed on draft_body, not draft_subject: state_machine._create_next_touch copies the previous
        # touch's draft_subject onto the new touch row (as the prev_subject source for "Re:" threading),
        # so a subject alone means "touch N-1 was drafted", not "this touch is drafted" (round-3, found
        # by the day-4 mock run: touches 2-4 were never drafted at all).
        if row.get("draft_body") and not _lint_failed_before(row):
            continue

        try:
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

            sender = rendered.get("sender") or {}
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

            # `outreach` has no raw LLM-envelope column, so `notes` is the one JSON object every
            # LLM-derived fact about this draft (fuzzy_variables' envelope, lint outcomes) rides in
            # on — a single merged dict, not one overwriting the other.
            # Start from the row's existing notes so operator-supplied fields (loom_url) and prior
            # flags survive a re-render; the rendered fields below are merged on top.
            notes_obj: dict[str, Any] = dict(_notes_dict(row))
            llm_envelope = rendered.get("llm")
            if llm_envelope:
                notes_obj["llm"] = {
                    "model_id": llm_envelope.get("model_id"),
                    "prompt_sha256": llm_envelope.get("prompt_sha256"),
                    "usage": llm_envelope.get("usage"),
                    "mock": llm_envelope.get("mock"),
                    # research lens (item 9): whether this envelope is an operator-authored
                    # manual_envelope() override rather than a real LLM call.
                    "manual": bool(llm_envelope.get("manual", False)),
                }

            if lint_result["violations"]:
                lint_failed += 1
                notes_obj["lint_violations"] = lint_result["violations"]
                # item 2 (round-3 critical): a lint-failed row must not sit at next_touch_at <=
                # today forever — that made it get re-selected FIRST every day (it sorts by
                # next_touch_at ascending) and eat the whole warmup cap, starving fresh
                # businesses out of ever being drafted. Push it out a day, and count the
                # failure so LINT_FAIL_LIMIT consecutive failures pulls it out of the
                # selectable set (see `_needs_operator_input` filter above) instead of retrying
                # forever.
                prior_notes = _notes_dict(row)
                fail_count = int(prior_notes.get("lint_fail_count") or 0) + 1
                notes_obj["lint_fail_count"] = fail_count
                current_next = row.get("next_touch_at")
                base = datetime.fromisoformat(current_next).date() if current_next else today
                patch["next_touch_at"] = (max(base, today) + timedelta(days=1)).isoformat()
                newly_flagged = fail_count >= LINT_FAIL_LIMIT and not prior_notes.get("needs_operator_input")
                if fail_count >= LINT_FAIL_LIMIT:
                    notes_obj["needs_operator_input"] = True
                patch["notes"] = json.dumps(notes_obj)
                st.update_outreach(row["id"], patch)
                st.log_event(
                    "outreach",
                    row["id"],
                    "lint_failed",
                    {"violations": lint_result["violations"], "lint_fail_count": fail_count},
                )
                if newly_flagged:
                    from execution.personal_workflows.prodcraft_medspa.common import notify

                    notify.error(
                        "prodcraft_medspa.daily_queue",
                        f"outreach row {row['id']} needs operator input after {fail_count} "
                        f"consecutive lint failures: {lint_result['violations']}",
                        1,
                    )
                continue

            if lint_result.get("needs_operator_input"):
                notes_obj["needs_operator_input"] = True
            elif notes_obj.get("needs_operator_input"):
                # A clean render with every placeholder resolved clears the parked flag.
                notes_obj["needs_operator_input"] = False

            if notes_obj:
                patch["notes"] = json.dumps(notes_obj)

            st.update_outreach(row["id"], patch)
            row.update(patch)
            state_machine.transition(st, {**row, "status": "queued"}, "drafted")
            row["status"] = "drafted"
            drafted += 1
        except Exception as exc:  # noqa: BLE001 — M3: one bad render must not abort the whole batch
            render_errors += 1
            st.log_event(
                "outreach", row["id"], "render_error", {"error": f"{type(exc).__name__}: {exc}"}
            )
            continue

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
        "render_error": render_errors,
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
    store_kind = reject_mock_with_supabase(parser, args)  # --mock + --store supabase is a hard error
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
