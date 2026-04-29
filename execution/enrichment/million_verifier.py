#!/usr/bin/env python3
"""
million_verifier.py
description: Verify email deliverability via Million Verifier API.
inputs: --input, --output, --accept, --mock; env: MILLION_VERIFIER_API_KEY
outputs: .tmp/verified_leads.json
usage:
    py execution/enrichment/million_verifier.py --input .tmp/enriched_leads.json --mock
    py execution/enrichment/million_verifier.py --input .tmp/enriched_leads.json
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
logger = setup_logging("million_verifier", log_dir=ROOT / ".tmp")

MV_API_URL = "https://api.millionverifier.com/api/v3"

MOCK_RESULTS = {
    "john.miller@sparklecarwash.com": {"result": "ok", "quality_score": 97},
    "sarah.jones@houstonhandwash.com": {"result": "ok", "quality_score": 95},
    "tony.rossi@tonyspizzapalace.com": {"result": "ok", "quality_score": 99},
    "info@napolipizzeria.com": {"result": "catch_all", "quality_score": 70},
    "mike.tran@cleanfreshlaundry.com": {"result": "ok", "quality_score": 93},
    "david.jackson@bayoumarina.com": {"result": "ok", "quality_score": 91},
    "carlos.mendez@gulfcoastauto.com": {"result": "ok", "quality_score": 96},
    "linda.nguyen@lonestardrycleaning.com": {"result": "invalid", "quality_score": 0},
    "ryan.taylor@sugarpest.com": {"result": "ok", "quality_score": 98},
    "anna.schmidt@katyfreshbakery.com": {"result": "ok", "quality_score": 94},
}


@retry_with_backoff(max_retries=3, base_delay=1.0)
def verify_email(email: str, api_key: str) -> dict:
    """Call Million Verifier single-email API. Returns result dict."""
    resp = requests.get(
        f"{MV_API_URL}/",
        params={"api": api_key, "email": email},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "result": data.get("result", "unknown"),
        "quality_score": data.get("quality", 0),
    }


def verify_lead(
    lead: dict, api_key: str, accept_results: set[str], mock: bool
) -> dict:
    """Verify a lead's email and update its status."""
    if lead.get("status") not in ("enriched",):
        return lead

    email = lead.get("owner_email", "")
    if not email:
        return lead

    if mock:
        result = MOCK_RESULTS.get(email, {"result": "unknown", "quality_score": 0})
    else:
        try:
            result = verify_email(email, api_key)
        except Exception:
            logger.exception("Million Verifier error for %s", email)
            lead["status"] = "error"
            lead["error_message"] = f"Million Verifier failed for {email}"
            return lead

    lead["email_verification_result"] = result["result"]
    lead["email_quality_score"] = result["quality_score"]
    lead["verified_at"] = now_iso()

    if result["result"] in accept_results:
        lead["email_verified"] = True
        lead["status"] = "verified"
    else:
        lead["email_verified"] = False
        lead["status"] = "email_invalid"
        logger.debug("Rejected %s — result: %s", email, result["result"])

    return lead


def main():
    parser = argparse.ArgumentParser(
        description="Verify email deliverability via Million Verifier"
    )
    parser.add_argument("--input", required=True, help="Path to enriched leads JSON")
    parser.add_argument("--output", default=str(ROOT / ".tmp" / "verified_leads.json"))
    parser.add_argument(
        "--accept",
        default="ok,catch_all",
        help="Comma-separated verification results to accept (default: ok,catch_all)",
    )
    parser.add_argument("--mock", action="store_true", help="Use mock data")
    args = parser.parse_args()

    (ROOT / ".tmp").mkdir(exist_ok=True)
    accept_results = set(args.accept.split(","))

    api_key = ""
    if not args.mock:
        api_key = os.environ.get("MILLION_VERIFIER_API_KEY", "")
        if not api_key:
            logger.error("MILLION_VERIFIER_API_KEY not set.")
            sys.exit(1)

    leads = load_leads(args.input)
    logger.info("Loaded %d leads from %s", len(leads), args.input)

    stats = {"total": 0, "verified": 0, "catch_all": 0, "invalid": 0, "unknown": 0, "error": 0, "skipped": 0}

    for lead in leads:
        stats["total"] += 1
        before_status = lead.get("status", "")

        verify_lead(lead, api_key, accept_results, args.mock)

        after_status = lead.get("status", "")
        if after_status == "verified":
            result = lead.get("email_verification_result", "")
            if result == "catch_all":
                stats["catch_all"] += 1
            else:
                stats["verified"] += 1
        elif after_status == "email_invalid":
            stats["invalid"] += 1
        elif after_status == "error":
            stats["error"] += 1
        elif before_status == after_status:
            stats["skipped"] += 1

    output_path = save_leads(leads, args.output)
    logger.info("Saved %d leads to %s", len(leads), output_path)
    logger.info(
        "Stats — total: %d, verified: %d, catch_all: %d, invalid: %d, unknown: %d, errors: %d, skipped: %d",
        stats["total"], stats["verified"], stats["catch_all"],
        stats["invalid"], stats["unknown"], stats["error"], stats["skipped"],
    )


if __name__ == "__main__":
    main()
