"""
gbp_reviews.py
description: Waterfall step 2 — Google Places (New) `GET places/{id}` with field mask `reviews` (5 max).
  Scans customer-written review text (never `reviews[].authorAttribution` — that is the reviewer, not
  the owner) for an owner mention ("Dr. X", "owner Y"). If the review text itself contains an email for
  that domain, that email is used directly; otherwise, once a name is found, a first@domain pattern
  guess is used as a lower-confidence email candidate (a common bootstrapped-outreach technique).
inputs: business dict (place_id), enrich.context.StepContext.
outputs: enrich.context.StepResult; on a hit, email_source="gbp_reviews".
"""

from __future__ import annotations

import json

from .context import StepContext, StepResult
from .names import extract_emails, extract_name_candidates

PLACES_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"
MAX_REVIEWS = 5


def _mock_reviews(business: dict, ctx: StepContext) -> list[dict]:
    place_id = business.get("place_id")
    if not place_id:
        return []
    fixture_path = ctx.fixtures_root / "gbp_reviews" / f"{place_id}.json"
    if not fixture_path.exists():
        return []
    return json.loads(fixture_path.read_text(encoding="utf-8")).get("reviews", [])


def _live_reviews(business: dict, ctx: StepContext) -> list[dict]:
    place_id = business.get("place_id")
    api_key = ctx.settings.GOOGLE_PLACES_API_KEY
    if not place_id or not api_key:
        return []
    try:
        resp = ctx.session.get(
            PLACES_DETAILS_URL.format(place_id=place_id),
            headers={"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": "reviews"},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json().get("reviews", [])
    except Exception:  # noqa: BLE001 — best-effort lookup; a Places failure is just a miss
        return []


def _review_text(review: dict) -> str:
    text_field = review.get("text")
    if isinstance(text_field, dict):
        return text_field.get("text", "") or ""
    return text_field or ""


def run(business: dict, ctx: StepContext) -> StepResult:
    reviews = (_mock_reviews(business, ctx) if ctx.mock else _live_reviews(business, ctx))[:MAX_REVIEWS]
    if not reviews:
        return StepResult(hit=False, source="gbp_reviews", evidence="no reviews returned")

    blob = "\n".join(_review_text(r) for r in reviews)
    names = extract_name_candidates(blob)
    personal, _generic = extract_emails(blob, ctx.domain)

    if names and not ctx.owner_name:
        ctx.owner_name = names[0]
        ctx.owner_first = names[0].split()[0]

    if personal:
        return StepResult(
            hit=True,
            owner_name=ctx.owner_name,
            owner_first=ctx.owner_first,
            email=personal[0],
            source="gbp_reviews",
            evidence=f"email found directly in review text: {personal[0]}",
            cost_usd=0.0,
        )

    if names and ctx.domain and ctx.owner_first:
        guess = f"{ctx.owner_first.lower()}@{ctx.domain}"
        return StepResult(
            hit=True,
            owner_name=ctx.owner_name,
            owner_first=ctx.owner_first,
            email=guess,
            source="gbp_reviews",
            evidence=f"owner mentioned in reviews ({names[0]}); email guessed as first-name@domain pattern",
            cost_usd=0.0,
        )

    if names:
        return StepResult(
            hit=False,
            source="gbp_reviews",
            owner_name=ctx.owner_name,
            owner_first=ctx.owner_first,
            evidence=f"owner mentioned in reviews ({names[0]}) but no domain to guess an email",
        )
    return StepResult(hit=False, source="gbp_reviews", evidence="no owner mention found in review text")
