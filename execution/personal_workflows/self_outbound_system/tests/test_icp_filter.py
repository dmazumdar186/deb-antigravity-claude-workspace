"""
test_icp_filter.py
description: Unit tests for icp_filter.py against the frozen 32-case corpus. Every known-bad MUST reject with the correct reason category; every known-good MUST pass. This is the regression-safe layer BENEATH the acceptance gate (which runs the same corpus end-to-end).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from icp_filter import filter_leads  # from conftest.py sys.path insertion

ROOT = Path(__file__).resolve().parent.parent
ICP_JSON = ROOT / "config" / "icp.json"
CORPUS_JSON = ROOT / "tests" / "acceptance_corpus.json"


def _load(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def icp_cfg() -> dict:
    return _load(ICP_JSON)


@pytest.fixture(scope="module")
def corpus() -> dict:
    return _load(CORPUS_JSON)


@pytest.fixture(scope="module")
def filtered(icp_cfg: dict, corpus: dict) -> tuple[list[dict], list[dict]]:
    suppression = set(corpus.get("suppressed_seed", []))
    # known_good first so the deliberate duplicate (bad-14) gets caught as
    # the "duplicate-of-good-01" case per corpus-declared expected reason.
    return filter_leads(
        corpus["known_good"] + corpus["known_bad"],
        icp_cfg,
        suppression=suppression,
    )


@pytest.mark.parametrize("bad_case", _load(CORPUS_JSON)["known_bad"], ids=lambda c: c["id"])
def test_known_bad_rejected(bad_case, filtered):
    """Every known-bad MUST land in the rejected list."""
    _kept, rejected = filtered
    rejected_ids = {r["lead"].get("id"): r["reason"] for r in rejected}
    assert bad_case["id"] in rejected_ids, (
        f"expected {bad_case['id']} rejected (reason: {bad_case['reject_reason']}), "
        f"but it was accepted"
    )


@pytest.mark.parametrize("good_case", _load(CORPUS_JSON)["known_good"], ids=lambda c: c["id"])
def test_known_good_accepted(good_case, filtered):
    """Every known-good MUST land in the kept list."""
    kept, _rejected = filtered
    kept_ids = {lead.get("id") for lead in kept}
    assert good_case["id"] in kept_ids, (
        f"expected {good_case['id']} kept (reason: {good_case['keep_reason']}), "
        f"but it was rejected"
    )


def test_no_am_domain_leaks_through(icp_cfg: dict):
    """Belt + suspenders: AM-locked domains MUST reject even if signals fire."""
    trojan = [{
        "id": "trojan-am",
        "email": "founder@accessorymasters.co",
        "name": "AM Trojan",
        "title": "Founder",
        "company": "AM Trojan",
        "domain": "accessorymasters.co",
        "notes": "Series A raised, wants to ship AI feature this quarter, has budget, urgent",
    }]
    kept, rejected = filter_leads(trojan, icp_cfg)
    assert kept == [], "AM-locked domain slipped through"
    assert rejected[0]["reason"] == "am-locked-domain"


# ---------------------------------------------------------------------------
# Regression tests for pipeline-auditor + code-reviewer P0/P1 findings
# 2026-07-08. See directives/personal_workflows/self_outbound_system.md
# changelog + acceptance corpus for context.
# ---------------------------------------------------------------------------


def test_hourly_rate_leak_with_signals_present(icp_cfg: dict):
    """Regression: an anti-ICP lead saying 'hourly-rate only' WITH real
    budget+urgency signals must reject with reason='hourly-rate-only'.
    Pipeline-auditor 2026-07-08 empirically showed this leak (hyphen vs
    space mismatch + config drift). Independent, hand-coded assertion."""
    leaky = [{
        "id": "leaky-hourly",
        "email": "boss@hourlyshop.com",
        "name": "Boss",
        "title": "Owner",
        "company": "Shop",
        "domain": "hourlyshop.com",
        "notes": "Wants ai feature this quarter urgent, has budget for it, but only pays hourly-rate, no fixed-price",
    }]
    kept, rejected = filter_leads(leaky, icp_cfg)
    assert kept == [], "hourly-rate anti-ICP lead with signals should reject"
    assert rejected[0]["reason"] == "hourly-rate-only", (
        f"expected hourly-rate-only, got {rejected[0]['reason']}"
    )


def test_intern_does_not_match_internal(icp_cfg: dict):
    """Regression: 'Internal Automation Lead' (a legit ops persona)
    should NOT be rejected by the anti-ICP 'intern' role match.
    Word-boundary regex fix applied 2026-07-08."""
    legit = [{
        "id": "legit-internal",
        "email": "lead@ops.com",
        "name": "Ops Lead",
        "title": "Internal Automation Lead",
        "company": "ScaleUp Co",
        "domain": "ops.com",
        "notes": "Roadmap gap on ai automation, has budget, wants to ship this quarter urgent, series b",
    }]
    kept, rejected = filter_leads(legit, icp_cfg)
    assert legit[0]["id"] in {lead.get("id") for lead in kept}, (
        f"'Internal Automation Lead' wrongly rejected. Rejected: {rejected}"
    )


def test_segment_tie_break_prefers_title_match(icp_cfg: dict):
    """Regression: on a signal-count tie, the segment whose vocabulary matches
    the TITLE field wins. good-06 (Head of Ops) ties at 2 signals across all
    three segments; heads_of_product_ops must win because 'head of' is in its
    budget keywords AND in the title. Pipeline-auditor 2026-07-08."""
    head_of_ops = [{
        "id": "seg-tiebreak",
        "email": "ops@fintech.com",
        "name": "Rakesh Patel",
        "title": "Head of Ops",
        "company": "FinTech Co",
        "domain": "fintech.com",
        "notes": "100+ manual hours/week on ops. Wants automation. Has budget. Urgent.",
    }]
    kept, rejected = filter_leads(head_of_ops, icp_cfg)
    assert kept, f"Head of Ops lead rejected: {rejected}"
    assert kept[0].get("segment") == "heads_of_product_ops", (
        f"Expected segment=heads_of_product_ops, got {kept[0].get('segment')}. "
        f"Signal bits: {kept[0].get('signals_bits')}"
    )


def test_icp_json_reject_if_any_keyword_actually_read(icp_cfg: dict):
    """Regression: adding a keyword to icp.json.anti_icp.reject_if_any_keyword
    MUST actually cause rejection. Prior scaffold hardcoded the list in Python;
    edits to icp.json had zero effect (config drift). Fixed 2026-07-08."""
    import copy as _copy
    cfg = _copy.deepcopy(icp_cfg)
    cfg["anti_icp"].setdefault("reject_if_any_keyword", []).append("madeup_test_marker_xyz123")

    lead = [{
        "id": "config-drift-test",
        "email": "buyer@genuinebiz.com",
        "name": "Real Buyer",
        "title": "VP Product",
        "company": "GenuineBiz",
        "domain": "genuinebiz.com",
        "notes": "Roadmap gap, series b, has budget, urgent, madeup_test_marker_xyz123 present",
    }]
    kept, rejected = filter_leads(lead, cfg)
    assert kept == [], "config-drift regression: new keyword had no effect"
    # Reason may be the generic anti-icp-keyword fallback since we didn't add
    # this to the code-side _KEYWORD_REASON_MAP.
    assert rejected[0]["reason"] in ("anti-icp-keyword",), (
        f"expected anti-icp-keyword fallback, got {rejected[0]['reason']}"
    )


def test_acceptance_corpus_bad_11_actual_reason_matches_declared(icp_cfg: dict):
    """Regression: bad-11 corpus case declares reject_reason='hourly-rate-only'.
    Pipeline-auditor 2026-07-08 caught the code rejecting via 'no-signals'
    (accidental correctness). After fix, actual reason MUST match declared."""
    bad_11 = [{
        "id": "bad-11",
        "email": "boss@shop.com",
        "name": "Boss",
        "title": "Owner",
        "company": "Shop",
        "notes": "Only interested in hourly-rate work, no fixed price.",
    }]
    kept, rejected = filter_leads(bad_11, icp_cfg)
    assert kept == [], "bad-11 must reject"
    assert rejected[0]["reason"] == "hourly-rate-only", (
        f"reason drift: expected hourly-rate-only, got {rejected[0]['reason']}"
    )
