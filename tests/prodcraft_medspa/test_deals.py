"""
test_deals.py
description: pytest suite for execution/personal_workflows/prodcraft_medspa/deals/deals.py.
inputs: pytest fixtures from conftest.py (local_store).
outputs: N/A (test assertions only).
"""

from __future__ import annotations

import pytest

from execution.personal_workflows.prodcraft_medspa.deals import deals


def _make_business(store, name="Test Med Spa"):
    return store.upsert_business({"place_id": f"place-{name}", "name": name, "metro": "chicago-north-shore"})


def test_record_growth_tier_defaults(local_store):
    business = _make_business(local_store)
    deal = deals.record(
        local_store,
        business_id=business["id"],
        tier="growth",
        setup_price=None,
        mrr=None,
        signed=None,
        baseline=10,
        booking_tool=None,
    )
    assert deal["setup_price"] == 4500.0
    assert deal["mrr"] == 199.0


def test_record_starter_tier_defaults(local_store):
    business = _make_business(local_store)
    deal = deals.record(
        local_store, business_id=business["id"], tier="starter", setup_price=None, mrr=None,
        signed=None, baseline=5, booking_tool=None,
    )
    assert deal["setup_price"] == 2500.0
    assert deal["mrr"] == 99.0


def test_record_premium_tier_defaults(local_store):
    business = _make_business(local_store)
    deal = deals.record(
        local_store, business_id=business["id"], tier="premium", setup_price=None, mrr=None,
        signed=None, baseline=20, booking_tool=None,
    )
    assert deal["setup_price"] == 8000.0
    assert deal["mrr"] == 299.0


def test_record_founding_tier_defaults_and_note(local_store):
    business = _make_business(local_store)
    deal = deals.record(
        local_store, business_id=business["id"], tier="founding", setup_price=None, mrr=None,
        signed=None, baseline=8, booking_tool=None,
    )
    # Founding: Growth-tier care plan ($199/mo) at a discounted Starter-level setup price.
    assert deal["setup_price"] == 2500.0
    assert deal["mrr"] == 199.0
    assert "founding" in deal["notes"].lower()


def test_record_explicit_price_overrides_tier_default(local_store):
    business = _make_business(local_store)
    deal = deals.record(
        local_store, business_id=business["id"], tier="growth", setup_price=5000.0, mrr=250.0,
        signed="2026-09-01", baseline=12, booking_tool="Vagaro",
    )
    assert deal["setup_price"] == 5000.0
    assert deal["mrr"] == 250.0
    assert deal["contract_signed_at"] == "2026-09-01"
    assert deal["current_booking_tool"] == "Vagaro"


def test_record_unknown_tier_raises(local_store):
    business = _make_business(local_store)
    with pytest.raises(ValueError):
        deals.record(
            local_store, business_id=business["id"], tier="bogus", setup_price=None, mrr=None,
            signed=None, baseline=None, booking_tool=None,
        )


def test_record_transitions_call_booked_outreach_to_closed_won(local_store):
    business = _make_business(local_store)
    local_store.upsert_outreach({"business_id": business["id"], "touch": 1, "status": "call_booked"})
    deals.record(
        local_store, business_id=business["id"], tier="growth", setup_price=None, mrr=None,
        signed=None, baseline=10, booking_tool=None,
    )
    rows = [r for r in local_store._read("outreach") if r["business_id"] == business["id"]]
    assert rows[0]["status"] == "closed_won"


def test_record_without_call_booked_row_does_not_raise(local_store):
    business = _make_business(local_store)
    # No outreach row at all — record() should still succeed (deal exists independent of outreach).
    deal = deals.record(
        local_store, business_id=business["id"], tier="growth", setup_price=None, mrr=None,
        signed=None, baseline=10, booking_tool=None,
    )
    assert deal["business_id"] == business["id"]


def test_golive_sets_live_at(local_store):
    business = _make_business(local_store)
    deals.record(
        local_store, business_id=business["id"], tier="growth", setup_price=None, mrr=None,
        signed=None, baseline=10, booking_tool=None,
    )
    deal = deals.golive(local_store, business_id=business["id"], live_at="2026-10-01")
    assert deal["live_at"] == "2026-10-01"


def test_proof_guarantee_met(local_store):
    business = _make_business(local_store)
    deals.record(
        local_store, business_id=business["id"], tier="growth", setup_price=None, mrr=None,
        signed=None, baseline=10, booking_tool=None,
    )
    result = deals.proof(local_store, business_id=business["id"], bookings_60d=25)
    assert result["deal"]["guarantee_met"] is True
    assert result["verdict"] == "GUARANTEE MET"
    assert result["threshold_2x_baseline"] == 20
    assert result["owed"] == "balance owed in full"


def test_proof_guarantee_not_met(local_store):
    business = _make_business(local_store)
    deals.record(
        local_store, business_id=business["id"], tier="growth", setup_price=None, mrr=None,
        signed=None, baseline=10, booking_tool=None,
    )
    result = deals.proof(local_store, business_id=business["id"], bookings_60d=15)
    assert result["deal"]["guarantee_met"] is False
    assert result["verdict"] == "guarantee NOT met"
    assert "waived" in result["owed"]


def test_proof_boundary_exactly_2x_is_not_met(local_store):
    """guarantee_met = bookings_60d > baseline * 2 (strict >, per CONTRACTS.md), so exactly 2x fails."""
    business = _make_business(local_store)
    deals.record(
        local_store, business_id=business["id"], tier="growth", setup_price=None, mrr=None,
        signed=None, baseline=10, booking_tool=None,
    )
    result = deals.proof(local_store, business_id=business["id"], bookings_60d=20)
    assert result["deal"]["guarantee_met"] is False


def test_proof_without_baseline_raises(local_store):
    business = _make_business(local_store)
    local_store.upsert_deal({"business_id": business["id"], "tier": "growth", "setup_price": 4500, "mrr": 199})
    with pytest.raises(ValueError):
        deals.proof(local_store, business_id=business["id"], bookings_60d=25)


def test_list_returns_all_deals(local_store):
    b1 = _make_business(local_store, "Spa One")
    b2 = _make_business(local_store, "Spa Two")
    deals.record(local_store, business_id=b1["id"], tier="starter", setup_price=None, mrr=None, signed=None, baseline=5, booking_tool=None)
    deals.record(local_store, business_id=b2["id"], tier="premium", setup_price=None, mrr=None, signed=None, baseline=5, booking_tool=None)
    result = deals.list_deals(local_store)
    assert len(result) == 2
