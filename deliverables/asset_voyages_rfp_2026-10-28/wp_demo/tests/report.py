"""Builds the gate-by-gate Markdown table from .tmp/results.json (Playwright JSON reporter)."""
import json
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
data = json.loads((root / ".tmp" / "results.json").read_text())
GATES = ["S1-F1", "S1-F2", "S1-F3", "S1-E1", "S1-E2", "S1-H1", "S1-H2",
         "S2-F1", "S2-F2", "S2-F3", "S2-F4", "S2-F5", "S2-F6", "S2-E1", "S2-E2", "S2-H1",
         "S3-F1", "S3-F2", "S3-F3", "S3-F4", "S3-E1", "S3-H1", "S3-H2", "S3-H3",
         "S4-F1", "S4-F2", "S4-F3", "S4-F4", "S4-F5", "S4-F6", "S4-E1", "S4-H1",
         "S5-F1", "S5-F2", "S5-F3", "S5-F4", "S5-F5", "S5-E1", "S5-H1", "S5-L1", "S5-L2",
         "X1", "X2", "X3", "X4"]
gates = {g: [] for g in GATES}
tests = []


def walk(suite):
    for spec in suite.get("specs", []):
        for t in spec["tests"]:
            r = t["results"][-1] if t["results"] else {"status": "skipped"}
            notes = {a["type"]: a.get("description") for a in t.get("annotations", []) if a["type"] != "serial"}
            tests.append((spec["title"], r["status"], notes))
    for s in suite.get("suites", []):
        walk(s)


for s in data["suites"]:
    walk(s)
for title, status, notes in tests:
    for g in set(re.findall(r"\b(S\d-[FEHL]\d|X\d)\b", title)):
        gates.setdefault(g, []).append((status, notes))

passed = sum(1 for _, s, _ in tests if s == "passed")
print(f"Tests: **{passed} passed / {len(tests) - passed} failed or not run** out of {len(tests)} (Playwright, Chromium, 1 worker).\n")
print("| Gate | Result | Evidence |\n|---|---|---|")
for g in GATES:
    rs = gates.get(g, [])
    if not rs:
        print(f"| {g} | NOT COVERED | out of scope for the plugin suite |")
        continue
    ok = all(s == "passed" for s, _ in rs)
    ev = "; ".join(f"{k}={v}" for _, n in rs for k, v in n.items())
    print(f"| {g} | {'PASS' if ok else 'FAIL'} | {len(rs)} test(s){'; ' + ev if ev else ''} |")
