"""
screenshots.py
description: Playwright mobile/desktop screenshots + above-fold CTA detection; upload to store-backed location.
inputs: Imported by audit_site.py; optional PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers.
outputs: PNG files under .tmp/prodcraft_medspa/screenshots/ and (Supabase store) an uploaded object URL.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from execution.personal_workflows.prodcraft_medspa.common import config, http

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
_LOCAL_CHROMIUM = "/opt/pw-browsers/chromium"

MOBILE_VIEWPORT = {"width": 390, "height": 844}
DESKTOP_VIEWPORT = {"width": 1440, "height": 900}
NAV_TIMEOUT_MS = 20_000
_CTA_RE = re.compile(r"book|schedule|consult|appointment|reserve", re.IGNORECASE)

try:
    from playwright.sync_api import sync_playwright  # type: ignore[import-untyped]

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


@dataclass
class ScreenshotResult:
    mobile_path: str | None
    desktop_path: str | None
    cta_above_fold: bool | None
    mobile_url: str | None = None
    desktop_url: str | None = None
    error: str | None = None


def _launch_kwargs() -> dict:
    if Path(_LOCAL_CHROMIUM).exists():
        return {"executable_path": _LOCAL_CHROMIUM}
    return {}


def _cta_above_fold(page) -> bool:  # noqa: ANN001 — playwright Page, optional dep
    """Any visible a/button whose text matches the CTA regex, within the first viewport."""
    try:
        elements = page.query_selector_all("a, button")
    except Exception:  # noqa: BLE001 — a hostile/broken page must not crash the audit
        return False
    for el in elements:
        try:
            if not el.is_visible():
                continue
            text = (el.inner_text() or "").strip()
            if not text or not _CTA_RE.search(text):
                continue
            box = el.bounding_box()
            if box and box["y"] < MOBILE_VIEWPORT["height"] and box["y"] >= -box["height"]:
                return True
        except Exception:  # noqa: BLE001 — a single stale/detached element must not abort the check
            continue
    return False


def capture_screenshots(url: str, slug: str, *, out_dir: Path | None = None) -> ScreenshotResult:
    """Capture mobile full-page + desktop viewport-only screenshots and detect an above-fold CTA.

    Saves under `out_dir` (default .tmp/prodcraft_medspa/screenshots/) as
    `{slug}_mobile.png` / `{slug}_desktop.png`. Never raises; failures land in
    ScreenshotResult.error and cta_above_fold=None.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return ScreenshotResult(None, None, None, error="playwright not installed")

    settings = config.bootstrap()
    out_dir = out_dir or (settings.TMP / "screenshots")
    out_dir.mkdir(parents=True, exist_ok=True)
    mobile_path = out_dir / f"{slug}_mobile.png"
    desktop_path = out_dir / f"{slug}_desktop.png"

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(**_launch_kwargs())
            try:
                mobile_ctx = browser.new_context(viewport=MOBILE_VIEWPORT, is_mobile=True)
                mobile_ctx.route(
                    re.compile(r".*\.(mp4|webm|ogg|mov)(\?.*)?$", re.IGNORECASE),
                    lambda route: route.abort(),
                )
                mobile_page = mobile_ctx.new_page()
                mobile_page.set_default_timeout(NAV_TIMEOUT_MS)
                mobile_page.goto(url, wait_until="load", timeout=NAV_TIMEOUT_MS)
                cta_above_fold = _cta_above_fold(mobile_page)
                mobile_page.screenshot(path=str(mobile_path), full_page=True)
                mobile_ctx.close()

                desktop_ctx = browser.new_context(viewport=DESKTOP_VIEWPORT)
                desktop_ctx.route(
                    re.compile(r".*\.(mp4|webm|ogg|mov)(\?.*)?$", re.IGNORECASE),
                    lambda route: route.abort(),
                )
                desktop_page = desktop_ctx.new_page()
                desktop_page.set_default_timeout(NAV_TIMEOUT_MS)
                desktop_page.goto(url, wait_until="load", timeout=NAV_TIMEOUT_MS)
                desktop_page.screenshot(path=str(desktop_path), full_page=False)
                desktop_ctx.close()
            finally:
                browser.close()
    except Exception as exc:  # noqa: BLE001 — any Playwright failure must degrade, not crash the audit
        return ScreenshotResult(None, None, None, error=str(exc))

    return ScreenshotResult(
        mobile_path=str(mobile_path),
        desktop_path=str(desktop_path),
        cta_above_fold=cta_above_fold,
    )


def upload_screenshot(local_path: str, business_slug: str, kind: str, store_kind: str) -> str:
    """Return the location to store in `audits.screenshot_{kind}_url`.

    'supabase': PUT to Supabase Storage bucket `audit-screenshots`, return the public object path.
    else: return the local file path unchanged (LocalStore mode).
    """
    if store_kind != "supabase":
        return local_path

    settings = config.bootstrap()
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        return local_path

    object_path = f"{business_slug}/{Path(local_path).name}"
    url = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/audit-screenshots/{object_path}"
    with open(local_path, "rb") as f:
        data = f.read()
    resp = http.post(
        url,
        data=data,
        headers={
            "apikey": settings.SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
            "Content-Type": "image/png",
            "x-upsert": "true",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/public/audit-screenshots/{object_path}"
