"""GreenJobs monthly report for Keith (maintenance service, P8): renderer only, never sends.

description: Renders the promised monthly report for one calendar month:
  uptime of both boards, traffic, applications, posting routes (console,
  Gaia feed, import) and what changed, plus any red items from the latest
  status.json. Every figure comes from a real input (probe log, D1 export,
  the month's traffic file); a missing one prints "not measured yet", never
  a number. A partial month of probes says so. "What changed" is written by
  the operator (--changes FILE, one item per line). The text is outward: it
  goes through /redteam before it is sent by a person.
inputs: --month YYYY-MM (default: last month) --changes FILE [--inputs DIR] [--state-dir DIR] [--status-dir DIR] [--out FILE]
  traffic: <inputs>/traffic_<YYYY-MM>.json {"sessions": n, "organic_clicks": n, "source": "GA4 + Search Console"}
outputs: the report on stdout, or written to --out; no network, no send path
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as C  # noqa: E402

NM = "not measured yet"
PLAIN = {  # red items in plain words for a non-technical reader
    "M1": "imported data does not match the Strategies exports",
    "M2": "some old links do not reach a page",
    "M3": "a board was down more than allowed",
    "M4": "email settings or the test mail failed on a board domain",
    "M5": "new jobs take over an hour to appear",
    "M6": "Gaia jobs are still being posted by hand",
    "M7": "staff time is over 8 hours a month",
    "M8": "some applications did not reach the employer",
    "M9": "an alert went to someone without consent (sends stopped)",
    "M10": "some job pages are not eligible for Google for Jobs",
    "M11": "search traffic is below 75% of before",
    "B1": "the daily backup is more than two days old",
    "B2": "the quarterly restore test is overdue or failed",
    "SLA1": "uptime this month is below the agreed 99.9%",
    "SLA2": "a problem was not answered within the agreed response time",
}
ROUTES = {
    "console": "posted in the console",
    "feed": "arrived by the Gaia feed",
    "strategies": "imported from Strategies",
}


def month_bounds(month: str) -> tuple[datetime, datetime]:
    y, m = (int(x) for x in month.split("-"))
    start = datetime(y, m, 1, tzinfo=timezone.utc)
    end = datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=timezone.utc)
    return start, end


def last_month(now: datetime) -> str:
    y, m = now.year, now.month - 1
    return f"{y - 1}-12" if m == 0 else f"{y}-{m:02d}"


def in_month(ts: Any, start: datetime, end: datetime) -> bool:
    d = C.parse_iso(ts)
    return bool(d and start <= d < end)


def figures(month: str, inputs: Path, state: Path) -> dict[str, Any]:
    start, end = month_bounds(month)
    out: dict[str, Any] = {"month": month}
    probes = [
        r
        for r in C.read_jsonl(state / "probe_log.jsonl")
        if r.get("kind") == "http"
        and C.scope_of(r["target"]) == "core"
        and in_month(r.get("at"), start, end)
    ]
    if probes:
        days = {r["at"][:10] for r in probes}
        out["uptime"] = {
            "pct": round(100 * sum(r["ok"] is True for r in probes) / len(probes), 2),
            "days": len(days),
            "month_days": (end - start).days,
        }
    else:
        out["uptime"] = None
    t = C.read_json(inputs / f"traffic_{month}.json")
    out["traffic"] = (
        {k: t.get(k) for k in ("sessions", "organic_clicks", "source")} if t else None
    )
    d1 = C.read_json(inputs / "d1_export.json")
    if d1:
        tables = d1.get("tables", {})
        apps = [
            a
            for a in tables.get("applications", [])
            if a.get("source") == "apply"
            and in_month(a.get("submitted_at"), start, end)
        ]
        out["applications"] = {
            s: sum(a.get("site") == s for a in apps) for s in C.BOARDS
        }
        jobs = [
            j
            for j in tables.get("jobs", [])
            if j.get("status") != "draft"
            and in_month(j.get("posted_at") or j.get("created_at"), start, end)
        ]
        out["routes"] = {
            src: {
                s: sum(j.get("source") == src and j.get("site") == s for j in jobs)
                for s in C.BOARDS
            }
            for src in ROUTES
        }
    else:
        out["applications"] = out["routes"] = None
    # written by the weekly audit / monthly compatibility jobs (deploy/audit_summary.py, compat_check.py)
    out["patches"] = C.read_json(inputs / "patches.json")
    return out


def patch_lines(patches: Any) -> list[str]:
    """Plain-words 'Patches and updates' lines; a missing section or null field reads "not measured yet"."""
    p = patches if isinstance(patches, dict) else {}
    au, cp = p.get("audit") or {}, p.get("compat") or {}
    n, q = au.get("npm_high_critical"), au.get("pip_advisories")
    if au.get("at") is None or n is None or q is None:
        sec = f"- Security check of the tools we use: {NM}"
    elif n + q:
        sec = f"- Security check of the tools we use ({au['at']}): {n + q} known issue(s) found, being fixed"
    else:
        sec = f"- Security check of the tools we use ({au['at']}): no known serious issues"
    age, stale = cp.get("age_days"), cp.get("stale")
    if age is None or stale is None:
        plat = f"- Cloudflare platform settings: {NM}"
    else:
        plat = "- Cloudflare platform settings: " + (
            "due for a routine update" if stale else "up to date"
        ) + f" (checked {cp.get('at')})"
    return [sec, plat]


def render(f: dict[str, Any], status: dict[str, Any] | None, changes: list[str]) -> str:
    changes = [c.strip() for c in changes if c.strip()]
    if not changes:
        raise ValueError("'what changed' is required (one item per line)")
    up = f["uptime"]
    if up is None:
        up_line = NM
    else:
        up_line = f"{up['pct']}% of checks answered on both boards"
        if up["days"] < up["month_days"]:
            up_line += f" (measured on {up['days']} of {up['month_days']} days)"
    tr = f["traffic"]
    tr_line = (
        NM
        if not tr or tr.get("sessions") is None
        else (
            f"{tr['sessions']} visits"
            + (
                f", {tr['organic_clicks']} from Google search"
                if tr.get("organic_clicks") is not None
                else ""
            )
            + (f" ({tr['source']})" if tr.get("source") else "")
        )
    )
    ap = f["applications"]
    ap_line = (
        NM
        if ap is None
        else f"{ap['ie'] + ap['uk']} (greenjobs.ie {ap['ie']}, greenjobs.co.uk {ap['uk']})"
    )
    rt = f["routes"]
    if rt is None:
        rt_lines = [f"- {NM}"]
    else:
        rt_lines = [
            f"- {sum(v.values())} {label}"
            for src, label in ROUTES.items()
            for v in [rt[src]]
        ]
    red = [
        PLAIN.get(m["id"], m["name"])
        for m in (status or {}).get("metrics", [])
        if m["grade"] == "FAIL" and m["id"] in PLAIN
    ]
    lines = [
        f"GreenJobs monthly report: {f['month']}",
        "",
        f"Uptime: {up_line}",
        f"Traffic: {tr_line}",
        f"Applications: {ap_line}",
        "Jobs by posting route:",
        *rt_lines,
        (
            f"Needs attention: {'; '.join(red) if red else 'nothing'}"
            if status
            else f"Needs attention: {NM}"
        ),
        "Patches and updates:",
        *patch_lines(f.get("patches")),
        "What changed:",
        *[f"- {c}" for c in changes],
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--month", default=last_month(datetime.now(timezone.utc)))
    ap.add_argument("--changes", type=Path, required=True)
    ap.add_argument("--inputs", type=Path, default=C.STATE_DIR / "inputs")
    ap.add_argument("--state-dir", type=Path, default=C.STATE_DIR)
    ap.add_argument("--status-dir", type=Path, default=C.STATE_DIR / "status")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    text = render(
        figures(a.month, a.inputs, a.state_dir),
        C.read_json(a.status_dir / "status.json"),
        a.changes.read_text(encoding="utf-8").splitlines(),
    )
    if a.out:
        a.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
