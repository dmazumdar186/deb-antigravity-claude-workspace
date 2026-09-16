"""
test_round2_fixlearn.py
description: pytest suite for the round-2 learning-systems + long-horizon lens fixes: audit
    mode/max_measurable (audit/audit_site.py, audit/scoring.py), fit_weights.py's metro/mode
    filters + template-variant table + queue_pick stamp + --report-telegram, scoring.py
    --recompute's score_recompute_diff event logging, deals.py's evidence_ref requirement, and
    the new weekly workflow file.
inputs: pytest fixtures from conftest.py (local_store).
outputs: N/A (pytest).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from execution.personal_workflows.prodcraft_medspa.audit import scoring
from execution.personal_workflows.prodcraft_medspa.deals import deals
from execution.personal_workflows.prodcraft_medspa.scripts import fit_weights

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# scoring.py: max_measurable
# ---------------------------------------------------------------------------


def test_max_measurable_no_website_is_100():
    scored = scoring.score({"has_website": False})
    assert scored["max_measurable"] == 100


def test_max_measurable_fully_measured_site():
    signals = {
        "has_website": True,
        "booking_widget": "vagaro",
        "is_mobile_friendly": True,
        "psi_mobile": 80,
        "vision_dated_score": 2,
        "has_cta_above_fold": True,
        "has_ssl": True,
        "builder": "wordpress",
        "theme_year": 2024,
        "has_jquery_legacy": False,
        "has_analytics": True,
        "footer_year": 2026,
    }
    scored = scoring.score(signals)
    assert scored["max_measurable"] == 100  # 22+15+15+15+10+8+8+4+3


def test_max_measurable_degraded_site_excludes_unmeasured_signals():
    # Only booking_widget (grep-based, always measurable) and has_ssl are known; everything else
    # (PSI, vision, screenshots, tech-detect, analytics, footer) is None -- never checked.
    signals = {
        "has_website": True,
        "booking_widget": None,
        "is_mobile_friendly": None,
        "psi_mobile": None,
        "vision_dated_score": None,
        "has_cta_above_fold": None,
        "has_ssl": False,
        "builder": None,
        "theme_year": None,
        "has_jquery_legacy": None,
        "has_analytics": None,
        "footer_year": None,
    }
    scored = scoring.score(signals)
    assert scored["max_measurable"] == 22 + 8  # no_booking_widget + no_ssl only
    assert scored["total"] == 22 + 8  # both signals failed, so total == max_measurable here


def test_score_still_returns_all_prior_keys():
    scored = scoring.score({"has_website": True})
    assert set(scored) == {"total", "bucket", "gaps", "score_version", "max_measurable"}


# ---------------------------------------------------------------------------
# scoring.py --recompute: score_recompute_diff event logging
# ---------------------------------------------------------------------------


def test_recompute_logs_score_recompute_diff_event(local_store):
    business = local_store.upsert_business({"place_id": "p1", "name": "Old Score Spa", "metro": "chicago-north-shore"})
    # Stored audit row has a stale total_score/bucket that no longer matches score(signals).
    local_store.insert_audit(
        {
            "business_id": business["id"],
            "has_website": True,
            "booking_widget": None,
            "total_score": 5,
            "bucket": "skip",
            "gaps": [],
        }
    )
    checked = 0
    diff_count = 0
    for b in local_store.find_businesses(metro="chicago-north-shore"):
        latest = local_store.latest_audit(b["id"])
        if not latest:
            continue
        checked += 1
        signals = scoring._signals_from_audit_row(latest)
        recomputed = scoring.score(signals)
        if (
            recomputed["total"] != latest.get("total_score")
            or recomputed["bucket"] != latest.get("bucket")
            or recomputed["gaps"] != latest.get("gaps")
        ):
            diff_count += 1
            local_store.log_event(
                "business",
                b["id"],
                "score_recompute_diff",
                {
                    "old": {"total_score": latest.get("total_score"), "bucket": latest.get("bucket")},
                    "new": {"total_score": recomputed["total"], "bucket": recomputed["bucket"]},
                    "score_version": recomputed["score_version"],
                },
            )
    assert checked == 1
    assert diff_count == 1
    events = [e for e in local_store._read("events") if e["event"] == "score_recompute_diff"]
    assert len(events) == 1
    assert events[0]["payload"]["old"]["total_score"] == 5
    assert events[0]["payload"]["new"]["total_score"] == 22  # no_booking_widget only


def _run_scoring_cli(args):
    return subprocess.run(
        [sys.executable, "-m", "execution.personal_workflows.prodcraft_medspa.audit.scoring", *args],
        cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def test_recompute_cli_never_patches_rows(tmp_path):
    store_root = tmp_path / "store"
    from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore

    st = LocalStore(root=store_root)
    business = st.upsert_business({"place_id": "p2", "name": "CLI Spa", "metro": "chicago-north-shore"})
    st.insert_audit({"business_id": business["id"], "has_website": True, "total_score": 1, "bucket": "skip", "gaps": []})

    proc = _run_scoring_cli(
        ["--recompute", "--metro", "chicago-north-shore", "--mock", "--store-root", str(store_root)]
    )
    assert proc.returncode == 0, proc.stderr
    stat = json.loads(proc.stdout.strip().splitlines()[-1])
    assert stat["diffs"] == 1

    # Row on disk is untouched -- scoring.py --recompute never patches.
    st2 = LocalStore(root=store_root)
    latest = st2.latest_audit(business["id"])
    assert latest["total_score"] == 1

    events = [e for e in st2._read("events") if e["event"] == "score_recompute_diff"]
    assert len(events) == 1


# ---------------------------------------------------------------------------
# fit_weights.py: --metro, --mode, template-variant table, queue_pick stamp
# ---------------------------------------------------------------------------


_SEED_COUNTER = {"n": 0}


def _seed_outreach_with_audit(store, *, metro, mode, replied, variant="a", vision_score=8):
    _SEED_COUNTER["n"] += 1
    business = store.upsert_business(
        {"place_id": f"place-{metro}-{variant}-{replied}-{mode}-{_SEED_COUNTER['n']}", "name": "Fit Spa", "metro": metro}
    )
    audit = store.insert_audit(
        {
            "business_id": business["id"],
            "has_website": True,
            "booking_widget": None,
            "is_mobile_friendly": False,
            "psi_mobile": 40,
            "vision_dated_score": vision_score,
            "has_cta_above_fold": False,
            "has_ssl": True,
            "total_score": 60,
            "bucket": "qualified",
            "gaps": [],
            "mode": mode,
        }
    )
    status = "replied" if replied else "sent"
    store.upsert_outreach(
        {
            "business_id": business["id"],
            "audit_id": audit["id"],
            "touch": 1,
            "status": status,
            "template_variant": variant,
            "sent_at": "2026-09-01T00:00:00Z",
            "replied_at": "2026-09-02T00:00:00Z" if replied else None,
        }
    )
    return business, audit


def test_touch1_outcomes_metro_filter(local_store):
    _seed_outreach_with_audit(local_store, metro="chicago-north-shore", mode="full", replied=True)
    _seed_outreach_with_audit(local_store, metro="minneapolis", mode="full", replied=False)

    chicago_only = fit_weights.touch1_outcomes(local_store, metro="chicago-north-shore", mode="full")
    assert len(chicago_only) == 1
    assert chicago_only[0][0]["business_id"] in {b["id"] for b in local_store.find_businesses(metro="chicago-north-shore")}

    all_metros = fit_weights.touch1_outcomes(local_store, metro=None, mode="full")
    assert len(all_metros) == 2


def test_touch1_outcomes_mode_filter_excludes_other_mode(local_store):
    _seed_outreach_with_audit(local_store, metro="chicago-north-shore", mode="full", replied=True, variant="a")
    _seed_outreach_with_audit(local_store, metro="chicago-north-shore", mode="degraded", replied=False, variant="b")

    full_only = fit_weights.touch1_outcomes(local_store, metro=None, mode="full")
    assert len(full_only) == 1

    degraded_only = fit_weights.touch1_outcomes(local_store, metro=None, mode="degraded")
    assert len(degraded_only) == 1

    both = fit_weights.touch1_outcomes(local_store, metro=None, mode="all")
    assert len(both) == 2


def test_touch1_outcomes_mode_filter_excludes_legacy_rows_without_mode(local_store):
    # An audit row predating the `mode` column (no "mode" key at all) must not silently count
    # as "full" -- it should only show up under --mode all.
    business = local_store.upsert_business({"place_id": "legacy-1", "name": "Legacy Spa", "metro": "chicago-north-shore"})
    audit = local_store.insert_audit(
        {"business_id": business["id"], "has_website": True, "total_score": 30, "bucket": "borderline", "gaps": []}
    )
    local_store.upsert_outreach(
        {"business_id": business["id"], "audit_id": audit["id"], "touch": 1, "status": "sent", "sent_at": "2026-08-01T00:00:00Z"}
    )
    assert fit_weights.touch1_outcomes(local_store, metro=None, mode="full") == []
    assert len(fit_weights.touch1_outcomes(local_store, metro=None, mode="all")) == 1


def test_fit_weights_invalid_mode_raises(local_store):
    with pytest.raises(ValueError):
        fit_weights.touch1_outcomes(local_store, metro=None, mode="bogus")


def test_template_variant_table_groups_by_variant(local_store):
    _seed_outreach_with_audit(local_store, metro="chicago-north-shore", mode="full", replied=True, variant="a")
    _seed_outreach_with_audit(local_store, metro="chicago-north-shore", mode="full", replied=False, variant="a")
    _seed_outreach_with_audit(local_store, metro="chicago-north-shore", mode="full", replied=True, variant="b")

    rows = fit_weights.touch1_outcomes(local_store, metro=None, mode="full")
    table = fit_weights.template_variant_table(rows)
    assert table["a"]["n"] == 2
    assert table["a"]["reply_rate"] == pytest.approx(0.5)
    assert table["b"]["n"] == 1
    assert table["b"]["reply_rate"] == pytest.approx(1.0)


def test_template_variant_table_groups_missing_variant_as_unknown(local_store):
    business = local_store.upsert_business({"place_id": "novar-1", "name": "No Variant Spa", "metro": "chicago-north-shore"})
    audit = local_store.insert_audit({"business_id": business["id"], "has_website": True, "total_score": 10, "bucket": "skip", "gaps": [], "mode": "full"})
    local_store.upsert_outreach({"business_id": business["id"], "audit_id": audit["id"], "touch": 1, "status": "sent", "sent_at": "2026-08-01T00:00:00Z"})
    rows = fit_weights.touch1_outcomes(local_store, metro=None, mode="full")
    table = fit_weights.template_variant_table(rows)
    assert table["unknown"]["n"] == 1


def test_fit_weights_cli_stamps_metro_mode_queue_pick(tmp_path):
    from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore

    store_root = tmp_path / "store"
    st = LocalStore(root=store_root)
    st.set_config("queue_pick", "score")
    for i in range(50):
        _seed_outreach_with_audit(st, metro="chicago-north-shore", mode="full", replied=(i % 5 == 0), variant="a" if i % 2 else "b")

    proc = subprocess.run(
        [
            sys.executable, "-m", "execution.personal_workflows.prodcraft_medspa.scripts.fit_weights",
            "--store-root", str(store_root), "--metro", "chicago-north-shore", "--mode", "full", "--min-sent", "50",
        ],
        cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 0, proc.stderr
    out_path = REPO_ROOT / ".tmp" / "prodcraft_medspa" / "fit_weights.json"
    result = json.loads(out_path.read_text(encoding="utf-8"))
    assert result["metro"] == "chicago-north-shore"
    assert result["mode"] == "full"
    assert result["queue_pick"] == "score"
    assert "template_variants" in result
    assert result["n_touch1_sent"] == 50


def test_fit_weights_report_telegram_mock_prints_not_enough_data(tmp_path, capsys):
    store_root = tmp_path / "store"
    proc = subprocess.run(
        [
            sys.executable, "-m", "execution.personal_workflows.prodcraft_medspa.scripts.fit_weights",
            "--mock", "--store-root", str(store_root), "--report-telegram", "--min-sent", "50",
        ],
        cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 0, proc.stderr
    assert "not enough data yet: 0/50 sends" in proc.stdout


def test_build_telegram_lines_has_no_em_dash_and_is_short():
    result = {
        "n_touch1_sent": 60,
        "overall_reply_rate": 0.15,
        "signals": {
            "no_booking_widget": {"point_biserial_r": 0.42},
            "dated_design": {"point_biserial_r": -0.10},
        },
    }
    variant_table = {"a": {"n": 30, "reply_rate": 0.2}, "b": {"n": 30, "reply_rate": 0.1}}
    lines = fit_weights.build_telegram_lines(result, variant_table, "chicago-north-shore", "full", "score")
    assert len(lines) <= 6
    for line in lines:
        assert "—" not in line
    assert any("chicago-north-shore" in line for line in lines)
    assert any("score" in line for line in lines)


# ---------------------------------------------------------------------------
# deals.py: evidence_ref requirement
# ---------------------------------------------------------------------------


def _make_business(store, name="Evidence Spa"):
    return store.upsert_business({"place_id": f"place-{name}", "name": name, "metro": "chicago-north-shore"})


def test_record_with_baseline_requires_evidence_ref(local_store):
    business = _make_business(local_store)
    with pytest.raises(ValueError, match="evidence-ref"):
        deals.record(
            local_store, business_id=business["id"], tier="growth", setup_price=None, mrr=None,
            signed=None, baseline=10, booking_tool=None, evidence_ref=None,
        )


def test_record_with_baseline_and_evidence_ref_stores_it(local_store):
    business = _make_business(local_store)
    deal = deals.record(
        local_store, business_id=business["id"], tier="growth", setup_price=None, mrr=None,
        signed=None, baseline=10, booking_tool=None, evidence_ref="https://example.test/baseline.png",
    )
    assert deal["baseline_evidence_ref"] == "https://example.test/baseline.png"


def test_record_without_baseline_does_not_require_evidence_ref(local_store):
    business = _make_business(local_store)
    deal = deals.record(
        local_store, business_id=business["id"], tier="growth", setup_price=None, mrr=None,
        signed=None, baseline=None, booking_tool=None, evidence_ref=None,
    )
    assert deal["business_id"] == business["id"]


def test_proof_requires_evidence_ref(local_store):
    business = _make_business(local_store)
    deals.record(
        local_store, business_id=business["id"], tier="growth", setup_price=None, mrr=None,
        signed=None, baseline=10, booking_tool=None, evidence_ref="https://example.test/baseline.png",
    )
    with pytest.raises(ValueError, match="evidence-ref"):
        deals.proof(local_store, business_id=business["id"], bookings_60d=25, evidence_ref=None)


def test_proof_requires_baseline_evidence_ref_on_file(local_store):
    business = _make_business(local_store)
    # Simulate a deal recorded before this contract existed: baseline present, no evidence ref.
    local_store.upsert_deal({"business_id": business["id"], "tier": "growth", "baseline_online_bookings_30d": 10})
    with pytest.raises(ValueError, match="baseline_evidence_ref"):
        deals.proof(local_store, business_id=business["id"], bookings_60d=25, evidence_ref="https://example.test/day60.png")


def test_proof_with_both_evidence_refs_succeeds_and_stores_ref(local_store):
    business = _make_business(local_store)
    deals.record(
        local_store, business_id=business["id"], tier="growth", setup_price=None, mrr=None,
        signed=None, baseline=10, booking_tool=None, evidence_ref="https://example.test/baseline.png",
    )
    result = deals.proof(local_store, business_id=business["id"], bookings_60d=25, evidence_ref="https://example.test/day60.png")
    assert result["deal"]["evidence_ref"] == "https://example.test/day60.png"
    assert result["deal"]["guarantee_met"] is True


def _run_deals_cli(args):
    return subprocess.run(
        [sys.executable, "-m", "execution.personal_workflows.prodcraft_medspa.deals.deals", *args],
        cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def test_deals_cli_record_baseline_without_evidence_ref_fails(tmp_path):
    store_root = tmp_path / "store"
    proc = _run_deals_cli(
        ["record", "--business-id", "biz-1", "--tier", "growth", "--baseline", "10",
         "--mock", "--store-root", str(store_root)]
    )
    assert proc.returncode != 0
    assert "evidence-ref" in proc.stderr


def test_deals_cli_record_baseline_with_evidence_ref_succeeds(tmp_path):
    store_root = tmp_path / "store"
    proc = _run_deals_cli(
        ["record", "--business-id", "biz-1", "--tier", "growth", "--baseline", "10",
         "--evidence-ref", "https://example.test/baseline.png",
         "--mock", "--store-root", str(store_root)]
    )
    assert proc.returncode == 0, proc.stderr


# ---------------------------------------------------------------------------
# Migration 0004 + weekly workflow — static file checks
# ---------------------------------------------------------------------------


def test_migration_0004_is_idempotent_sql_text():
    path = REPO_ROOT / "execution/personal_workflows/prodcraft_medspa/db/migrations/0004_measurement_columns.sql"
    text = path.read_text(encoding="utf-8")
    for col in ("audits add column if not exists mode", "audits add column if not exists max_measurable",
                "audits add column if not exists llm_cost_usd", "outreach add column if not exists score_at_send",
                "deals add column if not exists evidence_ref", "deals add column if not exists baseline_evidence_ref"):
        assert col in text


def test_weekly_workflow_yaml_is_valid_and_wired():
    import yaml

    path = REPO_ROOT / ".github/workflows/prodcraft_medspa_weekly.yml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert True in doc or "on" in doc  # PyYAML parses bare `on:` as boolean True key
    schedule_key = True if True in doc else "on"
    assert doc[schedule_key]["schedule"][0]["cron"] == "0 15 * * 1"
    assert doc["concurrency"]["group"] == "prodcraft-medspa"
    job = doc["jobs"]["weekly"]
    assert job["if"] == "vars.PRODCRAFT_CRON_ENABLED == 'true'"
    run_step = next(s for s in job["steps"] if "fit_weights.py" in s.get("run", ""))
    assert "--store supabase" in run_step["run"]
    assert "--report-telegram" in run_step["run"]
