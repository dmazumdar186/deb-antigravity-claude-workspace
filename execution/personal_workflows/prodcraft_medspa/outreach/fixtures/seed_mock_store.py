"""
seed_mock_store.py
description: Seed a LocalStore with businesses/audits/previews/config that exercise
    daily_queue.py, scan_replies.py, advance.py and deals/deals.py end-to-end in --mock mode.
    Six of the seeded businesses' owner_email addresses match outreach/fixtures/inbox/*.json so
    `scan_replies --mock` produces all six sentiment outcomes.
inputs: seed(store) -> None (importable, used by tests/prodcraft_medspa/test_outreach.py and by
    this file's own CLI: --store-root PATH).
outputs: Populates the given LocalStore's businesses/audits/previews/config tables.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from execution.personal_workflows.prodcraft_medspa.common import store as store_mod  # noqa: E402

# (name, suburb, owner_first, owner_last, owner_email, gap_signal, gap_points, gap_phrase)
_BUSINESSES = [
    (
        "Glow Aesthetics",
        "Winnetka",
        "Dana",
        "Ortiz",
        "owner1@example-medspa-1.test",
        "no_booking_widget",
        22,
        "clients can't book online without calling",
    ),
    (
        "Radiance Skin Bar",
        "Glencoe",
        "Priya",
        "Shah",
        "owner2@example-medspa-2.test",
        "not_mobile_friendly",
        15,
        "the site is hard to use on a phone, where most people look you up",
    ),
    (
        "Lakeside Aesthetics",
        "Highland Park",
        "Marcus",
        "Webb",
        "owner3@example-medspa-3.test",
        "no_cta_above_fold",
        10,
        "there's no way to book from the first screen",
    ),
    (
        "North Shore Med Spa",
        "Lake Forest",
        "Renee",
        "Castillo",
        "owner4@example-medspa-4.test",
        "poor_performance",
        15,
        "pages take several seconds to load on mobile",
    ),
    (
        "Bella Vista Med Spa",
        "Northbrook",
        "Jordan",
        "Lee",
        "owner5@example-medspa-5.test",
        "old_builder",
        8,
        "the site builder limits online booking options",
    ),
    (
        "Winnetka Wellness",
        "Winnetka",
        "Taylor",
        "Kim",
        "owner6@example-medspa-6.test",
        "no_ssl",
        8,
        "browsers flag the site as not secure",
    ),
    (
        "Evanston Skin Studio",
        "Evanston",
        "Alex",
        "Nguyen",
        "owner7@example-medspa-7.test",
        "dated_design",
        15,
        "the layout hides the booking step",
    ),
]


def seed(store: Any, *, metro: str = "chicago-north-shore", today: date | None = None) -> dict:
    """Populate `store` with businesses/audits/previews/config. Returns id maps for tests."""
    today = today or date.today()
    store.set_config("sender", {
        "name": "Debanjan @ ProdCraft",
        "physical_address": "123 Main St, Chicago, IL 60601",
        "signature": "Debanjan",
    })
    store.set_config(
        "phase0",
        {"passed": False, "sends": 0, "calls_booked": 0, "queue_cap_locked": 5, "queue_cap_open": 20},
    )
    store.set_config("touch_days", [0, 3, 7, 12])
    store.set_config("proof_lines", [])

    business_ids: dict[str, str] = {}
    audit_ids: dict[str, str] = {}
    preview_ids: dict[str, str] = {}

    for i, (name, suburb, first, last, email, gap_signal, gap_points, gap_phrase) in enumerate(_BUSINESSES):
        place_id = f"mock-place-{i + 1}"
        business = store.upsert_business(
            {
                "place_id": place_id,
                "name": name,
                "slug": name.lower().replace(" ", "-"),
                "address": f"{100 + i} Green Bay Rd, {suburb}, IL 600{i:02d}",
                "city": suburb,
                "suburb": suburb,
                "metro": metro,
                "state": "IL",
                "phone": f"(847) 555-01{i:02d}",
                "website_url": f"https://example-medspa-{i + 1}.test",
                "final_url": f"https://example-medspa-{i + 1}.test",
                "rating": 4.6,
                "review_count": 80 + i,
                "primary_type": "spa",
                "business_status": "OPERATIONAL",
                "is_chain": False,
                "owner_name": f"{first} {last}",
                "owner_first": first,
                "owner_email": email,
                "email_status": "deliverable",
                "email_source": "contact_page",
                "do_not_contact": False,
            }
        )
        business_ids[name] = business["id"]

        audit = store.insert_audit(
            {
                "business_id": business["id"],
                "score_version": "1.0",
                "has_website": True,
                "booking_widget": None if gap_signal == "no_booking_widget" else "calendly",
                "is_mobile_friendly": gap_signal != "not_mobile_friendly",
                "psi_mobile": 40 if gap_signal == "poor_performance" else 75,
                "vision_dated_score": 8 if gap_signal == "dated_design" else 3,
                "has_cta_above_fold": gap_signal != "no_cta_above_fold",
                "has_ssl": gap_signal != "no_ssl",
                "builder": "wix" if gap_signal == "old_builder" else "custom",
                "has_analytics": True,
                "total_score": 45 + gap_points,
                "bucket": "qualified",
                "gaps": [{"signal": gap_signal, "points": gap_points, "human_phrase": gap_phrase}],
            }
        )
        audit_ids[name] = audit["id"]

        preview = store.upsert_preview(
            {
                "business_id": business["id"],
                "template_id": "medspa-v1",
                "slug_suffix": f"m{i:05d}",
                "subdomain_url": f"https://{business['slug']}-m{i:05d}.preview.prodcraft.fyi",
                "status": "approved",
                "content": {
                    "services": [
                        {"name": "Botox", "blurb": "Schedule a consultation.", "icon": "syringe"},
                        {"name": "HydraFacial", "blurb": "Book a visit.", "icon": "sparkle"},
                    ]
                },
                "content_hash": f"hash-{i}",
                "deployed_at": today.isoformat(),
                "expires_at": (today + timedelta(days=30)).isoformat(),
                "takedown": False,
            }
        )
        preview_ids[name] = preview["id"]

    return {"business_ids": business_ids, "audit_ids": audit_ids, "preview_ids": preview_ids}


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a LocalStore for prodcraft_medspa mock demos")
    parser.add_argument("--store-root", default=".tmp/prodcraft_medspa/store")
    args = parser.parse_args()

    st = store_mod.get_store(kind="local", root=args.store_root)
    ids = seed(st)
    print(f"seeded {len(ids['business_ids'])} businesses under {args.store_root}")


if __name__ == "__main__":
    main()
