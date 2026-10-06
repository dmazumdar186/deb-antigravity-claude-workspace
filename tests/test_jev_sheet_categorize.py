"""Offline tests for execution/google/jev_sheet_categorize.py (decide_many monkeypatched)."""
import csv
from pathlib import Path

import pytest

from execution.google import jev_sheet_categorize as mod
from execution.modules import jev_client
from execution.modules.jev_client import JevResult

OPTIONS = "Groceries,Rent,Transport,Income,Other"


def _res(choice, conf=0.9, error=None, cost=0.00002):
    if error:
        return JevResult(error=error)
    return JevResult(answers={"category": {"choice": choice, "confidence": conf}}, cost_usd=cost)


def _write_csv(path: Path, rows):
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["date", "description", "amount"])
        w.writeheader()
        w.writerows(rows)


def _read_csv(path: Path):
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture
def csv_in(tmp_path):
    p = tmp_path / "bank.csv"
    _write_csv(p, [
        {"date": "2026-10-01", "description": "TESCO STORES", "amount": "-42.10"},
        {"date": "2026-10-01", "description": "RENT TO LANDLORD", "amount": "-1200.00"},
        {"date": "2026-10-02", "description": "TFL TRAVEL", "amount": "-6.40"},
        {"date": "2026-10-03", "description": "SALARY ACME LTD", "amount": "3100.00"},
    ])
    return p


def test_csv_output_columns_and_values(tmp_path, csv_in, monkeypatch):
    canned = [_res("Groceries"), _res("rent"), _res("Transport", conf=0.3), _res("Income")]
    seen = {}

    def fake(states, questions, **kw):
        seen["states"] = states
        seen["questions"] = questions
        return canned

    monkeypatch.setattr(jev_client, "decide_many", fake)
    monkeypatch.setattr(jev_client, "available", lambda: True)
    monkeypatch.setattr(jev_client, "append_ledger", lambda *a, **k: None)
    out = tmp_path / "out.csv"
    rc = mod.main(["--csv", str(csv_in), "--options", OPTIONS, "--column", "category",
                   "--output", str(out), "--min-confidence", "0.55"])
    assert rc == 0
    rows = _read_csv(out)
    assert list(rows[0].keys()) == ["date", "description", "amount", "category"]
    assert [r["category"] for r in rows] == ["Groceries", "Rent", "?", "Income"]
    assert seen["questions"]["category"]["type"] == "choice"
    assert set(seen["questions"]["category"]["criteria"]) == set(OPTIONS.split(","))
    assert seen["states"][0] == {"date": "2026-10-01", "description": "TESCO STORES", "amount": "-42.10"}


def test_never_writes_option_outside_list(monkeypatch):
    rows = [{"description": "a"}, {"description": "b"}, {"description": "c"}]
    canned = [_res("Crypto"), _res("", error="HTTP 500"), _res("Other")]
    monkeypatch.setattr(jev_client, "decide_many", lambda s, q, **kw: canned)
    stats = mod.categorize_rows(
        rows, column="category", options=mod.parse_options(OPTIONS), question="q",
        source_cols=["description"], min_confidence=0.5, overwrite=False, limit=None, workers=1,
    )
    allowed = set(OPTIONS.split(",")) | {"?"}
    assert all(r["category"] in allowed for r in rows)
    assert [r["category"] for r in rows] == ["?", "?", "Other"]
    assert stats["filled"] == 1 and stats["needs_review"] == 2 and stats["errors"] == 1
    assert stats["filled"] + stats["needs_review"] == stats["eligible"]


def test_blank_only_unless_overwrite(monkeypatch):
    rows = [{"d": "x", "category": "Rent"}, {"d": "y", "category": ""}]
    calls = []

    def fake(states, q, **kw):
        calls.append(len(states))
        return [_res("Income")] * len(states)

    monkeypatch.setattr(jev_client, "decide_many", fake)
    kw = dict(column="category", options=mod.parse_options(OPTIONS), question="q",
              source_cols=["d"], min_confidence=0.5, limit=None, workers=1)
    mod.categorize_rows(rows, overwrite=False, **kw)
    assert calls == [1] and rows[0]["category"] == "Rent" and rows[1]["category"] == "Income"
    mod.categorize_rows(rows, overwrite=True, **kw)
    assert calls == [1, 2] and rows[0]["category"] == "Income"


def test_parse_options_with_descriptions():
    opts = mod.parse_options("A=first thing, B=second thing,C")
    assert opts == {"A": "first thing", "B": "second thing", "C": "the row belongs to 'C'"}
    with pytest.raises(ValueError):
        mod.parse_options("Only")


def test_dry_run_writes_nothing(tmp_path, csv_in, monkeypatch):
    monkeypatch.setattr(jev_client, "decide_many", lambda s, q, **kw: [_res("Other")] * len(s))
    monkeypatch.setattr(jev_client, "available", lambda: True)
    monkeypatch.setattr(jev_client, "append_ledger", lambda *a, **k: None)
    assert mod.main(["--csv", str(csv_in), "--options", OPTIONS, "--dry-run"]) == 0
    assert not csv_in.with_suffix(".jev.csv").exists()
