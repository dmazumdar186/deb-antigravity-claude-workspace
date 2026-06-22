"""
description: Universal model router — call any LLM (GLM 5.2, Opus, Sonnet, GPT-4o, Gemini) by alias.
             Routes to the cheapest available path: Anthropic / OpenAI / Gemini direct when keys are set,
             OpenRouter when not. Single `call_model(alias, ...)` function for click-of-a-button switching
             across providers.
inputs: env keys (ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY) — read at call time.
        Alias name, system prompt, user message, optional max_tokens / temperature / via_openrouter override.
outputs: dict with keys `text` (str), `model` (resolved id), `provider` (route taken), `usage` (token counts if available).
        Raises RuntimeError with a clear message when the chosen alias has no available route.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from typing import Any, Literal

try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Alias table — edit here when new models land. Each alias names:
#   native_provider: which direct SDK to try first
#   native_model:    the model ID for that direct SDK
#   or_model:        the model ID for OpenRouter (fallback)
#   sensitivity:     "public" | "sensitive_ok" — gate per model-tier.md guardrail
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Alias:
    native_provider: str  # "anthropic" | "openai" | "gemini" | "openrouter_only"
    native_model: str
    or_model: str
    sensitivity: str  # "public" only for GLM; "sensitive_ok" for the rest

ALIASES: dict[str, _Alias] = {
    # --- Anthropic ---
    "opus":    _Alias("anthropic", "claude-opus-4-7",    "anthropic/claude-opus-4.7",    "sensitive_ok"),
    "sonnet":  _Alias("anthropic", "claude-sonnet-4-6",  "anthropic/claude-sonnet-4.6",  "sensitive_ok"),
    # --- OpenAI ---
    "gpt4o":   _Alias("openai",    "gpt-4o",             "openai/gpt-4o",                "sensitive_ok"),
    "gpt":     _Alias("openai",    "gpt-4o",             "openai/gpt-4o",                "sensitive_ok"),  # convenience
    "o1":      _Alias("openai",    "o1",                 "openai/o1",                    "sensitive_ok"),
    # --- Google Gemini ---
    "gemini":      _Alias("gemini", "gemini-2.5-flash",  "google/gemini-2.5-flash",      "sensitive_ok"),
    "gemini-pro":  _Alias("gemini", "gemini-2.5-pro",    "google/gemini-2.5-pro",        "sensitive_ok"),
    # --- Z.AI / GLM (OR-only by design — Z.AI direct needs separate key) ---
    "glm":     _Alias("openrouter_only", "",             "z-ai/glm-5.2",                 "public"),
    "glm-5.2": _Alias("openrouter_only", "",             "z-ai/glm-5.2",                 "public"),
    "glm-4.7": _Alias("openrouter_only", "",             "z-ai/glm-4.7",                 "public"),
}


def list_aliases() -> list[str]:
    """Return sorted alias names."""
    return sorted(ALIASES.keys())


# Personal-mode remap: which alias to use as the cheap muscle in place of expensive ones.
# When mode="personal", any alias in this map is rerouted to its replacement, EXCEPT when
# the call carries sensitivity="sensitive" (which raises instead — see call_model).
_PERSONAL_REMAP: dict[str, str] = {
    "opus": "glm",
    "sonnet": "glm",
    "gpt": "glm",
    "gpt4o": "glm",
    "o1": "glm",
    # gemini, gemini-pro: unchanged (already free/cheap)
    # glm, glm-5.2, glm-4.7: unchanged
}


def call_model(
    alias: str,
    *,
    system: str,
    user: str,
    max_tokens: int = 1024,
    temperature: float | None = None,
    via_openrouter: bool = False,
    mode: Literal["client", "personal"] = "client",
    sensitivity: Literal["public", "sensitive"] = "public",
) -> dict[str, Any]:
    """Single-shot LLM call routed by alias.

    Args:
        alias: one of `list_aliases()`. Case-insensitive.
        system: system prompt.
        user: user message.
        max_tokens: max response tokens.
        temperature: optional sampling temperature.
        via_openrouter: force OpenRouter route even when a native key exists. Use when
                        you want consistent OR routing for cost accounting.
        mode: "client" (default — quality first, billable) or "personal" (cost first,
              remaps Opus/Sonnet/GPT to GLM via OR for ~$0). Per ~/.claude/rules/model-tier.md.
        sensitivity: "public" (default) or "sensitive". Sensitive payloads (PII, CV
              content, cold-email leads, AM-scoped, client data) MUST NOT route through
              public-only aliases (GLM family) — raises RuntimeError instead of silently
              leaking. Personal-mode also rejects sensitive payloads.

    Returns:
        {"text": str, "model": str, "provider": str, "usage": dict | None}

    Raises:
        ValueError: unknown alias.
        RuntimeError: no available route for the chosen alias (e.g. GLM but OR balance
                      empty); OR sensitivity="sensitive" with public-only target.
    """
    key = alias.lower().strip()
    if key not in ALIASES:
        raise ValueError(f"Unknown model alias '{alias}'. Available: {list_aliases()}")

    # Personal-mode remap: opus/sonnet/gpt → glm (the cheap muscle).
    # Sensitivity guardrail wins: sensitive payloads cannot be remapped to public-only.
    if mode == "personal" and sensitivity == "sensitive":
        raise RuntimeError(
            f"personal-mode rejected: sensitive payload requires client mode or an explicit "
            f"sensitive_ok alias (Anthropic / OpenAI / Gemini direct). Alias '{alias}' "
            f"with sensitivity='sensitive' is blocked from personal-mode remap."
        )
    if mode == "personal" and key in _PERSONAL_REMAP:
        original_key = key
        key = _PERSONAL_REMAP[key]
        logger.info("personal-mode remap: %s → %s", original_key, key)

    a = ALIASES[key]

    # Final sensitivity gate at the alias level: a public-only alias never receives sensitive data,
    # regardless of mode (catches client-mode calls that explicitly request GLM with sensitive data).
    if sensitivity == "sensitive" and a.sensitivity == "public":
        raise RuntimeError(
            f"alias '{key}' is public-only (sensitivity='public') and cannot accept sensitive payloads. "
            f"Use opus/sonnet/gpt/gemini for sensitive data."
        )

    # Routing decision
    if via_openrouter or a.native_provider == "openrouter_only":
        return _call_openrouter(a.or_model, system, user, max_tokens, temperature)
    if a.native_provider == "anthropic":
        if os.environ.get("ANTHROPIC_API_KEY"):
            return _call_anthropic(a.native_model, system, user, max_tokens, temperature)
        return _call_openrouter(a.or_model, system, user, max_tokens, temperature)
    if a.native_provider == "openai":
        if os.environ.get("OPENAI_API_KEY"):
            return _call_openai(a.native_model, system, user, max_tokens, temperature)
        return _call_openrouter(a.or_model, system, user, max_tokens, temperature)
    if a.native_provider == "gemini":
        if os.environ.get("GEMINI_API_KEY"):
            return _call_gemini(a.native_model, system, user, max_tokens, temperature)
        return _call_openrouter(a.or_model, system, user, max_tokens, temperature)
    raise RuntimeError(f"Unhandled native_provider '{a.native_provider}' for alias '{alias}'")


# ---------------------------------------------------------------------------
# Provider-specific paths
# ---------------------------------------------------------------------------

def _call_anthropic(model: str, system: str, user: str, max_tokens: int, temperature: float | None) -> dict[str, Any]:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    resp = client.messages.create(**kwargs)
    text = "".join(block.text for block in resp.content if hasattr(block, "text"))
    return {
        "text": text,
        "model": model,
        "provider": "anthropic",
        "usage": {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens},
    }


def _call_openai(model: str, system: str, user: str, max_tokens: int, temperature: float | None) -> dict[str, Any]:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    resp = client.chat.completions.create(**kwargs)
    return {
        "text": resp.choices[0].message.content or "",
        "model": model,
        "provider": "openai",
        "usage": {"input_tokens": resp.usage.prompt_tokens, "output_tokens": resp.usage.completion_tokens},
    }


def _call_gemini(model: str, system: str, user: str, max_tokens: int, temperature: float | None) -> dict[str, Any]:
    # Modern Gemini SDK (`google.genai`). The legacy `google.generativeai` is deprecated.
    from google import genai  # type: ignore[import-untyped]
    from google.genai import types  # type: ignore[import-untyped]

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    cfg_kwargs: dict[str, Any] = {
        "system_instruction": system,
        "max_output_tokens": max_tokens,
    }
    if temperature is not None:
        cfg_kwargs["temperature"] = temperature
    # Gemini 2.5 series eats output tokens for "thinking" by default; disable for routed single-shots
    # to keep behavior predictable and avoid finish_reason=MAX_TOKENS on small max_tokens.
    if model.startswith("gemini-2.5"):
        cfg_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)

    resp = client.models.generate_content(
        model=model,
        contents=user,
        config=types.GenerateContentConfig(**cfg_kwargs),
    )

    # Extract text defensively — response.text can raise when finish_reason is non-STOP.
    text = ""
    try:
        text = resp.text or ""
    except Exception:
        if resp.candidates:
            parts = getattr(resp.candidates[0].content, "parts", None) or []
            text = "".join(getattr(p, "text", "") or "" for p in parts)

    usage = None
    if getattr(resp, "usage_metadata", None):
        usage = {
            "input_tokens": getattr(resp.usage_metadata, "prompt_token_count", None),
            "output_tokens": getattr(resp.usage_metadata, "candidates_token_count", None),
        }
    return {"text": text, "model": model, "provider": "gemini", "usage": usage}


def _call_openrouter(
    model: str,
    system: str,
    user: str,
    max_tokens: int,
    temperature: float | None,
    base_url: str | None = None,
) -> dict[str, Any]:
    # Reuse existing llm_client which already has retry / dict-keyed cache + base_url support.
    # chat_completion does not currently surface a temperature parameter; route ignores it.
    _ = temperature
    # When invoked as a CLI script (`py execution/modules/model_router.py ...`), the package root
    # is not on sys.path — import siblings via package-relative path.
    try:
        from execution.modules.llm_client import chat_completion  # type: ignore[import-not-found]
    except ImportError:
        from llm_client import chat_completion  # type: ignore[import-not-found]

    kwargs: dict[str, Any] = {"system": system, "user_message": user, "model": model, "max_tokens": max_tokens}
    if base_url is not None:
        kwargs["base_url"] = base_url
    text = chat_completion(**kwargs)

    # Provider label reflects the actual routing target.
    provider_label = "openrouter"
    if base_url and "z.ai" in base_url:
        provider_label = "z-ai-direct"
    elif base_url and "nvidia" in base_url:
        provider_label = "nvidia-nim"
    return {"text": text, "model": model, "provider": provider_label, "usage": None}


# ---------------------------------------------------------------------------
# CLI — `py execution/modules/model_router.py <alias> "<prompt>"`
# ---------------------------------------------------------------------------

def _cli() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Universal model router — single LLM call by alias.")
    parser.add_argument("alias", nargs="?", help=f"Model alias: {', '.join(list_aliases())}")
    parser.add_argument("prompt", nargs="?", help="User prompt (the system prompt defaults to a generic creative-coder system).")
    parser.add_argument("--system", default="You are a helpful expert. Answer concisely.", help="System prompt override.")
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--via-openrouter", action="store_true", help="Force OpenRouter route even when native key exists.")
    parser.add_argument("--mode", choices=("client", "personal"), default="client",
                        help="client (default, quality/billable) or personal (remaps Opus/Sonnet/GPT to GLM for ~$0).")
    parser.add_argument("--sensitive", action="store_true",
                        help="Mark payload as sensitive (PII / CV / leads / client data). Blocks GLM and personal-mode remap.")
    parser.add_argument("--list", action="store_true", help="List available aliases and exit.")
    args = parser.parse_args()

    if args.list or not args.alias:
        print("Available aliases:")
        for name in list_aliases():
            a = ALIASES[name]
            native = "OR-only" if a.native_provider == "openrouter_only" else a.native_provider
            print(f"  {name:12s}  native={native:10s}  model={a.native_model or a.or_model}  sensitivity={a.sensitivity}")
        return 0

    if not args.prompt:
        print("ERROR: prompt required (positional arg #2). Use --list to see aliases.", file=sys.stderr)
        return 2

    try:
        result = call_model(
            args.alias,
            system=args.system,
            user=args.prompt,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            via_openrouter=args.via_openrouter,
            mode=args.mode,
            sensitivity="sensitive" if args.sensitive else "public",
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(result["text"])
    print(f"\n--- routed via {result['provider']} ({result['model']}) ---", file=sys.stderr)
    if result.get("usage"):
        print(f"--- tokens: {result['usage']} ---", file=sys.stderr)
    return 0


if __name__ == "__main__":
    # Windows cp1252 fix for cross-platform CLI use.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(_cli())
