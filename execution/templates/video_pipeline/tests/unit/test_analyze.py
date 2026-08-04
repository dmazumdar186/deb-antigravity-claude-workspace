"""
Unit tests for analyze.py — pure-function tests for scene planning + cost math.
No network. Runs in CI on every push.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE))

import analyze  # noqa: E402


def test_cache_key_stable():
    a = analyze._cache_key("https://youtu.be/abc", "gemini-direct", "default", 24)
    b = analyze._cache_key("https://youtu.be/abc", "gemini-direct", "default", 24)
    assert a == b
    assert len(a) == 16


def test_cache_key_differs_by_provider():
    a = analyze._cache_key("s", "gemini-direct", "default", 24)
    b = analyze._cache_key("s", "anthropic", "default", 24)
    assert a != b


def test_estimate_cost_eur_gemini_free():
    # Gemini free tier -> €0
    assert analyze._estimate_cost_eur("gemini-direct", 24) == 0.0


def test_estimate_cost_eur_scales_with_frames():
    a = analyze._estimate_cost_eur("anthropic", 10)
    b = analyze._estimate_cost_eur("anthropic", 20)
    assert b > a
    assert 0 < a < b


def test_plan_analysis_shape(tmp_path):
    cfg = {
        "aspect_ratio": "9:16",
        "duration_seconds": 30,
    }
    plan = analyze._plan_analysis("https://youtu.be/abc", cfg, "gemini-direct", "default", 24)
    assert plan["would_extract_frames"] == 24
    assert plan["would_build_grids"] == 24 // 9
    assert plan["cost_eur_estimate"] == 0.0
    assert plan["aspect_ratio"] == "9:16"


def test_validate_source_rejects_missing_local(tmp_path):
    with pytest.raises(FileNotFoundError):
        analyze._validate_source(str(tmp_path / "does_not_exist.mp4"))


def test_validate_source_accepts_url():
    out = analyze._validate_source("https://youtu.be/abc")
    assert out.startswith("https://")


def test_load_config_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        analyze._load_config(tmp_path / "nope.json")
