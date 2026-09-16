"""
store.py
description: Store Protocol + LocalStore (JSON files) and SupabaseStore (PostgREST) implementations.
inputs: Imported by every stage script; env PRODCRAFT_STORE, SUPABASE_URL, SUPABASE_SERVICE_KEY.
outputs: LocalStore writes one JSON file per table under its root dir; SupabaseStore makes HTTPS calls.
"""

from __future__ import annotations

import json
import os
import re
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

# Tables addressable by generic get_row()/update_row() (id-keyed). `config` is keyed on `key`
# and `chains` is keyed on `pattern` — they have no `id` column, so id-based accessors reject
# them with ValueError; list_rows() still works against the full TABLES allowlist for both.
ID_TABLES = frozenset(TABLES) - {"config", "chains"}

_QUEUE_STATUSES = ("queued", "sent")

# Tables whose rows carry an `updated_at` column that generic update_row() should refresh.
# Mirrors existing hand-written behaviour: update_outreach() always stamps updated_at;
# update_preview() never does (previews has no updated_at column in schema.sql).
_TABLES_WITH_UPDATED_AT = frozenset({"businesses", "outreach"})

# Column/filter/order-by identifiers accepted anywhere a caller-supplied name reaches a
# PostgREST query string (list_rows filters and order_by). Deliberately conservative
# (lower snake_case only) — this is what stands between an LLM- or caller-derived key and
# PostgREST operator injection via `+`/`#`/`&` in an f-string-built URL.
_KEY_RE = re.compile(r"[a-z_][a-z0-9_]*")


def _validate_key(key: str) -> str:
    if not _KEY_RE.fullmatch(key):
        raise ValueError(f"invalid column/filter/order key: {key!r}")
    return key


def _pg_value(value: Any) -> str:
    """Normalise a Python value for a PostgREST `eq.`/`is.` filter. Booleans -> 'true'/'false'."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


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

    def list_rows(
        self, table: str, *, order_by: str | None = None, descending: bool = False, limit: int | None = None, **filters: Any
    ) -> list[dict]: ...  # generic table read; equality filters only, None value means "is null"; table validated against TABLES

    def get_row(self, table: str, row_id: str) -> dict | None: ...  # single row by id, or None if not found; table must be in ID_TABLES

    def update_row(self, table: str, row_id: str, patch: dict) -> dict: ...  # generic patch-by-id; stamps updated_at for tables that have it

    def list_previews(self, business_id: str) -> list[dict]: ...  # all previews for one business, newest (created_at) first

    def list_outreach(self, business_id: str) -> list[dict]: ...  # all outreach rows for one business, newest (created_at) first

    def load_chains(self, patterns: list[dict]) -> int: ...  # seed helper: merge every {"pattern", "note"} row, returns count processed


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
            slug = row.get("slug")
            now = _now_iso()
            if slug is not None:
                for other in rows:
                    if other.get("slug") == slug and other.get("place_id") != place_id:
                        raise ValueError(
                            f"slug {slug!r} already belongs to place_id {other.get('place_id')!r} "
                            f"(schema.sql declares businesses.slug unique)"
                        )
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
            # max(existing ids)+1 rather than len(rows)+1: len() collides with a prior id once
            # any row has been pruned (e.g. a retention job deleting old events).
            next_id = max((r.get("id", 0) for r in rows), default=0) + 1
            rows.append(
                {
                    "id": next_id,
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

    def load_chains(self, patterns: list[dict]) -> int:
        """Seed helper: merge each {"pattern": ..., "note": ...} dict into the chains table,
        keyed on `pattern`. Existing rows not present in `patterns` are kept (this merges,
        it does not replace the table); a row whose pattern already exists is updated in
        place. Raises ValueError if any entry lacks `pattern`. Returns the count of entries
        processed (not the resulting table size)."""
        for entry in patterns:
            if not entry.get("pattern"):
                raise ValueError(f"chains entry missing 'pattern': {entry!r}")
        with self._lock:
            rows = self._read("chains")
            index_by_pattern = {r.get("pattern"): i for i, r in enumerate(rows)}
            for entry in patterns:
                pattern = entry["pattern"]
                if pattern in index_by_pattern:
                    rows[index_by_pattern[pattern]] = {**rows[index_by_pattern[pattern]], **entry}
                else:
                    rows.append(dict(entry))
                    index_by_pattern[pattern] = len(rows) - 1
            self._write("chains", rows)
        return len(patterns)

    # -- generic table access ----------------------------------------------

    def list_rows(
        self,
        table: str,
        *,
        order_by: str | None = None,
        descending: bool = False,
        limit: int | None = None,
        **filters: Any,
    ) -> list[dict]:
        """Equality-filter every kwarg in `filters` (None value means "column is null").

        `order_by` sorts ascending by default (missing/None values sort last); `limit` truncates
        after ordering. Raises ValueError for a table not in `TABLES`, or for a filter/order_by
        key that isn't a plain lower-snake-case identifier (mirrors SupabaseStore's PostgREST
        query-string safety check, so both backends reject the same inputs).

        Tie-order caveat: when `order_by` values are of mixed Python types across rows, they are
        coerced to `str` for comparison purposes only (returned rows keep their original values);
        ties after coercion fall back to input order (Python's sort is stable).
        """
        if table not in TABLES:
            raise ValueError(f"unknown table: {table!r} (known: {TABLES})")
        for key in filters:
            _validate_key(key)
        if order_by is not None:
            _validate_key(order_by)
        rows = self._read(table)
        for key, value in filters.items():
            if value is None:
                rows = [r for r in rows if r.get(key) is None]
            else:
                rows = [r for r in rows if r.get(key) == value]
        if order_by:
            values = [r.get(order_by) for r in rows]
            mixed_types = len({type(v) for v in values if v is not None}) > 1

            def _sort_key(r: dict) -> tuple[bool, Any]:
                v = r.get(order_by)
                if v is None:
                    return (True, "")
                return (False, str(v) if mixed_types else v)

            rows = sorted(rows, key=_sort_key, reverse=descending)
        if limit is not None:
            rows = rows[:limit]
        return rows

    def get_row(self, table: str, row_id: str) -> dict | None:
        if table not in ID_TABLES:
            raise ValueError(f"table {table!r} has no id column (use list_rows/get_config/chains)")
        for row in self._read(table):
            if row.get("id") == row_id:
                return row
        return None

    def update_row(self, table: str, row_id: str, patch: dict) -> dict:
        if table not in ID_TABLES:
            raise ValueError(f"table {table!r} has no id column (use list_rows/set_config/load_chains)")
        with self._lock:
            rows = self._read(table)
            for i, existing in enumerate(rows):
                if existing.get("id") == row_id:
                    merged = {**existing, **patch}
                    if table in _TABLES_WITH_UPDATED_AT:
                        merged["updated_at"] = _now_iso()
                    rows[i] = merged
                    self._write(table, rows)
                    return merged
            raise KeyError(f"{table} row {row_id} not found")

    def list_previews(self, business_id: str) -> list[dict]:
        return self.list_rows("previews", business_id=business_id, order_by="created_at", descending=True)

    def list_outreach(self, business_id: str) -> list[dict]:
        return self.list_rows("outreach", business_id=business_id, order_by="created_at", descending=True)


# ---------------------------------------------------------------------------
# SupabaseStore — PostgREST over requests, service-key auth.
# ---------------------------------------------------------------------------


class SupabaseStore:
    """PostgREST-backed Store using the Supabase service key. Never logs the key."""

    _PAGE_SIZE = 1000

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

    def _request(self, method: str, path: str, *, idempotent: bool = True, **kwargs: Any) -> requests.Response:
        """Retry up to 3x with backoff on 429/5xx (5xx only when `idempotent`) and on connection
        errors regardless of `idempotent`. Never sleeps after the final attempt. Never includes
        the key in exception text; does include the response status code and a body snippet.

        `idempotent=False` is for POSTs that would duplicate a row if a "successful" insert's
        response was merely lost before we saw it (e.g. `events`, which has a bigserial id and
        no natural key to de-dupe on) — those calls skip the 5xx retry entirely and only retry
        on 429/connection errors, where we know the server never processed the request.
        Idempotent inserts (`audits`, `metro_stats`) instead get a client-side uuid `id` plus
        `Prefer: resolution=merge-duplicates`, so retrying them after a 5xx is safe and they
        keep `idempotent=True` (the default).
        """
        url = f"{self.url}/rest/v1/{path}"
        last_exc: Exception | None = None
        attempts = 3
        for attempt in range(attempts):
            try:
                resp = self._session.request(method, url, timeout=20, **kwargs)
                retryable_status = resp.status_code == 429 or (idempotent and resp.status_code in (500, 502, 503, 504))
                if retryable_status:
                    last_exc = RuntimeError(
                        f"Supabase request failed: {method} {path} -> {resp.status_code} {resp.text[:200]}"
                    )
                    if attempt < attempts - 1:
                        time.sleep(1 * (2**attempt))
                    continue
                resp.raise_for_status()
                return resp
            except requests.exceptions.HTTPError:
                raise RuntimeError(
                    f"Supabase request failed: {method} {path} -> {resp.status_code} {resp.text[:200]}"
                ) from None
            except requests.exceptions.RequestException as exc:
                last_exc = exc
                if attempt < attempts - 1:
                    time.sleep(1 * (2**attempt))
        if isinstance(last_exc, RuntimeError):
            # Already carries the status code + body snippet from the last retryable response.
            raise last_exc
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
            "GET", "businesses", params=[("id", f"eq.{business_id}")], headers=self._headers()
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

        params: list[tuple[str, str]] = []
        if metro is not None:
            params.append(("metro", f"eq.{_pg_value(metro)}"))
        if do_not_contact is not None:
            params.append(("do_not_contact", f"eq.{_pg_value(bool(do_not_contact))}"))
        if is_chain is not None:
            params.append(("is_chain", f"eq.{_pg_value(bool(is_chain))}"))
        if drop_reason_is_null is not None:
            params.append(("drop_reason", "is.null" if drop_reason_is_null else "not.is.null"))
        if has_email is not None:
            params.append(("email_status", "eq.deliverable" if has_email else "neq.deliverable"))

        resp = self._request("GET", "businesses", params=params, headers=self._headers())
        businesses = resp.json()

        if bucket is None:
            return businesses

        # Two-query join: fetch latest audit per business, filter by bucket.
        out = []
        for b in businesses:
            audit_resp = self._request(
                "GET",
                "audits",
                params=[("business_id", f"eq.{b['id']}"), ("order", "audited_at.desc"), ("limit", "1")],
                headers=self._headers(),
            )
            audits = audit_resp.json()
            if audits and audits[0].get("bucket") == bucket:
                out.append(b)
        return out

    # -- audits ----------------------------------------------------------

    def insert_audit(self, row: dict) -> dict:
        # Idempotent insert: client-side id + merge-duplicates so a retried POST after a lost
        # 5xx response upserts the same row instead of creating a duplicate audit.
        body = dict(row)
        body.setdefault("id", _new_id())
        resp = self._request(
            "POST",
            "audits?on_conflict=id",
            headers=self._headers(prefer="return=representation,resolution=merge-duplicates"),
            json=body,
        )
        data = resp.json()
        return data[0] if isinstance(data, list) else data

    def latest_audit(self, business_id: str) -> dict | None:
        resp = self._request(
            "GET",
            "audits",
            params=[("business_id", f"eq.{business_id}"), ("order", "audited_at.desc"), ("limit", "1")],
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
            "previews",
            params=[("id", f"eq.{preview_id}")],
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
            "outreach",
            params=[("id", f"eq.{outreach_id}")],
            headers=self._headers(prefer="return=representation"),
            json=patch,
        )
        data = resp.json()
        return data[0] if isinstance(data, list) else data

    def queue(self, today: date, cap: int) -> list[dict]:
        params = [
            ("next_touch_at", f"lte.{today.isoformat()}"),
            ("status", "in.(" + ",".join(_QUEUE_STATUSES) + ")"),
            ("order", "next_touch_at.asc,created_at.asc"),
            ("limit", str(cap)),
        ]
        resp = self._request("GET", "outreach", params=params, headers=self._headers())
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
        # Idempotent insert: same rationale as insert_audit (client-side id + merge-duplicates).
        body = dict(row)
        body.setdefault("id", _new_id())
        resp = self._request(
            "POST",
            "metro_stats?on_conflict=id",
            headers=self._headers(prefer="return=representation,resolution=merge-duplicates"),
            json=body,
        )
        data = resp.json()
        return data[0] if isinstance(data, list) else data

    # -- config ----------------------------------------------------------

    def get_config(self, key: str, default: Any = None) -> Any:
        resp = self._request("GET", "config", params=[("key", f"eq.{key}")], headers=self._headers())
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
        # events.id is a bigserial with no unique business key to merge-duplicates on, so a
        # retried POST after a lost 5xx response could double-insert; we deliberately do NOT
        # retry on 5xx here (idempotent=False), only on 429/connection errors where the server
        # is known not to have processed the request.
        self._request(
            "POST",
            "events",
            headers=self._headers(),
            json={"entity": entity, "entity_id": entity_id, "event": event, "payload": payload or {}},
            idempotent=False,
        )

    # -- chains ----------------------------------------------------------

    def chains(self) -> list[str]:
        resp = self._request("GET", "chains?select=pattern", headers=self._headers())
        return [r["pattern"] for r in resp.json()]

    # -- generic table access ----------------------------------------------

    def list_rows(
        self,
        table: str,
        *,
        order_by: str | None = None,
        descending: bool = False,
        limit: int | None = None,
        **filters: Any,
    ) -> list[dict]:
        """Equality-filter every kwarg in `filters` (`?col=eq.value`; None value becomes `?col=is.null`).

        `order_by` maps to PostgREST `order=col.asc|desc`. Filter/order keys are validated
        against `_KEY_RE` (ValueError otherwise) and values are always sent via `requests`
        `params=` as (key, value) tuples — never f-string-interpolated into the URL — so `+`,
        `#`, `&`, and other PostgREST/URL-significant characters in a filter value are encoded
        correctly instead of becoming a literal space, truncating the query, or injecting an
        extra parameter.

        Paginates internally in pages of `_PAGE_SIZE` (1000, PostgREST's default max-rows) using
        `Range-Unit: items` + `Range: a-b`, continuing until a short page comes back, because a
        naive single request silently truncates a full-table read at PostgREST's server-side cap.
        `limit`, if given, caps the total across all pages (not just the first page).
        Raises ValueError for a table not in `TABLES` (prevents an LLM- or caller-derived name
        from reaching an arbitrary PostgREST path).
        """
        if table not in TABLES:
            raise ValueError(f"unknown table: {table!r} (known: {TABLES})")
        for key in filters:
            _validate_key(key)
        if order_by is not None:
            _validate_key(order_by)

        base_params: list[tuple[str, str]] = []
        for key, value in filters.items():
            base_params.append((key, "is.null" if value is None else f"eq.{_pg_value(value)}"))
        if order_by:
            base_params.append(("order", f"{order_by}.{'desc' if descending else 'asc'}"))

        rows: list[dict] = []
        offset = 0
        while True:
            if limit is not None:
                remaining = limit - len(rows)
                if remaining <= 0:
                    break
                page_size = min(self._PAGE_SIZE, remaining)
            else:
                page_size = self._PAGE_SIZE
            headers = self._headers()
            headers["Range-Unit"] = "items"
            headers["Range"] = f"{offset}-{offset + page_size - 1}"
            resp = self._request("GET", table, params=base_params, headers=headers)
            page = resp.json()
            rows.extend(page)
            if len(page) < page_size:
                break
            offset += page_size
        if limit is not None:
            rows = rows[:limit]
        return rows

    def get_row(self, table: str, row_id: str) -> dict | None:
        if table not in ID_TABLES:
            raise ValueError(f"table {table!r} has no id column (use list_rows/get_config/chains)")
        resp = self._request("GET", table, params=[("id", f"eq.{row_id}")], headers=self._headers())
        data = resp.json()
        return data[0] if data else None

    def update_row(self, table: str, row_id: str, patch: dict) -> dict:
        if table not in ID_TABLES:
            raise ValueError(f"table {table!r} has no id column (use list_rows/set_config/load_chains)")
        body = dict(patch)
        if table in _TABLES_WITH_UPDATED_AT:
            body["updated_at"] = _now_iso()
        resp = self._request(
            "PATCH",
            table,
            params=[("id", f"eq.{row_id}")],
            headers=self._headers(prefer="return=representation"),
            json=body,
        )
        data = resp.json()
        if not data:
            raise KeyError(f"{table} row {row_id} not found")
        return data[0] if isinstance(data, list) else data

    def list_previews(self, business_id: str) -> list[dict]:
        return self.list_rows("previews", business_id=business_id, order_by="created_at", descending=True)

    def list_outreach(self, business_id: str) -> list[dict]:
        return self.list_rows("outreach", business_id=business_id, order_by="created_at", descending=True)

    def load_chains(self, patterns: list[dict]) -> int:
        """Seed helper: upsert every {"pattern", "note"} row via PostgREST merge-duplicates.
        Raises ValueError if any entry lacks `pattern` (mirrors LocalStore's validation)."""
        for entry in patterns:
            if not entry.get("pattern"):
                raise ValueError(f"chains entry missing 'pattern': {entry!r}")
        for entry in patterns:
            self._request(
                "POST",
                "chains?on_conflict=pattern",
                headers=self._headers(prefer="resolution=merge-duplicates"),
                json=entry,
            )
        return len(patterns)


def get_store(kind: str | None = None, root: str | Path | None = None) -> Store:
    """Factory: 'local' -> LocalStore, 'supabase' -> SupabaseStore. Defaults to env PRODCRAFT_STORE, then 'local'."""
    resolved = (kind or os.environ.get("PRODCRAFT_STORE") or "local").strip().lower()
    if resolved == "supabase":
        return SupabaseStore()
    return LocalStore(root=root or ".tmp/prodcraft_medspa/store")
