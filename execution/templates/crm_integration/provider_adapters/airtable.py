"""Airtable adapter.

Reference: https://airtable.com/developers/web/api
Rate limit: 5 req/s per base (hard).
Webhook signature: MAC computed per Airtable webhooks v0 spec.
  https://airtable.com/developers/web/api/model/webhooks
"""
from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any, Iterator

from .base import Adapter


class AirtableAdapter(Adapter):
    REQUESTS_PER_WINDOW = 5
    WINDOW_SECONDS = 1

    BASE = "https://api.airtable.com/v0"

    def __init__(self, tenant_config: dict[str, Any]) -> None:
        super().__init__(tenant_config)
        token = os.environ.get("AIRTABLE_PAT", "")
        base_id = os.environ.get("AIRTABLE_BASE_ID", "")
        table_id = tenant_config.get("provider", {}).get("table_id", "")
        if not token or not base_id or not table_id:
            raise RuntimeError(
                "AIRTABLE_PAT + AIRTABLE_BASE_ID + provider.table_id required"
            )
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self._base_id = base_id
        self._table_id = table_id

    def _client(self):
        try:
            import httpx
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("httpx missing. pip install httpx>=0.27") from e
        return httpx.Client(headers=self._headers, timeout=30.0)

    def list_records(self, since_watermark: str | None) -> Iterator[dict[str, Any]]:
        offset: str | None = None
        while True:
            self._rate_gate()
            params: dict[str, Any] = {"pageSize": 100}
            if offset:
                params["offset"] = offset
            if since_watermark:
                params["filterByFormula"] = (
                    f"IS_AFTER(LAST_MODIFIED_TIME(), '{since_watermark}')"
                )
            with self._client() as c:
                r = c.get(f"{self.BASE}/{self._base_id}/{self._table_id}", params=params)
                r.raise_for_status()
                payload = r.json()
            for record in payload.get("records", []):
                yield record
            offset = payload.get("offset")
            if not offset:
                break

    def get_record(self, record_id: str) -> dict[str, Any]:
        self._rate_gate()
        with self._client() as c:
            r = c.get(f"{self.BASE}/{self._base_id}/{self._table_id}/{record_id}")
            r.raise_for_status()
            return r.json()

    def create_record(self, provider_payload: dict[str, Any]) -> dict[str, Any]:
        self._rate_gate()
        with self._client() as c:
            r = c.post(
                f"{self.BASE}/{self._base_id}/{self._table_id}",
                json={"fields": provider_payload.get("fields", provider_payload)},
            )
            r.raise_for_status()
            return r.json()

    def update_record(
        self, record_id: str, provider_payload: dict[str, Any]
    ) -> dict[str, Any]:
        self._rate_gate()
        with self._client() as c:
            r = c.patch(
                f"{self.BASE}/{self._base_id}/{self._table_id}/{record_id}",
                json={"fields": provider_payload.get("fields", provider_payload)},
            )
            r.raise_for_status()
            return r.json()

    def subscribe_webhook(self, target_url: str, secret: str) -> dict[str, Any]:
        self._rate_gate()
        with self._client() as c:
            r = c.post(
                f"{self.BASE}/bases/{self._base_id}/webhooks",
                json={
                    "notificationUrl": target_url,
                    "specification": {
                        "options": {
                            "filters": {"dataTypes": ["tableData"]},
                            "includes": {"includeCellValuesInFieldIds": "all"},
                        }
                    },
                },
            )
            r.raise_for_status()
            return r.json()

    def verify_webhook_signature(
        self, raw_body: bytes, signature_header: str, secret: str
    ) -> bool:
        """Airtable webhook MAC: HMAC-SHA256 hex, base16, of the raw body.
        Header format: 'hmac-sha256=<hex>'.
        """
        candidate = signature_header.replace("hmac-sha256=", "").strip()
        expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, candidate)
