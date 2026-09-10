"""
seed_mock_store.py
description: Seeds a LocalStore with 10 "qualified" businesses (+2 helper rows used only by isolated
  step tests, not by the waterfall run) whose fixtures are wired to resolve at the exact distribution
  CONTRACTS.md specifies: 3 at contact_page, 1 at gbp_reviews, 2 at state_registry+findymail, 2 at
  apollo, 1 at generic_inbox, 1 unresolved; verification marks 8 deliverable, 1 risky. Also seeds one
  do_not_contact business (must be skipped) and one already-deliverable business (idempotency check).
inputs: a Store instance (LocalStore in tests; importable, not runnable on its own).
outputs: businesses + audits rows written into the given store; returns the seeded business dicts.
"""

from __future__ import annotations

METRO = "chicago-north-shore"
SCORE_VERSION = "1.0"

# (place_id, name, domain-or-None, state-or-None) — order matches the intended waterfall resolution:
# b01-b03 -> contact_page, b04 -> gbp_reviews, b05-b06 -> state_registry+findymail, b07-b08 -> apollo,
# b09 -> generic_inbox, b10 -> unresolved (no website at all).
_QUALIFIED = [
    ("p01", "Glow Aesthetics One", "example-medspa-01.test", "IL"),
    ("p02", "Silver Spa Two", "example-medspa-02.test", "MN"),
    ("p03", "Bloom Med Spa Three", "example-medspa-03.test", "OH"),
    ("p04", "Radiant Wellness Four", "example-medspa-04.test", "MI"),
    ("p05", "Serenity Skin Five", "example-medspa-05.test", "IL"),
    ("p06", "Coastal Med Spa Six", "example-medspa-06.test", "IN"),
    ("p07", "Pure Radiance Seven", "example-medspa-07.test", None),
    ("p08", "Elevate Aesthetics Eight", "example-medspa-08.test", None),
    ("p09", "Value Med Spa Nine", "example-medspa-09.test", None),
    ("p10", "Ghost Listing Ten", None, None),
]


def seed(store, *, metro: str = METRO) -> list[dict]:
    """Seed businesses + audits into `store`. Returns the 10 qualified business rows (as upserted)."""
    seeded: list[dict] = []
    for place_id, name, domain, state in _QUALIFIED:
        business = store.upsert_business(
            {
                "place_id": place_id,
                "name": name,
                "slug": name.lower().replace(" ", "-"),
                "metro": metro,
                "state": state,
                "website_url": f"https://{domain}" if domain else None,
                "final_url": f"https://{domain}" if domain else None,
                "is_chain": False,
                "drop_reason": None,
                "do_not_contact": False,
            }
        )
        store.insert_audit(
            {
                "business_id": business["id"],
                "score_version": SCORE_VERSION,
                "total_score": 60,
                "bucket": "qualified",
                "gaps": [],
                "has_website": domain is not None,
            }
        )
        seeded.append(business)

    # p04's place_id must line up with the gbp_reviews fixture filename (fixtures/gbp_reviews/p04.json).
    # An already-do_not_contact business — must never be returned by eligible_businesses().
    dnc_business = store.upsert_business(
        {
            "place_id": "p_dnc",
            "name": "Opted Out Spa",
            "slug": "opted-out-spa",
            "metro": metro,
            "state": "IL",
            "website_url": "https://example-medspa-dnc.test",
            "final_url": "https://example-medspa-dnc.test",
            "is_chain": False,
            "drop_reason": None,
            "do_not_contact": True,
        }
    )
    store.insert_audit(
        {
            "business_id": dnc_business["id"],
            "score_version": SCORE_VERSION,
            "total_score": 70,
            "bucket": "qualified",
            "gaps": [],
            "has_website": True,
        }
    )

    # An already-deliverable business — must be skipped by eligible_businesses() unless --force.
    already_done = store.upsert_business(
        {
            "place_id": "p_already_done",
            "name": "Already Enriched Spa",
            "slug": "already-enriched-spa",
            "metro": metro,
            "state": "IL",
            "website_url": "https://example-medspa-done.test",
            "final_url": "https://example-medspa-done.test",
            "is_chain": False,
            "drop_reason": None,
            "do_not_contact": False,
            "owner_name": "Prior Owner",
            "owner_first": "Prior",
            "owner_email": "prior@example-medspa-done.test",
            "email_status": "deliverable",
            "email_source": "contact_page",
        }
    )
    store.insert_audit(
        {
            "business_id": already_done["id"],
            "score_version": SCORE_VERSION,
            "total_score": 65,
            "bucket": "qualified",
            "gaps": [],
            "has_website": True,
        }
    )

    return seeded
