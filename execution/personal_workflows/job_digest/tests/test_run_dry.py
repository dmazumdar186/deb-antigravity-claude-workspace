"""
description: Offline end-to-end test of run.run() in dry mode. Monkeypatches
    sources.fetch_all with synthetic SourceJobs so the test never touches the
    network, and uses the shared test profile (sheet.enabled: false) so the
    sheet-write branch is skipped without needing credentials.
inputs: tmp_path fixtures, monkeypatch
outputs: pytest assertions
"""

from __future__ import annotations

import json
import smtplib
from pathlib import Path

import pytest
import yaml

from .. import run as run_module
from .. import sources as sources_module
from ..contracts import JobSource
from ..notifier import email as email_module
from ..notifier import sheet as sheet_module
from ._helpers import TEST_PROFILE_PATH, make_source_job


def _fake_fetch_all(profile, *, dry: bool = False):
    return {
        "fixture": [
            make_source_job(
                title="Senior Sales Manager",
                location_raw="Paris",
                description_snippet="Lead our B2B sales team in Paris using our CRM.",
                contract_type_raw="CDI",
                source=JobSource.FIXTURE,
                url="https://example.com/jobs/1",
            ),
            make_source_job(
                title="Backend Software Engineer",
                location_raw="Berlin",
                description_snippet="Build backend services in Go.",
                contract_type_raw="Unbefristet",
                source=JobSource.FIXTURE,
                url="https://example.com/jobs/2",
            ),
            make_source_job(
                title="Sales Manager Intern",
                location_raw="Paris",
                description_snippet="Internship in sales.",
                contract_type_raw="Internship",
                source=JobSource.FIXTURE,
                url="https://example.com/jobs/3",
            ),
        ]
    }


@pytest.fixture(autouse=True)
def _patch_fetch_all(monkeypatch: pytest.MonkeyPatch) -> None:
    # Patch the module OBJECT reached via the same relative-import chain
    # run_module itself uses (`from .. import sources as sources_module`) —
    # patching by a hardcoded dotted string can silently miss a duplicate
    # module tree if this test file is ever collected under a different
    # top-level package name than run.py resolves at runtime.
    monkeypatch.setattr(sources_module, "fetch_all", _fake_fetch_all)


def test_run_dry_produces_summary_and_digest(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    out_dir = tmp_path / "out"

    result = run_module.run(
        TEST_PROFILE_PATH,
        mode="dry",
        state_dir=state_dir,
        out_dir=out_dir,
    )

    assert result["exit_code"] == 0
    assert result["stats"]["fetched_total"] == 3
    # sales manager kept, engineer dropped by title, intern dropped by exclude.
    assert result["stats"]["filters"]["kept"] == 1
    assert result["stats"]["digest_rows"] == 1
    assert result["stats"]["acceptance"]["passed"] is True

    assert (out_dir / "summary.json").exists()
    assert (out_dir / "run_log.jsonl").exists()
    log_lines = (out_dir / "run_log.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(log_lines) == 1
    json.loads(log_lines[0])  # valid JSON

    # dry mode must never touch state (no mark_seen / lock).
    assert not (state_dir / "seen.json").exists()
    assert not (state_dir / "email_lock.txt").exists()


def test_run_dry_is_idempotent_state_wise(tmp_path: Path) -> None:
    """Running twice in dry mode never marks jobs seen, so the second run
    sees the same 'new' set as the first."""
    state_dir = tmp_path / "state"
    out_dir = tmp_path / "out"

    first = run_module.run(TEST_PROFILE_PATH, mode="dry", state_dir=state_dir, out_dir=out_dir)
    second = run_module.run(TEST_PROFILE_PATH, mode="dry", state_dir=state_dir, out_dir=out_dir)

    assert first["stats"]["new_after_state_dedup"] == second["stats"]["new_after_state_dedup"]


def test_run_dry_reports_rungs_and_no_hard_send(tmp_path: Path) -> None:
    """M4: rank() surfaces a rungs dict in stats; M6: the dry-run digest lands
    in THIS run's own out_dir, not the JOB_DIGEST_OUT_DIR env fallback."""
    state_dir = tmp_path / "state"
    out_dir = tmp_path / "out"

    result = run_module.run(TEST_PROFILE_PATH, mode="dry", state_dir=state_dir, out_dir=out_dir)

    rungs = result["stats"]["rungs"]
    assert rungs["heuristic"] == "ran"
    assert rungs["gemini"] == "skipped:no_key"
    assert rungs["anthropic"] == "skipped:no_key"

    assert result["stats"]["email_sent"] is False
    assert result["stats"]["email_written"] is True
    assert (out_dir / "digest.txt").exists()
    assert (out_dir / "digest.html").exists()


def _sheet_enabled_profile_path(tmp_path: Path) -> Path:
    raw = yaml.safe_load(TEST_PROFILE_PATH.read_text(encoding="utf-8"))
    raw["sheet"]["enabled"] = True
    path = tmp_path / "profile_sheet_enabled.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return path


def test_run_live_sheet_write_receives_a_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C1: run.py must never hand notifier.sheet.write_jobs a bare str for
    service_account_path — sheet.py's _open_client calls .exists() on it."""
    profile_path = _sheet_enabled_profile_path(tmp_path)
    monkeypatch.setenv("SHEETS_SPREADSHEET_ID", "fake-spreadsheet-id")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_PATH", "some/fake/service_account.json")

    captured: dict = {}

    def fake_write_jobs(pairs, profile, spreadsheet_id, service_account_path, *, stats=None):
        captured["service_account_path"] = service_account_path
        captured["stats"] = stats
        return "https://docs.google.com/spreadsheets/d/fake-spreadsheet-id/edit"

    monkeypatch.setattr(sheet_module, "write_jobs", fake_write_jobs)

    result = run_module.run(
        profile_path, mode="live", state_dir=tmp_path / "state", out_dir=tmp_path / "out"
    )

    assert result["exit_code"] == 0
    assert isinstance(captured["service_account_path"], Path)
    assert captured["service_account_path"] == Path("some/fake/service_account.json")
    # stats= must be passed through so the Summary tab has something to render.
    assert captured["stats"] is not None
    assert result["stats"]["sheet_ok"] is True
    # H2: no URL or spreadsheet id ever lands in stats/summary.json.
    assert "sheet_url" not in result["stats"]
    assert "fake-spreadsheet-id" not in json.dumps(result, default=str)


def test_run_live_sheet_write_skipped_before_acceptance_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """M5: sheet write must happen AFTER acceptance, only when it passed."""
    profile_path = _sheet_enabled_profile_path(tmp_path)
    monkeypatch.setenv("SHEETS_SPREADSHEET_ID", "fake-spreadsheet-id")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_PATH", "some/fake/service_account.json")

    write_calls = []
    monkeypatch.setattr(
        sheet_module, "write_jobs",
        lambda *a, **k: write_calls.append(1) or "https://example.com/sheet",
    )
    monkeypatch.setattr(run_module.acceptance, "check", lambda pairs, profile: (False, ["forced failure for test"]))

    result = run_module.run(
        profile_path, mode="live", state_dir=tmp_path / "state", out_dir=tmp_path / "out"
    )

    assert result["exit_code"] == 3
    assert write_calls == []  # never reached — acceptance failed first


def test_run_summary_json_never_contains_sheet_url_or_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """H2: summary.json/run_log.jsonl must carry sheet_ok, never the URL/id."""
    profile_path = _sheet_enabled_profile_path(tmp_path)
    monkeypatch.setenv("SHEETS_SPREADSHEET_ID", "TOTALLY-SECRET-SPREADSHEET-ID")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_PATH", "some/fake/service_account.json")
    monkeypatch.setattr(
        sheet_module, "write_jobs",
        lambda *a, **k: "https://docs.google.com/spreadsheets/d/TOTALLY-SECRET-SPREADSHEET-ID/edit",
    )

    out_dir = tmp_path / "out"
    result = run_module.run(profile_path, mode="live", state_dir=tmp_path / "state", out_dir=out_dir)
    assert result["exit_code"] == 0

    summary_text = (out_dir / "summary.json").read_text(encoding="utf-8")
    log_text = (out_dir / "run_log.jsonl").read_text(encoding="utf-8")
    for blob in (summary_text, log_text):
        assert "TOTALLY-SECRET-SPREADSHEET-ID" not in blob
        assert "sheet_ok" in blob


def _fake_fetch_all_second_batch(profile, *, dry: bool = False):
    return {
        "fixture": [
            make_source_job(
                title="Senior Sales Manager",
                location_raw="Paris",
                description_snippet="Lead our B2B sales team in Paris using our CRM.",
                contract_type_raw="CDI",
                source=JobSource.FIXTURE,
                url="https://example.com/jobs/second-batch",
            ),
        ]
    }


def test_email_lock_blocks_second_send_and_leaves_new_jobs_unseen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C2: two live runs within min_hours_between_emails — the second run must
    send nothing, and must NOT mark its (unsent) new jobs as seen."""
    state_dir = tmp_path / "state"
    monkeypatch.setattr(email_module, "send_digest", lambda *a, **k: True)

    first = run_module.run(TEST_PROFILE_PATH, mode="live", state_dir=state_dir, out_dir=tmp_path / "out1")
    assert first["exit_code"] == 0
    assert first["stats"]["email_sent"] is True

    # A different job on the second fetch so state-dedup doesn't hide the point.
    monkeypatch.setattr(sources_module, "fetch_all", _fake_fetch_all_second_batch)
    second = run_module.run(TEST_PROFILE_PATH, mode="live", state_dir=state_dir, out_dir=tmp_path / "out2")

    assert second["stats"]["email_lock_ok"] is False
    assert second["stats"]["email_sent"] is False

    # The second run's new job was never marked seen — a fresh dry run still sees it as new.
    third = run_module.run(TEST_PROFILE_PATH, mode="dry", state_dir=state_dir, out_dir=tmp_path / "out3")
    assert third["stats"]["new_after_state_dedup"] >= 1


def test_non_auth_smtp_failure_leaves_jobs_unseen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2: a non-auth SMTPException from send_digest must not crash the run
    and must leave the digest's jobs unmarked (so the next run retries them)."""
    state_dir = tmp_path / "state"

    def boom(*a, **k):
        raise smtplib.SMTPException("transient failure, not an auth error")

    monkeypatch.setattr(email_module, "send_digest", boom)

    result = run_module.run(TEST_PROFILE_PATH, mode="live", state_dir=state_dir, out_dir=tmp_path / "out")
    assert result["exit_code"] == 0  # non-auth failure is logged, not fatal
    assert result["stats"]["email_sent"] is False

    again = run_module.run(TEST_PROFILE_PATH, mode="dry", state_dir=state_dir, out_dir=tmp_path / "out2")
    assert again["stats"]["new_after_state_dedup"] >= 1
