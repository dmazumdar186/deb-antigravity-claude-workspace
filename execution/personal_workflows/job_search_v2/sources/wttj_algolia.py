"""
description: Welcome to the Jungle (WTTJ) source adapter using their public Algolia
    search backend. Replaces the broken Playwright-based wttj.py (consent-gate
    blocked, __NEXT_DATA__ moved). No browser, no consent dance — same backend
    WTTJ's own SPA calls.
inputs:
  - CLI: --keywords, --country-code (default FR), --max-pages, --posted-within-hours, --fixture
  - env: none (public referer-gated Algolia credentials are baked in below)
outputs:
  - stdout: JSON-lines of SourceJob records
  - .tmp/job_search_v2/wttj_algolia_<run_id>.jsonl (when run standalone)

Architecture cribbed (MIT) from sivad259-alt/job-scanner:
    https://github.com/sivad259-alt/job-scanner — jobscanner/wttj_jobs/

The Algolia application id + search-only API key below are the PUBLIC,
referer-restricted credentials WTTJ serves to every anonymous browser load.
They are NOT account secrets. If WTTJ rotates them (rare), re-harvest from a
live page load: open the jobs page, watch a request to *-dsn.algolia.net, copy
the x-algolia-api-key header.

Why this exists: the prior `wttj.py` (Playwright) is permanently DARK because
WTTJ's page wraps results behind a Didomi cookie-consent modal that headless
goto cannot dismiss, AND the page moved its hydration off of __NEXT_DATA__.
Hitting Algolia directly bypasses both problems — the search backend doesn't
care about consent modals.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html as html_lib
import json
import logging
import random
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv

_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR.parent.parent.parent))

from execution.personal_workflows.job_search_v2.contracts import JobSource, SourceJob  # noqa: E402

load_dotenv()
logger = logging.getLogger("wttj_algolia")

PROJECT_ROOT = Path(__file__).resolve().parents[4]
TMP_DIR = PROJECT_ROOT / ".tmp" / "job_search_v2"

# --- Public Algolia credentials (referer-gated, NOT secrets) -------------
ALGOLIA_APP_ID = "CSEKHVMS53"
ALGOLIA_API_KEY = "4bd8f6215d0cc52b26430765769e65a0"
ALGOLIA_INDEX = "wk_cms_jobs_production_published_at_desc"  # sorted by recency desc
ALGOLIA_QUERY_URL = f"https://{ALGOLIA_APP_ID.lower()}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX}/query"

JOB_PAGE_URL_FMT = "https://www.welcometothejungle.com/en/companies/{org}/jobs/{slug}"
DEFAULT_COUNTRY = "FR"

DEFAULT_KEYWORDS = [
    "product manager",
    "senior product manager",
    "lead product manager",
    "head of product",
    "chef de produit",
    "AI product manager",
    "product owner",
]

DEFAULT_POSTED_WITHIN_HOURS = 48
HITS_PER_PAGE = 100
DEFAULT_MAX_PAGES = 3  # 300 hits/keyword is plenty given the 48h recency floor
RETRIES = 3
BACKOFF_BASE = 1.0
SEARCH_DELAY_MIN = 0.5
SEARCH_DELAY_MAX = 1.0
TIMEOUT = 20

HEADERS = {
    "X-Algolia-Application-Id": ALGOLIA_APP_ID,
    "X-Algolia-API-Key": ALGOLIA_API_KEY,
    "Content-Type": "application/json",
    # Referer is REQUIRED — the search key is referer-restricted, 403 without it.
    "Referer": "https://www.welcometothejungle.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v]+")


class WttjAlgoliaBlockedError(RuntimeError):
    """Raised on Algolia 403 (key/referer rotated)."""


def _strip_html(s: Optional[str]) -> str:
    if not s:
        return ""
    text = _TAG_RE.sub(" ", s)
    text = html_lib.unescape(text)
    text = _WS_RE.sub(" ", text)
    return text.strip()


def _parse_iso(s: str) -> datetime | None:
    if not s:
        return None
    s = s.strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        m = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.\d+)?(.*)", s)
        if not m:
            return None
        try:
            d = datetime.fromisoformat(m.group(1) + (m.group(2) or ""))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def _age_hours(published_at: str) -> float | None:
    d = _parse_iso(published_at)
    if d is None:
        return None
    return (datetime.now(timezone.utc) - d).total_seconds() / 3600.0


def _hit_to_source_job(hit: dict) -> SourceJob | None:
    try:
        org = hit.get("organization") or {}
        object_id = str(hit.get("objectID", "")).strip()
        if not object_id:
            return None
        title = (hit.get("name") or "").strip()
        company = (org.get("name") or "Unknown").strip()
        if not title or not company:
            return None
        org_slug = org.get("slug") or ""
        slug = hit.get("slug") or ""
        if not org_slug or not slug:
            return None
        url = JOB_PAGE_URL_FMT.format(org=org_slug, slug=slug)

        offices = hit.get("offices") or []
        office = (hit.get("office") or {}) or (offices[0] if offices else {})
        loc_parts = [office.get("city"), office.get("country") or "France"]
        location_raw = ", ".join(p for p in loc_parts if p)

        return SourceJob(
            source=JobSource.WTTJ_ALGOLIA,
            source_id=object_id,
            url=url,
            title=title,
            company=company,
            location_raw=location_raw,
            description_snippet="",  # Algolia hit is metadata-only; ranker uses title+company
            posted_at=_parse_iso(hit.get("published_at") or ""),
            contract_type_raw=(hit.get("contract_type") or "").upper(),
        )
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("wttj_algolia: skip hit (parse error): %s", exc)
        return None


def _search_page(
    client: httpx.Client, keyword: str, page: int, country_code: str
) -> Optional[dict]:
    """POST one Algolia query page. None on transient failure; raises BlockedError on 403."""
    body = json.dumps({
        "query": keyword,
        "hitsPerPage": HITS_PER_PAGE,
        "page": page,
        "facetFilters": [[f"offices.country_code:{country_code}"]],
        "attributesToRetrieve": ["*"],
    })
    for attempt in range(RETRIES):
        try:
            resp = client.post(ALGOLIA_QUERY_URL, content=body, timeout=TIMEOUT)
        except httpx.HTTPError:
            time.sleep(BACKOFF_BASE * (attempt + 1))
            continue
        if resp.status_code == 403:
            raise WttjAlgoliaBlockedError(
                f"Algolia 403 for index {ALGOLIA_INDEX} — referer/key rejected. "
                "The public search key may have rotated; re-harvest from a live page load."
            )
        if resp.status_code == 429:
            time.sleep(BACKOFF_BASE * (attempt + 1))
            continue
        if resp.status_code == 200:
            try:
                return resp.json()
            except ValueError:
                return None
        time.sleep(BACKOFF_BASE * (attempt + 1))
    return None


def fetch(
    keywords: Optional[list[str]] = None,
    country_code: str = DEFAULT_COUNTRY,
    posted_within_hours: int = DEFAULT_POSTED_WITHIN_HOURS,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> list[SourceJob]:
    """Run one Algolia search per keyword (recency-sorted), early-stop on age window.

    Because the index is sorted by published_at desc, once any hit on a page is
    older than the posted_within_hours window, we can stop paging that keyword.
    """
    keywords = keywords or DEFAULT_KEYWORDS
    seen_ids: set[str] = set()
    out: list[SourceJob] = []

    with httpx.Client(headers=HEADERS) as client:
        for kw in keywords:
            for page_idx in range(max_pages):
                try:
                    blob = _search_page(client, kw, page_idx, country_code)
                except WttjAlgoliaBlockedError as exc:
                    logger.error("wttj_algolia: BLOCKED — %s", exc)
                    return out
                if blob is None:
                    break
                hits = blob.get("hits") or []
                if not hits:
                    break
                added = 0
                hit_too_old = False
                for hit in hits:
                    age = _age_hours(hit.get("published_at") or "")
                    if age is not None and age > posted_within_hours:
                        hit_too_old = True
                        # don't break — within a single page there can still be
                        # newer hits if the sort is approximate; just skip this one
                        continue
                    object_id = str(hit.get("objectID", ""))
                    if not object_id or object_id in seen_ids:
                        continue
                    sj = _hit_to_source_job(hit)
                    if sj is None:
                        continue
                    seen_ids.add(object_id)
                    out.append(sj)
                    added += 1
                logger.info(
                    "wttj_algolia: keyword=%r page=%d → %d hits, %d kept (cumul %d)",
                    kw, page_idx, len(hits), added, len(out),
                )
                # Recency-sorted: if we already saw an out-of-window hit on this
                # page, the next page will be entirely out of window — stop.
                if hit_too_old:
                    break
                time.sleep(random.uniform(SEARCH_DELAY_MIN, SEARCH_DELAY_MAX))
    return out


def fetch_from_fixture(fixture_path: Path) -> list[SourceJob]:
    """Offline mode: read a recorded Algolia response JSON.

    Fixture shape: the raw {hits: [...], nbPages, nbHits} dict from one Algolia
    query response. Used by parser tests (NOT front-door — fixture tests live
    under parser_/unit_ names per 2026-06-18 tightening).
    """
    if not fixture_path.exists():
        return []
    blob = json.loads(fixture_path.read_text(encoding="utf-8"))
    hits = blob.get("hits", []) if isinstance(blob, dict) else (blob or [])
    seen_ids: set[str] = set()
    out: list[SourceJob] = []
    for hit in hits:
        object_id = str(hit.get("objectID", ""))
        if not object_id or object_id in seen_ids:
            continue
        sj = _hit_to_source_job(hit)
        if sj is None:
            continue
        seen_ids.add(object_id)
        out.append(sj)
    return out


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="WTTJ public Algolia source adapter.")
    parser.add_argument("--keywords", default="", help="Comma-separated. Empty = use DEFAULT_KEYWORDS.")
    parser.add_argument("--country-code", default=DEFAULT_COUNTRY, help="ISO country code (default FR).")
    parser.add_argument("--posted-within-hours", type=int, default=DEFAULT_POSTED_WITHIN_HOURS)
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    parser.add_argument("--fixture", type=Path, help="Read from a JSON fixture instead of live.")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if args.fixture:
        jobs = fetch_from_fixture(args.fixture)
        logger.info("wttj_algolia: %d jobs from fixture", len(jobs))
    else:
        kw_list = [k.strip() for k in args.keywords.split(",") if k.strip()] or None
        try:
            jobs = fetch(
                keywords=kw_list,
                country_code=args.country_code,
                posted_within_hours=args.posted_within_hours,
                max_pages=args.max_pages,
            )
        except WttjAlgoliaBlockedError as exc:
            logger.error("wttj_algolia: aborted — %s", exc)
            return 1
        logger.info("wttj_algolia: %d jobs from live API", len(jobs))

    out_path = args.out or (TMP_DIR / f"wttj_algolia_{uuid.uuid4().hex[:8]}.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for job in jobs:
            line = job.model_dump_json()
            f.write(line + "\n")
            try:
                sys.stdout.write(line + "\n")
            except UnicodeEncodeError:
                sys.stdout.buffer.write((line + "\n").encode("utf-8", errors="replace"))
    logger.info("wttj_algolia: wrote %d to %s", len(jobs), out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
