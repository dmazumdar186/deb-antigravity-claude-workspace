"""Parser tests for sources/wttj_algolia.py.

Tests the Algolia-hit → SourceJob mapping against minimal fixtures that mimic the
WTTJ Algolia response shape observed on 2026-06-18. Per the 2026-06-18 front-door
tightening, fixture tests are parser tests, not synthetics.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from execution.personal_workflows.job_search_v2.contracts import JobSource
from execution.personal_workflows.job_search_v2.sources import wttj_algolia as wa


def _hit(
    object_id: str = "4129304",
    name: str = "Senior Product Manager",
    org_name: str = "LumApps",
    org_slug: str = "lumapps",
    slug: str = "senior-product-manager",
    published_at: str | None = None,
    contract_type: str = "FULL_TIME",
    country: str = "France",
    city: str = "Paris",
) -> dict:
    """Build a minimal Algolia hit matching the observed live shape."""
    if published_at is None:
        published_at = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
    return {
        "objectID": object_id,
        "name": name,
        "slug": slug,
        "organization": {"name": org_name, "slug": org_slug},
        "offices": [{"city": city, "country": country, "country_code": "FR"}],
        "published_at": published_at,
        "contract_type": contract_type,
    }


def test_hit_to_source_job_extracts_fields():
    sj = wa._hit_to_source_job(_hit())
    assert sj is not None
    assert sj.source == JobSource.WTTJ_ALGOLIA
    assert sj.source_id == "4129304"
    assert sj.title == "Senior Product Manager"
    assert sj.company == "LumApps"
    assert "Paris" in sj.location_raw
    assert "lumapps/jobs/senior-product-manager" in str(sj.url)
    assert sj.contract_type_raw == "FULL_TIME"
    assert sj.posted_at is not None
    assert sj.posted_at.tzinfo is not None


def test_hit_to_source_job_skips_missing_org_or_slug():
    """The canonical job URL needs both org_slug and slug — without them, we cannot
    construct a stable URL, so the hit must be dropped (rather than emit a URL that
    leads to a 404)."""
    h = _hit()
    h["organization"]["slug"] = ""
    assert wa._hit_to_source_job(h) is None

    h = _hit()
    h["slug"] = ""
    assert wa._hit_to_source_job(h) is None


def test_hit_to_source_job_handles_missing_offices():
    """Some Algolia hits ship `office` (singular dict) instead of `offices` (list)."""
    h = _hit()
    h["offices"] = []
    h["office"] = {"city": "Lyon", "country": "France"}
    sj = wa._hit_to_source_job(h)
    assert sj is not None
    assert "Lyon" in sj.location_raw


def test_age_hours_parses_iso_with_offset():
    """Algolia ships `published_at` as `2026-06-16T16:00:00.000+02:00` — must parse."""
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    age = wa._age_hours(one_hour_ago)
    assert age is not None
    assert 0.5 < age < 2.0  # ~1 hour


def test_age_hours_returns_none_on_garbage():
    assert wa._age_hours("") is None
    assert wa._age_hours("not-a-date") is None


def test_fetch_from_fixture_parses_hits_array():
    """The fixture mode reads the raw Algolia response shape: {hits: [...], nbPages: N}."""
    fixture = {
        "hits": [_hit("1", "Job One"), _hit("2", "Job Two")],
        "nbPages": 1,
        "nbHits": 2,
    }
    # Write a temp fixture
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tmp:
        json.dump(fixture, tmp)
        tmp_path = Path(tmp.name)
    try:
        jobs = wa.fetch_from_fixture(tmp_path)
        assert len(jobs) == 2
        titles = {j.title for j in jobs}
        assert titles == {"Job One", "Job Two"}
    finally:
        tmp_path.unlink()


def test_fetch_from_fixture_dedups_within_batch():
    """Live WTTJ returns clones of the same posting under different objectIDs. The
    fixture reader dedups by objectID before emitting SourceJobs (the orchestrator's
    normalizer then dedupes by content_hash for cross-source collapse)."""
    fixture = {"hits": [_hit("1"), _hit("1"), _hit("1")]}
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tmp:
        json.dump(fixture, tmp)
        tmp_path = Path(tmp.name)
    try:
        jobs = wa.fetch_from_fixture(tmp_path)
        assert len(jobs) == 1  # the three duplicate objectIDs collapse to one
    finally:
        tmp_path.unlink()


def test_fetch_from_fixture_missing_file_returns_empty():
    assert wa.fetch_from_fixture(Path("/nonexistent/x.json")) == []
