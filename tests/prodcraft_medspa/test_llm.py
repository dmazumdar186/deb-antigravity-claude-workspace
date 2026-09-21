"""
test_llm.py
description: Tests for common/llm.py — mock fixture path, prompt sha256 stability, 4-count cost calc.
inputs: N/A (pytest).
outputs: N/A (pytest).
"""

from __future__ import annotations

import hashlib

import pytest

from execution.personal_workflows.prodcraft_medspa.common.llm import (
    PRICING,
    _cost_usd,
    call,
    render_prompt,
)


def test_render_prompt_substitutes_variables(tmp_path):
    prompt_path = tmp_path / "p.md"
    prompt_path.write_text("Hello {{name}}, your score is {{score}}.", encoding="utf-8")
    rendered = render_prompt(prompt_path, {"name": "Glow Aesthetics", "score": 42})
    assert rendered == "Hello Glow Aesthetics, your score is 42."


def test_render_prompt_missing_variable_raises(tmp_path):
    prompt_path = tmp_path / "p.md"
    prompt_path.write_text("Hello {{name}}.", encoding="utf-8")
    with pytest.raises(KeyError):
        render_prompt(prompt_path, {})


def test_call_mock_reads_fixture_and_zeroes_usage(tmp_path, fixtures_root):
    prompt_path = tmp_path / "sample_prompt.md"
    prompt_path.write_text("Score this: {{business_name}}", encoding="utf-8")

    result = call(
        "sample_prompt",
        prompt_path,
        {"business_name": "Glow Aesthetics"},
        model="claude-fable-5-1",
        mock=True,
        fixtures_root=fixtures_root,
    )

    assert "dated_score" in result["text"]
    assert result["model_id"] == "claude-fable-5-1"
    assert result["usage"] == {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
    assert result["cost_usd"] == 0.0


def test_call_mock_missing_fixture_raises_with_expected_path(tmp_path, fixtures_root):
    prompt_path = tmp_path / "p.md"
    prompt_path.write_text("no vars here", encoding="utf-8")

    with pytest.raises(FileNotFoundError) as exc_info:
        call(
            "does_not_exist",
            prompt_path,
            {},
            model="claude-sonnet-5",
            mock=True,
            fixtures_root=fixtures_root,
        )
    assert "does_not_exist.txt" in str(exc_info.value)


def test_prompt_sha256_is_stable_across_calls(tmp_path, fixtures_root):
    prompt_path = tmp_path / "sample_prompt.md"
    prompt_path.write_text("Score this: {{business_name}}", encoding="utf-8")
    variables = {"business_name": "Glow Aesthetics"}

    r1 = call("sample_prompt", prompt_path, variables, model="claude-sonnet-5", mock=True, fixtures_root=fixtures_root)
    r2 = call("sample_prompt", prompt_path, variables, model="claude-sonnet-5", mock=True, fixtures_root=fixtures_root)

    expected = hashlib.sha256(b"Score this: Glow Aesthetics").hexdigest()
    assert r1["prompt_sha256"] == expected
    assert r1["prompt_sha256"] == r2["prompt_sha256"]


def test_pricing_table_has_four_entries_per_model():
    for model, rates in PRICING.items():
        assert set(rates) == {"input", "cache_read", "cache_write", "output"}, model


def test_cost_usd_uses_all_four_token_counts():
    usage = {
        "input_tokens": 1_000_000,
        "output_tokens": 1_000_000,
        "cache_read_input_tokens": 1_000_000,
        "cache_creation_input_tokens": 1_000_000,
    }
    cost = _cost_usd("claude-sonnet-5", usage)
    expected = 2.00 + 10.00 + 0.20 + 2.50
    assert cost == pytest.approx(expected)


def test_cost_usd_fable_cache_read_rate():
    usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 1_000_000,
        "cache_creation_input_tokens": 0,
    }
    cost = _cost_usd("claude-fable-5-1", usage)
    assert cost == pytest.approx(0.25)


def test_call_mock_without_fixtures_root_raises_value_error(tmp_path):
    prompt_path = tmp_path / "p.md"
    prompt_path.write_text("hi", encoding="utf-8")
    with pytest.raises(ValueError):
        call("x", prompt_path, {}, model="claude-sonnet-5", mock=True)


def test_manual_envelope_and_override_lookup():
    from execution.personal_workflows.prodcraft_medspa.common import llm

    biz = {"llm_overrides": {"fuzzy_variables": {"a": 1}, "extract_services": ""}}
    assert llm.override_for(biz, "fuzzy_variables") == {"a": 1}
    assert llm.override_for(biz, "extract_services") is None  # empty string is not an override
    assert llm.override_for({}, "fuzzy_variables") is None
    env = llm.manual_envelope("fuzzy_variables", {"a": 1})
    assert env["model_id"] == "manual:operator" and env["manual"] is True and env["mock"] is False
    assert env["cost_usd"] == 0.0 and len(env["prompt_sha256"]) == 64
    assert env["text"] == '{"a": 1}'
