"""Unit tests for job_search_v2.contracts — verify the enum additions and SourceJob
validation behave correctly after the 2026-06-18 source rewrite.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from execution.personal_workflows.job_search_v2.contracts import (
    JobSource,
    SourceJob,
    canonicalize_url,
    compute_content_hash,
)


def test_jobsource_enum_includes_new_api_sources():
    """The 2026-06-18 rewrite added LINKEDIN_GUEST_API + WTTJ_ALGOLIA. Both must be
    in the enum so adapters can construct SourceJob(source=...) without runtime errors.
    """
    assert JobSource.LINKEDIN_GUEST_API.value == "linkedin_guest_api"
    assert JobSource.WTTJ_ALGOLIA.value == "wttj_algolia"
    # Legacy sources must still exist (orchestrator opt-in path):
    assert JobSource.LINKEDIN_GMAIL.value == "linkedin_gmail"
    assert JobSource.WTTJ.value == "wttj"


def test_source_job_round_trips_through_json():
    """SourceJob → JSON → SourceJob must be byte-identical so the orchestrator's
    per-source JSONL persistence works."""
    sj = SourceJob(
        source=JobSource.LINKEDIN_GUEST_API,
        source_id="4428049765",
        url="https://fr.linkedin.com/jobs/view/product-owner-aem-h-f-at-nexton-4428049765",
        title="Product Owner AEM H/F",
        company="NEXTON",
        location_raw="Paris, Île-de-France, France",
        posted_at=datetime(2026, 6, 16, tzinfo=timezone.utc),
    )
    payload = sj.model_dump_json()
    restored = SourceJob.model_validate_json(payload)
    assert restored.source == sj.source
    assert restored.source_id == sj.source_id
    assert restored.title == sj.title


def test_source_job_rejects_empty_required_fields():
    """Empty title/company/source_id must raise — this protects dedup, which keys
    on `title|company|canonical_url`. An empty field collapses unrelated jobs."""
    with pytest.raises(ValidationError):
        SourceJob(
            source=JobSource.WTTJ_ALGOLIA,
            source_id="",  # empty
            url="https://example.com",
            title="x",
            company="y",
        )
    with pytest.raises(ValidationError):
        SourceJob(
            source=JobSource.WTTJ_ALGOLIA,
            source_id="1",
            url="https://example.com",
            title="",  # empty
            company="y",
        )


def test_canonicalize_url_strips_tracking_params():
    """LinkedIn cards carry utm_source/utm_medium etc.; canonical must drop them so
    the dedup key doesn't collide across campaigns of the same posting."""
    url = "https://fr.linkedin.com/jobs/view/abc-123?utm_source=email&utm_medium=alert&trk=feed"
    canon = canonicalize_url(url)
    assert "utm_source" not in canon
    assert "utm_medium" not in canon
    assert "trk" not in canon
    assert canon.startswith("https://fr.linkedin.com/")


def test_content_hash_is_stable_and_collision_resistant():
    """compute_content_hash must be deterministic across runs (used as the seen-set
    primary key in the SQLite dedup DB)."""
    h1 = compute_content_hash("Senior PM", "NEXTON", "https://example.com/jobs/1")
    h2 = compute_content_hash("Senior PM", "NEXTON", "https://example.com/jobs/1")
    h3 = compute_content_hash("Senior PM", "OTHER", "https://example.com/jobs/1")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 64  # sha256 hex
