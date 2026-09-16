"""
test_scripts.py
description: Tests for execution/personal_workflows/prodcraft_medspa/scripts/* — run_metro funnel
    math, stage-failure handling, doctor's env-presence + exit-code gating, fit_weights' refuse
    threshold and correlation math, sync_sheets' mock CSV shape, and a YAML sanity check on both
    GitHub Actions workflow files.
inputs: N/A (pytest).
outputs: N/A (pytest); some tests write under tmp_path only.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PKG_ROOT = REPO_ROOT / "execution" / "personal_workflows" / "prodcraft_medspa"

from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore
from execution.personal_workflows.prodcraft_medspa.scripts import (  # noqa: E402
    doctor,
    fit_weights,
    run_metro,
    sync_sheets,
)
from execution.personal_workflows.prodcraft_medspa.scripts._stage_runner import (  # noqa: E402
    common_store_args,
    parse_stat_line,
    reject_mock_with_supabase,
    resolve_store_kind,
    run_module,
)


# ---------------------------------------------------------------------------
# _stage_runner
# ---------------------------------------------------------------------------


def test_parse_stat_line_finds_last_json_line():
    stdout = "some log line\nanother line\n" + json.dumps({"script": "x", "in": 3, "out": 2, "dropped": {}})
    stat = parse_stat_line(stdout)
    assert stat == {"script": "x", "in": 3, "out": 2, "dropped": {}}


def test_parse_stat_line_returns_none_without_script_key():
    assert parse_stat_line("no json here\n{\"foo\": 1}") is None


def test_run_module_missing_module_is_clean_failure_not_crash():
    result = run_module("discovery.this_module_does_not_exist_xyz", ["--metro", "chicago_north_shore"])
    assert result["ok"] is False
    assert result["returncode"] != 0
    assert "not implemented yet" in result["error"] or "ModuleNotFoundError" in result["error"]


def test_common_store_args():
    class Ns:
        mock = True
        store = "local"
        store_root = "/tmp/foo"

    assert common_store_args(Ns()) == ["--mock", "--store", "local", "--store-root", "/tmp/foo"]


# ---------------------------------------------------------------------------
# _stage_runner — resolve_store_kind / reject_mock_with_supabase (code-reviewer C4/M1)
# ---------------------------------------------------------------------------


def _ns(**overrides):
    import argparse

    base = dict(mock=False, store=None)
    base.update(overrides)
    return argparse.Namespace(**base)


def test_resolve_store_kind_explicit_store_wins():
    assert resolve_store_kind(_ns(store="supabase")) == "supabase"
    assert resolve_store_kind(_ns(mock=True, store="local")) == "local"


def test_resolve_store_kind_mock_implies_local_even_with_supabase_env(monkeypatch):
    """CONTRACTS.md: '--mock implies --store local unless overridden' — including when
    PRODCRAFT_STORE=supabase is set in the environment and --store is left unset."""
    monkeypatch.setenv("PRODCRAFT_STORE", "supabase")
    assert resolve_store_kind(_ns(mock=True)) == "local"


def test_resolve_store_kind_no_mock_no_store_falls_back_to_env_then_local(monkeypatch):
    monkeypatch.setenv("PRODCRAFT_STORE", "supabase")
    assert resolve_store_kind(_ns()) == "supabase"
    monkeypatch.delenv("PRODCRAFT_STORE", raising=False)
    assert resolve_store_kind(_ns()) == "local"


def test_reject_mock_with_supabase_errors_on_explicit_combo():
    import argparse

    parser = argparse.ArgumentParser()
    with pytest.raises(SystemExit) as exc_info:
        reject_mock_with_supabase(parser, _ns(mock=True, store="supabase"))
    assert exc_info.value.code == 2


def test_reject_mock_with_supabase_ok_and_returns_resolved_kind(monkeypatch):
    import argparse

    monkeypatch.delenv("PRODCRAFT_STORE", raising=False)
    parser = argparse.ArgumentParser()
    assert reject_mock_with_supabase(parser, _ns(mock=True)) == "local"
    assert reject_mock_with_supabase(parser, _ns(store="supabase")) == "supabase"


# ---------------------------------------------------------------------------
# run_metro — funnel math against a seeded store
# ---------------------------------------------------------------------------


def _seed_funnel_store(store: LocalStore) -> None:
    metro = "chicago_north_shore"
    # 5 found: 1 chain (dropped), 1 too-small (dropped), 3 operational.
    b_chain = store.upsert_business({"place_id": "p1", "name": "Ideal Image", "metro": metro, "is_chain": True})
    b_small = store.upsert_business({"place_id": "p2", "name": "Tiny Spa", "metro": metro, "is_chain": False, "drop_reason": "too_small"})
    b1 = store.upsert_business({"place_id": "p3", "name": "Glow Aesthetics", "metro": metro, "is_chain": False})
    b2 = store.upsert_business({"place_id": "p4", "name": "Radiant Med Spa", "metro": metro, "is_chain": False})
    b3 = store.upsert_business({"place_id": "p5", "name": "Skip Spa", "metro": metro, "is_chain": False})

    # audits: b1, b2 audited (qualified, borderline); b3 not audited at all.
    store.insert_audit({"business_id": b1["id"], "bucket": "qualified", "total_score": 60})
    store.insert_audit({"business_id": b2["id"], "bucket": "borderline", "total_score": 30})

    # owner found only for b1.
    store.upsert_business({**b1, "owner_name": "Jamie Rivera"})

    # email verified for b1.
    store.upsert_business({**b1, "owner_name": "Jamie Rivera", "email_status": "deliverable"})

    # preview built for b1.
    store.upsert_preview({"business_id": b1["id"], "content_hash": "abc123", "subdomain_url": "https://glow-k3x9qa.preview.prodcraft.fyi"})


def test_compute_funnel_math(tmp_path):
    store = LocalStore(root=tmp_path / "store")
    _seed_funnel_store(store)

    funnel = run_metro.compute_funnel(store, "chicago_north_shore")
    counts = {name: count for name, count, _reasons in funnel["stages"]}

    assert counts["found"] == 5
    assert counts["operational (kept)"] == 3
    assert counts["audited"] == 2
    assert counts["qualified"] == 1
    assert counts["owner found"] == 1
    assert counts["email verified"] == 1
    assert counts["preview built"] == 1


def test_compute_funnel_drop_reasons_present(tmp_path):
    store = LocalStore(root=tmp_path / "store")
    _seed_funnel_store(store)

    funnel = run_metro.compute_funnel(store, "chicago_north_shore")
    reasons_by_stage = {name: reasons for name, _count, reasons in funnel["stages"]}

    assert reasons_by_stage["operational (kept)"] == {"chain": 1, "too_small": 1}
    # qualified drop reason: b2 is borderline
    assert reasons_by_stage["qualified"] == {"borderline": 1}


def test_compute_funnel_labels_missing_email_status_no_email_not_unknown(tmp_path):
    """pipeline-auditor: a business with email_status=None (no email attempt at all) is
    'no_email', distinct from a genuine-but-non-deliverable verifier status literally named
    'unknown'."""
    store = LocalStore(root=tmp_path / "store")
    metro = "chicago_north_shore"
    b1 = store.upsert_business({"place_id": "p1", "name": "Owner No Email", "metro": metro, "is_chain": False})
    b2 = store.upsert_business({"place_id": "p2", "name": "Owner Unknown Status", "metro": metro, "is_chain": False})
    store.insert_audit({"business_id": b1["id"], "bucket": "qualified", "total_score": 60})
    store.insert_audit({"business_id": b2["id"], "bucket": "qualified", "total_score": 60})
    store.upsert_business({**b1, "owner_name": "A"})  # email_status left unset -> None
    store.upsert_business({**b2, "owner_name": "B", "email_status": "unknown"})

    funnel = run_metro.compute_funnel(store, metro)
    reasons_by_stage = {name: reasons for name, _count, reasons in funnel["stages"]}
    assert reasons_by_stage["email verified"] == {"no_email": 1, "unknown": 1}


def test_run_record_filename_unique_within_same_second():
    """pipeline-auditor: two runs for the same metro starting in the same second must not
    collide on the run-record filename."""
    names = {run_metro.run_record_filename("chicago_north_shore") for _ in range(20)}
    assert len(names) == 20
    for name in names:
        assert name.startswith("chicago_north_shore_")
        assert name.endswith(".json")


def test_estimate_total_cost_sums_reported_cost_usd():
    results = [
        {"stat": {"script": "a", "cost_usd": 1.5}},
        {"stat": {"script": "b", "cost_usd": 2.25}},
        {"stat": {"script": "c"}},  # no cost_usd — contributes 0
        {"stat": None},
    ]
    assert run_metro.estimate_total_cost(results) == pytest.approx(3.75)


def _metro_args(**overrides):
    import argparse

    base = dict(
        metro="chicago_north_shore", mock=True, store="local", store_root="/tmp/x",
        sample_n=0, sample_only=False, auto_approve=False, skip_vision=False, skip_screenshots=False,
        continue_on_error=False, import_csv=None, import_source=None,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def test_audit_stage_always_runs_full_audit_even_with_sample_n():
    """HANDOFF item 2: --sample-n must never replace audit.audit_site."""
    module, cli = run_metro.build_stage_args("audit", _metro_args(sample_n=40))
    assert module == "audit.audit_site"
    assert "--n" not in cli


def test_expand_stages_adds_sample_after_full_audit():
    stages = run_metro.expand_stages(["discovery", "audit", "enrich", "preview"], _metro_args(sample_n=40), "local")
    assert stages == ["discovery", "audit", "audit_sample", "enrich", "preview", "approve"]  # mock implies approve
    module, cli = run_metro.build_stage_args("audit_sample", _metro_args(sample_n=40))
    assert module == "audit.sample_audit"
    assert cli[cli.index("--n") + 1] == "40"
    assert "--reuse-audits" in cli  # metro_stats only; nothing audited twice


def test_expand_stages_sample_only_replaces_full_audit():
    stages = run_metro.expand_stages(["discovery", "audit"], _metro_args(sample_n=40, sample_only=True), "local")
    assert stages == ["discovery", "audit_sample"]
    _, cli = run_metro.build_stage_args("audit_sample", _metro_args(sample_n=40, sample_only=True))
    assert "--reuse-audits" not in cli


def test_expand_stages_unchanged_without_sample_n():
    assert run_metro.expand_stages(["discovery", "audit"], _metro_args(mock=False), "local") == ["discovery", "audit"]


def test_expand_stages_live_default_has_no_approve_stage():
    """Production: previews stay in review until a human approves (automation-boundaries.md)."""
    stages = run_metro.expand_stages(run_metro.ALL_STAGES, _metro_args(mock=False), "local")
    assert "approve" not in stages


def test_expand_stages_mock_or_auto_approve_appends_approve_after_preview():
    for kwargs in ({"mock": True}, {"mock": False, "auto_approve": True}):
        stages = run_metro.expand_stages(run_metro.ALL_STAGES, _metro_args(**kwargs), "local")
        assert stages == ["discovery", "audit", "enrich", "preview", "approve"], kwargs
    module, cli = run_metro.build_stage_args("approve", _metro_args(mock=True))
    assert module == "preview.approve"
    assert "--all-review" in cli and "--metro" in cli


def test_expand_stages_never_adds_approve_against_supabase_store():
    """code-reviewer C4/M1: --auto-approve (or --mock's implied auto-approve) may only add the
    approve stage when the resolved store is local. expand_stages stays pure (no error) — main()
    is what parser.error()s on this combination before ever calling expand_stages."""
    for kwargs in ({"mock": True, "store": "supabase"}, {"auto_approve": True, "store": "supabase"}):
        stages = run_metro.expand_stages(run_metro.ALL_STAGES, _metro_args(**kwargs), "supabase")
        assert "approve" not in stages, kwargs


def test_audit_sample_stage_requires_sample_n():
    with pytest.raises(ValueError):
        run_metro.build_stage_args("audit_sample", _metro_args(sample_n=0))


# ---------------------------------------------------------------------------
# --import-csv (build instructions item on run_metro.py)
# ---------------------------------------------------------------------------


def test_expand_stages_import_csv_inserts_import_stage_first():
    args = _metro_args(import_csv="/tmp/prospects.csv")
    stages = run_metro.expand_stages(["discovery", "audit", "enrich", "preview"], args, "local")
    # --mock (the _metro_args default) still implies --auto-approve, appended after preview;
    # --import-csv's insertion must not disturb that.
    assert stages == ["import", "discovery", "audit", "enrich", "preview", "approve"]


def test_expand_stages_import_csv_without_discovery_still_inserts_at_front():
    args = _metro_args(import_csv="/tmp/prospects.csv", mock=False)
    stages = run_metro.expand_stages(["enrich"], args, "local")
    assert stages == ["import", "enrich"]


def test_expand_stages_without_import_csv_flag_has_no_import_stage():
    args = _metro_args(import_csv=None)
    stages = run_metro.expand_stages(["discovery", "audit"], args, "local")
    assert "import" not in stages


def test_expand_stages_import_csv_idempotent_if_already_present():
    args = _metro_args(import_csv="/tmp/prospects.csv", mock=False)
    stages = run_metro.expand_stages(["import", "discovery"], args, "local")
    assert stages == ["import", "discovery"]  # not inserted twice


def test_build_stage_args_import_stage():
    module, cli = run_metro.build_stage_args("import", _metro_args(import_csv="/tmp/prospects.csv"))
    assert module == "discovery.import_csv"
    assert cli[cli.index("--csv") + 1] == "/tmp/prospects.csv"
    assert cli[cli.index("--metro") + 1] == "chicago_north_shore"
    assert "--mock" in cli


def test_build_stage_args_import_stage_with_source():
    _, cli = run_metro.build_stage_args(
        "import", _metro_args(import_csv="/tmp/prospects.csv", import_source="web_search_2026_09")
    )
    assert cli[cli.index("--source") + 1] == "web_search_2026_09"


def test_build_stage_args_import_stage_requires_path():
    with pytest.raises(ValueError):
        run_metro.build_stage_args("import", _metro_args(import_csv=None))


def test_run_metro_cli_missing_stage_module_exits_nonzero(tmp_path):
    """End-to-end: run_metro.py against a stage whose module does not exist yet
    (preview.build_preview exists, but we point --stages at just 'enrich' with a metro that has no
    fixtures, forcing a real subprocess failure path is slow; instead exercise the exact
    documented contract — a missing module — via a monkeypatched STAGE_MODULE, same as
    test_run_module_missing_module_is_clean_failure_not_crash but through run_stages()."""
    import argparse

    args = argparse.Namespace(
        metro="chicago_north_shore",
        mock=True,
        store="local",
        store_root=str(tmp_path / "store"),
        sample_n=0,
        skip_vision=True,
        skip_screenshots=True,
        continue_on_error=False,
    )
    orig = dict(run_metro.STAGE_MODULE)
    run_metro.STAGE_MODULE["discovery"] = "discovery.this_module_does_not_exist_xyz"
    try:
        results = run_metro.run_stages(["discovery"], args)
    finally:
        run_metro.STAGE_MODULE.clear()
        run_metro.STAGE_MODULE.update(orig)

    assert len(results) == 1
    assert results[0]["ok"] is False
    assert "not implemented yet" in results[0]["error"]


def test_run_metro_cli_mock_with_store_supabase_exits_2(tmp_path):
    """code-reviewer C4/M1: --mock must never reach a Supabase store."""
    proc = subprocess.run(
        [sys.executable, "-m", "execution.personal_workflows.prodcraft_medspa.scripts.run_metro",
         "--metro", "chicago_north_shore", "--mock", "--store", "supabase"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 2
    assert "--mock cannot be combined with --store supabase" in proc.stderr


def test_run_metro_cli_auto_approve_with_store_supabase_exits_2(tmp_path):
    """--auto-approve is local-store only; a Supabase/live store must parser.error(), not
    silently skip the approve stage."""
    proc = subprocess.run(
        [sys.executable, "-m", "execution.personal_workflows.prodcraft_medspa.scripts.run_metro",
         "--metro", "chicago_north_shore", "--auto-approve", "--store", "supabase"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 2
    assert "--auto-approve is local-store only" in proc.stderr


def test_run_metro_cli_mock_with_env_supabase_resolves_local(tmp_path):
    """CONTRACTS.md: '--mock implies --store local unless overridden' — including when
    PRODCRAFT_STORE=supabase is set in the environment and --store is left unset. `--stages ""`
    (no stages) isolates run_metro's OWN store resolution (used for its compute_funnel
    cross-check) from the stage subprocesses it would otherwise shell out to — those are other
    packages' CLIs and this test must not depend on their own --mock/--store handling being
    correct."""
    env = dict(__import__("os").environ)
    env["PRODCRAFT_STORE"] = "supabase"
    env.pop("SUPABASE_URL", None)
    env.pop("SUPABASE_SERVICE_KEY", None)
    proc = subprocess.run(
        [sys.executable, "-m", "execution.personal_workflows.prodcraft_medspa.scripts.run_metro",
         "--metro", "chicago_north_shore", "--mock", "--store-root", str(tmp_path / "store"),
         "--stages", ""],
        cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    # If run_metro's own store resolution had picked Supabase, compute_funnel's get_store() call
    # would fail trying to reach a real Supabase endpoint (no SUPABASE_URL/SERVICE_KEY in env)
    # rather than succeed against the local --store-root.
    assert "SupabaseStore" not in proc.stderr
    assert proc.returncode == 0, proc.stderr


# ---------------------------------------------------------------------------
# doctor.py
# ---------------------------------------------------------------------------


def test_doctor_no_env_reports_all_missing(monkeypatch):
    for names in doctor.SERVICE_ENV_VARS.values():
        for n in names:
            monkeypatch.delenv(n, raising=False)
    from execution.personal_workflows.prodcraft_medspa.common.config import bootstrap

    settings = bootstrap()
    presence = doctor.env_presence(settings)
    assert all(v is False for v in presence.values())

    for stage in ("discovery", "audit", "outreach"):
        missing = settings.missing_for_stage(stage)
        assert missing, f"expected missing vars for stage {stage} with no env set"


def test_doctor_cli_no_env_exits_nonzero_for_selected_stages(tmp_path, monkeypatch):
    env = {k: v for k, v in __import__("os").environ.items() if not k.endswith("_API_KEY") and "SUPABASE" not in k and "CLOUDFLARE" not in k and "GMAIL" not in k and "TELEGRAM" not in k}
    proc = subprocess.run(
        [sys.executable, str(PKG_ROOT / "scripts" / "doctor.py"), "--stages", "discovery"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=30,
    )
    assert proc.returncode != 0
    last_line = proc.stdout.strip().splitlines()[-1]
    stat = json.loads(last_line)
    assert stat["script"] == "doctor"
    assert "discovery" in stat["failing_stages"]


def test_doctor_cli_mock_env_does_not_crash():
    """Mock/no-env runs must not crash (CONTRACTS.md)."""
    proc = subprocess.run(
        [sys.executable, str(PKG_ROOT / "scripts" / "doctor.py")],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    # exit code may be non-zero (missing creds is expected) but must not traceback
    assert "Traceback" not in proc.stderr


# ---------------------------------------------------------------------------
# fit_weights.py
# ---------------------------------------------------------------------------


def test_fit_weights_refuses_under_50_sends(tmp_path, capsys):
    store = LocalStore(root=tmp_path / "store")
    for i in range(10):
        b = store.upsert_business({"place_id": f"p{i}", "name": f"Spa {i}", "metro": "m"})
        store.insert_audit({"business_id": b["id"], "bucket": "qualified", "has_website": True, "booking_widget": None})
        store.upsert_outreach({"business_id": b["id"], "touch": 1, "status": "sent", "sent_at": "2026-09-01T00:00:00Z"})

    rows = fit_weights.touch1_outcomes(store)
    assert len(rows) == 10
    assert len(rows) < 50  # refuse threshold


def test_fit_weights_computes_correctly_on_synthetic_60_rows(tmp_path):
    store = LocalStore(root=tmp_path / "store")
    # 60 touch-1 sends. 30 have no_booking_widget=True and reply 60% of the time; 30 have it False
    # and reply 10% of the time — a clear positive signal.
    for i in range(60):
        has_signal = i < 30
        replied = has_signal and (i % 5 != 0)  # 24/30 replied when signal true (~80%) — strong split
        b = store.upsert_business({"place_id": f"q{i}", "name": f"Spa {i}", "metro": "m"})
        store.insert_audit(
            {
                "business_id": b["id"],
                "bucket": "qualified",
                "has_website": True,
                "booking_widget": None if has_signal else "vagaro",
            }
        )
        outreach_row = {
            "business_id": b["id"],
            "touch": 1,
            "status": "replied" if replied else "sent",
            "sent_at": "2026-09-01T00:00:00Z",
        }
        if replied:
            outreach_row["replied_at"] = "2026-09-02T00:00:00Z"
        store.upsert_outreach(outreach_row)

    rows = fit_weights.touch1_outcomes(store)
    assert len(rows) == 60

    result = fit_weights.compute_signal_table(rows)
    assert result["n_touch1_sent"] == 60
    signal_row = result["signals"]["no_booking_widget"]
    assert signal_row["n_true"] == 30
    assert signal_row["n_false"] == 30
    # signal-true group replied 24/30, signal-false group replied 0/30 (booking_widget="vagaro" => no_booking_widget False, no replies)
    assert signal_row["reply_rate_true"] == pytest.approx(24 / 30)
    assert signal_row["reply_rate_false"] == pytest.approx(0.0)
    assert signal_row["point_biserial_r"] > 0.5  # strong positive correlation


def test_fit_weights_point_biserial_none_when_outcome_has_no_variance():
    outcomes = [False, False, False]
    signal_values = [True, False, True]
    assert fit_weights.point_biserial(signal_values, outcomes) is None


# ---------------------------------------------------------------------------
# sync_sheets.py
# ---------------------------------------------------------------------------


def test_sync_sheets_mock_csv_columns_match_v_pipeline(tmp_path, monkeypatch):
    store = LocalStore(root=tmp_path / "store")
    b = store.upsert_business(
        {
            "place_id": "p1",
            "name": "Glow Aesthetics",
            "suburb": "Winnetka",
            "metro": "chicago_north_shore",
            "website_url": "https://glowaesthetics.example",
            "owner_name": "Jamie Rivera",
            "owner_email": "jamie@example.test",
            "email_status": "deliverable",
            "is_chain": False,
        }
    )
    store.insert_audit({"business_id": b["id"], "total_score": 60, "bucket": "qualified"})
    store.upsert_preview({"business_id": b["id"], "content_hash": "h1", "subdomain_url": "https://glow-k3x9.preview.prodcraft.fyi", "status": "approved"})
    store.upsert_outreach({"business_id": b["id"], "touch": 1, "status": "sent", "sent_at": "2026-09-01T00:00:00Z", "next_touch_at": "2026-09-04"})

    rows = sync_sheets.compute_v_pipeline(store)
    assert len(rows) == 1
    assert set(rows[0].keys()) == set(sync_sheets.V_PIPELINE_COLUMNS)

    out_csv = tmp_path / "v_pipeline.csv"
    sync_sheets.write_csv(rows, out_csv, sync_sheets.V_PIPELINE_COLUMNS)
    with open(out_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == sync_sheets.V_PIPELINE_COLUMNS
        csv_rows = list(reader)
    assert len(csv_rows) == 1
    assert csv_rows[0]["name"] == "Glow Aesthetics"
    assert csv_rows[0]["bucket"] == "qualified"
    assert csv_rows[0]["preview_status"] == "approved"


def test_sync_sheets_excludes_chains_and_dropped():
    store = LocalStore(root=Path("/tmp") / "prodcraft_test_sync_sheets_store")
    import shutil

    shutil.rmtree(store.root, ignore_errors=True)
    store = LocalStore(root=store.root)
    store.upsert_business({"place_id": "c1", "name": "Ideal Image", "metro": "m", "is_chain": True})
    store.upsert_business({"place_id": "c2", "name": "Dropped Spa", "metro": "m", "is_chain": False, "drop_reason": "too_small"})
    store.upsert_business({"place_id": "c3", "name": "Kept Spa", "metro": "m", "is_chain": False})

    rows = sync_sheets.compute_v_pipeline(store)
    names = {r["name"] for r in rows}
    assert names == {"Kept Spa"}
    shutil.rmtree(store.root, ignore_errors=True)


# ---------------------------------------------------------------------------
# GitHub Actions workflow YAML sanity + env-name coverage
# ---------------------------------------------------------------------------

CONTRACTS_ENV_NAMES = [
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "GOOGLE_PLACES_API_KEY",
    "PAGESPEED_API_KEY",
    "ANTHROPIC_API_KEY",
    "APOLLO_API_KEY",
    "FINDYMAIL_API_KEY",
    "HUNTER_API_KEY",
    "MILLION_VERIFIER_API_KEY",
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_ACCOUNT_ID",
    "R2_BUCKET",
    "PREVIEW_BASE_DOMAIN",
    "GMAIL_CREDENTIALS_JSON",
    "GMAIL_TOKEN_JSON",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "GOOGLE_SHEETS_MIRROR_ID",
    "DASHBOARD_USER",
    "DASHBOARD_PASS",
]


@pytest.mark.parametrize(
    "workflow_path",
    [
        REPO_ROOT / ".github" / "workflows" / "prodcraft_medspa_replies.yml",
        REPO_ROOT / ".github" / "workflows" / "prodcraft_medspa_ci.yml",
    ],
)
def test_workflow_yaml_parses(workflow_path: Path):
    assert workflow_path.exists(), f"missing {workflow_path}"
    with open(workflow_path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    assert doc is not None
    assert "jobs" in doc


def test_replies_workflow_references_every_contracts_env_name():
    text = (REPO_ROOT / ".github" / "workflows" / "prodcraft_medspa_replies.yml").read_text(encoding="utf-8")
    missing = [name for name in CONTRACTS_ENV_NAMES if f"secrets.{name}" not in text]
    assert not missing, f"prodcraft_medspa_replies.yml is missing secrets for: {missing}"


def test_replies_workflow_guarded_by_cron_enabled_variable():
    text = (REPO_ROOT / ".github" / "workflows" / "prodcraft_medspa_replies.yml").read_text(encoding="utf-8")
    assert "vars.PRODCRAFT_CRON_ENABLED == 'true'" in text


# ---------------------------------------------------------------------------
# daily.py — full mock chain (apply_schema -> run_metro --mock -> daily.py --mock) now ends
# with sent rows (operator decision 2026-09-16: sending is automated, no human in the loop).
# ---------------------------------------------------------------------------


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    # Generous timeout: run_metro.py --mock does a real `npm run build` per preview, which can
    # take well over 5 minutes under concurrent load from other agents' test runs in this repo.
    return subprocess.run(
        cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900
    )


def test_daily_mock_chain_ends_with_sent_rows(tmp_path):
    store_root = tmp_path / "store"

    apply_schema = _run(
        [sys.executable, str(PKG_ROOT / "db" / "apply_schema.py"), "--store", "local", "--root", str(store_root)]
    )
    assert apply_schema.returncode == 0, apply_schema.stderr

    metro = _run(
        [
            sys.executable, str(PKG_ROOT / "scripts" / "run_metro.py"),
            "--metro", "chicago_north_shore", "--mock", "--store", "local", "--store-root", str(store_root),
        ]
    )
    assert metro.returncode == 0, metro.stderr

    daily = _run(
        [
            sys.executable, str(PKG_ROOT / "scripts" / "daily.py"),
            "--mock", "--store", "local", "--store-root", str(store_root),
            "--recipient-override", "test@example.test",
        ]
    )
    assert daily.returncode == 0, daily.stderr
    last_line = daily.stdout.strip().splitlines()[-1]
    stat = json.loads(last_line)
    assert stat["script"] == "daily"
    assert stat["sent"] == 4
    assert stat["any_failed"] is False

    # A second same-day run must not re-send (already sent; next touch not due yet).
    daily2 = _run(
        [
            sys.executable, str(PKG_ROOT / "scripts" / "daily.py"),
            "--mock", "--store", "local", "--store-root", str(store_root),
            "--recipient-override", "test@example.test",
        ]
    )
    assert daily2.returncode == 0, daily2.stderr
    stat2 = json.loads(daily2.stdout.strip().splitlines()[-1])
    assert stat2["sent"] == 0


def test_replies_and_daily_workflows_share_concurrency_group():
    replies_text = (REPO_ROOT / ".github" / "workflows" / "prodcraft_medspa_replies.yml").read_text(encoding="utf-8")
    daily_text = (REPO_ROOT / ".github" / "workflows" / "prodcraft_medspa_daily.yml").read_text(encoding="utf-8")
    assert "group: prodcraft-medspa\n" in replies_text
    assert "group: prodcraft-medspa\n" in daily_text


DAILY_WORKFLOW_EXTRA_SECRETS = [
    "GOOGLE_SERVICE_ACCOUNT_JSON",
    "PREVIEW_PUBLISH_SECRET",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
]


def test_daily_workflow_yaml_parses_and_is_gated():
    path = REPO_ROOT / ".github" / "workflows" / "prodcraft_medspa_daily.yml"
    assert path.exists()
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    assert doc is not None
    assert "jobs" in doc
    assert doc["jobs"]["daily"]["if"] == "vars.PRODCRAFT_CRON_ENABLED == 'true'"
    # PyYAML's safe_load parses the bare `on:` key as the boolean True (YAML 1.1), not "on".
    on_section = doc.get("on", doc.get(True))
    assert on_section["schedule"][0]["cron"] == "0 14 * * *"
    assert "workflow_dispatch" in on_section
    assert "metro" in on_section["workflow_dispatch"]["inputs"]


def test_daily_workflow_references_every_contracts_env_name_plus_new_ones():
    text = (REPO_ROOT / ".github" / "workflows" / "prodcraft_medspa_daily.yml").read_text(encoding="utf-8")
    missing = [name for name in CONTRACTS_ENV_NAMES if f"secrets.{name}" not in text]
    assert not missing, f"prodcraft_medspa_daily.yml is missing secrets for: {missing}"
    missing_new = [name for name in DAILY_WORKFLOW_EXTRA_SECRETS if f"secrets.{name}" not in text]
    assert not missing_new, f"prodcraft_medspa_daily.yml is missing secrets for: {missing_new}"
    assert "vars.PRODCRAFT_RECIPIENT_OVERRIDE" in text


def test_daily_workflow_runs_metro_then_daily_then_sync_sheets_then_npm_ci():
    text = (REPO_ROOT / ".github" / "workflows" / "prodcraft_medspa_daily.yml").read_text(encoding="utf-8")
    assert "npm ci" in text
    assert "run_metro.py" in text
    idx_metro = text.index("run_metro.py")
    idx_daily = text.index("daily.py")
    idx_sync = text.index("sync_sheets.py")
    assert idx_metro < idx_daily < idx_sync


# ---------------------------------------------------------------------------
# sync_sheets.py — two-tab mirror (pipeline + daily_log), --xlsx
# ---------------------------------------------------------------------------


def _seed_sent_outreach_store(tmp_path):
    store = LocalStore(root=tmp_path / "store")
    b = store.upsert_business(
        {
            "place_id": "p1",
            "name": "Glow Aesthetics",
            "suburb": "Winnetka",
            "metro": "chicago_north_shore",
            "website_url": "https://glowaesthetics.example",
            "owner_name": "Jamie Rivera",
            "owner_email": "jamie@example.test",
            "email_status": "deliverable",
            "is_chain": False,
        }
    )
    store.insert_audit({"business_id": b["id"], "total_score": 60, "bucket": "qualified"})
    store.upsert_preview(
        {"business_id": b["id"], "content_hash": "h1", "subdomain_url": "https://glow-k3x9.preview.prodcraft.fyi", "status": "approved"}
    )
    store.upsert_outreach(
        {
            "business_id": b["id"],
            "touch": 1,
            "status": "sent",
            "sent_at": "2026-09-15T12:00:00Z",
            "draft_subject": "Quick idea for Glow Aesthetics' bookings",
            "gmail_thread_id": "thread-abc",
            "reply_sentiment": "positive",
            "reply_summary": "Interested, wants a call Thursday.",
            "replied_at": "2026-09-16T09:00:00Z",
        }
    )
    return store, b


def test_sync_sheets_v_pipeline_columns_include_reply_and_test_recipient():
    """Task spec: pipeline tab = existing v_pipeline columns plus reply_sentiment, reply_summary,
    replied_at, test_recipient (preview_status/outreach_status/touch/sent_at already existed)."""
    for col in ("reply_sentiment", "reply_summary", "replied_at", "test_recipient", "preview_status", "outreach_status", "touch", "sent_at"):
        assert col in sync_sheets.V_PIPELINE_COLUMNS


def test_sync_sheets_compute_v_pipeline_carries_reply_fields(tmp_path):
    store, _b = _seed_sent_outreach_store(tmp_path)
    rows = sync_sheets.compute_v_pipeline(store)
    assert len(rows) == 1
    assert rows[0]["reply_sentiment"] == "positive"
    assert rows[0]["reply_summary"] == "Interested, wants a call Thursday."
    assert rows[0]["replied_at"] == "2026-09-16T09:00:00Z"
    assert rows[0]["test_recipient"] is None


def test_sync_sheets_compute_daily_log_one_row_per_send(tmp_path):
    store, b = _seed_sent_outreach_store(tmp_path)
    rows = sync_sheets.compute_daily_log(store)
    assert len(rows) == 1
    row = rows[0]
    assert row["date"] == "2026-09-15"
    assert row["business"] == "Glow Aesthetics"
    assert row["recipient"] == "jamie@example.test"  # falls back to owner_email, no test_recipient set
    assert row["subject"] == "Quick idea for Glow Aesthetics' bookings"
    assert row["preview_url"] == "https://glow-k3x9.preview.prodcraft.fyi"
    assert row["gmail_thread_id"] == "thread-abc"
    assert row["status"] == "sent"


def test_sync_sheets_compute_daily_log_prefers_test_recipient_over_owner_email(tmp_path):
    store = LocalStore(root=tmp_path / "store")
    b = store.upsert_business({"place_id": "p1", "name": "Glow", "metro": "m", "owner_email": "real@owner.test", "is_chain": False})
    store.upsert_outreach(
        {"business_id": b["id"], "touch": 1, "status": "sent", "sent_at": "2026-09-15T00:00:00Z", "test_recipient": "operator@override.test"}
    )
    rows = sync_sheets.compute_daily_log(store)
    assert rows[0]["recipient"] == "operator@override.test"


def test_sync_sheets_compute_daily_log_excludes_unsent_rows(tmp_path):
    store = LocalStore(root=tmp_path / "store")
    b = store.upsert_business({"place_id": "p1", "name": "Glow", "metro": "m", "is_chain": False})
    store.upsert_outreach({"business_id": b["id"], "touch": 1, "status": "queued"})  # no sent_at
    assert sync_sheets.compute_daily_log(store) == []


def test_sync_sheets_mock_produces_both_csvs_with_documented_headers(tmp_path, monkeypatch):
    store, _b = _seed_sent_outreach_store(tmp_path)
    monkeypatch.setattr(sync_sheets, "get_store", lambda kind=None, root=None: store)
    monkeypatch.setattr(sync_sheets, "REPO_ROOT", tmp_path)

    argv = ["sync_sheets.py", "--mock"]
    monkeypatch.setattr(sys, "argv", argv)
    sync_sheets.main()

    pipeline_csv = tmp_path / ".tmp" / "prodcraft_medspa" / "v_pipeline.csv"
    daily_log_csv = tmp_path / ".tmp" / "prodcraft_medspa" / "daily_log.csv"
    assert pipeline_csv.exists()
    assert daily_log_csv.exists()

    with open(pipeline_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == sync_sheets.V_PIPELINE_COLUMNS
        assert len(list(reader)) == 1

    with open(daily_log_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == sync_sheets.DAILY_LOG_COLUMNS
        assert len(list(reader)) == 1


def test_sync_sheets_xlsx_skips_cleanly_when_openpyxl_missing(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "openpyxl", None)  # force `import openpyxl` to raise ImportError
    out_path = tmp_path / "mirror.xlsx"
    wrote = sync_sheets.write_xlsx([{"name": "x"}], [{"business": "x"}], out_path)
    assert wrote is False
    assert not out_path.exists()


def test_sync_sheets_xlsx_writes_workbook_when_openpyxl_present(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    store, _b = _seed_sent_outreach_store(tmp_path)
    pipeline_rows = sync_sheets.compute_v_pipeline(store)
    daily_log_rows = sync_sheets.compute_daily_log(store)
    out_path = tmp_path / "mirror.xlsx"

    wrote = sync_sheets.write_xlsx(pipeline_rows, daily_log_rows, out_path)
    assert wrote is True
    assert out_path.exists()

    wb = openpyxl.load_workbook(str(out_path))
    assert set(wb.sheetnames) == {"pipeline", "daily_log"}
    pipeline_header = [c.value for c in next(wb["pipeline"].iter_rows(min_row=1, max_row=1))]
    assert pipeline_header == sync_sheets.V_PIPELINE_COLUMNS
    daily_log_header = [c.value for c in next(wb["daily_log"].iter_rows(min_row=1, max_row=1))]
    assert daily_log_header == sync_sheets.DAILY_LOG_COLUMNS


# ---------------------------------------------------------------------------
# doctor.py — Gmail gmail.send scope, sheets config, recipient override, queue_pick
# ---------------------------------------------------------------------------


def test_doctor_gmail_send_scope_missing_reports_false(monkeypatch):
    from execution.personal_workflows.prodcraft_medspa.common.config import bootstrap

    monkeypatch.setenv("GMAIL_TOKEN_JSON", json.dumps({"scopes": ["https://www.googleapis.com/auth/gmail.readonly"]}))
    settings = bootstrap()
    ok, detail = doctor.check_gmail_send_scope(settings)
    assert ok is False
    assert "missing gmail.send" in detail


def test_doctor_gmail_send_scope_present_reports_true(monkeypatch):
    from execution.personal_workflows.prodcraft_medspa.common.config import bootstrap

    monkeypatch.setenv("GMAIL_TOKEN_JSON", json.dumps({"scopes": ["https://www.googleapis.com/auth/gmail.send"]}))
    settings = bootstrap()
    ok, detail = doctor.check_gmail_send_scope(settings)
    assert ok is True
    assert "gmail.send" in detail


def test_doctor_gmail_send_scope_skips_without_token(monkeypatch):
    from execution.personal_workflows.prodcraft_medspa.common.config import bootstrap

    monkeypatch.delenv("GMAIL_TOKEN_JSON", raising=False)
    settings = bootstrap()
    ok, detail = doctor.check_gmail_send_scope(settings)
    assert ok is None


def test_doctor_masked_recipient_override_shows_domain_only(monkeypatch):
    monkeypatch.setenv("PRODCRAFT_RECIPIENT_OVERRIDE", "operator@example.test")
    display, warning = doctor.masked_recipient_override()
    assert display == "***@example.test"
    assert "operator@example.test" not in display
    assert warning != ""


def test_doctor_masked_recipient_override_unset(monkeypatch):
    monkeypatch.delenv("PRODCRAFT_RECIPIENT_OVERRIDE", raising=False)
    display, warning = doctor.masked_recipient_override()
    assert display == "(not set)"
    assert warning == ""


def test_doctor_sheets_config_reports_missing(monkeypatch):
    monkeypatch.delenv("GOOGLE_SHEETS_MIRROR_ID", raising=False)
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_PATH", raising=False)
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON", raising=False)
    ok, detail = doctor.check_sheets_config()
    assert ok is False
    assert "GOOGLE_SHEETS_MIRROR_ID" in detail


def test_doctor_sheets_config_ok_when_present(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEETS_MIRROR_ID", "sheet123")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_PATH", "/tmp/sa.json")
    ok, detail = doctor.check_sheets_config()
    assert ok is True


def test_doctor_cli_still_does_not_crash_with_new_checks():
    proc = subprocess.run(
        [sys.executable, str(PKG_ROOT / "scripts" / "doctor.py"), "--stages", "outreach,sheets"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert "Traceback" not in proc.stderr
    last_line = proc.stdout.strip().splitlines()[-1]
    stat = json.loads(last_line)
    assert stat["script"] == "doctor"


def test_fit_weights_excludes_test_recipient_rows(tmp_path):
    """Dry-run sends to the operator's own inbox must never enter reply-rate statistics."""
    from execution.personal_workflows.prodcraft_medspa.scripts import fit_weights

    store = LocalStore(root=tmp_path / "store")
    b = store.upsert_business({"place_id": "p1", "name": "Spa", "slug": "spa", "metro": "m"})
    a = store.insert_audit({"business_id": b["id"], "bucket": "qualified", "total_score": 60, "score_version": "1.0", "gaps": []})
    store.upsert_outreach({"business_id": b["id"], "touch": 1, "status": "sent", "sent_at": "2026-09-16T00:00:00Z", "audit_id": a["id"], "test_recipient": "me@example.test", "next_touch_at": "2026-09-16"})
    b2 = store.upsert_business({"place_id": "p2", "name": "Spa 2", "slug": "spa-2", "metro": "m"})
    a2 = store.insert_audit({"business_id": b2["id"], "bucket": "qualified", "total_score": 60, "score_version": "1.0", "gaps": []})
    store.upsert_outreach({"business_id": b2["id"], "touch": 1, "status": "sent", "sent_at": "2026-09-16T00:00:00Z", "audit_id": a2["id"], "next_touch_at": "2026-09-16"})
    assert len(fit_weights.touch1_outcomes(store)) == 1
