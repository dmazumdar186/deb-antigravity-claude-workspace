"""pytest: the round-2 staging eye review fixes (qa/EYE_REVIEW_2026-11-20_r2.md), Python and browser side.

description: N1 the static apply form posts to the edition's API base (staging: the Worker origin + ?site=), the CSP
  allows exactly that form target, the Worker's ALLOWED_ORIGINS per wrangler env equals the environment's board
  origins (check-config fails a widened or narrowed list) and staging routes applications to a reserved inbox under
  pinned DRY_RUN; N2/N3/N5/N7/m2 measured in Chromium on a seeded staging board build (phone_layout.mjs, 360-430 px);
  N4 "Apply now"; N6 no /for-keith/ and no link to it on a board build; N8 the staging seed strips dated sentences
  from test-data adverts; N9 link-apply source line and no headline zero; m1 no demo wording on a board build;
  m3 display locations; m4 the mid-sentence paragraph break.
inputs: none (offline; node + Playwright Chromium for the layout test)
outputs: pass/fail
Run: python3 -m pytest -q tests/greenjobs_redesign/test_eye_review_r2.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
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
sys.path.insert(0, str(CODE / "deploy"))
import build_site as bs  # noqa: E402
import release  # noqa: E402
import staging_seed as ss  # noqa: E402

SEED = date(2026, 11, 20)
CFG = json.loads((CODE / "deploy" / "environments.json").read_text(encoding="utf-8"))
WORKER_IE = CFG["envs"]["staging"]["api_base"]["ie"]


@pytest.fixture(scope="module")
def board():
    """A staging board build of the seeded data, as release.py builds it: --board-site uk, --api-base <IE Worker>."""
    seed = REPO / ".tmp" / "test_r2_seed"
    ss.prepare("staging", SEED, seed, SRC / "data", GAIA_FIXTURE)
    site = REPO / ".tmp" / "test_r2_board"
    shutil.rmtree(site, ignore_errors=True)
    old = bs.API_BASE
    bs.API_BASE = WORKER_IE
    try:
        assert (
            bs.build(
                SRC,
                site,
                editions=["ie", "uk"],
                data_dir=seed / "data",
                today=SEED,
                board_site="uk",
            )
            == 0
        )
    finally:
        bs.API_BASE = old
    yield site
    if not os.environ.get("GJ_KEEP_R2_BOARD"):  # set it to inspect the tree after a failure
        shutil.rmtree(site, ignore_errors=True)


def job_pages(site: Path, ed: str, needle: str) -> list[str]:
    return [
        p.read_text(encoding="utf-8")
        for p in sorted((site / ed / "jobs").glob("*/index.html"))
        if needle in p.read_text(encoding="utf-8")
    ]


# ── N1: the form posts where the API is ─────────────────────────────────────────


def test_n1_static_form_posts_to_the_worker_origin_with_site(board):
    for ed in ("ie", "uk"):
        pages = job_pages(board, ed, "data-apply-form")
        assert pages, ed
        assert all(f'action="{WORKER_IE}/api/apply?site={ed}"' in h for h in pages), ed
        assert not any(
            'action="/api/apply"' in h for h in pages
        ), "a relative action posts to Pages (405)"
    headers = (board / "_headers").read_text(encoding="utf-8")
    assert f"form-action 'self' {WORKER_IE};" in headers
    assert f"connect-src 'self' {WORKER_IE};" in headers


def test_n1_production_form_stays_same_origin():
    old = bs.API_BASE
    bs.API_BASE = ""
    try:
        assert bs.apply_action("uk") == "/api/apply"
        assert (
            'action="/api/apply"'
            in bs.apply_ctx(
                {"id": "x", "apply_mode": "email"}, "greenjobs.co.uk", "uk"
            )["apply_form"]
        )
    finally:
        bs.API_BASE = old


def test_n1_allowed_origins_are_exactly_each_environments_board_origins(tmp_path):
    toml = (REPO / CFG["worker_dir"] / "wrangler.toml").read_text(encoding="utf-8")
    data = tomllib.loads(toml)
    for env, wenvs in (
        ("staging", ("staging", "staging-uk")),
        ("production", ("production",)),
    ):
        want = release.board_origins(CFG["envs"][env])
        for w in wenvs:
            got = {
                o.strip() for o in data["env"][w]["vars"]["ALLOWED_ORIGINS"].split(",")
            }
            assert got == want, (w, got, want)
        assert release.check_wrangler_toml(CFG, env) == []
    assert release.board_origins(CFG["envs"]["staging"]) == {
        "https://greenjobs-stg-ie.pages.dev",
        "https://greenjobs-stg-uk.pages.dev",
    }
    assert release.board_origins(CFG["envs"]["production"]) == {
        "https://greenjobs.ie",
        "https://www.greenjobs.ie",
        "https://greenjobs.co.uk",
        "https://www.greenjobs.co.uk",
    }
    # the gate fires: a staging Worker that also allows a production origin, or misses its own board, is refused
    wider = toml.replace(
        'ALLOWED_ORIGINS = "https://greenjobs-stg-ie.pages.dev,https://greenjobs-stg-uk.pages.dev"',
        'ALLOWED_ORIGINS = "https://greenjobs-stg-ie.pages.dev,https://greenjobs-stg-uk.pages.dev,https://greenjobs.ie"',
        1,
    )
    assert wider != toml
    (tmp_path / "w.toml").write_text(wider, encoding="utf-8")
    assert any(
        "ALLOWED_ORIGINS" in p
        for p in release.check_wrangler_toml(CFG, "staging", tmp_path / "w.toml")
    )
    narrow = toml.replace(
        'ALLOWED_ORIGINS = "https://greenjobs-stg-ie.pages.dev,https://greenjobs-stg-uk.pages.dev"\n\n[env.staging-uk.version_metadata]',
        'ALLOWED_ORIGINS = "https://greenjobs-stg-ie.pages.dev"\n\n[env.staging-uk.version_metadata]',
        1,
    )
    assert narrow != toml
    (tmp_path / "n.toml").write_text(narrow, encoding="utf-8")
    assert any(
        "env.staging-uk.vars.ALLOWED_ORIGINS" in p
        for p in release.check_wrangler_toml(CFG, "staging", tmp_path / "n.toml")
    )


def test_n1_staging_routes_applications_to_a_reserved_inbox_and_never_sends():
    data = tomllib.loads(
        (REPO / CFG["worker_dir"] / "wrangler.toml").read_text(encoding="utf-8")
    )
    for w in ("staging", "staging-uk"):
        v = data["env"][w]["vars"]
        assert (
            v["DRY_RUN"] == "1"
            and v["MAIL_PROVIDER"] == "none"
            and v["LIVE_CONFIRM"] == ""
        )
        for k in ("APPLY_INBOX_IE", "APPLY_INBOX_UK"):
            assert re.fullmatch(r"[a-z0-9-]+@example\.com", v[k]), (
                w,
                k,
            )  # RFC 2606: never a real mailbox
    assert (
        data["env"]["production"]["vars"]["APPLY_INBOX_IE"] == ""
    )  # production untouched


# ── N2-N7, m1, m2 in a real browser ───────────────────────────────────────────


def test_phone_layout_in_chromium(board):
    r = subprocess.run(
        [
            "node",
            str(REPO / "tests" / "greenjobs_redesign" / "phone_layout.mjs"),
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
    assert re.search(r"phone layout: (\d+) pass, 0 fail", r.stdout)
    assert int(re.search(r"phone layout: (\d+) pass", r.stdout).group(1)) >= 150  # floor: every page x width x check ran


def test_n2_form_markup_binds_every_label(board):
    h = job_pages(board, "ie", "data-apply-form")[0]
    form = re.search(r'<form class="job__apply-form".*?</form>', h, re.S).group(0)
    for fid in ("ap-name", "ap-email", "ap-phone", "ap-cover", "ap-cv", "ap-consent"):
        assert f'for="{fid}"' in form and f'id="{fid}"' in form, fid
        assert (
            f'aria-describedby="{fid}-err"' in form and f'id="{fid}-err"' in form
        ), fid
    assert form.count('class="in') == 5


# ── N4, N6, N9, m1 ────────────────────────────────────────────────────────────


def test_n4_email_apply_button_says_apply_now(board):
    for ed in ("ie", "uk"):
        for h in job_pages(board, ed, "data-apply-form"):
            assert ">Apply now<span" in h
            assert not re.search(r">Apply on greenjobs\.(ie|co\.uk)<", h)


def test_n6_no_for_keith_on_a_board_build(board):
    assert (
        not (board / "ie" / "for-keith").exists()
        and not (board / "uk" / "for-keith").exists()
    )
    hits = [
        str(p.relative_to(board))
        for p in board.rglob("*.html")
        if "for-keith" in p.read_text(encoding="utf-8")
    ]
    assert hits == []
    dash = (board / "ie" / "dashboard" / "index.html").read_text(encoding="utf-8")
    assert "Back to the evidence page" not in dash


def test_m1_no_demo_wording_on_a_board_build(board):
    hits = [
        str(p.relative_to(board))
        for p in board.rglob("*.html")
        if "Demo redesign" in p.read_text(encoding="utf-8")
    ]
    assert hits == []


def test_m1_n6_the_demo_build_keeps_its_note_and_evidence_page():
    old = bs.BOARD_BUILD
    try:
        bs.BOARD_BUILD = False
        assert "Demo redesign" in bs.demo_note()
        bs.BOARD_BUILD = True
        assert bs.demo_note() == ""
    finally:
        bs.BOARD_BUILD = old


def test_n9_link_apply_source_line_and_no_headline_zero(board):
    links = job_pages(board, "ie", 'data-ev="apply_click"')
    assert links, "the seeded IE board has link-apply (Gaia) roles"
    for h in links:
        host = re.search(r'<a class="btn btn--lime" href="https://([^/"]+)', h).group(1)
        assert f"Description as published on {host}; reference" in h
        assert "published by the employer on greenjobs.ie" not in h
    for ed in ("ie", "uk"):
        for p in (board / ed / "jobs").glob("*/index.html"):
            assert '<b class="num">0</b> similar' not in p.read_text(
                encoding="utf-8"
            ), p


# ── N8: test-data adverts quote no dates ──────────────────────────────────────


def test_n8_seed_strips_dated_sentences_from_test_data_only():
    ham = (
        "<p>This is a Permanent Full-Time role for 37.5 hours per week.</p><p><strong>Closing date: 23:59, Monday, 19th October 2026 <br> </strong>"
        "This employer is looking to conduct interviews as soon as applications present, so please do not delay.</p>"
    )
    out = ss.strip_date_sentences(ham)
    assert (
        "October" not in out
        and "37.5 hours per week" in out
        and "please do not delay" in out
    )
    long = (
        "<p>"
        + "We restore peatland across the uplands with partners. " * 4
        + "Please apply before 5 October 2026 and answer a few questions. Interviews follow.</p>"
    )
    out = ss.strip_date_sentences(long)
    assert (
        "October" not in out
        and "Interviews follow." in out
        and out.count("We restore peatland") == 4
    )
    assert ss.strip_date_sentences(out) == out  # idempotent
    for d in (
        "19/10/2026",
        "September 24, 2026",
        "December 2026",
        "4th October",
        "1 December 2026",
    ):
        assert ss.DATE_IN_TEXT.search(d), d
    for not_a_date in ("37.5 hours", "Band 5", "Ref 481110", "May we", "Sept"):
        assert (
            not ss.DATE_IN_TEXT.search(not_a_date) or not_a_date == "Sept"
        ), not_a_date


def test_n8_seeded_boards_quote_no_dates_in_test_data(board):
    for ed in ("ie", "uk"):
        data = json.loads(
            (REPO / ".tmp" / "test_r2_seed" / "data" / f"{ed}.json").read_text(
                encoding="utf-8"
            )
        )
        for j in data["jobs"]:
            if j.get("seed_source") != "test":
                continue  # Gaia feed roles keep their real text and real dates
            text = (
                re.sub(r"<[^>]+>", " ", j.get("description_html") or "")
                + " "
                + (j.get("summary") or "")
            )
            assert not ss.DATE_IN_TEXT.search(text), (
                ed,
                j["id"],
                ss.DATE_IN_TEXT.search(text).group(0),
            )


# ── m3, m4 ────────────────────────────────────────────────────────────────────


def test_m3_display_locations_on_the_board(board):
    uk = "".join(
        p.read_text(encoding="utf-8")
        for p in (board / "uk" / "jobs").glob("*/index.html")
    )
    for odd in (
        "West Yorkshire, Scotland (nationwide)",
        "London Central, West Yorkshire, England",
        "Dublin, United Kingdom (UK)",
        "Monagahan",
    ):
        assert odd not in uk, odd


def test_m4_mid_sentence_break_is_joined_in_the_sanitiser():
    raw = json.loads((SRC / "data" / "ie.json").read_text(encoding="utf-8"))
    arb = next(j for j in raw["jobs"] if str(j["id"]) == "11498685")
    html = bs.sanitise_html(arb["description_html"], arb["url"])
    assert "arboricultural and ecological advice to clients across Ireland." in html
    assert not re.search(r"arboricultural and\s*</p>", html)
