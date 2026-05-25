"""
description: Scrape PM/PO job listings from Welcome to the Jungle (France only) via Firecrawl SDK.
inputs:
  - queries: list[str] — search terms (e.g. ["product manager", "product owner"])
  - output_path: pathlib.Path | None — where to write raw JSON; defaults to .tmp/job_tracker/{run_id}/raw_wttj.json
  - max_results: int — cap on total results returned (default 200)
outputs:
  - list[RawJob] written to output_path and returned in-memory
"""

import sys
import json
import re
import argparse
import logging
import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution.personal_workflows._jt_utils import (  # noqa: E402
    retry_with_backoff,
    setup_logging,
    now_iso,
    generate_run_id,
    save_json,
)

BOARD = "wttj"
WTTJ_HOST = "https://www.welcometothejungle.com"
MAX_PAGES = 10

logger = logging.getLogger(__name__)


def _get_firecrawl_app():
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        raise EnvironmentError("FIRECRAWL_API_KEY is not set in environment.")
    from firecrawl import FirecrawlApp
    return FirecrawlApp(api_key=api_key)


def _build_url(query: str, page: int) -> str:
    encoded_query = quote_plus(query)
    # Brackets kept literal in the URL for WTTJ's faceted search param
    return (
        f"{WTTJ_HOST}/fr/jobs"
        f"?query={encoded_query}"
        f"&refinementList[offices.country_code][]=FR"
        f"&page={page}"
    )


@retry_with_backoff(max_retries=3)
def _fetch_markdown(app, url: str) -> str:
    result = app.scrape_url(url, params={"formats": ["markdown"], "onlyMainContent": True})
    return result.get("markdown") or ""


def _parse_markdown(markdown: str) -> list[dict]:
    """
    Scan WTTJ markdown for job card link patterns:
      [<title>](https://www.welcometothejungle.com/.../jobs/<slug>)
    Then look ahead ~6 lines for company and location hints.
    """
    jobs: list[dict] = []
    lines = markdown.splitlines()

    # Regex: markdown link whose href points to a WTTJ job page
    job_link_re = re.compile(
        r"\[(?P<title>[^\]]+)\]\((?P<url>https?://(?:www\.)?welcometothejungle\.com[^\)]+/jobs/[^\)]+)\)",
        re.IGNORECASE,
    )

    i = 0
    while i < len(lines):
        line = lines[i]
        match = job_link_re.search(line)
        if match:
            title = match.group("title").strip()
            source_url = match.group("url").strip()

            # Guard: must actually belong to WTTJ
            if "welcometothejungle.com" not in source_url:
                i += 1
                continue

            company_name: str | None = None
            location: str | None = None

            # Scan the following 6 lines for metadata
            window = lines[i + 1: i + 7]
            for meta_line in window:
                stripped = meta_line.strip()
                if not stripped or stripped.startswith("[") or stripped.startswith("#"):
                    continue
                # Heuristic: first non-empty, non-link, non-heading line is company
                if company_name is None and re.search(r"[A-Za-zÀ-ÿ]", stripped):
                    company_name = stripped
                elif location is None and re.search(r"[A-Za-zÀ-ÿ]", stripped):
                    location = stripped

            jobs.append({
                "board": BOARD,
                "source_url": source_url,
                "title": title,
                "company_name": company_name or "",
                "location": location,
                "posted_at": None,
                "description_snippet": "",
                "raw_extracted_at": now_iso(),
            })
        i += 1

    return jobs


def scrape(
    queries: list[str],
    output_path: Path | None = None,
    *,
    run_id: str | None = None,
    max_results: int = 200,
) -> list[dict]:
    """Returns list[RawJob] and writes JSON to output_path (or default tmp path) if provided."""
    run_id = run_id or generate_run_id()
    setup_logging()

    if output_path is None:
        output_path = PROJECT_ROOT / ".tmp" / "job_tracker" / run_id / f"raw_{BOARD}.json"

    all_jobs: list[dict] = []
    seen_urls: set[str] = set()

    try:
        app = _get_firecrawl_app()
        per_query_cap = max(1, max_results // max(len(queries), 1))

        for query in queries:
            query_jobs: list[dict] = []

            for page in range(1, MAX_PAGES + 1):
                url = _build_url(query, page)
                logger.info(json.dumps({"event": "fetching_page", "board": BOARD, "query": query, "page": page, "url": url}))

                try:
                    markdown = _fetch_markdown(app, url)
                except Exception as exc:
                    logger.warning(json.dumps({"event": "page_fetch_error", "board": BOARD, "query": query, "page": page, "error": str(exc)}))
                    break

                page_jobs = _parse_markdown(markdown)

                if not page_jobs:
                    logger.info(json.dumps({"event": "no_cards_on_page", "board": BOARD, "query": query, "page": page}))
                    break

                for job in page_jobs:
                    norm_url = job["source_url"].lower()
                    if norm_url not in seen_urls:
                        seen_urls.add(norm_url)
                        query_jobs.append(job)

                if len(query_jobs) >= per_query_cap:
                    break

            all_jobs.extend(query_jobs[:per_query_cap])

        all_jobs = all_jobs[:max_results]

        output_path.parent.mkdir(parents=True, exist_ok=True)
        save_json(all_jobs, output_path)

        logger.info(json.dumps({"event": "scraper_done", "board": BOARD, "count": len(all_jobs), "queries": queries}))

    except Exception as exc:
        logger.error(json.dumps({"event": "scraper_failed", "board": BOARD, "error": str(exc)}))
        return []

    return all_jobs


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Welcome to the Jungle job listings (France).")
    parser.add_argument("--query", dest="queries", action="append", required=True, metavar="QUERY",
                        help="Search query (repeatable).")
    parser.add_argument("--output", dest="output", default=None, metavar="PATH",
                        help="Output JSON path.")
    parser.add_argument("--max-results", dest="max_results", type=int, default=200,
                        help="Maximum total results (default: 200).")
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else None
    results = scrape(args.queries, output_path=output_path, max_results=args.max_results)
    print(f"Scraped {len(results)} jobs from {BOARD}.")


if __name__ == "__main__":
    main()
