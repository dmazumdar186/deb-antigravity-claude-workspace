"""
test_pipeline.py
description: Comprehensive pytest test suite for the Accessory Masters cold email pipeline.
inputs: None (all tests run offline with mock=True).
outputs: pytest results.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "execution"))

from modules.reply_classifier import classify_mock, classify, DEFAULT_MOCK_SIGNALS
from modules.outputs.auto_reply import (
    handle_reply,
    should_handoff,
    _generate_reply_mock,
)
from modules.outputs.telegram import format_positive_reply, notify_positive_reply
from modules.outputs.report_generator import (
    generate_mock_metrics,
    generate_report,
    format_html_report,
    format_telegram_report,
    format_slack_report,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def accessory_masters_config():
    """Load the real Accessory Masters config file."""
    config_path = ROOT / "config" / "accessory_masters.json"
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def auto_reply_config():
    """Minimal config with auto_reply enabled."""
    return {
        "auto_reply": {
            "enabled": True,
            "model": "anthropic/claude-haiku-4.5",
            "delay_min_seconds": 120,
            "delay_max_seconds": 420,
            "sender_persona": "Aleksandar, business broker backed by Hedgestone Capital Group",
            "hot_lead_signals": [
                "phone number", "my number", "call me at",
                "ready to sell", "want to sell", "schedule a call",
            ],
            "guard_rails": [
                "Never promise specific valuations",
                "Never use exclamation marks",
                "Never write more than 3 sentences",
                "Never mention AI or automation",
            ],
        },
        "tone": {
            "auto_reply_instruction": "Write 2-3 short sentences max.",
        },
    }


@pytest.fixture
def disabled_auto_reply_config():
    """Config with auto_reply disabled."""
    return {
        "auto_reply": {"enabled": False},
    }


@pytest.fixture
def sample_positive_reply():
    return {
        "body": "I've been thinking about selling my restaurant. What's the process?",
        "from_email": "owner@example.com",
        "from_name": "James",
        "company": "Joe's Diner",
        "classification": "positive",
    }


@pytest.fixture
def sample_hot_reply():
    return {
        "body": "I'm ready to sell. Call me at 832-555-0199.",
        "from_email": "maria@example.com",
        "from_name": "Maria Garcia",
        "company": "Katy Marina",
        "classification": "hot_positive",
    }


@pytest.fixture
def sample_negative_reply():
    return {
        "body": "Not interested, please remove me from your list.",
        "from_email": "tony@example.com",
        "from_name": "Tony",
        "company": "Tony's Pizza",
        "classification": "negative",
    }


@pytest.fixture
def sample_neutral_reply():
    return {
        "body": "I am currently out of the office and will return on Monday.",
        "from_email": "auto@example.com",
        "from_name": "",
        "company": "Clean & Fresh Laundromat",
        "classification": "neutral",
    }


@pytest.fixture
def sample_telegram_reply():
    return {
        "from_name": "Jane Doe",
        "from_email": "jane@example.com",
        "company": "Acme Corp",
        "industry": "SaaS",
        "email_subject": "Quick question about your growth strategy",
        "body": "Hi, thanks for reaching out! I'd love to schedule a call to discuss.",
        "received_at": "2026-04-30T10:00:00Z",
        "ghl_link": "https://app.gohighlevel.com/contacts/example",
    }


# ===================================================================
# 1. Reply Classifier Tests
# ===================================================================

class TestReplyClassifier:
    """Tests for modules.reply_classifier.classify_mock()."""

    def test_hot_positive_phone_number(self):
        assert classify_mock("Call me at 555-1234") == "hot_positive"

    def test_hot_positive_ready_to_sell(self):
        assert classify_mock("I'm ready to sell my business") == "hot_positive"

    def test_hot_positive_schedule_call(self):
        assert classify_mock("Let's schedule a call to discuss") == "hot_positive"

    def test_hot_positive_my_number_is(self):
        assert classify_mock("My number is 832-555-0199") == "hot_positive"

    def test_negative_not_interested(self):
        assert classify_mock("Not interested, thanks") == "negative"

    def test_negative_remove(self):
        assert classify_mock("Please remove me from your list") == "negative"

    def test_negative_unsubscribe(self):
        assert classify_mock("Unsubscribe me immediately") == "negative"

    def test_negative_stop(self):
        assert classify_mock("Stop emailing me") == "negative"

    def test_neutral_out_of_office(self):
        assert classify_mock("I am out of office until next week") == "neutral"

    def test_neutral_auto_reply(self):
        assert classify_mock("This is an auto-reply message") == "neutral"

    def test_neutral_vacation(self):
        assert classify_mock("I'm on vacation until June") == "neutral"

    def test_positive_interested(self):
        assert classify_mock("I'm interested in learning more") == "positive"

    def test_positive_tell_me_more(self):
        assert classify_mock("Tell me more about the process") == "positive"

    def test_positive_yes(self):
        assert classify_mock("Yes, I'd like to hear more") == "positive"

    def test_unknown_text_defaults_neutral(self):
        assert classify_mock("kjashdfkjhsdf random gibberish") == "neutral"

    def test_empty_text_defaults_neutral(self):
        assert classify_mock("") == "neutral"

    def test_none_text_defaults_neutral(self):
        assert classify_mock(None) == "neutral"

    def test_custom_signals(self):
        custom = {
            "hot_positive": ["urgent deal"],
            "negative": ["go away"],
            "neutral": ["maybe later"],
            "positive": ["sounds good"],
        }
        assert classify_mock("This is an urgent deal", signals=custom) == "hot_positive"
        assert classify_mock("Go away please", signals=custom) == "negative"
        assert classify_mock("Maybe later", signals=custom) == "neutral"
        assert classify_mock("That sounds good to me", signals=custom) == "positive"
        # Unrecognized text still defaults to neutral
        assert classify_mock("Hello there", signals=custom) == "neutral"

    def test_classify_unified_routes_to_mock(self):
        """classify() with mock=True should call classify_mock()."""
        result = classify("I'm interested in selling", mock=True)
        assert result == "positive"

    def test_classify_mock_priority_hot_over_positive(self):
        """hot_positive signals should take priority over positive when both match."""
        # "call me" is positive, but "call me at" is hot_positive
        assert classify_mock("Call me at 555-1234, I'm interested") == "hot_positive"

    def test_classify_case_insensitive(self):
        assert classify_mock("NOT INTERESTED") == "negative"
        assert classify_mock("READY TO SELL") == "hot_positive"


# ===================================================================
# 2. Auto Reply Tests
# ===================================================================

class TestAutoReply:
    """Tests for modules.outputs.auto_reply."""

    def test_handle_reply_handoff_for_hot_lead(self, auto_reply_config, sample_hot_reply):
        result = handle_reply(sample_hot_reply, auto_reply_config, mock=True)
        assert result["action"] == "handoff"
        assert "hot lead" in result["reason"].lower()

    def test_handle_reply_auto_reply_for_positive(self, auto_reply_config, sample_positive_reply):
        result = handle_reply(sample_positive_reply, auto_reply_config, mock=True)
        assert result["action"] == "auto_reply"
        assert "reply_text" in result
        assert len(result["reply_text"]) > 0
        assert "delay_seconds" in result

    def test_handle_reply_skip_when_disabled(self, disabled_auto_reply_config, sample_positive_reply):
        result = handle_reply(sample_positive_reply, disabled_auto_reply_config, mock=True)
        assert result["action"] == "skip"
        assert "disabled" in result["reason"].lower()

    def test_handle_reply_skip_for_negative(self, auto_reply_config, sample_negative_reply):
        result = handle_reply(sample_negative_reply, auto_reply_config, mock=True)
        assert result["action"] == "skip"
        assert "not actionable" in result["reason"].lower()

    def test_handle_reply_skip_for_neutral(self, auto_reply_config, sample_neutral_reply):
        result = handle_reply(sample_neutral_reply, auto_reply_config, mock=True)
        assert result["action"] == "skip"
        assert "not actionable" in result["reason"].lower()

    def test_should_handoff_phone_number(self):
        assert should_handoff("Call me at 555-1234") is True

    def test_should_handoff_ready_to_sell(self):
        assert should_handoff("I'm ready to sell my business") is True

    def test_should_handoff_schedule_call(self):
        assert should_handoff("Let's schedule a call") is True

    def test_should_handoff_my_number(self):
        assert should_handoff("My number is 832-555-0199") is True

    def test_should_handoff_false_for_normal_text(self):
        assert should_handoff("I'm interested in selling") is False

    def test_should_handoff_false_for_empty(self):
        assert should_handoff("") is False

    def test_should_handoff_false_for_none(self):
        assert should_handoff(None) is False

    def test_should_handoff_custom_signals(self):
        custom = ["magic word", "secret phrase"]
        assert should_handoff("This has the magic word", hot_lead_signals=custom) is True
        assert should_handoff("Normal text", hot_lead_signals=custom) is False

    def test_generate_reply_mock_returns_nonempty(self):
        result = _generate_reply_mock("Tell me about the process", "From: James at Joe's Diner")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_auto_reply_delay_in_range(self, auto_reply_config, sample_positive_reply):
        result = handle_reply(sample_positive_reply, auto_reply_config, mock=True)
        assert result["action"] == "auto_reply"
        delay = result["delay_seconds"]
        assert 120 <= delay <= 420

    def test_handoff_takes_priority_over_positive_classification(self, auto_reply_config):
        """Even if classification is positive, body with hot signals should handoff."""
        reply = {
            "body": "Ready to sell, call me at 555-1234",
            "from_email": "test@example.com",
            "from_name": "Test",
            "company": "Test Co",
            "classification": "positive",
        }
        result = handle_reply(reply, auto_reply_config, mock=True)
        assert result["action"] == "handoff"


# ===================================================================
# 3. Telegram Tests
# ===================================================================

class TestTelegram:
    """Tests for modules.outputs.telegram."""

    def test_format_includes_lead_name(self, sample_telegram_reply):
        msg = format_positive_reply(sample_telegram_reply)
        assert "Jane Doe" in msg

    def test_format_includes_email(self, sample_telegram_reply):
        msg = format_positive_reply(sample_telegram_reply)
        assert "jane@example.com" in msg

    def test_format_includes_company(self, sample_telegram_reply):
        msg = format_positive_reply(sample_telegram_reply)
        assert "Acme Corp" in msg

    def test_format_includes_industry(self, sample_telegram_reply):
        msg = format_positive_reply(sample_telegram_reply)
        assert "SaaS" in msg

    def test_format_truncates_body_to_200_chars(self):
        long_body = "A" * 500
        reply = {
            "from_name": "Test",
            "from_email": "test@example.com",
            "company": "Test Co",
            "industry": "Testing",
            "email_subject": "Subject",
            "body": long_body,
            "received_at": "2026-04-30",
            "ghl_link": "#",
        }
        msg = format_positive_reply(reply)
        # The body preview should be at most 200 A's
        assert "A" * 201 not in msg
        assert "A" * 200 in msg

    def test_format_handles_missing_fields(self):
        msg = format_positive_reply({})
        assert "Unknown" in msg  # defaults for from_name, company, industry

    def test_notify_returns_false_when_token_missing(self, sample_telegram_reply):
        result = notify_positive_reply("", "some_chat_id", sample_telegram_reply)
        assert result is False

    def test_notify_returns_false_when_chat_id_missing(self, sample_telegram_reply):
        result = notify_positive_reply("some_token", "", sample_telegram_reply)
        assert result is False

    def test_notify_returns_false_when_both_missing(self, sample_telegram_reply):
        result = notify_positive_reply("", "", sample_telegram_reply)
        assert result is False

    def test_format_custom_template(self, sample_telegram_reply):
        template = "Lead: {from_name} | Email: {from_email}"
        msg = format_positive_reply(sample_telegram_reply, template=template)
        assert msg == "Lead: Jane Doe | Email: jane@example.com"


# ===================================================================
# 4. Report Generator Tests
# ===================================================================

class TestReportGenerator:
    """Tests for modules.outputs.report_generator."""

    def test_generate_mock_metrics_has_instantly_key(self):
        metrics = generate_mock_metrics()
        assert "instantly" in metrics

    def test_generate_mock_metrics_has_ghl_key(self):
        metrics = generate_mock_metrics()
        assert "ghl" in metrics

    def test_generate_mock_metrics_instantly_fields(self):
        metrics = generate_mock_metrics()
        instantly = metrics["instantly"]
        expected_keys = [
            "emails_sent", "emails_delivered", "emails_opened",
            "replies", "bounces", "unsubscribes",
            "deliverability_pct", "open_rate_pct", "reply_rate_pct", "bounce_rate_pct",
        ]
        for key in expected_keys:
            assert key in instantly, f"Missing instantly key: {key}"

    def test_generate_mock_metrics_ghl_fields(self):
        metrics = generate_mock_metrics()
        ghl = metrics["ghl"]
        expected_keys = [
            "contacts_created", "opportunities_total", "opportunities_open",
            "opportunities_won", "appointments_booked", "pipeline_value",
        ]
        for key in expected_keys:
            assert key in ghl, f"Missing ghl key: {key}"

    def test_generate_mock_metrics_values_positive(self):
        metrics = generate_mock_metrics()
        assert metrics["instantly"]["emails_sent"] > 0
        assert metrics["ghl"]["contacts_created"] >= 0

    def test_generate_report_structure(self):
        metrics = generate_mock_metrics()
        report = generate_report(metrics["instantly"], metrics["ghl"])
        assert "client" in report
        assert "generated_at" in report
        assert "date_range" in report
        assert "email" in report
        assert "crm" in report
        assert "summary" in report

    def test_generate_report_combines_metrics(self):
        metrics = generate_mock_metrics()
        report = generate_report(metrics["instantly"], metrics["ghl"])
        assert report["email"] == metrics["instantly"]
        assert report["crm"] == metrics["ghl"]

    def test_generate_report_with_config(self):
        metrics = generate_mock_metrics()
        config = {"client": "Accessory Masters"}
        report = generate_report(metrics["instantly"], metrics["ghl"], config=config)
        assert report["client"] == "Accessory Masters"

    def test_generate_report_summary_keys(self):
        metrics = generate_mock_metrics()
        report = generate_report(metrics["instantly"], metrics["ghl"])
        summary = report["summary"]
        assert "total_emails_sent" in summary
        assert "total_replies" in summary
        assert "reply_rate_pct" in summary
        assert "deliverability_pct" in summary
        assert "contacts_created" in summary
        assert "appointments_booked" in summary
        assert "pipeline_value" in summary
        assert "opportunities_open" in summary

    def test_format_html_report_returns_valid_html(self):
        metrics = generate_mock_metrics()
        report = generate_report(metrics["instantly"], metrics["ghl"])
        html = format_html_report(report)
        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html
        assert "<body>" in html

    def test_format_html_report_contains_metric_values(self):
        instantly = {
            "emails_sent": 999,
            "emails_delivered": 950,
            "emails_opened": 400,
            "replies": 25,
            "bounces": 10,
            "unsubscribes": 3,
            "deliverability_pct": 95.1,
            "open_rate_pct": 42.1,
            "reply_rate_pct": 2.6,
            "bounce_rate_pct": 1.0,
        }
        ghl = {
            "contacts_created": 12,
            "opportunities_total": 8,
            "opportunities_open": 5,
            "opportunities_won": 3,
            "appointments_booked": 4,
            "pipeline_value": 250000.0,
        }
        report = generate_report(instantly, ghl)
        html = format_html_report(report)
        assert "999" in html         # emails_sent
        assert "95.1" in html        # deliverability_pct
        assert "42.1" in html        # open_rate_pct
        assert "25" in html          # replies
        assert "12" in html          # contacts_created
        assert "250,000" in html     # pipeline_value formatted

    def test_format_html_report_contains_client_name(self):
        metrics = generate_mock_metrics()
        config = {"client": "Test Client Inc"}
        report = generate_report(metrics["instantly"], metrics["ghl"], config=config)
        html = format_html_report(report)
        assert "Test Client Inc" in html

    def test_format_telegram_report_returns_formatted_message(self):
        metrics = generate_mock_metrics()
        report = generate_report(metrics["instantly"], metrics["ghl"])
        msg = format_telegram_report(report)
        assert isinstance(msg, str)
        assert len(msg) > 0
        assert "Weekly Report" in msg

    def test_format_telegram_report_contains_metrics(self):
        instantly = {
            "emails_sent": 750,
            "emails_delivered": 720,
            "emails_opened": 300,
            "replies": 18,
            "bounces": 8,
            "unsubscribes": 2,
            "deliverability_pct": 96.0,
            "open_rate_pct": 41.7,
            "reply_rate_pct": 2.5,
            "bounce_rate_pct": 1.1,
        }
        ghl = {
            "contacts_created": 7,
            "opportunities_total": 4,
            "opportunities_open": 3,
            "opportunities_won": 1,
            "appointments_booked": 2,
            "pipeline_value": 175000.0,
        }
        report = generate_report(instantly, ghl)
        msg = format_telegram_report(report)
        assert "750" in msg    # emails_sent
        assert "18" in msg     # replies
        assert "7" in msg      # contacts_created
        assert "175,000" in msg  # pipeline_value

    def test_format_slack_report_returns_formatted_message(self):
        metrics = generate_mock_metrics()
        report = generate_report(metrics["instantly"], metrics["ghl"])
        msg = format_slack_report(report)
        assert isinstance(msg, str)
        assert len(msg) > 0
        assert "Weekly Report" in msg

    def test_format_slack_report_contains_metrics(self):
        instantly = {
            "emails_sent": 850,
            "emails_delivered": 820,
            "emails_opened": 350,
            "replies": 20,
            "bounces": 6,
            "unsubscribes": 1,
            "deliverability_pct": 96.5,
            "open_rate_pct": 42.7,
            "reply_rate_pct": 2.4,
            "bounce_rate_pct": 0.7,
        }
        ghl = {
            "contacts_created": 10,
            "opportunities_total": 6,
            "opportunities_open": 4,
            "opportunities_won": 2,
            "appointments_booked": 3,
            "pipeline_value": 300000.0,
        }
        report = generate_report(instantly, ghl)
        msg = format_slack_report(report)
        assert "850" in msg    # emails_sent
        assert "20" in msg     # replies
        assert "10" in msg     # contacts_created
        assert "300,000" in msg  # pipeline_value

    def test_format_slack_report_contains_slack_emoji(self):
        metrics = generate_mock_metrics()
        report = generate_report(metrics["instantly"], metrics["ghl"])
        msg = format_slack_report(report)
        assert ":bar_chart:" in msg
        assert ":envelope:" in msg


# ===================================================================
# 5. Pipeline Integration Tests
# ===================================================================

class TestPipelineIntegration:
    """Integration tests for the full pipeline and reply polling."""

    def test_full_mock_force_pipeline_exits_cleanly(self, accessory_masters_config, tmp_path):
        """run_pipeline() with --mock --force should complete without errors."""
        from gtm_client_workflows.accessory_masters_pipeline import run_pipeline

        # Override state_file and output_dir to use tmp_path
        config = accessory_masters_config.copy()
        config["pipeline"] = {
            "state_file": str(tmp_path / "pipeline_state.json"),
            "output_dir": str(tmp_path),
        }

        # run_pipeline doesn't return a value; it should simply not raise
        run_pipeline(config, stage="all", mock=True, force=True)

        # Verify state file was created
        state_file = tmp_path / "pipeline_state.json"
        assert state_file.exists()

    def test_poll_replies_mock_processes_all_types(self, accessory_masters_config):
        """poll_replies() in mock mode should process all 4 reply types."""
        from gtm_client_workflows.accessory_masters_pipeline import poll_replies

        # poll_replies doesn't return a value; it should not raise
        poll_replies(accessory_masters_config, mock=True)

    def test_poll_replies_mock_classifies_correctly(self, accessory_masters_config):
        """Verify that mock replies get the expected classifications."""
        from gtm_client_workflows.accessory_masters_pipeline import _get_mock_replies

        mock_signals = accessory_masters_config.get("classification", {}).get("mock_signals")
        replies = _get_mock_replies()

        classifications = []
        for reply in replies:
            cls = classify_mock(reply["body"], signals=mock_signals)
            classifications.append(cls)

        # Based on the mock reply bodies:
        # Maria: "ready to sell" + "call me at" + "my number is" -> hot_positive
        # John: "sell" + "process" -> positive (but "sell" is in positive signals)
        # Tony: "not interested" + "remove" -> negative
        # Auto: "out of the office" + "will return" -> neutral
        assert "hot_positive" in classifications
        assert "negative" in classifications
        assert "neutral" in classifications
        # John's reply contains "sell" which is positive
        assert "positive" in classifications

    def test_mock_replies_have_required_fields(self):
        """All mock replies should have the fields needed by the pipeline."""
        from gtm_client_workflows.accessory_masters_pipeline import _get_mock_replies

        required = {"from_email", "from_name", "subject", "body", "company", "industry", "received_at"}
        for reply in _get_mock_replies():
            missing = required - set(reply.keys())
            assert not missing, f"Reply from {reply.get('from_email')} missing: {missing}"
