"""
llm.py
description: Thin wrapper over the Anthropic SDK for prompt-file-driven calls (extraction, vision scoring).
inputs: Imported by audit/, enrich/, outreach/ scripts; no CLI args (importable module).
outputs: {"text", "model_id", "prompt_sha256", "usage": {4 token counts}, "cost_usd"} envelope dict.
"""

from __future__ import annotations

import base64
import hashlib
import re
from pathlib import Path
from typing import Any

# Pricing per MTok (USD), per .claude/rules/python-hardening.md rule 4:
# input / cache_read / cache_write / output, read from each model's published rate.
PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-5": {
        "input": 2.00,
        "cache_read": 0.20,
        "cache_write": 2.50,
        "output": 10.00,
    },
    "claude-fable-5-1": {
        "input": 10.00,
        "cache_read": 0.25,
        "cache_write": 12.50,
        "output": 50.00,
    },
}

_VAR_RE = re.compile(r"\{\{(\w+)\}\}")


def render_prompt(prompt_path: Path, variables: dict[str, Any]) -> str:
    """Render a {{variable}} markdown prompt template. Missing variables raise KeyError."""
    template = prompt_path.read_text(encoding="utf-8")

    def _sub(match: re.Match) -> str:
        key = match.group(1)
        if key not in variables:
            raise KeyError(f"Prompt {prompt_path} references undefined variable '{{{{{key}}}}}'")
        return str(variables[key])

    return _VAR_RE.sub(_sub, template)


def _cost_usd(model: str, usage: dict[str, int]) -> float:
    rates = PRICING.get(model)
    if not rates:
        return 0.0
    return (
        usage.get("input_tokens", 0) / 1_000_000 * rates["input"]
        + usage.get("cache_read_input_tokens", 0) / 1_000_000 * rates["cache_read"]
        + usage.get("cache_creation_input_tokens", 0) / 1_000_000 * rates["cache_write"]
        + usage.get("output_tokens", 0) / 1_000_000 * rates["output"]
    )


def _zero_usage() -> dict[str, int]:
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }


def call(
    prompt_name: str,
    prompt_path: Path,
    variables: dict[str, Any],
    *,
    model: str,
    mock: bool,
    max_tokens: int = 1024,
    images: list[bytes] | None = None,
    fixtures_root: Path | None = None,
) -> dict:
    """Render `prompt_path` with `variables`, call `model`, return the response envelope.

    In --mock mode (mock=True), reads `fixtures_root/llm/{prompt_name}.txt` instead of
    calling the API and returns zeroed usage/cost. Raises FileNotFoundError naming the
    expected path if the fixture is missing.
    """
    rendered = render_prompt(prompt_path, variables)
    prompt_sha256 = hashlib.sha256(rendered.encode("utf-8")).hexdigest()

    if mock:
        if fixtures_root is None:
            raise ValueError("call(mock=True) requires fixtures_root")
        fixture_path = fixtures_root / "llm" / f"{prompt_name}.txt"
        if not fixture_path.exists():
            raise FileNotFoundError(f"Mock fixture not found: {fixture_path}")
        text = fixture_path.read_text(encoding="utf-8")
        return {
            "text": text,
            "model_id": model,
            "prompt_sha256": prompt_sha256,
            "usage": _zero_usage(),
            "cost_usd": 0.0,
        }

    try:
        import anthropic
    except ImportError as exc:
        raise ImportError(
            "The 'anthropic' package is required for live LLM calls. "
            "Install it with: pip install anthropic"
        ) from exc

    content: list[dict[str, Any]] = [{"type": "text", "text": rendered}]
    for image_bytes in images or []:
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64.b64encode(image_bytes).decode("ascii"),
                },
            }
        )

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=0,
        messages=[{"role": "user", "content": content}],
    )

    text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
    usage = {
        "input_tokens": getattr(response.usage, "input_tokens", 0) or 0,
        "output_tokens": getattr(response.usage, "output_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(response.usage, "cache_read_input_tokens", 0) or 0,
        "cache_creation_input_tokens": getattr(response.usage, "cache_creation_input_tokens", 0) or 0,
    }

    return {
        "text": text,
        "model_id": model,
        "prompt_sha256": prompt_sha256,
        "usage": usage,
        "cost_usd": _cost_usd(model, usage),
    }
