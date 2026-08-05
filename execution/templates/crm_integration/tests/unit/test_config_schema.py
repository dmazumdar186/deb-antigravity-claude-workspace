"""Unit tests for config/schema.py — validation + fail-fast at boot."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_TEMPLATE_ROOT = Path(__file__).resolve().parents[2]
if str(_TEMPLATE_ROOT) not in sys.path:
    sys.path.insert(0, str(_TEMPLATE_ROOT))

import pytest  # noqa: E402

from config.schema import load_tenant_config, TenantConfig  # noqa: E402


def _write(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "tenant.test.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _minimal_config() -> dict:
    return {
        "tenant_slug": "test",
        "provider": {
            "type": "fixture",
            "credentials_env": [],
            "rate_limit": {"requests_per_window": 10, "window_seconds": 1},
        },
        "destination": {"type": "jsonl", "credentials_env": [], "target": "./x.jsonl"},
        "field_mappings": {"email": "properties.email"},
    }


def test_minimal_config_loads(tmp_path):
    cfg = load_tenant_config(_write(tmp_path, _minimal_config()))
    assert isinstance(cfg, TenantConfig)
    assert cfg.tenant_slug == "test"


def test_missing_config_exits_2(tmp_path):
    with pytest.raises(SystemExit) as e:
        load_tenant_config(tmp_path / "nope.json")
    assert e.value.code == 2


def test_invalid_slug_pattern_exits(tmp_path):
    data = _minimal_config()
    data["tenant_slug"] = "Not A Slug!"
    with pytest.raises(SystemExit) as e:
        load_tenant_config(_write(tmp_path, data))
    assert e.value.code == 2


def test_empty_field_mappings_exits(tmp_path):
    data = _minimal_config()
    data["field_mappings"] = {}
    with pytest.raises(SystemExit) as e:
        load_tenant_config(_write(tmp_path, data))
    assert e.value.code == 2


def test_missing_env_var_exits(tmp_path, monkeypatch):
    data = _minimal_config()
    data["provider"]["type"] = "hubspot"
    data["provider"]["credentials_env"] = ["HUBSPOT_ACCESS_TOKEN"]
    # Ensure env var is not set. Use dict(os.environ) semantics (per
    # ~/.claude/rules/environ-not-copy-copy.md), monkeypatch handles cleanly.
    monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
    with pytest.raises(SystemExit) as e:
        load_tenant_config(_write(tmp_path, data))
    assert e.value.code == 2


def test_env_var_present_passes(tmp_path, monkeypatch):
    data = _minimal_config()
    data["provider"]["type"] = "hubspot"
    data["provider"]["credentials_env"] = ["HUBSPOT_ACCESS_TOKEN"]
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "test-token")
    cfg = load_tenant_config(_write(tmp_path, data))
    assert cfg.provider.type == "hubspot"


def test_rate_limit_must_be_positive(tmp_path):
    data = _minimal_config()
    data["provider"]["rate_limit"]["requests_per_window"] = 0
    with pytest.raises(SystemExit):
        load_tenant_config(_write(tmp_path, data))


def test_unknown_provider_rejected(tmp_path):
    data = _minimal_config()
    data["provider"]["type"] = "notreal"
    with pytest.raises(SystemExit):
        load_tenant_config(_write(tmp_path, data))


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
