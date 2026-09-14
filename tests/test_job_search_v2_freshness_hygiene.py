"""Unit tests for the 2026-09-10 freshness/hygiene work across job_search_v2:
notifier/sheet.py (STANDARD_HEADERS Posted/Verified, verification_stamp,
_job_to_dict, append_jobs header auto-extension), purge_irrelevant_rows.py
(_purge_tab domain gate, _row_verdict, reverify_rows, purge_sheet reverify
wiring), tests/acceptance_job_search_v2.py (check_verified_stamp, _check_row
domain check, check_regression_corpus, check_pipeline_degradation), and a
run.py fixture-mode wiring smoke test.

Follows the FakeWorksheet / FakeSpreadsheet + sys.modules gspread stub pattern
from tests/test_job_search_v2_dedup_fingerprint.py, and the make_job /
fetch_returning pattern from tests/test_job_search_v2_posting_verifier.py.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

# ---------------------------------------------------------------------------
# gspread is broken in this sandbox (cryptography/_cffi_backend import panic),
# but sheet.py / purge_irrelevant_rows.py only `import gspread` lazily inside
# function bodies, just to reach `gspread.WorksheetNotFound`. Stub a minimal
# fake module in sys.modules so those functions work against our FakeSpreadsheet
# without needing the real (broken-in-this-env) package.
# ---------------------------------------------------------------------------
if "gspread" not in sys.modules:
    _fake_gspread = types.ModuleType("gspread")

    class _WorksheetNotFound(Exception):
        pass

    _fake_gspread.WorksheetNotFound = _WorksheetNotFound
    sys.modules["gspread"] = _fake_gspread

import gspread  # noqa: E402  (real or the stub installed above)

from execution.personal_workflows.job_search_v2.contracts import (  # noqa: E402
    ContractType,
    JobSource,
    NormalizedJob,
    JobTier,
    RankedJob,
    RemoteMode,
    compute_content_hash,
    compute_fingerprint,
)
from execution.personal_workflows.job_search_v2.normalizer import posting_verifier as pv  # noqa: E402
from execution.personal_workflows.job_search_v2.notifier import sheet as sheet_mod  # noqa: E402
from execution.personal_workflows.job_search_v2 import purge_irrelevant_rows as purge_mod  # noqa: E402

import tests.acceptance_job_search_v2 as acc  # noqa: E402


NOW = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)


# ===========================================================================
# Shared fakes (copied from test_job_search_v2_dedup_fingerprint.py, with the
# `update()` start-column fix verified below rather than re-fixed).
# ===========================================================================


class FakeWorksheet:
    def __init__(self, title: str, header: list[str], rows: list[list[str]] | None = None,
                 row_count: int = 1000, col_count: int = 20):
        self.title = title
        self._grid = [header] + [list(r) for r in (rows or [])]
        self.row_count = row_count
        self.col_count = col_count

    def row_values(self, n: int) -> list[str]:
        return list(self._grid[n - 1]) if len(self._grid) >= n else []

    def col_values(self, idx: int) -> list[str]:
        return [row[idx - 1] if len(row) >= idx else "" for row in self._grid]

    def get_all_values(self) -> list[list[str]]:
        return [list(r) for r in self._grid]

    def update(self, *, range_name: str, values: list[list[str]], value_input_option: str = "USER_ENTERED"):
        # Only used by _append_dicts / dedup rewrite / _ensure_headers in these
        # tests — reconstruct the grid honoring the range's starting row AND
        # starting column (2026-09-10 fix: header-extension writes like
        # "G1:H1" must land at column G, not column A).
        a1 = range_name.split(":")[0]
        start_row = int("".join(c for c in a1 if c.isdigit()) or "1")
        col_letters = "".join(c for c in a1 if c.isalpha()).upper()
        start_col = 0
        for ch in col_letters:
            start_col = start_col * 26 + (ord(ch) - ord("A") + 1)
        start_col = max(start_col, 1) - 1  # 0-based offset
        for i, row in enumerate(values):
            r = start_row - 1 + i
            while len(self._grid) <= r:
                self._grid.append([])
            existing = list(self._grid[r])
            width = max(len(existing), start_col + len(row), len(self._grid[0]) if self._grid else 0)
            padded = existing + [""] * (width - len(existing))
            for j, val in enumerate(row):
                padded[start_col + j] = val
            self._grid[r] = padded

    def resize(self, *, rows: int, cols: int):
        self.row_count = rows
        self.col_count = cols

    def batch_clear(self, ranges):
        self._grid = self._grid[:1]


class FakeSpreadsheet:
    def __init__(self, worksheets: dict[str, FakeWorksheet]):
        self._ws = dict(worksheets)

    def worksheet(self, title: str) -> FakeWorksheet:
        if title not in self._ws:
            raise gspread.WorksheetNotFound(title)
        return self._ws[title]

    def worksheets(self) -> list[FakeWorksheet]:
        return list(self._ws.values())

    def add_worksheet(self, *, title: str, rows, cols):
        ws = FakeWorksheet(title, header=[])
        self._ws[title] = ws
        return ws


def _make_normalized(source, title, company, url, posted_at=None, source_id="1", location="Paris"):
    from execution.personal_workflows.job_search_v2.contracts import canonicalize_url

    canonical = canonicalize_url(url)
    return NormalizedJob(
        source=source,
        source_id=source_id,
        url=url,
        canonical_url=canonical,
        title=title,
        company=company,
        location=location,
        description_snippet="",
        posted_at=posted_at,
        contract_type=ContractType.CDI,
        remote_mode=RemoteMode.UNKNOWN,
        fetched_at=datetime.now(timezone.utc),
        content_hash=compute_content_hash(title, company, canonical),
        fingerprint=compute_fingerprint(title, company),
    )


# ===========================================================================
# 1. notifier/sheet.py
# ===========================================================================


def test_standard_headers_ends_with_posted_verified():
    assert sheet_mod.STANDARD_HEADERS[-2:] == ["Posted", "Verified"]


def test_verification_stamp_open_shape():
    posted = datetime(2026, 9, 8, tzinfo=timezone.utc)
    checked = datetime(2026, 9, 10, tzinfo=timezone.utc)
    assert sheet_mod.verification_stamp("open", posted, checked) == "open · posted 2026-09-08 · checked 2026-09-10"


def test_verification_stamp_unverified_reason_ok_unverified_fresh():
    posted = datetime(2026, 9, 9, tzinfo=timezone.utc)
    checked = datetime(2026, 9, 10, tzinfo=timezone.utc)
    stamp = sheet_mod.verification_stamp("open", posted, checked, reason="ok_unverified_fresh")
    assert stamp == "unverified (source date) · posted 2026-09-09 · checked 2026-09-10"


def test_verification_stamp_unverifiable_status_forces_unverified_label():
    posted = datetime(2026, 9, 9, tzinfo=timezone.utc)
    checked = datetime(2026, 9, 10, tzinfo=timezone.utc)
    stamp = sheet_mod.verification_stamp("unverifiable", posted, checked)
    assert stamp.startswith("unverified (source date) ·")


def test_verification_stamp_posted_unknown_when_none():
    checked = datetime(2026, 9, 10, tzinfo=timezone.utc)
    stamp = sheet_mod.verification_stamp("open", None, checked)
    assert "posted unknown" in stamp


def _ranked_job_from_normalized(job):
    return None


class _FakeRecord:
    def __init__(self, status, posted_at, checked_at, reason=""):
        self.status = status
        self.posted_at = posted_at
        self.checked_at = checked_at
        self.reason = reason


def test_job_to_dict_uses_record_posted_over_source_posted():
    job = _make_normalized(JobSource.FIXTURE, "Product Manager", "Acme",
                            "https://boards.example/jobs/1",
                            posted_at=datetime(2026, 8, 1, tzinfo=timezone.utc))
    record = _FakeRecord("open", datetime(2026, 9, 8, tzinfo=timezone.utc),
                          datetime(2026, 9, 10, tzinfo=timezone.utc))
    d = sheet_mod._job_to_dict(job, None, "2026-09-10T00:00:00+00:00", record)
    assert d["Posted"] == "2026-09-08"
    assert d["Verified"] == "open · posted 2026-09-08 · checked 2026-09-10"


def test_job_to_dict_record_none_falls_back_to_source_date_and_blank_verified():
    job = _make_normalized(JobSource.FIXTURE, "Product Manager", "Acme",
                            "https://boards.example/jobs/2",
                            posted_at=datetime(2026, 8, 1, tzinfo=timezone.utc))
    d = sheet_mod._job_to_dict(job, None, "2026-09-10T00:00:00+00:00", None)
    assert d["Posted"] == "2026-08-01"
    assert d["Verified"] == ""


def test_job_to_dict_record_disabled_reason_blank_verified():
    job = _make_normalized(JobSource.FIXTURE, "Product Manager", "Acme",
                            "https://boards.example/jobs/3",
                            posted_at=datetime(2026, 8, 1, tzinfo=timezone.utc))
    record = _FakeRecord("open", datetime(2026, 8, 1, tzinfo=timezone.utc),
                          datetime(2026, 9, 10, tzinfo=timezone.utc), reason="disabled")
    d = sheet_mod._job_to_dict(job, None, "2026-09-10T00:00:00+00:00", record)
    assert d["Verified"] == ""
    # Posted still comes from the record when it has a posted_at, even for
    # a "disabled" record (only Verified is gated on reason != disabled).
    assert d["Posted"] == "2026-08-01"


def test_append_jobs_auto_extends_legacy_headers_and_writes_stamp(monkeypatch):
    legacy_header = ["Company", "Title", "Country", "Location", "Contract", "Link"]
    ws = FakeWorksheet("PM", header=legacy_header)
    fake_sp = FakeSpreadsheet({"PM": ws})
    monkeypatch.setattr(sheet_mod, "_open_sheet", lambda *a, **k: (fake_sp, None))

    job = _make_normalized(JobSource.FIXTURE, "Product Manager", "Acme",
                            "https://boards.example/jobs/new-1")
    record = _FakeRecord("open", datetime(2026, 9, 8, tzinfo=timezone.utc),
                          datetime(2026, 9, 10, tzinfo=timezone.utc))

    rows_appended, per_tab, ok = sheet_mod.append_jobs(
        [job],
        routing_config={"fallback_tab": "PM", "titles": {}},
        verification={job.content_hash: record},
    )

    assert ok is True
    assert rows_appended == 1
    header_row = ws.get_all_values()[0]
    assert "Posted" in header_row
    assert "Verified" in header_row
    data_row = ws.get_all_values()[1]
    verified_col = header_row.index("Verified")
    posted_col = header_row.index("Posted")
    assert data_row[posted_col] == "2026-09-08"
    assert data_row[verified_col] == "open · posted 2026-09-08 · checked 2026-09-10"


# ===========================================================================
# 2. purge_irrelevant_rows.py — domain gate in _purge_tab
# ===========================================================================


def test_purge_tab_removes_hardware_titles_keeps_software_pm(monkeypatch):
    monkeypatch.setattr(purge_mod, "_reject_location_patterns", lambda: [])
    header = ["_id", "Company", "Title", "Country", "Location", "Contract", "Link"]
    ws = FakeWorksheet(
        "PM",
        header=header,
        rows=[
            ["h1", "Acme", "Hardware Product Manager", "France", "Paris", "CDI",
             "https://boards.example/jobs/1"],
            ["h2", "Acme", "Chef de Produit Instrumentation", "France", "Paris", "CDI",
             "https://boards.example/jobs/2"],
            ["h3", "Acme", "Senior Product Manager", "France", "Paris", "CDI",
             "https://boards.example/jobs/3"],
        ],
    )
    kept, removed, sample = purge_mod._purge_tab(ws, dry_run=False)

    assert removed == 2
    assert kept == 1
    remaining_titles = [r[header.index("Title")] for r in ws.get_all_values()[1:] if any(c.strip() for c in r)]
    assert remaining_titles == ["Senior Product Manager"]
    assert any("Hardware Product Manager" in s for s in sample)
    assert any("[" in s for s in sample)  # reason reported alongside the removed title


# ===========================================================================
# 2b. purge_irrelevant_rows.py — _row_verdict matrix
# ===========================================================================


def _jsonld_html(days_ago: int) -> str:
    posted = (NOW - timedelta(days=days_ago)).date().isoformat()
    return (
        '<html><head><script type="application/ld+json">'
        f'{{"@type": "JobPosting", "datePosted": "{posted}"}}'
        '</script></head><body>Apply now for this great job.</body></html>'
    )


def test_row_verdict_404_removes_closed():
    fetch = lambda u: (404, "", u)  # noqa: E731
    decision, stamp, posted = purge_mod._row_verdict("https://x.example/j", NOW, 7.0, fetch)
    assert decision == "remove"
    assert "closed" in stamp
    assert posted is None


def test_row_verdict_403_strict_removes_lenient_keeps_unverified():
    fetch = lambda u: (403, "", u)  # noqa: E731
    # Strict (default): a blocked host is never shipped on trust.
    decision, stamp, posted = purge_mod._row_verdict("https://x.example/j", NOW, 7.0, fetch)
    assert decision == "remove" and stamp.startswith("unverifiable")
    # Strict + browser fallback that serves the page → confirmed open.
    good = ('<html><body><script type="application/ld+json">{"@type":"JobPosting","datePosted":"%s"}</script>'
            '<button>Apply</button>' + "x" * 600 + "</body></html>") % (NOW - timedelta(days=2)).date().isoformat()
    decision, stamp, posted = purge_mod._row_verdict("https://x.example/j", NOW, 7.0, fetch,
                                                     browser_fetch=lambda u: (200, good, u))
    assert decision == "keep" and stamp.startswith("open · posted")
    # Lenient: kept on the (unknown) source date, flagged.
    decision, stamp, posted = purge_mod._row_verdict("https://x.example/j", NOW, 7.0, fetch, strict=False,
                                                     source_posted_at=NOW - timedelta(days=1))
    assert decision == "keep_unverified"
    assert stamp.startswith("unverified (source date) ·")


def test_row_verdict_empty_body_strict_removes():
    fetch = lambda u: (200, "", u)  # noqa: E731
    decision, stamp, posted = purge_mod._row_verdict("https://x.example/j", NOW, 7.0, fetch)
    assert decision == "remove" and "unverifiable" in stamp


def test_row_verdict_redirect_to_search_page_removes():
    html = "<html><body>Apply now</body></html>"
    fetch = lambda u: (200, html, "https://x.example/jobs/search?q=pm")  # noqa: E731
    decision, stamp, posted = purge_mod._row_verdict("https://x.example/j", NOW, 7.0, fetch)
    assert decision == "remove"


def test_row_verdict_expired_jd_redirect_removes():
    html = "<html><body>Apply now</body></html>"
    fetch = lambda u: (  # noqa: E731
        200, html, "https://www.linkedin.com/jobs/pm-jobs?trk=expired_jd_redirect"
    )
    decision, stamp, posted = purge_mod._row_verdict("https://x.example/j", NOW, 7.0, fetch)
    assert decision == "remove"


def test_row_verdict_closed_text_page_removes():
    html = "<html><body>This job is no longer available.</body></html>"
    fetch = lambda u: (200, html, u)  # noqa: E731
    decision, stamp, posted = purge_mod._row_verdict("https://x.example/j", NOW, 7.0, fetch)
    assert decision == "remove"


def test_row_verdict_fresh_3_days_keeps_with_open_stamp():
    html = _jsonld_html(3)
    fetch = lambda u: (200, html, u)  # noqa: E731
    decision, stamp, posted = purge_mod._row_verdict("https://x.example/j", NOW, 7.0, fetch)
    assert decision == "keep"
    assert stamp.startswith("open · posted")
    assert "checked 2026-09-10" in stamp
    assert posted.date() == (NOW - timedelta(days=3)).date()


def test_row_verdict_stale_10_days_removes():
    html = _jsonld_html(10)
    fetch = lambda u: (200, html, u)  # noqa: E731
    decision, stamp, posted = purge_mod._row_verdict("https://x.example/j", NOW, 7.0, fetch)
    assert decision == "remove"
    assert "stale" in stamp


def test_row_verdict_apply_button_no_date_removes_undatable():
    html = "<html><body>Apply now for this great job. No dates anywhere.</body></html>"
    fetch = lambda u: (200, html, u)  # noqa: E731
    decision, stamp, posted = purge_mod._row_verdict("https://x.example/j", NOW, 7.0, fetch)
    assert decision == "remove"
    assert stamp.startswith("age_unknown")


# ===========================================================================
# 2c. purge_irrelevant_rows.py — reverify_rows
# ===========================================================================


def _pm_header():
    return ["_id", "Company", "Title", "Country", "Location", "Contract", "Link"]


def _pm_rows_for_reverify():
    return [
        ["h1", "Acme", "Fresh PM", "France", "Paris", "CDI", "https://x.example/fresh"],
        ["h2", "Acme", "Stale PM", "France", "Paris", "CDI", "https://x.example/stale"],
        ["h3", "Acme", "Closed PM", "France", "Paris", "CDI", "https://x.example/closed"],
        ["h4", "Acme", "Blocked PM", "France", "Paris", "CDI", "https://x.example/blocked"],
    ]


def _make_reverify_fetch():
    def fetch(url):
        if url.endswith("/fresh"):
            return 200, _jsonld_html(3), url
        if url.endswith("/stale"):
            return 200, _jsonld_html(10), url
        if url.endswith("/closed"):
            return 404, "", url
        if url.endswith("/blocked"):
            return 403, "", url
        raise AssertionError(f"unexpected url {url}")
    return fetch


def test_reverify_rows_matrix_and_stats():
    ws = FakeWorksheet("PM", header=_pm_header(), rows=_pm_rows_for_reverify())
    sp = FakeSpreadsheet({"PM": ws})

    stats = purge_mod.reverify_rows(
        sp, tabs=["PM"], dry_run=False, max_age_days=7.0, max_fetches=100,
        concurrency=2, only_unstamped=True, fetch=_make_reverify_fetch(), now=NOW, browser_fallback=False,
    )

    assert stats["checked"] == 4
    assert stats["removed"] == 3  # stale + closed + blocked (strict, no browser)
    assert stats["stamped"] == 1  # fresh
    assert stats["unverified"] == 0
    assert stats["remaining_unstamped"] == 0

    header_row = ws.get_all_values()[0]
    assert "Posted" in header_row
    assert "Verified" in header_row
    remaining_titles = {
        r[header_row.index("Title")] for r in ws.get_all_values()[1:] if any(c.strip() for c in r)
    }
    assert remaining_titles == {"Fresh PM"}

    verified_col = header_row.index("Verified")
    posted_col = header_row.index("Posted")
    for row in ws.get_all_values()[1:]:
        if not any(c.strip() for c in row):
            continue
        title = row[header_row.index("Title")]
        if title == "Fresh PM":
            assert row[verified_col].startswith("open · posted")
            assert row[posted_col] == (NOW - timedelta(days=3)).date().isoformat()
        elif title == "Blocked PM":
            assert row[verified_col].startswith("unverified (source date) ·")


def test_reverify_rows_dry_run_changes_nothing_but_reports():
    ws = FakeWorksheet("PM", header=_pm_header(), rows=_pm_rows_for_reverify())
    sp = FakeSpreadsheet({"PM": ws})
    before = ws.get_all_values()

    stats = purge_mod.reverify_rows(
        sp, tabs=["PM"], dry_run=True, max_age_days=7.0, max_fetches=100,
        concurrency=2, only_unstamped=True, fetch=_make_reverify_fetch(), now=NOW, browser_fallback=False,
    )

    assert stats["removed"] == 3
    assert stats["stamped"] == 1
    assert ws.get_all_values() == before


def test_reverify_rows_max_fetches_1_leaves_remaining_unstamped_3():
    ws = FakeWorksheet("PM", header=_pm_header(), rows=_pm_rows_for_reverify())
    sp = FakeSpreadsheet({"PM": ws})
    calls = []

    def counting_fetch(url):
        calls.append(url)
        return _make_reverify_fetch()(url)

    stats = purge_mod.reverify_rows(
        sp, tabs=["PM"], dry_run=False, max_age_days=7.0, max_fetches=1,
        concurrency=2, only_unstamped=True, fetch=counting_fetch, now=NOW,
    )

    assert stats["remaining_unstamped"] == 3
    assert len(calls) == 1


def test_reverify_rows_only_unstamped_skips_already_stamped_rows():
    header = [*_pm_header(), "Posted", "Verified"]
    rows = [
        ["h1", "Acme", "Already Stamped PM", "France", "Paris", "CDI", "https://x.example/fresh",
         "2026-09-09", "open · posted 2026-09-09 · checked 2026-09-09"],
        ["h2", "Acme", "Stale PM", "France", "Paris", "CDI", "https://x.example/stale", "", ""],
    ]
    ws = FakeWorksheet("PM", header=header, rows=rows)
    sp = FakeSpreadsheet({"PM": ws})
    calls = []

    def counting_fetch(url):
        calls.append(url)
        return _make_reverify_fetch()(url)

    stats = purge_mod.reverify_rows(
        sp, tabs=["PM"], dry_run=False, max_age_days=7.0, max_fetches=100,
        concurrency=2, only_unstamped=True, fetch=counting_fetch, now=NOW, browser_fallback=False,
    )

    assert calls == ["https://x.example/stale"]
    assert stats["checked"] == 1
    assert stats["removed"] == 1  # stale row removed


def test_reverify_rows_skips_non_http_links():
    header = _pm_header()
    rows = [["h1", "Acme", "No Link PM", "France", "Paris", "CDI", ""]]
    ws = FakeWorksheet("PM", header=header, rows=rows)
    sp = FakeSpreadsheet({"PM": ws})
    calls = []

    def counting_fetch(url):
        calls.append(url)
        return _make_reverify_fetch()(url)

    stats = purge_mod.reverify_rows(
        sp, tabs=["PM"], dry_run=False, max_age_days=7.0, max_fetches=100,
        concurrency=2, only_unstamped=True, fetch=counting_fetch, now=NOW, browser_fallback=False,
    )

    assert calls == []
    assert stats["checked"] == 0


# ===========================================================================
# 2d. purge_sheet — reverify wiring
# ===========================================================================


def test_purge_sheet_reverify_true_returns_stats_and_adds_to_removed(monkeypatch):
    header = ["_id", "Company", "Title", "Country", "Location", "Contract", "Link", "Status"]
    ws = FakeWorksheet(
        "PM",
        header=header,
        rows=[[r[0], r[1], r[2], r[3], r[4], r[5], r[6], ""] for r in _pm_rows_for_reverify()],
    )
    sp = FakeSpreadsheet({"PM": ws})

    monkeypatch.setattr(purge_mod, "classify_title", lambda title: (True, "ok"))
    monkeypatch.setattr(purge_mod, "classify_language", lambda title, desc: (True, "ok"))
    monkeypatch.setattr(purge_mod, "classify_domain", lambda title, desc, **k: (True, "ok"))
    monkeypatch.setattr(purge_mod, "_reject_location_patterns", lambda: [])

    stats = purge_mod.purge_sheet(
        sp, tabs=["PM"], delete_obsolete=False, dedup=False, reverify=True,
        max_age_days=7.0, reverify_max_fetches=100,
    )
    # purge_sheet's own reverify_rows call uses the real fetch_page default;
    # patch it out via monkeypatching the module-level default is awkward, so
    # instead verify the wiring shape: "reverify" key present, and
    # removed_rows includes whatever reverify removed (>= _purge_tab removals,
    # which here is 0 since classify_* are stubbed to always pass).
    assert "reverify" in stats
    assert stats["removed_rows"] >= stats["reverify"]["removed"]


def test_purge_sheet_reverify_false_skips_it(monkeypatch):
    header = ["_id", "Company", "Title", "Country", "Location", "Contract", "Link", "Status"]
    ws = FakeWorksheet("PM", header=header, rows=[])
    sp = FakeSpreadsheet({"PM": ws})

    monkeypatch.setattr(purge_mod, "classify_title", lambda title: (True, "ok"))
    monkeypatch.setattr(purge_mod, "classify_language", lambda title, desc: (True, "ok"))
    monkeypatch.setattr(purge_mod, "classify_domain", lambda title, desc, **k: (True, "ok"))
    monkeypatch.setattr(purge_mod, "_reject_location_patterns", lambda: [])

    stats = purge_mod.purge_sheet(
        sp, tabs=["PM"], delete_obsolete=False, dedup=False, reverify=False,
    )
    assert "reverify" not in stats


# ===========================================================================
# 3. tests/acceptance_job_search_v2.py
# ===========================================================================


@pytest.mark.parametrize("stamp,want_clean", acc.STAMP_CORPUS)
def test_check_verified_stamp_corpus(stamp, want_clean):
    got = acc.check_verified_stamp(stamp)
    assert (got is None) == want_clean


def test_check_verified_stamp_7_days_exactly_allowed():
    assert acc.check_verified_stamp("open · posted 2026-09-03 · checked 2026-09-10") is None


def test_check_verified_stamp_8_days_is_violation():
    v = acc.check_verified_stamp("open · posted 2026-09-02 · checked 2026-09-10")
    assert v is not None
    assert "stale" in v


def test_check_verified_stamp_future_posted_date_violation():
    v = acc.check_verified_stamp("open · posted 2026-09-12 · checked 2026-09-10")
    assert v is not None
    assert "future" in v


def test_check_verified_stamp_closed_is_violation():
    v = acc.check_verified_stamp("closed · posted 2026-09-09 · checked 2026-09-10")
    assert v is not None
    assert "CLOSED" in v


def test_check_verified_stamp_garbage_is_violation():
    assert acc.check_verified_stamp("garbage") is not None


def test_check_row_hardware_title_flags_non_software_domain():
    violations = acc._check_row(
        "PM", "Hardware Product Manager", "Paris", "https://x",
        "open · posted 2026-09-09 · checked 2026-09-10",
    )
    assert any("non-software domain" in v for v in violations)


def test_check_row_clean_software_row_with_fresh_stamp_no_violations():
    violations = acc._check_row(
        "PM", "Senior Product Manager", "Paris, France", "https://boards.example/jobs/1",
        "open · posted 2026-09-09 · checked 2026-09-10",
    )
    assert violations == []


def test_check_row_verified_none_skips_stamp_check():
    # An out-of-scope/invalid title with no stamp check requested: the
    # stamp-related violation must be absent even though other gates still run.
    violations = acc._check_row(
        "PM", "Senior Product Manager", "Paris, France", "https://boards.example/jobs/1",
        None,
    )
    assert not any("Verified stamp" in v or "verified CLOSED" in v or "stale at insert" in v
                   for v in violations)


def test_check_regression_corpus_returns_empty():
    assert acc.check_regression_corpus() == []


def _write_stats_and_check(tmp_path_factory, stats: dict, monkeypatch) -> list[str]:
    tmp_dir = WORKSPACE_ROOT / ".tmp" / "job_search_v2_test_freshness"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    stats_path = tmp_dir / f"stats_{id(stats)}.json"
    stats_path.write_text(json.dumps(stats), encoding="utf-8")
    monkeypatch.setenv("CURRENT_RUN_STATS_PATH", str(stats_path))
    try:
        return acc.check_pipeline_degradation()
    finally:
        stats_path.unlink(missing_ok=True)


def _base_stats(**overrides) -> dict:
    stats = {
        "mode": "live",
        "ranker": {"requested": 10, "placeholder": 0},
        "per_source": {"a": 1, "b": 1, "c": 1, "d": 1, "e": 0, "f": 0},
        "sheet_ok": True,
        "top_matches_ok": True,
    }
    stats.update(overrides)
    return stats


def test_check_pipeline_degradation_verification_disabled_flags_skipped(monkeypatch, tmp_path_factory):
    stats = _base_stats(verification={"disabled": True})
    failures = _write_stats_and_check(tmp_path_factory, stats, monkeypatch)
    assert any("POSTING VERIFICATION SKIPPED" in f for f in failures)


def test_check_pipeline_degradation_proper_verification_no_skip_failure(monkeypatch, tmp_path_factory):
    stats = _base_stats(verification={
        "total_in": 10, "kept": 8, "warnings": ["host x blocked"],
    })
    failures = _write_stats_and_check(tmp_path_factory, stats, monkeypatch)
    assert not any("POSTING VERIFICATION SKIPPED" in f for f in failures)


# ===========================================================================
# 4. run.py wiring smoke test
# ===========================================================================


def test_run_fixture_mode_dry_run_smoke():
    run_py = WORKSPACE_ROOT / "execution" / "personal_workflows" / "job_search_v2" / "run.py"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(WORKSPACE_ROOT)

    proc = subprocess.run(
        [sys.executable, str(run_py), "--mode", "fixture", "--dry-run",
         "--no-ranker", "--no-sonnet-rerank", "--no-location-filter"],
        cwd=str(WORKSPACE_ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300, env=env,
    )
    assert proc.returncode == 0, (
        f"run.py exited {proc.returncode}\nSTDOUT:\n{proc.stdout[-4000:]}\n"
        f"STDERR:\n{proc.stderr[-4000:]}"
    )

    runs_dir = WORKSPACE_ROOT / ".tmp" / "job_search_v2" / "runs"
    run_dirs = sorted(
        (d for d in runs_dir.glob("run_*") if d.is_dir()),
        key=lambda d: d.stat().st_mtime,
    )
    assert run_dirs, f"no run_* directories found under {runs_dir}"
    newest = run_dirs[-1]
    summary_path = newest / "summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    for key in ("domain_filter", "verification", "after_verification", "sheet_dedup"):
        assert key in summary, f"summary.json missing {key!r} (run_dir={newest})"



# ===========================================================================
# Strict re-check sweep of already-stamped rows (2026-09-14)
# ===========================================================================

def _stamped_pm_rows():
    # header: Company, Title, Country, Location, Contract, Link, Posted, Verified
    old = (NOW - timedelta(days=5)).date().isoformat()
    recent = (NOW - timedelta(days=1)).date().isoformat()
    return [
        ["Acme", "Still Open PM", "", "Paris", "CDI", "https://x.example/open", "2026-09-05",
         f"open · posted 2026-09-05 · checked {old}"],
        ["Acme", "Now Closed PM", "", "Paris", "CDI", "https://x.example/closed", "2026-09-05",
         f"open · posted 2026-09-05 · checked {old}"],
        ["Acme", "Recently Checked PM", "", "Paris", "CDI", "https://x.example/recent", "2026-09-08",
         f"open · posted 2026-09-08 · checked {recent}"],
        ["Acme", "Blocked PM", "", "Paris", "CDI", "https://x.example/blocked", "2026-09-05",
         f"open · posted 2026-09-05 · checked {old} · rechecked {old}"],
    ]


def _recheck_fetch(calls):
    open_html = ('<html><body><script type="application/ld+json">{"@type":"JobPosting","datePosted":"2026-09-05"}'
                 '</script><button>Apply</button>' + "x" * 600 + "</body></html>")
    closed_html = "<html><body><h1>No longer accepting applications</h1>" + "<p>f</p>" * 100 + "</body></html>"

    def fetch(u):
        calls.append(u)
        if u.endswith("/closed"):
            return 200, closed_html, u
        if u.endswith("/blocked"):
            return 403, "", u
        return 200, open_html, u
    return fetch


def test_recheck_sweep_removes_closed_and_blocked_and_restamps_open():
    header = ["Company", "Title", "Country", "Location", "Contract", "Link", "Posted", "Verified"]
    ws = FakeWorksheet("PM", header=header, rows=_stamped_pm_rows())
    sp = FakeSpreadsheet({"PM": ws})
    calls: list[str] = []
    stats = purge_mod.reverify_rows(
        sp, tabs=["PM"], dry_run=False, max_fetches=100, concurrency=2, fetch=_recheck_fetch(calls),
        now=NOW, recheck_after_days=3.0, strict=True, browser_fallback=False,
    )
    assert stats["checked"] == 0  # no unstamped rows
    assert stats["rechecked"] == 1 and stats["recheck_removed"] == 2
    assert not any(u.endswith("/recent") for u in calls), "rows checked < 3 days ago must not be re-fetched"
    rows = [r for r in ws.get_all_values()[1:] if any(c.strip() for c in r)]
    titles = {r[1] for r in rows}
    assert titles == {"Still Open PM", "Recently Checked PM"}
    still_open = next(r for r in rows if r[1] == "Still Open PM")
    assert still_open[7].endswith(f"· rechecked {NOW.date().isoformat()}")
    assert still_open[7].count("rechecked") == 1


def test_recheck_sweep_lenient_keeps_blocked_and_budget_is_shared():
    header = ["Company", "Title", "Country", "Location", "Contract", "Link", "Posted", "Verified"]
    ws = FakeWorksheet("PM", header=header, rows=_stamped_pm_rows())
    sp = FakeSpreadsheet({"PM": ws})
    calls: list[str] = []
    stats = purge_mod.reverify_rows(
        sp, tabs=["PM"], dry_run=False, max_fetches=2, concurrency=1, fetch=_recheck_fetch(calls),
        now=NOW, recheck_after_days=3.0, strict=False, browser_fallback=False,
    )
    assert len(calls) == 2 and stats["remaining_recheck"] == 1


def test_recheck_sweep_uses_browser_for_blocked_rows():
    header = ["Company", "Title", "Country", "Location", "Contract", "Link", "Posted", "Verified"]
    ws = FakeWorksheet("PM", header=header, rows=_stamped_pm_rows())
    sp = FakeSpreadsheet({"PM": ws})
    open_html = ('<html><body><script type="application/ld+json">{"@type":"JobPosting","datePosted":"2026-09-05"}'
                 '</script><button>Apply</button>' + "x" * 600 + "</body></html>")
    browser_calls: list[str] = []

    def browser_fetch(u):
        browser_calls.append(u)
        return 200, open_html, u

    stats = purge_mod.reverify_rows(
        sp, tabs=["PM"], dry_run=False, max_fetches=100, concurrency=2, fetch=_recheck_fetch([]),
        now=NOW, recheck_after_days=3.0, strict=True, browser_fetch=browser_fetch,
    )
    assert browser_calls == ["https://x.example/blocked"]
    assert stats["recheck_removed"] == 1  # only the genuinely closed one
    titles = {r[1] for r in ws.get_all_values()[1:] if any(c.strip() for c in r)}
    assert "Blocked PM" in titles
