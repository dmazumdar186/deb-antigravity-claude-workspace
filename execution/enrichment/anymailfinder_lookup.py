#!/usr/bin/env python3
"""
anymailfinder_lookup.py
description: Find business owner emails via AnymailFinder API.
inputs: --input, --output, --min-confidence, --mock; env: ANYMAILFINDER_API_KEY
outputs: .tmp/enriched_leads.json
usage:
    py execution/enrichment/anymailfinder_lookup.py --input .tmp/serper_leads.json --mock
    py execution/enrichment/anymailfinder_lookup.py --input .tmp/serper_leads.json
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
    load_leads,
    now_iso,
    retry_with_backoff,
    save_leads,
    setup_logging,
)

load_dotenv(ROOT / ".env")
logger = setup_logging("anymailfinder", log_dir=ROOT / ".tmp")

ANYMAILFINDER_PERSON_URL = "https://api.anymailfinder.com/v5.0/search/person.json"
ANYMAILFINDER_COMPANY_URL = "https://api.anymailfinder.com/v5.0/search/company.json"

MOCK_EMAILS = {
    "sparklecarwash.com": {"email": "john.miller@sparklecarwash.com", "name": "John Miller", "confidence": 92, "type": "personal"},
    "houstonhandwash.com": {"email": "sarah.jones@houstonhandwash.com", "name": "Sarah Jones", "confidence": 88, "type": "personal"},
    "tonyspizzapalace.com": {"email": "tony.rossi@tonyspizzapalace.com", "name": "Tony Rossi", "confidence": 95, "type": "personal"},
    "napolipizzeria.com": {"email": "info@napolipizzeria.com", "name": "", "confidence": 60, "type": "generic"},
    "cleanfreshlaundry.com": {"email": "mike.tran@cleanfreshlaundry.com", "name": "Mike Tran", "confidence": 85, "type": "personal"},
    "bayoumarina.com": {"email": "david.jackson@bayoumarina.com", "name": "David Jackson", "confidence": 78, "type": "personal"},
    "gulfcoastauto.com": {"email": "carlos.mendez@gulfcoastauto.com", "name": "Carlos Mendez", "confidence": 91, "type": "personal"},
    "lonestardrycleaning.com": {"email": "linda.nguyen@lonestardrycleaning.com", "name": "Linda Nguyen", "confidence": 87, "type": "personal"},
    "sugarpest.com": {"email": "ryan.taylor@sugarpest.com", "name": "Ryan Taylor", "confidence": 94, "type": "personal"},
    "katyfreshbakery.com": {"email": "anna.schmidt@katyfreshbakery.com", "name": "Anna Schmidt", "confidence": 90, "type": "personal"},
}


@retry_with_backoff(max_retries=3, base_delay=1.0)
def find_email_person(domain: str, first_name: str, last_name: str, api_key: str) -> dict | None:
    """Find email by person name + domain. Use when owner name is known."""
    resp = requests.post(
        ANYMAILFINDER_PERSON_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"domain": domain, "first_name": first_name, "last_name": last_name},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results", {})

    email = results.get("email")
    if not email:
        return None

    return {
        "email": email,
        "name": f"{first_name} {last_name}".strip(),
        "confidence": 90 if results.get("validation") == "valid" else 60,
        "type": "generic" if _is_generic(email) else "personal",
    }


@retry_with_backoff(max_retries=3, base_delay=1.0)
def find_email_company(domain: str, company_name: str, api_key: str) -> dict | None:
    """Find email by domain + company name. Fallback when no owner name available."""
    resp = requests.post(
        ANYMAILFINDER_COMPANY_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"domain": domain, "company_name": company_name},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results", {})

    emails = results.get("emails", [])
    if not emails:
        return None

    email = emails[0]
    return {
        "email": email,
        "name": "",
        "confidence": 70 if results.get("validation") == "valid" else 50,
        "type": "generic" if _is_generic(email) else "personal",
    }


def find_email(domain: str, company_name: str, api_key: str, owner_name: str = "") -> dict | None:
    """Try person search first (if name available), fall back to company search."""
    if owner_name and " " in owner_name.strip():
        parts = owner_name.strip().split(None, 1)
        result = find_email_person(domain, parts[0], parts[1], api_key)
        if result:
            return result

    return find_email_company(domain, company_name, api_key)


def _is_generic(email: str) -> bool:
    """Check if an email is a generic address (info@, contact@, etc.)."""
    generic_prefixes = {"info", "contact", "admin", "support", "hello", "office", "sales", "team"}
    local = email.split("@")[0].lower()
    return local in generic_prefixes


def enrich_lead(lead: dict, api_key: str, min_confidence: int, mock: bool) -> dict:
    """Add email data to a lead record."""
    domain = lead.get("domain", "")

    if lead.get("owner_email"):
        logger.debug("Skipping %s — already has email", lead.get("business_name"))
        return lead

    if not domain:
        lead["status"] = "no_domain"
        logger.debug("Skipping %s — no domain", lead.get("business_name"))
        return lead

    if mock:
        result = MOCK_EMAILS.get(domain)
    else:
        try:
            result = find_email(domain, lead.get("business_name", ""), api_key, lead.get("owner_name", ""))
        except Exception:
            logger.exception("AnymailFinder error for %s", domain)
            lead["status"] = "error"
            lead["error_message"] = f"AnymailFinder lookup failed for {domain}"
            return lead

    if not result:
        lead["status"] = "no_email_found"
        return lead

    if result["confidence"] < min_confidence:
        lead["status"] = "low_confidence"
        lead["email_confidence"] = result["confidence"]
        logger.debug(
            "Low confidence (%d) for %s, skipping", result["confidence"], domain
        )
        return lead

    lead["owner_name"] = result["name"] or lead.get("owner_name", "")
    lead["owner_email"] = result["email"]
    lead["email_confidence"] = result["confidence"]
    lead["email_type"] = result["type"]
    lead["enriched_at"] = now_iso()
    lead["status"] = "enriched"
    return lead


def main():
    parser = argparse.ArgumentParser(
        description="Find business owner emails via AnymailFinder"
    )
    parser.add_argument("--input", required=True, help="Path to sourced leads JSON")
    parser.add_argument("--output", default=str(ROOT / ".tmp" / "enriched_leads.json"))
    parser.add_argument("--min-confidence", type=int, default=50)
    parser.add_argument("--mock", action="store_true", help="Use mock data")
    args = parser.parse_args()

    (ROOT / ".tmp").mkdir(exist_ok=True)

    api_key = ""
    if not args.mock:
        api_key = os.environ.get("ANYMAILFINDER_API_KEY", "")
        if not api_key:
            logger.error("ANYMAILFINDER_API_KEY not set.")
            sys.exit(1)

    leads = load_leads(args.input)
    logger.info("Loaded %d leads from %s", len(leads), args.input)

    stats = {"total": 0, "enriched": 0, "no_domain": 0, "no_email": 0, "low_confidence": 0, "error": 0, "skipped": 0}

    for lead in leads:
        stats["total"] += 1
        enriched = enrich_lead(lead, api_key, args.min_confidence, args.mock)
        status = enriched.get("status", "")
        if status == "enriched":
            stats["enriched"] += 1
        elif status == "no_domain":
            stats["no_domain"] += 1
        elif status == "no_email_found":
            stats["no_email"] += 1
        elif status == "low_confidence":
            stats["low_confidence"] += 1
        elif status == "error":
            stats["error"] += 1
        else:
            stats["skipped"] += 1

    output_path = save_leads(leads, args.output)
    logger.info("Saved %d leads to %s", len(leads), output_path)
    logger.info(
        "Stats — total: %d, enriched: %d, no_domain: %d, no_email: %d, low_confidence: %d, errors: %d",
        stats["total"], stats["enriched"], stats["no_domain"],
        stats["no_email"], stats["low_confidence"], stats["error"],
    )


if __name__ == "__main__":
    main()
