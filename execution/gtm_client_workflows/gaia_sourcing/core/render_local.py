"""Local JavaScript rendering via Playwright + Chromium.

Used by core.cache.fetch_rendered as the middle rung between Firecrawl (paid,
best quality) and raw HTTP (free, but a JS-only directory returns an empty
shell -- see fetch_rendered's docstring for the ocsc.ie/people example).

The default Playwright browser revision (1234) is not installed in this
environment; a pinned Chromium build lives under /opt/pw-browsers instead, so
the executable path must be supplied explicitly rather than left to
Playwright's own resolution. Never runs `playwright install` -- if the
expected binary is missing, `available()` reports False and callers fall
through to raw HTTP.
"""

from __future__ import annotations

import atexit
import glob
import logging
import os
import threading
from typing import Optional

from .cache import _throttle
from .config import CONFIG

logger = logging.getLogger(__name__)

_BROWSERS_ROOT = "/opt/pw-browsers"

_LOCK = threading.Lock()
_STATE: dict = {"playwright": None, "browser": None, "unavailable": False}


def _find_chromium_executable() -> Optional[str]:
    """Locate a usable Chromium binary without ever invoking `playwright install`.

    Resolution order: GAIA_CHROMIUM_PATH env override -> auto-detected build
    under /opt/pw-browsers -> None (let Playwright try its own default, which
    is expected to be absent in this environment but costs nothing to try).
    """
    override = os.environ.get("GAIA_CHROMIUM_PATH")
    if override and os.path.isfile(override):
        return override

    # Prefer a full chromium-* build (has the "chrome" binary) over the
    # headless-shell variant, which has a different CLI surface.
    candidates = sorted(glob.glob(os.path.join(_BROWSERS_ROOT, "chromium-*", "chrome-linux", "chrome")))
    if candidates:
        return candidates[-1]

    return None


def available() -> bool:
    """True if local rendering has a reasonable chance of working.

    Cheap and side-effect-free: does not launch a browser, just checks that
    playwright is importable and CONFIG.render_local allows it. A launch
    failure at call time is still handled gracefully by render_page_text.
    """
    if not CONFIG.render_local:
        return False
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return False
    return True


def _get_browser():
    """Lazily create and cache a single browser instance for this process."""
    with _LOCK:
        if _STATE["unavailable"]:
            return None
        if _STATE["browser"] is not None:
            return _STATE["browser"]

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            _STATE["unavailable"] = True
            return None

        executable_path = _find_chromium_executable()
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", _BROWSERS_ROOT)

        try:
            pw = sync_playwright().start()
            launch_kwargs = {"headless": True}
            if executable_path:
                launch_kwargs["executable_path"] = executable_path
            browser = pw.chromium.launch(**launch_kwargs)
        except Exception as exc:
            # Never a stack trace here -- this runs on every fetch_rendered
            # call once Firecrawl is absent, and a noisy traceback per URL
            # would drown the run log.
            logger.warning("render_local: browser launch failed (%s)", type(exc).__name__)
            try:
                pw.stop()  # type: ignore[possibly-undefined]
            except Exception:
                pass
            _STATE["unavailable"] = True
            return None

        _STATE["playwright"] = pw
        _STATE["browser"] = browser
        return browser


def _close_browser() -> None:
    with _LOCK:
        browser = _STATE.get("browser")
        pw = _STATE.get("playwright")
        if browser is not None:
            try:
                browser.close()
            except Exception:
                # Best-effort cleanup at interpreter exit; nothing downstream
                # depends on this succeeding.
                pass
        if pw is not None:
            try:
                pw.stop()
            except Exception:
                pass
        _STATE["browser"] = None
        _STATE["playwright"] = None


atexit.register(_close_browser)


def render_page_text(
    url: str, timeout_s: int = 45, wait_ms: int = 2500
) -> Optional[tuple[str, Optional[str]]]:
    """Render `url` in headless Chromium and return (body_inner_text, title).

    Returns None on any failure -- a caller falls through to raw HTTP rather
    than treating this as a hard error. Respects the same per-host throttle
    as core.cache's other fetch paths.
    """
    browser = _get_browser()
    if browser is None:
        return None

    _throttle(url)

    page = None
    try:
        page = browser.new_page(user_agent=CONFIG.user_agent)
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_s * 1000)
        page.wait_for_timeout(wait_ms)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            # Some directories keep a long-poll or analytics beacon open
            # forever; networkidle never fires and that's fine -- the
            # domcontentloaded + fixed wait above already got the content.
            pass

        # Lazy-loaded directories (infinite scroll, "load more on scroll")
        # only populate once scrolled into view at least once.
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(300)
        except Exception:
            pass

        text = page.evaluate("document.body.innerText")
        title = page.title()
        return (text or "", title or None)
    except Exception as exc:
        logger.warning("render_local: render failed for ...%s (%s)", url[-60:], type(exc).__name__)
        return None
    finally:
        if page is not None:
            try:
                page.close()
            except Exception:
                pass
