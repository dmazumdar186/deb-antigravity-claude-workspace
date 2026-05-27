"""Unit tests for play_console_tester_gate.py."""

import json
from datetime import date, timedelta

import pytest


def _import_pcg():
    import play_console_tester_gate
    return play_console_tester_gate


def test_days_remaining_at_start():
    pcg = _import_pcg()
    today = date(2026, 5, 27)
    started = today.isoformat()
    app = {"play_tester_gate_started_at": started, "play_tester_count_manual": 0}
    g = pcg.compute_gate(app, today)
    assert g["days_elapsed"] == 0
    assert g["days_remaining"] == 14


def test_days_remaining_midway():
    pcg = _import_pcg()
    today = date(2026, 5, 27)
    started = (today - timedelta(days=7)).isoformat()
    app = {"play_tester_gate_started_at": started, "play_tester_count_manual": 0}
    g = pcg.compute_gate(app, today)
    assert g["days_elapsed"] == 7
    assert g["days_remaining"] == 7


def test_days_remaining_past_deadline():
    pcg = _import_pcg()
    today = date(2026, 5, 27)
    started = (today - timedelta(days=20)).isoformat()
    app = {"play_tester_gate_started_at": started, "play_tester_count_manual": 0}
    g = pcg.compute_gate(app, today)
    assert g["days_elapsed"] == 20
    # days_remaining is clamped at 0 (max(0, ...))
    assert g["days_remaining"] == 0


def test_gate_open_truth_table_all_met():
    pcg = _import_pcg()
    today = date(2026, 5, 27)
    started = (today - timedelta(days=14)).isoformat()
    app = {"play_tester_gate_started_at": started, "play_tester_count_manual": 20}
    g = pcg.compute_gate(app, today)
    assert g["days_remaining"] == 0
    assert g["testers_needed"] == 0
    assert g["gate_open"] is True


def test_gate_open_truth_table_days_short():
    pcg = _import_pcg()
    today = date(2026, 5, 27)
    started = (today - timedelta(days=10)).isoformat()
    app = {"play_tester_gate_started_at": started, "play_tester_count_manual": 25}
    g = pcg.compute_gate(app, today)
    assert g["gate_open"] is False


def test_gate_open_truth_table_testers_short():
    pcg = _import_pcg()
    today = date(2026, 5, 27)
    started = (today - timedelta(days=20)).isoformat()
    app = {"play_tester_gate_started_at": started, "play_tester_count_manual": 5}
    g = pcg.compute_gate(app, today)
    assert g["days_remaining"] == 0
    assert g["testers_needed"] == 15
    assert g["gate_open"] is False


def test_gate_open_not_started():
    pcg = _import_pcg()
    today = date(2026, 5, 27)
    app = {"play_tester_gate_started_at": None, "play_tester_count_manual": None}
    g = pcg.compute_gate(app, today)
    assert g["started_at"] is None
    assert g["days_elapsed"] is None
    assert g["days_remaining"] is None
    assert g["testers_needed"] == 20
    assert g["gate_open"] is False


def test_parse_iso_date_handles_full_iso():
    pcg = _import_pcg()
    d = pcg.parse_iso_date("2026-05-27T12:34:56+00:00")
    assert d == date(2026, 5, 27)


def test_parse_iso_date_handles_z():
    pcg = _import_pcg()
    d = pcg.parse_iso_date("2026-05-27T12:34:56Z")
    assert d == date(2026, 5, 27)


def test_parse_iso_date_handles_short_form():
    pcg = _import_pcg()
    d = pcg.parse_iso_date("2026-05-27")
    assert d == date(2026, 5, 27)


def test_parse_iso_date_handles_none():
    pcg = _import_pcg()
    assert pcg.parse_iso_date(None) is None
    assert pcg.parse_iso_date("") is None


def test_parse_iso_date_handles_garbage():
    pcg = _import_pcg()
    assert pcg.parse_iso_date("not a date") is None


def test_compute_gate_handles_missing_fields():
    pcg = _import_pcg()
    today = date(2026, 5, 27)
    g = pcg.compute_gate({}, today)
    assert g["started_at"] is None
    assert g["tester_count"] == 0
    assert g["gate_open"] is False
