"""
google_sheets_writer.py
description: Google Sheets writer for the Job Search pipeline. Service-account auth via gspread. Owns workbook bootstrap, batch writes, hidden column management, and the hidden _meta tab used for cron idempotency.
inputs:  Env var GOOGLE_SERVICE_ACCOUNT_PATH (path to JSON key); SHEETS_SPREADSHEET_ID (the workbook).
outputs: Reads/writes the live Google Sheet. Returns Python dicts (read) or void (write).
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv; load_dotenv()

import gspread
from gspread.exceptions import APIError
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution.personal_workflows._jt_utils import setup_logging  # noqa: E402

logger = setup_logging("google_sheets_writer")

# ---------------------------------------------------------------------------
# Module-level client cache
# ---------------------------------------------------------------------------

_client: "gspread.Client | None" = None


# ---------------------------------------------------------------------------
# Retry predicate — 429 and 5xx APIErrors are retriable
# ---------------------------------------------------------------------------

def _is_retriable(exc: BaseException) -> bool:
    """Return True if the exception is a retriable gspread APIError."""
    if not isinstance(exc, APIError):
        return False
    try:
        status = exc.response.status_code
    except AttributeError:
        return False
    return status == 429 or status >= 500


_retry_on_api_error = retry(
    retry=retry_if_exception(_is_retriable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def get_client() -> gspread.Client:
    """Return a cached gspread Client authenticated via service account.

    Reads GOOGLE_SERVICE_ACCOUNT_PATH from the environment.
    Caches the client at module level so repeated calls do not re-auth.

    Raises:
        ValueError: if GOOGLE_SERVICE_ACCOUNT_PATH is not set.
        FileNotFoundError: if the key file does not exist at that path.
        gspread.exceptions.APIError: on auth failure.
    """
    global _client
    if _client is not None:
        return _client

    try:
        key_path_raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", "").strip()
        if not key_path_raw:
            raise ValueError(
                "GOOGLE_SERVICE_ACCOUNT_PATH env var is not set. "
                "Point it at the service account JSON key file."
            )
        key_path = Path(key_path_raw)
        if not key_path.is_absolute():
            # Resolve relative to project root so the env value
            # "credentials/service_account.json" works from any cwd.
            key_path = PROJECT_ROOT / key_path
        if not key_path.exists():
            raise FileNotFoundError(
                f"Service account key not found: {key_path}. "
                "Download it from GCP → IAM → Service Accounts → Keys."
            )
        _client = gspread.service_account(filename=str(key_path))
        logger.info("gspread client authenticated via %s", key_path)
        return _client
    except (ValueError, FileNotFoundError):
        raise
    except Exception as exc:
        logger.error("Failed to authenticate gspread client: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Workbook access
# ---------------------------------------------------------------------------

def open_workbook(spreadsheet_id: str) -> gspread.Spreadsheet:
    """Open and return a Spreadsheet by ID.

    Raises:
        gspread.exceptions.SpreadsheetNotFound: if not found or not shared.
        gspread.exceptions.APIError: on transient API errors.
    """
    try:
        client = get_client()
        spreadsheet = client.open_by_key(spreadsheet_id)
        logger.info("Opened workbook: %s (%s)", spreadsheet.title, spreadsheet_id)
        return spreadsheet
    except gspread.exceptions.SpreadsheetNotFound:
        logger.error(
            "Spreadsheet not found: %s. "
            "Verify the ID and that the service account has Editor access.",
            spreadsheet_id,
        )
        raise
    except Exception as exc:
        logger.error("Failed to open workbook %s: %s", spreadsheet_id, exc)
        raise


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def ensure_workbook_initialized(
    spreadsheet: gspread.Spreadsheet,
    visible_tabs: list[str],
    column_headers: list[str],
) -> None:
    """Create missing tabs and write headers row 1; also create/hide _meta tab
    and create/move Summary tab to position 0.

    Idempotent: existing tabs and existing headers in row 1 are not touched.

    Args:
        spreadsheet: Open gspread Spreadsheet object.
        visible_tabs: List of tab names to ensure exist (e.g. ["PM", "AI PM"]).
        column_headers: Column header strings to write in row 1 of each tab.
    """
    try:
        existing_titles = {ws.title for ws in spreadsheet.worksheets()}

        # Ensure each visible tab exists with headers
        for tab_name in visible_tabs:
            if tab_name not in existing_titles:
                logger.info("Creating tab: %s", tab_name)
                ws = spreadsheet.add_worksheet(
                    title=tab_name, rows=200, cols=len(column_headers) or 14
                )
                _write_headers(ws, column_headers)
            else:
                # Tab exists — check if row 1 is empty; write headers only if it is
                ws = spreadsheet.worksheet(tab_name)
                existing_row1 = ws.row_values(1)
                if not existing_row1:
                    _write_headers(ws, column_headers)
                    logger.info("Wrote headers to existing empty tab: %s", tab_name)
                else:
                    logger.debug("Tab %s already has headers — skipping.", tab_name)

        # Ensure _meta tab exists and is hidden
        if "_meta" not in existing_titles:
            logger.info("Creating hidden _meta tab")
            meta_ws = spreadsheet.add_worksheet(title="_meta", rows=10, cols=2)
            _hide_worksheet(meta_ws)
        else:
            logger.debug("_meta tab already exists.")

        # Ensure Summary tab exists at position 0 (first/default tab on open)
        ensure_summary_tab(spreadsheet)

        # Clean up the default "Sheet1" if Google Drive created one and it's untouched
        _delete_default_sheet1(spreadsheet, visible_tabs)

    except Exception as exc:
        logger.error("ensure_workbook_initialized failed: %s", exc)
        raise


def _delete_default_sheet1(spreadsheet: gspread.Spreadsheet, visible_tabs: list[str]) -> None:
    """Delete Google Drive's default 'Sheet1' tab if it exists, has no data, and isn't
    one of our intended visible tabs. Best-effort; failures are logged and ignored."""
    try:
        for ws in spreadsheet.worksheets():
            if ws.title != "Sheet1":
                continue
            if "Sheet1" in visible_tabs:
                return  # user intentionally wants it
            vals = ws.get_all_values()
            non_empty = any(any(cell.strip() for cell in row) for row in vals)
            if non_empty:
                logger.debug("Default Sheet1 has data — keeping.")
                return
            logger.info("Deleting empty default Sheet1.")
            spreadsheet.del_worksheet(ws)
            return
    except Exception as exc:  # noqa: BLE001 — non-fatal cleanup
        logger.warning("Could not delete default Sheet1: %s", exc)


def ensure_summary_tab(spreadsheet: gspread.Spreadsheet) -> gspread.Worksheet:
    """Create the Summary tab if missing and move it to index 0 so it opens by default."""
    titles = {ws.title: ws for ws in spreadsheet.worksheets()}
    if "Summary" in titles:
        ws = titles["Summary"]
        logger.debug("Summary tab already exists.")
    else:
        logger.info("Creating Summary tab")
        ws = spreadsheet.add_worksheet(title="Summary", rows=50, cols=6)
    # Move to position 0 (does no harm if already there)
    try:
        spreadsheet.batch_update({"requests": [{
            "updateSheetProperties": {
                "properties": {"sheetId": ws.id, "index": 0},
                "fields": "index",
            }
        }]})
    except Exception as exc:  # noqa: BLE001 — non-fatal; tab still works at any index
        logger.warning("Could not move Summary tab to index 0: %s", exc)
    return ws


_HISTORY_TAB = "_history"
_HISTORY_HEADER = ["Date", "Total", "Discovered", "Per-tab JSON"]
HISTORY_MAX_ROWS = 90  # ~3 months of daily runs; SPARKLINE in Summary shows last 30


def ensure_history_tab(spreadsheet: gspread.Spreadsheet) -> gspread.Worksheet:
    """Create a hidden _history tab with header row, if absent. Returns the worksheet."""
    titles = {ws.title: ws for ws in spreadsheet.worksheets()}
    if _HISTORY_TAB in titles:
        return titles[_HISTORY_TAB]
    logger.info("Creating hidden %s tab", _HISTORY_TAB)
    ws = spreadsheet.add_worksheet(title=_HISTORY_TAB, rows=200, cols=4)
    ws.update(values=[_HISTORY_HEADER], range_name="A1", value_input_option="RAW")
    _hide_worksheet(ws)
    return ws


def append_history(
    spreadsheet: gspread.Spreadsheet,
    run_at_iso: str,
    total: int,
    discovered: int,
    write_counts: dict[str, int],
) -> None:
    """Append one row to the _history tab and trim to the last HISTORY_MAX_ROWS.
    Per-tab counts go in column D as JSON so the schema doesn't depend on tab list."""
    import json as _json
    ws = ensure_history_tab(spreadsheet)
    ws.append_row(
        [run_at_iso, str(total), str(discovered), _json.dumps(write_counts)],
        value_input_option="RAW",
    )
    try:
        # Read current row count and trim if over cap (1 header + N data rows)
        n = len(ws.col_values(1))
        if n > HISTORY_MAX_ROWS + 1:
            # Delete oldest data rows so only header + last HISTORY_MAX_ROWS remain
            rows_to_delete = n - (HISTORY_MAX_ROWS + 1)
            ws.delete_rows(2, 2 + rows_to_delete - 1)
            logger.info("Trimmed %d old rows from %s", rows_to_delete, _HISTORY_TAB)
    except Exception as exc:  # noqa: BLE001 — trim is best-effort
        logger.warning("Could not trim %s: %s", _HISTORY_TAB, exc)


def read_history(spreadsheet: gspread.Spreadsheet, limit: int = 14) -> list[dict]:
    """Read the last `limit` rows of the _history tab. Newest first.
    Returns list of {date, total, discovered, per_tab (dict)}."""
    import json as _json
    titles = {ws.title for ws in spreadsheet.worksheets()}
    if _HISTORY_TAB not in titles:
        return []
    try:
        ws = spreadsheet.worksheet(_HISTORY_TAB)
        rows = ws.get_all_values()
    except Exception as exc:  # noqa: BLE001 — non-fatal
        logger.warning("Could not read %s: %s", _HISTORY_TAB, exc)
        return []
    out: list[dict] = []
    for row in rows[1:]:  # skip header
        if not row or not row[0]:
            continue
        try:
            per_tab = _json.loads(row[3]) if len(row) > 3 and row[3] else {}
        except (_json.JSONDecodeError, ValueError):
            per_tab = {}
        out.append({
            "date":       row[0],
            "total":      int(row[1]) if len(row) > 1 and row[1].isdigit() else 0,
            "discovered": int(row[2]) if len(row) > 2 and row[2].isdigit() else 0,
            "per_tab":    per_tab,
        })
    out.reverse()  # newest first
    return out[:limit]


def write_summary(
    spreadsheet: gspread.Spreadsheet,
    visible_tabs: list[str],
    write_counts: dict[str, int],
    run_at_iso: str,
    recent_runs: list[dict] | None = None,
) -> None:
    """Render an intuitive dashboard into the Summary tab.

    Args:
        spreadsheet: open gspread spreadsheet
        visible_tabs: list of tab names in display order (excluding Summary/_meta)
        write_counts: dict {tab_name: jobs_added_in_last_run}
        run_at_iso: ISO timestamp of the run that just finished
        recent_runs: optional list of {date, total_added, errors} dicts (newest first),
            shown in a small history section. Pass [] or None to skip the history.
    """
    ws = ensure_summary_tab(spreadsheet)

    # Query current row counts per tab so "Total jobs" reflects the live sheet
    totals: dict[str, int] = {}
    for tab in visible_tabs:
        try:
            tab_ws = spreadsheet.worksheet(tab)
            # row count excluding header row
            vals = tab_ws.get_all_values()
            totals[tab] = max(0, len(vals) - 1)
        except Exception:  # noqa: BLE001 — missing tab → 0
            totals[tab] = 0

    total_added = sum(int(v) for v in write_counts.values())
    total_jobs = sum(totals.values())

    # SPARKLINE formula: 30-day trend of "Total" column in _history.
    # OFFSET picks the last 30 data rows (skips header); SPARKLINE plots them.
    # If _history has fewer rows, SPARKLINE gracefully shows what's there.
    sparkline_formula = (
        '=IFERROR('
        'SPARKLINE('
        'OFFSET(_history!B2, MAX(0, COUNTA(_history!B:B)-31), 0, MIN(30, COUNTA(_history!B:B)-1), 1),'
        '{"charttype","line";"linewidth",2;"color","#1a73e8"}'
        '), "")'
    )

    rows: list[list[str]] = [
        ["JOB SEARCH DASHBOARD", "", "", "", "", ""],
        [f"Last updated: {run_at_iso}", "", "", "", "", ""],
        [f"Last run added: {total_added} new jobs", "30-day trend:", sparkline_formula, "", "", ""],
        ["", "", "", "", "", ""],
        ["Tab", "Total jobs", "Added in last run", "Open tab", "", ""],
    ]
    workbook_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}/edit"
    for tab in visible_tabs:
        # Use HYPERLINK formula so the user can click straight into each tab
        tab_link = f'=HYPERLINK("{workbook_url}#gid={spreadsheet.worksheet(tab).id}", "Open {tab}")'
        rows.append([tab, str(totals.get(tab, 0)), str(write_counts.get(tab, 0)), tab_link, "", ""])
    rows.append(["TOTAL", str(total_jobs), str(total_added), "", "", ""])

    # Recent runs: read from _history tab (persistent across cloud runs).
    # Caller may still pass recent_runs explicitly (used by tests + back-compat).
    history = recent_runs
    if history is None:
        try:
            history = read_history(spreadsheet, limit=14)
        except Exception as exc:  # noqa: BLE001 — non-fatal
            logger.warning("Could not read _history for Summary: %s", exc)
            history = []
    if history:
        rows.append(["", "", "", "", "", ""])
        rows.append(["Recent runs (last 14)", "", "", "", "", ""])
        rows.append(["Date", "New jobs", "Discovered", "", "", ""])
        for r in history[:14]:
            # Accept both schemas: from read_history ({date,total,discovered,per_tab})
            # and from legacy recent_runs ({date,total_added,discovered,...})
            date = r.get("date", "")
            total = r.get("total", r.get("total_added", ""))
            disc = r.get("discovered", "")
            rows.append([str(date), str(total), str(disc), "", "", ""])

    # Clear existing content first so old rows beyond new content don't linger
    try:
        ws.clear()
    except Exception as exc:  # noqa: BLE001 — clear is best-effort
        logger.warning("Could not clear Summary before write: %s", exc)

    # Write with USER_ENTERED so HYPERLINK formulas evaluate
    end_col = chr(ord("A") + len(rows[0]) - 1)
    ws.update(
        values=rows,
        range_name=f"A1:{end_col}{len(rows)}",
        value_input_option="USER_ENTERED",
    )
    logger.info("write_summary: wrote %d rows to Summary tab", len(rows))


def _write_headers(ws: gspread.Worksheet, column_headers: list[str]) -> None:
    """Write column_headers to row 1 of worksheet."""
    ws.update("A1", [column_headers], value_input_option="RAW")


def _hide_worksheet(ws: gspread.Worksheet) -> None:
    """Hide a worksheet via a batchUpdate sheetProperties request."""
    try:
        ws.spreadsheet.batch_update(
            {
                "requests": [
                    {
                        "updateSheetProperties": {
                            "properties": {
                                "sheetId": ws.id,
                                "hidden": True,
                            },
                            "fields": "hidden",
                        }
                    }
                ]
            }
        )
    except Exception as exc:
        logger.warning("Could not hide worksheet %s: %s", ws.title, exc)
        # Non-fatal — the tab just won't be hidden


# ---------------------------------------------------------------------------
# _meta idempotency
# ---------------------------------------------------------------------------

def read_meta_last_run_at(spreadsheet: gspread.Spreadsheet) -> "datetime | None":
    """Read the last-run timestamp from _meta!A1.

    Returns:
        datetime (timezone-aware UTC) if A1 contains a parseable ISO string;
        None if empty, missing, or unparseable (caller should treat as epoch zero).
    """
    try:
        meta_ws = spreadsheet.worksheet("_meta")
        val = meta_ws.acell("A1").value
        if not val:
            return None
        dt = datetime.fromisoformat(val)
        # Ensure timezone-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except gspread.exceptions.WorksheetNotFound:
        logger.warning("_meta tab not found; treating as first run.")
        return None
    except (ValueError, TypeError) as exc:
        logger.warning("Could not parse _meta!A1 as ISO datetime (%s); treating as first run.", exc)
        return None
    except Exception as exc:
        logger.error("read_meta_last_run_at failed: %s", exc)
        raise


def write_meta_last_run_at(spreadsheet: gspread.Spreadsheet, when: datetime) -> None:
    """Write an ISO 8601 timestamp to _meta!A1.

    Args:
        spreadsheet: Open gspread Spreadsheet.
        when: The datetime to write (will be serialised as ISO string).
    """
    try:
        meta_ws = spreadsheet.worksheet("_meta")
        meta_ws.update("A1", [[when.isoformat()]], value_input_option="RAW")
        logger.info("Updated _meta!A1 to %s", when.isoformat())
    except Exception as exc:
        logger.error("write_meta_last_run_at failed: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Read tab
# ---------------------------------------------------------------------------

def read_tab(
    spreadsheet: gspread.Spreadsheet,
    tab_name: str,
) -> "tuple[dict[str, dict], list[list[str]]]":
    """Read a visible tab and separate script rows from user-added rows.

    Args:
        spreadsheet: Open gspread Spreadsheet.
        tab_name: Name of the tab to read.

    Returns:
        A tuple of:
        - carry_forward_map: dict mapping dedup_hash -> {"first_seen": str,
          "status": str, "notes": str, "also_seen_on": list[str]}.
          Keys are the values in column A (index 0).
          Rows with an empty column A are excluded from this map.
        - user_added_rows: list of raw row lists (list[str]) for rows where
          column A is empty (manually added by the user). Order-preserved.

    Raises:
        gspread.exceptions.WorksheetNotFound: if the tab doesn't exist.
    """
    try:
        ws = spreadsheet.worksheet(tab_name)
        all_values = ws.get_all_values()
    except gspread.exceptions.WorksheetNotFound:
        logger.warning("Tab %s not found; returning empty state.", tab_name)
        return {}, []
    except Exception as exc:
        logger.error("read_tab(%s) failed: %s", tab_name, exc)
        raise

    try:
        carry_forward_map: dict[str, dict] = {}
        user_added_rows: list[list[str]] = []

        if not all_values:
            return carry_forward_map, user_added_rows

        # Row 0 is the header row — skip it
        # Column indices (0-based):
        #   0 = _id (dedup_hash)  A
        #   1 = First Seen        B
        #   10 = Also Seen On     K  (index 10)
        #   12 = Status           M  (index 12)
        #   13 = Notes            N  (index 13)
        _IDX_HASH = 0
        _IDX_FIRST_SEEN = 1
        _IDX_ALSO_SEEN = 10
        _IDX_STATUS = 12
        _IDX_NOTES = 13

        for row in all_values[1:]:  # skip header
            # Pad short rows so index access doesn't raise
            padded = row + [""] * max(0, 14 - len(row))
            dedup_hash = padded[_IDX_HASH].strip()
            if not dedup_hash:
                # User-added row (no hash in col A)
                user_added_rows.append(row)
            else:
                also_seen_raw = padded[_IDX_ALSO_SEEN].strip()
                also_seen_list = (
                    [b.strip() for b in also_seen_raw.split(",") if b.strip()]
                    if also_seen_raw
                    else []
                )
                carry_forward_map[dedup_hash] = {
                    "first_seen": padded[_IDX_FIRST_SEEN].strip(),
                    "status": padded[_IDX_STATUS].strip(),
                    "notes": padded[_IDX_NOTES].strip(),
                    "also_seen_on": also_seen_list,
                }

        logger.info(
            "read_tab(%s): %d script rows, %d user-added rows",
            tab_name,
            len(carry_forward_map),
            len(user_added_rows),
        )
        return carry_forward_map, user_added_rows

    except Exception as exc:
        logger.error("read_tab(%s) parsing failed: %s", tab_name, exc)
        raise


# ---------------------------------------------------------------------------
# Write tab
# ---------------------------------------------------------------------------

@_retry_on_api_error
def write_tab(
    spreadsheet: gspread.Spreadsheet,
    tab_name: str,
    column_headers: list[str],
    computed_rows: list[list[str]],
    user_added_rows: list[list[str]],
    status_dropdown_values: list[str],
) -> None:
    """Batch-write a title tab: headers + computed rows + user-added rows.

    Steps:
    1. Compose the full values matrix (headers + computed + user rows).
    2. Push the matrix via a single worksheet.update call.
    3. Follow-up batch_update to:
       (a) hide column A (col 0, the dedup_hash),
       (b) set data-validation dropdown on the Status column (M, col index 12),
       (c) freeze row 1.

    Args:
        spreadsheet: Open gspread Spreadsheet.
        tab_name: Tab to write.
        column_headers: Header row values (len must match column count).
        computed_rows: Script-generated rows (sorted newest-first, hash in col 0).
        user_added_rows: Rows preserved from previous read where col A was empty.
        status_dropdown_values: Allowed values for the Status dropdown
            (e.g. ["New","Applied","Saved","Skip","Interview","Rejected"]).
    """
    try:
        ws = spreadsheet.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        logger.warning("Tab %s not found during write; creating it.", tab_name)
        ws = spreadsheet.add_worksheet(
            title=tab_name, rows=200, cols=len(column_headers) or 14
        )

    try:
        # ------------------------------------------------------------------
        # Step 1: compose the full values matrix
        # ------------------------------------------------------------------
        all_rows: list[list[str]] = [column_headers] + computed_rows + user_added_rows
        n_cols = len(column_headers)
        # Pad / truncate each row to n_cols so gspread doesn't misalign columns
        normalized: list[list[str]] = [
            (row + [""] * max(0, n_cols - len(row)))[:n_cols]
            for row in all_rows
        ]

        # ------------------------------------------------------------------
        # Step 2: single batch values write
        # ------------------------------------------------------------------
        # Clear the sheet first so stale rows below the new batch are removed
        ws.clear()
        ws.update("A1", normalized, value_input_option="USER_ENTERED")
        logger.info(
            "write_tab(%s): wrote %d header + %d computed + %d user rows",
            tab_name,
            1,
            len(computed_rows),
            len(user_added_rows),
        )

        # ------------------------------------------------------------------
        # Step 3: structural follow-up batch_update
        # ------------------------------------------------------------------
        sheet_id = ws.id

        requests: list[dict] = []

        # (a) hide column A (index 0)
        requests.append(
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 0,
                        "endIndex": 1,
                    },
                    "properties": {"hiddenByUser": True},
                    "fields": "hiddenByUser",
                }
            }
        )

        # (b) Status column (M = index 12) data validation
        if status_dropdown_values:
            requests.append(
                _build_dropdown_validation_request(
                    sheet_id=sheet_id,
                    col_index=12,  # M
                    start_row_index=1,  # skip header
                    values=status_dropdown_values,
                )
            )

        # (c) freeze row 1
        requests.append(
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            }
        )

        spreadsheet.batch_update({"requests": requests})
        logger.info("write_tab(%s): structural batch_update complete.", tab_name)

    except Exception as exc:
        logger.error("write_tab(%s) failed: %s", tab_name, exc)
        raise


def _build_dropdown_validation_request(
    sheet_id: int,
    col_index: int,
    start_row_index: int,
    values: list[str],
) -> dict:
    """Build a setDataValidation request for a one-of-list dropdown."""
    return {
        "setDataValidation": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": start_row_index,
                "endRowIndex": 10000,  # covers all data rows generously
                "startColumnIndex": col_index,
                "endColumnIndex": col_index + 1,
            },
            "rule": {
                "condition": {
                    "type": "ONE_OF_LIST",
                    "values": [{"userEnteredValue": v} for v in values],
                },
                "showCustomUi": True,
                "strict": False,  # allow free-text; show warning, don't block
            },
        }
    }


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Google Sheets writer smoke test. Validates service-account auth and lists tabs.",
    )
    parser.add_argument(
        "--spreadsheet-id",
        metavar="ID",
        default=os.environ.get("SHEETS_SPREADSHEET_ID", ""),
        help="Spreadsheet ID to open (defaults to SHEETS_SPREADSHEET_ID env var).",
    )
    args = parser.parse_args()

    spreadsheet_id = args.spreadsheet_id.strip()
    if not spreadsheet_id:
        print("[--MISSING] SHEETS_SPREADSHEET_ID")
        sys.exit(1)

    try:
        spreadsheet = open_workbook(spreadsheet_id)
        tab_names = [ws.title for ws in spreadsheet.worksheets()]
        print(f"[OK] Opened '{spreadsheet.title}' — {len(tab_names)} tab(s):")
        for name in tab_names:
            print(f"  • {name}")
    except Exception as exc:
        print(f"[FAIL] Could not open workbook: {exc}")
        sys.exit(1)
