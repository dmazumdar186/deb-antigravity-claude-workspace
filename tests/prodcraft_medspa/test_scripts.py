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
        continue_on_error=False,
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
    sync_sheets.write_csv(rows, out_csv)
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
