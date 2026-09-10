"""
contact_page.py
description: Waterfall step 1 — fetch the site home page plus /about, /about-us, /contact, /team,
  /our-team, /meet-* pages (discovered from the homepage nav in live mode), and extract a candidate
  owner/founder name plus a personal mailbox. Generic mailboxes (info@, hello@, ...) are recorded as
  a fallback candidate on StepContext.generic_email rather than treated as a hit.
inputs: business dict (website_url/final_url), enrich.context.StepContext.
outputs: enrich.context.StepResult; on a hit, email_source="contact_page".
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from .context import StepContext, StepResult
from .names import extract_emails, extract_name_candidates, strip_html

NAV_PATHS = ["/about", "/about-us", "/contact", "/team", "/our-team"]
NAV_LINK_RE = re.compile(r'href=["\']([^"\']*(?:about|contact|team|meet)[^"\']*)["\']', re.IGNORECASE)
MAX_PAGES = 8


def _fetch_mock(business: dict, ctx: StepContext) -> str:
    if not ctx.domain:
        return ""
    fixture_path = ctx.fixtures_root / "contact_pages" / f"{ctx.domain}.html"
    if not fixture_path.exists():
        return ""
    return fixture_path.read_text(encoding="utf-8")


def _fetch_live(business: dict, ctx: StepContext) -> str:
    url = business.get("final_url") or business.get("website_url")
    if not url:
        return ""
    try:
        resp = ctx.session.get(url, timeout=20)
        resp.raise_for_status()
        home_html = resp.text
    except Exception:  # noqa: BLE001 — best-effort scrape; a fetch failure is just a miss for this step
        return ""

    pages = [home_html]
    to_fetch = {urljoin(url, link) for link in NAV_LINK_RE.findall(home_html)}
    to_fetch.update(urljoin(url, path) for path in NAV_PATHS)
    for page_url in list(to_fetch)[:MAX_PAGES]:
        try:
            resp = ctx.session.get(page_url, timeout=10)
            if resp.status_code == 200:
                pages.append(resp.text)
        except Exception:  # noqa: BLE001 — a missing subpage is a normal case, not an error
            continue
    return "\n".join(pages)


def run(business: dict, ctx: StepContext) -> StepResult:
    raw = _fetch_mock(business, ctx) if ctx.mock else _fetch_live(business, ctx)
    if not raw:
        return StepResult(hit=False, source="contact_page", evidence="no page content fetched")

    text = strip_html(raw)
    names = extract_name_candidates(text)
    personal, generic = extract_emails(text, ctx.domain)

    if names and not ctx.owner_name:
        ctx.owner_name = names[0]
        ctx.owner_first = names[0].split()[0]
    if generic and not ctx.generic_email:
        ctx.generic_email = generic[0]

    if personal:
        email = personal[0]
        if not ctx.owner_first:
            # Best-effort first-name guess from the local part when no name pattern matched.
            ctx.owner_first = email.split("@", 1)[0].split(".")[0].capitalize()
        return StepResult(
            hit=True,
            owner_name=ctx.owner_name,
            owner_first=ctx.owner_first,
            email=email,
            source="contact_page",
            evidence=f"personal mailbox on site: {email}",
            cost_usd=0.0,
        )

    name_note = f"; name candidate: {names[0]}" if names else ""
    return StepResult(hit=False, source="contact_page", evidence=f"no personal mailbox found{name_note}")
