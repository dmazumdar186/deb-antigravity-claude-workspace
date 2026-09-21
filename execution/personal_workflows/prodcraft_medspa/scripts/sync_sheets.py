"""
sync_sheets.py
description: Mirrors two read-only tabs to a Google Sheet: "pipeline" (db/schema.sql's v_pipeline
    view, extended with preview/outreach/reply columns) and "daily_log" (one row per outreach send).
    Reuses execution/google/google_sheets_writer.py's auth + atomic-write pattern. For LocalStore,
    both views' joins are recomputed here in Python so LocalStore and Supabase produce identical
    columns.
inputs: CLI: [--mock] [--store {local,supabase}] [--store-root P] [--xlsx PATH]. Env:
    GOOGLE_SHEETS_MIRROR_ID, GOOGLE_SERVICE_ACCOUNT_PATH (both required unless --mock or the sheet
    write is skipped for lack of them); SUPABASE_URL/SUPABASE_SERVICE_KEY if --store supabase.
outputs: --mock: .tmp/prodcraft_medspa/v_pipeline.csv and daily_log.csv. Live: overwrites the
    "pipeline" and "daily_log" tabs of the GOOGLE_SHEETS_MIRROR_ID workbook. --xlsx PATH: also (or
    instead, if no sheet target) writes both tabs into one .xlsx workbook via openpyxl, if
    importable — otherwise prints a one-line skip and never fails the run. stdout: final JSON stat
    line.
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

from execution.personal_workflows.prodcraft_medspa.common.store import get_store  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.scripts._stage_runner import reject_mock_with_supabase  # noqa: E402

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
    "reply_sentiment",
    "reply_summary",
    "replied_at",
    "test_recipient",
]

# One row per outreach send (a row with sent_at set), newest first.
DAILY_LOG_COLUMNS = [
    "date",
    "business",
    "recipient",
    "subject",
    "preview_url",
    "gmail_thread_id",
    "status",
]


def _all_rows(store: Any, table: str) -> list[dict]:
    """Full-table read via the Store Protocol's generic list_rows()."""
    return store.list_rows(table)


def _latest_by_business(rows: list[dict], date_key: str) -> dict[str, dict]:
    """business_id -> the row with the max `date_key` value for that business."""
    out: dict[str, dict] = {}
    for row in rows:
        bid = row.get("business_id")
        existing = out.get(bid)
        if existing is None or (row.get(date_key) or "") > (existing.get(date_key) or ""):
            out[bid] = row
    return out


def compute_v_pipeline(store: Any) -> list[dict]:
    """Recompute db/schema.sql's `v_pipeline` view in Python, for either Store backend.

    Matches the SQL exactly: businesses where is_chain = false and drop_reason is null, left-join
    the latest audit / latest preview / latest-by-touch outreach row per business.
    """
    businesses = [
        b for b in _all_rows(store, "businesses") if not b.get("is_chain") and b.get("drop_reason") is None
    ]

    audits_by_business = _latest_by_business(_all_rows(store, "audits"), "audited_at")
    previews_by_business = _latest_by_business(_all_rows(store, "previews"), "created_at")

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
                "reply_sentiment": o.get("reply_sentiment"),
                "reply_summary": o.get("reply_summary"),
                "replied_at": o.get("replied_at"),
                "test_recipient": o.get("test_recipient"),
            }
        )
    return rows


def compute_daily_log(store: Any) -> list[dict]:
    """One row per outreach send (any outreach row with `sent_at` set), newest first.

    `recipient` is `test_recipient` when set (a send made while PRODCRAFT_RECIPIENT_OVERRIDE was
    active) else the business's `owner_email`. `subject`/`gmail_thread_id`/`status` come straight
    off the outreach row; `preview_url` is that business's latest preview.
    """
    businesses_by_id = {b["id"]: b for b in _all_rows(store, "businesses")}
    previews_by_business = _latest_by_business(_all_rows(store, "previews"), "created_at")

    rows = []
    for o in _all_rows(store, "outreach"):
        sent_at = o.get("sent_at")
        if not sent_at:
            continue
        b = businesses_by_id.get(o.get("business_id"), {})
        p = previews_by_business.get(o.get("business_id"), {})
        rows.append(
            {
                "date": str(sent_at)[:10],
                "business": b.get("name"),
                "recipient": o.get("test_recipient") or b.get("owner_email"),
                "subject": o.get("draft_subject"),
                "preview_url": p.get("subdomain_url"),
                "gmail_thread_id": o.get("gmail_thread_id"),
                "status": o.get("status"),
            }
        )
    rows.sort(key=lambda r: r.get("date") or "", reverse=True)
    return rows


def write_csv(rows: list[dict], out_path: Path, columns: list[str]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in columns})


def write_xlsx(pipeline_rows: list[dict], daily_log_rows: list[dict], out_path: Path) -> bool:
    """Write both tabs to one .xlsx workbook via openpyxl, if it's importable.

    Optional dependency by design (CONTRACTS.md: cloud/CI runs must never fail for lack of it) —
    returns False and prints a one-line skip instead of raising when openpyxl isn't installed.
    """
    try:
        import openpyxl  # type: ignore[import-untyped]
    except ImportError:
        print(f"--xlsx skipped: openpyxl not installed (pip install openpyxl) — target was {out_path}")
        return False

    wb = openpyxl.Workbook()
    ws_pipeline = wb.active
    ws_pipeline.title = "pipeline"
    ws_pipeline.append(V_PIPELINE_COLUMNS)
    for row in pipeline_rows:
        ws_pipeline.append([("" if row.get(c) is None else row.get(c)) for c in V_PIPELINE_COLUMNS])

    ws_daily = wb.create_sheet("daily_log")
    ws_daily.append(DAILY_LOG_COLUMNS)
    for row in daily_log_rows:
        ws_daily.append([("" if row.get(c) is None else row.get(c)) for c in DAILY_LOG_COLUMNS])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(out_path))
    print(f"Wrote {out_path} (pipeline {len(pipeline_rows)} rows, daily_log {len(daily_log_rows)} rows)")
    return True


def _column_letter(n: int) -> str:
    """1-indexed column number -> spreadsheet column letters (A, B, ..., Z, AA, AB, ..., AZ, BA, ...).

    Replaces the old `chr(ord("A") + n - 1)`, which only ever produced a single character and
    silently emitted an out-of-range/garbage character (or raised) for any sheet past column 26
    ('Z') — this pipeline's own V_PIPELINE_COLUMNS is currently 19 wide, but DAILY_LOG_COLUMNS plus
    any future column additions make >26 a real possibility. Equivalent to gspread.utils's
    rowcol_to_a1 column half, reimplemented here so this module has no hard gspread dependency at
    CSV/--mock time (gspread is only imported, lazily, inside _get_service_account_client()).
    """
    if n < 1:
        raise ValueError(f"column number must be >= 1, got {n}")
    letters = ""
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def _get_service_account_client():
    import gspread  # type: ignore[import-untyped]

    key_path_raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", "").strip()
    if not key_path_raw:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_PATH env var is not set")
    key_path = Path(key_path_raw)
    if not key_path.is_absolute():
        key_path = REPO_ROOT / key_path
    if not key_path.exists():
        raise FileNotFoundError(f"Service account key not found: {key_path}")
    return gspread.service_account(filename=str(key_path))


def write_google_sheet(rows: list[dict], spreadsheet_id: str, tab_name: str, columns: list[str]) -> None:
    """Overwrite one tab in one atomic ws.update(), mirroring
    execution/google/google_sheets_writer.py's write_top_matches() pattern (single call sized to
    cover both the new rows and any longer previous extent, so no intermediate empty-sheet state).
    """
    client = _get_service_account_client()
    spreadsheet = client.open_by_key(spreadsheet_id)

    titles = {ws.title: ws for ws in spreadsheet.worksheets()}
    if tab_name in titles:
        ws = titles[tab_name]
    else:
        ws = spreadsheet.add_worksheet(title=tab_name, rows=max(200, len(rows) + 10), cols=len(columns))

    header = columns
    data = [[("" if row.get(c) is None else str(row.get(c))) for c in columns] for row in rows]
    all_rows = [header] + data

    try:
        prev_extent = int(ws.row_count)
    except (TypeError, ValueError):
        prev_extent = 0
    pad = max(prev_extent, len(all_rows)) - len(all_rows)
    if pad > 0:
        all_rows += [[""] * len(header) for _ in range(pad)]

    end_col = _column_letter(len(header))
    ws.update(values=all_rows, range_name=f"A1:{end_col}{len(all_rows)}", value_input_option="RAW")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--store", choices=["local", "supabase"], default=None)
    parser.add_argument("--store-root", dest="store_root", default=None)
    parser.add_argument(
        "--xlsx",
        default=None,
        metavar="PATH",
        help="also write both tabs to one .xlsx workbook at PATH (needs openpyxl; skipped, not "
        "fatal, if it's not installed)",
    )
    args = parser.parse_args()
    store_kind = reject_mock_with_supabase(parser, args)  # --mock implies local; never supabase

    store = get_store(kind=store_kind, root=args.store_root) if args.store_root else get_store(kind=store_kind)
    pipeline_rows = compute_v_pipeline(store)
    daily_log_rows = compute_daily_log(store)
    total_rows = len(pipeline_rows) + len(daily_log_rows)

    if args.xlsx:
        write_xlsx(pipeline_rows, daily_log_rows, Path(args.xlsx))

    if args.mock:
        pipeline_path = REPO_ROOT / ".tmp" / "prodcraft_medspa" / "v_pipeline.csv"
        daily_log_path = REPO_ROOT / ".tmp" / "prodcraft_medspa" / "daily_log.csv"
        write_csv(pipeline_rows, pipeline_path, V_PIPELINE_COLUMNS)
        write_csv(daily_log_rows, daily_log_path, DAILY_LOG_COLUMNS)
        print(f"Wrote {pipeline_path} ({len(pipeline_rows)} rows)")
        print(f"Wrote {daily_log_path} ({len(daily_log_rows)} rows)")
        print(json.dumps({"script": "sync_sheets", "in": total_rows, "out": total_rows, "dropped": {}, "target": str(pipeline_path.parent)}))
        return

    spreadsheet_id = os.environ.get("GOOGLE_SHEETS_MIRROR_ID")
    if not spreadsheet_id:
        print("GOOGLE_SHEETS_MIRROR_ID not set — falling back to CSV (pass --mock to do this deliberately)", file=sys.stderr)
        pipeline_path = REPO_ROOT / ".tmp" / "prodcraft_medspa" / "v_pipeline.csv"
        daily_log_path = REPO_ROOT / ".tmp" / "prodcraft_medspa" / "daily_log.csv"
        write_csv(pipeline_rows, pipeline_path, V_PIPELINE_COLUMNS)
        write_csv(daily_log_rows, daily_log_path, DAILY_LOG_COLUMNS)
        print(json.dumps({"script": "sync_sheets", "in": total_rows, "out": total_rows, "dropped": {}, "target": str(pipeline_path.parent), "note": "no GOOGLE_SHEETS_MIRROR_ID"}))
        return

    try:
        write_google_sheet(pipeline_rows, spreadsheet_id, "pipeline", V_PIPELINE_COLUMNS)
        write_google_sheet(daily_log_rows, spreadsheet_id, "daily_log", DAILY_LOG_COLUMNS)
    except Exception as exc:  # noqa: BLE001 — report and fall back rather than crash a mirror sync
        from execution.personal_workflows.prodcraft_medspa.common import notify

        notify.error("sync_sheets", str(exc), count=1)
        print(f"sync_sheets failed: {exc}", file=sys.stderr)
        print(json.dumps({"script": "sync_sheets", "in": total_rows, "out": 0, "dropped": {"write_error": total_rows}, "error": str(exc)}))
        sys.exit(1)

    print(f"Wrote {len(pipeline_rows)} rows to Google Sheet {spreadsheet_id}, tab 'pipeline'")
    print(f"Wrote {len(daily_log_rows)} rows to Google Sheet {spreadsheet_id}, tab 'daily_log'")
    print(json.dumps({"script": "sync_sheets", "in": total_rows, "out": total_rows, "dropped": {}, "target": spreadsheet_id}))


if __name__ == "__main__":
    main()
