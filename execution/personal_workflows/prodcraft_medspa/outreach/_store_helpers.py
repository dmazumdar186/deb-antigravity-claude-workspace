"""
_store_helpers.py
description: Thin, business-shaped wrappers over the Store Protocol's generic list_rows() for the
    "list rows for business X" / "list rows by status" patterns the outreach package needs.
inputs: Imported by outreach/* modules; no CLI args (importable module).
outputs: Plain lists of dicts; no filesystem/network side effects beyond the underlying Store call.

Previously this module reached into LocalStore._read / SupabaseStore._request/_headers directly
(a documented Store-boundary violation). The Store Protocol (common/store.py) now exposes a generic
list_rows(table, **filters) that both implementations honor, so these helpers just call that.
"""

from __future__ import annotations

from typing import Any


def list_all(store: Any, table: str) -> list[dict]:
    """Return every row in `table`, regardless of Store implementation."""
    return store.list_rows(table)


def outreach_for_business(store: Any, business_id: str) -> list[dict]:
    """All outreach rows (any touch, any status) for one business."""
    return store.list_rows("outreach", business_id=business_id)


def outreach_by_status(store: Any, status: str) -> list[dict]:
    """All outreach rows across every business currently in `status`."""
    return store.list_rows("outreach", status=status)


def previews_for_business(store: Any, business_id: str) -> list[dict]:
    """All preview rows for one business, newest (`created_at`) first."""
    return store.list_previews(business_id)
