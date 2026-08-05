"""HubSpot CRM adapter.

description: List/get/create/update HubSpot contacts + verify HubSpot webhooks.
inputs:      HUBSPOT_ACCESS_TOKEN (private-app token) in env
outputs:     dicts matching HubSpot v3 contact shape

Reference: https://developers.hubspot.com/docs/api/crm/contacts
Rate limit reference: https://developers.hubspot.com/docs/api/usage-details
  (Free / Starter: 100 req / 10 s. Enterprise: 190 req / 10 s.)

Webhook signature v3 spec:
  https://developers.hubspot.com/docs/api/webhooks/validating-requests
  Formula: HMAC-SHA256(app_secret, requestMethod + requestURI + requestBody + timestamp)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Any, Iterator

from .base import Adapter


class HubSpotAdapter(Adapter):
    REQUESTS_PER_WINDOW = 100
    WINDOW_SECONDS = 10

    BASE = "https://api.hubapi.com"

    def __init__(self, tenant_config: dict[str, Any]) -> None:
        super().__init__(tenant_config)
        token = os.environ.get("HUBSPOT_ACCESS_TOKEN", "")
        if not token:
            # Schema validation should have caught this — defense in depth.
            raise RuntimeError("HUBSPOT_ACCESS_TOKEN missing at HubSpotAdapter init")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # ---- helpers ----------------------------------------------------------
    def _client(self):
        try:
            import httpx
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "httpx missing. pip install httpx>=0.27"
            ) from e
        return httpx.Client(headers=self._headers, timeout=30.0)

    # ---- Adapter interface -------------------------------------------------
    def list_records(self, since_watermark: str | None) -> Iterator[dict[str, Any]]:
        """Paginated search for contacts modified since `since_watermark`.

        Uses /crm/v3/objects/contacts/search with lastmodifieddate GT filter
        when a watermark is provided, else /crm/v3/objects/contacts.
        """
        page_after: str | None = None
        while True:
            self._rate_gate()
            with self._client() as c:
                if since_watermark:
                    body: dict[str, Any] = {
                        "filterGroups": [
                            {
                                "filters": [
                                    {
                                        "propertyName": "lastmodifieddate",
                                        "operator": "GT",
                                        "value": since_watermark,
                                    }
                                ]
                            }
                        ],
                        "sorts": [{"propertyName": "lastmodifieddate", "direction": "ASCENDING"}],
                        "limit": 100,
                    }
                    if page_after:
                        body["after"] = page_after
                    r = c.post(f"{self.BASE}/crm/v3/objects/contacts/search", json=body)
                else:
                    params: dict[str, Any] = {"limit": 100}
                    if page_after:
                        params["after"] = page_after
                    r = c.get(f"{self.BASE}/crm/v3/objects/contacts", params=params)
                r.raise_for_status()
                payload = r.json()

            for record in payload.get("results", []):
                yield record

            paging = payload.get("paging", {}).get("next", {})
            page_after = paging.get("after")
            if not page_after:
                break

    def get_record(self, record_id: str) -> dict[str, Any]:
        self._rate_gate()
        with self._client() as c:
            r = c.get(f"{self.BASE}/crm/v3/objects/contacts/{record_id}")
            r.raise_for_status()
            return r.json()

    def create_record(self, provider_payload: dict[str, Any]) -> dict[str, Any]:
        self._rate_gate()
        with self._client() as c:
            r = c.post(
                f"{self.BASE}/crm/v3/objects/contacts",
                json={"properties": provider_payload.get("properties", provider_payload)},
            )
            r.raise_for_status()
            return r.json()

    def update_record(
        self, record_id: str, provider_payload: dict[str, Any]
    ) -> dict[str, Any]:
        self._rate_gate()
        with self._client() as c:
            r = c.patch(
                f"{self.BASE}/crm/v3/objects/contacts/{record_id}",
                json={"properties": provider_payload.get("properties", provider_payload)},
            )
            r.raise_for_status()
            return r.json()

    def subscribe_webhook(self, target_url: str, secret: str) -> dict[str, Any]:
        """HubSpot webhook subscriptions are created against a private app.
        This method is a stub because HubSpot requires an OAuth app or a
        webhook-subscription API call scoped to the app id, which varies per
        tenant. Real setup: HubSpot UI -> Settings -> Integrations -> Private
        apps -> Webhooks. Log the target for audit.
        """
        return {
            "provider": "hubspot",
            "target_url": target_url,
            "note": "HubSpot webhooks must be registered in-app; see README.",
        }

    def verify_webhook_signature(
        self, raw_body: bytes, signature_header: str, secret: str
    ) -> bool:
        """HubSpot v3 signature: base64(HMAC-SHA256(secret, method+uri+body+timestamp)).

        The webhook receiver must pass the concatenated string as raw_body
        (i.e. method + uri + body + timestamp). If the caller only has the
        body, this defaults to a simple body-HMAC — that's NOT a valid v3
        check, so the receiver should always build the v3 string.
        """
        computed = base64.b64encode(
            hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
        ).decode("ascii")
        return hmac.compare_digest(computed, signature_header.strip())
