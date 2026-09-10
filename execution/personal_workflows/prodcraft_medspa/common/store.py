"""
store.py
description: Store Protocol + LocalStore (JSON files) and SupabaseStore (PostgREST) implementations.
inputs: Imported by every stage script; env PRODCRAFT_STORE, SUPABASE_URL, SUPABASE_SERVICE_KEY.
outputs: LocalStore writes one JSON file per table under its root dir; SupabaseStore makes HTTPS calls.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import requests

TABLES = (
    "businesses",
    "audits",
    "previews",
    "outreach",
    "deals",
    "metro_stats",
    "config",
    "events",
    "chains",
)

_QUEUE_STATUSES = ("queued", "sent")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_id() -> str:
    return str(uuid.uuid4())


class Store(Protocol):
    """Persistence interface every pipeline stage codes against. See CONTRACTS.md."""

    def upsert_business(self, row: dict) -> dict: ...  # keyed on place_id

    def get_business(self, business_id: str) -> dict | None: ...

    def find_businesses(self, **filters: Any) -> list[dict]: ...  # metro=, bucket=, has_email=, do_not_contact=

    def insert_audit(self, row: dict) -> dict: ...

    def latest_audit(self, business_id: str) -> dict | None: ...

    def upsert_preview(self, row: dict) -> dict: ...  # keyed on (business_id, content_hash)

    def update_preview(self, preview_id: str, patch: dict) -> dict: ...

    def upsert_outreach(self, row: dict) -> dict: ...  # keyed on (business_id, touch)

    def update_outreach(self, outreach_id: str, patch: dict) -> dict: ...

    def queue(self, today: date, cap: int) -> list[dict]: ...  # next_touch_at <= today, status in (queued, sent)

    def upsert_deal(self, row: dict) -> dict: ...

    def insert_metro_stats(self, row: dict) -> dict: ...

    def get_config(self, key: str, default: Any = None) -> Any: ...

    def set_config(self, key: str, value: Any) -> None: ...

    def log_event(self, entity: str, entity_id: str, event: str, payload: dict | None = None) -> None: ...

    def chains(self) -> list[str]: ...


# ---------------------------------------------------------------------------
# LocalStore — one JSON file per table, atomic writes, uuid4 ids.
# ---------------------------------------------------------------------------


class LocalStore:
    """JSON-file-backed Store. One file per table under `root`. Thread-safe."""

    def __init__(self, root: str | Path = ".tmp/prodcraft_medspa/store"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    # -- low-level file I/O ------------------------------------------------

    def _path(self, table: str) -> Path:
        return self.root / f"{table}.json"

    def _read(self, table: str) -> list[dict]:
        path = self._path(table)
        if not path.exists():
            return []
        with open(path, encoding="utf-8") as f:
            content = f.read().strip()
        return json.loads(content) if content else []

    def _write(self, table: str, rows: list[dict]) -> None:
        """Atomic write: write to a temp file in the same dir, then os.replace()."""
        path = self._path(table)
        tmp_path = path.with_suffix(f".tmp-{uuid.uuid4().hex}")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, default=str)
        os.replace(tmp_path, path)

    # -- businesses ----------------------------------------------------------

    def upsert_business(self, row: dict) -> dict:
        with self._lock:
            rows = self._read("businesses")
            place_id = row.get("place_id")
            now = _now_iso()
            for i, existing in enumerate(rows):
                if existing.get("place_id") == place_id:
                    merged = {**existing, **row}
                    merged["id"] = existing["id"]
                    merged["created_at"] = existing.get("created_at", now)
                    merged["updated_at"] = now
                    rows[i] = merged
                    self._write("businesses", rows)
                    return merged
            new_row = dict(row)
            new_row["id"] = new_row.get("id") or _new_id()
            new_row.setdefault("created_at", now)
            new_row["updated_at"] = now
            rows.append(new_row)
            self._write("businesses", rows)
            return new_row

    def get_business(self, business_id: str) -> dict | None:
        rows = self._read("businesses")
        for row in rows:
            if row.get("id") == business_id:
                return row
        return None

    def find_businesses(self, **filters: Any) -> list[dict]:
        rows = self._read("businesses")
        metro = filters.get("metro")
        bucket = filters.get("bucket")
        has_email = filters.get("has_email")
        do_not_contact = filters.get("do_not_contact")
        is_chain = filters.get("is_chain")
        drop_reason_is_null = filters.get("drop_reason_is_null")

        audits_by_business = self._latest_audits_by_business()

        out = []
        for b in rows:
            if metro is not None and b.get("metro") != metro:
                continue
            if do_not_contact is not None and bool(b.get("do_not_contact")) != bool(do_not_contact):
                continue
            if is_chain is not None and bool(b.get("is_chain")) != bool(is_chain):
                continue
            if drop_reason_is_null is not None:
                is_null = b.get("drop_reason") is None
                if is_null != bool(drop_reason_is_null):
                    continue
            if has_email is not None:
                deliverable = b.get("email_status") == "deliverable"
                if deliverable != bool(has_email):
                    continue
            if bucket is not None:
                latest = audits_by_business.get(b.get("id"))
                if not latest or latest.get("bucket") != bucket:
                    continue
            out.append(b)
        return out

    # -- audits ----------------------------------------------------------

    def _latest_audits_by_business(self) -> dict[str, dict]:
        audits = self._read("audits")
        latest: dict[str, dict] = {}
        for a in audits:
            bid = a.get("business_id")
            existing = latest.get(bid)
            if existing is None or (a.get("audited_at") or "") > (existing.get("audited_at") or ""):
                latest[bid] = a
        return latest

    def insert_audit(self, row: dict) -> dict:
        with self._lock:
            rows = self._read("audits")
            new_row = dict(row)
            new_row["id"] = new_row.get("id") or _new_id()
            new_row.setdefault("audited_at", _now_iso())
            rows.append(new_row)
            self._write("audits", rows)
            return new_row

    def latest_audit(self, business_id: str) -> dict | None:
        return self._latest_audits_by_business().get(business_id)

    # -- previews ----------------------------------------------------------

    def upsert_preview(self, row: dict) -> dict:
        with self._lock:
            rows = self._read("previews")
            key = (row.get("business_id"), row.get("content_hash"))
            now = _now_iso()
            for i, existing in enumerate(rows):
                if (existing.get("business_id"), existing.get("content_hash")) == key:
                    merged = {**existing, **row}
                    merged["id"] = existing["id"]
                    merged["created_at"] = existing.get("created_at", now)
                    rows[i] = merged
                    self._write("previews", rows)
                    return merged
            new_row = dict(row)
            new_row["id"] = new_row.get("id") or _new_id()
            new_row.setdefault("created_at", now)
            rows.append(new_row)
            self._write("previews", rows)
            return new_row

    def update_preview(self, preview_id: str, patch: dict) -> dict:
        with self._lock:
            rows = self._read("previews")
            for i, existing in enumerate(rows):
                if existing.get("id") == preview_id:
                    merged = {**existing, **patch}
                    rows[i] = merged
                    self._write("previews", rows)
                    return merged
            raise KeyError(f"preview {preview_id} not found")

    # -- outreach ----------------------------------------------------------

    def upsert_outreach(self, row: dict) -> dict:
        with self._lock:
            rows = self._read("outreach")
            key = (row.get("business_id"), row.get("touch"))
            now = _now_iso()
            for i, existing in enumerate(rows):
                if (existing.get("business_id"), existing.get("touch")) == key:
                    merged = {**existing, **row}
                    merged["id"] = existing["id"]
                    merged["created_at"] = existing.get("created_at", now)
                    merged["updated_at"] = now
                    rows[i] = merged
                    self._write("outreach", rows)
                    return merged
            new_row = dict(row)
            new_row["id"] = new_row.get("id") or _new_id()
            new_row.setdefault("created_at", now)
            new_row["updated_at"] = now
            rows.append(new_row)
            self._write("outreach", rows)
            return new_row

    def update_outreach(self, outreach_id: str, patch: dict) -> dict:
        with self._lock:
            rows = self._read("outreach")
            for i, existing in enumerate(rows):
                if existing.get("id") == outreach_id:
                    merged = {**existing, **patch}
                    merged["updated_at"] = _now_iso()
                    rows[i] = merged
                    self._write("outreach", rows)
                    return merged
            raise KeyError(f"outreach {outreach_id} not found")

    def queue(self, today: date, cap: int) -> list[dict]:
        rows = self._read("outreach")
        today_str = today.isoformat()
        matching = [
            r
            for r in rows
            if r.get("status") in _QUEUE_STATUSES
            and r.get("next_touch_at") is not None
            and str(r.get("next_touch_at")) <= today_str
        ]
        matching.sort(key=lambda r: (r.get("next_touch_at") or "", r.get("created_at") or ""))
        return matching[:cap]

    # -- deals ----------------------------------------------------------

    def upsert_deal(self, row: dict) -> dict:
        with self._lock:
            rows = self._read("deals")
            new_row = dict(row)
            business_id = new_row.get("business_id")
            for i, existing in enumerate(rows):
                if existing.get("business_id") == business_id:
                    merged = {**existing, **new_row}
                    merged["id"] = existing["id"]
                    merged.setdefault("created_at", existing.get("created_at", _now_iso()))
                    rows[i] = merged
                    self._write("deals", rows)
                    return merged
            new_row["id"] = new_row.get("id") or _new_id()
            new_row.setdefault("created_at", _now_iso())
            rows.append(new_row)
            self._write("deals", rows)
            return new_row

    # -- metro_stats ----------------------------------------------------------

    def insert_metro_stats(self, row: dict) -> dict:
        with self._lock:
            rows = self._read("metro_stats")
            new_row = dict(row)
            new_row["id"] = new_row.get("id") or _new_id()
            new_row.setdefault("measured_at", _now_iso())
            rows.append(new_row)
            self._write("metro_stats", rows)
            return new_row

    # -- config ----------------------------------------------------------

    def get_config(self, key: str, default: Any = None) -> Any:
        rows = self._read("config")
        for row in rows:
            if row.get("key") == key:
                return row.get("value")
        return default

    def set_config(self, key: str, value: Any) -> None:
        with self._lock:
            rows = self._read("config")
            now = _now_iso()
            for i, row in enumerate(rows):
                if row.get("key") == key:
                    rows[i] = {"key": key, "value": value, "updated_at": now}
                    self._write("config", rows)
                    return
            rows.append({"key": key, "value": value, "updated_at": now})
            self._write("config", rows)

    # -- events ----------------------------------------------------------

    def log_event(self, entity: str, entity_id: str, event: str, payload: dict | None = None) -> None:
        with self._lock:
            rows = self._read("events")
            rows.append(
                {
                    "id": len(rows) + 1,
                    "entity": entity,
                    "entity_id": entity_id,
                    "event": event,
                    "payload": payload or {},
                    "created_at": _now_iso(),
                }
            )
            self._write("events", rows)

    # -- chains ----------------------------------------------------------

    def chains(self) -> list[str]:
        rows = self._read("chains")
        return [r["pattern"] for r in rows]

    def load_chains(self, patterns: list[dict]) -> None:
        """Seed helper: patterns is a list of {"pattern": ..., "note": ...} dicts."""
        with self._lock:
            self._write("chains", patterns)


# ---------------------------------------------------------------------------
# SupabaseStore — PostgREST over requests, service-key auth.
# ---------------------------------------------------------------------------


class SupabaseStore:
    """PostgREST-backed Store using the Supabase service key. Never logs the key."""

    def __init__(self, url: str | None = None, service_key: str | None = None):
        self.url = (url or os.environ.get("SUPABASE_URL") or "").rstrip("/")
        self._service_key = service_key or os.environ.get("SUPABASE_SERVICE_KEY") or ""
        if not self.url or not self._service_key:
            raise ValueError("SupabaseStore requires SUPABASE_URL and SUPABASE_SERVICE_KEY")
        self._session = requests.Session()

    def _headers(self, *, prefer: str | None = None) -> dict:
        headers = {
            "apikey": self._service_key,
            "Authorization": f"Bearer {self._service_key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        """Retry 3x with backoff on 5xx/429. Never includes the key in exception text."""
        url = f"{self.url}/rest/v1/{path}"
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                resp = self._session.request(method, url, timeout=20, **kwargs)
                if resp.status_code in (429, 500, 502, 503, 504):
                    time.sleep(1 * (2**attempt))
                    continue
                resp.raise_for_status()
                return resp
            except requests.exceptions.RequestException as exc:
                last_exc = exc
                time.sleep(1 * (2**attempt))
        raise RuntimeError(f"Supabase request failed after retries: {method} {path}") from last_exc

    # -- businesses ----------------------------------------------------------

    def upsert_business(self, row: dict) -> dict:
        resp = self._request(
            "POST",
            "businesses?on_conflict=place_id",
            headers=self._headers(prefer="return=representation,resolution=merge-duplicates"),
            json=row,
        )
        data = resp.json()
        return data[0] if isinstance(data, list) else data

    def get_business(self, business_id: str) -> dict | None:
        resp = self._request(
            "GET", f"businesses?id=eq.{business_id}", headers=self._headers()
        )
        data = resp.json()
        return data[0] if data else None

    def find_businesses(self, **filters: Any) -> list[dict]:
        metro = filters.get("metro")
        bucket = filters.get("bucket")
        has_email = filters.get("has_email")
        do_not_contact = filters.get("do_not_contact")
        is_chain = filters.get("is_chain")
        drop_reason_is_null = filters.get("drop_reason_is_null")

        params = []
        if metro is not None:
            params.append(f"metro=eq.{metro}")
        if do_not_contact is not None:
            params.append(f"do_not_contact=eq.{str(bool(do_not_contact)).lower()}")
        if is_chain is not None:
            params.append(f"is_chain=eq.{str(bool(is_chain)).lower()}")
        if drop_reason_is_null is not None:
            params.append("drop_reason=is.null" if drop_reason_is_null else "drop_reason=not.is.null")
        if has_email is not None:
            params.append("email_status=eq.deliverable" if has_email else "email_status=neq.deliverable")

        query = "businesses?" + "&".join(params) if params else "businesses"
        resp = self._request("GET", query, headers=self._headers())
        businesses = resp.json()

        if bucket is None:
            return businesses

        # Two-query join: fetch latest audit per business, filter by bucket.
        out = []
        for b in businesses:
            audit_resp = self._request(
                "GET",
                f"audits?business_id=eq.{b['id']}&order=audited_at.desc&limit=1",
                headers=self._headers(),
            )
            audits = audit_resp.json()
            if audits and audits[0].get("bucket") == bucket:
                out.append(b)
        return out

    # -- audits ----------------------------------------------------------

    def insert_audit(self, row: dict) -> dict:
        resp = self._request(
            "POST", "audits", headers=self._headers(prefer="return=representation"), json=row
        )
        data = resp.json()
        return data[0] if isinstance(data, list) else data

    def latest_audit(self, business_id: str) -> dict | None:
        resp = self._request(
            "GET",
            f"audits?business_id=eq.{business_id}&order=audited_at.desc&limit=1",
            headers=self._headers(),
        )
        data = resp.json()
        return data[0] if data else None

    # -- previews ----------------------------------------------------------

    def upsert_preview(self, row: dict) -> dict:
        resp = self._request(
            "POST",
            "previews?on_conflict=business_id,content_hash",
            headers=self._headers(prefer="return=representation,resolution=merge-duplicates"),
            json=row,
        )
        data = resp.json()
        return data[0] if isinstance(data, list) else data

    def update_preview(self, preview_id: str, patch: dict) -> dict:
        resp = self._request(
            "PATCH",
            f"previews?id=eq.{preview_id}",
            headers=self._headers(prefer="return=representation"),
            json=patch,
        )
        data = resp.json()
        return data[0] if isinstance(data, list) else data

    # -- outreach ----------------------------------------------------------

    def upsert_outreach(self, row: dict) -> dict:
        resp = self._request(
            "POST",
            "outreach?on_conflict=business_id,touch",
            headers=self._headers(prefer="return=representation,resolution=merge-duplicates"),
            json=row,
        )
        data = resp.json()
        return data[0] if isinstance(data, list) else data

    def update_outreach(self, outreach_id: str, patch: dict) -> dict:
        resp = self._request(
            "PATCH",
            f"outreach?id=eq.{outreach_id}",
            headers=self._headers(prefer="return=representation"),
            json=patch,
        )
        data = resp.json()
        return data[0] if isinstance(data, list) else data

    def queue(self, today: date, cap: int) -> list[dict]:
        status_filter = "status=in.(" + ",".join(_QUEUE_STATUSES) + ")"
        resp = self._request(
            "GET",
            f"outreach?next_touch_at=lte.{today.isoformat()}&{status_filter}"
            f"&order=next_touch_at.asc,created_at.asc&limit={cap}",
            headers=self._headers(),
        )
        return resp.json()

    # -- deals ----------------------------------------------------------

    def upsert_deal(self, row: dict) -> dict:
        resp = self._request(
            "POST",
            "deals?on_conflict=business_id",
            headers=self._headers(prefer="return=representation,resolution=merge-duplicates"),
            json=row,
        )
        data = resp.json()
        return data[0] if isinstance(data, list) else data

    # -- metro_stats ----------------------------------------------------------

    def insert_metro_stats(self, row: dict) -> dict:
        resp = self._request(
            "POST", "metro_stats", headers=self._headers(prefer="return=representation"), json=row
        )
        data = resp.json()
        return data[0] if isinstance(data, list) else data

    # -- config ----------------------------------------------------------

    def get_config(self, key: str, default: Any = None) -> Any:
        resp = self._request("GET", f"config?key=eq.{key}", headers=self._headers())
        data = resp.json()
        return data[0]["value"] if data else default

    def set_config(self, key: str, value: Any) -> None:
        self._request(
            "POST",
            "config?on_conflict=key",
            headers=self._headers(prefer="resolution=merge-duplicates"),
            json={"key": key, "value": value},
        )

    # -- events ----------------------------------------------------------

    def log_event(self, entity: str, entity_id: str, event: str, payload: dict | None = None) -> None:
        self._request(
            "POST",
            "events",
            headers=self._headers(),
            json={"entity": entity, "entity_id": entity_id, "event": event, "payload": payload or {}},
        )

    # -- chains ----------------------------------------------------------

    def chains(self) -> list[str]:
        resp = self._request("GET", "chains?select=pattern", headers=self._headers())
        return [r["pattern"] for r in resp.json()]


def get_store(kind: str | None = None, root: str | Path | None = None) -> Store:
    """Factory: 'local' -> LocalStore, 'supabase' -> SupabaseStore. Defaults to env PRODCRAFT_STORE, then 'local'."""
    resolved = (kind or os.environ.get("PRODCRAFT_STORE") or "local").strip().lower()
    if resolved == "supabase":
        return SupabaseStore()
    return LocalStore(root=root or ".tmp/prodcraft_medspa/store")
