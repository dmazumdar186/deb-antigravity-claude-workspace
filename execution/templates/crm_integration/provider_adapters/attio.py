"""Attio adapter.

Reference: https://docs.attio.com/rest-api
Rate limit: ~200 req/min per API key.
Webhook signature: header `x-attio-signature`, HMAC-SHA256 hex of raw body.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any, Iterator

from .base import Adapter


class AttioAdapter(Adapter):
    REQUESTS_PER_WINDOW = 200
    WINDOW_SECONDS = 60

    BASE = "https://api.attio.com/v2"

    def __init__(self, tenant_config: dict[str, Any]) -> None:
        super().__init__(tenant_config)
        token = os.environ.get("ATTIO_API_KEY", "")
        if not token:
            raise RuntimeError("ATTIO_API_KEY missing")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _client(self):
        try:
            import httpx
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("httpx missing. pip install httpx>=0.27") from e
        return httpx.Client(headers=self._headers, timeout=30.0)

    def list_records(self, since_watermark: str | None) -> Iterator[dict[str, Any]]:
        object_slug = self.config.get("provider", {}).get("record_type", "people")
        cursor: str | None = None
        while True:
            self._rate_gate()
            body: dict[str, Any] = {"limit": 100}
            if cursor:
                body["cursor"] = cursor
            if since_watermark:
                body["filter"] = {
                    "updated_at": {"$gt": since_watermark},
                }
            with self._client() as c:
                r = c.post(f"{self.BASE}/objects/{object_slug}/records/query", json=body)
                r.raise_for_status()
                payload = r.json()
            for record in payload.get("data", []):
                yield record
            cursor = payload.get("next_cursor")
            if not cursor:
                break

    def get_record(self, record_id: str) -> dict[str, Any]:
        object_slug = self.config.get("provider", {}).get("record_type", "people")
        self._rate_gate()
        with self._client() as c:
            r = c.get(f"{self.BASE}/objects/{object_slug}/records/{record_id}")
            r.raise_for_status()
            return r.json().get("data", {})

    def create_record(self, provider_payload: dict[str, Any]) -> dict[str, Any]:
        object_slug = self.config.get("provider", {}).get("record_type", "people")
        self._rate_gate()
        with self._client() as c:
            r = c.post(
                f"{self.BASE}/objects/{object_slug}/records",
                json={"data": {"values": provider_payload}},
            )
            r.raise_for_status()
            return r.json().get("data", {})

    def update_record(
        self, record_id: str, provider_payload: dict[str, Any]
    ) -> dict[str, Any]:
        object_slug = self.config.get("provider", {}).get("record_type", "people")
        self._rate_gate()
        with self._client() as c:
            r = c.patch(
                f"{self.BASE}/objects/{object_slug}/records/{record_id}",
                json={"data": {"values": provider_payload}},
            )
            r.raise_for_status()
            return r.json().get("data", {})

    def subscribe_webhook(self, target_url: str, secret: str) -> dict[str, Any]:
        self._rate_gate()
        with self._client() as c:
            r = c.post(
                f"{self.BASE}/webhooks",
                json={
                    "data": {
                        "target_url": target_url,
                        "secret": secret,
                        "subscriptions": [
                            {"event_type": "record.created"},
                            {"event_type": "record.updated"},
                        ],
                    }
                },
            )
            r.raise_for_status()
            return r.json().get("data", {})

    def verify_webhook_signature(
        self, raw_body: bytes, signature_header: str, secret: str
    ) -> bool:
        expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature_header.strip())
