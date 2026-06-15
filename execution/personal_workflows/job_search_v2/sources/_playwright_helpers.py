"""
description: Small Playwright helpers shared by WTTJ + APEC + future SPA-gated sources.
inputs: imported by source modules
outputs: a `render_page()` function that handles the consent + hydration dance.

Common shape of "scrape a French SPA":
    1. goto URL
    2. dismiss cookie consent (Didomi, Axeptio, OneTrust — each site uses one)
    3. wait for a content selector that proves real data is on the page
    4. return the rendered HTML

Returning [] cleanly when Playwright isn't installed lets the orchestrator survive
on the other sources. The consent + selector lists are intentionally broad — French
SPAs change their consent vendor every 6–12 months.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("playwright_helpers")

# Cookie-consent button selectors, tried in order. First one that resolves wins.
# We keep this list small + maintained. If a site adds a new vendor, add it here.
CONSENT_SELECTORS = [
    # Didomi (APEC, many FR gov + finance sites)
    "#didomi-notice-agree-button",
    "button#didomi-notice-agree-button",
    # Axeptio (WTTJ, many FR media)
    "#axeptio_btn_acceptAll",
    "button#axeptio_btn_acceptAll",
    # OneTrust (occasional)
    "#onetrust-accept-btn-handler",
    # Generic text-based fallbacks
    "button:has-text('Tout accepter')",
    "button:has-text('Accepter tout')",
    "button:has-text('Accept all')",
    "button:has-text('I agree')",
    "button:has-text('Accept')",
]

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def render_page(
    url: str,
    *,
    wait_selectors: list[str] | None = None,
    consent_selectors: list[str] | None = None,
    locale: str = "fr-FR",
    user_agent: str = DEFAULT_UA,
    extra_wait_ms: int = 2500,
    nav_timeout_ms: int = 30000,
) -> str:
    """Render a JS-heavy page and return the post-hydration HTML.

    wait_selectors: list of CSS selectors. The function returns as soon as ANY
        of them is visible (with a per-selector timeout cap). Used as a "real
        content has loaded" signal. If empty, just waits networkidle + extra_wait_ms.

    consent_selectors: override the default CONSENT_SELECTORS list.

    Returns the HTML string. Returns "" if Playwright isn't installed or all the
    steps time out — caller decides whether that's fatal.
    """
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        logger.warning("playwright_helpers: playwright not installed. Returning empty HTML. "
                       "Install: pip install playwright && playwright install chromium")
        return ""

    consent_selectors = consent_selectors or CONSENT_SELECTORS
    wait_selectors = wait_selectors or []

    html = ""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(user_agent=user_agent, locale=locale)
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=nav_timeout_ms)

            # 1. Try cookie consent — best-effort, fail-fast.
            for sel in consent_selectors:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=1500):
                        btn.click(timeout=2000)
                        logger.info("playwright_helpers: clicked consent selector %s", sel)
                        page.wait_for_timeout(500)
                        break
                except Exception:  # noqa: BLE001 — selector miss is normal
                    continue

            # 2. Wait for at least one content selector to be visible.
            content_seen = False
            for sel in wait_selectors:
                try:
                    page.locator(sel).first.wait_for(state="visible", timeout=8000)
                    content_seen = True
                    logger.info("playwright_helpers: content selector %s appeared", sel)
                    break
                except Exception:  # noqa: BLE001 — selector miss continues to next
                    continue

            if not content_seen and wait_selectors:
                logger.info("playwright_helpers: none of %d wait selectors appeared — proceeding with whatever rendered",
                            len(wait_selectors))

            # 3. Extra settle time for late-binding XHRs.
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:  # noqa: BLE001 — networkidle is best-effort
                pass
            page.wait_for_timeout(extra_wait_ms)

            html = page.content()
            browser.close()
    except Exception as exc:  # noqa: BLE001 — playwright surface is broad
        logger.warning("playwright_helpers: render_page errored on %s: %s", url, exc)
        return html

    return html
