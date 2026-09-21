"""
state_registry.py
description: Waterfall step 3 — best-effort state business-registry lookups (IL SOS, MN SOS, OH SOS,
  MI LARA, IN INBiz) for the registered agent / member name behind a business. These are unofficial
  HTML search-page scrapers (no public API for any of the five states); one polite GET attempt per
  lookup, 2s delay, parsed with regex (no bs4 required). This step never yields an email — registries
  don't publish one — it only ever enriches StepContext.owner_name for later steps (Apollo/Findymail/
  Hunter search by name + domain).
inputs: business dict (name, state), enrich.context.StepContext.
outputs: enrich.context.StepResult (hit is always False); `lookup(name, state, ctx=...)` is the
  reusable {registered_agent, members[], source_url} function per CONTRACTS.md.

# SELF-HEALING CHANGE LOG
# Per .claude/rules/automation-boundaries.md ("self-healing standing instruction"): these state SOS
# search pages change their markup without notice and have no public API. If the same lookup failure
# (0 results, or a changed selector producing garbage) recurs more than 3 times for the same state,
# assume the page changed. Investigate with full autonomy, fix the regex/endpoint below, then append
# a dated entry here: problem, solution, what was updated. Keep prior entries — this log is the audit
# trail for a possible bad self-rewrite (e.g. a transient rate limit mistaken for a page change).
# Scope limit: an automation running this step may rewrite only THIS file — CONTRACTS.md, the rest of
# enrich/, and everything under common/ still require operator approval per CLAUDE.md.
#
# 2026-09-10 — initial build. No incidents yet.
"""

from __future__ import annotations

import re
import time

from .context import StepContext, StepResult

REQUEST_DELAY_SECONDS = 2.0

# Best-effort, unofficial search endpoints — see change-log above; these are the most likely thing
# to rot in this whole package.
STATE_ENDPOINTS: dict[str, dict[str, str]] = {
    "IL": {"url": "https://apps.ilsos.gov/businessentitysearch/businessentitysearch", "query_param": "name"},
    "MN": {"url": "https://mblsportal.sos.mn.gov/Business/Search", "query_param": "SearchTerm"},
    "OH": {"url": "https://businesssearch.ohiosos.gov/", "query_param": "q"},
    "MI": {"url": "https://cofs.lara.state.mi.us/SearchApi/Search/Search", "query_param": "SEARCH_VALUE"},
    "IN": {"url": "https://bsd.sos.in.gov/PublicBusinessSearch", "query_param": "SearchTerm"},
}

_NAME_CORE = r"[A-Z][a-zA-Z'\-]+(?:\s[A-Z]\.)?\s[A-Z][a-zA-Z'\-]+"
AGENT_RE = re.compile(rf"Registered Agent:?\s*({_NAME_CORE})", re.IGNORECASE)
MEMBER_RE = re.compile(rf"(?:Member|Manager|Officer):?\s*({_NAME_CORE})", re.IGNORECASE)


def _mock_html(state: str, ctx: StepContext) -> str:
    fixture_path = ctx.fixtures_root / "state_registry" / f"{state}.html"
    if not fixture_path.exists():
        return ""
    return fixture_path.read_text(encoding="utf-8")


def _live_html(name: str, state: str, ctx: StepContext) -> str:
    endpoint = STATE_ENDPOINTS.get(state)
    if not endpoint or not name:
        return ""
    try:
        time.sleep(REQUEST_DELAY_SECONDS)  # polite delay; one attempt only per CONTRACTS.md
        resp = ctx.session.get(endpoint["url"], params={endpoint["query_param"]: name}, timeout=20)
        if resp.status_code != 200:
            return ""
        return resp.text
    except Exception:  # noqa: BLE001 — best-effort lookup; a fetch failure is just a miss
        return ""


def lookup(name: str, state: str, *, ctx: StepContext) -> dict:
    """Search-page GET + regex parse. Returns {registered_agent, members, source_url}."""
    state_key = (state or "").upper()
    html = _mock_html(state_key, ctx) if ctx.mock else _live_html(name, state_key, ctx)
    agent = None
    members: list[str] = []
    if html:
        match = AGENT_RE.search(html)
        agent = match.group(1).strip() if match else None
        members = [m.group(1).strip() for m in MEMBER_RE.finditer(html)]
    return {
        "registered_agent": agent,
        "members": members,
        "source_url": STATE_ENDPOINTS.get(state_key, {}).get("url"),
    }


def run(business: dict, ctx: StepContext) -> StepResult:
    state = business.get("state")
    if not state:
        return StepResult(hit=False, source="state_registry", evidence="no state on business record")

    result = lookup(business.get("name", ""), state, ctx=ctx)
    name = result.get("registered_agent") or (result.get("members") or [None])[0]
    if not name:
        return StepResult(
            hit=False, source="state_registry", evidence=f"no registry match ({result.get('source_url')})"
        )

    if not ctx.owner_name:
        ctx.owner_name = name
        ctx.owner_first = name.split()[0]

    return StepResult(
        hit=False,  # registries never publish an email — this step only feeds StepContext for later steps
        source="state_registry",
        owner_name=ctx.owner_name,
        owner_first=ctx.owner_first,
        evidence=f"registered agent/member found: {name} ({result.get('source_url')})",
    )
