"""CRM sync driver — provider ↔ destination, incremental + idempotent.

description: Reads records from a CRM (via provider_adapters/), maps them to
             an internal shape (via mapping.py), writes them to a destination
             (via destinations/). Supports pull_only / push_only / bidirectional.
inputs:      --tenant <slug> (config file at config/tenant.<slug>.json)
             --dry-run (no external mutations; returns would_* counters)
             --incremental (default) / --full-refresh
             --subscribe-webhook (register webhook, then exit)
             --suggest-mapping (LLM-assisted field mapping; costs €0 on Gemini free)
             --mode {cheap,balanced,premium}  (used only by --suggest-mapping)
outputs:     JSONL stat line in .tmp/crm_sync_runs/<tenant>.jsonl per run;
             records upserted into destination.

Modes:
    cheap     — Gemini 2.5 Flash (default; free tier).
    balanced  — claude-sonnet-5 (paid Anthropic; only when budget approved).
    premium   — claude-opus-5 (paid; explicit override only).

The default sync path calls ZERO LLMs. --suggest-mapping is the only LLM path.

See also: directives/crm_and_pm/crm_integration_template.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure local package imports work whether run as module or script.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()

from config.schema import load_tenant_config, TenantConfig  # noqa: E402
from provider_adapters import get_adapter  # noqa: E402
from destinations import get_destination  # noqa: E402
from mapping import to_internal, dedup_key  # noqa: E402


# Workspace-standard model routing (currency: EUR per ~/.claude/rules/currency-eur.md).
MODE_TO_MODEL = {
    "cheap": "gemini-2.5-flash",
    "balanced": "claude-sonnet-5",
    "premium": "claude-opus-5",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _watermark_state_path(tenant_slug: str) -> Path:
    root = Path(os.environ.get("CRM_SYNC_LOG_DIR", "./.tmp/crm_sync_runs"))
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{tenant_slug}.state.json"


def _run_log_path(tenant_slug: str) -> Path:
    root = Path(os.environ.get("CRM_SYNC_LOG_DIR", "./.tmp/crm_sync_runs"))
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{tenant_slug}.jsonl"


def _load_watermark(tenant_slug: str) -> str | None:
    p = _watermark_state_path(tenant_slug)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("watermark")
    except json.JSONDecodeError:
        # Corrupt state — surface, don't silently reset. Bare-except is banned.
        raise RuntimeError(
            f"corrupt watermark state at {p}. "
            f"Delete manually if you accept a full re-pull."
        )


def _save_watermark(tenant_slug: str, watermark: str) -> None:
    p = _watermark_state_path(tenant_slug)
    p.write_text(json.dumps({"watermark": watermark, "saved_at": _now_iso()}), encoding="utf-8")


def _write_run_log(tenant_slug: str, stats: dict[str, Any]) -> None:
    p = _run_log_path(tenant_slug)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(stats, ensure_ascii=False) + "\n")


def _pull(
    cfg: TenantConfig,
    dry_run: bool,
    incremental: bool,
) -> dict[str, Any]:
    stats: dict[str, Any] = {
        "ts": _now_iso(),
        "tenant": cfg.tenant_slug,
        "mode": "pull",
        "dry_run": dry_run,
        "records_fetched": 0,
        "records_created": 0,
        "records_updated": 0,
        "records_skipped_dedup": 0,
        "errors": 0,
        "elapsed_ms": 0,
        "watermark_before": None,
        "watermark_after": None,
        "cost_eur_estimate": 0.0,
    }
    t0 = time.perf_counter()

    AdapterCls = get_adapter(cfg.provider.type)
    adapter = AdapterCls(cfg.model_dump())

    since = _load_watermark(cfg.tenant_slug) if incremental else None
    stats["watermark_before"] = since

    # Refuse to start if the plan can't reasonably fit the estimated request volume.
    # We estimate 1 request per page + 1 per max_pages pages max; conservative.
    expected_requests = max(1, cfg.sync.max_pages)
    try:
        adapter.preflight_quota(expected_requests)
    except Exception as e:
        stats["errors"] = 1
        stats["error_reason"] = f"preflight_quota_failed: {e}"
        stats["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
        _write_run_log(cfg.tenant_slug, stats)
        raise

    if dry_run:
        # Never open the destination; count fetches and short-circuit.
        page_count = 0
        latest_watermark = since
        for record in adapter.list_records(since_watermark=since):
            stats["records_fetched"] += 1
            internal = to_internal(
                record,
                provider=cfg.provider.type,
                field_mappings=cfg.field_mappings,
                id_path=cfg.provider.id_field,
                watermark_path=cfg.provider.watermark_field,
                record_type=cfg.provider.record_type,
            )
            if internal["watermark"] and (
                latest_watermark is None or internal["watermark"] > latest_watermark
            ):
                latest_watermark = internal["watermark"]
            page_count += 1
            if page_count >= cfg.sync.max_pages * 100:
                break
        stats["would_upsert"] = stats["records_fetched"]
        stats["watermark_after"] = latest_watermark
        stats["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
        _write_run_log(cfg.tenant_slug, stats)
        return stats

    DestCls = get_destination(cfg.destination.type)
    dest = DestCls(cfg.model_dump())

    seen_this_run: set[str] = set()
    latest_watermark = since
    try:
        for record in adapter.list_records(since_watermark=since):
            stats["records_fetched"] += 1
            internal = to_internal(
                record,
                provider=cfg.provider.type,
                field_mappings=cfg.field_mappings,
                id_path=cfg.provider.id_field,
                watermark_path=cfg.provider.watermark_field,
                record_type=cfg.provider.record_type,
            )
            key = dedup_key(internal)
            if key in seen_this_run:
                stats["records_skipped_dedup"] += 1
                continue
            seen_this_run.add(key)
            try:
                action = dest.upsert(internal)
                if action == "created":
                    stats["records_created"] += 1
                elif action == "updated":
                    stats["records_updated"] += 1
                else:
                    stats["records_skipped_dedup"] += 1
                if internal["watermark"] and (
                    latest_watermark is None or internal["watermark"] > latest_watermark
                ):
                    latest_watermark = internal["watermark"]
            except Exception as e:
                stats["errors"] += 1
                # Per python-hardening #5, log with reason — don't silently swallow.
                print(
                    f"[sync] upsert failed for {key}: {e}",
                    file=sys.stderr,
                )
    finally:
        dest.close()

    if latest_watermark and latest_watermark != since:
        _save_watermark(cfg.tenant_slug, latest_watermark)

    stats["watermark_after"] = latest_watermark
    stats["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
    _write_run_log(cfg.tenant_slug, stats)
    return stats


def _push(cfg: TenantConfig, dry_run: bool) -> dict[str, Any]:
    """Push-side: read internal records and CREATE/UPDATE in provider.

    Left as a scaffold. Real implementation requires: a source of internal
    records (Sheet reader / KV enumerator), a diff strategy against provider
    to decide create-vs-update, and conflict resolution rules. Each tenant's
    push spec differs enough that this is best handled per-tenant, using
    mapping.from_internal + adapter.create_record / update_record.
    """
    return {
        "ts": _now_iso(),
        "tenant": cfg.tenant_slug,
        "mode": "push",
        "dry_run": dry_run,
        "note": "push scaffold — implement per-tenant; use mapping.from_internal + adapter.create/update_record",
    }


def _subscribe_webhook(cfg: TenantConfig, target_url: str) -> dict[str, Any]:
    if not cfg.webhook.enabled:
        raise RuntimeError(
            f"webhook not enabled in config for tenant {cfg.tenant_slug}. "
            f"set webhook.enabled = true and re-run."
        )
    secret = os.environ.get(cfg.webhook.secret_env, "")
    if not secret:
        raise RuntimeError(f"webhook secret env var {cfg.webhook.secret_env} is empty")
    AdapterCls = get_adapter(cfg.provider.type)
    adapter = AdapterCls(cfg.model_dump())
    result = adapter.subscribe_webhook(target_url, secret)
    print(json.dumps({"subscribed": True, "provider_response": result}, indent=2))
    return result


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CRM sync driver")
    p.add_argument("--tenant", required=True, help="tenant slug (matches config file)")
    p.add_argument("--config-dir", default="config", help="directory of tenant configs")
    p.add_argument("--dry-run", action="store_true", help="no external mutations")
    p.add_argument("--full-refresh", action="store_true", help="ignore watermark, pull everything")
    p.add_argument("--push", action="store_true", help="push-side sync only")
    p.add_argument(
        "--subscribe-webhook",
        metavar="TARGET_URL",
        help="register webhook with provider and exit",
    )
    p.add_argument(
        "--mode",
        choices=list(MODE_TO_MODEL.keys()),
        default="cheap",
        help="LLM tier for --suggest-mapping (default: cheap = Gemini free)",
    )
    return p.parse_args()


def _resolve_config_path(config_dir: str, tenant_slug: str) -> Path:
    # Look up config: tenant.<slug>.json OR (if slug == example) tenant.example.json
    root = Path(config_dir)
    if not root.is_absolute():
        root = _HERE / root
    candidates = [
        root / f"tenant.{tenant_slug}.json",
        root / f"{tenant_slug}.json",
        root / "tenant.example.json" if tenant_slug == "example" else None,
    ]
    for c in candidates:
        if c and c.exists():
            return c
    raise FileNotFoundError(
        f"no tenant config found for {tenant_slug!r} in {root} "
        f"(looked for: tenant.<slug>.json, <slug>.json)"
    )


def main() -> int:
    args = parse_args()
    cfg_path = _resolve_config_path(args.config_dir, args.tenant)
    cfg = load_tenant_config(cfg_path)

    if args.subscribe_webhook:
        _subscribe_webhook(cfg, args.subscribe_webhook)
        return 0

    if args.push or cfg.sync.mode == "push_only":
        stats = _push(cfg, dry_run=args.dry_run)
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        return 0

    incremental = cfg.sync.incremental and not args.full_refresh
    stats = _pull(cfg, dry_run=args.dry_run, incremental=incremental)

    if cfg.sync.mode == "bidirectional" and not args.dry_run:
        push_stats = _push(cfg, dry_run=False)
        stats["push"] = push_stats

    print(json.dumps(stats, indent=2, ensure_ascii=False))
    # Non-zero exit on any errors so CI notices.
    return 1 if stats.get("errors", 0) > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
