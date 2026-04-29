"""
ghl.py
description: Reusable GoHighLevel V2 API client — contact and opportunity creation.
inputs: API key (env), location ID, pipeline config, contact/reply data.
outputs: Created contact ID, opportunity ID.
"""

import logging

import requests

from modules.pipeline_utils import retry_with_backoff

logger = logging.getLogger(__name__)

DEFAULT_API_VERSION = "2021-07-28"


def _build_headers(api_key: str, api_version: str | None = None) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Version": api_version or DEFAULT_API_VERSION,
    }


@retry_with_backoff(max_retries=3, base_delay=2.0)
def create_contact(
    api_url: str,
    api_key: str,
    location_id: str,
    contact_data: dict,
    tags: list[str] | None = None,
    custom_fields: list[dict] | None = None,
    api_version: str | None = None,
) -> str | None:
    """Create a contact in GHL. Returns the contact ID or None on failure."""
    payload = {
        "locationId": location_id,
        **contact_data,
    }
    if tags:
        payload["tags"] = tags
    if custom_fields:
        payload["customFields"] = custom_fields

    resp = requests.post(
        f"{api_url}/contacts/",
        headers=_build_headers(api_key, api_version),
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    contact_id = resp.json().get("contact", {}).get("id")
    logger.info("Created GHL contact: %s", contact_id)
    return contact_id


@retry_with_backoff(max_retries=3, base_delay=2.0)
def create_opportunity(
    api_url: str,
    api_key: str,
    pipeline_id: str,
    stage_id: str,
    contact_id: str,
    name: str,
    status: str = "open",
    monetary_value: float | None = None,
    api_version: str | None = None,
) -> str | None:
    """Create an opportunity in GHL. Returns the opportunity ID or None."""
    payload = {
        "pipelineId": pipeline_id,
        "stageId": stage_id,
        "contactId": contact_id,
        "name": name,
        "status": status,
    }
    if monetary_value is not None:
        payload["monetaryValue"] = monetary_value

    resp = requests.post(
        f"{api_url}/opportunities/",
        headers=_build_headers(api_key, api_version),
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    opp_id = resp.json().get("opportunity", {}).get("id")
    logger.info("Created GHL opportunity: %s", opp_id)
    return opp_id


def route_positive_reply(
    api_url: str,
    api_key: str,
    location_id: str,
    pipeline_id: str | None,
    stage_id: str | None,
    reply: dict,
    tags: list[str] | None = None,
    source: str = "cold email pipeline",
    api_version: str | None = None,
) -> dict:
    """Create a contact + opportunity for a positive reply. Returns result summary."""
    name_parts = (reply.get("from_name", "") or "").split()
    first_name = name_parts[0] if name_parts else ""
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

    result = {"contact_id": None, "opportunity_id": None, "error": None}

    if not location_id:
        logger.warning("GHL location_id not configured — skipping routing.")
        result["error"] = "location_id not configured"
        return result

    try:
        contact_id = create_contact(
            api_url=api_url,
            api_key=api_key,
            location_id=location_id,
            contact_data={
                "firstName": first_name,
                "lastName": last_name,
                "email": reply.get("from_email", ""),
                "companyName": reply.get("company", ""),
                "source": source,
            },
            tags=tags or ["cold email", "positive reply"],
            custom_fields=[
                {"key": "reply_text", "value": (reply.get("body", "") or "")[:500]},
            ],
            api_version=api_version,
        )
        result["contact_id"] = contact_id

        if pipeline_id and stage_id and contact_id:
            opp_name = f"{reply.get('from_name', 'Unknown')} — {reply.get('company', 'Unknown')}"
            opp_id = create_opportunity(
                api_url=api_url,
                api_key=api_key,
                pipeline_id=pipeline_id,
                stage_id=stage_id,
                contact_id=contact_id,
                name=opp_name,
                api_version=api_version,
            )
            result["opportunity_id"] = opp_id
        elif not pipeline_id or not stage_id:
            logger.warning("GHL pipeline_id/stage_id not configured — skipping opportunity creation.")

    except Exception:
        logger.exception("GHL routing failed for %s", reply.get("from_email"))
        result["error"] = "GHL API error"

    return result
