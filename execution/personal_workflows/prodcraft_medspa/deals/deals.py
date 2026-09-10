"""
deals.py
description: Deal recording, go-live, and the 60-day booking-rate guarantee proof (PROJECT_SPEC.md
    §9 tiers, guarantee_met = bookings_60d > baseline_online_bookings_30d * 2).
inputs: CLI subcommands:
    record --business-id ID --tier founding|starter|growth|premium [--setup-price] [--mrr]
        [--signed ISO] [--baseline N] [--booking-tool X]
    golive --business-id ID --live-at ISO
    proof --business-id ID --bookings-60d N
    list
    Common: [--store {local,supabase}] [--store-root PATH].
outputs: stdout JSON stat lines per subcommand; Store mutations via store.upsert_deal and, on
    `record`, outreach/state_machine.transition(..., "closed_won").
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from execution.personal_workflows.prodcraft_medspa.common import config, store as store_mod  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.outreach import _store_helpers, state_machine  # noqa: E402

# PROJECT_SPEC.md §9 — Tiers: Starter $2,500 + $99/mo · Growth $4,500 + $199/mo (default) ·
# Premium $8,000 + $299/mo · Founding: Growth pricing structure but discounted per Hormozi #1
# in the panel pass (first clients: Growth quality at Starter-ish setup, full $199/mo care plan,
# in exchange for a before/after booking number + testimonial) — CONTRACTS.md D8.
TIER_DEFAULTS: dict[str, dict[str, float]] = {
    "starter": {"setup_price": 2500.0, "mrr": 99.0},
    "growth": {"setup_price": 4500.0, "mrr": 199.0},
    "premium": {"setup_price": 8000.0, "mrr": 299.0},
    "founding": {"setup_price": 2500.0, "mrr": 199.0},
}
FOUNDING_NOTE = (
    "founding tier: Growth-tier care plan ($199/mo) at a discounted Starter-level setup price "
    "in exchange for a before/after booking number and a testimonial (Hormozi #1, panel pass D8)."
)


def _parse_date(value: str | None) -> str | None:
    if not value:
        return None
    # Accept bare dates (YYYY-MM-DD) or full ISO timestamps; store as given if already ISO.
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    except ValueError:
        return value  # already ISO-ish or another accepted format — pass through unmodified


def record(st: Any, *, business_id: str, tier: str, setup_price: float | None, mrr: float | None,
           signed: str | None, baseline: int | None, booking_tool: str | None) -> dict:
    if tier not in TIER_DEFAULTS:
        raise ValueError(f"unknown tier {tier!r}; must be one of {sorted(TIER_DEFAULTS)}")
    defaults = TIER_DEFAULTS[tier]
    row = {
        "business_id": business_id,
        "tier": tier,
        "setup_price": setup_price if setup_price is not None else defaults["setup_price"],
        "mrr": mrr if mrr is not None else defaults["mrr"],
        "contract_signed_at": _parse_date(signed) or date.today().isoformat(),
        "baseline_online_bookings_30d": baseline,
        "current_booking_tool": booking_tool,
    }
    if tier == "founding":
        row["notes"] = FOUNDING_NOTE
    deal = st.upsert_deal(row)
    st.log_event("deal", deal["id"], "recorded", {"tier": tier})

    # Transition the business's outreach to closed_won (CLI contract: "On record transition
    # outreach to closed_won"). Find the most-advanced non-terminal-lost outreach row for this
    # business (prefer call_booked, else replied) since closed_won is only legal from call_booked.
    candidates = [
        r
        for r in _store_helpers.outreach_for_business(st, business_id)
        if r.get("status") not in ("closed_won", "closed_lost", "dnc")
    ]
    candidates.sort(key=lambda r: int(r.get("touch") or 0), reverse=True)
    outreach_row = next((r for r in candidates if r.get("status") == "call_booked"), None)
    if outreach_row:
        state_machine.transition(st, outreach_row, "closed_won", notes="deal recorded")

    return deal


def golive(st: Any, *, business_id: str, live_at: str) -> dict:
    deal = st.upsert_deal({"business_id": business_id, "live_at": _parse_date(live_at)})
    st.log_event("deal", deal["id"], "go_live", {"live_at": live_at})
    return deal


def proof(st: Any, *, business_id: str, bookings_60d: int) -> dict:
    existing = None
    for row in _store_helpers.list_all(st, "deals"):
        if row.get("business_id") == business_id:
            existing = row
            break
    baseline = (existing or {}).get("baseline_online_bookings_30d")
    if baseline is None:
        raise ValueError(
            f"no baseline_online_bookings_30d recorded for business {business_id}; "
            "run `deals record --baseline N` first"
        )

    guarantee_met = bookings_60d > baseline * 2
    deal = st.upsert_deal(
        {"business_id": business_id, "bookings_60d": bookings_60d, "guarantee_met": guarantee_met}
    )
    st.log_event("deal", deal["id"], "proof", {"bookings_60d": bookings_60d, "guarantee_met": guarantee_met})

    verdict = "GUARANTEE MET" if guarantee_met else "guarantee NOT met"
    threshold = baseline * 2
    owed = (
        "balance owed in full"
        if guarantee_met
        else "second-half balance waived per the 60-day guarantee"
    )
    return {
        "deal": deal,
        "verdict": verdict,
        "baseline_online_bookings_30d": baseline,
        "threshold_2x_baseline": threshold,
        "bookings_60d": bookings_60d,
        "owed": owed,
    }


def list_deals(st: Any) -> list[dict]:
    return _store_helpers.list_all(st, "deals")


def main() -> None:
    parser = argparse.ArgumentParser(description="ProdCraft deals: record, go-live, 60-day proof")
    sub = parser.add_subparsers(dest="command", required=True)

    p_record = sub.add_parser("record")
    p_record.add_argument("--business-id", required=True)
    p_record.add_argument("--tier", required=True, choices=list(TIER_DEFAULTS))
    p_record.add_argument("--setup-price", type=float, default=None)
    p_record.add_argument("--mrr", type=float, default=None)
    p_record.add_argument("--signed", default=None)
    p_record.add_argument("--baseline", type=int, default=None)
    p_record.add_argument("--booking-tool", default=None)

    p_golive = sub.add_parser("golive")
    p_golive.add_argument("--business-id", required=True)
    p_golive.add_argument("--live-at", required=True)

    p_proof = sub.add_parser("proof")
    p_proof.add_argument("--business-id", required=True)
    p_proof.add_argument("--bookings-60d", type=int, required=True)

    p_list = sub.add_parser("list")

    for p in (p_record, p_golive, p_proof, p_list):
        p.add_argument("--store", choices=["local", "supabase"], default=None)
        p.add_argument("--store-root", default=None)

    args = parser.parse_args()

    settings = config.bootstrap()
    store_kind = args.store or settings.store_kind
    st = store_mod.get_store(kind=store_kind, root=args.store_root)

    if args.command == "record":
        deal = record(
            st,
            business_id=args.business_id,
            tier=args.tier,
            setup_price=args.setup_price,
            mrr=args.mrr,
            signed=args.signed,
            baseline=args.baseline,
            booking_tool=args.booking_tool,
        )
        print(json.dumps({"script": "deals.record", "deal": deal}))
    elif args.command == "golive":
        deal = golive(st, business_id=args.business_id, live_at=args.live_at)
        print(json.dumps({"script": "deals.golive", "deal": deal}))
    elif args.command == "proof":
        result = proof(st, business_id=args.business_id, bookings_60d=args.bookings_60d)
        print(json.dumps({"script": "deals.proof", **result}))
        print(f"{result['verdict']}: {result['bookings_60d']} vs threshold {result['threshold_2x_baseline']} -> {result['owed']}")
    elif args.command == "list":
        deals = list_deals(st)
        print(json.dumps({"script": "deals.list", "deals": deals}))


if __name__ == "__main__":
    main()
