"""
instantly.py
description: Reusable Instantly.ai API client — lead upload with rate limiting and reply fetching.
inputs: API key (env), campaign ID, lead data, field mapping config.
outputs: Upload results, normalized reply data.
"""

import logging
import time

import requests

from modules.pipeline_utils import retry_with_backoff

logger = logging.getLogger(__name__)

DEFAULT_FIELD_MAPPING = {
    "email": "owner_email",
    "first_name_from": "owner_name",
    "last_name_from": "owner_name",
    "company_name": "business_name",
    "custom_variables": {
        "opener": "personalized_opener",
        "industry": "industry",
        "city": "city",
    },
}


def _parse_name(full_name: str) -> tuple[str, str]:
    parts = (full_name or "").split()
    first = parts[0] if parts else ""
    last = " ".join(parts[1:]) if len(parts) > 1 else ""
    return first, last


def _build_lead_payload(
    lead: dict, campaign_id: str, field_mapping: dict | None = None
) -> dict:
    mapping = field_mapping or DEFAULT_FIELD_MAPPING
    email = lead.get(mapping.get("email", "owner_email"), "")
    name_field = mapping.get("first_name_from", "owner_name")
    first_name, last_name = _parse_name(lead.get(name_field, ""))
    company = lead.get(mapping.get("company_name", "business_name"), "")

    custom_vars = {}
    for var_name, lead_field in mapping.get("custom_variables", {}).items():
        custom_vars[var_name] = lead.get(lead_field, "")

    return {
        "campaign": campaign_id,
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "company_name": company,
        "custom_variables": custom_vars,
    }


@retry_with_backoff(max_retries=3, base_delay=2.0)
def upload_lead(
    api_url: str, api_key: str, campaign_id: str, lead: dict,
    field_mapping: dict | None = None,
) -> dict:
    """Upload a single lead to Instantly. Returns the API response dict."""
    payload = _build_lead_payload(lead, campaign_id, field_mapping)
    resp = requests.post(
        f"{api_url}/leads",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def upload_leads(
    api_url: str,
    api_key: str,
    campaign_id: str,
    leads: list[dict],
    field_mapping: dict | None = None,
    rate_limit_delay: float = 1.0,
) -> dict:
    """Upload a batch of leads with rate limiting. Returns summary dict."""
    uploaded = 0
    errors = 0

    for i, lead in enumerate(leads):
        try:
            result = upload_lead(api_url, api_key, campaign_id, lead, field_mapping)
            lead["uploaded_to_instantly"] = True
            lead["campaign_id"] = campaign_id
            lead["instantly_lead_id"] = result.get("id")
            lead["status"] = "uploaded"
            uploaded += 1
        except Exception:
            logger.exception("Failed to upload lead %s", lead.get("owner_email", "?"))
            lead["status"] = "error"
            lead["error_message"] = "Instantly upload failed"
            errors += 1

        if i < len(leads) - 1:
            time.sleep(rate_limit_delay)

    logger.info("Instantly upload: %d succeeded, %d failed out of %d", uploaded, errors, len(leads))
    return {"uploaded": uploaded, "errors": errors, "total": len(leads)}


@retry_with_backoff(max_retries=3, base_delay=2.0)
def fetch_replies(
    api_url: str, api_key: str, params: dict | None = None,
) -> list[dict]:
    """Fetch replies from Instantly Unibox API. Returns raw reply list."""
    default_params = {"email_type": "received", "limit": 50}
    if params:
        default_params.update(params)

    resp = requests.get(
        f"{api_url}/unibox/emails",
        headers={"Authorization": f"Bearer {api_key}"},
        params=default_params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def normalize_reply(raw: dict) -> dict:
    """Map Instantly API reply fields to internal format."""
    return {
        "from_email": raw.get("from_address_email", raw.get("from_email", "")),
        "from_name": raw.get("from_address_name", raw.get("from_name", "")),
        "subject": raw.get("subject", ""),
        "body": raw.get("body", raw.get("text_body", "")),
        "company": raw.get("company_name", raw.get("company", "")),
        "received_at": raw.get("timestamp", raw.get("received_at", "")),
        "campaign_id": raw.get("campaign_id", ""),
        "lead_email": raw.get("to_address_email", ""),
    }


def normalize_replies(raw_replies: list[dict]) -> list[dict]:
    """Normalize a batch of raw Instantly replies."""
    return [normalize_reply(r) for r in raw_replies]


@retry_with_backoff(max_retries=3, base_delay=2.0)
def fetch_step_analytics(
    api_url: str, api_key: str, campaign_id: str,
) -> list[dict]:
    """Fetch per-step campaign analytics from Instantly for variant tracking."""
    resp = requests.get(
        f"{api_url}/campaigns/{campaign_id}/analytics/steps",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    steps = data.get("steps", data.get("data", []))

    results = []
    for i, step in enumerate(steps):
        sent = step.get("total_sent", step.get("sent", 0))
        replied = step.get("total_replied", step.get("replied", 0))
        results.append({
            "step_id": step.get("id", step.get("step_id", f"step_{i}")),
            "label": step.get("subject", step.get("name", f"Step {i + 1}")),
            "emails_sent": sent,
            "replies": replied,
            "response_rate_pct": round(replied / sent * 100, 1) if sent > 0 else 0.0,
        })

    return results
