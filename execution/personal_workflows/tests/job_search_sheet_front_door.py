"""Front-door synthetic for the job_search_sheet orchestrator.

Per ~/.claude/rules/front-door-synthetic.md: enters through the same CLI a
GitHub-Actions cron does — `py execution/personal_workflows/job_search_sheet.py
--mock --dry-run --no-llm` — and asserts each pipeline stage emits its
expected log line.

Costs NOTHING per run: --mock uses tests/fixtures/raw_*.json instead of
hitting Adzuna / Jooble / FranceTravail; --dry-run skips the Google Sheets
write; --no-llm skips Stage 2.5 so no Gemini quota is burned.

Usage:
    py execution/personal_workflows/tests/job_search_sheet_front_door.py
    py execution/personal_workflows/tests/job_search_sheet_front_door.py --runs 5
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[2]
ORCHESTRATOR = WORKSPACE / "execution" / "personal_workflows" / "job_search_sheet.py"

# Expected stage log markers, in order.
EXPECTED_STAGES = [
    "Stage 0",          # bootstrap
    "Stage 1",          # discovery
    "Stage 2",          # keyword filter
    "Stage 3",          # dedup
    "Stage",            # final stage marker (sheet write or dry-run summary)
]


def run_once(extra_args: list[str]) -> tuple[bool, str]:
    cmd = [
        sys.executable, str(ORCHESTRATOR),
        "--mock", "--dry-run", "--no-llm",
        *extra_args,
    ]
    # Force SHEETS_SPREADSHEET_ID empty so the orchestrator's `if not dry_run
    # or sheet_id:` guard skips the Sheets API read entirely. Without this
    # the synthetic burns the operator's 60-reads/min Sheets quota and goes
    # flaky on consecutive runs.
    import os as _os
    env = dict(_os.environ)
    env["SHEETS_SPREADSHEET_ID"] = ""
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(WORKSPACE),
            env=env,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return False, "timeout >120s"

    combined = (r.stdout or "") + (r.stderr or "")

    if r.returncode != 0:
        return False, f"exit={r.returncode}; last 200 chars: {combined[-200:]!r}"

    # Stage progression: each expected marker must appear at least once.
    missing = [s for s in EXPECTED_STAGES if s not in combined]
    if missing:
        return False, f"missing stage markers: {missing}; got: {combined[-300:]!r}"

    # Reject silent-fallback symptoms: parse_error from the LLM gate is one
    # of the audit-flagged silent failure modes. With --no-llm the gate is
    # skipped so this should never appear.
    if "parse_error" in combined.lower():
        return False, "parse_error in output — --no-llm should skip the gate entirely"

    return True, "stages emitted; exit 0; no parse_error"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--delay", type=float, default=1.0)
    args, extra = ap.parse_known_args()

    passes = 0
    for i in range(1, args.runs + 1):
        print(f"\n=== Run {i}/{args.runs} ===", file=sys.stderr)
        ok, msg = run_once(extra)
        tag = "PASS" if ok else "FAIL"
        print(f"  [front-door] {tag}: {msg}", file=sys.stderr)
        if not ok:
            return 1
        passes += 1
        if i < args.runs:
            time.sleep(args.delay)

    print(f"\n[front-door] all {args.runs} run(s) PASS ({passes}/{args.runs})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
