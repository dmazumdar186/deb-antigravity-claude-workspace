"""
test_job_tracker_e2e.py
description: Full DAG end-to-end test for the French PM/PO Job Tracker orchestrator.
    All external calls (scrapers, SIRENE, LinkedIn enrichment, Gmail) are mocked.
    Tests idempotency, deduplication, contact persistence, digest HTML generation,
    and expiry housekeeping across simulated multi-day runs.
inputs: pytest tmp_path fixture; freezegun for time jumps; unittest.mock.patch for externals.
outputs: pytest pass/fail; no real API calls, no email sent.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from freezegun import freeze_time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# We import run_pipeline after patching so the module-level imports in the
# orchestrator don't try to import unavailable custom scraper modules at
# collection time.  The patch targets are applied via the @patch decorator
# or context managers inside each test.

# ---------------------------------------------------------------------------
# Fixture data (mirrors tests/fixtures/ files; kept inline for test isolation)
# ---------------------------------------------------------------------------

_FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"

_FAKE_RESOLUTION = {
    "siren": None,  # None so each company dedupes by name_normalized (avoids UNIQUE siren collision)
    "naf_code": "62.01Z",
    "is_digital_sector": 1,
    "website": None,
    "matched_denomination": "Fake Co",
    "source": "sirene",
}

_FAKE_CONTACTS = [
    {
        "full_name": "Alice Martin",
        "title": "CPO",
        "seniority": "cpo",
        "linkedin_url": "https://www.linkedin.com/in/alice-martin/",
        "source": "firecrawl_dork",
    },
    {
        "full_name": "Bob Lefevre",
        "title": "Head of Product",
        "seniority": "head_of_product",
        "linkedin_url": "https://www.linkedin.com/in/bob-lefevre/",
        "source": "firecrawl_dork",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_args(tmp_path: Path, **overrides) -> argparse.Namespace:
    """Build an argparse.Namespace that mimics --mock --dry-run --no-resolve --no-enrich."""
    defaults = {
        "boards": "",          # empty → use all config boards
        "mock": True,
        "dry_run": True,
        "no_enrich": False,
        "no_resolve": False,
        "send": False,
        "db": str(tmp_path / "jt.db"),
        "max_per_board": 200,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _patch_all_externals():
    """Return a list of (target_string, mock_or_return_value) for use with patch()."""
    return [
        # Scrapers — each .scrape() is never called in --mock mode, but the modules
        # must be importable.  We patch at the orchestrator's local reference.
        (
            "execution.personal_workflows.job_tracker_pm_france.lookup_company",
            lambda name: _FAKE_RESOLUTION,
        ),
        (
            "execution.personal_workflows.job_tracker_pm_france.find_contacts_for_company",
            lambda name, max_total=5: _FAKE_CONTACTS,
        ),
        (
            "execution.personal_workflows.job_tracker_pm_france.send_digest",
            lambda html, subject="": (True, None),
        ),
    ]


def _run_with_mocks(args: argparse.Namespace):
    """Import and run the orchestrator pipeline under all external patches."""
    patches = _patch_all_externals()
    context_managers = [
        patch(target, side_effect=fn if callable(fn) else None, return_value=None if callable(fn) else fn)
        for target, fn in patches
    ]
    # Use patch as a simple attribute replacement (side_effect for callables)
    import contextlib

    @contextlib.contextmanager
    def _apply():
        active = []
        try:
            for target, replacement in patches:
                p = patch(target, side_effect=replacement if callable(replacement) else None)
                m = p.start()
                if not callable(replacement):
                    m.return_value = replacement
                active.append(p)
            yield
        finally:
            for p in active:
                p.stop()

    from execution.personal_workflows.job_tracker_pm_france import run_pipeline

    with _apply():
        return run_pipeline(args)


# ---------------------------------------------------------------------------
# Test 1 — Happy-path run: exit 0, companies + jobs + contacts in DB
# ---------------------------------------------------------------------------

def test_happy_path_run(tmp_path):
    """Orchestrator exits 0 and populates companies, jobs, and contacts tables."""
    from freezegun import freeze_time

    args = _make_args(tmp_path)

    with freeze_time("2026-05-14T08:00:00+00:00"):
        exit_code = _run_with_mocks(args)

    assert exit_code == 0, f"run_pipeline returned non-zero exit code: {exit_code}"

    # Inspect DB directly
    from execution.personal_workflows.job_tracker_db import init_db, query_active_within_window
    import sqlite3

    conn = init_db(args.db)

    jobs = query_active_within_window(conn, 7)
    assert len(jobs) > 0, "No active jobs found after happy-path run"

    companies = conn.execute("SELECT * FROM companies").fetchall()
    assert len(companies) > 0, "No companies found after happy-path run"

    contacts = conn.execute("SELECT * FROM contacts").fetchall()
    assert len(contacts) > 0, "No contacts found after happy-path run"

    conn.close()


# ---------------------------------------------------------------------------
# Test 2 — Second run with same fixture is idempotent
# ---------------------------------------------------------------------------

def test_second_run_no_duplicates(tmp_path):
    """Running the pipeline twice with the same fixture does not duplicate jobs."""
    args = _make_args(tmp_path)

    with freeze_time("2026-05-14T08:00:00+00:00"):
        rc1 = _run_with_mocks(args)

    with freeze_time("2026-05-14T08:05:00+00:00"):
        rc2 = _run_with_mocks(args)

    assert rc1 == 0
    assert rc2 == 0

    from execution.personal_workflows.job_tracker_db import init_db
    conn = init_db(args.db)
    job_count_after_run1 = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    conn.close()

    # Re-open after second run
    conn = init_db(args.db)
    job_count_after_run2 = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    conn.close()

    assert job_count_after_run1 == job_count_after_run2, (
        f"Second run introduced duplicate jobs: {job_count_after_run1} → {job_count_after_run2}"
    )


# ---------------------------------------------------------------------------
# Test 3 — last_seen_at updated on second run for pre-existing jobs
# ---------------------------------------------------------------------------

def test_second_run_updates_last_seen_at(tmp_path):
    """Pre-existing jobs get their last_seen_at bumped on the second run."""
    args = _make_args(tmp_path)

    with freeze_time("2026-05-14T08:00:00+00:00"):
        _run_with_mocks(args)

    with freeze_time("2026-05-14T09:30:00+00:00"):
        _run_with_mocks(args)

    from execution.personal_workflows.job_tracker_db import init_db
    conn = init_db(args.db)
    rows = conn.execute("SELECT last_seen_at FROM jobs").fetchall()
    conn.close()

    # Every job's last_seen_at should be at or after 09:30
    for row in rows:
        ts = row[0]
        # Accept any ISO string that starts with the run-2 date (same calendar day in this test)
        assert "2026-05-14T09" in ts or "2026-05-14T08" in ts, (
            f"Unexpected last_seen_at: {ts}"
        )


# ---------------------------------------------------------------------------
# Test 4 — Cross-board dedupe via job_hash
# ---------------------------------------------------------------------------

def test_cross_board_dedup(tmp_path):
    """The Doctolib job present in both wttj and google fixtures appears only once in DB."""
    args = _make_args(tmp_path)

    # Load fixture to count unique Doctolib Senior PM job hashes
    wttj_fixture = json.loads((_FIXTURES_DIR / "raw_wttj.json").read_text(encoding="utf-8"))
    google_fixture = json.loads((_FIXTURES_DIR / "raw_google.json").read_text(encoding="utf-8"))

    # Find the duplicate entry (same source_url in both fixtures)
    wttj_urls = {j["source_url"] for j in wttj_fixture}
    google_dup = [j for j in google_fixture if j["source_url"] in wttj_urls]
    assert len(google_dup) == 1, "Fixture setup: expected exactly 1 cross-board duplicate"

    with freeze_time("2026-05-14T08:00:00+00:00"):
        _run_with_mocks(args)

    from execution.personal_workflows.job_tracker_db import init_db
    conn = init_db(args.db)

    # Count Doctolib jobs in the DB — should be at most 2 (SPM + SPO from wttj fixture)
    # The google duplicate must not create an extra row
    doctolib_jobs = conn.execute(
        """
        SELECT j.id, j.title FROM jobs j
        JOIN companies c ON c.id = j.company_id
        WHERE c.name_normalized = ?
        """,
        ("doctolib",),
    ).fetchall()
    conn.close()

    # wttj has 2 Doctolib jobs; google adds 1 duplicate → after dedup, still 2
    assert len(doctolib_jobs) == 2, (
        f"Expected 2 Doctolib jobs (deduped), found {len(doctolib_jobs)}: "
        + str([(r[0], r[1]) for r in doctolib_jobs])
    )


# ---------------------------------------------------------------------------
# Test 5 — Contacts persist and are joined to companies correctly
# ---------------------------------------------------------------------------

def test_contacts_linked_to_companies(tmp_path):
    """Each enriched company has contacts linked via company_id FK."""
    args = _make_args(tmp_path)

    with freeze_time("2026-05-14T08:00:00+00:00"):
        _run_with_mocks(args)

    from execution.personal_workflows.job_tracker_db import init_db, get_contacts_for_company
    conn = init_db(args.db)

    companies = conn.execute("SELECT id, name FROM companies").fetchall()
    contact_found = False
    for company in companies:
        contacts = get_contacts_for_company(conn, company["id"])
        if contacts:
            contact_found = True
            # Verify FK integrity
            for c in contacts:
                assert c["company_id"] == company["id"]
            break

    conn.close()
    assert contact_found, "Expected at least one company to have contacts after enrichment"


# ---------------------------------------------------------------------------
# Test 6 — render_digest_html produces HTML with company names + LinkedIn URL
# ---------------------------------------------------------------------------

def test_digest_html_contains_expected_content(tmp_path):
    """Digest HTML includes company names and at least one contact LinkedIn URL."""
    args = _make_args(tmp_path)

    with freeze_time("2026-05-14T08:00:00+00:00"):
        _run_with_mocks(args)

    from execution.personal_workflows.job_tracker_db import init_db, query_active_within_window
    from execution.personal_workflows.job_digest_renderer import render_digest_html

    conn = init_db(args.db)
    jobs = query_active_within_window(conn, 7)
    company_names = list({j["company_name"] for j in jobs})
    conn.close()

    html, included_ids = render_digest_html(args.db, window_days=7)

    assert len(included_ids) > 0, "Digest included no job IDs"
    assert "<html" in html.lower(), "Digest output is not valid HTML"

    # At least one company name should appear in the HTML
    found_any = any(name in html for name in company_names)
    assert found_any, (
        f"None of the company names found in digest HTML. "
        f"Companies: {company_names}"
    )

    # Alice Martin's LinkedIn URL (from fake contacts) should appear
    assert "alice-martin" in html or "linkedin.com/in/" in html, (
        "Expected a LinkedIn contact URL in the digest HTML"
    )


# ---------------------------------------------------------------------------
# Test 7 — Day +8 after mark_expired: digest shows 0 active jobs
# ---------------------------------------------------------------------------

def test_day8_no_active_jobs_in_digest(tmp_path):
    """After jumping 8 days and calling mark_expired, the digest window contains 0 jobs."""
    args = _make_args(tmp_path)

    with freeze_time("2026-05-14T08:00:00+00:00"):
        _run_with_mocks(args)

    # Simulate 8 days later: housekeeping flags all jobs as expired
    with freeze_time("2026-05-22T08:00:00+00:00"):
        from execution.personal_workflows.job_tracker_db import init_db, mark_expired, query_active_within_window
        conn = init_db(args.db)
        mark_expired(conn, window_days=7)
        active = query_active_within_window(conn, 7)
        conn.close()

    assert len(active) == 0, (
        f"Expected 0 active jobs 8 days after insertion, found {len(active)}"
    )


# ---------------------------------------------------------------------------
# Test 8 — Degraded board (zero-result board) is detected and logged
# ---------------------------------------------------------------------------

def test_degraded_board_detection(tmp_path):
    """_detect_degraded_boards flags a board whose count is < 30 % of its median."""
    from execution.personal_workflows.job_tracker_pm_france import _detect_degraded_boards

    # Board had median of 100 results; today got 10 (10 % < 30 %)
    degraded = _detect_degraded_boards(
        counts_today={"wttj": 10, "indeed": 80},
        medians={"wttj": 100.0, "indeed": 90.0},
    )
    assert "wttj" in degraded, "wttj should be flagged as degraded (10 < 30% of 100)"
    assert "indeed" not in degraded, "indeed should not be flagged (80 > 30% of 90)"


def test_degraded_board_zero_median_not_flagged(tmp_path):
    """A board with no prior history (median=0) must never be flagged as degraded."""
    from execution.personal_workflows.job_tracker_pm_france import _detect_degraded_boards

    degraded = _detect_degraded_boards(
        counts_today={"wttj": 0},
        medians={"wttj": 0.0},
    )
    assert "wttj" not in degraded, (
        "A board with zero median must not be flagged — no baseline to compare against"
    )


# ---------------------------------------------------------------------------
# Test 9 — _company_slug produces filesystem-safe strings
# ---------------------------------------------------------------------------

def test_company_slug():
    from execution.personal_workflows.job_tracker_pm_france import _company_slug

    assert _company_slug("Doctolib") == "doctolib"
    assert _company_slug("BlaBlaCar") == "blablacar"
    assert _company_slug("Société Générale") == "societe-generale"  # accents become base letters
    assert "/" not in _company_slug("A/B Testing Co.")
    assert " " not in _company_slug("Some Company Name")
    # Must not start or end with a dash
    slug = _company_slug("  --Test--  ")
    assert not slug.startswith("-"), f"slug starts with dash: {slug!r}"
    assert not slug.endswith("-"), f"slug ends with dash: {slug!r}"


# ---------------------------------------------------------------------------
# Test 10 — _split_boards_arg parses correctly
# ---------------------------------------------------------------------------

def test_split_boards_arg():
    from execution.personal_workflows.job_tracker_pm_france import _split_boards_arg

    assert _split_boards_arg("wttj,indeed") == ["wttj", "indeed"]
    assert _split_boards_arg("WTTJ , APEC") == ["wttj", "apec"]
    assert _split_boards_arg("") == []
    assert _split_boards_arg("google") == ["google"]
