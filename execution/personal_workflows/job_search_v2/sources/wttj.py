"""
description: Welcome to the Jungle (WTTJ) source adapter — parses the public job-list
    page for Paris PM roles. WTTJ is a Next.js SPA, but the page serialises job data
    into a <script id="__NEXT_DATA__"> JSON blob — we extract from there first (cheap)
    and only fall back to Playwright if that path returns zero jobs. No login required.
    Polite throttle: 3 s between page fetches; max 3 pages.

inputs:
    - CLI: --query (default: "product manager"), --location (default: "Paris, France")
    - CLI: --max-pages (default: 3), --senior-only (default: True)
    - CLI: --fixture PATH (offline mode — parse a recorded HTML file)
    - CLI: --out PATH (output JSONL; defaults to .tmp/job_search_v2/wttj_<run_id>.jsonl)
    - No env / credentials — WTTJ public search is unauthenticated.

outputs:
    - stdout: JSON-lines of SourceJob records (one per line)
    - .tmp/job_search_v2/wttj_<run_id>.jsonl

Anti-bot posture (June 2026): WTTJ's public search is unauthenticated; httpx with a
realistic User-Agent works. They do have Cloudflare but rate-limit thresholds are
generous for honest traffic. The polite 3s throttle plus a real UA string is enough.

If WTTJ ever blocks the cheap httpx path, the Playwright fallback hydrates the SPA
properly. Playwright is imported lazily inside a try/except ImportError so this module
remains importable even when Playwright isn't installed.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv, find_dotenv

_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR.parent.parent.parent))

from execution.personal_workflows.job_search_v2.contracts import JobSource, SourceJob  # noqa: E402

load_dotenv(find_dotenv(usecwd=False))
logger = logging.getLogger("wttj")

PROJECT_ROOT = Path(__file__).resolve().parents[4]
TMP_DIR = PROJECT_ROOT / ".tmp" / "job_search_v2"

SEARCH_URL = "https://www.welcometothejungle.com/en/jobs"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# Extract the __NEXT_DATA__ JSON blob from a WTTJ page. Used by both live and fixture paths.
_NEXT_DATA_RE = re.compile(
    r'<script\s+id="__NEXT_DATA__"\s+type="application/json"[^>]*>(.*?)</script>',
    re.DOTALL,
)


def _parse_next_data(html: str) -> list[SourceJob]:
    """Pull <script id="__NEXT_DATA__"> JSON out of HTML and walk to the jobs array.

    The Next.js data path varies between WTTJ deploys; we probe a few plausible paths
    and pick the first one that yields a non-empty list of dicts with 'title' + 'slug'.
    """
    m = _NEXT_DATA_RE.search(html)
    if not m:
        logger.info("wttj: no __NEXT_DATA__ blob found in HTML")
        return []
    try:
        blob = json.loads(m.group(1))
    except json.JSONDecodeError as exc:
        logger.warning("wttj: __NEXT_DATA__ JSON parse failed: %s", exc)
        return []

    # Probe known-ish paths for the jobs list. If WTTJ changes again, extend this list.
    candidate_paths = [
        ("props", "pageProps", "searchResults", "jobs"),
        ("props", "pageProps", "jobs"),
        ("props", "pageProps", "initialData", "jobs"),
        ("props", "pageProps", "results"),
        ("props", "pageProps", "hits"),
    ]
    raw_jobs: list[dict] = []
    for path in candidate_paths:
        node = blob
        ok = True
        for key in path:
            if isinstance(node, dict) and key in node:
                node = node[key]
            else:
                ok = False
                break
        if ok and isinstance(node, list) and node and isinstance(node[0], dict):
            raw_jobs = node
            logger.info("wttj: __NEXT_DATA__ matched path %s (%d items)", ".".join(path), len(raw_jobs))
            break

    return [j for j in (_to_sourcejob(rj) for rj in raw_jobs) if j is not None]


def _to_sourcejob(raw: dict) -> SourceJob | None:
    """Map one WTTJ job dict (from __NEXT_DATA__) to SourceJob.

    The shape is best-effort — WTTJ's keys have shifted historically. We accept a
    handful of common aliases; if none of them yield a usable title+url, we skip.
    """
    try:
        title = raw.get("name") or raw.get("title") or ""
        slug = raw.get("slug") or raw.get("id") or raw.get("reference") or ""
        if not title or not slug:
            return None

        # Company info
        org = raw.get("organization") or raw.get("company") or {}
        if isinstance(org, dict):
            company = org.get("name") or org.get("displayName") or "Unknown"
            company_slug = org.get("slug") or ""
        else:
            company = str(org) or "Unknown"
            company_slug = ""

        # URL — WTTJ public URL shape:
        url = raw.get("url") or raw.get("permalink")
        if not url:
            if company_slug:
                url = f"https://www.welcometothejungle.com/en/companies/{company_slug}/jobs/{slug}"
            else:
                url = f"https://www.welcometothejungle.com/en/jobs/{slug}"

        # Location — WTTJ uses nested office objects
        offices = raw.get("offices") or raw.get("locations") or []
        if isinstance(offices, list) and offices:
            first = offices[0]
            if isinstance(first, dict):
                loc_raw = first.get("city") or first.get("name") or first.get("displayName") or ""
                country = first.get("country") or ""
                if loc_raw and country and country.lower() not in loc_raw.lower():
                    loc_raw = f"{loc_raw}, {country}"
            else:
                loc_raw = str(first)
        else:
            loc_raw = raw.get("locationName") or ""

        description = raw.get("description") or raw.get("profile") or raw.get("missions") or ""
        description = description[:400] if isinstance(description, str) else ""

        # Contract type — WTTJ tag is often "FULL_TIME" / "INTERNSHIP" / "FREELANCE"
        contract = raw.get("contractType") or raw.get("contract_type") or raw.get("employmentType") or ""

        # Posted at
        posted_str = raw.get("publishedAt") or raw.get("publicationDate") or raw.get("createdAt") or ""
        posted_at = None
        if posted_str:
            try:
                posted_at = datetime.fromisoformat(posted_str.replace("Z", "+00:00"))
            except ValueError:
                posted_at = None

        return SourceJob(
            source=JobSource.WTTJ,
            source_id=str(slug),
            url=url,
            title=title,
            company=company,
            location_raw=str(loc_raw),
            description_snippet=description,
            posted_at=posted_at,
            contract_type_raw=str(contract),
        )
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("wttj: skip job (parse error): %s", exc)
        return None


def _try_playwright(search_url: str, query_params: dict, max_pages: int) -> list[SourceJob]:
    """Fallback path when __NEXT_DATA__ is empty. Renders the SPA and re-parses.

    Playwright is imported lazily — if the package isn't installed, we return [].
    """
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        logger.warning("wttj: playwright not installed — skipping render fallback. Run `pip install playwright && playwright install chromium` to enable.")
        return []

    all_jobs: list[SourceJob] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=UA, locale="en-US")
            page = context.new_page()
            for page_num in range(1, max_pages + 1):
                params = {**query_params, "page": page_num}
                qs = "&".join(f"{k}={httpx.URL('').copy_set_param(k, str(v)).query.decode()}" for k, v in params.items())
                # Simpler: build via httpx URL
                url = str(httpx.URL(search_url).copy_merge_params(params))
                logger.info("wttj: playwright loading page %d (%s)", page_num, url)
                page.goto(url, wait_until="networkidle", timeout=20000)
                html = page.content()
                jobs = _parse_next_data(html)
                if not jobs:
                    logger.info("wttj: playwright page %d yielded 0 jobs — end of results", page_num)
                    break
                all_jobs.extend(jobs)
                time.sleep(3.0)
            browser.close()
    except Exception as exc:  # noqa: BLE001 — playwright surface is broad; log + degrade
        logger.warning("wttj: playwright fallback errored: %s", exc)
    return all_jobs


def fetch(
    query: str = "product manager",
    location: str = "Paris, France",
    max_pages: int = 3,
    polite_delay_s: float = 3.0,
    senior_only: bool = True,
) -> list[SourceJob]:
    """Public search → list[SourceJob]. Cheap path first, Playwright fallback."""
    params_base = {
        "query": query,
        "aroundQuery": location,
    }
    if senior_only:
        params_base["refinementList[experience_level_minimum][0]"] = "senior"

    all_jobs: list[SourceJob] = []
    headers = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.8,fr;q=0.6"}

    with httpx.Client(timeout=20.0, follow_redirects=True, headers=headers) as client:
        for page_num in range(1, max_pages + 1):
            params = {**params_base, "page": page_num}
            try:
                r = client.get(SEARCH_URL, params=params)
            except httpx.HTTPError as exc:
                logger.warning("wttj: HTTP error on page %d: %s — stopping", page_num, exc)
                break
            if r.status_code in (403, 429):
                logger.warning("wttj: %d on page %d — likely rate-limited; stopping with %d so far", r.status_code, page_num, len(all_jobs))
                break
            if r.status_code != 200:
                logger.warning("wttj: HTTP %d on page %d — stopping", r.status_code, page_num)
                break

            page_jobs = _parse_next_data(r.text)
            if not page_jobs:
                logger.info("wttj: page %d returned 0 jobs via __NEXT_DATA__ — end of results (or SPA-only)", page_num)
                break
            all_jobs.extend(page_jobs)
            time.sleep(polite_delay_s)

    if not all_jobs:
        # Try the SPA-rendered fallback. May still return [] if Playwright isn't installed.
        logger.info("wttj: cheap path yielded 0 — trying Playwright fallback")
        all_jobs = _try_playwright(SEARCH_URL, params_base, max_pages)

    return all_jobs


def fetch_from_fixture(fixture_path: Path) -> list[SourceJob]:
    """Offline mode: read a recorded HTML page and run the __NEXT_DATA__ parser on it."""
    html = fixture_path.read_text(encoding="utf-8")
    return _parse_next_data(html)


def _write_jsonl(jobs: list[SourceJob], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for job in jobs:
            f.write(job.model_dump_json() + "\n")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Welcome to the Jungle source adapter.")
    parser.add_argument("--query", default="product manager")
    parser.add_argument("--location", default="Paris, France")
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--no-senior", action="store_true", help="Drop the senior_only filter.")
    parser.add_argument("--fixture", type=Path, help="Read from HTML fixture instead of live (offline mode).")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if args.fixture:
        jobs = fetch_from_fixture(args.fixture)
        logger.info("wttj: %d jobs from fixture %s", len(jobs), args.fixture)
    else:
        jobs = fetch(
            query=args.query,
            location=args.location,
            max_pages=args.max_pages,
            senior_only=not args.no_senior,
        )

    run_id = uuid.uuid4().hex[:8]
    out_path = args.out or (TMP_DIR / f"wttj_{run_id}.jsonl")
    _write_jsonl(jobs, out_path)
    logger.info("wttj: wrote %d jobs to %s", len(jobs), out_path)

    for job in jobs:
        sys.stdout.write(job.model_dump_json() + "\n")
    return 0 if jobs else 1


if __name__ == "__main__":
    sys.exit(main())
