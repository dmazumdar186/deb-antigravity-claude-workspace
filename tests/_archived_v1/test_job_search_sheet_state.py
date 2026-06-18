"""
Tests for Google Sheets state preservation logic in google_sheets_writer.py.

All tests mock gspread heavily — NO live API calls are made.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution.google.google_sheets_writer import (  # noqa: E402
    ensure_workbook_initialized,
    read_tab,
    write_tab,
    read_meta_last_run_at,
    write_meta_last_run_at,
)


# ---------------------------------------------------------------------------
# Helpers: build a fake worksheet and spreadsheet
# ---------------------------------------------------------------------------


def _make_worksheet(title: str, values: list[list[str]] | None = None) -> MagicMock:
    """Create a mock gspread Worksheet."""
    ws = MagicMock()
    ws.title = title
    ws.id = hash(title) % 100000
    ws.get_all_values.return_value = values or []
    ws.row_values.return_value = values[0] if values else []
    ws.acell.return_value.value = None
    ws.spreadsheet = MagicMock()  # needed for batch_update calls
    return ws


def _make_spreadsheet(worksheets: list[MagicMock]) -> MagicMock:
    """Create a mock gspread Spreadsheet with the given worksheets."""
    sp = MagicMock()
    sp.worksheets.return_value = worksheets
    _ws_map = {ws.title: ws for ws in worksheets}

    def _worksheet(name: str) -> MagicMock:
        if name not in _ws_map:
            import gspread

            raise gspread.exceptions.WorksheetNotFound(name)
        return _ws_map[name]

    def _add_worksheet(title: str, rows: int = 200, cols: int = 14) -> MagicMock:
        new_ws = _make_worksheet(title)
        _ws_map[title] = new_ws
        worksheets.append(new_ws)
        return new_ws

    sp.worksheet.side_effect = _worksheet
    sp.add_worksheet.side_effect = _add_worksheet
    sp.batch_update.return_value = {}
    return sp


VISIBLE_TABS = ["PM", "AI PM", "AI Automation", "AI Mobile", "AI Process", "AI Consultant"]
COLUMN_HEADERS = [
    "_id", "First Seen", "Posted", "Company", "Title", "Country",
    "Location", "Remote?", "Contract", "Source", "Also Seen On",
    "Link", "Status", "Notes",
]
STATUS_DROPDOWN = ["New", "Applied", "Saved", "Skip", "Interview", "Rejected"]


# ---------------------------------------------------------------------------
# Test: ensure_workbook_initialized on empty sheet
# ---------------------------------------------------------------------------


def test_ensure_workbook_initialized_empty_sheet():
    """On a completely empty workbook, all 6 visible tabs + _meta + Summary must be created."""
    sp = _make_spreadsheet([])  # no worksheets

    ensure_workbook_initialized(sp, VISIBLE_TABS, COLUMN_HEADERS)

    # 8 tabs should have been created: 6 visible + _meta + Summary
    assert sp.add_worksheet.call_count == 8, (
        f"Expected 8 add_worksheet calls (6 visible + _meta + Summary), got {sp.add_worksheet.call_count}"
    )
    created_titles = [c.kwargs.get("title") or c.args[0] for c in sp.add_worksheet.call_args_list]
    assert "Summary" in created_titles, f"Summary tab must be created. Got: {created_titles}"


def test_ensure_workbook_initialized_partial_sheet():
    """Only missing tabs are created when some already exist."""
    existing_pm = _make_worksheet("PM", [COLUMN_HEADERS])  # already has headers
    existing_meta = _make_worksheet("_meta")
    sp = _make_spreadsheet([existing_pm, existing_meta])

    ensure_workbook_initialized(sp, VISIBLE_TABS, COLUMN_HEADERS)

    created_titles = [c.kwargs.get("title") or c.args[0] for c in sp.add_worksheet.call_args_list]
    # PM and _meta already exist → should NOT be in created_titles
    assert "PM" not in created_titles
    assert "_meta" not in created_titles
    # Remaining 5 visible tabs must be created
    for tab in VISIBLE_TABS:
        if tab != "PM":
            assert tab in created_titles, f"Expected tab '{tab}' to be created."


# ---------------------------------------------------------------------------
# Test: read_tab — script rows vs user-added rows
# ---------------------------------------------------------------------------


def test_read_tab_returns_carry_forward_and_user_rows():
    """read_tab must separate script rows (col-A has hash) from user rows (col-A empty)."""
    # 14 columns per plan
    script_row = [
        "abc123hash",          # A: _id
        "2026-06-07",          # B: First Seen
        "2026-06-07",          # C: Posted
        "Mistral AI",          # D: Company
        "Senior PM",           # E: Title
        "FR",                  # F: Country
        "Paris",               # G: Location
        "No",                  # H: Remote?
        "CDI",                 # I: Contract
        "adzuna",              # J: Source
        "jooble",              # K: Also Seen On
        "https://adzuna.fr/1", # L: Link
        "Applied",             # M: Status
        "Interesting role",    # N: Notes
    ]
    user_row = [
        "",                    # A: empty → user-added row
        "2026-06-05",
        "2026-06-05",
        "My Dream Company",
        "Head of Product",
        "FR",
        "Paris",
        "Hybrid",
        "CDI",
        "manual",
        "",
        "https://example.com",
        "Saved",
        "Applied directly",
    ]

    ws = _make_worksheet("PM", [COLUMN_HEADERS, script_row, user_row])
    sp = _make_spreadsheet([ws])

    carry_forward, user_added = read_tab(sp, "PM")

    assert "abc123hash" in carry_forward
    entry = carry_forward["abc123hash"]
    assert entry["first_seen"] == "2026-06-07"
    assert entry["status"] == "Applied"
    assert entry["notes"] == "Interesting role"
    assert "jooble" in entry["also_seen_on"]

    assert len(user_added) == 1
    assert user_added[0][3] == "My Dream Company"


def test_read_tab_empty_sheet_returns_empty_maps():
    """An empty tab returns empty carry_forward_map and user_added_rows."""
    ws = _make_worksheet("PM", [])
    sp = _make_spreadsheet([ws])

    cf, ur = read_tab(sp, "PM")
    assert cf == {}
    assert ur == []


def test_read_tab_only_header_row():
    """Tab with only a header row returns empty maps."""
    ws = _make_worksheet("PM", [COLUMN_HEADERS])
    sp = _make_spreadsheet([ws])

    cf, ur = read_tab(sp, "PM")
    assert cf == {}
    assert ur == []


# ---------------------------------------------------------------------------
# Test: write_tab column order and user rows
# ---------------------------------------------------------------------------


def test_write_tab_column_order():
    """write_tab must write: [headers] + [computed_rows] + [user_added_rows]."""
    ws = _make_worksheet("PM")
    sp = _make_spreadsheet([ws])

    computed = [
        ["hash1", "2026-06-09", "2026-06-07", "CompA", "Senior PM", "FR",
         "Paris", "No", "CDI", "adzuna", "", "https://a.com", "New", ""],
    ]
    user_added = [
        ["", "2026-06-01", "", "Manual Co", "Head of PM", "FR",
         "Paris", "Hybrid", "", "manual", "", "https://b.com", "Saved", "applied"],
    ]

    write_tab(sp, "PM", COLUMN_HEADERS, computed, user_added, STATUS_DROPDOWN)

    # ws.update should have been called with the composed matrix
    ws.update.assert_called_once()
    call_args = ws.update.call_args
    written_matrix = call_args.args[1] if call_args.args else call_args.kwargs.get("values", [])

    # Row 0 = headers, row 1 = computed, row 2 = user
    assert written_matrix[0] == COLUMN_HEADERS
    assert written_matrix[1][0] == "hash1"       # _id of computed row
    assert written_matrix[2][0] == ""            # empty _id = user-added row
    assert written_matrix[2][3] == "Manual Co"


def test_write_tab_no_user_rows():
    """write_tab with no user rows must write exactly headers + computed."""
    ws = _make_worksheet("PM")
    sp = _make_spreadsheet([ws])

    computed = [
        ["h1", "2026-06-09", "", "Co", "PM", "FR", "Paris", "No", "CDI",
         "adzuna", "", "https://x.com", "New", ""],
    ]
    write_tab(sp, "PM", COLUMN_HEADERS, computed, [], STATUS_DROPDOWN)

    ws.update.assert_called_once()
    written = ws.update.call_args.args[1]
    assert len(written) == 2  # header + 1 computed


# ---------------------------------------------------------------------------
# Test: read_meta_last_run_at
# ---------------------------------------------------------------------------


def test_read_meta_last_run_at_empty_returns_none():
    """Empty _meta!A1 must return None."""
    meta_ws = _make_worksheet("_meta")
    meta_ws.acell.return_value.value = None
    sp = _make_spreadsheet([meta_ws])

    result = read_meta_last_run_at(sp)
    assert result is None


def test_read_meta_last_run_at_parses_iso():
    """A valid ISO string in _meta!A1 must return a timezone-aware datetime."""
    meta_ws = _make_worksheet("_meta")
    meta_ws.acell.return_value.value = "2026-06-08T07:00:00+00:00"
    sp = _make_spreadsheet([meta_ws])

    result = read_meta_last_run_at(sp)
    assert result is not None
    assert result.year == 2026
    assert result.month == 6
    assert result.day == 8
    assert result.tzinfo is not None


def test_read_meta_last_run_at_unparseable_returns_none():
    """A non-ISO value in _meta!A1 returns None (treat as first run)."""
    meta_ws = _make_worksheet("_meta")
    meta_ws.acell.return_value.value = "not-a-date"
    sp = _make_spreadsheet([meta_ws])

    result = read_meta_last_run_at(sp)
    assert result is None


# ---------------------------------------------------------------------------
# Test: write_meta_last_run_at
# ---------------------------------------------------------------------------


def test_write_meta_last_run_at_writes_iso():
    """write_meta_last_run_at must call worksheet.update with the ISO string."""
    meta_ws = _make_worksheet("_meta")
    sp = _make_spreadsheet([meta_ws])

    when = datetime(2026, 6, 9, 7, 0, 0, tzinfo=timezone.utc)
    write_meta_last_run_at(sp, when)

    meta_ws.update.assert_called_once()
    written_value = meta_ws.update.call_args.args[1]
    assert "2026-06-09" in str(written_value)
