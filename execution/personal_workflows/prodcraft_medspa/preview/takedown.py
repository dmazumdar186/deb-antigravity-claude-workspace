"""
takedown.py
description: Programmatic takedown of one or more previews (by --business-id, --preview-id, or --host).
    Deletes the R2 prefix directly, calls the Worker's public POST /remove takedown path (see publish.py's
    module docstring "NOTE on takedown" — /api/publish has no takedown field to update), sets
    previews.status='takedown'/takedown=true/takedown_at, businesses.do_not_contact=true, and closes every
    non-terminal outreach row for the business to status 'dnc' (field-only; the outreach state machine
    itself belongs to another package).
inputs: --business-id ID | --preview-id ID | --host HOST (exactly one), --mock, --store {local,supabase},
    --store-root PATH. Env per CONTRACTS.md ("preview" stage) for the live R2/Worker calls.
outputs: R2 objects deleted, a POST to the Worker's /remove, `previews`/`businesses`/`outreach` rows updated,
    `events` rows logged ("takedown"), stdout JSON stat line {"script":"takedown","in","out","errors"}.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))  # repo root, for direct-script execution

from execution.personal_workflows.prodcraft_medspa.common import config, models, notify  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.common.store import get_store  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.preview import publish, r2  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.preview.build_preview import (  # noqa: E402
    find_previews_for_business,
)
from execution.personal_workflows.prodcraft_medspa.scripts._stage_runner import (  # noqa: E402
    reject_mock_with_supabase,
)

_TERMINAL_OUTREACH_STATUSES = {"closed_won", "closed_lost", "dnc"}


def _find_preview_by_id(store, preview_id: str) -> dict | None:
    return store.get_row("previews", preview_id)


def _find_preview_by_host(store, host: str) -> dict | None:
    subdomain_url = f"https://{host}"
    matches = store.list_rows("previews", subdomain_url=subdomain_url)
    return matches[0] if matches else None


def _find_outreach_for_business(store, business_id: str) -> list[dict]:
    return store.list_outreach(business_id)


def resolve_target_previews(store, *, business_id: str | None, preview_id: str | None, host: str | None) -> list[dict]:
    if preview_id:
        preview = _find_preview_by_id(store, preview_id)
        return [preview] if preview else []
    if host:
        preview = _find_preview_by_host(store, host)
        return [preview] if preview else []
    if business_id:
        return [p for p in find_previews_for_business(store, business_id) if not p.get("takedown")]
    return []


def _host_from_preview(preview: dict) -> str:
    subdomain_url = preview.get("subdomain_url") or ""
    return subdomain_url.split("//", 1)[-1].split("/", 1)[0]


def take_down_preview(store, preview: dict, *, mock: bool, tmp_root: Path, dnc: bool = True) -> dict:
    """Unpublish one preview (R2 prefix delete + Worker /remove + previews row -> takedown).

    `dnc=True` (default; every in-tree caller — the remove/dnc path AND, since the round-4
    audit, the negative-reply path in outreach/scan_replies.py) also stamps
    `businesses.do_not_contact = True` and closes every non-terminal outreach row for the
    business to `dnc`. `dnc=False` performs the same unpublish but leaves the business row and
    its outreach rows untouched; kept for callers that need an unpublish that is not an opt-out
    (e.g. an operator-driven re-render). Idempotent-safe either way."""
    host = _host_from_preview(preview)
    # The R2 prefix segment is the host's first label — same rule the Worker uses (slugSuffixFromHost).
    prefix_label = host.split(".")[0] if host else preview.get("slug_suffix", "")
    prefix = f"previews/{prefix_label}"

    if mock:
        r2_client = r2.MockR2(root=tmp_root / "r2")
    else:
        r2_client = r2.R2Client(
            account_id=os.environ.get("CLOUDFLARE_ACCOUNT_ID", ""),
            access_key=os.environ.get("R2_ACCESS_KEY_ID", ""),
            secret_key=os.environ.get("R2_SECRET_ACCESS_KEY", ""),
            bucket=os.environ.get("R2_BUCKET", "prodcraft-previews"),
        )
    deleted = r2_client.delete_prefix(prefix)

    publish.takedown(host, mock=mock, meta_dir=tmp_root / "kv")

    now = models.now_iso()
    updated = store.update_preview(preview["id"], {"status": "takedown", "takedown": True, "takedown_at": now})

    business_id = preview.get("business_id")
    business = store.get_business(business_id) if (business_id and dnc) else None
    if business:
        # update_row() patches by id instead of round-tripping the whole row through
        # upsert_business() (keyed on place_id) — avoids a lost-update window against a
        # business row another process mutated between the read above and this write
        # (code-reviewer C4/M1).
        store.update_row("businesses", business["id"], {"do_not_contact": True})

    outreach_closed = 0
    for row in _find_outreach_for_business(store, business_id) if (business_id and dnc) else []:
        if row.get("status") in _TERMINAL_OUTREACH_STATUSES:
            continue
        store.update_outreach(row["id"], {"status": "dnc"})
        outreach_closed += 1

    store.log_event("preview", preview["id"], "takedown", {"host": host, "r2_objects_deleted": deleted})
    if business_id:
        store.log_event(
            "business", business_id, "takedown", {"host": host, "outreach_closed": outreach_closed, "dnc": dnc}
        )

    return {
        "preview_id": preview["id"],
        "business_id": business_id,
        "host": host,
        "r2_objects_deleted": deleted,
        "outreach_closed": outreach_closed,
        "status": updated.get("status"),
    }


def main() -> None:
    settings = config.bootstrap()
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--business-id")
    group.add_argument("--preview-id")
    group.add_argument("--host")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--store", choices=["local", "supabase"], default=None)
    parser.add_argument("--store-root", default=None)
    args = parser.parse_args()

    store_kind = reject_mock_with_supabase(parser, args)
    store = get_store(kind=store_kind, root=args.store_root)

    previews = resolve_target_previews(
        store, business_id=args.business_id, preview_id=args.preview_id, host=args.host
    )
    stats = {"script": "takedown", "in": len(previews), "out": 0, "errors": 0}
    results = []

    for preview in previews:
        try:
            results.append(take_down_preview(store, preview, mock=args.mock, tmp_root=settings.TMP))
            stats["out"] += 1
        except Exception as exc:  # noqa: BLE001 — one bad preview must not abort the rest of the batch
            stats["errors"] += 1
            notify.error("takedown", f"{preview.get('id')}: {exc}")

    print(json.dumps({**stats, "results": results}))
    if stats["in"] == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
