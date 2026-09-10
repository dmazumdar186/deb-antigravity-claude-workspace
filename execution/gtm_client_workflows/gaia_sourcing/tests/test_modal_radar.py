"""Tests for execution/modal_radar.py (workspace execution root) and its
underlying pure logic in layers/recut.py. No network, no Modal required --
`modal` is imported lazily in the thin wrapper module, so these run whether
or not the `modal` package is installed in this environment.

`modal_radar` here refers to `gtm_client_workflows.gaia_sourcing.layers.recut`
-- the pure, modal-free module that `execution/modal_radar.py` (the deployed
Modal app, a thin wrapper) actually delegates to. Testing against
`layers.recut` directly means this suite needs no sys.path games to reach a
top-level `execution/modal_radar.py` module, and it is exactly the surface
the thin wrapper re-exports unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gtm_client_workflows.gaia_sourcing.layers import recut as modal_radar
from gtm_client_workflows.gaia_sourcing.roles import ROLE1, ROLE2

FIXTURE_RUN_DIR = Path(__file__).parent / "fixtures" / "console"


def _load(name: str) -> dict:
    return json.loads((FIXTURE_RUN_DIR / (name + ".json")).read_text(encoding="utf-8"))


@pytest.fixture()
def extract():
    return _load("extract")


@pytest.fixture()
def validate():
    return _load("validate")


def test_recut_runs_without_modal_installed():
    # The whole point of the lazy import: this module is importable and its
    # pure function callable with zero dependency on the `modal` package.
    assert hasattr(modal_radar, "recut")


def test_recut_role1_no_overrides_survives_both_fixture_persons(extract, validate):
    result = modal_radar.recut(extract, validate, ROLE1, {})
    survivor_ids = {s["person_id"] for s in result["survivors"]}
    assert survivor_ids == {"alice_kearney", "brian_walsh"}
    assert result["excluded"] == []


def test_recut_with_director_ceiling_excludes_the_director_fixture_person(extract, validate):
    # ciara_hennessy's title is "Technical Director" -- above associate_director.
    # The base ROLE2 spec already carries that ceiling; applying it again
    # (or an equivalently strict one) through overrides must still exclude her.
    overrides = {"max_grade": "associate_director"}
    result = modal_radar.recut(extract, validate, ROLE2, overrides)
    excluded_ids = {x["person_id"] for x in result["excluded"]}
    assert "ciara_hennessy" in excluded_ids
    rec = next(x for x in result["excluded"] if x["person_id"] == "ciara_hennessy")
    assert "seniority_ceiling" in rec["gates_failed"]
    assert result["per_gate_counts"].get("seniority_ceiling", 0) >= 1


def test_recut_lenient_ceiling_lets_the_director_survive(extract, validate):
    overrides = {"max_grade": "director"}
    result = modal_radar.recut(extract, validate, ROLE2, overrides)
    survivor_ids = {s["person_id"] for s in result["survivors"]}
    assert "ciara_hennessy" in survivor_ids


def test_overrides_never_mutate_roles_role1(extract, validate):
    before = json.dumps(
        [{"gate_id": g.gate_id, "params": dict(g.params)} for g in ROLE1.hard_gates],
        sort_keys=True,
    )
    modal_radar.recut(
        extract, validate, ROLE1,
        {"max_grade": "senior_engineer", "max_years": 1, "min_years": 99,
         "counties": ["Donegal"], "strict_location": True},
    )
    after = json.dumps(
        [{"gate_id": g.gate_id, "params": dict(g.params)} for g in ROLE1.hard_gates],
        sort_keys=True,
    )
    assert before == after, "recut() must never mutate the module-level ROLE1 JobSpec"


def test_overrides_never_mutate_roles_role2(extract, validate):
    before = json.dumps(
        [{"gate_id": g.gate_id, "params": dict(g.params)} for g in ROLE2.hard_gates],
        sort_keys=True,
    )
    modal_radar.recut(extract, validate, ROLE2, {"max_grade": "senior_engineer"})
    after = json.dumps(
        [{"gate_id": g.gate_id, "params": dict(g.params)} for g in ROLE2.hard_gates],
        sort_keys=True,
    )
    assert before == after


def test_recut_handler_reads_from_run_dir(tmp_path, monkeypatch, extract, validate):
    run_dir = tmp_path / "gaia-test-campaign"
    run_dir.mkdir(parents=True)
    (run_dir / "extract.json").write_text(json.dumps(extract), encoding="utf-8")
    (run_dir / "validate.json").write_text(json.dumps(validate), encoding="utf-8")

    monkeypatch.setattr(modal_radar, "_run_dir_for", lambda campaign_id: run_dir)

    out = modal_radar.recut_handler({
        "campaign_id": "gaia-test-campaign",
        "role_id": ROLE1.role_id,
        "brief_overrides": {},
    })
    assert "recut_id" in out
    assert {s["person_id"] for s in out["survivors"]} == {"alice_kearney", "brian_walsh"}
    # Audit copy written under run/<c>/recuts/<uuid>.json
    recut_files = list((run_dir / "recuts").glob("*.json"))
    assert len(recut_files) == 1
    saved = json.loads(recut_files[0].read_text(encoding="utf-8"))
    assert saved["recut_id"] == out["recut_id"]


def test_recut_handler_missing_stage_files_returns_error_not_crash(tmp_path, monkeypatch):
    run_dir = tmp_path / "no-such-campaign"
    monkeypatch.setattr(modal_radar, "_run_dir_for", lambda campaign_id: run_dir)
    out = modal_radar.recut_handler({
        "campaign_id": "no-such-campaign", "role_id": ROLE1.role_id, "brief_overrides": {},
    })
    assert "error" in out


def test_recut_handler_unknown_role_id_returns_error(tmp_path, monkeypatch, extract, validate):
    run_dir = tmp_path / "gaia-test-campaign"
    run_dir.mkdir(parents=True)
    (run_dir / "extract.json").write_text(json.dumps(extract), encoding="utf-8")
    (run_dir / "validate.json").write_text(json.dumps(validate), encoding="utf-8")
    monkeypatch.setattr(modal_radar, "_run_dir_for", lambda campaign_id: run_dir)
    out = modal_radar.recut_handler({
        "campaign_id": "gaia-test-campaign", "role_id": "not_a_real_role", "brief_overrides": {},
    })
    assert "error" in out


def test_approve_appends_the_exact_record(tmp_path, monkeypatch):
    run_dir = tmp_path / "gaia-test-campaign"
    monkeypatch.setattr(modal_radar, "_run_dir_for", lambda campaign_id: run_dir)

    out = modal_radar.approve_handler({
        "campaign_id": "gaia-test-campaign",
        "draft_id": "alice_kearney",
        "by": "keith",
        "action": "approve",
    })
    assert out["status"] == "recorded"

    lines = (run_dir / "approvals.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["draft_id"] == "alice_kearney"
    assert rec["campaign_id"] == "gaia-test-campaign"
    assert rec["by"] == "keith"
    assert rec["action"] == "approve"
    assert "at" in rec

    # A second call appends rather than overwrites.
    modal_radar.approve_handler({
        "campaign_id": "gaia-test-campaign",
        "draft_id": "brian_walsh",
        "by": "keith",
        "action": "reject",
    })
    lines = (run_dir / "approvals.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_approve_rejects_invalid_action(tmp_path, monkeypatch):
    run_dir = tmp_path / "gaia-test-campaign"
    monkeypatch.setattr(modal_radar, "_run_dir_for", lambda campaign_id: run_dir)
    out = modal_radar.approve_handler({
        "campaign_id": "gaia-test-campaign", "draft_id": "alice_kearney",
        "by": "keith", "action": "delete_everything",
    })
    assert "error" in out
    assert not (run_dir / "approvals.jsonl").exists()


def test_approve_requires_campaign_and_draft_id():
    out = modal_radar.approve_handler({"by": "keith", "action": "approve"})
    assert "error" in out
