"""
_store_helpers.py
description: Defensive "list all rows in a table" helper for LocalStore/SupabaseStore.
inputs: Imported by outreach/* modules; no CLI args (importable module).
outputs: Plain lists of dicts; no filesystem/network side effects beyond the underlying Store call.

CONTRACTS.md's Store Protocol (common/store.py) intentionally has no generic "list all rows in
table X" or "list rows for business Y" method — only narrow, purpose-built accessors
(find_businesses, latest_audit, queue, ...). The outreach state machine and daily queue need a
few list operations the Protocol doesn't expose (e.g. "every outreach row for this business",
"every preview", "every sent outreach row for the bounce-rate window"). Rather than editing
common/store.py (out of scope for this build), this module reaches into the two existing Store
implementations' own internals defensively:
  - LocalStore exposes `_read(table)` (an underscore-prefixed but stable helper already used
    throughout store.py's own methods).
  - SupabaseStore exposes `_request(method, path, **kw)` + `_headers(...)` the same way.
Any future third Store implementation that provides neither will get a clear NotImplementedError
naming this gap instead of a silent wrong answer.
"""

from __future__ import annotations

from typing import Any


def list_all(store: Any, table: str) -> list[dict]:
    """Return every row in `table`, regardless of Store implementation."""
    read = getattr(store, "_read", None)
    if callable(read):
        return list(read(table))

    request = getattr(store, "_request", None)
    headers_fn = getattr(store, "_headers", None)
    if callable(request) and callable(headers_fn):
        resp = request("GET", table, headers=headers_fn())
        return resp.json()

    raise NotImplementedError(
        f"Store {type(store).__name__} exposes neither _read (LocalStore) nor "
        f"_request/_headers (SupabaseStore); outreach package cannot list '{table}' rows. "
        "CONTRACTS.md's Store Protocol has no generic list-all method — this is a documented "
        "gap (see execution/personal_workflows/prodcraft_medspa/outreach/_store_helpers.py)."
    )


def outreach_for_business(store: Any, business_id: str) -> list[dict]:
    """All outreach rows (any touch, any status) for one business."""
    return [r for r in list_all(store, "outreach") if r.get("business_id") == business_id]


def outreach_by_status(store: Any, status: str) -> list[dict]:
    """All outreach rows across every business currently in `status`."""
    return [r for r in list_all(store, "outreach") if r.get("status") == status]


def previews_for_business(store: Any, business_id: str) -> list[dict]:
    """All preview rows for one business, newest (`created_at`) first."""
    rows = [r for r in list_all(store, "previews") if r.get("business_id") == business_id]
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows
