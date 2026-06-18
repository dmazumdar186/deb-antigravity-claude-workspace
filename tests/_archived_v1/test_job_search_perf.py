"""
Performance tests (Tier 5) for job_search_sheet.

These don't run the real pipeline (too slow + paid APIs). Instead they assert
guard-rails on what the runs.jsonl logs SHOULD contain, and bench the lightweight
hot-paths (dedup, filter_titles, _load_recent_runs).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from execution.personal_workflows.job_search_sheet import filter_titles, _load_recent_runs  # noqa: E402


# ---------------------------------------------------------------------------
# Hot-path micro-benchmarks
# ---------------------------------------------------------------------------

def test_filter_titles_is_fast():
    """filter_titles is on the cron critical path; must be effectively free."""
    titles = {
        f"key_{i}": {"tab": f"tab_{i}", "synonyms": [f"synonym_{i}_{j}" for j in range(10)]}
        for i in range(100)
    }
    start = time.perf_counter()
    for _ in range(1000):
        filter_titles(titles, "synonym_50_5")
    elapsed = time.perf_counter() - start
    # 1000 iterations on 100×10 synonyms should be well under 1s
    assert elapsed < 1.0, f"filter_titles too slow: {elapsed:.3f}s for 1000 iters"


def test_load_recent_runs_is_fast(tmp_path: Path):
    """Loading 1000 historical runs should be < 0.5s; we only show 14."""
    log = tmp_path / "runs.jsonl"
    lines = [
        json.dumps({"run_at": f"2025-{(i%12)+1:02d}-01T00:00:00Z",
                    "written_per_tab": {"PM": i}, "discovered": i, "after_dedup": i})
        for i in range(1000)
    ]
    log.write_text("\n".join(lines), encoding="utf-8")
    start = time.perf_counter()
    out = _load_recent_runs(log, limit=14)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.5, f"_load_recent_runs too slow: {elapsed:.3f}s on 1000-row log"
    assert len(out) == 14


# ---------------------------------------------------------------------------
# Runs log shape guard-rails (catches runaway pipelines)
# ---------------------------------------------------------------------------

def test_recent_runs_within_quota():
    """If runs log exists, no single run should have discovered > 1000 — that'd
    blow through Adzuna's 250/day free tier across 6 titles × 4 queries = 24 calls
    × ~50 jobs/page = ~1200 max upper bound. > 2000 would indicate runaway."""
    log = ROOT / ".tmp" / "job_search" / "job_search_runs.jsonl"
    if not log.exists():
        pytest.skip("No runs log yet")
    bad = []
    for raw in log.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            continue
        n = d.get("discovered", 0)
        if isinstance(n, int) and n > 2000:
            bad.append((d.get("run_id", "?"), n))
    assert not bad, f"Runs that discovered > 2000 jobs (quota risk): {bad}"


def test_recent_runs_have_required_fields():
    log = ROOT / ".tmp" / "job_search" / "job_search_runs.jsonl"
    if not log.exists():
        pytest.skip("No runs log yet")
    required = {"run_id", "run_at", "discovered", "after_keyword_filter",
                "after_dedup", "written_per_tab"}
    missing = []
    for raw in log.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            continue
        absent = required - set(d.keys())
        if absent:
            missing.append((d.get("run_id", "?"), sorted(absent)))
    assert not missing, f"Run-log entries missing fields: {missing[:3]}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
