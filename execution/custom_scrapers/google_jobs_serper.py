"""
description: Scrape PM/PO job listings from Google Jobs via Serper.dev /jobs endpoint.
inputs:
  - queries: list[str] — search terms (e.g. ["product manager", "product owner"])
  - output_path: pathlib.Path | None — where to write raw JSON; defaults to .tmp/job_tracker/{run_id}/raw_google.json
  - max_results: int — cap on total results returned (default 200)
outputs:
  - list[RawJob] written to output_path and returned in-memory

Environment variables required:
  SERPER_API_KEY — API key from serper.dev
"""

import sys
import json
import re
import argparse
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import requests
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

BOARD = "google"
SERPER_JOBS_URL = "https://google.serper.dev/jobs"

logger = logging.getLogger(__name__)


def _get_serper_api_key() -> str | None:
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        logger.warning(json.dumps({
            "event": "missing_credentials",
            "board": BOARD,
            "detail": "SERPER_API_KEY not set in environment",
        }))
        return None
    return api_key


def _parse_relative_date(raw: str) -> str | None:
    """
    Best-effort parse of Serper's relative date strings like:
      '2 days ago', '3 hours ago', '1 week ago', 'Posted 5 days ago', 'Today', 'yesterday'
    Returns ISO date string (YYYY-MM-DD) or None if unparseable.
    """
    if not raw:
        return None

    raw_lower = raw.lower().strip()

    if raw_lower in ("today", "aujourd'hui", "just now"):
        return datetime.utcnow().strftime("%Y-%m-%d")

    if raw_lower in ("yesterday", "hier"):
        return (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

    # Match patterns like "2 days ago", "3 hours ago", "1 week ago"
    pattern = re.compile(
        r"(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago",
        re.IGNORECASE,
    )
    match = pattern.search(raw_lower)
    if match:
        value = int(match.group(1))
        unit = match.group(2).lower()
        delta_map = {
            "second": timedelta(seconds=value),
            "minute": timedelta(minutes=value),
            "hour": timedelta(hours=value),
            "day": timedelta(days=value),
            "week": timedelta(weeks=value),
            "month": timedelta(days=value * 30),
            "year": timedelta(days=value * 365),
        }
        delta = delta_map.get(unit)
        if delta:
            return (datetime.utcnow() - delta).strftime("%Y-%m-%d")

    # Try parsing explicit dates as fallback (e.g. "2025-05-10" or "10/05/2025")
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


@retry_with_backoff(max_retries=3)
def _fetch_jobs_page(api_key: str, query: str, page: int) -> list[dict]:
    """Call Serper /jobs endpoint for one page. Returns raw job dicts from response."""
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "q": f"{query} France",
        "gl": "fr",
        "hl": "fr",
        "page": page,
    }
    resp = requests.post(SERPER_JOBS_URL, headers=headers, json=payload, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data.get("jobs", []) or []


def _map_serper_job(raw: dict) -> dict | None:
    """
    Map a Serper job result dict to RawJob.
    Returns None if no usable source_url is found.
    """
    # Prefer applyLink, then shareLink; skip if neither present
    source_url = raw.get("applyLink") or raw.get("shareLink")
    if not source_url:
        return None

    # posted_at: try structured field first, then relative string
    posted_at_raw: str = raw.get("posted_at") or raw.get("date") or ""
    posted_at = _parse_relative_date(posted_at_raw)

    description = raw.get("description", "") or ""
    snippet = description[:400] if description else ""

    job: dict = {
        "board": BOARD,
        "source_url": source_url,
        "title": raw.get("title", ""),
        "company_name": raw.get("company", "") or "",
        "location": raw.get("location") or None,
        "posted_at": posted_at,
        "description_snippet": snippet,
        "raw_extracted_at": now_iso(),
    }

    # Carry raw date string as extra field if we couldn't parse it
    if posted_at is None and posted_at_raw:
        job["posted_at_raw"] = posted_at_raw

    return job


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
        api_key = _get_serper_api_key()
        if api_key is None:
            return []

        per_query_cap = max(1, max_results // max(len(queries), 1))

        for query in queries:
            query_jobs: list[dict] = []
            page = 1

            while len(query_jobs) < per_query_cap:
                logger.info(json.dumps({
                    "event": "fetching_page",
                    "board": BOARD,
                    "query": query,
                    "page": page,
                }))

                try:
                    raw_jobs = _fetch_jobs_page(api_key, query, page)
                except Exception as exc:
                    logger.warning(json.dumps({
                        "event": "page_fetch_error",
                        "board": BOARD,
                        "query": query,
                        "page": page,
                        "error": str(exc),
                    }))
                    break

                if not raw_jobs:
                    logger.info(json.dumps({
                        "event": "no_jobs_on_page",
                        "board": BOARD,
                        "query": query,
                        "page": page,
                    }))
                    break

                for raw in raw_jobs:
                    job = _map_serper_job(raw)
                    if job is None:
                        continue
                    norm_url = job["source_url"].lower()
                    if norm_url not in seen_urls:
                        seen_urls.add(norm_url)
                        query_jobs.append(job)

                page += 1

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
    parser = argparse.ArgumentParser(description="Scrape Google Jobs via Serper.dev /jobs endpoint.")
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
