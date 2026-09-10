"""
test_enrich.py
description: Test suite for execution/personal_workflows/prodcraft_medspa/enrich/ — name-regex
  robustness, each waterfall step against its own fixtures, full-waterfall ordering/stop-at-first-hit,
  the exact by_source distribution CONTRACTS.md specifies, verification mapping, idempotency without
  --force, and do_not_contact skipping.
inputs: pytest; local_store/fixtures_root fixtures from tests/prodcraft_medspa/conftest.py.
outputs: pytest results; no files written outside tmp_path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from execution.personal_workflows.prodcraft_medspa.common import http
from execution.personal_workflows.prodcraft_medspa.common.config import Settings
from execution.personal_workflows.prodcraft_medspa.enrich import (
    apollo,
    contact_page,
    findymail,
    generic_inbox,
    gbp_reviews,
    hunter,
    names,
    state_registry,
    verify,
    waterfall,
)
from execution.personal_workflows.prodcraft_medspa.enrich.context import StepContext
from execution.personal_workflows.prodcraft_medspa.enrich.fixtures.seed_mock_store import seed

ENRICH_FIXTURES = Path(__file__).resolve().parents[2] / (
    "execution/personal_workflows/prodcraft_medspa/enrich/fixtures"
)


def make_ctx(**overrides) -> StepContext:
    defaults = dict(
        mock=True,
        fixtures_root=ENRICH_FIXTURES,
        settings=Settings(),
        session=http.session(),
    )
    defaults.update(overrides)
    return StepContext(**defaults)


# ---------------------------------------------------------------------------
# Name-regex robustness
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Book Now for your free consultation!",
        "Laser Hair removal is our most popular service.",
    ],
)
def test_name_regex_rejects_non_names(text):
    assert names.extract_name_candidates(text) == []


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Our practice is led by Dr. Maria Lopez, MD.", "Maria Lopez"),
        ("Jennifer Cho, RN has been with us since 2015.", "Jennifer Cho"),
        ("Founded by Alex Rivera in 2019, the spa has grown steadily.", "Alex Rivera"),
    ],
)
def test_name_regex_accepts_real_names(text, expected):
    assert expected in names.extract_name_candidates(text)


def test_extract_emails_splits_personal_from_generic():
    text = "Contact info@example.test or reach Jane directly at jane@example.test."
    personal, generic = names.extract_emails(text, domain="example.test")
    assert personal == ["jane@example.test"]
    assert generic == ["info@example.test"]


# ---------------------------------------------------------------------------
# Individual steps on fixtures
# ---------------------------------------------------------------------------


def test_contact_page_hit_with_name_and_email():
    business = {"place_id": "p01", "name": "Glow Aesthetics One"}
    ctx = make_ctx(domain="example-medspa-01.test")
    result = contact_page.run(business, ctx)
    assert result.hit is True
    assert result.source == "contact_page"
    assert result.email == "maria@example-medspa-01.test"
    assert result.owner_name == "Maria Lopez"


def test_contact_page_hit_email_only_no_name():
    business = {"place_id": "p02", "name": "Silver Spa Two"}
    ctx = make_ctx(domain="example-medspa-02.test")
    result = contact_page.run(business, ctx)
    assert result.hit is True
    assert result.email == "amy@example-medspa-02.test"
    assert result.owner_first == "Amy"  # derived from local-part, no name pattern matched


def test_contact_page_records_generic_candidate_without_hit():
    business = {"place_id": "p09", "name": "Value Med Spa Nine"}
    ctx = make_ctx(domain="example-medspa-09.test")
    result = contact_page.run(business, ctx)
    assert result.hit is False
    assert ctx.generic_email == "info@example-medspa-09.test"


def test_contact_page_miss_without_fixture():
    business = {"place_id": "p10", "name": "Ghost Listing Ten"}
    ctx = make_ctx(domain=None)
    result = contact_page.run(business, ctx)
    assert result.hit is False


def test_gbp_reviews_guesses_email_from_owner_mention():
    business = {"place_id": "p04", "name": "Radiant Wellness Four"}
    ctx = make_ctx(domain="example-medspa-04.test")
    result = gbp_reviews.run(business, ctx)
    assert result.hit is True
    assert result.source == "gbp_reviews"
    assert result.owner_name == "Robert Kim"
    assert result.email == "robert@example-medspa-04.test"


def test_gbp_reviews_ignores_author_attribution():
    # p_no_owner.json's only name-shaped text is the reviewer's own name in authorAttribution,
    # which gbp_reviews.py must never scan.
    business = {"place_id": "p_no_owner", "name": "Anywhere Spa"}
    ctx = make_ctx(domain="example-medspa-anywhere.test")
    result = gbp_reviews.run(business, ctx)
    assert result.hit is False
    assert ctx.owner_name is None


def test_state_registry_lookup_returns_registered_agent():
    ctx = make_ctx()
    result = state_registry.lookup("Serenity Skin Five", "IL", ctx=ctx)
    assert result["registered_agent"] == "Emily Ortiz"
    assert result["source_url"]


def test_state_registry_step_never_hits_but_sets_context():
    business = {"place_id": "p05", "name": "Serenity Skin Five", "state": "IL"}
    ctx = make_ctx(domain="example-medspa-05.test")
    result = state_registry.run(business, ctx)
    assert result.hit is False
    assert ctx.owner_name == "Emily Ortiz"
    assert ctx.owner_first == "Emily"


def test_state_registry_no_state_is_a_clean_miss():
    business = {"place_id": "p07", "name": "Pure Radiance Seven", "state": None}
    ctx = make_ctx(domain="example-medspa-07.test")
    result = state_registry.run(business, ctx)
    assert result.hit is False
    assert ctx.owner_name is None


def test_apollo_hit_from_domain_search():
    business = {"place_id": "p07", "name": "Pure Radiance Seven"}
    ctx = make_ctx(domain="example-medspa-07.test")
    result = apollo.run(business, ctx)
    assert result.hit is True
    assert result.email == "nicole@example-medspa-07.test"
    assert result.cost_usd == 0.0  # Apollo is credits, not per-call cost


def test_findymail_needs_name_and_domain():
    business = {"place_id": "p05", "name": "Serenity Skin Five"}
    ctx = make_ctx(domain="example-medspa-05.test")  # no owner_name set
    assert findymail.run(business, ctx).hit is False

    ctx.owner_name = "Emily Ortiz"
    ctx.owner_first = "Emily"
    result = findymail.run(business, ctx)
    assert result.hit is True
    assert result.email == "emily@example-medspa-05.test"
    assert result.cost_usd == pytest.approx(0.10)


def test_hunter_hit_from_fixture():
    business = {"place_id": "p11", "name": "Sam's Med Spa Eleven"}
    ctx = make_ctx(domain="example-medspa-11.test", owner_name="Sam Patel", owner_first="Sam")
    result = hunter.run(business, ctx)
    assert result.hit is True
    assert result.email == "sam@example-medspa-11.test"
    assert result.cost_usd == pytest.approx(0.10)


def test_generic_inbox_uses_generic_candidate_first():
    ctx = make_ctx(domain="example-medspa-09.test", generic_email="info@example-medspa-09.test")
    result = generic_inbox.run({}, ctx)
    assert result.hit is True
    assert result.email == "info@example-medspa-09.test"


def test_generic_inbox_falls_back_to_info_at_domain():
    ctx = make_ctx(domain="example-medspa-xx.test")
    result = generic_inbox.run({}, ctx)
    assert result.hit is True
    assert result.email == "info@example-medspa-xx.test"


def test_generic_inbox_miss_without_domain():
    ctx = make_ctx(domain=None)
    assert generic_inbox.run({}, ctx).hit is False


# ---------------------------------------------------------------------------
# Verification mapping
# ---------------------------------------------------------------------------


def test_verify_ok_maps_to_deliverable():
    status, cost = verify.verify(
        "maria@example-medspa-01.test", mock=True, fixtures_root=ENRICH_FIXTURES, api_key=None
    )
    assert status == "deliverable"
    assert cost > 0


def test_verify_catch_all_maps_to_risky_never_deliverable():
    status, _ = verify.verify(
        "info@example-medspa-09.test", mock=True, fixtures_root=ENRICH_FIXTURES, api_key=None
    )
    assert status == "risky"
    assert status != "deliverable"


def test_verify_invalid_maps_to_undeliverable():
    status, _ = verify.verify(
        "bounced@example-medspa-12.test", mock=True, fixtures_root=ENRICH_FIXTURES, api_key=None
    )
    assert status == "undeliverable"


def test_verify_unknown_email_is_unknown():
    status, _ = verify.verify(
        "nobody@nowhere.test", mock=True, fixtures_root=ENRICH_FIXTURES, api_key=None
    )
    assert status == "unknown"


def test_verify_no_email_is_unknown_and_free():
    status, cost = verify.verify(None, mock=True, fixtures_root=ENRICH_FIXTURES, api_key=None)
    assert status == "unknown"
    assert cost == 0.0


# ---------------------------------------------------------------------------
# Full waterfall — ordering, stop-at-first-hit, source distribution, gates
# ---------------------------------------------------------------------------


def test_waterfall_stat_line_matches_designed_distribution(local_store):
    seed(local_store)
    settings = Settings()

    stats = waterfall.run(
        metro="chicago-north-shore",
        business_id=None,
        min_score=45,
        mock=True,
        store=local_store,
        limit=None,
        force=False,
        fixtures_root=ENRICH_FIXTURES,
        settings=settings,
    )

    assert stats["script"] == "waterfall"
    assert stats["in"] == 10  # do_not_contact + already-deliverable rows are excluded up front
    assert stats["email_found"] == 9
    assert stats["unresolved"] == 1
    assert stats["verified_deliverable"] == 8
    assert stats["by_source"] == {
        "contact_page": 3,
        "gbp_reviews": 1,
        "state_registry": 0,
        "apollo": 2,
        "findymail": 2,
        "hunter": 0,
        "generic_inbox": 1,
    }
    assert stats["cost_usd"] > 0


def test_waterfall_stops_at_first_hit_contact_page_wins(local_store):
    seed(local_store)
    settings = Settings()
    business = local_store.find_businesses(metro="chicago-north-shore")
    b01 = next(b for b in business if b["place_id"] == "p01")

    patch, hit_source, _cost = waterfall.run_waterfall_for_business(
        b01,
        ctx_template={
            "mock": True,
            "fixtures_root": ENRICH_FIXTURES,
            "settings": settings,
            "session": http.session(),
        },
        store=local_store,
    )
    assert hit_source == "contact_page"
    assert patch["email_source"] == "contact_page"
    assert patch["owner_email"] == "maria@example-medspa-01.test"

    events = [e for e in local_store._read("events") if e["entity_id"] == b01["id"]]  # noqa: SLF001
    step_events = [e["event"] for e in events]
    # contact_page hit first — no later step should have been attempted.
    assert "enrich:step:contact_page:hit" in step_events
    assert not any(e.startswith("enrich:step:gbp_reviews") for e in step_events)
    assert not any(e.startswith("enrich:step:apollo") for e in step_events)


def test_waterfall_skips_do_not_contact(local_store):
    seed(local_store)
    candidates = waterfall.eligible_businesses(
        local_store, metro="chicago-north-shore", business_id=None, min_score=45, force=False
    )
    assert all(not c.get("do_not_contact") for c in candidates)
    assert not any(c["place_id"] == "p_dnc" for c in candidates)


def test_waterfall_idempotent_without_force(local_store):
    seed(local_store)
    candidates = waterfall.eligible_businesses(
        local_store, metro="chicago-north-shore", business_id=None, min_score=45, force=False
    )
    assert not any(c["place_id"] == "p_already_done" for c in candidates)


def test_waterfall_force_reprocesses_deliverable(local_store):
    seed(local_store)
    candidates = waterfall.eligible_businesses(
        local_store, metro="chicago-north-shore", business_id=None, min_score=45, force=True
    )
    assert any(c["place_id"] == "p_already_done" for c in candidates)


def test_waterfall_respects_min_score(local_store):
    seed(local_store)
    candidates = waterfall.eligible_businesses(
        local_store, metro="chicago-north-shore", business_id=None, min_score=200, force=False
    )
    assert candidates == []


def test_waterfall_second_run_finds_nothing_new(local_store):
    seed(local_store)
    settings = Settings()
    first = waterfall.run(
        metro="chicago-north-shore",
        business_id=None,
        min_score=45,
        mock=True,
        store=local_store,
        limit=None,
        force=False,
        fixtures_root=ENRICH_FIXTURES,
        settings=settings,
    )
    assert first["in"] == 10

    second = waterfall.run(
        metro="chicago-north-shore",
        business_id=None,
        min_score=45,
        mock=True,
        store=local_store,
        limit=None,
        force=False,
        fixtures_root=ENRICH_FIXTURES,
        settings=settings,
    )
    # Only a *deliverable* email removes a business from the queue (per CLI contract: "without a
    # deliverable email unless --force"). p09 (risky, generic_inbox) and p10 (no domain, unresolved)
    # remain eligible and re-resolve identically on the second pass.
    assert second["in"] == 2
    assert second["email_found"] == 1
    assert second["unresolved"] == 1
    assert second["by_source"]["generic_inbox"] == 1
