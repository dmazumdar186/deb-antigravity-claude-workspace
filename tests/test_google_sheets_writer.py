"""Tests for execution/google/google_sheets_writer.py.

Covers the surfaces NOT already exercised by test_job_search_sheet_state:
  - write_top_matches: atomic single-update semantics (no clear+update race)
  - write_top_matches: row-padding so trailing rows from prior writes vanish
  - write_top_matches: empty-state writes informational row, not empty sheet
  - _is_retriable: retry predicate behaviour on each status code class

All gspread Worksheet / Spreadsheet objects are mocked.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

WORKSPACE = Path(__file__).resolve().parents[1]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from execution.google import google_sheets_writer as mod  # noqa: E402


# ----------------------------------------------------------------------------
# _is_retriable predicate
# ----------------------------------------------------------------------------

def _api_err(status_code):
    # gspread APIError(self, response: requests.Response); we bypass __init__
    # so we don't need a real Response object.
    err = mod.APIError.__new__(mod.APIError)
    err.response = SimpleNamespace(status_code=status_code)
    return err


def test_is_retriable_429():
    assert mod._is_retriable(_api_err(429)) is True


def test_is_retriable_500():
    assert mod._is_retriable(_api_err(500)) is True


def test_is_retriable_503():
    assert mod._is_retriable(_api_err(503)) is True


def test_is_retriable_400_not_retriable():
    assert mod._is_retriable(_api_err(400)) is False


def test_is_retriable_403_not_retriable():
    assert mod._is_retriable(_api_err(403)) is False


def test_is_retriable_non_api_error():
    assert mod._is_retriable(ValueError("oops")) is False


def test_is_retriable_api_error_without_response():
    err = mod.APIError.__new__(mod.APIError)
    # No response attribute set → not retriable
    assert mod._is_retriable(err) is False


# ----------------------------------------------------------------------------
# write_top_matches — atomic single update
# ----------------------------------------------------------------------------

def _mock_ws(prev_row_count: int) -> MagicMock:
    ws = MagicMock()
    ws.row_count = prev_row_count
    return ws


def _mock_spreadsheet_with_ws(ws):
    ss = MagicMock()
    # ensure_top_matches_tab walks spreadsheet.worksheets() looking for the tab.
    fake = MagicMock()
    fake.title = mod._TOP_MATCHES_TAB if hasattr(mod, "_TOP_MATCHES_TAB") else "Top Matches"
    # Bind ws to the worksheets list so ensure_top_matches_tab returns it.
    ws.title = fake.title
    ss.worksheets.return_value = [ws]
    return ss


def test_write_top_matches_makes_one_update_call(monkeypatch):
    """clear+update was the race. We now make ONE update call only — no clear()."""
    ws = _mock_ws(prev_row_count=200)
    monkeypatch.setattr(mod, "ensure_top_matches_tab", lambda _ss: ws)
    mod.write_top_matches(MagicMock(), [["1", "A", "x", "T", "Co", "L", "C", "S", "W", "L"]])
    # Exactly one update call
    assert ws.update.call_count == 1
    # No separate clear() call (the audit gap)
    ws.clear.assert_not_called()


def test_write_top_matches_pads_to_prev_row_count(monkeypatch):
    """If the previous sheet had 200 rows and we only have 3 to write, we still write 200
    rows so trailing data from prior runs is blanked atomically."""
    ws = _mock_ws(prev_row_count=200)
    monkeypatch.setattr(mod, "ensure_top_matches_tab", lambda _ss: ws)
    new_rows = [["r1"] * len(mod._TOP_MATCHES_HEADER)]
    mod.write_top_matches(MagicMock(), new_rows)
    call_kwargs = ws.update.call_args.kwargs
    values = call_kwargs["values"]
    # header + 1 data row + padding to 200
    assert len(values) == 200
    # Trailing rows are blank
    assert all(cell == "" for cell in values[-1])


def test_write_top_matches_writes_empty_state_when_no_rows(monkeypatch):
    ws = _mock_ws(prev_row_count=0)
    monkeypatch.setattr(mod, "ensure_top_matches_tab", lambda _ss: ws)
    mod.write_top_matches(MagicMock(), [])
    call_kwargs = ws.update.call_args.kwargs
    values = call_kwargs["values"]
    # Header row + empty-state row (no padding when prev_row_count == 0).
    assert values[0] == mod._TOP_MATCHES_HEADER
    assert mod._TOP_MATCHES_EMPTY_STATE in values[1]


def test_write_top_matches_uses_user_entered_for_hyperlinks(monkeypatch):
    ws = _mock_ws(prev_row_count=0)
    monkeypatch.setattr(mod, "ensure_top_matches_tab", lambda _ss: ws)
    mod.write_top_matches(MagicMock(), [["1"] * len(mod._TOP_MATCHES_HEADER)])
    call_kwargs = ws.update.call_args.kwargs
    # USER_ENTERED so HYPERLINK() formulas evaluate
    assert call_kwargs["value_input_option"] == "USER_ENTERED"


def test_write_top_matches_normalises_row_widths(monkeypatch):
    """Short rows get padded to header width; long rows get truncated."""
    ws = _mock_ws(prev_row_count=0)
    monkeypatch.setattr(mod, "ensure_top_matches_tab", lambda _ss: ws)
    short = ["only", "two"]
    long = ["x"] * (len(mod._TOP_MATCHES_HEADER) + 5)
    mod.write_top_matches(MagicMock(), [short, long])
    values = ws.update.call_args.kwargs["values"]
    # All rows now exactly len(header) wide
    n_cols = len(mod._TOP_MATCHES_HEADER)
    for row in values:
        assert len(row) == n_cols
