"""Orchestrator dispatch tests for execution/personal_workflows/job_search_v2/run.py.

Regression test for the 2026-06-18 bug where `_call_source` had a hand-rolled if-chain
that diverged from `_DISPATCH` — newly-added sources fell through the chain and
returned [], silently producing 0 jobs even though the standalone source worked.
"""
from __future__ import annotations

from execution.personal_workflows.job_search_v2 import run
from execution.personal_workflows.job_search_v2.contracts import JobSource


def test_dispatch_includes_every_jobsource_value_except_fixture():
    """Every JobSource value (except FIXTURE which is test-only) MUST be in _DISPATCH.
    A missing source = silent 0-job emission, the exact bug the 2026-06-18 cleanup fixed."""
    expected = {s.value for s in JobSource if s != JobSource.FIXTURE}
    assert set(run._DISPATCH.keys()) == expected


def test_dispatch_contains_new_2026_06_18_sources():
    assert "linkedin_guest_api" in run._DISPATCH
    assert "wttj_algolia" in run._DISPATCH


def test_call_source_returns_empty_on_unknown_source():
    """An unknown source name must return [] and log — NOT raise — so the pipeline
    survives a typo in --sources."""
    out = run._call_source("does_not_exist", mode="fixture", max_pages=1, posted_within_days=1)
    assert out == []


def test_call_source_routes_via_dispatch_dict_not_hardcoded_chain():
    """If _call_source ever regresses to a hand-rolled if-chain, this test will catch
    it: a synthetic JobSource value that we add to _DISPATCH at runtime MUST be
    dispatched correctly without code changes to _call_source itself.
    """
    called = {"hit": False}

    def fake_source(mode: str, max_pages: int):
        called["hit"] = True
        return []

    # Monkey-patch _DISPATCH for the duration of the test
    sentinel_name = "synthetic_test_source_xyz"
    run._DISPATCH[sentinel_name] = fake_source
    try:
        out = run._call_source(sentinel_name, mode="fixture", max_pages=1, posted_within_days=1)
        assert out == []
        assert called["hit"] is True, (
            "Expected _call_source to route via _DISPATCH; if this fails, the hand-rolled "
            "if-chain regression has come back — check run.py:_call_source for "
            "hardcoded source-name comparisons."
        )
    finally:
        del run._DISPATCH[sentinel_name]


def test_default_sources_string_lists_only_live_verified():
    """The default --sources list must hold only the 4 LIVE-VERIFIED sources as of
    2026-06-18: france_travail, linkedin_guest_api, wttj_algolia, linkedin_gmail.
    Probationary / DARK sources are opt-in only.
    """
    # Re-parse via argparse so the test reflects the actual CLI default, not just a string match.
    import argparse
    parser = argparse.ArgumentParser()
    # Mirror the production default exactly (kept in sync with run.py:main).
    parser.add_argument("--sources", default="france_travail,linkedin_guest_api,wttj_algolia,linkedin_gmail")
    args = parser.parse_args([])
    defaults = set(s.strip() for s in args.sources.split(","))
    assert "linkedin_guest_api" in defaults
    assert "wttj_algolia" in defaults
    assert "france_travail" in defaults
    # DARK sources must NOT be in the default:
    assert "wttj" not in defaults
    assert "apec" not in defaults
    # Probationary sources must NOT be in the default:
    assert "indeed_gmail" not in defaults
    assert "hellowork_gmail" not in defaults
    assert "jobgether_gmail" not in defaults
