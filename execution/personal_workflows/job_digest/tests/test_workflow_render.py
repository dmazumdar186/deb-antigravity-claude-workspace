"""
description: Offline unit tests for workflow_render.py's render_workflow() and
    its per-zone DST cron-grouping helper (_schedule_groups).
inputs: synthetic Profile objects (Europe/Paris, America/New_York — northern
    DST; Asia/Kolkata — no DST; Australia/Sydney — inverted/southern DST).
    DST-grouping tests pin year=2026 (via _schedule_groups' private `year`
    kwarg) so results are deterministic regardless of when the suite runs —
    _schedule_groups samples the 1st of every month at hour_local, and a
    zone's exact transition-month boundary can shift by one month in a given
    year depending on which day of the week the 1st falls on (documented,
    accepted edge — see workflow_render.py's module docstring).
outputs: pytest assertions that the rendered YAML parses and carries the
    expected cron groups/month gates, and that layout="standalone" (default)
    vs layout="workspace" swap the install/run command forms.
"""
from __future__ import annotations

import yaml

from execution.personal_workflows.job_digest.profile_schema import Profile
from execution.personal_workflows.job_digest.workflow_render import (
    _schedule_groups,
    render_workflow,
)

_PINNED_YEAR = 2026


def _profile(timezone: str, hour_local: int = 9) -> Profile:
    raw = {
        "version": 1,
        "candidate": {"name": "Jordan Example", "email": "jordan.example@example.com"},
        "roles": [{"title": "Sales Manager", "synonyms": [], "seniority": "any"}],
        "locations": {"countries": ["FR"], "cities": [], "remote_ok": True},
        "screening": {"summary": "A" * 50, "skills": []},
        "digest": {"hour_local": hour_local, "timezone": timezone},
    }
    return Profile.model_validate(raw)


def _cron_lines(text: str) -> list[str]:
    return [
        line.split("cron:", 1)[1].strip().strip('"')
        for line in text.splitlines()
        if "cron:" in line
    ]


def test_output_is_valid_yaml():
    profile = _profile("Europe/Paris")
    text = render_workflow(profile)
    parsed = yaml.safe_load(text)
    assert parsed["name"] == "job-digest"
    assert "schedule" in parsed["on"]
    assert "workflow_dispatch" in parsed["on"]


def test_europe_paris_emits_two_month_gated_pairs():
    profile = _profile("Europe/Paris", hour_local=9)
    text = render_workflow(profile, minute=13)
    crons = _cron_lines(text)

    # DST zone -> 4 cron entries (2 pairs): summer (Apr-Oct) + winter (Nov-Mar/Jan-Mar).
    assert len(crons) == 4

    months = {c.split()[3] for c in crons}
    assert "4-10" in months
    assert "1-3,11-12" in months

    # Every cron must carry a real HH:MM, and each pair's second entry sits
    # ~40 minutes after the first.
    for month in ("4-10", "1-3,11-12"):
        pair = [c for c in crons if c.split()[3] == month]
        assert len(pair) == 2
        m1, h1 = int(pair[0].split()[0]), int(pair[0].split()[1])
        m2, h2 = int(pair[1].split()[0]), int(pair[1].split()[1])
        gap = ((h2 * 60 + m2) - (h1 * 60 + m1)) % 1440
        assert gap == 40


def test_asia_kolkata_single_pair_at_expected_utc_time():
    profile = _profile("Asia/Kolkata", hour_local=9)
    text = render_workflow(profile, minute=13)
    crons = _cron_lines(text)

    # No DST -> single pair, no month gate.
    assert len(crons) == 2
    for c in crons:
        assert c.split()[3] == "*"

    times = sorted(f"{int(c.split()[1]):02d}:{int(c.split()[0]):02d}" for c in crons)
    # 9:13 IST (UTC+5:30) -> 03:43 UTC; second fire 40 min later -> 04:23 UTC.
    assert times == ["03:43", "04:23"]


def test_minute_offset_argument_changes_schedule():
    profile = _profile("Asia/Kolkata", hour_local=9)
    default_crons = _cron_lines(render_workflow(profile))
    custom_crons = _cron_lines(render_workflow(profile, minute=0))
    assert default_crons != custom_crons


def test_workflow_contains_expected_structural_pieces():
    profile = _profile("Europe/Paris")
    parsed = yaml.safe_load(render_workflow(profile))

    assert parsed["permissions"]["contents"] == "write"
    assert parsed["permissions"]["issues"] == "write"
    assert parsed["concurrency"]["group"] == "job-digest"
    assert parsed["on"]["workflow_dispatch"]["inputs"]["dry_run"]["type"] == "boolean"

    steps = parsed["jobs"]["run"]["steps"]
    step_names = [s.get("name", "") for s in steps]
    assert any("Set up Python" in n for n in step_names)
    assert any("Install dependencies" in n for n in step_names)
    assert any("Run job_digest" in n for n in step_names)
    assert any("Commit state" in n for n in step_names)
    assert any("Upload run artifacts" in n for n in step_names)
    assert any("failure issue" in n for n in step_names)


# ----- standalone (default) vs workspace layout -----


def test_standalone_layout_is_the_default_and_uses_engine_paths():
    profile = _profile("Asia/Kolkata")
    text = render_workflow(profile)
    assert "PYTHONPATH=engine python -m job_digest.cli run profile.yaml" in text
    assert "pip install -r engine/requirements.txt" in text
    assert "execution.personal_workflows.job_digest.cli" not in text


def test_workspace_layout_keeps_in_repo_module_path():
    profile = _profile("Asia/Kolkata")
    text = render_workflow(profile, layout="workspace")
    assert "python -m execution.personal_workflows.job_digest.cli run profile.yaml" in text
    assert "pip install -r requirements.txt" in text
    assert "PYTHONPATH=engine" not in text


def test_unknown_layout_rejected():
    import pytest

    profile = _profile("Asia/Kolkata")
    with pytest.raises(ValueError):
        render_workflow(profile, layout="bogus")


# ----- state commit-back step (H1) -----


def test_state_commit_step_skips_dry_run_and_handles_missing_state_dir():
    profile = _profile("Asia/Kolkata")
    parsed = yaml.safe_load(render_workflow(profile))
    steps = parsed["jobs"]["run"]["steps"]
    commit_step = next(s for s in steps if "Commit state" in s.get("name", ""))

    assert "dry_run" in commit_step["if"]
    run_text = commit_step["run"]
    assert "mkdir -p state" in run_text
    # git add must run after mkdir so it never fails on a fresh clone / dry run / early exit.
    assert run_text.index("mkdir -p state") < run_text.index("git add state")
    # commit failure ("nothing to commit") must not be silently identical to a
    # push failure being hidden — push failure must surface as a warning, not `|| true`.
    assert "git push || echo" in run_text
    assert "::warning::" in run_text
    assert "git pull --rebase --autostash" in run_text


def test_permissions_documented_at_job_level():
    text = render_workflow(_profile("Asia/Kolkata"))
    assert "GitHub Actions grants permissions per JOB" in text


# ----- DST month-grouping via _schedule_groups, pinned to a fixed year -----


def test_schedule_groups_europe_paris_pinned_year():
    profile = _profile("Europe/Paris", hour_local=9)
    groups = _schedule_groups(profile, minute=13, year=_PINNED_YEAR)
    months = {g["months"] for g in groups}
    assert months == {"4-10", "1-3,11-12"}


def test_schedule_groups_new_york_pinned_year():
    profile = _profile("America/New_York", hour_local=9)
    groups = _schedule_groups(profile, minute=13, year=_PINNED_YEAR)
    months = {g["months"] for g in groups}
    assert months == {"4-10", "1-3,11-12"}


def test_schedule_groups_kolkata_single_group():
    profile = _profile("Asia/Kolkata", hour_local=9)
    groups = _schedule_groups(profile, minute=13, year=_PINNED_YEAR)
    assert len(groups) == 1
    assert groups[0]["months"] == "*"


def test_schedule_groups_sydney_inverted_and_documented():
    profile = _profile("Australia/Sydney", hour_local=9)
    groups = _schedule_groups(profile, minute=13, year=_PINNED_YEAR)
    # Southern-hemisphere DST: exactly two groups, together covering all 12 months,
    # with the higher (more positive) UTC offset being the Dec/Jan-adjacent group.
    assert len(groups) == 2
    months = {g["months"] for g in groups}
    # 1st-of-month sampling for 2026 puts the DST/summer group's boundary one
    # month later on each side than the "Oct-Mar" civil description (Sydney's
    # real transition days in 2026 are Apr 5 and Oct 4, both after the 1st) —
    # this is the documented sampling edge, not a bug.
    assert months == {"1-4,11-12", "5-10"}
    covered = set()
    for g in groups:
        for part in g["months"].split(","):
            if "-" in part:
                a, b = part.split("-")
                covered.update(range(int(a), int(b) + 1))
            else:
                covered.add(int(part))
    assert covered == set(range(1, 13))


def test_render_workflow_parses_for_sydney_and_new_york():
    for tz in ("Australia/Sydney", "America/New_York"):
        parsed = yaml.safe_load(render_workflow(_profile(tz)))
        assert parsed["name"] == "job-digest"
        assert isinstance(parsed["on"]["schedule"], list)
