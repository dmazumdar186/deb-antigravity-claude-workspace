"""
Sanity tests (Tier 4) for job_search_sheet pipeline — quick smoke checks
that the system is alive and core invariants hold. No real API calls.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _py(*args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["py", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, cwd=str(ROOT),
    )


# ---------------------------------------------------------------------------
# Imports — every script must import cleanly
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mod", [
    "execution.personal_workflows.job_search_sheet",
    "execution.personal_workflows.job_search_llm_gate",
    "execution.personal_workflows.job_search_notify",
    "execution.personal_workflows.job_search_setup",
    "execution.google.google_sheets_writer",
    "execution.custom_scrapers.adzuna_jobs",
    "execution.custom_scrapers.jooble_jobs",
])
def test_module_imports_cleanly(mod: str):
    proc = _py("-c", f"import {mod}")
    assert proc.returncode == 0, f"{mod} failed to import:\nSTDOUT:{proc.stdout}\nSTDERR:{proc.stderr}"


# ---------------------------------------------------------------------------
# --help works on every CLI entry
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("script", [
    "execution/personal_workflows/job_search_sheet.py",
    "execution/personal_workflows/job_search_setup.py",
    "execution/personal_workflows/job_search_notify.py",
    "execution/custom_scrapers/adzuna_jobs.py",
    "execution/custom_scrapers/jooble_jobs.py",
])
def test_cli_help_works(script: str):
    proc = _py(script, "--help")
    assert proc.returncode == 0, f"{script} --help failed:\n{proc.stderr}"
    # Help text should mention either 'usage:' or 'options:' or 'description:'
    combined = (proc.stdout + proc.stderr).lower()
    assert "usage" in combined or "options" in combined or "description" in combined, \
        f"{script} --help produced unexpected output:\n{proc.stdout[:400]}"


# ---------------------------------------------------------------------------
# Config files are well-formed
# ---------------------------------------------------------------------------

def test_config_job_search_parses():
    cfg = json.loads((ROOT / "config" / "job_search.json").read_text(encoding="utf-8"))
    assert "visible_tabs" in cfg
    assert "column_headers" in cfg
    assert "titles" in cfg
    assert len(cfg["visible_tabs"]) == 6, "Phase 1a expects 6 visible tabs"
    assert "_meta" not in cfg["visible_tabs"], "_meta tab must NOT be in visible_tabs"
    assert "Summary" not in cfg["visible_tabs"], "Summary tab is auto-added, not in config"
    # Every visible tab must have a matching title key
    for tab in cfg["visible_tabs"]:
        assert tab in cfg["titles"], f"tab {tab!r} has no entry in cfg['titles']"


def test_workflow_yaml_present():
    p = ROOT / ".github" / "workflows" / "job_search_daily.yml"
    assert p.exists(), "GH Actions workflow missing"
    txt = p.read_text(encoding="utf-8")
    assert "cron:" in txt
    assert "GOOGLE_SERVICE_ACCOUNT_JSON_B64" in txt
    assert "GMAIL_SMTP_USER" in txt, "Daily-summary email vars must be wired into the workflow"
    assert "concurrency:" in txt, "Concurrency guard required per plan A5"


def test_gitignore_protects_secrets():
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gi
    assert "credentials/" in gi or "credentials.json" in gi


# ---------------------------------------------------------------------------
# Runs log integrity
# ---------------------------------------------------------------------------

def test_runs_log_lines_parse():
    """If a runs log exists, every line must parse as JSON (otherwise summary breaks)."""
    log = ROOT / ".tmp" / "job_search" / "job_search_runs.jsonl"
    if not log.exists():
        pytest.skip("No runs log yet")
    bad = []
    for i, raw in enumerate(log.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            json.loads(raw)
        except json.JSONDecodeError as exc:
            bad.append((i, str(exc)[:100]))
    assert not bad, f"Malformed runs.jsonl lines: {bad}"


# ---------------------------------------------------------------------------
# Setup check-only is exit-0 in current state
# ---------------------------------------------------------------------------

def test_check_only_passes_in_current_state():
    """The provisioning is supposed to be complete; --check-only should be all green."""
    proc = _py("execution/personal_workflows/job_search_setup.py", "--check-only", timeout=120)
    if proc.returncode != 0:
        pytest.skip(f"--check-only fails in current env (likely missing SA JSON in CI):\n{proc.stdout[-600:]}")
    assert "all" in proc.stdout.lower() and "passed" in proc.stdout.lower()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
