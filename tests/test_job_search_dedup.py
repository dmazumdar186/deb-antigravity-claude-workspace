"""
Tests for the dedup + Jaccard guard logic in job_search_sheet.py.

All tests are source-agnostic: they use hand-crafted job dicts, not live APIs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution.personal_workflows.job_search_sheet import (  # noqa: E402
    _dedup_jobs,
    _assign_titles,
    _build_sheet_row,
    _jaccard_trigram,
)
from execution.personal_workflows._jt_utils import compute_job_hash, normalize_company, normalize_title  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def adzuna_jobs() -> list[dict]:
    """Simulated Adzuna raw jobs (already processed by filter — passed_filters=True)."""
    return [
        {
            "board": "adzuna",
            "source_url": "https://adzuna.fr/1",
            "title": "Senior Product Manager",
            "company_name": "Mistral AI",
            "location": "Paris, France",
            "posted_at": "2026-06-07",
            "description_snippet": "Looking for a senior PM to lead our AI product strategy at Mistral AI.",
            "contract_type": "Permanent",
            "country": "FR",
        },
        {
            "board": "adzuna",
            "source_url": "https://adzuna.fr/2",
            "title": "AI Product Manager",
            "company_name": "Hugging Face",
            "location": "Remote (France)",
            "posted_at": "2026-06-08",
            "description_snippet": "AI PM role focused on developer tools and model hub product.",
            "contract_type": "Permanent",
            "country": "FR",
        },
    ]


@pytest.fixture()
def jooble_jobs() -> list[dict]:
    """Simulated Jooble raw jobs — includes one overlap with adzuna_jobs."""
    return [
        {
            "board": "jooble",
            "source_url": "https://jooble.fr/1",
            "title": "Senior Product Manager",  # same company+title+location → merge
            "company_name": "Mistral AI",
            "location": "Paris, France",
            "posted_at": "2026-06-07",
            "description_snippet": "Looking for a senior PM to lead our AI product strategy at Mistral AI.",
            "contract_type": "Permanent",
            "country": "FR",
        },
        {
            "board": "jooble",
            "source_url": "https://jooble.fr/3",
            "title": "Freelance Product Manager",
            "company_name": "TotalEnergies",
            "location": "Paris, France",
            "posted_at": "2026-06-05",
            "description_snippet": "4-month freelance PM mission on data platform. TJM 600-700.",
            "contract_type": "Freelance",
            "country": "FR",
        },
    ]


@pytest.fixture()
def france_travail_jobs() -> list[dict]:
    """Simulated FT jobs — includes one overlap with jooble (different description → Jaccard < 0.4)."""
    return [
        {
            "board": "francetravail",
            "source_url": "https://ft.fr/1",
            "title": "AI Product Manager",  # same company+title+location as Hugging Face above
            "company_name": "Hugging Face",
            "location": "Remote (France)",
            "posted_at": "2026-06-08",
            # Very different description → Jaccard < 0.4 with adzuna version
            "description_snippet": "Completely different text: quantum computing blockchain NFT metaverse.",
            "contract_type": None,
            "country": "FR",
        },
    ]


# ---------------------------------------------------------------------------
# Test: 3-source overlap → one row per (company, title, location); also_seen_on accumulates
# ---------------------------------------------------------------------------


def test_3source_overlap_dedup(adzuna_jobs, jooble_jobs):
    """Mistral AI Senior PM appears in both adzuna and jooble → deduplicated to 1 row.
    also_seen_on must include 'jooble' (the merged board).
    """
    combined = adzuna_jobs + jooble_jobs
    deduped = _dedup_jobs(combined)

    # 4 total → 3 unique (Mistral AI deduped with Jooble copy)
    assert len(deduped) == 3, f"Expected 3 unique jobs, got {len(deduped)}"

    # Find the Mistral AI winner
    mistral_jobs = [j for j in deduped if j.get("company_name") == "Mistral AI"]
    assert len(mistral_jobs) == 1

    winner = mistral_jobs[0]
    assert winner["board"] == "adzuna"  # first-seen wins
    assert "jooble" in winner.get("also_seen_on", [])


def test_3source_overlap_all_sources(adzuna_jobs, jooble_jobs, france_travail_jobs):
    """Combining all 3 sources: Hugging Face AI PM appears in adzuna + ft but with
    very different descriptions → Jaccard < 0.4 → keep BOTH as distinct rows.
    """
    combined = adzuna_jobs + jooble_jobs + france_travail_jobs
    deduped = _dedup_jobs(combined)

    hugging_face_jobs = [j for j in deduped if j.get("company_name") == "Hugging Face"]
    # Jaccard on the two "AI Product Manager @ Hugging Face" snippets should be < 0.4
    # so both must be present
    assert len(hugging_face_jobs) == 2, (
        "Hugging Face PM jobs have divergent descriptions; both should be kept."
    )


# ---------------------------------------------------------------------------
# Test: Cross-run merge (carry-forward + current run)
# ---------------------------------------------------------------------------


def test_cross_run_also_seen_on_merge():
    """Simulate carry-forward with also_seen_on=["adzuna"] and current run finding the
    same job via jooble.  After materialisation, also_seen_on must include both boards.
    """
    job = {
        "board": "jooble",
        "source_url": "https://jooble.fr/99",
        "title": "Product Manager",
        "company_name": "ACME Corp",
        "location": "Lyon, France",
        "posted_at": "2026-06-01",
        "description_snippet": "PM role at ACME Corp.",
        "contract_type": "Permanent",
        "country": "FR",
    }
    deduped = _dedup_jobs([job])
    assert len(deduped) == 1
    h = deduped[0]["dedup_hash"]

    # Simulate a carry-forward map where adzuna had already seen this job
    carry_forward = {
        "status": "Applied",
        "notes": "my note",
        "also_seen_on": ["adzuna"],
        "first_seen": "2026-05-30",
    }

    row = _build_sheet_row(deduped[0], carry_forward, "2026-06-09")
    # Column K (index 10) = Also Seen On
    also_seen_str = row[10]
    # "adzuna" should appear (from carry-forward); "jooble" is the current source (col J)
    # The field shows boards *other than* the primary source
    assert "adzuna" in also_seen_str


def test_cross_run_status_preserved():
    """Status=Applied must survive a re-render via carry_forward."""
    job = {
        "board": "adzuna",
        "source_url": "https://adzuna.fr/99",
        "title": "Senior Product Manager",
        "company_name": "SomeCompany",
        "location": "Paris",
        "posted_at": "2026-06-01",
        "description_snippet": "PM role.",
        "contract_type": "Permanent",
        "country": "FR",
    }
    deduped = _dedup_jobs([job])
    carry_forward = {
        "status": "Applied",
        "notes": "interviewing",
        "also_seen_on": [],
        "first_seen": "2026-05-20",
    }
    row = _build_sheet_row(deduped[0], carry_forward, "2026-06-09")
    assert row[12] == "Applied"   # M = Status
    assert row[13] == "interviewing"  # N = Notes


# ---------------------------------------------------------------------------
# Test: Jaccard collision case — two distinct roles at same company → keep both
# ---------------------------------------------------------------------------


def test_jaccard_different_descriptions_kept():
    """Two jobs at the same (company, title, location) but with very different
    descriptions (Jaccard < 0.4) must both survive dedup as distinct rows.
    """
    base = {
        "board": "adzuna",
        "source_url": "https://adzuna.fr/A",
        "title": "Product Manager",
        "company_name": "BigCorp",
        "location": "Paris",
        "posted_at": "2026-06-01",
        "description_snippet": "The quick brown fox jumps over the lazy dog product roadmap.",
        "contract_type": "Permanent",
        "country": "FR",
    }
    duplicate = {
        "board": "jooble",
        "source_url": "https://jooble.fr/B",
        "title": "Product Manager",
        "company_name": "BigCorp",
        "location": "Paris",
        "posted_at": "2026-06-02",
        # Completely different description
        "description_snippet": "Completely different text: quantum computing blockchain NFT metaverse AI.",
        "contract_type": "Permanent",
        "country": "FR",
    }
    deduped = _dedup_jobs([base, duplicate])
    assert len(deduped) == 2, "Two distinct roles at same company must both be kept."


def test_jaccard_similar_descriptions_merged():
    """Two jobs at the same (company, title, location) with near-identical descriptions
    (Jaccard >= 0.4) must be merged into one row.
    """
    description = "Looking for a senior product manager to lead our platform roadmap."
    base = {
        "board": "adzuna",
        "source_url": "https://adzuna.fr/X",
        "title": "Senior Product Manager",
        "company_name": "TechCo",
        "location": "Lyon",
        "posted_at": "2026-06-01",
        "description_snippet": description,
        "contract_type": "Permanent",
        "country": "FR",
    }
    dup = {
        "board": "jooble",
        "source_url": "https://jooble.fr/Y",
        "title": "Senior Product Manager",
        "company_name": "TechCo",
        "location": "Lyon",
        "posted_at": "2026-06-01",
        "description_snippet": description + " Minor variation.",
        "contract_type": "Permanent",
        "country": "FR",
    }
    deduped = _dedup_jobs([base, dup])
    assert len(deduped) == 1, "Near-identical descriptions must be merged."
    assert "jooble" in deduped[0].get("also_seen_on", [])


# ---------------------------------------------------------------------------
# Test: Status / Notes preservation via _build_sheet_row
# ---------------------------------------------------------------------------


def test_status_default_new_when_no_carry_forward():
    """Without a carry-forward, Status defaults to 'New'."""
    job = {
        "board": "adzuna",
        "source_url": "https://adzuna.fr/Z",
        "title": "AI PM",
        "company_name": "Foo",
        "location": "Paris",
        "posted_at": "2026-06-01",
        "description_snippet": "AI PM at Foo.",
        "contract_type": "CDI",
        "country": "FR",
        "dedup_hash": "abc123",
    }
    row = _build_sheet_row(job, None, "2026-06-09")
    assert row[12] == "New"


def test_dedup_hash_deterministic():
    """dedup_hash for a given (company, title, location) must be deterministic."""
    company = normalize_company("Mistral AI")
    title = normalize_title("Senior Product Manager")
    location = "paris"
    h1 = compute_job_hash(company, title, location)
    h2 = compute_job_hash(company, title, location)
    assert h1 == h2


# ---------------------------------------------------------------------------
# Test: Title assignment
# ---------------------------------------------------------------------------


def test_assign_titles_matches_synonyms():
    """A job with title 'AI Product Manager' should match the 'AI PM' tab."""
    from execution.custom_scrapers.adzuna_jobs import _map_adzuna_job  # noqa: PLC0415 — local import

    titles_config = {
        "PM": {
            "synonyms": ["product manager", "chef de produit"],
            "tab": "PM",
        },
        "AI PM": {
            "synonyms": ["ai product manager", "product manager ai", "ml product manager"],
            "tab": "AI PM",
        },
    }
    job = {"title": "AI Product Manager — LLM Applications"}
    tabs = _assign_titles(job, titles_config)
    assert "AI PM" in tabs


def test_assign_titles_no_match():
    """A job with an unrelated title should match no tabs."""
    titles_config = {
        "PM": {"synonyms": ["product manager"], "tab": "PM"},
    }
    job = {"title": "Software Engineer — Backend Python"}
    tabs = _assign_titles(job, titles_config)
    assert tabs == []


# ---------------------------------------------------------------------------
# Test: _jaccard_trigram edge cases
# ---------------------------------------------------------------------------


def test_jaccard_both_empty_returns_zero():
    """Two empty strings must return 0.0, not 1.0.

    Returning 1.0 would auto-merge any two jobs that both lack a description
    snippet, defeating the purpose of the Jaccard guard.
    """
    assert _jaccard_trigram("", "") == 0.0


def test_jaccard_one_empty_returns_zero():
    """One empty, one non-empty → 0.0 (no similarity, no merge)."""
    assert _jaccard_trigram("", "some description text here") == 0.0
    assert _jaccard_trigram("some description text here", "") == 0.0


def test_jaccard_identical_nonempty_returns_one():
    """Sanity: identical non-empty strings must still return 1.0."""
    text = "Looking for a senior product manager to lead our platform roadmap."
    assert _jaccard_trigram(text, text) == 1.0
