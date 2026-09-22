#!/usr/bin/env python3
"""Scrape greenjobs.ie / greenjobs.co.uk into structured JSON for the redesign demo.

description: Polite crawler for the two GreenJobs boards (sjbimg.com job-board
    platform). Collects the facet lists (sectors, categories, regions, job types
    with counts) from the homepage, pages through /jobboard/cands/jobresults.asp,
    fetches every job detail page, parses salary/location/dates/description, and
    captures About / Contact / network / advertising page text. Optionally
    downloads brand and employer logos into an assets folder with a manifest.
inputs: --site ie|uk|both (default both); --max-jobs N (cap per site, default 400);
    --out DIR (data output dir); --assets DIR (logo folder; omit to skip logos);
    --concurrency N (default 4); --sleep S (default 0.3). No secrets required.
outputs: {out}/ie.json, {out}/uk.json (see JOB_FIELDS below), {out}/pages_{site}.json
    (plain text of informational pages for brief writing), {assets}/logos.json
    manifest plus downloaded logo files, {out}/perf_{site}.json (page-weight
    measurements of the homepage: bytes, request counts).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import html
import json
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


SAL_RE_TRAIL = re.compile(
    r"(?P<a>\d[\d,\.]*)\s*(?P<ak>k)?\s*(?P<cur>[£€$])"
    r"(?:\s*(?:-|–|to|and)\s*(?P<b>\d[\d,\.]*)\s*(?P<bk>k)?\s*[£€$])?"
    r"\s*(?P<per>pa|per annum|p\.a\.|per year|pm|per month|ph|per hour|per day|pd|per week|pw)?", re.I)


def parse_salary(text: str | None):
    """Return (min, max, currency, period) from an explicit salary string."""
    if not text:
        return None, None, None, None
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
        home = open(cfg["snapshot"], encoding="utf-8", errors="ignore").read()
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
    with open(os.path.join(out_dir, f"{key}.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, f"pages_{key}.json"), "w", encoding="utf-8") as fh:
        json.dump(pages, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, f"perf_{key}.json"), "w", encoding="utf-8") as fh:
        json.dump(measure_page(home, base), fh, indent=1)
    if assets_dir:
        download_logos(key, home, employers, base, assets_dir, sleep_s)
    return data


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


def download_logos(key: str, home: str, employers: list, base: str, assets_dir: str, sleep_s: float) -> None:
    os.makedirs(assets_dir, exist_ok=True)
    manifest_path = os.path.join(assets_dir, "logos.json")
    manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) else {}
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
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1, ensure_ascii=False)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--site", choices=["ie", "uk", "both"], default="both")
    ap.add_argument("--max-jobs", type=int, default=400)
    ap.add_argument("--out", default="deliverables/greenjobs_redesign_2026-09-22/src/data")
    ap.add_argument("--assets", default=None, help="logo folder; omit to skip downloads")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--sleep", type=float, default=0.3)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    os.makedirs(a.out, exist_ok=True)
    for key in (["ie", "uk"] if a.site == "both" else [a.site]):
        d = crawl_site(key, a.max_jobs, min(a.concurrency, 4), max(a.sleep, 0.3), a.out, a.assets)
        LOG.info("%s done: %s", key, d["stats"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
