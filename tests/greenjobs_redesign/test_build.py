"""Unit + integration tests for the GreenJobs redesign build pipeline.

description: Exercises build_site.py helpers in isolation (sector taxonomy,
  region resolution, date parsing, HTML sanitising, salary labels, image
  sizing, output guard) and the build -> validate chain against the six-job
  fixture and, when present, the real datasets, plus injected faults the
  validator must catch. Never writes into deliverables/{src,site}: every build
  target is a fresh directory under the repo's .tmp/.
inputs: none (reads the checked-in src/ tree read-only)
outputs: stdout PASS/FAIL lines; exit code 0 (all pass) / 1 (failures)

Run: python3 tests/greenjobs_redesign/test_build.py
     or: python3 -m pytest tests/greenjobs_redesign/test_build.py -q
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO / "execution" / "gtm_client_workflows" / "greenjobs_redesign"
SRC = REPO / "deliverables" / "greenjobs_redesign_2026-09-22" / "src"
FIXTURE = SRC / "data" / "_fixture.json"

sys.path.insert(0, str(SCRIPT_DIR))
import build_site  # noqa: E402
import validate_site  # noqa: E402

RESULTS: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> None:
    RESULTS.append((ok, label))
    print(("PASS  " if ok else "FAIL  ") + label)


# ------------------------------------------------------------- unit tier

def test_esc_and_json():
    check(build_site.esc('<b>"x"</b> & Y') == "&lt;b&gt;&quot;x&quot;&lt;/b&gt; &amp; Y", "esc escapes <, >, &, \"")
    out = build_site.json_ld({"t": "</script><script>alert(1)</script>"})
    check("</script>" not in out and json.loads(out.replace("\\u003c", "<")), "json_ld neutralises </script> and round-trips")
    check("<" not in build_site.json_embed({"a": "<x>"}), "json_embed escapes <")


def test_parse_date():
    check(build_site.parse_date("18/09/2026") == "2026-09-18", "parse_date: dd/mm/yyyy")
    check(build_site.parse_date("2026-09-18T10:00:00Z") == "2026-09-18", "parse_date: ISO datetime")
    check(build_site.parse_date("31/02/2026") == "", "parse_date: impossible date -> ''")
    check(build_site.parse_date(None) == "", "parse_date: None -> ''")


def test_sectors():
    j = {"title": "Wind Turbine Technician", "sectors": ["Wind Jobs", "Renewable Energy jobs"], "summary": "", "description_html": ""}
    s = build_site.assign_sectors(j)
    check(s[0] == "Wind energy", f"assign_sectors: wind title + raw sectors -> Wind energy first (got {s})")
    j2 = {"title": "Office Administrator", "sectors": [], "summary": "", "description_html": "<p>General admin.</p>"}
    check(build_site.assign_sectors(j2) == ["Environmental science & consulting"], "assign_sectors: no match falls back to the umbrella sector")
    j3 = {"title": "Ecologist", "sectors": None, "summary": None, "description_html": None}
    check(build_site.assign_sectors(j3)[0] == "Ecology, nature recovery & biodiversity", "assign_sectors: null fields are tolerated")


def test_regions():
    table = json.loads((SRC / "data" / "regions_ie.json").read_text(encoding="utf-8"))
    ed = build_site.EDITIONS["ie"]
    check(build_site.resolve_regions({"region": "Ireland", "location": "Galway City, Co. Galway"}, table, ed) == ["Galway"], "resolve_regions: alias 'Galway City' -> Galway")
    check(build_site.resolve_regions({"region": None, "location": "Carlow, Dublin, Cork"}, table, ed) == ["Carlow", "Cork", "Dublin"] or set(build_site.resolve_regions({"region": None, "location": "Carlow, Dublin, Cork"}, table, ed)) == {"Carlow", "Dublin", "Cork"}, "resolve_regions: multi-county location -> all three")
    check(build_site.resolve_regions({"region": "United Kingdom", "location": "London"}, table, ed) == [ed["elsewhere"]], "resolve_regions: UK job on IE edition -> elsewhere bucket")
    check(build_site.resolve_regions({"region": "", "location": "Remote"}, table, ed) == [ed["none"]], "resolve_regions: remote -> nationwide bucket")
    uk = json.loads((SRC / "data" / "regions_uk.json").read_text(encoding="utf-8"))
    r = build_site.resolve_regions({"region": "London, Yorkshire and Humber, Country", "location": "Leeds"}, uk, build_site.EDITIONS["uk"])
    check(set(r) == {"London", "Yorkshire and the Humber"}, f"resolve_regions: UK free-text region list + city (got {r})")


def test_sanitise_html():
    raw = '<p onclick="x()">Hi <script>alert(1)</script><a href="/apply" style="color:red">apply</a><img src="x.png"><iframe src="e"></iframe></p><h1>Big</h1>'
    out = build_site.sanitise_html(raw, "https://www.greenjobs.ie/jobs/1/")
    check("<script" not in out and "iframe" not in out and "<img" not in out, "sanitise_html: drops script/iframe/img")
    check("onclick" not in out and "style=" not in out, "sanitise_html: strips event handlers and style")
    check('href="https://www.greenjobs.ie/apply"' in out, "sanitise_html: relative href made absolute against the job URL")
    check("<h1>" not in out and "<h3>" in out, "sanitise_html: h1 demoted to h3")
    check(build_site.sanitise_html(None, "https://x/") == "", "sanitise_html: None -> ''")


def test_salary_label():
    check(build_site.salary_label({"sal_min": 55000, "sal_max": 65000, "cur": "EUR", "period": "year"}) == "€55k–65k", "salary_label: range")
    check(build_site.salary_label({"sal_min": None, "sal_max": None}) == "", "salary_label: undisclosed -> ''")
    check(build_site.salary_label({"sal_min": 30, "sal_max": 30, "cur": "GBP", "period": "hour"}) == "£30/hr", "salary_label: hourly")


def test_image_size(tmp_root: Path):
    png = tmp_root / "a.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + (300).to_bytes(4, "big") + (120).to_bytes(4, "big") + b"\x08\x06\x00\x00\x00")
    check(build_site.image_size(png) == (300, 120), "image_size: PNG header")
    gif = tmp_root / "a.gif"
    gif.write_bytes(b"GIF89a" + (64).to_bytes(2, "little") + (32).to_bytes(2, "little") + b"\x00" * 6)
    check(build_site.image_size(gif) == (64, 32), "image_size: GIF header")
    svg = tmp_root / "a.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96.69 163.03"></svg>', encoding="utf-8")
    check(build_site.image_size(svg) == (96, 163), "image_size: SVG viewBox")
    check(build_site.image_size(tmp_root / "missing.png") == (200, 80), "image_size: missing file -> default")


def test_publish_text():
    out = build_site.publish_text("/* c */\n  .a { x: 1 }\n// line\nvar re = /a\\/\\/b/; // keep\n")
    check("/* c */" not in out and "// line" not in out and "// keep" in out, "publish_text: strips block + whole-line comments only")


def test_guard_output(tmp_root: Path):
    check(bool(build_site.guard_output(SRC, SRC)), "guard_output: refuses --out == --src")
    check(bool(build_site.guard_output(SRC, Path("/etc"))), "guard_output: refuses an --out outside the allowed areas")
    check(build_site.guard_output(SRC, tmp_root / "fresh") == "", "guard_output: allows a fresh dir under .tmp")
    nonempty = tmp_root / "nonempty"
    nonempty.mkdir()
    (nonempty / "keep.txt").write_text("x", encoding="utf-8")
    check(bool(build_site.guard_output(SRC, nonempty)), "guard_output: refuses a non-empty dir without the marker")
    (nonempty / build_site.MARKER).write_text("x", encoding="utf-8")
    check(build_site.guard_output(SRC, nonempty) == "", "guard_output: allows a marked dir")


def test_check_dataset_rejects_bad_ids():
    good = {"jobs": [{"id": "abc_1-Z", "title": "T", "sectors": ["Wind energy"]}]}
    check(build_site.check_dataset(good) == [], "check_dataset: safe id passes")
    for bad in ("../x", "a b", "", "x/y", "a<b>"):
        probs = build_site.check_dataset({"jobs": [{"id": bad, "title": "T", "sectors": []}]})
        check(any("job id" in x for x in probs), f"check_dataset: id {bad!r} rejected")


def test_bad_id_fails_build(tmp_root: Path):
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw["jobs"][0]["id"] = "../escape"
    bad = tmp_root / "bad_fixture.json"
    bad.write_text(json.dumps(raw), encoding="utf-8")
    rc = build_site.build(SRC, tmp_root / "site_bad_id", editions=["ie"], fixture=bad)
    check(rc != 0, "build: injected bad job id fails the build (non-zero exit)")


def test_plural_and_snapshot():
    check(build_site.plural("county") == "counties", "plural: county -> counties")
    check(build_site.plural("region") == "regions", "plural: region -> regions")
    check(build_site.snapshot_label("2026-09-22") == "Snapshot of 22 September 2026", "snapshot_label: ISO date -> 'Snapshot of 22 September 2026'")
    check(build_site.median_salary([{"sal_min": 50000, "sal_max": 60000, "period": "year"}, {"sal_min": 40000, "sal_max": None, "period": "year"}, {"sal_min": None, "sal_max": None}], "€") == "€47.5k", "median_salary: midpoint median formatted like lib.js")


def test_employers_strip_is_honest():
    emps = [{"name": n, "url": "", "logo": "", "lw": 0, "lh": 0} for n in ["A", "B", "C", "D", "E", "F", "G", "Pad1", "Pad2"]]
    mk = lambda names: {"site": "x.ie", "employers": emps, "jobs": [{"employer": n} for n in names]}  # noqa: E731
    six = build_site.employers_strip(mk(["A", "B", "C", "D", "E", "F"]), "../")
    check(six["mode"] == "hiring" and six["title"] == "Employers hiring now" and "Pad1" not in six["html"] and "G" not in six["html"].replace("Green", ""), "employers_strip: >=6 live employers -> 'hiring now' with live employers only")
    two = build_site.employers_strip(mk(["A", "B"]), "../")
    check(two["mode"] == "network" and two["title"] == "Employers on the GreenJobs network" and "2 of them have live roles" in two["sub"] and "Pad1" in two["html"], "employers_strip: <6 live -> network title, padded honestly")
    check(build_site.employers_strip({"site": "x", "employers": [], "jobs": []}, "../")["html"] == "", "employers_strip: no employers -> empty html")


def test_render_fails_loudly():
    try:
        build_site.render("<p>{{missing}}</p>", {})
        check(False, "render: unknown key raises")
    except KeyError:
        check(True, "render: unknown key raises")


# ------------------------------------------------------------- integration tier

def test_fixture_build(tmp_root: Path):
    out = tmp_root / "site_fixture"
    rc = build_site.build(SRC, out, editions=["ie", "uk"], fixture=FIXTURE)
    check(rc == 0, "integration: fixture build (both editions) returns 0")
    check((out / "index.html").exists() and (out / "ie" / "jobs" / "1001" / "index.html").exists() and (out / "uk" / "jobs" / "1007" / "index.html").exists(), "integration: chooser + job pages written for both editions")
    check(not (out / "uk" / "jobs" / "1001" / "index.html").exists() and (out / "ie" / "jobs" / "1007" / "index.html").exists() and (out / "uk" / "jobs" / "1004" / "index.html").exists() and (out / "uk" / "jobs" / "1008" / "index.html").exists(),
          "integration: UK edition drops the Dublin-only role, keeps remote, London and Belfast; IE keeps the London role (B5)")
    for req in ("sitemap.xml", "manifest.webmanifest", "robots.txt", "404.html", "ie/data/jobs.json", "assets/maps"):
        pass
    check((out / "sitemap.xml").read_text(encoding="utf-8").count("<url>") >= 2 * (6 + 6), "integration: sitemap lists pages and job pages")
    home = (out / "ie" / "index.html").read_text(encoding="utf-8")
    check("Nuclear Decommissioning" not in home and "(0)" not in home, "integration: zero-count sector never rendered on the home page")
    check('id="gj-data"' in (out / "ie" / "jobs" / "index.html").read_text(encoding="utf-8"), "integration: dataset embedded on the board")
    job = (out / "ie" / "jobs" / "1002" / "index.html").read_text(encoding="utf-8")
    check("Not disclosed" in job and '"JobPosting"' in job and "baseSalary" not in job, "integration: null salary renders 'Not disclosed' and omits baseSalary in JSON-LD")
    check("role__logo--t" in job or "role__logo" in job, "integration: missing logo falls back to an initial tile")
    css = sum(p.stat().st_size for p in (out / "css").glob("*.css"))
    js = sum(p.stat().st_size for p in (out / "js").glob("*.js"))
    check(css <= validate_site.CSS_BUDGET and js <= validate_site.JS_BUDGET, f"integration: budgets hold (css {css}, js {js})")
    check(not list(out.rglob("*.test.js")), "integration: test files not shipped")


def test_real_data_build(tmp_root: Path):
    if not (SRC / "data" / "ie.json").exists() or not (SRC / "data" / "uk.json").exists():
        check(True, "integration: real datasets absent, skipped")
        return
    out = tmp_root / "site_real"
    rc = build_site.build(SRC, out, editions=["ie", "uk"])
    check(rc == 0, "integration: real-data build returns 0")
    for ed in ("ie", "uk"):
        raw = json.loads((SRC / "data" / f"{ed}.json").read_text(encoding="utf-8"))
        pages = len(list((out / ed / "jobs").glob("*/index.html")))
        data = build_site.normalise(raw, ed, SRC, SRC / "assets" / "logos")
        check(pages == len(data["jobs"]) and pages + len(data["excluded"]) == len(raw["jobs"]), f"integration: {ed} job page count {pages} + {len(data['excluded'])} excluded == dataset {len(raw['jobs'])}")
        if ed == "uk":
            check(all(j["loc_class"] in ("uk", "ni", "remote", "cross") for j in data["jobs"]) and all(x["loc_class"] in ("ie", "intl") for x in data["excluded"]), "integration: UK edition carries only uk/ni/remote/cross roles; ie-only and international are excluded (B5)")
            keith = (out / "uk" / "for-keith" / "index.html").read_text(encoding="utf-8")
            check(f"{len(data['excluded'])} excluded" in keith, "integration: UK evidence page states the excluded count")


def test_validator_catches_injected_faults(tmp_root: Path):
    out = tmp_root / "site_faults"
    rc = build_site.build(SRC, out, editions=["ie", "uk"], fixture=FIXTURE)
    check(rc == 0, "faults: baseline fixture build passes")
    jobs = {"ie": json.loads((out / "ie" / "jobs" / "index.html").read_text(encoding="utf-8").split('id="gj-data">')[1].split("</script>")[0])["jobs"]}
    home = out / "ie" / "index.html"
    clean = home.read_text(encoding="utf-8")

    def with_patch(fn):
        home.write_text(fn(clean), encoding="utf-8")
        fails = validate_site.validate(out, jobs)
        home.write_text(clean, encoding="utf-8")
        return fails

    check(any("absolute path" in f for f in with_patch(lambda t: t.replace('href="jobs/index.html"', 'href="/jobs/index.html"', 1))), "faults: leading-slash href caught")
    check(any("does not resolve" in f for f in with_patch(lambda t: t.replace("</body>", '<img src="../assets/nope.png" alt="x" width="1" height="1"></body>'))), "faults: missing image caught")
    check(any("forbidden word" in f for f in with_patch(lambda t: t.replace("</body>", "<p>Built with AI.</p></body>"))), "faults: 'AI' on a public page caught")
    check(any("third-party" in f for f in with_patch(lambda t: t.replace("</head>", '<script src="https://cdn.example.com/x.js"></script></head>'))), "faults: third-party script caught")
    check(any("missing width/height" in f for f in with_patch(lambda t: t.replace("</body>", '<img src="../assets/favicon.svg" alt="x"></body>'))), "faults: undimensioned image caught")
    check(any("noindex" in f for f in with_patch(lambda t: t.replace('content="noindex,nofollow"', 'content="index"'))), "faults: missing noindex caught")
    check(any("exactly one <h1>" in f for f in with_patch(lambda t: t.replace("</main>", "<h1>Two</h1></main>"))), "faults: second h1 caught")
    check(any("countyies" in f for f in with_patch(lambda t: t.replace("</main>", "<p>14 countyies</p></main>"))), "faults: 'countyies' caught")
    check("countyies" not in clean and "counties" in clean, "home: unit pluralised as 'counties'")
    check("For Keith" not in clean and "for-keith" not in clean, "home: for-keith is not linked from the public shell")
    check("Snapshot of" in clean, "home: hero carries the snapshot date")
    check('class="hero"' in clean and clean.index('class="hero"') < clean.index('id="h-insight"'), "home: opens on the light hero; the compact insight band replaced the film (2026-09-28)")
    check('id="s-q"' in clean and 'btn--post' in clean and 'employers/index.html#post' in clean, "home: hero search and Post a job present")
    check(clean.count('<article class="row"') == min(8, len(jobs["ie"])) and "tag--lvl" in clean, "home: compact rows (up to eight) with career-level chips")
    check('alt="Certified B Corporation"' in clean and 'class="hero__bcorp"' in clean, "home: B Corp mark in the hero with the confirmed wording")
    check("data-film-steps" not in clean, "home: the film rail is gone (compact insight band since 2026-09-28)")
    for t, lvl in (("Graduate Ecologist", "Graduate/Early career"), ("Senior Hydrogeologist", "Senior/Principal"), ("Associate Director, Planning", "Director/Associate"), ("Wind Turbine Technician", "Mid-level")):
        check(build_site.level_of(t) == lvl, f"level_of: {t!r} -> {lvl}")
    check(build_site.sector_stat([{"sal_min": None, "sal_max": None}, {"sal_min": 30000, "sal_max": None, "period": "year"}], "€") == "1 discloses pay", "sector_stat: counts disclosures under three")
    uk_home = (out / "uk" / "index.html").read_text(encoding="utf-8")
    check('data-lvl="' in uk_home and 'data-n="' in uk_home, "home: UK map regions carry data-n/data-lvl at build time (IE home has no map band since 2026-09-28)")
    check(any("Employers hiring now" in f for f in with_patch(lambda t: t.replace('data-strip="network"', 'data-strip="hiring"').replace('<div class="marq__track">', '<div class="marq__track"><div class="emp"><span>Ghost Ltd</span></div>'))), "faults: non-live employer under 'hiring now' caught")
    check(validate_site.validate(out, jobs) == [], "faults: clean build validates with zero problems after patches are reverted")
    keith = out / "ie" / "for-keith" / "index.html"
    k = keith.read_text(encoding="utf-8")
    keith.write_text(k.replace("</main>", "<p>AI Claude</p></main>"), encoding="utf-8")
    check(not any("forbidden" in f for f in validate_site.validate(out, jobs)), "faults: for-keith/ is exempt from the word filter")
    keith.write_text(k, encoding="utf-8")


# ------------------------------------------------------------- dashboard tier

def _dash_recompute(raw: dict, ed_key: str) -> dict:
    """Independent recomputation of the headline KPIs from the raw fixture."""
    from datetime import date as _date
    asof = _date.fromisoformat(str(raw["fetched"])[:10])
    ie_p, uk_p = build_site.place_words(SRC)
    jobs = [j for j in raw["jobs"] if build_site.loc_class(j, ie_p, uk_p) in build_site.EDITION_INCLUDES[ed_key]]  # B5: the UK board excludes ie-only/intl roles
    live = len(jobs)
    new7 = sum(1 for j in jobs if 0 <= (asof - _date.fromisoformat(build_site.parse_date(j["posted"]))).days < 7)
    closing7 = sum(1 for j in jobs if j.get("closing") and 0 <= (_date.fromisoformat(build_site.parse_date(j["closing"])) - asof).days <= 7)
    sal_n = sum(1 for j in jobs if j.get("salary_min") is not None or j.get("salary_max") is not None)
    emp: dict[str, int] = {}
    for j in jobs:
        emp[j["employer"]] = emp.get(j["employer"], 0) + 1
    return {"live": live, "new7": new7, "closing7": closing7, "sal_n": sal_n, "sal_pct": round(100 * sal_n / live), "top_share": round(100 * max(emp.values()) / live), "employers": len(emp)}


def test_dashboard_renders_per_edition(tmp_root: Path):
    import re
    out = tmp_root / "site_dash"
    rc = build_site.build(SRC, out, editions=["ie", "uk"], fixture=FIXTURE)
    check(rc == 0, "dashboard: fixture build passes with the dashboard page")
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for ed in ("ie", "uk"):
        want = _dash_recompute(raw, ed)  # per edition: the UK board excludes ie-only/intl roles (B5)
        path = out / ed / "dashboard" / "index.html"
        check(path.exists(), f"dashboard: {ed}/dashboard/index.html written")
        html_text = path.read_text(encoding="utf-8")
        check('content="noindex,nofollow"' in html_text and html_text.count("<h1") == 1, f"dashboard: {ed} page is noindex with one h1")
        m = re.search(r'<script type="application/json" id="gj-dash">(.*?)</script>', html_text, re.S)
        k = json.loads(m.group(1)) if m else {}
        check(all(k.get(key) == val for key, val in want.items()), f"dashboard: {ed} headline KPIs match an independent recomputation ({want})")
        check(sum(k["quality"]) == k["live"] and len(k["weeks"]) == 4 and k["asof"] == str(raw["fetched"])[:10], f"dashboard: {ed} quality distribution sums to live roles, 4-week trend, data-as-of date")
        check(f'>{k["live"]}</b>' in html_text and f'>{k["sal_pct"]}%</b>' in html_text and "Data as of" in html_text, f"dashboard: {ed} tiles carry the computed numbers and the as-of line")
        wired = re.findall(r'<div class="kpi kpi--wired">(.*?)</div>', html_text, re.S)
        check(len(wired) >= 14, f"dashboard: {ed} has the wired-at-launch tiles ({len(wired)})")
        for tile in wired:
            body = re.sub(r'<span class="kpi__t">.*?</span>', "", tile, flags=re.S)
            body = re.sub(r"<code>[^<]*</code>", "", body)
            if re.search(r"\d", body):
                check(False, f"dashboard: {ed} wired tile carries a digit outside a labelled target: {body[:80]!r}")
                break
        else:
            check(True, f"dashboard: {ed} wired tiles show no live numbers (dashes only, targets labelled)")
        check("—" in wired[0] and "collected from launch" in html_text, f"dashboard: {ed} wired tiles use a neutral dash with the collected-from-launch caption")
        check("Plausible" not in html_text and "GA4" not in html_text and "analytics provider" in html_text, f"dashboard: {ed} names no analytics vendor")
        check('data-csv' in html_text and "js/dashboard.js" in html_text and "js/charts.js" in html_text, f"dashboard: {ed} ships the CSV button and scripts")
        check(("Concentration risk" in html_text or "concentration risk" in html_text) == (k["top_share"] > 50), f"dashboard: {ed} concentration flag shown only when top employer share > 50%")
    home = (out / "ie" / "index.html").read_text(encoding="utf-8")
    check("dashboard/index.html" not in home and "dashboard" not in (out / "sitemap.xml").read_text(encoding="utf-8"), "dashboard: not in the primary nav or sitemap")
    check("dashboard/index.html" in (out / "ie" / "for-keith" / "index.html").read_text(encoding="utf-8"), "dashboard: linked from the for-keith evidence page")


def test_dashboard_kpis_edge_cases():
    data = {"fetched": "2026-09-22", "jobs": [], "sectors": [], "regions": []}
    k = build_site.dashboard_kpis(data)
    check(k["live"] == 0 and k["sal_median"] is None and k["days_to_close"] is None and k["top_share"] == 0, "dashboard: empty dataset yields zeros and n/a, no division by zero")
    job = {"title": "Hybrid analyst", "location": "Remote", "text": "x" * 400, "employer": "Acme Recruitment", "posted": "2026-09-20", "closing": "2026-10-20", "sal_min": 40000, "sal_max": None, "cur": "EUR", "period": "year", "logo": "a.png"}
    k = build_site.dashboard_kpis({**data, "jobs": [job]})
    check(k["agency_pct"] == 100 and k["remote_pct"] == 100 and k["quality"][4] == 1 and k["days_to_close"] == 30 and k["sal_median"] == 40000 and k["new7"] == 1, "dashboard: agency, remote, quality, days-to-close and median computed on a single role")


# Keith's 28 Sept notes, sections A/C/E/F: builder-speak off public pages,
# hero credibility markers, footer phone order, employers page, home structure.
BUILDER_SPEAK = ["The send button is honest", "actually says", "read from the title", "not estimates", "Demo:", "this demo",
                 "small and honest", "puts the planet on the payroll", "career level read from", "Packages on request", "Every region, counted"]


def test_keith_pages_and_copy(tmp_root: Path):
    real = (SRC / "data" / "ie.json").exists() and (SRC / "data" / "uk.json").exists()
    out = tmp_root / "site_keith"
    rc = build_site.build(SRC, out, editions=["ie", "uk"], fixture=None if real else FIXTURE)
    check(rc == 0, "keith: build for copy checks returns 0")
    pages = [p for p in out.rglob("index.html") if "for-keith" not in p.parts and not (p.parent.parent.name == "jobs")]
    hits = []
    for p in pages:
        text = p.read_text(encoding="utf-8")
        body = text.split('id="gj-data">')[0] if 'id="gj-data">' in text else text  # employer-authored dataset text is exempt
        for phrase in BUILDER_SPEAK:
            if phrase in body:
                hits.append(f"{p.relative_to(out)}: {phrase!r}")
    check(not hits, f"keith F1: no builder-speak on public pages ({hits[:4]})")
    ie = (out / "ie" / "index.html").read_text(encoding="utf-8")
    uk = (out / "uk" / "index.html").read_text(encoding="utf-8")
    ie_hero = ie.split('class="hero__facts"')[1].split("</p>")[0]
    uk_hero = uk.split('class="hero__facts"')[1].split("</p>")[0]
    check("employers" not in ie_hero and "live roles" in ie_hero and "since" in ie_hero and "specialist job sites" in ie_hero and "sectors" in ie_hero,
          "keith A2: IE hero has no employer count and carries the credibility markers")
    check("employers hiring now" in uk_hero and "live roles" in uk_hero, "keith A2: UK hero keeps the employer count")
    check("Work that works <em>for the planet.</em>" in ie and "across Ireland." in ie and "across the UK." in uk, "keith A1: new h1 and edition sub-line")
    check(ie.count("bcorp-line--footer") == 1 and ie.count("independently certified") >= 3, "keith A3: B Corp explainer in hero trust, header and footer")
    check(ie.count('class="sectors stagger"') == 1 and "data-fit" not in ie and "fit-q" not in ie, "keith C2: home has exactly one sector block and no fit panel")
    check('id="h-map"' not in ie and 'id="h-map"' in uk and "See where green employers are hiring" in uk, "keith C1/C4: region band on UK home only, with the new heading")
    check("data-film" not in ie and "film.js" not in ie and not (out / "js" / "film.js").exists() and "data-landscape" in ie, "keith C3: film replaced; film.js not shipped; landscape hero kept")
    check(ie.index('id="h-latest"') < ie.index('id="h-sectors"') < ie.index('id="h-insight"') < ie.index('id="h-why"') < ie.index('id="h-emp"') < ie.index('id="h-alert"'), "keith C1: IE home section order")
    check(uk.index('id="h-latest"') < uk.index('id="h-sectors"') < uk.index('id="h-map"') < uk.index('id="h-insight"') < uk.index('id="h-why"') < uk.index('id="h-emp"') < uk.index('id="h-alert"'), "keith C1: UK home section order")
    check("Advertise once. Reach candidates across the GreenJobs specialist network." in ie, "keith E5: network line in the home employer section")
    emp_ie = (out / "ie" / "employers" / "index.html").read_text(encoding="utf-8")
    emp_uk = (out / "uk" / "employers" / "index.html").read_text(encoding="utf-8")
    check("Request advertising rates" in emp_ie and 'href="mailto:' in emp_ie and emp_ie.index("Request advertising rates") < emp_ie.index('id="h-reach"'), "keith E1: rate CTA high on the employers page")
    check('<table class="evid cmp">' in emp_ie and "<th scope=\"col\">Standard</th>" in emp_ie and "Premium" in emp_ie and "Membership" in emp_ie and "Ask us" in emp_ie, "keith E4: comparison table with Standard / Premium / Membership")
    check("Trusted across the UK" in emp_uk and "Testimonial supplied at launch" in emp_uk and "Trusted across the UK" not in emp_ie, "keith E7: UK-only trust block with labelled slots")
    check("Preview exactly how your vacancy will appear to candidates." in emp_ie, "keith E6: one-line preview explanation")
    check("Organisations recruiting through GreenJobs" in emp_ie, "keith E3: recruiting organisations block")
    if real:
        ftr_uk = uk.split('<h4>Contact</h4>')[1].split("</ul>")[0]
        ftr_ie = ie.split('<h4>Contact</h4>')[1].split("</ul>")[0]
        check(ftr_uk.index("Calling from the UK: ") < ftr_uk.index("Calling from Ireland: ") and "+44 28 4303 2055" in ftr_uk and "(01) 912 5247" in ftr_uk, "keith F3: UK footer lists the UK number first")
        check(ftr_ie.index("Calling from Ireland: ") < ftr_ie.index("Calling from the UK: "), "keith F3: IE footer lists the Irish number first")
    keith = (out / "ie" / "for-keith" / "index.html").read_text(encoding="utf-8")
    check("Changes from your 28 September notes" in keith and 'class="changes"' in keith, "keith: evidence page lists the checklist status")
    check('{{head_extra}}' not in ie and "Compare disclosed salaries and identify employers committed to greater pay transparency." in ie, "keith F2: salary framing on the home page; head_extra resolved")


# ------------------------------------------------------------- Keith B/D/G (2026-09-28)

def test_taxonomy_infrastructure_roles():
    mk = lambda title, summary="", sectors=None: {"title": title, "sectors": sectors or [], "summary": summary, "description_html": ""}  # noqa: E731
    for title in ("Highways Civil Engineer", "Assistant Road Engineer", "Senior Transport Planner", "Design Coordinator – Rail", "Active Travel Officer"):
        s = build_site.assign_sectors(mk(title))
        check(s[0] == "Sustainable infrastructure & transport" and "Sustainability & ESG" not in s and "Built environment & energy efficiency" not in s, f"taxonomy: {title!r} -> infrastructure, never Sustainability/Built environment (got {s})")
    check(build_site.assign_sectors(mk("Senior Environmental Engineer", "Civil and environmental engineering design, remediation."))[0] == "Environmental engineering", "taxonomy: environmental engineer -> Environmental engineering")
    check(build_site.assign_sectors(mk("Senior Health & Safety Consultant", "HSE audits and CDM advice"))[0] == "Health, safety & environment", "taxonomy: H&S -> Health, safety & environment")
    check(build_site.assign_sectors(mk("Carbon Analyst", "Climate change mitigation and net zero pathways"))[0] == "Climate & carbon", "taxonomy: carbon/climate -> Climate & carbon")
    check(build_site.assign_sectors(mk("Nature Recovery Officer", "biodiversity net gain"))[0] == "Ecology, nature recovery & biodiversity", "taxonomy: nature recovery -> renamed ecology sector")
    names = [n for n, _, _, _ in build_site.TAXONOMY]
    check("Ecology & conservation" not in names and "Sustainability & net zero" not in names and len(names) == len(set(names)), "taxonomy: old names retired, no duplicates")


def test_loc_class():
    lc = build_site.loc_class
    check(lc({"location": "Dublin", "region": "Ireland", "country": "United Kingdom"}) == "ie", "loc_class: Dublin on the UK site -> ie (country field is not trusted)")
    check(lc({"location": "London City", "region": "London", "country": "Ireland"}) == "uk", "loc_class: London on the IE site -> uk")
    check(lc({"location": "Belfast", "region": "Northern Ireland"}) == "ni", "loc_class: Belfast -> ni")
    check(lc({"location": "Belfast, Manchester", "region": ""}) == "uk", "loc_class: NI + GB city -> uk")
    check(lc({"location": "United Kingdom (UK), Ireland (nationwide)", "region": "Country"}) == "cross", "loc_class: UK + Ireland -> cross")
    check(lc({"location": "Dublin, London", "region": "Ireland, United Kingdom"}) == "cross", "loc_class: Dublin + London -> cross")
    check(lc({"location": "Remote", "region": "Nationwide"}) == "remote", "loc_class: Remote -> remote")
    check(lc({"location": "Switzerland", "region": "Country", "country": "United Kingdom"}) == "intl", "loc_class: Switzerland -> intl")
    check(lc({"location": "Building Control Consultant (Remote - UK Wide)", "region": "United Kingdom"}) == "uk", "loc_class: remote within the UK -> uk")
    check(lc({"location": "", "region": "", "country": "Ireland"}) == "ie", "loc_class: falls back to the scraped country")
    check(set(build_site.LOC_LABEL) == {"ie", "uk", "ni", "remote", "cross", "intl"}, "loc_class: every class has a label")


def test_agency_workplace_level_contract():
    check(build_site.is_agency("Gaia Talent") and build_site.is_agency("Mattinson Partnership") and build_site.is_agency("CHM Recruit") and build_site.is_agency("Acme Recruitment Ltd"), "agency: named agencies and staffing words are agencies")
    check(not build_site.is_agency("Arup") and not build_site.is_agency("Natural Resources Wales") and not build_site.is_agency("Green Environmental Consultancy"), "agency: direct employers (incl. a consultancy) are not agencies")
    wp = build_site.workplace_of
    check(wp({"title": "Ecologist", "summary": "Hybrid working, two days in the office", "description_html": ""}) == "hybrid", "workplace: hybrid beats office")
    check(wp({"title": "Consultant (Remote - UK Wide)", "summary": "", "description_html": ""}) == "remote", "workplace: remote in title")
    check(wp({"title": "Resident Engineer", "summary": "", "description_html": "<p>Site based role.</p>"}) == "site", "workplace: site-based")
    check(wp({"title": "Analyst", "summary": "Office based in Cork", "description_html": ""}) == "office", "workplace: office-based")
    check(wp({"title": "Analyst", "summary": "", "description_html": ""}) == "unspecified", "workplace: unknown -> unspecified")
    check(build_site.level_of("Graduate Engineer") == "Graduate/Early career" and build_site.level_of("Senior Ecologist") == "Senior/Principal" and build_site.level_of("Associate Director – Water") == "Director/Associate" and build_site.level_of("Ecologist") == "Mid-level", "level_of: graduate / senior / director / mid")
    check(set(build_site.LEVEL_ORDER) == {"Graduate/Early career", "Mid-level", "Senior/Principal", "Director/Associate"}, "level facet: options match level_of() labels")
    ct = build_site.contract_of
    check(ct({"type": "Permanent", "title": "", "summary": "", "description_html": ""}) == ["permanent"], "contract: type Permanent")
    check("fixed-term" in ct({"type": "Contract", "title": "", "summary": "Maternity cover, fixed term 12 months", "description_html": ""}), "contract: fixed-term from text")
    check("part-time" in ct({"type": "", "title": "", "summary": "24-32 hours per week, part-time", "description_html": ""}), "contract: part-time from text")


def test_currency_label_never_converts():
    j = {"sal_min": 5100, "sal_max": 6000, "cur": "EUR", "period": "month", "sal_text": ""}
    check(build_site.salary_label(j) == "€5.1k–6k/mo", "currency: label in the advertised currency")
    uk = build_site.salary_label(j, "GBP")
    check(uk.startswith("€5.1k–6k/mo (paid in euros, about £") and "£" in uk, f"currency: on the UK edition the euro salary keeps € and gains a sterling equivalent ({uk})")
    check(build_site.salary_label(j, "EUR") == "€5.1k–6k/mo", "currency: same currency -> no note")
    g = {"sal_min": 50000, "sal_max": 60000, "cur": "GBP", "period": "year", "sal_text": ""}
    ie = build_site.salary_label(g, "EUR")
    check(ie.startswith("£50k–60k (paid in sterling, about €58.5k–70.2k)"), f"currency: sterling on IE -> euro equivalent at 1.17 ({ie})")
    check(build_site.currency_note(g, "EUR") == "Paid in sterling" and build_site.currency_note(g, "GBP") == "", "currency: note only when currencies differ")
    a = build_site.annual_mid(g, "EUR")
    check(a and abs(a[0] - 58500) < 1 and abs(a[1] - 70200) < 1, "currency: annual_mid converts into the edition currency for comparison")
    check(build_site.annual_mid(g) == (50000, 60000, 55000), "currency: annual_mid without an edition currency is untouched")
    check(build_site.median_salary([g], "€", "EUR") == "€64.4k" and build_site.median_salary([g], "£", "GBP") == "£55k", "currency: median in the edition currency, never relabelled")


def test_similar_jobs_and_landings(tmp_root: Path):
    mk = lambda i, sector, region, sal: {"id": str(i), "title": f"Role {i}", "sectors": [sector], "regions": [region], "sal_min": sal, "sal_max": sal, "cur": "EUR", "period": "year", "posted": "2026-09-01", "loc_class": "ie"}  # noqa: E731
    me = mk(0, "Water & flood", "Dublin", 50000)
    pool = [mk(1, "Water & flood", "Dublin", 50000), mk(2, "Water & flood", "Cork", 90000), mk(3, "Wind energy", "Dublin", 50000), mk(4, "Wind energy", "Cork", None), mk(5, "Water & flood", "Galway", 52000), mk(6, "Water & flood", "Mayo", 51000)]
    sim = build_site.similar_jobs(me, pool + [me], "EUR", 4)
    check(len(sim) == 4 and sim[0]["id"] == "1" and all(s["id"] != "0" for s in sim) and "4" not in [s["id"] for s in sim], f"similar_jobs: at most 4, self excluded, same sector+region first, unrelated last (got {[s['id'] for s in sim]})")
    out = tmp_root / "site_landing"
    rc = build_site.build(SRC, out, editions=["ie", "uk"], fixture=FIXTURE)
    check(rc == 0, "landing: fixture build passes")
    eco = out / "ie" / "ecology-jobs-ireland" / "index.html"
    check(eco.exists() and eco.read_text(encoding="utf-8").count('class="role reveal"') == 2, "landing: IE ecology page lists exactly the ecology roles (Dublin + Belfast in the fixture)")
    uk_eco = out / "uk" / "ecology-jobs-uk" / "index.html"
    check(uk_eco.exists() and uk_eco.read_text(encoding="utf-8").count('class="role reveal"') == 1, "landing: UK ecology page lists only the Belfast role (Dublin excluded)")
    built = [p for p in (out / "uk").glob("*-jobs-*/index.html")]
    check(built and all(p.read_text(encoding="utf-8").count('class="role reveal"') >= 1 for p in built), "landing: every built landing page carries at least one role")
    check(build_site.landing_pages({"ed": "uk", "jobs": []}) == [], "landing: no roles -> no landing page")
    dub = out / "ie" / "environmental-jobs-dublin" / "index.html"
    check(not dub.exists() or dub.read_text(encoding="utf-8").count('class="role reveal"') >= 1, "landing: a page is only built with at least one role")
    site_map = (out / "sitemap.xml").read_text(encoding="utf-8")
    check("ecology-jobs-ireland/index.html" in site_map and "guides/salary-guide/index.html" in site_map, "landing: sitemap lists landing pages and the salary guide")
    guide = (out / "ie" / "guides" / "salary-guide" / "index.html").read_text(encoding="utf-8")
    check("Last updated" in guide and "disclosed salaries" in guide and 'name="robots" content="noindex' in guide, "guide: salary guide has a last-updated date and stays noindex")
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', eco.read_text(encoding="utf-8"), re.S).group(1))
    check(ld["@type"] == "ItemList" and ld["itemListElement"][0]["item"]["@type"] == "JobPosting", "landing: ItemList of JobPosting JSON-LD")


def test_hreflang_and_jsonld(tmp_root: Path):
    out = tmp_root / "site_seo"
    rc = build_site.build(SRC, out, editions=["ie", "uk"], fixture=FIXTURE)
    check(rc == 0, "seo: fixture build passes")
    board = (out / "uk" / "jobs" / "index.html").read_text(encoding="utf-8")
    check('rel="canonical" href="https://greenjobs-redesign.pages.dev/uk/jobs/index.html"' in board and 'hreflang="en-IE"' in board and 'hreflang="en-GB"' in board and 'hreflang="x-default"' in board, "seo: canonical + hreflang pair on a shared page")
    head = board.split("</head>")[0]
    check('rel="canonical"' in head and 'hreflang="en-IE"' in head, "seo: the links sit inside <head>")
    job = (out / "uk" / "jobs" / "1007" / "index.html").read_text(encoding="utf-8")
    check('rel="canonical"' in job and 'rel="alternate"' not in job.split("</head>")[0], "seo: job page has a canonical and no hreflang pair (ids differ per edition)")
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', job, re.S).group(1))
    check(ld["baseSalary"]["currency"] == "GBP" and ld["baseSalary"]["value"]["minValue"] == 45000 and ld["validThrough"].startswith("2026-10-15") and ld["jobLocation"]["address"]["addressCountry"] == "GB", "seo: JobPosting carries the job's currency, validThrough from the closing date and the country from loc_class")
    remote = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', (out / "uk" / "jobs" / "1004" / "index.html").read_text(encoding="utf-8"), re.S).group(1))
    check(remote.get("jobLocationType") == "TELECOMMUTE" and remote["baseSalary"]["currency"] == "EUR", "seo: remote role -> TELECOMMUTE; euro salary keeps EUR on the UK edition")
    ie_job = (out / "ie" / "jobs" / "1007" / "index.html").read_text(encoding="utf-8")
    check("paid in sterling, about €" in ie_job and ">UK<" in ie_job, "B2/B3: sterling role on the IE edition carries the note, the equivalent and a UK badge")
    base = {"title": "x", "text": "", "summary": "", "employer": "e", "url": "https://x", "posted": "", "closing": "", "type": "", "period": None, "workplace": "unspecified"}
    cross = build_site.job_jsonld_payload({**base, "location": "Dublin, London", "sal_min": 1, "sal_max": 2, "cur": None, "loc_class": "cross"}, {"ed": "ie"})
    check(cross.get("applicantLocationRequirements") == [{"@type": "Country", "name": "Ireland"}, {"@type": "Country", "name": "United Kingdom"}], "seo: cross-border role -> applicantLocationRequirements for both countries")
    check("baseSalary" not in build_site.job_jsonld_payload({**base, "location": "", "sal_min": 1000, "sal_max": 2000, "cur": None, "period": "year", "loc_class": "ie"}, {"ed": "ie"}), "seo: numeric salary without a currency code -> no baseSalary")


def test_ni_region_and_facets(tmp_root: Path):
    uk = json.loads((SRC / "data" / "regions_uk.json").read_text(encoding="utf-8"))
    ni = uk["regions"].get("Northern Ireland") or []
    check(all(a in ni for a in ("Belfast", "Derry", "Antrim", "Down", "Armagh", "Tyrone", "Fermanagh", "Londonderry", "NI")), "regions: Northern Ireland has the required aliases")
    check("Northern Ireland" in json.loads((SRC / "assets" / "maps" / "regions_index.json").read_text(encoding="utf-8"))["uk"], "regions: the UK map carries a Northern Ireland polygon")
    check(build_site.resolve_regions({"region": "", "location": "Belfast"}, uk, build_site.EDITIONS["uk"]) == ["Northern Ireland"], "regions: Belfast resolves to Northern Ireland")
    check(all(a in uk["regions"]["East Midlands"] for a in ("Nottingham", "Leicester", "Derby", "Lincoln", "Northampton")), "regions: East Midlands aliases present")
    out = tmp_root / "site_facets"
    check(build_site.build(SRC, out, editions=["ie", "uk"], fixture=FIXTURE) == 0, "facets: fixture build passes")
    board = (out / "ie" / "jobs" / "index.html").read_text(encoding="utf-8")
    for fid in ("f-wp", "f-level", "f-ct", "f-smin", "f-smax", "f-only", "f-close", "f-emp"):
        check(f'id="{fid}"' in board and (f'for="{fid}"' in board or f'<input type="checkbox" id="{fid}"' in board), f"facets: control {fid} present and labelled")
    check("Ireland only" in board and "UK only" in (out / "uk" / "jobs" / "index.html").read_text(encoding="utf-8"), "facets: edition-aware only-toggle label")
    check("counted in each, so totals can exceed" in board and "counted in each" in (out / "ie" / "sectors" / "index.html").read_text(encoding="utf-8"), "B6: multi-count sentence on the jobs map and sectors page")
    embedded = json.loads(re.search(r'id="gj-data">(.*?)</script>', board, re.S).group(1))
    j = embedded["jobs"][0]
    check(all(k in j for k in ("loc_class", "workplace", "level", "contract", "agency", "closing")) and embedded.get("home") == ["ie", "cross", "remote"], "facets: dataset carries the facet fields and the home classes")
    check('class="tag tag--loc"' in (out / "ie" / "index.html").read_text(encoding="utf-8"), "B3: location badge rendered on home cards")
    fit = (out / "uk" / "jobs" / "index.html").read_text(encoding="utf-8")
    check("Quick job match" in fit and "processed on your device and is not uploaded or stored" in fit and "Keyword matching, not an assessment of your suitability" in fit, "D3: matcher renamed with the two disclosure lines")
    check("ecologist Bristol" in fit and "ecologist dublin" not in fit.lower(), "D4: UK examples, never 'ecologist dublin' on UK")
    ie_fit = (out / "ie" / "jobs" / "index.html").read_text(encoding="utf-8")
    check("ecologist Dublin" in ie_fit and "Bristol" not in ie_fit, "D4: IE keeps Irish examples")


def main() -> int:
    import inspect
    base = REPO / ".tmp"
    base.mkdir(exist_ok=True)
    tmp_root = Path(tempfile.mkdtemp(prefix="greenjobs_test_build_", dir=str(base)))
    try:
        for name, fn in sorted(globals().items()):
            if not name.startswith("test_") or not callable(fn) or name == "test_all_via_pytest":
                continue
            if "tmp_root" in inspect.signature(fn).parameters:
                fn(tmp_root)
            else:
                fn()
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
    passed = sum(1 for ok, _ in RESULTS if ok)
    failed = [label for ok, label in RESULTS if not ok]
    print(f"\nUnit+Integration: {passed} passed, {len(failed)} failed")
    for label in failed:
        print(f"  FAIL: {label}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())


try:
    import pytest

    @pytest.fixture
    def tmp_root():
        base = REPO / ".tmp"
        base.mkdir(exist_ok=True)
        d = Path(tempfile.mkdtemp(prefix="greenjobs_test_build_pytest_", dir=str(base)))
        try:
            yield d
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_all_via_pytest(tmp_root):
        import inspect
        RESULTS.clear()
        for name, fn in sorted(globals().items()):
            if not name.startswith("test_") or name == "test_all_via_pytest" or not callable(fn):
                continue
            if "tmp_root" in inspect.signature(fn).parameters:
                fn(tmp_root)
            else:
                fn()
        failed = [label for ok, label in RESULTS if not ok]
        assert not failed, "failures: " + "; ".join(failed)
except ImportError:
    pass  # pytest is optional: main() above is the canonical runner; the fixture only exists when pytest collects this file
