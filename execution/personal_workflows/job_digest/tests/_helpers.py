"""
description: Shared test helpers for job_digest's offline test suite.
inputs: none (pure helper functions)
outputs: factory functions used by tests/test_*.py to build NormalizedJob /
    SourceJob fixtures and load the shared test profile without hitting the
    network or any real credentials.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..contracts import (
    ContractType,
    JobSource,
    NormalizedJob,
    RemoteMode,
    SourceJob,
    canonicalize_url,
    compute_content_hash,
)
from ..profile_schema import Profile, load_profile

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
TEST_PROFILE_PATH = FIXTURES_DIR / "profile_test.yaml"


def load_test_profile() -> Profile:
    return load_profile(TEST_PROFILE_PATH)


def make_normalized_job(
    *,
    title: str,
    company: str = "Acme Corp",
    location: str = "Paris",
    description_snippet: str = "",
    contract_type: ContractType = ContractType.CDI,
    contract_type_raw: str = "CDI",
    remote_mode: RemoteMode = RemoteMode.UNKNOWN,
    source: JobSource = JobSource.FIXTURE,
    source_id: str | None = None,
    url: str = "https://example.com/jobs/1",
) -> NormalizedJob:
    canonical = canonicalize_url(url)
    content_hash = compute_content_hash(title, company, canonical)
    return NormalizedJob(
        source=source,
        source_id=source_id or content_hash[:12],
        url=url,
        canonical_url=canonical,
        title=title,
        company=company,
        location=location,
        description_snippet=description_snippet,
        posted_at=datetime.now(timezone.utc),
        contract_type=contract_type,
        contract_type_raw=contract_type_raw,
        remote_mode=remote_mode,
        fetched_at=datetime.now(timezone.utc),
        content_hash=content_hash,
    )


def make_source_job(
    *,
    title: str,
    company: str = "Acme Corp",
    location_raw: str = "Paris",
    description_snippet: str = "",
    contract_type_raw: str = "CDI",
    source: JobSource = JobSource.FIXTURE,
    source_id: str | None = None,
    url: str = "https://example.com/jobs/1",
) -> SourceJob:
    return SourceJob(
        source=source,
        source_id=source_id or title.replace(" ", "-").lower(),
        url=url,
        title=title,
        company=company,
        location_raw=location_raw,
        description_snippet=description_snippet,
        contract_type_raw=contract_type_raw,
    )
