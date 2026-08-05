"""Destination interface."""
from __future__ import annotations

import abc
from typing import Any


class Destination(abc.ABC):
    def __init__(self, tenant_config: dict[str, Any]) -> None:
        self.config = tenant_config

    @abc.abstractmethod
    def upsert(self, internal_record: dict[str, Any]) -> str:
        """Write `internal_record` to the destination, keyed by internal_id.

        Returns one of: 'created', 'updated', 'skipped'.
        """

    def close(self) -> None:  # pragma: no cover
        """Flush any buffered writes. Override if needed."""
