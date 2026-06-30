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

# Cached clients keyed by base_url. Round-2 plan-skeptic Issue B: a bare
# singleton silently routes calls to whichever base_url was registered first.
# A dict keyed on base_url lets OR and Z.AI-direct coexist without cross-talk.
_clients: dict[str, object] = {}

MAX_RETRIES = 2
BASE_DELAY = 1.0

_OR_BASE_URL = "https://openrouter.ai/api/v1"


def _get_client(base_url: str = _OR_BASE_URL):
    if base_url not in _clients:
        from openai import OpenAI

        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY not set")
        _clients[base_url] = OpenAI(api_key=api_key, base_url=base_url)
    return _clients[base_url]


def chat_completion(
    system: str,
    user_message: str,
    # Default Sonnet 4.6 per ~/.claude/rules/model-tier.md (2026-06-14).
    # Haiku 4.5 is banned workspace-wide. AM-frozen callers that need Haiku
    # for compatibility pass `model=` explicitly.
    model: str = "anthropic/claude-sonnet-4.6",
    max_tokens: int = 150,
    base_url: str = _OR_BASE_URL,
) -> str:
    """Single-turn chat completion via OpenRouter (or Z.AI-direct if base_url overridden).
    Retries on rate limit / server errors."""
    from openai import APIStatusError, RateLimitError

    client = _get_client(base_url)
    last_exc = None
    # Disable reasoning/thinking for Z.AI GLM models — they default to "thinking
    # mode" which burns the entire output budget on internal reasoning before
    # emitting a single visible token. On long creative outputs this manifests
    # as `content=None` + `finish_reason='length'`. The OR-canonical way to
    # opt out is `reasoning: { enabled: false }` via extra_body.
    extra: dict | None = None
    if model.lower().startswith("z-ai/"):
        extra = {"reasoning": {"enabled": False}}
    for attempt in range(MAX_RETRIES + 1):
        try:
            create_kwargs: dict = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
            }
            if extra is not None:
                create_kwargs["extra_body"] = extra
            resp = client.chat.completions.create(**create_kwargs)
            # Defensive extraction: some providers (notably GLM via OR on long
            # outputs) can return message.content=None alongside a non-empty
            # finish_reason. Treat empty as empty rather than AttributeError.
            if not resp.choices:
                return ""
            msg = resp.choices[0].message
            content = getattr(msg, "content", None) or ""
            finish = getattr(resp.choices[0], "finish_reason", None)
            if not content and finish:
                logger.warning("Empty content from %s, finish_reason=%r", model, finish)
            return content.strip()
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
    if last_exc is None:
        raise RuntimeError("chat_completion exhausted retries with no exception captured")
    raise last_exc
