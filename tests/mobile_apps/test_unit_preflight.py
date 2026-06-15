"""Unit tests for execution/mobile_apps/preflight.py.

Tests use monkeypatch to stub `subprocess.run` and `shutil.which` so each check
runs without touching the host environment.

Covers:
  - Each individual check (node, eas, wrangler, modal, env keys, Apple gate)
  - aggregate_exit_code: required RED -> 1; only YELLOW/BLOCK -> 0
  - --json output shape (machine-readable contract for the skill / CI)
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

WORKSPACE = Path(__file__).resolve().parents[2]
_PF_PATH = WORKSPACE / "execution" / "mobile_apps" / "preflight.py"
_spec = importlib.util.spec_from_file_location("mobile_preflight", _PF_PATH)
pf = importlib.util.module_from_spec(_spec)
sys.modules["mobile_preflight"] = pf
_spec.loader.exec_module(pf)


def _ok(returncode=0, stdout="", stderr=""):
    return MagicMock(returncode=returncode, stdout=stdout, stderr=stderr)


@pytest.fixture
def stub_run(monkeypatch):
    """Reset subprocess + which stubs for each test."""
    holder = {"calls": []}

    def make(callback):
        def _run(cmd, **kw):
            holder["calls"].append(cmd)
            return callback(cmd)
        return _run

    def set_run(callback):
        monkeypatch.setattr(pf.subprocess, "run", make(callback))

    def set_which(callback):
        monkeypatch.setattr(pf.shutil, "which", callback)

    return {"set_run": set_run, "set_which": set_which, "calls": holder["calls"]}


# ----------------------------------------------------------------------------
# check_node_version
# ----------------------------------------------------------------------------

def test_node_green_on_v20(stub_run):
    stub_run["set_which"](lambda n: "node" if n == "node" else None)
    stub_run["set_run"](lambda cmd: _ok(stdout="v20.10.0\n"))
    status, msg, _hint = pf.check_node_version()
    assert status == "GREEN"
    assert "v20.10.0" in msg


def test_node_red_when_not_on_path(stub_run):
    stub_run["set_which"](lambda _n: None)
    status, msg, hint = pf.check_node_version()
    assert status == "RED"
    assert "PATH" in msg


def test_node_red_on_old_version(stub_run):
    stub_run["set_which"](lambda n: "node")
    stub_run["set_run"](lambda cmd: _ok(stdout="v16.20.0\n"))
    status, msg, _hint = pf.check_node_version()
    assert status == "RED"
    assert "< required 18" in msg


def test_node_red_when_command_fails(stub_run):
    stub_run["set_which"](lambda n: "node")
    stub_run["set_run"](lambda cmd: _ok(returncode=1, stderr="boom"))
    status, msg, _hint = pf.check_node_version()
    assert status == "RED"
    assert "failed" in msg


# ----------------------------------------------------------------------------
# check_eas_cli / check_eas_session
# ----------------------------------------------------------------------------

def test_eas_cli_green(stub_run):
    stub_run["set_which"](lambda n: "eas")
    stub_run["set_run"](lambda cmd: _ok(stdout="eas-cli/14.2.0\n"))
    status, msg, _ = pf.check_eas_cli()
    assert status == "GREEN"
    assert "14.2.0" in msg


def test_eas_session_red_when_not_logged_in(stub_run):
    stub_run["set_which"](lambda n: "eas")
    stub_run["set_run"](lambda cmd: _ok(returncode=1, stdout="not logged in"))
    status, msg, hint = pf.check_eas_session()
    assert status == "RED"
    assert "eas login" in hint


def test_eas_session_green_returns_account(stub_run):
    stub_run["set_which"](lambda n: "eas")
    stub_run["set_run"](lambda cmd: _ok(stdout="debanjan186\n"))
    status, msg, _ = pf.check_eas_session()
    assert status == "GREEN"
    assert "debanjan186" in msg


# ----------------------------------------------------------------------------
# check_wrangler_session warns about AM session
# ----------------------------------------------------------------------------

def test_wrangler_session_red_warns_about_am(stub_run):
    stub_run["set_which"](lambda n: "wrangler")
    stub_run["set_run"](lambda cmd: _ok(returncode=1, stderr="no auth"))
    status, _msg, hint = pf.check_wrangler_session()
    assert status == "RED"
    assert "AM" in hint  # the hint must warn about clobbering AM session


# ----------------------------------------------------------------------------
# Modal token
# ----------------------------------------------------------------------------

def test_modal_token_red_when_no_modal_cli(stub_run):
    stub_run["set_which"](lambda _n: None)
    status, msg, hint = pf.check_modal_token()
    assert status == "RED"
    assert "pip install modal" in hint


def test_modal_token_red_when_token_missing(stub_run):
    stub_run["set_which"](lambda n: "modal")
    stub_run["set_run"](lambda cmd: _ok(returncode=1, stderr="no token"))
    status, msg, hint = pf.check_modal_token()
    assert status == "RED"
    assert "modal token new" in hint


# ----------------------------------------------------------------------------
# .env key checks
# ----------------------------------------------------------------------------

def test_env_key_present_returns_green():
    status, msg, _ = pf.check_env_key({"EXPO_TOKEN": "abc"}, "EXPO_TOKEN", required=True)
    assert status == "GREEN" and msg == "present"


def test_env_key_missing_required_returns_red():
    status, msg, hint = pf.check_env_key({}, "EXPO_TOKEN", required=True)
    assert status == "RED" and "MISSING" in msg
    assert "EXPO_TOKEN" in hint


def test_env_key_missing_optional_returns_yellow():
    status, msg, _ = pf.check_env_key({}, "APPLE_ID", required=False)
    assert status == "YELLOW"


def test_env_key_empty_string_treated_as_missing():
    """Audit edge case: `EXPO_TOKEN=` with no value should be RED, not GREEN."""
    status, _, _ = pf.check_env_key({"EXPO_TOKEN": ""}, "EXPO_TOKEN", required=True)
    assert status == "RED"


# ----------------------------------------------------------------------------
# Apple enrollment gate
# ----------------------------------------------------------------------------

def test_apple_enrollment_active(monkeypatch):
    monkeypatch.setenv("APPLE_ENROLLMENT_STATUS", "active")
    monkeypatch.setattr(pf, "_read_env_keys", lambda: {})
    status, msg, _ = pf.check_apple_enrollment()
    assert status == "GREEN"
    assert msg == "active"


def test_apple_enrollment_pending_blocks_phase_4_5(monkeypatch):
    monkeypatch.delenv("APPLE_ENROLLMENT_STATUS", raising=False)
    monkeypatch.setattr(pf, "_read_env_keys", lambda: {})
    status, _, hint = pf.check_apple_enrollment()
    assert status == "BLOCK"
    assert "4-5" in hint


# ----------------------------------------------------------------------------
# aggregate_exit_code
# ----------------------------------------------------------------------------

def test_aggregate_zero_when_no_required_red():
    items = [
        {"name": "x", "status": "GREEN", "required": True, "message": "", "hint": ""},
        {"name": "y", "status": "YELLOW", "required": False, "message": "", "hint": ""},
        {"name": "z", "status": "BLOCK", "required": False, "message": "", "hint": ""},
    ]
    assert pf.aggregate_exit_code(items) == 0


def test_aggregate_one_when_required_red():
    items = [
        {"name": "x", "status": "GREEN", "required": True, "message": "", "hint": ""},
        {"name": "y", "status": "RED", "required": True, "message": "", "hint": ""},
    ]
    assert pf.aggregate_exit_code(items) == 1


def test_aggregate_zero_when_red_is_optional():
    """Optional RED shouldn't fail preflight (defensive — no current check emits this,
    but the contract should be explicit)."""
    items = [
        {"name": "x", "status": "GREEN", "required": True, "message": "", "hint": ""},
        {"name": "y", "status": "RED", "required": False, "message": "", "hint": ""},
    ]
    assert pf.aggregate_exit_code(items) == 0


# ----------------------------------------------------------------------------
# JSON output contract
# ----------------------------------------------------------------------------

def test_json_output_has_machine_readable_contract(monkeypatch, capsys):
    """The --json flag is the skill / CI contract; shape must not regress."""
    # Force everything to GREEN so the test doesn't depend on the host.
    def _fake_collect(required_only=False):
        return [
            {"name": "node --version", "status": "GREEN", "message": "v20", "hint": "", "required": True},
            {"name": "Phase 4-5 gate", "status": "GREEN", "message": "active", "hint": "", "required": False},
        ]
    monkeypatch.setattr(pf, "collect", _fake_collect)
    rc = pf.main(["--json"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert rc == 0
    assert payload["exit_code"] == 0
    assert payload["all_required_green"] is True
    assert payload["phase_4_5_blocked"] is False
    assert isinstance(payload["items"], list)
    assert payload["items"][0]["name"] == "node --version"


def test_json_output_flags_phase_4_5_block(monkeypatch, capsys):
    def _fake_collect(required_only=False):
        return [
            {"name": "node --version", "status": "GREEN", "message": "v20", "hint": "", "required": True},
            {"name": "Phase 4-5 gate", "status": "BLOCK", "message": "pending", "hint": "x", "required": False},
        ]
    monkeypatch.setattr(pf, "collect", _fake_collect)
    rc = pf.main(["--json"])
    payload = json.loads(capsys.readouterr().out)
    # Exit 0 — phase 4-5 block is informational, not a hard fail.
    assert rc == 0
    assert payload["phase_4_5_blocked"] is True


def test_json_output_nonzero_when_required_red(monkeypatch, capsys):
    def _fake_collect(required_only=False):
        return [
            {"name": "eas --version", "status": "RED", "message": "missing", "hint": "install eas-cli", "required": True},
        ]
    monkeypatch.setattr(pf, "collect", _fake_collect)
    rc = pf.main(["--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["exit_code"] == 1
    assert payload["all_required_green"] is False


# ----------------------------------------------------------------------------
# _read_env_keys
# ----------------------------------------------------------------------------

def test_read_env_keys_ignores_comments_and_blank(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "# a comment\n"
        "\n"
        "KEY1=value1\n"
        "KEY2=\"quoted value\"\n"
        "KEY3='single'\n"
        "BAD-LINE-NO-EQUALS\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(pf, "ENV_PATH", env)
    out = pf._read_env_keys()
    assert out == {"KEY1": "value1", "KEY2": "quoted value", "KEY3": "single"}


def test_read_env_keys_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(pf, "ENV_PATH", tmp_path / "does-not-exist.env")
    assert pf._read_env_keys() == {}
