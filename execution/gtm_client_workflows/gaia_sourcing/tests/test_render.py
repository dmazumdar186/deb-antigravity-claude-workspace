"""
L13 renderer tests -- UX/UI and honesty properties of the artifact itself.

The dossier is the only thing the client ever sees, so these assert on what a
reader will find on the page, not on whether the function returned. They run
against a synthetic run directory with zero network.
"""

from __future__ import annotations

import json
import re

import pytest

from gtm_client_workflows.gaia_sourcing.render import render as R

CLAIM = {
    "claim_id": "c1",
    "subject_person_id": "p1",
    "dimension": "technical_skill",
    "assertion": "Designed a transfer structure to Eurocode 2.",
    "evidence_quote": "designed the transfer structure to EN 1992-1-1",
    "source_doc_id": "d1",
    "source_url": "https://example.ie/p/one",
    "confidence": "direct",
    "quote_verified": True,
}

GATE_OK = {"gate_id": "chartered", "passed": True, "basis": None, "note": None}


@pytest.fixture
def rendered(tmp_path, monkeypatch):
    """Build the artifacts into a temp dir and return (html, csv, out_dir)."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    out_dir = tmp_path / "deliverables"
    monkeypatch.setattr(R, "RUN_DIR", run_dir)
    monkeypatch.setattr(R, "OUT_DIR", out_dir)
    # The notice-liveness probe is mocked DEAD by default so these tests
    # assert on the withheld-outreach branch deterministically. Left
    # unmocked it hits the real URL, so the suite's verdict changed the
    # moment the notice was actually deployed -- a test whose result depends
    # on today's network is not a test.
    monkeypatch.setattr(R, "head_ok", lambda url, timeout=20: (False, 404))

    def w(name, obj):
        (run_dir / (name + ".json")).write_text(json.dumps(obj), encoding="utf-8")

    w("extract", {
        "persons": {
            "p1": {
                "person_id": "p1", "full_name": "Sean O'Brien",
                "current_title": "Senior Structural Engineer",
                "current_employer": "Example Engineers", "location": "Dublin",
                "doc_ids": ["d1"],
                "role_id": "role1_senior_structural_engineer",
                "profile_url": "https://example.ie/p/one",
            }
        },
        "claims": [CLAIM],
    })
    w("validate", {"claims": [CLAIM], "stats": {"drop_rate": 0.0}})
    w("gate", {"p1": {
        "role_id": "role1_senior_structural_engineer", "tier": "B",
        "gates": [GATE_OK], "n_claims": 1, "client_side": False,
    }})
    w("adversarial", {"p1": {
        "person_id": "p1", "role_id": "role1_senior_structural_engineer",
        "tier": "B", "gates": [GATE_OK],
        "strengths": ["Named design-code evidence, rare in this pool."],
        "unknowns": ["Years of experience not stated."],
        "adversarial_findings": [],
    }})
    w("contact", {"p1": {
        "person_id": "p1", "email": "sean.obrien@example.ie",
        "email_status": "pattern_guess", "email_provider": "pattern",
        "linkedin_url": "https://www.linkedin.com/in/seanobrien",
        "linkedin_live": False, "recommended_first_channel": "linkedin",
        "channel_rationale": "LinkedIn first.",
    }})
    w("movability", {"p1": {
        "person_id": "p1", "assessment": "unknown", "signals": [],
        "rationale": "No public signal either way.",
    }})
    w("messages", {})
    w("linkcheck", {"p1": {
        "person_id": "p1", "all_alive": False,
        "checks": [
            {"url": "https://example.ie/p/one", "alive": True,
             "http_status": 200, "name_matched": True, "note": ""},
            # LinkedIn answers every non-browser client with 999.
            {"url": "https://www.linkedin.com/in/seanobrien", "alive": None,
             "http_status": 999, "name_matched": None, "note": ""},
        ],
    }})
    w("poolmap", {
        "role1_senior_structural_engineer": {
            "role_id": "role1_senior_structural_engineer",
            "profiles_assessed": 40, "raw_claims": 100, "evidence_validated": 95,
            "passed_all_gates": 12, "delivered": 1,
            "exclusions": [{"reason": "chartered", "count": 20}],
            "client_side_sidebar": [],
        },
        "role2_transport_major_projects_manager": {
            "role_id": "role2_transport_major_projects_manager",
            "profiles_assessed": 19, "raw_claims": 300, "evidence_validated": 290,
            "passed_all_gates": 4, "delivered": 0, "exclusions": [],
            "client_side_sidebar": ["Aidan Foley -- Transport Infrastructure Ireland"],
        },
    })

    R.build(allow_placeholder_notice=True)
    html = (out_dir / "dossier.html").read_text(encoding="utf-8")
    csv_text = (out_dir / "candidates.csv").read_text(encoding="utf-8-sig")
    return html, csv_text, out_dir


# ---------------------------------------------------------------------------
# Self-containment -- it must open on a train
# ---------------------------------------------------------------------------


def test_dossier_loads_no_external_assets(rendered):
    """No CDN, no remote stylesheet, no remote script.

    Evidence links point outward by design and are anchors, not assets -- a
    dead evidence link degrades one claim; a dead stylesheet makes the whole
    dossier look broken on the client's first open.
    """
    html, _, _ = rendered
    assert not re.search(r"<script[^>]*\ssrc=", html, re.I)
    assert not re.search(r'<link[^>]+href="https?://', html, re.I)
    assert "cdn." not in html.lower()


def test_dossier_has_a_print_stylesheet(rendered):
    html, _, _ = rendered
    assert "@media print" in html
    assert "page-break-inside" in html or "break-inside" in html


def test_dossier_is_responsive(rendered):
    html, _, _ = rendered
    # Quote style is the renderer's business; the meta tag being there is not.
    assert re.search(r"name=['\"]viewport['\"]", html)
    assert "@media (max-width" in html


# ---------------------------------------------------------------------------
# Honesty -- the properties that make the artifact worth trusting
# ---------------------------------------------------------------------------


def test_every_claim_shows_its_verbatim_quote_and_source(rendered):
    html, _, _ = rendered
    assert "EN 1992-1-1" in html, "the evidence quote itself must be on the page"
    assert "example.ie/p/one" in html, "and the source must be clickable"


def test_email_honesty_label_is_visible(rendered):
    """A pattern guess must read as a guess on the page, not just in the CSV."""
    html, _, _ = rendered
    assert "pattern guess" in html.lower()
    assert "NOT verified" in html


def test_shortfall_is_announced_not_hidden(rendered):
    """Delivering 1 of 10 must say so at the top of the section."""
    html, _, _ = rendered
    assert "Short of target" in html
    assert "1 of 10" in html


def test_client_side_engineers_are_sidebarred_not_counted(rendered):
    html, csv_text, _ = rendered
    assert "Aidan Foley" in html
    assert "not part of the shortlist" in html.lower()
    assert "Aidan Foley" not in csv_text, "sidebar names must never enter the 15"


def test_outreach_withheld_when_the_privacy_notice_is_dead(rendered):
    """Outreach citing a 404 privacy notice is worse than no outreach."""
    html, _, _ = rendered
    assert "Outreach drafts withheld" in html


def test_outreach_ships_once_the_notice_is_live(tmp_path, monkeypatch, rendered):
    """The other half of the gate, which nothing exercised until the notice
    was actually deployed and the suite's verdict quietly changed."""
    _html, _csv, out_dir = rendered
    monkeypatch.setattr(R, "head_ok", lambda url, timeout=20: (True, 200))

    R.build(allow_placeholder_notice=False)
    html = (out_dir / "dossier.html").read_text(encoding="utf-8")

    assert "Outreach drafts withheld" not in html


def test_a_dead_notice_hard_fails_unless_the_override_is_passed(tmp_path,
                                                                monkeypatch,
                                                                rendered):
    """Rendering outreach against a notice that 404s is the one thing this
    gate exists to stop, so the default is a refusal, not a warning."""
    monkeypatch.setattr(R, "head_ok", lambda url, timeout=20: (False, 404))

    with pytest.raises(SystemExit) as exc:
        R.build(allow_placeholder_notice=False)

    assert "REFUSING TO RENDER" in str(exc.value)


def test_unknown_movability_is_stated_as_unknown(rendered):
    html, _, _ = rendered
    assert "UNKNOWN" in html


# ---------------------------------------------------------------------------
# CSV contract
# ---------------------------------------------------------------------------


def test_csv_carries_contact_route_and_evidence_counts(rendered):
    _, csv_text, _ = rendered
    header = csv_text.splitlines()[0]
    for col in ("email", "email_status", "linkedin_url", "tier",
                "primary_signal_claims", "top_evidence_source"):
        assert col in header, "missing CSV column: " + col


def test_pool_maps_are_written_per_role(rendered):
    _, _, out_dir = rendered
    for name in ("pool_map_role1.md", "pool_map_role2.md"):
        text = (out_dir / name).read_text(encoding="utf-8")
        assert "Profiles assessed" in text
        assert "Delivered" in text


def test_bot_blocked_link_is_not_reported_as_broken(rendered):
    """"Could not check" and "did not return 200" are different sentences.

    Collapsing them told the client that eight of eleven candidates had a dead
    source link, when in every case it was their live LinkedIn profile.
    """
    html, _, _ = rendered
    assert "did not return 200" not in html
    assert "could not be checked automatically" in html
    assert "nothing suggests they are broken" in html
