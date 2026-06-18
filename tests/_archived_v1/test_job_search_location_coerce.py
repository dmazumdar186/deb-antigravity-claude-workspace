"""Regression tests for the dict-location coercion fixes.

The job_search_sheet synthetic surfaced a real bug 2026-06-15: the france_travail
scraper returned location as a dict ({"libelle": "Paris (75)"}) while every other
board returned a plain string. compute_job_hash and _build_sheet_row both
crashed on AttributeError: 'dict' object has no attribute 'strip' / 'lower'.

These tests pin the defensive coercion so the schema cross-board never breaks
the pipeline again.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from execution.personal_workflows._jt_utils import compute_job_hash  # noqa: E402


# ----------------------------------------------------------------------------
# compute_job_hash dict-location coercion
# ----------------------------------------------------------------------------

def test_hash_with_string_location():
    h = compute_job_hash("acme", "pm", "Paris")
    assert isinstance(h, str) and len(h) == 40  # SHA-1 hex


def test_hash_with_none_location():
    h = compute_job_hash("acme", "pm", None)
    assert isinstance(h, str)


def test_hash_with_libelle_dict_location():
    """France Travail shape: {'libelle': 'Paris (75)'}."""
    h_dict = compute_job_hash("acme", "pm", {"libelle": "Paris (75)"})
    h_str = compute_job_hash("acme", "pm", "Paris (75)")
    assert h_dict == h_str, "dict-with-libelle must hash the same as the equivalent string"


def test_hash_with_name_dict_location():
    """Alternative shape some boards use: {'name': 'Paris'}."""
    h_dict = compute_job_hash("acme", "pm", {"name": "Paris"})
    h_str = compute_job_hash("acme", "pm", "Paris")
    assert h_dict == h_str


def test_hash_with_empty_dict_location():
    h_dict = compute_job_hash("acme", "pm", {})
    h_str = compute_job_hash("acme", "pm", "")
    assert h_dict == h_str


def test_hash_with_dict_missing_known_keys():
    """A dict with no libelle/name/display falls through to empty string."""
    h_dict = compute_job_hash("acme", "pm", {"unknown_key": "Paris"})
    h_str = compute_job_hash("acme", "pm", "")
    assert h_dict == h_str


def test_hash_with_numeric_location_coerced():
    """Pathological: a number where a string is expected — coerce, don't crash."""
    h = compute_job_hash("acme", "pm", 12345)
    assert isinstance(h, str)


def test_hash_collisions_match_case_insensitively():
    """Sanity: case-insensitive lowering applied to the location segment."""
    a = compute_job_hash("acme", "pm", "Paris")
    b = compute_job_hash("acme", "pm", "PARIS")
    assert a == b
