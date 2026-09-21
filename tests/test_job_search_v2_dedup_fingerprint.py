"""Unit tests for the 2026-09-10 dedup-fingerprint fix across job_search_v2:
contracts.compute_fingerprint / canonicalize_url, normalize.py in-batch merge,
dedup.py seen.db schema migration + fingerprint matching, notifier/sheet.py
cross-tab dedup, and purge_irrelevant_rows.py cross-tab dedup_rows.

Root causes fixed (operator complaint: same job appears several times):
  1. dedup keyed only on exact SHA256(title|company|canonical_url) -> two-source
     or tracking-variant duplicates slipped through. Fixed by `fingerprint`.
  2. seen.db cache loss resets cross-day dedup -> schema migration keeps old
     DBs usable, but a lost cache is still lost; out of scope here.
  3. the sheet append only checked `_id` in the ONE target tab -> fixed by
     scanning every role tab for _id / Link / fingerprint before appending.
"""
from __future__ import annotations

import sqlite3
import sys
import types
from datetime import datetime, timezone
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
    RemoteMode,
    SourceJob,
    canonicalize_url,
    compute_content_hash,
    compute_fingerprint,
)
from execution.personal_workflows.job_search_v2.normalizer.normalize import (  # noqa: E402
    batch_normalize,
)
from execution.personal_workflows.job_search_v2.normalizer import dedup as dedup_mod  # noqa: E402
from execution.personal_workflows.job_search_v2.notifier import sheet as sheet_mod  # noqa: E402
from execution.personal_workflows.job_search_v2 import purge_irrelevant_rows as purge_mod  # noqa: E402


# ===========================================================================
# 1. compute_fingerprint normalization
# ===========================================================================


def test_fingerprint_strips_gender_markers_fr_en():
    a = compute_fingerprint("Product Manager (H/F)", "Acme")
    b = compute_fingerprint("Product Manager", "Acme")
    assert a == b


def test_fingerprint_strips_gender_markers_de():
    a = compute_fingerprint("Produktmanager (m/w/d)", "Acme")
    b = compute_fingerprint("Produktmanager", "Acme")
    assert a == b


def test_fingerprint_strips_various_gender_marker_spellings():
    base = compute_fingerprint("Product Owner", "Acme")
    variants = [
        "Product Owner (m/w/d)",
        "Product Owner m/w/d",
        "Product Owner (f/h)",
        "Product Owner h/f/x",
        "Product Owner f/m/x",
        "Product Owner w/m/d",
        "Product Owner (x/f/m)",
        "Product Owner (m/f)",
        "Product Owner - All Genders",
    ]
    for v in variants:
        assert compute_fingerprint(v, "Acme") == base, f"failed for {v!r}"


def test_fingerprint_strips_accents():
    a = compute_fingerprint("Chef de Produit Senior", "Société Générale")
    b = compute_fingerprint("Chef de Produit Senior", "Societe Generale")
    assert a == b


def test_fingerprint_strips_legal_suffixes_and_is_case_insensitive():
    variants = ["NEXTON SAS", "Nexton", "nexton sasu", "NEXTON GmbH", "Nexton Group", "Nexton Groupe"]
    fps = {compute_fingerprint("Product Manager", c) for c in variants}
    assert len(fps) == 1


def test_fingerprint_strips_via_recruiter_prefix_and_suffix():
    a = compute_fingerprint("Product Manager", "Acme")
    leading = compute_fingerprint("Product Manager", "via Acme")
    trailing = compute_fingerprint("Product Manager", "Acme via LinkedIn Talent Solutions")
    assert a == leading == trailing


def test_fingerprint_empty_or_placeholder_company_uses_title_only_marker():
    for company in ("", "Unknown", "unknown", "Confidential", "  "):
        fp = compute_fingerprint("Product Manager", company)
        expected = compute_fingerprint("Product Manager", "")
        assert fp == expected
    # Sanity: distinct titles with placeholder companies must NOT collide.
    assert compute_fingerprint("Product Manager", "") != compute_fingerprint("Product Owner", "")


def test_fingerprint_differs_for_genuinely_different_jobs():
    a = compute_fingerprint("Product Manager", "Acme")
    b = compute_fingerprint("Product Owner", "Acme")
    c = compute_fingerprint("Product Manager", "Other Co")
    assert len({a, b, c}) == 3


def test_fingerprint_is_64_char_hex():
    fp = compute_fingerprint("Product Manager", "Acme")
    assert len(fp) == 64
    int(fp, 16)  # raises if not hex


# ===========================================================================
# 2. canonicalize_url: new tracking params + trailing slash
# ===========================================================================


@pytest.mark.parametrize("param", [
    "refId", "trackingId", "position", "pageNum", "originalSubdomain",
    "origin", "campaign", "xkcb", "xpse", "vjs", "advn", "sjdu",
    "utm_id", "mkt_tok", "_hsenc", "_hsmi", "hsCtaTracking",
    "itm_source", "itm_medium",
])
def test_canonicalize_url_strips_new_tracking_params(param):
    url = f"https://boards.example.com/jobs/123?{param}=abc123&keep=1"
    canon = canonicalize_url(url)
    assert param not in canon
    assert "keep=1" in canon


def test_canonicalize_url_keeps_q_param():
    """`q` is explicitly NOT a tracking param — some boards use it to identify
    the job itself, so stripping it would collapse distinct postings."""
    url = "https://boards.example.com/jobs?q=abc123"
    canon = canonicalize_url(url)
    assert "q=abc123" in canon


def test_canonicalize_url_strips_trailing_slash_on_path():
    a = canonicalize_url("https://example.com/jobs/123")
    b = canonicalize_url("https://example.com/jobs/123/")
    assert a == b
    assert not a.endswith("/") or a.endswith("//")  # root "/" untouched, not collapsed to ""


def test_canonicalize_url_strips_trailing_slash_on_fragment():
    a = canonicalize_url("https://example.com/jobs/123#detail")
    b = canonicalize_url("https://example.com/jobs/123#detail/")
    assert a == b


def test_canonicalize_url_root_path_untouched():
    # Guard against the trailing-slash strip reducing "/" to "" (which would
    # change the URL's shape rather than merely canonicalizing it).
    canon = canonicalize_url("https://example.com/")
    assert canon == "https://example.com/"


# ===========================================================================
# 3. normalize.py in-batch merge across sources (content_hash OR fingerprint)
# ===========================================================================


def _src(source, source_id, title, company, url, posted_at=None, snippet="", contract=""):
    return SourceJob(
        source=source,
        source_id=source_id,
        url=url,
        title=title,
        company=company,
        description_snippet=snippet,
        posted_at=posted_at,
        contract_type_raw=contract,
    )


def test_batch_normalize_merges_by_fingerprint_across_sources_with_different_urls():
    """Same posting, two boards, two different URLs (so content_hash differs) —
    must still merge via fingerprint."""
    jobs = [
        _src(JobSource.WTTJ_ALGOLIA, "1", "Product Manager (H/F)", "Acme SAS",
             "https://wttj.example/jobs/1"),
        _src(JobSource.LINKEDIN_GUEST_API, "2", "Product Manager", "Acme",
             "https://linkedin.example/jobs/2"),
    ]
    out = batch_normalize(jobs)
    assert len(out) == 1
    survivor = out[0]
    assert survivor.source == JobSource.WTTJ_ALGOLIA  # first occurrence wins
    assert JobSource.LINKEDIN_GUEST_API in survivor.also_seen_on


def test_batch_normalize_prefers_non_none_posted_at_from_dupe():
    posted = datetime(2026, 9, 1, tzinfo=timezone.utc)
    jobs = [
        _src(JobSource.WTTJ_ALGOLIA, "1", "Product Manager", "Acme",
             "https://wttj.example/jobs/1", posted_at=None),
        _src(JobSource.LINKEDIN_GUEST_API, "2", "Product Manager", "Acme",
             "https://linkedin.example/jobs/2", posted_at=posted),
    ]
    out = batch_normalize(jobs)
    assert len(out) == 1
    assert out[0].posted_at == posted


def test_batch_normalize_keeps_first_posted_at_when_first_already_has_one():
    first_posted = datetime(2026, 8, 20, tzinfo=timezone.utc)
    second_posted = datetime(2026, 9, 1, tzinfo=timezone.utc)
    jobs = [
        _src(JobSource.WTTJ_ALGOLIA, "1", "Product Manager", "Acme",
             "https://wttj.example/jobs/1", posted_at=first_posted),
        _src(JobSource.LINKEDIN_GUEST_API, "2", "Product Manager", "Acme",
             "https://linkedin.example/jobs/2", posted_at=second_posted),
    ]
    out = batch_normalize(jobs)
    assert out[0].posted_at == first_posted


def test_batch_normalize_prefers_longer_description_snippet():
    jobs = [
        _src(JobSource.WTTJ_ALGOLIA, "1", "Product Manager", "Acme",
             "https://wttj.example/jobs/1", snippet="short"),
        _src(JobSource.LINKEDIN_GUEST_API, "2", "Product Manager", "Acme",
             "https://linkedin.example/jobs/2", snippet="a much longer description snippet here"),
    ]
    out = batch_normalize(jobs)
    assert out[0].description_snippet == "a much longer description snippet here"


def test_batch_normalize_still_merges_exact_content_hash_dupes():
    """Same source, same URL (the pre-existing content_hash path) still works."""
    jobs = [
        _src(JobSource.WTTJ_ALGOLIA, "1", "Product Manager", "Acme",
             "https://wttj.example/jobs/1"),
        _src(JobSource.WTTJ_ALGOLIA, "1", "Product Manager", "Acme",
             "https://wttj.example/jobs/1"),
    ]
    out = batch_normalize(jobs)
    assert len(out) == 1


def test_batch_normalize_does_not_merge_genuinely_different_jobs():
    jobs = [
        _src(JobSource.WTTJ_ALGOLIA, "1", "Product Manager", "Acme",
             "https://wttj.example/jobs/1"),
        _src(JobSource.LINKEDIN_GUEST_API, "2", "Product Owner", "Other Co",
             "https://linkedin.example/jobs/2"),
    ]
    out = batch_normalize(jobs)
    assert len(out) == 2


# ===========================================================================
# 4. dedup.py: seen.db schema migration + fingerprint matching
# ===========================================================================

_OLD_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen (
    content_hash TEXT PRIMARY KEY,
    canonical_url TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    source TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);
"""


def _make_normalized(source, title, company, url, source_id="1"):
    canonical = canonicalize_url(url)
    return NormalizedJob(
        source=source,
        source_id=source_id,
        url=url,
        canonical_url=canonical,
        title=title,
        company=company,
        location="Paris",
        description_snippet="",
        posted_at=None,
        contract_type=ContractType.CDI,
        remote_mode=RemoteMode.UNKNOWN,
        fetched_at=datetime.now(timezone.utc),
        content_hash=compute_content_hash(title, company, canonical),
        fingerprint=compute_fingerprint(title, company),
    )


def test_filter_new_migrates_old_schema_db_and_adds_fingerprint_column(tmp_path):
    db_path = tmp_path / "seen.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_OLD_SCHEMA)
    conn.commit()
    conn.close()

    # Confirm the DB genuinely lacks the column before filter_new touches it.
    conn = sqlite3.connect(str(db_path))
    cols_before = {r[1] for r in conn.execute("PRAGMA table_info(seen)")}
    conn.close()
    assert "fingerprint" not in cols_before

    job = _make_normalized(JobSource.WTTJ_ALGOLIA, "Product Manager", "Acme", "https://wttj.example/jobs/1")
    new_jobs, stats = dedup_mod.filter_new([job], db_path=db_path)

    assert len(new_jobs) == 1
    assert stats["new"] == 1

    conn = sqlite3.connect(str(db_path))
    cols_after = {r[1] for r in conn.execute("PRAGMA table_info(seen)")}
    assert "fingerprint" in cols_after
    row = conn.execute("SELECT fingerprint FROM seen WHERE content_hash = ?", (job.content_hash,)).fetchone()
    conn.close()
    assert row[0] == job.fingerprint


def test_filter_new_dedups_cross_source_via_fingerprint_even_with_different_url(tmp_path):
    db_path = tmp_path / "seen.db"

    job1 = _make_normalized(JobSource.WTTJ_ALGOLIA, "Product Manager (H/F)", "Acme SAS", "https://wttj.example/jobs/1")
    new1, stats1 = dedup_mod.filter_new([job1], db_path=db_path)
    assert len(new1) == 1
    assert stats1["already_seen_by_fingerprint"] == 0

    # Different source, different URL (different content_hash), but same
    # underlying posting per the fingerprint (accent/gender-marker/legal-suffix
    # normalized) -> must be caught as already-seen.
    job2 = _make_normalized(JobSource.LINKEDIN_GUEST_API, "Product Manager", "Acme", "https://linkedin.example/jobs/2")
    assert job2.content_hash != job1.content_hash
    assert job2.fingerprint == job1.fingerprint

    new2, stats2 = dedup_mod.filter_new([job2], db_path=db_path)
    assert len(new2) == 0
    assert stats2["already_seen"] == 1
    assert stats2["already_seen_by_fingerprint"] == 1


def test_filter_new_backfills_fingerprint_on_old_rows_with_null_fingerprint(tmp_path):
    """A row inserted by an older pipeline run (pre-fingerprint column, or the
    column just added by migration) has fingerprint=NULL. The next run for the
    same job should backfill it rather than leaving it permanently unmatched."""
    db_path = tmp_path / "seen.db"
    job = _make_normalized(JobSource.WTTJ_ALGOLIA, "Product Manager", "Acme", "https://wttj.example/jobs/1")

    conn = sqlite3.connect(str(db_path))
    conn.executescript(_OLD_SCHEMA)
    conn.execute(
        "INSERT INTO seen (content_hash, canonical_url, title, company, source, first_seen_at, last_seen_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (job.content_hash, job.canonical_url, job.title, job.company, job.source.value,
         datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()

    new_jobs, stats = dedup_mod.filter_new([job], db_path=db_path)
    assert len(new_jobs) == 0  # matched by content_hash (exact same job) -> already seen
    assert stats["already_seen"] == 1

    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT fingerprint FROM seen WHERE content_hash = ?", (job.content_hash,)).fetchone()
    conn.close()
    assert row[0] == job.fingerprint  # backfilled, no longer NULL/empty


# ===========================================================================
# 5. notifier/sheet.py: cross-tab dedup
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
        # Only used by _append_dicts / dedup rewrite for A1:... full-range or
        # header writes in these tests — reconstruct the grid from the range's
        # starting row.
        a1 = range_name.split(":")[0]
        start_row = int("".join(c for c in a1 if c.isdigit()) or "1")
        col_letters = "".join(c for c in a1 if c.isalpha()).upper()
        start_col = 0
        for ch in col_letters:
            start_col = start_col * 26 + (ord(ch) - ord("A") + 1)
        start_col = max(start_col, 1) - 1  # 0-based offset (header extension writes G1:H1)
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
        # Best-effort: clear everything from row 2 down (tests only use A2:...).
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


def _ranked_job_from_normalized(job):
    return None


def test_dedup_dicts_skips_existing_id_link_fingerprint_and_in_batch_dupe():
    d_existing_id = {"_id": "abc123", "Link": "https://x.example/1", "Title": "PM", "Company": "Acme",
                      "fingerprint": "id-match-should-not-matter"}
    d_existing_link = {"_id": "new1", "Link": "https://x.example/2", "Title": "PM2", "Company": "Acme",
                        "fingerprint": "unique-1"}
    d_existing_fp = {"_id": "new2", "Link": "https://x.example/3", "Title": "PM3", "Company": "Acme",
                      "fingerprint": "existing-fp"}
    d_fresh = {"_id": "new3", "Link": "https://x.example/4", "Title": "PM4", "Company": "Acme",
               "fingerprint": "fresh-fp"}
    d_in_batch_dupe = {"_id": "new3-dup", "Link": "https://x.example/5", "Title": "PM4", "Company": "Acme",
                        "fingerprint": "fresh-fp"}  # same fingerprint as d_fresh -> in-batch dupe

    existing_ids = {"abc123"}
    existing_links = {sheet_mod.canonicalize_url("https://x.example/2")}
    existing_fps = {"existing-fp"}

    kept, stats = sheet_mod._dedup_dicts(
        [d_existing_id, d_existing_link, d_existing_fp, d_fresh, d_in_batch_dupe],
        existing_ids, existing_links, existing_fps,
    )

    assert kept == [d_fresh]
    assert stats["skipped_existing_id"] == 1
    assert stats["skipped_existing_link"] == 1
    assert stats["skipped_existing_fingerprint"] == 1
    assert stats["skipped_in_batch"] == 1
    assert stats["appended"] == 1


def test_append_jobs_dedups_across_tabs_with_fake_worksheets(monkeypatch):
    # "PM" tab already has a job that will collide by _id (content_hash[:16]).
    job_existing_id = _make_normalized(JobSource.FIXTURE, "Product Manager", "Existing Co",
                                        "https://boards.example/jobs/existing-id")
    pm_ws = FakeWorksheet(
        "PM",
        header=["_id", "Company", "Title", "Country", "Location", "Contract", "Link"],
        rows=[[job_existing_id.content_hash[:16], "Existing Co", "Product Manager", "", "Paris", "CDI",
               str(job_existing_id.url)]],
    )
    # "AI PM" tab has a job that will collide by fingerprint with a new job
    # (different title spelling/gender marker, same normalized identity).
    ai_pm_ws = FakeWorksheet(
        "AI PM",
        header=["Company", "Title", "Country", "Location", "Contract", "Link"],
        rows=[["Acme SAS", "AI Product Manager (H/F)", "", "Paris", "CDI", "https://boards.example/jobs/ai-pm-1"]],
    )
    fake_sp = FakeSpreadsheet({"PM": pm_ws, "AI PM": ai_pm_ws})

    monkeypatch.setattr(sheet_mod, "_open_sheet", lambda *a, **k: (fake_sp, None))

    routing_config = {
        "fallback_tab": "PM",
        "titles": {"ai_pm": {"tab": "AI PM", "synonyms": ["ai product manager"]}},
    }

    dup_by_id = job_existing_id  # same content_hash[:16] -> should be skipped
    dup_by_fp = _make_normalized(JobSource.WTTJ_ALGOLIA, "AI Product Manager", "Acme",
                                  "https://boards.example/jobs/ai-pm-2")  # matches ai_pm_ws row via fingerprint
    fresh = _make_normalized(JobSource.FIXTURE, "Product Owner", "Brand New Co",
                              "https://boards.example/jobs/fresh-1")

    rows_appended, per_tab, ok = sheet_mod.append_jobs(
        [dup_by_id, dup_by_fp, fresh],
        routing_config=routing_config,
    )

    assert ok is True
    assert rows_appended == 1
    assert per_tab.get("PM", 0) == 1
    assert "AI PM" not in per_tab or per_tab["AI PM"] == 0
    assert sheet_mod.LAST_APPEND_STATS["skipped_existing_id"] == 1
    assert sheet_mod.LAST_APPEND_STATS["skipped_existing_fingerprint"] == 1
    assert sheet_mod.LAST_APPEND_STATS["appended"] == 1

    # The fresh job actually landed in the PM tab's grid.
    pm_values = pm_ws.get_all_values()
    assert any("Product Owner" in row for row in pm_values)


def test_append_jobs_dry_run_still_dedups_in_batch():
    job = _make_normalized(JobSource.FIXTURE, "Product Manager", "Acme", "https://boards.example/jobs/1")
    dupe = _make_normalized(JobSource.WTTJ_ALGOLIA, "Product Manager", "Acme SAS", "https://boards.example/jobs/2")
    assert job.fingerprint == dupe.fingerprint

    rows_appended, per_tab, ok = sheet_mod.append_jobs([job, dupe], dry_run=True)
    assert ok is True
    assert rows_appended == 1
    assert sheet_mod.LAST_APPEND_STATS["skipped_in_batch"] == 1


# ===========================================================================
# 6. purge_irrelevant_rows.py: dedup_rows keeps the Status-bearing row
# ===========================================================================


def test_dedup_rows_keeps_status_bearing_row_over_untouched_duplicate():
    header = ["_id", "First Seen", "Company", "Title", "Country", "Location", "Contract",
              "Link", "Status"]
    ws = FakeWorksheet(
        "PM",
        header=header,
        rows=[
            ["hash1", "2026-09-01", "Acme", "Product Manager", "", "Paris", "CDI",
             "https://boards.example/jobs/1", ""],  # untouched duplicate — should be REMOVED
            ["hash2", "2026-09-02", "Acme", "Product Manager", "", "Paris", "CDI",
             "https://boards.example/jobs/1", "Applied"],  # operator edit — must SURVIVE
        ],
    )
    sp = FakeSpreadsheet({"PM": ws})

    stats = purge_mod.dedup_rows(sp, tabs=["PM"])

    assert stats["removed_duplicates"] == 1
    remaining = ws.get_all_values()[1:]
    remaining_status = [r[header.index("Status")] for r in remaining if any(c.strip() for c in r)]
    assert remaining_status == ["Applied"]


def test_dedup_rows_cross_tab_prefers_earliest_first_seen_when_no_status():
    header = ["_id", "First Seen", "Company", "Title", "Country", "Location", "Contract",
              "Link", "Status"]
    pm_ws = FakeWorksheet(
        "PM",
        header=header,
        rows=[["h1", "2026-09-05", "Acme", "Product Manager", "", "Paris", "CDI",
               "https://boards.example/jobs/dup", ""]],
    )
    ai_pm_ws = FakeWorksheet(
        "AI PM",
        header=header,
        rows=[["h2", "2026-09-01", "Acme", "Product Manager", "", "Paris", "CDI",
               "https://boards.example/jobs/dup", ""]],  # earlier First Seen -> should survive
    )
    sp = FakeSpreadsheet({"PM": pm_ws, "AI PM": ai_pm_ws})

    stats = purge_mod.dedup_rows(sp, tabs=["PM", "AI PM"])

    assert stats["removed_duplicates"] == 1
    pm_remaining = [r for r in pm_ws.get_all_values()[1:] if any(c.strip() for c in r)]
    ai_pm_remaining = [r for r in ai_pm_ws.get_all_values()[1:] if any(c.strip() for c in r)]
    assert pm_remaining == []
    assert len(ai_pm_remaining) == 1


def test_dedup_rows_dry_run_only_reports_no_writes():
    header = ["_id", "Company", "Title", "Link", "Status"]
    ws = FakeWorksheet(
        "PM",
        header=header,
        rows=[
            ["h1", "Acme", "Product Manager", "https://boards.example/jobs/1", ""],
            ["h2", "Acme", "Product Manager", "https://boards.example/jobs/1", ""],
        ],
    )
    sp = FakeSpreadsheet({"PM": ws})
    before = ws.get_all_values()

    stats = purge_mod.dedup_rows(sp, tabs=["PM"], dry_run=True)

    assert stats["removed_duplicates"] == 1
    assert ws.get_all_values() == before  # untouched


def test_purge_sheet_reports_removed_duplicates(monkeypatch):
    header = ["_id", "Company", "Title", "Country", "Location", "Contract", "Link", "Status"]
    ws = FakeWorksheet(
        "PM",
        header=header,
        rows=[
            ["h1", "Acme", "Product Manager", "France", "Paris", "CDI",
             "https://boards.example/jobs/1", ""],
            ["h2", "Acme", "Product Manager", "France", "Paris", "CDI",
             "https://boards.example/jobs/1", ""],
        ],
    )
    sp = FakeSpreadsheet({"PM": ws})

    # classify_title / classify_language must not reject our synthetic "Product
    # Manager" rows for this test to isolate dedup behavior.
    monkeypatch.setattr(purge_mod, "classify_title", lambda title: (True, "ok"))
    monkeypatch.setattr(purge_mod, "classify_language", lambda title, desc: (True, "ok"))
    monkeypatch.setattr(purge_mod, "_reject_location_patterns", lambda: [])

    stats = purge_mod.purge_sheet(sp, tabs=["PM"], delete_obsolete=False)

    assert stats["removed_duplicates"] == 1


def test_fingerprint_ignores_trailing_contract_suffix():
    from execution.personal_workflows.job_search_v2.contracts import compute_fingerprint as fp
    assert fp("Product Manager - CDI", "Doctolib") == fp("Product Manager (H/F)", "Doctolib SAS")
    assert fp("Product Manager CDI Paris", "Doctolib") != fp("Product Manager", "Doctolib")  # location stays



def test_title_only_role_anchor_settles_language_without_langdetect():
    from execution.personal_workflows.job_search_v2.normalizer.language_filter import classify_language
    ok, reason = classify_language(
        "Product Specialist/Chef de produit- Endovasculaire- Rungis, Île-de-France, France (H/F)", "")
    assert ok is True and reason == "accept:role_anchor_en_fr"
    # A German tell still rejects even with an English role anchor.
    ok2, reason2 = classify_language("Product Manager für unseren Standort Berlin", "")
    assert ok2 is False
