"""
hunter.py
description: Waterfall step 5b — Hunter `email-finder` (name + domain), tried after Findymail per
  CONTRACTS.md ("pick whichever key is present, Findymail first"). Requires both an owner name (from
  an earlier step) and a domain; misses immediately (no call) without either, or without
  HUNTER_API_KEY set in live mode.
inputs: business dict, enrich.context.StepContext (uses ctx.domain, ctx.owner_name); env HUNTER_API_KEY.
outputs: enrich.context.StepResult; on a hit, email_source="hunter".
"""

from __future__ import annotations

import json

from .context import StepContext, StepResult

EMAIL_FINDER_URL = "https://api.hunter.io/v2/email-finder"
COST_PER_FIND_USD = 0.10


def _mock_response(ctx: StepContext) -> dict | None:
    if not ctx.domain:
        return None
    fixture_path = ctx.fixtures_root / "hunter" / f"{ctx.domain}.json"
    if not fixture_path.exists():
        return None
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _live_response(ctx: StepContext) -> dict | None:
    api_key = ctx.settings.HUNTER_API_KEY
    if not api_key or not ctx.domain or not ctx.owner_name:
        return None
    parts = ctx.owner_name.split()
    params = {
        "domain": ctx.domain,
        "first_name": parts[0],
        "last_name": parts[-1],
        "api_key": api_key,
    }
    try:
        resp = ctx.session.get(EMAIL_FINDER_URL, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except Exception:  # noqa: BLE001 — best-effort lookup; an API failure is just a miss
        return None


def _extract_email(data: dict) -> str | None:
    # Hunter's live response nests the result under "data"; mock fixtures may use either shape.
    payload = data.get("data", data)
    return payload.get("email")


def run(business: dict, ctx: StepContext) -> StepResult:
    if not ctx.domain or not ctx.owner_name:
        return StepResult(hit=False, source="hunter", evidence="need both an owner name and a domain")

    data = _mock_response(ctx) if ctx.mock else _live_response(ctx)
    email = _extract_email(data) if data else None
    if not email:
        return StepResult(hit=False, source="hunter", evidence="no Hunter result")

    return StepResult(
        hit=True,
        owner_name=ctx.owner_name,
        owner_first=ctx.owner_first,
        email=email,
        source="hunter",
        evidence="Hunter email-finder hit",
        cost_usd=COST_PER_FIND_USD,
    )
