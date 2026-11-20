"""GreenJobs weekly update for Keith (Proposal :92): 5 lines, renderer only, never sends.

description: Renders the five lines DECISION.md fixes (red items,
  applications, alerts sent, staff hours, next step) from status.json (red =
  FAIL grades, in the monthly report's plain words) and measures_ie.json +
  measures_uk.json (the object the dashboard reads via /api/stats). A null
  measure prints "not measured yet", never a number; a two-board total is
  printed only when both boards have a value. The monthly report is
  monthly_report.py; both are owed (engagement record P8). The draft is outward
  text: it goes through /redteam before a person sends it.
inputs: --next-step TEXT [--status-dir DIR] [--out FILE]
outputs: the 5 lines on stdout, or written to --out; no network, no send path
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as C  # noqa: E402
from monthly_report import NM, PLAIN  # noqa: E402


def both(ms: dict[str, dict[str, Any]], key: str) -> int | None:
    vals = [ms[s]["measures"].get(key) for s in ("ie", "uk")]
    return None if any(v is None for v in vals) else sum(vals)


def render(
    status: dict[str, Any], ms: dict[str, dict[str, Any]], next_step: str
) -> str:
    if not next_step.strip():
        raise ValueError("next step is required")
    red = [
        PLAIN[m["id"]]
        for m in status["metrics"]
        if m["grade"] == "FAIL" and m["id"] in PLAIN
    ]
    apps, sent = both(ms, "applications_7d"), both(ms, "alerts_sent_7d")
    mins = ms["uk"]["measures"].get("staff_minutes_month")
    lines = [
        f"Red items: {'; '.join(red) if red else 'none'}",
        f"Applications this week: {NM if apps is None else apps}",
        f"Alerts sent this week: {NM if sent is None else sent}",
        f"Staff hours this month: {NM if mins is None else round(mins / 60, 1)}",
        f"Next step: {next_step.strip()}",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--status-dir", type=Path, default=C.STATE_DIR / "status")
    ap.add_argument("--next-step", required=True)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    status = C.read_json(a.status_dir / "status.json")
    ms = {s: C.read_json(a.status_dir / f"measures_{s}.json") for s in ("ie", "uk")}
    if not status or not all(ms.values()):
        print("FAIL  run metrics.py first (status.json / measures_*.json missing)")
        return 1
    text = render(status, ms, a.next_step)
    if a.out:
        a.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
