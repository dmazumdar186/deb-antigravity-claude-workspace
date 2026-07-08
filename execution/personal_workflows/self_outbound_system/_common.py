"""
_common.py
description: Shared helpers for the self_outbound_system pipeline. Path helpers, timestamped filename builders, EUR conversion constant, argparse defaults. No side effects at import time.
inputs: None (imported by sibling scripts).
outputs: Constants and small pure functions.

Rules honored:
- ~/.claude/rules/python-execution.md (docstring shape, pathlib, no side effects)
- ~/.claude/rules/currency-eur.md (USD_TO_EUR at 0.92, exposed here as the single source of truth for cost-report conversion in this pipeline)
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import re
from pathlib import Path
from typing import Any

# Update when EUR/USD moves >5%. See ~/.claude/rules/currency-eur.md
USD_TO_EUR: float = 0.92

# Anthropic Sonnet 4.6 pricing (USD per million tokens) with cache-aware entries
# per ~/.claude/rules/python-hardening.md rule 4. Values match Anthropic published
# pricing for claude-sonnet-4-6 as of 2026-07-08.
SONNET_46_PRICING_USD_PER_MTOK: dict[str, float] = {
    "input": 3.0,
    "cache_read": 0.30,   # 0.1x input
    "cache_write": 3.75,  # 1.25x input
    "output": 15.0,
}

# Gemini 2.5 Flash pricing (USD per million tokens). No cache tier in current
# free-tier accounting; we keep the same 4-key shape for consistency.
GEMINI_25_FLASH_PRICING_USD_PER_MTOK: dict[str, float] = {
    "input": 0.075,
    "cache_read": 0.019,
    "cache_write": 0.09,
    "output": 0.30,
}

ROOT: Path = Path(__file__).resolve().parent
WORKSPACE_ROOT: Path = ROOT.parents[2]  # execution/personal_workflows/self_outbound_system -> workspace root
CONFIG_DIR: Path = ROOT / "config"
TESTS_DIR: Path = ROOT / "tests"
FIXTURES_DIR: Path = TESTS_DIR / "fixtures"
TMP_DIR: Path = WORKSPACE_ROOT / ".tmp" / "self_outbound"

EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9\-.]+$")


def ensure_tmp_dir() -> Path:
    """Create the pipeline's intermediates directory if missing; return it."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    return TMP_DIR


def timestamp() -> str:
    """Return a filesystem-safe UTC ISO-8601 timestamp, e.g. 20260708T093015Z."""
    return _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def today_str() -> str:
    """Return the UTC date as YYYYMMDD."""
    return _dt.datetime.utcnow().strftime("%Y%m%d")


def usd_to_eur(usd: float) -> float:
    """Convert a USD price to EUR using the workspace-wide constant."""
    return round(usd * USD_TO_EUR, 6)


def anthropic_cost_usd(
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    pricing: dict[str, float] | None = None,
) -> float:
    """Cache-aware Sonnet cost calc (USD). Accepts all 4 token classes per
    ~/.claude/rules/python-hardening.md rule 4."""
    p = pricing or SONNET_46_PRICING_USD_PER_MTOK
    return (
        input_tokens * p["input"]
        + output_tokens * p["output"]
        + cache_read_tokens * p["cache_read"]
        + cache_write_tokens * p["cache_write"]
    ) / 1_000_000


def anthropic_cost_eur(
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    pricing: dict[str, float] | None = None,
) -> float:
    """EUR wrapper around anthropic_cost_usd. User-facing per currency-eur rule."""
    return usd_to_eur(
        anthropic_cost_usd(
            input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, pricing
        )
    )


def load_json(path: Path) -> Any:
    """Read a JSON file with utf-8 encoding, returning parsed content."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: Any) -> Path:
    """Write a JSON file with utf-8 encoding + indented shape. Validates
    non-None before writing per python-execution rule."""
    if payload is None:
        raise ValueError(f"refuse to write None to {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=False)
    return path


def get_logger(name: str) -> logging.Logger:
    """Configured logger. Info-level, one-line message shape."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def is_valid_email(email: str) -> bool:
    """Cheap format check. Does not verify deliverability."""
    return bool(email and EMAIL_RE.match(email))


def print_stat(script: str, stats: dict[str, Any]) -> None:
    """Uniform stat line at end of each script, JSON-encoded for grep-ability."""
    print(f"[STAT] {script} " + json.dumps(stats, ensure_ascii=False, sort_keys=True))


# ---------------------------------------------------------------------------
# Config-schema validation (anneal MEDIUM 2026-07-08).
# Fail-fast on malformed icp.json / tone.json so a bad diff can't silently
# yield 0-kept-leads or a personalizer with no variants.
# ---------------------------------------------------------------------------

_REQUIRED_ICP_KEYS: tuple[str, ...] = ("segments", "anti_icp", "signal_rule")
_REQUIRED_TONE_KEYS: tuple[str, ...] = ("voice", "opener_constraints", "subject_constraints", "variants", "cta")


def validate_icp_config(cfg: dict) -> None:
    """Raise SystemExit(2) with a clear message if icp.json is malformed.
    Call at boot before any filter or send. See anneal-reviewer 2026-07-08."""
    if not isinstance(cfg, dict):
        raise SystemExit("icp.json is not a JSON object (dict). Fix and retry.")
    missing = [k for k in _REQUIRED_ICP_KEYS if k not in cfg]
    if missing:
        raise SystemExit(
            f"icp.json is missing required top-level keys: {missing}. "
            f"Config load-time schema check per ~/.claude/rules/mandatory-audit-stack.md."
        )
    if not isinstance(cfg.get("segments"), dict) or not cfg["segments"]:
        raise SystemExit("icp.json.segments must be a non-empty dict.")
    if not isinstance(cfg.get("anti_icp"), dict):
        raise SystemExit("icp.json.anti_icp must be a dict.")
    signal_rule = cfg.get("signal_rule", {})
    if not isinstance(signal_rule, dict) or "min_signals" not in signal_rule:
        raise SystemExit("icp.json.signal_rule.min_signals is required.")
    # Anti-ICP list keys must be lists (not None or scalars).
    for key in ("reject_if_any_keyword", "reject_if_role_matches", "reject_if_domain_matches"):
        v = cfg["anti_icp"].get(key, [])
        if not isinstance(v, list):
            raise SystemExit(f"icp.json.anti_icp.{key} must be a list (got {type(v).__name__}).")


def validate_tone_config(cfg: dict) -> None:
    """Raise SystemExit(2) with a clear message if tone.json is malformed."""
    if not isinstance(cfg, dict):
        raise SystemExit("tone.json is not a JSON object. Fix and retry.")
    missing = [k for k in _REQUIRED_TONE_KEYS if k not in cfg]
    if missing:
        raise SystemExit(f"tone.json is missing required top-level keys: {missing}. Fix and retry.")
    variants = cfg.get("variants", {})
    if not isinstance(variants, dict) or not variants:
        raise SystemExit("tone.json.variants must be a non-empty dict.")
    for vname, vcfg in variants.items():
        if "audience_segment" not in vcfg:
            raise SystemExit(f"tone.json.variants.{vname}.audience_segment is required.")
