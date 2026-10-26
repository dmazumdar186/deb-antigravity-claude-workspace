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
    fit_out_of_5,
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


# ----- Fit /5 (2026-10-26) -----


@pytest.mark.parametrize("final_score, expected", [
    (0.0, 1),      # floor: a scored job never shows 0
    (0.1, 1),      # round(0.5) == 0 under banker's rounding -> clamped to 1
    (0.49, 2),     # round(2.45) == 2
    (0.5, 2),      # round(2.5) == 2 (banker's rounding) — asserted, not assumed
    (0.7, 4),      # round(3.5) == 4
    (0.75, 4),     # tier-A threshold -> 4
    (0.95, 5),
    (1.0, 5),
    (None, None),  # never scored (placeholder)
])
def test_fit_out_of_5(final_score, expected):
    assert fit_out_of_5(final_score) == expected


def test_fit_out_of_5_rejects_garbage_as_none():
    assert fit_out_of_5("n/a") is None  # type: ignore[arg-type]


def test_ranked_job_carries_fit5_and_placeholder_is_blank():
    from execution.personal_workflows.job_search_v2.contracts import RankedJob
    from execution.personal_workflows.job_search_v2.ranker.score import _placeholder_ranked

    class _J:  # minimal stand-in: _placeholder_ranked only reads content_hash
        content_hash = "a" * 64

    assert _placeholder_ranked(_J(), "disabled").fit5 is None
    rj = RankedJob(content_hash="b" * 64, score=0.82, tier=JobTier.A, reasoning="x",
                   rubric_version="v", ranker_model="m", fit5=fit_out_of_5(0.82))
    assert rj.fit5 == 4


def test_sheet_headers_end_with_fit5_and_top_matches_has_it():
    from execution.personal_workflows.job_search_v2.notifier import sheet as sheet_mod
    assert sheet_mod.STANDARD_HEADERS[-1] == "Fit /5"
    assert sheet_mod.STANDARD_HEADERS[-3:-1] == ["Posted", "Verified"]
    assert "Fit /5" in sheet_mod.TOP_MATCHES_HEADERS
    assert sheet_mod.TOP_MATCHES_HEADERS.index("Fit /5") == sheet_mod.TOP_MATCHES_HEADERS.index("Fit") + 1


# ----- secondary identity sources (GitHub + prodcraft.fyi) -----


def test_profile_json_has_secondary_sources():
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    gh = profile.get("github") or {}
    fs = profile.get("freelance_site") or {}
    assert gh.get("login") == "dmazumdar186" and gh.get("repos"), "github section missing/empty"
    assert fs.get("url", "").startswith("https://prodcraft.fyi") and fs.get("skills_keywords"), \
        "freelance_site section missing/empty"


def test_prompt_render_includes_secondary_evidence_and_stays_bounded():
    from execution.personal_workflows.job_search_v2.ranker.score import (
        _SECONDARY_SECTION_MAX_CHARS, _render_profile_for_prompt,
    )
    profile = {
        "schema_version": "1.0", "skills": [{"name": "RAG", "level": "expert",
                                             "evidence": ["CV"], "tracks": ["A"]}],
        "github": {"login": "x", "repos": [{"name": "r" + str(i), "description": "d" * 500}
                                           for i in range(40)],
                   "languages": ["Python"], "topics": ["rag"], "commits_last_12_months": 3},
        "freelance_site": {"url": "https://prodcraft.fyi", "tagline": "t",
                           "service_lines": ["Custom AI operations"],
                           "skills_keywords": ["RAG", "n8n"]},
    }
    text = _render_profile_for_prompt(profile)
    assert "<GITHUB_EVIDENCE" in text and "<FREELANCE_SITE_EVIDENCE" in text
    assert "Custom AI operations" in text
    gh_block = text.split("<GITHUB_EVIDENCE")[1].split("</GITHUB_EVIDENCE>")[0]
    assert len(gh_block) < _SECONDARY_SECTION_MAX_CHARS + 200
    # core profile keys are verbatim, the raw secondary dicts are not duplicated
    assert text.count('"github"') == 0


def test_heuristic_counts_secondary_keywords_with_word_boundaries():
    from execution.personal_workflows.job_search_v2.ranker.score import _secondary_skill_keywords
    profile = {"github": {"languages": ["Python"], "topics": ["cold-email"]},
               "freelance_site": {"skills_keywords": ["API", "Python"]}}
    kws = _secondary_skill_keywords(profile)
    assert kws == ["Python", "cold email", "API"]


def test_append_dicts_migrates_short_header_and_writes_fit5():
    """A live tab whose header predates "Fit /5" (8 columns) must gain the
    header at the next free column and get fit5 written there; existing data
    cells are untouched."""
    from execution.personal_workflows.job_search_v2.notifier import sheet as sheet_mod

    class _Ws:
        title = "PM"
        row_count, col_count = 1000, 8

        def __init__(self, header, rows):
            self.grid = [list(header)] + [list(r) for r in rows]

        def row_values(self, n):
            return list(self.grid[n - 1]) if len(self.grid) >= n else []

        def col_values(self, idx):
            return [r[idx - 1] if len(r) >= idx else "" for r in self.grid]

        def get_all_values(self):
            return [list(r) for r in self.grid]

        def resize(self, *, rows, cols):
            self.col_count = cols

        def update(self, *, range_name, values, value_input_option="USER_ENTERED"):
            a1 = range_name.split(":")[0]
            row0 = int("".join(c for c in a1 if c.isdigit())) - 1
            col0 = 0
            for ch in "".join(c for c in a1 if c.isalpha()):
                col0 = col0 * 26 + ord(ch) - 64
            col0 -= 1
            for i, vals in enumerate(values):
                while len(self.grid) <= row0 + i:
                    self.grid.append([])
                row = self.grid[row0 + i]
                row += [""] * (col0 + len(vals) - len(row))
                for j, v in enumerate(vals):
                    row[col0 + j] = v

        def append_rows(self, rows, value_input_option="USER_ENTERED"):
            self.grid += [list(r) for r in rows]

    old_header = sheet_mod.STANDARD_HEADERS[:-1]
    existing = ["Acme", "PM", "FR", "Paris", "cdi", "https://a", "2026-10-01", "open"]
    ws = _Ws(old_header, [existing])
    header_map = sheet_mod._ensure_headers(ws, sheet_mod.STANDARD_HEADERS)
    assert ws.grid[0] == sheet_mod.STANDARD_HEADERS
    assert header_map["Fit /5"] == len(sheet_mod.STANDARD_HEADERS)
    assert ws.grid[1] == existing  # data row untouched
    written = sheet_mod._append_dicts(ws, [{
        "_id": "x", "Company": "Beta", "Title": "Senior PM", "Country": "FR",
        "Location": "Paris", "Contract": "cdi", "Link": "https://b",
        "Posted": "2026-10-20", "Verified": "open", "Fit /5": "4",
    }])
    assert written == 1
    assert ws.grid[-1][header_map["Fit /5"] - 1] == "4"
