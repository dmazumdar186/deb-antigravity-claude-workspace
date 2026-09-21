"""
test_store.py
description: Contract suite for Store implementations — run against LocalStore always,
             against SupabaseStore when SUPABASE_URL/SUPABASE_SERVICE_KEY are set (skip otherwise).
inputs: N/A (pytest); env SUPABASE_URL, SUPABASE_SERVICE_KEY for the Supabase leg.
outputs: N/A (pytest).
"""

from __future__ import annotations

import json
import time
from datetime import date, timedelta

import pytest
import requests

from execution.personal_workflows.prodcraft_medspa.common.store import ID_TABLES, LocalStore, SupabaseStore
from tests.prodcraft_medspa.conftest import skip_without_supabase, PKG_ROOT


def _fake_supabase_store() -> SupabaseStore:
    """A SupabaseStore that never touches the network — used to unit-test URL/params
    construction and retry logic by monkeypatching `_request` or `_session.request`."""
    return SupabaseStore(url="https://fake-project.supabase.co", service_key="fake-service-key")


class _FakeResp:
    """Minimal stand-in for requests.Response, enough for _request()'s retry logic."""

    def __init__(self, status_code: int, text: str = "", json_data=None):
        self.status_code = status_code
        self.text = text
        self._json_data = json_data if json_data is not None else []

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code} error")

    def json(self):
        return self._json_data


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

    count = store.load_chains(patterns)
    assert count == len(patterns)

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


# ---------------------------------------------------------------------------
# Generic list_rows / get_row / update_row / list_previews / list_outreach
# ---------------------------------------------------------------------------


def test_list_rows_filters_orders_and_limits(store):
    b1 = store.upsert_business(_business_row(place_id="lr-1", metro="Chicago North Shore"))
    b2 = store.upsert_business(_business_row(place_id="lr-2", metro="Chicago North Shore", name="Second Spa"))
    store.upsert_business(_business_row(place_id="lr-3", metro="Denver Metro", name="Other Metro Spa"))

    matches = store.list_rows("businesses", metro="Chicago North Shore")
    matched_ids = {r["id"] for r in matches}
    assert {b1["id"], b2["id"]}.issubset(matched_ids)
    assert all(r["metro"] == "Chicago North Shore" for r in matches)

    ordered = store.list_rows("businesses", metro="Chicago North Shore", order_by="created_at", descending=True)
    assert ordered[0]["id"] == b2["id"]

    limited = store.list_rows("businesses", metro="Chicago North Shore", limit=1)
    assert len(limited) == 1


def test_list_rows_none_filter_means_is_null(store):
    business = store.upsert_business(_business_row(place_id="lr-null"))
    not_null_business = store.upsert_business(
        {**_business_row(place_id="lr-not-null"), "drop_reason": "too_small"}
    )

    null_rows = store.list_rows("businesses", place_id="lr-null", drop_reason=None)
    assert any(r["id"] == business["id"] for r in null_rows)

    # place_id="lr-not-null" AND drop_reason IS NULL should match nothing: that business has
    # drop_reason set, so filtering for a null drop_reason must exclude it (previously this
    # half of the test asserted over an empty/self-consistent comprehension and could not fail).
    not_null_rows = store.list_rows("businesses", place_id="lr-not-null", drop_reason=None)
    assert not any(r["id"] == not_null_business["id"] for r in not_null_rows)


def test_list_rows_unknown_table_raises_value_error(store):
    with pytest.raises(ValueError):
        store.list_rows("not_a_real_table")


def test_get_row_hit_and_miss(store):
    business = store.upsert_business(_business_row(place_id="gr-hit"))
    fetched = store.get_row("businesses", business["id"])
    assert fetched["id"] == business["id"]

    assert store.get_row("businesses", "00000000-0000-0000-0000-000000000000") is None


def test_get_row_unknown_table_raises_value_error(store):
    with pytest.raises(ValueError):
        store.get_row("not_a_real_table", "some-id")


def test_update_row_patches_and_stamps_updated_at(store):
    business = store.upsert_business(_business_row(place_id="ur-1"))
    before = business.get("updated_at")

    updated = store.update_row("businesses", business["id"], {"name": "Renamed Spa"})
    assert updated["name"] == "Renamed Spa"
    assert updated.get("updated_at") is not None
    assert before is None or updated["updated_at"] >= before


def test_update_row_missing_row_raises_key_error(store):
    with pytest.raises(KeyError):
        store.update_row("businesses", "00000000-0000-0000-0000-000000000000", {"name": "nope"})


def test_update_row_unknown_table_raises_value_error(store):
    with pytest.raises(ValueError):
        store.update_row("not_a_real_table", "some-id", {"x": 1})


def test_list_previews_returns_newest_first(store):
    business = store.upsert_business(_business_row(place_id="lp-1"))
    bid = business["id"]
    store.upsert_preview(
        {
            "business_id": bid,
            "content_hash": "h1",
            "slug_suffix": "s1",
            "subdomain_url": "https://a.preview.prodcraft.fyi",
            "content": {},
            "created_at": "2026-01-01T00:00:00Z",
        }
    )
    store.upsert_preview(
        {
            "business_id": bid,
            "content_hash": "h2",
            "slug_suffix": "s2",
            "subdomain_url": "https://b.preview.prodcraft.fyi",
            "content": {},
            "created_at": "2026-06-01T00:00:00Z",
        }
    )

    previews = store.list_previews(bid)
    assert len(previews) == 2
    assert previews[0]["content_hash"] == "h2"  # newest first


def test_list_outreach_returns_newest_first(store):
    business = store.upsert_business(_business_row(place_id="lo-1"))
    bid = business["id"]
    store.upsert_outreach({"business_id": bid, "touch": 1, "status": "sent", "created_at": "2026-01-01T00:00:00Z"})
    store.upsert_outreach({"business_id": bid, "touch": 2, "status": "queued", "created_at": "2026-02-01T00:00:00Z"})

    rows = store.list_outreach(bid)
    assert len(rows) == 2
    assert rows[0]["touch"] == 2  # newest first


def test_local_store_deals_and_metro_stats(tmp_path):
    store = _local_factory(tmp_path)
    business = store.upsert_business(_business_row(place_id="place-deal"))
    deal = store.upsert_deal({"business_id": business["id"], "tier": "starter", "setup_price": 500, "mrr": 150})
    assert deal["id"]

    stats = store.insert_metro_stats(
        {"metro": "Chicago North Shore", "sampled": 40, "qualified": 12, "pct_qualified": 30.0, "ci_low": 18.0, "ci_high": 45.0, "score_version": "1.0"}
    )
    assert stats["id"]


# ---------------------------------------------------------------------------
# C1: filter/order key validation and unencoded-value injection (list_rows/get_row/update_row)
# ---------------------------------------------------------------------------


def test_list_rows_rejects_invalid_filter_key(store):
    with pytest.raises(ValueError):
        store.list_rows("businesses", **{"bad key; drop": "x"})


def test_list_rows_rejects_invalid_order_by_key(store):
    with pytest.raises(ValueError):
        store.list_rows("businesses", order_by="bad-key")


def test_supabase_list_rows_sends_filters_via_params_not_url_string():
    """Values are handed to `requests` as (key, value) tuples, not concatenated into the path,
    so `requests` — not our f-strings — is responsible for percent-encoding special characters
    like `+`, `#`, `&` correctly."""
    store = _fake_supabase_store()
    captured = {}

    def fake_request(method, path, **kwargs):
        captured["path"] = path
        captured["params"] = kwargs.get("params")
        return _FakeResp(200, json_data=[])

    store._request = fake_request  # noqa: SLF001
    store.list_rows("businesses", name="A+B & C#D")

    assert captured["path"] == "businesses"  # no query string baked into the path
    params = dict(captured["params"])
    assert params["name"] == "eq.A+B & C#D"  # raw value preserved for requests to encode


def test_supabase_get_row_and_update_row_use_params_for_id():
    store = _fake_supabase_store()
    captured = []

    def fake_request(method, path, **kwargs):
        captured.append((method, path, kwargs.get("params")))
        return _FakeResp(200, json_data=[{"id": "biz+1"}])

    store._request = fake_request  # noqa: SLF001
    store.get_row("businesses", "biz+1")
    store.update_row("businesses", "biz+1", {"name": "x"})

    for method, path, params in captured:
        assert path == "businesses"
        assert dict(params)["id"] == "eq.biz+1"


def test_supabase_find_businesses_normalizes_booleans():
    store = _fake_supabase_store()
    captured = {}

    def fake_request(method, path, **kwargs):
        captured["params"] = kwargs.get("params")
        return _FakeResp(200, json_data=[])

    store._request = fake_request  # noqa: SLF001
    store.find_businesses(do_not_contact=True, is_chain=False)

    params = dict(captured["params"])
    assert params["do_not_contact"] == "eq.true"
    assert params["is_chain"] == "eq.false"


# ---------------------------------------------------------------------------
# C2: SupabaseStore.list_rows pagination
# ---------------------------------------------------------------------------


def test_supabase_list_rows_pages_until_short_page_returned():
    store = _fake_supabase_store()
    total_rows = [{"id": i} for i in range(1500)]
    ranges_requested = []

    def fake_request(method, path, **kwargs):
        rng = kwargs["headers"]["Range"]
        ranges_requested.append(rng)
        start, end = (int(x) for x in rng.split("-"))
        return _FakeResp(200, json_data=total_rows[start : end + 1])

    store._request = fake_request  # noqa: SLF001
    rows = store.list_rows("businesses")

    assert rows == total_rows
    assert ranges_requested == ["0-999", "1000-1999"]  # second page is short (500) -> loop stops


def test_supabase_list_rows_limit_caps_total_across_pages():
    store = _fake_supabase_store()
    total_rows = [{"id": i} for i in range(2500)]
    ranges_requested = []

    def fake_request(method, path, **kwargs):
        rng = kwargs["headers"]["Range"]
        ranges_requested.append(rng)
        start, end = (int(x) for x in rng.split("-"))
        return _FakeResp(200, json_data=total_rows[start : end + 1])

    store._request = fake_request  # noqa: SLF001
    rows = store.list_rows("businesses", limit=1500)

    assert rows == total_rows[:1500]
    assert ranges_requested == ["0-999", "1000-1499"]  # second page request capped by remaining limit


# ---------------------------------------------------------------------------
# M3: load_chains merges (doesn't overwrite) and validates `pattern`
# ---------------------------------------------------------------------------


def test_load_chains_merges_keeps_existing_and_adds_new(store):
    store.load_chains([{"pattern": "acme", "note": "n1"}])
    count = store.load_chains([{"pattern": "acme", "note": "n1-updated"}, {"pattern": "beta", "note": "n2"}])

    assert count == 2
    loaded = set(store.chains())
    assert {"acme", "beta"}.issubset(loaded)


def test_load_chains_missing_pattern_raises_value_error(store):
    with pytest.raises(ValueError):
        store.load_chains([{"note": "no pattern here"}])


def test_local_store_load_chains_merge_preserves_rows_not_in_new_batch(tmp_path):
    store = _local_factory(tmp_path)
    store.load_chains([{"pattern": "acme", "note": "n1"}, {"pattern": "gamma", "note": "g"}])
    store.load_chains([{"pattern": "acme", "note": "n1-updated"}])

    rows = store._read("chains")  # noqa: SLF001
    by_pattern = {r["pattern"]: r for r in rows}
    assert by_pattern["acme"]["note"] == "n1-updated"
    assert "gamma" in by_pattern  # a full _write() overwrite would have dropped this row


# ---------------------------------------------------------------------------
# M4: _request retry/error-message/idempotency behaviour
# ---------------------------------------------------------------------------


def test_request_error_message_includes_status_code_and_body(monkeypatch):
    store = _fake_supabase_store()
    monkeypatch.setattr(time, "sleep", lambda s: None)
    monkeypatch.setattr(
        store._session, "request", lambda *a, **k: _FakeResp(500, text="internal server error detail")  # noqa: SLF001
    )

    with pytest.raises(RuntimeError) as exc_info:
        store._request("GET", "businesses")  # noqa: SLF001

    msg = str(exc_info.value)
    assert "500" in msg
    assert "internal server error detail" in msg


def test_request_does_not_sleep_after_final_attempt(monkeypatch):
    store = _fake_supabase_store()
    sleep_calls = []
    monkeypatch.setattr(time, "sleep", lambda s: sleep_calls.append(s))
    monkeypatch.setattr(store._session, "request", lambda *a, **k: _FakeResp(503, text="unavailable"))  # noqa: SLF001

    with pytest.raises(RuntimeError):
        store._request("GET", "businesses")  # noqa: SLF001

    assert len(sleep_calls) == 2  # 3 attempts -> sleeps after attempt 1 and 2, not after attempt 3


def test_request_4xx_is_not_retried(monkeypatch):
    store = _fake_supabase_store()
    call_count = {"n": 0}

    def fake_request(*a, **k):
        call_count["n"] += 1
        return _FakeResp(409, text="conflict: duplicate slug")

    monkeypatch.setattr(time, "sleep", lambda s: (_ for _ in ()).throw(AssertionError("must not sleep on 4xx")))
    monkeypatch.setattr(store._session, "request", fake_request)

    with pytest.raises(RuntimeError) as exc_info:
        store._request("POST", "businesses")  # noqa: SLF001

    assert call_count["n"] == 1  # no retry storm on a 4xx
    assert "409" in str(exc_info.value)


def test_supabase_insert_audit_uses_client_side_id_and_merge_duplicates():
    store = _fake_supabase_store()
    captured = {}

    def fake_request(method, path, **kwargs):
        captured["path"] = path
        captured["headers"] = kwargs["headers"]
        captured["json"] = kwargs["json"]
        return _FakeResp(201, json_data=[kwargs["json"]])

    store._request = fake_request  # noqa: SLF001
    row = store.insert_audit({"business_id": "b1", "total_score": 10})

    assert "id" in row and row["id"]
    assert "on_conflict=id" in captured["path"]
    assert "resolution=merge-duplicates" in captured["headers"]["Prefer"]


def test_supabase_insert_metro_stats_uses_client_side_id_and_merge_duplicates():
    store = _fake_supabase_store()
    captured = {}

    def fake_request(method, path, **kwargs):
        captured["path"] = path
        captured["headers"] = kwargs["headers"]
        captured["json"] = kwargs["json"]
        return _FakeResp(201, json_data=[kwargs["json"]])

    store._request = fake_request  # noqa: SLF001
    row = store.insert_metro_stats({"metro": "Chicago North Shore", "sampled": 10})

    assert "id" in row and row["id"]
    assert "on_conflict=id" in captured["path"]
    assert "resolution=merge-duplicates" in captured["headers"]["Prefer"]


def test_supabase_log_event_does_not_retry_on_5xx(monkeypatch):
    store = _fake_supabase_store()
    call_count = {"n": 0}

    def fake_request(*a, **k):
        call_count["n"] += 1
        return _FakeResp(500, text="boom")

    monkeypatch.setattr(time, "sleep", lambda s: (_ for _ in ()).throw(AssertionError("must not sleep/retry on 5xx")))
    monkeypatch.setattr(store._session, "request", fake_request)

    with pytest.raises(RuntimeError):
        store.log_event("business", "b1", "test-event")

    assert call_count["n"] == 1  # events has no natural key to de-dupe on; a 5xx must not retry


def test_supabase_log_event_does_retry_on_429(monkeypatch):
    store = _fake_supabase_store()
    responses = [_FakeResp(429, text="rate limited"), _FakeResp(201, json_data=[{"id": 1}])]

    def fake_request(*a, **k):
        return responses.pop(0)

    monkeypatch.setattr(time, "sleep", lambda s: None)
    monkeypatch.setattr(store._session, "request", fake_request)

    store.log_event("business", "b1", "test-event")  # must not raise: 429 is retried even though idempotent=False
    assert responses == []


# ---------------------------------------------------------------------------
# M5: ID_TABLES restricts get_row/update_row to id-keyed tables
# ---------------------------------------------------------------------------


def test_id_tables_excludes_config_and_chains():
    assert "config" not in ID_TABLES
    assert "chains" not in ID_TABLES
    assert "businesses" in ID_TABLES


def test_get_row_rejects_id_less_tables(store):
    with pytest.raises(ValueError):
        store.get_row("config", "some-key")
    with pytest.raises(ValueError):
        store.get_row("chains", "some-pattern")


def test_update_row_rejects_id_less_tables(store):
    with pytest.raises(ValueError):
        store.update_row("config", "some-key", {"value": 1})
    with pytest.raises(ValueError):
        store.update_row("chains", "some-pattern", {"note": "x"})


# ---------------------------------------------------------------------------
# Minor (a): list_rows order_by tolerates mixed types
# ---------------------------------------------------------------------------


def test_list_rows_order_by_mixed_types_does_not_raise(store):
    store.upsert_business({**_business_row(place_id="mix-1"), "rating": 4.5})
    store.upsert_business({**_business_row(place_id="mix-2"), "rating": "no-rating"})

    rows = store.list_rows("businesses", order_by="rating")
    place_ids = {r["place_id"] for r in rows if r["place_id"] in ("mix-1", "mix-2")}
    assert place_ids == {"mix-1", "mix-2"}  # would previously raise TypeError comparing float/str


# ---------------------------------------------------------------------------
# Minor (b): LocalStore events id survives pruning (max(existing ids)+1, not len(rows)+1)
# ---------------------------------------------------------------------------


def test_local_store_log_event_id_survives_pruning(tmp_path):
    store = _local_factory(tmp_path)
    business = store.upsert_business(_business_row(place_id="place-event-prune"))
    store.log_event("business", business["id"], "e1")
    store.log_event("business", business["id"], "e2")

    events = store._read("events")  # noqa: SLF001
    assert [e["id"] for e in events] == [1, 2]

    store._write("events", events[1:])  # noqa: SLF001  simulate a retention job pruning id=1
    store.log_event("business", business["id"], "e3")

    ids_after = [e["id"] for e in store._read("events")]  # noqa: SLF001
    assert ids_after == [2, 3]  # not [2, 2] -- len(rows)+1 would have collided here


# ---------------------------------------------------------------------------
# Research lens: businesses.slug unique constraint enforced client-side by LocalStore
# ---------------------------------------------------------------------------


def test_local_store_upsert_business_rejects_slug_collision_across_place_ids(tmp_path):
    store = _local_factory(tmp_path)
    store.upsert_business(_business_row(place_id="place-slug-a", slug="glow-aesthetics"))

    with pytest.raises(ValueError):
        store.upsert_business(_business_row(place_id="place-slug-b", slug="glow-aesthetics"))


def test_local_store_upsert_business_same_place_id_can_keep_its_own_slug(tmp_path):
    store = _local_factory(tmp_path)
    first = store.upsert_business(_business_row(place_id="place-slug-c", slug="glow-aesthetics-c"))
    second = store.upsert_business(_business_row(place_id="place-slug-c", slug="glow-aesthetics-c", rating=5.0))
    assert first["id"] == second["id"]
    assert second["rating"] == 5.0
