"""Tenant config schema — fail-fast validation at boot.

description: Pydantic-based schema for per-tenant config JSON files.
inputs:      Path to tenant config JSON, live os.environ
outputs:     Validated TenantConfig instance, or SystemExit with the offending
             field path and reason.

The schema enforces:
- Every required env-var reference is set and non-empty at boot.
- Rate-limit math is coherent (window > 0, requests > 0).
- Field mappings' internal keys are unique.
- Destination type is one of the registered destinations.
- Provider type is one of the registered adapters.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal

try:
    from pydantic import BaseModel, Field, ValidationError, field_validator
except ImportError:  # pragma: no cover — clean install path
    print("pydantic missing. Install with: pip install pydantic>=2.5", file=sys.stderr)
    sys.exit(2)


Provider = Literal["hubspot", "pipedrive", "attio", "clickup", "airtable", "fixture"]
Destination = Literal["google_sheet", "jsonl", "kv"]


class RateLimit(BaseModel):
    requests_per_window: int = Field(gt=0)
    window_seconds: int = Field(gt=0)


class ProviderConfig(BaseModel):
    type: Provider
    credentials_env: list[str] = Field(
        description="Env-var names required for this provider. Validated non-empty at boot."
    )
    rate_limit: RateLimit
    watermark_field: str = Field(default="updated_at")
    id_field: str = Field(default="id")
    record_type: str = Field(default="contact")


class DestinationConfig(BaseModel):
    type: Destination
    credentials_env: list[str] = Field(default_factory=list)
    target: str = Field(description="e.g. sheet_id, KV namespace binding, file path.")


class SyncConfig(BaseModel):
    mode: Literal["pull_only", "push_only", "bidirectional"] = "pull_only"
    incremental: bool = True
    dedup_ttl_seconds: int = Field(default=60 * 60 * 24 * 60, gt=0)  # 60 days
    max_pages: int = Field(default=100, gt=0)


class WebhookConfig(BaseModel):
    enabled: bool = False
    secret_env: str = Field(default="WEBHOOK_SECRET")
    kv_dedup_binding: str = Field(default="WEBHOOK_DEDUP")


class TenantConfig(BaseModel):
    tenant_slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_-]+$")
    provider: ProviderConfig
    destination: DestinationConfig
    sync: SyncConfig = Field(default_factory=SyncConfig)
    webhook: WebhookConfig = Field(default_factory=WebhookConfig)
    field_mappings: dict[str, str] = Field(
        description="{internal_key: dot.path.in.provider.record}"
    )

    @field_validator("field_mappings")
    @classmethod
    def _mappings_nonempty(cls, v: dict[str, str]) -> dict[str, str]:
        if not v:
            raise ValueError("field_mappings must have at least one entry")
        for k in v:
            if not k or not isinstance(k, str):
                raise ValueError(f"invalid internal_key: {k!r}")
        return v


def load_tenant_config(path: Path) -> TenantConfig:
    """Load + validate a tenant config JSON. Exit 2 with a readable message on failure.

    ALSO validates every env var referenced under `credentials_env` is set and
    non-empty in os.environ RIGHT NOW. This is the fail-fast at boot; a missing
    HUBSPOT_ACCESS_TOKEN should not surface as a 401 twenty minutes into a sync.
    """
    import json

    if not path.exists():
        print(f"config not found: {path}", file=sys.stderr)
        sys.exit(2)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"config not valid JSON: {path}: {e}", file=sys.stderr)
        sys.exit(2)

    try:
        cfg = TenantConfig(**raw)
    except ValidationError as e:
        print(f"config schema failed for {path}:", file=sys.stderr)
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"])
            print(f"  - {loc}: {err['msg']}", file=sys.stderr)
        sys.exit(2)

    missing: list[str] = []
    for var in cfg.provider.credentials_env + cfg.destination.credentials_env:
        if not os.environ.get(var):
            missing.append(var)
    if cfg.webhook.enabled and not os.environ.get(cfg.webhook.secret_env):
        missing.append(cfg.webhook.secret_env)
    if missing:
        print(
            f"missing required env vars for tenant {cfg.tenant_slug}: {', '.join(missing)}",
            file=sys.stderr,
        )
        print("add them to .env then re-run.", file=sys.stderr)
        sys.exit(2)

    return cfg
