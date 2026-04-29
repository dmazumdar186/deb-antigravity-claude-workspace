#!/usr/bin/env python3
"""
prospeo_leads.py
description: Source B2B leads via Prospeo API for niches not indexed on Google Maps.
inputs: --domain, --company, --config, --output, --mock; env: PROSPEO_API_KEY
outputs: .tmp/prospeo_leads.json
usage:
    py execution/lead_sourcing/prospeo_leads.py --company "Houston Manufacturing Co" --mock
    py execution/lead_sourcing/prospeo_leads.py --config config/accessory_masters.json --mock
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
    normalize_domain,
    now_iso,
    retry_with_backoff,
    save_leads,
    setup_logging,
)

load_dotenv(ROOT / ".env")
logger = setup_logging("prospeo", log_dir=ROOT / ".tmp")

PROSPEO_BASE_URL = "https://api.prospeo.io"


def get_mock_data() -> list[dict]:
    """Return hardcoded B2B Houston business data for local testing."""
    run_id = generate_run_id()
    ts = now_iso()
    businesses = [
        {
            "company": "Houston Precision Manufacturing",
            "domain": "houstonprecision.com",
            "first_name": "Robert",
            "last_name": "Chen",
            "email": "robert@houstonprecision.com",
            "position": "Owner",
            "industry": "manufacturing",
            "address": "8900 Industrial Blvd, Houston, TX 77061",
        },
        {
            "company": "Gulf Coast Fabrication",
            "domain": "gcfab.com",
            "first_name": "Maria",
            "last_name": "Gonzalez",
            "email": "maria@gcfab.com",
            "position": "CEO",
            "industry": "manufacturing",
            "address": "3200 Clinton Dr, Houston, TX 77020",
        },
        {
            "company": "Bayou City Consulting",
            "domain": "bayoucityconsulting.com",
            "first_name": "James",
            "last_name": "Williams",
            "email": "james@bayoucityconsulting.com",
            "position": "Managing Partner",
            "industry": "professional services",
            "address": "1000 Main St Ste 2400, Houston, TX 77002",
        },
    ]
    leads = []
    for b in businesses:
        lead = _build_lead(b, run_id, ts)
        leads.append(lead)
    return leads


def _parse_address(address: str) -> tuple[str, str]:
    """Extract city and state from a full address string."""
    if not address:
        return ("", "")
    parts = [p.strip() for p in address.split(",")]
    if len(parts) >= 2:
        last = parts[-1].strip()
        tokens = last.split()
        state = tokens[0] if tokens else ""
        city = parts[-2].strip() if len(parts) >= 3 else ""
        return (city, state)
    return ("", "")


def _build_lead(record: dict, run_id: str, timestamp: str) -> dict:
    """Construct a pipeline lead record from a Prospeo result."""
    address = record.get("address", "")
    city, state = _parse_address(address)
    domain = normalize_domain(record.get("domain", ""))
    first = record.get("first_name", "")
    last = record.get("last_name", "")
    owner_name = f"{first} {last}".strip() if (first or last) else ""

    lead = {
        "business_name": record.get("company", ""),
        "address": address,
        "city": city,
        "state": state,
        "phone": record.get("phone", ""),
        "website": f"https://{domain}" if domain else "",
        "domain": domain,
        "industry": record.get("industry", ""),
        "rating": None,
        "reviews_count": None,
        "source": "prospeo",
        "source_query": record.get("company", ""),
        "sourced_at": timestamp,
        "status": "sourced",
        "pipeline_run_id": run_id,
        "owner_name": owner_name,
        "owner_email": record.get("email", ""),
        "owner_position": record.get("position", ""),
        "linkedin_url": record.get("linkedin_url", ""),
    }
    lead["dedup_key"] = compute_dedup_key(lead)
    return lead


@retry_with_backoff(max_retries=3, base_delay=1.0)
def search_by_domain(domain: str, api_key: str) -> list[dict]:
    """Search Prospeo for contacts at a given domain."""
    resp = requests.post(
        f"{PROSPEO_BASE_URL}/domain-search",
        headers={"Content-Type": "application/json"},
        json={"key": api_key, "domain": domain},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("response", {}).get("email_list", [])


@retry_with_backoff(max_retries=3, base_delay=1.0)
def search_by_company(company: str, api_key: str) -> list[dict]:
    """Search Prospeo for contacts at a given company name."""
    resp = requests.post(
        f"{PROSPEO_BASE_URL}/company-email-finder",
        headers={"Content-Type": "application/json"},
        json={"key": api_key, "company": company},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("response", {}).get("email_list", [])


def parse_prospeo_results(
    raw_results: list[dict], industry: str, run_id: str, timestamp: str
) -> list[dict]:
    """Transform raw Prospeo results into pipeline lead records."""
    leads = []
    for r in raw_results:
        record = {
            "company": r.get("company", ""),
            "domain": r.get("domain", ""),
            "first_name": r.get("first_name", ""),
            "last_name": r.get("last_name", ""),
            "email": r.get("email", ""),
            "position": r.get("position", ""),
            "linkedin_url": r.get("linkedin_url", ""),
            "industry": industry,
            "address": "",
        }
        lead = _build_lead(record, run_id, timestamp)
        if lead["business_name"] or lead["domain"]:
            leads.append(lead)
    return leads


def run_from_config(config_path: str, api_key: str, run_id: str) -> list[dict]:
    """Run Prospeo queries for all B2B niches listed in config."""
    config = load_config(config_path)
    sourcing = config.get("sourcing", {})
    prospeo_niches = sourcing.get("use_prospeo_for", [])

    if not prospeo_niches:
        logger.info("No Prospeo niches configured, skipping")
        return []

    geo = config["icp"]["geography"]
    all_leads = []

    for niche in prospeo_niches:
        query = f"{niche} {geo['city']} {geo['state']}"
        logger.info("Prospeo search: %s", query)
        try:
            raw = search_by_company(query, api_key)
            leads = parse_prospeo_results(raw, niche, run_id, now_iso())
            all_leads.extend(leads)
            logger.info("Got %d results for '%s'", len(leads), niche)
        except Exception:
            logger.exception("Failed Prospeo query: %s", query)

    logger.info("Total raw leads from Prospeo: %d", len(all_leads))
    return deduplicate(all_leads)


def main():
    parser = argparse.ArgumentParser(
        description="Source B2B leads via Prospeo API"
    )
    parser.add_argument("--domain", help="Search by domain (e.g. 'example.com')")
    parser.add_argument("--company", help="Search by company name")
    parser.add_argument("--config", help="Path to config JSON (runs all B2B niches)")
    parser.add_argument("--output", default=str(ROOT / ".tmp" / "prospeo_leads.json"))
    parser.add_argument("--mock", action="store_true", help="Use mock data")
    args = parser.parse_args()

    (ROOT / ".tmp").mkdir(exist_ok=True)
    run_id = generate_run_id()

    if args.mock:
        logger.info("Running in MOCK mode")
        leads = get_mock_data()
    elif args.domain:
        api_key = os.environ.get("PROSPEO_API_KEY")
        if not api_key:
            logger.error("PROSPEO_API_KEY not set.")
            sys.exit(1)
        raw = search_by_domain(args.domain, api_key)
        leads = parse_prospeo_results(raw, "", run_id, now_iso())
        leads = deduplicate(leads)
    elif args.company:
        api_key = os.environ.get("PROSPEO_API_KEY")
        if not api_key:
            logger.error("PROSPEO_API_KEY not set.")
            sys.exit(1)
        raw = search_by_company(args.company, api_key)
        leads = parse_prospeo_results(raw, "", run_id, now_iso())
        leads = deduplicate(leads)
    elif args.config:
        api_key = os.environ.get("PROSPEO_API_KEY")
        if not api_key:
            logger.error("PROSPEO_API_KEY not set.")
            sys.exit(1)
        leads = run_from_config(args.config, api_key, run_id)
    else:
        parser.error("Provide --domain, --company, --config, or --mock")
        return

    output_path = save_leads(leads, args.output)
    logger.info("Saved %d leads to %s", len(leads), output_path)


if __name__ == "__main__":
    main()
