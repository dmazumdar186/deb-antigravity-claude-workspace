"""
apollo.py
description: Waterfall step 4 — Apollo.io `people/match` by name+domain (when StepContext.owner_name is
  already known) or `mixed_people/search` by organization domain + titles Owner/Founder/Medical Director
  (when no name is known yet). Apollo is already licensed and billed by monthly credits, not per call.
inputs: business dict, enrich.context.StepContext (uses ctx.domain, ctx.owner_name); env APOLLO_API_KEY.
outputs: enrich.context.StepResult; on a hit, email_source="apollo".
"""

from __future__ import annotations

import json

from .context import StepContext, StepResult

MATCH_URL = "https://api.apollo.io/v1/people/match"
SEARCH_URL = "https://api.apollo.io/v1/mixed_people/search"
TITLES = ["Owner", "Founder", "Medical Director"]
COST_USD = 0.0  # Apollo credits are already licensed monthly — no marginal per-call cost.


def _mock_response(ctx: StepContext) -> dict | None:
    if not ctx.domain:
        return None
    fixture_path = ctx.fixtures_root / "apollo" / f"{ctx.domain}.json"
    if not fixture_path.exists():
        return None
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _live_response(ctx: StepContext) -> dict | None:
    api_key = ctx.settings.APOLLO_API_KEY
    if not api_key or not ctx.domain:
        return None
    headers = {"Content-Type": "application/json", "X-Api-Key": api_key}
    try:
        if ctx.owner_name:
            parts = ctx.owner_name.split()
            payload = {"first_name": parts[0], "last_name": parts[-1], "domain": ctx.domain}
            resp = ctx.session.post(MATCH_URL, json=payload, headers=headers, timeout=20)
        else:
            payload = {"q_organization_domains": ctx.domain, "person_titles": TITLES}
            resp = ctx.session.post(SEARCH_URL, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except Exception:  # noqa: BLE001 — best-effort lookup; an API failure is just a miss
        return None


def run(business: dict, ctx: StepContext) -> StepResult:
    if not ctx.domain:
        return StepResult(hit=False, source="apollo", evidence="no domain to search")

    data = _mock_response(ctx) if ctx.mock else _live_response(ctx)
    if not data:
        return StepResult(hit=False, source="apollo", evidence="no Apollo match")

    person = data.get("person") or next(iter(data.get("people") or []), None)
    if not person or not person.get("email"):
        return StepResult(hit=False, source="apollo", evidence="Apollo returned no email")

    name = person.get("name") or f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
    first = person.get("first_name") or (name.split()[0] if name else None)
    if name and not ctx.owner_name:
        ctx.owner_name = name
        ctx.owner_first = first

    return StepResult(
        hit=True,
        owner_name=ctx.owner_name or name or None,
        owner_first=ctx.owner_first or first,
        email=person["email"],
        source="apollo",
        evidence=f"Apollo match, email_status={person.get('email_status', 'unknown')}",
        cost_usd=COST_USD,
    )
