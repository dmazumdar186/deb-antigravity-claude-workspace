"""GreenJobs post-switch acceptance: grade every acceptance-list item once a day for 10 working days (P17).

description: Reads acceptance_list.json and grades each item for one date
  from real evidence only: the day's status.json (metric items), the last 24 h
  of the probe log (probe items), measures_<site>.json (measure items) and the
  operator's dated acceptance_evidence.json entries (evidence items: a test
  application received, a job posted/edited/closed, ...). Missing evidence is
  UNMEASURED, never PASS. Writes the day into acceptance_history.json keyed by
  date (a re-run the same day replaces that day's entry; earlier days are
  never changed). Outside the 10-working-day window it does nothing.
inputs: [--date YYYY-MM-DD] [--list FILE] [--state-dir DIR] [--status-dir DIR] [--evidence FILE] [--force]
  acceptance_evidence.json: {"A3": {"2026-12-03": {"ok": true, "note": "job 123 posted, edited, closed by Rashieda"}}}
outputs: <state>/acceptance_history.json; stdout day verdict; exit 1 when any item FAILs
"""

from __future__ import annotations

import argparse
import operator
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as C  # noqa: E402

LIST = Path(__file__).resolve().parent / "acceptance_list.json"
OPS = {">": operator.gt, ">=": operator.ge, "==": operator.eq, "<=": operator.le}


def window(start: str, n: int) -> list[str]:
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def grade_item(
    item: dict[str, Any],
    day: str,
    status: dict[str, Any] | None,
    probes: list[dict[str, Any]],
    measures: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    c = item["check"]
    t = c["type"]
    if t == "metric":
        if not status or str(status.get("generated_at", ""))[:10] != day:
            return {"grade": "UNMEASURED", "why": "no status.json generated that day"}
        m = next((m for m in status["metrics"] if m["id"] == c["metric"]), None)
        if not m or m["grade"] == "UNMEASURED":
            return {"grade": "UNMEASURED", "why": f"{c['metric']} not measured"}
        return {
            "grade": "PASS" if m["grade"] in c["accept"] else "FAIL",
            "why": f"{m['id']} {m['grade']}: {m['display']}",
        }
    if t == "probe":
        end = datetime.fromisoformat(day).replace(tzinfo=timezone.utc) + timedelta(
            days=1
        )
        rows = [
            r
            for r in probes
            if r.get("kind") == c["kind"]
            and r.get("scope", C.scope_of(r["target"])) == "core"
            and (d := C.parse_iso(r.get("at")))
            and end - timedelta(days=1) <= d < end
        ]
        if not rows:
            return {"grade": "UNMEASURED", "why": f"no {c['kind']} probe rows that day"}
        v = sum(r["ok"] is True for r in rows) / len(rows)
        return {
            "grade": "PASS" if v >= c["min_ok"] else "FAIL",
            "why": f"{v:.3%} of {len(rows)} checks ok",
        }
    if t == "measure":
        ms = measures.get(c["site"])
        v = (ms or {}).get("measures", {}).get(c["key"])
        if v is None or str((ms or {}).get("as_of", ""))[:10] != day:
            return {
                "grade": "UNMEASURED",
                "why": f"{c['site']} {c['key']} not measured that day",
            }
        return {
            "grade": "PASS" if OPS[c["op"]](v, c["value"]) else "FAIL",
            "why": f"{c['key']} = {v}",
        }
    if t == "evidence":
        e = (evidence.get(item["id"]) or {}).get(day)
        if (
            not e
            or not isinstance(e.get("ok"), bool)
            or not str(e.get("note") or "").strip()
        ):
            return {"grade": "UNMEASURED", "why": "no dated evidence entry with a note"}
        return {"grade": "PASS" if e["ok"] else "FAIL", "why": e["note"]}
    raise ValueError(f"unknown check type {t}")


def run(
    day: str,
    list_path: Path,
    state: Path,
    status_dir: Path,
    evidence_path: Path,
    force: bool = False,
) -> dict[str, Any] | None:
    spec = C.read_json(list_path)
    days = window(spec["start"], spec["working_days"])
    if day not in days and not force:
        return None
    status = C.read_json(status_dir / "status.json")
    measures = {s: C.read_json(status_dir / f"measures_{s}.json") for s in C.BOARDS}
    probes = C.read_jsonl(state / "probe_log.jsonl")
    evidence = C.read_json(evidence_path, {}) or {}
    items = {
        it["id"]: {
            "text": it["text"],
            **grade_item(it, day, status, probes, measures, evidence),
        }
        for it in spec["items"]
    }
    grades = [v["grade"] for v in items.values()]
    verdict = (
        "FAIL"
        if "FAIL" in grades
        else "INCOMPLETE" if "UNMEASURED" in grades else "ACCEPTED"
    )
    entry = {
        "day": days.index(day) + 1 if day in days else None,
        "of": len(days),
        "checked_at": C.now_iso(),
        "verdict": verdict,
        "items": items,
    }
    path = state / "acceptance_history.json"
    hist = C.read_json(path, {}) or {}
    hist[day] = entry
    C.write_json(path, dict(sorted(hist.items())))
    return entry


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--date", default=C.now_iso()[:10])
    ap.add_argument("--list", type=Path, default=LIST)
    ap.add_argument("--state-dir", type=Path, default=C.STATE_DIR)
    ap.add_argument("--status-dir", type=Path, default=C.STATE_DIR / "status")
    ap.add_argument(
        "--evidence", type=Path, default=C.STATE_DIR / "acceptance_evidence.json"
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="grade a date outside the 10-day window (rehearsal)",
    )
    a = ap.parse_args(argv)
    e = run(a.date, a.list, a.state_dir, a.status_dir, a.evidence, a.force)
    if e is None:
        print(f"{a.date} is outside the acceptance window; nothing done")
        return 0
    print(f"{a.date} day {e['day']}/{e['of']}: {e['verdict']}")
    for k, v in e["items"].items():
        print(f"  {v['grade']:<10} {k} {v['text']} ({v['why']})")
    return 1 if e["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
