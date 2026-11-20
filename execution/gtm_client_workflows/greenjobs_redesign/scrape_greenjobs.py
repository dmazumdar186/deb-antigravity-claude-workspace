#!/usr/bin/env python3
"""Scrape greenjobs.ie / greenjobs.co.uk into structured JSON for the redesign demo.

description: Polite crawler for the two GreenJobs boards (sjbimg.com job-board
    platform). Collects the facet lists (sectors, categories, regions, job types
    with counts) from the homepage, pages through /jobboard/cands/jobresults.asp,
    fetches every job detail page, parses salary/location/dates/description, and
    captures About / Contact / network / advertising page text. Optionally
    downloads brand and employer logos into an assets folder with a manifest,
    plus the client-logo wall from /for-employers.asp (the organisations the
    board publishes as its clients) into {assets}/clients/.
inputs: --snapshot [--snapshot-out DIR] [--dry-run] [--snapshot-from-data DIR] (public live-board
    snapshot: <=1 req/s, honest UA, robots honoured, JSON only; see run_snapshot); --site ie|uk|both (default both); --max-jobs N (cap per site, default 400);
    --out DIR (data output dir); --assets DIR (logo folder; omit to skip logos);
    --concurrency N (default 4); --sleep S (default 0.3); --clients-only (refresh
    only the client-logo wall, leaving the job snapshot untouched). No secrets.
outputs: {out}/ie.json, {out}/uk.json (see JOB_FIELDS below), {out}/pages_{site}.json
    (plain text of informational pages for brief writing), {assets}/logos.json
    manifest plus downloaded logo files, {out}/perf_{site}.json (page-weight
    measurements of the homepage: bytes, request counts), {out}/clients_{site}.json
    = [{name, file, source}] with the files under {assets}/clients/ (needs --assets).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import html
import json
import math
import logging
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

LOG = logging.getLogger("scrape_greenjobs")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "Chrome/128 Safari/537.36")
SITES = {
    "ie": {"base": "https://www.greenjobs.ie", "site": "greenjobs.ie",
           "currency": "EUR", "snapshot": "/tmp/gj_httpswwwgreenjobsie.html"},
    "uk": {"base": "https://www.greenjobs.co.uk", "site": "greenjobs.co.uk",
           "currency": "GBP", "snapshot": "/tmp/gj_httpswwwgreenjobscouk.html"},
}
INFO_PAGES = [
    "/about-us.cms.asp", "/contact-us.cms.asp",
    "/the-greenjobs-network-of-websites.cms.asp",
    "/recruiter-zone-advertising.cms.asp", "/for-employers.asp",
    "/join-our-social-media-network.cms.asp", "/newsletter-signup.asp",
    "/one-percent-for-the-planet-member.cms.asp", "/partners-and-links.cms.asp",
    "/client-testimonials.cms.asp", "/talent-finder-network.cms.asp",
    "/job-distribution-partners.cms.asp", "/green-job-sectors.cms.asp",
    "/cv-writing-service.cms.asp", "/company-az/",
]
FETCHED = "2026-09-22"
_lock = threading.Lock()
_last = [0.0]


def _throttle(sleep_s: float) -> None:
    with _lock:
        wait = _last[0] + sleep_s - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.monotonic()


def fetch(url: str, sleep_s: float = 0.3, binary: bool = False, retries: int = 2):
    """GET a URL with the browser UA; returns text (or bytes) or None."""
    for attempt in range(retries + 1):
        _throttle(sleep_s)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                return data if binary else data.decode("utf-8", errors="ignore")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            LOG.warning("fetch failed (%s/%s) %s: %s", attempt + 1, retries + 1, url, exc)
            time.sleep(1.5 * (attempt + 1))
    return None


# ---------------------------------------------------------------- helpers
def strip_tags(s: str) -> str:
    s = re.sub(r"<script.*?</script>|<style.*?</style>", "", s, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>|</div>|</dd>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\xa0]+", " ", s)
    s = re.sub(r"\s*\n\s*", "\n", s)
    return s.strip()


def clean_html(frag: str, limit: int = 6000) -> str:
    """Remove scripts, styles, inline attributes and tracking from a description."""
    frag = re.sub(r"<script.*?</script>|<style.*?</style>|<!--.*?-->", "", frag, flags=re.S | re.I)
    frag = re.sub(r"<(img|iframe|object|embed|form|input|font|span)[^>]*>|</(font|span)>", "", frag, flags=re.I)
    frag = re.sub(r"<(\w+)[^>]*>", lambda m: "<%s>" % m.group(1).lower(), frag)
    frag = re.sub(r"<p>\s*</p>|<div>\s*</div>", "", frag)
    frag = re.sub(r"\s+", " ", frag).strip()
    if len(frag) > limit:
        cut = frag[:limit]
        cut = cut[: cut.rfind("</")] if "</" in cut else cut
        frag = cut + " <p>[truncated]</p>"
    return frag


SAL_RE = re.compile(
    r"(?P<cur>[£€$])\s?(?P<a>\d[\d,\.]*)\s*(?P<ak>k)?"
    r"(?:\s*(?:-|–|to|and)\s*(?:[£€$]\s?)?(?P<b>\d[\d,\.]*)\s*(?P<bk>k)?)?"
    r"\s*(?P<per>pa|per annum|p\.a\.|/annum|per year|pm|per month|ph|per hour|/hour|per day|pd|per week|pw)?",
    re.I)


GARBLED_POUND_RE = re.compile(r"(?:\u00c2\u00a3|\u00c2\ufffd|\ufffd)(?=\s?(?:\d|k\b))")


SAL_RE_TRAIL = re.compile(
    r"(?P<a>\d[\d,\.]*)\s*(?P<ak>k)?\s*(?P<cur>[£€$])"
    r"(?:\s*(?:-|–|to|and)\s*(?P<b>\d[\d,\.]*)\s*(?P<bk>k)?\s*[£€$])?"
    r"\s*(?P<per>pa|per annum|p\.a\.|per year|pm|per month|ph|per hour|per day|pd|per week|pw)?", re.I)


def parse_salary(text: str | None):
    """Return (min, max, currency, period) from an explicit salary string."""
    if not text:
        return None, None, None, None
    # The source site serves some adverts in the wrong encoding: "£" arrives as
    # "Â£" or U+FFFD. Normalise before matching so a garbled upper bound is not
    # lost (found by tests/greenjobs_redesign/test_scrape.py, 2026-09-28).
    text = GARBLED_POUND_RE.sub("\u00a3", text)
    m = SAL_RE.search(text)
    if not m:
        m = SAL_RE_TRAIL.search(text)
    if not m:
        return None, None, None, None

    def num(v, k):
        if not v:
            return None
        try:
            f = float(v.replace(",", ""))
        except ValueError:
            return None
        return int(f * 1000) if k else int(f)

    a, b = num(m.group("a"), m.group("ak")), num(m.group("b"), m.group("bk"))
    if a is None or a < 100 and not m.group("per"):
        return None, None, None, None
    cur = {"£": "GBP", "€": "EUR", "$": "USD"}[m.group("cur")]
    per = (m.group("per") or "").lower()
    period = ("hour" if per in ("ph", "per hour", "/hour") else
              "day" if per in ("pd", "per day") else
              "week" if per in ("pw", "per week") else
              "month" if per in ("pm", "per month") else
              "year" if per else None)
    if period is None:
        period = "hour" if a < 100 else "day" if a < 1000 else "month" if a < 10000 else "year"
    return a, b if b is not None else None, cur, period


def first(pattern: str, text: str, flags: int = 0):
    """Return the whole match (or group 1 when present) of pattern in text, else None."""
    m = re.search(pattern, text, flags)
    if not m:
        return None
    return m.group(1) if m.groups() else m.group(0)


def slugify(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


# ---------------------------------------------------------------- homepage facets
def parse_facets(home: str, base: str) -> dict:
    """Parse every 'Search By ...' box on the homepage into name/slug/url/count lists."""
    out = {}
    for m in re.finditer(r'<div class="searchByBox"><h2>Search By(?:&nbsp;| )([^<]+)</h2>(.*?)</ul>', home, re.S):
        key = m.group(1).strip().lower()
        items = []
        for a in re.finditer(r'<a href="([^"]+)" title="([^"]*)">.*?<em>\((\d+)\)</em>', m.group(2)):
            items.append({"name": html.unescape(a.group(2)), "slug": slugify(a.group(1)),
                          "url": base + a.group(1), "count": int(a.group(3))})
        out[key] = items
    # Region tab (UK): plain links without counts; IE: location tab with country links
    loc = re.search(r'id="locationTab".*?</div>\s*</div>', home, re.S)
    if loc:
        items = []
        for a in re.finditer(r'<a href="([^"]+)"[^>]*title="([^"]*)"[^>]*>(.*?)</a>', loc.group(0)):
            cnt = re.search(r"\((\d+)\)", a.group(3))
            href = a.group(1)
            items.append({"name": html.unescape(a.group(2)), "slug": slugify(href.split("=")[-1]),
                          "url": href if href.startswith("http") else base + href,
                          "count": int(cnt.group(1)) if cnt else None})
        seen = set()
        out["location"] = [i for i in items if not (i["name"] in seen or seen.add(i["name"]))]
    return out


def parse_featured_employers(home: str, base: str) -> list:
    emp = {}
    for m in re.finditer(r'<a href="([^"]+)"[^>]*>\s*<img src="([^"]+)"[^>]*(?:title|alt)="([^"]*)"', home):
        href, src, name = m.group(1), m.group(2), html.unescape(m.group(3))
        if "clientlogos" not in src and "banners/BANNER_fea" not in src:
            continue
        u = re.search(r"u=([^&]+)", href)
        target = urllib.parse.unquote(u.group(1)) if u else base + href
        if "browse-jobs" not in target and "companies" not in target:
            continue
        emp.setdefault(name, {"name": name, "logo_url": base + src, "url": target})
    return list(emp.values())


# ---------------------------------------------------------------- results + jobs
def parse_results(page: str, base: str) -> tuple[list, int]:
    total = re.search(r'numResultsTop"><strong>(\d+)</strong>', page)
    jobs = []
    for m in re.finditer(r'<div id="jobResult(\d+)" class="jobInfo([^"]*)">(.*?)<p class="jobDescription">', page, re.S):
        jid, cls, body = m.group(1), m.group(2), m.group(3)
        href = re.search(r'href="(/jobs/\d+/[^"]+)"', body)
        logo = re.search(r'<img src="([^"]+)"[^>]*alt="([^"]*)"', body)
        jobs.append({"id": jid, "url": base + href.group(1) if href else None,
                     "featured": "featuredJob" in cls,
                     "logo_url": base + logo.group(1) if logo else None,
                     "employer": html.unescape(logo.group(2)) if logo else None})
    return jobs, int(total.group(1)) if total else 0


def dl_items(dd: str) -> list:
    return [html.unescape(x) for x in re.findall(r"<em>(.*?)</em>", dd)]


def parse_job(page: str, base: str, meta: dict, country: str, currency: str) -> dict:
    sec = re.search(r'<div id="JBcontent" class="jobView">(.*?)<div id="right"', page, re.S)
    body = sec.group(1) if sec else page
    title = re.search(r"<h1>(.*?)</h1>", body, re.S)
    fields = {}
    for m in re.finditer(r'<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>', body, re.S):
        fields[strip_tags(m.group(1)).rstrip(":").strip()] = m.group(2)
    desc = re.search(r'<div class="jobDescription">(.*?)</div>\s*<!-- job documents -->', body, re.S)
    desc_html = clean_html(desc.group(1)) if desc else ""
    logo = re.search(r'<div class="jobLogo">.*?<img src="([^"]+)"[^>]*?(?:title|alt)="([^"]*)"', body, re.S)
    recruiter = strip_tags(fields.get("Recruiter", "")) or (html.unescape(logo.group(2)) if logo else meta.get("employer"))
    salary_text = strip_tags(fields.get("Salary", "")) or None
    salary_desc = strip_tags(fields.get("Salary Description", "")) or None
    sal_text = salary_text or salary_desc
    smin, smax, scur, sper = parse_salary(sal_text)
    vicinity = dl_items(fields.get("Vicinity", "")) or [strip_tags(fields.get("Vicinity", ""))]
    region = dl_items(fields.get("Region", ""))
    location = ", ".join([v for v in vicinity if v]) or ", ".join(region)
    return {
        "id": meta["id"], "slug": slugify(meta["url"]).replace(".asp", ""),
        "title": strip_tags(title.group(1)) if title else None, "url": meta["url"],
        "employer": recruiter or None,
        "location": location, "region": ", ".join(region), "country": country,
        "type": ", ".join(dl_items(fields.get("Job Type", ""))) or None,
        "salary_text": sal_text, "salary_min": smin, "salary_max": smax,
        "currency": scur, "period": sper,
        "sectors": dl_items(fields.get("Sector", "")),
        "categories": dl_items(fields.get("Job Category", "")),
        "education": ", ".join(dl_items(fields.get("Education Level", ""))) or None,
        "posted": strip_tags(fields.get("Posted", "")) or None,
        "closing": strip_tags(fields.get("Closing Date", "")) or None,
        "start_date": strip_tags(fields.get("Start Date", "")) or None,
        "job_ref": strip_tags(fields.get("Job Ref", "")) or None,
        "featured": meta.get("featured", False),
        "summary": re.sub(r"\s+", " ", strip_tags(desc_html))[:400] if desc_html else "",
        "description_html": desc_html,
        "logo_url": (base + logo.group(1)) if logo else meta.get("logo_url"),
    }


def crawl_site(key: str, max_jobs: int, concurrency: int, sleep_s: float, out_dir: str,
               assets_dir: str | None) -> dict:
    cfg = SITES[key]
    base, country = cfg["base"], "Ireland" if key == "ie" else "United Kingdom"
    home = fetch(base + "/", sleep_s)
    if not home and os.path.exists(cfg["snapshot"]):
        LOG.warning("using homepage snapshot %s", cfg["snapshot"])
        with open(cfg["snapshot"], encoding="utf-8", errors="ignore") as fh:
            home = fh.read()
    if not home:
        raise SystemExit("cannot fetch homepage for " + key)
    facets = parse_facets(home, base)
    employers = parse_featured_employers(home, base)

    # results paging
    listing, total, pg = [], None, 1
    while True:
        page = fetch(f"{base}/jobboard/cands/jobresults.asp?pg={pg}", sleep_s)
        if not page:
            break
        jobs, total = parse_results(page, base)
        if not jobs:
            break
        listing.extend(jobs)
        LOG.info("%s results page %d: %d jobs (total %s)", key, pg, len(jobs), total)
        if len(listing) >= min(total, max_jobs):
            break
        pg += 1
    seen, uniq = set(), []
    for j in listing:
        if j["url"] and j["id"] not in seen:
            seen.add(j["id"])
            uniq.append(j)
    uniq = uniq[:max_jobs]

    def work(meta):
        page = fetch(meta["url"], sleep_s)
        return parse_job(page, base, meta, country, cfg["currency"]) if page else None

    with cf.ThreadPoolExecutor(max_workers=concurrency) as ex:
        jobs = [j for j in ex.map(work, uniq) if j]
    LOG.info("%s: parsed %d/%d job pages", key, len(jobs), len(uniq))

    # employers from jobs (merge)
    known = {e["name"] for e in employers}
    for j in jobs:
        if j["employer"] and j["employer"] not in known:
            known.add(j["employer"])
            employers.append({"name": j["employer"], "logo_url": j["logo_url"],
                              "url": f"{base}/browse-jobs/{re.sub(r'[^a-z0-9]+', '-', j['employer'].lower()).strip('-')}/"})

    # info pages (plain text) for brief writing
    pages = {}
    for path in INFO_PAGES:
        p = fetch(base + path, sleep_s)
        if not p:
            continue
        m = re.search(r'<div id="(?:JBcontent|content)[^"]*"[^>]*>(.*?)<div id="right"', p, re.S) or \
            re.search(r'<div id="main"[^>]*>(.*?)<div id="footer"', p, re.S)
        pages[path] = {"url": base + path, "title": (first(r"<title>(.*?)</title>", p, re.S) or "").strip(),
                       "text": strip_tags(m.group(1) if m else p)[:12000],
                       "links": sorted(set(re.findall(r'href="(https?://[^"]+)"', m.group(1) if m else p))),
                       "images": sorted(set(re.findall(r'<img[^>]*src="([^"]+)"', m.group(1) if m else p)))}
    about = pages.get("/about-us.cms.asp", {}).get("text", "")
    about = about.split("About GreenJobs", 1)[-1].strip() if "About GreenJobs" in about else about

    contact_txt = pages.get("/contact-us.cms.asp", {}).get("text", "")
    contact = {
        "source": base + "/contact-us.cms.asp",
        "company": "GreenJobs Limited (The GreenJobs Network of Websites)" if "GreenJobs Limited" in contact_txt else None,
        "address": first(r"Ennis Digital Hub.*?Ireland", contact_txt, re.S),
        "phones": re.findall(r"Telephone Number \(([^)]+)\): ([+\d() ]+\d)", contact_txt),
        "emails": [e.replace("(at)", "@") for e in re.findall(r"[\w.]+\(at\)[\w.]+", contact_txt)] +
                  sorted(set(re.findall(r"mailto:([^\"?]+)", home))),
        "opening_hours": first(r"Our Opening Hours.*?2pm", contact_txt, re.S),
    }
    contact["address"] = ", ".join(x.strip() for x in contact["address"].splitlines() if x.strip()) if contact["address"] else None

    net = pages.get("/the-greenjobs-network-of-websites.cms.asp", {})
    network = [{"url": u, "name": urllib.parse.urlparse(u).netloc.replace("www.", "")}
               for u in net.get("links", []) if re.search(r"jobs(uk)?\.(com|ie|co\.uk)", u)]
    if not network:
        network = [{"url": u, "name": urllib.parse.urlparse(u).netloc.replace("www.", "")}
                   for u in sorted(set(re.findall(r'href="(https://www\.\w+jobs(?:uk)?\.(?:com|ie|co\.uk)/)"', home)))]

    # regions: UK from homepage facet, IE derived from job vicinities
    regions = facets.get("region") or []
    if not regions:
        counts = {}
        for j in jobs:
            for loc in [x.strip() for x in j["location"].split(",") if x.strip()]:
                counts[loc] = counts.get(loc, 0) + 1
        regions = [{"name": n, "slug": re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-"),
                    "url": f"{base}/browse-jobs/{re.sub(r'[^a-z0-9]+', '-', n.lower()).strip('-')}/",
                    "count": c} for n, c in sorted(counts.items(), key=lambda x: -x[1])]

    data = {
        "site": cfg["site"], "base_url": base, "fetched": FETCHED, "jobs": jobs,
        "sectors": facets.get("sector") or facets.get("industry sector") or [],
        "categories": facets.get("job category", []),
        "regions": regions, "locations": facets.get("location", []),
        "job_types": facets.get("job type", []),
        "employers": employers, "about": about, "about_source": base + "/about-us.cms.asp",
        "contact": contact, "network_sites": network,
        "stats": {"total_jobs": total, "jobs_scraped": len(jobs),
                  "jobs_with_salary": sum(1 for j in jobs if j["salary_min"] is not None),
                  "jobs_with_salary_text": sum(1 for j in jobs if j["salary_text"]),
                  "featured_jobs": sum(1 for j in jobs if j["featured"])},
    }
    floor = snapshot_floor(os.path.join(out_dir, f"{key}.json"))
    if len(jobs) < floor:
        LOG.error("%s: collected %d jobs, below the floor of %d (50%% of the existing snapshot); src/data left untouched", key, len(jobs), floor)
        data["stats"]["rejected"] = f"{len(jobs)} jobs < floor {floor}"
        return data
    write_json_atomic(os.path.join(out_dir, f"{key}.json"), data)
    write_json_atomic(os.path.join(out_dir, f"pages_{key}.json"), pages)
    write_json_atomic(os.path.join(out_dir, f"perf_{key}.json"), measure_page(home, base))
    if assets_dir:
        download_logos(key, home, employers, base, assets_dir, sleep_s)
        data["stats"]["client_logos"] = len(refresh_clients(key, assets_dir, sleep_s, out_dir))
    return data


def snapshot_floor(path: str, ratio: float = 0.5) -> int:
    """Minimum job count a crawl must reach before it may replace the snapshot
    at `path`: half of the jobs in the existing file (0 when there is none or
    it is unreadable). Guards src/data against a broken crawl (panel 10)."""
    try:
        with open(path, encoding="utf-8") as fh:
            existing = json.load(fh)
    except (OSError, ValueError):
        return 0
    n = len(existing.get("jobs") or []) if isinstance(existing, dict) else 0
    return math.ceil(n * ratio)


def write_json_atomic(path: str, payload) -> None:
    """Write to a temp file beside the target, then rename over it, so a crash
    mid-write never leaves a truncated snapshot."""
    tmp = f"{path}.tmp{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def measure_page(home: str, base: str) -> dict:
    scripts = re.findall(r'<script[^>]*src="([^"]+)"', home)
    css = re.findall(r'<link[^>]*rel="stylesheet"[^>]*href="([^"]+)"', home) or re.findall(r'<link[^>]*href="([^"]+\.css[^"]*)"', home)
    imgs = re.findall(r'<img[^>]*src="([^"]+)"', home)
    inline_js = len(re.findall(r"<script(?![^>]*src)", home))
    return {"html_bytes": len(home.encode("utf-8")), "script_tags_external": len(scripts),
            "scripts": scripts, "stylesheets": css, "img_tags": len(imgs),
            "inline_script_blocks": inline_js,
            "inline_style_attrs": len(re.findall(r'style="', home)),
            "total_requests_estimate": 1 + len(scripts) + len(css) + len(set(imgs)),
            "has_viewport_meta": bool(re.search(r'name="viewport"', home)),
            "links_total": len(re.findall(r"<a ", home)),
            "browse_links": len(re.findall(r'href="/browse-jobs/', home)),
            "jquery": first(r"jquery/([\d.]+)/", home),
            "bootstrap": "bootstrap.min.js" in home, "html5shiv": "html5shiv" in home,
            "platform_cdn": "sjbimg.com" in home, "ga4": re.findall(r"gtag/js\?id=([\w-]+)", home)}


CLIENTS_PAGE = "/for-employers.asp"
CLIENT_LOGO_MAX_BYTES = 200 * 1024
# Filename-derived names: acronyms the client's slugs spell in lower case, and
# the spelling slips in the live filenames (kept as the client publishes them
# on the wall, corrected only in the visible name).
_ACRONYMS = {"bgs", "ukho", "weca", "mwp", "hta", "nhs", "hsbc", "gsk", "kpmg", "res", "rwe", "bre", "wwf",
             "apem", "mko", "uk", "bvg", "jba", "suez", "atos", "wsp"}
_SLUG_FIXES = {"repsonsible": "responsible", "orsted": "ørsted", "ennvironment": "environment", "parliment": "parliament",
               "incoporating": "incorporating", "buckinghamshirecouncil": "buckinghamshire-council"}
_SMALL_WORDS = {"of", "and", "for", "the", "in"}


def client_name_from_file(fname: str) -> str:
    """'aberdeen-city-council-logo.png' -> 'Aberdeen City Council'."""
    stem = os.path.splitext(os.path.basename(fname))[0].lower()
    for bad, good in _SLUG_FIXES.items():
        stem = stem.replace(bad, good)
    stem = re.sub(r"[-_]?logo$", "", stem)
    words = [w for w in re.split(r"[-_]+", stem) if w]
    out = []
    for i, w in enumerate(words):
        if w in _ACRONYMS:
            out.append(w.upper())
        elif w in _SMALL_WORDS and i:
            out.append(w)
        else:
            out.append(w[:1].upper() + w[1:])
    return " ".join(out) or stem


def parse_client_logos(page: str, base: str) -> list:
    """Every logo on the /for-employers.asp client wall: [{name, src}] in page
    order, deduplicated by file name. The name is the alt text when the site
    gives one (it does not today), else derived from the file name."""
    m = re.search(r'<div id="clientLogos">(.*?)</ul>', page, re.S)
    scope = m.group(0) if m else page  # no wrapper: any /logos/advertise/ image on the page
    seen, out = set(), []
    for tag in re.findall(r"<img\b[^>]*>", scope, re.I):
        src = first(r'src="([^"]+)"', tag)
        if not src or "/logos/advertise/" not in src:
            continue
        url = src if src.startswith("http") else (("https:" + src) if src.startswith("//") else base + src)
        fname = os.path.basename(urllib.parse.urlparse(url).path)
        if not fname or fname in seen:
            continue
        seen.add(fname)
        alt = html.unescape(first(r'\balt="([^"]*)"', tag) or "").strip()
        out.append({"name": alt or client_name_from_file(fname), "src": url})
    return out


def download_client_logos(key: str, page: str, base: str, assets_dir: str, sleep_s: float, out_dir: str) -> list:
    """Fetch the client wall into {assets_dir}/clients/ (atomic writes, dedupe by
    file name, <= CLIENT_LOGO_MAX_BYTES each), record each in logos.json under
    'client:<file>' with source and fetched date, and write {out_dir}/clients_{key}.json
    = [{name, file, source}]. Returns the list written (empty when the page is
    unreachable; the previous clients_{key}.json is then left untouched)."""
    logos = parse_client_logos(page, base)
    if not logos:
        LOG.error("%s: no client logos found on %s", key, CLIENTS_PAGE)
        return []
    cdir = os.path.join(assets_dir, "clients")
    os.makedirs(cdir, exist_ok=True)
    manifest_path = os.path.join(assets_dir, "logos.json")
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path) as fh:
            manifest = json.load(fh)
    today = time.strftime("%Y-%m-%d")
    written = []
    for item in logos:
        fname = os.path.basename(urllib.parse.urlparse(item["src"]).path)
        target = os.path.join(cdir, fname)
        mkey = "client:" + fname
        if not os.path.exists(target):
            blob = fetch(item["src"], sleep_s, binary=True, retries=1)
            if not blob:
                LOG.warning("%s: client logo unreachable, skipped: %s", key, item["src"])
                continue
            if len(blob) > CLIENT_LOGO_MAX_BYTES:
                blob = shrink_image(blob, fname)  # a few wall PNGs are 400-500 KB originals
                if not blob or len(blob) > CLIENT_LOGO_MAX_BYTES:
                    LOG.warning("%s: client logo over %d KB even after shrinking, skipped: %s", key, CLIENT_LOGO_MAX_BYTES // 1024, item["src"])
                    continue
            tmp = f"{target}.tmp{os.getpid()}"
            with open(tmp, "wb") as fh:
                fh.write(blob)
            os.replace(tmp, target)
            manifest[mkey] = {"file": "clients/" + fname, "source": item["src"], "bytes": len(blob), "site": key, "fetched": today, "name": item["name"]}
        else:
            rec = manifest.setdefault(mkey, {"file": "clients/" + fname, "source": item["src"], "bytes": os.path.getsize(target), "site": key, "name": item["name"]})
            rec.setdefault("fetched", today)
        written.append({"name": item["name"], "file": fname, "source": item["src"]})
    write_json_atomic(manifest_path, manifest)
    if written:
        write_json_atomic(os.path.join(out_dir, f"clients_{key}.json"), written)
    LOG.info("%s: client wall %d logos on the page, %d files available", key, len(logos), len(written))
    return written


def shrink_image(blob: bytes, fname: str, max_w: int = 480) -> bytes | None:
    """Strip metadata (the oversize wall PNGs are 120x60 px carrying ~400 KB of
    ICC/XMP) and downscale to at most `max_w` px wide (Pillow, when installed),
    then re-encode optimised. None when Pillow is missing or the file cannot be
    decoded; the caller then skips the logo."""
    try:
        from PIL import Image  # optional dependency
        import io
        im = Image.open(io.BytesIO(blob))
        im.load()
        if im.width > max_w:
            im = im.resize((max_w, max(1, round(im.height * max_w / im.width))), Image.LANCZOS)
        clean = Image.new(im.mode, im.size)  # a fresh image carries no icc_profile/xmp chunks
        clean.paste(im)
        im = clean
        out = io.BytesIO()
        if fname.lower().endswith((".jpg", ".jpeg")):
            im.convert("RGB").save(out, "JPEG", quality=82, optimize=True)
        else:
            im.save(out, "PNG", optimize=True)
        return out.getvalue()
    except Exception as exc:  # noqa: BLE001 - any decode failure just skips the logo
        LOG.warning("shrink failed for %s: %s", fname, exc)
        return None


def refresh_clients(key: str, assets_dir: str, sleep_s: float, out_dir: str) -> list:
    """Fetch /for-employers.asp (one retry inside fetch) and run download_client_logos."""
    base = SITES[key]["base"]
    page = fetch(base + CLIENTS_PAGE, sleep_s, retries=1)
    if not page:
        LOG.error("%s: cannot fetch %s; clients_%s.json left untouched", key, CLIENTS_PAGE, key)
        return []
    return download_client_logos(key, page, base, assets_dir, sleep_s, out_dir)


def download_logos(key: str, home: str, employers: list, base: str, assets_dir: str, sleep_s: float) -> None:
    os.makedirs(assets_dir, exist_ok=True)
    manifest_path = os.path.join(assets_dir, "logos.json")
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path) as fh:
            manifest = json.load(fh)
    targets = []
    for src in re.findall(r'<img[^>]*src="([^"]+)"', home):
        if re.search(r"logo|bcorp|b-corp|corp", src, re.I) and "clientlogos" not in src and "banners" not in src:
            targets.append(("site:" + key + ":" + os.path.basename(src), src))
    for src in set(re.findall(r'src="([^"]*(?:\.svg))"', home)):
        targets.append(("site:" + key + ":" + os.path.basename(src), src))
    for e in employers[:30]:
        if e.get("logo_url"):
            targets.append((e["name"], e["logo_url"]))
    for name, src in targets:
        url = src if src.startswith("http") else (("https:" + src) if src.startswith("//") else base + src)
        fname = os.path.basename(urllib.parse.urlparse(url).path)
        if not fname or name in manifest and manifest[name].get("file") == fname and os.path.exists(os.path.join(assets_dir, fname)):
            continue
        blob = fetch(url, sleep_s, binary=True, retries=1)
        if not blob:
            continue
        with open(os.path.join(assets_dir, fname), "wb") as fh:
            fh.write(blob)
        manifest.setdefault(name, {"file": fname, "source": url, "bytes": len(blob), "site": key})
    write_json_atomic(manifest_path, manifest)  # never a half-written logos.json (round 4)


# ---------------------------------------------------------------- live snapshot (2026-11-20)
# Public pages only, read-only, <= 1 request/second, honest generic User-Agent,
# robots.txt honoured. Enabled by --snapshot; the default crawl above is unchanged.
SNAPSHOT_UA = (
    "GreenJobsMigrationSnapshot/1.0 (read-only copy of public pages for the site owner)"
)
SNAPSHOT_MIN_SLEEP = 1.0
KEITH_COUNTS = {
    "told": {"uk": 105, "ie": 133},
    "observed_2026-11-16": {"uk": 78, "ie": 145},
}

# Multiposter / feed vendors (a hit means a job may arrive by feed) versus
# employer ATS hosts (a hit only means the apply link goes to the employer's own system).
FEED_VENDORS = {
    "broadbean": r"broadbean|adcourier|aplitrak",
    "idibu": r"idibu",
    "logicmelon": r"logic-?melon",
    "jobg8": r"jobg8",
    "multiposter_other": r"multiposting|jobmultiposter|jobtarget|veritone|jobiak",
}
ATS_HOSTS = {
    "workday": r"myworkdayjobs\.com|myworkday\.com",
    "oracle_cloud": r"oraclecloud\.com",
    "greenhouse": r"greenhouse\.io",
    "lever": r"lever\.co",
    "smartrecruiters": r"smartrecruiters\.com",
    "successfactors": r"successfactors|sapsf\.",
    "taleo": r"taleo\.net",
    "icims": r"icims\.com",
    "workable": r"workable\.com",
    "bullhorn": r"bullhorn|bhhosted",
    "tribepad": r"tribepad",
    "eploy": r"eploy\.",
    "jobadder": r"jobadder",
    "cezanne": r"cezanne",
    "hireful": r"hireful",
    "teamtailor": r"teamtailor",
    "pinpoint": r"pinpointhq",
    "recruitee": r"recruitee\.com",
    "brassring": r"brassring",
    "jobvite": r"jobvite",
    "ukg": r"ultipro|ukg\.com",
    "dayforce": r"dayforcehcm",
    "avature": r"avature",
    "csod": r"csod\.com",
    "aecom_jobs": r"^aecom\.jobs$",
}
TRACKING_PARAM_RE = re.compile(
    r"[?&](utm_\w+|source|src|trackid|tracking\w*|xs|bbid|aplitrak\w*|ref|referrer|via)=",
    re.I,
)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
APPLY_CONTEXT_RE = re.compile(
    r"apply|application|send|submit|forward|CV|resume|curriculum|cover letter|enquir|contact",
    re.I,
)
OWN_DOMAINS = ("greenjobs.ie", "greenjobs.co.uk")


def _host(url: str) -> str:
    h = (urllib.parse.urlparse(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def hidden_fields(page: str) -> dict:
    """name -> value for every hidden input on the page (first occurrence wins)."""
    out = {}
    for tag in re.findall(r"<input\b[^>]*>", page, re.I):
        if not re.search(r'type\s*=\s*["\']?hidden', tag, re.I):
            continue
        name = first(r'\bname\s*=\s*"([^"]*)"', tag)
        if name and name not in out:
            out[name] = html.unescape(first(r'\bvalue\s*=\s*"([^"]*)"', tag) or "")
    return out


def classify_apply(page: str, desc_html: str, own_hosts=OWN_DOMAINS) -> dict:
    """Deterministic apply-mechanism rules, in priority order:
    1. hidden strAppLink = mailto:  -> email;  http(s) to a foreign host -> link;  own host -> falls through.
    2. no usable strAppLink and the description carries a mailto: link, or an e-mail address within
       120 chars of an apply word (apply/send/CV/...) -> email.
    3. otherwise the 'Apply Now' button posts the site's own form (JobApplyLink.asp) -> onsite_form.
    Returns {mode, email, link, link_host, evidence}; evidence is the snippet that decided it.
    """
    hid = hidden_fields(page)
    raw = (hid.get("strAppLink") or "").strip()
    if raw.lower().startswith("mailto:"):
        addr = raw[7:].split("?")[0].strip()
        return {
            "mode": "email",
            "email": addr,
            "link": None,
            "link_host": None,
            "evidence": f'strAppLink="{raw[:160]}"',
        }
    if re.match(r"https?://", raw, re.I):
        host = _host(raw)
        if not any(host == d or host.endswith("." + d) for d in own_hosts):
            return {
                "mode": "link",
                "email": None,
                "link": raw,
                "link_host": host,
                "evidence": f'strAppLink="{raw[:200]}"',
            }
    text = desc_html or ""
    m = re.search(r'mailto:([^"\'?>\s]+)', text, re.I)
    if m:
        return {
            "mode": "email",
            "email": m.group(1).strip(),
            "link": None,
            "link_host": None,
            "evidence": re.sub(
                r"\s+", " ", strip_tags(text[max(0, m.start() - 80) : m.end() + 40])
            )[:200]
            or m.group(0),
        }
    plain = strip_tags(text)
    for em in EMAIL_RE.finditer(plain):
        ctx = plain[max(0, em.start() - 120) : em.end() + 60]
        if APPLY_CONTEXT_RE.search(ctx):
            return {
                "mode": "email",
                "email": em.group(0),
                "link": None,
                "link_host": None,
                "evidence": re.sub(r"\s+", " ", ctx).strip()[:200],
            }
    form = first(r'action="(/jobboard/cands/JobApplyLink\.asp[^"]*)"', page)
    return {
        "mode": "onsite_form",
        "email": None,
        "link": None,
        "link_host": None,
        "evidence": (
            ("form action=" + html.unescape(form)[:120])
            if form
            else "no strAppLink, no e-mail in description; Apply Now form"
        ),
    }


def detect_feed_markers(
    page: str, apply: dict, job_ref: str | None, hidden: dict | None = None
) -> dict:
    """Markers that a job came in through a multiposter feed. Reports vendor hits (Broadbean, Idibu,
    LogicMelon, JobG8 ...) found in the page source or apply URL, tracking parameters on the apply URL,
    the employer ATS behind an apply link, the job-ref shape and any unexpected hidden field.
    `feed_vendor` is set only on a vendor hit; an ATS host alone is NOT a feed marker.
    """
    hid = hidden if hidden is not None else hidden_fields(page)
    markers = []
    haystack = [
        ("apply_url", apply.get("link") or ""),
        ("job_ref", job_ref or ""),
        ("hidden_fields", " ".join(f"{k}={v}" for k, v in hid.items())),
        (
            "page_source",
            re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I),
        ),
    ]
    for vendor, pat in FEED_VENDORS.items():
        for where, text in haystack:
            m = re.search(pat, text, re.I)
            if m:
                markers.append(
                    {
                        "kind": "vendor",
                        "vendor": vendor,
                        "where": where,
                        "evidence": text[max(0, m.start() - 40) : m.end() + 40].strip()[
                            :160
                        ],
                    }
                )
                break
    link = apply.get("link") or ""
    host = apply.get("link_host") or ""
    ats = None
    for name, pat in ATS_HOSTS.items():
        if host and re.search(pat, host, re.I):
            ats = name
            break
    if link and TRACKING_PARAM_RE.search(link):
        markers.append(
            {
                "kind": "tracking_param",
                "vendor": None,
                "where": "apply_url",
                "evidence": ",".join(
                    sorted(
                        {m.group(1).lower() for m in TRACKING_PARAM_RE.finditer(link)}
                    )
                ),
            }
        )
    extra = sorted(k for k in hid if k not in ("strAppLink", "cookie"))
    if extra:
        markers.append(
            {
                "kind": "extra_hidden_field",
                "vendor": None,
                "where": "hidden_fields",
                "evidence": ",".join(extra),
            }
        )
    ref_shape = None
    if job_ref:
        ref_shape = re.sub(r"[A-Za-z]", "A", re.sub(r"\d", "9", job_ref.strip()))[:30]
    vendors = sorted({m["vendor"] for m in markers if m["kind"] == "vendor"})
    return {
        "feed_vendor": vendors[0] if vendors else None,
        "vendors": vendors,
        "employer_ats": ats,
        "job_ref_shape": ref_shape,
        "markers": markers,
    }


def day_first_iso(raw: str | None) -> str | None:
    """'31/10/2026' -> '2026-10-31' (day-first only); None when not a date."""
    m = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$", raw or "")
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= d <= 31 and 1 <= mo <= 12):
        return None
    return f"{y:04d}-{mo:02d}-{d:02d}"


def employer_class(name: str | None) -> str:
    """'gaia' (Gaia Talent's own jobs), 'chm_recruit', 'mattinson', 'third_party' or 'unknown' from the employer field."""
    n = (name or "").strip().lower()
    if not n:
        return "unknown"
    if re.search(r"\bgaia\s+talent\b", n):
        return "gaia"
    if re.search(r"\bchm\s+recruit", n):
        return "chm_recruit"
    if re.search(r"\bmattinson\s+partnership\b", n):
        return "mattinson"
    return "third_party"


def snapshot_record(job: dict, page: str, site: str, fetched_at: str) -> dict:
    """Extend a parse_job() dict with the snapshot fields: ISO dates, employer link, apply mode with
    evidence, feed markers and the source URL. Pure function of the page."""
    base = SITES[site]["base"]
    apply = classify_apply(page, job.get("description_html") or "")
    hid = hidden_fields(page)
    sec = re.search(
        r'<div id="JBcontent" class="jobView">(.*?)<div id="right"', page, re.S
    )
    body = sec.group(1) if sec else page
    emp_href = first(r'<div class="jobLogo"><a href="(/browse-jobs/[^"]+)"', body)
    return {
        "id": job["id"],
        "site": site,
        "source_url": job["url"],
        "fetched_at": fetched_at,
        "title": job["title"],
        "employer": job["employer"],
        "employer_class": employer_class(job["employer"]),
        "employer_url": base + emp_href if emp_href else None,
        "employer_logo_url": job.get("logo_url"),
        "location": job["location"],
        "region": job["region"],
        "country": job["country"],
        "job_type": job["type"],
        "salary_text": job["salary_text"],
        "closing": job["closing"],
        "closing_iso": day_first_iso(job["closing"]),
        "posted": job["posted"],
        "posted_iso": day_first_iso(job["posted"]),
        "sectors": job["sectors"],
        "categories": job["categories"],
        "job_ref": job["job_ref"],
        "description_html": job["description_html"],
        "featured": job["featured"],
        "apply": apply,
        "feed": detect_feed_markers(page, apply, job["job_ref"], hid),
    }


# --- URL inventory -> redirect map -------------------------------------------------
STATIC_TARGETS = (
    {  # old static page -> page the build actually produces (edition-relative)
        "/": "",
        "/for-employers.asp": "employers/",
        "/recruiter-zone-advertising.cms.asp": "employers/",
        "/recruiter-zone-advertising-form.asp": "employers/",
        "/green-job-sectors.cms.asp": "sectors/",
        "/company-az/": "employers/",
    }
)
NON_PAGE_PATTERNS = (
    r"^/jobboard/(scripts/(?!vbs/adredirect)|public|images|css|js)",
    r"^/(images|css|js|scripts)/",
    r"\.(png|jpe?g|gif|svg|css|js|ico|woff2?)$",
)
ACCOUNT_PATTERN = r"^/jobboard/cands/(candLogin|candRegister|cookie-policy|jobWishList|searchCriteria|JobApplyLink|tellafriend)\.asp"


def url_pattern(path_qs: str) -> tuple[str, str]:
    """(kind, pattern) for an old-site path (with query). Pattern replaces ids with {id} and slugs with {slug}."""
    u = urllib.parse.urlparse(path_qs)
    p = u.path
    if re.match(r"^/jobs/\d+/[^/]+\.asp$", p):
        return "job", "/jobs/{id}/{slug}.asp"
    if re.match(r"^/jobboard/cands/jobview\.asp$", p, re.I):
        return "job", "/jobboard/cands/jobview.asp?v={id}"
    if re.match(r"^/jobboard/cands/jobresults\.asp$", p, re.I):
        q = urllib.parse.parse_qs(u.query)
        if "lstRegion" in q or "lstVicinity" in q:
            return (
                "location",
                "/jobboard/cands/JobResults.asp?c=1&lstRegion={region}[&lstVicinity={vicinity}]",
            )
        return "listing", "/jobboard/cands/jobresults.asp?pg={n}"
    if re.match(r"^/browse-jobs/[^/]+/?$", p):
        return "facet", "/browse-jobs/{slug}/"
    if re.match(ACCOUNT_PATTERN, p, re.I):
        return "account", p
    if re.match(r"^/jobboard/scripts/vbs/adredirect\.asp$", p, re.I):
        return "banner_redirect", "/jobboard/scripts/vbs/adredirect.asp?b={id}&u={url}"
    if any(re.search(pt, p, re.I) for pt in NON_PAGE_PATTERNS):
        return "asset", "(static asset)"
    if p.startswith("/company-az"):
        return "employer_index", "/company-az/"
    if p == "/" or p.endswith(".asp"):
        return "static", p
    return "other", p


def facet_kinds(facets: dict) -> dict:
    """slug -> kind (sector / category / region / location / job_type) from the homepage facet lists."""
    out = {}
    label = {
        "sector": "sector",
        "industry sector": "sector",
        "job category": "category",
        "region": "region",
        "location": "location",
        "job type": "job_type",
    }
    for key, items in (facets or {}).items():
        for it in items:
            out.setdefault(it["slug"], label.get(key, key))
    return out


def build_landings(ed: str) -> list:
    """The landing pages build_site.py produces for this edition, with the old board sector/location
    slugs that feed each (explicit, so no path is invented). Keep in step with build_site.LANDINGS.
    """
    if ed == "ie":
        return [
            {"slug": "ecology-jobs-ireland", "live_slugs": ["ecology-jobs"]},
            {"slug": "environmental-jobs-dublin", "live_slugs": ["dublin"]},
            {
                "slug": "renewable-energy-jobs-ireland",
                "live_slugs": ["renewable-energy-jobs", "solar-jobs", "wind-jobs"],
            },
            {
                "slug": "sustainability-jobs-ireland",
                "live_slugs": ["sustainability-jobs"],
            },
        ]
    return [
        {"slug": "ecology-jobs-uk", "live_slugs": ["ecology-jobs"]},
        {"slug": "environmental-jobs-london", "live_slugs": ["london"]},
        {
            "slug": "renewable-energy-jobs-uk",
            "live_slugs": ["renewable-energy-jobs", "solar-jobs", "wind-jobs"],
        },
        {"slug": "sustainability-jobs-uk", "live_slugs": ["sustainability-jobs"]},
    ]


def landing_for_slug(ed: str, slug: str) -> str | None:
    for l in build_landings(ed):
        if slug in l["live_slugs"]:
            return l["slug"]
    return None


def map_old_url(
    path_qs: str, site: str, live_ids: set, kinds: dict, employer_slugs: set
) -> dict:
    """Map one old URL to a path the build produces, or mark it unmapped with a proposed target.
    Paths are edition-prefixed as in deliverables/greenjobs_redesign_2026-09-22/site (/{ie|uk}/...).
    """
    ed = site
    kind, pattern = url_pattern(path_qs)
    u = urllib.parse.urlparse(path_qs)
    p = u.path
    res = {"old": path_qs, "kind": kind, "pattern": pattern}
    if kind == "job":
        m = re.match(r"^/jobs/(\d+)/", p)
        jid = m.group(1) if m else (urllib.parse.parse_qs(u.query).get("v") or [""])[0]
        if jid in live_ids:
            return {
                **res,
                "status": "mapped",
                "target": f"/{ed}/jobs/{jid}/",
                "reason": "live job page in the new build",
            }
        return {
            **res,
            "status": "mapped",
            "target": f"/{ed}/jobs/",
            "reason": "job not in the live set (closed/unknown): send to the board",
        }
    if kind == "listing":
        return {
            **res,
            "status": "mapped",
            "target": f"/{ed}/jobs/",
            "reason": "paged results -> board",
        }
    if kind in ("facet", "location"):
        q = urllib.parse.parse_qs(u.query)
        slug = (
            slugify(p)
            if kind == "facet"
            else re.sub(
                r"[^a-z0-9]+",
                "-",
                (q.get("lstVicinity") or q.get("lstRegion") or [""])[0].lower(),
            ).strip("-")
        )
        fk = kinds.get(slug) or ("employer" if slug in employer_slugs else "unknown")
        res["facet_kind"] = fk
        hit = landing_for_slug(ed, slug)
        if hit:
            return {
                **res,
                "status": "mapped",
                "target": f"/{ed}/{hit}/",
                "reason": f"{fk} slug matches a built landing page",
            }
        if fk == "employer":
            return {
                **res,
                "status": "unmapped",
                "target": None,
                "proposed": f"/{ed}/employers/",
                "reason": "the build has no per-employer pages; only /employers/ (advertise page)",
            }
        return {
            **res,
            "status": "unmapped",
            "target": None,
            "proposed": f"/{ed}/jobs/",
            "reason": f"the build has no {fk} page for this slug; board root until a filter URL exists",
        }
    if kind in ("static", "employer_index"):
        if p in STATIC_TARGETS:
            return {
                **res,
                "status": "mapped",
                "target": f"/{ed}/{STATIC_TARGETS[p]}",
                "reason": "equivalent page in the build",
            }
        return {
            **res,
            "status": "unmapped",
            "target": None,
            "proposed": f"/{ed}/",
            "reason": "no equivalent static page in the build (about/contact/terms/privacy/cookie etc.)",
        }
    if kind in ("account", "banner_redirect"):
        return {
            **res,
            "status": "unmapped",
            "target": None,
            "proposed": f"/{ed}/",
            "reason": "candidate account / banner tracker: no equivalent (no candidate data is kept)",
        }
    if kind == "asset":
        return {
            **res,
            "status": "skip",
            "target": None,
            "reason": "static asset, not redirected",
        }
    return {
        **res,
        "status": "unmapped",
        "target": None,
        "proposed": f"/{ed}/",
        "reason": "unrecognised pattern",
    }


def collect_internal_paths(page: str, base: str) -> set:
    """Every same-site href (path + query) on a page, fragments dropped."""
    out = set()
    host = _host(base)
    for h in re.findall(r'href="([^"#]+)', page):
        h = html.unescape(h).strip()
        if h.startswith(("mailto:", "tel:", "javascript:")):
            continue
        if h.startswith("//"):
            h = "https:" + h
        if re.match(r"https?://", h):
            if _host(h) != host:
                continue
            u = urllib.parse.urlparse(h)
            h = u.path + ("?" + u.query if u.query else "")
        if h.startswith("/"):
            out.add(h)
    return out


def parse_sitemap(xml: str) -> tuple[list, list]:
    """(page urls, child sitemap urls) from a sitemap or sitemap index."""
    locs = [
        html.unescape(x).strip()
        for x in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", xml or "")
    ]
    if re.search(r"<sitemapindex", xml or "", re.I):
        return [], locs
    return locs, []


def build_redirect_map(
    site: str,
    paths: set,
    live_ids: set,
    facets: dict,
    employer_slugs: set,
    provenance: str,
) -> dict:
    kinds = facet_kinds(facets)
    entries = [
        map_old_url(p, site, live_ids, kinds, employer_slugs) for p in sorted(paths)
    ]
    pats = {}
    for e in entries:
        r = pats.setdefault(
            e["pattern"],
            {
                "pattern": e["pattern"],
                "kind": e["kind"],
                "count": 0,
                "example": e["old"],
                "mapped": 0,
                "unmapped": 0,
                "skipped": 0,
                "target_rule": None,
                "proposed": None,
                "reason": e["reason"],
            },
        )
        r["count"] += 1
        r[
            (
                "mapped"
                if e["status"] == "mapped"
                else "skipped" if e["status"] == "skip" else "unmapped"
            )
        ] += 1
        if e["status"] == "mapped" and not r["target_rule"]:
            r["target_rule"] = e["target"]
        if e["status"] == "unmapped" and not r["proposed"]:
            r["proposed"] = e.get("proposed")
    return {
        "site": site,
        "provenance": provenance,
        "edition_prefix": f"/{site}/",
        "entries": entries,
        "patterns": sorted(pats.values(), key=lambda r: (-r["count"], r["pattern"])),
        "unmapped": [e for e in entries if e["status"] == "unmapped"],
    }


# --- robots + polite fetch ------------------------------------------------------------
def robots_allows(robots_txt: str | None, url: str, ua: str = SNAPSHOT_UA) -> bool:
    """True when robots.txt permits `url` for `ua`. No robots.txt (None/empty) = allowed."""
    if not robots_txt:
        return True
    import urllib.robotparser

    rp = urllib.robotparser.RobotFileParser()
    rp.parse(robots_txt.splitlines())
    return rp.can_fetch(ua, url)


def robots_sitemaps(robots_txt: str | None) -> list:
    return re.findall(r"(?im)^\s*sitemap:\s*(\S+)", robots_txt or "")


def aggregate_employers(jobs_by_site: dict) -> dict:
    """employers.json payload from the snapshot job records: per site, per employer: job count,
    logo URL, employer page URL, class; plus the Gaia / third-party split of jobs."""
    out = {"sites": {}}
    for site, jobs in jobs_by_site.items():
        emp = {}
        for j in jobs:
            name = j.get("employer") or "(none)"
            e = emp.setdefault(
                name,
                {
                    "name": name,
                    "class": j.get("employer_class") or employer_class(name),
                    "jobs": 0,
                    "job_ids": [],
                    "logo_url": None,
                    "employer_url": None,
                },
            )
            e["jobs"] += 1
            e["job_ids"].append(j["id"])
            e["logo_url"] = e["logo_url"] or j.get("employer_logo_url")
            e["employer_url"] = e["employer_url"] or j.get("employer_url")
        lst = sorted(emp.values(), key=lambda e: (-e["jobs"], e["name"].lower()))
        split = {}
        for j in jobs:
            c = j.get("employer_class") or employer_class(j.get("employer"))
            split[c] = split.get(c, 0) + 1
        out["sites"][site] = {
            "employers": lst,
            "distinct_employers": len(lst),
            "jobs": len(jobs),
            "class_split_jobs": split,
        }
    return out


def snapshot_crawl(key: str, sleep_s: float, max_jobs: int, fetched_at: str) -> dict:
    """Crawl one site read-only: robots, sitemap(s), homepage, every results page, every job page."""
    cfg = SITES[key]
    base = cfg["base"]
    errors = []
    robots = fetch(base + "/robots.txt", sleep_s, retries=0)
    if robots is None:
        errors.append("robots.txt not fetched (treated as allow-all)")
    sitemap_urls, queue = [], list(robots_sitemaps(robots)) or [base + "/sitemap.xml"]
    seen_sm = set()
    while queue and len(seen_sm) < 20:
        sm = queue.pop(0)
        if sm in seen_sm or not robots_allows(robots, sm):
            continue
        seen_sm.add(sm)
        xml = fetch(sm, sleep_s, retries=0)
        if not xml:
            errors.append(f"sitemap not available: {sm}")
            continue
        pages, kids = parse_sitemap(xml)
        sitemap_urls.extend(pages)
        queue.extend(kids)
    empty = {
        "jobs": [],
        "source_total": None,
        "listing_ids": [],
        "paths": set(),
        "facets": {},
        "robots": robots,
        "sitemap_urls": sitemap_urls,
        "errors": errors,
        "employer_slugs": set(),
    }
    home = fetch(base + "/", sleep_s)
    if not home:
        errors.append("homepage not fetched")
        return empty
    facets = parse_facets(home, base)
    paths = collect_internal_paths(home, base)
    listing, total, pg, seen_ids = [], None, 1, set()
    while pg <= 200:
        url = f"{base}/jobboard/cands/jobresults.asp?pg={pg}"
        if not robots_allows(robots, url):
            errors.append(f"robots.txt disallows {url}")
            break
        page = fetch(url, sleep_s)
        if not page:
            errors.append(f"results page {pg} not fetched")
            break
        paths |= collect_internal_paths(page, base)
        jobs_pg, total = parse_results(page, base)
        new = [j for j in jobs_pg if j["id"] not in seen_ids]
        if not new:
            break
        seen_ids |= {j["id"] for j in new}
        listing.extend(new)
        if total and len(listing) >= total:
            break
        pg += 1
    listing = [j for j in listing if j["url"]]
    out_jobs = []
    for meta in listing[:max_jobs]:
        if not robots_allows(robots, meta["url"]):
            errors.append(f"robots.txt disallows job {meta['id']}")
            continue
        page = fetch(meta["url"], sleep_s)
        if not page:
            errors.append(f"job page {meta['id']} not fetched")
            continue
        paths |= collect_internal_paths(page, base)
        j = parse_job(
            page,
            base,
            meta,
            "Ireland" if key == "ie" else "United Kingdom",
            cfg["currency"],
        )
        out_jobs.append(snapshot_record(j, page, key, fetched_at))
    emp_slugs = {slugify(j["employer_url"]) for j in out_jobs if j.get("employer_url")}
    return {
        **empty,
        "jobs": out_jobs,
        "source_total": total,
        "listing_ids": [j["id"] for j in listing],
        "paths": paths,
        "facets": facets,
        "employer_slugs": emp_slugs,
    }


def snapshot_stats(jobs: list) -> dict:
    modes, feeds, hosts = {}, {}, {}
    for j in jobs:
        modes[j["apply"]["mode"]] = modes.get(j["apply"]["mode"], 0) + 1
        v = j["feed"]["feed_vendor"] or "none"
        feeds[v] = feeds.get(v, 0) + 1
        if j["apply"]["link_host"]:
            hosts[j["apply"]["link_host"]] = hosts.get(j["apply"]["link_host"], 0) + 1
    return {
        "jobs": len(jobs),
        "apply_modes": modes,
        "feed_vendor_hits": feeds,
        "link_hosts": dict(sorted(hosts.items(), key=lambda kv: -kv[1])),
    }


def redirect_map_from_data(k: str, data_dir: str) -> dict:
    """Offline: redirect map for site k from an earlier {k}.json snapshot (patterns from its jobs, facets, employers)."""
    with open(os.path.join(data_dir, f"{k}.json"), encoding="utf-8") as fh:
        d = json.load(fh)
    paths = {"/", "/jobboard/cands/jobresults.asp?pg=1", "/company-az/"} | {
        "/" + p.lstrip("/") for p in INFO_PAGES
    }
    paths |= {f"/jobs/{j['id']}/{j['slug']}.asp" for j in d["jobs"]}
    for key in ("sectors", "categories", "regions", "locations", "job_types"):
        paths |= {
            "/browse-jobs/" + i["slug"] + "/" for i in d.get(key, []) if i.get("slug")
        }
    slugs = {slugify(e["url"]) for e in d.get("employers", []) if e.get("url")}
    paths |= {"/browse-jobs/" + s + "/" for s in slugs}
    facets = {
        "sector": d.get("sectors", []),
        "job category": d.get("categories", []),
        "region": d.get("regions", []),
        "location": d.get("locations", []),
        "job type": d.get("job_types", []),
    }
    return build_redirect_map(
        k,
        paths,
        {j["id"] for j in d["jobs"]},
        facets,
        slugs,
        f"derived from the {d.get('fetched')} snapshot in {data_dir}; NOT a live crawl",
    )


def run_snapshot(
    out_dir: str,
    sites: list,
    sleep_s: float,
    max_jobs: int,
    dry_run: bool,
    from_data: str | None = None,
) -> int:
    """--snapshot driver. dry_run prints the plan and makes no request. from_data=DIR builds only the
    redirect map from an earlier {site}.json snapshot (offline). Writes JSON only (never CSV).
    """
    global UA
    fetched_at = time.strftime("%Y-%m-%d")
    sleep_s = max(sleep_s, SNAPSHOT_MIN_SLEEP)
    if dry_run:
        for k in sites:
            LOG.info(
                "DRY RUN %s: would fetch robots.txt, sitemap, homepage, results pages 1..N, every job page "
                "at <= %.1f req/s with UA %r; writing nothing",
                k,
                1 / sleep_s,
                SNAPSHOT_UA,
            )
        return 0
    os.makedirs(out_dir, exist_ok=True)
    if from_data:
        rm = {k: redirect_map_from_data(k, from_data) for k in sites}
        write_json_atomic(
            os.path.join(out_dir, "redirect_map.json"),
            {"generated": fetched_at, "sites": rm},
        )
        return 0
    UA = SNAPSHOT_UA
    results, rc = {}, 0
    for k in sites:
        r = snapshot_crawl(k, sleep_s, max_jobs, fetched_at)
        results[k] = r
        if not r["jobs"]:
            rc = 3
        write_json_atomic(
            os.path.join(out_dir, f"jobs_{k}.json"),
            {
                "site": SITES[k]["site"],
                "fetched_at": fetched_at,
                "ua": SNAPSHOT_UA,
                "source_total": r["source_total"],
                "listing_ids": len(r["listing_ids"]),
                "parsed": len(r["jobs"]),
                "errors": r["errors"],
                "stats": snapshot_stats(r["jobs"]),
                "jobs": r["jobs"],
            },
        )
    write_json_atomic(
        os.path.join(out_dir, "employers.json"),
        {
            "generated": fetched_at,
            **aggregate_employers({k: results[k]["jobs"] for k in sites}),
        },
    )
    rm = {}
    for k in sites:
        r = results[k]
        paths = set(r["paths"]) | {
            urllib.parse.urlparse(u).path for u in r["sitemap_urls"]
        }
        rm[k] = build_redirect_map(
            k,
            paths,
            {j["id"] for j in r["jobs"]},
            r["facets"],
            r["employer_slugs"],
            f"live crawl {fetched_at}",
        )
        rm[k]["sitemap_urls"] = len(r["sitemap_urls"])
    write_json_atomic(
        os.path.join(out_dir, "redirect_map.json"),
        {"generated": fetched_at, "sites": rm},
    )
    return rc
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--site", choices=["ie", "uk", "both"], default="both")
    ap.add_argument("--max-jobs", type=int, default=400)
    ap.add_argument("--out", default="deliverables/greenjobs_redesign_2026-09-22/src/data")
    ap.add_argument("--assets", default=None, help="logo folder; omit to skip downloads")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--sleep", type=float, default=0.3)
    ap.add_argument("--clients-only", action="store_true", help="refresh only the /for-employers.asp client-logo wall (needs --assets)")
    ap.add_argument("--snapshot", action="store_true", help="public live-board snapshot (jobs, apply modes, feed markers, redirect map) into --snapshot-out")
    ap.add_argument("--snapshot-out", default="deliverables/greenjobs_migration_2026-11-06/build/live_snapshot_2026-11-20")
    ap.add_argument("--dry-run", action="store_true", help="with --snapshot: print the plan, make no request, write nothing")
    ap.add_argument("--snapshot-from-data", default=None, help="with --snapshot: build only redirect_map.json from an earlier {site}.json snapshot dir (offline)")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if a.snapshot:
        return run_snapshot(a.snapshot_out, ["ie", "uk"] if a.site == "both" else [a.site], a.sleep, a.max_jobs, a.dry_run, a.snapshot_from_data)
    os.makedirs(a.out, exist_ok=True)
    rc = 0
    if a.clients_only:
        if not a.assets:
            ap.error("--clients-only needs --assets")
        for key in (["ie", "uk"] if a.site == "both" else [a.site]):
            n = len(refresh_clients(key, a.assets, max(a.sleep, 0.3), a.out))
            LOG.info("%s clients: %d", key, n)
            rc = rc or (0 if n else 3)
        return rc
    for key in (["ie", "uk"] if a.site == "both" else [a.site]):
        d = crawl_site(key, a.max_jobs, min(a.concurrency, 4), max(a.sleep, 0.3), a.out, a.assets)
        LOG.info("%s done: %s", key, d["stats"])
        if d["stats"].get("rejected"):
            rc = 3  # below the snapshot floor: nothing was written for this site; with --site both one rejected site fails the whole run
    if rc:
        LOG.error("run rejected: at least one site fell below its snapshot floor (exit %d)", rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())
