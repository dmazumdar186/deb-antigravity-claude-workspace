#!/usr/bin/env python3
"""Generate the GreenJobs test register (handover/TEST_REGISTER.md).

Lists every test under tests/greenjobs_redesign/ (plus the browser-free JS tests
that build/run_tests.sh runs from the board source), grouped by engagement
promise P# where the mapping in PROMISES says so. Which files are part of the
suite is read from the CURRENT build/run_tests.sh, never from a copy.

  python3 .../ops/test_register.py                 # list only, "last run: not run"
  python3 .../ops/test_register.py --run           # run run_tests.sh + every covered file
  python3 .../ops/test_register.py --run --out deliverables/greenjobs_migration_2026-11-06/handover/TEST_REGISTER.md

Offline, no network, no secrets. Writes only --out (default: stdout).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import OrderedDict
from datetime import date
from pathlib import Path

ROOT = Path(
    subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=Path(__file__).resolve().parent,
    ).stdout.strip()
)
TESTS = ROOT / "tests" / "greenjobs_redesign"
RUN_TESTS = ROOT / "deliverables/greenjobs_migration_2026-11-06/build/run_tests.sh"
FEATURES = ROOT / "deliverables/greenjobs_migration_2026-11-06/build/features"
JS_SRC = ROOT / "deliverables/greenjobs_redesign_2026-09-22/src/js"

PROMISE_TITLES = OrderedDict(
    [
        ("P1", "Both boards on Keith's domains, current jobs, our design"),
        ("P2", "Staff console: post, edit, close (and reopen)"),
        ("P3", "Applications to the chosen inbox (per-job email or link)"),
        ("P4", "Job alert emails (flag off)"),
        ("P5a", "Candidate records Keith chooses to keep (consented import)"),
        ("P6", "KPI dashboard, figures live from job data"),
        ("P7", "301 for every indexed URL; export and import"),
        ("P8", "Weekly update and monthly report"),
        ("P9", "Daily backups, quarterly restore drill, uptime monitoring"),
        ("P11", "Employer logins (phase 2, flag off)"),
        ("P13", "Gaia feed (standalone, not wired to the board)"),
        ("P15", "Newsletter sends (flag off)"),
        ("P16", "Export archive (Strategies export bot)"),
        ("P17", "10 working days of acceptance checks"),
        ("P18", "JobPosting structured data and sitemaps"),
        ("P20", "Service levels (99.9% uptime, 4 h posting outage, 1 business day)"),
        ("P21", "Change-document items re-verified on the new build"),
        ("P23", "The two site-manager fixes"),
        ("P24", "Analytics (GA4)"),
        ("P25", "Security patches, release pipeline, staging smoke"),
        ("UNMAPPED", "Supporting or hardening tests with no single promise"),
    ]
)

# first matching rule wins; paths are relative to tests/greenjobs_redesign/
RULES = [
    (r"^platform/e2e_board", ["P1", "P2", "P3"]),
    (
        r"^platform/(worker|auth|validate|audit_fixes|integration_gaps)\.test",
        ["P2", "P3"],
    ),
    (r"^platform/apply_mode|^test_apply_mode_site", ["P3"]),
    (r"^platform/bdd_runner|^platform/bdd_steps|^platform/gherkin", ["P1", "P2", "P3"]),
    (r"^platform/(parity|board_wiring|live_consistency)", ["P1"]),
    (r"^platform/listmail", ["P4", "P15"]),
    (r"^platform/feed_review_employer", ["P11", "P13"]),
    (r"^platform/eye_review|^test_eye_review", ["P1", "P21", "P23"]),
    (r"^test_gaia_feed_sync", ["P13"]),
    (r"^test_d1_classifier_import", ["P5a", "P13"]),
    (r"^test_platform_taxonomy", ["P1", "P2"]),
    (r"^test_strategies_import|^test_strategies_real_headers", ["P5a", "P7"]),
    (r"^test_strategies_export_bot", ["P16"]),
    (r"^ops/test_redirects|^ops/redirect_rules", ["P7"]),
    (r"^ops/test_probe_incidents", ["P9", "P20"]),
    (r"^ops/test_metrics", ["P8", "P20", "P6"]),
    (r"^ops/test_backup_acceptance", ["P9", "P17"]),
    (r"^ops/test_patches", ["P25"]),
    (r"^smoke/test_stat_markers|^dashboard_dom|^js:(dashboard|live|api)", ["P6"]),
    (r"^smoke/", ["P25"]),
    (r"^test_analytics", ["P24"]),
    (
        r"^test_(build|pages_files|snapshot|scrape|gaps)|^layout|^js:(lib|adbuilder)",
        ["P1"],
    ),
]

PY_DEF = re.compile(r"^\s*(?:async\s+)?def (test_\w+)", re.M)
JS_TEST = re.compile(r"^\s*(?:test|it)\(\s*(['\"`])(.+?)\1", re.M)
SCENARIO = re.compile(r"^\s*Scenario(?: Outline)?:\s*(.+)$", re.M)


def promises_for(key: str) -> list[str]:
    for pat, ps in RULES:
        if re.search(pat, key):
            return ps
    return ["UNMAPPED"]


def covered_by_run_tests(rel: str, text: str) -> bool:
    base = rel.rsplit("/", 1)[-1]
    if base in text:
        return True
    if (
        rel.startswith("platform/")
        and rel.endswith(".test.mjs")
        and "platform/*.test.mjs" in text
    ):
        return True
    for d in ("ops", "smoke"):
        if (
            rel.startswith(d + "/")
            and rel.endswith(".py")
            and base.startswith("test_")
            and re.search(rf"tests/greenjobs_redesign/{d}(\s|$)", text)
        ):
            return True
    return False


def collect() -> list[dict]:
    text = RUN_TESTS.read_text(encoding="utf-8")
    items = []
    for p in sorted(TESTS.rglob("*")):
        if not p.is_file() or "fixtures" in p.parts or "layout_baseline" in p.parts:
            continue
        rel = p.relative_to(TESTS).as_posix()
        if p.name == "conftest.py":
            continue
        if p.suffix == ".py" and p.name.startswith("test_"):
            names = PY_DEF.findall(p.read_text(encoding="utf-8"))
            kind, cmd = "py", f"python3 -m pytest -q tests/greenjobs_redesign/{rel}"
            if rel == "test_build.py":
                cmd = "python3 tests/greenjobs_redesign/test_build.py"
        elif p.name.endswith(".test.mjs"):
            names = [m[1] for m in JS_TEST.findall(p.read_text(encoding="utf-8"))]
            kind, cmd = (
                "node",
                f"node --no-warnings --test tests/greenjobs_redesign/{rel}",
            )
        else:
            continue  # helpers, browser scripts (phone_layout, r4_layout, verify_browser), bdd steps
        if rel == "platform/bdd_runner.test.mjs":
            for f in sorted(FEATURES.glob("*.feature")):
                names += [
                    f"[{f.name}] {s.strip()}"
                    for s in SCENARIO.findall(f.read_text(encoding="utf-8"))
                ]
        items.append(
            dict(
                key=rel,
                kind=kind,
                cmd=cmd,
                names=names,
                path=p,
                covered=covered_by_run_tests(rel, text),
            )
        )
    for f in sorted(JS_SRC.glob("*.test.js")):
        rel = f"js:{f.stem.replace('.test', '')}"
        covered = f.name in text
        names = [m[1] for m in JS_TEST.findall(f.read_text(encoding="utf-8"))]
        items.append(
            dict(
                key=rel,
                kind="nodejs",
                cmd=f"cd deliverables/greenjobs_redesign_2026-09-22/src/js && node --test {f.name}",
                names=names,
                path=f,
                covered=covered,
                outside=True,
            )
        )
    return items


def run(cmd: str, cwd: Path) -> tuple[int, str]:
    r = subprocess.run(
        cmd, shell=True, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800
    )
    return r.returncode, (r.stdout + "\n" + r.stderr)


def result_of(item: dict) -> str:
    if not item["covered"]:
        return "not in run_tests.sh (not run)"
    cwd = ROOT
    cmd = item["cmd"]
    if item["kind"] == "nodejs":
        cwd = JS_SRC
        cmd = f"node --test {item['path'].name}"
    code, out = run(cmd, cwd)
    if item["kind"] == "py" and item["key"] != "test_build.py":
        m = re.findall(r"(\d+) (passed|failed|error|skipped)", out)
        summary = ", ".join(f"{n} {w}" for n, w in m) or "no summary"
    elif item["key"] == "test_build.py":
        m = re.search(r"Unit\+Integration[^\n]*", out)
        summary = m.group(0).strip() if m else "no summary"
    else:
        p = re.search(r"^# pass (\d+)", out, re.M)
        f = re.search(r"^# fail (\d+)", out, re.M)
        summary = (
            f"{p.group(1) if p else '?'} passed, {f.group(1) if f else '?'} failed"
        )
    return f"{'PASS' if code == 0 else 'FAIL'} ({summary})"


def render(items: list[dict], results: dict, suite: str, stamp: str) -> str:
    total = sum(len(i["names"]) for i in items)
    lines = [
        "# GreenJobs test register",
        "",
        f"Generated by `execution/gtm_client_workflows/greenjobs_redesign/ops/test_register.py` on {stamp}. "
        "Do not edit by hand; re-run the script (command at the end).",
        "",
        f"- Tests listed: **{total}** across **{len(items)}** test files "
        f"({sum(1 for i in items if i['covered'])} are part of `run_tests.sh`).",
        f"- Whole suite: `bash deliverables/greenjobs_migration_2026-11-06/build/run_tests.sh` - last run: **{suite}**.",
        "- Counts in the result column are the runner's own totals for that file (a pytest file counts parametrised cases; "
        "the names below are the test functions found in the source). The BDD scenarios run through `platform/bdd_runner.test.mjs`.",
        "- Files under `tests/greenjobs_redesign/` that are not in `run_tests.sh` need a browser or are scratch checks; "
        "they are listed but not run by the register.",
        "",
    ]
    groups: dict[str, list[dict]] = OrderedDict((k, []) for k in PROMISE_TITLES)
    for it in items:
        groups[promises_for(it["key"])[0]].append(it)
    lines += [
        "## Summary by promise",
        "",
        "| Promise | What it covers | Test files | Tests |",
        "|---|---|---|---|",
    ]
    for k, title in PROMISE_TITLES.items():
        g = groups[k]
        lines.append(
            f"| {k} | {title} | {len(g)} | {sum(len(i['names']) for i in g)} |"
        )
    lines += [
        "",
        "Primary promise = first in a file's promise list; a file that proves several promises says so below. "
        "Promise numbers are those of `deliverables/engagement_record_2026-11-20/RECORD.md`. "
        "No test exists for: P5b, P10, P12 (config only), P14, P19, P22, P26, P27, P28, P29 (process or phase 2).",
        "",
    ]
    for k, title in PROMISE_TITLES.items():
        g = groups[k]
        if not g:
            continue
        lines += [f"## {k}: {title}", ""]
        for it in g:
            ps = ", ".join(promises_for(it["key"]))
            rel = it["path"].relative_to(ROOT).as_posix()
            lines += [
                f"### `{rel}`",
                "",
                f"- Promises: {ps}",
                f"- Run: `{it['cmd']}`",
                f"- In `run_tests.sh`: {'yes' if it['covered'] else 'no'}",
                f"- Last run: {results.get(it['key'], 'not run (list only)')}",
                f"- Tests ({len(it['names'])}):",
            ]
            lines += [f"  - {n}" for n in it["names"]] or [
                "  - (none found by the scanner)"
            ]
            lines.append("")
    lines += [
        "## Regenerate",
        "",
        "```",
        "python3 execution/gtm_client_workflows/greenjobs_redesign/ops/test_register.py --run \\",
        "  --out deliverables/greenjobs_migration_2026-11-06/handover/TEST_REGISTER.md",
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--run",
        action="store_true",
        help="run run_tests.sh and every covered file, record results",
    )
    ap.add_argument("--out", help="write the register here (default stdout)")
    ap.add_argument("--date", default=date.today().isoformat())
    a = ap.parse_args()
    (ROOT / ".tmp").mkdir(exist_ok=True)
    items = collect()
    results, suite = {}, "not run (list only)"
    if a.run:
        code, out = run(f"bash {RUN_TESTS.relative_to(ROOT).as_posix()}", ROOT)
        tail = [l for l in out.strip().splitlines() if l.strip()][-1:] or [""]
        suite = f"{'PASS' if code == 0 else 'FAIL'} (exit {code}, last line: {tail[0]})"
        for it in items:
            results[it["key"]] = result_of(it)
    md = render(items, results, suite, a.date)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(md, encoding="utf-8")
        print(
            f"wrote {a.out}: {sum(len(i['names']) for i in items)} tests in {len(items)} files; suite {suite}"
        )
    else:
        sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
