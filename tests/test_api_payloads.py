#!/usr/bin/env python3
"""
test_api_payloads.py
description: Tests for API payload construction and routing logic in Instantly, GHL, AnymailFinder, and Million Verifier.
inputs: None (all HTTP calls mocked).
outputs: pytest results.
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "execution"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


# ---------------------------------------------------------------------------
# Instantly: _build_lead_payload and _parse_name
# ---------------------------------------------------------------------------

from modules.outputs.instantly import _build_lead_payload, _parse_name


class TestParseName:
    """Edge cases for _parse_name()."""

    def test_full_name(self):
        first, last = _parse_name("John Smith")
        assert first == "John"
        assert last == "Smith"

    def test_first_name_only(self):
        first, last = _parse_name("John")
        assert first == "John"
        assert last == ""

    def test_empty_string(self):
        first, last = _parse_name("")
        assert first == ""
        assert last == ""

    def test_none(self):
        first, last = _parse_name(None)
        assert first == ""
        assert last == ""

    def test_three_part_name(self):
        first, last = _parse_name("Mary Jane Watson")
        assert first == "Mary"
        assert last == "Jane Watson"


class TestBuildLeadPayload:
    """Verify _build_lead_payload maps fields correctly."""

    SAMPLE_LEAD = {
        "owner_email": "tony@sparkle.com",
        "owner_name": "Tony Rossi",
        "business_name": "Sparkle Car Wash",
        "personalized_opener": "Saw your 4.5-star reviews",
        "industry": "car wash",
        "city": "Houston",
    }

    def test_email_mapped(self):
        payload = _build_lead_payload(self.SAMPLE_LEAD, "camp_123")
        assert payload["email"] == "tony@sparkle.com"

    def test_name_split(self):
        payload = _build_lead_payload(self.SAMPLE_LEAD, "camp_123")
        assert payload["first_name"] == "Tony"
        assert payload["last_name"] == "Rossi"

    def test_company_mapped(self):
        payload = _build_lead_payload(self.SAMPLE_LEAD, "camp_123")
        assert payload["company_name"] == "Sparkle Car Wash"

    def test_campaign_id(self):
        payload = _build_lead_payload(self.SAMPLE_LEAD, "camp_123")
        assert payload["campaign"] == "camp_123"

    def test_custom_variables(self):
        payload = _build_lead_payload(self.SAMPLE_LEAD, "camp_123")
        assert payload["custom_variables"]["opener"] == "Saw your 4.5-star reviews"
        assert payload["custom_variables"]["industry"] == "car wash"
        assert payload["custom_variables"]["city"] == "Houston"

    def test_missing_fields_default_empty(self):
        sparse_lead = {"owner_email": "a@b.com"}
        payload = _build_lead_payload(sparse_lead, "camp_x")
        assert payload["first_name"] == ""
        assert payload["last_name"] == ""
        assert payload["company_name"] == ""


# ---------------------------------------------------------------------------
# AnymailFinder: find_email routing logic
# ---------------------------------------------------------------------------

from enrichment.anymailfinder_lookup import find_email


class TestFindEmailRouting:
    """Verify find_email routes to person search vs company search correctly."""

    PERSON_RESULT = {"email": "tony@sparkle.com", "name": "Tony Rossi", "confidence": 90, "type": "personal"}
    COMPANY_RESULT = {"email": "info@sparkle.com", "name": "", "confidence": 70, "type": "generic"}

    @patch("enrichment.anymailfinder_lookup.find_email_person", return_value=PERSON_RESULT)
    @patch("enrichment.anymailfinder_lookup.find_email_company")
    def test_person_search_when_full_name(self, mock_company, mock_person):
        result = find_email("sparkle.com", "Sparkle Car Wash", "key123", owner_name="Tony Rossi")
        mock_person.assert_called_once_with("sparkle.com", "Tony", "Rossi", "key123")
        mock_company.assert_not_called()
        assert result == self.PERSON_RESULT

    @patch("enrichment.anymailfinder_lookup.find_email_person")
    @patch("enrichment.anymailfinder_lookup.find_email_company", return_value=COMPANY_RESULT)
    def test_company_search_when_single_name(self, mock_company, mock_person):
        result = find_email("sparkle.com", "Sparkle Car Wash", "key123", owner_name="Tony")
        mock_person.assert_not_called()
        mock_company.assert_called_once_with("sparkle.com", "Sparkle Car Wash", "key123")
        assert result == self.COMPANY_RESULT

    @patch("enrichment.anymailfinder_lookup.find_email_person")
    @patch("enrichment.anymailfinder_lookup.find_email_company", return_value=COMPANY_RESULT)
    def test_company_search_when_no_name(self, mock_company, mock_person):
        result = find_email("sparkle.com", "Sparkle Car Wash", "key123", owner_name="")
        mock_person.assert_not_called()
        mock_company.assert_called_once()
        assert result == self.COMPANY_RESULT

    @patch("enrichment.anymailfinder_lookup.find_email_person", return_value=None)
    @patch("enrichment.anymailfinder_lookup.find_email_company", return_value=COMPANY_RESULT)
    def test_falls_back_to_company_when_person_fails(self, mock_company, mock_person):
        result = find_email("sparkle.com", "Sparkle Car Wash", "key123", owner_name="Tony Rossi")
        mock_person.assert_called_once()
        mock_company.assert_called_once()
        assert result == self.COMPANY_RESULT


# ---------------------------------------------------------------------------
# Million Verifier: verify_email response parsing
# ---------------------------------------------------------------------------

from enrichment.million_verifier import verify_email


class TestVerifyEmailParsing:
    """Verify that verify_email parses API responses correctly."""

    def _mock_response(self, result_str, quality):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"result": result_str, "quality": quality}
        return mock_resp

    @patch("enrichment.million_verifier.requests.get")
    def test_ok_result(self, mock_get):
        mock_get.return_value = self._mock_response("ok", 97)
        result = verify_email("test@example.com", "fake_key")
        assert result["result"] == "ok"
        assert result["quality_score"] == 97

    @patch("enrichment.million_verifier.requests.get")
    def test_catch_all_result(self, mock_get):
        mock_get.return_value = self._mock_response("catch_all", 70)
        result = verify_email("info@example.com", "fake_key")
        assert result["result"] == "catch_all"
        assert result["quality_score"] == 70

    @patch("enrichment.million_verifier.requests.get")
    def test_invalid_result(self, mock_get):
        mock_get.return_value = self._mock_response("invalid", 0)
        result = verify_email("bad@example.com", "fake_key")
        assert result["result"] == "invalid"
        assert result["quality_score"] == 0

    @patch("enrichment.million_verifier.requests.get")
    def test_disposable_result(self, mock_get):
        mock_get.return_value = self._mock_response("disposable", 10)
        result = verify_email("temp@throwaway.com", "fake_key")
        assert result["result"] == "disposable"
        assert result["quality_score"] == 10

    @patch("enrichment.million_verifier.requests.get")
    def test_ok_and_catch_all_are_acceptable(self, mock_get):
        """Mirrors production logic: 'ok' and 'catch_all' pass; 'invalid' and 'disposable' do not."""
        accept = {"ok", "catch_all"}
        for status in ["ok", "catch_all"]:
            mock_get.return_value = self._mock_response(status, 80)
            result = verify_email("x@example.com", "key")
            assert result["result"] in accept

    @patch("enrichment.million_verifier.requests.get")
    def test_invalid_and_disposable_are_rejected(self, mock_get):
        accept = {"ok", "catch_all"}
        for status in ["invalid", "disposable"]:
            mock_get.return_value = self._mock_response(status, 0)
            result = verify_email("x@example.com", "key")
            assert result["result"] not in accept
