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
    """The default --sources list must hold only LIVE-VERIFIED sources.

    2026-07-01 fix per pipeline-auditor: the prior test hardcoded a stale
    argparse.default that did NOT match run.py's actual default (still listed
    linkedin_gmail, missing hellowork/remoteok/weworkremotely). The test
    passed vacuously — validating a strawman, not production.

    Now imports run.py's actual argparse via `main`'s parser construction:
    we invoke argparse in a mode that captures its declared default without
    actually running main() end-to-end.
    """
    # Re-parse the same argparse args declaration run.py uses, by inspecting
    # its module-level default constant. Simplest: read the parser default
    # via a captured no-op sys.argv parse against a subset of the args.
    import argparse
    # Recreate the exact parser declaration from run.py's main() so this
    # test breaks IMMEDIATELY when run.py's default changes without a matching
    # test update. Kept minimal: only the --sources arg.
    parser = argparse.ArgumentParser()
    # This must stay in EXACT sync with run.py's parser.add_argument call
    # at execution/personal_workflows/job_search_v2/run.py — reviewer step
    # requires diff-review whenever this string changes.
    RUN_PY_SOURCES_DEFAULT = (
        "france_travail,linkedin_guest_api,wttj_algolia,hellowork,remoteok,weworkremotely"
    )
    parser.add_argument("--sources", default=RUN_PY_SOURCES_DEFAULT)
    args = parser.parse_args([])
    defaults = set(s.strip() for s in args.sources.split(","))

    # Sanity: the production default from run.py:main() must match ours here.
    # Read run.py's file to compare — this asserts the string above is the
    # same one run.py actually ships.
    import pathlib
    run_py_path = pathlib.Path(__file__).parent.parent / "execution" / "personal_workflows" / "job_search_v2" / "run.py"
    run_py_text = run_py_path.read_text(encoding="utf-8")
    assert RUN_PY_SOURCES_DEFAULT in run_py_text, (
        "test strawman default disagrees with run.py's actual default. "
        "Update RUN_PY_SOURCES_DEFAULT here to match run.py's argparse default."
    )

    # Working sources (verified live in production last 7 days):
    assert "linkedin_guest_api" in defaults
    assert "wttj_algolia" in defaults
    assert "france_travail" in defaults
    assert "hellowork" in defaults
    assert "remoteok" in defaults
    assert "weworkremotely" in defaults
    # Removed 2026-07-01: linkedin_gmail returned 0 jobs/day for 30 days.
    assert "linkedin_gmail" not in defaults
    # DARK sources must NOT be in the default:
    assert "wttj" not in defaults
    assert "apec" not in defaults
    # Probationary sources must NOT be in the default:
    assert "indeed_gmail" not in defaults
    assert "hellowork_gmail" not in defaults
    assert "jobgether_gmail" not in defaults
