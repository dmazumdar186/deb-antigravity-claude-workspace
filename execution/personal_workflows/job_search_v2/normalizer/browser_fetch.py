"""
description: Headless-Chromium fetch fallback for posting_verifier. Some hosts
    (weworkremotely.com) 403 httpx but serve the full page to a real browser;
    others (LinkedIn guest pages) intermittently serve a lighter variant that
    comes back complete on a second request. This module provides a single
    shared-browser context manager so posting_verifier's pass-2 (serial)
    re-check can open a real page without paying browser-launch cost per URL.
inputs:
    - env PLAYWRIGHT_CHROMIUM_PATH (optional executable override)
    - env JOB_SEARCH_V2_INSECURE_TLS=1 (optional; ignore TLS errors — this
      sandbox sits behind a private-CA proxy, production must verify TLS)
outputs:
    - make_browser_fetcher() context manager yielding fetch(url) ->
      (status, html, final_url) or None if playwright/browser is unavailable

Design notes:
    - NOT thread-safe: one Chromium instance, one page open at a time. Callers
      (posting_verifier's pass 2) use it serially, never from a thread pool.
    - Never raises: import failure or launch failure both degrade to a logged
      warning and `None` from the context manager, so callers just skip the
      browser fallback rather than crashing the batch.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Callable, Iterator

logger = logging.getLogger("normalizer.browser_fetch")

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
_LOCALE = "fr-FR"
_PAGE_TIMEOUT_MS = 45_000
_POST_LOAD_WAIT_MS = 1_500

FetchFn = Callable[[str], tuple[int | None, str, str]]


def browser_available() -> bool:
    """True iff the `playwright` package can be imported. Does not attempt to
    launch a browser (that can still fail for other reasons at launch time)."""
    try:
        import playwright  # noqa: F401
    except Exception:  # noqa: BLE001 — import surface, never fatal
        return False
    return True


@contextmanager
def make_browser_fetcher() -> Iterator[FetchFn | None]:
    """Yield a `fetch(url) -> (status, html, final_url)` callable backed by one
    shared headless Chromium browser, or `None` if playwright is not
    importable or the browser fails to launch. Always cleans up the browser
    and the underlying playwright driver on exit; never raises.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001 — import surface, never fatal
        logger.warning("browser_fetch: playwright not importable (%s) — browser fallback disabled", exc)
        yield None
        return

    insecure_tls = os.environ.get("JOB_SEARCH_V2_INSECURE_TLS") == "1"
    chromium_path = os.environ.get("PLAYWRIGHT_CHROMIUM_PATH") or None

    playwright_ctx = None
    browser = None
    try:
        playwright_ctx = sync_playwright().start()
        launch_kwargs: dict = {"headless": True}
        if chromium_path:
            launch_kwargs["executable_path"] = chromium_path
        browser = playwright_ctx.chromium.launch(**launch_kwargs)
    except Exception as exc:  # noqa: BLE001 — launch surface, never fatal
        logger.warning("browser_fetch: chromium launch failed (%s) — browser fallback disabled", exc)
        try:
            if browser is not None:
                browser.close()
        except Exception as close_exc:  # noqa: BLE001 — best-effort cleanup
            logger.warning("browser_fetch: cleanup after failed launch raised (%s)", close_exc)
        try:
            if playwright_ctx is not None:
                playwright_ctx.stop()
        except Exception as close_exc:  # noqa: BLE001 — best-effort cleanup
            logger.warning("browser_fetch: playwright.stop() after failed launch raised (%s)", close_exc)
        yield None
        return

    def fetch(url: str) -> tuple[int | None, str, str]:
        context = None
        page = None
        try:
            context = browser.new_context(
                user_agent=_USER_AGENT,
                locale=_LOCALE,
                ignore_https_errors=insecure_tls,
            )
            page = context.new_page()
            page.set_default_timeout(_PAGE_TIMEOUT_MS)
            response = page.goto(url, wait_until="domcontentloaded", timeout=_PAGE_TIMEOUT_MS)
            page.wait_for_timeout(_POST_LOAD_WAIT_MS)
            html = page.content()
            final_url = page.url
            status = response.status if response is not None else None
            return status, html, final_url
        except Exception as exc:  # noqa: BLE001 — network/browser surface, never fatal
            logger.warning("browser_fetch: fetch failed for %s (%s)", url, exc)
            return None, "", url
        finally:
            try:
                if page is not None:
                    page.close()
            except Exception as close_exc:  # noqa: BLE001 — best-effort cleanup
                logger.warning("browser_fetch: page.close() raised (%s)", close_exc)
            try:
                if context is not None:
                    context.close()
            except Exception as close_exc:  # noqa: BLE001 — best-effort cleanup
                logger.warning("browser_fetch: context.close() raised (%s)", close_exc)

    try:
        yield fetch
    finally:
        try:
            browser.close()
        except Exception as exc:  # noqa: BLE001 — best-effort cleanup
            logger.warning("browser_fetch: browser.close() raised (%s)", exc)
        try:
            playwright_ctx.stop()
        except Exception as exc:  # noqa: BLE001 — best-effort cleanup
            logger.warning("browser_fetch: playwright.stop() raised (%s)", exc)
