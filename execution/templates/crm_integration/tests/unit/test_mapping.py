"""Unit tests for mapping.py — pure functions, no I/O.

Run:  py -m pytest execution/templates/crm_integration/tests/unit/ -v
"""
from __future__ import annotations

import sys
from pathlib import Path

_TEMPLATE_ROOT = Path(__file__).resolve().parents[2]
if str(_TEMPLATE_ROOT) not in sys.path:
    sys.path.insert(0, str(_TEMPLATE_ROOT))

import pytest  # noqa: E402

from mapping import (  # noqa: E402
    _nested_get,
    _nested_set,
    _parse_iso8601,
    _stringify_id,
    apply_field_mapping,
    dedup_key,
    from_internal,
    to_internal,
)


# --- helpers ---------------------------------------------------------------

def test_nested_get_hits_deep_key():
    assert _nested_get({"a": {"b": {"c": 1}}}, "a.b.c") == 1


def test_nested_get_returns_none_on_missing():
    assert _nested_get({"a": {}}, "a.b.c") is None
    assert _nested_get({}, "a") is None
    assert _nested_get({"a": "str"}, "a.b") is None  # not a dict at hop


def test_nested_set_creates_intermediate_dicts():
    d: dict = {}
    _nested_set(d, "a.b.c", 42)
    assert d == {"a": {"b": {"c": 42}}}


def test_nested_set_overwrites_scalar_at_intermediate():
    d = {"a": "was-a-string"}
    _nested_set(d, "a.b", 1)
    assert d == {"a": {"b": 1}}


def test_stringify_id_handles_int_str_none():
    assert _stringify_id(1) == "1"
    assert _stringify_id("abc") == "abc"
    assert _stringify_id(None) is None


# --- watermark parsing -----------------------------------------------------

def test_parse_iso8601_z_suffix():
    got = _parse_iso8601("2026-08-04T10:00:00Z")
    assert got and got.startswith("2026-08-04T10:00:00")


def test_parse_iso8601_pipedrive_space_format():
    got = _parse_iso8601("2026-08-04 09:30:00")
    assert got and got.startswith("2026-08-04T09:30:00")


def test_parse_iso8601_epoch_ms():
    got = _parse_iso8601(1_754_308_800_000)  # ~2025-08-04
    assert got and got.startswith("2025-08-04")


def test_parse_iso8601_returns_none_on_junk():
    assert _parse_iso8601(None) is None
    assert _parse_iso8601("") is None
    assert _parse_iso8601("not-a-date") is None


# --- field mapping ---------------------------------------------------------

def test_apply_field_mapping_basic():
    source = {"properties": {"email": "a@b.co", "firstname": "A"}}
    out = apply_field_mapping(source, {"email": "properties.email", "first_name": "properties.firstname"})
    assert out == {"email": "a@b.co", "first_name": "A"}


def test_apply_field_mapping_missing_becomes_none():
    out = apply_field_mapping({"properties": {"email": "x"}}, {"missing": "properties.missing"})
    assert out == {"missing": None}


# --- canonical shape -------------------------------------------------------

def test_to_internal_hubspot_shape():
    source = {
        "id": "42",
        "properties": {
            "email": "alice@example.com",
            "firstname": "Alice",
            "lastmodifieddate": "2026-08-04T10:00:00Z",
        },
    }
    internal = to_internal(
        source,
        provider="hubspot",
        field_mappings={"email": "properties.email", "first_name": "properties.firstname"},
        id_path="id",
        watermark_path="properties.lastmodifieddate",
        record_type="contact",
    )
    assert internal["internal_id"] == "42"
    assert internal["record_type"] == "contact"
    assert internal["_provider"] == "hubspot"
    assert internal["email"] == "alice@example.com"
    assert internal["watermark"].startswith("2026-08-04T10:00:00")


def test_to_internal_missing_watermark_becomes_none():
    source = {"id": "1", "properties": {"email": "x"}}
    internal = to_internal(
        source,
        provider="hubspot",
        field_mappings={"email": "properties.email"},
        id_path="id",
        watermark_path="properties.lastmodifieddate",
        record_type="contact",
    )
    assert internal["watermark"] is None


def test_from_internal_re_nests_dot_paths():
    internal = {
        "internal_id": "42",
        "watermark": "2026-08-04T10:00:00Z",
        "record_type": "contact",
        "_provider": "hubspot",
        "email": "alice@example.com",
        "first_name": "Alice",
    }
    provider_shape = from_internal(
        internal,
        {"email": "properties.email", "first_name": "properties.firstname"},
    )
    assert provider_shape == {
        "properties": {"email": "alice@example.com", "firstname": "Alice"}
    }


def test_from_internal_skips_canonical_and_underscore_keys():
    internal = {
        "internal_id": "42", "watermark": "x", "record_type": "y", "_provider": "z",
        "email": "e",
    }
    provider_shape = from_internal(internal, {"email": "properties.email"})
    assert "id" not in provider_shape
    assert "properties" in provider_shape


# --- dedup key -------------------------------------------------------------

def test_dedup_key_stable_across_field_changes():
    r1 = {"_provider": "hubspot", "record_type": "contact", "internal_id": "42", "email": "old"}
    r2 = {"_provider": "hubspot", "record_type": "contact", "internal_id": "42", "email": "new"}
    assert dedup_key(r1) == dedup_key(r2)


def test_dedup_key_differs_across_providers():
    r1 = {"_provider": "hubspot", "record_type": "contact", "internal_id": "42"}
    r2 = {"_provider": "attio", "record_type": "contact", "internal_id": "42"}
    assert dedup_key(r1) != dedup_key(r2)


def test_dedup_key_no_watermark_leakage():
    r1 = {"_provider": "hubspot", "record_type": "contact", "internal_id": "42",
          "watermark": "2026-08-04T10:00:00Z"}
    r2 = {"_provider": "hubspot", "record_type": "contact", "internal_id": "42",
          "watermark": "2026-08-04T11:00:00Z"}
    # A record's identity does not change when its watermark ticks forward.
    assert dedup_key(r1) == dedup_key(r2)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
