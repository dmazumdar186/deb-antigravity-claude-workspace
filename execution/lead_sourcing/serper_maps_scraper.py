#!/usr/bin/env python3
"""
serper_maps_scraper.py
description: Scrape Google Maps business listings via Serper.dev Maps API.
inputs: --query or --config, --limit, --output, --mock; env: SERPER_API_KEY
outputs: .tmp/serper_leads.json
usage:
    py execution/lead_sourcing/serper_maps_scraper.py --query "car wash Houston TX" --mock
    py execution/lead_sourcing/serper_maps_scraper.py --config config/accessory_masters.json --mock
"""

import argparse
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "execution"))

from modules.pipeline_utils import (
    compute_dedup_key,
    deduplicate,
    generate_run_id,
    load_config,
    now_iso,
    retry_with_backoff,
    save_leads,
    setup_logging,
)

load_dotenv(ROOT / ".env")
logger = setup_logging("serper_maps", log_dir=ROOT / ".tmp")

SERPER_MAPS_URL = "https://google.serper.dev/maps"


def get_mock_data() -> list[dict]:
    """Return hardcoded Houston business data for local testing."""
    run_id = generate_run_id()
    ts = now_iso()
    businesses = [
        {"name": "Sparkle Car Wash", "address": "4521 Main St, Houston, TX 77002", "phone": "+1-713-555-0101", "website": "https://sparklecarwash.com", "rating": 4.5, "reviews": 187, "industry": "car wash"},
        {"name": "Houston Hand Wash", "address": "1200 Westheimer Rd, Houston, TX 77006", "phone": "+1-713-555-0102", "website": "https://houstonhandwash.com", "rating": 4.2, "reviews": 93, "industry": "car wash"},
        {"name": "Tony's Pizza Palace", "address": "3456 Richmond Ave, Houston, TX 77046", "phone": "+1-713-555-0103", "website": "https://tonyspizzapalace.com", "rating": 4.7, "reviews": 312, "industry": "pizzeria"},
        {"name": "Napoli Pizzeria", "address": "890 Shepherd Dr, Houston, TX 77007", "phone": "+1-713-555-0104", "website": "https://napolipizzeria.com", "rating": 4.4, "reviews": 156, "industry": "pizzeria"},
        {"name": "Clean & Fresh Laundromat", "address": "2100 Airline Dr, Houston, TX 77009", "phone": "+1-713-555-0105", "website": "https://cleanfreshlaundry.com", "rating": 3.9, "reviews": 45, "industry": "laundromat"},
        {"name": "Bayou Marina Services", "address": "7800 Navigation Blvd, Houston, TX 77011", "phone": "+1-713-555-0106", "website": "https://bayoumarina.com", "rating": 4.1, "reviews": 67, "industry": "marina"},
        {"name": "Gulf Coast Auto Repair", "address": "5500 Telephone Rd, Houston, TX 77087", "phone": "+1-713-555-0107", "website": "https://gulfcoastauto.com", "rating": 4.6, "reviews": 234, "industry": "auto repair"},
        {"name": "Lone Star Dry Cleaners", "address": "1900 Montrose Blvd, Houston, TX 77006", "phone": "+1-713-555-0108", "website": "https://lonestardrycleaning.com", "rating": 4.3, "reviews": 89, "industry": "dry cleaner"},
        {"name": "Sugar Land Pest Control", "address": "450 Highway 6, Sugar Land, TX 77478", "phone": "+1-281-555-0109", "website": "https://sugarpest.com", "rating": 4.8, "reviews": 201, "industry": "pest control"},
        {"name": "Katy Fresh Bakery", "address": "23100 Cinco Ranch Blvd, Katy, TX 77494", "phone": "+1-281-555-0110", "website": "https://katyfreshbakery.com", "rating": 4.9, "reviews": 445, "industry": "bakery"},
    ]
    leads = []
    for b in businesses:
        lead = _build_lead(
            business_name=b["name"],
            address=b["address"],
            phone=b["phone"],
            website=b["website"],
            rating=b["rating"],
            reviews_count=b["reviews"],
            industry=b["industry"],
            source_query=f"{b['industry']} Houston TX",
            run_id=run_id,
            timestamp=ts,
        )
        leads.append(lead)
    return leads


def _parse_address(address: str) -> tuple[str, str]:
    """Extract city and state from a full address string. Returns (city, state)."""
    if not address:
        return ("", "")
    parts = [p.strip() for p in address.split(",")]
    if len(parts) >= 2:
        last = parts[-1].strip()
        tokens = last.split()
        state = tokens[0] if tokens else ""
        city = parts[-2].strip() if len(parts) >= 3 else parts[-1].strip()
        return (city, state)
    return ("", "")


def _extract_domain(url: str) -> str:
    """Extract bare domain from a URL."""
    if not url:
        return ""
    from modules.pipeline_utils import normalize_domain
    return normalize_domain(url)


def _build_lead(
    business_name: str,
    address: str,
    phone: str,
    website: str,
    rating: float | None,
    reviews_count: int | None,
    industry: str,
    source_query: str,
    run_id: str,
    timestamp: str,
) -> dict:
    """Construct a standardized lead record."""
    city, state = _parse_address(address)
    domain = _extract_domain(website)
    lead = {
        "business_name": business_name,
        "address": address,
        "city": city,
        "state": state,
        "phone": phone,
        "website": website,
        "domain": domain,
        "industry": industry,
        "rating": rating,
        "reviews_count": reviews_count,
        "source": "serper_maps",
        "source_query": source_query,
        "sourced_at": timestamp,
        "status": "sourced",
        "pipeline_run_id": run_id,
    }
    lead["dedup_key"] = compute_dedup_key(lead)
    return lead


@retry_with_backoff(max_retries=3, base_delay=1.0)
def search_maps(query: str, limit: int, api_key: str) -> list[dict]:
    """Call Serper.dev Maps API and return raw place results."""
    resp = requests.post(
        SERPER_MAPS_URL,
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json={"q": query, "num": limit},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("places", [])


def parse_serper_results(
    raw_places: list[dict], query: str, industry: str, run_id: str, timestamp: str
) -> list[dict]:
    """Transform raw Serper places into pipeline lead records."""
    leads = []
    for place in raw_places:
        lead = _build_lead(
            business_name=place.get("title", ""),
            address=place.get("address", ""),
            phone=place.get("phoneNumber", ""),
            website=place.get("website", ""),
            rating=place.get("rating"),
            reviews_count=place.get("reviewsCount") or place.get("reviews"),
            industry=industry,
            source_query=query,
            run_id=run_id,
            timestamp=timestamp,
        )
        if lead["business_name"]:
            leads.append(lead)
    return leads


def run_single_query(
    query: str, industry: str, limit: int, api_key: str, run_id: str
) -> list[dict]:
    """Run a single Serper Maps query and return parsed leads."""
    logger.info("Querying Serper Maps: %s (limit=%d)", query, limit)
    raw = search_maps(query, limit, api_key)
    logger.info("Got %d results for '%s'", len(raw), query)
    return parse_serper_results(raw, query, industry, run_id, now_iso())


def run_from_config(config_path: str, api_key: str, run_id: str) -> list[dict]:
    """Run all ICP niches x cities from config and return merged, deduplicated leads."""
    config = load_config(config_path)
    icp = config["icp"]
    sourcing = config.get("sourcing", {})
    limit = sourcing.get("serper_results_per_query", 100)
    prospeo_niches = set(sourcing.get("use_prospeo_for", []))

    industries = [i for i in icp["industries"] if i not in prospeo_niches]
    geo = icp["geography"]
    cities = [f"{geo['city']}, {geo['state']}"]
    if geo.get("include_suburbs"):
        cities.extend(f"{s}, {geo['state']}" for s in geo.get("suburbs", []))

    all_leads = []
    for industry in industries:
        for city in cities:
            query = f"{industry} {city}"
            try:
                leads = run_single_query(query, industry, limit, api_key, run_id)
                all_leads.extend(leads)
            except Exception:
                logger.exception("Failed query: %s", query)

    logger.info("Total raw leads from Serper: %d", len(all_leads))
    return deduplicate(all_leads)


def main():
    parser = argparse.ArgumentParser(
        description="Scrape Google Maps business listings via Serper.dev"
    )
    parser.add_argument("--query", help="Single search query (e.g. 'car wash Houston TX')")
    parser.add_argument("--industry", help="Industry label for --query mode", default="")
    parser.add_argument("--config", help="Path to config JSON (runs all ICP niches)")
    parser.add_argument("--limit", type=int, default=100, help="Max results per query")
    parser.add_argument("--output", default=str(ROOT / ".tmp" / "serper_leads.json"))
    parser.add_argument("--mock", action="store_true", help="Use mock data")
    args = parser.parse_args()

    (ROOT / ".tmp").mkdir(exist_ok=True)
    run_id = generate_run_id()

    if args.mock:
        logger.info("Running in MOCK mode")
        leads = get_mock_data()
    elif args.query:
        api_key = os.environ.get("SERPER_API_KEY")
        if not api_key:
            logger.error("SERPER_API_KEY not set. Add it to .env or pass as env var.")
            sys.exit(1)
        leads = run_single_query(args.query, args.industry or args.query.split()[0], args.limit, api_key, run_id)
        leads = deduplicate(leads)
    elif args.config:
        api_key = os.environ.get("SERPER_API_KEY")
        if not api_key:
            logger.error("SERPER_API_KEY not set. Add it to .env or pass as env var.")
            sys.exit(1)
        leads = run_from_config(args.config, api_key, run_id)
    else:
        parser.error("Provide --query, --config, or --mock")
        return

    output_path = save_leads(leads, args.output)
    logger.info("Saved %d leads to %s", len(leads), output_path)

    industries = {}
    for lead in leads:
        ind = lead.get("industry", "unknown")
        industries[ind] = industries.get(ind, 0) + 1
    for ind, count in sorted(industries.items()):
        logger.info("  %s: %d leads", ind, count)


if __name__ == "__main__":
    main()
