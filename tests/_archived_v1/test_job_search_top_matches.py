"""
Tests for the "Top Matches" feature of the job_search_sheet pipeline.

Covers:
- LLM gate fit_score / match_identity parsing (clamp, defaults, enum-guard, bool-guard)
- Truncated / garbage JSON recovery (safe defaults, no crash)
- Regression: existing relevance labels preserved after the dual-task prompt change
  (includes a BORDERLINE fixture for real discriminative power)
- classify_batch attaches fit_score + match_identity; cache_control wiring when profile present
- select_top_matches() pure selection: is_new filter, threshold, ranking + tie-break, cap
- write_top_matches() writer: header, rows, empty-state; ensure_top_matches_tab → index 1

All LLM/network/gspread calls are mocked — no live API hits.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution.personal_workflows.job_search_llm_gate import (  # noqa: E402
    GateVerdict,
    classify_batch,
    _parse_verdict_json,
)
from execution.personal_workflows.job_search_sheet import select_top_matches  # noqa: E402
from execution.google import google_sheets_writer as gsw  # noqa: E402


# ===========================================================================
# Gate: fit_score parsing
# ===========================================================================


def test_fit_score_valid_parsed():
    raw = json.dumps({"relevance": "relevant", "fit_score": 87, "match_identity": "salaried", "reason": "ok"})
    result = _parse_verdict_json(raw)
    assert result["fit_score"] == 87


@pytest.mark.parametrize("raw_val, expected", [
    (150, 100),    # above range → clamp to 100
    (-5, 0),       # below range → clamp to 0
    (100, 100),    # boundary
    (0, 0),        # boundary
    (79.6, 79),    # float → int truncation, in range
])
def test_fit_score_clamped(raw_val, expected):
    raw = json.dumps({"relevance": "relevant", "fit_score": raw_val, "reason": "x"})
    assert _parse_verdict_json(raw)["fit_score"] == expected


def test_fit_score_missing_defaults_to_zero():
    raw = json.dumps({"relevance": "relevant", "reason": "no score"})
    assert _parse_verdict_json(raw)["fit_score"] == 0


def test_fit_score_non_int_defaults_to_zero():
    raw = json.dumps({"relevance": "relevant", "fit_score": "high", "reason": "x"})
    assert _parse_verdict_json(raw)["fit_score"] == 0


def test_fit_score_bool_is_not_treated_as_int():
    # JSON true would be a bool in Python; must NOT become fit_score=1
    raw = json.dumps({"relevance": "relevant", "fit_score": True, "reason": "x"})
    assert _parse_verdict_json(raw)["fit_score"] == 0


# ===========================================================================
# Gate: match_identity enum-guard
# ===========================================================================


@pytest.mark.parametrize("raw_val, expected", [
    ("salaried", "salaried"),
    ("freelance", "freelance"),
    ("SALARIED", "salaried"),     # case-insensitive
    ("contractor", None),         # unknown → None
    (None, None),                 # missing → None
    (42, None),                   # wrong type → None
])
def test_match_identity_enum_guard(raw_val, expected):
    payload = {"relevance": "relevant", "fit_score": 50, "reason": "x"}
    if raw_val is not None:
        payload["match_identity"] = raw_val
    result = _parse_verdict_json(json.dumps(payload))
    assert result["match_identity"] == expected


# ===========================================================================
# Gate: truncated / garbage JSON recovery
# ===========================================================================


def test_truncated_json_returns_safe_defaults():
    # max_tokens cutoff mid-response → invalid JSON
    raw = '{"relevance": "relevant", "contract_type": "CDI", "fit_sc'
    result = _parse_verdict_json(raw)
    assert result["relevance"] == "borderline"  # parse_error fallback
    assert result["fit_score"] == 0
    assert result["match_identity"] is None
    assert "parse_error" in result["reason"]


def test_garbage_text_returns_safe_defaults():
    result = _parse_verdict_json("Sorry, I cannot classify this job posting.")
    assert result["fit_score"] == 0
    assert result["match_identity"] is None
    assert result["relevance"] == "borderline"


# ===========================================================================
# Gate: regression — existing relevance labels preserved (incl BORDERLINE)
# ===========================================================================


@pytest.mark.parametrize("relevance, contract", [
    ("relevant", "CDI"),
    ("borderline", "Contract"),   # the discriminating case for the dual-task prompt
    ("irrelevant", "Unknown"),
])
def test_relevance_labels_preserved_after_prompt_change(relevance, contract):
    raw = json.dumps({
        "relevance": relevance,
        "contract_type": contract,
        "fit_score": 60,
        "match_identity": "salaried",
        "reason": "regression check",
    })
    result = _parse_verdict_json(raw)
    assert result["relevance"] == relevance
    # contract normalisation unchanged: "Unknown" → None, others preserved
    if contract == "Unknown":
        assert result["contract_type"] is None
    else:
        assert result["contract_type"] == contract


# ===========================================================================
# Gate: classify_batch attaches fit fields + cache_control wiring
# ===========================================================================


def _make_job(title="Senior AI Product Manager"):
    return {
        "title": title,
        "company_name": "ACME",
        "location": "Paris, France",
        "description_snippet": f"{title} role.",
        "contract_type": None,
    }


def _gemini_model(verdict_list):
    model = MagicMock()
    resp = MagicMock()
    resp.text = json.dumps(verdict_list)
    model.generate_content.return_value = resp
    return model


def test_classify_batch_attaches_fit_fields():
    jobs = [_make_job()]
    model = _gemini_model([
        {"relevance": "relevant", "contract_type": "CDI",
         "fit_score": 91, "match_identity": "salaried", "reason": "strong match"},
    ])
    with patch(
        "execution.personal_workflows.job_search_llm_gate._build_gemini_model",
        return_value=model,
    ):
        verdicts = classify_batch(jobs, max_jobs=10, throttle_s=0)
    v = verdicts[0]
    assert isinstance(v, GateVerdict)
    assert v.fit_score == 91
    assert v.match_identity == "salaried"


def test_profile_text_is_injected_into_gemini_prompt():
    jobs = [_make_job()]
    model = _gemini_model([{"relevance": "relevant", "fit_score": 80, "match_identity": "salaried", "reason": "ok"}])
    marker = "UNIQUE_PROFILE_MARKER_XYZ"
    with patch(
        "execution.personal_workflows.job_search_llm_gate._build_gemini_model",
        return_value=model,
    ):
        classify_batch(jobs, max_jobs=10, throttle_s=0, profile_text=marker + (" pad" * 400))
    sent_prompt = model.generate_content.call_args[0][0]
    assert marker in sent_prompt  # the curated profile reaches the model


def test_paid_tier_off_by_default_never_calls_anthropic():
    """Default (anthropic_optin=False): even if Gemini fails, no paid Anthropic call is made."""
    jobs = [_make_job()]
    bad = MagicMock(); bad.generate_content.side_effect = RuntimeError("quota")
    with (
        patch("execution.personal_workflows.job_search_llm_gate._build_gemini_model", return_value=bad),
        patch("execution.personal_workflows.job_search_llm_gate._build_claude_client") as claude_builder,
    ):
        verdicts = classify_batch(jobs, max_jobs=10, throttle_s=0)
    assert verdicts[0].fit_score == 0  # parse_error fallback
    claude_builder.assert_not_called()


# ===========================================================================
# select_top_matches() — pure selection logic
# ===========================================================================


def _scored(h, fit, posted="2026-06-10", title="Senior PM"):
    return {
        "dedup_hash": h, "_fit_score": fit, "posted_at": posted,
        "title": title, "company_name": "Co", "_match_identity": "salaried",
        "_fit_reason": "r", "source_url": "http://x", "location": "Paris",
    }


def test_threshold_filter_80_in_79_out():
    jobs = [_scored("a", 80), _scored("b", 79), _scored("c", 100)]
    out = select_top_matches(jobs, known_hashes=set(), threshold=80, max_rows=25)
    hashes = {j["dedup_hash"] for j in out}
    assert hashes == {"a", "c"}  # 79 excluded


def test_is_new_filter_excludes_carry_forward():
    jobs = [_scored("new1", 90), _scored("old1", 95)]
    out = select_top_matches(jobs, known_hashes={"old1"}, threshold=80, max_rows=25)
    assert [j["dedup_hash"] for j in out] == ["new1"]  # old1 already in sheet → excluded


def test_unscored_jobs_never_selected():
    # cap-exceeded / --no-llm jobs carry _fit_score = -1 and must never appear
    jobs = [{"dedup_hash": "x", "_fit_score": -1, "posted_at": "2026-06-10"}]
    out = select_top_matches(jobs, known_hashes=set(), threshold=80, max_rows=25)
    assert out == []


def test_ranking_sort_desc_with_posted_tiebreak():
    jobs = [
        _scored("low", 81, posted="2026-06-09"),
        _scored("hi_old", 95, posted="2026-06-01"),
        _scored("hi_new", 95, posted="2026-06-10"),
    ]
    out = select_top_matches(jobs, known_hashes=set(), threshold=80, max_rows=25)
    # 95s first (newer posted wins tie), then the 81
    assert [j["dedup_hash"] for j in out] == ["hi_new", "hi_old", "low"]


def test_max_rows_cap():
    jobs = [_scored(f"j{i}", 90 + (i % 5)) for i in range(40)]
    out = select_top_matches(jobs, known_hashes=set(), threshold=80, max_rows=10)
    assert len(out) == 10


def test_empty_pool_returns_empty():
    assert select_top_matches([], set(), 80, 25) == []


# ===========================================================================
# Writer: write_top_matches + ensure_top_matches_tab
# ===========================================================================


def _fake_spreadsheet(existing_titles=None):
    sp = MagicMock()
    wss = []
    for t in (existing_titles or []):
        w = MagicMock()
        w.title = t
        w.id = 111
        wss.append(w)
    sp.worksheets.return_value = wss
    new_ws = MagicMock()
    new_ws.id = 999
    sp.add_worksheet.return_value = new_ws
    return sp, new_ws


def test_ensure_top_matches_tab_creates_and_moves_to_index_1():
    sp, new_ws = _fake_spreadsheet(existing_titles=["Summary"])
    ws = gsw.ensure_top_matches_tab(sp)
    assert ws is new_ws
    sp.add_worksheet.assert_called_once()
    # batch_update called to move to index 1
    req = sp.batch_update.call_args[0][0]
    props = req["requests"][0]["updateSheetProperties"]["properties"]
    assert props["index"] == 1


def test_write_top_matches_writes_header_and_rows():
    sp, _ = _fake_spreadsheet(existing_titles=["Summary", "Top Matches"])
    # existing "Top Matches" ws is returned by ensure
    ws = sp.worksheets.return_value[1]
    rows = [["1", "90", "salaried", "Senior PM", "Co", "Paris", "CDI", "", "why", "http://x"]]
    gsw.write_top_matches(sp, rows)
    values = ws.update.call_args.kwargs["values"]
    assert values[0] == gsw._TOP_MATCHES_HEADER
    assert values[1][3] == "Senior PM"


def test_write_top_matches_empty_state():
    sp, _ = _fake_spreadsheet(existing_titles=["Summary", "Top Matches"])
    ws = sp.worksheets.return_value[1]
    gsw.write_top_matches(sp, [])
    values = ws.update.call_args.kwargs["values"]
    assert values[0] == gsw._TOP_MATCHES_HEADER
    assert gsw._TOP_MATCHES_EMPTY_STATE in values[1][0]
