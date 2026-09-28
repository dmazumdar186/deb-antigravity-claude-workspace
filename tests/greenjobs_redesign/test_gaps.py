"""Branch tests for build_site.py and validate_site.py that the main suite
does not reach.

description: Every uncovered, network-free branch found by the 2026-09-28
  coverage pass: helper edge cases (dates, currency, images, sanitiser, region
  tables, hero footage present / absent / poster-only, brief facts), the
  build()'s failure exits (missing src, refused --out, missing or empty
  dataset, node missing or failing, validation failure, rebuild into a marked
  dir, no site_base), the CLI main() with --today, and one synthetic site
  that trips every validator failure message so each string is asserted.
  Dead-since-the-film-removal geometry helpers are exercised directly and
  listed in tests/greenjobs_redesign/COVERAGE.md.
inputs: none (reads the checked-in src/ tree read-only)
outputs: stdout PASS/FAIL lines; exit code 0 (all pass) / 1 (failures)

Run: python3 tests/greenjobs_redesign/test_gaps.py
     (also executed by tests/greenjobs_redesign/test_build.py and run_all.py)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
# GJ_SCRIPT_DIR points the suite at a copy of the scripts (mutation testing).
# The copy must sit three directories below the repo root, e.g. .tmp/mut/esc/,
# because build_site locates the repo via Path(__file__).parents[3].
SCRIPT_DIR = Path(os.environ.get("GJ_SCRIPT_DIR") or REPO / "execution" / "gtm_client_workflows" / "greenjobs_redesign")
SRC = REPO / "deliverables" / "greenjobs_redesign_2026-09-22" / "src"
FIXTURE = SRC / "data" / "_fixture.json"

sys.path.insert(0, str(SCRIPT_DIR))
import build_site  # noqa: E402
import validate_site  # noqa: E402

RESULTS: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> None:
    RESULTS.append((ok, label))
    print(("PASS  " if ok else "FAIL  ") + label)


def _has(fails: list[str], needle: str) -> bool:
    return any(needle in f for f in fails)


# ------------------------------------------------------------- build_site helpers

def test_helper_edges(tmp_root: Path):
    check(build_site.parse_date("September 2026") == "" and build_site.parse_date("12-2026") == "", "parse_date: unrecognised text -> ''")
    check(build_site.sanitise_html("<marquee>x</marquee><p>y</p>", "https://x/") == "x <p>y</p>", "sanitise_html: a tag outside the allow-list is dropped, its text kept")
    check(build_site.sanitise_html('<a href="javascript:alert(1)">z</a>', "https://x/") == "<a>z</a>", "sanitise_html: javascript: href is stripped")
    jpg = tmp_root / "a.jpg"
    sof = b"\xff\xc0" + struct.pack(">H", 17) + b"\x08" + struct.pack(">HH", 120, 300) + b"\x03" + b"\x00" * 9
    jpg.write_bytes(b"\xff\xd8" + b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + b"\x00" * 9 + b"\x00" + b"\xff\xd0" + sof)
    check(build_site.image_size(jpg) == (300, 120), "image_size: JPEG SOF0 after an APP0 segment, a stray byte and an RST marker")
    bad_jpg = tmp_root / "b.jpg"
    bad_jpg.write_bytes(b"\xff\xd8\xff\xe0" + struct.pack(">H", 4) + b"\x00\x00")
    check(build_site.image_size(bad_jpg) == (200, 80), "image_size: JPEG without a frame header -> default")
    unk = tmp_root / "c.bin"
    unk.write_bytes(b"\x00" * 40)
    check(build_site.image_size(unk) == (200, 80), "image_size: unknown bytes -> default")
    svg = tmp_root / "d.svg"
    svg.write_text("<svg></svg>", encoding="utf-8")
    check(build_site.image_size(svg) == (200, 80), "image_size: SVG without a viewBox -> default")
    check(build_site._kb(2048) == "2.0&nbsp;KB", "_kb: kilobyte label (helper currently has no caller)")
    check(build_site.fx_convert(10, "EUR", "EUR") == 10 and build_site.fx_convert(10, "USD", "EUR") == 10 and build_site.fx_convert(117, "EUR", "GBP") == 100, "fx_convert: identity for the same or an unrated currency; EUR->GBP divides")
    check(build_site.days_until("not-a-date", date(2026, 9, 28)) is None, "days_until: invalid ISO -> None")
    check(build_site.snapshot_label("soon") == "Snapshot of soon", "snapshot_label: non-date text is echoed")
    t = date(2026, 9, 28)
    check(build_site.ago("", t) == "" and build_site.ago("garbage", t) == "" and build_site.ago("2026-09-27", t) == "Yesterday" and build_site.ago("2026-09-28", t) == "Today" and build_site.ago("2026-06-01", t) == "4 mo ago", "ago: empty, invalid, yesterday, today, months")
    check(build_site.sparkline_weeks([{"posted": ""}, {"posted": "nope"}, {"posted": "2026-09-27"}], t, 4) == [0, 0, 0, 1], "sparkline_weeks: skips empty and invalid dates")
    check(build_site.annual_mid({"sal_min": 100, "sal_max": 200, "cur": "EUR", "period": "year"}) is None and build_site.annual_mid({"sal_min": 1, "sal_max": 2, "cur": "EUR", "period": "aeon"}) is None, "annual_mid: implausible annual figures or an unknown period -> None")
    check(build_site.money_k(900, "€") == "€900" and build_site.money_k(62000, "£") == "£62k", "money_k: below 1000 keeps the figure")
    check(build_site.loc_class({"location": "", "region": "", "country": "United Kingdom"}) == "uk" and build_site.loc_class({"location": "", "region": "", "country": "Mars"}) == "intl", "loc_class: scraped-country fallbacks (UK, unknown -> intl)")
    check(build_site.with_head_extra("<html><head></head></html>", "<html>{{content}}</html>", "<link>") == "<html><head><link>\n</head></html>" and build_site.with_head_extra("x", "{{head_extra}}", "<link>") == "x", "with_head_extra: inserts before </head> only when the shell lacks the key")
    check(build_site.hero_bcorp({}, "../") == "" and build_site.bcorp_line(None, "../") == "", "hero_bcorp / bcorp_line: no brief -> ''")
    check(build_site.off_map_note({"regions": [{"name": "Dublin", "n": 2, "on_map": True}]}, "x") == "", "off_map_note: nothing off the map -> ''")
    check(build_site.waterfall({}, "") == '<p class="muted">Live-site request counts were not measured for this edition.</p>', "waterfall: no live measurement -> plain note")
    check(build_site.keith_changes(tmp_root) == "", "keith_changes: no checklist beside src -> ''")
    check(build_site.social_links(tmp_root, "ie") == [] and build_site.place_words(tmp_root) == ([], []) and build_site.ni_place_words(tmp_root) == [], "social_links / place_words / ni_place_words: missing data files -> empty")
    orig = build_site.PROJECT
    build_site.PROJECT = "no_such_project"
    try:
        check(build_site._load_ni_words() == build_site._NI_SEED, "_load_ni_words: unreadable regions table -> the seed list")
    finally:
        build_site.PROJECT = orig
    k = build_site.dashboard_kpis({"fetched": "2026-09-22", "jobs": [{"title": "t", "location": "", "text": "", "employer": "E", "posted": "31/31/2026", "closing": "2026-10-01", "sal_min": None, "sal_max": None, "cur": None, "period": None, "logo": ""}], "sectors": [], "regions": []})
    check(k["days_to_close"] is None and k["live"] == 1, "dashboard_kpis: an unparseable posted date is ignored for the advertised window")


def test_dataset_and_brief(tmp_root: Path):
    probs = build_site.check_dataset({"jobs": []})
    check(probs == ["no usable jobs after normalisation"], "check_dataset: empty dataset")
    probs = build_site.check_dataset({"jobs": [{"id": "1", "title": "a<b>", "sectors": ["x|y"]}]})
    check(_has(probs, "angle brackets") and _has(probs, "sector contains '|'"), "check_dataset: angle brackets in a title and '|' in a sector")
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw["jobs"] = [{**raw["jobs"][0]}, {**raw["jobs"][0]}, {**raw["jobs"][1], "id": "x1", "title": ""}, {**raw["jobs"][1], "id": "x2", "url": "ftp://nope"}]
    data = build_site.normalise(raw, "ie", SRC, SRC / "assets" / "logos")
    check([j["id"] for j in data["jobs"]] == ["1001"], "normalise: duplicate ids, empty titles and non-http URLs are skipped")
    check(build_site.read_brief(tmp_root) == {"facts": [], "b_corp": False, "employer_points": [], "text": "", "social": []}, "read_brief: no brief.md -> empty facts")
    (tmp_root / "data").mkdir()
    (tmp_root / "data" / "brief.md").write_text("- loose bullet\n## Facts\n- Founded 2008\nplain line\n## Employer offer\n- Cheap ads\n## Social\nhttps://www.linkedin.com/company/greenjobs B Corp\n", encoding="utf-8")
    b = build_site.read_brief(tmp_root)
    check(b["facts"] == ["loose bullet", "Founded 2008"] and b["employer_points"] == ["Cheap ads"] and b["b_corp"] and b["social"] == ["https://www.linkedin.com/company/greenjobs"], "read_brief: facts under a fact heading or none, employer points, B Corp flag, social links")
    fixture_data = build_site.normalise(json.loads(FIXTURE.read_text(encoding="utf-8")), "ie", SRC, SRC / "assets" / "logos")
    fixture_data["contact"] = {"address": "Ennis Digital Hub, Ennis"}
    fixture_data["about"] = "Launched in 2008."
    derived = build_site.derived_facts(fixture_data)
    check([h for h, _ in derived] == ["One of 2 specialist boards", "Green recruitment since 2008", "Real people in Ennis, Co. Clare"], f"derived_facts: network size, founding year and town from the dataset ({[h for h, _ in derived]})")
    fixture_data["contact"] = {"address": "1 Main St, Cork"}
    check("Real people in 1 Main St" in build_site.facts_block({"text": ""}, fixture_data), "facts_block: without brief.md the facts are derived (town = first address part)")
    src2 = tmp_root / "src_regions"
    (src2 / "data").mkdir(parents=True)
    (src2 / "assets" / "maps").mkdir(parents=True)
    (src2 / "data" / "regions_ie.json").write_text(json.dumps({"regions": {"Dublin": []}}), encoding="utf-8")
    (src2 / "assets" / "maps" / "regions_index.json").write_text(json.dumps({"ie": ["Dublin", "Cork"]}), encoding="utf-8")
    try:
        build_site.load_region_table(src2, "ie")
        check(False, "load_region_table: a map region missing from the table exits")
    except SystemExit as exc:
        check("lacks map regions: ['Cork']" in str(exc), "load_region_table: a map region missing from the table exits")


def test_hero_footage_variants(tmp_root: Path):
    src = tmp_root / "src_hero"
    hero = src / build_site.HERO_DIR
    hero.mkdir(parents=True)
    check(build_site.hero_files(src, "ie") == {} and build_site.hero_video(src, "ie", "../") == "", "hero: no footage -> no <video>")
    (hero / "ie-poster.webp").write_bytes(b"x")
    check(build_site.hero_files(src, "ie") == {"poster": "ie-poster.webp"} and build_site.hero_video(src, "ie", "../") == "", "hero: poster only -> still no <video> (the canvas is the hero)")
    (hero / "ie.mp4").write_bytes(b"x")
    v = build_site.hero_video(src, "ie", "../")
    check(v == '<video class="hero__video" data-hero-video muted loop playsinline autoplay preload="metadata" poster="../assets/hero/ie-poster.webp" aria-hidden="true" tabindex="-1"><source src="../assets/hero/ie.mp4" type="video/mp4"></video>', f"hero: landscape + poster -> exactly one source and the poster path ({v})")
    (hero / "ie-m.mp4").write_bytes(b"x")
    (hero / "ie-poster.jpg").write_bytes(b"x")
    v = build_site.hero_video(src, "ie", "../../")
    check(v.count("<source") == 2 and '<source src="../../assets/hero/ie-m.mp4" type="video/mp4" media="(max-width: 799px)"><source src="../../assets/hero/ie.mp4" type="video/mp4">' in v and 'poster="../../assets/hero/ie-poster.webp"' in v, "hero: portrait source first with its media query, root-relative paths, webp poster wins over jpg")
    (hero / "ie-poster.webp").unlink()
    check(build_site.hero_files(src, "ie") == {"video": "ie.mp4", "mobile": "ie-m.mp4", "poster": "ie-poster.jpg"}, "hero: jpg poster used when no webp")
    real = build_site.hero_video(SRC, "uk", "../")
    check('<source src="../assets/hero/uk-m.mp4"' in real and '<source src="../assets/hero/uk.mp4"' in real and 'poster="../assets/hero/uk-poster.jpg"' in real, "hero: the shipped src carries full UK footage")
    fails: list[str] = []
    fake_site = tmp_root / "hero_site"
    (fake_site / "ie").mkdir(parents=True)
    (fake_site / "uk").mkdir()
    shutil.copytree(SRC / build_site.HERO_DIR, fake_site / build_site.HERO_DIR)
    validate_site._check_hero(fake_site, fails)
    sizes = {p.name: p.stat().st_size for p in (SRC / build_site.HERO_DIR).glob("*")}
    check(fails == [] and validate_site.HERO_BUDGET_FILE == 2 * 1024 * 1024 and validate_site.HERO_BUDGET_TOTAL == 6 * 1024 * 1024 and max(sizes.values()) > 1024, f"hero: the shipped footage passes the 2 MB / 6 MB budgets with no failure ({sizes})")
    (fake_site / build_site.HERO_DIR / "big.bin").write_bytes(b"\0" * (validate_site.HERO_BUDGET_TOTAL + 1))
    fails = []
    validate_site._check_hero(fake_site, fails)
    check(fails == [f"assets/hero/big.bin: {validate_site.HERO_BUDGET_TOTAL + 1} bytes exceeds the per-file hero budget {validate_site.HERO_BUDGET_FILE}", f"hero footage: {sum(sizes.values()) + validate_site.HERO_BUDGET_TOTAL + 1} bytes exceeds the total hero budget {validate_site.HERO_BUDGET_TOTAL}"], f"hero: an oversize file trips both the per-file and total messages with the exact byte counts ({fails})")


def test_geometry_helpers():
    """svg_polygons / ring_area / point_in_rings / sample_map_points / film_payload
    have had no caller since the home film was removed (2026-09-28). They are
    pure and deterministic; covered here and listed as dead in COVERAGE.md."""
    rings = build_site.svg_polygons("M0 0 L10 0 L10 10 L0 10 Z M20 20 L30 20 L30 30 Z M1 1")
    check(len(rings) == 2 and build_site.ring_area(rings[0]) == 100 and build_site.ring_area(rings[1]) == 50, "svg_polygons/ring_area: two rings, a 3-point ring, a degenerate one dropped")
    check(len(build_site.svg_polygons("M0 0 L10 0 L10 10 M20 20 L30 20 L30 30")) == 2, "svg_polygons: an unclosed ring is kept when a new M starts or the data ends")
    check(build_site.point_in_rings(5, 5, rings) and not build_site.point_in_rings(15, 15, rings) and build_site.point_in_rings(25, 22, rings), "point_in_rings: even-odd containment")
    svg = ('<svg viewBox="0 0 100 100"><g class="gmap__r" data-region="A &amp; B" data-cx="5" data-cy="5"><path d="M0 0 L10 0 L10 10 L0 10 Z"/></g>'
           '<g class="gmap__r" data-region="C"><path d="M50 50 L90 50 L90 90 L50 90 Z"/></g><g class="gmap__r"><path d="M0 0 L1 0 L1 1 Z"/></g><g class="gmap__r" data-region="empty"></g></svg>')
    geo = build_site.sample_map_points(svg, n=40, seed=1)
    check(geo["vb"] == [100, 100] and [r["n"] for r in geo["regions"]] == ["A & B", "C"] and geo["regions"][0]["x"] == 5 and geo["regions"][1]["x"] == 0 and len(geo["pts"]) % 3 == 0 and len(geo["pts"]) // 3 >= 12, "sample_map_points: regions with names and paths only, at least six points each, integer triples")
    check(build_site.sample_map_points(svg, n=40, seed=1) == geo and build_site.sample_map_points("<svg></svg>")["vb"] == [600, 800], "sample_map_points: deterministic for a seed; default viewBox when missing")
    data = build_site.normalise(json.loads(FIXTURE.read_text(encoding="utf-8")), "ie", SRC, SRC / "assets" / "logos")
    fp = build_site.film_payload(data, SRC)
    check(fp["n_jobs"] == len(data["jobs"]) and fp["sym"] == "€" and fp["sectors"] and any(r["c"] for r in fp["regions"]) and len(fp["bands"]) == len(build_site.SALARY_EDGES), "film_payload: map points, counts per region, bands and sectors from the fixture")


# ------------------------------------------------------------- rendered output

def test_escaping_in_rendered_html(tmp_root: Path):
    t = date(2026, 9, 22)
    j = {"id": "q1", "title": 'Water "Lead" & Ops <x>', "employer": "'Quote' Co", "location": "Cork", "type": "", "sal_min": None, "sal_max": None, "cur": None, "period": None, "sal_text": "",
         "sectors": ["Water & flood"], "color": "#3f7ea6", "posted": "2026-09-20", "closing": "", "summary": "", "text": "", "description_html": "", "logo": "", "lw": 0, "lh": 0,
         "url": "https://x/j", "href": "q1/index.html", "loc_class": "ie", "workplace": "unspecified", "level": "Mid-level", "contract": [], "agency": False, "regions": ["Cork"]}
    card = build_site.role_card(j, "../", "jobs/", t)
    check('data-title="Water &quot;Lead&quot; &amp; Ops &lt;x&gt;"' in card and 'aria-label="Save: Water &quot;Lead&quot; &amp; Ops &lt;x&gt;"' in card and "<h3><a href=\"jobs/q1/index.html\">Water &quot;Lead&quot; &amp; Ops &lt;x&gt;</a></h3>" in card and '<span>&#x27;Quote&#x27; Co</span>' in card and "<x>" not in card, "role_card: title quotes, ampersand and angle brackets are escaped in attributes and text; employer apostrophes too")
    row = build_site.home_row(j, "../", "jobs/", t)
    check('data-title="Water &quot;Lead&quot; &amp; Ops &lt;x&gt;"' in row and '<i style="background:#3f7ea6"></i>Water &amp; flood</span>' in row, "home_row: escaped title in data-title, escaped sector name")
    check(build_site.logo_img({"logo": "", "employer": '"A'}, "../") == '<div class="role__logo role__logo--t" aria-hidden="true">&quot;</div>', "logo_img: the initial tile escapes a quote")
    sel = build_site.select_pairs("f-x", "Lbl", [('a"b', "A & B")], "Any")
    check(sel == '<div class="field"><label for="f-x">Lbl</label><select class="in" id="f-x" name="x"><option value="">Any</option><option value="a&quot;b">A &amp; B</option></select></div>', f"select_pairs: option value and text escaped ({sel})")
    check(build_site.esc('a"b\'c') == "a&quot;b&#x27;c" and build_site.qs('a b/c') == "a%20b%2Fc", "esc / qs: quotes and apostrophes escaped, query values percent-encoded")
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw["jobs"][0]["title"] = 'Ecologist "Bats" & Birds'
    raw["jobs"][0]["employer"] = "O'Brien & Sons"
    fx = tmp_root / "quoted.json"
    fx.write_text(json.dumps(raw), encoding="utf-8")
    out = tmp_root / "site_quoted"
    rc, err = _build(SRC, out, editions=["ie", "uk"], fixture=fx)
    page = (out / "ie" / "jobs" / "1001" / "index.html").read_text(encoding="utf-8")
    check(rc == 0 and "Ecologist &quot;Bats&quot; &amp; Birds" in page and 'data-title="Ecologist &quot;Bats&quot; &amp; Birds"' in page and "O&#x27;Brien &amp; Sons" in page and 'Ecologist "Bats"' not in page.split("<body")[1].split('id="gj-data"')[0], f"build: a title with quotes and an ampersand is escaped everywhere on its job page and the site still validates ({err[:120]})")
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.S).group(1))
    check(ld["title"] == 'Ecologist "Bats" & Birds' and ld["hiringOrganization"]["name"] == "O'Brien & Sons", "build: JSON-LD carries the raw title (JSON-escaped, not HTML-escaped)")
    home = (out / "ie" / "index.html").read_text(encoding="utf-8")
    check('aria-label="Save: Ecologist &quot;Bats&quot; &amp; Birds"' in home, "build: the home row's save button carries the escaped title")


def test_landing_zero_role_guard(tmp_root: Path):
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    eco = {j["id"]: j for j in raw["jobs"]}
    eco["1001"] = {**eco["1001"], "summary": "Lead ecological impact assessments and habitat surveys across Leinster.", "description_html": "<p>Bat and bird surveys, NIS and EIAR chapters.</p>", "sectors": ["Ecology"]}
    raw["jobs"] = [eco["1001"], eco["1008"]]  # Dublin ecologist (wind text removed) + Belfast ecologist: no renewable / sustainability roles at all
    fx = tmp_root / "eco_only.json"
    fx.write_text(json.dumps(raw), encoding="utf-8")
    ie = build_site.normalise(raw, "ie", SRC, SRC / "assets" / "logos")
    uk = build_site.normalise(raw, "uk", SRC, SRC / "assets" / "logos")
    check([s["slug"] for s, _ in build_site.landing_pages(ie)] == ["ecology-jobs-ireland", "environmental-jobs-dublin"] and [len(js) for _, js in build_site.landing_pages(ie)] == [2, 1], "landing_pages: IE builds only the ecology and Dublin pages (2 and 1 roles); renewable and sustainability have zero roles and are skipped")
    check([s["slug"] for s, _ in build_site.landing_pages(uk)] == ["ecology-jobs-uk"] and [j["id"] for _, js in build_site.landing_pages(uk) for j in js] == ["1008"], "landing_pages: UK builds only the ecology page with the Belfast role (Dublin excluded, no London role)")
    check(build_site.landing_pages({"ed": "ie", "jobs": []}) == [] and build_site.landing_pages({"ed": "uk", "jobs": []}) == [], "landing_pages: no roles -> no pages on either edition")
    out = tmp_root / "site_eco"
    rc, err = _build(SRC, out, editions=["ie", "uk"], fixture=fx)
    built = {ed: sorted(p.parent.name for p in (out / ed).glob("*-jobs-*/index.html")) for ed in ("ie", "uk")}
    check(rc == 0 and built == {"ie": ["ecology-jobs-ireland", "environmental-jobs-dublin"], "uk": ["ecology-jobs-uk"]}, f"build: only landing pages with at least one role are written ({built}; {err[:120]})")
    check(all(p.read_text(encoding="utf-8").count('<article class="role reveal"') >= 1 for ed in ("ie", "uk") for p in (out / ed).glob("*-jobs-*/index.html")), "build: every written landing page carries a role card")
    site_map = (out / "sitemap.xml").read_text(encoding="utf-8")
    check("ie/ecology-jobs-ireland/index.html" in site_map and "renewable-energy-jobs-ireland" not in site_map and "sustainability-jobs-uk" not in site_map, "build: the sitemap lists only the landing pages that were built")
    guides = (out / "ie" / "guides" / "index.html").read_text(encoding="utf-8")
    check("Ecology jobs in Ireland</a> <span class=\"muted\">· 2 live</span>" in guides and "Renewable energy jobs" not in guides, "build: the guides hub links only built landing pages with their live counts")
    head = (out / "ie" / "environmental-jobs-dublin" / "index.html").read_text(encoding="utf-8").split("</head>")[0]
    check('rel="canonical" href="https://greenjobs-redesign.pages.dev/ie/environmental-jobs-dublin/index.html"' in head and 'rel="alternate"' not in head, "build: a landing page built on one edition only has a canonical and no hreflang pair")


# ------------------------------------------------------------- build plumbing failures

class _Proc:
    def __init__(self, rc: int, out: str = "", err: str = "") -> None:
        self.returncode, self.stdout, self.stderr = rc, out, err


def test_node_and_js_checks(tmp_root: Path):
    check(build_site.run_node_tests(tmp_root) is None, "run_node_tests: no lib.test.js -> None")
    js = tmp_root / "src_js" / "js"
    js.mkdir(parents=True)
    (js / "lib.test.js").write_text("", encoding="utf-8")
    orig = build_site.subprocess.run
    try:
        build_site.subprocess.run = lambda *a, **k: (_ for _ in ()).throw(OSError("node missing"))
        check(build_site.run_node_tests(tmp_root / "src_js") is None, "run_node_tests: node missing (OSError) -> None")
        build_site.subprocess.run = lambda *a, **k: _Proc(1, "TAP\n")
        check(build_site.run_node_tests(tmp_root / "src_js") == (0, 1), "run_node_tests: non-zero exit without a fail line counts one failure")
        build_site.subprocess.run = lambda *a, **k: _Proc(0, "")
        check(build_site.run_node_tests(tmp_root / "src_js") == (0, 1), "run_node_tests: zero tests reported counts as a failure")
        build_site.subprocess.run = lambda *a, **k: _Proc(0, "# pass 3\n# fail 0\n")
        check(build_site.run_node_tests(tmp_root / "src_js") == (3, 0), "run_node_tests: pass/fail lines parsed")
        site = tmp_root / "site_js"
        (site / "js").mkdir(parents=True)
        (site / "js" / "a.js").write_text("var x = ;", encoding="utf-8")
        build_site.subprocess.run = lambda *a, **k: (_ for _ in ()).throw(subprocess.SubprocessError("timeout"))
        probs = build_site.check_built_js(site)
        check(_has(probs, "node --check could not run") and len(probs) == 1, "check_built_js: node unavailable -> one problem per script")
    finally:
        build_site.subprocess.run = orig
    probs = build_site.check_built_js(site)
    check(_has(probs, "does not parse after the publish pass") and _has(probs, "does not start with 'use strict'"), "check_built_js: real node flags a syntax error and a missing 'use strict'")


def test_guard_output_edges(tmp_root: Path):
    f = tmp_root / "afile"
    f.write_text("x", encoding="utf-8")
    check("exists and is not a directory" in build_site.guard_output(SRC, f), "guard_output: --out is a file")
    orig = os.environ.get("CLAUDE_SCRATCHPAD")
    scratch = Path(tempfile.mkdtemp(prefix="gj_scratch_"))
    os.environ["CLAUDE_SCRATCHPAD"] = str(scratch)
    try:
        check(build_site.guard_output(SRC, scratch / "site") == "", "guard_output: CLAUDE_SCRATCHPAD is an allowed build area")
    finally:
        if orig is None:
            del os.environ["CLAUDE_SCRATCHPAD"]
        else:
            os.environ["CLAUDE_SCRATCHPAD"] = orig
        shutil.rmtree(scratch, ignore_errors=True)


def _build(*a, **k) -> tuple[int, str]:
    """build() plus its stderr, so a failure exit can be matched to its message."""
    import io
    from contextlib import redirect_stderr
    buf = io.StringIO()
    with redirect_stderr(buf):
        rc = build_site.build(*a, **k)
    return rc, buf.getvalue()


def test_build_failure_exits(tmp_root: Path):
    rc, err = _build(tmp_root / "no_src", tmp_root / "o1", editions=["ie"])
    check(rc == 2 and f"FAIL  source directory not found: {tmp_root / 'no_src'}" in err and not (tmp_root / "o1").exists(), "build: missing --src -> 2 with the message; nothing written")
    rc, err = _build(SRC, Path("/etc/greenjobs_never"), editions=["ie"])
    check(rc == 2 and "outside the build areas" in err and "refusing to delete it" in err, "build: refused --out -> 2 with the guard's message")
    rc, err = _build(SRC, tmp_root / "o2", editions=["ie"], fixture=tmp_root / "missing.json")
    check(rc == 2 and f"FAIL  dataset missing: {tmp_root / 'missing.json'}" in err, "build: missing dataset -> 2 with the path")
    empty = tmp_root / "empty.json"
    empty.write_text(json.dumps({"site": "x", "fetched": "2026-09-22", "jobs": []}), encoding="utf-8")
    rc, err = _build(SRC, tmp_root / "o3", editions=["ie"], fixture=empty)
    check(rc == 2 and "ie.json has 1 problem(s):" in err and "no usable jobs after normalisation" in err and not (tmp_root / "o3").exists(), "build: empty dataset -> 2, names the problem, writes nothing")
    orig = build_site.run_node_tests
    build_site.run_node_tests = lambda src: (2, 1)
    try:
        rc, err = _build(SRC, tmp_root / "o4", editions=["ie", "uk"], fixture=FIXTURE)
        check(rc == 1 and "FAIL  1 node test(s) failing" in err and (tmp_root / "o4" / "ie" / "index.html").exists() and not (tmp_root / "o4" / "ie" / "for-keith" / "index.html").exists(), "build: a failing node test -> 1 after the pages, before the evidence page")
    finally:
        build_site.run_node_tests = orig
    orig_js = build_site.check_built_js
    build_site.check_built_js = lambda site: ["injected problem"]
    try:
        rc, err = _build(SRC, tmp_root / "o5", editions=["ie", "uk"], fixture=FIXTURE)
        check(rc == 1 and "FAIL  1 validation problem(s):" in err and "  - injected problem" in err, "build: a validation problem -> 1 and the problem is listed")
    finally:
        build_site.check_built_js = orig_js


def test_rebuild_and_no_site_base(tmp_root: Path):
    out = tmp_root / "o6"
    check(build_site.build(SRC, out, editions=["ie", "uk"], fixture=FIXTURE) == 0, "rebuild: first fixture build passes")
    (out / "stale.txt").write_text("x", encoding="utf-8")
    check(build_site.build(SRC, out, editions=["ie", "uk"], fixture=FIXTURE) == 0 and not (out / "stale.txt").exists(), "rebuild: a marked --out is wiped and rebuilt")
    src2 = tmp_root / "src_nobase"
    shutil.copytree(SRC, src2, ignore=shutil.ignore_patterns("ie.json", "uk.json", "__pycache__"))
    (src2 / "config.json").unlink()
    out2 = tmp_root / "o7"
    import io
    from contextlib import redirect_stderr
    buf = io.StringIO()
    with redirect_stderr(buf):
        rc = build_site.build(src2, out2, editions=["ie", "uk"], fixture=FIXTURE)
    check(rc == 1 and "no canonical link" in buf.getvalue(), "no site_base: a build without config.json renders but fails validation (section pages need a canonical)")
    check("<url>" not in (out2 / "sitemap.xml").read_text(encoding="utf-8") and 'rel="canonical"' not in (out2 / "ie" / "index.html").read_text(encoding="utf-8"), "no site_base: empty sitemap, no canonical links")


def test_cli_main_with_today(tmp_root: Path):
    out = tmp_root / "o8"
    argv = sys.argv
    sys.argv = ["build_site.py", "--src", str(SRC), "--out", str(out), "--edition", "both", "--data-fixture", str(FIXTURE), "--today", "2026-10-01"]
    try:
        rc = build_site.main()
    finally:
        sys.argv = argv
    check(rc == 0 and not (out / "ie" / "jobs" / "1005" / "index.html").exists() and '"today":"2026-10-01"' in (out / "ie" / "jobs" / "index.html").read_text(encoding="utf-8"), "main(): CLI with --today builds and drops the role closing before it")


# ------------------------------------------------------------- validator messages

SHELL = '<!doctype html><html lang="en-IE"><head><title>T</title><meta name="robots" content="noindex,nofollow">{head}</head><body><main><h1>H</h1>{body}</main></body></html>'


def _site(tmp_root: Path) -> Path:
    site = tmp_root / "synthetic_site"
    if site.exists():
        shutil.rmtree(site)
    (site / "assets" / "fonts").mkdir(parents=True)
    (site / "ie" / "jobs" / "1").mkdir(parents=True)
    (site / "ie" / "dashboard").mkdir()
    (site / "ie" / "plain").mkdir()
    for f in ("A.woff2", "B.woff2"):
        (site / "assets" / "fonts" / f).write_bytes(b"x")
    (site / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
    (site / "js").mkdir()
    (site / "js" / "x.test.js").write_text("'use strict';\n", encoding="utf-8")
    return site


def _w(site: Path, rel: str, text: str) -> None:
    (site / rel).parent.mkdir(parents=True, exist_ok=True)
    (site / rel).write_text(text, encoding="utf-8")


def test_validator_every_message(tmp_root: Path):
    check(validate_site.validate(tmp_root / "no_pages_here", {}) == [f"no HTML pages found under {tmp_root / 'no_pages_here'}"], "validate: no pages -> one failure")
    site = _site(tmp_root)
    fonts = "A.woff2 B.woff2"
    # root: unrendered key, no lang, two titles, empty href, javascript:, escaping path, img without alt, bad + empty JSON-LD, bad dataset, google fonts, unlabelled controls, duplicate hreflang, video faults
    _w(site, "index.html", '<html><head><title>a</title><title>b</title><link rel="alternate" hreflang="en-IE" href="https://x/ie/index.html"><link rel="alternate" hreflang="en-IE" href="https://x/ie/index.html"><link rel="alternate" hreflang="x-default" href="https://x/ie/index.html">'
           '<link rel="stylesheet" href="https://fonts.googleapis.com/css"></head><body>{{unrendered}} <a href="">e</a><a href="javascript:void(0)">j</a><a href="../../../etc/passwd">esc</a><img src="assets/fonts/A.woff2" width="1" height="1">'
           '<script type="application/ld+json">{bad</script><script type="application/ld+json">{}</script><script type="application/json" id="gj-data">nope</script>'
           '<input type="text"><input type="text" id="unl"><input type="text" id="lab" aria-label="ok"><video muted playsinline></video><video><source src="/abs.mp4"><source src="missing.mp4"></video>' + fonts + '</body></html>')
    # a job page: no apply link, unparsable JSON-LD, bad baseSalary, bad validThrough
    _w(site, "ie/jobs/1/index.html", SHELL.format(head='<link rel="canonical" href="https://x/ie/jobs/1/index.html">', body='<script type="application/ld+json">{oops</script><script type="application/ld+json">{"@type":"JobPosting","baseSalary":{"currency":"XXX","value":{}},"validThrough":"soon"}</script>' + fonts))
    # a section page with no canonical; the home page without the landscape host
    _w(site, "ie/plain/index.html", SHELL.format(head="", body=fonts))
    _w(site, "ie/index.html", SHELL.format(head='<link rel="canonical" href="https://x/ie/index.html">', body=fonts))
    # dashboard: no gj-dash block
    _w(site, "ie/dashboard/index.html", SHELL.format(head='<link rel="canonical" href="https://x/ie/dashboard/index.html">', body=fonts))
    # jobs board: dataset with two jobs (one page exists) pointing at a missing page
    _w(site, "ie/jobs/index.html", SHELL.format(head='<link rel="canonical" href="https://x/ie/jobs/index.html">', body='<script type="application/json" id="gj-data">{"jobs":[{"href":"1/index.html"},{"href":"2/index.html"}]}</script>' + fonts))
    # a page that does not preload the fonts
    _w(site, "ie/nofont/index.html", SHELL.format(head='<link rel="canonical" href="https://x/ie/nofont/index.html">', body="none"))
    jobs = {"ie": [{"employer": "E"}], "zz": [{"employer": "Z"}]}
    orig_css = validate_site.CSS_BUDGET
    validate_site.CSS_BUDGET = validate_site.JS_BUDGET = 0
    (site / "css").mkdir()
    (site / "css" / "s.css").write_text("a{}", encoding="utf-8")
    try:
        fails = validate_site.validate(site, jobs, {"ie": {"k": 1}}, lambda d: {"live": 5})
    finally:
        validate_site.CSS_BUDGET = orig_css
        validate_site.JS_BUDGET = 125 * 1024
    expect = [
        "unrendered template key {{unrendered}}", "<html> has no lang attribute", "expected exactly one non-empty <title>, found 2", "expected exactly one <h1>, found 0", "missing <meta name=robots",
        "empty href attribute on <a>", "uses a forbidden scheme", "escapes the site root", 'has no alt attribute', "JSON-LD block 0 does not parse", "JSON-LD block 1 is empty",
        "embedded dataset block 0 does not parse", "requests fonts from Google", "a <input> form control has no id", '<input id="unl"> has no <label for> and no aria-label',
        "duplicate hreflang values", "<video> has no source", "hero video reference '/abs.mp4' is not a relative local path", "hero video reference 'missing.mp4' does not exist", "hero <video> must be muted and playsinline",
        "ie/jobs/1/index.html: job page has no apply link", "JobPosting baseSalary must carry a currency code and a numeric value", "JobPosting validThrough is not a date",
        "ie/plain/index.html: no canonical link", "ie/index.html: home page has no hero landscape host", "ie/dashboard/index.html: no embedded gj-dash KPI block",
        "zz: rendered 0 job pages, dataset has 1", "ie/jobs/index.html: embedded dataset has 2 jobs, expected 1", "dataset href 2/index.html has no page",
        "CSS budget:", "JS budget:", "a *.test.js file was shipped", "manifest.webmanifest is missing", "sitemap.xml is missing", "404.html is missing", "robots.txt does not disallow crawling",
        "assets/hero/ie.mp4 is missing", "assets/hero/ie-poster.webp|jpg is missing", "ie/nofont/index.html: does not preload A.woff2",
    ]
    for needle in expect:
        check(_has(fails, needle), f"validate: message {needle!r}")
    check(not _has(fails, '<input id="lab">'), "validate: an aria-labelled control passes")
    # dashboard: unparsable gj-dash, then a live tile value outside the KPI set
    _w(site, "ie/dashboard/index.html", SHELL.format(head="", body='<script type="application/json" id="gj-dash">{x</script>' + fonts))
    check(_has(validate_site.validate(site, {}, {"ie": {}}, lambda d: {"live": 5}), "gj-dash block does not parse"), "validate: unparsable gj-dash block")
    _w(site, "ie/dashboard/index.html", SHELL.format(head="", body='<script type="application/json" id="gj-dash">{"live":5}</script><div class="kpi"><span class="kpi__l">L</span><b class="kpi__v num">999</b></div><div class="kpi"><span class="kpi__l">M</span><b class="kpi__v num">€5</b></div>' + fonts))
    fails = validate_site.validate(site, {}, {"ie": {}}, lambda d: {"live": 5})
    check(_has(fails, "live tile value '999' is not a value of dashboard_kpis(data)") and not _has(fails, "'€5'"), "validate: a live tile value must be one of the fresh KPI values (currency prefix ignored)")
    shutil.rmtree(site / "assets" / "fonts")
    check(_has(validate_site.validate(site, {}), "expected two self-hosted woff2 files"), "validate: fewer than two woff2 files")


def run_all(tmp_root: Path) -> list[tuple[bool, str]]:
    import inspect
    RESULTS.clear()
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        if "tmp_root" in inspect.signature(fn).parameters:
            fn(tmp_root)
        else:
            fn()
    return list(RESULTS)


def main() -> int:
    base = REPO / ".tmp"
    base.mkdir(exist_ok=True)
    tmp_root = Path(tempfile.mkdtemp(prefix="greenjobs_test_gaps_", dir=str(base)))
    try:
        results = run_all(tmp_root)
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
    failed = [label for ok, label in results if not ok]
    print(f"\nGaps: {len(results) - len(failed)} passed, {len(failed)} failed")
    for label in failed:
        print(f"  FAIL: {label}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
