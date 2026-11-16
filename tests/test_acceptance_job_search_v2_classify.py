"""
description: Unit tests for the acceptance gate's BLOCKING vs ADVISORY split
    (2026-11-16): a ranker outage must yield DEGRADED (exit 2, digest ships);
    any blocking failure (e.g. source coverage) must still yield FAIL (exit 1).
inputs: none (fake stats tempfile under .tmp/ via CURRENT_RUN_STATS_PATH; fake sheet)
outputs: pytest results only; temp files are removed.
"""

from __future__ import annotations

import json
import shutil
import sys
import uuid
from pathlib import Path

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

import tests.acceptance_job_search_v2 as acc  # noqa: E402

SOURCES = [
    "france_travail",
    "linkedin_guest_api",
    "wttj_algolia",
    "hellowork",
    "remoteok",
    "weworkremotely",
]


def _healthy_stats() -> dict:
    return {
        "mode": "live",
        "dry_run": False,
        "ranker": {"requested": 40, "placeholder": 0, "chunk_failures": []},
        "verification": {"disabled": False, "strict": True, "warnings": []},
        "per_source": {s: 10 for s in SOURCES},
        "sheet_ok": True,
        "top_matches_ok": True,
        "after_dedup_new": 12,
        "sheet_appended": 5,
    }


@pytest.fixture
def stats_env(monkeypatch):
    """Write stats into a scratch dir under .tmp/ (the path guard requires it)
    and point RUN_LOG_PATH there so the zero-new streak file stays sandboxed."""
    scratch = WORKSPACE_ROOT / ".tmp" / f"pytest_acceptance_{uuid.uuid4().hex[:8]}"
    scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(acc, "RUN_LOG_PATH", scratch / "run_log.jsonl")
    monkeypatch.setattr(acc, "STRICT", True)

    def write(stats: dict) -> None:
        path = scratch / "current_stats.json"
        path.write_text(json.dumps(stats), encoding="utf-8")
        monkeypatch.setenv("CURRENT_RUN_STATS_PATH", str(path))

    yield write
    shutil.rmtree(scratch, ignore_errors=True)


def _ranker_down(stats: dict) -> dict:
    stats["ranker"] = {"requested": 40, "placeholder": 40, "chunk_failures": [0, 1]}
    return stats


def test_healthy_run_has_no_failures(stats_env):
    stats_env(_healthy_stats())
    assert acc.check_pipeline_degradation() == []


def test_ranker_only_failures_are_advisory(stats_env):
    stats_env(_ranker_down(_healthy_stats()))
    failures = acc.check_pipeline_degradation()
    blocking, advisory = acc.classify_failures(failures)
    assert blocking == []
    assert len(advisory) == 2
    assert advisory[0].startswith("RANKER DEGRADED")
    assert "profile heuristic fallback" in advisory[0]
    assert advisory[1].startswith("RANKER CHUNK FAILURES")


def test_write_failed_is_advisory(stats_env):
    stats = _healthy_stats()
    stats["top_matches_ok"] = False
    stats_env(stats)
    blocking, advisory = acc.classify_failures(acc.check_pipeline_degradation())
    assert blocking == [] and advisory and advisory[0].startswith("WRITE FAILED")


def test_source_coverage_failure_is_blocking_even_with_ranker_down(stats_env):
    # Positive safeguard test: a blocking failure must NOT be downgraded.
    stats = _ranker_down(_healthy_stats())
    stats["per_source"] = {s: (10 if i < 2 else 0) for i, s in enumerate(SOURCES)}
    stats_env(stats)
    blocking, advisory = acc.classify_failures(acc.check_pipeline_degradation())
    assert len(blocking) == 1 and blocking[0].startswith("SOURCE COVERAGE DEGRADED")
    assert len(advisory) == 2


def test_verification_skipped_is_blocking(stats_env):
    stats = _healthy_stats()
    stats["verification"] = {"disabled": True}
    stats_env(stats)
    blocking, _ = acc.classify_failures(acc.check_pipeline_degradation())
    assert blocking and blocking[0].startswith("POSTING VERIFICATION SKIPPED")


def test_unknown_failure_defaults_to_blocking():
    blocking, advisory = acc.classify_failures(["SOMETHING NEW broke"])
    assert blocking == ["SOMETHING NEW broke"] and advisory == []


# --- main() exit codes against a fake, clean sheet -------------------------


class _FakeWS:
    def __init__(self, rows):
        self._rows = rows

    def get_all_values(self):
        return self._rows


class _FakeSheet:
    def __init__(self, rows_by_tab):
        self._rows = rows_by_tab

    def worksheet(self, tab):
        return _FakeWS(self._rows.get(tab, []))


@pytest.fixture
def clean_sheet(monkeypatch):
    top = [
        ["Title", "Location", "Link"],
        ["Senior Product Manager", "Paris", "https://example.com/job/1"],
    ]
    monkeypatch.setattr(
        acc, "_open_sheet", lambda: _FakeSheet({acc.TOP_MATCHES_TAB: top})
    )
    monkeypatch.setattr(acc, "reverify_backlog", lambda _stats: 0)


def test_main_exit_0_when_healthy(stats_env, clean_sheet, capsys):
    stats_env(_healthy_stats())
    assert acc.main() == 0
    assert "RESULT: PASS" in capsys.readouterr().out


def test_main_exit_2_degraded_when_ranker_only(stats_env, clean_sheet, capsys):
    stats_env(_ranker_down(_healthy_stats()))
    assert acc.main() == 2
    out = capsys.readouterr().out
    assert "RESULT: DEGRADED" in out
    assert f"{acc.ADVISORY_MARKER} RANKER DEGRADED" in out  # run.py parses this marker


def test_main_exit_1_when_blocking_present(stats_env, clean_sheet, capsys):
    stats = _ranker_down(_healthy_stats())
    stats["per_source"] = {s: 0 for s in SOURCES}
    stats_env(stats)
    assert acc.main() == 1
    assert "RESULT: FAIL" in capsys.readouterr().out
