"""
Source provider protocol + test double -- RADAR_CONTRACTS.md section A.

`SourceProvider` is the shape every source plugin implements (the free
chartership-register plugins in this file's sibling modules, and the
licensed providers -- pdl/crustdata/apollo -- built separately and wired in
through `registry.register_provider`). `FixtureProvider` is a fixed,
network-free implementation used by tests: it never calls out, so a contract
test (registry lookup, SourceResult round-trip) never depends on any real
plugin's internals or on network access.

Nothing in this module touches the network.
"""

from __future__ import annotations

import threading
import time
from typing import Literal, Optional, Protocol, runtime_checkable

from ..core.contracts import ProviderRecord, RawDocument, SourceQuery, SourceResult

TextSource = Literal["text_layer", "ocr", "provider_field"]

# ---------------------------------------------------------------------------
# Shared per-provider throttle -- same shape as core/cache.py's `_throttle`
# (a lock-guarded "last hit" clock per key, sleep off the remainder of
# rate_limit_s), but keyed by an arbitrary string (a provider name) rather
# than a URL host, so every source plugin can share ONE implementation
# instead of each hand-rolling its own module-level `_last_hit` global.
#
# python-hardening rule 2: several plugins (engineers_ireland.py, ice.py,
# istructe.py) each carried their own `_last_hit = 0.0` module global read
# and written with no lock at all -- fine under a single-threaded run.py
# stage today, but a read-then-write race the moment two threads fetch the
# same provider concurrently (run_all's ThreadPoolExecutor is exactly that).
# ---------------------------------------------------------------------------

_THROTTLE_LOCK = threading.Lock()
_THROTTLE_LAST: dict[str, float] = {}


def throttle(key: str, rate_limit_s: float) -> None:
    """Block until at least `rate_limit_s` has passed since the last call
    with this same `key` (typically a provider name). Thread-safe."""
    with _THROTTLE_LOCK:
        last = _THROTTLE_LAST.get(key, 0.0)
        wait = rate_limit_s - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
        _THROTTLE_LAST[key] = time.monotonic()


@runtime_checkable
class SourceProvider(Protocol):
    """RADAR_CONTRACTS.md section A. Every source plugin -- register scrapers
    and licensed providers alike -- implements exactly this shape so
    run.py/registry.py can drive them uniformly."""

    name: str  # "engineers_ireland", "istructe", "ice", "pdl", ...
    text_source: TextSource
    rate_limit_s: float

    def fetch(self, query: SourceQuery) -> SourceResult: ...

    def cost_eur(self, result: SourceResult) -> float: ...


class FixtureProvider:
    """A SourceProvider backed by a fixed, in-memory list of documents /
    provider records. Test-only: nothing here fetches, caches, or rate-limits
    for real, so it is deliberately unfit to be registered for a live run --
    it exists so contract tests can exercise the registry and the
    SourceResult shape without depending on a real plugin or the network.
    """

    text_source: TextSource = "text_layer"

    def __init__(
        self,
        name: str = "fixture",
        documents: Optional[list[RawDocument]] = None,
        provider_records: Optional[list[ProviderRecord]] = None,
        rate_limit_s: float = 0.0,
        cost_per_doc_eur: float = 0.0,
    ) -> None:
        self.name = name
        self.rate_limit_s = rate_limit_s
        self._documents = list(documents or [])
        self._provider_records = list(provider_records or [])
        self._cost_per_doc_eur = cost_per_doc_eur

    def fetch(self, query: SourceQuery) -> SourceResult:
        docs = self._documents[: query.limit]
        records = self._provider_records[: query.limit]
        return SourceResult(
            provider=self.name,
            documents=docs,
            provider_records=records,
            fetched=len(docs) + len(records),
            cost_eur=(len(docs) + len(records)) * self._cost_per_doc_eur,
        )

    def cost_eur(self, result: SourceResult) -> float:
        return (len(result.documents) + len(result.provider_records)) * self._cost_per_doc_eur
