"""Integration test — sync.py driver against the FixtureAdapter.

Exercises the full driver (config load, adapter dispatch, mapping, dedup,
destination upsert, watermark save, run-log write) without any network I/O.

Run:  py -m pytest execution/templates/crm_integration/tests/integration/ -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_TEMPLATE_ROOT = Path(__file__).resolve().parents[2]


def _run(args: list[str], env_override: dict[str, str]) -> subprocess.CompletedProcess:
    # Per python-hardening.md #1: subprocess needs encoding + errors.
    # Per python-hardening.md #6: dict(os.environ), NEVER copy.copy(os.environ).
    env = dict(os.environ)
    env.update(env_override)
    return subprocess.run(
        [sys.executable, "sync.py", *args],
        cwd=str(_TEMPLATE_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=30,
    )


def test_dry_run_against_fixture(tmp_path):
    log_dir = tmp_path / "crm_sync_runs"
    fixture_path = _TEMPLATE_ROOT / "tests" / "fixtures" / "hubspot_contact.json"
    r = _run(
        ["--tenant", "fixture", "--config-dir", "tests/fixtures", "--dry-run"],
        {
            "CRM_SYNC_LOG_DIR": str(log_dir),
            "FIXTURE_ADAPTER_PATH": str(fixture_path),
        },
    )
    assert r.returncode == 0, f"stderr:\n{r.stderr}\nstdout:\n{r.stdout}"
    payload = json.loads(r.stdout)
    assert payload["records_fetched"] == 3
    assert payload["would_upsert"] == 3
    assert payload["dry_run"] is True
    # Watermark of latest fixture record.
    assert payload["watermark_after"].startswith("2026-08-04T12:00:00")

    # Run-log line present.
    log_file = log_dir / "fixture.jsonl"
    assert log_file.exists()
    line = json.loads(log_file.read_text(encoding="utf-8").splitlines()[-1])
    assert line["tenant"] == "fixture"


def test_full_run_writes_to_destination(tmp_path):
    log_dir = tmp_path / "crm_sync_runs"
    out_file = tmp_path / "fixture.jsonl"

    # Write a modified tenant config that points destination to tmp_path.
    tenant_cfg = json.loads(
        (_TEMPLATE_ROOT / "tests" / "fixtures" / "tenant.fixture.json").read_text(encoding="utf-8")
    )
    tenant_cfg["destination"]["target"] = str(out_file)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "tenant.fixture.json").write_text(json.dumps(tenant_cfg), encoding="utf-8")

    fixture_path = _TEMPLATE_ROOT / "tests" / "fixtures" / "hubspot_contact.json"
    r = _run(
        ["--tenant", "fixture", "--config-dir", str(config_dir)],
        {
            "CRM_SYNC_LOG_DIR": str(log_dir),
            "FIXTURE_ADAPTER_PATH": str(fixture_path),
        },
    )
    assert r.returncode == 0, f"stderr:\n{r.stderr}\nstdout:\n{r.stdout}"
    payload = json.loads(r.stdout)
    assert payload["records_fetched"] == 3
    assert payload["records_created"] == 3
    assert payload["records_updated"] == 0
    assert payload["errors"] == 0

    # Destination has 3 lines.
    lines = out_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    records = [json.loads(x) for x in lines]
    emails = sorted(r["email"] for r in records)
    assert emails == ["alice@example.com", "bob@example.com", "carol@example.com"]

    # Re-run: everything should be deduped (0 created, 0 updated because dedup
    # via seen-set kicks in before upsert-and-write within the same run;
    # across runs the JSONL append-only pattern re-writes).
    r2 = _run(
        ["--tenant", "fixture", "--config-dir", str(config_dir)],
        {
            "CRM_SYNC_LOG_DIR": str(log_dir),
            "FIXTURE_ADAPTER_PATH": str(fixture_path),
        },
    )
    assert r2.returncode == 0
    payload2 = json.loads(r2.stdout)
    assert payload2["records_fetched"] == 3
    # Same dedup keys already in seen-set from run 1 -> destination reports 'updated'.
    assert payload2["records_created"] == 0
    assert payload2["records_updated"] == 3


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
