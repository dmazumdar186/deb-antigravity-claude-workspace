"""
description: Offline tests for ranker/rank.py's dispatcher — signature (M4:
    rank() -> tuple[list[RankedJob], dict[str, str]]) and rung bookkeeping.
inputs: none (synthetic NormalizedJob fixtures via tests/_helpers.py)
outputs: pytest assertions
"""

from __future__ import annotations

from ..ranker.rank import rank
from ._helpers import load_test_profile, make_normalized_job


def test_rank_returns_tuple_of_list_and_rungs_dict() -> None:
    profile = load_test_profile()
    job = make_normalized_job(title="Sales Manager", location="Paris")

    result = rank([job], profile)

    assert isinstance(result, tuple)
    assert len(result) == 2
    ranked, rungs = result
    assert isinstance(ranked, list)
    assert isinstance(rungs, dict)
    assert ranked[0].content_hash == job.content_hash


def test_rank_no_keys_reports_skipped_no_key_for_both_optional_rungs() -> None:
    profile = load_test_profile()
    job = make_normalized_job(title="Sales Manager", location="Paris")

    _, rungs = rank([job], profile, gemini_key=None, anthropic_key=None)

    assert rungs["heuristic"] == "ran"
    assert rungs["gemini"] == "skipped:no_key"
    assert rungs["anthropic"] == "skipped:no_key"


def test_rank_empty_jobs_reports_skipped_no_jobs_for_every_rung() -> None:
    profile = load_test_profile()

    ranked, rungs = rank([], profile)

    assert ranked == []
    assert rungs == {
        "heuristic": "skipped:no_jobs",
        "gemini": "skipped:no_jobs",
        "anthropic": "skipped:no_jobs",
    }


def test_rank_anthropic_rung_failure_is_reported_not_raised(monkeypatch) -> None:
    from .. import ranker

    profile = load_test_profile()
    job = make_normalized_job(title="Sales Manager", location="Paris")

    def boom(*a, **k):
        raise RuntimeError("anthropic API exploded")

    monkeypatch.setattr(ranker.rank, "rerank_anthropic", boom)

    ranked, rungs = rank([job], profile, anthropic_key="fake-key")

    assert rungs["anthropic"] == "failed:RuntimeError"
    # Heuristic scores still stand — ranking is never lost to an LLM rung failure.
    assert len(ranked) == 1


def test_gemini_partial_result_merges_per_hash(monkeypatch) -> None:
    """A Gemini rung that returns only some jobs overrides those and keeps the
    heuristic score for the rest, reporting the rung as partial."""
    from ..contracts import JobTier, RankedJob
    from ..ranker import rank as rank_module
    from ._helpers import load_test_profile, make_normalized_job

    profile = load_test_profile()
    jobs = [
        make_normalized_job(title="Sales Manager", location="Paris", url="https://example.com/a"),
        make_normalized_job(title="Sales Manager", location="Paris", url="https://example.com/b"),
    ]

    def fake_gemini(js, prof, key):
        return [RankedJob(content_hash=js[0].content_hash, score=0.99, tier=JobTier.A,
                          reasoning="gemini", rubric_version="t", ranker_model="gemini")]

    monkeypatch.setattr(rank_module, "score_gemini", fake_gemini)
    ranked, rungs = rank_module.rank(jobs, profile, gemini_key="k", anthropic_key=None)
    assert rungs["gemini"].startswith("ran:partial 1/2")
    by_hash = {r.content_hash: r for r in ranked}
    assert by_hash[jobs[0].content_hash].ranker_model == "gemini"
    assert by_hash[jobs[1].content_hash].ranker_model != "gemini"
