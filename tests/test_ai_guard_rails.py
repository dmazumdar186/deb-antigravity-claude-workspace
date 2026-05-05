"""
test_ai_guard_rails.py
description: Tests that real LLM output complies with all deterministic guard rails.
inputs: OPENROUTER_API_KEY in .env (skips all tests if missing).
outputs: pytest results — pass/fail per guard rail assertion.
"""

import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "execution"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

SKIP_REASON = "OPENROUTER_API_KEY not set — skipping real LLM guard rail tests"
HAS_API_KEY = bool(os.environ.get("OPENROUTER_API_KEY", ""))

from modules.reply_classifier import classify, VALID_CLASSES
from modules.outputs.auto_reply import handle_reply, should_handoff
from personalization.ai_opener_generator import (
    generate_opener,
    build_system_prompt,
    validate_opener,
)
from personalization.variant_generator import (
    generate_challenger_variant,
    validate_variant,
)


@pytest.fixture(scope="module")
def tone_config():
    with open(ROOT / "config" / "tone.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def master_config():
    with open(ROOT / "config" / "accessory_masters.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def variants_config():
    with open(ROOT / "config" / "email_variants.json", encoding="utf-8") as f:
        return json.load(f)


NEVER_SAY = [
    "exciting opportunity", "game-changing", "transform your", "synergy",
    "leverage", "utilize", "solution", "partnership", "disrupt",
    "innovative", "cutting-edge", "best-in-class", "reach out",
    "touch base", "circle back", "take it to the next level",
]

AI_MENTIONS = ["artificial intelligence", "automation", "algorithm", "machine learning", "chatbot", "ai-powered"]

CLASSIFIER_INPUTS = [
    "I've been thinking about selling my restaurant. What's the process?",
    "Not interested, stop emailing me.",
    "I'm out of the office until next Monday.",
    "Call me at 713-555-0888, I'm ready to sell.",
    "Maybe, depends on the price.",
]

AUTO_REPLY_INPUTS = [
    {
        "body": "I've been thinking about selling my restaurant. What does the process look like?",
        "from_email": "owner@joesdiner.com", "from_name": "James",
        "company": "Joe's Diner", "classification": "positive",
    },
    {
        "body": "How much is my car wash worth?",
        "from_email": "tony@sparkle.com", "from_name": "Tony",
        "company": "Sparkle Car Wash", "classification": "positive",
    },
    {
        "body": "Who is this? What company are you with?",
        "from_email": "pat@print.com", "from_name": "Pat",
        "company": "Pat's Printing", "classification": "positive",
    },
    {
        "body": "I'm interested but not sure about the timing. What does the market look like right now?",
        "from_email": "maria@laundry.com", "from_name": "Maria",
        "company": "Clean & Fresh Laundromat", "classification": "positive",
    },
]

OPENER_LEADS = [
    {
        "business_name": "Sparkle Car Wash", "industry": "car wash",
        "city": "Houston", "state": "TX", "rating": 4.5,
        "reviews_count": 187, "website": "sparklecarwash.com", "owner_name": "Tony",
    },
    {
        "business_name": "Mario's Pizzeria", "industry": "pizzeria",
        "city": "Katy", "state": "TX", "rating": 3.8,
        "reviews_count": 42, "website": "", "owner_name": "Mario",
    },
    {
        "business_name": "Clean & Fresh Laundromat", "industry": "laundromat",
        "city": "Sugar Land", "state": "TX", "rating": 4.9,
        "reviews_count": 312, "website": "cleanfreshlaundry.com", "owner_name": "",
    },
]

DEFAULT_MODEL = "anthropic/claude-haiku-4.5"


# ---------------------------------------------------------------------------
# Classifier guard rails
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_API_KEY, reason=SKIP_REASON)
class TestClassifierGuardRails:

    @pytest.mark.parametrize("body", CLASSIFIER_INPUTS)
    def test_output_is_valid_class(self, body):
        result = classify(body, mock=False)
        assert result in VALID_CLASSES, f"Got '{result}', expected one of {VALID_CLASSES}"

    @pytest.mark.parametrize("body", CLASSIFIER_INPUTS)
    def test_single_word_output(self, body):
        result = classify(body, mock=False)
        assert " " not in result.strip(), f"Classifier returned multi-word: '{result}'"


# ---------------------------------------------------------------------------
# Auto-reply guard rails
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_API_KEY, reason=SKIP_REASON)
class TestAutoReplyGuardRails:

    @pytest.fixture(autouse=True)
    def _generate_replies(self, master_config):
        self.replies = []
        for inp in AUTO_REPLY_INPUTS:
            result = handle_reply(inp, master_config, mock=False)
            if result["action"] == "auto_reply":
                self.replies.append(result["reply_text"])
        assert len(self.replies) > 0, "No auto-replies were generated"

    def test_no_exclamation_marks(self):
        for text in self.replies:
            assert "!" not in text, f"Exclamation mark found: {text!r}"

    def test_max_three_sentences(self):
        for text in self.replies:
            sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
            assert len(sentences) <= 4, f"Too many sentences ({len(sentences)}): {text!r}"

    def test_max_sixty_words(self):
        for text in self.replies:
            word_count = len(text.split())
            assert word_count <= 65, f"Too many words ({word_count}): {text!r}"

    def test_no_ai_mention(self):
        for text in self.replies:
            lower = text.lower()
            for term in AI_MENTIONS:
                assert term not in lower, f"AI mention '{term}' found: {text!r}"
            assert not re.search(r'\bai\b', lower), f"'AI' as standalone word found: {text!r}"

    def test_no_never_say_phrases(self):
        for text in self.replies:
            lower = text.lower()
            for phrase in NEVER_SAY:
                assert phrase.lower() not in lower, f"Never-say phrase '{phrase}' found: {text!r}"

    def test_no_valuation_promises(self):
        for text in self.replies:
            lower = text.lower()
            assert not re.search(r'\$\s*[\d,]+', text), f"Dollar amount found: {text!r}"
            assert "valued at" not in lower, f"Valuation promise found: {text!r}"
            assert "worth approximately" not in lower, f"Valuation promise found: {text!r}"

    def test_hot_lead_triggers_handoff(self, master_config):
        hot_reply = {
            "body": "Ready to sell. My number is 832-555-0199.",
            "from_email": "hot@test.com", "from_name": "Maria",
            "company": "Test Co", "classification": "hot_positive",
        }
        result = handle_reply(hot_reply, master_config, mock=False)
        assert result["action"] == "handoff", f"Expected handoff, got {result['action']}"


# ---------------------------------------------------------------------------
# Opener guard rails
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_API_KEY, reason=SKIP_REASON)
class TestOpenerGuardRails:

    @pytest.fixture(autouse=True)
    def _generate_openers(self, tone_config):
        self.openers = []
        self.tone_config = tone_config
        system_prompt = build_system_prompt(tone_config)
        for lead in OPENER_LEADS:
            opener = generate_opener(lead, system_prompt, DEFAULT_MODEL, tone_config)
            self.openers.append((opener, lead))

    def test_word_count_5_to_25(self):
        for opener, lead in self.openers:
            word_count = len(opener.split())
            assert 5 <= word_count <= 25, (
                f"Opener for {lead['business_name']} has {word_count} words: {opener!r}"
            )

    def test_no_exclamation_marks(self):
        for opener, lead in self.openers:
            assert "!" not in opener, (
                f"Exclamation in opener for {lead['business_name']}: {opener!r}"
            )

    def test_no_never_say_phrases(self):
        for opener, lead in self.openers:
            lower = opener.lower()
            for phrase in NEVER_SAY:
                assert phrase.lower() not in lower, (
                    f"Never-say '{phrase}' in opener for {lead['business_name']}: {opener!r}"
                )

    def test_passes_validation(self):
        for opener, lead in self.openers:
            assert validate_opener(opener, self.tone_config), (
                f"Opener for {lead['business_name']} failed validate_opener(): {opener!r}"
            )

    def test_references_business_context(self):
        for opener, lead in self.openers:
            lower = opener.lower()
            has_ref = any([
                lead["business_name"].lower() in lower,
                lead["industry"].lower() in lower,
                lead["city"].lower() in lower,
                str(lead.get("rating", "")) in opener,
                str(lead.get("reviews_count", "")) in opener,
            ])
            assert has_ref, (
                f"Opener for {lead['business_name']} doesn't reference business: {opener!r}"
            )


# ---------------------------------------------------------------------------
# Variant guard rails
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_API_KEY, reason=SKIP_REASON)
class TestVariantGuardRails:

    @pytest.fixture(autouse=True)
    def _generate_variant(self, tone_config, variants_config, master_config):
        human_variants = [v for v in variants_config.get("variants", []) if v.get("type") == "human"]
        constraints = master_config.get("copy_optimization", {}).get("variant_constraints", {})
        self.variant = generate_challenger_variant(
            human_variants, tone_config, constraints, DEFAULT_MODEL, mock=False,
        )
        self.constraints = constraints

    def test_valid_json_structure(self):
        assert "subject" in self.variant, "Missing 'subject' in variant"
        assert "body" in self.variant, "Missing 'body' in variant"
        assert self.variant["subject"], "Empty subject"
        assert self.variant["body"], "Empty body"

    def test_body_max_60_words(self):
        words = self.variant["body"].split()
        assert len(words) <= 65, f"Variant body has {len(words)} words"

    def test_body_max_3_sentences(self):
        body = self.variant["body"]
        sentences = [s.strip() for s in body.replace("?", ".").replace("...", ".").split(".") if s.strip()]
        assert len(sentences) <= 4, f"Variant body has {len(sentences)} sentences"

    def test_no_exclamation_marks(self):
        assert "!" not in self.variant["body"], f"Exclamation in variant body"
        assert "!" not in self.variant["subject"], f"Exclamation in variant subject"

    def test_passes_validation(self):
        assert validate_variant(self.variant["body"], self.constraints), (
            f"Variant failed validate_variant(): {self.variant['body']!r}"
        )

    def test_uses_template_variables(self):
        body = self.variant["body"]
        template_vars = ["{{opener}}", "{{business_name}}", "{{city}}", "{{industry}}"]
        has_template = any(tv in body for tv in template_vars)
        assert has_template, (
            f"Variant body uses no template variables: {body!r}"
        )

    def test_type_is_ai(self):
        assert self.variant["type"] == "ai"
        assert self.variant["active"] is False


# ---------------------------------------------------------------------------
# Auto-reply guard rails — production handle_reply() path with real LLM
# ---------------------------------------------------------------------------

class TestAutoReplyGuardRailsReal:
    """Test auto-reply through the production handle_reply() path with real LLM."""

    @pytest.fixture
    def config(self):
        config_path = Path(__file__).resolve().parent.parent / "config" / "accessory_masters.json"
        with open(config_path) as f:
            return json.load(f)

    def _make_reply(self, body, classification="positive"):
        return {"body": body, "from_email": "owner@test.com", "from_name": "James",
                "company": "Test Co", "classification": classification}

    def test_positive_reply_has_no_exclamation_marks(self, config):
        if not os.environ.get("OPENROUTER_API_KEY"):
            pytest.skip("OPENROUTER_API_KEY not set")
        result = handle_reply(self._make_reply("Yes, I'm interested in selling."), config, mock=False)
        assert result["action"] == "auto_reply"
        assert "!" not in result["reply_text"]

    def test_positive_reply_under_60_words(self, config):
        if not os.environ.get("OPENROUTER_API_KEY"):
            pytest.skip("OPENROUTER_API_KEY not set")
        result = handle_reply(self._make_reply("Tell me more about the process."), config, mock=False)
        assert result["action"] == "auto_reply"
        assert len(result["reply_text"].split()) <= 60

    def test_positive_reply_under_3_sentences(self, config):
        if not os.environ.get("OPENROUTER_API_KEY"):
            pytest.skip("OPENROUTER_API_KEY not set")
        result = handle_reply(self._make_reply("What would my business sell for?"), config, mock=False)
        assert result["action"] == "auto_reply"
        sentences = [s for s in re.split(r'(?<=[.!?])\s+', result["reply_text"]) if s.strip()]
        assert len(sentences) <= 4  # Allow greeting + 3 sentences

    def test_positive_reply_no_dollar_amounts(self, config):
        if not os.environ.get("OPENROUTER_API_KEY"):
            pytest.skip("OPENROUTER_API_KEY not set")
        result = handle_reply(self._make_reply("How much could I get for a car wash doing $800K revenue?"), config, mock=False)
        assert result["action"] == "auto_reply"
        assert not re.search(r'\$\s*[\d,]+', result["reply_text"])

    def test_hot_positive_triggers_handoff(self, config):
        result = handle_reply(self._make_reply("Call me at 832-555-0199, ready to sell.", "hot_positive"), config, mock=False)
        assert result["action"] == "handoff"

    def test_negative_skipped(self, config):
        result = handle_reply(self._make_reply("Not interested, remove me.", "negative"), config, mock=False)
        assert result["action"] == "skip"

    def test_neutral_skipped(self, config):
        result = handle_reply(self._make_reply("Out of office until Monday.", "neutral"), config, mock=False)
        assert result["action"] == "skip"

    def test_objection_valuation_no_specific_number(self, config):
        if not os.environ.get("OPENROUTER_API_KEY"):
            pytest.skip("OPENROUTER_API_KEY not set")
        result = handle_reply(self._make_reply("How much is my car wash worth?"), config, mock=False)
        assert result["action"] == "auto_reply"
        assert not re.search(r'\$\s*[\d,]+', result["reply_text"])
