"""
test_store.py
description: Contract suite for Store implementations — run against LocalStore always,
             against SupabaseStore when SUPABASE_URL/SUPABASE_SERVICE_KEY are set (skip otherwise).
inputs: N/A (pytest); env SUPABASE_URL, SUPABASE_SERVICE_KEY for the Supabase leg.
outputs: N/A (pytest).
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore, SupabaseStore
from tests.prodcraft_medspa.conftest import skip_without_supabase, PKG_ROOT


def _local_factory(tmp_path):
    return LocalStore(root=tmp_path / "store")


def _supabase_factory(tmp_path):
    return SupabaseStore()


@pytest.fixture(params=["local", pytest.param("supabase", marks=skip_without_supabase)])
def store(request, tmp_path):
    if request.param == "local":
        return _local_factory(tmp_path)
    return _supabase_factory(tmp_path)


def _business_row(place_id: str = "place-1", **overrides) -> dict:
    row = {
        "place_id": place_id,
        "name": "Glow Aesthetics",
        "slug": f"glow-aesthetics-{place_id}",
        "metro": "Chicago North Shore",
        "city": "Winnetka",
        "is_chain": False,
        "do_not_contact": False,
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# Upsert idempotency on place_id
# ---------------------------------------------------------------------------


def test_upsert_business_idempotent_on_place_id(store):
    first = store.upsert_business(_business_row(rating=4.5))
    second = store.upsert_business(_business_row(rating=4.8, name="Glow Aesthetics Updated"))

    assert first["id"] == second["id"]
    fetched = store.get_business(first["id"])
    assert fetched["rating"] == 4.8 or float(fetched["rating"]) == 4.8
    assert fetched["name"] == "Glow Aesthetics Updated"


def test_upsert_business_creates_distinct_rows_for_distinct_place_ids(store):
    a = store.upsert_business(_business_row(place_id="place-a"))
    b = store.upsert_business(_business_row(place_id="place-b"))
    assert a["id"] != b["id"]


def test_get_business_missing_returns_none(store):
    assert store.get_business("00000000-0000-0000-0000-000000000000") is None


# ---------------------------------------------------------------------------
# Audits append-only + latest_audit ordering
# ---------------------------------------------------------------------------


def test_audits_append_only_and_latest_audit_ordering(store):
    business = store.upsert_business(_business_row(place_id="place-audit"))
    bid = business["id"]

    a1 = store.insert_audit(
        {"business_id": bid, "total_score": 30, "bucket": "borderline", "audited_at": "2026-01-01T00:00:00Z"}
    )
    a2 = store.insert_audit(
        {"business_id": bid, "total_score": 55, "bucket": "qualified", "audited_at": "2026-02-01T00:00:00Z"}
    )

    assert a1["id"] != a2["id"]
    latest = store.latest_audit(bid)
    assert latest["id"] == a2["id"]
    assert latest["bucket"] == "qualified"


def test_latest_audit_none_when_no_audits(store):
    business = store.upsert_business(_business_row(place_id="place-no-audit"))
    assert store.latest_audit(business["id"]) is None


def test_find_businesses_by_bucket_uses_latest_audit(store):
    business = store.upsert_business(_business_row(place_id="place-bucket", metro="Chicago North Shore"))
    bid = business["id"]
    store.insert_audit(
        {"business_id": bid, "total_score": 20, "bucket": "skip", "audited_at": "2026-01-01T00:00:00Z"}
    )
    store.insert_audit(
        {"business_id": bid, "total_score": 60, "bucket": "qualified", "audited_at": "2026-03-01T00:00:00Z"}
    )

    qualified = store.find_businesses(metro="Chicago North Shore", bucket="qualified")
    assert any(b["id"] == bid for b in qualified)

    skipped = store.find_businesses(metro="Chicago North Shore", bucket="skip")
    assert not any(b["id"] == bid for b in skipped)


# ---------------------------------------------------------------------------
# Preview upsert by content_hash
# ---------------------------------------------------------------------------


def test_preview_upsert_by_business_and_content_hash(store):
    business = store.upsert_business(_business_row(place_id="place-preview"))
    bid = business["id"]

    p1 = store.upsert_preview(
        {
            "business_id": bid,
            "content_hash": "hash-a",
            "slug_suffix": "abc123",
            "subdomain_url": "https://glow-abc123.preview.prodcraft.fyi",
            "content": {"name": "Glow"},
        }
    )
    p2 = store.upsert_preview(
        {
            "business_id": bid,
            "content_hash": "hash-a",
            "slug_suffix": "abc123",
            "subdomain_url": "https://glow-abc123.preview.prodcraft.fyi",
            "content": {"name": "Glow Updated"},
        }
    )
    assert p1["id"] == p2["id"]

    p3 = store.upsert_preview(
        {
            "business_id": bid,
            "content_hash": "hash-b",
            "slug_suffix": "def456",
            "subdomain_url": "https://glow-def456.preview.prodcraft.fyi",
            "content": {"name": "Glow"},
        }
    )
    assert p3["id"] != p1["id"]


def test_update_preview_patches_fields(store):
    business = store.upsert_business(_business_row(place_id="place-preview-patch"))
    preview = store.upsert_preview(
        {
            "business_id": business["id"],
            "content_hash": "hash-x",
            "slug_suffix": "xyz789",
            "subdomain_url": "https://glow-xyz789.preview.prodcraft.fyi",
            "content": {},
            "status": "review",
        }
    )
    updated = store.update_preview(preview["id"], {"status": "approved"})
    assert updated["status"] == "approved"


# ---------------------------------------------------------------------------
# Outreach unique (business_id, touch)
# ---------------------------------------------------------------------------


def test_outreach_unique_business_and_touch(store):
    business = store.upsert_business(_business_row(place_id="place-outreach"))
    bid = business["id"]

    o1 = store.upsert_outreach({"business_id": bid, "touch": 1, "status": "queued"})
    o2 = store.upsert_outreach({"business_id": bid, "touch": 1, "status": "drafted"})
    assert o1["id"] == o2["id"]
    assert o2["status"] == "drafted"

    o3 = store.upsert_outreach({"business_id": bid, "touch": 2, "status": "queued"})
    assert o3["id"] != o1["id"]


def test_update_outreach_patches_fields(store):
    business = store.upsert_business(_business_row(place_id="place-outreach-patch"))
    outreach = store.upsert_outreach({"business_id": business["id"], "touch": 1, "status": "queued"})
    updated = store.update_outreach(outreach["id"], {"status": "sent"})
    assert updated["status"] == "sent"


# ---------------------------------------------------------------------------
# Queue ordering by latest audit total_score desc with cap and status filter
# ---------------------------------------------------------------------------


def test_queue_respects_next_touch_at_status_and_cap(store):
    today = date(2026, 6, 15)
    business = store.upsert_business(_business_row(place_id="place-queue"))
    bid = business["id"]

    store.upsert_outreach(
        {
            "business_id": bid,
            "touch": 1,
            "status": "queued",
            "next_touch_at": (today - timedelta(days=1)).isoformat(),
        }
    )
    future_business = store.upsert_business(_business_row(place_id="place-queue-future"))
    store.upsert_outreach(
        {
            "business_id": future_business["id"],
            "touch": 1,
            "status": "queued",
            "next_touch_at": (today + timedelta(days=5)).isoformat(),
        }
    )
    dnc_business = store.upsert_business(_business_row(place_id="place-queue-dnc"))
    store.upsert_outreach(
        {
            "business_id": dnc_business["id"],
            "touch": 1,
            "status": "dnc",
            "next_touch_at": (today - timedelta(days=1)).isoformat(),
        }
    )

    result = store.queue(today, cap=10)
    business_ids = {r["business_id"] for r in result}
    assert bid in business_ids
    assert future_business["id"] not in business_ids
    assert dnc_business["id"] not in business_ids


def test_queue_cap_limits_results(store):
    today = date(2026, 6, 15)
    for i in range(5):
        business = store.upsert_business(_business_row(place_id=f"place-cap-{i}"))
        store.upsert_outreach(
            {
                "business_id": business["id"],
                "touch": 1,
                "status": "queued",
                "next_touch_at": (today - timedelta(days=1)).isoformat(),
            }
        )
    result = store.queue(today, cap=2)
    assert len(result) <= 2


# ---------------------------------------------------------------------------
# Config get/set
# ---------------------------------------------------------------------------


def test_config_get_set_roundtrip(store):
    store.set_config("phase0", {"passed": False, "sends": 0})
    value = store.get_config("phase0")
    assert value == {"passed": False, "sends": 0}


def test_config_get_default_when_missing(store):
    assert store.get_config("does_not_exist", default="fallback") == "fallback"


def test_config_set_overwrites(store):
    store.set_config("touch_days", [0, 3, 7, 12])
    store.set_config("touch_days", [0, 2, 5, 10])
    assert store.get_config("touch_days") == [0, 2, 5, 10]


# ---------------------------------------------------------------------------
# Events logged
# ---------------------------------------------------------------------------


def test_log_event_does_not_raise(store):
    business = store.upsert_business(_business_row(place_id="place-event"))
    store.log_event("business", business["id"], "status:queued->sent", {"touch": 1})
    # LocalStore exposes _read for verification; SupabaseStore has no local read-back
    # in this contract suite, so only assert no exception was raised for it.
    if isinstance(store, LocalStore):
        events = store._read("events")  # noqa: SLF001
        assert any(e["entity_id"] == business["id"] and e["event"] == "status:queued->sent" for e in events)


# ---------------------------------------------------------------------------
# Chains loaded after seeding
# ---------------------------------------------------------------------------


def test_chains_loaded_after_seeding(store):
    seed_path = PKG_ROOT / "db" / "seed_chains.json"
    patterns = json.loads(seed_path.read_text(encoding="utf-8"))

    if isinstance(store, LocalStore):
        store.load_chains(patterns)
    else:
        for entry in patterns:
            store._request(  # noqa: SLF001
                "POST",
                "chains?on_conflict=pattern",
                headers=store._headers(prefer="resolution=merge-duplicates"),  # noqa: SLF001
                json=entry,
            )

    loaded = store.chains()
    assert "ideal image" in loaded
    assert "laseraway" in loaded
    assert len(loaded) == len(patterns)


# ---------------------------------------------------------------------------
# LocalStore-specific: atomic writes, uuid ids, thread safety
# ---------------------------------------------------------------------------


def test_local_store_ids_are_uuid4_strings(tmp_path):
    store = _local_factory(tmp_path)
    business = store.upsert_business(_business_row(place_id="place-uuid"))
    import uuid

    uuid.UUID(business["id"])  # raises ValueError if not a valid UUID


def test_local_store_atomic_write_leaves_no_tmp_files(tmp_path):
    store = _local_factory(tmp_path)
    store.upsert_business(_business_row(place_id="place-atomic"))
    tmp_files = list((tmp_path / "store").glob("*.tmp-*"))
    assert tmp_files == []


def test_local_store_deals_and_metro_stats(tmp_path):
    store = _local_factory(tmp_path)
    business = store.upsert_business(_business_row(place_id="place-deal"))
    deal = store.upsert_deal({"business_id": business["id"], "tier": "starter", "setup_price": 500, "mrr": 150})
    assert deal["id"]

    stats = store.insert_metro_stats(
        {"metro": "Chicago North Shore", "sampled": 40, "qualified": 12, "pct_qualified": 30.0, "ci_low": 18.0, "ci_high": 45.0, "score_version": "1.0"}
    )
    assert stats["id"]
