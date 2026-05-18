"""
description: Provider-agnostic model registry — resolves tier labels to concrete model IDs at runtime
             by querying each provider's models.list() API. Results are cached locally for 7 days.
             Falls back to cache, then to LAST_KNOWN_GOOD literals, so it never crashes on missing keys.
             v3: added OpenRouter resolver with strict ALLOWED_FAMILIES allowlist.
inputs: env ANTHROPIC_API_KEY (optional), GEMINI_API_KEY (optional), OPENROUTER_API_KEY (optional);
        CLI --refresh forces a cache bypass.
outputs: Concrete model ID string (e.g. 'claude-sonnet-4-6', 'gemini-2.5-flash',
         'anthropic/claude-sonnet-4-6'); cache written to .tmp/model_registry.json;
         INFO log lines on resolution.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Fix 1 — prevent Unicode crash on Windows cp1252 when run as CLI
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed; env vars must be set externally

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ALLOWED_FAMILIES — hard allowlist for OpenRouter resolution.
# Models outside these families are NEVER considered, regardless of recency.
# Edit this list to add/remove provider families as the landscape evolves.
# ---------------------------------------------------------------------------
ALLOWED_FAMILIES = ("anthropic/", "openai/", "google/")

# ---------------------------------------------------------------------------
# LAST_KNOWN_GOOD — the ONLY place model IDs appear as literals in this file.
# Updated manually ~quarterly when logs show stale models being picked.
# ---------------------------------------------------------------------------
LAST_KNOWN_GOOD: dict[str, dict[str, str]] = {
    "anthropic": {"default": "claude-sonnet-4-6", "premium": "claude-opus-4-7"},
    "gemini": {"default": "gemini-2.5-flash"},
    "openrouter": {
        # Fix 14 — OR catalog uses dots (4.6, 4.7), not dashes (4-6, 4-7)
        "default": "anthropic/claude-sonnet-4.6",
        "premium": "anthropic/claude-opus-4.7",
        "gemini":  "google/gemini-2.5-pro",  # for OR-only setup, Gemini tier via OR
    },
}

# Cache config
_WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
_CACHE_PATH = _WORKSPACE_ROOT / ".tmp" / "model_registry.json"
_TTL_DAYS = 7

# Module-level cache (avoids repeated disk reads in the same process)
_mem_cache: dict | None = None


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _load_cache() -> dict | None:
    """Return parsed cache dict if the file exists and is fresh, else None."""
    global _mem_cache
    if _mem_cache is not None:
        return _mem_cache
    if not _CACHE_PATH.exists():
        return None
    try:
        data = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        resolved_at = datetime.fromisoformat(data["resolved_at"])
        age_days = (datetime.now(timezone.utc) - resolved_at).days
        if age_days >= _TTL_DAYS:
            return None
        _mem_cache = data
        return data
    except Exception as exc:
        logger.debug("Cache read failed (%s) — treating as stale", exc)
        return None


def _save_cache(payload: dict) -> None:
    global _mem_cache
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Fix 15 — atomic write: write to .tmp then rename to avoid partial-read corruption
    tmp_path = _CACHE_PATH.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(_CACHE_PATH)
    _mem_cache = payload
    logger.info("Cache written: %s (TTL %d days)", _CACHE_PATH, _TTL_DAYS)


# ---------------------------------------------------------------------------
# Anthropic resolution
# ---------------------------------------------------------------------------

# Matches IDs like claude-sonnet-4-6, claude-opus-4-7, claude-haiku-3-5
_ANTHROPIC_RE = re.compile(
    r"^claude-(?P<family>[a-z]+)-(?P<maj>\d+)(?:-(?P<min>\d+))?",
    re.IGNORECASE,
)

_FAMILY_RANK_PREMIUM = ["opus", "sonnet", "haiku"]
_FAMILY_RANK_DEFAULT = ["sonnet", "haiku"]


def _resolve_anthropic(tier: str) -> tuple[str, str | None]:
    """
    Query Anthropic models.list() and return (model_id, created_at_iso).
    Raises on network/auth failure so caller can fall back.
    """
    import anthropic  # lazy import — only when key is available

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    client = anthropic.Anthropic(api_key=api_key)

    # Collect all models with parsed metadata
    models = list(client.models.list())

    parsed: list[tuple[str, str, int, int, str | None]] = []  # (family, id, maj, min, created_at)
    unmatched: list[tuple[str, str | None]] = []  # (id, created_at) for fallback

    for m in models:
        model_id: str = m.id
        created_at: str | None = getattr(m, "created_at", None)
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()
        match = _ANTHROPIC_RE.match(model_id)
        if match:
            family = match.group("family").lower()
            maj = int(match.group("maj"))
            min_ = int(match.group("min") or 0)
            parsed.append((family, model_id, maj, min_, created_at))
        else:
            unmatched.append((model_id, created_at))

    family_rank = _FAMILY_RANK_PREMIUM if tier == "premium" else _FAMILY_RANK_DEFAULT

    for preferred_family in family_rank:
        candidates = [
            (model_id, maj, min_, created_at)
            for (family, model_id, maj, min_, created_at) in parsed
            if family == preferred_family
        ]
        if candidates:
            # Sort by (maj, min) descending → pick latest
            best = sorted(candidates, key=lambda x: (x[1], x[2]), reverse=True)[0]
            return best[0], best[3]

    # Family-unknown fallback: most recently created for premium, second-most for default
    all_with_created = [
        (model_id, created_at)
        for (_, model_id, _, _, created_at) in parsed
    ] + unmatched

    all_with_created.sort(key=lambda x: x[1] or "", reverse=True)
    idx = 0 if tier == "premium" else 1
    if idx < len(all_with_created):
        return all_with_created[idx]

    raise RuntimeError("No Anthropic models found")


# ---------------------------------------------------------------------------
# Gemini resolution
# ---------------------------------------------------------------------------

_GEMINI_FLASH_RE = re.compile(
    r"^models/gemini-(?P<ver>[\d.]+)-flash",
    re.IGNORECASE,
)


def _resolve_gemini(_tier: str) -> tuple[str, str | None]:
    """
    Query Gemini models list and return (model_id, created_at_iso).
    Only 'default' tier is supported for Gemini (always Flash); _tier is
    accepted for API uniformity with _resolve_anthropic but is not used.
    Raises on network/auth failure.
    """
    from google import genai  # lazy import

    api_key = os.environ.get("GEMINI_API_KEY", "")
    client = genai.Client(api_key=api_key)

    models = list(client.models.list())

    flash_candidates: list[tuple[str, float, str | None]] = []
    all_candidates: list[tuple[str, str | None]] = []

    for m in models:
        # name is like 'models/gemini-2.5-flash'
        raw_name: str = getattr(m, "name", "") or ""
        # Expose as bare ID without 'models/' prefix
        model_id = raw_name.removeprefix("models/")
        created_at: str | None = getattr(m, "create_time", None)
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()
        elif created_at is not None:
            created_at = str(created_at)

        all_candidates.append((model_id, created_at))

        flash_match = _GEMINI_FLASH_RE.match(raw_name)
        if flash_match:
            try:
                ver = float(flash_match.group("ver"))
            except ValueError:
                ver = 0.0
            flash_candidates.append((model_id, ver, created_at))

    if flash_candidates:
        # Latest flash by version number
        best = sorted(flash_candidates, key=lambda x: x[1], reverse=True)[0]
        return best[0], best[2]

    # Recency fallback: most recently created Gemini model
    all_candidates.sort(key=lambda x: x[1] or "", reverse=True)
    if all_candidates:
        return all_candidates[0]

    raise RuntimeError("No Gemini models found")


# ---------------------------------------------------------------------------
# OpenRouter resolution  (v3 — no auth required for model listing)
# ---------------------------------------------------------------------------

# Regex helpers for parsing OR model IDs
_OR_CLAUDE_OPUS_RE = re.compile(r"^anthropic/claude-opus-(\d+)", re.IGNORECASE)
_OR_CLAUDE_SONNET_RE = re.compile(r"^anthropic/claude-sonnet-(\d+)", re.IGNORECASE)
_OR_CLAUDE_HAIKU_RE = re.compile(r"^anthropic/claude-haiku-(\d+)", re.IGNORECASE)
_OR_GPT5_RE = re.compile(r"^openai/gpt-5", re.IGNORECASE)
_OR_GPT4O_RE = re.compile(r"^openai/gpt-4o(?!-mini)", re.IGNORECASE)  # Fix 6 — exclude gpt-4o-mini
_OR_GEMINI3_RE = re.compile(r"^google/gemini-3", re.IGNORECASE)
_OR_GEMINI25PRO_RE = re.compile(r"^google/gemini-2\.5-pro", re.IGNORECASE)
_OR_GEMINI25FLASH_RE = re.compile(r"^google/gemini-2\.5-flash", re.IGNORECASE)
_OR_GPT4O_MINI_RE = re.compile(r"^openai/gpt-4o-mini", re.IGNORECASE)


def _or_unix_to_iso(created: int | float | None) -> str | None:
    """Convert unix timestamp (seconds) to ISO 8601 string."""
    if created is None:
        return None
    try:
        return datetime.fromtimestamp(float(created), tz=timezone.utc).isoformat()
    except (ValueError, OSError, OverflowError):
        return None


def _resolve_openrouter(tier: str) -> tuple[str, str | None]:
    """
    Resolve the best OpenRouter model for the given tier.

    Uses the public GET /api/v1/models endpoint (no auth required for listing).
    Applies ALLOWED_FAMILIES allowlist FIRST, then vision + tools capability
    filters, then a family-preference ladder.

    Parameters
    ----------
    tier : str
        One of 'default', 'premium', 'gemini'.

    Returns
    -------
    tuple[str, str | None]
        (model_id, created_at_iso) where model_id is e.g. 'anthropic/claude-sonnet-4-6'.

    Raises
    ------
    RuntimeError
        If no allowed, vision-capable, tool-capable models are found (triggers
        LAST_KNOWN_GOOD fallback in the caller).
    """
    import requests  # stdlib-compatible; already in standard Python env

    url = "https://openrouter.ai/api/v1/models"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        raise RuntimeError(f"OpenRouter /models fetch failed: {exc}") from exc

    raw_models = data.get("data", [])
    # Fix 10 — validate shape before iterating
    if not isinstance(raw_models, list):
        raise RuntimeError(
            f"OR /models returned unexpected 'data' shape: {type(raw_models).__name__}"
        )

    # Fix 16 — stricter allowlist: reject "legacy", "test", "deprecated" suffixes
    def _is_allowed_id(id_: str) -> bool:
        for prefix in ALLOWED_FAMILIES:
            if id_.startswith(prefix):
                rest = id_[len(prefix):]
                if rest.startswith("legacy") or rest.startswith("test") or rest.startswith("deprecated"):
                    return False
                return True
        return False

    # Step 1 — ALLOWLIST FILTER (applied first, before any other filter)
    allowed = [m for m in raw_models if _is_allowed_id(m.get("id", ""))]
    logger.debug("OR allowlist: %d/%d models kept", len(allowed), len(raw_models))

    # Step 2 — Vision filter
    vision = [
        m for m in allowed
        if "image" in m.get("architecture", {}).get("input_modalities", [])
    ]
    logger.debug("OR vision filter: %d models kept", len(vision))

    # Step 3 — Tools filter
    capable = [
        m for m in vision
        if "tools" in m.get("supported_parameters", [])
    ]
    logger.debug("OR tools filter: %d models kept", len(capable))

    if not capable:
        raise RuntimeError(
            "No allowed vision+tools models found on OpenRouter — "
            "allowlist or capability filter may be too restrictive."
        )

    # Helper: pick most recent model matching a regex
    def _best_match(pattern: re.Pattern, pool: list[dict]) -> dict | None:
        matches = [m for m in pool if pattern.search(m.get("id", ""))]
        if not matches:
            return None
        return sorted(matches, key=lambda m: m.get("created", 0) or 0, reverse=True)[0]

    # Helper: pick highest versioned claude-* model
    def _best_claude_family(family_re: re.Pattern, pool: list[dict]) -> dict | None:
        """Return the model with the highest version number from a claude family."""
        best_m: dict | None = None
        best_ver = -1
        for m in pool:
            match = family_re.match(m.get("id", ""))
            if match:
                try:
                    ver = int(match.group(1))
                except (IndexError, ValueError):
                    ver = 0
                if ver > best_ver:
                    best_ver = ver
                    best_m = m
        return best_m

    # ---------------------------------------------------------------------------
    # Premium ladder: opus > gpt-5 > gpt-4o > gemini-3 > gemini-2.5-pro > sonnet
    # ---------------------------------------------------------------------------
    if tier == "premium":
        for picker, label in [
            (lambda p: _best_claude_family(_OR_CLAUDE_OPUS_RE, p), "claude-opus-*"),
            (lambda p: _best_match(_OR_GPT5_RE, p),                "gpt-5*"),
            (lambda p: _best_match(_OR_GPT4O_RE, p),               "gpt-4o"),
            (lambda p: _best_match(_OR_GEMINI3_RE, p),             "gemini-3*"),
            (lambda p: _best_match(_OR_GEMINI25PRO_RE, p),         "gemini-2.5-pro"),
            (lambda p: _best_claude_family(_OR_CLAUDE_SONNET_RE, p), "claude-sonnet-*"),
        ]:
            chosen = picker(capable)
            if chosen:
                model_id = chosen["id"]
                created_iso = _or_unix_to_iso(chosen.get("created"))
                logger.info("OR premium → %s (matched %s)", model_id, label)
                return model_id, created_iso

    # ---------------------------------------------------------------------------
    # Default ladder: sonnet > haiku > gpt-4o-mini > gemini-2.5-flash
    # ---------------------------------------------------------------------------
    elif tier in ("default", "gemini"):
        for picker, label in [
            (lambda p: _best_claude_family(_OR_CLAUDE_SONNET_RE, p), "claude-sonnet-*"),
            (lambda p: _best_claude_family(_OR_CLAUDE_HAIKU_RE, p),  "claude-haiku-*"),
            (lambda p: _best_match(_OR_GPT4O_MINI_RE, p),            "gpt-4o-mini"),
            (lambda p: _best_match(_OR_GEMINI25FLASH_RE, p),         "gemini-2.5-flash"),
        ] if tier == "default" else [
            # For 'gemini' sub-tier: prefer gemini-2.5-pro specifically
            (lambda p: _best_match(_OR_GEMINI25PRO_RE, p),           "gemini-2.5-pro"),
            (lambda p: _best_match(_OR_GEMINI3_RE, p),               "gemini-3*"),
            (lambda p: _best_claude_family(_OR_CLAUDE_SONNET_RE, p), "claude-sonnet-*"),
        ]:
            chosen = picker(capable)
            if chosen:
                model_id = chosen["id"]
                created_iso = _or_unix_to_iso(chosen.get("created"))
                logger.info("OR %s → %s (matched %s)", tier, model_id, label)
                return model_id, created_iso

    raise RuntimeError(f"No suitable OpenRouter model found for tier='{tier}'")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_RESOLVERS = {
    "anthropic": _resolve_anthropic,
    "gemini": _resolve_gemini,
    "openrouter": _resolve_openrouter,
}


def resolve_model(
    provider: str,
    tier: str,
    refresh: bool = False,
    allow_network: bool = True,
) -> str:
    """
    Resolve a provider+tier label to a concrete model ID.

    Parameters
    ----------
    provider : str
        One of 'anthropic', 'gemini', 'openrouter'.
    tier : str
        One of 'default', 'premium'. Gemini only supports 'default'.
        OpenRouter also supports 'gemini' sub-tier (Gemini via OR).
    refresh : bool
        If True, bypass the local cache and re-query the provider API.
    allow_network : bool
        If False (offline / shallow-dry-run mode), skip the live API call entirely.
        Resolution order becomes: cache → LAST_KNOWN_GOOD, with no HTTP requests made.
        Defaults to True (normal behaviour).

    Returns
    -------
    str
        Concrete model ID (e.g. 'claude-sonnet-4-6', 'anthropic/claude-sonnet-4-6').
        Never raises — falls back to LAST_KNOWN_GOOD on all failures.
    """
    provider = provider.lower()
    tier = tier.lower()

    if provider not in LAST_KNOWN_GOOD:
        raise ValueError(f"Unknown provider '{provider}'. Supported: {list(LAST_KNOWN_GOOD)}")
    if tier not in LAST_KNOWN_GOOD[provider]:
        raise ValueError(
            f"Unknown tier '{tier}' for provider '{provider}'. "
            f"Supported: {list(LAST_KNOWN_GOOD[provider])}"
        )

    # 1. Try cache (unless refresh forced)
    if not refresh:
        cache = _load_cache()
        if cache and provider in cache and tier in cache[provider]:
            cached_id = cache[provider][tier]
            logger.debug("Cache hit: %s/%s → %s", provider, tier, cached_id)
            return cached_id

    # 1b. Offline mode: cache miss → fall straight to LAST_KNOWN_GOOD (no HTTP)
    if not allow_network:
        fallback = LAST_KNOWN_GOOD[provider][tier]
        logger.warning(
            "Offline mode (allow_network=False); using LAST_KNOWN_GOOD for %s/%s → %s",
            provider, tier, fallback,
        )
        return fallback

    # 2. Try live API
    resolver = _RESOLVERS.get(provider)

    # For OpenRouter, listing is anonymous — no key needed for resolution.
    # Key is only required for actual inference calls.
    if provider == "openrouter":
        api_key_present = True  # listing always works without a key
        api_key_env = "OPENROUTER_API_KEY"
    else:
        api_key_env = "ANTHROPIC_API_KEY" if provider == "anthropic" else "GEMINI_API_KEY"
        api_key_present = bool(os.environ.get(api_key_env, ""))

    if not api_key_present:
        logger.warning(
            "%s not set — cannot query %s models API; falling back to cache/LAST_KNOWN_GOOD",
            api_key_env,
            provider,
        )
    elif resolver:
        try:
            model_id, created_at = resolver(tier)
            created_str = created_at or "unknown"
            logger.info(
                "Resolved %s %s → %s (created %s)", provider, tier, model_id, created_str
            )

            # Refresh and save the full cache with all providers + tiers we know
            cache = _load_cache() or {}
            cache.setdefault(provider, {})[tier] = model_id
            cache["resolved_at"] = datetime.now(timezone.utc).isoformat()
            cache["ttl_days"] = _TTL_DAYS
            _save_cache(cache)

            return model_id

        except Exception as exc:
            logger.warning(
                "Failed to resolve %s/%s from API (%s) — falling back to cache/LAST_KNOWN_GOOD",
                provider,
                tier,
                exc,
            )

    # 3. Stale cache fallback (even if TTL exceeded, better than nothing)
    if _CACHE_PATH.exists():
        try:
            stale = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
            if provider in stale and tier in stale[provider]:
                stale_id = stale[provider][tier]
                logger.warning(
                    "Using stale cache for %s/%s → %s", provider, tier, stale_id
                )
                return stale_id
        except Exception:
            pass

    # 4. LAST_KNOWN_GOOD — absolute fallback
    fallback = LAST_KNOWN_GOOD[provider][tier]
    logger.warning("Using LAST_KNOWN_GOOD for %s/%s → %s", provider, tier, fallback)
    return fallback


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _refresh_all() -> None:
    """Force-refresh all providers/tiers and print results."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(message)s",
    )
    results: dict[str, dict[str, str]] = {}
    for provider, tiers in LAST_KNOWN_GOOD.items():
        results[provider] = {}
        for tier in tiers:
            model_id = resolve_model(provider, tier, refresh=True)
            results[provider][tier] = model_id

    print("\nResolved model IDs:")
    for provider, tiers in results.items():
        for tier, model_id in tiers.items():
            print(f"  {provider:12s} {tier:10s} -> {model_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Model registry CLI")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force refresh from provider APIs (bypass cache)",
    )
    args = parser.parse_args()

    if args.refresh:
        _refresh_all()
    else:
        # Default: print current resolved IDs (using cache if fresh)
        logging.basicConfig(level=logging.WARNING, format="%(levelname)s | %(message)s")
        print("Current resolved model IDs (use --refresh to force re-fetch):")
        for provider, tiers in LAST_KNOWN_GOOD.items():
            for tier in tiers:
                model_id = resolve_model(provider, tier, refresh=False)
                print(f"  {provider:12s} {tier:10s} -> {model_id}")
