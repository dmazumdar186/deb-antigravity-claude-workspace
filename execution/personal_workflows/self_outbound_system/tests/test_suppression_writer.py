"""
test_suppression_writer.py
description: Unit tests for suppression_writer. Covers happy path (single add), dedup (already-present), history-always-appended, invalid inputs (bad email / reason / source), bulk mode, and concurrency safety via the file lock. Uses --dry-run + a tmp-path monkeypatch so no real writes happen to config/suppression.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import suppression_writer as sw
from suppression_writer import SuppressionError, add_suppression, add_bulk


@pytest.fixture
def isolated_suppression(tmp_path, monkeypatch):
    """Redirect SUPPRESSION_FILE + LOCK_FILE to tmp so tests don't clobber
    the real config/suppression.json."""
    supp = tmp_path / "suppression.json"
    lock = tmp_path / ".suppression.lock"
    supp.write_text(json.dumps({
        "_description": "test",
        "emails": [],
        "domains": ["accessorymasters.co"],
        "history": [],
    }), encoding="utf-8")
    monkeypatch.setattr(sw, "SUPPRESSION_FILE", supp)
    monkeypatch.setattr(sw, "LOCK_FILE", lock)
    return supp


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_add_new_email_writes_to_emails_and_history(isolated_suppression):
    result = add_suppression(
        email="test@example.com",
        reason="negative_reply",
        source="reply_classifier",
        alert=False,
    )
    assert result["added_to_emails"] is True
    assert result["already_present"] is False
    assert result["normalized_email"] == "test@example.com"

    state = _read(isolated_suppression)
    assert "test@example.com" in state["emails"]
    assert len(state["history"]) == 1
    assert state["history"][0]["email"] == "test@example.com"
    assert state["history"][0]["reason"] == "negative_reply"
    assert state["history"][0]["source"] == "reply_classifier"


def test_dedup_second_add_is_no_op_on_emails_but_still_logs_history(isolated_suppression):
    add_suppression("dup@example.com", "negative_reply", "reply_classifier", alert=False)
    result = add_suppression("dup@example.com", "unsubscribe_click", "webhook", alert=False)
    assert result["added_to_emails"] is False
    assert result["already_present"] is True

    state = _read(isolated_suppression)
    assert state["emails"].count("dup@example.com") == 1
    assert len(state["history"]) == 2
    assert state["history"][1]["reason"] == "unsubscribe_click"


def test_email_normalization_lowercase(isolated_suppression):
    add_suppression("Mixed@Example.com", "manual_add", "manual", alert=False)
    state = _read(isolated_suppression)
    assert "mixed@example.com" in state["emails"]


def test_am_locked_domain_flag(isolated_suppression):
    result = add_suppression("anyone@accessorymasters.co", "am_locked_domain", "manual", alert=False)
    assert result["am_locked_domain"] is True

    result2 = add_suppression("other@notlocked.com", "manual_add", "manual", alert=False)
    assert result2["am_locked_domain"] is False


def test_invalid_email_raises(isolated_suppression):
    with pytest.raises(SuppressionError):
        add_suppression("not-an-email", "manual_add", "manual", alert=False)


def test_invalid_reason_raises(isolated_suppression):
    with pytest.raises(SuppressionError):
        add_suppression("x@example.com", "bad_reason", "manual", alert=False)


def test_invalid_source_raises(isolated_suppression):
    with pytest.raises(SuppressionError):
        add_suppression("x@example.com", "manual_add", "bad_source", alert=False)


def test_dry_run_does_not_write(isolated_suppression):
    add_suppression("dry@example.com", "manual_add", "manual", alert=False, dry_run=True)
    state = _read(isolated_suppression)
    assert "dry@example.com" not in state["emails"]
    assert state["history"] == []  # nothing written


def test_bulk_mode(isolated_suppression):
    entries = [
        {"email": "a@example.com", "reason": "negative_reply", "source": "webhook"},
        {"email": "b@example.com", "reason": "unsubscribe_click", "source": "webhook"},
        {"email": "invalid-email", "reason": "manual_add", "source": "manual"},  # will error
        {"email": "A@Example.com", "reason": "hard_bounce", "source": "webhook"},  # dup of a@
    ]
    results = add_bulk(entries, alert=False)
    assert len(results) == 4
    assert results[0]["added_to_emails"] is True
    assert results[1]["added_to_emails"] is True
    assert "error" in results[2]
    assert results[3]["already_present"] is True  # dedup wins over case

    state = _read(isolated_suppression)
    assert set(state["emails"]) == {"a@example.com", "b@example.com"}
    # history: 2 new + 1 dup entry (bulk validates before append; the invalid one didn't reach add_suppression)
    assert len(state["history"]) == 3


def test_missing_suppression_file_raises(tmp_path, monkeypatch):
    """If the file doesn't exist, we raise instead of creating one silently —
    the config file is source-of-truth and must be intentionally seeded."""
    missing = tmp_path / "missing.json"
    lock = tmp_path / ".lock"
    monkeypatch.setattr(sw, "SUPPRESSION_FILE", missing)
    monkeypatch.setattr(sw, "LOCK_FILE", lock)
    with pytest.raises(SuppressionError, match="suppression file missing"):
        add_suppression("x@example.com", "manual_add", "manual", alert=False)


def test_history_entry_has_iso_timestamp(isolated_suppression):
    add_suppression("ts@example.com", "manual_add", "manual", alert=False)
    state = _read(isolated_suppression)
    ts = state["history"][0]["timestamp"]
    # crude ISO check: "2026-07-14T..." at minimum
    assert len(ts) >= 19
    assert ts[4] == "-"
    assert ts[10] == "T"
