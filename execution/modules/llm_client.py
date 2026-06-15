"""
llm_client.py
description: OpenRouter LLM wrapper — OpenAI-compatible API client for all LLM calls.
inputs: env OPENROUTER_API_KEY; model, system prompt, user message, max_tokens.
outputs: Text response string.
"""

import logging
import os
import time

logger = logging.getLogger(__name__)

_client = None

MAX_RETRIES = 2
BASE_DELAY = 1.0


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY not set")
        _client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )
    return _client


def chat_completion(
    system: str,
    user_message: str,
    # Default Sonnet 4.6 per ~/.claude/rules/model-tier.md (2026-06-14).
    # Haiku 4.5 is banned workspace-wide. AM-frozen callers that need Haiku
    # for compatibility pass `model=` explicitly.
    model: str = "anthropic/claude-sonnet-4.6",
    max_tokens: int = 150,
) -> str:
    """Single-turn chat completion via OpenRouter. Retries on rate limit / server errors."""
    from openai import APIStatusError, RateLimitError

    client = _get_client()
    last_exc = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
            )
            return resp.choices[0].message.content.strip()
        except RateLimitError as e:
            last_exc = e
            if attempt < MAX_RETRIES:
                delay = BASE_DELAY * (2 ** attempt)
                logger.warning("Rate limited (attempt %d/%d), retrying in %.1fs", attempt + 1, MAX_RETRIES + 1, delay)
                time.sleep(delay)
        except APIStatusError as e:
            last_exc = e
            if e.status_code >= 500 and attempt < MAX_RETRIES:
                delay = BASE_DELAY * (2 ** attempt)
                logger.warning("Server error %d (attempt %d/%d), retrying in %.1fs", e.status_code, attempt + 1, MAX_RETRIES + 1, delay)
                time.sleep(delay)
            else:
                raise
    raise last_exc
