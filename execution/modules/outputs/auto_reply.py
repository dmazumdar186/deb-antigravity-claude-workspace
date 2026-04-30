"""
auto_reply.py
description: AI auto-reply engine — generates human-sounding responses to positive cold email replies.
inputs: Reply dict (body, from_email, from_name, company, classification), config dict, API key (env or param).
outputs: Action dict with reply_text and delay, or skip/handoff reason.
"""

import logging
import os
import random
import time

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_HOT_LEAD_SIGNALS = [
    "phone number", "my number", "call me at",
    "ready to sell", "want to sell", "schedule a call",
]
FALLBACK_REPLY = "Thanks for getting back to me. Let me follow up with more details shortly."


def generate_reply_mock(body: str, context: str) -> str:
    return (
        "Thanks for reaching out. I'd love to learn more about your business. "
        "Would a quick call this week work?"
    )


def generate_reply(
    body: str, context: str,
    api_key: str | None = None, model: str | None = None,
    system_prompt: str | None = None, guard_rails: list[str] | None = None,
) -> str:
    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        logger.error("ANTHROPIC_API_KEY not set for auto-reply generation.")
        return FALLBACK_REPLY

    if not system_prompt:
        system_prompt = (
            ("Rules:\n" + "\n".join(f"- {r}" for r in guard_rails))
            if guard_rails else "Reply naturally and briefly."
        )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        resp = client.messages.create(
            model=model or DEFAULT_MODEL, max_tokens=150,
            system=system_prompt,
            messages=[{"role": "user",
                       "content": f"Reply to this email naturally:\n\n{body}\n\nContext: {context}"}],
        )
        return resp.content[0].text.strip()
    except Exception:
        logger.exception("Auto-reply generation failed, using fallback")
        return FALLBACK_REPLY


def should_handoff(body: str, hot_lead_signals: list[str] | None = None) -> bool:
    signals = hot_lead_signals or DEFAULT_HOT_LEAD_SIGNALS
    return any(s in (body or "").lower() for s in signals)


def schedule_delayed_send(
    reply_text: str, delay_min: int, delay_max: int,
    send_fn, mock: bool = False,
) -> int:
    delay = random.randint(delay_min, delay_max)
    if mock:
        logger.info("Mock mode — would delay %d seconds before sending", delay)
        return delay
    time.sleep(delay)
    send_fn(reply_text)
    return delay


def handle_reply(reply: dict, config: dict, mock: bool = False) -> dict:
    ar = config.get("auto_reply", {})
    if not ar.get("enabled", False):
        logger.info("Auto-reply disabled, skipping")
        return {"action": "skip", "reason": "auto_reply disabled"}

    body = reply.get("body", "")
    if should_handoff(body, ar.get("hot_lead_signals")):
        return {"action": "handoff", "reason": "hot lead detected"}

    if reply.get("classification", "neutral") in ("negative", "neutral"):
        return {"action": "skip", "reason": "not actionable"}

    context = (f"From: {reply.get('from_name', '')} at {reply.get('company', '')} "
               f"({reply.get('from_email', '')})")

    tone = config.get("tone", {})
    persona = ar.get("sender_persona", "")
    guard_rails = ar.get("guard_rails", [])
    system_prompt = "\n\n".join(filter(None, [
        f"You are {persona}." if persona else None,
        tone.get("auto_reply_instruction", ""),
        ("Rules:\n" + "\n".join(f"- {r}" for r in guard_rails)) if guard_rails else None,
    ]))

    if mock:
        reply_text = generate_reply_mock(body, context)
    else:
        reply_text = generate_reply(
            body, context, model=ar.get("model"),
            system_prompt=system_prompt, guard_rails=guard_rails,
        )

    delay = random.randint(ar.get("delay_min_seconds", 120), ar.get("delay_max_seconds", 420))
    return {"action": "auto_reply", "reply_text": reply_text, "delay_seconds": delay}


if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv
    load_dotenv()

    parser = argparse.ArgumentParser(description="Auto-reply engine demo")
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    cfg = {
        "auto_reply": {
            "enabled": True, "model": DEFAULT_MODEL,
            "delay_min_seconds": 120, "delay_max_seconds": 420,
            "sender_persona": "Aleksandar, business broker backed by Hedgestone Capital Group",
            "hot_lead_signals": DEFAULT_HOT_LEAD_SIGNALS,
            "guard_rails": ["Never promise specific valuations", "Never use exclamation marks",
                            "Never write more than 3 sentences", "Never mention AI or automation"],
        },
        "tone": {"auto_reply_instruction": "Write 2-3 short sentences max. Sound like a human text."},
    }
    sample = {
        "body": "I've been thinking about selling my restaurant. What does the process look like?",
        "from_email": "owner@example.com", "from_name": "James",
        "company": "Joe's Diner", "classification": "positive",
    }
    print(handle_reply(sample, cfg, mock=args.mock))
