"""Pure record-shape transforms between provider records and internal records.

description: Bidirectional field mapping — provider record <-> internal record.
inputs:      dict from a provider adapter's list/get_record; internal-shape dict
outputs:     dict in the opposite shape

Every function here is pure (no I/O, no time, no randomness). This is the
layer that gets unit-tested exhaustively — the acceptance gate reuses it,
per output-acceptance-gate.md, but the frozen fixtures in tests/fixtures/
are the independent oracle.

Design note (Singer-inspired): each record has a stable `internal_id` (the
CRM's own record id) and a `watermark` (updated_at ISO-8601). The sync
driver uses those two fields for dedup and incremental watermarking. Mapping
is otherwise config-driven — see config/tenant.example.json's
`field_mappings` block.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _parse_iso8601(value: Any) -> str | None:
    """Return an ISO-8601 UTC string, or None if value is unparseable/empty.

    Provider APIs vary: HubSpot returns epoch-ms as string, Pipedrive returns
    'YYYY-MM-DD HH:MM:SS' in the tenant's timezone, Attio returns ISO-8601.
    Normalize to UTC ISO-8601 for a comparable watermark.
    """
    if value in (None, "", 0):
        return None
    try:
        if isinstance(value, (int, float)):
            # Assume epoch-ms (HubSpot convention). Epoch-s would be < 10^10.
            ts_s = value / 1000 if value > 10 ** 10 else value
            return datetime.fromtimestamp(ts_s, tz=timezone.utc).isoformat()
        if isinstance(value, str):
            v = value.strip().replace("Z", "+00:00")
            # Best-effort ISO-8601 parse; fall through if it's Pipedrive's
            # space-separated format.
            try:
                return datetime.fromisoformat(v).astimezone(timezone.utc).isoformat()
            except ValueError:
                dt = datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S")
                return dt.replace(tzinfo=timezone.utc).isoformat()
    except (ValueError, TypeError, OSError):
        # OSError guards against absurd epoch values on Windows (year > 3000).
        return None
    return None


def apply_field_mapping(
    source: dict[str, Any],
    field_mappings: dict[str, str],
) -> dict[str, Any]:
    """Copy source[foreign_key] -> result[internal_key] per config.

    Missing source keys become None in the result (never KeyError).
    Uses dot-paths for nested lookups: 'properties.email' -> source['properties']['email'].
    """
    out: dict[str, Any] = {}
    for internal_key, foreign_path in field_mappings.items():
        out[internal_key] = _nested_get(source, foreign_path)
    return out


def _nested_get(d: dict[str, Any], path: str) -> Any:
    """Dot-path lookup. Returns None on any missing hop."""
    cur: Any = d
    for hop in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(hop)
        if cur is None:
            return None
    return cur


# ---------------------------------------------------------------------------
# Provider-agnostic canonical shape
# ---------------------------------------------------------------------------
# Every provider record, after mapping, has at least these keys. Downstream
# destinations rely on this contract.

CANONICAL_KEYS = ("internal_id", "watermark", "record_type")


def to_internal(
    provider_record: dict[str, Any],
    provider: str,
    field_mappings: dict[str, str],
    id_path: str,
    watermark_path: str,
    record_type: str,
) -> dict[str, Any]:
    """Provider record -> canonical internal record.

    provider:        adapter name (e.g. 'hubspot') — recorded for audit
    field_mappings:  {internal_key: dot.path.in.source}
    id_path:         where to find the provider's record id
    watermark_path:  where to find the last-modified timestamp
    record_type:     'contact' / 'deal' / 'task' / 'company' / ...
    """
    mapped = apply_field_mapping(provider_record, field_mappings)
    mapped["internal_id"] = _stringify_id(_nested_get(provider_record, id_path))
    mapped["watermark"] = _parse_iso8601(_nested_get(provider_record, watermark_path))
    mapped["record_type"] = record_type
    mapped["_provider"] = provider
    return mapped


def from_internal(
    internal_record: dict[str, Any],
    field_mappings: dict[str, str],
) -> dict[str, Any]:
    """Canonical internal record -> provider-shape dict for create/update.

    Uses the inverse of `field_mappings`. Skips canonical keys and any key
    starting with '_'. Dot-paths are re-nested.
    """
    out: dict[str, Any] = {}
    for internal_key, foreign_path in field_mappings.items():
        if internal_key in CANONICAL_KEYS or internal_key.startswith("_"):
            continue
        value = internal_record.get(internal_key)
        if value is None:
            continue
        _nested_set(out, foreign_path, value)
    return out


def _nested_set(d: dict[str, Any], path: str, value: Any) -> None:
    """Set d[path.split('.')[0]][...][last] = value, creating dicts along the way."""
    hops = path.split(".")
    cur = d
    for hop in hops[:-1]:
        if hop not in cur or not isinstance(cur[hop], dict):
            cur[hop] = {}
        cur = cur[hop]
    cur[hops[-1]] = value


def _stringify_id(value: Any) -> str | None:
    """Provider record ids are sometimes int, sometimes str. Force str for
    consistent dedup key hashing."""
    if value is None:
        return None
    return str(value)


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def dedup_key(record: dict[str, Any]) -> str:
    """Stable key for KV / SQLite dedup. Provider + type + id.

    Never include the watermark — a record's identity does not change when its
    fields do. The watermark drives incremental sync; the dedup_key drives
    'have I already seen this?'.
    """
    prov = record.get("_provider") or "unknown"
    rtype = record.get("record_type") or "unknown"
    rid = record.get("internal_id") or "missing"
    return f"{prov}:{rtype}:{rid}"
