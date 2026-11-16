"""2026-11-16: a zero-candidate run must never blank the Top Matches tab.

It rebuilds from the role tabs (recent open rows by Fit /5); if those yield
nothing it leaves the previous tab untouched.
"""

from datetime import date
from unittest import mock

import pytest

from execution.personal_workflows.job_search_v2.notifier import sheet

HEADER = [
    "Company",
    "Title",
    "Location",
    "Contract",
    "Link",
    "Posted",
    "Verified",
    "Fit /5",
]
TODAY = date(2026, 11, 16)


def _row(title, link, fit, verified="open · posted 2026-11-15 · checked 2026-11-15"):
    return ["Acme", title, "Paris", "CDI", link, "2026-11-15", verified, fit]


def test_selector_keeps_recent_open_scored_rows_sorted_by_fit():
    tabs = {
        "PM": [
            HEADER,
            _row("PM low", "https://x/1", "3"),
            _row("PM high", "https://x/2", "5"),
            _row(
                "PM closed",
                "https://x/3",
                "5",
                verified="closed · posted 2026-11-15 · checked 2026-11-16",
            ),
            _row(
                "PM stale",
                "https://x/4",
                "5",
                verified="open · posted 2026-10-01 · checked 2026-10-01",
            ),
            _row("PM unscored", "https://x/5", ""),
        ],
        "PO": [
            HEADER,
            _row("PO mid", "https://x/6", "4"),
            _row("PM high dup", "https://x/2", "5"),
        ],  # same link -> deduped
    }
    out = sheet.select_top_from_role_rows(tabs, today=TODAY)
    assert [r["Title"] for r in out] == ["PM high", "PO mid", "PM low"]
    assert [r["Rank"] for r in out] == ["1", "2", "3"]
    assert out[1]["Source Tab"] == "PO"
    assert all(r["Fit"] == "" for r in out)  # tier not guessed


def test_selector_respects_top_n():
    tabs = {"PM": [HEADER] + [_row(f"t{i}", f"https://x/{i}", "4") for i in range(40)]}
    assert len(sheet.select_top_from_role_rows(tabs, today=TODAY, top_n=25)) == 25


def _fake_sp(role_values):
    ws_role = mock.Mock()
    ws_role.get_all_values.return_value = role_values
    ws_top = mock.Mock(row_count=100)
    sp = mock.Mock()
    sp.worksheet.side_effect = lambda t: (
        ws_top if t == sheet.TOP_MATCHES_TAB else ws_role
    )
    return sp, ws_top


def test_zero_candidates_with_no_usable_rows_writes_nothing():
    pytest.importorskip("gspread")
    sp, ws_top = _fake_sp([HEADER])
    with mock.patch.object(
        sheet, "_open_sheet", return_value=(sp, None)
    ), mock.patch.object(sheet, "_discover_role_tabs", return_value=["PM"]):
        n, ok = sheet.refresh_top_matches([], ranked_by_hash={}, dry_run=False)
    assert (n, ok) == (0, True)
    ws_top.batch_clear.assert_not_called()  # previous rows survive
    ws_top.update.assert_not_called()


def test_zero_candidates_rebuilds_from_role_tabs():
    pytest.importorskip("gspread")
    sp, ws_top = _fake_sp(
        [
            HEADER,
            _row(
                "Senior PM",
                "https://x/9",
                "4",
                verified=f"open · posted {date.today()} · checked {date.today()}",
            ),
        ]
    )
    with mock.patch.object(
        sheet, "_open_sheet", return_value=(sp, None)
    ), mock.patch.object(
        sheet, "_discover_role_tabs", return_value=["PM"]
    ), mock.patch.object(
        sheet,
        "_ensure_headers",
        return_value={h: i + 1 for i, h in enumerate(sheet.TOP_MATCHES_HEADERS)},
    ), mock.patch.object(
        sheet, "_read_header_map", return_value={"Fit": 1}
    ):
        n, ok = sheet.refresh_top_matches([], ranked_by_hash={}, dry_run=False)
    assert (n, ok) == (1, True)
    written = ws_top.update.call_args.kwargs["values"]
    assert "Senior PM" in written[0] and "https://x/9" in written[0]


def test_with_candidates_still_opens_sheet():
    """Positive control: a run WITH candidates must still reach the sheet."""
    job = mock.Mock(content_hash="h1")
    ranked = mock.Mock(score=0.9)
    ranked.tier.value = "A"
    with mock.patch.object(
        sheet, "_open_sheet", return_value=(None, "no creds")
    ) as opener:
        n, ok = sheet.refresh_top_matches(
            [job], ranked_by_hash={"h1": ranked}, dry_run=False
        )
    opener.assert_called_once()
    assert (n, ok) == (0, False)
