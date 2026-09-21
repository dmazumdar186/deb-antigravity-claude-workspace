"""
advance.py
description: Follow-up scheduler. For `sent` rows whose next_touch_at <= date, touch < 4, and
    not replied, creates the touch+1 `queued` row (state_machine's sent->queued). Touch-4 `sent`
    rows past next_touch_at + 5d close as closed_lost.
inputs: CLI: [--date YYYY-MM-DD] [--mock] [--store {local,supabase}] [--store-root PATH].
outputs: stdout stat line {"script":"advance","date":...,"advanced":n,"closed_lost":n};
    Store mutations via outreach/state_machine.py transitions.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from execution.personal_workflows.prodcraft_medspa.common import config, store as store_mod  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.outreach import _store_helpers, state_machine  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.scripts._stage_runner import reject_mock_with_supabase  # noqa: E402

CLOSE_LOST_GRACE_DAYS = 5


def _parse_date(value: str | None) -> date:
    if not value:
        return date.today()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        # exit code 2 (argparse's own usage-error convention) and a one-line message on stderr —
        # never a traceback surfacing through daily.py's stderr (round-2 audit finding).
        print(f"invalid --date, expected YYYY-MM-DD (got {value!r})", file=sys.stderr)
        raise SystemExit(2) from None


def _as_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def run_advance(st: Any, today: date) -> dict:
    sent_rows = [r for r in _store_helpers.list_all(st, "outreach") if r.get("status") == "sent"]

    advanced = 0
    closed_lost = 0

    for row in sent_rows:
        if row.get("replied_at"):
            continue
        if row.get("reply_sentiment") == "bounce":
            continue  # scan_replies already cascaded this business's other touches to closed_lost
        touch = int(row.get("touch") or 1)
        next_touch_at = _as_date(row.get("next_touch_at"))
        if next_touch_at is None or next_touch_at > today:
            continue

        if touch < state_machine.MAX_TOUCH:
            state_machine.transition(st, row, "queued")
            advanced += 1
            continue

        # touch == MAX_TOUCH: close as lost once next_touch_at + grace days has passed.
        if today >= next_touch_at + timedelta(days=CLOSE_LOST_GRACE_DAYS):
            state_machine.transition(st, row, "closed_lost")
            closed_lost += 1

    return {"script": "advance", "date": today.isoformat(), "advanced": advanced, "closed_lost": closed_lost}


def main() -> None:
    parser = argparse.ArgumentParser(description="Advance sent outreach rows to their next touch or close them out")
    parser.add_argument("--date", default=None)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--store", choices=["local", "supabase"], default=None)
    parser.add_argument("--store-root", default=None)
    args = parser.parse_args()

    settings = config.bootstrap()
    store_kind = reject_mock_with_supabase(parser, args)  # --mock implies local; never supabase
    st = store_mod.get_store(kind=store_kind, root=args.store_root)
    today = _parse_date(args.date)

    try:
        stats = run_advance(st, today)
    except Exception as exc:  # noqa: BLE001 — top-level failure must reach the error channel
        from execution.personal_workflows.prodcraft_medspa.common import notify

        notify.error("prodcraft_medspa.advance", f"{type(exc).__name__}: {exc}")
        raise

    print(json.dumps(stats))


if __name__ == "__main__":
    main()
