"""
description: One-shot cleanup that removes rows from each role tab + Top
    Matches whose Title fails the relevance gate (title_filter.classify_title).
    Fixes the historical junk (cybersecurity / SEO / accounting / facilities
    consultants) that leaked in before the relevance allowlist was added.
inputs:
    - env: SHEETS_SPREADSHEET_ID, GOOGLE_SERVICE_ACCOUNT_PATH
    - CLI: --dry-run (preview), --tabs (subset)
outputs:
    - In-place rewrite of each tab keeping only relevant-title rows.
    - Stdout: per-tab kept/removed counts + sample removed titles.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv, find_dotenv

_HERE = Path(__file__).resolve()
_WORKSPACE = _HERE.parents[3]
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))

from execution.personal_workflows.job_search_v2.normalizer.title_filter import classify_title  # noqa: E402
from execution.personal_workflows.job_search_v2.normalizer.language_filter import classify_language  # noqa: E402
from execution.personal_workflows.job_search_v2.notifier.sheet import (  # noqa: E402
    TOP_MATCHES_TAB,
    _col_index_to_letter,
    _open_sheet,
)

load_dotenv(find_dotenv(usecwd=False))
logger = logging.getLogger("purge_irrelevant_rows")

ROLE_TABS = ["PM", "AI PM", "AI Automation", "AI Mobile", "AI Process", "AI Consultant"]


def _purge_tab(ws, dry_run: bool) -> tuple[int, int, list[str]]:
    """Keep only rows whose Title passes the relevance gate. Returns
    (kept, removed, sample_removed_titles)."""
    all_rows = ws.get_all_values()
    if not all_rows:
        return 0, 0, []
    header = all_rows[0]
    idx = {h: i for i, h in enumerate(header) if h and h.strip()}
    title_i = idx.get("Title")
    if title_i is None:
        logger.warning("%s: no Title column — skipping", ws.title)
        return 0, 0, []

    data_rows = [r for r in all_rows[1:] if any(c.strip() for c in r)]
    kept_rows = []
    removed_titles = []
    for row in data_rows:
        title = row[title_i] if len(row) > title_i else ""
        rel_ok, _ = classify_title(title)
        lang_ok, _ = classify_language(title, "")
        if rel_ok and lang_ok:
            kept_rows.append(row)
        else:
            removed_titles.append(title)

    removed = len(removed_titles)
    if dry_run or removed == 0:
        return len(kept_rows), removed, removed_titles[:5]

    n_cols = len(header)
    new_grid = [header] + kept_rows
    end_col = _col_index_to_letter(n_cols)
    # Clear the old body region then rewrite.
    old_last = len(all_rows)
    try:
        ws.batch_clear([f"A2:{end_col}{old_last}"])
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning("%s: clear failed: %s", ws.title, exc)
    if len(new_grid) > 1:
        ws.update(
            range_name=f"A1:{end_col}{len(new_grid)}",
            values=new_grid,
            value_input_option="USER_ENTERED",
        )
    return len(kept_rows), removed, removed_titles[:5]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Purge irrelevant-title rows from job_search_v2 tabs.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--tabs", default="")
    args = parser.parse_args()

    sp, err = _open_sheet(None, None)
    if sp is None:
        logger.error("Cannot open sheet: %s", err)
        return 1

    tabs = [t.strip() for t in args.tabs.split(",") if t.strip()] or (ROLE_TABS + [TOP_MATCHES_TAB])
    import gspread  # type: ignore

    total_removed = 0
    for tab in tabs:
        try:
            ws = sp.worksheet(tab)
        except gspread.WorksheetNotFound:
            continue
        kept, removed, sample = _purge_tab(ws, dry_run=args.dry_run)
        total_removed += removed
        tag = "[dry-run] " if args.dry_run else ""
        print(f"{tag}{tab}: kept {kept}, removed {removed}")
        for s in sample:
            print(f"    removed e.g.: {s[:70]}")

    print(f"\nTotal {'would remove' if args.dry_run else 'removed'}: {total_removed} irrelevant rows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
