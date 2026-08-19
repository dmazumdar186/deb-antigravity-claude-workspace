#!/usr/bin/env python3
"""
AnyMailFinder API Client - Email enrichment for lead generation.

This module provides a reusable client for finding emails via AnyMailFinder.
Uses the v5.1 API with success-based pricing (only charged for valid emails).

Environment Variables:
    ANYMAILFINDER_API_KEY: Your AnyMailFinder API key

Usage:
    from anymailfinder_client import get_client

    client = get_client()
    result = client.find_email(full_name="John Doe", domain="microsoft.com")
    if result["success"] and result["data"]["email_status"] == "valid":
        print(f"Found: {result['data']['email']}")
"""

import os
import time
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.anymailfinder.com/v5.1"


def get_headers() -> dict:
    """Get authorization headers for AnyMailFinder API."""
    api_key = os.getenv("ANYMAILFINDER_API_KEY")
    if not api_key:
        raise ValueError("ANYMAILFINDER_API_KEY not set in .env")
    return {
        "Authorization": api_key,
        "Content-Type": "application/json",
    }


class AnyMailFinderClient:
    """AnyMailFinder API client for email discovery."""

    def __init__(self):
        self.headers = get_headers()
        self.request_count = 0
        self.valid_count = 0
        self.not_found_count = 0

    def find_email(
        self,
        domain: Optional[str] = None,
        company_name: Optional[str] = None,
        full_name: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        timeout: int = 180,
    ) -> dict:
        """
        Find a person's email address.

        Args:
            domain: Company domain (preferred, e.g., "microsoft.com")
            company_name: Company name (fallback if no domain)
            full_name: Full name (e.g., "John Doe")
            first_name: First name (use with last_name if no full_name)
            last_name: Last name (use with first_name if no full_name)
            timeout: Request timeout in seconds (default 180, API recommendation)

        Returns:
            dict with keys:
                - success: bool
                - data: {email, email_status, valid_email} or None
                - error: error message if failed

        Notes:
            - Requires either domain OR company_name
            - Requires either full_name OR (first_name AND last_name)
            - Only charged for valid emails (risky/not_found are free)
        """
        url = f"{BASE_URL}/find-email/person"

        # Build payload
        payload = {}

        # Domain/company (at least one required)
        if domain:
            payload["domain"] = domain
        elif company_name:
            payload["company_name"] = company_name
        else:
            return {
                "success": False,
                "error": "Either domain or company_name is required",
                "data": None,
            }

        # Name (at least one form required)
        if full_name:
            payload["full_name"] = full_name
        elif first_name and last_name:
            payload["first_name"] = first_name
            payload["last_name"] = last_name
        else:
            return {
                "success": False,
                "error": "Either full_name or (first_name and last_name) is required",
                "data": None,
            }

        self.request_count += 1

        try:
            response = requests.post(
                url,
                json=payload,
                headers=self.headers,
                timeout=timeout,
            )
            return self._handle_response(response)
        except requests.Timeout:
            return {
                "success": False,
                "error": f"Request timed out after {timeout}s",
                "data": None,
            }
        except requests.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "data": None,
            }

    def find_emails_batch(
        self,
        leads: list[dict],
        delay_between_requests: float = 0.5,
        on_progress: Optional[callable] = None,
    ) -> list[dict]:
        """
        Find emails for a batch of leads.

        Args:
            leads: List of dicts with keys: full_name (or first_name+last_name),
                   domain (or company_name)
            delay_between_requests: Seconds to wait between requests (politeness)
            on_progress: Optional callback(index, total, result) for progress updates

        Returns:
            List of result dicts, each with original lead data + enrichment results
        """
        results = []
        total = len(leads)

        for i, lead in enumerate(leads):
            result = self.find_email(
                domain=lead.get("domain"),
                company_name=lead.get("company_name") or lead.get("company"),
                full_name=lead.get("full_name") or lead.get("name"),
                first_name=lead.get("first_name"),
                last_name=lead.get("last_name"),
            )

            # Track stats
            if result["success"]:
                status = result["data"].get("email_status", "unknown")
                if status == "valid":
                    self.valid_count += 1
                else:
                    self.not_found_count += 1

            # Combine original lead data with result
            enriched = {**lead, "enrichment": result}
            results.append(enriched)

            if on_progress:
                on_progress(i + 1, total, result)

            # Rate limiting (polite delay)
            if i < total - 1:
                time.sleep(delay_between_requests)

        return results

    def get_stats(self) -> dict:
        """Get enrichment statistics for this session."""
        return {
            "total_requests": self.request_count,
            "valid_emails": self.valid_count,
            "not_found": self.not_found_count,
            "success_rate": (
                self.valid_count / self.request_count * 100
                if self.request_count > 0
                else 0
            ),
        }

    # ─────────────────────────────────────────────────────────────
    # Bulk API Methods
    # ─────────────────────────────────────────────────────────────

    def create_bulk_search(
        self,
        leads: list[dict],
        file_name: Optional[str] = None,
    ) -> dict:
        """
        Create a bulk email search job.

        Args:
            leads: List of dicts with keys: domain, first_name, last_name
            file_name: Optional label for the search

        Returns:
            dict with search ID and status
        """
        url = f"{BASE_URL}/bulk/json"

        # Build data array with header row
        data = [["domain", "first_name", "last_name"]]
        for lead in leads:
            domain = lead.get("domain", "")
            first_name = lead.get("first_name", "")
            last_name = lead.get("last_name", "")
            if domain and (first_name or last_name):
                data.append([domain, first_name, last_name])

        payload = {
            "data": data,
            "domain_field_index": 0,
            "first_name_field_index": 1,
            "last_name_field_index": 2,
        }
        if file_name:
            payload["file_name"] = file_name

        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=60)
            return self._handle_response(response)
        except Exception as e:
            return {"success": False, "error": str(e), "data": None}

    def get_bulk_search_status(self, search_id: str) -> dict:
        """
        Get the status of a bulk search.

        Args:
            search_id: The bulk search ID

        Returns:
            dict with status and counts
        """
        url = f"{BASE_URL}/bulk/{search_id}"
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            return self._handle_response(response)
        except Exception as e:
            return {"success": False, "error": str(e), "data": None}

    def download_bulk_results(
        self,
        search_id: str,
        format: str = "json_arr",
    ) -> dict:
        """
        Download results from a completed bulk search.

        Args:
            search_id: The bulk search ID
            format: Output format (csv, xlsx, json_arr, json_obj)

        Returns:
            dict with results data
        """
        url = f"{BASE_URL}/bulk/{search_id}/download"
        params = {"download_as": format}
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=120)
            if format in ("json_arr", "json_obj"):
                return self._handle_response(response)
            else:
                # For CSV/XLSX, return raw content
                if response.status_code == 200:
                    return {"success": True, "data": response.content}
                else:
                    return {"success": False, "error": response.text, "status_code": response.status_code}
        except Exception as e:
            return {"success": False, "error": str(e), "data": None}

    def bulk_enrich(
        self,
        leads: list[dict],
        file_name: Optional[str] = None,
        poll_interval: int = 5,
        timeout: int = 600,
        on_progress: Optional[callable] = None,
    ) -> dict:
        """
        Run bulk enrichment and wait for results.

        Args:
            leads: List of dicts with domain, first_name, last_name
            file_name: Optional label
            poll_interval: Seconds between status checks
            timeout: Max seconds to wait
            on_progress: Optional callback(status_dict)

        Returns:
            dict with enriched results
        """
        # Create the bulk search
        create_result = self.create_bulk_search(leads, file_name)
        if not create_result["success"]:
            return create_result

        search_id = create_result["data"].get("id")
        if not search_id:
            return {"success": False, "error": "No search ID returned", "data": create_result["data"]}

        print(f"  Bulk search created: ID {search_id}")

        # Poll for completion
        start_time = time.time()
        while True:
            status_result = self.get_bulk_search_status(search_id)
            if not status_result["success"]:
                return status_result

            status = status_result["data"].get("status", "unknown")
            counts = status_result["data"].get("counts", {})

            if on_progress:
                on_progress(status_result["data"])

            print(f"  Status: {status} | Found: {counts.get('found_valid', 0)} | Not found: {counts.get('not_found', 0)}")

            if status == "completed":
                break
            elif status in ("failed", "cancelled"):
                return {"success": False, "error": f"Bulk search {status}", "data": status_result["data"]}

            if time.time() - start_time > timeout:
                return {"success": False, "error": f"Timeout after {timeout}s", "data": status_result["data"]}

            time.sleep(poll_interval)

        # Download results (json_obj returns list of dicts)
        print(f"  Downloading results...")
        download_result = self.download_bulk_results(search_id, format="json_obj")
        if not download_result["success"]:
            return download_result

        # Results could be in data directly or nested
        results = download_result["data"]
        if isinstance(results, dict):
            results = results.get("data", results.get("results", []))

        # Normalize results and update stats
        if isinstance(results, list):
            for r in results:
                if isinstance(r, dict):
                    # Normalize field names (bulk API uses 'amf_status')
                    if "amf_status" in r and "email_status" not in r:
                        r["email_status"] = r["amf_status"]
                    # Bulk API returns "ok" for valid emails (not "valid")
                    status = r.get("email_status") or r.get("amf_status") or ""
                    if status in ("valid", "ok"):
                        self.valid_count += 1
                    else:
                        self.not_found_count += 1
            self.request_count += len(results)

        return {"success": True, "data": results, "search_id": search_id}

    def _handle_response(self, response: requests.Response, raw: bool = False) -> dict:
        """Handle API response and normalize format."""
        if response.status_code == 200:
            data = response.json()
            # For bulk endpoints or lists, return raw data
            if raw or isinstance(data, list):
                return {"success": True, "data": data}
            if isinstance(data, dict) and (data.get("id") or data.get("counts")):
                return {"success": True, "data": data}
            # For single email lookup, normalize
            return {
                "success": True,
                "data": {
                    "email": data.get("email") if isinstance(data, dict) else None,
                    "email_status": data.get("email_status") if isinstance(data, dict) else None,
                    "valid_email": data.get("valid_email") if isinstance(data, dict) else None,
                },
            }
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get("message", error_data.get("error", str(error_data)))
            except Exception:
                error_msg = response.text or f"HTTP {response.status_code}"
            return {
                "success": False,
                "error": error_msg,
                "status_code": response.status_code,
                "data": None,
            }


def get_client() -> AnyMailFinderClient:
    """Get a configured AnyMailFinder client instance."""
    return AnyMailFinderClient()


if __name__ == "__main__":
    # Quick test
    import argparse

    parser = argparse.ArgumentParser(description="Test AnyMailFinder API")
    parser.add_argument("--name", required=True, help="Full name to search")
    parser.add_argument("--domain", required=True, help="Company domain")
    args = parser.parse_args()

    try:
        client = get_client()
        print(f"Searching for {args.name} at {args.domain}...")
        result = client.find_email(full_name=args.name, domain=args.domain)

        if result["success"]:
            data = result["data"]
            print(f"  Status: {data['email_status']}")
            if data["email"]:
                print(f"  Email: {data['email']}")
            else:
                print("  No email found")
        else:
            print(f"  Error: {result['error']}")
    except ValueError as e:
        print(f"Setup error: {e}")
