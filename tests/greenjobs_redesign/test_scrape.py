"""Offline tests for scrape_greenjobs.py against a recorded HTML corpus.

description: Serves the recorded pages under tests/fixtures/greenjobs_scrape/
  (real greenjobs.ie / greenjobs.co.uk HTML captured 2026-09-28) through a
  monkeypatched fetch layer and runs the crawler end to end into a scratch
  directory: job counts and ids, field parsing, sector tags, the 50% snapshot
  floor (exit 3), atomic writes, logo download manifest, the homepage-snapshot
  fallback, garbled-pound repair, and every fetch/parse error branch that can
  be reached without a network. Never touches the network.
inputs: none (reads the fixtures read-only)
outputs: stdout PASS/FAIL lines; exit code 0 (all pass) / 1 (failures)

Run: python3 tests/greenjobs_redesign/test_scrape.py
     (also executed by tests/greenjobs_redesign/test_build.py and run_all.py)
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.error
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO / "execution" / "gtm_client_workflows" / "greenjobs_redesign"
FIX = REPO / "tests" / "fixtures" / "greenjobs_scrape"

sys.path.insert(0, str(SCRIPT_DIR))
import build_site  # noqa: E402
import scrape_greenjobs as sg  # noqa: E402

RESULTS: list[tuple[bool, str]] = []
IE_JOBS = ("11502675", "11502679", "11502682")
UK_JOBS = ("11502470", "11502481")


def check(ok: bool, label: str) -> None:
    RESULTS.append((ok, label))
    print(("PASS  " if ok else "FAIL  ") + label)


def _read(host: str, name: str) -> str:
    return (FIX / host / name).read_text(encoding="utf-8", errors="ignore")


# Synthetic pages for branches the recorded corpus cannot reach: a job with a
# garbled pound salary, an info page wrapped in <div id="main">, one with no
# wrapper at all, and a listing page 2 with a job whose detail page is missing.
SYNTH_JOB = """<html><head><title>x</title></head><body>
<div id="JBcontent" class="jobView"><h1>Waste &amp; Recycling Supervisor</h1>
<div class="jobLogo"><a href="/x"><img src="/jobboard/public/5104/clientlogos/Logo_1.png" alt="Synthetic Waste Ltd"></a></div>
<dl><dt>Recruiter:</dt><dd>Synthetic Waste Ltd</dd>
<dt>Salary:</dt><dd>Â£30,000 - Â£35,000 per annum</dd>
<dt>Vicinity:</dt><dd><em>Leeds</em>, <em>Bradford</em></dd>
<dt>Region:</dt><dd><em>Yorkshire and the Humber</em></dd>
<dt>Job Type:</dt><dd><em>Permanent</em>, <em>Full Time</em></dd>
<dt>Sector:</dt><dd><em>Waste Jobs</em><em>Recycling Jobs</em></dd>
<dt>Job Category:</dt><dd><em>Operations</em></dd>
<dt>Education Level:</dt><dd><em>Degree</em></dd>
<dt>Posted:</dt><dd>01/09/2026</dd><dt>Closing Date:</dt><dd>30/09/2026</dd>
<dt>Start Date:</dt><dd>ASAP</dd><dt>Job Ref:</dt><dd>SYN-1</dd></dl>
<div class="jobDescription"><p style="x">Pays Â£30k.<script>bad()</script><span>ok</span></p><p></p></div>
<!-- job documents --></div><div id="right"></div></body></html>"""
SYNTH_MAIN_PAGE = '<html><head><title> Main wrapped </title></head><body><div id="main"><p>For employers</p><a href="https://x.example/a">a</a><img src="/i.png"></div><div id="footer"></div></body></html>'
SYNTH_PLAIN_PAGE = "<html><body><p>No wrapper at all</p></body></html>"
SYNTH_RESULTS_PG2 = ('<div id="numResultsTop"><strong>108</strong></div>'
                     '<div id="jobResult99999999" class="jobInfo"><a href="/jobs/99999999/ghost-role.asp">Ghost</a><p class="jobDescription">'
                     '<div id="jobResult99999998" class="jobInfo featuredJob"><p class="jobDescription">')


class FakeFetch:
    """Serves the fixture corpus by URL; records every request. Unknown URLs
    return None (the crawler's 'fetch failed' path)."""

    def __init__(self, hosts: dict[str, str], extra: dict[str, str | bytes | None] | None = None, page2: bool = False) -> None:
        self.calls: list[str] = []
        self.pages: dict[str, str | bytes | None] = {}
        for host, key in hosts.items():
            base = f"https://{host}"
            self.pages[base + "/"] = _read(host, "home.html")
            self.pages[base + "/jobboard/cands/jobresults.asp?pg=1"] = _read(host, "jobresults_pg1.html")
            if page2:
                self.pages[base + "/jobboard/cands/jobresults.asp?pg=2"] = SYNTH_RESULTS_PG2
            for p in (FIX / host).glob("job_*.html"):
                jid = p.stem[4:]
                listing = _read(host, "jobresults_pg1.html")
                m = re.search(r'href="(/jobs/%s/[^"]+)"' % jid, listing)
                self.pages[base + m.group(1)] = p.read_text(encoding="utf-8", errors="ignore")
            for p in (FIX / host).glob("*.cms.asp.html"):
                self.pages[base + "/" + p.name[:-5]] = p.read_text(encoding="utf-8", errors="ignore")
        self.pages.update(extra or {})

    def __call__(self, url: str, sleep_s: float = 0.3, binary: bool = False, retries: int = 2):
        self.calls.append(url)
        v = self.pages.get(url)
        if binary:
            return v if isinstance(v, bytes) else None
        return v if isinstance(v, str) else None


def _with_fetch(fake: FakeFetch):
    original = sg.fetch
    sg.fetch = fake  # type: ignore[assignment]
    return original


# ------------------------------------------------------------- unit tier

def test_parse_salary():
    ps = sg.parse_salary
    check(ps("€55,000 - €65,000 per annum") == (55000, 65000, "EUR", "year"), "parse_salary: euro range per annum")
    check(ps("£30k–£35k") == (30000, 35000, "GBP", "year"), "parse_salary: k amounts, en dash, no period -> year by magnitude")
    check(ps("$45 per hour") == (45, None, "USD", "hour"), "parse_salary: hourly with explicit period")
    check(ps("£350 pd") == (350, None, "GBP", "day"), "parse_salary: per day")
    check(ps("£600 per week") == (600, None, "GBP", "week"), "parse_salary: per week")
    check(ps("€4,500 pm") == (4500, None, "EUR", "month"), "parse_salary: per month")
    check(ps("£45") == (None, None, None, None), "parse_salary: a bare figure under 100 without a period is not a salary")
    check(ps("€250") == (250, None, "EUR", "day") and ps("€5000") == (5000, None, "EUR", "month") and ps("€50000") == (50000, None, "EUR", "year") and ps("€50 ph") == (50, None, "EUR", "hour"), "parse_salary: period inferred from magnitude when absent")
    check(ps("40000€ - 50000€ pa") == (40000, 50000, "EUR", "year"), "parse_salary: trailing-currency form")
    check(ps("Competitive Salary + Excellent Range of Benefits") == (None, None, None, None), "parse_salary: no figure -> all None")
    check(ps(None) == (None, None, None, None) and ps("") == (None, None, None, None), "parse_salary: None / empty -> all None")
    check(ps("£1.2.3 pa") == (None, None, None, None), "parse_salary: unparseable number -> all None")
    check(ps("Â£30,000 to Â£35,000 per annum") == (30000, 35000, "GBP", "year") and ps("\ufffd30k - \ufffd35k") == (30000, 35000, "GBP", "year"), "parse_salary: mojibake 'Â£' / U+FFFD pounds are normalised so the upper bound survives")
    check(ps("\ufffdCompetitive") == (None, None, None, None), "parse_salary: a replacement character not followed by a figure is left alone")


def test_text_helpers():
    check(sg.strip_tags("<p>Hi&nbsp;<b>there</b></p><script>x()</script><br>y") == "Hi there\ny", "strip_tags: drops script, unescapes, newlines at block ends")
    long = "<p>" + "word " * 2000 + "</p>"
    out = sg.clean_html(long, limit=500)
    check(out.endswith("<p>[truncated]</p>") and len(out) < 560, "clean_html: truncates at the last closing tag and marks it")
    check(sg.clean_html('<P STYLE="x">a<span>b</span><img src="q"></P><p></p><!-- c -->') == "<p>ab</P>", "clean_html: lower-cases opening tags, strips attributes, spans, images, comments and empty paragraphs (closing tags keep their case: a known quirk)")
    check(sg.clean_html("x" * 20, limit=10) == "xxxxxxxxxx <p>[truncated]</p>", "clean_html: truncation without any closing tag keeps the cut")
    check(sg.first(r"<title>(.*?)</title>", "<title>T</title>") == "T" and sg.first(r"abc", "xabcx") == "abc" and sg.first(r"zzz", "abc") is None, "first: group 1, whole match, None")
    check(sg.slugify("https://x/jobs/1/a-b.asp") == "a-b.asp" and sg.slugify("https://x/a/") == "a", "slugify: last path segment")
    check(sg.dl_items("<em>A &amp; B</em>, <em>C</em>") == ["A & B", "C"], "dl_items: unescaped em items")


def test_parse_results_and_facets():
    base = "https://www.greenjobs.ie"
    jobs, total = sg.parse_results(_read("www.greenjobs.ie", "jobresults_pg1.html"), base)
    check(len(jobs) == 10 and total == 108, f"parse_results: IE page 1 has 10 jobs of 108 ({len(jobs)}, {total})")
    check(jobs[0]["id"] == "11502737" and jobs[0]["url"] == base + "/jobs/11502737/principal-civil-engineer-water.asp" and jobs[0]["featured"] and jobs[0]["employer"] == "Mott MacDonald" and jobs[0]["logo_url"].startswith(base + "/jobboard/public/"), "parse_results: id, url, featured, employer, logo of the first IE result")
    uk_jobs, uk_total = sg.parse_results(_read("www.greenjobs.co.uk", "jobresults_pg1.html"), "https://www.greenjobs.co.uk")
    check(len(uk_jobs) == 15 and uk_total == 123, "parse_results: UK page 1 has 15 jobs of 123")
    check(sg.parse_results("<html><body>nothing here</body></html>", base) == ([], 0), "parse_results: malformed page -> no jobs, total 0")
    pg2, _ = sg.parse_results(SYNTH_RESULTS_PG2, base)
    check(pg2[0]["url"] == base + "/jobs/99999999/ghost-role.asp" and pg2[1]["url"] is None and pg2[1]["featured"] and pg2[1]["logo_url"] is None, "parse_results: a result without a link or logo yields None fields")
    fac = sg.parse_facets(_read("www.greenjobs.ie", "home.html"), base)
    check(set(fac) == {"sector", "job category", "job type", "location"} and len(fac["sector"]) > 100 and fac["sector"][0] == {"name": "Acoustics Jobs", "slug": "acoustics-jobs", "url": base + "/browse-jobs/acoustics-jobs/", "count": 0}, "parse_facets: IE sector / category / type boxes plus the location tab")
    uk_fac = sg.parse_facets(_read("www.greenjobs.co.uk", "home.html"), "https://www.greenjobs.co.uk")
    check("industry sector" in uk_fac and "region" in uk_fac and len(uk_fac["region"]) == 14 and all(r["count"] is not None for r in uk_fac["region"]), "parse_facets: UK uses 'Industry Sector' and a 14-region box with counts")
    check(len({i["name"] for i in fac["location"]}) == len(fac["location"]), "parse_facets: location tab names are deduplicated")
    check(sg.parse_facets("<html></html>", base) == {}, "parse_facets: malformed homepage -> {}")
    emps = sg.parse_featured_employers(_read("www.greenjobs.ie", "home.html"), base)
    check(len(emps) == 5 and emps[0]["name"] == "Veolia" and emps[0]["url"] == base + "/browse-jobs/veolia", "parse_featured_employers: five IE featured employers, Veolia first, browse-jobs target")
    check(sg.parse_featured_employers('<a href="/x"><img src="/clientlogos/a.png" alt="A"></a><a href="/y"><img src="/other.png" alt="B"></a>', base) == [], "parse_featured_employers: non-browse targets and non-logo images are skipped")


def test_parse_job_fields():
    base = "https://www.greenjobs.ie"
    listing, _ = sg.parse_results(_read("www.greenjobs.ie", "jobresults_pg1.html"), base)
    meta = next(j for j in listing if j["id"] == "11502675")
    j = sg.parse_job(_read("www.greenjobs.ie", "job_11502675.html"), base, meta, "Ireland", "EUR")
    check(j["title"] == "Principal Environmental Consultant" and j["employer"] == "Mott MacDonald" and j["slug"] == "principal-environmental-consultant", "parse_job: title, employer (Recruiter field) and slug")
    check(j["location"] == "Galway, Dublin, Cork" and j["region"] == "Ireland" and j["country"] == "Ireland", "parse_job: vicinity joined into location; region; country")
    check(j["salary_text"] == "Competitive Salary + Excellent Range of Benefits" and j["salary_min"] is None and j["currency"] is None and j["period"] is None, "parse_job: 'Competitive' salary keeps the text and no figures")
    check(j["posted"] == "24/09/2026" and j["closing"] == "31/10/2026" and j["start_date"] == "ASAP" and j["job_ref"] == "GreenJobs - 16372", "parse_job: posted / closing / start / ref")
    check("Water Jobs" in j["sectors"] and len(j["sectors"]) == 10 and "Planning" in j["categories"] and j["education"] == "See job description" and j["type"] == "Permanent", "parse_job: sector tags, categories, education, type")
    check(j["featured"] is True and j["logo_url"] == base + "/jobboard/public/5104/clientlogos/Logo_81162.jpg" and j["description_html"].startswith("<") and "<script" not in j["description_html"] and len(j["summary"]) <= 400 and j["summary"], "parse_job: featured flag, logo, cleaned description, 400-char summary")
    uk = sg.parse_job(_read("www.greenjobs.co.uk", "job_11502481.html"), "https://www.greenjobs.co.uk", {"id": "11502481", "url": "https://www.greenjobs.co.uk/jobs/11502481/x.asp"}, "United Kingdom", "GBP")
    check(uk["title"].startswith("Principal Ecologist") and uk["employer"] == "Jacobs" and uk["location"] == "Peterborough" and uk["region"] == "East of England" and uk["sectors"] == [] and uk["featured"] is False, "parse_job: UK page: no sector tags, region facet, featured defaults False")
    syn = sg.parse_job(SYNTH_JOB, base, {"id": "s1", "url": base + "/jobs/s1/waste.asp", "employer": "meta"}, "United Kingdom", "GBP")
    check(syn["salary_min"] == 30000 and syn["salary_max"] == 35000 and syn["currency"] == "GBP" and syn["period"] == "year", "parse_job: garbled 'Â£' salary still yields 30000-35000 GBP")
    check(build_site.repair_pounds(syn["salary_text"]) == "£30,000 - £35,000 per annum" and build_site.repair_pounds(syn["description_html"]) == "<p>Pays £30k.ok</p>", "parse_job + repair_pounds: the mojibake pound is repaired downstream in the build")
    check(syn["location"] == "Leeds, Bradford" and syn["type"] == "Permanent, Full Time" and syn["sectors"] == ["Waste Jobs", "Recycling Jobs"] and syn["education"] == "Degree" and syn["title"] == "Waste & Recycling Supervisor", "parse_job: multi-item vicinity/type/sector lists and unescaped title")
    bare = sg.parse_job("<html><body>garbage</body></html>", base, {"id": "z", "url": base + "/jobs/z/z.asp", "employer": "From Listing", "logo_url": "L"}, "Ireland", "EUR")
    check(bare["title"] is None and bare["employer"] == "From Listing" and bare["logo_url"] == "L" and bare["location"] == "" and bare["sectors"] == [] and bare["summary"] == "" and bare["salary_text"] is None, "parse_job: malformed page falls back to listing metadata and empty fields")
    nologo = sg.parse_job('<div id="JBcontent" class="jobView"><h1>T</h1><div class="jobLogo"><img src="/l.png" alt="Logo Co"></div><div id="right">', base, {"id": "n", "url": base + "/jobs/n/n.asp"}, "Ireland", "EUR")
    check(nologo["employer"] == "Logo Co" and nologo["logo_url"] == base + "/l.png", "parse_job: employer falls back to the logo alt when there is no Recruiter field")


def test_measure_page():
    p = sg.measure_page(_read("www.greenjobs.ie", "home.html"), "https://www.greenjobs.ie")
    check(p["html_bytes"] > 150000 and p["script_tags_external"] == 16 and p["jquery"] == "1.11.0" and p["bootstrap"] and p["platform_cdn"] and p["ga4"] == ["G-ZQPJGM484J"] and p["has_viewport_meta"] and p["total_requests_estimate"] > 20, "measure_page: IE homepage weight and stack from the recorded page")
    q = sg.measure_page('<html><link href="/a.css"><script>x</script></html>', "https://x")
    check(q["stylesheets"] == ["/a.css"] and q["inline_script_blocks"] == 1 and q["jquery"] is None and q["ga4"] == [] and not q["bootstrap"], "measure_page: stylesheet fallback regex, inline script count, empty stack")


def test_fetch_error_branches():
    slept: list[float] = []
    orig_sleep, orig_open = sg.time.sleep, sg.urllib.request.urlopen
    sg.time.sleep = lambda s: slept.append(s)
    try:
        def boom(req, timeout=30):
            raise urllib.error.URLError("no route")
        sg.urllib.request.urlopen = boom
        check(sg.fetch("https://example.invalid/", 0, retries=1) is None and len([s for s in slept if s >= 1.5]) == 2, "fetch: URLError on every attempt -> None after retries with back-off")
        slept.clear()

        def http_err(req, timeout=30):
            raise urllib.error.HTTPError("https://example.invalid/", 500, "boom", {}, io.BytesIO(b""))
        sg.urllib.request.urlopen = http_err
        check(sg.fetch("https://example.invalid/", 0, retries=0) is None, "fetch: HTTPError -> None")

        class Resp:
            def __init__(self, data: bytes) -> None:
                self.data = data

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return self.data
        seen = {}

        def ok(req, timeout=30):
            seen["ua"] = req.get_header("User-agent")
            return Resp("café £30k".encode("utf-8"))
        sg.urllib.request.urlopen = ok
        check(sg.fetch("https://example.invalid/", 0) == "café £30k" and seen["ua"] == sg.UA, "fetch: decodes UTF-8 text and sends the browser User-Agent")
        check(sg.fetch("https://example.invalid/", 0, binary=True) == "café £30k".encode("utf-8"), "fetch: binary=True returns raw bytes")
        sg._last[0] = sg.time.monotonic() + 5  # force a positive wait inside _throttle
        slept.clear()
        sg._throttle(0.5)
        check(slept and 0 < slept[0] <= 5.5, "throttle: waits for the remaining interval before the next request")
    finally:
        sg.time.sleep, sg.urllib.request.urlopen = orig_sleep, orig_open
        sg._last[0] = 0.0


def test_snapshot_floor_and_atomic_write(tmp_root: Path):
    p = tmp_root / "floor.json"
    check(sg.snapshot_floor(str(p)) == 0, "snapshot_floor: missing file -> 0")
    p.write_text("{not json", encoding="utf-8")
    check(sg.snapshot_floor(str(p)) == 0, "snapshot_floor: unreadable JSON -> 0")
    p.write_text("[1,2,3]", encoding="utf-8")
    check(sg.snapshot_floor(str(p)) == 0, "snapshot_floor: a non-dict snapshot -> 0")
    p.write_text(json.dumps({"jobs": [{}] * 7}), encoding="utf-8")
    check(sg.snapshot_floor(str(p)) == 4 and sg.snapshot_floor(str(p), 0.1) == 1, "snapshot_floor: ceil(7 * 0.5) = 4; ratio is a parameter")
    target = tmp_root / "atomic.json"
    sg.write_json_atomic(str(target), {"v": 1})
    orig_replace = sg.os.replace
    sg.os.replace = lambda a, b: (_ for _ in ()).throw(OSError("disk full"))
    try:
        sg.write_json_atomic(str(target), {"v": 2})
        check(False, "write_json_atomic: rename failure propagates")
    except OSError:
        check(True, "write_json_atomic: rename failure propagates")
    finally:
        sg.os.replace = orig_replace
    tmps = list(tmp_root.glob("atomic.json.tmp*"))
    check(json.loads(target.read_text(encoding="utf-8")) == {"v": 1} and len(tmps) == 1 and json.loads(tmps[0].read_text(encoding="utf-8")) == {"v": 2}, "write_json_atomic: the old snapshot is intact after a failed rename; the temp file holds the new payload")
    for t in tmps:
        t.unlink()


# ------------------------------------------------------------- integration tier (crawl end to end, offline)

def test_crawl_ie(tmp_root: Path):
    out = tmp_root / "crawl_ie"
    extra = {"https://www.greenjobs.ie/for-employers.asp": SYNTH_MAIN_PAGE, "https://www.greenjobs.ie/company-az/": SYNTH_PLAIN_PAGE}
    fake = FakeFetch({"www.greenjobs.ie": "ie"}, extra)
    orig = _with_fetch(fake)
    try:
        out.mkdir()
        d = sg.crawl_site("ie", 400, 2, 0, str(out), None)
    finally:
        sg.fetch = orig
    jobs = d["jobs"]
    check(len(jobs) == 3 and {j["id"] for j in jobs} == set(IE_JOBS), f"crawl ie: 3 of the 10 listed jobs have a recorded detail page; the 7 missing pages are dropped ({[j['id'] for j in jobs]})")
    check(d["stats"] == {"total_jobs": 108, "jobs_scraped": 3, "jobs_with_salary": 0, "jobs_with_salary_text": 3, "featured_jobs": 3}, f"crawl ie: stats ({d['stats']})")
    check(fake.calls.count("https://www.greenjobs.ie/jobboard/cands/jobresults.asp?pg=1") == 1 and "https://www.greenjobs.ie/jobboard/cands/jobresults.asp?pg=2" in fake.calls and "https://www.greenjobs.ie/jobboard/cands/jobresults.asp?pg=3" not in fake.calls, "crawl ie: pages until a results page fails to fetch (page 2 missing -> stop)")
    by = {j["id"]: j for j in jobs}
    check(by["11502682"]["title"] == "Senior Engineer - Utilities" and by["11502682"]["employer"] == "WSP" and by["11502682"]["location"] == "Dublin, Kildare, Limerick" and by["11502682"]["closing"] == "31/10/2026" and by["11502682"]["country"] == "Ireland", "crawl ie: job fields survive the crawl")
    check(d["site"] == "greenjobs.ie" and d["base_url"] == "https://www.greenjobs.ie" and d["fetched"] == sg.FETCHED and len(d["sectors"]) > 100 and d["categories"] and d["job_types"] and d["locations"], "crawl ie: facets carried into the dataset")
    check([r["name"] for r in d["regions"]][:1] == ["Dublin"] and all(set(r) == {"name", "slug", "url", "count"} for r in d["regions"]) and next(r for r in d["regions"] if r["name"] == "Dublin")["count"] == 3, "crawl ie: no region facet on IE -> regions derived from job vicinities, Dublin first with 3")
    names = {e["name"] for e in d["employers"]}
    check({"Veolia", "Mott MacDonald", "WSP"} <= names and next(e for e in d["employers"] if e["name"] == "WSP")["url"] == "https://www.greenjobs.ie/browse-jobs/wsp/", "crawl ie: featured employers merged with job employers")
    check(d["about"].startswith("GreenJobs is a job board") and "About GreenJobs" not in d["about"][:20], "crawl ie: about text split after the heading")
    c = d["contact"]
    check(c["company"] and c["address"] == "Ennis Digital Hub, Quin Road Business Park, Quin Road, Ennis, Co. Clare, V95 VW74, Ireland" and c["phones"] == [("Calling From Ireland", "(01) 912 5247"), ("Calling From Outside Ireland", "+44 28 4303 2055")] and "info@greenjobs.ie" in c["emails"] and c["opening_hours"].startswith("Our Opening Hours"), f"crawl ie: contact block parsed from the contact page ({c})")
    check(len(d["network_sites"]) >= 5 and {"greenjobs.ie", "greenjobs.co.uk"} <= {n["name"] for n in d["network_sites"]}, "crawl ie: network sites from the network page")
    pages = json.loads((out / "pages_ie.json").read_text(encoding="utf-8"))
    check(pages["/for-employers.asp"]["text"] == "For employers\na" and pages["/for-employers.asp"]["title"] == "Main wrapped" and pages["/for-employers.asp"]["links"] == ["https://x.example/a"] and pages["/for-employers.asp"]["images"] == ["/i.png"], "crawl ie: an info page wrapped in <div id=main> is extracted through the fallback regex")
    check(pages["/company-az/"]["text"] == "No wrapper at all" and pages["/company-az/"]["title"] == "" and "/newsletter-signup.asp" not in pages, "crawl ie: an unwrapped page keeps its whole text; unfetchable pages are skipped")
    written = json.loads((out / "ie.json").read_text(encoding="utf-8"))
    perf = json.loads((out / "perf_ie.json").read_text(encoding="utf-8"))
    check(written["stats"] == d["stats"] and perf["jquery"] == "1.11.0" and not list(out.glob("*.tmp*")), "crawl ie: ie.json, pages_ie.json and perf_ie.json written atomically (no temp files left)")
    raw_norm = build_site.normalise(written, "ie", REPO / "deliverables" / "greenjobs_redesign_2026-09-22" / "src", tmp_root / "nologos")
    check(len(raw_norm["jobs"]) == 3 and all(j["sectors"] for j in raw_norm["jobs"]) and all(j["closing"] == "2026-10-31" for j in raw_norm["jobs"]), "crawl ie -> build_site.normalise: the crawl output is a valid dataset for the build")


def test_crawl_uk_with_logos_and_paging(tmp_root: Path):
    out = tmp_root / "crawl_uk"
    assets = tmp_root / "logos"
    logo_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    extra: dict[str, str | bytes | None] = {"https://www.greenjobs.co.uk/jobboard/public/5105/clientlogos/Logo_83486.jpg": logo_png}
    fake = FakeFetch({"www.greenjobs.co.uk": "uk"}, extra, page2=True)
    home = fake.pages["https://www.greenjobs.co.uk/"]
    site_logos = [s for s in re.findall(r'<img[^>]*src="([^"]+)"', home) if re.search(r"logo|bcorp|b-corp|corp", s, re.I) and "clientlogos" not in s and "banners" not in s]
    for s in site_logos[:1]:
        fake.pages[s if s.startswith("http") else ("https:" + s if s.startswith("//") else "https://www.greenjobs.co.uk" + s)] = logo_png
    assets.mkdir()
    (assets / "logos.json").write_text(json.dumps({"Preexisting": {"file": "keep.png", "source": "x", "bytes": 1, "site": "uk"}}), encoding="utf-8")
    orig = _with_fetch(fake)
    try:
        out.mkdir()
        d = sg.crawl_site("uk", 14, 4, 0, str(out), str(assets))  # 11502481 is the 14th listed job, 11502470 the 15th
    finally:
        sg.fetch = orig
    check(len(d["jobs"]) == 1 and d["jobs"][0]["id"] == "11502481" and d["jobs"][0]["employer"] == "Jacobs" and d["jobs"][0]["country"] == "United Kingdom" and d["stats"]["total_jobs"] == 123, f"crawl uk: --max-jobs 14 caps the detail fetches at the first 14 listed jobs, of which one has a recorded page ({[j['id'] for j in d['jobs']]})")
    check(fake.calls.count("https://www.greenjobs.co.uk/jobboard/cands/jobresults.asp?pg=1") == 1 and "https://www.greenjobs.co.uk/jobboard/cands/jobresults.asp?pg=2" not in fake.calls, "crawl uk: paging stops once the cap is reached")
    check([r["name"] for r in d["regions"]] and len(d["regions"]) == 14 and d["sectors"] and d["sectors"][0]["name"] == "Conservation Jobs", "crawl uk: regions from the homepage facet; sectors from 'Industry Sector'")
    check(d["contact"]["company"] is None and d["contact"]["address"] is None and d["contact"]["opening_hours"] is None, "crawl uk: no contact page fetched -> empty contact fields")
    check(d["network_sites"] and all(re.search(r"jobs(uk)?\.(com|ie|co\.uk)/$", n["url"]) for n in d["network_sites"]), "crawl uk: network sites fall back to the homepage links when the network page is missing")
    manifest = json.loads((assets / "logos.json").read_text(encoding="utf-8"))
    check("Preexisting" in manifest and manifest.get("Jacobs", {}).get("file") == "Logo_83486.jpg" and (assets / "Logo_83486.jpg").read_bytes() == logo_png, "download_logos: existing manifest kept, the fetched employer logo saved and recorded")
    check(sum(1 for k in manifest if k.startswith("site:uk:")) >= 1, "download_logos: site logo / svg targets recorded when fetchable")
    n_binary_calls = sum(1 for u in fake.calls if "clientlogos" in u or u.endswith(".svg"))
    check(n_binary_calls >= 1 and not any(f.name.endswith(".tmp") for f in assets.iterdir()), "download_logos: unfetchable logos are skipped without leaving files")
    # a second run skips what the manifest already has
    fake.calls.clear()
    orig = _with_fetch(fake)
    try:
        sg.download_logos("uk", home, [{"name": "Jacobs", "logo_url": "https://www.greenjobs.co.uk/jobboard/public/5105/clientlogos/Logo_83486.jpg"}, {"name": "NoFile", "logo_url": "https://www.greenjobs.co.uk/"}, {"name": "NoLogo"}], "https://www.greenjobs.co.uk", str(assets), 0)
    finally:
        sg.fetch = orig
    check("https://www.greenjobs.co.uk/jobboard/public/5105/clientlogos/Logo_83486.jpg" not in fake.calls and "https://www.greenjobs.co.uk/" not in fake.calls, "download_logos: an already-downloaded logo and a URL without a file name are not fetched again")


def test_crawl_paging_and_missing_page(tmp_root: Path):
    out = tmp_root / "crawl_pg"
    fake = FakeFetch({"www.greenjobs.ie": "ie"}, {"https://www.greenjobs.ie/jobboard/cands/jobresults.asp?pg=3": '<div id="numResultsTop"><strong>108</strong></div><p>No more results</p>'}, page2=True)
    orig = _with_fetch(fake)
    try:
        out.mkdir()
        d = sg.crawl_site("ie", 400, 2, 0, str(out), None)
    finally:
        sg.fetch = orig
    check("https://www.greenjobs.ie/jobboard/cands/jobresults.asp?pg=3" in fake.calls and "https://www.greenjobs.ie/jobboard/cands/jobresults.asp?pg=4" not in fake.calls and len(d["jobs"]) == 3 and "99999999" not in {j["id"] for j in d["jobs"]}, "crawl: a listed job whose detail page 404s (fetch None) is dropped; the result without a URL is ignored; paging continues past page 2 and stops at an empty results page")


def test_snapshot_floor_rejects_and_main_exit_code(tmp_root: Path):
    out = tmp_root / "floor_out"
    out.mkdir()
    old = {"site": "greenjobs.ie", "jobs": [{"id": str(i)} for i in range(100)]}
    sg.write_json_atomic(str(out / "ie.json"), old)
    fake = FakeFetch({"www.greenjobs.ie": "ie"})
    orig = _with_fetch(fake)
    try:
        rc = sg.main(["--site", "ie", "--out", str(out), "--sleep", "0"])
    finally:
        sg.fetch = orig
    check(rc == 3 and json.loads((out / "ie.json").read_text(encoding="utf-8")) == old and not (out / "pages_ie.json").exists() and not (out / "perf_ie.json").exists(), "floor: 3 jobs < 50 (half of the 100-job snapshot) -> main() exits 3 and nothing is written for the site")
    fake2 = FakeFetch({"www.greenjobs.ie": "ie", "www.greenjobs.co.uk": "uk"})
    orig = _with_fetch(fake2)
    try:
        rc = sg.main(["--out", str(tmp_root / "both_out"), "--concurrency", "9"])
    finally:
        sg.fetch = orig
    check(rc == 0 and (tmp_root / "both_out" / "ie.json").exists() and (tmp_root / "both_out" / "uk.json").exists(), "main: --site both with no prior snapshot writes both datasets and exits 0")


def test_homepage_snapshot_fallback(tmp_root: Path):
    fake = FakeFetch({"www.greenjobs.ie": "ie"})
    del fake.pages["https://www.greenjobs.ie/"]
    snap = tmp_root / "home_snapshot.html"
    snap.write_text(_read("www.greenjobs.ie", "home.html"), encoding="utf-8")
    orig_snap = sg.SITES["ie"]["snapshot"]
    sg.SITES["ie"]["snapshot"] = str(snap)
    orig = _with_fetch(fake)
    out = tmp_root / "snap_out"
    out.mkdir()
    try:
        d = sg.crawl_site("ie", 400, 1, 0, str(out), None)
        check(len(d["jobs"]) == 3 and len(d["sectors"]) > 100, "crawl: an unreachable homepage falls back to the saved snapshot")
        sg.SITES["ie"]["snapshot"] = str(tmp_root / "nope.html")
        try:
            sg.crawl_site("ie", 400, 1, 0, str(out), None)
            check(False, "crawl: no homepage and no snapshot -> SystemExit")
        except SystemExit as exc:
            check("cannot fetch homepage for ie" in str(exc), "crawl: no homepage and no snapshot -> SystemExit")
    finally:
        sg.fetch = orig
        sg.SITES["ie"]["snapshot"] = orig_snap


def test_fixture_provenance():
    sizes = {p.relative_to(FIX).as_posix(): p.stat().st_size for p in FIX.rglob("*.html")}
    check(len(sizes) == 12 and all(v > 20000 for v in sizes.values()), f"fixtures: 12 recorded pages, each a real page (>20 KB): {sizes}")
    check(all("sjbimg.com" in _read(*k.split("/", 1)) for k in sizes if "home" in k), "fixtures: the homepages carry the platform CDN, so they are real captures")


def run_all(tmp_root: Path) -> list[tuple[bool, str]]:
    """Run every test here into `tmp_root`; return the (ok, label) list. Used by test_build.py."""
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
    tmp_root = Path(tempfile.mkdtemp(prefix="greenjobs_test_scrape_", dir=str(base)))
    try:
        results = run_all(tmp_root)
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
    failed = [label for ok, label in results if not ok]
    print(f"\nScraper: {len(results) - len(failed)} passed, {len(failed)} failed")
    for label in failed:
        print(f"  FAIL: {label}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
