"""
description: One-shot migration that rewrites every role tab + Top Matches tab
    to only the trimmed column set the operator approved on 2026-06-24. Reads
    all existing data, extracts only the columns we want to keep, then fully
    overwrites the tab with the trimmed schema. Safe to re-run (idempotent).
inputs:
    - env: SHEETS_SPREADSHEET_ID, GOOGLE_SERVICE_ACCOUNT_PATH
    - CLI: --dry-run (preview without writing), --tabs (comma-separated subset)
outputs:
    - In-place rewrite of each role tab + Top Matches tab.
    - Stdout: per-tab rows-kept / cols-trimmed report.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv, find_dotenv

_HERE = Path(__file__).resolve()
_WORKSPACE = _HERE.parents[3]
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))

from execution.personal_workflows.job_search_v2.notifier.sheet import (  # noqa: E402
    STANDARD_HEADERS,
    TOP_MATCHES_HEADERS,
    TOP_MATCHES_TAB,
    _col_index_to_letter,
    _open_sheet,
)

load_dotenv(find_dotenv(usecwd=False))
logger = logging.getLogger("trim_sheet_columns")

ROLE_TABS = ["PM", "AI PM", "AI Automation", "AI Mobile", "AI Process", "AI Consultant"]


def _rewrite_tab(ws, target_headers: list[str], dry_run: bool) -> tuple[int, int, int]:
    """Read all rows, keep only target_headers' data, fully overwrite. Returns
    (data_rows_kept, original_cols, new_cols)."""
    all_rows = ws.get_all_values()
    if not all_rows:
        return 0, 0, len(target_headers)

    header = all_rows[0]
    orig_cols = len([h for h in header if h and h.strip()])

    # Build {orig_header_name: orig_col_index} lookup.
    orig_idx = {h: i for i, h in enumerate(header) if h and h.strip()}

    data_rows = [r for r in all_rows[1:] if any(c.strip() for c in r)]
    if not data_rows:
        new_grid = [target_headers]
    else:
        new_grid = [target_headers]
        for row in data_rows:
            new_row = []
            for h in target_headers:
                src_idx = orig_idx.get(h)
                if src_idx is None or src_idx >= len(row):
                    new_row.append("")
                else:
                    new_row.append(row[src_idx])
            new_grid.append(new_row)

    if dry_run:
        logger.info(
            "[dry-run] %s: would write %d rows x %d cols (was %d cols)",
            ws.title, len(new_grid), len(target_headers), orig_cols,
        )
        return len(new_grid) - 1, orig_cols, len(target_headers)

    end_col_letter = _col_index_to_letter(max(len(target_headers), orig_cols))
    end_row = max(len(new_grid), ws.row_count)
    # Clear everything first so leftover columns past target don't linger.
    try:
        ws.batch_clear([f"A1:{end_col_letter}{end_row}"])
    except Exception as exc:  # noqa: BLE001 — best-effort clear
        logger.warning("%s: pre-clear failed: %s", ws.title, exc)

    target_end_col_letter = _col_index_to_letter(len(target_headers))
    range_str = f"A1:{target_end_col_letter}{len(new_grid)}"
    if ws.row_count < len(new_grid):
        try:
            ws.resize(rows=len(new_grid) + 20, cols=max(ws.col_count, len(target_headers)))
        except Exception as exc:  # noqa: BLE001 — best-effort resize
            logger.warning("%s: resize failed: %s", ws.title, exc)
    ws.update(range_name=range_str, values=new_grid, value_input_option="USER_ENTERED")
    logger.info(
        "%s: wrote %d rows x %d cols (was %d cols)",
        ws.title, len(new_grid), len(target_headers), orig_cols,
    )
    return len(new_grid) - 1, orig_cols, len(target_headers)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Trim job_search_v2 sheet columns to the operator-approved schema.")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing.")
    parser.add_argument(
        "--tabs",
        default="",
        help="Comma-separated subset of tabs to migrate (default = all role tabs + Top Matches).",
    )
    args = parser.parse_args()

    sp, err = _open_sheet(None, None)
    if sp is None:
        logger.error("Cannot open sheet: %s", err)
        return 1

    if args.tabs.strip():
        tabs = [t.strip() for t in args.tabs.split(",") if t.strip()]
    else:
        tabs = ROLE_TABS + [TOP_MATCHES_TAB]

    import gspread  # type: ignore

    rc = 0
    for tab_name in tabs:
        try:
            ws = sp.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            logger.warning("%s: tab not found — skipping", tab_name)
            continue
        target = TOP_MATCHES_HEADERS if tab_name == TOP_MATCHES_TAB else STANDARD_HEADERS
        try:
            _rewrite_tab(ws, target, dry_run=args.dry_run)
        except Exception as exc:  # noqa: BLE001 — log + continue with other tabs
            logger.error("%s: rewrite failed: %s", tab_name, exc, exc_info=True)
            rc = 1

    print("Done." + (" (dry-run; no changes written)" if args.dry_run else ""))
    print(f"Operator: open {os.environ.get('SHEETS_SPREADSHEET_ID', '<sheet>')} to verify visually.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
