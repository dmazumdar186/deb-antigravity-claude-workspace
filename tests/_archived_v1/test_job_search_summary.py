"""
Unit tests for write_summary, ensure_summary_tab, _delete_default_sheet1,
and _load_recent_runs.

All tests mock gspread heavily — NO live API calls.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from execution.google.google_sheets_writer import (  # noqa: E402
    ensure_summary_tab,
    write_summary,
    _delete_default_sheet1,
    ensure_history_tab,
    append_history,
    read_history,
)
from execution.personal_workflows.job_search_sheet import _load_recent_runs  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ws(title: str, values: list[list[str]] | None = None, sheet_id: int = 1):
    ws = MagicMock()
    ws.title = title
    ws.id = sheet_id
    ws.get_all_values.return_value = values or []
    return ws


def _make_sp(worksheets: list, sheet_id: str = "SHEET_ID_X"):
    sp = MagicMock()
    sp.id = sheet_id
    sp.worksheets.return_value = worksheets
    sp.worksheet.side_effect = lambda name: next(w for w in worksheets if w.title == name)
    new_ws = _make_ws("__new__")
    sp.add_worksheet.return_value = new_ws
    return sp, new_ws


# ---------------------------------------------------------------------------
# ensure_summary_tab
# ---------------------------------------------------------------------------

def test_ensure_summary_tab_creates_when_absent():
    sp, new_ws = _make_sp([])
    ws = ensure_summary_tab(sp)
    sp.add_worksheet.assert_called_once_with(title="Summary", rows=50, cols=6)
    assert ws is new_ws


def test_ensure_summary_tab_reuses_existing():
    existing = _make_ws("Summary", sheet_id=42)
    sp, _ = _make_sp([existing])
    ws = ensure_summary_tab(sp)
    sp.add_worksheet.assert_not_called()
    assert ws is existing


def test_ensure_summary_tab_moves_to_index_0():
    sp, new_ws = _make_sp([])
    ensure_summary_tab(sp)
    # batch_update must be called with an updateSheetProperties index=0 request
    sp.batch_update.assert_called_once()
    body = sp.batch_update.call_args[0][0]
    req = body["requests"][0]["updateSheetProperties"]
    assert req["properties"]["index"] == 0
    assert req["fields"] == "index"


# ---------------------------------------------------------------------------
# _delete_default_sheet1
# ---------------------------------------------------------------------------

def test_delete_default_sheet1_when_empty():
    sheet1 = _make_ws("Sheet1", [])
    pm = _make_ws("PM", [["_id", "First Seen"]])
    sp, _ = _make_sp([sheet1, pm])
    _delete_default_sheet1(sp, ["PM", "AI PM"])
    sp.del_worksheet.assert_called_once_with(sheet1)


def test_delete_default_sheet1_keeps_when_has_data():
    sheet1 = _make_ws("Sheet1", [["hello", "world"]])
    sp, _ = _make_sp([sheet1])
    _delete_default_sheet1(sp, ["PM"])
    sp.del_worksheet.assert_not_called()


def test_delete_default_sheet1_keeps_when_in_visible_tabs():
    """If user intentionally has 'Sheet1' as a visible tab name, do NOT delete it."""
    sheet1 = _make_ws("Sheet1", [])
    sp, _ = _make_sp([sheet1])
    _delete_default_sheet1(sp, ["Sheet1", "PM"])
    sp.del_worksheet.assert_not_called()


def test_delete_default_sheet1_noop_when_absent():
    pm = _make_ws("PM")
    sp, _ = _make_sp([pm])
    _delete_default_sheet1(sp, ["PM"])
    sp.del_worksheet.assert_not_called()


# ---------------------------------------------------------------------------
# write_summary
# ---------------------------------------------------------------------------

@pytest.fixture
def summary_workbook():
    summary = _make_ws("Summary", sheet_id=0)
    pm = _make_ws("PM", [["_id"] + [""] * 13] + [["x"] * 14] * 5, sheet_id=10)  # 5 data rows
    ai_pm = _make_ws("AI PM", [["_id"] + [""] * 13] + [["x"] * 14] * 2, sheet_id=20)  # 2 data rows
    sp, _ = _make_sp([summary, pm, ai_pm], sheet_id="SID_TEST")
    return sp, summary


def test_write_summary_writes_header_and_per_tab(summary_workbook):
    sp, summary = summary_workbook
    write_summary(
        sp,
        visible_tabs=["PM", "AI PM"],
        write_counts={"PM": 3, "AI PM": 1},
        run_at_iso="2026-06-09 18:00 UTC",
        recent_runs=[],  # explicitly skip history to keep this test focused on the dashboard
    )
    # Summary tab gets a single .update call with USER_ENTERED
    assert summary.update.call_count == 1
    kwargs = summary.update.call_args.kwargs
    rows = kwargs["values"]
    # Title + 'last updated' + 'last run added/sparkline' + blank + header + 2 data + TOTAL = 8 rows minimum
    assert len(rows) >= 8
    assert rows[0][0].startswith("JOB SEARCH DASHBOARD")
    assert "2026-06-09 18:00 UTC" in rows[1][0]
    # Sparkline row: col B labels it, col C holds the formula
    assert rows[2][1] == "30-day trend:"
    assert rows[2][2].startswith("=IFERROR(SPARKLINE("), f"Expected SPARKLINE formula, got: {rows[2][2]!r}"
    # Per-tab row data
    pm_row = next(r for r in rows if r[0] == "PM")
    assert pm_row[1] == "5"  # total
    assert pm_row[2] == "3"  # added
    ai_pm_row = next(r for r in rows if r[0] == "AI PM")
    assert ai_pm_row[1] == "2"
    assert ai_pm_row[2] == "1"
    # TOTAL row
    total_row = next(r for r in rows if r[0] == "TOTAL")
    assert total_row[1] == "7"   # 5 + 2
    assert total_row[2] == "4"   # 3 + 1


def test_write_summary_uses_user_entered_for_hyperlinks(summary_workbook):
    sp, summary = summary_workbook
    write_summary(sp, ["PM", "AI PM"], {"PM": 1, "AI PM": 0}, "2026-06-09", recent_runs=[])
    assert summary.update.call_args.kwargs.get("value_input_option") == "USER_ENTERED"
    rows = summary.update.call_args.kwargs["values"]
    # HYPERLINK formula in column D (index 3)
    hyperlink_rows = [r for r in rows if r[0] in ("PM", "AI PM")]
    for r in hyperlink_rows:
        assert r[3].startswith("=HYPERLINK("), f"Expected HYPERLINK formula in col D, got: {r[3]!r}"
        assert "spreadsheets/d/SID_TEST" in r[3]


def test_write_summary_clears_before_writing(summary_workbook):
    sp, summary = summary_workbook
    write_summary(sp, ["PM"], {"PM": 1}, "2026-06-09", recent_runs=[])
    summary.clear.assert_called_once()


def test_write_summary_with_recent_runs(summary_workbook):
    sp, summary = summary_workbook
    recent = [
        {"date": "2026-06-09", "total_added": 124, "discovered": 205},
        {"date": "2026-06-08", "total_added": 80, "discovered": 150},
    ]
    write_summary(sp, ["PM"], {"PM": 124}, "2026-06-09", recent_runs=recent)
    rows = summary.update.call_args.kwargs["values"]
    # Recent runs section header now reads "Recent runs (last 14)"
    recent_header_idx = next(i for i, r in enumerate(rows) if r[0].startswith("Recent runs"))
    # data_idx = header + column-headers + first data
    data_idx = recent_header_idx + 2
    assert rows[data_idx][0] == "2026-06-09"
    assert rows[data_idx][1] == "124"


# ---------------------------------------------------------------------------
# ensure_history_tab / append_history / read_history
# ---------------------------------------------------------------------------

def test_ensure_history_tab_creates_hidden_when_absent():
    sp, new_ws = _make_sp([])
    ws = ensure_history_tab(sp)
    sp.add_worksheet.assert_called_once_with(title="_history", rows=200, cols=4)
    # Header row written
    new_ws.update.assert_called_once()
    assert "Date" in new_ws.update.call_args.kwargs.get("values", [[]])[0]
    # Hidden via the new worksheet's spreadsheet.batch_update (per _hide_worksheet impl)
    assert new_ws.spreadsheet.batch_update.called
    assert ws is new_ws


def test_ensure_history_tab_reuses_existing():
    existing = _make_ws("_history", sheet_id=99)
    sp, _ = _make_sp([existing])
    ws = ensure_history_tab(sp)
    sp.add_worksheet.assert_not_called()
    assert ws is existing


def test_append_history_writes_row():
    existing = _make_ws("_history", [["Date","Total","Discovered","Per-tab JSON"]] + [["2026-06-08","50","100","{}"]])
    sp, _ = _make_sp([existing])
    append_history(sp, "2026-06-09", total=124, discovered=205,
                   write_counts={"PM": 89, "AI PM": 26})
    existing.append_row.assert_called_once()
    args, kwargs = existing.append_row.call_args
    row = args[0]
    assert row[0] == "2026-06-09"
    assert row[1] == "124"
    assert row[2] == "205"
    assert '"PM": 89' in row[3]
    assert '"AI PM": 26' in row[3]


def test_append_history_trims_above_cap():
    """When the _history tab has more than HISTORY_MAX_ROWS+1 rows, oldest get deleted."""
    from execution.google.google_sheets_writer import HISTORY_MAX_ROWS
    existing = _make_ws("_history")
    # Simulate col_values returning more rows than the cap
    existing.col_values.return_value = ["Date"] + [f"2026-06-{i:02d}" for i in range(1, HISTORY_MAX_ROWS + 5)]
    sp, _ = _make_sp([existing])
    append_history(sp, "2026-06-09", total=1, discovered=1, write_counts={})
    existing.delete_rows.assert_called_once()
    # Args: start_row=2, end_row=2+extra-1 (3 rows to delete in this fixture)
    args = existing.delete_rows.call_args.args
    assert args[0] == 2  # always trim from row 2 (after header)


def test_read_history_returns_newest_first():
    rows = [
        ["Date", "Total", "Discovered", "Per-tab JSON"],
        ["2026-06-07", "50", "100", '{"PM": 50}'],
        ["2026-06-08", "75", "150", '{"PM": 60, "AI PM": 15}'],
        ["2026-06-09", "120", "200", '{"PM": 100, "AI PM": 20}'],
    ]
    ws = _make_ws("_history", rows)
    sp, _ = _make_sp([ws])
    out = read_history(sp, limit=5)
    assert len(out) == 3
    assert out[0]["date"] == "2026-06-09"
    assert out[0]["total"] == 120
    assert out[0]["per_tab"] == {"PM": 100, "AI PM": 20}
    assert out[2]["date"] == "2026-06-07"


def test_read_history_returns_empty_when_tab_absent():
    sp, _ = _make_sp([])  # no _history tab
    out = read_history(sp, limit=10)
    assert out == []


def test_read_history_tolerates_malformed_per_tab_json():
    rows = [
        ["Date", "Total", "Discovered", "Per-tab JSON"],
        ["2026-06-09", "50", "100", "{not valid json}"],
    ]
    ws = _make_ws("_history", rows)
    sp, _ = _make_sp([ws])
    out = read_history(sp, limit=5)
    assert len(out) == 1
    assert out[0]["per_tab"] == {}  # gracefully degraded


def test_read_history_respects_limit():
    rows = [["Date", "Total", "Discovered", "Per-tab JSON"]]
    for i in range(1, 25):
        rows.append([f"2026-05-{i:02d}", str(i), str(i*5), "{}"])
    ws = _make_ws("_history", rows)
    sp, _ = _make_sp([ws])
    out = read_history(sp, limit=10)
    assert len(out) == 10
    assert out[0]["date"] == "2026-05-24"  # newest


def test_write_summary_falls_back_to_history_tab(summary_workbook):
    """If recent_runs is None (default), Summary reads from _history tab."""
    sp, summary = summary_workbook
    # Add a populated _history tab to the workbook
    history_ws = _make_ws("_history", [
        ["Date", "Total", "Discovered", "Per-tab JSON"],
        ["2026-06-09", "47", "50", '{"PM": 46, "AI PM": 1}'],
    ])
    sp.worksheets.return_value = list(sp.worksheets.return_value) + [history_ws]
    sp.worksheet.side_effect = lambda name: next(
        w for w in sp.worksheets.return_value if w.title == name
    )
    write_summary(sp, ["PM"], {"PM": 47}, "2026-06-09")  # no recent_runs arg
    rows = summary.update.call_args.kwargs["values"]
    history_section = [r for r in rows if r[0] == "2026-06-09" and r[1] == "47"]
    assert len(history_section) == 1, f"Expected history row from _history tab in Summary; got: {rows}"


# ---------------------------------------------------------------------------
# _load_recent_runs
# ---------------------------------------------------------------------------

def test_load_recent_runs_missing_file_returns_empty():
    out = _load_recent_runs(Path("/no/such/file"), limit=5)
    assert out == []


def test_load_recent_runs_parses_and_reverses(tmp_path: Path):
    log = tmp_path / "runs.jsonl"
    rows = [
        {"run_at": "2026-06-07T10:00:00Z", "written_per_tab": {"PM": 5}, "discovered": 20,
         "after_keyword_filter": 10, "after_dedup": 5},
        {"run_at": "2026-06-08T10:00:00Z", "written_per_tab": {"PM": 7, "AI PM": 2}, "discovered": 30,
         "after_keyword_filter": 15, "after_dedup": 9},
        {"run_at": "2026-06-09T10:00:00Z", "written_per_tab": {"PM": 10}, "discovered": 40,
         "after_keyword_filter": 20, "after_dedup": 10},
    ]
    log.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    out = _load_recent_runs(log, limit=5)
    assert len(out) == 3
    assert out[0]["date"] == "2026-06-09"
    assert out[0]["total_added"] == 10
    assert out[1]["date"] == "2026-06-08"
    assert out[1]["total_added"] == 9  # 7+2
    assert out[2]["date"] == "2026-06-07"


def test_load_recent_runs_skips_malformed_lines(tmp_path: Path):
    log = tmp_path / "runs.jsonl"
    log.write_text(
        "this is not json\n"
        + json.dumps({"run_at": "2026-06-09T10:00:00Z",
                      "written_per_tab": {"PM": 1},
                      "discovered": 5}) + "\n"
        + "{not_valid_json,}\n",
        encoding="utf-8",
    )
    out = _load_recent_runs(log)
    assert len(out) == 1
    assert out[0]["date"] == "2026-06-09"


def test_load_recent_runs_respects_limit(tmp_path: Path):
    log = tmp_path / "runs.jsonl"
    lines = [
        json.dumps({"run_at": f"2026-06-{i:02d}T10:00:00Z",
                    "written_per_tab": {"PM": i}, "discovered": i, "after_dedup": i})
        for i in range(1, 25)
    ]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out = _load_recent_runs(log, limit=10)
    assert len(out) == 10
