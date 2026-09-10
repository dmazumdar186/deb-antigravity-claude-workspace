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
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))  # repo root, for direct-script execution

from execution.personal_workflows.prodcraft_medspa.common import config, models, notify  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.common.store import (  # noqa: E402
    LocalStore,
    SupabaseStore,
    get_store,
)
from execution.personal_workflows.prodcraft_medspa.preview import publish, r2  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.preview.build_preview import (  # noqa: E402
    find_previews_for_business,
)

_TERMINAL_OUTREACH_STATUSES = {"closed_won", "closed_lost", "dnc"}


def _find_preview_by_id(store, preview_id: str) -> dict | None:
    if isinstance(store, LocalStore):
        for row in store._read("previews"):  # noqa: SLF001 — Store protocol has no by-id preview lookup
            if row.get("id") == preview_id:
                return row
        return None
    if isinstance(store, SupabaseStore):
        resp = store._request("GET", f"previews?id=eq.{preview_id}", headers=store._headers())  # noqa: SLF001
        data = resp.json()
        return data[0] if data else None
    return None


def _find_preview_by_host(store, host: str) -> dict | None:
    subdomain_url = f"https://{host}"
    if isinstance(store, LocalStore):
        for row in store._read("previews"):  # noqa: SLF001
            if row.get("subdomain_url") == subdomain_url:
                return row
        return None
    if isinstance(store, SupabaseStore):
        quoted = urllib.parse.quote(subdomain_url, safe="")
        resp = store._request("GET", f"previews?subdomain_url=eq.{quoted}", headers=store._headers())  # noqa: SLF001
        data = resp.json()
        return data[0] if data else None
    return None


def _find_outreach_for_business(store, business_id: str) -> list[dict]:
    if isinstance(store, LocalStore):
        return [r for r in store._read("outreach") if r.get("business_id") == business_id]  # noqa: SLF001
    if isinstance(store, SupabaseStore):
        resp = store._request("GET", f"outreach?business_id=eq.{business_id}", headers=store._headers())  # noqa: SLF001
        return resp.json()
    return []


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


def take_down_preview(store, preview: dict, *, mock: bool, tmp_root: Path) -> dict:
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
    business = store.get_business(business_id) if business_id else None
    if business:
        store.upsert_business({**business, "do_not_contact": True})

    outreach_closed = 0
    for row in _find_outreach_for_business(store, business_id) if business_id else []:
        if row.get("status") in _TERMINAL_OUTREACH_STATUSES:
            continue
        store.update_outreach(row["id"], {"status": "dnc"})
        outreach_closed += 1

    store.log_event("preview", preview["id"], "takedown", {"host": host, "r2_objects_deleted": deleted})
    if business_id:
        store.log_event("business", business_id, "takedown", {"host": host, "outreach_closed": outreach_closed})

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

    store_kind = args.store or ("local" if args.mock else None)
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
