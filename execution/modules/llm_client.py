"""
llm_client.py
description: OpenRouter LLM wrapper — OpenAI-compatible API client for all LLM calls.
inputs: env OPENROUTER_API_KEY; model, system prompt, user message, max_tokens.
outputs: Text response string.
"""

import os

_client = None


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
    model: str = "anthropic/claude-haiku-4.5",
    max_tokens: int = 150,
) -> str:
    """Single-turn chat completion via OpenRouter. Raises on failure."""
    client = _get_client()
    resp = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
    )
    return resp.choices[0].message.content.strip()
