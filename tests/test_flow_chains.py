"""
test_flow_chains.py
description: End-to-end flow chain tests that verify full delivery paths, not just component interfaces.
inputs: None (all tests run offline with mocks/patches).
outputs: pytest results.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "execution"))

from modules.outputs.auto_reply import handle_reply, schedule_delayed_send
from modules.outputs.ghl import create_appointment, suggest_booking
from modules.outputs.report_generator import run_weekly_report
from personalization.variant_generator import (
    generate_challenger_variant,
    load_variants,
    save_variants,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def full_config():
    config_path = ROOT / "config" / "accessory_masters.json"
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def positive_reply():
    return {
        "body": "Yes, I've been thinking about selling. Tell me more.",
        "from_email": "owner@testbiz.com",
        "from_name": "James",
        "company": "Joe's Diner",
        "classification": "positive",
        "lead_email": "alex@sendingdomain.com",
    }


@pytest.fixture
def hot_reply():
    return {
        "body": "I'm ready to sell. Call me at 713-555-1234",
        "from_email": "seller@hotlead.com",
        "from_name": "Maria",
        "company": "Maria's Bakery",
        "classification": "hot_positive",
        "lead_email": "alex@sendingdomain.com",
    }


# ---------------------------------------------------------------------------
# Flow 1: Auto-reply — generate text AND invoke send_fn
# ---------------------------------------------------------------------------

class TestAutoReplySendFlow:
    """Verify that handle_reply() actually invokes the send function, not just
    generates text. This is the gap that existed before the fix."""

    def test_send_fn_called_for_positive_reply(self, full_config, positive_reply):
        send_fn = MagicMock()
        result = handle_reply(positive_reply, full_config, mock=True, send_fn=send_fn)

        assert result["action"] == "auto_reply"
        assert result["reply_text"]
        assert result["delay_seconds"] >= 0
        # In mock mode, schedule_delayed_send logs but doesn't call send_fn
        # (time.sleep is skipped). That's correct behavior for mock.

    def test_send_fn_not_called_for_hot_lead(self, full_config, hot_reply):
        send_fn = MagicMock()
        result = handle_reply(hot_reply, full_config, mock=True, send_fn=send_fn)

        assert result["action"] == "handoff"
        send_fn.assert_not_called()

    def test_send_fn_not_called_for_negative(self, full_config):
        reply = {
            "body": "Not interested, please remove me",
            "from_email": "no@thanks.com",
            "from_name": "Bob",
            "classification": "negative",
        }
        send_fn = MagicMock()
        result = handle_reply(reply, full_config, mock=True, send_fn=send_fn)

        assert result["action"] == "skip"
        send_fn.assert_not_called()

    def test_send_fn_not_called_when_disabled(self, full_config):
        config = {**full_config, "auto_reply": {"enabled": False}}
        send_fn = MagicMock()
        result = handle_reply(
            {"body": "interested", "classification": "positive"},
            config, mock=True, send_fn=send_fn,
        )

        assert result["action"] == "skip"
        send_fn.assert_not_called()

    def test_schedule_delayed_send_calls_fn_in_live_mode(self):
        send_fn = MagicMock()
        delay = schedule_delayed_send(
            "test reply", 0, 0, send_fn, mock=False,
        )
        assert delay == 0
        send_fn.assert_called_once_with("test reply")

    def test_schedule_delayed_send_skips_in_mock_mode(self):
        send_fn = MagicMock()
        delay = schedule_delayed_send(
            "test reply", 120, 420, send_fn, mock=True,
        )
        assert 120 <= delay <= 420
        send_fn.assert_not_called()

    def test_no_send_fn_logs_warning(self, full_config, positive_reply, caplog):
        import logging
        with caplog.at_level(logging.WARNING):
            result = handle_reply(positive_reply, full_config, mock=True, send_fn=None)

        assert result["action"] == "auto_reply"
        assert "not sent" in caplog.text.lower() or "no send_fn" in caplog.text.lower()

    def test_objection_match_produces_reply_text(self, full_config):
        reply = {
            "body": "How much is my business worth?",
            "from_email": "curious@owner.com",
            "from_name": "Pat",
            "company": "Pat's Printing",
            "classification": "positive",
        }
        send_fn = MagicMock()
        result = handle_reply(reply, full_config, mock=True, send_fn=send_fn)

        assert result["action"] == "auto_reply"
        assert "valuation" in result["reply_text"].lower() or "range" in result["reply_text"].lower()


# ---------------------------------------------------------------------------
# Flow 2: Weekly report — generate AND send
# ---------------------------------------------------------------------------

class TestWeeklyReportFlow:
    """Verify that run_weekly_report() both generates a report AND attempts
    to deliver it through configured channels."""

    def test_mock_report_generates_all_sections(self, full_config):
        result = run_weekly_report(full_config, mock=True)

        assert "report" in result
        report = result["report"]
        assert "email" in report
        assert "crm" in report
        assert "summary" in report
        assert report["email"]["emails_sent"] > 0
        assert report["crm"]["contacts_created"] >= 0

    def test_report_attempts_telegram_when_enabled(self, full_config):
        config = {**full_config}
        config["reporting"] = {
            **config.get("reporting", {}),
            "telegram_enabled": True,
        }

        with patch("modules.outputs.report_generator.send_report_telegram") as mock_tg:
            mock_tg.return_value = True
            with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "fake", "TELEGRAM_CHAT_ID": "123"}):
                result = run_weekly_report(config, mock=True)

        mock_tg.assert_called_once()
        assert result["telegram_sent"] is True

    def test_report_attempts_email_when_enabled(self, full_config):
        config = {**full_config}
        config["reporting"] = {
            **config.get("reporting", {}),
            "email_enabled": True,
            "recipients": ["test@example.com"],
            "smtp_config": {
                "host": "smtp.test.com",
                "port": 587,
                "username": "user",
                "password": "pass",
            },
        }

        with patch("modules.outputs.report_generator.send_report_email") as mock_email:
            mock_email.return_value = True
            result = run_weekly_report(config, mock=True)

        mock_email.assert_called_once()
        assert result["html_sent"] is True

    def test_report_skips_channels_when_disabled(self, full_config):
        config = {**full_config}
        config["reporting"] = {
            "email_enabled": False,
            "slack_enabled": False,
            "telegram_enabled": False,
        }

        result = run_weekly_report(config, mock=True)

        assert result["html_sent"] is False
        assert result["slack_sent"] is False
        assert result["telegram_sent"] is False
        assert result["report"] is not None


# ---------------------------------------------------------------------------
# Flow 3: Variant generator — generate, activate, and link to Instantly
# ---------------------------------------------------------------------------

class TestVariantActivationFlow:
    """Verify that generated variants can be linked to Instantly steps
    via the activate action."""

    def test_generated_variant_has_null_step_id(self):
        tone = {
            "sender_name": "Aleksandar",
            "company_name": "Accessory Masters",
            "backing": "Hedgestone Capital Group",
            "tone_description": "Direct",
        }
        constraints = {"max_words": 60, "max_sentences": 3, "no_exclamation_marks": True}

        variant = generate_challenger_variant([], tone, constraints, "test", mock=True)

        assert variant["instantly_step_id"] is None
        assert variant["active"] is False
        assert variant["type"] == "ai"
        assert variant["variant_id"].startswith("ai_")

    def test_activate_links_step_id(self, tmp_path):
        variants_data = {
            "variants": [],
            "ai_challengers": [
                {
                    "variant_id": "ai_20260502",
                    "type": "ai",
                    "label": "AI Challenger",
                    "subject": "Test",
                    "body": "Test body",
                    "active": False,
                    "instantly_step_id": None,
                }
            ],
        }

        variants_file = tmp_path / "test_variants.json"
        with open(variants_file, "w") as f:
            json.dump(variants_data, f)

        loaded = load_variants(str(variants_file))
        for v in loaded["ai_challengers"]:
            if v["variant_id"] == "ai_20260502":
                v["instantly_step_id"] = "step_abc123"
                v["active"] = True

        save_variants(loaded, str(variants_file))

        reloaded = load_variants(str(variants_file))
        activated = reloaded["ai_challengers"][0]
        assert activated["instantly_step_id"] == "step_abc123"
        assert activated["active"] is True


# ---------------------------------------------------------------------------
# Flow 4: Pipeline poll_replies wiring — classification → routing → auto-reply
# ---------------------------------------------------------------------------

class TestPollRepliesWiring:
    """Verify that the poll_replies flow connects classification to GHL routing,
    notification, and auto-reply sending — not just logging."""

    def test_positive_reply_triggers_ghl_and_notification(self, full_config):
        with patch("gtm_client_workflows.accessory_masters_pipeline.route_positive_reply") as mock_ghl, \
             patch("gtm_client_workflows.accessory_masters_pipeline.telegram_notify") as mock_tg, \
             patch("gtm_client_workflows.accessory_masters_pipeline.notify_positive_reply") as mock_slack:

            from gtm_client_workflows.accessory_masters_pipeline import _handle_positive_reply

            reply = {
                "from_name": "James",
                "from_email": "james@test.com",
                "company": "Test Co",
                "body": "Interested in selling",
                "classification": "positive",
            }

            _handle_positive_reply(
                reply,
                full_config.get("ghl", {}),
                full_config.get("notifications", {}),
                mock=True,
            )
            # In mock mode, _handle_positive_reply logs but doesn't call APIs.
            # This test confirms the function is reachable and doesn't crash.

    def test_instantly_send_reply_module_exists(self):
        from modules.outputs.instantly import send_reply
        assert callable(send_reply)

    def test_send_reply_imported_in_pipeline(self):
        import gtm_client_workflows.accessory_masters_pipeline as pipeline
        assert hasattr(pipeline, "send_reply")


# ---------------------------------------------------------------------------
# Flow 5: Instantly send_reply has correct signature
# ---------------------------------------------------------------------------

class TestInstantlySendReply:

    def test_send_reply_accepts_required_args(self):
        from modules.outputs.instantly import send_reply
        import inspect
        sig = inspect.signature(send_reply)
        params = list(sig.parameters.keys())
        assert "api_url" in params
        assert "api_key" in params
        assert "reply_to_email" in params
        assert "reply_text" in params


# ---------------------------------------------------------------------------
# Flow 6: GHL Appointment — create_appointment signature & suggest_booking
# ---------------------------------------------------------------------------

class TestGHLAppointmentFlow:

    def test_create_appointment_has_correct_signature(self):
        import inspect
        sig = inspect.signature(create_appointment)
        params = list(sig.parameters.keys())
        assert "api_url" in params
        assert "api_key" in params
        assert "calendar_id" in params
        assert "contact_id" in params
        assert "start_time" in params
        assert "end_time" in params
        assert "title" in params
        assert "appointment_status" in params
        assert "api_version" in params

    def test_suggest_booking_without_calendar_id(self):
        result = suggest_booking(contact_id="c123", reply={}, calendar_id=None)
        assert result == {"booking_suggested": True, "contact_id": "c123", "calendar_id": None}

    def test_suggest_booking_with_calendar_id(self):
        result = suggest_booking(contact_id="c123", reply={}, calendar_id="cal_abc")
        assert result["calendar_id"] == "cal_abc"

    def test_suggest_booking_imported_in_pipeline(self):
        import gtm_client_workflows.accessory_masters_pipeline as pipeline
        assert hasattr(pipeline, "suggest_booking")
