"""Run every GreenJobs redesign test in one command.

description: Executes test_build.py (build + validator, which also runs
  test_scrape.py's offline scraper suite and test_gaps.py), the node --test
  suites for lib.js and dashboard.js, the Playwright dashboard DOM check and
  the Playwright layout regression suite. A browser tier that cannot run
  prints SKIP; the exit code is then non-zero unless --allow-skip is given
  (round 4: a skipped tier is not a passed tier). Prints the total check
  count and writes it into COVERAGE.md.
inputs: --allow-skip (optional)
outputs: each tier's PASS/FAIL/SKIP lines, a summary with the total check
  count; COVERAGE.md "Last full run" line updated; exit code 0/1

Run: python3 tests/greenjobs_redesign/run_all.py
Coverage: python3 -m coverage run --include="execution/gtm_client_workflows/greenjobs_redesign/*" tests/greenjobs_redesign/test_build.py && python3 -m coverage report -m
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
JS = REPO / "deliverables" / "greenjobs_redesign_2026-09-22" / "src" / "js"
COVERAGE = HERE / "COVERAGE.md"
RUN_LINE = re.compile(r"^Last full run \(run_all\.py.*$", re.M)


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=str(cwd), text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    sys.stdout.write(proc.stdout)
    sys.stdout.flush()
    return proc.returncode, proc.stdout


def count_checks(out: str, node: bool = False) -> int:
    """Checks a tier ran: the python summary line, node's TAP totals, or PASS/FAIL lines."""
    m = re.search(r"Unit\+Integration: (\d+) passed, (\d+) failed", out)
    if m:
        return int(m.group(1)) + int(m.group(2))
    if node:
        return sum(int(x) for x in re.findall(r"^# (?:pass|fail) (\d+)$", out, re.M))
    return len(re.findall(r"^(?:PASS|FAIL) ", out, re.M))


def write_total(total: int, tiers: list[tuple[str, str, int]]) -> None:
    if not COVERAGE.exists():
        return
    text = COVERAGE.read_text(encoding="utf-8")
    line = f"Last full run (run_all.py, {date.today().isoformat()}): {total} checks — " + ", ".join(f"{n} {s.lower()} ({c})" for s, n, c in tiers) + "."
    text = RUN_LINE.sub(line, text) if RUN_LINE.search(text) else text.rstrip("\n") + "\n\n" + line + "\n"
    COVERAGE.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--allow-skip", action="store_true", help="a browser tier that prints SKIP does not fail the run")
    a = ap.parse_args(argv)
    tiers: list[tuple[str, str, int]] = []  # (status, name, checks)

    def add(name: str, rc: int, out: str, node: bool = False, may_skip: bool = False) -> None:
        skipped = may_skip and rc == 0 and re.search(r"^SKIP ", out, re.M) is not None
        tiers.append(("SKIP" if skipped else "PASS" if rc == 0 else "FAIL", name, count_checks(out, node)))

    rc, out = run([sys.executable, str(HERE / "test_build.py")], REPO)  # its main() runs test_scrape and test_gaps too
    add("python (build + validate + scrape + gaps)", rc, out)
    rc, out = run(["node", "--test", "lib.test.js", "dashboard.test.js"], JS)
    add("node --test lib.js + dashboard.js", rc, out, node=True)
    rc, out = run(["node", str(HERE / "dashboard_dom.test.mjs")], REPO)
    add("playwright dashboard DOM", rc, out, may_skip=True)
    rc, out = run(["node", str(HERE / "layout.test.mjs")], REPO)
    add("playwright layout regression", rc, out, may_skip=True)
    total = sum(c for _, _, c in tiers)
    print("\nSummary:")
    for status, name, checks in tiers:
        print(f"  {status}  {name} ({checks} checks)")
    print(f"  Total: {total} checks across {len(tiers)} tiers")
    write_total(total, tiers)
    failed = any(s == "FAIL" for s, _, _ in tiers)
    skipped = any(s == "SKIP" for s, _, _ in tiers)
    if skipped and not a.allow_skip:
        print("  A browser tier was skipped; pass --allow-skip to accept that (exit 1 otherwise).")
    return 1 if failed or (skipped and not a.allow_skip) else 0


if __name__ == "__main__":
    raise SystemExit(main())
