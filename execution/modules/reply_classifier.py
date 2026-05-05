"""
reply_classifier.py
description: Reusable AI reply classifier — classifies cold email replies as positive/negative/neutral.
inputs: Reply body text, model config, signal lists for mock mode; env: OPENROUTER_API_KEY.
outputs: Classification string: "positive", "negative", or "neutral".
"""

import logging

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "anthropic/claude-haiku-4.5"

DEFAULT_SYSTEM_PROMPT = (
    "Classify this cold email reply as exactly one of: hot_positive, positive, negative, neutral.\n"
    "hot_positive = gives a phone number, says ready to sell, wants to schedule a call immediately\n"
    "positive = interested in selling, wants to talk, asks about the process, engages with conditions or involves others (accountant, partner)\n"
    "negative = not interested, asks to be removed, hostile, already sold the business\n"
    "neutral = out of office, auto-reply, bounce, unclear intent, vague hedging with no engagement\n\n"
    "Examples:\n"
    '"Call me at 713-555-0888, I\'m ready to sell." -> hot_positive\n'
    '"Yes, tell me more about the process." -> positive\n'
    '"I\'m interested but not ready yet. Maybe next year." -> positive\n'
    '"If the price is right, I\'d consider it." -> positive\n'
    '"Yes" -> positive\n'
    '"Not interested, remove me from your list." -> negative\n'
    '"Too late, sold the business last month." -> negative\n'
    '"Don\'t call me at 555-0199 again. Remove me." -> negative\n'
    '"Out of office until Monday." -> neutral\n'
    '"Maybe. Depends on the price." -> neutral\n\n'
    "Reply with exactly one word: hot_positive, positive, negative, or neutral."
)

DEFAULT_MOCK_SIGNALS = {
    "hot_positive": [
        "phone number", "call me at", "my number is", "ready to sell",
        "want to sell now", "schedule a call",
    ],
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

VALID_CLASSES = {"hot_positive", "positive", "negative", "neutral"}


def classify_mock(body: str, signals: dict | None = None) -> str:
    """Classify using keyword matching. Configurable signal lists per client."""
    sigs = signals or DEFAULT_MOCK_SIGNALS
    text = (body or "").lower()

    for signal in sigs.get("hot_positive", []):
        if signal in text:
            return "hot_positive"
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
    """Classify using OpenRouter LLM. Returns 'positive', 'negative', or 'neutral'."""
    try:
        from modules.llm_client import chat_completion

        result = chat_completion(
            system=system_prompt or DEFAULT_SYSTEM_PROMPT,
            user_message=body or "",
            model=model or DEFAULT_MODEL,
            max_tokens=10,
        ).lower()
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
