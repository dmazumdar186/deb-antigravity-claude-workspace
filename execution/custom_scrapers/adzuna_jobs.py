"""
description: Adzuna jobs API scraper. Free-tier: 250 req/day per app. Covers FR, DE, NL, ES, IT, BE, AT, PL, PT, CA, US among others. Returns structured fields incl. contract_time (permanent/contract) and full_time/part_time flags.
inputs:  queries (list[str]) — title synonyms; country (str) — ISO2 like "fr"; max_results (int) default 50; results_per_page default 50; pages default 1. Env vars: ADZUNA_APP_ID, ADZUNA_APP_KEY.
outputs: list[RawJob] dicts written to .tmp/job_search/<run_id>/raw_adzuna_<country>.json (also returned).
"""

import sys
import json
import re
import argparse
import logging
import os
from datetime import datetime
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

BOARD = "adzuna"
ADZUNA_BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"

# French contract keywords in description text when structured field is absent
_FR_CONTRACT_RE = re.compile(r"\b(CDI|CDD|freelance|free-lance)\b", re.IGNORECASE)

logger = logging.getLogger(__name__)


def _get_credentials() -> tuple[str, str] | tuple[None, None]:
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        logger.warning(json.dumps({
            "event": "missing_credentials",
            "board": BOARD,
            "detail": "ADZUNA_APP_ID or ADZUNA_APP_KEY not set in environment",
        }))
        return None, None
    return app_id, app_key


def _parse_contract_type(r: dict, country: str) -> str | None:
    """Derive a normalised contract_type string from Adzuna structured fields.

    Priority:
    1. Structured contract_type field ("permanent" → "Permanent", "contract" → "Contract").
    2. For FR country: scan description_snippet for CDI / CDD / freelance keywords.
    3. Return None if nothing conclusive.
    """
    ct = (r.get("contract_type") or "").lower()
    if ct == "permanent":
        return "Permanent"
    if ct == "contract":
        return "Contract"

    # FR-specific: parse description for French contract keywords
    if country.lower() == "fr":
        description = r.get("description", "") or ""
        match = _FR_CONTRACT_RE.search(description)
        if match:
            keyword = match.group(0).upper()
            if keyword == "CDI":
                return "CDI"
            if keyword == "CDD":
                return "CDD"
            if keyword in ("FREELANCE", "FREE-LANCE"):
                return "Freelance"

    return None


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _parse_posted_at(raw: str) -> str | None:
    """Strip Adzuna ISO 8601 datetime to YYYY-MM-DD, or return None.

    Validates that the first 10 characters look like a date (yyyy-mm-dd) AND
    that the date is actually constructable. A bare slice without validation
    silently emitted strings like "not-a-dat" for malformed upstream values
    (regression-tested in tests/test_custom_scrapers.py).
    """
    if not raw or len(raw) < 10:
        return None
    head = raw[:10]
    if not _ISO_DATE_RE.match(head):
        return None
    try:
        datetime.strptime(head, "%Y-%m-%d")  # raises on impossible dates (e.g. 2026-13-40)
    except (ValueError, TypeError):
        return None
    return head


@retry_with_backoff(max_retries=3)
def _fetch_jobs_page(
    app_id: str,
    app_key: str,
    country: str,
    query: str,
    page: int = 1,
    results_per_page: int = 50,
) -> dict:
    """Call Adzuna search endpoint for one (query, page).

    Returns the raw response dict (with "results" list and "count").
    Raises requests.HTTPError on non-2xx so retry_with_backoff can handle 429/5xx.
    """
    url = ADZUNA_BASE_URL.format(country=country.lower(), page=page)
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": results_per_page,
        "what": query,
        "content-type": "application/json",
    }
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _map_adzuna_job(r: dict, country: str) -> dict:
    """Map a single Adzuna result dict to RawJob schema."""
    return {
        "board": BOARD,
        "source_url": r.get("redirect_url", ""),
        "title": r.get("title", ""),
        "company_name": (r.get("company") or {}).get("display_name", "") or "",
        "location": (r.get("location") or {}).get("display_name") or None,
        "posted_at": _parse_posted_at(r.get("created", "")),
        "description_snippet": (r.get("description") or "")[:400],
        "raw_extracted_at": now_iso(),
        "contract_type": _parse_contract_type(r, country),
        "country": country.upper(),
    }


def scrape(
    queries: list[str],
    output_path: Path | None = None,
    *,
    run_id: str | None = None,
    country: str = "fr",
    max_results: int = 50,
    pages: int = 1,
) -> list[dict]:
    """Scrape Adzuna for the given queries and country.

    Returns list[RawJob] and writes JSON to output_path (or default tmp path).

    Quota handling: if Adzuna returns HTTP 429 or a JSON "exception" field
    mentioning "rate" or "limit", logs adzuna_quota_exhausted=true and returns
    whatever has been collected so far — does NOT keep retrying.
    """
    run_id = run_id or generate_run_id()
    setup_logging("adzuna_jobs")

    if output_path is None:
        output_path = (
            PROJECT_ROOT / ".tmp" / "job_search" / run_id
            / f"raw_adzuna_{country.lower()}.json"
        )

    all_jobs: list[dict] = []
    seen_urls: set[str] = set()
    quota_exhausted = False

    app_id, app_key = _get_credentials()
    if app_id is None:
        return []

    for query in queries:
        if quota_exhausted:
            break

        for page_num in range(1, pages + 1):
            if quota_exhausted:
                break

            logger.info(json.dumps({
                "event": "fetching_page",
                "board": BOARD,
                "query": query,
                "country": country,
                "page": page_num,
            }))

            try:
                data = _fetch_jobs_page(app_id, app_key, country, query, page=page_num)
            except requests.exceptions.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else None
                if status == 429:
                    logger.warning(json.dumps({
                        "event": "adzuna_quota_exhausted",
                        "board": BOARD,
                        "country": country,
                        "query": query,
                        "collected_so_far": len(all_jobs),
                    }))
                    quota_exhausted = True
                    break
                logger.warning(json.dumps({
                    "event": "page_fetch_error",
                    "board": BOARD,
                    "query": query,
                    "country": country,
                    "page": page_num,
                    "error": str(exc),
                }))
                break
            except Exception as exc:  # noqa: BLE001 — ConnectionError etc; log + skip page
                logger.warning(json.dumps({
                    "event": "page_fetch_error",
                    "board": BOARD,
                    "query": query,
                    "country": country,
                    "page": page_num,
                    "error": str(exc),
                }))
                break

            # Check for Adzuna API-level quota / error signal in response body
            exception_msg = (data.get("exception") or "").lower()
            if exception_msg and ("rate" in exception_msg or "limit" in exception_msg):
                logger.warning(json.dumps({
                    "event": "adzuna_quota_exhausted",
                    "board": BOARD,
                    "country": country,
                    "query": query,
                    "api_exception": data.get("exception"),
                    "collected_so_far": len(all_jobs),
                }))
                quota_exhausted = True
                break

            results = data.get("results", []) or []
            if not results:
                logger.info(json.dumps({
                    "event": "no_results_on_page",
                    "board": BOARD,
                    "query": query,
                    "country": country,
                    "page": page_num,
                }))
                break

            for r in results:
                url = r.get("redirect_url", "")
                norm_url = url.lower()
                if norm_url and norm_url not in seen_urls:
                    seen_urls.add(norm_url)
                    all_jobs.append(_map_adzuna_job(r, country))

            if len(all_jobs) >= max_results:
                break

    all_jobs = all_jobs[:max_results]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_json(all_jobs, output_path)

    logger.info(json.dumps({
        "event": "scraper_done",
        "board": BOARD,
        "country": country,
        "count": len(all_jobs),
        "queries": queries,
        "quota_exhausted": quota_exhausted,
    }))

    return all_jobs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape Adzuna job listings via their free REST API."
    )
    parser.add_argument(
        "--country", default="fr",
        help="ISO2 country code (lowercase). Default: fr. Supported: fr de nl es it be at pl pt ca us",
    )
    parser.add_argument(
        "--query", dest="queries", action="append", required=True, metavar="QUERY",
        help="Search query (repeatable). E.g. --query 'product manager' --query 'chef de produit'",
    )
    parser.add_argument(
        "--pages", type=int, default=1,
        help="Number of result pages per query (default: 1 = 50 results). Cap at 1 for free-tier quota.",
    )
    parser.add_argument(
        "--output", dest="output", default=None, metavar="PATH",
        help="Output JSON path. Defaults to .tmp/job_search/<run_id>/raw_adzuna_<country>.json",
    )
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else None
    results = scrape(
        args.queries,
        output_path=output_path,
        country=args.country,
        pages=args.pages,
    )
    print(f"Scraped {len(results)} jobs from {BOARD} ({args.country.upper()}).")


if __name__ == "__main__":
    main()
