"""JSONL destination — append-only file, one record per line.

description: Default dev destination. Idempotent by dedup_key.
inputs:      destination.target = file path
outputs:     newline-delimited JSON records, plus a sidecar `.seen.json`
             tracking dedup keys already written.

Safe for tests, dry-runs, and small-scale prod. Not for high-volume streams
(rewrites `.seen.json` after every batch — fine <100k records).
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .base import Destination


class JsonlDestination(Destination):
    def __init__(self, tenant_config: dict[str, Any]) -> None:
        super().__init__(tenant_config)
        target = tenant_config.get("destination", {}).get("target")
        if not target:
            raise RuntimeError("jsonl destination requires destination.target = <path>")
        self._path = Path(target)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._seen_path = self._path.with_suffix(self._path.suffix + ".seen.json")
        self._lock = threading.Lock()
        self._seen: set[str] = self._load_seen()

    def _load_seen(self) -> set[str]:
        if not self._seen_path.exists():
            return set()
        try:
            return set(json.loads(self._seen_path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            # Corrupt seen file — surface, don't silently reset. Bare-except is banned.
            raise RuntimeError(
                f"corrupt seen-file at {self._seen_path}. "
                f"Delete it manually if you accept re-writing all records."
            )

    def upsert(self, internal_record: dict[str, Any]) -> str:
        from mapping import dedup_key  # local import to avoid cycle at package load

        key = dedup_key(internal_record)
        with self._lock:
            already_seen = key in self._seen
            if already_seen:
                # Overwrite by appending — JSONL is append-only; downstream reader
                # takes the last line per key. That's the standard Singer pattern.
                self._seen.add(key)  # no-op, but keep symmetry
                action = "updated"
            else:
                self._seen.add(key)
                action = "created"
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(internal_record, ensure_ascii=False) + "\n")
            self._seen_path.write_text(
                json.dumps(sorted(self._seen)), encoding="utf-8"
            )
        return action

    def close(self) -> None:
        # Nothing to flush — writes are file-open-per-record.
        pass
