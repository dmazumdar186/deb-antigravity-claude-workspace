#!/usr/bin/env python3
"""
Scrape leads using Apify's code_crafter/leads-finder actor.
"""

import os
import sys
import json
import argparse
from datetime import datetime
from dotenv import load_dotenv
from apify_client import ApifyClient

# Load environment variables
load_dotenv()

def scrape_leads(query, location, max_items, job_titles=None, company_keywords=None, require_email=True):
    """
    Run the Apify actor to scrape leads.
    """
    api_token = os.getenv("APIFY_API_TOKEN")
    if not api_token:
        print("Error: APIFY_API_TOKEN not found in .env", file=sys.stderr)
        return None

    client = ApifyClient(api_token)

    # Prepare the actor input
    # Based on documentation: https://apify.com/code_crafter/leads-finder#input-schema-fields-you-can-use
    # Allow separate job titles and company keywords for better targeting
    run_input = {
        "fetch_count": int(max_items),
        "contact_job_title": job_titles if job_titles else [query],
        "company_keywords": company_keywords if company_keywords else [query],
        "contact_location": [location.lower()],
        "language": "en",
    }

    # Only add email filter if required
    if require_email:
        run_input["email_status"] = ["validated"]

    print(f"Starting scrape for '{query}' in '{location}' (Limit: {max_items})...")
    print(f"Debug: run_input = {json.dumps(run_input, indent=2)}")
    
    try:
        # Run the actor and wait for it to finish
        run = client.actor("code_crafter/leads-finder").call(run_input=run_input)
    except Exception as e:
        print(f"Error running actor: {e}") # Print to stdout
        return None

    if not run:
        print("Error: Actor run failed to start", file=sys.stderr)
        return None

    print(f"Scrape finished. Fetching results from dataset {run['defaultDatasetId']}...")

    # Fetch results from the actor's default dataset
    results = []
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        results.append(item)
            
    return results

def save_results(results, prefix="leads"):
    """
    Save results to a JSON file.
    """
    if not results:
        print("No results to save.")
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # If prefix includes a directory path, use it directly; otherwise default to active/
    if "/" in prefix:
        filename = f"{prefix}_{timestamp}.json"
        os.makedirs(os.path.dirname(filename), exist_ok=True)
    else:
        output_dir = "active"
        os.makedirs(output_dir, exist_ok=True)
        filename = f"{output_dir}/{prefix}_{timestamp}.json"
    
    with open(filename, "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"Results saved to {filename}")
    return filename

def main():
    parser = argparse.ArgumentParser(description="Scrape leads using Apify")
    parser.add_argument("--query", required=True, help="Search query (e.g., 'Plumbers')")
    parser.add_argument("--location", required=True, help="Location (e.g., 'New York')")
    parser.add_argument("--max_items", type=int, default=25, help="Maximum number of items to scrape")
    parser.add_argument("--output_prefix", default="leads", help="Prefix for the output file")
    parser.add_argument("--job_titles", nargs='+', help="Specific job titles to target (e.g., CEO Founder)")
    parser.add_argument("--company_keywords", nargs='+', help="Company keywords to filter (e.g., 'software' 'SaaS')")
    parser.add_argument("--no-email-filter", action="store_true", help="Don't filter by validated emails (faster, larger results)")

    args = parser.parse_args()

    require_email = not args.no_email_filter
    results = scrape_leads(args.query, args.location, args.max_items, args.job_titles, args.company_keywords, require_email)
    
    if results:
        print(f"Found {len(results)} leads.")
        save_results(results, prefix=args.output_prefix)
    else:
        print("No leads found or error occurred.")
        sys.exit(1)

if __name__ == "__main__":
    main()
