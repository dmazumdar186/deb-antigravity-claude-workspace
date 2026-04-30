"""
test_variant_generator.py
description: Pytest test suite for the variant generator module (Deliverable 12).
inputs: None (all tests run offline with mock=True).
outputs: pytest results.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "execution"))

from personalization.variant_generator import (
    load_variants,
    validate_variant,
    generate_mock_variant,
    generate_challenger_variant,
    generate_mock_performance,
    fetch_variant_performance,
    recommend_replacement,
    format_variant_report,
    build_variant_system_prompt,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_variants():
    return [
        {"variant_id": "v1", "type": "human", "label": "Cold Open", "subject": "Quick question", "body": "I help business owners explore what their business could sell for.", "active": True, "instantly_step_id": "step_0"},
        {"variant_id": "v2", "type": "human", "label": "Bump", "subject": "Following up", "body": "Hey, just checking in.", "active": True, "instantly_step_id": "step_1"},
        {"variant_id": "v3", "type": "human", "label": "Case Study", "subject": "Sold one nearby", "body": "We sold a business like yours in your area recently.", "active": True, "instantly_step_id": "step_2"},
        {"variant_id": "v4", "type": "human", "label": "Free Value", "subject": "Free guide", "body": "I put together a short guide for owners thinking about selling.", "active": True, "instantly_step_id": "step_3"},
    ]


@pytest.fixture
def sample_ai_variant():
    return {"variant_id": "ai_20260430", "type": "ai", "label": "AI Challenger", "subject": "Thought about selling?", "body": "Business owners in Houston are getting serious offers right now. Worth a conversation?", "active": True, "instantly_step_id": "step_4"}


@pytest.fixture
def sample_performance():
    return [
        {"variant_id": "v1", "emails_sent": 250, "replies": 10, "positive_replies": 7, "negative_replies": 3, "response_rate_pct": 4.0},
        {"variant_id": "v2", "emails_sent": 220, "replies": 7, "positive_replies": 4, "negative_replies": 3, "response_rate_pct": 3.2},
        {"variant_id": "v3", "emails_sent": 200, "replies": 9, "positive_replies": 6, "negative_replies": 3, "response_rate_pct": 4.5},
        {"variant_id": "v4", "emails_sent": 180, "replies": 5, "positive_replies": 3, "negative_replies": 2, "response_rate_pct": 2.8},
        {"variant_id": "ai_20260430", "emails_sent": 150, "replies": 7, "positive_replies": 5, "negative_replies": 2, "response_rate_pct": 4.7},
    ]


@pytest.fixture
def copy_optimization_config():
    return {
        "min_sends_for_comparison": 100,
        "replacement_threshold_pct": 0.5,
        "max_variants": 5,
        "variant_constraints": {
            "max_words": 60,
            "max_sentences": 3,
            "no_exclamation_marks": True,
        },
    }


@pytest.fixture
def sample_tone_config():
    return {
        "voice": "I",
        "sender_name": "Aleksandar",
        "company_name": "Accessory Masters",
        "tone_description": "Blunt, direct, no fluff.",
        "copy_philosophy": "Ultra-short. One sentence if possible.",
        "never_say": [],
        "example_openers": ["I noticed your car wash on Main St has been open since 2012."],
    }


# ===================================================================
# 1. Variant Generation Tests
# ===================================================================

class TestVariantGeneration:
    """Tests for variant generation and validation."""

    def test_generate_mock_variant_returns_dict(self, sample_variants):
        result = generate_mock_variant(sample_variants)
        assert isinstance(result, dict)
        required_keys = {"variant_id", "type", "label", "subject", "body", "created_at", "active"}
        assert required_keys.issubset(set(result.keys()))

    def test_generate_mock_variant_type_is_ai(self, sample_variants):
        result = generate_mock_variant(sample_variants)
        assert result["type"] == "ai"

    def test_generate_mock_variant_not_active(self, sample_variants):
        result = generate_mock_variant(sample_variants)
        assert result["active"] is False

    def test_generate_challenger_mock_mode(self, sample_variants, sample_tone_config, copy_optimization_config):
        result = generate_challenger_variant(
            sample_variants,
            sample_tone_config,
            copy_optimization_config.get("variant_constraints", {}),
            client=None,
            model=None,
            mock=True,
        )
        assert isinstance(result, dict)
        assert "variant_id" in result
        assert "body" in result

    def test_validate_variant_accepts_valid(self):
        constraints = {"max_words": 60, "max_sentences": 3, "no_exclamation_marks": True}
        assert validate_variant("I help business owners explore options.", constraints) is True

    def test_validate_variant_rejects_exclamation(self):
        constraints = {"max_words": 60, "max_sentences": 3, "no_exclamation_marks": True}
        assert validate_variant("Great opportunity for you!", constraints) is False

    def test_validate_variant_rejects_over_max_words(self):
        constraints = {"max_words": 60, "max_sentences": 3, "no_exclamation_marks": True}
        long_body = " ".join(["word"] * 70)
        assert validate_variant(long_body, constraints) is False


# ===================================================================
# 2. Variant Performance Tests
# ===================================================================

class TestVariantPerformance:
    """Tests for variant performance tracking."""

    def test_generate_mock_performance_length(self, sample_variants):
        active = [v for v in sample_variants if v.get("active")]
        perf = generate_mock_performance(active)
        assert len(perf) == len(active)

    def test_generate_mock_performance_has_required_fields(self, sample_variants):
        perf = generate_mock_performance(sample_variants)
        required = {"variant_id", "emails_sent", "replies", "response_rate_pct"}
        for entry in perf:
            assert required.issubset(set(entry.keys()))

    def test_generate_mock_performance_rates_positive(self, sample_variants):
        perf = generate_mock_performance(sample_variants)
        for entry in perf:
            assert entry["response_rate_pct"] > 0

    def test_fetch_variant_performance_mock(self, sample_variants):
        perf = fetch_variant_performance(
            api_url="", api_key="", campaign_id="",
            variants=sample_variants, mock=True,
        )
        assert isinstance(perf, list)
        assert len(perf) > 0

    def test_build_system_prompt_includes_tone(self, sample_tone_config, sample_variants):
        prompt = build_variant_system_prompt(sample_tone_config, sample_variants)
        assert "Blunt, direct" in prompt

    def test_build_system_prompt_includes_variants(self, sample_tone_config, sample_variants):
        prompt = build_variant_system_prompt(sample_tone_config, sample_variants)
        assert "I help business owners explore what their business could sell for." in prompt


# ===================================================================
# 3. Variant Recommendation Tests
# ===================================================================

class TestVariantRecommendation:
    """Tests for variant replacement recommendations."""

    def test_recommend_replace_when_ai_outperforms(self, sample_performance, copy_optimization_config):
        variants = [
            {"variant_id": "v1", "type": "human", "active": True},
            {"variant_id": "v2", "type": "human", "active": True},
            {"variant_id": "v3", "type": "human", "active": True},
            {"variant_id": "v4", "type": "human", "active": True},
            {"variant_id": "ai_20260430", "type": "ai", "active": True},
        ]
        result = recommend_replacement(variants, sample_performance, copy_optimization_config)
        assert result["action"] == "replace"

    def test_recommend_keep_when_ai_underperforms(self, copy_optimization_config):
        perf = [
            {"variant_id": "v1", "emails_sent": 200, "replies": 10, "response_rate_pct": 5.0},
            {"variant_id": "v2", "emails_sent": 200, "replies": 8, "response_rate_pct": 4.0},
            {"variant_id": "ai_bad", "emails_sent": 200, "replies": 2, "response_rate_pct": 1.0},
        ]
        variants = [
            {"variant_id": "v1", "type": "human", "active": True},
            {"variant_id": "v2", "type": "human", "active": True},
            {"variant_id": "ai_bad", "type": "ai", "active": True},
        ]
        result = recommend_replacement(variants, perf, copy_optimization_config)
        assert result["action"] == "keep"

    def test_recommend_insufficient_data(self, copy_optimization_config):
        perf = [
            {"variant_id": "v1", "emails_sent": 10, "replies": 1, "response_rate_pct": 10.0},
            {"variant_id": "ai_new", "emails_sent": 5, "replies": 0, "response_rate_pct": 0.0},
        ]
        variants = [
            {"variant_id": "v1", "type": "human", "active": True},
            {"variant_id": "ai_new", "type": "ai", "active": True},
        ]
        result = recommend_replacement(variants, perf, copy_optimization_config)
        assert result["action"] == "insufficient_data"

    def test_recommend_identifies_worst_human(self, sample_performance, copy_optimization_config):
        variants = [
            {"variant_id": "v1", "type": "human", "active": True},
            {"variant_id": "v2", "type": "human", "active": True},
            {"variant_id": "v3", "type": "human", "active": True},
            {"variant_id": "v4", "type": "human", "active": True},
            {"variant_id": "ai_20260430", "type": "ai", "active": True},
        ]
        result = recommend_replacement(variants, sample_performance, copy_optimization_config)
        assert result["worst_human"]["variant_id"] == "v4"

    def test_format_variant_report_nonempty(self, sample_variants, sample_performance):
        rec = {"action": "replace", "worst_human": {"variant_id": "v4"}, "ai_variant": {"variant_id": "ai_20260430"}, "reason": "AI outperforms worst human."}
        report = format_variant_report(sample_variants, sample_performance, rec)
        assert isinstance(report, str)
        assert len(report) > 0

    def test_format_variant_report_contains_rates(self, sample_variants, sample_performance):
        rec = {"action": "replace", "worst_human": {"variant_id": "v4"}, "ai_variant": {"variant_id": "ai_20260430"}, "reason": "AI outperforms worst human."}
        report = format_variant_report(sample_variants, sample_performance, rec)
        assert "4.0" in report or "4.0%" in report
        assert "2.8" in report or "2.8%" in report
