"""GreenJobs incidents and service levels (P20): open/close from probe results, operator ack, SLA attainment.

description: Service levels sold (Proposal :92, :134, :137): 99.9% monthly
  uptime; response within 4 hours for a posting outage (sev-1: the staff
  console, the jobs API or the apply endpoint of a board is down) and within
  1 business day for anything else (sev-2: a board host down, mail records
  differ). The probe calls update() each run: a failing check opens one
  incident (alerting the operator at once for sev-1, and for sev-2 too, with
  its 1-business-day deadline), a passing check closes it. `ack ID` records
  the operator's response time. sla() reports attainment for the status page.
inputs: ack <incident id> | list   [--state-dir DIR]
outputs: <state>/incidents.json; operator alerts via notify.Notifier (outbox; live with --send on the probe)
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as C  # noqa: E402
from notify import Notifier  # noqa: E402

UPTIME_TARGET = 0.999  # per calendar month (P20)
SEV1_RESPONSE = timedelta(hours=4)
SEV2_BUSINESS_DAYS = 1


def add_business_days(start: datetime, n: int) -> datetime:
    """Deadline n business days (Mon-Fri) after start, same clock time. Public holidays are not modelled."""
    d = start
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def deadline(inc: dict[str, Any]) -> datetime:
    opened = C.parse_iso(inc["opened_at"])
    return (
        opened + SEV1_RESPONSE
        if inc["sev"] == 1
        else add_business_days(opened, SEV2_BUSINESS_DAYS)
    )


def update(
    state: Path,
    failing: dict[str, tuple[int, str]],
    checked: set[str],
    now: str,
    notifier: Notifier,
) -> list[str]:
    """failing: {check id: (sev, evidence)} among `checked`. Opens one incident per failing check (idempotent while
    it stays open), closes incidents whose check passed this run. Returns event lines.
    """
    path = Path(state) / "incidents.json"
    data = C.read_json(path, {}) or {}
    incs = data.setdefault("incidents", {})
    open_by_check = {v["check"]: k for k, v in incs.items() if not v.get("closed_at")}
    events = []
    for check, (sev, evidence) in sorted(failing.items()):
        if check in open_by_check:
            continue
        iid = f"{now[:16].replace(':', '').replace('-', '')}-{check}"
        incs[iid] = {
            "check": check,
            "sev": sev,
            "opened_at": now,
            "evidence": evidence,
            "acked_at": None,
            "closed_at": None,
        }
        due = deadline(incs[iid]).isoformat()
        notifier.queue(
            f"incident:{iid}",
            "OPS_ALERT_EMAIL",
            f"GreenJobs SEV-{sev}: {check} failing",
            f"Incident {iid}\nCheck: {check}\nEvidence: {evidence}\nOpened: {now}\nRespond by: {due}\n"
            f"Ack: python3 execution/gtm_client_workflows/greenjobs_redesign/ops/incidents.py ack {iid}\n",
            "ops_alert",
            "",
        )
        events.append(f"opened {iid} (sev-{sev}, respond by {due})")
    for check, iid in open_by_check.items():
        if check in checked and check not in failing:
            incs[iid]["closed_at"] = now
            events.append(f"closed {iid}")
    C.write_json(path, data)
    return events


def ack(state: Path, iid: str, now: str | None = None) -> bool:
    path = Path(state) / "incidents.json"
    data = C.read_json(path, {}) or {}
    inc = data.get("incidents", {}).get(iid)
    if not inc:
        return False
    if not inc.get("acked_at"):  # idempotent: the first response time stands
        inc["acked_at"] = now or C.now_iso()
        C.write_json(path, data)
    return True


def sla(state: Path, now: datetime) -> dict[str, Any] | None:
    """Response attainment over incidents opened this calendar month; None when no incident log exists yet."""
    data = C.read_json(Path(state) / "incidents.json")
    if data is None:
        return None
    month = now.strftime("%Y-%m")
    rows = [
        v | {"id": k}
        for k, v in data.get("incidents", {}).items()
        if v["opened_at"][:7] == month
    ]
    met, breached = 0, []
    for r in rows:
        due = deadline(r)
        acked = C.parse_iso(r.get("acked_at"))
        if acked and acked <= due:
            met += 1
        elif acked or now > due:
            breached.append(f"{r['id']} (sev-{r['sev']})")
    pending = len(rows) - met - len(breached)
    return {
        "incidents": len(rows),
        "met": met,
        "breached": breached,
        "pending": pending,
        "sev1": sum(r["sev"] == 1 for r in rows),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["ack", "list"])
    ap.add_argument("id", nargs="?")
    ap.add_argument("--state-dir", type=Path, default=C.STATE_DIR)
    a = ap.parse_args(argv)
    if a.cmd == "ack":
        ok = ack(a.state_dir, a.id or "")
        print("acked" if ok else f"no incident {a.id}")
        return 0 if ok else 1
    for k, v in (
        (C.read_json(a.state_dir / "incidents.json", {}) or {})
        .get("incidents", {})
        .items()
    ):
        print(
            k,
            f"sev-{v['sev']}",
            "open" if not v.get("closed_at") else "closed",
            "acked" if v.get("acked_at") else "UNACKED",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
