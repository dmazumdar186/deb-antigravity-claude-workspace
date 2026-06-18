"""
Monkey/chaos tests (Tier 6) for job_search_sheet pipeline.

These probe failure modes — bad input, missing files, malformed config, path
traversal, encoding edge cases. The pipeline must NEVER crash with an
unhandled exception; it must error cleanly or degrade gracefully.

Non-destructive: any file we modify is restored after.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import scrapers at MODULE load so their load_dotenv() runs ONCE here, before
# any per-test monkeypatch.delenv. If we imported inside the test, the in-test
# import would re-run module body and load_dotenv() would re-populate the
# env var that monkeypatch just deleted, defeating the test.
from execution.custom_scrapers import adzuna_jobs as _adzuna  # noqa: E402
from execution.custom_scrapers import jooble_jobs as _jooble  # noqa: E402


def _py(*args: str, env_overrides: dict | None = None, timeout: int = 60) -> subprocess.CompletedProcess:
    import os
    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        ["py", *args], capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout, cwd=str(ROOT), env=env,
    )


# ---------------------------------------------------------------------------
# Title filter — garbage input
# ---------------------------------------------------------------------------

def test_title_with_unicode_garbage():
    """Unicode garbage as --title must not crash; should exit non-zero."""
    from execution.personal_workflows.job_search_sheet import filter_titles
    titles_cfg = {"PM": {"tab": "PM", "synonyms": ["product manager"]}}
    # Various adversarial inputs
    for needle in ["🚀🦄💩", "\x00null\x00", "../../../etc/passwd",
                   "x" * 10000, "<script>alert(1)</script>",
                   "'; DROP TABLE titles; --"]:
        out = filter_titles(titles_cfg, needle)
        assert out == {}, f"Adversarial --title {needle!r} should not match"


# ---------------------------------------------------------------------------
# Sheet ID with path traversal in CLI
# ---------------------------------------------------------------------------

def test_sheet_id_path_traversal_does_not_escape():
    """--sheet-id passes through to gspread.open_by_key which treats it as opaque ID.
    Path traversal patterns must not be interpreted as paths."""
    proc = _py(
        "execution/personal_workflows/job_search_sheet.py",
        "--sheet-id", "../../../etc/passwd",
        "--title", "PM", "--geo", "FR", "--no-llm",
        timeout=60,
    )
    # Must fail (sheet not found) but NOT touch /etc/passwd or any local file
    assert proc.returncode != 0
    # Output must not contain any contents of /etc/passwd-like leak
    assert "root:x:" not in proc.stdout
    assert "root:x:" not in proc.stderr


# ---------------------------------------------------------------------------
# Corrupted runs log
# ---------------------------------------------------------------------------

def test_corrupted_runs_log_doesnt_crash_load():
    """_load_recent_runs must survive a junk-filled runs log."""
    from execution.personal_workflows.job_search_sheet import _load_recent_runs
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as fh:
        fh.write("not json\n")
        fh.write("\x00\x01\x02 binary garbage\n")
        fh.write("{partial json,\n")
        fh.write("[" * 1000 + "\n")  # unmatched brackets
        fh.write(json.dumps({"run_at": "2026-06-09T10:00:00Z", "written_per_tab": {"PM": 1}}) + "\n")
        fh.write("\n\n\n")  # blank lines
        path = Path(fh.name)
    try:
        out = _load_recent_runs(path, limit=5)
        # Must return only the parseable line
        assert len(out) == 1
        assert out[0]["date"] == "2026-06-09"
    finally:
        path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Adzuna scraper — bad inputs
# ---------------------------------------------------------------------------

def test_adzuna_scrape_with_missing_keys(monkeypatch):
    """When ADZUNA_APP_ID/KEY are missing, scraper should return [] and log warning, not raise."""
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    out = _adzuna.scrape(queries=["product manager"], country="fr", pages=1)
    assert out == []


def test_jooble_scrape_with_missing_key(monkeypatch):
    """When JOOBLE_API_KEY is missing, scraper should return [] and log warning, not raise."""
    monkeypatch.delenv("JOOBLE_API_KEY", raising=False)
    out = _jooble.scrape(queries=["product manager"], country="France", page=1)
    assert out == []


# ---------------------------------------------------------------------------
# Notify — bad data shapes
# ---------------------------------------------------------------------------

def test_notify_handles_empty_summary():
    """_build_body must not crash on a near-empty summary dict."""
    from execution.personal_workflows.job_search_notify import _build_body
    subject, body = _build_body({}, None)
    assert "0 new jobs" in subject
    assert isinstance(body, str)


def test_notify_handles_summary_with_string_counts():
    """Bad data types in written_per_tab must not crash."""
    from execution.personal_workflows.job_search_notify import _build_body
    summary = {"written_per_tab": {"PM": "5", "AI PM": 3}}
    subject, body = _build_body(summary, None)
    assert "8" in subject  # int("5") + 3


def test_notify_with_unicode_tab_names():
    from execution.personal_workflows.job_search_notify import _build_body
    summary = {"written_per_tab": {"测试": 1, "🚀": 2}}
    subject, body = _build_body(summary, "SID")
    assert "3 new" in subject
    assert "测试" in body
    assert "🚀" in body


# ---------------------------------------------------------------------------
# Sheets writer — survive corrupt mock responses
# ---------------------------------------------------------------------------

def test_load_recent_runs_with_directory_not_file(tmp_path: Path):
    """If RUNS_LOG path is somehow a directory, return [] not crash."""
    from execution.personal_workflows.job_search_sheet import _load_recent_runs
    d = tmp_path / "not_a_file"
    d.mkdir()
    out = _load_recent_runs(d, limit=5)
    assert out == []


# ---------------------------------------------------------------------------
# Env var injection — try to break env parsing
# ---------------------------------------------------------------------------

def test_env_var_with_equals_signs_in_value():
    """Quick sanity that .env loader handles value containing '='."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False, encoding="utf-8") as fh:
        fh.write("FOO=bar=baz=qux\n")
        fh.write("EMPTY=\n")
        fh.write("# comment\n")
        path = Path(fh.name)
    try:
        from dotenv import dotenv_values
        vals = dotenv_values(path)
        assert vals.get("FOO") == "bar=baz=qux"
        assert vals.get("EMPTY") == ""
    finally:
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
