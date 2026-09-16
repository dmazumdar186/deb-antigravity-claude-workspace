"""
test_round2_fixdb.py
description: Tests for the round-2 audit-stack fixes owned by the "fixdb" worker (see CONTRACTS.md
    and the round-2 audit findings): schema/migration consistency, Store upsert_preview merge
    guards + manual_patch + purge_pii, build_preview.py's orphan-event fix, state_machine.py's
    redraft transition + non-skippable dnc takedown, common/config_validate.py, sync_sheets.py's
    column-letter helper, doctor.py's new checks, verify.py's domain-only logging, import_csv.py's
    email validation + import event, advance.py's clean --date usage error, fit_weights.py's
    None-as-unknown boolean signals, and deals.py's zero-baseline guarantee floor.
inputs: N/A (pytest); local_store/fixtures_root from conftest.py, _seed_glow/_run_build reused from
    test_preview.py.
outputs: N/A (pytest).
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from execution.personal_workflows.prodcraft_medspa.common import config_validate
from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore
from execution.personal_workflows.prodcraft_medspa.deals import deals
from execution.personal_workflows.prodcraft_medspa.discovery import import_csv
from execution.personal_workflows.prodcraft_medspa.enrich import verify as verify_mod
from execution.personal_workflows.prodcraft_medspa.outreach import advance, state_machine
from execution.personal_workflows.prodcraft_medspa.preview import build_preview
from execution.personal_workflows.prodcraft_medspa.scripts import doctor, purge_pii, sync_sheets
from tests.prodcraft_medspa.conftest import PKG_ROOT
from tests.prodcraft_medspa.test_preview import _run_build, _seed_glow

REPO_ROOT = PKG_ROOT.parents[2]


# ---------------------------------------------------------------------------
# Item 1: schema / migration consistency
# ---------------------------------------------------------------------------


def test_schema_sql_and_migration_0003_agree_on_new_columns():
    schema_sql = (PKG_ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    migration_sql = (PKG_ROOT / "db" / "migrations" / "0003_round2_columns.sql").read_text(encoding="utf-8")

    new_columns = [
        "gmail_message_id",
        "sent_via",
        "seen_reply_ids",
        "publish_mode",
        "local_build_dir",
        "email_policy",
        "min_score",
        "hosted_at",
        "original_host",
        "discovery_source",
        "llm_overrides",
        "pii_purged_at",
    ]
    for col in new_columns:
        assert col in schema_sql, f"{col} missing from schema.sql"
        assert col in migration_sql, f"{col} missing from 0003_round2_columns.sql"

    # every ADD COLUMN in the migration must be IF NOT EXISTS (idempotent, safe to re-run)
    for line in migration_sql.splitlines():
        if line.strip().lower().startswith("alter table") and "add column" in line.lower():
            assert "if not exists" in line.lower(), f"non-idempotent ADD COLUMN: {line}"


def test_audits_is_mobile_friendly_stays_nullable():
    schema_sql = (PKG_ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    for line in schema_sql.splitlines():
        if "is_mobile_friendly" in line:
            assert "not null" not in line.lower()


# ---------------------------------------------------------------------------
# Item 2: Store.upsert_preview merge guards + manual_patch + purge_pii
# ---------------------------------------------------------------------------


def test_upsert_preview_never_downgrades_approved_status(local_store):
    business = local_store.upsert_business({"place_id": "p-up1", "name": "A", "slug": "a", "metro": "m"})
    row = {"business_id": business["id"], "content_hash": "h1", "subdomain_url": "https://a.example", "status": "review"}
    created = local_store.upsert_preview(row)
    local_store.update_preview(created["id"], {"status": "approved"})

    reupserted = local_store.upsert_preview({**row, "status": "review"})
    assert reupserted["id"] == created["id"]
    assert reupserted["status"] == "approved"


def test_upsert_preview_never_silently_overwrites_subdomain_url(local_store):
    business = local_store.upsert_business({"place_id": "p-up2", "name": "B", "slug": "b", "metro": "m"})
    row = {"business_id": business["id"], "content_hash": "h2", "subdomain_url": "https://original.example", "status": "review"}
    created = local_store.upsert_preview(row)

    reupserted = local_store.upsert_preview({**row, "subdomain_url": "https://different.example"})
    assert reupserted["id"] == created["id"]
    assert reupserted["subdomain_url"] == "https://original.example"


def test_upsert_preview_returns_existing_id_on_merge(local_store):
    business = local_store.upsert_business({"place_id": "p-up3", "name": "C", "slug": "c", "metro": "m"})
    row = {"business_id": business["id"], "content_hash": "h3", "subdomain_url": "https://c.example", "status": "review"}
    first = local_store.upsert_preview(row)
    second = local_store.upsert_preview({**row, "status": "live"})
    assert second["id"] == first["id"]
    assert second["status"] == "live"


def test_manual_patch_updates_row_and_logs_event(local_store):
    business = local_store.upsert_business({"place_id": "p-mp1", "name": "D", "slug": "d", "metro": "m"})
    updated = local_store.manual_patch("businesses", business["id"], {"owner_name": "Jane"}, reason="operator fix")
    assert updated["owner_name"] == "Jane"

    events = local_store.list_rows("events", entity="businesses")
    manual_events = [e for e in events if e["event"] == "manual_patch"]
    assert len(manual_events) == 1
    assert manual_events[0]["payload"] == {"table": "businesses", "id": business["id"], "fields": ["owner_name"], "reason": "operator fix"}


def test_purge_pii_blanks_business_and_outreach_pii(local_store):
    business = local_store.upsert_business(
        {"place_id": "p-pii1", "name": "E", "slug": "e", "metro": "m", "owner_name": "John", "owner_email": "john@e.com", "phone": "555-1111"}
    )
    outreach = local_store.upsert_outreach(
        {"business_id": business["id"], "touch": 1, "status": "sent", "gmail_message_id": "abc", "reply_excerpt": "call me at 555"}
    )

    updated = local_store.purge_pii(business["id"], reason="dnc retention")
    assert updated["owner_name"] is None
    assert updated["owner_email"] is None
    assert updated["phone"] is None
    assert updated["do_not_contact"] is True
    assert updated["pii_purged_at"] is not None

    outreach_after = local_store.get_row("outreach", outreach["id"])
    assert outreach_after["gmail_message_id"] is None
    assert outreach_after["reply_excerpt"] is None
    assert outreach_after["status"] == "sent"  # status untouched
    assert outreach_after["pii_purged_at"] is not None

    events = local_store.list_rows("events", entity="business", event="pii_purged")
    assert len(events) == 1
    assert events[0]["payload"]["reason"] == "dnc retention"


def test_purge_pii_cli_end_to_end(tmp_path):
    store_root = tmp_path / "store"
    store = LocalStore(root=store_root)
    business = store.upsert_business({"place_id": "p-pii2", "name": "F", "slug": "f", "metro": "m", "owner_email": "f@e.com"})

    purge_pii.main(["--business-id", business["id"], "--reason", "test", "--mock", "--store-root", str(store_root)])

    reopened = LocalStore(root=store_root)
    after = reopened.get_business(business["id"])
    assert after["owner_email"] is None
    assert after["do_not_contact"] is True


# ---------------------------------------------------------------------------
# Item 3: build_preview.py uses the RETURNED preview row's id (no orphan events)
# ---------------------------------------------------------------------------


def test_rebuild_same_content_leaves_no_orphan_preview_events(local_store, tmp_path):
    business, _audit = _seed_glow(local_store)
    _run_build(local_store, business, tmp_path)
    _run_build(local_store, business, tmp_path, force=True)  # same content -> merge, not a new row

    previews = build_preview.find_previews_for_business(local_store, business["id"])
    assert len(previews) == 1
    preview_id = previews[0]["id"]

    preview_events = [e for e in local_store.list_rows("events") if e.get("entity") == "preview" and e.get("entity_id") == preview_id]
    events_by_name = {e["event"] for e in preview_events}
    assert {"built", "published"}.issubset(events_by_name)
    # every preview event references the one real, stored preview row — no id generated before
    # upsert_preview() and then discarded.
    for e in preview_events:
        assert e["entity_id"] == preview_id


# ---------------------------------------------------------------------------
# Item 4: state_machine.py redraft + non-skippable, idempotent dnc takedown
# ---------------------------------------------------------------------------


def _seed_outreach_with_preview(store):
    business = store.upsert_business({"place_id": "p-sm1", "name": "G", "slug": "g", "metro": "m"})
    preview = store.upsert_preview(
        {"business_id": business["id"], "content_hash": "hsm1", "subdomain_url": "https://g.example", "status": "review"}
    )
    outreach = store.upsert_outreach({"business_id": business["id"], "touch": 1, "status": "sent", "preview_id": preview["id"]})
    return business, preview, outreach


def test_redraft_transitions_drafted_to_queued_with_reason(local_store):
    business = local_store.upsert_business({"place_id": "p-sm2", "name": "H", "slug": "h", "metro": "m"})
    outreach = local_store.upsert_outreach({"business_id": business["id"], "touch": 1, "status": "drafted"})

    updated = state_machine.redraft(local_store, outreach["id"], reason="lint failed")
    assert updated["status"] == "queued"

    events = [e for e in local_store.list_rows("events", entity="outreach", entity_id=outreach["id"]) if e["event"] == "status:drafted->queued"]
    assert len(events) == 1
    assert events[0]["payload"]["fields"]["reason"] == "lint failed"


def test_redraft_unknown_outreach_id_raises_key_error(local_store):
    with pytest.raises(KeyError):
        state_machine.redraft(local_store, "does-not-exist", reason="x")


def test_dnc_calls_takedown_fn_exactly_once_across_two_calls(local_store):
    _business, preview, outreach = _seed_outreach_with_preview(local_store)
    calls: list[str] = []

    def fake_takedown_fn(preview_row: dict) -> dict:
        calls.append(preview_row["id"])
        local_store.update_preview(preview_row["id"], {"status": "takedown", "takedown": True})
        return {"status": "takedown", "r2_objects_deleted": 0, "outreach_closed": 0}

    row1 = state_machine.transition(local_store, outreach, "dnc", takedown_fn=fake_takedown_fn, reason="remove")
    assert row1["status"] == "dnc"
    assert calls == [preview["id"]]

    # A second dnc call against a (now terminal) row is illegal, so re-check the guard the way a
    # real second wave would exercise it: directly re-running the takedown helper for the same
    # preview, which is now already marked takedown.
    reloaded_preview = local_store.get_row("previews", preview["id"])
    state_machine._takedown_one_preview(local_store, reloaded_preview, fake_takedown_fn)
    assert calls == [preview["id"]]  # takedown_fn was NOT called again


def test_dnc_missing_preview_row_logs_warning_not_crash(local_store, capsys):
    business = local_store.upsert_business({"place_id": "p-sm3", "name": "I", "slug": "i", "metro": "m"})
    outreach = local_store.upsert_outreach(
        {"business_id": business["id"], "touch": 1, "status": "sent", "preview_id": "ghost-preview-id"}
    )
    updated = state_machine.transition(local_store, outreach, "dnc", reason="remove")
    assert updated["status"] == "dnc"
    captured = capsys.readouterr()
    assert "ghost-preview-id" in captured.err


# ---------------------------------------------------------------------------
# Item 5 / 11 / 15: common/config_validate.py
# ---------------------------------------------------------------------------


def test_validate_config_accepts_seed_config():
    seed_config = json.loads((PKG_ROOT / "db" / "seed_config.json").read_text(encoding="utf-8"))
    assert config_validate.validate_config(seed_config) == []


@pytest.mark.parametrize(
    "cfg,expected_substring",
    [
        ({"queue_pick": "bogus"}, "queue_pick"),
        ({"email_policy": "bogus"}, "email_policy"),
        ({"preview_publish_mode": "bogus"}, "preview_publish_mode"),
        ({"min_score": 10}, "min_score"),
        ({"min_score": 200}, "min_score"),
        ({"live_send_confirmed": "yes"}, "live_send_confirmed"),
        ({"auto_approve_previews": "yes"}, "auto_approve_previews"),
        ({"preview_host_suffix": "prodcraft.fyi"}, "preview_host_suffix"),
        ({"phase0": {"cap": 0}}, "phase0.cap"),
        ({"phase0": {"cap": 51}}, "phase0.cap"),
        ({"phase0": {"warmup_days": 61}}, "phase0.warmup_days"),
        ({"phase0": {"warmup_days": -1}}, "phase0.warmup_days"),
        ({"phase0": {"cap": 5, "warmup_start_cap": 6}}, "phase0.warmup_start_cap"),
        ({"phase0": {"queue_pick_until_passed": "bogus"}}, "phase0.queue_pick_until_passed"),
        ({"phase0": "not-a-dict"}, "phase0"),
    ],
)
def test_validate_config_rejects_bad_values(cfg, expected_substring):
    problems = config_validate.validate_config(cfg)
    assert any(expected_substring in p for p in problems), problems


def test_validate_config_treats_missing_keys_as_not_configured():
    assert config_validate.validate_config({}) == []
    assert config_validate.validate_config({"phase0": {}}) == []


def test_assert_valid_config_raises_value_error_listing_every_problem():
    with pytest.raises(ValueError) as exc_info:
        config_validate.assert_valid_config({"queue_pick": "bogus", "min_score": 999})
    assert "queue_pick" in str(exc_info.value)
    assert "min_score" in str(exc_info.value)


def test_phase0_warmup_start_cap_within_cap_is_valid():
    assert config_validate.validate_config({"phase0": {"cap": 10, "warmup_start_cap": 2}}) == []


# ---------------------------------------------------------------------------
# Item 6: sync_sheets.py column-letter helper + reject_mock_with_supabase guard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "n,expected",
    [(1, "A"), (2, "B"), (26, "Z"), (27, "AA"), (28, "AB"), (52, "AZ"), (53, "BA"), (702, "ZZ"), (703, "AAA")],
)
def test_column_letter_handles_more_than_26_columns(n, expected):
    assert sync_sheets._column_letter(n) == expected


def test_column_letter_rejects_non_positive():
    with pytest.raises(ValueError):
        sync_sheets._column_letter(0)


def test_sync_sheets_cli_mock_with_store_supabase_exits_2():
    proc = subprocess.run(
        [sys.executable, "-m", "execution.personal_workflows.prodcraft_medspa.scripts.sync_sheets", "--mock", "--store", "supabase"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert proc.returncode == 2


# ---------------------------------------------------------------------------
# Item 7 / 14: doctor.py new checks
# ---------------------------------------------------------------------------


def test_check_sender_address_is_valid_accepts_well_formed_address(local_store):
    local_store.set_config("sender", {"name": "Jane", "physical_address": "123 Main St, Winnetka, IL 60093"})
    ok, detail = doctor.check_sender_address_is_valid(local_store)
    assert ok is True, detail


def test_check_sender_address_is_valid_rejects_placeholder(local_store):
    local_store.set_config("sender", {"name": "Jane", "physical_address": "operator to confirm"})
    ok, detail = doctor.check_sender_address_is_valid(local_store)
    assert ok is False
    assert "placeholder" in detail


def test_check_sender_address_is_valid_skips_when_unset(local_store):
    ok, detail = doctor.check_sender_address_is_valid(local_store)
    assert ok is None


def test_check_email_found_rate_reports_na_below_ten_rows(local_store):
    status, detail = doctor.check_email_found_rate(local_store)
    assert status == "n/a"


def test_check_email_found_rate_warns_below_30_percent(local_store, monkeypatch):
    import datetime as dt

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    for i in range(12):
        local_store.upsert_business(
            {
                "place_id": f"p-rate-{i}",
                "name": f"biz{i}",
                "slug": f"biz{i}",
                "metro": "m",
                "email_status": "deliverable" if i < 2 else "undeliverable",
                "owner_email": f"o{i}@e.com" if i < 2 else None,
                "updated_at": now,
            }
        )
    status, detail = doctor.check_email_found_rate(local_store)
    assert status == "WARN", detail


def test_check_spf_dmarc_unchecked_without_sender_email(local_store):
    spf, dmarc, detail = doctor.check_spf_dmarc(local_store)
    assert spf == "unchecked"
    assert dmarc == "unchecked"


def test_doctor_never_crashes_with_no_env(tmp_path, monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    proc = subprocess.run(
        [sys.executable, "-m", "execution.personal_workflows.prodcraft_medspa.scripts.doctor", "--stages", "store"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    # doctor must never traceback; exit 0 or 1 (missing stage), never an uncaught exception.
    assert "Traceback" not in proc.stderr
    assert proc.returncode in (0, 1)


def test_service_env_vars_r2_includes_r2_credentials():
    assert "R2_ACCESS_KEY_ID" in doctor.SERVICE_ENV_VARS["r2"]
    assert "R2_SECRET_ACCESS_KEY" in doctor.SERVICE_ENV_VARS["r2"]


# ---------------------------------------------------------------------------
# Item 8: verify.py domain-only logging; import_csv.py email validation + import event;
# advance.py clean --date usage error
# ---------------------------------------------------------------------------


def test_verify_unset_api_key_logs_domain_only_never_full_address(capsys, tmp_path):
    status, cost = verify_mod.verify("prospect.owner@example-medspa.test", mock=False, fixtures_root=tmp_path, api_key=None)
    assert status == "unverified"
    captured = capsys.readouterr()
    assert "prospect.owner@example-medspa.test" not in captured.err
    assert "@example-medspa.test" in captured.err


@pytest.mark.parametrize(
    "email,expect_kept",
    [
        ("owner@example-medspa.test", True),
        ("owner @example-medspa.test", False),  # space
        ("owner@localcompany", False),  # missing TLD
        ("not-an-email", False),
    ],
)
def test_import_csv_email_validation(email, expect_kept):
    rows, _dropped = import_csv.process_csv_rows(
        [{"name": "Biz", "address": "1 Main St", "email": email, "review_count": "20"}],
        chains=[],
        metro="m",
        source="manual",
        existing_slugs={},
    )
    assert len(rows) == 1
    if expect_kept:
        assert rows[0]["owner_email"] == email
        assert rows[0]["email_status"] == "unverified"
    else:
        assert "owner_email" not in rows[0]


def test_import_csv_logs_one_import_event_per_business(local_store):
    rows, _dropped = import_csv.process_csv_rows(
        [{"name": "Biz", "address": "1 Main St", "email": "owner@example-medspa.test", "review_count": "20"}],
        chains=[],
        metro="m",
        source="manual",
        existing_slugs={},
    )
    for row in rows:
        stored = local_store.upsert_business(row)
        local_store.log_event("business", stored["id"], "import", {"source": row.get("discovery_source"), "had_email": bool(row.get("owner_email"))})

    import_events = local_store.list_rows("events", event="import")
    assert len(import_events) == 1
    assert import_events[0]["payload"] == {"source": "csv:manual", "had_email": True}


def test_advance_parse_date_bad_value_exits_2_no_traceback():
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "execution.personal_workflows.prodcraft_medspa.outreach.advance",
            "--date",
            "not-a-date",
            "--mock",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert proc.returncode == 2
    assert "Traceback" not in proc.stderr
    assert "invalid --date" in proc.stderr


# ---------------------------------------------------------------------------
# Item 9: fit_weights.py — None boolean signal is "unknown", never False
# ---------------------------------------------------------------------------


def test_bool_signal_none_is_excluded_not_false():
    from execution.personal_workflows.prodcraft_medspa.scripts.fit_weights import SIGNALS

    fn = SIGNALS["not_mobile_friendly"]
    assert fn({"is_mobile_friendly": None}) is None
    assert fn({"is_mobile_friendly": False}) is True  # is_mobile_friendly=False -> "not mobile friendly" signal fires
    assert fn({"is_mobile_friendly": True}) is False


def test_compute_signal_table_excludes_none_rows_from_that_signal():
    from execution.personal_workflows.prodcraft_medspa.scripts.fit_weights import compute_signal_table

    rows = [
        ({"is_mobile_friendly": None, "has_website": True}, True),
        ({"is_mobile_friendly": False, "has_website": True}, False),
        ({"is_mobile_friendly": True, "has_website": True}, True),
    ]
    result = compute_signal_table(rows)
    signal = result["signals"]["not_mobile_friendly"]
    # the None row must be excluded entirely — n_true + n_false == 2, not 3.
    assert signal["n_true"] + signal["n_false"] == 2


# ---------------------------------------------------------------------------
# Item 10: deals.py zero-baseline guarantee floor
# ---------------------------------------------------------------------------


def test_guarantee_not_trivially_met_with_zero_baseline(local_store):
    business = local_store.upsert_business({"place_id": "p-deal1", "name": "J", "slug": "j", "metro": "m"})
    deals.record(local_store, business_id=business["id"], tier="starter", setup_price=None, mrr=None, signed=None, baseline=0, booking_tool=None)
    result = deals.proof(local_store, business_id=business["id"], bookings_60d=1)
    assert result["deal"]["guarantee_met"] is False
    assert result["threshold_2x_baseline"] == deals.ZERO_BASELINE_FLOOR * 2


def test_guarantee_met_above_floored_threshold(local_store):
    business = local_store.upsert_business({"place_id": "p-deal2", "name": "K", "slug": "k", "metro": "m"})
    deals.record(local_store, business_id=business["id"], tier="starter", setup_price=None, mrr=None, signed=None, baseline=0, booking_tool=None)
    result = deals.proof(local_store, business_id=business["id"], bookings_60d=11)
    assert result["deal"]["guarantee_met"] is True


def test_guarantee_uses_real_baseline_when_above_floor(local_store):
    business = local_store.upsert_business({"place_id": "p-deal3", "name": "L", "slug": "l", "metro": "m"})
    deals.record(local_store, business_id=business["id"], tier="starter", setup_price=None, mrr=None, signed=None, baseline=20, booking_tool=None)
    result = deals.proof(local_store, business_id=business["id"], bookings_60d=41)
    assert result["threshold_2x_baseline"] == 40
    assert result["deal"]["guarantee_met"] is True
