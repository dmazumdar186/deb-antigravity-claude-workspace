"""
test_monkey.py — Monkey Tests
Edge cases, invalid inputs, and error resilience.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "execution"))

from modules.reply_classifier import classify_mock
from modules.outputs.auto_reply import handle_reply, should_handoff, generate_reply_mock
from modules.outputs.telegram import format_positive_reply


class TestClassifyMockEdgeCases:
    """classify_mock should handle garbage inputs gracefully."""

    def test_none_input(self):
        assert classify_mock(None) == "neutral"

    def test_empty_string(self):
        assert classify_mock("") == "neutral"

    def test_integer_input_raises(self):
        with pytest.raises(AttributeError):
            classify_mock(12345)

    def test_very_long_string(self):
        long_text = "interested " * 5000
        result = classify_mock(long_text)
        assert result in ("neutral", "positive", "negative", "hot_positive")

    def test_unicode_input(self):
        result = classify_mock("Je suis intéressé 🤝")
        assert result in ("neutral", "positive", "negative", "hot_positive")

    def test_special_characters(self):
        result = classify_mock("!@#$%^&*(){}[]|\\:\";<>?,./~`")
        assert result == "neutral"

    def test_whitespace_only(self):
        result = classify_mock("   \t\n  ")
        assert result == "neutral"


class TestShouldHandoffEdgeCases:
    """should_handoff should handle garbage inputs."""

    def test_none_input(self):
        assert should_handoff(None) is False

    def test_empty_string(self):
        assert should_handoff("") is False

    def test_numeric_input_raises(self):
        with pytest.raises(AttributeError):
            should_handoff(99999)

    def test_empty_signals_uses_defaults(self):
        # None signals falls through to defaults; explicit empty list also falls to defaults
        result = should_handoff("call me at 555", hot_lead_signals=None)
        assert result is True


class TestFormatPositiveReplyEdgeCases:
    """format_positive_reply should handle incomplete data."""

    def test_empty_dict(self):
        msg = format_positive_reply({})
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_none_values(self):
        reply = {"from_name": None, "from_email": None, "company": None}
        msg = format_positive_reply(reply)
        assert isinstance(msg, str)

    def test_numeric_values(self):
        reply = {"from_name": 123, "from_email": 456, "company": 789}
        msg = format_positive_reply(reply)
        assert isinstance(msg, str)

    def test_empty_body(self):
        reply = {"from_name": "Test", "body": "", "from_email": "t@t.com"}
        msg = format_positive_reply(reply)
        assert isinstance(msg, str)


class TestHandleReplyEdgeCases:
    """handle_reply should handle missing/broken inputs."""

    @pytest.fixture
    def valid_config(self):
        return {
            "auto_reply": {
                "enabled": True,
                "delay_min_seconds": 120,
                "delay_max_seconds": 420,
                "sender_persona": "Test",
                "hot_lead_signals": ["call me"],
                "guard_rails": [],
            },
            "tone": {"auto_reply_instruction": "Be brief."},
        }

    def test_disabled_config(self):
        reply = {"body": "interested", "classification": "positive"}
        config = {"auto_reply": {"enabled": False}}
        result = handle_reply(reply, config, mock=True)
        assert result["action"] == "skip"

    def test_negative_classification(self, valid_config):
        reply = {"body": "not interested", "classification": "negative",
                 "from_email": "a@b.com", "from_name": "X", "company": "Y"}
        result = handle_reply(reply, valid_config, mock=True)
        assert result["action"] == "skip"

    def test_neutral_classification(self, valid_config):
        reply = {"body": "out of office", "classification": "neutral",
                 "from_email": "a@b.com", "from_name": "X", "company": "Y"}
        result = handle_reply(reply, valid_config, mock=True)
        assert result["action"] == "skip"


class TestGenerateReplyMockEdgeCases:
    """generate_reply_mock should handle edge case inputs."""

    def test_empty_body(self):
        result = generate_reply_mock("", "context")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_none_context(self):
        result = generate_reply_mock("Tell me more", None)
        assert isinstance(result, str)

    def test_very_long_body(self):
        long = "Tell me about selling " * 1000
        result = generate_reply_mock(long, "context")
        assert isinstance(result, str)
        assert len(result) > 0


class TestParseSerperEdgeCases:
    """parse_serper_results should handle malformed data."""

    def test_empty_places_list(self):
        from lead_sourcing.serper_maps_scraper import parse_serper_results
        leads = parse_serper_results([], "query", "industry", "run-1", "2026-05-01")
        assert leads == []

    def test_places_with_missing_keys(self):
        from lead_sourcing.serper_maps_scraper import parse_serper_results
        places = [{"title": "Test Biz"}]
        leads = parse_serper_results(places, "query", "industry", "run-1", "2026-05-01")
        assert len(leads) == 1
        assert leads[0]["business_name"] == "Test Biz"

    def test_places_with_empty_dicts(self):
        from lead_sourcing.serper_maps_scraper import parse_serper_results
        places = [{}]
        leads = parse_serper_results(places, "query", "industry", "run-1", "2026-05-01")
        assert isinstance(leads, list)


class TestParseProspeoEdgeCases:
    """parse_prospeo_results should handle malformed data."""

    def test_empty_results_list(self):
        from lead_sourcing.prospeo_leads import parse_prospeo_results
        leads = parse_prospeo_results([], "industry", "run-1", "2026-05-01")
        assert leads == []

    def test_results_with_empty_dicts(self):
        from lead_sourcing.prospeo_leads import parse_prospeo_results
        leads = parse_prospeo_results([{}], "industry", "run-1", "2026-05-01")
        assert isinstance(leads, list)

    def test_results_with_partial_data(self):
        from lead_sourcing.prospeo_leads import parse_prospeo_results
        partial = [{"first_name": "Alice", "last_name": "Smith"}]
        leads = parse_prospeo_results(partial, "industry", "run-1", "2026-05-01")
        assert isinstance(leads, list)


class TestDeduplicateEdgeCases:
    """deduplicate should handle edge cases."""

    def test_empty_list(self):
        from modules.pipeline_utils import deduplicate
        assert deduplicate([]) == []

    def test_single_item(self):
        from modules.pipeline_utils import deduplicate
        leads = [{"business_name": "Test", "domain": "test.com", "phone": "555"}]
        result = deduplicate(leads)
        assert len(result) == 1

    def test_all_duplicates(self):
        from modules.pipeline_utils import deduplicate
        lead = {"business_name": "Test", "domain": "test.com", "phone": "555"}
        result = deduplicate([lead, lead.copy(), lead.copy()])
        assert len(result) == 1

    def test_no_duplicates(self):
        from modules.pipeline_utils import deduplicate
        leads = [
            {"business_name": "A", "domain": "a.com", "phone": "111"},
            {"business_name": "B", "domain": "b.com", "phone": "222"},
        ]
        result = deduplicate(leads)
        assert len(result) == 2
