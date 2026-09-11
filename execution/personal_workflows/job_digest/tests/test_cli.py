"""
description: Offline tests for cli.py's subcommand functions, run.run() replaced with
    a fake so these are pure argparse/exit-code contract tests.
inputs: none (synthetic argparse.Namespace via build_parser().parse_args)
outputs: pytest assertions
"""

from __future__ import annotations

import argparse

import pytest

from .. import cli as cli_module
from ._helpers import TEST_PROFILE_PATH


def _preview_args(state_dir, out_dir) -> argparse.Namespace:
    return cli_module.build_parser().parse_args(
        ["preview", str(TEST_PROFILE_PATH), "--state-dir", str(state_dir), "--out-dir", str(out_dir)]
    )


def test_n9_preview_returns_exit_3_when_acceptance_gate_failed(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """N9: cli preview must surface (and exit with) 3 when the acceptance gate
    failed, not silently swallow it as exit 0."""

    def fake_run_pipeline(*a, **k):
        return {
            "exit_code": 3,
            "stats": {
                "acceptance": {"passed": False, "problems": ["too few jobs"]},
            },
        }

    monkeypatch.setattr(cli_module, "run_pipeline", fake_run_pipeline)
    args = _preview_args(tmp_path / "state", tmp_path / "out")
    assert cli_module._cmd_preview(args) == 3


def test_validate_problem_count_excludes_header_line(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    """LOW fix: profile_schema._format_errors() prepends a
    "profile.yaml has N problem(s):" header before N bulleted item lines, and
    validate_file() splits that whole string into one list of N+1 lines —
    _cmd_validate must report N, not N+1."""
    bad_profile = tmp_path / "bad_profile.yaml"
    bad_profile.write_text(
        "version: 1\n"
        "roles: []\n"  # violates min_length=1 -> 1 problem
        "locations:\n"
        "  countries: []\n",  # violates min_length=1 -> 1 more problem (candidate/screening also missing)
        encoding="utf-8",
    )
    args = cli_module.build_parser().parse_args(["validate", str(bad_profile)])
    exit_code = cli_module._cmd_validate(args)
    assert exit_code == 1

    out = capsys.readouterr().out
    header = next(line for line in out.splitlines() if "problem(s):" in line)
    reported_count = int(header.split(":")[1].strip().split()[0])
    bulleted_count = sum(1 for line in out.splitlines() if line.lstrip().startswith("-"))
    assert bulleted_count > 0
    assert reported_count == bulleted_count


def test_preview_returns_exit_0_when_acceptance_passed(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_pipeline(*a, **k):
        return {
            "exit_code": 0,
            "stats": {"acceptance": {"passed": True, "problems": []}},
        }

    monkeypatch.setattr(cli_module, "run_pipeline", fake_run_pipeline)
    args = _preview_args(tmp_path / "state", tmp_path / "out")
    assert cli_module._cmd_preview(args) == 0
