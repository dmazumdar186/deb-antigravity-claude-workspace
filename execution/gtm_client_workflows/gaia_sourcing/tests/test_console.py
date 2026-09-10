"""Tests for render/console.py against the fixture run dir in
tests/fixtures/console/. No network, no LLM, no real run/ directory touched.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from gtm_client_workflows.gaia_sourcing.render import console
from gtm_client_workflows.gaia_sourcing.roles import ROLE1, ROLE2

FIXTURE_RUN_DIR = Path(__file__).parent / "fixtures" / "console"


def _render(tmp_path, run_dir=FIXTURE_RUN_DIR, page_status=None):
    out_dir = tmp_path / "console"
    console.render_console("gaia-test-campaign", out_dir, run_dir=run_dir, page_status=page_status)
    return out_dir


def _no_missing_key_errors(html: str) -> None:
    # A KeyError/AttributeError surfacing into the page would render as a
    # Python repr somewhere in the markup -- these are the shapes that leak
    # through str(exc) if a caller ever let one propagate into an f-string.
    for bad in ("KeyError", "AttributeError", "Traceback (most recent call last)"):
        assert bad not in html, "found " + bad + " leaked into rendered HTML"


def test_render_console_produces_all_pages(tmp_path):
    out_dir = _render(tmp_path)
    expected = {
        "index.html", "jobs.html", "poolmap.html", "scorecard.html",
        "shortlist_" + ROLE1.role_id + ".html",
        "shortlist_" + ROLE2.role_id + ".html",
        "card_alice_kearney.html", "card_brian_walsh.html", "card_ciara_hennessy.html",
    }
    produced = {p.name for p in out_dir.glob("*.html")}
    assert expected.issubset(produced)


def test_every_page_renders_without_missing_key_errors(tmp_path):
    out_dir = _render(tmp_path)
    for f in out_dir.glob("*.html"):
        html = f.read_text(encoding="utf-8")
        _no_missing_key_errors(html)
        assert "<!doctype html>" in html.lower()
        assert "<title>" in html


def test_index_shows_empty_states_when_optional_stage_files_absent(tmp_path):
    out_dir = _render(tmp_path)
    html = (out_dir / "index.html").read_text(encoding="utf-8")
    # Fixture run dir carries no outreach_queue.json / replies.json -- the
    # page must say so honestly rather than showing a fabricated zero.
    assert "No outreach_queue.json yet" in html
    assert "No replies.json yet" in html


def test_scorecard_empty_state_lists_six_metric_names(tmp_path):
    out_dir = _render(tmp_path)
    html = (out_dir / "scorecard.html").read_text(encoding="utf-8")
    for key, _label, _threshold in console.SCORECARD_METRICS:
        assert key in html
    assert len(console.SCORECARD_METRICS) == 6


def test_scorecard_renders_values_when_present(tmp_path):
    run_dir = tmp_path / "run_with_scorecard"
    run_dir.mkdir()
    for f in FIXTURE_RUN_DIR.glob("*.json"):
        (run_dir / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    (run_dir / "scorecard.json").write_text(json.dumps({
        "composition_violations": 0,
        "quote_drop_rate": 0.02,
        "grade_precision": 0.95,
        "residence_precision": 0.91,
        "delivered_over_pool": 0.5,
        "cost_per_delivered_card": 1.8,
    }), encoding="utf-8")
    out_dir = _render(tmp_path, run_dir=run_dir)
    html = (out_dir / "scorecard.html").read_text(encoding="utf-8")
    assert "0.95" in html
    assert "not computed" not in html


def test_health_banner_renders_days_since_refresh(tmp_path):
    run_dir = tmp_path / "run_with_health"
    run_dir.mkdir()
    for f in FIXTURE_RUN_DIR.glob("*.json"):
        (run_dir / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    (run_dir / "health.json").write_text(json.dumps({"days_since_refresh": 3}), encoding="utf-8")
    out_dir = _render(tmp_path, run_dir=run_dir)
    html = (out_dir / "index.html").read_text(encoding="utf-8")
    assert "3 days ago" in html


def test_health_banner_renders_the_real_stage_health_shape(tmp_path):
    """run.py's stage_health writes {stale_days, pool_last_refreshed, ...}
    (RADAR_CONTRACTS.md section G / HANDOFF.md 2026-09-10), not the older
    days_since_refresh/pool_refreshed_at names -- the banner must read both.
    """
    run_dir = tmp_path / "run_with_real_health"
    run_dir.mkdir()
    for f in FIXTURE_RUN_DIR.glob("*.json"):
        (run_dir / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    (run_dir / "health.json").write_text(json.dumps({
        "campaign_id": "gaia-test-campaign",
        "generated_at": "2026-09-10T12:00:00+00:00",
        "pool_last_refreshed": "2026-09-03",
        "stale_days": 7,
        "integrations": {"recruit_crm": "missing", "alert_webhook": "missing",
                          "modal_radar": "missing"},
    }), encoding="utf-8")
    out_dir = _render(tmp_path, run_dir=run_dir)
    html = (out_dir / "index.html").read_text(encoding="utf-8")
    assert "7 days ago" in html


def test_index_shows_pending_approval_from_the_real_outreach_queue_shape(tmp_path):
    """layers/outreach_queue.py writes a dict keyed by draft_id, each value
    a QueueEntry with a "state" field (not "status") -- the console's
    Pending-approvals table must read that exact shape.
    """
    run_dir = tmp_path / "run_with_queue"
    run_dir.mkdir()
    for f in FIXTURE_RUN_DIR.glob("*.json"):
        (run_dir / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    draft_id = "alice_kearney:" + ROLE1.role_id
    (run_dir / "outreach_queue.json").write_text(json.dumps({
        draft_id: {
            "draft_id": draft_id,
            "person_id": "alice_kearney",
            "role_id": ROLE1.role_id,
            "state": "pending_approval",
            "history": [{"ts": "2026-09-10T00:00:00+00:00", "from": "draft",
                         "to": "pending_approval", "by": "system"}],
        },
        "brian_walsh:" + ROLE1.role_id: {
            "draft_id": "brian_walsh:" + ROLE1.role_id,
            "person_id": "brian_walsh",
            "role_id": ROLE1.role_id,
            "state": "approved",
            "history": [],
        },
    }), encoding="utf-8")
    out_dir = _render(tmp_path, run_dir=run_dir)
    html = (out_dir / "index.html").read_text(encoding="utf-8")
    assert "Alice Kearney" in html
    assert draft_id in html
    # brian_walsh is "approved", not "pending_approval" -- must not surface here.
    assert "Brian Walsh" not in html.split("Pending approvals")[1].split("</section>")[0]


def test_health_banner_absent_when_no_health_file(tmp_path):
    out_dir = _render(tmp_path)
    html = (out_dir / "index.html").read_text(encoding="utf-8")
    assert "class='health" not in html.replace('"', "'")


def test_shortlist_page_lists_all_three_fixture_persons_across_two_roles(tmp_path):
    out_dir = _render(tmp_path)
    r1 = (out_dir / ("shortlist_" + ROLE1.role_id + ".html")).read_text(encoding="utf-8")
    r2 = (out_dir / ("shortlist_" + ROLE2.role_id + ".html")).read_text(encoding="utf-8")
    assert "Alice Kearney" in r1
    assert "Brian Walsh" in r1
    assert "Ciara Hennessy" not in r1
    assert "Ciara Hennessy" in r2


def test_shortlist_page_includes_brief_rail_defaults_from_roles(tmp_path):
    out_dir = _render(tmp_path)
    html = (out_dir / ("shortlist_" + ROLE1.role_id + ".html")).read_text(encoding="utf-8")
    ceiling = next(g for g in ROLE1.hard_gates if g.check == "seniority_ceiling")
    assert 'value=\'' + ceiling.params["max_grade"] + '\' selected' in html or \
        "selected>" + ceiling.params["max_grade"] in html


def test_card_page_shows_evidence_gates_contact_and_outreach(tmp_path):
    out_dir = _render(tmp_path)
    html = (out_dir / "card_alice_kearney.html").read_text(encoding="utf-8")
    assert "Chartered Engineer" in html  # evidence quote
    assert "chartered" in html  # gate id
    assert "alice.kearney@example.com" in html  # contact
    assert "Senior Structural Engineer opportunity" in html  # outreach draft


def test_card_page_outreach_empty_state_for_person_without_a_draft(tmp_path):
    out_dir = _render(tmp_path)
    html = (out_dir / "card_ciara_hennessy.html").read_text(encoding="utf-8")
    assert "No outreach drafted for this person yet." in html


def test_page_status_badges_default_to_cached(tmp_path):
    out_dir = _render(tmp_path)
    html = (out_dir / "index.html").read_text(encoding="utf-8")
    assert "badge CACHED" in html


def test_page_status_override_shows_live_badge(tmp_path):
    out_dir = _render(tmp_path, page_status={"index": "LIVE"})
    html = (out_dir / "index.html").read_text(encoding="utf-8")
    assert "badge LIVE" in html


def test_empty_run_dir_still_renders_index_with_empty_states(tmp_path):
    empty_run = tmp_path / "empty_run"
    empty_run.mkdir()
    out_dir = _render(tmp_path, run_dir=empty_run)
    html = (out_dir / "index.html").read_text(encoding="utf-8")
    _no_missing_key_errors(html)
    assert "No outreach_queue.json yet" in html
    jobs_html = (out_dir / "jobs.html").read_text(encoding="utf-8")
    assert "0 / " in jobs_html


def test_poolmap_page_renders_fixture_counts(tmp_path):
    out_dir = _render(tmp_path)
    html = (out_dir / "poolmap.html").read_text(encoding="utf-8")
    assert re.search(r"<div class=\"tnum\">2</div>", html)  # role1 profiles_assessed
