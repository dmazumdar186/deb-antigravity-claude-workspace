"""
generic_inbox.py
description: Waterfall step 6 — final fallback. Uses a generic mailbox already seen on the site
  (StepContext.generic_email, set by contact_page.py) or falls back to info@{domain} as a last resort.
  Always hits when a domain exists; never hits when there is no domain to construct a mailbox from
  (e.g. a business with no website — see waterfall.py's "unresolved" case).
inputs: business dict, enrich.context.StepContext (uses ctx.domain, ctx.generic_email).
outputs: enrich.context.StepResult; on a hit, email_source="generic_inbox".
"""

from __future__ import annotations

from .context import StepContext, StepResult


def run(business: dict, ctx: StepContext) -> StepResult:
    if not ctx.domain:
        return StepResult(hit=False, source="generic_inbox", evidence="no domain to construct a mailbox from")

    email = ctx.generic_email or f"info@{ctx.domain}"
    evidence = (
        f"generic mailbox found on site: {email}"
        if ctx.generic_email
        else f"last-resort fallback: {email}"
    )
    return StepResult(
        hit=True,
        owner_name=ctx.owner_name,
        owner_first=ctx.owner_first,
        email=email,
        source="generic_inbox",
        evidence=evidence,
        cost_usd=0.0,
    )
