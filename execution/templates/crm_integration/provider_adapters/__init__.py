"""Provider adapter registry.

Add a new adapter:
  1. Create provider_adapters/<name>.py implementing the Adapter interface (base.py).
  2. Register its class here in ADAPTERS.
  3. Add its literal to config/schema.py Provider type.
"""
from __future__ import annotations

from .base import Adapter, FixtureAdapter
from .hubspot import HubSpotAdapter
from .pipedrive import PipedriveAdapter
from .attio import AttioAdapter
from .clickup import ClickUpAdapter
from .airtable import AirtableAdapter


ADAPTERS: dict[str, type[Adapter]] = {
    "hubspot": HubSpotAdapter,
    "pipedrive": PipedriveAdapter,
    "attio": AttioAdapter,
    "clickup": ClickUpAdapter,
    "airtable": AirtableAdapter,
    "fixture": FixtureAdapter,
}


def get_adapter(name: str) -> type[Adapter]:
    if name not in ADAPTERS:
        raise KeyError(
            f"unknown provider adapter: {name}. registered: {sorted(ADAPTERS)}"
        )
    return ADAPTERS[name]


__all__ = ["Adapter", "ADAPTERS", "get_adapter"]
