"""
description: Scrape PM/PO job listings from APEC (cadres/executives France) via Firecrawl SDK.
inputs:
  - queries: list[str] — search terms (e.g. ["product manager", "product owner"])
  - output_path: pathlib.Path | None — where to write raw JSON; defaults to .tmp/job_tracker/{run_id}/raw_apec.json
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
from datetime import datetime
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

BOARD = "apec"
APEC_HOST = "https://www.apec.fr"
MAX_PAGES = 5

logger = logging.getLogger(__name__)


def _get_firecrawl_app():
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        raise EnvironmentError("FIRECRAWL_API_KEY is not set in environment.")
    from firecrawl import FirecrawlApp
    return FirecrawlApp(api_key=api_key)


def _build_url(query: str, page: int) -> str:
    encoded_query = quote_plus(query)
    return (
        f"{APEC_HOST}/candidat/recherche-emploi.html/emploi"
        f"?motsCles={encoded_query}&page={page}"
    )


@retry_with_backoff(max_retries=3)
def _fetch_markdown(app, url: str) -> str:
    result = app.scrape_url(
        url,
        params={
            "formats": ["markdown"],
            "onlyMainContent": True,
            "actions": [{"type": "wait", "milliseconds": 2000}],
        },
    )
    return result.get("markdown") or ""


def _parse_french_date(date_str: str) -> str | None:
    """
    Parse a French date like '12/05/2025' or 'Publiée le 12/05/2025' into ISO format.
    Returns 'YYYY-MM-DD' string or None.
    """
    match = re.search(r"(\d{2})/(\d{2})/(\d{4})", date_str)
    if match:
        day, month, year = match.group(1), match.group(2), match.group(3)
        try:
            dt = datetime(int(year), int(month), int(day))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None


def _parse_markdown(markdown: str) -> list[dict]:
    """
    APEC markdown job cards typically follow a repeating structure:
      - A heading or bold-linked job title (often linking to /candidat/offre-emploi-detail/...)
      - A company name line
      - A location line
      - A 'Publiée le dd/mm/yyyy' line

    We scan for APEC job detail links as anchor points, then extract surrounding metadata.
    """
    jobs: list[dict] = []
    lines = markdown.splitlines()

    # Link to an APEC job detail page
    job_link_re = re.compile(
        r"\[(?P<title>[^\]]+)\]\((?P<url>https?://(?:www\.)?apec\.fr/candidat/offre-emploi-detail[^\)]+)\)",
        re.IGNORECASE,
    )
    # Date pattern
    date_re = re.compile(r"[Pp]ubli[ée]e?\s+le\s+(\d{2}/\d{2}/\d{4})")

    i = 0
    while i < len(lines):
        line = lines[i]
        match = job_link_re.search(line)
        if match:
            title = match.group("title").strip()
            source_url = match.group("url").strip()

            company_name: str | None = None
            location: str | None = None
            posted_at: str | None = None

            # Scan next 8 lines for metadata
            window = lines[i + 1: i + 9]
            for meta_line in window:
                stripped = meta_line.strip()
                if not stripped:
                    continue

                # Date line
                date_match = date_re.search(stripped)
                if date_match and posted_at is None:
                    posted_at = _parse_french_date(date_match.group(1))
                    continue

                # Skip markdown links and headings for name/location
                plain = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", stripped).strip()
                if plain.startswith("#") or not re.search(r"[A-Za-zÀ-ÿ]", plain):
                    continue
                if plain == title:
                    continue

                if company_name is None:
                    company_name = plain
                elif location is None:
                    location = plain

            jobs.append({
                "board": BOARD,
                "source_url": source_url,
                "title": title,
                "company_name": company_name or "",
                "location": location,
                "posted_at": posted_at,
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
    parser = argparse.ArgumentParser(description="Scrape APEC job listings (France cadres).")
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
