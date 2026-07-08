"""
run.py
description: Daily orchestrator for the self-outbound system. Reads KILL_SWITCH first; halts if 1. Chains canary → sourcer → icp_filter → enricher → personalizer → instantly_client(upload) → instantly_client(stats) → acceptance → digest. Canary FAIL halts the day; acceptance FAIL engages the kill switch.
inputs: --segment <name>, --limit <int>, --dry-run/--live, --output-log <path>. Env: KILL_SWITCH (halt if 1).
outputs: .tmp/self_outbound/run_<date>.log — structured JSONL log of each step. Prints end-of-run digest to stdout.

Reads directive: directives/personal_workflows/self_outbound_system.md (Phase 3 script #12, the orchestrator).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    TMP_DIR,
    ensure_tmp_dir,
    get_logger,
    print_stat,
    timestamp,
    today_str,
)

load_dotenv()
log = get_logger("run")

SCRIPT_DIR = Path(__file__).resolve().parent

# Set in main() at run start. _find_latest filters TMP_DIR by mtime >= this
# timestamp so a crashed step CANNOT silently substitute yesterday's artifact.
# Pipeline-auditor 2026-07-08 empirically reproduced this bug — the fix is
# time-scoped file lookup + explicit returncode checks on every step.
_RUN_START_TS: float = 0.0


def _sh(step: str, args: list[str], run_log: Path) -> subprocess.CompletedProcess:
    """Invoke a sub-script under the same Python interpreter, capturing
    stdout/stderr with utf-8 encoding per hardening rule 1.
    Sets PYTHONIOENCODING=utf-8 so the child can print non-ASCII without
    crashing on Windows cp1252 default stdout encoding."""
    cmd = [sys.executable, str(SCRIPT_DIR / f"{step}.py"), *args]
    log.info("step=%s cmd=%s", step, " ".join(cmd[1:]))
    # Never copy.copy(os.environ); hardening rule 6
    child_env = dict(os.environ)
    child_env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=child_env,
    )
    with open(run_log, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "step": step,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }, ensure_ascii=False) + "\n")
    # Reconfigure own stdout/stderr for utf-8 on first write to avoid cp1252
    # crashes when relaying child output (e.g. em-dashes elsewhere in the
    # pipeline). Idempotent; Python 3.7+.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError) as exc:
            # AttributeError: not a TextIOWrapper (e.g. redirected pipe wrapper)
            # ValueError: already reconfigured or unsupported
            log.debug("could not reconfigure %s: %s (safe to ignore)", stream, exc)
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    return proc


def _dry_flag(dry_run: bool) -> str:
    return "--dry-run" if dry_run else "--live"


def _find_latest(pattern: str) -> Path | None:
    """Find latest file matching pattern IN THIS RUN. Files older than
    _RUN_START_TS are ignored — otherwise a crashed step silently
    substitutes yesterday's artifact and the pipeline reports all-green
    on stale data (pipeline-auditor 2026-07-08, empirically reproduced)."""
    matches = sorted(TMP_DIR.glob(pattern))
    fresh = [p for p in matches if p.stat().st_mtime >= _RUN_START_TS]
    return fresh[-1] if fresh else None


def _run_step(
    step: str,
    args_list: list[str],
    run_log: Path,
    output_pattern: str | None,
    step_stats: dict[str, str],
) -> Path | None:
    """Run a sub-step. Check returncode. If output_pattern is given, verify
    the step produced a fresh file matching it. Returns output path on
    success (or True-ish sentinel when output_pattern is None); None on ANY
    failure. Caller inspects return value + step_stats and decides how to
    halt.

    Fixes P0 bug found by code-reviewer + pipeline-auditor 2026-07-08:
    prior scaffold ignored returncode and inferred success from file
    presence, silently continuing on stale data when a step crashed.
    """
    proc = _sh(step, args_list, run_log)
    if proc.returncode != 0:
        log.error("%s FAIL (returncode=%d)", step, proc.returncode)
        step_stats[step] = "FAIL"
        return None
    if output_pattern is not None:
        out_path = _find_latest(output_pattern)
        if out_path is None:
            log.error(
                "%s returned 0 but produced no fresh output matching '%s' "
                "(refusing to reuse stale artifact from prior run).",
                step,
                output_pattern,
            )
            step_stats[step] = "FAIL_NO_FRESH_OUTPUT"
            return None
        step_stats[step] = "OK"
        return out_path
    step_stats[step] = "OK"
    return TMP_DIR  # sentinel: step ran + returned 0 but produces no artifact


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[1])
    p.add_argument("--segment", type=str, default=None,
                   help="Optional segment name (see config/icp.json).")
    p.add_argument("--limit", type=int, default=0,
                   help="Override daily send cap. 0 = use icp.json total_daily_send_cap.")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", default=True,
                   help="Dry-run (default). Passes --dry-run to every sub-script.")
    p.add_argument("--live", dest="dry_run", action="store_false",
                   help="Live mode. All sub-scripts flip to --live.")
    p.add_argument("--output-log", type=Path, default=None,
                   help="Override run-log path.")
    return p.parse_args(argv)


def _halt(reason: str, run_log: Path, dry: str, step_stats: dict, args_dry_run: bool) -> int:
    """Fire digest, print run-stats, return non-zero. Common halt path."""
    _sh("digest", [dry], run_log)
    print_stat("run", {"halted_at": reason, "step_stats": step_stats, "dry_run": args_dry_run})
    return 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ensure_tmp_dir()

    # Set run-start timestamp BEFORE any step fires. _find_latest filters
    # TMP_DIR by mtime >= this value to prevent stale-data substitution.
    global _RUN_START_TS
    _RUN_START_TS = time.time()

    # Never copy.copy(os.environ) — hardening rule 6
    env = dict(os.environ)
    kill = env.get("KILL_SWITCH", "0").strip()
    if kill == "1":
        msg = "KILL_SWITCH=1 in env — halting run.py immediately. No sub-steps executed."
        log.error(msg)
        print(msg)
        return 2

    dry = _dry_flag(args.dry_run)
    run_log = args.output_log or (TMP_DIR / f"run_{today_str()}_{timestamp()}.log")
    run_log.parent.mkdir(parents=True, exist_ok=True)
    run_log.write_text("", encoding="utf-8")  # reset per run

    step_stats: dict[str, str] = {}

    # 1. Canary (front-door synthetic). FAIL halts the day.
    canary_proc = _sh("canary", [dry], run_log)
    step_stats["canary"] = "PASS" if canary_proc.returncode == 0 else "FAIL"
    if canary_proc.returncode != 0:
        log.error("canary FAIL — halting day. No cold sends.")
        return _halt("canary", run_log, dry, step_stats, args.dry_run)

    # 2. Sourcer.
    sourcer_args = [dry]
    if args.segment:
        sourcer_args += ["--segment", args.segment]
    if args.limit:
        sourcer_args += ["--limit", str(args.limit)]
    sourced_path = _run_step("sourcer", sourcer_args, run_log, "sourced_leads_*.json", step_stats)
    if sourced_path is None:
        return _halt("sourcer", run_log, dry, step_stats, args.dry_run)

    # 3. ICP filter. returncode + fresh-output check via _run_step.
    filtered_path = _run_step("icp_filter", ["--input", str(sourced_path), dry], run_log, "filtered_leads_*.json", step_stats)
    if filtered_path is None:
        return _halt("icp_filter", run_log, dry, step_stats, args.dry_run)

    # 4. Enricher.
    enriched_path = _run_step("enricher", ["--input", str(filtered_path), dry], run_log, "enriched_leads_*.json", step_stats)
    if enriched_path is None:
        return _halt("enricher", run_log, dry, step_stats, args.dry_run)

    # 5. Personalizer.
    personalized_path = _run_step("personalizer", ["--input", str(enriched_path), dry], run_log, "personalized_leads_*.json", step_stats)
    if personalized_path is None:
        return _halt("personalizer", run_log, dry, step_stats, args.dry_run)

    # 6. Instantly upload — returncode gated (was unconditionally OK before fix).
    upload_path = _run_step(
        "instantly_client",
        ["--action", "upload", "--input", str(personalized_path), dry],
        run_log,
        "instantly_result_*.json",
        step_stats,
    )
    # Rename step_stats key so the two instantly_client calls are distinguishable
    upload_stat = step_stats.pop("instantly_client", "FAIL")
    step_stats["instantly_upload"] = upload_stat
    if upload_path is None:
        return _halt("instantly_upload", run_log, dry, step_stats, args.dry_run)

    # 7. Instantly stats (fixture in dry-run) so digest + acceptance can read them.
    stats_path = _run_step(
        "instantly_client",
        ["--action", "stats", dry],
        run_log,
        "instantly_result_*.json",
        step_stats,
    )
    stats_stat = step_stats.pop("instantly_client", "FAIL")
    step_stats["instantly_stats"] = stats_stat
    if stats_path is None:
        # Not fatal — acceptance can still run corpus check. Continue with warning.
        log.warning("instantly_stats FAIL — acceptance will run corpus-only")

    # 8. Acceptance gate. In dry-run, corpus + today's-output check. Failure engages kill switch.
    acceptance_args = [dry]
    if stats_path is not None and not args.dry_run:
        acceptance_args += ["--stats", str(stats_path)]
    accept_proc = _sh("acceptance", acceptance_args, run_log)
    step_stats["acceptance"] = "PASS" if accept_proc.returncode == 0 else "FAIL"
    if accept_proc.returncode != 0:
        log.error("acceptance FAIL — engaging kill switch")
        _sh("killswitch", ["--engage", dry], run_log)
        return _halt("acceptance", run_log, dry, step_stats, args.dry_run)

    # 9. Digest.
    _sh("digest", [dry], run_log)
    step_stats["digest"] = "OK"

    print_stat("run", {
        "step_stats": step_stats,
        "dry_run": args.dry_run,
        "run_log": str(run_log),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
