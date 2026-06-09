"""
Unit tests for filter_titles() in job_search_sheet.py.

Guards against silent zero-result runs when --title is passed but doesn't
match any key/tab/synonym.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution.personal_workflows.job_search_sheet import filter_titles  # noqa: E402


@pytest.fixture
def titles_cfg():
    return {
        "PM": {
            "tab": "PM",
            "synonyms": ["product manager", "senior product manager", "lead product manager"],
        },
        "AI PM": {
            "tab": "AI PM",
            "synonyms": ["ai product manager", "ml product manager"],
        },
        "AI Consultant": {
            "tab": "AI Consultant",
            "synonyms": ["ai consultant", "ai strategy consultant"],
        },
    }


def test_no_filter_returns_all(titles_cfg):
    """Empty title_arg returns the full dict (a copy)."""
    out = filter_titles(titles_cfg, None)
    assert out == titles_cfg
    assert out is not titles_cfg  # must be a copy, not the same ref

    out2 = filter_titles(titles_cfg, "")
    assert out2 == titles_cfg


def test_match_by_key_case_insensitive(titles_cfg):
    out = filter_titles(titles_cfg, "pm")
    assert set(out.keys()) == {"PM"}

    out2 = filter_titles(titles_cfg, "AI PM")
    assert set(out2.keys()) == {"AI PM"}


def test_match_by_tab_name(titles_cfg):
    out = filter_titles(titles_cfg, "AI Consultant")
    assert set(out.keys()) == {"AI Consultant"}


def test_match_by_synonym(titles_cfg):
    """The original bug: --title 'Product Manager' must match PM bucket via synonyms."""
    out = filter_titles(titles_cfg, "Product Manager")
    assert set(out.keys()) == {"PM"}, f"Expected PM via synonym, got {list(out.keys())}"

    out2 = filter_titles(titles_cfg, "ml product manager")
    assert set(out2.keys()) == {"AI PM"}


def test_no_match_returns_empty_dict(titles_cfg):
    """Bad input: empty dict — caller must handle as error, NOT proceed silently."""
    out = filter_titles(titles_cfg, "Frontend Engineer")
    assert out == {}, "Non-matching --title must return empty dict so caller can error out"


def test_synonym_match_is_exact_not_substring(titles_cfg):
    """Substring matches should NOT trip the filter (avoid 'manager' matching multiple)."""
    out = filter_titles(titles_cfg, "manager")
    # 'manager' is not exactly any key, tab, or synonym
    assert out == {}, "Substring should not match — only exact key/tab/synonym"
