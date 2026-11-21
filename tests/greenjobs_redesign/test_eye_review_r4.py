"""pytest: the round-4 staging eye review minors (qa/EYE_REVIEW_2026-11-21_r4.md).

description: chip "x" + consent checkbox + UK map tap areas >= 44 px (hit area, not glyph); multi-region UK location
  strings go to the staff review queue; the Ham Wall staging text no longer demands a CV; R4-1 confirmation scrolled
  into view; R4-2 breadcrumb on one line with even spacing; R4-3 unique view-transition-name per job; R4-4 IE/UK switch
  visible in the iPhone header. Browser checks: r4_layout.mjs (Chromium, 360/390/412 px).
inputs: none (offline)
outputs: pass/fail
Run: python3 -m pytest -q tests/greenjobs_redesign/test_eye_review_r4.py
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
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
import staging_seed as ss  # noqa: E402

SEED = date(2026, 11, 20)
CSS = (SRC / "css" / "styles.css").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def board():
    out = REPO / ".tmp" / "test_r4_seed"
    ss.prepare("staging", SEED, out, SRC / "data", GAIA_FIXTURE)
    site = REPO / ".tmp" / "test_r4_board"
    shutil.rmtree(site, ignore_errors=True)
    assert (
        bs.build(
            SRC,
            site,
            editions=["ie", "uk"],
            data_dir=out / "data",
            today=SEED,
            board_site="ie",
            site_base="https://greenjobs-stg-ie.pages.dev/",
        )
        == 0
    )
    yield site
    shutil.rmtree(site, ignore_errors=True)


def test_layout_in_chromium(board):
    r = subprocess.run(
        [
            "node",
            str(REPO / "tests" / "greenjobs_redesign" / "r4_layout.mjs"),
            str(board),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
        cwd=REPO,
    )
    fails = [ln for ln in r.stdout.splitlines() if ln.startswith("FAIL")]
    assert r.returncode == 0 and not fails, (
        "\n".join(fails[:20]) or r.stdout[-2000:] + r.stderr[-2000:]
    )
    assert int(re.search(r"r4 layout: (\d+) pass", r.stdout).group(1)) >= 60


def test_css_hit_areas_and_switch():
    assert re.search(r"\.chip button\{width:44px;height:44px", CSS)
    assert re.search(r"\.check input\{[^}]*width:44px;height:44px", CSS)
    assert ".check input::before" in CSS and ".gmap__hit" in CSS
    assert not re.search(
        r"max-width:400px\)\{\.hdr__tools \.edsw\{display:none", CSS
    ), "R4-4"
    assert "view-transition-name:job-title" not in CSS


def test_map_regions_carry_a_tap_disc(board):
    html = (board / "uk" / "index.html").read_text(encoding="utf-8")
    regions = len(re.findall(r'<g class="gmap__r[ "]', html))
    assert regions >= 10 and html.count('class="gmap__hit"') == regions
    assert bs.MAP_HIT_R * 2 * (328 / 600) >= 44  # 360 px phone, 16 px gutters


def test_unique_view_transition_names(board):
    names = []
    for p in sorted((board / "uk" / "jobs").glob("*/index.html"))[:30]:
        m = re.search(
            r'<h1 class="vt-title" style="view-transition-name:([^"]+)"',
            p.read_text(encoding="utf-8"),
        )
        assert m and m.group(1).startswith("jt-")
        names.append(m.group(1))
    assert len(names) == len(set(names)) > 5
    assert bs.vt_name("uk:strat:1 2") == "jt-uk-strat-1-2"


@pytest.mark.parametrize(
    ("raw", "queued"),
    [
        ("Newcastle upon Tyne, Edinburgh", True),
        ("United Kingdom (UK), Ireland (nationwide)", True),
        ("West Yorkshire, Scotland (nationwide)", True),
        ("East Sussex, West Sussex", False),
        ("London Central, West Yorkshire, England", False),
    ],
)
def test_multi_region_locations_queue_for_staff(raw, queued):
    reason = bs.location_review_reason(raw)
    assert bool(reason) is queued
    if queued:
        assert raw.split(",")[0] in reason and len(reason) <= 150


def test_ham_wall_staging_text_matches_the_optional_cv():
    raw = json.loads((SRC / "data" / "uk.json").read_text(encoding="utf-8"))
    ham = next(j for j in raw["jobs"] if str(j["id"]) == "11502133")
    assert "copy of your CV" in ham["description_html"]
    out = ss.strip_external_apply_sentences(ham["description_html"])
    assert "copy of your CV" not in out and "click the apply button" in out
    assert ss.strip_external_apply_sentences(out) == out


def test_confirmation_is_scrolled_into_view():
    js = (SRC / "js" / "api.js").read_text(encoding="utf-8")
    assert (
        "reveal(st)" in js and "scrollIntoView" in js and "prefers-reduced-motion" in js
    )


def test_cross_nation_places_keep_their_display_but_are_queued():
    # moved from the r3 table: shown as written, now also queued (r3 asserted "not queued")
    assert bs.display_location("Newcastle upon Tyne, Edinburgh") == "Newcastle upon Tyne, Edinburgh"
