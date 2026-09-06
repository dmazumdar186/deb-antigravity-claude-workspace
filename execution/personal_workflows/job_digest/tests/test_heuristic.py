"""
description: Offline tests for ranker/heuristic.py — combine() weighting/hard-zero
    rule and score_heuristic()'s Profile-driven dimension scoring.
inputs: none (synthetic NormalizedJob fixtures via tests/_helpers.py)
outputs: pytest assertions
"""

from __future__ import annotations

import logging

from ..contracts import ContractType, JobTier, RemoteMode
from ..profile_schema import Profile
from ..ranker.heuristic import combine, score_heuristic, tier_for
from ._helpers import load_test_profile, make_normalized_job


def _profile_with_must_have(must_have: list[str]) -> Profile:
    raw = {
        "version": 1,
        "candidate": {"name": "Test Candidate", "email": "test@example.com"},
        "roles": [{"title": "Sales Manager", "synonyms": [], "seniority": "any"}],
        "locations": {"countries": ["FR"], "cities": [], "remote_ok": True},
        "screening": {"summary": "A" * 50, "skills": [], "must_have": must_have, "nice_to_have": []},
    }
    return Profile.model_validate(raw)


def test_combine_hard_zero_on_title_fit() -> None:
    dims = {"title_fit": 0.0, "skill_overlap": 1.0, "contract_fit": 1.0, "seniority_fit": 1.0, "location_fit": 1.0}
    assert combine(dims) == 0.0


def test_combine_weighted_average() -> None:
    dims = {"title_fit": 1.0, "skill_overlap": 1.0, "contract_fit": 1.0, "seniority_fit": 1.0, "location_fit": 1.0}
    assert combine(dims) == 1.0


def test_tier_thresholds() -> None:
    assert tier_for(0.80) == JobTier.A
    assert tier_for(0.60) == JobTier.B
    assert tier_for(0.30) == JobTier.C
    assert tier_for(0.10) == JobTier.SKIP


def test_strong_match_scores_tier_a() -> None:
    profile = load_test_profile()
    job = make_normalized_job(
        title="Senior Sales Manager",
        location="Paris",
        description_snippet="Lead B2B sales team leadership using our CRM and SaaS platform.",
        contract_type=ContractType.CDI,
        contract_type_raw="CDI",
    )
    [ranked] = score_heuristic([job], profile)
    assert ranked.tier in (JobTier.A, JobTier.B)
    assert ranked.ranker_model == "heuristic-v1"


def test_wrong_role_scores_zero() -> None:
    profile = load_test_profile()
    job = make_normalized_job(title="Backend Software Engineer", location="Paris")
    [ranked] = score_heuristic([job], profile)
    assert ranked.score == 0.0
    assert ranked.tier == JobTier.SKIP


def test_remote_job_gets_full_location_fit_when_remote_ok() -> None:
    profile = load_test_profile()
    job = make_normalized_job(
        title="Sales Manager",
        location="Remote",
        remote_mode=RemoteMode.REMOTE,
    )
    [ranked] = score_heuristic([job], profile)
    # location_fit alone isn't directly exposed, but a remote+title match must
    # not hard-zero on location (it would if location_fit resolved to 0.0).
    assert ranked.score > 0.0


def test_must_have_missing_penalizes_skill_overlap_not_hard_zero() -> None:
    """M2: a missing must-have keyword must NOT hard-zero title_fit — it
    should halve skill_overlap and flag must_have_missing in reasoning."""
    profile = _profile_with_must_have(["Salesforce"])
    job = make_normalized_job(
        title="Sales Manager",
        location="Paris",
        description_snippet="Lead our team using HubSpot CRM.",  # no "Salesforce" mention
    )
    [ranked] = score_heuristic([job], profile)
    assert ranked.score > 0.0  # never hard-zeroed
    assert "must_have_missing" in ranked.reasoning


def test_must_have_present_no_penalty_flag() -> None:
    profile = _profile_with_must_have(["Salesforce"])
    job = make_normalized_job(
        title="Sales Manager",
        location="Paris",
        description_snippet="Lead our team using Salesforce CRM.",
    )
    [ranked] = score_heuristic([job], profile)
    assert "must_have_missing" not in ranked.reasoning


def test_must_have_batch_warning_logged_over_80_percent(caplog) -> None:
    profile = _profile_with_must_have(["Salesforce"])
    jobs = [
        make_normalized_job(
            title=f"Sales Manager {i}",
            location="Paris",
            description_snippet="Lead a team using HubSpot.",
            url=f"https://example.com/jobs/{i}",
        )
        for i in range(5)
    ]
    with caplog.at_level(logging.WARNING, logger="job_digest.ranker.heuristic"):
        score_heuristic(jobs, profile)
    assert any("must_have penalized" in rec.message for rec in caplog.records)


def test_location_fit_city_match_scores_full() -> None:
    profile = load_test_profile()  # countries FR, IN; cities ["Paris"]
    job = make_normalized_job(title="Sales Manager", location="Paris")
    [ranked] = score_heuristic([job], profile)
    assert "location=1.00" in ranked.reasoning


def test_location_fit_country_match_without_city_constraint_scores_0_8() -> None:
    profile = load_test_profile()  # cities=["Paris"] only belongs to FR
    job = make_normalized_job(title="Sales Manager", location="Bengaluru, India")
    [ranked] = score_heuristic([job], profile)
    assert "location=0.80" in ranked.reasoning


def test_location_fit_country_match_with_city_mismatch_scores_0_7() -> None:
    profile = load_test_profile()  # wants Paris specifically (FR)
    job = make_normalized_job(title="Sales Manager", location="Lyon, France")
    [ranked] = score_heuristic([job], profile)
    assert "location=0.70" in ranked.reasoning
