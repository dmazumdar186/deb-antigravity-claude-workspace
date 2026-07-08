"""
test_run_smoke.py
description: End-to-end dry-run smoke test. `py run.py --dry-run` MUST exit 0, produce a run log, and emit all pipeline artifacts under .tmp/self_outbound/.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
RUN_PY = ROOT / "run.py"
TMP = ROOT.parents[2] / ".tmp" / "self_outbound"


def test_run_dry_run_smoke():
    """Invoke run.py --dry-run, assert exit 0, assert artifacts exist."""
    env = dict(os.environ)  # never copy.copy(os.environ); hardening rule 6
    env["KILL_SWITCH"] = "0"

    proc = subprocess.run(
        [sys.executable, str(RUN_PY), "--dry-run"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0, (
        f"run.py --dry-run exited {proc.returncode}\n"
        f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )

    # Each pipeline step must have written at least one artifact.
    patterns = [
        "sourced_leads_*.json",
        "filtered_leads_*.json",
        "enriched_leads_*.json",
        "personalized_leads_*.json",
        "instantly_result_*.json",
        "canary_*.json",
        "acceptance_*.json",
        "run_*.log",
    ]
    missing = [p for p in patterns if not list(TMP.glob(p))]
    assert not missing, f"missing artifacts in {TMP}: {missing}"


def test_run_halts_when_killswitch_set():
    """KILL_SWITCH=1 in env must halt run.py immediately with rc=2."""
    env = dict(os.environ)
    env["KILL_SWITCH"] = "1"

    proc = subprocess.run(
        [sys.executable, str(RUN_PY), "--dry-run"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=str(ROOT),
    )
    assert proc.returncode == 2, f"expected rc=2 on KILL_SWITCH=1, got {proc.returncode}"
    assert "KILL_SWITCH" in proc.stdout or "KILL_SWITCH" in proc.stderr
