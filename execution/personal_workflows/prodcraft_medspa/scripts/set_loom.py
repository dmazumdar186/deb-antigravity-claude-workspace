"""
set_loom.py
description: Touch-2 operator path. Records `notes.loom_url` (the Loom walkthrough URL that touch 2
    parks on) for one outreach row and, when the row is `drafted`, sends it back through the
    pipeline via state_machine.redraft() so the next daily_queue run re-renders it with the real
    URL and send.py stops dropping it as `needs_operator_input`. Idempotent: re-running with the
    same URL changes nothing and never redrafts (a `drafted` row keeps its clean draft).
inputs: --prospect-id ID (an `outreach` row id, or a `businesses` id: the latest non-terminal
    touch-2 row for that business is used), --url https://www.loom.com/share/... (https and a
    loom.com host, else exit 2), --store {local,supabase}, --store-root PATH, [--touch N] (default 2).
outputs: the outreach row patched (notes.loom_url; `manual_patch` event with reason `set_loom`),
    a `redraft` transition when the row was `drafted`; one JSON line on stdout with the resulting
    row state: {"script":"set_loom","outreach_id","business_id","touch","status","loom_url",
    "redrafted":bool,"changed":bool}.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))  # repo root, for direct-script execution

from execution.personal_workflows.prodcraft_medspa.common.store import get_store  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.outreach import state_machine  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.outreach.daily_queue import _notes_dict  # noqa: E402

_TERMINAL = {"closed_won", "closed_lost", "dnc"}
_LOOM_HOSTS = ("loom.com",)


class InvalidLoomUrl(ValueError):
    pass


def validate_loom_url(url: str) -> str:
    """Return the URL unchanged when it is https on loom.com (or a subdomain); raise otherwise.
    Strict on purpose: this value is pasted verbatim into a customer-facing email."""
    candidate = (url or "").strip()
    parts = urlsplit(candidate)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https":
        raise InvalidLoomUrl("loom url must use https")
    if not (host in _LOOM_HOSTS or any(host.endswith("." + h) for h in _LOOM_HOSTS)):
        raise InvalidLoomUrl(f"loom url host must be loom.com, got {host or '(none)'!r}")
    if not parts.path or parts.path == "/":
        raise InvalidLoomUrl("loom url has no share path")
    if any(ch in candidate for ch in "\r\n \t"):
        raise InvalidLoomUrl("loom url contains whitespace")
    return candidate


def resolve_outreach_row(store, prospect_id: str, *, touch: int = 2) -> dict:
    """`prospect_id` may be an outreach id or a business id. For a business id, pick the newest
    non-terminal row for `touch`. Raises KeyError when nothing matches."""
    row = store.get_row("outreach", prospect_id)
    if row is not None:
        return row
    candidates = [
        r for r in store.list_outreach(prospect_id)
        if int(r.get("touch") or 0) == touch and r.get("status") not in _TERMINAL
    ]
    if not candidates:
        raise KeyError(f"no outreach row with id {prospect_id!r} and no open touch-{touch} row for business {prospect_id!r}")
    return candidates[0]  # list_outreach returns newest first


def set_loom(store, prospect_id: str, url: str, *, touch: int = 2) -> dict:
    """The one-command operator path: validate, record notes.loom_url, redraft if drafted."""
    loom_url = validate_loom_url(url)
    row = resolve_outreach_row(store, prospect_id, touch=touch)

    notes = dict(_notes_dict(row))
    changed = notes.get("loom_url") != loom_url
    if changed:
        notes["loom_url"] = loom_url
        row = store.manual_patch("outreach", row["id"], {"notes": json.dumps(notes)}, "set_loom")

    # Round-4 item J: redraft only when the URL actually changed. A `drafted` row already
    # rendered with this exact URL has a clean draft; redrafting would discard it for nothing.
    redrafted = False
    if changed and row.get("status") == "drafted":
        row = state_machine.redraft(store, row["id"], "set_loom")
        redrafted = True

    return {
        "script": "set_loom",
        "outreach_id": row["id"],
        "business_id": row.get("business_id"),
        "touch": row.get("touch"),
        "status": row.get("status"),
        "loom_url": loom_url,
        "redrafted": redrafted,
        "changed": changed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--prospect-id", required=True, help="outreach row id, or a business id (newest open touch-N row)")
    parser.add_argument("--url", required=True, help="https://www.loom.com/share/...")
    parser.add_argument("--touch", type=int, default=2)
    parser.add_argument("--store", choices=["local", "supabase"], default=None)
    parser.add_argument("--store-root", default=None)
    args = parser.parse_args()

    store = get_store(kind=args.store, root=args.store_root)
    try:
        result = set_loom(store, args.prospect_id, args.url, touch=args.touch)
    except InvalidLoomUrl as exc:
        # set_loom() validates before it reads or writes anything, so exit 2 here leaves the
        # store untouched (one validation path, round-4 item F).
        parser.error(str(exc))
    except KeyError as exc:
        print(json.dumps({"script": "set_loom", "error": str(exc)}))
        sys.exit(1)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
