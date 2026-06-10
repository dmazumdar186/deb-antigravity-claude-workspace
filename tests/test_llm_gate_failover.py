"""
Tests for the FREE-first, batched job_search_llm_gate.

Architecture under test:
  tier 0 = Gemini primary (batched)   — free
  tier 1 = Gemini secondary (batched) — free
  tier 2 = Anthropic (batched)        — PAID, only if anthropic_optin=True

All LLM calls are mocked — no live API hits. classify_batch is always called with
throttle_s=0 so tests don't sleep.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution.personal_workflows.job_search_llm_gate import (  # noqa: E402
    classify_batch,
    _parse_verdict_json,
    _parse_verdict_array,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _job(title="Senior AI Product Manager", company="ACME"):
    return {
        "title": title, "company_name": company, "location": "Paris, France",
        "description_snippet": f"{title} at {company}.", "contract_type": None,
    }


def _verdict(relevance="relevant", contract="CDI", fit=85, identity="salaried", reason="ok"):
    return {"relevance": relevance, "contract_type": contract,
            "fit_score": fit, "match_identity": identity, "reason": reason}


def _gemini_model_returning(verdict_lists):
    """A mock Gemini model whose generate_content returns a JSON-array response per call.
    `verdict_lists` is a list of per-call verdict lists (consumed in order)."""
    model = MagicMock()
    responses = []
    for vlist in verdict_lists:
        r = MagicMock()
        r.text = json.dumps(vlist)
        responses.append(r)
    model.generate_content.side_effect = responses
    return model


def _gemini_model_raising(exc=RuntimeError("429 quota exceeded")):
    model = MagicMock()
    model.generate_content.side_effect = exc
    return model


# ---------------------------------------------------------------------------
# Happy path + batching
# ---------------------------------------------------------------------------


def test_happy_path_gemini_single_batch():
    """3 jobs, batch_size 10 → ONE batched Gemini call; verdicts carry fit_score."""
    jobs = [_job("Senior PM"), _job("AI PM"), _job("Data PM")]
    model = _gemini_model_returning([[_verdict(fit=88), _verdict(fit=82), _verdict(fit=90)]])
    with patch(
        "execution.personal_workflows.job_search_llm_gate._build_gemini_model",
        return_value=model,
    ):
        verdicts = classify_batch(jobs, max_jobs=200, batch_size=10, throttle_s=0)
    assert len(verdicts) == 3
    assert [v.fit_score for v in verdicts] == [88, 82, 90]
    assert all(v.match_identity == "salaried" for v in verdicts)
    # Batched: exactly ONE API call for 3 jobs
    assert model.generate_content.call_count == 1


def test_batching_splits_into_multiple_calls():
    """25 jobs, batch_size 10 → 3 calls (10 + 10 + 5)."""
    jobs = [_job(f"PM {i}") for i in range(25)]
    model = _gemini_model_returning([
        [_verdict() for _ in range(10)],
        [_verdict() for _ in range(10)],
        [_verdict() for _ in range(5)],
    ])
    with patch(
        "execution.personal_workflows.job_search_llm_gate._build_gemini_model",
        return_value=model,
    ):
        verdicts = classify_batch(jobs, max_jobs=200, batch_size=10, throttle_s=0)
    assert len(verdicts) == 25
    assert model.generate_content.call_count == 3


# ---------------------------------------------------------------------------
# Tier escalation
# ---------------------------------------------------------------------------


def test_primary_gemini_fails_secondary_handles():
    """Primary Gemini raises → secondary Gemini scores the batch."""
    jobs = [_job("PM1"), _job("PM2")]
    primary = _gemini_model_raising()
    secondary = _gemini_model_returning([[_verdict(fit=70), _verdict(fit=60)]])

    def _build(model_name):
        return primary if model_name == "gemini-2.5-flash" else secondary

    with patch(
        "execution.personal_workflows.job_search_llm_gate._build_gemini_model",
        side_effect=_build,
    ):
        verdicts = classify_batch(jobs, max_jobs=200, batch_size=10, throttle_s=0)
    assert [v.fit_score for v in verdicts] == [70, 60]
    assert secondary.generate_content.call_count == 1


def test_both_gemini_fail_no_optin_yields_parse_error_no_paid_call():
    """Both free Gemini tiers fail and anthropic_optin=False → parse_error fallbacks,
    and the PAID Anthropic client is NEVER built."""
    jobs = [_job("PM1"), _job("PM2")]
    bad = _gemini_model_raising()
    with (
        patch("execution.personal_workflows.job_search_llm_gate._build_gemini_model", return_value=bad),
        patch("execution.personal_workflows.job_search_llm_gate._build_claude_client") as claude_builder,
    ):
        verdicts = classify_batch(jobs, max_jobs=200, batch_size=10, throttle_s=0,
                                  anthropic_optin=False)
    assert all(v.relevance == "borderline" and v.fit_score == 0 for v in verdicts)
    assert all("parse_error" in v.reason for v in verdicts)
    claude_builder.assert_not_called()  # never incurs a paid call


def test_both_gemini_fail_with_optin_uses_anthropic():
    """Both Gemini tiers fail and anthropic_optin=True → Anthropic batch scores the jobs."""
    jobs = [_job("PM1"), _job("PM2")]
    bad = _gemini_model_raising()
    claude_resp = MagicMock()
    claude_block = MagicMock()
    claude_block.text = json.dumps([_verdict(fit=95), _verdict(fit=91)])
    claude_resp.content = [claude_block]
    claude_client = MagicMock()
    claude_client.messages.create.return_value = claude_resp
    with (
        patch("execution.personal_workflows.job_search_llm_gate._build_gemini_model", return_value=bad),
        patch("execution.personal_workflows.job_search_llm_gate._build_claude_client", return_value=claude_client),
    ):
        verdicts = classify_batch(jobs, max_jobs=200, batch_size=10, throttle_s=0,
                                  anthropic_optin=True)
    assert [v.fit_score for v in verdicts] == [95, 91]
    assert claude_client.messages.create.call_count == 1


# ---------------------------------------------------------------------------
# Cap, empty, length-mismatch
# ---------------------------------------------------------------------------


def test_hard_cap_returns_none_for_excess():
    """Jobs beyond max_jobs get None; classified ones are scored."""
    jobs = [_job(f"PM {i}") for i in range(10)]
    model = _gemini_model_returning([[_verdict() for _ in range(3)]])
    with patch(
        "execution.personal_workflows.job_search_llm_gate._build_gemini_model",
        return_value=model,
    ):
        verdicts = classify_batch(jobs, max_jobs=3, batch_size=10, throttle_s=0)
    assert len(verdicts) == 10
    assert all(v is not None for v in verdicts[:3])
    assert all(v is None for v in verdicts[3:])


def test_empty_input_returns_empty():
    assert classify_batch([], throttle_s=0) == []


def test_array_length_mismatch_is_padded():
    """Gemini returns fewer objects than jobs in the batch → missing ones become parse_error."""
    jobs = [_job("A"), _job("B"), _job("C")]
    model = _gemini_model_returning([[_verdict(fit=88), _verdict(fit=77)]])  # only 2 for 3 jobs
    with patch(
        "execution.personal_workflows.job_search_llm_gate._build_gemini_model",
        return_value=model,
    ):
        verdicts = classify_batch(jobs, max_jobs=200, batch_size=10, throttle_s=0)
    assert len(verdicts) == 3
    assert verdicts[0].fit_score == 88
    assert verdicts[1].fit_score == 77
    assert verdicts[2].fit_score == 0 and "parse_error" in verdicts[2].reason


def test_primary_unparseable_escalates_to_secondary():
    """A truncated/garbage primary response (whole batch unparseable) must ESCALATE to the
    secondary model rather than silently dropping every job to parse_error."""
    jobs = [_job("A"), _job("B")]
    primary = MagicMock()
    bad = MagicMock(); bad.text = "garbage, not json at all"
    primary.generate_content.return_value = bad
    secondary = _gemini_model_returning([[_verdict(fit=81), _verdict(fit=72)]])

    def _build(model_name):
        return primary if model_name == "gemini-2.5-flash" else secondary

    with patch(
        "execution.personal_workflows.job_search_llm_gate._build_gemini_model",
        side_effect=_build,
    ):
        verdicts = classify_batch(jobs, max_jobs=200, batch_size=10, throttle_s=0)
    assert [v.fit_score for v in verdicts] == [81, 72]  # rescued by secondary
    assert secondary.generate_content.call_count == 1


def test_malformed_batch_response_all_parse_error():
    """Non-JSON batch response → every job in the batch falls back to parse_error."""
    jobs = [_job("A"), _job("B")]
    model = MagicMock()
    bad = MagicMock(); bad.text = "Sorry, I can't help with that."
    model.generate_content.return_value = bad
    with patch(
        "execution.personal_workflows.job_search_llm_gate._build_gemini_model",
        return_value=model,
    ):
        verdicts = classify_batch(jobs, max_jobs=200, batch_size=10, throttle_s=0)
    assert all(v.relevance == "borderline" and "parse_error" in v.reason for v in verdicts)


# ---------------------------------------------------------------------------
# _parse_verdict_array unit tests
# ---------------------------------------------------------------------------


def test_parse_array_exact():
    raw = json.dumps([_verdict(fit=80), _verdict(fit=70)])
    out = _parse_verdict_array(raw, 2)
    assert [d["fit_score"] for d in out] == [80, 70]


def test_parse_array_truncates_extra():
    raw = json.dumps([_verdict(fit=80), _verdict(fit=70), _verdict(fit=60)])
    out = _parse_verdict_array(raw, 2)
    assert len(out) == 2


def test_parse_array_salvages_prose_wrapped_json():
    raw = "Here are the results:\n[" + json.dumps(_verdict(fit=85))[0:] + "]\nDone."
    # build a clean salvageable string
    raw = "Sure!\n" + json.dumps([_verdict(fit=85)]) + "\nthanks"
    out = _parse_verdict_array(raw, 1)
    assert out[0]["fit_score"] == 85


def test_parse_array_fences_stripped():
    raw = "```json\n" + json.dumps([_verdict(fit=88)]) + "\n```"
    out = _parse_verdict_array(raw, 1)
    assert out[0]["fit_score"] == 88


# ---------------------------------------------------------------------------
# _parse_verdict_json (single object) — unchanged behaviour
# ---------------------------------------------------------------------------


def test_partial_json_missing_contract_type():
    result = _parse_verdict_json(json.dumps({"relevance": "relevant", "reason": "good"}))
    assert result["relevance"] == "relevant"
    assert result["contract_type"] is None


def test_unknown_relevance_defaults_to_borderline():
    result = _parse_verdict_json(json.dumps({"relevance": "maybe", "contract_type": "CDI", "reason": "x"}))
    assert result["relevance"] == "borderline"


def test_markdown_fences_stripped_single():
    inner = json.dumps({"relevance": "irrelevant", "contract_type": "Unknown", "reason": "mismatch"})
    result = _parse_verdict_json(f"```json\n{inner}\n```")
    assert result["relevance"] == "irrelevant"
    assert result["contract_type"] is None


def test_malformed_json_returns_parse_error_fallback():
    result = _parse_verdict_json("not json at all")
    assert result["relevance"] == "borderline"
    assert "parse_error" in result["reason"]


def test_parse_known_contract_type_preserved():
    for ct_in, ct_out in [("CDI", "CDI"), ("cdi", "CDI"), ("Freelance", "Freelance"),
                          ("PERMANENT", "Permanent"), ("contract", "Contract")]:
        result = _parse_verdict_json(json.dumps({"relevance": "relevant", "contract_type": ct_in, "reason": "ok"}))
        assert result["contract_type"] == ct_out
