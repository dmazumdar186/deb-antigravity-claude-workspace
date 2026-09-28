"""Run every GreenJobs redesign test in one command.

description: Executes test_build.py (build + validator, which also runs
  test_scrape.py's offline scraper suite), the node --test suites for lib.js
  and dashboard.js, and the Playwright dashboard DOM check (which skips
  itself when Chromium is absent). Exit 1 if any tier fails.
inputs: none
outputs: each tier's PASS/FAIL lines, then a summary; exit code 0/1

Run: python3 tests/greenjobs_redesign/run_all.py
Coverage: python3 -m coverage run --include="execution/gtm_client_workflows/greenjobs_redesign/*" tests/greenjobs_redesign/run_all.py && python3 -m coverage report -m
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
JS = REPO / "deliverables" / "greenjobs_redesign_2026-09-22" / "src" / "js"


def main() -> int:
    # Same semantics as `python3 tests/greenjobs_redesign/test_build.py`
    # (its main() runs test_scrape and test_gaps as well), so one command and
    # the documented coverage command see exactly the same checks.
    import runpy
    try:
        runpy.run_path(str(HERE / "test_build.py"), run_name="__main__")
        py_rc = 0
    except SystemExit as exc:
        py_rc = int(exc.code or 0)
    tiers: list[tuple[str, int]] = [("python (build + validate + scrape + gaps)", py_rc)]
    node = subprocess.run(["node", "--test", "lib.test.js", "dashboard.test.js"], cwd=str(JS), text=True, encoding="utf-8", errors="replace")
    tiers.append(("node --test lib.js + dashboard.js", node.returncode))
    dom = subprocess.run(["node", str(HERE / "dashboard_dom.test.mjs")], cwd=str(REPO), text=True, encoding="utf-8", errors="replace")
    tiers.append(("playwright dashboard DOM", dom.returncode))
    print("\nSummary:")
    for name, rc in tiers:
        print(f"  {'PASS' if rc == 0 else 'FAIL'}  {name} (exit {rc})")
    return 1 if any(rc for _, rc in tiers) else 0


if __name__ == "__main__":
    raise SystemExit(main())
