"""
findymail.py
description: Waterfall step 5a — Findymail `search/name` (name + domain) for an email address.
  Findymail pays only on verified finds (~$0.10/find estimate booked here). Requires both an owner
  name (from an earlier step) and a domain; misses immediately (no call) without either, or without
  FINDYMAIL_API_KEY set in live mode.
inputs: business dict, enrich.context.StepContext (uses ctx.domain, ctx.owner_name); env FINDYMAIL_API_KEY.
outputs: enrich.context.StepResult; on a hit, email_source="findymail".
"""

from __future__ import annotations

import json

from .context import StepContext, StepResult

SEARCH_URL = "https://app.findymail.com/api/search/name"
COST_PER_FIND_USD = 0.10


def _mock_response(ctx: StepContext) -> dict | None:
    if not ctx.domain:
        return None
    fixture_path = ctx.fixtures_root / "findymail" / f"{ctx.domain}.json"
    if not fixture_path.exists():
        return None
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _live_response(ctx: StepContext) -> dict | None:
    api_key = ctx.settings.FINDYMAIL_API_KEY
    if not api_key or not ctx.domain or not ctx.owner_name:
        return None
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"name": ctx.owner_name, "domain": ctx.domain}
    try:
        resp = ctx.session.post(SEARCH_URL, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except Exception:  # noqa: BLE001 — best-effort lookup; an API failure is just a miss
        return None


def run(business: dict, ctx: StepContext) -> StepResult:
    if not ctx.domain or not ctx.owner_name:
        return StepResult(hit=False, source="findymail", evidence="need both an owner name and a domain")

    data = _mock_response(ctx) if ctx.mock else _live_response(ctx)
    if not data or not data.get("email"):
        return StepResult(hit=False, source="findymail", evidence="no Findymail result")

    return StepResult(
        hit=True,
        owner_name=ctx.owner_name,
        owner_first=ctx.owner_first,
        email=data["email"],
        source="findymail",
        evidence="Findymail name+domain search hit",
        cost_usd=COST_PER_FIND_USD,
    )
