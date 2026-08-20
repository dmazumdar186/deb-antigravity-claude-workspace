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
    """A pattern guess must read as a guess on the page, not just in the CSV.

    The wording moved when Contact became the reach block at the top of the
    card; the property did not. An inferred address is still labelled as one
    at the point the reader sees the address.
    """
    html, _, _ = rendered
    assert "unverified" in html.lower()
    assert "Inferred address" in html


def test_email_button_does_not_depend_on_a_mail_client(rendered):
    """The button was valid HTML and still did nothing when clicked.

    mailto: is only a route if something is registered to answer it. Windows
    hands the protocol to whatever holds the UserChoice association -- often a
    browser with no web mail handler -- and the navigation is then dropped with
    no error, no console line and no visible change. An iframed preview of this
    file cannot navigate to mailto: at all. In both cases the reader clicks,
    nothing happens, and concludes the dossier is broken.

    So the address the click would have used has to be reachable without the
    protocol: on the element for the handler to copy, and in title= for a
    hover to reveal when scripting is off.
    """
    html, _, _ = rendered
    buttons = re.findall(r'<a class="cta cta-em[^>]*>', html)
    assert buttons, "no email button rendered"
    for b in buttons:
        addr = re.search(r'data-email="([^"]+)"', b)
        assert addr, "email button with no copyable address: " + b
        assert 'href="mailto:' + addr.group(1) + '"' in b, (
            "the copied address must be the one the link would mail: " + b)
        assert 'title="' + addr.group(1) in b, (
            "hover must reveal the address without scripting: " + b)


def test_clipboard_fallback_ships_inside_the_page(rendered):
    """The handler travels with the document or it is not there at all.

    The dossier is mailed around as a single file and read offline, so an
    external script would be a dead reference exactly when it matters. It is
    also why the acceptance gate's "no external assets" check must keep
    passing with this present -- inline, no src.
    """
    html, _, _ = rendered
    assert "<script>" in html
    assert "a.cta-em" in html and "clipboard" in html
    assert not re.search(r'<script[^>]+src=', html), "script must be inline"


def test_every_mailto_on_the_page_is_covered_not_just_the_button(rendered):
    """The card prints the address twice, and both were dead.

    Fixing only the button left the reach-block link -- the same address, one
    line lower -- failing in exactly the way the commit was about. A reader who
    clicks the address rather than the button gets the same silence. The
    handler matches any mailto: anchor, so adding a third one later cannot
    quietly reintroduce the bug.
    """
    html, _, _ = rendered
    assert 'a[href^="mailto:"]' in html, (
        "the handler must match every mailto: link, not only .cta-em")


def test_the_copy_is_announced_to_screen_readers(rendered):
    """A silent textContent swap is confirmation only for people who can see it.

    The button's whole job after this fix is to tell the reader the copy
    happened. Without a live region that confirmation reaches sighted users
    only, which makes the fix itself inaccessible.
    """
    html, _, _ = rendered
    for b in re.findall(r'<a class="cta cta-em[^>]*>', html):
        assert 'aria-live="polite"' in b, "copy state not announced: " + b


class _Spec:
    primary_signal_dimension = "technical_skill"


def _dc(dimension, assertion, quote):
    return {"dimension": dimension, "assertion": assertion,
            "evidence_quote": quote, "confidence": "direct",
            "source_url": "https://example.ie/p", "source_doc_id": "d"}


def test_the_detail_pane_does_not_quote_one_sentence_twice():
    """The repetition bug, re-fixed on the path that actually ships.

    _claims_html grouped claims that rest on one source sentence, and the
    table layout stopped calling it -- so a sentence evidencing three
    dimensions printed three times again, spending a three-quote budget on one
    piece of evidence. Patrick Raggett shipped that way. The grouping now lives
    in _group_by_quote and both renderers use it; this asserts on the pane
    rather than on the helper, because the helper was never the thing that
    broke.
    """
    quote = "Patrick is a Chartered Engineer with over 15 years of experience"
    claims = [
        _dc("years_experience", "Over 15 years.", quote),
        _dc("chartership", "Chartered.", quote + "."),
        _dc("technical_skill", "Bridges.", "designed the Royal Canal Greenway"),
    ]
    pane = R._detail_cell({"person_id": "p1"}, claims, {"tier": "B"},
                          {"email_status": "verified"}, {}, {}, _Spec())
    assert pane.count("<blockquote>") == 2, pane


def test_the_detail_pane_shows_the_longest_quote_of_a_group():
    """The longest carries the most context for a reader who clicks through."""
    claims = [
        _dc("sector", "B.", "commercial offices and schools"),
        _dc("project", "A.", "including commercial offices and schools"),
    ]
    pane = R._detail_cell({"person_id": "p1"}, claims, {"tier": "B"},
                          {"email_status": "verified"}, {}, {}, _Spec())
    assert "including commercial offices and schools" in pane


def test_mailto_navigation_is_not_suppressed(rendered):
    """Copying is the fallback, not a replacement.

    Where a mail client does exist, clicking should still open it. The handler
    must not call preventDefault, or the fix would break the readers for whom
    the button already worked.
    """
    html, _, _ = rendered
    assert "preventDefault" not in html


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
    """Movability is now one line rather than a section, but an unknown still
    has to say unknown rather than quietly disappear."""
    html, _, _ = rendered
    assert "mov-unknown" in html
    assert "unknown movability" in html.lower()


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

    The explanatory sentence that used to accompany this -- "N links could not
    be checked, nothing suggests they are broken" -- went with the distill
    pass. On a card the reader scans to decide who to call, a paragraph
    reassuring them about a non-problem is exactly the weight that was
    crowding out the evidence, and saying nothing is the correct report for
    "no problem found". The load-bearing half is that an unverifiable link is
    never called dead.
    """
    html, _, _ = rendered
    assert "did not return 200" not in html
    assert "broken" not in html.lower()


def test_a_genuinely_dead_link_is_still_reported(tmp_path, monkeypatch):
    """Silence means "nothing found", so a real 404 has to break it."""
    block = R._reach_block(
        {"full_name": "Sean O'Brien", "current_employer": "Example Engineers"},
        {"email_status": "none"},
        {"checks": [{"url": "https://example.ie/gone", "alive": False,
                     "http_status": 404}]},
    )

    assert "did not return 200" in block


# ---------------------------------------------------------------------------
# One source sentence, one quote on the card
# ---------------------------------------------------------------------------


def _c(dimension, assertion, quote, doc="d1"):
    return {"dimension": dimension, "assertion": assertion,
            "evidence_quote": quote, "source_url": "https://ocsc.ie/people/",
            "source_doc_id": doc}


QUOTE = ("Eddie has over 25 years of experience in structural and civil "
         "engineering in Ireland on private and public developments")


def test_one_sentence_evidencing_two_dimensions_is_quoted_once():
    """A single sentence is legitimately experience, sector and location at
    once. Emitting one bullet per dimension printed it three times under three
    labels, and a card that repeats itself reads as padding however true each
    line is."""
    html = R._claims_html([
        _c("years_experience", "Over 25 years of experience.", QUOTE),
        _c("sector", "Structural and civil engineering in Ireland.", QUOTE + "."),
    ])

    assert html.count("<blockquote>") == 1
    assert "Over 25 years of experience." in html
    assert "Structural and civil engineering in Ireland." in html


def test_a_trailing_full_stop_does_not_defeat_the_grouping():
    """The exact-match key failed on precisely this: the same sentence quoted
    once with its full stop and once without."""
    html = R._claims_html([
        _c("sector", "A.", "the same sentence"),
        _c("project", "B.", "the same sentence."),
    ])

    assert html.count("<blockquote>") == 1


def test_a_leading_word_does_not_defeat_the_grouping():
    html = R._claims_html([
        _c("sector", "A.", "including commercial offices and schools"),
        _c("project", "B.", "commercial offices and schools"),
    ])

    assert html.count("<blockquote>") == 1


def test_the_longest_quote_is_the_one_shown():
    """It carries the most context for a reader who clicks through to check."""
    html = R._claims_html([
        _c("project", "B.", "commercial offices and schools"),
        _c("sector", "A.", "including commercial offices and schools"),
    ])

    assert "including commercial offices and schools" in html


def test_genuinely_different_evidence_stays_separate():
    html = R._claims_html([
        _c("chartership", "Chartered.", "BE, CEng MIStructE, MIEI, RConsEI"),
        _c("years_experience", "25 years.", QUOTE),
    ])

    assert html.count("<blockquote>") == 2


def test_every_group_still_carries_a_source_link():
    html = R._claims_html([
        _c("years_experience", "A.", QUOTE),
        _c("sector", "B.", QUOTE + "."),
        _c("chartership", "C.", "BE, CEng MIStructE"),
    ])

    assert html.count('class="src"') == html.count("<blockquote>") == 2


def test_claims_keep_the_order_they_arrived_in():
    """Grouping sorts internally by quote length; the card must not."""
    html = R._claims_html([
        _c("chartership", "FIRST.", "BE, CEng MIStructE, MIEI, RConsEI"),
        _c("years_experience", "SECOND.", QUOTE),
    ])

    assert html.index("FIRST.") < html.index("SECOND.")


def test_an_ocr_group_still_declares_its_provenance(monkeypatch):
    monkeypatch.setattr(R, "_OCR_DOC_IDS", {"scan"})

    html = R._claims_html([
        _c("years_experience", "A.", QUOTE, doc="scan"),
        _c("sector", "B.", QUOTE + ".", doc="scan"),
    ])

    assert html.count("recovered by OCR") == 1


# ---------------------------------------------------------------------------
# Every candidate is reachable
# ---------------------------------------------------------------------------


def _p(name="Philip Penco", employer="Barrett Mahony Consulting Engineers", **kw):
    return {"full_name": name, "current_employer": employer, **kw}


def test_a_candidate_with_no_email_and_no_linkedin_is_still_reachable():
    """Six of thirteen delivered cards were a dead end: five had a
    pattern-guessed address the card itself said not to use for a first touch
    and no LinkedIn URL, one had nothing at all. A shortlist entry nobody can
    contact is not a shortlist entry."""
    routes = R._reach_routes(_p(), {"email_status": "none", "email": None})

    assert routes, "a candidate must never render with zero routes"
    kinds = [k for k, _, _ in routes]
    assert "search" in kinds
    assert "switchboard" in kinds


def test_a_missing_linkedin_url_becomes_a_search_not_a_shrug():
    """The provider returning no profile URL is not the same as there being no
    profile."""
    routes = R._reach_routes(_p(), {"email_status": "none"})
    label, href = next((l, h) for k, l, h in routes if k == "search")

    assert "linkedin.com/search" in href
    assert "Philip+Penco" in href
    assert "Barrett+Mahony" in href


def test_an_unknown_firm_still_yields_a_way_to_find_it():
    """Cronin & Sutton is a real Dublin consultancy that simply was not in the
    Role 1 sourcing list, so no domain was ever fetched for it."""
    routes = R._reach_routes(
        _p("Pearse Sutton", "Cronin & Sutton Consulting"), {"email_status": "none"})

    assert len(routes) >= 2
    assert any(k == "switchboard" for k, _, _ in routes)


def test_a_verified_email_outranks_a_search_but_not_linkedin():
    """I8: LinkedIn first. Approaching a senior engineer at their employer's
    mailbox about leaving that employer is monitored mail."""
    both = R._reach_routes(_p(), {
        "email_status": "verified", "email": "a@b.com",
        "linkedin_url": "https://linkedin.com/in/x"})
    assert [k for k, _, _ in both][:2] == ["linkedin", "email"]

    no_li = R._reach_routes(_p(), {"email_status": "verified", "email": "a@b.com"})
    assert [k for k, _, _ in no_li][0] == "email"


def test_a_pattern_guess_never_leads(monkeypatch):
    """It is a guess. It ranks below finding the person properly."""
    routes = R._reach_routes(_p(), {
        "email_status": "pattern_guess", "email": "philip.penco@barrettmahony.com"})

    assert routes[0][0] != "guess"
    assert any(k == "guess" for k, _, _ in routes)
    guess_label = next(l for k, l, _ in routes if k == "guess")
    assert "unverified" in guess_label.lower()


def test_the_two_roles_render_as_two_sections(rendered):
    """Run together they read as one list, which understates the delivery."""
    html, _, _ = rendered

    assert html.count('class="role-band"') == 2
    assert "Senior Structural Engineer" in html
    assert "Transport Major Projects Manager" in html


def test_the_removed_sections_are_gone(rendered):
    html, _, _ = rendered

    assert "Not verified / open questions" not in html
    assert "every quote verified against its source" not in html


def test_the_evidence_itself_survived_the_cut(rendered):
    """Distilling the card must not touch the thing the card is for."""
    html, _, _ = rendered

    assert "<blockquote>" in html
    assert "EN 1992-1-1" in html
    assert 'class="src"' in html
