"""
description: Offline tests for normalizer/normalize.py's _detect_remote (C3).
inputs: none (uses the exact location strings shipped in tests/fixtures*)
outputs: pytest assertions
"""

from __future__ import annotations

from ..contracts import JobSource, RemoteMode
from ..normalizer.normalize import _detect_remote, batch_normalize
from ._helpers import make_source_job


def test_bare_remote_location_strings_are_remote() -> None:
    """Exact strings RemoteOK/WeWorkRemotely put in location_raw — none of
    these name a city/region, so they must resolve to REMOTE, not HYBRID
    (C3: was defaulting to HYBRID, which filters then dropped)."""
    for loc in [
        "Remote",
        "Remote (Worldwide)",
        "Remote (US)",
        "Remote (EU)",
        "Remote (Canada)",
        "Remote (Anywhere)",
        "Remote (US Time Zones)",
        "Remote (Europe)",
        "Anywhere",
        "Worldwide",
    ]:
        assert _detect_remote(loc, "") == RemoteMode.REMOTE, loc


def test_n7_additional_bare_remote_location_strings_are_remote() -> None:
    """N7: additional real-world bare-remote location strings."""
    for loc in [
        "Remote US",
        "Remote - Europe",
        "Anywhere in the World",
        "Work from anywhere",
        "100% télétravail",
    ]:
        assert _detect_remote(loc, "") == RemoteMode.REMOTE, loc


def test_hybrid_location_string() -> None:
    assert _detect_remote("Hybrid - Paris, France", "") == RemoteMode.HYBRID
    assert _detect_remote("Hybride - Lyon", "") == RemoteMode.HYBRID


def test_onsite_location_string() -> None:
    assert _detect_remote("On-site - Berlin, Germany", "") == RemoteMode.ONSITE
    assert _detect_remote("Présentiel - Paris", "") == RemoteMode.ONSITE


def test_city_location_falls_through_to_description_heuristic() -> None:
    # A real city name is not a bare-remote string, so it must not be
    # short-circuited to REMOTE just because the description mentions remote work.
    assert _detect_remote("Paris, Île-de-France, France", "") == RemoteMode.UNKNOWN
    assert (
        _detect_remote("Berlin, Germany", "This role is hybrid, 3 days in office.")
        == RemoteMode.HYBRID
    )


def test_batch_normalize_merges_cross_source_same_title_company_duplicates() -> None:
    """MEDIUM fix: two rows from different sources with the same folded
    (title, company) but different URLs (so different content_hash) must be
    merged into one digest row — the first kept, the second folded into
    also_seen_on — rather than appearing twice."""
    linkedin_job = make_source_job(
        title="Sales Manager",
        company="Acme Corp",
        url="https://linkedin.com/jobs/view/12345",
        source=JobSource.LINKEDIN_GUEST_API,
    )
    wttj_job = make_source_job(
        title="  Sales Manager  ",  # extra whitespace + same folded key
        company="ACME CORP",  # different casing, same folded key
        url="https://welcometothejungle.com/en/companies/acme/jobs/sales-manager",
        source=JobSource.WTTJ_ALGOLIA,
    )

    result = batch_normalize([linkedin_job, wttj_job])

    assert len(result) == 1
    merged = result[0]
    assert merged.source == JobSource.LINKEDIN_GUEST_API  # first-seen kept
    assert JobSource.WTTJ_ALGOLIA in merged.also_seen_on


def test_batch_normalize_keeps_distinct_title_company_pairs_separate() -> None:
    job_a = make_source_job(title="Sales Manager", company="Acme Corp", url="https://example.com/a")
    job_b = make_source_job(title="Account Executive", company="Acme Corp", url="https://example.com/b")

    result = batch_normalize([job_a, job_b])

    assert len(result) == 2
