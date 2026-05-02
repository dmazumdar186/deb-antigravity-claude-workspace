"""
auto_reply.py
description: AI auto-reply engine — generates human-sounding responses to positive cold email replies.
inputs: Reply dict (body, from_email, from_name, company, classification), config dict; env: OPENROUTER_API_KEY.
outputs: Action dict with reply_text and delay, or skip/handoff reason.
"""

import logging
import random
import time

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "anthropic/claude-haiku-4-5-20251001"
DEFAULT_HOT_LEAD_SIGNALS = [
    "phone number", "my number", "call me at",
    "ready to sell", "want to sell", "schedule a call",
]
FALLBACK_REPLY = "Thanks for getting back to me. Let me follow up with more details shortly."


def _match_objection(body: str, objection_responses: dict | None) -> dict | None:
    if not objection_responses or not body:
        return None
    text = body.lower()
    for key, obj in objection_responses.items():
        triggers = obj.get("triggers", [])
        if any(t in text for t in triggers):
            return obj
    return None


def generate_reply_mock(body: str, context: str, objection_responses: dict | None = None) -> str:
    match = _match_objection(body, objection_responses)
    if match:
        return match["response"]
    return (
        "Thanks for reaching out. I'd love to learn more about your business. "
        "Would a quick call this week work?"
    )


def generate_reply(
    body: str, context: str,
    api_key: str | None = None, model: str | None = None,
    system_prompt: str | None = None, guard_rails: list[str] | None = None,
) -> str:
    if not system_prompt:
        system_prompt = (
            ("Rules:\n" + "\n".join(f"- {r}" for r in guard_rails))
            if guard_rails else "Reply naturally and briefly."
        )

    try:
        from modules.llm_client import chat_completion

        return chat_completion(
            system=system_prompt,
            user_message=f"Reply to this email naturally:\n\n{body}\n\nContext: {context}",
            model=model or DEFAULT_MODEL,
            max_tokens=150,
        )
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


def handle_reply(reply: dict, config: dict, mock: bool = False, send_fn=None) -> dict:
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
    objection_responses = ar.get("objection_responses")

    objection_section = None
    match = _match_objection(body, objection_responses)
    if match:
        objection_section = (
            f"The prospect's message matches this objection: \"{match.get('triggers', [''])[0]}\"\n"
            f"Example response for this objection: \"{match['response']}\"\n"
            f"Use this as a guide but vary the wording naturally."
        )

    system_prompt = "\n\n".join(filter(None, [
        f"You are {persona}." if persona else None,
        tone.get("auto_reply_instruction", ""),
        ("Rules:\n" + "\n".join(f"- {r}" for r in guard_rails)) if guard_rails else None,
        objection_section,
    ]))

    if mock:
        reply_text = generate_reply_mock(body, context, objection_responses)
    else:
        reply_text = generate_reply(
            body, context, model=ar.get("model"),
            system_prompt=system_prompt, guard_rails=guard_rails,
        )

    delay_min = ar.get("delay_min_seconds", 120)
    delay_max = ar.get("delay_max_seconds", 420)

    if send_fn:
        delay = schedule_delayed_send(reply_text, delay_min, delay_max, send_fn, mock)
    else:
        delay = random.randint(delay_min, delay_max)
        logger.warning("No send_fn provided — reply generated but not sent")

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
