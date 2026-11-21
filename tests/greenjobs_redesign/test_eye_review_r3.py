"""pytest: the round-3 staging eye review fixes (qa/EYE_REVIEW_2026-11-21_r3.md), Python side.

description: R3-6 the IE/UK switch goes to the other edition's own board origin (--edition-origin, staging -> staging)
  and each edition's canonical is its own board; m3 UK locations: a nation-wide tick is checked against the places'
  nation (regions_uk.json) on the real odd source values, shown "anywhere in Scotland", and the importer queues the job
  for staff with the quote; R3-7 an email-apply advert that sends applicants to an external form is queued for staff
  (mode unchanged) and the staging seed's Ham Wall test advert no longer contradicts the on-page form.
  Worker side: tests/greenjobs_redesign/platform/eye_review_r3.test.mjs; layout (m2, R3-4, R3-5): phone_layout.mjs
  via test_eye_review_r2.py::test_phone_layout_in_chromium; R3-3: src/js/api.test.js; Gaia fallback + edition origins
  in release.py: smoke/test_release.py::test_r3_*.
inputs: none (offline)
outputs: pass/fail
Run: python3 -m pytest -q tests/greenjobs_redesign/test_eye_review_r3.py
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CODE = REPO / "execution" / "gtm_client_workflows" / "greenjobs_redesign"
SRC = REPO / "deliverables" / "greenjobs_redesign_2026-09-22" / "src"
GAIA_FIXTURE = (
    REPO / "tests" / "greenjobs_redesign" / "fixtures" / "gaia_d1" / "feed_small.json"
)
sys.path.insert(0, str(CODE))
import build_site as bs  # noqa: E402
import job_classifier as jc  # noqa: E402
import staging_seed as ss  # noqa: E402
import strategies_import as si  # noqa: E402

SEED = date(2026, 11, 20)
BOARD = {
    "ie": "https://greenjobs-stg-ie.pages.dev/",
    "uk": "https://greenjobs-stg-uk.pages.dev/",
}
HAM_WALL = "11502133"
RAW_UK = json.loads((SRC / "data" / "uk.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def seeded():
    out = REPO / ".tmp" / "test_r3_seed"
    ss.prepare("staging", SEED, out, SRC / "data", GAIA_FIXTURE)
    return out


@pytest.fixture(scope="module")
def board(seeded):
    """The IE staging board as release.py builds it: --board-site ie, --edition-origin for both editions."""
    site = REPO / ".tmp" / "test_r3_board"
    shutil.rmtree(site, ignore_errors=True)
    old = dict(bs.EDITION_ORIGINS)
    bs.EDITION_ORIGINS.clear()
    bs.EDITION_ORIGINS.update(BOARD)
    try:
        assert (
            bs.build(
                SRC,
                site,
                editions=["ie", "uk"],
                data_dir=seeded / "data",
                today=SEED,
                board_site="ie",
                site_base=BOARD["ie"],
            )
            == 0
        )
    finally:
        bs.EDITION_ORIGINS.clear()
        bs.EDITION_ORIGINS.update(old)
    yield site
    shutil.rmtree(site, ignore_errors=True)


# ── R3-6 ──────────────────────────────────────────────────────────────────────


def _switch(html: str, ed: str) -> str:
    return re.search(rf'<a href="([^"]+)" data-edswitch="{ed}"', html).group(1)


def test_r3_6_edition_switch_goes_to_the_other_editions_board_host(board):
    ie_home = (board / "ie" / "index.html").read_text(encoding="utf-8")
    assert _switch(ie_home, "uk") == "https://greenjobs-stg-uk.pages.dev/uk/index.html"
    assert not _switch(ie_home, "ie").startswith(
        "http"
    ), "the current edition stays relative"
    ie_jobs = (board / "ie" / "jobs" / "index.html").read_text(encoding="utf-8")
    assert _switch(ie_jobs, "uk").startswith("https://greenjobs-stg-uk.pages.dev/uk/")
    uk_home = (board / "uk" / "index.html").read_text(
        encoding="utf-8"
    )  # the UK copy on the IE host
    assert _switch(uk_home, "ie") == "https://greenjobs-stg-ie.pages.dev/ie/index.html"
    assert (
        '<link rel="canonical" href="https://greenjobs-stg-uk.pages.dev/uk/index.html">'
        in uk_home
    )
    assert (
        '<link rel="canonical" href="https://greenjobs-stg-ie.pages.dev/ie/index.html">'
        in ie_home
    )
    assert (
        'hreflang="en-GB" href="https://greenjobs-stg-uk.pages.dev/uk/index.html"'
        in ie_home
    )


def test_r3_6_without_edition_origins_the_switch_stays_relative():
    data = {
        "ed": "ie",
        "site": "greenjobs.ie",
        "network_sites": [],
        "contact": {},
        "jobs": [],
        "today": "2026-11-20",
        "fetched": "2026-11-20",
    }
    assert bs.EDITION_ORIGINS == {}
    ctx = bs.shell_ctx(data, 1, "jobs", "t", "d", same_path="jobs/index.html")
    assert 'href="../uk/jobs/index.html" data-edswitch="uk"' in ctx["edsw"]


def test_r3_6_cli_rejects_a_bad_edition_origin(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_site.py",
            "--edition-origin",
            "ie=http://insecure.example",
            "--out",
            str(REPO / ".tmp" / "x"),
        ],
    )
    with pytest.raises(SystemExit):
        bs.main()
    assert "--edition-origin" in capsys.readouterr().err


# ── m3: UK locations against the nation table ─────────────────────────────────

ODD = [  # the actual multi-region strings in the September UK source feed (src/data/uk.json)
    (
        "West Yorkshire, Scotland (nationwide)",
        "West Yorkshire, anywhere in Scotland",
        True,
    ),
    (
        "Manchester, England, Scotland (nationwide)",
        "Manchester, anywhere in Scotland",
        True,
    ),
    (
        "London Central, West Yorkshire, England",
        "Central London, West Yorkshire",
        False,
    ),
    ("Newcastle upon Tyne, Edinburgh", "Newcastle upon Tyne, Edinburgh", False),
    ("Merseyside, England", "Merseyside", False),
    (
        "Cambridgeshire, Hertfordshire, Cambridge",
        "Cambridgeshire, Hertfordshire, Cambridge",
        False,
    ),
]


def test_m3_the_odd_values_are_real_source_values():
    locs = {j.get("location") for j in RAW_UK["jobs"]}
    for raw, _, _ in ODD:
        assert raw in locs, raw


@pytest.mark.parametrize(("raw", "shown", "queued"), ODD)
def test_m3_location_validated_against_the_region_table(raw, shown, queued):
    assert bs.display_location(raw) == shown
    assert bs.display_location(shown) == shown, "idempotent"
    reason = bs.location_review_reason(raw)
    assert bool(reason) is queued
    if queued:
        assert (
            f'"{raw}"' in reason and "(England)" in reason and "Scotland-wide" in reason
        )


def test_m3_nation_table_comes_from_regions_uk():
    assert bs.place_nation("West Yorkshire") == "england"
    assert bs.place_nation("Edinburgh") == "scotland"
    assert bs.place_nation("Cardiff") == "wales"
    assert bs.place_nation("Belfast") == "northern ireland"
    assert bs.place_nation("Cork") is None


def test_m3_board_never_says_west_yorkshire_scotland(board):
    uk = "".join(
        p.read_text(encoding="utf-8")
        for p in (board / "uk" / "jobs").glob("*/index.html")
    )
    assert "West Yorkshire, Scotland" not in uk
    assert "West Yorkshire, anywhere in Scotland" in uk


# ── R3-7: apply route in the advert vs the job's apply mode ───────────────────


def _uk(jid: str) -> dict:
    return next(j for j in RAW_UK["jobs"] if str(j["id"]) == jid)


def test_r3_7_ham_wall_text_is_flagged_when_the_job_applies_by_email():
    desc = _uk(HAM_WALL)["description_html"]
    r = jc.apply_route_review_reason(desc, "email")
    assert r and "You will be taken to a simple CHM Recruit form" in r
    assert (
        jc.apply_route_review_reason(desc, "link") is None
    ), "a link-mode job already sends applicants off-site"


def test_r3_7_click_apply_alone_is_not_flagged():
    # Mattinson's "or click apply" means the on-page button: never a review item
    assert (
        jc.apply_route_review_reason(
            "<p>Reach out to Ethan on 020 7960 2589 or click apply to find out more.</p>",
            "email",
        )
        is None
    )
    assert (
        jc.apply_route_review_reason(
            "<p>Design your workday to suit your life.</p>", "email"
        )
        is None
    )
    for txt in (
        "For full details and to apply for this post, please visit our website.",
        "Please apply via the link and be assured that all applications are confidential.",
        "You will be redirected to our careers portal.",
    ):
        assert jc.apply_route_review_reason(f"<p>{txt}</p>", "email"), txt


def _class_sql(site: str, r: dict) -> list[str]:
    si._CLASSIFIER["jc"] = jc
    c = jc.classify(
        {
            "title": r["title"],
            "employer": "CHM Recruit",
            "location": r["location"],
            "description_html": r["description"],
        },
        site,
        jc.canonical_taxonomy(),
        require_frozen=False,
    )
    t3 = si.load_named(si.DEFAULT_UPSERTS_0003)
    return si.class_sql(site, {**r, "_class": c}, t3, "2026-11-21T00:00:00Z")


def test_r3_7_and_m3_the_import_queues_the_job_for_staff_with_the_quote_and_keeps_it_live():
    ham = _uk(HAM_WALL)
    sql = "\n".join(
        _class_sql(
            "uk",
            {
                "id": f"uk:strat:{HAM_WALL}",
                "title": ham["title"],
                "description": ham["description_html"],
                "location": "West Yorkshire, Scotland (nationwide)",
                "apply_mode": "email",
            },
        )
    )
    review = next(s for s in sql.splitlines() if s.startswith("INSERT INTO job_review"))
    assert "You will be taken to a simple CHM Recruit form" in review
    assert "West Yorkshire (England) listed with Scotland-wide" in review
    assert re.search(
        r",\s*0,\s*'queued',\s*'2026-11-21T00:00:00Z'", review
    ), "hold 0: the job stays live"
    assert (
        "apply_mode" not in review and "UPDATE jobs" not in sql
    ), "the apply mode is never changed"
    clean = "\n".join(
        _class_sql(
            "uk",
            {
                "id": "uk:strat:1",
                "title": "Senior Ecologist",
                "description": "<p>Lead bat and badger surveys across Cumbria. Click apply.</p>",
                "location": "Cumbria",
                "apply_mode": "email",
            },
        )
    )
    assert "INSERT INTO job_review" not in clean


def test_r3_7_staging_seed_ham_wall_no_longer_contradicts_the_form(seeded):
    data = json.loads((seeded / "data" / "uk.json").read_text(encoding="utf-8"))
    ham = next(j for j in data["jobs"] if str(j["id"]) == HAM_WALL)
    assert "taken to a simple CHM Recruit form" not in ham["description_html"]
    assert "redirected to complete your application" not in ham["description_html"]
    assert (
        "click the apply button" in ham["description_html"]
    ), "the rest of the advert stays"
    sql = (seeded / "seed.sql").read_text(encoding="utf-8")
    row = next(
        s
        for s in sql.splitlines()
        if s.startswith("INSERT INTO jobs") and f"'uk:strat:{HAM_WALL}'" in s
    )
    assert "'email'" in row and "CHM Recruit form" not in row
    assert (
        ss.strip_external_apply_sentences(ham["description_html"])
        == ham["description_html"]
    ), "idempotent"
