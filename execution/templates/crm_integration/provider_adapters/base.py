"""Adapter base class + fixture adapter for tests.

description: Abstract interface every CRM provider adapter implements.
inputs:      TenantConfig, live os.environ
outputs:     yields dicts (list_records), returns dicts (get/create/update)

Design: Singer-inspired. The adapter is I/O; mapping.py is pure. Rate-limit
math is inside the adapter — the sync driver does not need to know provider
quotas.
"""
from __future__ import annotations

import abc
import hashlib
import hmac
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Iterator


class RateLimitExceeded(RuntimeError):
    """Raised by an adapter when its own preflight math says the requested
    window would breach the CRM's quota. Sync driver refuses to start."""


class Adapter(abc.ABC):
    """Every provider adapter implements these six methods."""

    # Subclasses SHOULD override.
    REQUESTS_PER_WINDOW: int = 60
    WINDOW_SECONDS: int = 60

    def __init__(self, tenant_config: dict[str, Any]) -> None:
        self.config = tenant_config
        self._lock = threading.Lock()
        self._request_timestamps: list[float] = []

    # ---- Rate-limit machinery (shared, thread-safe) ------------------------
    def _rate_gate(self) -> None:
        """Blocks until a request can be sent without breaching the window.

        Uses a sliding window over self._request_timestamps. Threadsafe.
        """
        with self._lock:
            now = time.monotonic()
            cutoff = now - self.WINDOW_SECONDS
            self._request_timestamps = [t for t in self._request_timestamps if t > cutoff]
            if len(self._request_timestamps) >= self.REQUESTS_PER_WINDOW:
                oldest = self._request_timestamps[0]
                wait_for = self.WINDOW_SECONDS - (now - oldest) + 0.01
                if wait_for > 0:
                    time.sleep(wait_for)
                    now = time.monotonic()
                    cutoff = now - self.WINDOW_SECONDS
                    self._request_timestamps = [
                        t for t in self._request_timestamps if t > cutoff
                    ]
            self._request_timestamps.append(now)

    def preflight_quota(self, expected_requests: int) -> None:
        """Refuse to start a sync that would visibly breach quota.

        We can't know the CRM's remaining balance without a call — but we can
        assert 'this run would try N req in T sec' against 'plan allows M req
        in W sec' and refuse ahead of time.
        """
        est_seconds = expected_requests * self.WINDOW_SECONDS / self.REQUESTS_PER_WINDOW
        if est_seconds > 60 * 15:  # CF Worker request cap; also sanity floor
            raise RateLimitExceeded(
                f"{self.__class__.__name__}: expected {expected_requests} requests "
                f"would take ~{est_seconds:.0f}s at plan limit "
                f"{self.REQUESTS_PER_WINDOW}/{self.WINDOW_SECONDS}s. "
                f"Split the run or upgrade the plan."
            )

    # ---- Provider I/O interface -------------------------------------------
    @abc.abstractmethod
    def list_records(self, since_watermark: str | None) -> Iterator[dict[str, Any]]:
        """Yield raw provider records modified after `since_watermark` (ISO-8601).

        Implementation MUST call self._rate_gate() before each network call.
        MUST paginate through everything; sync driver caps with max_pages.
        """

    @abc.abstractmethod
    def get_record(self, record_id: str) -> dict[str, Any]:
        """Fetch one record by id."""

    @abc.abstractmethod
    def create_record(self, provider_payload: dict[str, Any]) -> dict[str, Any]:
        """Create a record. Returns the created record (with id)."""

    @abc.abstractmethod
    def update_record(
        self, record_id: str, provider_payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Partial-update. Returns the updated record."""

    @abc.abstractmethod
    def subscribe_webhook(self, target_url: str, secret: str) -> dict[str, Any]:
        """Register `target_url` for record change events. Returns the
        provider's subscription record for audit."""

    def verify_webhook_signature(
        self, raw_body: bytes, signature_header: str, secret: str
    ) -> bool:
        """Default: HMAC-SHA256 hex digest match. Override per provider spec.

        The default is safe when the provider signs the raw body with the
        shared secret using SHA-256 — a common pattern. Providers with
        version prefixes (HubSpot v3) or query-string signing override this.
        """
        expected = hmac.new(
            secret.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()
        # Strip common prefixes like 'sha256=' before comparing.
        candidate = signature_header.split("=", 1)[-1].strip()
        return hmac.compare_digest(expected, candidate)


# ---------------------------------------------------------------------------
# FixtureAdapter — used by tests and by --dry-run against a synthetic tenant
# ---------------------------------------------------------------------------

class FixtureAdapter(Adapter):
    """Reads records from a JSON file. Never calls out. Used for tests + dry-run."""

    REQUESTS_PER_WINDOW = 1_000_000
    WINDOW_SECONDS = 1

    def __init__(self, tenant_config: dict[str, Any]) -> None:
        super().__init__(tenant_config)
        fixture_path = os.environ.get(
            "FIXTURE_ADAPTER_PATH",
            str(Path(__file__).parent.parent / "tests" / "fixtures" / "hubspot_contact.json"),
        )
        self._fixture_path = Path(fixture_path)
        self._records: list[dict[str, Any]] = self._load()

    def _load(self) -> list[dict[str, Any]]:
        if not self._fixture_path.exists():
            return []
        data = json.loads(self._fixture_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "results" in data:
            return list(data["results"])
        if isinstance(data, dict):
            return [data]
        return []

    def list_records(self, since_watermark: str | None) -> Iterator[dict[str, Any]]:
        for rec in self._records:
            yield rec

    def get_record(self, record_id: str) -> dict[str, Any]:
        for rec in self._records:
            if str(rec.get("id")) == str(record_id):
                return rec
        raise KeyError(record_id)

    def create_record(self, provider_payload: dict[str, Any]) -> dict[str, Any]:
        new_id = f"fixture_{len(self._records) + 1}"
        rec = {"id": new_id, **provider_payload}
        self._records.append(rec)
        return rec

    def update_record(
        self, record_id: str, provider_payload: dict[str, Any]
    ) -> dict[str, Any]:
        for i, rec in enumerate(self._records):
            if str(rec.get("id")) == str(record_id):
                self._records[i] = {**rec, **provider_payload}
                return self._records[i]
        raise KeyError(record_id)

    def subscribe_webhook(self, target_url: str, secret: str) -> dict[str, Any]:
        return {"subscription_id": "fixture", "target_url": target_url}
