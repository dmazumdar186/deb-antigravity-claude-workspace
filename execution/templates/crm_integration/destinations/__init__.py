"""Destination registry.

A destination is 'where the mapped record lands' — Google Sheet, Postgres,
KV, JSONL file. Add a new one by subclassing Destination in a new module
and registering here.
"""
from __future__ import annotations

from .base import Destination
from .jsonl import JsonlDestination
from .google_sheet import GoogleSheetDestination


DESTINATIONS: dict[str, type[Destination]] = {
    "jsonl": JsonlDestination,
    "google_sheet": GoogleSheetDestination,
    # "kv":       KvDestination,   # implement per-worker
    # "postgres": PostgresDestination,
}


def get_destination(name: str) -> type[Destination]:
    if name not in DESTINATIONS:
        raise KeyError(
            f"unknown destination: {name}. registered: {sorted(DESTINATIONS)}"
        )
    return DESTINATIONS[name]


__all__ = ["Destination", "DESTINATIONS", "get_destination"]
