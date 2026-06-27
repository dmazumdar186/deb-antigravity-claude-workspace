"""
description: Unit tests for the profile-grounded ranker (v3, 2026-06-27).
    Covers:
      - _compute_final_score weighting math
      - hard-zero penalty (title / contract / location = 0 -> final = 0)
      - _tier_from_final thresholds (A>=0.75, B>=0.5, C>=0.25, else SKIP)
      - _format_reasoning shape (dims + matched skills + missing critical)
      - profile.json schema invariants (the artifact the ranker reads)
inputs: pytest discovery
outputs: pytest assertions
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from execution.personal_workflows.job_search_v2.contracts import JobTier  # noqa: E402
from execution.personal_workflows.job_search_v2.ranker.score import (  # noqa: E402
    DIMENSION_WEIGHTS,
    PROFILE_PATH,
    TIER_THRESHOLDS,
    _compute_final_score,
    _format_reasoning,
    _tier_from_final,
)


def test_dimension_weights_sum_to_one():
    assert abs(sum(DIMENSION_WEIGHTS.values()) - 1.0) < 1e-9


def test_perfect_score_is_one():
    dims = {k: 1.0 for k in DIMENSION_WEIGHTS}
    assert _compute_final_score(dims) == 1.0


def test_all_zero_is_zero():
    dims = {k: 0.0 for k in DIMENSION_WEIGHTS}
    assert _compute_final_score(dims) == 0.0


@pytest.mark.parametrize("hard_zero_dim", ["title_fit", "contract_fit", "location_fit"])
def test_hard_zero_penalty(hard_zero_dim):
    """Any single hard-zero dim drops final to 0 even with everything else perfect.
    This is the 'wrong contract' / 'wrong country' / 'wrong role family' guard
    that prevents skill-overlap from masking a fatal mismatch."""
    dims = {k: 1.0 for k in DIMENSION_WEIGHTS}
    dims[hard_zero_dim] = 0.0
    assert _compute_final_score(dims) == 0.0


def test_soft_dim_zero_does_not_trigger_penalty():
    """skill_overlap and seniority_fit are NOT in the hard-zero set. Zero on
    them produces a low but non-zero final score."""
    dims = {k: 1.0 for k in DIMENSION_WEIGHTS}
    dims["skill_overlap"] = 0.0
    score = _compute_final_score(dims)
    assert score > 0.0
    assert score < 1.0


def test_tier_thresholds():
    assert _tier_from_final(1.0) is JobTier.A
    assert _tier_from_final(0.75) is JobTier.A
    assert _tier_from_final(0.7499) is JobTier.B
    assert _tier_from_final(0.5) is JobTier.B
    assert _tier_from_final(0.4999) is JobTier.C
    assert _tier_from_final(0.25) is JobTier.C
    assert _tier_from_final(0.2499) is JobTier.SKIP
    assert _tier_from_final(0.0) is JobTier.SKIP


def test_tier_thresholds_constant_stays_in_sync():
    """If someone reorders TIER_THRESHOLDS, the tier_from_final break-tie picks
    the first match. This guards against silently routing A jobs to B by
    swapping the order."""
    assert TIER_THRESHOLDS[0][0] == "A"
    assert TIER_THRESHOLDS[0][1] > TIER_THRESHOLDS[1][1] > TIER_THRESHOLDS[2][1]


def test_reasoning_includes_all_five_dim_keys():
    dims = {"title_fit": 0.9, "skill_overlap": 0.8, "contract_fit": 1.0,
            "seniority_fit": 0.7, "location_fit": 0.6}
    out = _format_reasoning("A", dims, ["Python", "LLM"], [],
                            "Strong PM fit with AI focus.")
    # Track tag + each dim short name + matched skills + reasoning text
    assert "[track A]" in out
    for short in ("title=", "skill=", "contract=", "seniority=", "location="):
        assert short in out
    assert "Python" in out and "LLM" in out
    assert "Strong PM fit" in out


def test_reasoning_caps_at_800_chars():
    """RankedJob.reasoning has max_length=800. The formatter must respect it
    even when matched + reasoning text are long."""
    dims = {k: 0.5 for k in DIMENSION_WEIGHTS}
    long_reason = "x" * 1000
    long_matched = [f"skill_{i}" for i in range(50)]
    out = _format_reasoning("B", dims, long_matched, [], long_reason)
    assert len(out) <= 800


def test_reasoning_handles_empty_matched_and_missing():
    """Empty matched_skills and missing_critical should render 'none', not
    raise on join-of-empty."""
    dims = {k: 0.5 for k in DIMENSION_WEIGHTS}
    out = _format_reasoning("A", dims, [], [], "weak fit")
    assert "matched: none" in out
    assert "missing: none" in out


# ----- profile.json schema invariants (the artifact, not the code) -----


def test_profile_json_exists():
    assert PROFILE_PATH.exists(), (
        f"profile.json missing at {PROFILE_PATH} — regenerate via "
        "py execution/personal_workflows/job_search_v2/profile/extract_profile.py"
    )


def test_profile_json_has_required_top_level_fields():
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    required = {"schema_version", "generated_at", "tracks", "skills",
                "domains", "languages", "locations", "hard_filters",
                "proof_points", "raw_source_paths"}
    assert required.issubset(set(profile.keys())), (
        f"missing keys: {required - set(profile.keys())}"
    )


def test_profile_json_has_both_tracks():
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    track_ids = {t["id"] for t in profile["tracks"]}
    assert track_ids == {"A", "B"}, f"expected A and B tracks, got {track_ids}"


def test_profile_json_skills_have_evidence():
    """Every skill must cite at least one source (CV / LinkedIn / project).
    This is the anchoring rule: no hallucinated capabilities."""
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    skills_no_evidence = [
        s["name"] for s in profile["skills"] if not s.get("evidence")
    ]
    assert not skills_no_evidence, (
        f"skills without evidence (likely hallucinated): {skills_no_evidence}"
    )


def test_profile_json_skill_levels_are_valid():
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    valid = {"expert", "strong", "familiar"}
    bad = [s for s in profile["skills"] if s["level"] not in valid]
    assert not bad, f"invalid skill levels: {[(s['name'], s['level']) for s in bad]}"


def test_profile_json_locations_block_us_and_apac():
    """Hard requirement per the operator's brand: no US, no APAC. If this
    test fails it means the extractor weakened the filter — check
    extract_profile.py prompt."""
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    blocked = {b.lower() for b in profile["locations"]["blocked_countries"]}
    assert any("united states" in b or "us" == b for b in blocked), \
        f"US not in blocked_countries: {blocked}"
    assert any("apac" in b or "asia" in b for b in blocked), \
        f"APAC not in blocked_countries: {blocked}"


def test_profile_json_has_en_and_fr_c2():
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    langs = {lang["code"].lower(): lang["level"] for lang in profile["languages"]}
    assert langs.get("en") == "C2", f"EN level: {langs.get('en')}"
    assert langs.get("fr") == "C2", f"FR level: {langs.get('fr')}"
