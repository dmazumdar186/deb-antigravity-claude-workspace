"""
description: Offline tests for acceptance.py's generic sanity gate.
inputs: none (synthetic NormalizedJob/RankedJob fixtures)
outputs: pytest assertions
"""

from __future__ import annotations

from .. import acceptance
from ..contracts import JobTier, RankedJob
from ._helpers import load_test_profile, make_normalized_job


def _ranked(job, score: float = 0.8, tier: JobTier = JobTier.A) -> RankedJob:
    return RankedJob(
        content_hash=job.content_hash,
        score=score,
        tier=tier,
        reasoning="test reasoning",
        rubric_version="test-v1",
        ranker_model="test",
    )


def test_empty_digest_passes() -> None:
    profile = load_test_profile()
    passed, problems = acceptance.check([], profile)
    assert passed is True
    assert problems == []


def test_healthy_digest_passes() -> None:
    profile = load_test_profile()
    jobs = [
        make_normalized_job(title="Sales Manager", location="Paris", url="https://example.com/1"),
        make_normalized_job(title="Regional Sales Manager", location="Bengaluru, India", url="https://example.com/2"),
    ]
    digest = [(j, _ranked(j)) for j in jobs]
    passed, problems = acceptance.check(digest, profile)
    assert passed is True
    assert problems == []


def test_wrong_role_majority_fails() -> None:
    profile = load_test_profile()
    jobs = [
        make_normalized_job(title="Backend Engineer", location="Paris", url="https://example.com/1"),
        make_normalized_job(title="Data Scientist", location="Paris", url="https://example.com/2"),
    ]
    digest = [(j, _ranked(j)) for j in jobs]
    passed, problems = acceptance.check(digest, profile)
    assert passed is False
    assert any("title-match" in p for p in problems)


def test_wrong_country_majority_fails() -> None:
    profile = load_test_profile()
    jobs = [
        make_normalized_job(title="Sales Manager", location="Berlin, Germany", url="https://example.com/1"),
        make_normalized_job(title="Sales Manager", location="London, UK", url="https://example.com/2"),
    ]
    digest = [(j, _ranked(j)) for j in jobs]
    passed, problems = acceptance.check(digest, profile)
    assert passed is False
    assert any("country or remote" in p for p in problems)


def test_excluded_title_fails() -> None:
    profile = load_test_profile()
    jobs = [
        make_normalized_job(title="Sales Manager Intern", location="Paris", url="https://example.com/1"),
    ]
    digest = [(j, _ranked(j)) for j in jobs]
    passed, problems = acceptance.check(digest, profile)
    assert passed is False
    assert any("excluded title" in p for p in problems)


def test_70_percent_title_match_fails_below_80_threshold() -> None:
    """M3: exactly a 70%-match digest must FAIL (below the 80% threshold)."""
    profile = load_test_profile()
    matching = [
        make_normalized_job(title="Sales Manager", location="Paris", url=f"https://example.com/m{i}")
        for i in range(7)
    ]
    non_matching = [
        make_normalized_job(title="Backend Engineer", location="Paris", url=f"https://example.com/x{i}")
        for i in range(3)
    ]
    digest = [(j, _ranked(j)) for j in (matching + non_matching)]
    passed, problems = acceptance.check(digest, profile)
    assert passed is False
    assert any("7/10" in p and "70%" in p for p in problems)


def test_missing_company_fails() -> None:
    """M3 rule (c): every row must have a non-empty company and a URL with a host."""
    profile = load_test_profile()
    job = make_normalized_job(title="Sales Manager", location="Paris", company="", url="https://example.com/1")
    digest = [(job, _ranked(job))]
    passed, problems = acceptance.check(digest, profile)
    assert passed is False
    assert any("missing company or a URL host" in p for p in problems)


def test_independent_from_filters_and_heuristic() -> None:
    """M3: acceptance.py must not import normalizer.filters or ranker.heuristic
    helpers — it is a deliberately independent re-check."""
    import inspect

    from .. import acceptance as acceptance_module

    src = inspect.getsource(acceptance_module)
    assert "from .normalizer" not in src
    assert "from .ranker" not in src
