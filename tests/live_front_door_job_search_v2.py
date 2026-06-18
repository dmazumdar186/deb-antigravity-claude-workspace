"""
description: TRUE live front-door synthetic for job_search_v2 per the 2026-06-18
    tightening of `~/.claude/rules/front-door-synthetic.md`. Reads the most-recent
    LIVE run from .tmp/job_search_v2/run_log.jsonl and asserts the floor on
    `total_fetched` + `non_zero_sources`. A green pass here means the production
    cron is genuinely serving the operator — not just that fixtures parse.
inputs:
    - .tmp/job_search_v2/run_log.jsonl (one summary line per orchestrator run)
    - CLI: --fetch-floor (default 5), --nonzero-sources-floor (default 2),
           --max-age-hours (default 25 — covers daily cron + 1h slack), --window (number of recent live runs to consider, default 1)
outputs:
    - stdout: PASS / DEGRADED summary
    - exit code: 0 on PASS, 1 on DEGRADED

Per the rule: a DEGRADED day flips system status to DEGRADED in every report and
resets the 5-consecutive-day count to zero. The substitute label for the
operator-facing status while the count is < 5 is exactly:
    LIVE-PROBATIONARY: day N of 5
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_LOG = PROJECT_ROOT / ".tmp" / "job_search_v2" / "run_log.jsonl"


def _read_runs(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _parse_run_id_utc(run_id: str) -> datetime | None:
    """run_id format: '20260618T065002-06d01f' (UTC timestamp + uuid suffix)."""
    if not run_id or "-" not in run_id:
        return None
    stamp = run_id.rsplit("-", 1)[0]
    try:
        return datetime.strptime(stamp, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def evaluate(
    runs: list[dict],
    fetch_floor: int,
    nonzero_sources_floor: int,
    max_age_hours: float,
    window: int,
) -> tuple[bool, list[str]]:
    """Return (is_passing, lines_to_print). Pure — no I/O so it's unit-testable."""
    lines: list[str] = []

    live_runs = [r for r in runs if r.get("mode") == "live"]
    if not live_runs:
        lines.append("DEGRADED: no live runs found in run_log.jsonl (only fixture runs).")
        return False, lines

    # Take the last `window` live runs, newest first.
    recent = live_runs[-window:]
    now = datetime.now(timezone.utc)
    horizon = now - timedelta(hours=max_age_hours)

    fresh = [r for r in recent if (_parse_run_id_utc(r.get("run_id", "")) or now) >= horizon]
    if not fresh:
        latest = recent[-1]
        age_hint = _parse_run_id_utc(latest.get("run_id", "")) or now
        hours_old = (now - age_hint).total_seconds() / 3600.0
        lines.append(
            f"DEGRADED: most recent live run is {hours_old:.1f}h old "
            f"(> max_age_hours={max_age_hours:.1f}). Cron may have stopped firing."
        )
        return False, lines

    issues: list[str] = []
    for r in fresh:
        per_source = r.get("per_source", {}) or {}
        nonzero = sum(1 for v in per_source.values() if v and int(v) > 0)
        total = int(r.get("total_fetched", 0))
        run_id = r.get("run_id", "?")

        lines.append(f"  run={run_id}  total_fetched={total}  non_zero_sources={nonzero}  per_source={per_source}")

        if total < fetch_floor:
            issues.append(f"    FAIL: total_fetched={total} < floor={fetch_floor}")
        if nonzero < nonzero_sources_floor:
            issues.append(f"    FAIL: non_zero_sources={nonzero} < floor={nonzero_sources_floor}")

    if issues:
        lines.append("")
        lines.extend(issues)
        lines.append("")
        lines.append(
            "DEGRADED — at least one recent live run is below the floor. "
            "Per ~/.claude/rules/front-door-synthetic.md, system status is DEGRADED "
            "until two consecutive runs clear the floor. The 5-consecutive-day "
            "LIVE-PROBATIONARY counter resets to 0."
        )
        return False, lines

    lines.append("")
    lines.append(
        f"PASS — all {len(fresh)} recent live run(s) clear floor "
        f"(fetch ≥ {fetch_floor}, non_zero_sources ≥ {nonzero_sources_floor})."
    )
    return True, lines


def main() -> int:
    parser = argparse.ArgumentParser(description="TRUE live front-door synthetic for job_search_v2.")
    parser.add_argument("--run-log", type=Path, default=RUN_LOG,
                        help="Path to run_log.jsonl (default: .tmp/job_search_v2/run_log.jsonl)")
    parser.add_argument("--fetch-floor", type=int, default=5,
                        help="Min total_fetched per run (default 5).")
    parser.add_argument("--nonzero-sources-floor", type=int, default=2,
                        help="Min non-zero sources per run (default 2).")
    parser.add_argument("--max-age-hours", type=float, default=25.0,
                        help="Max age of the most recent live run (default 25h).")
    parser.add_argument("--window", type=int, default=1,
                        help="How many recent live runs to evaluate (default 1).")
    args = parser.parse_args()

    print(f"live_front_door_job_search_v2: reading {args.run_log}")
    runs = _read_runs(args.run_log)
    print(f"  total runs in log: {len(runs)}")

    ok, lines = evaluate(
        runs,
        fetch_floor=args.fetch_floor,
        nonzero_sources_floor=args.nonzero_sources_floor,
        max_age_hours=args.max_age_hours,
        window=args.window,
    )
    for line in lines:
        try:
            print(line)
        except UnicodeEncodeError:
            sys.stdout.buffer.write((line + "\n").encode("utf-8", errors="replace"))

    print()
    print("== live_front_door_job_search_v2:", "PASS ==" if ok else "DEGRADED ==")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
