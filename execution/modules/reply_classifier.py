"""
reply_classifier.py
description: Reusable AI reply classifier — classifies cold email replies as positive/negative/neutral.
inputs: Reply body text, API key (env or param), model config, signal lists for mock mode.
outputs: Classification string: "positive", "negative", or "neutral".
"""

import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-haiku-4-5-20251001"

DEFAULT_SYSTEM_PROMPT = (
    "Classify this cold email reply as exactly one of: positive, negative, neutral.\n"
    "positive = interested in selling their business, wants to talk, asks about the process\n"
    "negative = not interested, asks to be removed, hostile\n"
    "neutral = out of office, auto-reply, bounce, unclear\n"
    "Reply with exactly one word: positive, negative, or neutral."
)

DEFAULT_MOCK_SIGNALS = {
    "negative": [
        "not interested", "remove", "stop", "unsubscribe",
        "no thanks", "don't", "no longer",
    ],
    "neutral": [
        "out of office", "auto-reply", "vacation", "will return",
    ],
    "positive": [
        "interested", "sell", "process", "tell me more", "call me", "yes",
    ],
}

VALID_CLASSES = {"positive", "negative", "neutral"}


def classify_mock(body: str, signals: dict | None = None) -> str:
    """Classify using keyword matching. Configurable signal lists per client."""
    sigs = signals or DEFAULT_MOCK_SIGNALS
    text = (body or "").lower()

    for signal in sigs.get("negative", []):
        if signal in text:
            return "negative"
    for signal in sigs.get("neutral", []):
        if signal in text:
            return "neutral"
    for signal in sigs.get("positive", []):
        if signal in text:
            return "positive"
    return "neutral"


def classify_real(
    body: str,
    api_key: str | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
) -> str:
    """Classify using Claude API. Returns 'positive', 'negative', or 'neutral'."""
    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        logger.error("ANTHROPIC_API_KEY not set for reply classification.")
        return "neutral"

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=key)
        resp = client.messages.create(
            model=model or DEFAULT_MODEL,
            max_tokens=10,
            system=system_prompt or DEFAULT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": body or ""}],
        )
        result = resp.content[0].text.strip().lower()
        if result in VALID_CLASSES:
            return result
        logger.warning("Unexpected classifier output: %r — defaulting to neutral", result)
        return "neutral"
    except Exception:
        logger.exception("Reply classification failed, defaulting to neutral")
        return "neutral"


def classify(
    body: str,
    mock: bool = False,
    api_key: str | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
    mock_signals: dict | None = None,
) -> str:
    """Unified entry point. Routes to mock or real classifier."""
    if mock:
        return classify_mock(body, mock_signals)
    return classify_real(body, api_key, model, system_prompt)
