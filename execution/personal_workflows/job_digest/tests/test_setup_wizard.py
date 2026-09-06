"""
description: Offline unit tests for setup_wizard.py's non-interactive
    --answers path (main() -> int).
inputs: a synthetic answers.json (profile.yaml-shaped) written to tmp_path.
outputs: pytest assertions that profile.yaml is written and passes
    profile_schema.load_profile(); and that invalid answers fail loudly
    without prompting (exit code 1, no crash).
"""
from __future__ import annotations

import json

from execution.personal_workflows.job_digest.profile_schema import load_profile
from execution.personal_workflows.job_digest.setup_wizard import main

_VALID_ANSWERS = {
    "candidate": {"name": "Jordan Example", "email": "jordan.example@example.com"},
    "roles": [
        {"title": "Sales Manager", "synonyms": ["Regional Sales Manager"], "seniority": "mid"},
    ],
    "locations": {"countries": ["FR", "IN"], "cities": ["Paris"], "remote_ok": True},
    "contracts": ["permanent", "fixed_term"],
    "screening": {
        "summary": (
            "I'm a sales manager with 8 years of B2B SaaS experience across France "
            "and India. I lead teams of up to 6 reps and hit 110% of quota."
        ),
        "skills": ["B2B sales", "SaaS", "CRM"],
    },
    "digest": {"hour_local": 9, "timezone": "Europe/Paris"},
    "sheet": {"enabled": True},
}


def test_answers_json_produces_valid_profile_yaml(tmp_path):
    answers_path = tmp_path / "answers.json"
    answers_path.write_text(json.dumps(_VALID_ANSWERS), encoding="utf-8")
    out_path = tmp_path / "profile.yaml"

    exit_code = main(["--answers", str(answers_path), "--out", str(out_path)])

    assert exit_code == 0
    assert out_path.exists()

    profile = load_profile(out_path)
    assert profile.candidate.email == "jordan.example@example.com"
    assert profile.roles[0].title == "Sales Manager"
    assert profile.locations.countries == ["FR", "IN"]
    assert profile.digest.timezone == "Europe/Paris"
    assert profile.sheet.enabled is True


def test_answers_json_written_profile_has_comment_header(tmp_path):
    answers_path = tmp_path / "answers.json"
    answers_path.write_text(json.dumps(_VALID_ANSWERS), encoding="utf-8")
    out_path = tmp_path / "profile.yaml"

    main(["--answers", str(answers_path), "--out", str(out_path)])

    text = out_path.read_text(encoding="utf-8")
    assert text.startswith("#")


def test_invalid_answers_fail_without_crashing(tmp_path, capsys):
    bad_answers = json.loads(json.dumps(_VALID_ANSWERS))
    bad_answers["candidate"]["email"] = "not-an-email"
    answers_path = tmp_path / "answers.json"
    answers_path.write_text(json.dumps(bad_answers), encoding="utf-8")
    out_path = tmp_path / "profile.yaml"

    exit_code = main(["--answers", str(answers_path), "--out", str(out_path)])

    assert exit_code == 1
    assert not out_path.exists()
    captured = capsys.readouterr()
    assert "email" in (captured.out + captured.err).lower()


def test_missing_answers_file_fails_cleanly(tmp_path):
    out_path = tmp_path / "profile.yaml"
    exit_code = main(["--answers", str(tmp_path / "nope.json"), "--out", str(out_path)])
    assert exit_code == 1
    assert not out_path.exists()
