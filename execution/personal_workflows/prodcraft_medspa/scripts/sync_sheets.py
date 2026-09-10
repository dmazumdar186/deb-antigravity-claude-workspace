"""
sync_sheets.py
description: Mirrors the read-only `v_pipeline` view (db/schema.sql) to a Google Sheet tab named
    "pipeline", reusing the execution/google/google_sheets_writer.py auth + atomic-write pattern.
    For LocalStore, the join `v_pipeline` performs in Postgres is recomputed here in Python.
inputs: CLI: [--mock] [--store {local,supabase}] [--store-root P]. Env: GOOGLE_SHEETS_MIRROR_ID,
    GOOGLE_SERVICE_ACCOUNT_PATH (both required unless --mock); SUPABASE_URL/SUPABASE_SERVICE_KEY
    if --store supabase.
outputs: --mock: .tmp/prodcraft_medspa/v_pipeline.csv. Live: overwrites the "pipeline" tab of the
    GOOGLE_SHEETS_MIRROR_ID workbook; stdout final JSON stat line.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from execution.personal_workflows.prodcraft_medspa.common.store import (  # noqa: E402
    LocalStore,
    SupabaseStore,
    get_store,
)

# Column order matches db/schema.sql's `create or replace view v_pipeline as select ...`
V_PIPELINE_COLUMNS = [
    "name",
    "suburb",
    "metro",
    "website_url",
    "owner_name",
    "owner_email",
    "email_status",
    "total_score",
    "bucket",
    "preview_url",
    "preview_status",
    "touch",
    "outreach_status",
    "sent_at",
    "next_touch_at",
]


def _all_rows(store: Any, table: str) -> list[dict]:
    """Same rationale as run_metro.py's _all_previews / fit_weights.py's _all_rows: the Store
    Protocol has no generic "list table" method, so this reaches into each concrete store."""
    if isinstance(store, LocalStore):
        return store._read(table)  # noqa: SLF001
    if isinstance(store, SupabaseStore):
        resp = store._request("GET", table, headers=store._headers())  # noqa: SLF001
        return resp.json()
    return []


def compute_v_pipeline(store: Any) -> list[dict]:
    """Recompute db/schema.sql's `v_pipeline` view in Python, for either Store backend.

    Matches the SQL exactly: businesses where is_chain = false and drop_reason is null, left-join
    the latest audit / latest preview / latest-by-touch outreach row per business.
    """
    businesses = [
        b for b in _all_rows(store, "businesses") if not b.get("is_chain") and b.get("drop_reason") is None
    ]

    audits_by_business: dict[str, dict] = {}
    for a in _all_rows(store, "audits"):
        bid = a.get("business_id")
        existing = audits_by_business.get(bid)
        if existing is None or (a.get("audited_at") or "") > (existing.get("audited_at") or ""):
            audits_by_business[bid] = a

    previews_by_business: dict[str, dict] = {}
    for p in _all_rows(store, "previews"):
        bid = p.get("business_id")
        existing = previews_by_business.get(bid)
        if existing is None or (p.get("created_at") or "") > (existing.get("created_at") or ""):
            previews_by_business[bid] = p

    outreach_by_business: dict[str, dict] = {}
    for o in _all_rows(store, "outreach"):
        bid = o.get("business_id")
        existing = outreach_by_business.get(bid)
        if existing is None or (o.get("touch") or 0) > (existing.get("touch") or 0):
            outreach_by_business[bid] = o

    rows = []
    for b in businesses:
        a = audits_by_business.get(b["id"], {})
        p = previews_by_business.get(b["id"], {})
        o = outreach_by_business.get(b["id"], {})
        rows.append(
            {
                "name": b.get("name"),
                "suburb": b.get("suburb"),
                "metro": b.get("metro"),
                "website_url": b.get("website_url"),
                "owner_name": b.get("owner_name"),
                "owner_email": b.get("owner_email"),
                "email_status": b.get("email_status"),
                "total_score": a.get("total_score"),
                "bucket": a.get("bucket"),
                "preview_url": p.get("subdomain_url"),
                "preview_status": p.get("status"),
                "touch": o.get("touch"),
                "outreach_status": o.get("status"),
                "sent_at": o.get("sent_at"),
                "next_touch_at": o.get("next_touch_at"),
            }
        )
    return rows


def write_csv(rows: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=V_PIPELINE_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in V_PIPELINE_COLUMNS})


def write_google_sheet(rows: list[dict], spreadsheet_id: str) -> None:
    """Overwrite the "pipeline" tab in one atomic ws.update(), mirroring
    execution/google/google_sheets_writer.py's write_top_matches() pattern (single call sized to
    cover both the new rows and any longer previous extent, so no intermediate empty-sheet state).
    """
    import gspread  # type: ignore[import-untyped]

    key_path_raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", "").strip()
    if not key_path_raw:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_PATH env var is not set")
    key_path = Path(key_path_raw)
    if not key_path.is_absolute():
        key_path = REPO_ROOT / key_path
    if not key_path.exists():
        raise FileNotFoundError(f"Service account key not found: {key_path}")

    client = gspread.service_account(filename=str(key_path))
    spreadsheet = client.open_by_key(spreadsheet_id)

    titles = {ws.title: ws for ws in spreadsheet.worksheets()}
    if "pipeline" in titles:
        ws = titles["pipeline"]
    else:
        ws = spreadsheet.add_worksheet(title="pipeline", rows=max(200, len(rows) + 10), cols=len(V_PIPELINE_COLUMNS))

    header = V_PIPELINE_COLUMNS
    data = [[("" if row.get(c) is None else str(row.get(c))) for c in V_PIPELINE_COLUMNS] for row in rows]
    all_rows = [header] + data

    try:
        prev_extent = int(ws.row_count)
    except (TypeError, ValueError):
        prev_extent = 0
    pad = max(prev_extent, len(all_rows)) - len(all_rows)
    if pad > 0:
        all_rows += [[""] * len(header) for _ in range(pad)]

    end_col = chr(ord("A") + len(header) - 1)
    ws.update(values=all_rows, range_name=f"A1:{end_col}{len(all_rows)}", value_input_option="RAW")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--store", choices=["local", "supabase"], default=None)
    parser.add_argument("--store-root", dest="store_root", default=None)
    args = parser.parse_args()

    store = get_store(kind=args.store, root=args.store_root) if args.store_root else get_store(kind=args.store)
    rows = compute_v_pipeline(store)

    if args.mock:
        out_path = REPO_ROOT / ".tmp" / "prodcraft_medspa" / "v_pipeline.csv"
        write_csv(rows, out_path)
        print(f"Wrote {out_path} ({len(rows)} rows)")
        print(json.dumps({"script": "sync_sheets", "in": len(rows), "out": len(rows), "dropped": {}, "target": str(out_path)}))
        return

    spreadsheet_id = os.environ.get("GOOGLE_SHEETS_MIRROR_ID")
    if not spreadsheet_id:
        print("GOOGLE_SHEETS_MIRROR_ID not set — falling back to CSV (pass --mock to do this deliberately)", file=sys.stderr)
        out_path = REPO_ROOT / ".tmp" / "prodcraft_medspa" / "v_pipeline.csv"
        write_csv(rows, out_path)
        print(json.dumps({"script": "sync_sheets", "in": len(rows), "out": len(rows), "dropped": {}, "target": str(out_path), "note": "no GOOGLE_SHEETS_MIRROR_ID"}))
        return

    try:
        write_google_sheet(rows, spreadsheet_id)
    except Exception as exc:  # noqa: BLE001 — report and fall back rather than crash a mirror sync
        from execution.personal_workflows.prodcraft_medspa.common import notify

        notify.error("sync_sheets", str(exc), count=1)
        print(f"sync_sheets failed: {exc}", file=sys.stderr)
        print(json.dumps({"script": "sync_sheets", "in": len(rows), "out": 0, "dropped": {"write_error": len(rows)}, "error": str(exc)}))
        sys.exit(1)

    print(f"Wrote {len(rows)} rows to Google Sheet {spreadsheet_id}, tab 'pipeline'")
    print(json.dumps({"script": "sync_sheets", "in": len(rows), "out": len(rows), "dropped": {}, "target": spreadsheet_id}))


if __name__ == "__main__":
    main()
