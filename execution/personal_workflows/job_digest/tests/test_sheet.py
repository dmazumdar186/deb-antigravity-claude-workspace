"""
description: Offline tests for notifier/sheet.py's pure helpers (no real
    gspread/Google API calls — the real gspread/cryptography stack is not
    usable in this sandbox, so tests either exercise pure functions directly
    or install fake `gspread` / `google.oauth2.service_account` modules into
    sys.modules before calling _open_client).
inputs: none (synthetic NormalizedJob/RankedJob fixtures + fake gspread modules)
outputs: pytest assertions
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from ..contracts import JobTier, RankedJob
from ..notifier import sheet as sheet_module
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


def test_short_id_truncates_and_handles_empty() -> None:
    assert sheet_module._short_id("abcdEFGH1234567890") == "abcd…"
    assert sheet_module._short_id("") == "<empty>"


def test_country_for_derives_from_registry_matches() -> None:
    profile = load_test_profile()  # countries: FR, IN
    job_fr = make_normalized_job(title="Sales Manager", location="Paris")
    job_in = make_normalized_job(title="Sales Manager", location="Bengaluru, India")
    job_unknown = make_normalized_job(title="Sales Manager", location="Nowhereland")

    assert sheet_module._country_for(job_fr, profile) == "FR"
    assert sheet_module._country_for(job_in, profile) == "IN"
    assert sheet_module._country_for(job_unknown, profile) == ""


def test_country_for_ignores_description_snippet() -> None:
    """HIGH fix: _country_for must match on the LOCATION string only — a New
    York job whose snippet mentions India in passing must not be mislabeled
    'IN'."""
    profile = load_test_profile()  # countries: FR, IN
    job = make_normalized_job(
        title="Sales Manager",
        location="New York, NY",
        description_snippet="Our team sells to customers across India.",
    )
    assert sheet_module._country_for(job, profile) == ""


def test_n3b_posted_at_utc_coerces_naive_datetime() -> None:
    """N3b: a naive posted_at (a source adapter's own tz gap) must be coerced
    to aware UTC, not left to raise a naive-vs-aware TypeError against the
    Top Matches cutoff. NormalizedJob is frozen, so use model_copy(update=)
    to set posted_at to each test value."""
    import datetime as dt

    base = make_normalized_job(title="Sales Manager", location="Paris")

    naive_job = base.model_copy(update={"posted_at": dt.datetime(2026, 1, 1, 12, 0, 0)})  # no tzinfo
    coerced = sheet_module._posted_at_utc(naive_job)
    assert coerced is not None
    assert coerced.tzinfo is not None
    assert coerced == dt.datetime(2026, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)

    aware_dt = dt.datetime(2026, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
    aware_job = base.model_copy(update={"posted_at": aware_dt})
    assert sheet_module._posted_at_utc(aware_job) == aware_dt

    none_job = base.model_copy(update={"posted_at": None})
    assert sheet_module._posted_at_utc(none_job) is None


def test_row_for_populates_country_column() -> None:
    profile = load_test_profile()
    job = make_normalized_job(title="Sales Manager", location="Paris")
    row = sheet_module._row_for(job, _ranked(job), "2026-09-06", profile)
    country_idx = sheet_module.COLUMNS.index("Country")
    assert row[country_idx] == "FR"


@pytest.fixture
def fake_gspread_modules(monkeypatch: pytest.MonkeyPatch):
    """Install minimal fake gspread + google.oauth2.service_account modules
    into sys.modules so _open_client's `import gspread` line resolves to a
    controllable fake instead of the real (broken-in-this-sandbox) package.
    """

    class FakeWorksheetNotFound(Exception):
        pass

    fake_gspread = types.ModuleType("gspread")
    fake_gspread.WorksheetNotFound = FakeWorksheetNotFound

    state = {"open_by_key": None}

    class FakeClient:
        def set_timeout(self, seconds):
            pass

        def open_by_key(self, spreadsheet_id):
            if state["open_by_key"] is not None:
                return state["open_by_key"](spreadsheet_id)
            return f"fake-spreadsheet:{spreadsheet_id}"

    fake_gspread.authorize = lambda creds: FakeClient()

    fake_service_account_mod = types.ModuleType("google.oauth2.service_account")

    class FakeCredentials:
        @classmethod
        def from_service_account_file(cls, path, scopes):
            return {"path": path, "scopes": scopes}

    fake_service_account_mod.Credentials = FakeCredentials

    monkeypatch.setitem(sys.modules, "gspread", fake_gspread)
    monkeypatch.setitem(sys.modules, "google.oauth2.service_account", fake_service_account_mod)
    return state


def test_open_client_coerces_str_path_no_attributeerror(fake_gspread_modules) -> None:
    """C1: sheet._open_client must Path()-coerce service_account_path itself —
    passing a bare str must never raise AttributeError from .exists()."""
    with pytest.raises(sheet_module.SheetError, match="service account JSON not found"):
        sheet_module._open_client("some-spreadsheet-id", "definitely/does/not/exist.json")


def test_open_client_accepts_real_path_object(tmp_path: Path, fake_gspread_modules) -> None:
    sa_path = tmp_path / "sa.json"
    sa_path.write_text("{}", encoding="utf-8")
    spreadsheet = sheet_module._open_client("some-spreadsheet-id", sa_path)
    assert spreadsheet == "fake-spreadsheet:some-spreadsheet-id"


def test_open_client_error_message_truncates_spreadsheet_id(tmp_path: Path, fake_gspread_modules) -> None:
    """H2: a SheetError raised on open must never embed the full spreadsheet id."""
    sa_path = tmp_path / "sa.json"
    sa_path.write_text("{}", encoding="utf-8")

    def boom(spreadsheet_id):
        raise RuntimeError("nope")

    fake_gspread_modules["open_by_key"] = boom

    full_id = "SUPERSECRETSPREADSHEETID1234567890"
    with pytest.raises(sheet_module.SheetError) as excinfo:
        sheet_module._open_client(full_id, sa_path)
    msg = str(excinfo.value)
    assert full_id not in msg
    assert "SUPE…" in msg
