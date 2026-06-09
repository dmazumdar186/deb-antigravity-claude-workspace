"""
description: Jooble jobs API scraper. Free-tier via form signup (email-based, no card). POST endpoint. Returns structured 'type' field for contract classification. Covers all major countries by full-name string.
inputs:  queries (list[str]) — title synonyms; country (str) — Jooble full country name (e.g. "France"); page (int) default 1; max_results (int) default 50. Env var: JOOBLE_API_KEY.
outputs: list[RawJob] dicts written to .tmp/job_search/<run_id>/raw_jooble_<iso2>.json (also returned).
"""

import sys
import json
import argparse
import logging
import os
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

BOARD = "jooble"
JOOBLE_BASE_URL = "https://jooble.org/api/{api_key}"

# Jooble full country name → ISO2 for RawJob "country" field and output filename
JOOBLE_COUNTRY_TO_ISO2: dict[str, str] = {
    "France": "FR",
    "Germany": "DE",
    "Netherlands": "NL",
    "Spain": "ES",
    "Italy": "IT",
    "Belgium": "BE",
    "Austria": "AT",
    "Poland": "PL",
    "Portugal": "PT",
    "Canada": "CA",
    "USA": "US",
    "United States": "US",
    "United Kingdom": "GB",
    "Switzerland": "CH",
    "Sweden": "SE",
    "Norway": "NO",
    "Denmark": "DK",
    "Finland": "FI",
    "Ireland": "IE",
    "Luxembourg": "LU",
}

# Jooble "type" field → normalised contract_type
_JOOBLE_TYPE_MAP: dict[str, str] = {
    "full-time": "Permanent",
    "part-time": "Part-time",
    "contract": "Contract",
    "temporary": "Contract",
    "freelance": "Freelance",
    "internship": "Internship",
}

logger = logging.getLogger(__name__)


def _get_api_key() -> str | None:
    api_key = os.environ.get("JOOBLE_API_KEY")
    if not api_key:
        logger.warning(json.dumps({
            "event": "missing_credentials",
            "board": BOARD,
            "detail": "JOOBLE_API_KEY not set in environment",
        }))
        return None
    return api_key


def _normalise_contract_type(jooble_type: str | None) -> str | None:
    """Map Jooble 'type' field to normalised contract_type string."""
    if not jooble_type:
        return None
    key = jooble_type.strip().lower()
    return _JOOBLE_TYPE_MAP.get(key)


def _parse_posted_at(raw: str) -> str | None:
    """Strip Jooble ISO date-time string to YYYY-MM-DD, or return None."""
    if not raw:
        return None
    try:
        return raw[:10]
    except Exception:  # noqa: BLE001 — defensive; string slice never raises but guard anyway
        return None


@retry_with_backoff(max_retries=3)
def _fetch_jobs_page(
    api_key: str,
    query: str,
    location: str,
    page: int = 1,
) -> dict:
    """POST to Jooble API for one (query, location, page).

    Returns the raw response dict {"totalCount": int, "jobs": [...]}.
    Raises requests.HTTPError on non-2xx so retry_with_backoff handles 429/5xx.
    For HTTP 401 (bad key), raises immediately — caller must not retry.
    """
    url = JOOBLE_BASE_URL.format(api_key=api_key)
    payload = {
        "keywords": query,
        "location": location,
        "page": page,
    }
    resp = requests.post(url, json=payload, timeout=20)

    # 401 = bad API key — raise immediately (retry_with_backoff re-raises non-429/5xx)
    resp.raise_for_status()
    return resp.json()


def _map_jooble_job(j: dict, country_name: str) -> dict:
    """Map a single Jooble job dict to RawJob schema."""
    iso2 = JOOBLE_COUNTRY_TO_ISO2.get(country_name, country_name[:2].upper())
    return {
        "board": BOARD,
        "source_url": j.get("link", ""),
        "title": j.get("title", ""),
        "company_name": j.get("company", "") or "",
        "location": j.get("location") or None,
        "posted_at": _parse_posted_at(j.get("updated", "")),
        "description_snippet": (j.get("snippet") or "")[:400],
        "raw_extracted_at": now_iso(),
        "contract_type": _normalise_contract_type(j.get("type")),
        "country": iso2,
    }


def scrape(
    queries: list[str],
    output_path: Path | None = None,
    *,
    run_id: str | None = None,
    country: str = "France",
    page: int = 1,
    max_results: int = 50,
) -> list[dict]:
    """Scrape Jooble for the given queries and country name.

    Returns list[RawJob] and writes JSON to output_path (or default tmp path).

    Failure modes:
    - HTTP 401: bad API key → log clearly, return [] (no retry).
    - HTTP 429: rate limit → retry_with_backoff handles 2 retries, then log + return collected.
    - HTTP 5xx: retry_with_backoff handles 3 retries, then log + return collected.
    """
    run_id = run_id or generate_run_id()
    setup_logging("jooble_jobs")

    iso2 = JOOBLE_COUNTRY_TO_ISO2.get(country, country[:2].upper())

    if output_path is None:
        output_path = (
            PROJECT_ROOT / ".tmp" / "job_search" / run_id
            / f"raw_jooble_{iso2.lower()}.json"
        )

    all_jobs: list[dict] = []
    seen_urls: set[str] = set()

    api_key = _get_api_key()
    if api_key is None:
        return []

    for query in queries:
        logger.info(json.dumps({
            "event": "fetching_page",
            "board": BOARD,
            "query": query,
            "country": country,
            "page": page,
        }))

        try:
            data = _fetch_jobs_page(api_key, query, country, page=page)
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status == 401:
                logger.error(json.dumps({
                    "event": "jooble_bad_api_key",
                    "board": BOARD,
                    "detail": "HTTP 401 — JOOBLE_API_KEY is invalid or revoked. "
                              "Re-register at https://jooble.org/api/about",
                }))
                return []  # Don't continue — key is dead
            if status == 429:
                logger.warning(json.dumps({
                    "event": "jooble_rate_limited",
                    "board": BOARD,
                    "country": country,
                    "query": query,
                    "collected_so_far": len(all_jobs),
                }))
                break  # Per-query stop; return what we have
            logger.warning(json.dumps({
                "event": "page_fetch_error",
                "board": BOARD,
                "query": query,
                "country": country,
                "page": page,
                "error": str(exc),
            }))
            continue
        except Exception as exc:  # noqa: BLE001 — ConnectionError etc; log + skip query
            logger.warning(json.dumps({
                "event": "page_fetch_error",
                "board": BOARD,
                "query": query,
                "country": country,
                "page": page,
                "error": str(exc),
            }))
            continue

        jobs_raw = data.get("jobs") or []
        if not jobs_raw:
            logger.info(json.dumps({
                "event": "no_jobs_returned",
                "board": BOARD,
                "query": query,
                "country": country,
                "total_count": data.get("totalCount", 0),
            }))
            continue

        for j in jobs_raw:
            url = j.get("link", "")
            norm_url = url.lower()
            if norm_url and norm_url not in seen_urls:
                seen_urls.add(norm_url)
                all_jobs.append(_map_jooble_job(j, country))

        if len(all_jobs) >= max_results:
            break

    all_jobs = all_jobs[:max_results]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_json(all_jobs, output_path)

    logger.info(json.dumps({
        "event": "scraper_done",
        "board": BOARD,
        "country": country,
        "iso2": iso2,
        "count": len(all_jobs),
        "queries": queries,
    }))

    return all_jobs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape Jooble job listings via their free POST API."
    )
    parser.add_argument(
        "--country", default="France",
        help=(
            "Jooble country name (full string, NOT ISO2). Default: France. "
            "Supported: France Germany Netherlands Spain Italy Belgium Austria Poland "
            "Portugal Canada USA"
        ),
    )
    parser.add_argument(
        "--query", dest="queries", action="append", required=True, metavar="QUERY",
        help="Search query (repeatable). E.g. --query 'product manager'",
    )
    parser.add_argument(
        "--page", type=int, default=1,
        help="Page number (default: 1).",
    )
    parser.add_argument(
        "--output", dest="output", default=None, metavar="PATH",
        help="Output JSON path. Defaults to .tmp/job_search/<run_id>/raw_jooble_<iso2>.json",
    )
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else None
    results = scrape(
        args.queries,
        output_path=output_path,
        country=args.country,
        page=args.page,
    )
    iso2 = JOOBLE_COUNTRY_TO_ISO2.get(args.country, args.country[:2].upper())
    print(f"Scraped {len(results)} jobs from {BOARD} ({iso2}).")


if __name__ == "__main__":
    main()
