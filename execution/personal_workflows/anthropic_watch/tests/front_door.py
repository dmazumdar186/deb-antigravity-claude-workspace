"""Front-door synthetic for anthropic_watch.

Per ~/.claude/rules/front-door-synthetic.md: enters through the actual user
surface (cron CLI command `py run.py --dry-run`), no internal shortcuts.

A real run against the live Firecrawl + GitHub + npm sources hits paid quota.
This synthetic exercises the run.py main() entry-point in-process with a
patched fetch_all that returns deterministic fixture data, so it can run
5/5 consecutively without burning Firecrawl credit. The ledger / Claude /
network paths are exercised by the unit tests in tests/test_anthropic_watch.py.

Usage:
  py execution/personal_workflows/anthropic_watch/tests/front_door.py
  py execution/personal_workflows/anthropic_watch/tests/front_door.py --runs 5
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
WORKSPACE_ROOT = HERE.parents[3]
sys.path.insert(0, str(WORKSPACE_ROOT))

from execution.personal_workflows.anthropic_watch import fetch as fetch_mod
from execution.personal_workflows.anthropic_watch import run as run_mod


def _fixture_items() -> dict[str, list[dict]]:
    """Deterministic per-source items. Keeps the synthetic cheap + repeatable."""
    return {
        "anthropic-news": [
            {"url": "https://www.anthropic.com/news/sample", "title": "Sample announcement",
             "source": "anthropic-news", "published": None, "raw_excerpt": "x"},
        ],
        "docs-claude-code": [],
        "github-claude-code": [
            {"url": "https://github.com/anthropics/claude-code/releases/tag/v0.0.1",
             "title": "v0.0.1", "source": "github-claude-code",
             "published": "2026-06-15", "raw_excerpt": "release"},
        ],
    }


def _run_once() -> tuple[int, str]:
    """One run of `run.main()` with --dry-run, patched fetchers, captured stdout."""
    fixture = _fixture_items()
    real_fetch_all = fetch_mod.fetch_all
    real_argv = sys.argv
    real_stdout = sys.stdout

    sys.stdout = io.StringIO()
    fetch_mod.fetch_all = lambda only=None: fixture
    # Also update the imported reference inside run_mod.
    run_mod.fetch_mod.fetch_all = lambda only=None: fixture
    sys.argv = ["run.py", "--dry-run"]
    try:
        rc = run_mod.main()
        out = sys.stdout.getvalue()
    finally:
        sys.argv = real_argv
        sys.stdout = real_stdout
        fetch_mod.fetch_all = real_fetch_all
        run_mod.fetch_mod.fetch_all = real_fetch_all
    return rc, out


def run_once() -> bool:
    rc, out = _run_once()
    if rc != 0:
        print(f"[front-door] FAIL: exit={rc}", file=sys.stderr)
        return False
    # Validate every fixture source's count line shows up.
    fixture = _fixture_items()
    missing = []
    for source, items in fixture.items():
        line = f"{source}: {len(items)} items"
        if line not in out:
            missing.append(line)
    if missing:
        print(f"[front-door] FAIL: stdout missing lines: {missing}", file=sys.stderr)
        return False
    print(f"[front-door] PASS sources={len(fixture)}", file=sys.stderr)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=1)
    args = ap.parse_args()

    passes = 0
    for i in range(1, args.runs + 1):
        print(f"\n=== Run {i}/{args.runs} ===", file=sys.stderr)
        if run_once():
            passes += 1
        else:
            return 1

    print(f"\n[front-door] all {args.runs} run(s) PASS", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
