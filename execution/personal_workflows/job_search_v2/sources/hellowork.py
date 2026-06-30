"""
description: Hellowork source adapter using the public web search + per-job
    schema.org JSON-LD JobPosting extraction. No auth, no scraping the
    SPA — Hellowork's job-detail pages embed the full posting as a
    standards-compliant <script type="application/ld+json"> blob which
    every job page reliably carries (5/5 in probe runs, 4-6k char
    descriptions). Replaces the prior Gmail-alert-based hellowork_gmail
    flow which never worked in production.

    Pipeline:
      1. GET /fr-fr/emploi/recherche.html?k=<keyword>&l=<location>&p=<page>
      2. Extract unique offer IDs via regex on '/fr-fr/emplois/(\\d+)\\.html'
      3. For each offer ID, GET the offer page in parallel (4 workers)
      4. Parse the JobPosting JSON-LD blob (title, hiringOrganization,
         jobLocation, employmentType, datePosted, description)
      5. Emit SourceJob

inputs:
  - CLI: --keywords (comma-separated), --locations (comma-separated; default
    "paris"), --max-pages-per-keyword, --posted-within-hours, --fixture
  - env: none

outputs:
  - stdout: JSON-lines of SourceJob records
  - .tmp/job_search_v2/hellowork_<run_id>.jsonl (when run standalone)
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from dotenv import find_dotenv, load_dotenv

_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR.parent.parent.parent))

from execution.personal_workflows.job_search_v2.contracts import (  # noqa: E402
    JobSource, SourceJob,
)

load_dotenv(find_dotenv(usecwd=False))
logger = logging.getLogger("hellowork")

PROJECT_ROOT = Path(__file__).resolve().parents[4]
TMP_DIR = PROJECT_ROOT / ".tmp" / "job_search_v2"

SEARCH_URL = "https://www.hellowork.com/fr-fr/emploi/recherche.html"
DETAIL_URL_FMT = "https://www.hellowork.com/fr-fr/emplois/{job_id}.html"

# Keyword set matches the operator's tracks. EN + FR only — matches the
# 2026-06-24 hard constraint set by WTTJ + LinkedIn sources.
DEFAULT_KEYWORDS = [
    # --- Track A: Permanent AI PM ---
    "AI product manager",
    "senior product manager",
    "lead product manager",
    "head of product",
    "GenAI product manager",
    "product manager",
    "chef de produit",
    "responsable produit",
    # --- Track B: Freelance AI Automation / Builder ---
    "AI automation",
    "AI consultant",
    "AI engineer",
    "consultant IA",
    "automatisation IA",
    "claude code",
]

# Locations — Hellowork's location filter is a free-text field that takes
# either city or region. Paris covers the Paris+50km zone per Hellowork's
# default radius (25km), and "ile-de-france" widens it to the IDF region.
DEFAULT_LOCATIONS = ["paris", "ile-de-france"]

DEFAULT_POSTED_WITHIN_HOURS = 48
DEFAULT_MAX_PAGES_PER_KEYWORD = 3
# Anti-bot tightening 2026-06-30: first prod run (28441297021) detected our
# 4-worker enrichment pattern and 403'd partway through. Reducing to 2
# workers + doubling per-req sleep produces a gentler crawl that should
# stay under Hellowork's threshold for our daily volume (~50 jobs/run).
DETAIL_MAX_WORKERS = 2
DETAIL_TIMEOUT = 20.0
DETAIL_RETRIES = 2
DETAIL_PER_REQ_SLEEP = (0.5, 1.0)
SEARCH_DELAY_MIN = 0.7
SEARCH_DELAY_MAX = 1.4
SEARCH_TIMEOUT = 20.0
BACKOFF_BASE = 1.0
DESC_MAX_CHARS = 2000

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

OFFER_ID_RE = re.compile(r"/fr-fr/emplois/(\d+)\.html")
LD_JSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
    re.DOTALL,
)
WS_RE = re.compile(r"\s+")
TAG_RE = re.compile(r"<[^>]+>")


class HelloworkBlockedError(RuntimeError):
    """Raised when Hellowork returns a 403 / captcha / WAF block."""


def _strip_html(s: Optional[str]) -> str:
    if not s:
        return ""
    text = TAG_RE.sub(" ", s)
    # Hellowork JSON-LD `description` uses HTML entities for accented chars
    # and embedded markup. Decode entities + collapse whitespace.
    try:
        import html as html_lib
        text = html_lib.unescape(text)
    except ImportError:  # pragma: no cover — stdlib, always present
        pass
    return WS_RE.sub(" ", text).strip()


def _parse_iso(s: str) -> datetime | None:
    if not s:
        return None
    s = s.strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except ValueError:
        return None


def _search_page(
    client: httpx.Client,
    keyword: str,
    location: str,
    page: int,
) -> Optional[str]:
    """Fetch one search-results page. Returns HTML or None on transient
    failure. Raises HelloworkBlockedError on 403 / captcha."""
    params = {"k": keyword, "l": location, "p": str(page)}
    for attempt in range(3):
        try:
            resp = client.get(
                SEARCH_URL, params=params, timeout=SEARCH_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            if attempt == 2:
                logger.warning(
                    "hellowork: search transient failure (%s) keyword=%r loc=%r p=%d",
                    exc, keyword, location, page,
                )
                return None
            time.sleep(BACKOFF_BASE * (attempt + 1))
            continue
        if resp.status_code == 403:
            raise HelloworkBlockedError(
                f"hellowork search 403 — keyword={keyword!r} loc={location!r}"
            )
        if resp.status_code in (429, 503):
            time.sleep(BACKOFF_BASE * (attempt + 1) * 2)
            continue
        if resp.status_code != 200 or len(resp.text) < 1000:
            return None
        return resp.text
    return None


def _extract_offer_ids(html: str) -> list[str]:
    """Pull all offer IDs out of a search-results page. The same id can
    appear multiple times (premium + regular slots); de-dup preserving
    discovery order."""
    seen: set[str] = set()
    out: list[str] = []
    for jid in OFFER_ID_RE.findall(html or ""):
        if jid not in seen:
            seen.add(jid)
            out.append(jid)
    return out


def _parse_job_posting_ld(html: str) -> dict | None:
    """Find the schema.org JobPosting JSON-LD blob on a job page. Pages have
    multiple ld+json blocks (WebSite, BreadcrumbList, ...); pick the
    JobPosting one. Returns parsed dict or None."""
    if not html:
        return None
    for blob in LD_JSON_RE.findall(html):
        try:
            d = json.loads(blob)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and d.get("@type") == "JobPosting":
            return d
        # Sometimes wrapped in @graph
        if isinstance(d, dict) and isinstance(d.get("@graph"), list):
            for node in d["@graph"]:
                if isinstance(node, dict) and node.get("@type") == "JobPosting":
                    return node
    return None


def _ld_to_source_job(job_id: str, ld: dict) -> SourceJob | None:
    """Map a schema.org JobPosting dict → SourceJob. Returns None on the
    minimum-fields check (title / company missing)."""
    try:
        title = (ld.get("title") or "").strip()
        hiring = ld.get("hiringOrganization") or {}
        company = ((hiring.get("name") if isinstance(hiring, dict) else "") or "").strip()
        if not title or not company:
            return None
        # jobLocation may be a list or a single dict
        loc = ld.get("jobLocation")
        if isinstance(loc, list):
            loc = loc[0] if loc else {}
        if not isinstance(loc, dict):
            loc = {}
        addr = loc.get("address") if isinstance(loc.get("address"), dict) else {}
        city = (addr.get("addressLocality") or "").strip()
        region = (addr.get("addressRegion") or "").strip()
        country = (addr.get("addressCountry") or "").strip()
        location_raw = ", ".join(p for p in (city, region, country) if p)

        description = _strip_html(ld.get("description") or "")[:DESC_MAX_CHARS]
        emp_type_raw = ld.get("employmentType") or ""
        if isinstance(emp_type_raw, list):
            emp_type_raw = emp_type_raw[0] if emp_type_raw else ""
        contract_type_raw = str(emp_type_raw).strip().upper()
        posted_at = _parse_iso(ld.get("datePosted") or "")

        return SourceJob(
            source=JobSource.HELLOWORK,
            source_id=job_id,
            url=DETAIL_URL_FMT.format(job_id=job_id),
            title=title,
            company=company,
            location_raw=location_raw,
            description_snippet=description,
            posted_at=posted_at,
            contract_type_raw=contract_type_raw,
        )
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("hellowork: ld→SourceJob failed for %s: %s", job_id, exc)
        return None


def _fetch_job_detail(client: httpx.Client, job_id: str) -> Optional[SourceJob]:
    """Fetch one job page and convert. Soft-fails on transient errors —
    returns None so the caller's row is just skipped, not raised."""
    url = DETAIL_URL_FMT.format(job_id=job_id)
    for attempt in range(DETAIL_RETRIES + 1):
        try:
            resp = client.get(url, timeout=DETAIL_TIMEOUT)
        except httpx.HTTPError as exc:
            if attempt == DETAIL_RETRIES:
                logger.debug("hellowork detail %s: %s — soft-fail", job_id, exc)
                return None
            time.sleep(BACKOFF_BASE * (attempt + 1))
            continue
        if resp.status_code == 403:
            raise HelloworkBlockedError(
                f"hellowork detail 403 — job_id={job_id}"
            )
        if resp.status_code in (429, 503):
            time.sleep(BACKOFF_BASE * (attempt + 1) * 2)
            continue
        if resp.status_code != 200 or len(resp.text) < 1000:
            return None
        ld = _parse_job_posting_ld(resp.text)
        if ld is None:
            return None
        return _ld_to_source_job(job_id, ld)
    return None


def _enrich_in_parallel(
    client: httpx.Client, job_ids: list[str], *,
    max_workers: int = DETAIL_MAX_WORKERS,
) -> list[SourceJob]:
    """Fetch detail for every id in parallel. Stops on HelloworkBlockedError.
    Returns SourceJobs that succeeded (may be shorter than input on partial
    failures)."""
    if not job_ids:
        return []
    out: list[SourceJob] = []
    blocked = False
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_fetch_job_detail, client, jid): jid for jid in job_ids}
        for fut in as_completed(futures):
            jid = futures[fut]
            try:
                sj = fut.result()
            except HelloworkBlockedError:
                blocked = True
                logger.warning("hellowork: blocked during detail enrichment — stopping early")
                break
            except Exception as exc:  # noqa: BLE001 — per-job soft-fail
                logger.debug("hellowork detail %s: %s — soft-fail", jid, exc)
                continue
            if sj is not None:
                out.append(sj)
            time.sleep(random.uniform(*DETAIL_PER_REQ_SLEEP))
    if blocked:
        logger.warning("hellowork: partial detail set retained (%d/%d).",
                       len(out), len(job_ids))
    return out


def fetch(
    keywords: Optional[list[str]] = None,
    locations: Optional[list[str]] = None,
    max_pages_per_keyword: int = DEFAULT_MAX_PAGES_PER_KEYWORD,
    posted_within_hours: int = DEFAULT_POSTED_WITHIN_HOURS,
) -> list[SourceJob]:
    """Search-and-enrich loop. Returns deduped SourceJobs across all
    keyword × location combinations.

    posted_within_hours is enforced post-fetch via the posted_at field on
    each SourceJob — Hellowork's UI offers a 24h/7d filter but the URL
    param is undocumented; we just filter what comes back.
    """
    keywords = keywords or DEFAULT_KEYWORDS
    locations = locations or DEFAULT_LOCATIONS
    seen_ids: set[str] = set()

    with httpx.Client(headers=HEADERS) as client:
        # Phase 1: search across (keyword × location × page) to collect IDs
        for kw in keywords:
            for loc in locations:
                for page in range(1, max_pages_per_keyword + 1):
                    try:
                        html = _search_page(client, kw, loc, page)
                    except HelloworkBlockedError as exc:
                        logger.error("hellowork: search blocked — %s", exc)
                        return _finalize_by_age(
                            _enrich_in_parallel(client, list(seen_ids)),
                            posted_within_hours,
                        )
                    if html is None:
                        break
                    page_ids = _extract_offer_ids(html)
                    new_ids = [i for i in page_ids if i not in seen_ids]
                    seen_ids.update(new_ids)
                    logger.info(
                        "hellowork: search kw=%r loc=%r page=%d → %d hits, %d new",
                        kw, loc, page, len(page_ids), len(new_ids),
                    )
                    if not new_ids:
                        # No new IDs after dedup — assume we've hit the
                        # tail of relevant results for this query.
                        break
                    time.sleep(random.uniform(SEARCH_DELAY_MIN, SEARCH_DELAY_MAX))

        if not seen_ids:
            return []

        # Phase 2: parallel detail fetch
        logger.info("hellowork: detail enrichment for %d unique ids", len(seen_ids))
        try:
            jobs = _enrich_in_parallel(client, list(seen_ids))
        except HelloworkBlockedError as exc:
            logger.error("hellowork: detail blocked — %s", exc)
            return []

    return _finalize_by_age(jobs, posted_within_hours)


def _finalize_by_age(
    jobs: list[SourceJob], posted_within_hours: int,
) -> list[SourceJob]:
    """Filter to jobs posted within the time window. Jobs with no posted_at
    are kept (better recall than dropping them silently)."""
    if posted_within_hours <= 0:
        return jobs
    now = datetime.now(timezone.utc)
    cutoff = now.timestamp() - posted_within_hours * 3600
    out: list[SourceJob] = []
    for sj in jobs:
        if sj.posted_at is None:
            out.append(sj)
            continue
        if sj.posted_at.timestamp() >= cutoff:
            out.append(sj)
    return out


def fetch_from_fixture(fixture_path: Path) -> list[SourceJob]:
    """Offline mode: parse a recorded job-page HTML (one job per file).
    Used by the parser test. Loose contract: filename must be the job_id."""
    if not fixture_path.exists():
        return []
    job_id = fixture_path.stem  # filename without extension
    html = fixture_path.read_text(encoding="utf-8")
    ld = _parse_job_posting_ld(html)
    if ld is None:
        return []
    sj = _ld_to_source_job(job_id, ld)
    return [sj] if sj else []


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    parser = argparse.ArgumentParser(description="Hellowork public search source.")
    parser.add_argument("--keywords", default="",
                        help="Comma-separated keyword list. Empty = use defaults.")
    parser.add_argument("--locations", default="",
                        help="Comma-separated locations. Empty = use defaults.")
    parser.add_argument("--max-pages-per-keyword", type=int,
                        default=DEFAULT_MAX_PAGES_PER_KEYWORD)
    parser.add_argument("--posted-within-hours", type=int,
                        default=DEFAULT_POSTED_WITHIN_HOURS)
    parser.add_argument("--fixture", type=Path,
                        help="Read from a JSON-LD-bearing HTML fixture instead of live.")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if args.fixture:
        jobs = fetch_from_fixture(args.fixture)
        logger.info("hellowork: %d jobs from fixture", len(jobs))
    else:
        kw_list = [k.strip() for k in args.keywords.split(",") if k.strip()] or None
        loc_list = [l.strip() for l in args.locations.split(",") if l.strip()] or None
        try:
            jobs = fetch(
                keywords=kw_list,
                locations=loc_list,
                max_pages_per_keyword=args.max_pages_per_keyword,
                posted_within_hours=args.posted_within_hours,
            )
        except HelloworkBlockedError as exc:
            logger.error("hellowork: aborted — %s", exc)
            return 1
        logger.info("hellowork: %d jobs from live API", len(jobs))

    out_path = args.out or (TMP_DIR / f"hellowork_{uuid.uuid4().hex[:8]}.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for job in jobs:
            line = job.model_dump_json()
            f.write(line + "\n")
            try:
                sys.stdout.write(line + "\n")
            except UnicodeEncodeError:
                sys.stdout.buffer.write((line + "\n").encode("utf-8", errors="replace"))
    logger.info("hellowork: wrote %d to %s", len(jobs), out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
