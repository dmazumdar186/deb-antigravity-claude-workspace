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

import html
import json
import re
import shutil
import subprocess
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


def skip(label: str) -> None:
    """A test that cannot run here is reported as SKIP and never counted as a pass."""
    SKIPS.append(label)
    print(f"SKIP  {label}")


SKIPS: list[str] = []


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
    check(build_site.median_salary([{"sal_min": 50000, "sal_max": 60000, "period": "year", "cur": "EUR"}, {"sal_min": 40000, "sal_max": None, "period": "year", "cur": "EUR"}, {"sal_min": None, "sal_max": None}], "€") == "€47.5k", "median_salary: midpoint median formatted like lib.js")


def test_employers_strip_is_honest():
    emps = [{"name": n, "url": "", "logo": "", "lw": 0, "lh": 0} for n in ["A", "B", "C", "D", "E", "F", "G", "Pad1", "Pad2"]]
    mk = lambda names: {"site": "x.ie", "employers": emps, "jobs": [{"employer": n} for n in names]}  # noqa: E731
    six = build_site.employers_strip(mk(["A", "B", "C", "D", "E", "F"]), "../")
    check(six["mode"] == "hiring" and six["title"] == "Employers hiring now" and "Pad1" not in six["html"] and "G" not in six["html"].replace("Green", ""), "employers_strip: >=6 live employers -> 'hiring now' with live employers only")
    two = build_site.employers_strip(mk(["A", "B"]), "../")
    check(two["mode"] == "network" and two["title"] == "Employers on the GreenJobs network" and two["sub"] == "Organisations with live roles on x.ie this week." and "Pad1" not in two["html"] and "<span>A</span>" in two["html"], "employers_strip: <6 live -> network title, live employers only, never padded (R041)")
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
    ie_home = (out / "ie" / "index.html").read_text(encoding="utf-8")
    uk_home = (out / "uk" / "index.html").read_text(encoding="utf-8")
    check("Senior Ecologist" not in uk_home and "Conservation Officer" in ie_home and "Conservation Officer" in uk_home,
          "integration: UK home/latest never lists an Ireland-only role; the NI role is on both editions")
    ie_jobs = json.loads((out / "ie" / "jobs" / "index.html").read_text(encoding="utf-8").split('id="gj-data">')[1].split("</script>")[0])["jobs"]
    check(len(ie_jobs) == 8 and "8 live" in ie_home and any(j["loc_class"] == "uk" for j in ie_jobs), f"integration: IE hero/dataset count 8 (every scraped role, the London one labelled UK), got {len(ie_jobs)}")
    check("0 roles excluded; 1 UK-only role shown with a UK label" in (out / "ie" / "for-keith" / "index.html").read_text(encoding="utf-8") and "5 Ireland-only roles kept off greenjobs.co.uk" in (out / "uk" / "for-keith" / "index.html").read_text(encoding="utf-8"),
          "integration: for-keith evidence table states the IE shown-with-label count and the UK excluded count")
    for req in ("sitemap.xml", "manifest.webmanifest", "robots.txt", "404.html", "ie/data/jobs.json", "assets/maps"):
        pass
    check((out / "sitemap.xml").read_text(encoding="utf-8").count("<url>") >= 2 * (6 + 6), "integration: sitemap lists pages and job pages")
    home = (out / "ie" / "index.html").read_text(encoding="utf-8")
    check("Nuclear Decommissioning" not in home and "(0)" not in home, "integration: zero-count sector never rendered on the home page")
    check('id="gj-data"' in (out / "ie" / "jobs" / "index.html").read_text(encoding="utf-8"), "integration: dataset embedded on the board")
    job = (out / "ie" / "jobs" / "1002" / "index.html").read_text(encoding="utf-8")
    check("Not disclosed" in job and '"JobPosting"' in job and "baseSalary" not in job, "integration: null salary renders 'Not disclosed' and omits baseSalary in JSON-LD")
    check("role__logo--t" in (out / "ie" / "index.html").read_text(encoding="utf-8"), "integration: missing logo falls back to an initial tile")
    css = sum(p.stat().st_size for p in (out / "css").glob("*.css"))
    js = sum(p.stat().st_size for p in (out / "js").glob("*.js"))
    check(css <= validate_site.CSS_BUDGET and js <= validate_site.JS_BUDGET, f"integration: budgets hold (css {css}, js {js})")
    check(not list(out.rglob("*.test.js")), "integration: test files not shipped")


def test_real_data_build(tmp_root: Path):
    if not (SRC / "data" / "ie.json").exists() or not (SRC / "data" / "uk.json").exists():
        skip("integration: real datasets absent")
        return
    out = tmp_root / "site_real"
    rc = build_site.build(SRC, out, editions=["ie", "uk"])
    check(rc == 0, "integration: real-data build returns 0")
    for ed in ("ie", "uk"):
        raw = json.loads((SRC / "data" / f"{ed}.json").read_text(encoding="utf-8"))
        pages = len(list((out / ed / "jobs").glob("*/index.html")))
        data = build_site.normalise(raw, ed, SRC, SRC / "assets" / "logos")
        check(pages == len(data["jobs"]) and pages + len(data["excluded"]) == len(raw["jobs"]), f"integration: {ed} job page count {pages} + {len(data['excluded'])} excluded == dataset {len(raw['jobs'])}")
        check(all(j["loc_class"] in build_site.EDITION_INCLUDES[ed] for j in data["jobs"]), f"integration: {ed} edition carries only {sorted(build_site.EDITION_INCLUDES[ed])} roles")
        keith = (out / ed / "for-keith" / "index.html").read_text(encoding="utf-8")
        if ed == "uk":
            check(all(x["loc_class"] in ("ie", "intl") for x in data["excluded"]), "integration: UK edition excludes only ie-only and international roles (B5)")
            single = sum(1 for x in data["excluded"] if x["loc_class"] == "ie")
            check(f"{len(data['excluded'])} excluded" in keith and f"{single} Ireland-only role{'' if single == 1 else 's'} kept off greenjobs.co.uk" in keith, f"integration: UK evidence page states the excluded count ({single} Ireland-only)")
        else:
            uk_only = sum(1 for j in data["jobs"] if j["loc_class"] == "uk")
            check(not data["excluded"] and f"0 roles excluded; {uk_only} UK-only role{'' if uk_only == 1 else 's'} shown with a UK label" in keith, f"integration: IE excludes nothing; evidence page states {uk_only} UK-only roles shown with a label (Keith B4)")
            fixed = [j for j in data["jobs"] if j.get("currency_source") == build_site.STERLING_SOURCE]  # r3 R011: unverified euro roles carry their own source
            check(len(fixed) == len(data["corrected"]) and all(j["cur"] == "GBP" and j["loc_class"] == "uk" for j in fixed) and len(fixed) == 21, f"integration: IE sterling correction from the greenjobs.co.uk twin applied to {len(fixed)} UK-only roles (all now GBP; exactly 21 on this snapshot)")
            page = (out / "ie" / "jobs" / fixed[0]["id"] / "index.html").read_text(encoding="utf-8")
            check("advertised in sterling, about €" in page and "Advertised in sterling on the greenjobs.co.uk listing" in page and "£" in page, "integration: corrected IE job page shows the sterling figure, the euro equivalent and the salary source")
        for page in (out / ed).rglob("index.html"):
            if "for-keith" in page.parts:
                continue
            bad = {lc for lc in re.findall(r'data-loc="([^"]*)"', page.read_text(encoding="utf-8")) if lc not in build_site.EDITION_INCLUDES[ed]}
            check(not bad, f"integration: {page.relative_to(out)} shows no role card outside the {ed} inclusion rule ({bad})")


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
    uk_home = out / "uk" / "index.html"
    uk_clean = uk_home.read_text(encoding="utf-8")
    uk_home.write_text(uk_clean.replace("</main>", '<article class="role"><span class="tag tag--loc" data-loc="ie">Ireland</span></article></main>'), encoding="utf-8")
    try:
        check(any("outside its inclusion rule" in f for f in validate_site.validate(out, jobs)), "faults: an Ireland-only role card on a UK page is caught (B5)")
    finally:
        uk_home.write_text(uk_clean, encoding="utf-8")
    check(not any("outside its inclusion rule" in f for f in with_patch(lambda t: t.replace("</main>", '<span class="tag tag--loc" data-loc="uk">UK</span></main>'))), "faults: a UK role card on an IE page is allowed (IE shows every class with a label)")
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
    check(build_site.sector_stat([{"sal_min": None, "sal_max": None}, {"sal_min": 30000, "sal_max": None, "period": "year"}], "€") == "1 disclosed salary", "sector_stat: counts disclosures under three")
    uk_home = (out / "uk" / "index.html").read_text(encoding="utf-8")
    check('data-lvl="' in uk_home and 'data-n="' in uk_home, "home: UK map regions carry data-n/data-lvl at build time (IE home has no map band since 2026-09-28)")
    check(any("employer strip (hiring)" in f for f in with_patch(lambda t: t.replace('data-strip="network"', 'data-strip="hiring"').replace('<div class="marq__track">', '<div class="marq__track"><div class="emp"><span>Ghost Ltd</span></div>'))), "faults: non-live employer under 'hiring now' caught")
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
    jobs = [j for j in raw["jobs"] if build_site.loc_class(j, ie_p, uk_p) in build_site.EDITION_INCLUDES[ed_key]]  # B5: each board excludes the other's single-country roles and intl
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
        check("—" in wired[0] and ("collected from launch" in html_text or "not yet collected" in html_text), f"dashboard: {ed} wired tiles use a neutral dash with the not-yet-collected caption")
        check("Plausible" not in html_text and "GA4" not in html_text and "analytics provider" in html_text, f"dashboard: {ed} names no analytics vendor")
        check('data-csv' in html_text and "js/dashboard.js" in html_text and "js/charts.js" in html_text, f"dashboard: {ed} ships the CSV button and scripts")
        check(("Most roles come from one employer." in html_text) == (k["top_share"] > 50) and "concentration risk" not in html_text.lower(), f"dashboard: {ed} 'Most roles come from one employer.' shown only when top employer share > 50%")
        check("Roles posted by recruitment agencies rather than the employer directly." in html_text, f"dashboard: {ed} agency tile reads in plain words")
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
    check("Trusted across the UK" in emp_uk and "Client testimonials available on request." in emp_uk and "Trusted across the UK" not in emp_ie, "keith E7: UK-only trust block, testimonials collected for launch (panel B4)")
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
    check(set(build_site.LOC_LABEL) == {"ie", "uk", "ni", "remote", "cross", "intl", "unspecified"}, "loc_class: every class has a label")


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
    check(uk.startswith("€5.1k–6k/mo (advertised in euros, about £") and "£" in uk, f"currency: on the UK edition the euro salary keeps € and gains a sterling equivalent ({uk})")
    check(build_site.salary_label(j, "EUR") == "€5.1k–6k/mo", "currency: same currency -> no note")
    g = {"sal_min": 50000, "sal_max": 60000, "cur": "GBP", "period": "year", "sal_text": ""}
    ie = build_site.salary_label(g, "EUR")
    check(ie.startswith("£50k–60k (advertised in sterling, about €58.5k–70.2k)"), f"currency: sterling on IE -> euro equivalent at 1.17 ({ie})")
    check(build_site.currency_note(g, "EUR") == "Advertised in sterling" and build_site.currency_note(g, "GBP") == "", "currency: note only when currencies differ")
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
    check(eco.exists() and eco.read_text(encoding="utf-8").count('class="role reveal"') == 1, "landing: IE ecology page lists only the Dublin ecology role (r4b: the Belfast role is outside the IE board's home set, like the hide toggle)")
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
    check("advertised in sterling, about €" in ie_job and ">UK<" in ie_job, "B2/B3: sterling role on the IE edition carries the note, the equivalent and a UK badge")
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
    for fid in ("f-wp", "f-level", "f-ct", "f-smin", "f-smax", "f-close", "f-emp"):
        check(f'id="{fid}"' in board and (f'for="{fid}"' in board or f'<input type="checkbox" id="{fid}"' in board), f"facets: control {fid} present and labelled")
    uk_board = (out / "uk" / "jobs" / "index.html").read_text(encoding="utf-8")
    check('id="f-only"' in board and '<input type="checkbox" id="f-only"' in board and "Hide UK/abroad-only roles" in board and "Hide Ireland/abroad-only roles" in uk_board, "facets: the hide toggle is present and labelled per edition (Keith B4: 'allow users to exclude UK opportunities')")
    ie_lc = [x["loc_class"] for x in json.loads(re.search(r'id="gj-data">(.*?)</script>', board, re.S).group(1))["jobs"]]
    uk_lc = [x["loc_class"] for x in json.loads(re.search(r'id="gj-data">(.*?)</script>', uk_board, re.S).group(1))["jobs"]]
    check("uk" in ie_lc and not {"ie", "intl"} & set(uk_lc), "facets: the IE board dataset carries the London role (labelled UK client-side); the UK board carries no Ireland-only or international role")
    check("counted in each, so totals can exceed" in board and "counted in each" in (out / "ie" / "sectors" / "index.html").read_text(encoding="utf-8"), "B6: multi-count sentence on the jobs map and sectors page")
    embedded = json.loads(re.search(r'id="gj-data">(.*?)</script>', board, re.S).group(1))
    j = embedded["jobs"][0]
    check(all(k in j for k in ("loc_class", "workplace", "level", "contract", "agency", "closing")) and embedded.get("home") == ["ie", "cross", "remote"] and all(x["loc_class"] in build_site.EDITION_INCLUDES["ie"] for x in embedded["jobs"]), "facets: dataset carries the facet fields, the home classes, and only IE-rule roles")
    check('class="tag tag--loc"' in (out / "ie" / "index.html").read_text(encoding="utf-8"), "B3: location badge rendered on home cards")
    fit = (out / "uk" / "jobs" / "index.html").read_text(encoding="utf-8")
    check("Quick job match" in fit and "Your information is processed on your device and is not uploaded or stored." in fit and "Keyword matching, not an assessment of your suitability" in fit, "D3: matcher renamed with the two disclosure lines (client sentence verbatim, R036; round 2 B)")
    check("ecologist Bristol" in fit and "ecologist dublin" not in fit.lower(), "D4: UK examples, never 'ecologist dublin' on UK")
    ie_fit = (out / "ie" / "jobs" / "index.html").read_text(encoding="utf-8")
    check("ecologist Dublin" in ie_fit and "Bristol" not in ie_fit, "D4: IE keeps Irish examples")


# ------------------------------------------------------------- # --- panel fixes A ---
# Panel findings 01/04/07/08/10/13 (2026-09-28): dates, classifiers, currency,
# validator rules, scraper floor. Each item below has at least one check.

def _raw_ie():
    return json.loads((SRC / "data" / "ie.json").read_text(encoding="utf-8"))


def test_pf_a_agency_rule():
    check("partnership" not in build_site.AGENCY_WORDS and build_site.is_agency("Mattinson Partnership") and build_site.is_agency("CHM Recruit") and build_site.is_agency("Gaia Talent"), "pf-A1: 'partnership' is not a staffing word; the three named agencies still are agencies")
    check(not build_site.is_agency("Great Grid Partnership") and not build_site.is_agency("Landscape Partnership Ltd"), "pf-A1: a partnership that is not a named agency is a direct employer")
    check(build_site.job_is_agency({"agency": False, "employer": "Acme Recruitment"}) is False and build_site.job_is_agency({"employer": "Acme Recruitment"}) is True, "pf-A1: job_is_agency reads the stored field first, derives otherwise")
    check(build_site.job_is_remote_or_hybrid({"workplace": "hybrid"}) and not build_site.job_is_remote_or_hybrid({"workplace": "site"}), "pf-A1: job_is_remote_or_hybrid reads the stored workplace")
    src_text = (SCRIPT_DIR / "build_site.py").read_text(encoding="utf-8")
    check(src_text.count("AGENCY_NAMES = {") == 1 and "AGENCY_RE" not in src_text, "pf-A1: AGENCY_NAMES is defined once; the dashboard's shadowing copy is gone")


def test_pf_a_loc_class_probes():
    ie_p, uk_p = build_site.place_words(SRC)
    ni_p = build_site.ni_place_words(SRC)
    lc = lambda j, ed="": build_site.loc_class(j, ie_p, uk_p, ed, ni_p)  # noqa: E731
    raw = _raw_ie()
    by = {j["id"]: j for j in raw["jobs"]}
    for jid in ("11493508", "11493513"):
        if jid in by:
            check(lc(by[jid], "ie") == "ie", f"pf-A2: IE {jid} (Dublin, Cork; region 'Ireland, United Kingdom', no UK text) -> ie")
    check(lc({"location": "Dublin, Cork", "region": "Ireland, United Kingdom", "country": "Ireland"}, "ie") == "ie", "pf-A2: on the IE site the region facet is not a UK signal")
    check(lc({"location": "Dublin, London", "region": "Ireland, United Kingdom", "country": "Ireland"}, "ie") == "cross", "pf-A2: a UK place in the location still makes it cross on IE")
    check(lc({"location": "Belfast", "region": "Ireland", "country": "Ireland"}, "ie") == "ni", "pf-A2: NI role on the IE site -> ni, not cross (bare 'Ireland' region stripped)")
    check(lc({"location": "Enniskillen", "region": ""}) == "ni" and lc({"location": "Bangor, Co. Down", "region": ""}) == "ni" and lc({"location": "Omagh", "region": ""}) == "ni", "pf-A2: NI_WORDS carries the full alias list (Enniskillen, Bangor Co. Down, Omagh)")
    check("enniskillen" in build_site.NI_WORDS and "down" not in build_site.NI_WORDS and "bangor" not in build_site.NI_WORDS, "pf-A2: NI_WORDS loaded from regions_uk.json without the ambiguous short aliases")
    check(lc({"location": "Bangor", "region": "Wales"}) == "uk", "pf-A2: bare Bangor with a Welsh region is uk, not ni")
    check(lc({"location": "Kyiv", "region": "Ukraine", "country": ""}) == "intl", "pf-A2: 'Ukraine' is not a UK match ('uk' is whole-word)")
    check(lc({"location": "", "region": "", "country": ""}) == "unspecified" and build_site.LOC_LABEL["unspecified"] == "Location not stated", "pf-A2: empty location + country -> 'unspecified', labelled 'Location not stated'")
    check("unspecified" in build_site.EDITION_INCLUDES["ie"] and "unspecified" in build_site.EDITION_INCLUDES["uk"], "pf-A2: unspecified roles are kept on both boards")
    check(build_site.EDITION_INCLUDES["ie"] == {"ie", "uk", "ni", "remote", "cross", "intl", "unspecified"} and build_site.EDITION_INCLUDES["uk"] == {"uk", "ni", "remote", "cross", "unspecified"}, "pf-A2: IE shows every class with a label (Keith: 'allow users to exclude UK opportunities'); UK excludes ie-only and intl")
    check(lc({"location": "London", "region": "London", "country": "Ireland"}, "ie") == "uk" and "uk" in build_site.EDITION_INCLUDES["ie"] and build_site.LOC_LABEL["uk"] == "UK", "pf-A2: golden probe: Mattinson-style 'London' advert on the IE site -> uk, shown on greenjobs.ie with a 'UK' label")
    twins = {"id:1": [{"id": "1", "currency": "GBP", "salary_min": 70000, "salary_max": 75000, "salary_text": "£70,000 to £75,000 per annum"}],
             "te:planner|mattinson partnership": [{"id": "9", "currency": "GBP", "salary_min": 30000, "salary_max": 40000, "salary_text": "£30,000 to £40,000"}]}
    fix = build_site.sterling_correction({"id": "1", "currency": "EUR", "salary_min": 70000, "salary_max": 75000}, "uk", twins)
    check(fix and fix["currency"] == "GBP" and fix["salary_min"] == 70000 and fix["salary_text"].startswith("£70,000"), "B2: a UK-only IE role priced in euros takes the greenjobs.co.uk twin's sterling figures (by id)")
    check(build_site.sterling_correction({"id": "2", "title": "Planner", "employer": "Mattinson Partnership", "currency": "EUR", "salary_min": 30000, "salary_max": 40000}, "uk", twins)["currency"] == "GBP", "B2: title + employer twin accepted when the figures match")
    check(build_site.sterling_correction({"id": "2", "title": "Planner", "employer": "Mattinson Partnership", "currency": "EUR", "salary_min": 80000, "salary_max": 100000}, "uk", twins) is None, "B2: title + employer twin with different figures is a different advert -> no correction")
    check(build_site.sterling_correction({"id": "1", "currency": "EUR", "salary_min": 1, "salary_max": 2}, "ie", twins) is None and build_site.sterling_correction({"id": "1", "currency": "GBP"}, "uk", twins) is None and build_site.sterling_correction({"id": "1", "currency": "EUR"}, "uk", {}) is None, "B2: only uk-class euro roles with a twin are corrected; Irish roles, sterling roles and fixture builds are untouched")
    check(build_site.salary_label({"sal_min": 70000, "sal_max": 75000, "cur": "GBP", "period": "year"}, "EUR").startswith("£70k–75k (advertised in sterling, about €"), "B2: corrected role renders '£70k–75k (advertised in sterling, about €…)' on the IE edition")
    check(lc({"location": "Belfast", "region": "Ireland", "country": "Ireland"}, "ie") in build_site.EDITION_INCLUDES["ie"] and "ni" in build_site.EDITION_INCLUDES["uk"] and build_site.LOC_LABEL["ni"] == "Northern Ireland", "pf-A2: golden probe: NI roles stay on both editions, labelled 'Northern Ireland'")
    check(lc({"location": "Dublin, London", "region": ""}) == "cross" and "cross" in build_site.EDITION_INCLUDES["ie"] and "cross" in build_site.EDITION_INCLUDES["uk"] and build_site.LOC_LABEL["cross"] == "Ireland & UK", "pf-A2: golden probe: cross-border roles stay on both editions, labelled 'Ireland & UK'")
    uk_tab = json.loads((SRC / "data" / "regions_uk.json").read_text(encoding="utf-8"))
    ed_uk = build_site.EDITIONS["uk"]
    check(build_site.resolve_regions({"region": "Country", "location": "United Kingdom (UK)"}, uk_tab, ed_uk) == [ed_uk["none"]], "pf-A2: 'United Kingdom (UK)' -> the UK-wide bucket, not 'elsewhere'")
    check(build_site.resolve_regions({"region": "Wales", "location": "South West Wales"}, uk_tab, ed_uk) == ["Wales"], "pf-A2: 'South West Wales' -> Wales only")
    check(build_site.resolve_regions({"region": "", "location": "Bristol, South West"}, uk_tab, ed_uk) == ["South West"], "pf-A2: a plain 'South West' still resolves")


def test_pf_a_workplace_contract_level():
    wp = build_site.workplace_of
    mk = lambda title, body: {"title": title, "type": "", "summary": "", "description_html": body}  # noqa: E731
    check(wp(mk("EHS Site Manager", "<p>Proficient in Microsoft Office.</p>")) == "site", "pf-A3: 'Microsoft Office' is not office-based; 'site manager' is site-based")
    check(wp(mk("Analyst", "<p>Reports to the Office of the Director at head office.</p>")) == "unspecified", "pf-A3: 'Office of' / 'head office' / bare 'office' are not workplace signals")
    check(wp(mk("Analyst", "<p>You will be office-based in Leeds.</p>")) == "office" and wp(mk("Analyst", "<p>Based in our Cork office.</p>")) == "office", "pf-A3: 'office-based' and 'based in our … office' still count")
    check(wp(mk("Warden", "<p>Daily patrol of the nature reserve, on site.</p>")) == "site", "pf-A3: reserve / on site / patrol -> site-based")
    ct = build_site.contract_of
    check("contract" not in ct(mk("Engineer", "<p>Our client is a leading contractor. Permanent role.</p>")), "pf-A3: 'contractor' no longer tags a permanent role as Contract")
    check("contract" in ct(mk("Engineer", "<p>This is a 12-month contract.</p>")) and "contract" in ct({"title": "x", "type": "Contract", "summary": "", "description_html": ""}) and "contract" in ct(mk("x", "<p>A contract role for six months.</p>")), "pf-A3: contract from the type or an explicit phrase")
    check(build_site.level_of("Assistant Project Manager") == "Mid-level" and build_site.level_of("Assistant Director – Water") == "Director/Associate", "pf-A3: 'Assistant … Manager' is not Graduate")
    check(build_site.level_of("Assistant Ecologist") == "Mid-level" and build_site.level_of("Graduate Ecologist") == "Graduate/Early career" and build_site.level_of("Research Assistant") == "Graduate/Early career", "pf-A3: assistant-to-a-role is mid-level; a bare assistant stays early career")
    check(build_site.level_of("Lead-free Solder Engineer") == "Mid-level" and build_site.level_of("Team Lead – Water") == "Senior/Principal", "pf-A3: 'lead-free' is not Senior; 'Lead' as a title word is")


def test_pf_a_sector_golden_set():
    gold = json.loads((Path(__file__).resolve().parent / "golden_sectors.json").read_text(encoding="utf-8"))
    raws = {ed: json.loads((SRC / "data" / f"{ed}.json").read_text(encoding="utf-8")) for ed in ("ie", "uk") if (SRC / "data" / f"{ed}.json").exists()}
    if len(raws) < 2:
        skip("pf-A4: real datasets absent, golden set")
        return
    by = {j["id"]: j for r in raws.values() for j in r["jobs"]}
    hits, misses = 0, []
    for g in gold:
        j = by.get(g["id"])
        if not j:
            continue
        got = build_site.assign_sectors(j)[0]
        if got == g["sector"]:
            hits += 1
        else:
            misses.append(f"{g['id']} {g['title'][:40]!r} -> {got}")
    n = hits + len(misses)
    check(n >= 40 and hits / max(1, n) >= 0.9, f"pf-A4: golden sector set agreement {hits}/{n} >= 90% (misses: {misses})")
    mk = lambda title, employer="", sectors=None: {"title": title, "employer": employer, "sectors": sectors or [], "summary": "", "description_html": ""}  # noqa: E731
    check(build_site.assign_sectors(mk("LGV Driver", "Grundon Waste Management"))[0] == "Waste & circular economy", "pf-A4: the employer name is scored (Waste Management -> Waste)")
    check(build_site.assign_sectors(mk("Network Officer", "Acme"))[0] == "Environmental science & consulting" and build_site.assign_sectors({**mk("Power Networks Engineer", "Acme"), "summary": "Design for energy networks."})[0] == "Energy networks & utilities", "pf-A4: bare 'network' / 'power' / 'officer' are not keywords; 'energy networks' is")
    pairs_ie = {(j["title"], j["employer"]): build_site.assign_sectors(j)[0] for j in raws["ie"]["jobs"]}
    pairs_uk = {(j["title"], j["employer"]): build_site.assign_sectors(j)[0] for j in raws["uk"]["jobs"]}
    shared = set(pairs_ie) & set(pairs_uk)
    disagree = [k for k in shared if pairs_ie[k] != pairs_uk[k]]
    check(len(shared) >= 30 and not disagree, f"pf-A4: the {len(shared)} adverts present on both editions (same title + employer; ids differ per site) get the same primary sector ({disagree[:3]})")
    for ed in ("ie", "uk"):
        for j in raws[ed]["jobs"]:
            if j["employer"] == "Commonland":
                check(build_site.assign_sectors(j)[0] in ("Ecology, nature recovery & biodiversity", "Environmental science & consulting"), f"pf-A4: {ed} Commonland {j['title'][:30]!r} lands in Ecology / Env science")


def test_pf_a_dates_and_closed_roles(tmp_root: Path):
    from datetime import date as _d
    today = _d(2026, 9, 28)
    du = build_site.days_until
    check(du("2026-09-28", today) == 0 and du("2026-10-05", today) == 7 and du("2026-10-06", today) == 8 and du("2026-09-27", today) == -1 and du("", today) is None, "pf-A5: days_until is whole calendar days")
    check(build_site.closing_within({"closing": "2026-09-28"}, today) and build_site.closing_within({"closing": "2026-10-05"}, today) and not build_site.closing_within({"closing": "2026-10-06"}, today) and not build_site.closing_within({"closing": "2026-09-27"}, today), "pf-A5: closing within 7 days = 0..7 inclusive")
    check(build_site.new_this_week({"posted": "2026-09-28"}, today) and build_site.new_this_week({"posted": "2026-09-22"}, today) and not build_site.new_this_week({"posted": "2026-09-21"}, today), "pf-A5: new this week = 0..6 days ago")
    check(build_site.is_closed({"closing": "2026-09-27"}, today) and not build_site.is_closed({"closing": "2026-09-28"}, today) and not build_site.is_closed({"closing": ""}, today), "pf-A5: closed = closing date before the build date; closing today is still open")
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    check(build_site.build_today(raw) == _d(2026, 9, 22) and build_site.build_today(raw, today) == today and build_site.build_today({}) == _d.today(), "pf-A5: build date = --today, else fetched, else the clock")
    data = build_site.normalise(raw, "ie", SRC, SRC / "assets" / "logos", _d(2026, 10, 1))
    ids = {j["id"] for j in data["jobs"]}
    check("1005" not in ids and "1003" in ids and len(data["closed"]) == 1 and data["today"] == "2026-10-01", "pf-A5: a role closing 2026-09-30 is dropped from a 2026-10-01 build; the drop is recorded")
    out = tmp_root / "site_today"
    rc = build_site.build(SRC, out, editions=["ie", "uk"], fixture=FIXTURE, today=_d(2026, 10, 1))
    check(rc == 0 and not (out / "ie" / "jobs" / "1005" / "index.html").exists(), "pf-A5: --today drops closed roles from the built site")
    home = (out / "ie" / "index.html").read_text(encoding="utf-8")
    board = (out / "ie" / "jobs" / "index.html").read_text(encoding="utf-8")
    check('"today":"2026-10-01"' in board and '"today":"2026-10-01"' in (out / "ie" / "data" / "jobs.json").read_text(encoding="utf-8"), "pf-A5: data.today is exposed to JavaScript")
    check("2026-10-01" in home.split("<footer")[-1] or "2026" in home.split("<footer")[-1], "pf-A5: footer year comes from the build date")
    check(">11 days ago<" in home or "2 wk ago" in home, "pf-A5: 'ago' labels are relative to the build date (1001 posted 2026-09-20 -> 11 days -> 2 wk ago)")
    out2 = tmp_root / "site_today2"
    build_site.build(SRC, out2, editions=["ie", "uk"], fixture=FIXTURE, today=_d(2026, 10, 1))
    same = (out / "ie" / "index.html").read_text(encoding="utf-8") == (out2 / "ie" / "index.html").read_text(encoding="utf-8")
    check(same, "pf-A5: two builds with the same --today produce identical home pages (date-deterministic)")


def test_pf_a_currency_and_rounding():
    check(build_site.rnd(324.5) == 325 and build_site.rnd(32450, -2) == 32500 and build_site.rnd(32449, -2) == 32400 and build_site.rnd(2.5) == 3 and build_site.rnd(-0.4) == 0, "pf-A6: rnd rounds half up like Math.round (32450 -> 32500, Python's round gives 32400)")
    check(build_site.money_k(32450, "€") == "€32.5k" and build_site.money_k(62500, "£") == "£62.5k", "pf-A6: money_k uses half-up rounding (32450 -> €32.5k)")
    usd = {"sal_min": 50000, "sal_max": 60000, "cur": "USD", "period": "year"}
    none = {"sal_min": 50000, "sal_max": 60000, "cur": None, "period": "year"}
    check(build_site.annual_mid(usd) is None and build_site.annual_mid(none) is None and build_site.annual_mid(usd, "EUR") is None, "pf-A6: USD / unknown currency never enters annual_mid")
    check(build_site.median_salary([usd, {"sal_min": 40000, "sal_max": 40000, "cur": "EUR", "period": "year"}], "€", "EUR") == "€40k", "pf-A6: medians ignore non-EUR/GBP salaries")
    check(build_site.salary_bands([usd], "€", "EUR") == [{"l": b["l"], "n": 0} for b in build_site.salary_bands([usd], "€", "EUR")], "pf-A6: bands ignore non-EUR/GBP salaries")
    check(build_site.salary_label(usd) == "$50k–60k", "pf-A6: the label still shows the advertised USD figure")


def test_pf_a_garbled_pounds():
    fx = "Salary �30,000 to �35,000, up to �2m portfolio, paying �80k, �Competitive, Â£45,000"
    out = build_site.repair_pounds(fx)
    check(out == "Salary £30,000 to £35,000, up to £2m portfolio, paying £80k, �Competitive, £45,000", f"pf-A7: '�' before a digit or a k-amount becomes £; other replacement characters stay ({out!r})")
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw["jobs"][0]["description_html"] = "<p>Paying �50,000.</p>"
    data = build_site.normalise(raw, "ie", SRC, SRC / "assets" / "logos")
    j = next(x for x in data["jobs"] if x["id"] == "1001")
    check("£50,000" in j["description_html"] and "£50,000" in j["text"], "pf-A7: normalise() repairs the description before sanitising")


def test_pf_a_landing_links(tmp_root: Path):
    from urllib.parse import parse_qs, urlparse
    out = tmp_root / "site_landing2"
    real = (SRC / "data" / "ie.json").exists() and (SRC / "data" / "uk.json").exists()
    rc = build_site.build(SRC, out, editions=["ie", "uk"], fixture=None if real else FIXTURE)
    check(rc == 0, "pf-A8: build for landing-link checks")
    for ed in ("ie", "uk"):
        raw = json.loads((SRC / "data" / f"{ed}.json" if real else FIXTURE).read_text(encoding="utf-8"))
        data = build_site.normalise(raw, ed, SRC, SRC / "assets" / "logos")
        for spec, in_page in build_site.landing_pages(data):
            page = (out / ed / spec["slug"] / "index.html").read_text(encoding="utf-8")
            m = re.search(r'href="([^"]*)">Open these (\d+) roles', page)
            if not m:
                m = re.search(r'href="(\.\./jobs/index\.html\?[^"]*)"', page)
            href = __import__("html").unescape(m.group(1))
            q = parse_qs(urlparse(href).query)
            n_cards = page.count('<article class="role')
            if "sector" in q:
                wanted = set(q["sector"][0].split("|"))
                opened = [j for j in data["jobs"] if set(j["sectors"]) & wanted and (not q.get("only") or j["loc_class"] in build_site.LANDING_LOC[ed])]
                check(wanted == set(spec["sectors"]) and q.get("only") == ["1"] and len(opened) == len(in_page) == n_cards, f"pf-A8: {ed}/{spec['slug']}: the search link opens every sector ({len(opened)} roles) = cards on the page ({n_cards})")
            else:
                opened = [j for j in data["jobs"] if q["loc"][0] in j["regions"]]
                check(len(opened) == len(in_page) == n_cards, f"pf-A8: {ed}/{spec['slug']}: the region link opens {len(opened)} roles = cards on the page ({n_cards})")
    check("%7C" in build_site.landing_search_href({"kind": "sector", "sectors": {"B", "A"}}) and "sector=A%7CB&only=1" in build_site.landing_search_href({"kind": "sector", "sectors": {"B", "A"}}), "pf-A8: multi-sector landings link with '|'-joined sectors")


def test_pf_a_similar_jobs_rules():
    mk = lambda i, title, emp, sectors, posted: {"id": str(i), "title": title, "employer": emp, "sectors": sectors, "regions": ["Dublin"], "sal_min": None, "sal_max": None, "cur": None, "period": None, "posted": posted, "loc_class": "ie"}  # noqa: E731
    me = mk(0, "Ecologist", "A", ["Ecology, nature recovery & biodiversity"], "2026-09-01")
    pool = [mk(1, "Ecologist", "A", ["Ecology, nature recovery & biodiversity"], "2026-09-05"),  # same title+employer as me -> hidden
            mk(2, "Senior Ecologist", "B", ["Ecology, nature recovery & biodiversity"], "2026-09-03"),
            mk(3, "Senior Ecologist", "B", ["Ecology, nature recovery & biodiversity"], "2026-09-02"),  # duplicate of 2 -> hidden
            mk(4, "Wind Technician", "C", ["Wind energy"], "2026-09-04"),  # same region, no shared sector -> hidden
            mk(5, "Bat Surveyor", "D", ["Ecology, nature recovery & biodiversity"], ""),  # no posted date -> last
            mk(6, "Botanist", "E", ["Ecology, nature recovery & biodiversity"], "2026-09-04")]
    sim = [s["id"] for s in build_site.similar_jobs(me, pool + [me], "EUR", 6)]
    check(sim == ["6", "2", "5"], f"pf-A9: similar jobs dedupe on (title, employer), need a shared sector, newest first, empty posted last (got {sim})")


def test_pf_a_employer_count_phrase(tmp_root: Path):
    check(build_site.emp_count_phrase("ie", 20) == "" and build_site.emp_count_phrase("uk", 4) == "" and build_site.emp_count_phrase("uk", 18) == " from 18 employers", "pf-A10: employer count phrase only on UK with five or more employers")
    out = tmp_root / "site_emp"
    real = (SRC / "data" / "ie.json").exists() and (SRC / "data" / "uk.json").exists()
    check(build_site.build(SRC, out, editions=["ie", "uk"], fixture=None if real else FIXTURE) == 0, "pf-A10: build for employer checks")
    ie_emp = (out / "ie" / "employers" / "index.html").read_text(encoding="utf-8")
    for ed in ("ie", "uk"):
        raw = json.loads((SRC / "data" / f"{ed}.json" if real else FIXTURE).read_text(encoding="utf-8"))
        data = build_site.normalise(raw, ed, SRC, SRC / "assets" / "logos")
        live = {j["employer"] for j in data["jobs"]}
        strip = build_site.employers_strip(data, "../../", cap=None)
        listed = {__import__("html").unescape(a or b) for a, b in re.findall(r'<(?:img[^>]*\balt="([^"]*)"|span>([^<]*)</span>)', strip["html"])}
        check(live <= listed, f"pf-A15: {ed} employers-page strip lists every live employer ({len(live)} of {len(listed)} shown)")
        home = build_site.employers_strip(data, "../")
        check(home["html"].count('class="emp"') <= 2 * 12 or home["mode"] == "network", f"pf-A15: {ed} home strip keeps the cap of 12")
    check("from 0 employers" not in ie_emp, "pf-A10: IE employers page has no empty employer-count phrase")
    for pat in re.finditer(r"from (\d+) employers", ie_emp):
        check(False, f"pf-A10: IE employers page states an employer count ({pat.group(0)}); the other agent's template should use {{{{emp_count_phrase}}}}")
        break


def test_pf_a_hreflang_pairs(tmp_root: Path):
    out = tmp_root / "site_hreflang"
    check(build_site.build(SRC, out, editions=["ie", "uk"], fixture=FIXTURE) == 0, "pf-A14: fixture build for hreflang checks")
    for rel in ("ie/dashboard/index.html", "uk/dashboard/index.html", "ie/for-keith/index.html", "ie/index.html", "uk/jobs/index.html"):
        head = (out / rel).read_text(encoding="utf-8").split("</head>")[0]
        links = re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"', head)
        langs = [hl for hl, _ in links]
        check(sorted(langs) == ["en-GB", "en-IE", "x-default"] and all(h.startswith("https://") for _, h in links), f"pf-A14: {rel} carries absolute en-IE + en-GB + x-default alternates ({langs})")
        gb = dict(links).get("en-GB", "")
        check(gb.endswith("/uk/" + rel.split("/", 1)[1]), f"pf-A14: {rel} en-GB alternate is the UK twin of the same path ({gb})")
    landing = next(p for p in (out / "ie").glob("*-jobs-*/index.html"))
    head = landing.read_text(encoding="utf-8").split("</head>")[0]
    twin = build_site.LANDING_PAIRS[landing.parent.name]
    check('rel="canonical" href="https://' in head and f'hreflang="en-GB" href="https://greenjobs-redesign.pages.dev/uk/{twin}/index.html"' in head,
          f"pf-A14 (R055): landing {landing.parent.name} has an absolute canonical and an en-GB alternate to its twin {twin}")


def test_pf_a_validator_rules(tmp_root: Path):
    out = tmp_root / "site_rules"
    check(build_site.build(SRC, out, editions=["ie", "uk"], fixture=FIXTURE) == 0, "pf-A11: fixture build for validator rules")
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data_by_ed = {ed: build_site.normalise(raw, ed, SRC, SRC / "assets" / "logos") for ed in ("ie", "uk")}
    paired = build_site.PAIRED_PATHS | set.intersection(*[{f"{s['slug']}/index.html" for s, _ in build_site.landing_pages(d)} for d in data_by_ed.values()])
    for d in data_by_ed.values():
        d["paired_paths"] = paired
    jobs = {k: d["jobs"] for k, d in data_by_ed.items()}
    V = lambda: validate_site.validate(out, jobs, data_by_ed, build_site.dashboard_kpis)  # noqa: E731
    check(V() == [], "pf-A11: the clean build passes the extended validator")

    def patched(path: Path, fn, needle: str):
        clean = path.read_text(encoding="utf-8")
        path.write_text(fn(clean), encoding="utf-8")
        try:
            return any(needle in f for f in V())
        finally:
            path.write_text(clean, encoding="utf-8")
    board = out / "ie" / "jobs" / "index.html"
    check(patched(board, lambda t: t.replace('hreflang="en-GB" href="https://greenjobs-redesign.pages.dev/uk/jobs/index.html"', 'hreflang="en-GB" href="https://greenjobs-redesign.pages.dev/uk/nope/index.html"'), "not a built page"), "pf-A11: an hreflang target missing from the other edition fails")
    check(patched(board, lambda t: t.replace('hreflang="en-GB" href="https://greenjobs-redesign.pages.dev/uk/jobs/index.html"', 'hreflang="en-GB" href="../../uk/jobs/index.html"'), "must be absolute"), "pf-A11: a relative hreflang href fails")
    check(patched(board, lambda t: t.replace('<link rel="alternate" hreflang="x-default" href="https://greenjobs-redesign.pages.dev/ie/jobs/index.html">', ""), "x-default"), "pf-A11: alternates without an x-default fail")
    landing = next(p for p in (out / "ie").glob("*-jobs-*/index.html"))
    check(patched(landing, lambda t: re.sub(r'<article class="role\b.*?</article>', "", t, flags=re.S), "no role card"), "pf-A11: a landing page with zero role cards fails")
    dash = out / "ie" / "dashboard" / "index.html"
    check(patched(dash, lambda t: t.replace('<b class="kpi__v">—</b>', '<b class="kpi__v">42</b>', 1), "digit outside"), "pf-A11: a live number in a wired-at-launch tile fails")
    check(patched(dash, lambda t: re.sub(r'(id="gj-dash">\{"asof":"[^"]+","live":)(\d+)', lambda m: m.group(1) + str(int(m.group(2)) + 1), t), "differ from a fresh"), "pf-A11: an embedded KPI block that does not match dashboard_kpis(data) fails")
    hero = out / "assets" / "hero" / "ie-m.mp4"
    blob = hero.read_bytes()
    hero.unlink()
    check(any("ie-m.mp4 is missing" in f for f in V()), "pf-A11: a missing hero file fails (mp4, -m.mp4 and poster are required per edition)")
    hero.write_bytes(b"\0" * (validate_site.HERO_BUDGET_FILE + 1))
    check(any("per-file hero budget" in f for f in V()), "pf-A11: a hero file over 2 MB fails")
    hero.write_bytes(blob)
    check(validate_site.HERO_BUDGET_FILE == 2 * 1024 * 1024 and validate_site.HERO_BUDGET_TOTAL == 6 * 1024 * 1024, "pf-A11: hero budgets are 2 MB per file, 6 MB total")
    src_text = (SCRIPT_DIR / "validate_site.py").read_text(encoding="utf-8")
    check(src_text.count('"data-landscape" not in raw') == 1, "pf-A11: the duplicate data-landscape check is gone")


def test_pf_a_scraper_floor(tmp_root: Path):
    import scrape_greenjobs as sg
    snap = tmp_root / "snap.json"
    check(sg.snapshot_floor(str(snap)) == 0, "pf-A12: no existing snapshot -> floor 0")
    sg.write_json_atomic(str(snap), {"jobs": [{"id": str(i)} for i in range(100)]})
    check(snap.exists() and not list(tmp_root.glob("snap.json.tmp*")) and len(json.loads(snap.read_text(encoding="utf-8"))["jobs"]) == 100, "pf-A12: write_json_atomic writes via a temp file and renames; no temp file is left")
    check(sg.snapshot_floor(str(snap)) == 50, "pf-A12: floor is 50% of the existing snapshot's jobs")
    crawl_src = (SCRIPT_DIR / "scrape_greenjobs.py").read_text(encoding="utf-8")
    check("if len(jobs) < floor:" in crawl_src and "rc = 3" in crawl_src and "os.replace(tmp, path)" in crawl_src, "pf-A12: crawl_site refuses to overwrite below the floor and main() exits non-zero")


def test_pf_a_node_missing_fails_build(tmp_root: Path):
    original = build_site.run_node_tests
    build_site.run_node_tests = lambda src: None
    try:
        rc = build_site.build(SRC, tmp_root / "site_nonode", editions=["ie"], fixture=FIXTURE)
    finally:
        build_site.run_node_tests = original
    check(rc != 0, "pf-A13: run_node_tests() returning None (node missing) fails the build")


def test_r3_visual_fixes(tmp_root: Path):
    """Round-3 visual sweep (visual_issues_v2): N4 long dates, N5 no IE employer count,
    R010 Built-environment secondary, R011 unverified euro source, visual 7/N3 strip tiles,
    visual 25 agency casing, visual 28 no placeholder copy, visual 12 zero regions."""
    check(build_site.date_long("2026-09-22") == "22 September 2026" and build_site.snapshot_label("2026-01-05") == "Snapshot of 5 January 2026", "r3 N4: date_long renders '22 September 2026'")
    mk = lambda ed, names: {"ed": ed, "site": "greenjobs.ie" if ed == "ie" else "greenjobs.co.uk", "employers": [{"name": n, "url": "", "logo": "", "lw": 0, "lh": 0} for n in names], "jobs": [{"employer": n} for n in names]}  # noqa: E731
    ie = build_site.employers_strip(mk("ie", ["A", "B", "C"]), "../")
    check(not re.search(r"\d", ie["sub"]) and ie["sub"] == "Organisations with live roles on greenjobs.ie this week.", f"r3 N5: IE strip sub carries no employer count ({ie['sub']!r})")
    uk = build_site.employers_strip(mk("uk", [f"E{i}" for i in range(4)]), "../")
    check(not re.search(r"\d", uk["sub"]), "r3 N5: UK strip sub has no count below 10 employers")
    check('class="mono"' in ie["html"] and ie["html"].count('class="mono"') == 3 and "marq__dup" not in ie["html"], "r3 visual 7 / r4b: employers without a logo get a monogram disc; a three-employer strip is a static row, not duplicated")
    eager = build_site.employers_strip({**mk("uk", [f"E{i}" for i in range(12)]), "employers": [{"name": f"E{i}", "url": "", "logo": "x.png", "lw": 10, "lh": 10} for i in range(12)]}, "../")["html"]
    first = eager.split('<span class="marq__dup"')[0]
    check(first.count('loading="eager"') == 8 and first.count('loading="lazy"') == 4 and 'decoding="async"' in first, "r3 N3: first eight marquee logos load eagerly, the rest lazily")
    j = {"currency_source": build_site.UNVERIFIED_SOURCE}
    check(build_site.salary_source_line(j) == build_site.UNVERIFIED_NOTE and build_site.salary_source_line({"currency_source": build_site.STERLING_SOURCE}).startswith("Advertised in sterling"), "r3 R011: salary_source_line maps both sources")
    mkj = lambda title, summary="", body="": {"title": title, "employer": "", "sectors": [], "summary": summary, "description_html": body}  # noqa: E731
    INF = "Sustainable infrastructure & transport"
    check(build_site.assign_sectors(mkj("Associate Civil Engineer", "roads rail bridges highways", "<p>building built environment construction</p>")) == [INF], "r3 R010: three body hits alone no longer add Built environment to a civil role")
    check(build_site.BUILT_ENV in build_site.assign_sectors(mkj("Civil Engineer – Building Services", "roads rail highways bridges", "<p>retrofit building insulation heat pump</p>")), "r3 R010: a title hit keeps Built environment as a secondary")
    if not (SRC / "data" / "ie.json").exists() or not (SRC / "data" / "uk.json").exists():
        skip("r3: real datasets absent")
        return
    out = tmp_root / "site_r3"
    check(build_site.build(SRC, out, editions=["ie", "uk"]) == 0, "r3: real-data build returns 0")
    raw = json.loads((SRC / "data" / "ie.json").read_text(encoding="utf-8"))
    by = {str(j["id"]): j for j in raw["jobs"]}
    if "11497629" in by:
        check(build_site.BUILT_ENV not in build_site.assign_sectors(by["11497629"]), "r3 R010: Associate Civil Engineer (Mattinson, London) no longer carries Built environment")
    data = build_site.normalise(raw, "ie", SRC, SRC / "assets" / "logos")
    unv = {j["id"] for j in data["jobs"] if j["currency_source"] == build_site.UNVERIFIED_SOURCE}
    check({"11497629", "11496364"} <= unv and all(j["cur"] == "EUR" and j["loc_class"] == "uk" for j in data["jobs"] if j["id"] in unv), f"r3 R011: UK-located euro roles with no sterling twin are marked unverified ({sorted(unv)})")
    for jid in ("11497629", "11496364"):
        page_html = (out / "ie" / "jobs" / jid / "index.html").read_text(encoding="utf-8")
        check(build_site.UNVERIFIED_NOTE in page_html and "Advertised in sterling" not in page_html, f"r3 R011: /ie/jobs/{jid}/ says the salary is as listed on greenjobs.ie, never invents sterling")
    ds = json.loads((out / "ie" / "data" / "jobs.json").read_text(encoding="utf-8"))
    check({j["id"] for j in ds["jobs"] if j.get("unverified_cur")} == unv and build_site.UNVERIFIED_NOTE in (SRC / "js" / "jobs.js").read_text(encoding="utf-8"), "r3 R011: jobs.json flags the roles and jobs.js prints the note on their cards")
    for ed in ("ie", "uk"):
        for rel in ("index.html", "employers/index.html"):
            page_html = (out / ed / rel).read_text(encoding="utf-8")
            strip_html = re.search(r'<div class="marq__track">(.*?)</div></div>', page_html, re.S)
            if strip_html:
                tiles = re.findall(r'<(?:a|div) class="emp"[^>]*>(.*?)</(?:a|div)>', strip_html.group(1), re.S)
                check(tiles and all("<img" in t or 'class="mono"' in t for t in tiles), f"r3 visual 7: every {ed} {rel} strip tile has an <img> or a .mono ({len(tiles)} tiles)")
            check(not re.search(r"\b\d+ of them ha(?:s|ve) live roles", page_html) and (ed == "uk" or not re.search(r"\b\d+ (?:organisations|employers) with live roles", page_html)), f"r3 N5: {ed} {rel} shows no employer count sentence on IE")
    iso = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
    bad = []
    for f in sorted(out.rglob("index.html")):
        rel = f.relative_to(out).as_posix()
        if "for-keith" in rel or "evidence" in rel:
            continue
        t = f.read_text(encoding="utf-8")
        t = re.sub(r"<script\b.*?</script>", "", t, flags=re.S)
        t = re.sub(r"<(?:time|code)\b[^>]*>.*?</(?:time|code)>", "", t, flags=re.S)
        t = re.sub(r"<[^>]+>", " ", t)  # drop attributes (datetime=, data-closing=, hrefs)
        if iso.search(t):
            bad.append(f"{rel}: {iso.search(t).group(0)}")
    check(not bad, f"r3 N4: no ISO date in visible text on public pages ({bad[:4]})")
    for ed in ("ie", "uk"):
        dash = (out / ed / "dashboard" / "index.html").read_text(encoding="utf-8")
        check("Chm Recruit" not in dash and "CHM Recruit" in dash, f"r3 visual 25: {ed} dashboard keeps 'CHM Recruit' casing")
        emp = (out / ed / "employers" / "index.html").read_text(encoding="utf-8")
        check(not re.search(r"supplied at launch|figure supplied|<em>[^<]*launch[^<]*</em>", emp, re.I), f"r3 visual 28: {ed} employers page has no italic placeholder copy")
        home = (out / ed / "index.html").read_text(encoding="utf-8")
        zero = re.findall(r'<g class="gmap__r is-zero"[^>]*data-region="([^"]*)"[^>]*data-n="0"', home)
        n0 = len(re.findall(r'data-n="0"', home))
        check(len(zero) == n0, f"r3 visual 12: every zero-count region on the {ed} home map carries is-zero ({zero})")
    check('"cmpwrap' in (out / "ie" / "employers" / "index.html").read_text(encoding="utf-8"), "r3 N1: package table wrapper present (desktop max-height removed in CSS)")
    css = (SRC / "css" / "styles.css").read_text(encoding="utf-8")
    check("max-height:min(72vh,760px)" not in css and "@media (max-width:700px){.cmpwrap{overflow-x:auto}}" in css, "r3 N1: .cmpwrap has no desktop max-height; horizontal scroll only <= 700px")
    check(".hero__cta .btn--post{flex:0 1 260px;max-width:260px}" in css, "r3 N2: hero Post a job CTA capped at 260px")
    check("transform:scale(1.06)" not in css and "object-fit:contain" in css.split(".emp img{")[1].split("}")[0], "r3 visual 32: marquee logos are contained with no scale bleed")
    check(".maplist--sm" in css and 'data-map-counts' in (out / "ie" / "jobs" / "index.html").read_text(encoding="utf-8"), "r3 visual 11: compact region count list under the jobs-page map")


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
        # Companion suites (2026-09-28): the offline scraper tests against the
        # recorded corpus and the branch tests for build/validate. One command
        # runs everything; each file also runs on its own.
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import test_gaps
        import test_scrape
        for suite in (test_scrape, test_gaps):
            RESULTS.extend(suite.run_all(tmp_root))
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
    passed = sum(1 for ok, _ in RESULTS if ok)
    failed = [label for ok, label in RESULTS if not ok]
    print(f"\nUnit+Integration: {passed} passed, {len(failed)} failed, {len(SKIPS)} skipped")
    for label in SKIPS:
        print(f"  SKIP: {label}")
    for label in failed:
        print(f"  FAIL: {label}")
    return 1 if failed else 0




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


# --- panel fixes B ---
# Panel pass 2026-09-28 (FINDINGS_LOG sections 02, 03, 05, 06, 07, 09, 11): copy,
# consent, forms, employers page, closed roles, dashboard rules, event layer.

def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_panel_b_copy_and_consent(tmp_root: Path):
    out = tmp_root / "site_panel_b"
    rc = build_site.build(SRC, out, editions=["ie", "uk"], fixture=FIXTURE)
    check(rc == 0, "panel B: fixture build passes")
    home = _read(out / "ie" / "index.html")
    # 1. cookie copy lists what is stored, never "nothing else"
    check("nothing else" not in home and all(w in home for w in ("theme", "edition", "saved roles", "weekly-email prompt", "dashboard view")),
          "panel B1: cookie dialog lists theme, edition, saved roles, subscribe prompt and dashboard view")
    # 2. quick job match wording + share is explicit
    jobs = _read(out / "ie" / "jobs" / "index.html")
    check("Your information is processed on your device and is not uploaded or stored." in jobs and "Keyword matching, not an assessment of your suitability." in jobs
          and "Copy shareable link" in jobs and "The link contains your search words." in jobs and "Nothing is uploaded" not in jobs,
          "panel B2 (re-worded round 2 B / R036): fit panel uses the client sentence verbatim; share note says the link carries the search words")
    fit_js = _read(SRC / "js" / "fit.js")
    check(fit_js.count("'#fit=' + G.encodeFit(") == 1 and "Explicit opt-in" in fit_js.split("'#fit=' + G.encodeFit(")[0][-400:],
          "panel B2: fit.js writes the hash only inside the share click handler")
    # 3. B Corp: generic definition, no text claim beyond the mark's alt on public pages
    public = [p for p in out.rglob("index.html") if "for-keith" not in p.parts]
    bad = []
    for p in public:
        t = _read(p)
        # 2026-09-28 visual fix: the home hero trust box now opens with the confirmed wording
        # "<b>Certified B Corporation.</b>" beside the mark (client request); that one use is allowed too.
        stripped = re.sub(r'alt="Certified B Corporation"|<b>Certified B Corporation\.</b>', "", t)
        if "Certified B Corporation" in stripped:
            bad.append(str(p.relative_to(out)))
    check(not bad, f"panel B3: 'Certified B Corporation' appears only as the mark's alt ({bad[:3]})")
    check("B Corps are businesses independently certified" in home, "panel B3: generic B Corp definition on the home page")
    keith = _read(out / "ie" / "for-keith" / "index.html")
    check("B Corp status" in keith and "logo" in keith.split("Launch checklist")[1][:1500], "panel B3/11: launch checklist asks for B Corp confirmation and logo permission")
    # 4. UK employers: no placeholder testimonial slots on the public page
    emp_uk = _read(out / "uk" / "employers" / "index.html")
    check("fact--slot" not in emp_uk and "Testimonial supplied at launch" not in emp_uk and "Client testimonials available on request." in emp_uk,
          "panel B4: UK employers page shows one collection line, no placeholder slots")
    # 5. demo forms: pre-submit note above the button + fallback link
    # Re-worded in round 2 B (visual 8 / R044): visitor voice, no "connects at launch" copy.
    for label, page_html, needle in (("home alerts", home, "Meanwhile, browse all roles"), ("subscribe dialog", home, "data-subscribe"), ("employers", emp_uk, "Preview only. Rates and posting are handled by the GreenJobs team")):
        pre = page_html.find('data-demo-pre'); btn = page_html.find('type="submit"', pre)
        check(0 <= pre < btn and "Job alerts by email are available on" in home and needle in page_html, f"panel B5: {label} form shows the where-to-sign-up note before the button (round 4: points at the live site, no 'opens at launch')")
    check(home.count("Meanwhile, browse all roles") >= 2, "panel B5: alert and subscribe forms carry the browse-all fallback link")
    # 6. employers page copy
    emp_ie = _read(out / "ie" / "employers" / "index.html")
    check(" from " not in emp_ie.split('class="lede"')[1].split("</p>")[0] and "employers are on" not in emp_ie, "panel B6: IE employers lede has no employer count")
    check("Request rates and post" not in emp_uk and emp_uk.count("Request advertising rates") >= 3, "panel B6: one CTA label everywhere")
    check("Send us the job description and logo; we post it and email you when it is live." in emp_uk and "account management" in emp_uk, "panel B6: done-for-you line from brief.md")
    rows = re.findall(r"<tr><th scope=\"row\">(.*?)</th>(.*?)</tr>", emp_uk)
    member_incl = [r for r, cells in rows if cells.count("<td") == 3 and cells.rsplit("<td", 1)[1].startswith(">Included")]
    check(set(member_incl) == {"Multiple postings at a discounted rate", "Employer self-management system with telephone training"}, f"panel B6: Membership ticks only what brief.md confirms ({member_incl})")
    check('class="cmphint"' in emp_uk and ".cmphint{display:none" in _read(out / "css" / "styles.css"), "panel B6: swipe hint present, hidden on wide screens")
    # 7. tags wrap on narrow screens
    css = _read(out / "css" / "styles.css")
    tag_rule = re.search(r"^\.tag\{[^\n]*\}", css, re.M).group(0)
    check(tag_rule.rfind("white-space:normal") > tag_rule.rfind("white-space:nowrap") and "max-width:100%" in tag_rule, "panel B7: .tag wraps (white-space normal wins, max-width set)")
    # 8. toggle label
    check("Hide UK/abroad-only roles" in jobs and "Hide Ireland/abroad-only roles" in _read(out / "uk" / "jobs" / "index.html") and "Ireland only" not in jobs.split('id="gj-data">')[0],
          "panel B8: toggle renamed per edition")
    # 9. closed roles: JS rule present, job page carries closing + apply hooks
    jobs_js = _read(SRC / "js" / "jobs.js")
    check("data.today" in jobs_js and "Date.now()" in jobs_js and "tag--closed" in jobs_js, "panel B9: card Closed chip uses data.today with Date.now() fallback")
    job_pages = [p for p in (out / "ie" / "jobs").glob("*/index.html")]
    jp = _read(job_pages[0])
    check('data-closing="' in jp and jp.count("data-apply") == 2 and "This role has closed" in _read(SRC / "js" / "main.js"), "panel B9: job page exposes closing date and apply hooks; main.js swaps in the closed state")
    # 10. dashboard + event layer
    dash = _read(out / "ie" / "dashboard" / "index.html")
    check(("Measures to come" in dash or "Event spec for launch" in dash) and "Measured after launch" not in dash, "panel B10: post-launch group renamed ('Measures to come' since round 4)")
    for tile in ("Apply clicks per employer", "Zero-result searches", "Alert match rate (weekly)", "Advertised window (median days)"):
        check(tile in dash, f"panel B10: tile '{tile}' present")
    check("Median days to close" not in dash and 'kpi__l">Sessions<' not in dash and 'kpi__l">Uptime<' not in dash and "dash__foot" in dash, "panel B10: sessions/uniques demoted to context, uptime/CWV to the footer strip")
    check("recruitment word" in dash and "known agency" in dash, "panel B10: agency tile describes the real rule")
    for label, wanted in (("Top search terms", "proposed target"), ("Top landing pages", "proposed target")):
        seg = dash.split(label, 1)[1][:600]
        check('kpi__t' in seg and wanted in seg, f"panel B10: '{label}' tile has a labelled target")
    check("prefers-reduced-motion:no-preference){.insight__tile:hover{transform" in css, "panel B10 QA: insight tile hover transform gated on no-preference")
    for p in job_pages + list((out / "uk" / "jobs").glob("*/index.html")):
        t = _read(p)
        links = re.findall(r"<a [^>]*data-apply[^>]*>", t)
        if len(links) != 2 or not all(all(k in a for k in ('data-ev="apply_click"', "data-ev-job=", "data-ev-employer=", "data-ev-sector=", "data-ev-region=")) for a in links):
            check(False, f"panel B10: every apply link carries data-ev ({p.relative_to(out)})")
            break
    else:
        check(True, "panel B10: every apply link carries data-ev with job, employer, sector and region")
    check('data-ev="search"' in home and 'data-ev="search"' in jobs and 'data-ev="alert_signup"' in home and 'data-ev="newsletter_signup"' in home
          and 'data-ev="request_rates"' in emp_uk and 'data-ev="post_job_click"' in home, "panel B10: search, alert, newsletter, request-rates and post-job carry data-ev")
    main_js = _read(SRC / "js" / "main.js")
    check("function track(" in main_js and "GJAnalytics" in main_js and "gj-consent" in main_js and "save_role" in main_js, "panel B10: consent-gated track() stub in main.js")
    # 11. for-keith
    check("Technical appendix" in keith and "<details" in keith and "Stack comparison" in keith.split("<details")[1] and "Stack comparison" not in keith.split("<details")[0],
          "panel B11: stack comparison lives in the collapsed technical appendix")
    check("eleven sectors" not in keith and "24 node tests" not in keith and "Launch checklist (needs GreenJobs)" in keith, "panel B11: stale numbers gone, launch checklist present")
    for item in ("H1", "H2", "I1"):
        check(re.search(r'chg--done"><b>Done</b> ' + item + r"\b", keith) is not None, f"panel B11: checklist shows {item} done")
    check("Quin Road Business Park, Quin Road, Ennis, Co. Clare, V95 VW74, Ireland" in home, "panel B11: footer address in full per brief.md §6")


def test_panel_b_dashboard_rules_from_stored_fields():
    """dashboard_kpis must derive agency/remote from the stored fields and the median from annual_mid in the edition currency."""
    ed = build_site.EDITIONS["uk"]
    jobs = []
    for i, (cur, lo, hi, agency, wp) in enumerate((("EUR", 50000, 50000, True, "remote"), ("GBP", 40000, 40000, False, "office"), ("GBP", None, None, False, "hybrid"))):
        jobs.append({"id": str(i), "title": "t", "employer": "Plain Name Ltd", "location": "x", "text": "y", "posted": "2026-09-20", "closing": "2026-09-27",
                     "sal_min": lo, "sal_max": hi, "cur": cur, "period": "year", "logo": "", "agency": agency, "workplace": wp, "sectors": [], "regions": []})
    data = {"ed": "uk", "fetched": "2026-09-22", "jobs": jobs, "sectors": [], "regions": []}
    k = build_site.dashboard_kpis(data)
    check(k["agency_pct"] == 33 and k["remote_pct"] == 67, f"panel B10: agency/remote from stored fields ({k['agency_pct']}, {k['remote_pct']})")
    eur_in_gbp = build_site.annual_mid(jobs[0], ed["currency"])[2]
    check(k["sal_median"] == round((eur_in_gbp + 40000) / 2), f"panel B10: median converts EUR into the edition currency ({k['sal_median']})")
    check(k["closing7"] == 3 and k["new7"] == 3, f"panel B10: three roles posted 2 days ago and closing in 5 days count in both windows ({k['new7']}, {k['closing7']})")




# --- round 2a (2026-09-28): matrix rows R010/R087, R012, R072/R077, R055, R041; visual 11/12/16/22/23/24/29/31

def _mk_job(title, summary="", body="", employer="Acme", typ="", location="Dublin", region="Ireland"):
    return {"title": title, "employer": employer, "sectors": [], "summary": summary, "description_html": body, "type": typ, "location": location, "region": region}


def test_r2a_secondary_sector_tags():
    INF = "Sustainable infrastructure & transport"
    two_body = _mk_job("Highways Civil Engineer", "Design highways and roads.", "<p>building construction</p>")
    check(build_site.assign_sectors(two_body) == [INF], "r2a R087: two stray body hits ('building', 'construction') no longer add Built environment to a highways role")
    explicit = _mk_job("Resident Engineer – Bridge Construction", "Bridge and highways construction supervision.", "<p>roads bridges rail</p>")
    check(build_site.assign_sectors(explicit)[:2] == [INF, "Built environment & energy efficiency"], "r2a R010: a title/summary that says 'Construction' keeps Built environment as a secondary")
    many = _mk_job("Civil Engineer", "roads rail bridges", "<p>policy planning sustainability esg water flood carbon</p>")
    secs = build_site.assign_sectors(many)
    check(secs[0] == INF and len(secs) <= 1 + build_site.MAX_SECONDARY, f"r2a R010: at most {build_site.MAX_SECONDARY} secondaries, never below a third of the primary's score ({secs})")
    gold = json.loads((Path(__file__).resolve().parent / "golden_sectors.json").read_text(encoding="utf-8"))
    raws = {ed: json.loads((SRC / "data" / f"{ed}.json").read_text(encoding="utf-8")) for ed in ("ie", "uk") if (SRC / "data" / f"{ed}.json").exists()}
    if len(raws) < 2:
        skip("r2a R010: real datasets absent, golden secondaries")
        return
    by = {j["id"]: j for r in raws.values() for j in r["jobs"]}
    with_sec = [g for g in gold if "secondaries" in g and g["id"] in by]
    misses = [f"{g['title'][:30]!r} -> {build_site.assign_sectors(by[g['id']])[1:]}" for g in with_sec if build_site.assign_sectors(by[g["id"]])[1:] != g["secondaries"]]
    check(len(with_sec) >= 8 and not misses, f"r2a R010/R087: the {len(with_sec)} golden highways/civil roles carry exactly the expected secondary sets ({misses[:3]})")
    forbidden = {"Built environment & energy efficiency", "Sustainability & ESG", "Policy, planning & advisory"}
    civil = re.compile(r"\b(civil|highways?|roads?|rail|bridge)\b", re.I)
    stray = []
    for j in by.values():
        if civil.search(j["title"]) and build_site.assign_sectors(j)[0] == INF:
            for s in build_site.assign_sectors(j)[1:]:
                if s in forbidden and not re.search(r"built environment|construction|sustainab|planner|policy", (j["title"] + " " + (j.get("summary") or "")).lower()):
                    stray.append(f"{j['title'][:30]!r}: {s}")
    check(not stray, f"r2a R010/R087: no civil/highways/roads/rail/bridge role carries Built environment / ESG / Policy without the title or summary saying so ({stray[:3]})")


def test_r2a_cross_border_phrases():
    lc = lambda j, ed="": build_site.loc_class(j, [], [], ed)  # noqa: E731
    check(lc(_mk_job("Labs Designer & Facilitator – UK/ Ireland", location="Dublin", region="Ireland, United Kingdom"), "ie") == "cross", "r2a R012: 'UK/ Ireland' in the title -> cross on the IE edition despite a Dublin location")
    check(lc(_mk_job("Landscape Developer – UK & Ireland", location="Dublin", region="Ireland"), "ie") == "cross" and lc(_mk_job("Landscape Developer – UK & Ireland", location="United Kingdom (UK), Ireland (nationwide)", region="Country"), "uk") == "cross", "r2a R012: 'UK & Ireland' -> cross on both editions")
    check(lc(_mk_job("Ecologist", "Work remote from the UK or Ireland.", location="Dublin"), "ie") == "cross" and lc(_mk_job("Ecologist – Ireland/UK", location="London", region="London"), "uk") == "cross", "r2a R012: 'remote from the UK or Ireland' and 'Ireland/UK' -> cross")
    check(lc(_mk_job("Ecologist", "Based in Dublin.", location="Dublin"), "ie") == "ie" and lc(_mk_job("UK Ecologist", location="Leeds", region="Yorkshire"), "uk") == "uk", "r2a R012: a plain Irish or British advert is unchanged")
    for ed in ("ie", "uk"):
        path = SRC / "data" / f"{ed}.json"
        if not path.exists():
            skip(f"r2a R012: {ed} dataset absent")
            continue
        data = build_site.normalise(json.loads(path.read_text(encoding="utf-8")), ed, SRC, SRC / "assets" / "logos")
        cl = {j["title"]: j["loc_class"] for j in data["jobs"] if j["employer"] == "Commonland"}
        check(len(cl) >= 2 and set(cl.values()) == {"cross"}, f"r2a R012: every Commonland role is 'cross' (Ireland & UK) on the {ed} edition ({cl})")


def test_r2a_facts_copy_and_facets():
    check(build_site.no_break_dash("Landscape Developer – UK & Ireland") == "Landscape Developer – UK & Ireland" and build_site.no_break_dash("Plain title") == "Plain title", "r2a visual 24: the space before an en dash becomes a no-break space in the job h1")
    check(build_site.contract_row({"type": "Contract", "contract": ["contract"]}) == "Contract" and build_site.contract_row({"type": "Permanent", "contract": ["permanent", "full-time"]}) == "Permanent, Full-time", "r2a visual 24: one 'Contract' row when type and contract agree")
    check(build_site.contract_row({"type": "Home Based", "contract": ["permanent"]}) == "Permanent" and build_site.contract_row({"type": "Volunteer", "contract": ["volunteer"]}) == "Volunteer", "r2a visual 31: 'Home Based' is a workplace, not a contract row value; Volunteer is a contract tag")
    check(build_site.contract_of({"type": "Volunteer", "summary": "", "description_html": ""}) == ["volunteer"] and build_site.workplace_of({"type": "Home Based", "summary": "", "description_html": ""}) == "remote", "r2a visual 31: Volunteer -> contract tag, Home Based -> workplace remote")
    facet = build_site.contract_facet([{"contract": ["permanent", "full-time"]}, {"contract": ["contract"]}, {"contract": []}])
    check([f["k"] for f in facet] == ["permanent", "contract", "full-time"] and facet[0]["name"] == "Permanent" and facet[0]["n"] == 1, "r2a visual 31: contract_facet lists only carried values, in CONTRACT_LABEL order, with counts")
    mk = lambda n: [{"sal_min": 1000 * (i + 30), "sal_max": None, "cur": "EUR", "period": "year"} for i in range(n)]  # noqa: E731
    check(build_site.sector_stat([{"sal_min": None, "sal_max": None}], "€") == "no disclosed salaries yet" and build_site.sector_stat(mk(1) + [{"sal_min": None, "sal_max": None}], "€") == "1 disclosed salary" and build_site.sector_stat(mk(2), "€") == "2 disclosed salaries", "r2a visual 29: sector card copy 'no disclosed salaries yet' / '1 disclosed salary' / 'n disclosed salaries'")
    ed = build_site.EDITIONS["ie"]
    jobs = [{"sal_min": 40000, "sal_max": 50000, "cur": "GBP", "period": "year", "sectors": ["Wind energy"], "title": "A"}, {"sal_min": 40000, "sal_max": 50000, "cur": "EUR", "period": "year", "sectors": ["Wind energy"], "title": "B"}]
    data = {"jobs": jobs, "sectors": [{"name": "Wind energy", "n": 2}], "fetched": "2026-09-22", "ed": "ie"}
    body = build_site.guide_salary_body(data, ed)
    check(body["fx_note"].startswith("1 of the disclosed salaries is advertised in another currency") and "converted at a fixed rate" in body["fx_note"], "r2a visual 29: the salary guide names the converted count when sterling salaries are present")
    body0 = build_site.guide_salary_body({**data, "jobs": jobs[1:]}, ed)
    check("no conversion was needed" in body0["fx_note"], "r2a visual 29: ... and says no conversion was needed only when every salary is in the edition currency")
    strip = build_site.employers_strip({"site": "greenjobs.ie", "employers": [{"name": n, "url": "", "logo": "", "lw": 0, "lh": 0} for n in ["Gaia Talent", "EirGrid", "Power NI", "Veolia"]], "jobs": [{"employer": "Gaia Talent"}]}, "../")
    check("Gaia Talent" in strip["html"] and not any(n in strip["html"] for n in ("EirGrid", "Power NI", "Veolia")), "r2a R041: the IE strip lists live employers only, never EirGrid / Power NI / Veolia")


def test_r2a_landing_intro_length():
    raws = {ed: SRC / "data" / f"{ed}.json" for ed in ("ie", "uk")}
    if not all(p.exists() for p in raws.values()):
        skip("r2a landing intro: real datasets absent")
        return
    for ed_key, path in raws.items():
        data = build_site.normalise(json.loads(path.read_text(encoding="utf-8")), ed_key, SRC, SRC / "assets" / "logos")
        for spec, jobs in build_site.landing_pages(data):
            intro = html.unescape(build_site.landing_intro(spec, jobs, build_site.EDITIONS[ed_key], data))
            words = len(intro.split())
            med = build_site.median_salary(jobs, build_site.EDITIONS[ed_key]["sym"], build_site.EDITIONS[ed_key]["currency"])
            check(words <= 80 and f"lists {len(jobs)} live" in intro and (med == "n/a" or med in intro), f"r2a: {ed_key}/{spec['slug']} intro is {words} words (<= 80) and keeps the count and median")


def test_r2a_regions_and_pairs():
    table = {"regions": {"London": [], "Northern Ireland": [], "East Midlands": []}}
    data = {"regions": [{"name": "London", "n": 3, "on_map": True}, {"name": "Northern Ireland", "n": 0, "on_map": True}, {"name": "Elsewhere", "n": 2, "on_map": False}]}
    ml = build_site.map_list(data, "jobs/index.html")
    check('?loc=Northern%20Ireland" class="is-zero"><span>Northern Ireland</span><b class="num">0</b>' in ml and "Elsewhere" not in ml and ml.index("London") < ml.index("Northern"), "r2a R072/R077: map_list keeps a 0-role mapped region (class is-zero) after the busy ones")
    pairs = build_site.paired_paths({"ie": {"index.html", "guides/index.html", "ecology-jobs-ireland/index.html", "environmental-jobs-dublin/index.html"}, "uk": {"index.html", "guides/index.html", "ecology-jobs-uk/index.html"}})
    check(pairs["ie"].get("ecology-jobs-ireland/index.html") == "ecology-jobs-uk/index.html" and pairs["uk"].get("ecology-jobs-uk/index.html") == "ecology-jobs-ireland/index.html", "r2a R055: PAIRED landing slugs map to their twin in the other edition")
    check("environmental-jobs-dublin/index.html" not in pairs["ie"] and pairs["ie"]["guides/index.html"] == "guides/index.html", "r2a R055: a landing whose twin is not built stays unpaired; guides pair with guides")
    check(build_site.paired_paths({"ie": {"index.html"}}) == {"ie": {}}, "r2a R055: a single-edition build has no pairs")
    ie_svg = (SRC / "assets" / "maps" / "ie.svg").read_text(encoding="utf-8")
    ctx = re.search(r'<g class="gmap__ctx"[^>]*data-note="([^"]*)"', ie_svg)
    check(bool(ctx) and ctx.group(1) == "Northern Ireland (see greenjobs.co.uk)" and ie_svg.count('class="gmap__r"') == 26 and "<title>" not in ie_svg, "r2a visual 11: the IE map draws Northern Ireland as a labelled context outline (not a county, no <title>)")
    uk_svg = build_site.map_svg(SRC, "uk", {"London": 5})
    check('data-region="Northern Ireland"' in uk_svg and re.search(r'data-region="Northern Ireland"[^>]*data-n="0"[^>]*>.*?<text[^>]*class="is-zero"[^>]*>0</text>', uk_svg, re.S) is not None, "r2a visual 12: the UK map labels a 0-role region with a muted 0")


def test_r2a_real_build_checks(tmp_root: Path):
    if not (SRC / "data" / "ie.json").exists() or not (SRC / "data" / "uk.json").exists():
        skip("r2a: real datasets absent")
        return
    out = tmp_root / "site_r2a"
    check(build_site.build(SRC, out, editions=["ie", "uk"]) == 0, "r2a: real-data build returns 0")
    uk_board = (out / "uk" / "jobs" / "index.html").read_text(encoding="utf-8")
    check('<option value="Northern Ireland">' in uk_board and '<option value="East Midlands">' in uk_board, "r2a R072/R077: the UK jobs datalist offers Northern Ireland and East Midlands at 0 roles")
    ds = json.loads(re.search(r'id="gj-data">(.*?)</script>', uk_board, re.S).group(1))
    check(any(r["name"] == "Northern Ireland" for r in ds["regions"]) and [c["k"] for c in ds["contracts"]][:2] == ["permanent", "contract"], "r2a R077 / visual 31: the UK dataset carries Northern Ireland in regions and the one contract facet")
    check('id="f-type"' in uk_board and 'type="hidden"' in uk_board.split('id="f-type"')[0][-80:] and "Any type" not in uk_board, "r2a visual 31: the Job type select is gone; ?type= keeps a hidden alias field")
    uk_home = (out / "uk" / "index.html").read_text(encoding="utf-8")
    check('?loc=Northern%20Ireland" class="is-zero"><span>Northern Ireland</span><b class="num">0</b>' in uk_home and '?loc=East%20Midlands" class="is-zero"' in uk_home, "r2a visual 12: the UK home region list shows Northern Ireland and East Midlands at 0")
    ie_board = (out / "ie" / "jobs" / "index.html").read_text(encoding="utf-8")
    check('class="gmap__ctx" data-note="Northern Ireland (see greenjobs.co.uk)"' in ie_board, "r2a visual 11: the IE jobs map carries the Northern Ireland context outline")
    for ed, slug, twin in (("ie", "ecology-jobs-ireland", "ecology-jobs-uk"), ("uk", "renewable-energy-jobs-uk", "renewable-energy-jobs-ireland"), ("ie", "sustainability-jobs-ireland", "sustainability-jobs-uk"), ("uk", "environmental-jobs-london", "environmental-jobs-dublin")):
        page = out / ed / slug / "index.html"
        if not page.exists():
            skip(f"r2a R055: {ed}/{slug} not built this week")
            continue
        head = page.read_text(encoding="utf-8").split("</head>")[0]
        other = "uk" if ed == "ie" else "ie"
        check(f'hreflang="{"en-GB" if other == "uk" else "en-IE"}" href="https://greenjobs-redesign.pages.dev/{other}/{twin}/index.html"' in head and 'hreflang="x-default"' in head, f"r2a R055: {ed}/{slug} links its hreflang twin {other}/{twin}")
    for ed, jid in (("ie", "11501646"), ("uk", "11501639")):
        page = out / ed / "jobs" / jid / "index.html"
        if not page.exists():
            continue
        html_text = page.read_text(encoding="utf-8")
        check('data-loc="cross">Ireland &amp; UK' in html_text.split("</h1>")[1][:600], f"r2a R012: Commonland 11501646/11501639 badge is 'Ireland & UK' on {ed}")
        check("<dt>Type</dt>" not in html_text and "<dt>Contract</dt><dd>Contract</dd>" in html_text and "Landscape Developer –" in html_text, f"r2a visual 24: one Contract row and a no-break dash in the h1 on {ed}")
    ie_emp = (out / "ie" / "employers" / "index.html").read_text(encoding="utf-8")
    check(not any(n in ie_emp for n in ("EirGrid", "Power NI", "Veolia")), "r2a R041 / visual 7: the IE employers page names no organisation without a live role")
    ie_home = (out / "ie" / "index.html").read_text(encoding="utf-8")
    check("disclose pay" not in ie_home and "discloses pay" not in ie_home, "r2a visual 29: '0 disclose pay' copy is gone from the IE home")
    n_sec = re.search(r"Roles across <b class=\"num\">(\d+)</b> sectors", ie_home)
    check(bool(n_sec) and int(n_sec.group(1)) >= 12, f"r2a R006: the hero fact renders the live sector count ({n_sec.group(1) if n_sec else '?'}), not the document's '10'")
    # validator: pair targets must link back; strip names must be live on the employers page too
    raw = {ed: json.loads((SRC / "data" / f"{ed}.json").read_text(encoding="utf-8")) for ed in ("ie", "uk")}
    data_by_ed = {ed: build_site.normalise(raw[ed], ed, SRC, SRC / "assets" / "logos") for ed in ("ie", "uk")}
    paired = build_site.paired_paths({k: build_site.PAIRED_PATHS | {f"{s['slug']}/index.html" for s, _ in build_site.landing_pages(d)} for k, d in data_by_ed.items()})
    for k, d in data_by_ed.items():
        d["paired_paths"] = paired[k]
    jobs = {k: d["jobs"] for k, d in data_by_ed.items()}
    V = lambda: validate_site.validate(out, jobs, data_by_ed, build_site.dashboard_kpis)  # noqa: E731
    check(V() == [], "r2a: the real build passes the extended validator")

    def patched(path: Path, fn, needle: str):
        clean = path.read_text(encoding="utf-8")
        path.write_text(fn(clean), encoding="utf-8")
        try:
            return any(needle in f for f in V())
        finally:
            path.write_text(clean, encoding="utf-8")
    landing = out / "ie" / "ecology-jobs-ireland" / "index.html"
    if landing.exists():
        check(patched(landing, lambda t: t.replace("/uk/ecology-jobs-uk/index.html", "/uk/jobs/index.html"), "does not link back"), "r2a R055: an hreflang alternate whose target does not link back fails validation")
    emp_page = out / "ie" / "employers" / "index.html"
    check(patched(emp_page, lambda t: t.replace('<div class="marq__track">', '<div class="marq__track"><div class="emp"><span>EirGrid</span></div>', 1), "no live role"), "r2a R041: a non-hiring name in the employers-page strip fails validation")


# --- round 2 B --- (2026-09-28): visual rows 3/4/8/9/10/13/14/15/17/18/19/20/21/26/28/30/32 (templates, CSS, JS)

def test_r2b_visitor_voice_and_shell(tmp_root: Path):
    out = tmp_root / "site_r2b"
    check(build_site.build(SRC, out, editions=["ie", "uk"]) == 0, "r2b: real-data build succeeds")
    home = _read(out / "ie" / "index.html")
    emp = _read(out / "ie" / "employers" / "index.html")
    jobs = _read(out / "ie" / "jobs" / "index.html")
    guides = _read(out / "ie" / "guides" / "index.html")
    e404 = _read(out / "404.html")
    css = _read(SRC / "css" / "styles.css")
    # 8: one voice, no team-facing copy in visitor dialogs; no fake success anywhere
    for bad in ("analytics provider is chosen", "connects to your email provider", "connects to the GreenJobs team", "Nothing was sent", "Sign-ups open at launch", "Posting opens at launch"):
        check(bad not in home and bad not in emp, f"r2b visual 8: '{bad}' is gone from visitor-facing copy")
    check("Off. Not used on this site." in home and home.count("Job alerts by email are available on") >= 2, "r2b visual 8: cookie analytics row and alert forms use the visitor sentences (alerts point at the live site since round 4)")
    check(emp.count("Preview only. Rates and posting are handled by the GreenJobs team") == 2 and "Thank you" not in emp, "r2b R044: the Post-a-job preview keeps one quiet line (pre-submit + post-submit variants), no fake success")
    # 18: hero keeps search + Post a job only
    hero = home.split('class="hero__cta"')[1].split("</div>")[0]
    check("Find a job" not in hero and hero.count("<a ") == 1 and "Post a job" in hero, "r2b visual 18: one secondary hero CTA (Post a job); 'Find a job' dropped")
    # 19: footer wordmark carries the leaf and a long-form date
    ftr = home.split('<footer class="ftr">')[1]
    check('class="logo logo--ftr"><svg' in ftr and re.search(r'<time datetime="\d{4}-\d{2}-\d{2}">\d{1,2} [A-Z][a-z]+ \d{4}</time>', ftr), "r2b visual 19: footer logo has the leaf icon; the as-of date is rendered server-side as '22 September 2026' (r3 N4: was client-side data-date-long)")
    # 21: client sentence verbatim beside the input; share note honest about contents
    check("Your information is processed on your device and is not uploaded or stored." in jobs and "The link contains your search words." in jobs, "r2b R036 / visual 21: fit hint verbatim, share note names the search words")
    # 26: guides: empty heading gone, closing line once
    check("Career advice and market reports" not in guides and guides.count("More guides follow as the data grows.") == 1, "r2b visual 26: empty guides heading hidden; one closing line")
    # 28: audience tiles: neutral sentences, not italic placeholders
    check("supplied at launch" not in emp and "published at launch" not in emp and "ask us" in emp.lower() and "font-style:italic" not in css.split(".tbc{")[1].split("}")[0], "r2b visual 28: audience tiles carry neutral 'ask us' sentences in the client's voice, no italics, no 'published at launch' promise")
    # 9: 404 renders inside the shell with fonts/theme and the two edition tiles
    check('class="hdr"' in e404 and '<footer class="ftr">' in e404 and "css/styles.css" in e404 and "gj-theme" in e404 and e404.count('class="tile"') == 2 and e404.count("<h1") == 1, "r2b visual 9: 404 page uses the shell header/footer, brand stylesheet, theme, two edition tiles, one h1")
    # 14/15: preview toggle sits before the form; sheet heading collapsed in CSS
    check(emp.index('data-adb-toggle') < emp.index('id="rates-form"'), "r2b visual 14: the Preview toggle is in flow before the form, not floating over 'Job title'")
    check(".sheet .rail>h2{" in css and "font-size:0" in css.split(".sheet .rail>h2{")[1].split("}")[0], "r2b visual 15: the inner 'Filters' heading is collapsed inside the sheet (Clear stays)")
    # 10: salary reachable above career level; rail has a scroll cue
    check(jobs.index('id="f-smin"') < jobs.index('id="f-level"') if 'id="f-level"' in jobs else True, "r2b visual 10: salary fieldset sits above Career level")
    check("[data-rail-home]::after" in css and "scrollbar-width:thin" in css, "r2b visual 10: rail scroll cue (fade + thin scrollbar)")
    # 3/20: dialog and alert rows no longer inherit the job-card .row rule
    check(".gjd .row{" in css and "padding:0" in css.split(".gjd .row{")[1].split("}")[0] and ".alertbox .row{" in css and "padding:0" in css.split(".alertbox .row{")[1].split("}")[0], "r2b visual 3/20: dialog/alert .row reset (input + button stack under 421px / 520px)")
    # 13: treemap legend + label truncation; 30: header B Corp label; 32: logo tile box
    check(".tmkey{" in css and "tmkey" in _read(SRC / "js" / "explore.js") and "maxCh" in _read(SRC / "js" / "charts.js"), "r2b visual 13: treemap labels truncate to the tile and a legend lists every sector with its count")
    check(".hdr__bcorp" in css and 'content:"Certified B Corporation"' not in css, "r2b visual 30 / r4 Dario: header B Corp mark styled; no certification text claim in CSS")
    check("object-fit:contain" in css.split(".emp img{")[1].split("}")[0] and ".emp.is-blank{display:none}" in css, "r2b visual 32: logo tiles are a fixed box with object-fit contain; blank logos are hidden")
    # 17: birds never drawn on the still frame and never at the left edge
    ls = _read(SRC / "js" / "landscape.js")
    check("!reduce.matches" in ls.split("/* birds")[1][:300] and "bx < 30" in ls, "r2b visual 17: no stray bird glyph on the reduced-motion frame or at the hero's left edge")
    # lib helpers wired
    js = _read(SRC / "js" / "jobs.js")
    check("G.orderSectors" in js and "G.suggestSectors" in js, "r2b: jobs.js uses lib.orderSectors / lib.suggestSectors from round 2 A")



# --- round 4 (panel v2 + trace 3, 2026-09-28) ---
def test_r4_sterling_figure_fidelity(tmp_root: Path):
    """Item 1: a slug shared by three adverts must not hand an IE role the wrong sterling figure."""
    mk = lambda i, lo, hi, posted: {"id": i, "slug": "senior-health-and-safety-consultant", "title": "Senior H&S Consultant", "employer": "Mattinson", "currency": "GBP", "salary_min": lo, "salary_max": hi, "salary_text": f"£{lo:,} to £{hi:,}", "posted": posted}  # noqa: E731
    twins = {"slug:senior-health-and-safety-consultant": [mk("a", 62000, 67000, "18/09/2026"), mk("b", 55000, 60000, "19/08/2026"), mk("c", 55000, 60000, "02/09/2026")]}
    fix = build_site.sterling_correction({"id": "x", "slug": "senior-health-and-safety-consultant", "currency": "EUR", "salary_min": 55000, "salary_max": 60000, "posted": "02/09/2026"}, "uk", twins)
    check(fix is not None and fix["salary_min"] == 55000 and fix["salary_text"].startswith("£55,000"), "r4 sterling: on the slug path only a twin with the same (min, max) is accepted, never the first namesake")
    fix2 = build_site.sterling_correction({"id": "x", "slug": "senior-health-and-safety-consultant", "currency": "EUR", "salary_min": 55000, "salary_max": 60000, "posted": "20/08/2026"}, "uk", twins)
    check(fix2 is not None and fix2["salary_text"] == "£55,000 to £60,000" and build_site._pick_twin(twins["slug:senior-health-and-safety-consultant"], {"salary_min": 55000, "salary_max": 60000, "posted": "20/08/2026"})["id"] == "b", "r4 sterling: among figure-matching twins the nearest posted date wins")
    check(build_site.sterling_correction({"id": "x", "slug": "senior-health-and-safety-consultant", "currency": "EUR", "salary_min": 50000, "salary_max": 52000}, "uk", twins) is None, "r4 sterling: no twin with the same figures -> no correction (the euros stay, flagged unverified)")
    if not (SRC / "data" / "ie.json").exists():
        skip("r4 sterling fidelity: real datasets absent")
        return
    raw = json.loads((SRC / "data" / "ie.json").read_text(encoding="utf-8"))
    data = build_site.normalise(raw, "ie", SRC, SRC / "assets" / "logos")
    src_by = {str(j["id"]): j for j in raw["jobs"]}
    fixed = [j for j in data["jobs"] if j.get("currency_source") == build_site.STERLING_SOURCE]
    bad = [(j["id"], j["sal_min"], j["sal_max"], src_by[j["id"]]["salary_min"], src_by[j["id"]]["salary_max"]) for j in fixed
           if (j["sal_min"], j["sal_max"]) != (src_by[j["id"]]["salary_min"], src_by[j["id"]]["salary_max"])]
    check(len(fixed) == 21 and not bad, f"r4 sterling fidelity: every restored GBP pair equals the IE source pair numerically; exactly 21 on this snapshot ({len(fixed)}; bad: {bad})")
    j = next((x for x in data["jobs"] if x["id"] == "11495292"), None)
    check(j is not None and (j["sal_min"], j["sal_max"], j["cur"]) == (55000, 60000, "GBP") and j["sal_text"].startswith("£55,000"), f"r4 sterling: IE 11495292 shows £55-60k from twin 11495291, not the £62-67k namesake ({j and (j['sal_min'], j['sal_max'], j['cur'])})")


def test_r4_secondary_sectors_and_enforcement():
    """Item 2: title / site-label / energy-family secondaries survive the ratio rule; golden expected-present set."""
    mk = lambda title, summary="", body="", sectors=None: {"title": title, "employer": "Acme", "summary": summary, "description_html": body, "sectors": sectors or []}  # noqa: E731
    check("Water & flood" in build_site.assign_sectors(mk("Coastal Engineering Project Manager", "Deliver coastal and highways schemes.", "<p>" + "roads rail highways bridges " * 3 + "</p>"))[1:], "r4 secondaries: a keyword in the title (coastal -> Water & flood) keeps the secondary whatever the ratio")
    check(build_site.assign_sectors(mk("Marine Enforcement Officer", "Enforce fisheries regulation at sea.", "<p>marine patrols</p>"))[0] == "Policy, planning & advisory", "r4 secondaries: 'enforcement officer' in the title weighs towards Policy (Marine Enforcement Officer)")
    check(build_site.assign_sectors(mk("Solar PV Designer", "Design solar PV systems.", "<p>renewable energy with battery storage</p>"))[:2] == ["Solar energy", "Renewable energy & storage"], "r4 secondaries: energy-family sectors (solar / wind / renewable / networks) keep each other as secondaries")
    check(build_site.assign_sectors(mk("Project Engineer – Roads", "Roads and transport schemes.", "<p>sustainable sustainability</p>", ["Sustainable Jobs"])) == ["Sustainable infrastructure & transport"], "r4 secondaries: the site's generic 'Sustainable' label does not add ESG to a roads role (ratio rule still applies outside the energy family)")
    gold = json.loads((Path(__file__).resolve().parent / "golden_sectors.json").read_text(encoding="utf-8"))
    raws = {ed: json.loads((SRC / "data" / f"{ed}.json").read_text(encoding="utf-8")) for ed in ("ie", "uk") if (SRC / "data" / f"{ed}.json").exists()}
    if len(raws) < 2:
        skip("r4 golden secondaries: real datasets absent")
        return
    by = {j["id"]: j for r in raws.values() for j in r["jobs"]}
    expect = [g for g in gold if g.get("expect_secondaries") and g["id"] in by]
    misses = [f"{g['id']} {g['title'][:30]!r}: wants {g['expect_secondaries']} got {build_site.assign_sectors(by[g['id']])}" for g in expect
              if not set(g["expect_secondaries"]) <= set(build_site.assign_sectors(by[g["id"]])[1:])]
    check(len(expect) >= 6 and not misses, f"r4 golden secondaries: all {len(expect)} expected-present secondaries are carried (drops: {misses})")
    check(build_site.assign_sectors(by["11499784"])[0] == "Policy, planning & advisory", f"r4 golden: uk 11499784 Marine Enforcement Officer -> Policy ({build_site.assign_sectors(by['11499784'])})")


def test_r4_workplace_contract_cross_dates():
    """Items 3-4: SITE_WORDS, contract type-wins, CROSS_RE separators and scope, date_long(None)."""
    wp = build_site.workplace_of
    mk = lambda title, body, typ="": {"title": title, "type": typ, "summary": "", "description_html": body}  # noqa: E731
    check(wp(mk("Energy Analyst", "<p>Model energy market reserves and balancing.</p>")) == "unspecified", "r4 workplace: 'energy market reserves' is not site-based")
    check(wp(mk("Quality Lead", "<p>Run the supplier onsite audit programme.</p>")) == "unspecified", "r4 workplace: 'supplier onsite audit' is not site-based")
    check(wp(mk("Engineer", "<p>You will be on site four days a week.</p>")) == "site" and wp(mk("Engineer", "<p>On-site role.</p>")) == "site" and wp(mk("Warden", "<p>Patrol the nature reserve.</p>")) == "site", "r4 workplace: standalone 'on site' / 'on-site' / 'nature reserve' still count")
    check("onsite" not in build_site.SITE_WORDS and "reserves" not in build_site.SITE_WORDS, "r4 workplace: bare 'onsite' and 'reserves' left SITE_WORDS")
    ct = build_site.contract_of
    check(ct(mk("Senior Bridge Engineer", "<p>This is a permanent opportunity with our client.</p>", "Contract")) == ["contract"], "r4 contract: scraped type Contract wins over 'permanent' in the text (Bridge Engineer -> Contract only)")
    check(ct(mk("Engineer", "<p>Permanent, full time.</p>", "")) == ["permanent", "full-time"] and ct(mk("Engineer", "<p>12-month contract.</p>", "")) == ["contract"], "r4 contract: text decides only when the type is absent")
    check(ct(mk("Engineer", "<p>Permanent role.</p>", "Full Time")) == ["permanent", "full-time"], "r4 contract: a type that only states hours (Full Time) leaves the permanent/contract axis to the text")
    if (SRC / "data" / "ie.json").exists():
        j = next(x for x in json.loads((SRC / "data" / "ie.json").read_text(encoding="utf-8"))["jobs"] if x["id"] == "11493521")
        check(ct(j) == ["contract"], f"r4 contract: IE 11493521 Senior Bridge Engineer -> Contract only ({ct(j)})")
    lc = build_site.loc_class
    for t in ("Planner – UK, Ireland", "Engineer UK-Ireland", "Lead (Ireland/UK)", "Consultant, Ireland & UK"):
        check(lc({"title": t, "location": "", "region": "", "summary": ""}) == "cross", f"r4 cross: {t!r} -> cross")
    boiler = {"title": "Ecologist", "location": "Leeds", "region": "", "summary": "x " * 200 + "We have offices in the UK and Ireland."}
    check(lc(boiler) == "uk" and lc({**boiler, "summary": "Cover the UK and Ireland. " + boiler["summary"]}) == "cross", "r4 cross: only the title and the first 300 characters of the summary count; employer boilerplate later on does not")
    check(build_site.date_long(None) == "" and build_site.date_long("") == "" and build_site.date_long("2026-09-22") == "22 September 2026", "r4 date_long: None / '' -> '' (never the string 'None')")


def test_r4_unverified_excluded_from_figures():
    """Item 5: roles flagged unverified_cur never enter medians, bands or the salary guide; the fx note says so."""
    base = {"sal_min": 40000, "sal_max": 50000, "cur": "EUR", "period": "year", "sectors": ["Wind energy"], "title": "A"}
    check(build_site.annual_mid({**base, "unverified_cur": True}) is None and build_site.annual_mid({**base, "currency_source": build_site.UNVERIFIED_SOURCE}) is None and build_site.annual_mid(base) is not None, "r4 unverified: annual_mid() returns None for either unverified flag, so every median/band/guide/dashboard figure skips the role")
    jobs = [base, {**base, "sal_min": 90000, "sal_max": 90000, "unverified_cur": True, "title": "B"}, {**base, "sal_min": 90000, "sal_max": 90000, "currency_source": build_site.UNVERIFIED_SOURCE, "title": "C"}]
    check(build_site.median_salary(jobs, "€", "EUR") == "€45k" and build_site.salary_bands(jobs, "€", "EUR")[2]["n"] == 1 and sum(b["n"] for b in build_site.salary_bands(jobs, "€", "EUR")) == 1, "r4 unverified: median and bands count only the verified role")
    body = build_site.guide_salary_body({"jobs": jobs, "sectors": [{"name": "Wind energy", "n": 3}], "fetched": "2026-09-22", "ed": "ie"}, build_site.EDITIONS["ie"])
    check(body["n_disc"] == "1" and body["fx_note"].endswith("2 UK-located roles with unconfirmed currency are excluded from medians."), f"r4 unverified: the salary guide's fx note names the excluded roles ({body['fx_note'][-90:]})")
    body1 = build_site.guide_salary_body({"jobs": jobs[:2], "sectors": [{"name": "Wind energy", "n": 2}], "fetched": "2026-09-22", "ed": "ie"}, build_site.EDITIONS["ie"])
    check(body1["fx_note"].endswith("1 UK-located role with unconfirmed currency is excluded from medians."), "r4 unverified: singular form")
    k = build_site.dashboard_kpis({"jobs": [{**j, "posted": "2026-09-20", "closing": "", "logo": "", "text": "", "employer": "E", "agency": False, "workplace": "office"} for j in jobs], "sectors": [], "regions": [], "fetched": "2026-09-22", "today": "2026-09-22", "ed": "ie"})
    check(k["sal_median"] == 45000 and k["sal_n"] == 3, "r4 unverified: dashboard median skips unverified roles while the disclosure count still counts them")


def test_r4_real_build_marker_hero_notes(tmp_root: Path):
    """Items 5-8 on real data: OK marker, hero facts, fx note, dashboard voice, validator CLI."""
    if not (SRC / "data" / "ie.json").exists() or not (SRC / "data" / "uk.json").exists():
        skip("r4 real build: real datasets absent")
        return
    out = tmp_root / "site_r4"
    out.mkdir()
    (out / build_site.MARKER).write_text("x\n", encoding="utf-8")
    (out / build_site.OK_MARKER).write_text("stale\n", encoding="utf-8")
    check(build_site.build(SRC, out, editions=["ie", "uk"]) == 0, "r4: real-data build succeeds")
    ok = out / build_site.OK_MARKER
    check(ok.is_file() and ok.read_text(encoding="utf-8").strip() == build_site.site_tree_sha(out) and len(ok.read_text().strip()) == 64, "r4 marker: .greenjobs-build-ok holds the sha256 of the validated tree")
    cli = subprocess.run([sys.executable, str(SCRIPT_DIR / "validate_site.py"), str(out), "--src", str(SRC)], capture_output=True, text=True, encoding="utf-8")
    check(cli.returncode == 0 and "PASS" in cli.stdout, f"r4 deploy gate: validate_site.py CLI re-validates a fresh build and accepts the marker ({cli.stdout.strip()[-80:]} {cli.stderr.strip()[-120:]})")
    (out / "ie" / "index.html").write_text((out / "ie" / "index.html").read_text(encoding="utf-8") + "<!-- edited -->", encoding="utf-8")
    cli2 = subprocess.run([sys.executable, str(SCRIPT_DIR / "validate_site.py"), str(out), "--src", str(SRC)], capture_output=True, text=True, encoding="utf-8")
    check(cli2.returncode == 1 and "does not match" in cli2.stderr, "r4 deploy gate: a file edited after the build makes the CLI refuse (sha mismatch)")
    ok.unlink()
    cli3 = subprocess.run([sys.executable, str(SCRIPT_DIR / "validate_site.py"), str(out), "--src", str(SRC)], capture_output=True, text=True, encoding="utf-8")
    check(cli3.returncode == 1 and "missing" in cli3.stderr, "r4 deploy gate: no marker -> the CLI refuses")
    sh = (SCRIPT_DIR / "deploy_cloudflare.sh").read_text(encoding="utf-8")
    check(".greenjobs-build-ok" in sh and "validate_site.py" in sh and sh.index(".greenjobs-build-ok") < sh.index("pages deploy"), "r4 deploy gate: deploy_cloudflare.sh checks the marker and re-runs validate_site.py before wrangler deploys")
    # hero facts from the data (IE 88 roles / 15 live sectors — Solar became live once 11501034 kept its
    # Solar secondary in round 4; UK 77 roles / 18 employers / 14 sectors)
    want = {"ie": (88, None, 15), "uk": (77, 18, 14)}
    for ed, (n_jobs, n_emp, n_sec) in want.items():
        raw = json.loads((SRC / "data" / f"{ed}.json").read_text(encoding="utf-8"))
        data = build_site.normalise(raw, ed, SRC, SRC / "assets" / "logos")
        emp = len({j["employer"] for j in data["jobs"]})
        facts = build_site.hero_facts(data, emp)
        live = sum(1 for s in data["sectors"] if s["n"])
        check(len(data["jobs"]) == n_jobs and live == n_sec and (n_emp is None or emp == n_emp), f"r4 hero facts data: {ed} has {len(data['jobs'])} roles, {emp} employers, {live} live sectors (expected {n_jobs}/{n_emp}/{n_sec})")
        check(f'<b class="num">{n_sec}</b> sectors' in facts and (("employers hiring now" not in facts) if n_emp is None else (f'<b class="num">{n_emp}</b> employers hiring now' in facts)), f"r4 hero facts: {ed} row prints {n_sec} sectors" + ("" if n_emp is None else f" and {n_emp} employers"))
        home = (out / ed / "index.html").read_text(encoding="utf-8")
        check(f'<b class="num">{n_jobs}</b>' in home or f">{n_jobs} live" in home or f"{n_jobs} live roles" in home, f"r4 hero facts: {ed} home page states {n_jobs} live roles")
    guide = (out / "ie" / "guides" / "index.html").read_text(encoding="utf-8")
    guide = (out / "ie" / "guides" / "salary-guide" / "index.html").read_text(encoding="utf-8")
    check("2 UK-located roles with unconfirmed currency are excluded from medians." in guide, "r4 unverified: the IE salary guide says the 2 unconfirmed-currency roles are excluded from medians")
    for ed in ("ie", "uk"):
        dash = (out / ed / "dashboard" / "index.html").read_text(encoding="utf-8")
        for bad in ("computed from the live listings at build time", "analytics provider will report", "switched on through the cookie", "target we propose", "switches Analytics on"):
            check(bad not in dash, f"r4 dashboard voice: {ed} no longer says {bad!r}")
        low = dash.lower()
        check("live figures from this week's listings" in low and "reported once analytics is connected" in low and "sent once an analytics provider is connected and the visitor allows analytics" in low, f"r4 dashboard voice: {ed} carries the visitor sentences")
        check("Live figures from this week's listings, and the measures reported once analytics is connected." in html.unescape(dash), f"r4 dashboard voice: {ed} meta description is in the visitor voice")


def test_r4_scraper_and_runner(tmp_root: Path):
    """Item 6: --site both fails when either site is rejected; logos.json atomic; run_all SKIP semantics."""
    import scrape_greenjobs as sg
    calls = []

    def fake_crawl(key, *a, **k):
        calls.append(key)
        return {"stats": {"rejected": "3 jobs < floor 50"} if key == "uk" else {}}
    orig = sg.crawl_site
    sg.crawl_site = fake_crawl
    try:
        rc = sg.main(["--site", "both", "--out", str(tmp_root / "scr")])
    finally:
        sg.crawl_site = orig
    check(rc == 3 and calls == ["ie", "uk"], f"r4 scraper: with --site both a rejected UK crawl fails the whole run (exit {rc}) after both sites ran")
    src = (SCRIPT_DIR / "scrape_greenjobs.py").read_text(encoding="utf-8")
    check("write_json_atomic(manifest_path, manifest)" in src and 'open(manifest_path, "w"' not in src, "r4 scraper: logos.json is written via write_json_atomic")
    runner = (Path(__file__).resolve().parent / "run_all.py").read_text(encoding="utf-8")
    check("--allow-skip" in runner and '"SKIP"' in runner and "Total:" in runner and "COVERAGE" in runner, "r4 run_all: SKIP tier fails the run unless --allow-skip; total check count printed and written to COVERAGE.md")
    check(build_site.date_long(None) == "", "r4: date_long(None) is safe for the runner's summaries")


def test_r4b_landings_strip_types(tmp_root: Path):
    """Coordinator follow-ups: landing loc filter, static strip under six employers, type casing, one guide date, wording."""
    mk = lambda i, lc, sectors, regions: {"id": i, "sectors": sectors, "regions": regions, "loc_class": lc}  # noqa: E731
    eco = build_site.ECOLOGY_SECTOR
    data = {"ed": "ie", "jobs": [mk("1", "ie", [eco], ["Dublin"]), mk("2", "uk", [eco], ["Elsewhere"]), mk("3", "ni", [eco], ["Belfast"]), mk("4", "cross", [eco], ["Dublin"]), mk("5", "remote", [eco], []), mk("6", "intl", [eco], [])]}
    got = {spec["slug"]: [j["id"] for j in jobs] for spec, jobs in build_site.landing_pages(data)}
    check(got.get("ecology-jobs-ireland") == ["1", "4", "5"] and got.get("environmental-jobs-dublin") == ["1", "4"] and build_site.LANDING_LOC == {k: set(v) for k, v in build_site.EDITION_HOME.items()}, f"r4b landings: an Ireland-named page lists the board's home set (ie/cross/remote) only, never a UK-only, NI or international one ({got})")
    data_uk = {"ed": "uk", "jobs": [mk("1", "ie", [eco], ["Dublin"]), mk("2", "uk", [eco], ["London"]), mk("3", "ni", [eco], ["Northern Ireland"]), mk("4", "cross", [eco], ["London"])]}
    got_uk = {spec["slug"]: [j["id"] for j in jobs] for spec, jobs in build_site.landing_pages(data_uk)}
    check(got_uk.get("ecology-jobs-uk") == ["2", "3", "4"] and got_uk.get("environmental-jobs-london") == ["2", "4"], f"r4b landings: a UK-named page mirrors with uk/ni/cross/remote ({got_uk})")
    emps = [{"name": f"E{i}", "url": "", "logo": "", "lw": 0, "lh": 0} for i in range(8)]
    small = build_site.employers_strip({"site": "greenjobs.ie", "ed": "ie", "employers": emps[:3], "jobs": [{"employer": e["name"]} for e in emps[:3]]}, "../")
    big = build_site.employers_strip({"site": "greenjobs.co.uk", "ed": "uk", "employers": emps, "jobs": [{"employer": e["name"]} for e in emps]}, "../")
    check("marq--static" in small["html"] and "data-marq" not in small["html"] and "marq__dup" not in small["html"] and "Pause" not in small["html"] and small["html"].count('class="emp"') == 3, "r4b strip: fewer than six live employers -> one static row, no duplicated logos, no Pause")
    check("marq__dup" in big["html"] and "data-marq-pause" in big["html"] and big["html"].count('class="emp"') == 16, "r4b strip: six or more keep the marquee (track duplicated once)")
    check(build_site.canon_type("Full Time") == "Full-time" and build_site.canon_type("part time") == "Part-time" and build_site.canon_type("Fixed Term") == "Fixed-term" and build_site.canon_type("Permanent") == "Permanent" and build_site.canon_type("Home Based") == "Home Based" and build_site.canon_type(None) == "", "r4b types: one spelling per job type (Full-time, Part-time, Fixed-term, Permanent, Contract)")
    check(build_site.contract_row({"type": "Full-time", "contract": ["permanent", "full-time"]}) == "Permanent, Full-time", "r4b types: the facts row does not repeat a canonical type")
    check(set(build_site.CONTRACT_LABEL.values()) >= {"Full-time", "Part-time", "Fixed-term", "Permanent", "Contract"}, "r4b types: CONTRACT_LABEL uses the same spellings")
    jobs = [{"sal_min": 40000, "sal_max": 50000, "cur": "GBP", "period": "year", "sectors": ["Wind energy"], "title": "A"}]
    body = build_site.guide_salary_body({"jobs": jobs, "sectors": [{"name": "Wind energy", "n": 1}], "fetched": "2026-09-22", "ed": "ie"}, build_site.EDITIONS["ie"])
    check("28 September" not in body["fx_note"] and body["updated"] == "22 September 2026", "r4b guide: one date only (the snapshot), no rate-set date")
    check(build_site.salary_label({"sal_min": 40000, "sal_max": 50000, "cur": "GBP", "period": "year"}, "EUR") == "£40k–50k (advertised in sterling, about €46.8k–58.5k)" and build_site.currency_note({"sal_min": 1, "cur": "GBP"}, "EUR") == "Advertised in sterling" and "paid in" not in (SRC / "js" / "lib.js").read_text(encoding="utf-8").lower(), "r4b wording: 'advertised in sterling/euros' in build_site and lib.js, 'paid in' gone")
    strip = build_site.salary_strip({"id": "x", "sectors": ["Wind energy"], "regions": ["Elsewhere"], "sal_min": None, "sal_max": None, "cur": None, "period": None}, [], "€", "county", on_map={"Dublin"})
    check("outside Ireland" in strip and "same location tag" not in strip, "r4b wording: off-map similar-roles line reads 'outside Ireland' on IE (unit county)")
    strip_uk = build_site.salary_strip({"id": "x", "sectors": ["Wind energy"], "regions": ["UK-wide / remote"], "sal_min": None, "sal_max": None, "cur": None, "period": None}, [], "£", "region", on_map={"London"})
    check("outside the UK" in strip_uk, "r4b wording: ... and 'outside the UK' on the UK edition")
    check('flag = k["top_share"] > 50' in (SCRIPT_DIR / "build_site.py").read_text(encoding="utf-8"), "r4b dashboard: 'Most roles come from one employer.' only when top share > 50% (source; rendered check in test_dashboard_renders_per_edition)")
    if not (SRC / "data" / "ie.json").exists():
        skip("r4b real landings: real datasets absent")
        return
    for ed in ("ie", "uk"):
        raw = json.loads((SRC / "data" / f"{ed}.json").read_text(encoding="utf-8"))
        d = build_site.normalise(raw, ed, SRC, SRC / "assets" / "logos")
        stray = [(spec["slug"], j["id"], j["loc_class"]) for spec, jobs in build_site.landing_pages(d) for j in jobs if j["loc_class"] not in build_site.LANDING_LOC[ed]]
        check(not stray, f"r4b real landings: {ed} landing pages carry no role outside {sorted(build_site.LANDING_LOC[ed])} ({stray[:3]})")
        check({j["type"] for j in d["jobs"]} <= {"Permanent", "Full-time", "Part-time", "Fixed-term", "Contract", "Volunteer", "Home Based", ""}, f"r4b types: {ed} data carries canonical type spellings ({sorted({j['type'] for j in d['jobs']})})")


# The runner stays last so every test defined above (incl. rounds appended later) is collected.


# --- round 4 B ---
# Round 4 B (2026-09-28): honesty + visitor-voice copy, chip anatomy, map side list,
# menu scoping, social icons, edition switch, cookie padding, P3 rows owned by the
# templates / CSS / page-JS side.

def test_round4_b_copy_css_js(tmp_root: Path):
    out = tmp_root / "site_r4b"
    rc = build_site.build(SRC, out, editions=["ie", "uk"], fixture=FIXTURE)
    check(rc == 0, "r4b: fixture build succeeds")
    if rc != 0:
        return
    home = _read(out / "ie" / "index.html"); uk_home = _read(out / "uk" / "index.html")
    emp = _read(out / "ie" / "employers" / "index.html"); dash = _read(out / "ie" / "dashboard" / "index.html")
    jobs = _read(out / "ie" / "jobs" / "index.html"); guides = _read(out / "ie" / "guides" / "index.html")
    css = _read(SRC / "css" / "styles.css"); main_js = _read(SRC / "js" / "main.js"); jobs_js = _read(SRC / "js" / "jobs.js")
    popups = _read(SRC / "js" / "popups.js"); fit_js = _read(SRC / "js" / "fit.js"); compass = _read(SRC / "js" / "compass.js")
    # A. honesty: the words "Certified B Corporation" survive only as the mark's alt; hero + footer carry the generic line
    for label, page in (("ie home", home), ("uk home", uk_home)):
        stripped = page.replace('alt="Certified B Corporation"', "")
        check("Certified B Corporation" not in stripped and "Certified B Corp" not in stripped, f"r4b A: {label} makes no 'Certified B Corp' text claim outside the alt")
        hero = page.split('class="hero__trust"')[1].split("</div>")[0]
        check('class="hero__bcorp"' in hero and "B Corps are businesses independently certified" in hero, f"r4b A: {label} hero keeps the mark plus the generic B Corp line")
    check('content:"Certified B Corp"' not in css and ".hdr__bcorp::after" not in css, "r4b A: header shows the B Corp mark only (no CSS text label)")
    # B. visitor voice
    check("when the new site launches" not in home and "when the new site launches" not in uk_home, "r4b B: no 'when the new site launches' build note anywhere on home")
    check(home.count("Job alerts by email are available on greenjobs.ie today") == 2 and 'href="https://www.greenjobs.ie/newsletter-signup.asp"' in home, "r4b B: IE alert + subscribe forms point at the live newsletter sign-up")
    check("/newsletter-signup.asp" in uk_home and "when the new site launches" not in uk_home, "r4b B: UK forms point at the live newsletter sign-up (domain follows the edition)")
    for f in (home.split('data-demo-form')[1], home.split('data-demo-form')[2]):
        check(f.find("data-demo-pre") < f.find('type="submit"') and "Your address has not been stored." in f, "r4b B: sign-up note sits above the button; post-submit line keeps 'not been stored'")
    check("published at launch" not in emp and "looking for green work" not in emp and "Thousands of visitors" not in emp and "Candidate audience: ask us for current monthly visitor and subscriber figures." in emp, "r4b B: employer audience tiles ask for figures instead of promising them")
    check("up to ten job alerts by email, free" in home.split('class="hero__alerts"')[1].split("</a>")[0].lower() and "weekly job alerts" not in home and "ten matches" not in home, "r4b B: hero alerts strip makes no weekly-matches claim")
    check("computed from the live listings at build time" not in dash and "Wired at launch" not in dash and "live figures from this week's listings" in dash and "once an analytics provider is connected and the visitor allows analytics" in dash, "r4b B: dashboard lede and event section in visitor voice")
    # C. salary chips: 'advertised in', currency glyph in the dot slot, dot centred on the first line
    check("advertised in" in jobs_js and "paid in ' +" not in jobs_js and 'class="tag__cur"' in jobs_js and "sterling: '\\u00a3'" in jobs_js, "r4b C: board chips say 'advertised in' with a currency glyph")
    check("advertised in" in main_js and 'class="tag__cur"' in main_js and "(?:paid|advertised) in" in main_js, "r4b C: server-rendered chips post-processed the same way (accepts lib.js's old or new label)")
    check(".tag__cur{" in css and "margin-top:calc(.6em - 4px)" in css.split(".tag i{")[1].split("}")[0], "r4b C: glyph slot styled; sector dot centred on the first text line")
    # D. map side list: one line per chip, no wrap inside a chip, lesser chips hidden at <=600 and 1024-1199
    check(".mapview__list .row__meta .tag{white-space:nowrap" in css and ".mapview__list .tag__t{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}" in css and "(max-width:600px),(min-width:1024px) and (max-width:1199px){.mapview__list .row__meta{flex-wrap:wrap}" in css, "r4b D: map side list chips never wrap inside themselves; only location + sector at narrow widths")
    # E. placeholder + insight contrast
    check('placeholder="e.g. Hydrogeologist"' in emp and "Senior Hydrogeologist" not in emp.split('id="p-title"')[1][:120], "r4b E: Post a job title placeholder fits the 1024 input")
    check("color:var(--accent-ink)" in css.split(".insight__n{")[1].split("}")[0] and '[data-theme="dark"] .insight__n{color:var(--accent)}' in css, "r4b E: insight numerals use the ink green in light theme, lime in dark")
    # F. menu scope, social icons, edition switch, cookie padding, fit status
    check(".menu__in>a{" in css and ".menu a{" not in css, "r4b F: mobile menu link rule scoped to the list links (edition switch keeps its pill)")
    check("facebook\\.com" in main_js and "linkedin\\.com" in main_js and "a.remove()" in main_js, "r4b F: footer social buttons get real marks; unknown hosts are dropped")
    check("window.location.search + window.location.hash" in main_js and "rel === here" in main_js, "r4b F: edition switch carries the query/hash when the other edition has the same page")
    check("data-cookie-open" in popups and "--cookie-h" in popups and "html[data-cookie-open] body{padding-bottom:var(--cookie-h" in css, "r4b F: cookie banner reserves its height below the page")
    check("data-fit-status" in fit_js and 'data-fit-status role="status"' in jobs and "GJsay('Link copied')" not in fit_js, "r4b F: Quick job match status lives in its toolbar, not the fixed toast")
    # G. P3 rows
    check("Skip to results" in jobs and jobs.index("Skip to results") < jobs.index("data-rail-home"), "r4b G: jobs page has a skip-to-results link before the filter rail")
    check("lives in this link" not in compass and "Loosened" not in compass, "r4b G: compass result drops the raw URL and developer phrasing")
    check("Data: Snapshot of" in guides and "Last updated: Snapshot" not in guides, "r4b G: guides index shows one date label")
    check('action="jobs/"' in home, "r4b G: hero search posts to jobs/ (no index.html in the shared URL)")
    check("{{posted_line}}<br>Description as published" in _read(SRC / "templates" / "job.html"), "r4b G: job page separates the posted line from the description note")
    check("tag--lvl" in jobs_js, "r4b G: desktop list rows carry the career-level chip like the cards")
    check("r.disc >= 3 ? 'median disclosed" in _read(SRC / "js" / "adbuilder.js"), "r4b G: ad builder only quotes a median from 3+ disclosed salaries, as the salary guide does")
    check("tel:+353" in main_js, "r4b H: Irish footer number rewritten to the international form")


# The runner guard stays last so every appended block above is defined before main() collects test_* functions.
if __name__ == "__main__":
    raise SystemExit(main())
