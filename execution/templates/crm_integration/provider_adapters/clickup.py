"""ClickUp adapter (tasks endpoint).

Reference: https://clickup.com/api
Rate limit: 100 req/min per token (free); 1000/min on paid.
Webhook signature: header `X-Signature`, HMAC-SHA256 hex of raw body.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any, Iterator

from .base import Adapter


class ClickUpAdapter(Adapter):
    REQUESTS_PER_WINDOW = 100
    WINDOW_SECONDS = 60

    BASE = "https://api.clickup.com/api/v2"

    def __init__(self, tenant_config: dict[str, Any]) -> None:
        super().__init__(tenant_config)
        token = os.environ.get("CLICKUP_API_TOKEN", "")
        team_id = os.environ.get("CLICKUP_TEAM_ID", "")
        if not token or not team_id:
            raise RuntimeError("CLICKUP_API_TOKEN + CLICKUP_TEAM_ID required")
        self._headers = {"Authorization": token, "Content-Type": "application/json"}
        self._team_id = team_id

    def _client(self):
        try:
            import httpx
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("httpx missing. pip install httpx>=0.27") from e
        return httpx.Client(headers=self._headers, timeout=30.0)

    def list_records(self, since_watermark: str | None) -> Iterator[dict[str, Any]]:
        list_id = self.config.get("provider", {}).get("list_id")
        if not list_id:
            raise RuntimeError(
                "clickup adapter needs provider.list_id in tenant config "
                "(add to tenant.<slug>.json)"
            )
        page = 0
        while True:
            self._rate_gate()
            params: dict[str, Any] = {"page": page}
            if since_watermark:
                # ClickUp expects epoch-ms.
                from datetime import datetime
                try:
                    dt = datetime.fromisoformat(since_watermark.replace("Z", "+00:00"))
                    params["date_updated_gt"] = int(dt.timestamp() * 1000)
                except ValueError:
                    pass
            with self._client() as c:
                r = c.get(f"{self.BASE}/list/{list_id}/task", params=params)
                r.raise_for_status()
                payload = r.json()
            tasks = payload.get("tasks", [])
            if not tasks:
                break
            for task in tasks:
                yield task
            if len(tasks) < 100:  # ClickUp returns 100/page; short page = end.
                break
            page += 1

    def get_record(self, record_id: str) -> dict[str, Any]:
        self._rate_gate()
        with self._client() as c:
            r = c.get(f"{self.BASE}/task/{record_id}")
            r.raise_for_status()
            return r.json()

    def create_record(self, provider_payload: dict[str, Any]) -> dict[str, Any]:
        list_id = self.config.get("provider", {}).get("list_id")
        self._rate_gate()
        with self._client() as c:
            r = c.post(f"{self.BASE}/list/{list_id}/task", json=provider_payload)
            r.raise_for_status()
            return r.json()

    def update_record(
        self, record_id: str, provider_payload: dict[str, Any]
    ) -> dict[str, Any]:
        self._rate_gate()
        with self._client() as c:
            r = c.put(f"{self.BASE}/task/{record_id}", json=provider_payload)
            r.raise_for_status()
            return r.json()

    def subscribe_webhook(self, target_url: str, secret: str) -> dict[str, Any]:
        self._rate_gate()
        with self._client() as c:
            r = c.post(
                f"{self.BASE}/team/{self._team_id}/webhook",
                json={
                    "endpoint": target_url,
                    "events": ["taskCreated", "taskUpdated", "taskDeleted"],
                },
            )
            r.raise_for_status()
            return r.json()

    def verify_webhook_signature(
        self, raw_body: bytes, signature_header: str, secret: str
    ) -> bool:
        expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature_header.strip())
