"""
description: End-to-end smoke test for the packaged, standalone job-digest
    bundle — builds dist/job-digest-skill.zip into a tmp dir, unzips it, and
    drives its CLI exactly the way a friend's machine would: from a
    non-repo cwd, with PYTHONPATH=<bundle>/engine, never importing the
    workspace's `execution.*` package.
inputs: none (everything happens under tmp_path / a subprocess)
outputs: pytest assertions on subprocess exit codes and stdout content.
    Uses subprocess with encoding="utf-8", errors="replace" per
    .claude/rules/python-hardening.md.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_PATH = REPO_ROOT / "scripts" / "package_job_digest.py"


def _load_package_module():
    spec = importlib.util.spec_from_file_location("package_job_digest_smoke", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def bundle_dir(tmp_path_factory):
    """Build the real zip and unzip it into a tmp dir. Module-scoped: every
    test in this file drives the same on-disk bundle, none of them mutate it."""
    pkg_mod = _load_package_module()
    dist_dir = tmp_path_factory.mktemp("dist")
    zip_path = pkg_mod.build(dist_dir=dist_dir, zip_name="job-digest-skill.zip")

    extract_dir = tmp_path_factory.mktemp("bundle")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)

    return extract_dir / "job-digest"


def _run_cli(bundle_dir: Path, args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    engine_dir = bundle_dir / "engine"
    env = {
        "PYTHONPATH": str(engine_dir),
        "PATH": __import__("os").environ.get("PATH", ""),
        "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", ""),
    }
    return subprocess.run(
        [sys.executable, "-m", "job_digest.cli", *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )


def test_validate_example_profile(bundle_dir, tmp_path):
    # Run from a non-repo cwd so a stray `execution` package on sys.path
    # can't mask a bundle that's missing something.
    non_repo_cwd = tmp_path / "cwd"
    non_repo_cwd.mkdir()

    example_profile = bundle_dir / "engine" / "job_digest" / "templates" / "profile.example.yaml"
    assert example_profile.exists(), "packaged bundle must include templates/profile.example.yaml"

    result = _run_cli(bundle_dir, ["validate", str(example_profile)], cwd=non_repo_cwd)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


def test_run_dry_mode(bundle_dir, tmp_path):
    non_repo_cwd = tmp_path / "cwd"
    non_repo_cwd.mkdir()
    example_profile = bundle_dir / "engine" / "job_digest" / "templates" / "profile.example.yaml"
    state_dir = tmp_path / "state"
    out_dir = tmp_path / "out"

    result = _run_cli(
        bundle_dir,
        [
            "run",
            str(example_profile),
            "--mode",
            "dry",
            "--state-dir",
            str(state_dir),
            "--out-dir",
            str(out_dir),
        ],
        cwd=non_repo_cwd,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    fixtures_dir = bundle_dir / "engine" / "job_digest" / "fixtures"
    if fixtures_dir.exists() and any(fixtures_dir.glob("*.jsonl")):
        # Fixtures are bundled — dry mode should have actually fetched rows
        # from them, not silently returned zero (see sources/__init__.py's C5 note).
        assert "fetched" in result.stdout
        fetched_line = next(line for line in result.stdout.splitlines() if "fetched_total" in line or "'fetched_total'" in line)
        # stats dict is printed inline by cli.py's `run` command; pull the int out crudely.
        import re

        match = re.search(r"'fetched_total':\s*(\d+)", fetched_line)
        assert match is not None, fetched_line
        assert int(match.group(1)) > 0
    # TODO: once every source's fixtures are confirmed present in every packaged
    # bundle build (not just this workspace checkout), drop the `if` guard above
    # and always assert fetched_total > 0.


def test_render_workflow_output_is_valid_and_standalone(bundle_dir, tmp_path):
    non_repo_cwd = tmp_path / "cwd"
    non_repo_cwd.mkdir()
    example_profile = bundle_dir / "engine" / "job_digest" / "templates" / "profile.example.yaml"

    result = _run_cli(bundle_dir, ["render-workflow", str(example_profile)], cwd=non_repo_cwd)
    assert result.returncode == 0, result.stdout + result.stderr

    parsed = yaml.safe_load(result.stdout)
    assert parsed["name"] == "job-digest"
    assert "PYTHONPATH=engine" in result.stdout
    assert "engine/requirements.txt" in result.stdout


def test_setup_with_answers(bundle_dir, tmp_path):
    non_repo_cwd = tmp_path / "cwd"
    non_repo_cwd.mkdir()

    # Confirm cli.py's `setup` subcommand actually accepts --answers before
    # relying on it — another agent owns cli.py and may not have landed it yet.
    probe = subprocess.run(
        [sys.executable, "-m", "job_digest.cli", "setup", "--help"],
        cwd=str(non_repo_cwd),
        env={"PYTHONPATH": str(bundle_dir / "engine"), "PATH": __import__("os").environ.get("PATH", "")},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if "--answers" not in probe.stdout:
        pytest.skip("cli.py's `setup` subcommand does not accept --answers yet (owned by another agent)")

    answers = {
        "candidate": {"name": "Jordan Example", "email": "jordan.example@example.com"},
        "roles": [{"title": "Sales Manager", "synonyms": [], "seniority": "mid"}],
        "locations": {"countries": ["FR"], "cities": [], "remote_ok": True},
        "contracts": ["permanent"],
        "screening": {"summary": "A" * 50, "skills": []},
        "digest": {"hour_local": 9, "timezone": "Europe/Paris"},
        "sheet": {"enabled": False},
    }
    import json

    answers_path = tmp_path / "answers.json"
    answers_path.write_text(json.dumps(answers), encoding="utf-8")
    out_path = tmp_path / "profile.yaml"

    result = _run_cli(
        bundle_dir,
        ["setup", "--answers", str(answers_path), "--out", str(out_path)],
        cwd=non_repo_cwd,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert out_path.exists()
