"""
Tests for LLM gate failover behaviour in job_search_llm_gate.py.

All tests mock both anthropic and google.generativeai — no live API calls.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution.personal_workflows.job_search_llm_gate import (  # noqa: E402
    GateVerdict,
    classify_batch,
    _parse_verdict_json,
    _make_verdict,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_job(title: str = "Senior Product Manager", company: str = "ACME") -> dict:
    return {
        "title": title,
        "company_name": company,
        "location": "Paris, France",
        "description_snippet": f"Exciting {title} role at {company}.",
        "contract_type": None,
    }


def _make_claude_response(relevance: str, contract_type: str, reason: str) -> MagicMock:
    """Build a mock Anthropic response object."""
    payload = json.dumps({
        "relevance": relevance,
        "contract_type": contract_type,
        "reason": reason,
    })
    content_block = MagicMock()
    content_block.text = payload
    response = MagicMock()
    response.content = [content_block]
    return response


def _make_gemini_response(relevance: str, contract_type: str, reason: str) -> MagicMock:
    """Build a mock Gemini response object."""
    payload = json.dumps({
        "relevance": relevance,
        "contract_type": contract_type,
        "reason": reason,
    })
    response = MagicMock()
    response.text = payload
    return response


# ---------------------------------------------------------------------------
# Test: Happy path — all jobs classified via Claude
# ---------------------------------------------------------------------------


def test_happy_path_claude():
    """All jobs are classified by Claude; no failover triggered."""
    jobs = [_make_job("Senior PM"), _make_job("AI PM")]

    mock_claude_resp = _make_claude_response("relevant", "CDI", "matches profile")
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_claude_resp

    with patch(
        "execution.personal_workflows.job_search_llm_gate._build_claude_client",
        return_value=mock_client,
    ):
        verdicts = classify_batch(jobs, max_jobs=200)

    assert len(verdicts) == 2
    for v in verdicts:
        assert v is not None
        assert v.relevance == "relevant"
        assert v.contract_type == "CDI"

    # Gemini must NOT have been called
    assert mock_client.messages.create.call_count == 2


# ---------------------------------------------------------------------------
# Test: Claude raises 429 → sticky failover to Gemini
# ---------------------------------------------------------------------------


def test_claude_429_triggers_gemini_failover():
    """When Claude raises RateLimitError, all subsequent jobs use Gemini (sticky)."""
    import anthropic

    jobs = [_make_job("PM1"), _make_job("PM2"), _make_job("PM3")]

    # Claude raises RateLimitError on every call
    mock_claude_client = MagicMock()
    mock_claude_client.messages.create.side_effect = anthropic.RateLimitError(
        message="rate limited",
        response=MagicMock(status_code=429),
        body={},
    )

    mock_gemini_resp = _make_gemini_response("borderline", "Contract", "unclear role")
    mock_gemini_model = MagicMock()
    mock_gemini_model.generate_content.return_value = mock_gemini_resp

    with (
        patch(
            "execution.personal_workflows.job_search_llm_gate._build_claude_client",
            return_value=mock_claude_client,
        ),
        patch(
            "execution.personal_workflows.job_search_llm_gate._build_gemini_model",
            return_value=mock_gemini_model,
        ),
    ):
        verdicts = classify_batch(jobs, max_jobs=200)

    assert len(verdicts) == 3
    for v in verdicts:
        assert v is not None
        assert v.relevance == "borderline"
        assert v.contract_type == "Contract"

    # All 3 jobs went through Gemini
    assert mock_gemini_model.generate_content.call_count == 3


# ---------------------------------------------------------------------------
# Test: Gemini-only mode (Claude raises on first job, Gemini handles rest)
# ---------------------------------------------------------------------------


def test_failover_is_sticky():
    """Once switched to Gemini, all remaining jobs use Gemini — no toggling back."""
    import anthropic

    jobs = [_make_job(f"Job {i}") for i in range(5)]

    # Claude raises on the very first call
    mock_claude_client = MagicMock()
    mock_claude_client.messages.create.side_effect = anthropic.InternalServerError(
        message="server error",
        response=MagicMock(status_code=500),
        body={},
    )

    mock_gemini_resp = _make_gemini_response("relevant", "Permanent", "good match")
    mock_gemini_model = MagicMock()
    mock_gemini_model.generate_content.return_value = mock_gemini_resp

    with (
        patch(
            "execution.personal_workflows.job_search_llm_gate._build_claude_client",
            return_value=mock_claude_client,
        ),
        patch(
            "execution.personal_workflows.job_search_llm_gate._build_gemini_model",
            return_value=mock_gemini_model,
        ),
    ):
        verdicts = classify_batch(jobs, max_jobs=200)

    # Claude called once (the first attempt), then switched to Gemini for all 5
    assert mock_gemini_model.generate_content.call_count == 5


# ---------------------------------------------------------------------------
# Test: Malformed JSON → parse_error fallback
# ---------------------------------------------------------------------------


def test_malformed_json_returns_parse_error_fallback():
    """When Claude returns non-JSON, verdict falls back to borderline/parse_error."""
    jobs = [_make_job("PM Role")]

    bad_content = MagicMock()
    bad_content.text = "Sorry, I can't classify this job."
    mock_response = MagicMock()
    mock_response.content = [bad_content]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch(
        "execution.personal_workflows.job_search_llm_gate._build_claude_client",
        return_value=mock_client,
    ):
        verdicts = classify_batch(jobs, max_jobs=200)

    assert len(verdicts) == 1
    v = verdicts[0]
    assert v is not None
    assert v.relevance == "borderline"
    assert v.contract_type is None
    assert "parse_error" in v.reason


def test_partial_json_missing_contract_type():
    """JSON missing contract_type falls back to contract_type=None."""
    raw = json.dumps({"relevance": "relevant", "reason": "good"})
    result = _parse_verdict_json(raw)
    assert result["relevance"] == "relevant"
    assert result["contract_type"] is None


def test_unknown_relevance_defaults_to_borderline():
    """Unknown relevance value is normalised to 'borderline'."""
    raw = json.dumps({"relevance": "maybe", "contract_type": "CDI", "reason": "test"})
    result = _parse_verdict_json(raw)
    assert result["relevance"] == "borderline"


def test_markdown_fences_stripped():
    """LLM output wrapped in ```json ... ``` must still parse correctly."""
    inner = json.dumps({"relevance": "irrelevant", "contract_type": "Unknown", "reason": "mismatch"})
    fenced = f"```json\n{inner}\n```"
    result = _parse_verdict_json(fenced)
    assert result["relevance"] == "irrelevant"
    # Unknown contract_type → None
    assert result["contract_type"] is None


# ---------------------------------------------------------------------------
# Test: Hard cap — jobs beyond max_jobs get None
# ---------------------------------------------------------------------------


def test_hard_cap_returns_none_for_excess():
    """Jobs beyond max_jobs cap must get None in output (not classified)."""
    jobs = [_make_job(f"Job {i}") for i in range(10)]

    mock_resp = _make_claude_response("relevant", "CDI", "ok")
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_resp

    with patch(
        "execution.personal_workflows.job_search_llm_gate._build_claude_client",
        return_value=mock_client,
    ):
        verdicts = classify_batch(jobs, max_jobs=3)

    assert len(verdicts) == 10
    # First 3 classified
    for v in verdicts[:3]:
        assert v is not None
        assert v.relevance == "relevant"
    # Last 7 → None
    for v in verdicts[3:]:
        assert v is None


def test_hard_cap_zero_jobs_not_classified():
    """max_jobs=0 means all jobs get None."""
    jobs = [_make_job("PM")]

    with patch(
        "execution.personal_workflows.job_search_llm_gate._build_claude_client",
        return_value=MagicMock(),
    ):
        verdicts = classify_batch(jobs, max_jobs=0)

    assert len(verdicts) == 1
    assert verdicts[0] is None


def test_empty_input_returns_empty():
    """classify_batch([]) must return []."""
    verdicts = classify_batch([])
    assert verdicts == []


# ---------------------------------------------------------------------------
# Test: _parse_verdict_json edge cases
# ---------------------------------------------------------------------------


def test_parse_unknown_contract_type_normalised_to_none():
    """'Unknown' contract_type → None (normalised away)."""
    raw = json.dumps({"relevance": "borderline", "contract_type": "Unknown", "reason": "unclear"})
    result = _parse_verdict_json(raw)
    assert result["contract_type"] is None


def test_parse_known_contract_type_preserved():
    """Recognised contract_type values are preserved with correct casing."""
    for ct_input, ct_expected in [
        ("CDI", "CDI"),
        ("cdi", "CDI"),
        ("Freelance", "Freelance"),
        ("PERMANENT", "Permanent"),
        ("contract", "Contract"),
    ]:
        raw = json.dumps({"relevance": "relevant", "contract_type": ct_input, "reason": "ok"})
        result = _parse_verdict_json(raw)
        assert result["contract_type"] == ct_expected, (
            f"Input '{ct_input}' expected '{ct_expected}', got '{result['contract_type']}'"
        )
