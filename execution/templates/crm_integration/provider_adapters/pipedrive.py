"""Pipedrive adapter (persons endpoint by default; deals is trivial to swap).

Reference: https://developers.pipedrive.com/docs/api/v1
Rate limit: default plan ~20 req/2s per token (varies by plan).
Webhook auth: HTTP Basic on the subscribe URL, so the "signature" is really
'did the request come with the basic-auth pair we configured?'.
"""
from __future__ import annotations

import os
from typing import Any, Iterator

from .base import Adapter


class PipedriveAdapter(Adapter):
    REQUESTS_PER_WINDOW = 20
    WINDOW_SECONDS = 2

    def __init__(self, tenant_config: dict[str, Any]) -> None:
        super().__init__(tenant_config)
        token = os.environ.get("PIPEDRIVE_API_TOKEN", "")
        domain = os.environ.get("PIPEDRIVE_COMPANY_DOMAIN", "")
        if not token or not domain:
            raise RuntimeError(
                "PIPEDRIVE_API_TOKEN + PIPEDRIVE_COMPANY_DOMAIN required"
            )
        self._token = token
        self._base = f"https://{domain}.pipedrive.com/api/v1"

    def _client(self):
        try:
            import httpx
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("httpx missing. pip install httpx>=0.27") from e
        return httpx.Client(timeout=30.0)

    def list_records(self, since_watermark: str | None) -> Iterator[dict[str, Any]]:
        start = 0
        limit = 100
        while True:
            self._rate_gate()
            params = {"api_token": self._token, "start": start, "limit": limit}
            if since_watermark:
                params["since_timestamp"] = since_watermark
            with self._client() as c:
                r = c.get(f"{self._base}/persons", params=params)
                r.raise_for_status()
                payload = r.json()
            for record in payload.get("data", []) or []:
                yield record
            pagination = payload.get("additional_data", {}).get("pagination", {})
            if not pagination.get("more_items_in_collection"):
                break
            start = pagination.get("next_start", start + limit)

    def get_record(self, record_id: str) -> dict[str, Any]:
        self._rate_gate()
        with self._client() as c:
            r = c.get(
                f"{self._base}/persons/{record_id}",
                params={"api_token": self._token},
            )
            r.raise_for_status()
            return r.json().get("data", {})

    def create_record(self, provider_payload: dict[str, Any]) -> dict[str, Any]:
        self._rate_gate()
        with self._client() as c:
            r = c.post(
                f"{self._base}/persons",
                params={"api_token": self._token},
                json=provider_payload,
            )
            r.raise_for_status()
            return r.json().get("data", {})

    def update_record(
        self, record_id: str, provider_payload: dict[str, Any]
    ) -> dict[str, Any]:
        self._rate_gate()
        with self._client() as c:
            r = c.put(
                f"{self._base}/persons/{record_id}",
                params={"api_token": self._token},
                json=provider_payload,
            )
            r.raise_for_status()
            return r.json().get("data", {})

    def subscribe_webhook(self, target_url: str, secret: str) -> dict[str, Any]:
        self._rate_gate()
        # Pipedrive webhooks: https://developers.pipedrive.com/docs/api/v1/Webhooks
        # HTTP Basic auth on the delivery URL: user='api', pass=secret.
        with self._client() as c:
            r = c.post(
                f"{self._base}/webhooks",
                params={"api_token": self._token},
                json={
                    "subscription_url": target_url,
                    "event_action": "*",
                    "event_object": "person",
                    "http_auth_user": "api",
                    "http_auth_password": secret,
                },
            )
            r.raise_for_status()
            return r.json().get("data", {})

    def verify_webhook_signature(
        self, raw_body: bytes, signature_header: str, secret: str
    ) -> bool:
        """Pipedrive doesn't sign the body — it authenticates the delivery URL
        with HTTP Basic auth. The receiver validates the Authorization header
        elsewhere; here we accept if the header 'user:secret' matches.
        """
        import base64
        expected = base64.b64encode(f"api:{secret}".encode("utf-8")).decode("ascii")
        got = signature_header.replace("Basic ", "").strip()
        # constant-time compare
        import hmac
        return hmac.compare_digest(expected, got)
