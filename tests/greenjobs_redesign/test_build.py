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
    check(build_site.assign_sectors(j3)[0] == "Ecology & conservation", "assign_sectors: null fields are tolerated")


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
    check((out / "index.html").exists() and (out / "ie" / "jobs" / "1001" / "index.html").exists() and (out / "uk" / "jobs" / "1001" / "index.html").exists(), "integration: chooser + job pages written for both editions")
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
        check(pages == len(raw["jobs"]), f"integration: {ed} job page count {pages} == dataset {len(raw['jobs'])}")


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
    check('data-lvl="' in clean and 'data-n="' in clean, "home: map regions carry data-n/data-lvl at build time")
    check(any("Employers hiring now" in f for f in with_patch(lambda t: t.replace('data-strip="network"', 'data-strip="hiring"').replace('<div class="marq__track">', '<div class="marq__track"><div class="emp"><span>Ghost Ltd</span></div>'))), "faults: non-live employer under 'hiring now' caught")
    check(validate_site.validate(out, jobs) == [], "faults: clean build validates with zero problems after patches are reverted")
    keith = out / "ie" / "for-keith" / "index.html"
    k = keith.read_text(encoding="utf-8")
    keith.write_text(k.replace("</main>", "<p>AI Claude</p></main>"), encoding="utf-8")
    check(not any("forbidden" in f for f in validate_site.validate(out, jobs)), "faults: for-keith/ is exempt from the word filter")
    keith.write_text(k, encoding="utf-8")


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
