"""GreenJobs metrics runner: M1-M11 + CPO/CDO metrics, graded, plus the client-facing measures objects.

description: Computes every metric in SYNTHESIS §4 (M1-M11) and the CPO/CDO
  additions in DECISION.md from whatever inputs exist (D1 export, probe log,
  DNS watcher state, redirect crawl, operator-supplied JSON). A metric whose
  input is missing is UNMEASURED with value null, never a number; a metric
  with no threshold in §4 is INFO. Grades PASS/WARN/FAIL use the §4 bounds.
  Writes status.json + status.html (operator-only technical health page) and
  measures_ie.json / measures_uk.json (client-facing; shape in
  measures.schema.json; served by GET /api/stats?site=, null renders "coming").
  Any FAIL drafts one operator alert per metric per day (outbox; live with --send)
  and exits 1.
inputs: [--inputs DIR] [--state-dir DIR] [--out DIR] [--now ISO] [--send]
  files in --inputs (all optional): d1_export.json, reconciliation.json, mail_test.json,
  visibility_probe.jsonl, staff_checkin.json, link_check.json, alert_sends.jsonl,
  jsonld_check.json, search_console.json, gdpr.json (shapes in the directive section "Ops")
  files in --state-dir: probe_log.jsonl, dns_state.json, redirect_crawl.json
outputs: <out>/status.json, <out>/status.html, <out>/measures_ie.json, <out>/measures_uk.json;
  <state>/outbox.jsonl (alerts); exit 0, or 1 when any metric FAILs
"""

from __future__ import annotations

import argparse
import html
import math
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as C  # noqa: E402
from common import build_site as B  # noqa: E402
from notify import Notifier  # noqa: E402

PASS, WARN, FAIL, UNMEASURED, INFO = "PASS", "WARN", "FAIL", "UNMEASURED", "INFO"
RANK = {FAIL: 0, WARN: 1, UNMEASURED: 2, INFO: 3, PASS: 4}
GAIA = next(
    n for n in B.AGENCY_NAMES if "gaia" in n
)  # "gaia talent", the build's own agency vocabulary
M7_BASELINE_NOTE = (
    "baseline 14 h/month is today's estimate, not a measurement (SYNTHESIS §4 M7)"
)
MEASURE_KEYS = (
    "live_jobs",
    "jobs_posted_30d",
    "applications_7d",
    "applications_30d",
    "applications_per_job_30d",
    "alerts_sent_7d",
    "alerts_opened_7d",
    "live_duplicates",
    "expired_still_showing",
    "staff_minutes_month",
)


def metric(
    mid: str, name: str, value: Any, grade: str, detail: str, display: str | None = None
) -> dict[str, Any]:
    """The one constructor. Guard: a null value can only be UNMEASURED (never PASS/WARN/FAIL/INFO)."""
    if value is None:
        grade = UNMEASURED
    if display is None:
        display = (
            "not measured"
            if value is None
            else (
                f"{value:.2%}"
                if isinstance(value, float) and value <= 1
                else str(value)
            )
        )
    return {
        "id": mid,
        "name": name,
        "value": value,
        "display": display,
        "grade": grade,
        "detail": detail,
    }


def hi(v: float, pass_: float, warn: float) -> str:
    return PASS if v >= pass_ else WARN if v >= warn else FAIL


def lo(v: float, pass_: float, warn: float) -> str:
    return PASS if v <= pass_ else WARN if v <= warn else FAIL


def ratio(n: Any, d: Any) -> float | None:
    try:
        n, d = float(n), float(d)
    except (TypeError, ValueError):
        return None
    return n / d if d > 0 and n >= 0 else None


class Inputs:
    def __init__(self, inputs: Path, state: Path, now: datetime):
        self.dir, self.state, self.now = Path(inputs), Path(state), now
        self.d1 = C.read_json(self.dir / "d1_export.json")
        t = (self.d1 or {}).get("tables", {}) if self.d1 else {}
        self.jobs = t.get("jobs") if self.d1 else None
        self.employers = {e["id"]: e for e in t.get("employers", [])} if self.d1 else {}
        self.apps = t.get("applications") if self.d1 else None

    def j(self, name: str) -> Any:
        return C.read_json(self.dir / name)

    def jl(self, name: str, base: Path | None = None) -> list[dict[str, Any]] | None:
        p = (base or self.dir) / name
        return C.read_jsonl(p) if p.exists() else None

    def within(self, ts: Any, days: float) -> bool:
        d = C.parse_iso(ts)
        return bool(d and self.now - timedelta(days=days) <= d <= self.now)


# ---------------------------------------------------------------- M1-M11


def m1(i: Inputs) -> dict[str, Any]:
    r = i.j("reconciliation.json")
    name = "Migration fidelity (imported ÷ exported, 50-row field diff)"
    if not r:
        return metric(
            "M1",
            name,
            None,
            UNMEASURED,
            "needs reconciliation.json (counts per export + sample field diffs)",
        )
    ratios = {
        k: ratio(r.get("imported", {}).get(k), v)
        for k, v in r.get("exported", {}).items()
    }
    if (
        not ratios
        or any(v is None for v in ratios.values())
        or r.get("sample_field_diffs") is None
    ):
        return metric("M1", name, None, UNMEASURED, "reconciliation.json incomplete")
    v = min(ratios.values())
    diffs = int(r["sample_field_diffs"])
    g = PASS if v >= 1 and diffs == 0 else WARN if v >= 0.99 else FAIL
    return metric(
        "M1", name, round(v, 4), g, f"per export {ratios}; field diffs {diffs}"
    )


def m2(i: Inputs) -> dict[str, Any]:
    r = C.read_json(i.state / "redirect_crawl.json")
    cov = C.read_json(C.GENERATED / "redirect_coverage.json") or {}
    pre = (
        f"static pre-check: {cov.get('served_pct')}% served, {cov.get('specific_match_pct')}% specific"
        if cov
        else "no static pre-check"
    )
    name = "Redirect coverage (old URLs ending on 200 in ≤2 hops)"
    v = ratio((r or {}).get("ok_le_2_hops"), (r or {}).get("checked"))
    if v is None:
        return metric(
            "M2",
            name,
            None,
            UNMEASURED,
            f"needs the live crawl (redirects.py crawl --live); {pre}",
        )
    return metric(
        "M2",
        name,
        round(v, 4),
        hi(v, 0.99, 0.95),
        f"{r['ok_le_2_hops']}/{r['checked']} at {r.get('at')}; {pre}",
    )


def m3(i: Inputs) -> dict[str, Any]:
    name = "Availability, both boards, apex + www (7 days)"
    rows = [
        r
        for r in (i.jl("probe_log.jsonl", i.state) or [])
        if r.get("kind") == "http" and i.within(r.get("at"), 7) and C.scope_of(r["target"]) == "core"
    ]
    if not rows:
        return metric(
            "M3",
            name,
            None,
            UNMEASURED,
            "no probe rows in the last 7 days (uptime_probe.py --live every 5 min)",
        )
    stamps = sorted(C.parse_iso(r["at"]) for r in rows)
    span_h = (stamps[-1] - stamps[0]).total_seconds() / 3600
    v = round(sum(r["ok"] is True for r in rows) / len(rows), 4)
    bad = sorted({r["target"] for r in rows if r["ok"] is not True})
    detail = f"{len(rows)} checks over {span_h:.1f} h; failing hosts: {', '.join(bad) or 'none'}"
    if span_h < 24:
        return metric(
            "M3",
            name,
            v,
            UNMEASURED,
            detail + " (graded once 24 h of probes exist)",
            display=f"{v:.2%} (partial)",
        )
    return metric("M3", name, v, hi(v, 0.995, 0.99), detail)


def m4(i: Inputs) -> dict[str, Any]:
    name = "Email intact (MX + SPF = inventory; test mail arrives)"
    rows = [
        r
        for r in (i.jl("probe_log.jsonl", i.state) or [])
        if r.get("kind") == "mail" and i.within(r.get("at"), 1) and C.scope_of(r["target"]) == "core"
    ]
    st = C.read_json(i.state / "dns_state.json") or {}
    drift = sorted(d for d, s in st.get("domains", {}).items() if s.get("last_drift") and C.scope_of(d) == "core")
    bad = sorted({r["target"] for r in rows if r.get("ok") is False}) + drift
    if bad:
        return metric(
            "M4",
            name,
            0,
            FAIL,
            f"mismatch on {', '.join(sorted(set(bad)))}",
            display="mismatch",
        )
    if not rows and not st:
        return metric(
            "M4", name, None, UNMEASURED, "no DNS mail checks in the last 24 h"
        )
    t = i.j("mail_test.json")
    if not t or not t.get("sent"):
        return metric(
            "M4",
            name,
            None,
            UNMEASURED,
            "DNS matches the inventory; test-mail half not measured (mail_test.json)",
        )
    ok = int(t.get("arrived", 0)) == int(t["sent"])
    return metric(
        "M4",
        name,
        1 if ok else 0,
        PASS if ok else FAIL,
        f"DNS match; test mail {t.get('arrived')}/{t['sent']} arrived",
        display="all match" if ok else "test mail missing",
    )


def net1(i: Inputs) -> dict[str, Any]:
    """The 8 network domains: optional scope (quoted separately), never part of the overall gate."""
    name = "Network domains (optional, quoted separately): forwards up and mail intact, 7 days"
    rows = [r for r in (i.jl("probe_log.jsonl", i.state) or []) if i.within(r.get("at"), 7) and C.scope_of(r["target"]) == "optional"]
    if not rows:
        return metric("NET1", name, None, INFO, "no probe rows for the network domains")
    v = round(sum(r["ok"] is True for r in rows) / len(rows), 4)
    bad = sorted({f"{r['target']} ({r['kind']})" for r in rows if r["ok"] is not True})
    return metric("NET1", name, v, INFO, f"{len(rows)} checks; failing: {', '.join(bad) or 'none'}")


BACKUP_PASS_H, BACKUP_WARN_H = 26, 48  # daily backup promised (P8): one missed night is WARN, two FAIL
DRILL_MAX_DAYS = 92  # restore drill promised every quarter


def b1(i: Inputs) -> dict[str, Any]:
    name = "Backup age: last good daily D1 export in R2 (hours)"
    rows = [r for r in (i.jl("backup_log.jsonl", i.state) or []) if r.get("ok") is True and r.get("mode") == "live"]
    last = max((C.parse_iso(r["at"]) for r in rows), default=None)
    if not last:
        return metric("B1", name, None, UNMEASURED, "no live backup recorded (d1_backup.py --live, daily)")
    h = round((i.now - last).total_seconds() / 3600, 1)
    return metric("B1", name, h, lo(h, BACKUP_PASS_H, BACKUP_WARN_H), f"last {last.isoformat()}", display=f"{h} h")


def b2(i: Inputs) -> dict[str, Any]:
    name = "Restore drill: last drill passed within a quarter"
    rows = [r for r in (i.jl("restore_drill_log.jsonl", i.state) or []) if r.get("mode") == "live"]
    if not rows:
        return metric("B2", name, None, UNMEASURED, "no live restore drill recorded (d1_restore_drill.py --live)")
    last = max(rows, key=lambda r: r["at"])
    age = (i.now - C.parse_iso(last["at"])).days
    ok = last.get("ok") is True and age <= DRILL_MAX_DAYS
    return metric("B2", name, age, PASS if ok else FAIL, f"last drill {last['at']}: {'passed' if last.get('ok') else 'FAILED'}; {last.get('detail', '')}",
                  display=f"{age} days ago")


def sla1(i: Inputs) -> dict[str, Any]:
    """P20: 99.9% uptime per calendar month (boards apex + www and the sev-1 posting checks)."""
    import incidents

    name = "Service level: uptime this month (target 99.9%)"
    start = i.now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rows = [r for r in (i.jl("probe_log.jsonl", i.state) or [])
            if r.get("kind") in ("http", "posting") and r.get("scope", C.scope_of(r["target"])) == "core"
            and (d := C.parse_iso(r.get("at"))) and start <= d <= i.now]
    if not rows:
        return metric("SLA1", name, None, UNMEASURED, "no probe rows this month")
    v = round(sum(r["ok"] is True for r in rows) / len(rows), 5)
    span_h = (max(C.parse_iso(r["at"]) for r in rows) - min(C.parse_iso(r["at"]) for r in rows)).total_seconds() / 3600
    detail = f"{len(rows)} checks over {span_h:.1f} h since {start.date().isoformat()}"
    if span_h < 24:
        return metric("SLA1", name, v, UNMEASURED, detail + " (graded once 24 h of probes exist)", display=f"{v:.3%} (partial)")
    return metric("SLA1", name, v, PASS if v >= incidents.UPTIME_TARGET else FAIL, detail, display=f"{v:.3%}")


def sla2(i: Inputs) -> dict[str, Any]:
    """P20: response within 4 h for a posting outage (sev-1), 1 business day otherwise."""
    import incidents

    name = "Service level: incident response this month (sev-1 4 h; others 1 business day)"
    s = incidents.sla(i.state, i.now)
    if s is None:
        return metric("SLA2", name, None, UNMEASURED, "no incident log yet (uptime_probe.py --live creates it)")
    if s["incidents"] == 0:
        return metric("SLA2", name, 1.0, PASS, "no incidents this month", display="no incidents")
    decided = s["met"] + len(s["breached"])
    v = round(s["met"] / decided, 4) if decided else None
    detail = f"{s['incidents']} incidents ({s['sev1']} sev-1): {s['met']} met, {len(s['breached'])} breached {s['breached'] or ''}, {s['pending']} within deadline"
    if v is None:
        return metric("SLA2", name, None, UNMEASURED, detail)
    return metric("SLA2", name, v, PASS if not s["breached"] else FAIL, detail, display=f"{s['met']}/{decided} on time")


def m5(i: Inputs) -> dict[str, Any]:
    name = "Time to live (job created → visible), p90 minutes, 30 days"
    rows = i.jl("visibility_probe.jsonl")
    mins = []
    for r in rows or []:
        a, b = C.parse_iso(r.get("created_at")), C.parse_iso(r.get("visible_at"))
        if a and b and i.within(r.get("created_at"), 30):
            mins.append(max(0.0, (b - a).total_seconds() / 60))
    if not mins:
        return metric(
            "M5",
            name,
            None,
            UNMEASURED,
            "needs visibility_probe.jsonl rows (created_at, visible_at)",
        )
    mins.sort()
    p90 = round(mins[max(0, math.ceil(0.9 * len(mins)) - 1)], 1)
    return metric(
        "M5", name, p90, lo(p90, 15, 60), f"{len(mins)} jobs", display=f"{p90} min"
    )


def _gaia(i: Inputs, job: dict[str, Any]) -> bool:
    e = i.employers.get(job.get("employer_id")) or {}
    return GAIA in str(e.get("name_norm") or e.get("name") or "").lower()


def m6(i: Inputs) -> dict[str, Any]:
    name = "Gaia jobs arriving by feed (not by hand), 30 days"
    if i.jobs is None:
        return metric("M6", name, None, UNMEASURED, "needs d1_export.json")
    g = [
        j
        for j in i.jobs
        if j.get("source") in ("console", "feed")
        and _gaia(i, j)
        and i.within(j.get("created_at"), 30)
    ]
    if not g:
        return metric(
            "M6", name, None, UNMEASURED, "no Gaia jobs created in the last 30 days"
        )
    v = round(sum(j["source"] == "feed" for j in g) / len(g), 4)
    return metric("M6", name, v, hi(v, 0.95, 0.80), f"{len(g)} Gaia jobs")


def staff_minutes(i: Inputs) -> int | None:
    c = i.j("staff_checkin.json")
    if not c or c.get("minutes") is None or c.get("month") != i.now.strftime("%Y-%m"):
        return None
    return int(c["minutes"])


def m7(i: Inputs) -> dict[str, Any]:
    name = "Staff time per month (hours)"
    mins = staff_minutes(i)
    if mins is None:
        return metric(
            "M7",
            name,
            None,
            UNMEASURED,
            f"needs this month's staff_checkin.json; {M7_BASELINE_NOTE}",
        )
    h = round(mins / 60, 1)
    return metric("M7", name, h, lo(h, 4, 8), M7_BASELINE_NOTE, display=f"{h} h")


def m8(i: Inputs) -> dict[str, Any]:
    name = "Apply delivery (email sent ÷ submitted; link mode valid https)"
    parts, notes = [], []
    if i.apps is not None:
        live = [a for a in i.apps if a.get("delivery_status") in ("sent", "failed")]
        if live:
            parts.append(sum(a["delivery_status"] == "sent" for a in live) / len(live))
            notes.append(
                f"email {sum(a['delivery_status'] == 'sent' for a in live)}/{len(live)}"
            )
        else:
            notes.append("no live email deliveries yet (dry_run rows are not counted)")
    lc = i.j("link_check.json")
    v = ratio((lc or {}).get("valid"), (lc or {}).get("checked"))
    if v is not None:
        parts.append(v)
        notes.append(f"links {lc['valid']}/{lc['checked']}")
    if not parts:
        return metric(
            "M8",
            name,
            None,
            UNMEASURED,
            "; ".join(notes) or "needs d1_export.json and/or link_check.json",
        )
    v = round(min(parts), 4)
    return metric("M8", name, v, hi(v, 0.99, 0.97), "; ".join(notes))


def m9(i: Inputs) -> dict[str, Any]:
    name = "Alerts sent to anyone without Marketing=yes"
    rows = i.jl("alert_sends.jsonl")
    if rows is None:
        return metric(
            "M9",
            name,
            None,
            UNMEASURED,
            "needs alert_sends.jsonl (send log joined to consent on CandidatePK)",
        )
    bad = sum(
        r.get("consent_marketing") is not True for r in rows
    )  # unknown consent counts as a breach
    return metric(
        "M9",
        name,
        bad,
        PASS if bad == 0 else FAIL,
        f"{len(rows)} sends checked" + ("; STOP SENDS" if bad else ""),
    )


def m10(i: Inputs) -> dict[str, Any]:
    name = "Job pages with valid JobPosting JSON-LD"
    r = i.j("jsonld_check.json")
    v = ratio((r or {}).get("valid"), (r or {}).get("checked"))
    if v is None:
        return metric(
            "M10",
            name,
            None,
            UNMEASURED,
            "needs jsonld_check.json from the schema validator",
        )
    return metric(
        "M10", name, round(v, 4), hi(v, 1.0, 0.95), f"{r['valid']}/{r['checked']}"
    )


def m11(i: Inputs) -> dict[str, Any]:
    name = "Search: indexed pages and organic clicks vs 4 weeks before"
    r = i.j("search_console.json")
    if not r:
        return metric(
            "M11",
            name,
            None,
            UNMEASURED,
            "needs search_console.json (Search Console + GA4)",
        )
    rs = [
        ratio(r.get("current", {}).get(k), r.get("baseline", {}).get(k))
        for k in ("indexed", "clicks")
    ]
    if any(x is None for x in rs):
        return metric("M11", name, None, UNMEASURED, "search_console.json incomplete")
    v = round(min(rs), 4)
    wk = r.get("weeks_since_switch")
    g = hi(v, 0.90, 0.75)
    if g != PASS and isinstance(wk, (int, float)) and wk < 6:
        g = WARN  # the §4 target is "by week 6"
    return metric(
        "M11",
        name,
        v,
        g,
        f"indexed {rs[0]:.0%}, clicks {rs[1]:.0%} of baseline; week {wk}",
    )


# ---------------------------------------------------------------- CPO / CDO (no §4 thresholds: INFO)


def live_jobs(i: Inputs, site: str | None = None) -> list[dict[str, Any]] | None:
    if i.jobs is None:
        return None
    return [
        j
        for j in i.jobs
        if j.get("status") == "live" and (site is None or j.get("site") == site)
    ]


def expired_showing(i: Inputs, site: str | None = None) -> int | None:
    lj = live_jobs(i, site)
    if lj is None:
        return None
    today = i.now.date().isoformat()
    return sum(
        1 for j in lj if j.get("closing_at") and str(j["closing_at"])[:10] < today
    )


def _title_key(j: dict[str, Any]) -> tuple[str, str, str]:
    t = re.sub(r"[^a-z0-9]+", " ", str(j.get("title") or "").lower()).strip()
    return (j.get("site"), str(j.get("employer_id") or ""), t)


def duplicates(i: Inputs, site: str | None = None) -> int | None:
    lj = live_jobs(i, site)
    if lj is None:
        return None
    seen: dict[tuple, int] = {}
    for j in lj:
        k = _title_key(j)
        seen[k] = seen.get(k, 0) + 1
    return sum(n - 1 for n in seen.values() if n > 1)


def apps_in(i: Inputs, days: int, site: str | None = None) -> int | None:
    if i.apps is None:
        return None
    return sum(
        1
        for a in i.apps
        if a.get("source") == "apply"
        and (site is None or a.get("site") == site)
        and i.within(a.get("submitted_at"), days)
    )


def alerts(
    i: Inputs, days: int, site: str | None = None, opened: bool = False
) -> int | None:
    rows = i.jl("alert_sends.jsonl")
    if rows is None:
        return None
    rows = [
        r
        for r in rows
        if (site is None or r.get("site") == site) and i.within(r.get("sent_at"), days)
    ]
    return sum(1 for r in rows if r.get("opened_at")) if opened else len(rows)


def cpo_cdo(i: Inputs) -> list[dict[str, Any]]:
    out = []
    a30, lj = apps_in(i, 30), live_jobs(i)
    apj = round(a30 / len(lj), 2) if a30 is not None and lj else None
    out.append(
        metric(
            "CPO1",
            "Applications per live job (30 days)",
            apj,
            INFO,
            "applications ÷ live jobs", display=None if apj is None else str(apj),
        )
    )
    s7, o7 = alerts(i, 7), alerts(i, 7, opened=True)
    out.append(
        metric(
            "CPO2",
            "Alerts sent / opened (7 days)",
            None if s7 is None else s7,
            INFO,
            "from alert_sends.jsonl",
            display=None if s7 is None else f"{s7} sent / {o7} opened",
        )
    )
    out.append(
        metric(
            "CPO3",
            "Expired jobs still showing",
            expired_showing(i),
            INFO,
            "status live and closing date passed",
        )
    )
    out.append(
        metric(
            "CPO4",
            "Live duplicates",
            duplicates(i),
            INFO,
            "same board, employer and title",
        )
    )
    g = i.j("gdpr.json") or {}
    r = i.j("reconciliation.json") or {}
    fm = ratio(r.get("fields_migrated"), r.get("fields_exported"))
    out.append(
        metric(
            "CDO1",
            "Fields migrated ÷ fields exported (minimisation)",
            None if fm is None else round(fm, 4),
            INFO,
            "lower is better: fields deliberately left behind",
        )
    )
    reqs = g.get("erasure_requests")
    if reqs is None:
        out.append(
            metric(
                "CDO2",
                "Erasure requests closed within 30 days",
                None,
                INFO,
                "needs gdpr.json",
            )
        )
    else:
        done = 0
        for q in reqs:
            a, b = C.parse_iso(q.get("received_at")), C.parse_iso(q.get("closed_at"))
            done += bool(a and b and (b - a).days <= 30)
        out.append(
            metric(
                "CDO2",
                "Erasure requests closed within 30 days",
                f"{done}/{len(reqs)}",
                INFO,
                "GDPR one-month limit",
            )
        )
    out.append(
        metric(
            "CDO3",
            "Archive access log entries",
            g.get("archive_access_entries"),
            INFO,
            "every read of the legacy archive",
        )
    )
    uc = ratio(g.get("unsubscribes_carried"), g.get("unsubscribes_exported"))
    out.append(
        metric(
            "CDO4",
            "Unsubscribes carried over",
            None if uc is None else round(uc, 4),
            INFO,
            "carried ÷ exported",
        )
    )
    return out


# ---------------------------------------------------------------- client measures (GET /api/stats?site=)


def measures(i: Inputs, site: str, generated_at: str) -> dict[str, Any]:
    lj = live_jobs(i, site)
    a30 = apps_in(i, 30, site)
    posted = None
    if i.jobs is not None:
        posted = sum(
            1
            for j in i.jobs
            if j.get("site") == site
            and j.get("status") != "draft"
            and j.get("source") in ("console", "feed")
            and i.within(j.get("posted_at") or j.get("created_at"), 30)
        )
    m = {
        "live_jobs": None if lj is None else len(lj),
        "jobs_posted_30d": posted,
        "applications_7d": apps_in(i, 7, site),
        "applications_30d": a30,
        "applications_per_job_30d": (
            round(a30 / len(lj), 2) if a30 is not None and lj else None
        ),
        "alerts_sent_7d": alerts(i, 7, site),
        "alerts_opened_7d": alerts(i, 7, site, opened=True),
        "live_duplicates": duplicates(i, site),
        "expired_still_showing": expired_showing(i, site),
        "staff_minutes_month": staff_minutes(i),
    }
    assert tuple(m) == MEASURE_KEYS
    return {"schema_version": 1, "site": site, "as_of": generated_at, "measures": m}


# ---------------------------------------------------------------- status page


def health(i: Inputs) -> dict[str, Any]:
    st = C.read_json(i.state / "dns_state.json") or {}
    probes = i.jl("probe_log.jsonl", i.state) or []
    last_at = max((r["at"] for r in probes), default=None)
    last = [r for r in probes if r["at"] == last_at]
    cov = C.read_json(C.GENERATED / "redirect_coverage.json") or {}
    return {
        "watcher": {
            "last_run": st.get("last_run"),
            "domains": {
                d: {
                    k: s.get(k)
                    for k in (
                        "status",
                        "on_cloudflare",
                        "mx_ok",
                        "spf_ok",
                        "notified_mode",
                        "fail_streak",
                        "last_drift",
                    )
                }
                for d, s in sorted(st.get("domains", {}).items())
            },
        },
        "probe": {
            "last_run": last_at,
            "ok": sum(r["ok"] is True for r in last),
            "total": len(last),
            "failing": [
                r["target"] + " (" + r["kind"] + ")"
                for r in last
                if r["ok"] is not True
            ],
        },
        "acceptance": (lambda h: {"date": max(h), **{k: h[max(h)][k] for k in ("day", "of", "verdict")}} if h else None)(
            C.read_json(i.state / "acceptance_history.json") or {}),
        "redirects": {
            k: cov.get(k)
            for k in ("old_urls", "served_pct", "specific_match_pct", "live_ids_source")
        }
        | {"leftovers": len(cov.get("leftovers", []))},
    }


def overall(ms: list[dict[str, Any]]) -> str:
    graded = [m["grade"] for m in ms if m["grade"] in (PASS, WARN, FAIL)]
    if FAIL in graded:
        return FAIL
    if WARN in graded:
        return WARN
    if any(m["grade"] == UNMEASURED for m in ms if m["id"][0] in "MBS"):
        return UNMEASURED
    return PASS


CSS = """:root{--bg:#fbfaf7;--fg:#1d2420;--mut:#5d6660;--line:#dcdcd4;--pass:#1f6f3f;--warn:#8a5a00;--fail:#a3261b;--un:#55606a}
@media (prefers-color-scheme:dark){:root{--bg:#141815;--fg:#e9ece8;--mut:#a3aba5;--line:#2c332e;--pass:#6fcf8f;--warn:#f0b54a;--fail:#ff7b6b;--un:#a9b4bd}}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:760px;margin:0 auto;padding:16px}h1{font-size:1.3rem;margin:.2rem 0}h2{font-size:1.05rem;margin:1.4rem 0 .4rem}
.m{border-top:1px solid var(--line);padding:.6rem 0}.m b{display:block}.g{font-weight:700;font-size:.85rem;letter-spacing:.03em}
.PASS{color:var(--pass)}.WARN{color:var(--warn)}.FAIL{color:var(--fail)}.UNMEASURED,.INFO{color:var(--un)}
.d{color:var(--mut);font-size:.9rem;overflow-wrap:anywhere}table{width:100%;border-collapse:collapse;font-size:.9rem}
td,th{text-align:left;padding:.3rem .2rem;border-top:1px solid var(--line);vertical-align:top}"""


def render_html(status: dict[str, Any]) -> str:
    e = html.escape
    rows = "".join(
        f'<div class="m"><span class="g {e(m["grade"])}">{e(m["grade"])}</span> <b>{e(m["id"])} · {e(m["name"])}</b>'
        f'<span>{e(str(m["display"]))}</span><div class="d">{e(m["detail"])}</div></div>'
        for m in status["metrics"]
    )
    w = status["health"]["watcher"]
    wrows = "".join(
        f"<tr><td>{e(d)}{' (optional)' if C.scope_of(d) == 'optional' else ''}</td><td>{e(str(s.get('status')))}</td><td>{'yes' if s.get('on_cloudflare') else 'no'}</td>"
        f"<td class=\"{'PASS' if s.get('mx_ok') and s.get('spf_ok') else 'FAIL' if s.get('mx_ok') is False or s.get('spf_ok') is False else 'UNMEASURED'}\">"
        f"{'ok' if s.get('mx_ok') and s.get('spf_ok') else 'DIFF' if s.get('mx_ok') is False or s.get('spf_ok') is False else '?'}</td>"
        f"<td>{e(str(s.get('notified_mode') or '-'))}</td></tr>"
        for d, s in w["domains"].items()
    )
    p, r = status["health"]["probe"], status["health"]["redirects"]
    acc = status["health"].get("acceptance")
    acc_line = f"{acc['date']}: day {acc['day']} of {acc['of']}: {acc['verdict']}" if acc else "not started (first check on 3 Dec)"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>GreenJobs ops status</title><style>{CSS}</style></head><body><main>
<h1>GreenJobs ops status: <span class="{e(status['overall'])}">{e(status['overall'])}</span></h1>
<p class="d">Operator only. Generated {e(status['generated_at'])}. UNMEASURED means the input does not exist yet; it is never shown as a number.</p>
<h2>Metrics</h2>{rows}
<h2>DNS watcher</h2><p class="d">Last run {e(str(w['last_run']))}</p>
<table><tr><th>Domain</th><th>State</th><th>Cloudflare NS</th><th>MX/SPF</th><th>Diana</th></tr>{wrows}</table>
<h2>Uptime probe</h2><p>{p['ok']}/{p['total']} checks ok at {e(str(p['last_run']))}</p><p class="d">{e(', '.join(p['failing']) or 'no failures')}</p>
<h2>Acceptance (10 working days after 3 Dec)</h2><p>{e(acc_line)}</p>
<h2>Redirects</h2><p>{e(str(r.get('old_urls')))} old URLs; {e(str(r.get('served_pct')))}% land on a served page; {e(str(r.get('specific_match_pct')))}% on a specific page or filter; {e(str(r.get('leftovers')))} fall back.</p>
<p class="d">Live job ids: {e(str(r.get('live_ids_source')))}</p>
</main></body></html>
"""


def run(
    inputs: Path,
    state: Path,
    out: Path,
    now: datetime,
    send: bool = False,
    notifier: Notifier | None = None,
) -> dict[str, Any]:
    i = Inputs(inputs, state, now)
    gen = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    ms = [f(i) for f in (sla1, sla2, m1, m2, m3, m4, m5, m6, m7, m8, m9, m10, m11, b1, b2, net1)] + cpo_cdo(i)
    for m in ms:  # the guard, again, on the assembled list
        assert not (m["value"] is None and m["grade"] != UNMEASURED), m
    status = {
        "generated_at": gen,
        "overall": overall(ms),
        "metrics": ms,
        "health": health(i),
    }
    C.write_json(out / "status.json", status)
    (out / "status.html").write_text(render_html(status), encoding="utf-8")
    for site in C.BOARDS:
        C.write_json(out / f"measures_{site}.json", measures(i, site, gen))
    nt = notifier or Notifier(state, send=send)
    for m in ms:
        if m["grade"] == FAIL:
            nt.queue(
                f"metric-fail:{m['id']}:{now.date().isoformat()}",
                "OPS_ALERT_EMAIL",
                f"GreenJobs RED: {m['id']} {m['name']}",
                f"{m['id']} {m['name']}: {m['display']}\n{m['detail']}\nStatus page: status.html ({gen})\n",
                "ops_alert",
                "",
            )
    return status


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--inputs", type=Path, default=C.STATE_DIR / "inputs")
    ap.add_argument("--state-dir", type=Path, default=C.STATE_DIR)
    ap.add_argument("--out", type=Path, default=C.STATE_DIR / "status")
    ap.add_argument("--now", help="ISO time to grade at (tests, replays); default now")
    ap.add_argument("--send", action="store_true")
    a = ap.parse_args(argv)
    now = C.parse_iso(a.now) if a.now else C.parse_iso(C.now_iso())
    st = run(a.inputs, a.state_dir, a.out, now, a.send)
    counts = {
        g: sum(m["grade"] == g for m in st["metrics"])
        for g in (PASS, WARN, FAIL, UNMEASURED, INFO)
    }
    print(f"overall {st['overall']}: {counts} -> {a.out}/status.html")
    return 1 if counts[FAIL] else 0


if __name__ == "__main__":
    sys.exit(main())
