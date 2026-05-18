"""
description: Fetch PM/PO job listings from France Travail (Pôle Emploi) official REST API using OAuth2 client_credentials flow.
inputs:
  - queries: list[str] — search terms (e.g. ["product manager", "product owner"])
  - output_path: pathlib.Path | None — where to write raw JSON; defaults to .tmp/job_tracker/{run_id}/raw_francetravail.json
  - max_results: int — cap on total results returned (default 200)
outputs:
  - list[RawJob] written to output_path and returned in-memory

Environment variables required:
  FRANCE_TRAVAIL_CLIENT_ID     — OAuth2 client ID from France Travail developer portal
  FRANCE_TRAVAIL_CLIENT_SECRET — OAuth2 client secret
"""

import sys
import json
import re
import argparse
import logging
import os
import time
from pathlib import Path

import requests
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

BOARD = "francetravail"

TOKEN_ENDPOINT = (
    "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
    "?realm=/partenaire"
)
SEARCH_ENDPOINT = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
PUBLIC_OFFER_URL = "https://candidat.francetravail.fr/offres/recherche/detail/{id}"

# In-memory token cache: {"access_token": str, "expires_at": float}
_token_cache: dict = {}

logger = logging.getLogger(__name__)


def _get_credentials() -> tuple[str, str] | tuple[None, None]:
    client_id = os.environ.get("FRANCE_TRAVAIL_CLIENT_ID")
    client_secret = os.environ.get("FRANCE_TRAVAIL_CLIENT_SECRET")
    if not client_id or not client_secret:
        logger.warning(json.dumps({
            "event": "missing_credentials",
            "board": BOARD,
            "detail": "FRANCE_TRAVAIL_CLIENT_ID or FRANCE_TRAVAIL_CLIENT_SECRET not set",
        }))
        return None, None
    return client_id, client_secret


@retry_with_backoff(max_retries=3)
def _fetch_token(client_id: str, client_secret: str) -> str:
    """Fetch OAuth2 access token using client_credentials grant. Caches result in _token_cache."""
    now = time.time()

    if _token_cache.get("access_token") and _token_cache.get("expires_at", 0) > now + 30:
        return _token_cache["access_token"]

    resp = requests.post(
        TOKEN_ENDPOINT,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "api_offresdemploiv2 o2dsoffre",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    resp.raise_for_status()
    token_data = resp.json()
    access_token: str = token_data["access_token"]
    expires_in: int = token_data.get("expires_in", 1800)

    _token_cache["access_token"] = access_token
    _token_cache["expires_at"] = now + expires_in

    return access_token


@retry_with_backoff(max_retries=3)
def _search_offers(token: str, query: str, range_start: int, range_end: int) -> list[dict]:
    """Call France Travail search endpoint. Returns list of raw offer dicts."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    params = {
        "motsCles": query,
        "codeROME": "M1707",
        "pays": "FR",
        "publieeDepuis": 7,
        "range": f"{range_start}-{range_end}",
    }
    resp = requests.get(SEARCH_ENDPOINT, headers=headers, params=params, timeout=20)

    # 204 No Content → no results
    if resp.status_code == 204:
        return []

    # 206 Partial Content is still success
    if resp.status_code not in (200, 206):
        resp.raise_for_status()

    data = resp.json()
    return data.get("resultats", [])


def _map_offer_to_raw_job(offer: dict) -> dict:
    offer_id = offer.get("id", "")
    source_url = PUBLIC_OFFER_URL.format(id=offer_id) if offer_id else ""

    # description_snippet: first 400 chars if available
    description = offer.get("description", "")
    snippet = description[:400] if description else ""

    # posted_at: dateCreation truncated to date
    date_creation = offer.get("dateCreation", "")
    posted_at = date_creation[:10] if date_creation else None

    return {
        "board": BOARD,
        "source_url": source_url,
        "title": offer.get("intitule", ""),
        "company_name": (offer.get("entreprise") or {}).get("nom", "") or "",
        "location": (offer.get("lieuTravail") or {}).get("libelle", "") or None,
        "posted_at": posted_at,
        "description_snippet": snippet,
        "raw_extracted_at": now_iso(),
    }


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
        client_id, client_secret = _get_credentials()
        if client_id is None:
            return []

        token = _fetch_token(client_id, client_secret)
        per_query_cap = max(1, max_results // max(len(queries), 1))

        for query in queries:
            query_jobs: list[dict] = []
            # France Travail API returns max 150 per call (range 0-149)
            range_start = 0
            page_size = 149

            while len(query_jobs) < per_query_cap:
                range_end = min(range_start + page_size, range_start + per_query_cap - len(query_jobs) - 1)
                logger.info(json.dumps({
                    "event": "fetching_page",
                    "board": BOARD,
                    "query": query,
                    "range": f"{range_start}-{range_end}",
                }))

                try:
                    offers = _search_offers(token, query, range_start, range_end)
                except Exception as exc:
                    logger.warning(json.dumps({"event": "page_fetch_error", "board": BOARD, "query": query, "error": str(exc)}))
                    break

                if not offers:
                    logger.info(json.dumps({"event": "no_offers_returned", "board": BOARD, "query": query, "range_start": range_start}))
                    break

                for offer in offers:
                    job = _map_offer_to_raw_job(offer)
                    norm_url = job["source_url"].lower()
                    if norm_url and norm_url not in seen_urls:
                        seen_urls.add(norm_url)
                        query_jobs.append(job)

                range_start = range_end + 1

                # If we got fewer results than requested, we've exhausted the listings
                if len(offers) < (range_end - (range_start - len(offers)) + 1):
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
    parser = argparse.ArgumentParser(description="Fetch France Travail job listings via official REST API.")
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
