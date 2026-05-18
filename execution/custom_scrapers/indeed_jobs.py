"""
description: Scrape PM/PO job listings from Indeed France via Firecrawl SDK with stealth proxy.
inputs:
  - queries: list[str] — search terms (e.g. ["product manager", "product owner"])
  - output_path: pathlib.Path | None — where to write raw JSON; defaults to .tmp/job_tracker/{run_id}/raw_indeed.json
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

from execution.personal_workflows._jt_utils import (
    retry_with_backoff,
    setup_logging,
    now_iso,
    generate_run_id,
    save_json,
    load_jt_config,
)

BOARD = "indeed"
INDEED_HOST = "https://fr.indeed.com"
MAX_PAGES = 5
RESULTS_PER_PAGE = 10

logger = logging.getLogger(__name__)


def _get_firecrawl_app():
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        raise EnvironmentError("FIRECRAWL_API_KEY is not set in environment.")
    from firecrawl import FirecrawlApp
    return FirecrawlApp(api_key=api_key)


def _build_url(query: str, start: int) -> str:
    encoded_query = quote_plus(query)
    return f"{INDEED_HOST}/jobs?q={encoded_query}&l=France&fromage=7&start={start}"


@retry_with_backoff(max_retries=3)
def _fetch_markdown(app, url: str) -> str:
    # Try with stealth proxy first; fall back if the SDK rejects the param
    try:
        result = app.scrape_url(
            url,
            params={
                "formats": ["markdown"],
                "onlyMainContent": True,
                "proxy": "stealth",
                "actions": [{"type": "wait", "milliseconds": 1500}],
            },
        )
    except TypeError:
        logger.warning(json.dumps({"event": "proxy_stealth_unavailable", "board": BOARD, "url": url}))
        result = app.scrape_url(url, params={"formats": ["markdown"], "onlyMainContent": True})
    except Exception:
        # Re-raise so retry_with_backoff can handle it
        raise

    return result.get("markdown") or ""


def _is_blocked(markdown: str) -> bool:
    """Detect captcha / empty blocks from Indeed anti-bot measures."""
    if len(markdown.strip()) < 200:
        return True
    lower = markdown.lower()
    return "captcha" in lower or "verify you are human" in lower or "access denied" in lower


def _parse_markdown(markdown: str) -> list[dict]:
    """
    Indeed markdown renders job cards as headings followed by metadata lines.
    Pattern: a heading (## ...) or bold text containing the job title,
    followed within 4 lines by company and location metadata.
    Also look for viewjob URLs embedded in the markdown.
    """
    jobs: list[dict] = []
    lines = markdown.splitlines()

    # Match an Indeed viewjob URL anywhere in the line
    url_re = re.compile(
        r"https?://fr\.indeed\.com/(?:viewjob\?jk=[a-z0-9]+|pagead/clk[^\s\)\"]+|rc/clk[^\s\)\"]+|company/[^\s\)\"]+/jobs/[^\s\)\"]+)",
        re.IGNORECASE,
    )
    # Match heading lines (## or bold)
    heading_re = re.compile(r"^#{1,4}\s+(?P<title>.+)$")

    i = 0
    while i < len(lines):
        line = lines[i]
        heading_match = heading_re.match(line.strip())

        if heading_match:
            title = heading_match.group("title").strip()
            # Strip any markdown links inside the heading
            title = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", title).strip()
            if not title:
                i += 1
                continue

            source_url: str | None = None
            company_name: str | None = None
            location: str | None = None

            # Look in the heading line itself and next 4 lines for URL + metadata
            window = [line] + lines[i + 1: i + 5]
            for win_line in window:
                url_match = url_re.search(win_line)
                if url_match and source_url is None:
                    source_url = url_match.group(0)

                stripped = win_line.strip()
                # Skip headings, empty, or link-only lines for metadata
                if stripped.startswith("#") or not stripped:
                    continue
                # Strip markdown links for metadata extraction
                plain = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", stripped).strip()
                if not plain or plain == title:
                    continue
                if company_name is None and re.search(r"[A-Za-zÀ-ÿ]", plain):
                    company_name = plain
                elif location is None and re.search(r"[A-Za-zÀ-ÿ]", plain):
                    location = plain

            if source_url is None:
                i += 1
                continue

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

            for page in range(MAX_PAGES):
                start = page * RESULTS_PER_PAGE
                url = _build_url(query, start)
                logger.info(json.dumps({"event": "fetching_page", "board": BOARD, "query": query, "page": page + 1, "url": url}))

                try:
                    markdown = _fetch_markdown(app, url)
                except Exception as exc:
                    logger.warning(json.dumps({"event": "page_fetch_error", "board": BOARD, "query": query, "page": page + 1, "error": str(exc)}))
                    break

                if _is_blocked(markdown):
                    logger.warning(json.dumps({"event": "indeed_blocked", "board": BOARD, "query": query, "page": page + 1}))
                    break

                page_jobs = _parse_markdown(markdown)

                if not page_jobs:
                    logger.info(json.dumps({"event": "no_cards_on_page", "board": BOARD, "query": query, "page": page + 1}))
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
    parser = argparse.ArgumentParser(description="Scrape Indeed France job listings.")
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
