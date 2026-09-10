"""
_stage_runner.py
description: Shared subprocess-invocation helpers for run_metro.py and daily.py. Every other
    package (discovery/, audit/, enrich/, preview/, outreach/, deals/) may not exist yet when this
    module is imported or run — per CONTRACTS.md, callers run each stage as a subprocess
    `python3 -m execution.personal_workflows.prodcraft_medspa.<pkg>.<script> ...` and treat a
    missing module as a clean stage failure rather than crashing the orchestrator.
inputs: Imported only; no CLI args, no env vars of its own.
outputs: dict results describing each subprocess invocation; no files written.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
PKG_DOTTED = "execution.personal_workflows.prodcraft_medspa"


def parse_stat_line(stdout: str) -> dict[str, Any] | None:
    """Return the last stdout line that parses as JSON with a "script" key, else None.

    CONTRACTS.md: "Every script ends by printing a one-line JSON stat
    (`{"script": ..., "in": n, "out": n, "dropped": {...}}`) to stdout." Scripts may also print
    progress/log lines before it, so scan from the bottom and take the first hit.
    """
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "script" in obj:
            return obj
    return None


def run_module(module_dotted: str, args: list[str], *, timeout: int = 1800) -> dict[str, Any]:
    """Run `python3 -m execution.personal_workflows.prodcraft_medspa.<module_dotted> <args>`.

    Returns a dict:
        {
          "module": module_dotted, "args": args, "returncode": int,
          "stat": dict | None,          # parsed final JSON stat line, if any
          "ok": bool,                   # returncode == 0 and a stat line was found
          "error": str | None,          # human-readable failure reason, else None
          "stdout": str, "stderr": str,
        }

    A missing module (other agents' packages may not exist yet in a fresh checkout) surfaces here
    as returncode != 0 with a clear "module not found" error rather than an exception, per
    CONTRACTS.md's "treat a missing module as a stage failure with a clear message".
    """
    full_module = f"{PKG_DOTTED}.{module_dotted}"
    cmd = [sys.executable, "-m", full_module, *args]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "module": module_dotted,
            "args": args,
            "returncode": -1,
            "stat": None,
            "ok": False,
            "error": f"timed out after {timeout}s: {exc}",
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }
    except OSError as exc:
        # e.g. the interpreter itself could not be launched — extremely unlikely, but
        # never let stage orchestration crash the caller.
        return {
            "module": module_dotted,
            "args": args,
            "returncode": -1,
            "stat": None,
            "ok": False,
            "error": f"could not launch subprocess: {exc}",
            "stdout": "",
            "stderr": "",
        }

    stat = parse_stat_line(proc.stdout)
    error: str | None = None
    if proc.returncode != 0:
        stderr_tail = "\n".join(proc.stderr.strip().splitlines()[-15:])
        if "ModuleNotFoundError" in proc.stderr or "No module named" in proc.stderr:
            error = (
                f"module '{full_module}' is not implemented yet "
                f"(ModuleNotFoundError) — this stage is owned by another agent's package"
            )
        else:
            error = f"exit {proc.returncode}: {stderr_tail or '(no stderr)'}"
    elif stat is None:
        error = "exit 0 but no final JSON stat line found on stdout"

    return {
        "module": module_dotted,
        "args": args,
        "returncode": proc.returncode,
        "stat": stat,
        "ok": proc.returncode == 0 and stat is not None,
        "error": error,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def common_store_args(args) -> list[str]:
    """Build the shared --mock / --store / --store-root flags from an argparse Namespace."""
    out: list[str] = []
    if getattr(args, "mock", False):
        out.append("--mock")
    store = getattr(args, "store", None)
    if store:
        out += ["--store", store]
    store_root = getattr(args, "store_root", None)
    if store_root:
        out += ["--store-root", store_root]
    return out
