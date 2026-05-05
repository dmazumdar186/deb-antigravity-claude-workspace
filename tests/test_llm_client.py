#!/usr/bin/env python3
"""
test_llm_client.py
description: Tests for LLM client retry logic — verifies retry on 429/5xx and no retry on 4xx.
inputs: None (OpenAI client fully mocked).
outputs: pytest results.
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "execution"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


class TestRetryLogic:
    """Test the retry behavior in chat_completion()."""

    def _make_success_response(self, text="Hello"):
        """Build a mock OpenAI ChatCompletion response."""
        message = MagicMock()
        message.content = text
        choice = MagicMock()
        choice.message = message
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    def _make_mock_client(self, side_effect):
        """Build a mock OpenAI client with chat.completions.create set to side_effect."""
        client = MagicMock()
        client.chat.completions.create = MagicMock(side_effect=side_effect)
        return client

    @patch("modules.llm_client.time.sleep")  # Don't actually sleep in tests
    @patch("modules.llm_client._get_client")
    def test_succeeds_on_first_try(self, mock_get_client, mock_sleep):
        """Normal case -- no retry needed."""
        success = self._make_success_response("Test reply")
        mock_get_client.return_value = self._make_mock_client([success])

        from modules.llm_client import chat_completion

        result = chat_completion(system="sys", user_message="hello")
        assert result == "Test reply"
        mock_sleep.assert_not_called()

    @patch("modules.llm_client.time.sleep")
    @patch("modules.llm_client._get_client")
    def test_retries_on_rate_limit(self, mock_get_client, mock_sleep):
        """429 error should be retried."""
        from openai import RateLimitError

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}
        mock_response.json.return_value = {"error": {"message": "rate limited"}}

        rate_err = RateLimitError(
            message="rate limited",
            response=mock_response,
            body={"error": {"message": "rate limited"}},
        )
        success = self._make_success_response("After retry")

        mock_get_client.return_value = self._make_mock_client([rate_err, success])

        from modules.llm_client import chat_completion

        result = chat_completion(system="sys", user_message="hello")
        assert result == "After retry"
        assert mock_sleep.call_count == 1

    @patch("modules.llm_client.time.sleep")
    @patch("modules.llm_client._get_client")
    def test_retries_on_server_error(self, mock_get_client, mock_sleep):
        """500 error should be retried."""
        from openai import APIStatusError

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.headers = {}
        mock_response.json.return_value = {"error": {"message": "internal error"}}

        server_err = APIStatusError(
            message="internal error",
            response=mock_response,
            body={"error": {"message": "internal error"}},
        )
        success = self._make_success_response("Recovered")

        mock_get_client.return_value = self._make_mock_client([server_err, success])

        from modules.llm_client import chat_completion

        result = chat_completion(system="sys", user_message="hello")
        assert result == "Recovered"
        assert mock_sleep.call_count == 1

    @patch("modules.llm_client.time.sleep")
    @patch("modules.llm_client._get_client")
    def test_no_retry_on_client_error(self, mock_get_client, mock_sleep):
        """400 error should NOT be retried -- re-raised immediately."""
        from openai import APIStatusError

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.headers = {}
        mock_response.json.return_value = {"error": {"message": "bad request"}}

        client_err = APIStatusError(
            message="bad request",
            response=mock_response,
            body={"error": {"message": "bad request"}},
        )

        mock_get_client.return_value = self._make_mock_client([client_err])

        from modules.llm_client import chat_completion

        with pytest.raises(APIStatusError):
            chat_completion(system="sys", user_message="hello")
        mock_sleep.assert_not_called()

    @patch("modules.llm_client.time.sleep")
    @patch("modules.llm_client._get_client")
    def test_raises_after_max_retries_exhausted(self, mock_get_client, mock_sleep):
        """After MAX_RETRIES+1 attempts on rate limit, the last exception is raised."""
        from openai import RateLimitError

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}
        mock_response.json.return_value = {"error": {"message": "rate limited"}}

        rate_err = RateLimitError(
            message="rate limited",
            response=mock_response,
            body={"error": {"message": "rate limited"}},
        )

        # MAX_RETRIES is 2, so 3 total attempts — all fail
        mock_get_client.return_value = self._make_mock_client([rate_err, rate_err, rate_err])

        from modules.llm_client import chat_completion

        with pytest.raises(RateLimitError):
            chat_completion(system="sys", user_message="hello")
        assert mock_sleep.call_count == 2  # retried twice before giving up
