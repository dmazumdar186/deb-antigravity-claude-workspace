#!/usr/bin/env python3
"""
ai_opener_generator.py
description: Generate personalized cold email first lines using Anthropic or OpenRouter LLM API.
inputs: --input, --output, --tone-config, --batch-size, --mock, --mode, --model;
        env: ANTHROPIC_API_KEY (preferred for cache_control), OPENROUTER_API_KEY (fallback)
outputs: .tmp/personalized_leads.json
usage:
    py execution/personalization/ai_opener_generator.py --input .tmp/verified_leads.json --mock
    py execution/personalization/ai_opener_generator.py --input .tmp/verified_leads.json --mode cheap
    py execution/personalization/ai_opener_generator.py --input .tmp/verified_leads.json --mode premium

Modes:
    cheap     — Haiku 4.5, fast.
    balanced  — Sonnet 4.6, standard depth (default).
    premium   — Opus 4.7, deep quality.
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "execution"))

from modules.pipeline_utils import (  # noqa: E402
    load_config,
    load_leads,
    now_iso,
    save_leads,
    setup_logging,
)

load_dotenv(ROOT / ".env")
logger = setup_logging("ai_opener", log_dir=ROOT / ".tmp")

# Workspace-standard model routing per --mode (matches _TEMPLATE.py pattern).
# OpenRouter uses dot notation and anthropic/ prefix; Anthropic SDK uses dash notation.
# Haiku 4.5 banned per ~/.claude/rules/model-tier.md (2026-06-14). "cheap" maps
# to Sonnet 4.6 — the rule's floor for user-facing LLM output.
MODE_TO_MODEL_OPENROUTER = {
    "cheap": "anthropic/claude-sonnet-4.6",
    "balanced": "anthropic/claude-sonnet-4.6",
    "premium": "anthropic/claude-opus-4.7",
}
MODE_TO_MODEL_ANTHROPIC = {
    "cheap": "claude-sonnet-4-6",
    "balanced": "claude-sonnet-4-6",
    "premium": "claude-opus-4-7",
}
DEFAULT_MODE = "balanced"

# Per python-hardening rule 4: 4 entries per model (input, cache_read, cache_write, output).
# Prices in USD per million tokens.
ANTHROPIC_PRICING: dict[str, dict[str, float]] = {
    # Haiku 4.5 banned per model-tier.md (2026-06-14); entry kept only so that
    # legacy cost calculations on AM-frozen call records still resolve.
    "claude-haiku-4-5": {
        "input": 0.80,
        "cache_read": 0.08,   # 0.1× input
        "cache_write": 1.00,  # 1.25× input
        "output": 4.00,
    },
    "claude-sonnet-4-6": {
        "input": 3.00,
        "cache_read": 0.30,   # 0.1× input
        "cache_write": 3.75,  # 1.25× input
        "output": 15.00,
    },
    "claude-opus-4-7": {
        "input": 15.00,
        "cache_read": 1.50,   # 0.1× input
        "cache_write": 18.75, # 1.25× input
        "output": 75.00,
    },
}


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


def _calc_cost(model_anthropic: str, usage) -> float:
    """
    Compute USD cost from Anthropic SDK usage object.
    Per python-hardening rule 4: reads all 4 token-count fields so that
    prompt-caching sessions are not over-estimated by 5-10×.

    Parameters
    ----------
    model_anthropic : str
        Bare Anthropic model ID (e.g. 'claude-sonnet-4-6'). Used to look up
        the 4-entry pricing table in ANTHROPIC_PRICING.
    usage : anthropic.types.Usage
        Usage object from response.usage.

    Returns
    -------
    float
        Cost in USD (may be 0.0 if model not in pricing table).
    """
    prices = ANTHROPIC_PRICING.get(model_anthropic)
    if prices is None:
        logger.warning("No pricing entry for model '%s'; cost logged as 0.0", model_anthropic)
        return 0.0

    input_tok = getattr(usage, "input_tokens", 0) or 0
    cache_read_tok = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_write_tok = getattr(usage, "cache_creation_input_tokens", 0) or 0
    output_tok = getattr(usage, "output_tokens", 0) or 0

    cost = (
        input_tok * prices["input"]
        + cache_read_tok * prices["cache_read"]
        + cache_write_tok * prices["cache_write"]
        + output_tok * prices["output"]
    ) / 1_000_000
    return cost


def _generate_opener_anthropic(
    lead: dict,
    system_prompt: str,
    model_anthropic: str,
    tone_config: dict,
) -> str:
    """
    Generate opener via Anthropic SDK directly.
    Marks the system prompt with cache_control: ephemeral so the static
    portion is cached across calls in the same session.
    Logs cache-aware cost (reads cache_read_input_tokens +
    cache_creation_input_tokens per python-hardening rule 4).
    """
    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    user_prompt = build_user_prompt(lead)

    for attempt in range(2):
        try:
            response = client.messages.create(
                model=model_anthropic,
                max_tokens=100,
                system=[
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = response.content[0].text.strip('"').strip("'")

            cost = _calc_cost(model_anthropic, response.usage)
            logger.debug(
                "Anthropic usage — input:%d cache_read:%d cache_write:%d output:%d cost:$%.6f",
                getattr(response.usage, "input_tokens", 0) or 0,
                getattr(response.usage, "cache_read_input_tokens", 0) or 0,
                getattr(response.usage, "cache_creation_input_tokens", 0) or 0,
                getattr(response.usage, "output_tokens", 0) or 0,
                cost,
            )

            if validate_opener(raw, tone_config):
                return raw

            if attempt == 0:
                logger.debug(
                    "Opener validation failed for %s, retrying: '%s'",
                    lead.get("business_name"),
                    raw,
                )
        except Exception:
            logger.exception(
                "Anthropic API error for %s (attempt %d)",
                lead.get("business_name"),
                attempt + 1,
            )

    return get_mock_opener(lead)


def generate_opener(
    lead: dict,
    system_prompt: str,
    model: str,
    tone_config: dict,
    model_anthropic: str | None = None,
) -> str:
    """
    Generate a personalized opener via LLM. Retries once on validation failure.

    Prefers the Anthropic SDK path (supports cache_control + cache-aware cost
    accounting) when ANTHROPIC_API_KEY is set and model_anthropic is provided.
    Falls back to OpenRouter via modules.llm_client otherwise.
    """
    import os

    use_anthropic = (
        model_anthropic is not None
        and bool(os.environ.get("ANTHROPIC_API_KEY", ""))
    )

    if use_anthropic:
        return _generate_opener_anthropic(lead, system_prompt, model_anthropic, tone_config)

    # OpenRouter fallback path (no cache_control support via OpenAI-compat client)
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
    model_anthropic: str | None = None,
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
            opener = generate_opener(lead, system_prompt, model, tone_config, model_anthropic)

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
    parser.add_argument(
        "--mode",
        choices=list(MODE_TO_MODEL_OPENROUTER.keys()),
        default=DEFAULT_MODE,
        help="Tier: cheap (Haiku 4.5) / balanced (Sonnet 4.6, default) / premium (Opus 4.7).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override model ID explicitly (bypasses --mode). "
             "Use OpenRouter format for OpenRouter (e.g. anthropic/claude-sonnet-4.6) "
             "or bare name for Anthropic SDK.",
    )
    parser.add_argument("--mock", action="store_true", help="Use mock openers")
    args = parser.parse_args()

    # --model explicit override takes precedence; otherwise resolve from --mode.
    if args.model:
        or_model = args.model
        # Best-effort: if caller passed a bare Anthropic name, map to OR format.
        # If they passed an OR-format name, use it directly.
        anthropic_model = args.model.replace("anthropic/", "").replace(".", "-") if "/" in args.model else args.model
    else:
        or_model = MODE_TO_MODEL_OPENROUTER[args.mode]
        anthropic_model = MODE_TO_MODEL_ANTHROPIC[args.mode]

    logger.info("Mode: %s | OR model: %s | Anthropic model: %s", args.mode if not args.model else "explicit", or_model, anthropic_model)

    (ROOT / ".tmp").mkdir(exist_ok=True)

    tone_config = load_config(args.tone_config)
    leads = load_leads(args.input)
    logger.info("Loaded %d leads from %s", len(leads), args.input)

    system_prompt = build_system_prompt(tone_config)

    leads = process_leads(
        leads, system_prompt, or_model, tone_config, args.mock, args.batch_size,
        model_anthropic=anthropic_model,
    )

    output_path = save_leads(leads, args.output)

    personalized = sum(1 for l in leads if l.get("status") == "personalized")
    logger.info("Saved %d leads to %s (%d personalized)", len(leads), output_path, personalized)


if __name__ == "__main__":
    main()
