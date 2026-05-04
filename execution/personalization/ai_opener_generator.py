#!/usr/bin/env python3
"""
ai_opener_generator.py
description: Generate personalized cold email first lines using OpenRouter LLM API.
inputs: --input, --output, --tone-config, --batch-size, --mock; env: OPENROUTER_API_KEY
outputs: .tmp/personalized_leads.json
usage:
    py execution/personalization/ai_opener_generator.py --input .tmp/verified_leads.json --mock
    py execution/personalization/ai_opener_generator.py --input .tmp/verified_leads.json
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "execution"))

from modules.pipeline_utils import (
    load_config,
    load_leads,
    now_iso,
    save_leads,
    setup_logging,
)

load_dotenv(ROOT / ".env")
logger = setup_logging("ai_opener", log_dir=ROOT / ".tmp")

DEFAULT_MODEL = "anthropic/claude-haiku-4.5"


def get_mock_opener(lead: dict) -> str:
    """Generate a template-based mock opener from lead data."""
    name = lead.get("business_name", "your business")
    industry = lead.get("industry", "business")
    city = lead.get("city", "Houston")
    rating = lead.get("rating")
    reviews = lead.get("reviews_count")

    if rating and reviews and reviews > 50:
        return f"I noticed {name} has a {rating} rating with {reviews}+ reviews in {city}."
    elif rating:
        return f"I saw {name} has a solid {rating}-star rating in {city}."
    else:
        return f"I came across {name} while researching {industry} businesses in {city}."


def build_system_prompt(tone_config: dict) -> str:
    """Construct the system prompt from tone configuration."""
    voice = tone_config.get("voice", "I")
    sender = tone_config.get("sender_name", "Aleksandar")
    tone_desc = tone_config.get("tone_description", "Direct and blunt.")
    opener_instruction = tone_config.get("opener_instruction", "")
    examples = tone_config.get("example_openers", [])
    never_say = tone_config.get("never_say", [])

    prompt = f"""You write personalized cold email opening lines for {sender}.

VOICE: Use "{voice}" (first person).

TONE: {tone_desc}

TASK: {opener_instruction}

CONSTRAINTS:
- Exactly one sentence, 5-25 words
- No exclamation marks
- No questions
- No sales language ("exciting opportunity", "game-changing", "transform")
- No compliments that feel fake ("impressive", "amazing", "incredible")
- Reference something specific and factual about the prospect"""

    if never_say:
        prompt += "\n- NEVER say: " + ", ".join(f'"{w}"' for w in never_say)

    if examples:
        prompt += "\n\nEXAMPLES OF GOOD OPENERS:\n"
        for ex in examples:
            prompt += f"- {ex}\n"

    return prompt


def build_user_prompt(lead: dict) -> str:
    """Construct the user prompt with prospect data."""
    parts = [f"Business: {lead.get('business_name', 'Unknown')}"]
    if lead.get("industry"):
        parts.append(f"Industry: {lead['industry']}")
    if lead.get("city") and lead.get("state"):
        parts.append(f"Location: {lead['city']}, {lead['state']}")
    if lead.get("rating"):
        parts.append(f"Rating: {lead['rating']} stars")
    if lead.get("reviews_count"):
        parts.append(f"Reviews: {lead['reviews_count']}")
    if lead.get("website"):
        parts.append(f"Website: {lead['website']}")
    if lead.get("owner_name"):
        parts.append(f"Owner: {lead['owner_name']}")

    return "Write one personalized opener for this business.\n\n" + "\n".join(parts)


def validate_opener(opener: str, tone_config: dict) -> bool:
    """Check if an opener meets the constraints."""
    if not opener:
        return False
    words = opener.split()
    if len(words) < 5 or len(words) > 25:
        return False
    if "!" in opener:
        return False
    never_say = tone_config.get("never_say", [])
    lower = opener.lower()
    for phrase in never_say:
        if phrase.lower() in lower:
            return False
    return True


def generate_opener(
    lead: dict,
    system_prompt: str,
    model: str,
    tone_config: dict,
) -> str:
    """Generate a personalized opener via OpenRouter LLM. Retries once on validation failure."""
    from modules.llm_client import chat_completion

    user_prompt = build_user_prompt(lead)

    for attempt in range(2):
        try:
            raw = chat_completion(
                system=system_prompt,
                user_message=user_prompt,
                model=model,
                max_tokens=100,
            )
            opener = raw.strip('"').strip("'")

            if validate_opener(opener, tone_config):
                return opener

            if attempt == 0:
                logger.debug(
                    "Opener validation failed for %s, retrying: '%s'",
                    lead.get("business_name"),
                    opener,
                )
        except Exception:
            logger.exception(
                "LLM API error for %s (attempt %d)",
                lead.get("business_name"),
                attempt + 1,
            )

    return get_mock_opener(lead)


def process_leads(
    leads: list[dict],
    system_prompt: str,
    model: str,
    tone_config: dict,
    mock: bool,
    batch_size: int,
) -> list[dict]:
    """Process all leads and add personalized openers."""
    total = len(leads)
    processed = 0

    for i, lead in enumerate(leads):
        if lead.get("status") not in ("verified",):
            continue

        if mock:
            opener = get_mock_opener(lead)
        else:
            opener = generate_opener(lead, system_prompt, model, tone_config)

        lead["personalized_opener"] = opener
        lead["opener_model"] = model if not mock else "mock"
        lead["personalized_at"] = now_iso()
        lead["status"] = "personalized"
        processed += 1

        if processed % batch_size == 0:
            logger.info("Processed %d/%d leads", processed, total)

    return leads


def main():
    parser = argparse.ArgumentParser(
        description="Generate personalized cold email openers via Claude API"
    )
    parser.add_argument("--input", required=True, help="Path to verified leads JSON")
    parser.add_argument("--output", default=str(ROOT / ".tmp" / "personalized_leads.json"))
    parser.add_argument("--tone-config", default=str(ROOT / "config" / "tone.json"))
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--mock", action="store_true", help="Use mock openers")
    args = parser.parse_args()

    (ROOT / ".tmp").mkdir(exist_ok=True)

    tone_config = load_config(args.tone_config)
    leads = load_leads(args.input)
    logger.info("Loaded %d leads from %s", len(leads), args.input)

    system_prompt = build_system_prompt(tone_config)

    leads = process_leads(
        leads, system_prompt, args.model, tone_config, args.mock, args.batch_size
    )

    output_path = save_leads(leads, args.output)

    personalized = sum(1 for l in leads if l.get("status") == "personalized")
    logger.info("Saved %d leads to %s (%d personalized)", len(leads), output_path, personalized)


if __name__ == "__main__":
    main()
