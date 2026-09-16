"""
transition.py
description: CLI for outreach/state_machine.py's transition() — the Python-side state-machine
    authority (the dashboard does the same thing via Cloudflare Pages Functions).
inputs: CLI: --outreach-id ID --to STATE [--sent-at ISO] [--sentiment ...] [--notes ...]
    [--mock] [--store {local,supabase}] [--store-root PATH]. transition.py makes no network calls
    of its own either way; --mock exists per CONTRACTS.md's "every script that touches the Store
    has --mock and --store" and just forces the local JSON store.
outputs: stdout JSON of the resulting (or newly-created, for sent->queued) outreach row plus a
    stat line; Store mutations per state_machine.transition()'s documented side effects.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from execution.personal_workflows.prodcraft_medspa.common import config, store as store_mod  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.outreach import state_machine  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.outreach._store_helpers import list_all  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.scripts._stage_runner import (  # noqa: E402
    reject_mock_with_supabase,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply one outreach state-machine transition")
    parser.add_argument("--outreach-id", required=True)
    parser.add_argument("--to", required=True, choices=list(state_machine.STATES))
    parser.add_argument("--sent-at", default=None)
    parser.add_argument("--sentiment", default=None)
    parser.add_argument("--notes", default=None)
    parser.add_argument("--mock", action="store_true", help="force the local JSON store (transition.py has no network calls)")
    parser.add_argument("--store", choices=["local", "supabase"], default=None)
    parser.add_argument("--store-root", default=None)
    args = parser.parse_args()

    settings = config.bootstrap()
    reject_mock_with_supabase(parser, args)  # --mock + --store supabase is a hard error
    store_kind = args.store or ("local" if args.mock else settings.store_kind)
    st = store_mod.get_store(kind=store_kind, root=args.store_root)

    matches = [r for r in list_all(st, "outreach") if r.get("id") == args.outreach_id]
    if not matches:
        print(json.dumps({"script": "transition", "error": f"outreach row {args.outreach_id} not found"}))
        raise SystemExit(1)
    row = matches[0]

    fields = {}
    if args.sent_at:
        fields["sent_at"] = args.sent_at
    if args.sentiment:
        fields["reply_sentiment"] = args.sentiment
    if args.notes:
        fields["notes"] = args.notes

    try:
        updated = state_machine.transition(st, row, args.to, **fields)
    except state_machine.IllegalTransition as exc:
        print(json.dumps({"script": "transition", "error": str(exc)}))
        raise SystemExit(1) from exc

    print(json.dumps({"script": "transition", "outreach": updated}))


if __name__ == "__main__":
    main()
