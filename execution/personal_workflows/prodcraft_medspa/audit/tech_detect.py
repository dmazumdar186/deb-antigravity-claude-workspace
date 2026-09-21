"""
tech_detect.py
description: Local (no Apify) fingerprint detection of site builder, WordPress theme/year, and jQuery version.
inputs: Imported by audit_site.py; optional network fetch of a WordPress theme's style.css header.
outputs: TechResult dataclass — no filesystem writes (caller persists via Store).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from execution.personal_workflows.prodcraft_medspa.common import http

BUILDER_FINGERPRINTS: dict[str, tuple[str, ...]] = {
    "wix": ("wix.com", "wixstatic.com", "_wixCssTest", "wix-code"),
    "squarespace": ("squarespace.com", "squarespace-cdn.com", "static1.squarespace.com"),
    "godaddy": ("godaddysites.com", "godaddy.com/websites", "wsimg.com"),
    "webflow": ("webflow.com", "assets-global.website-files.com", "webflow.js"),
    "wordpress": ("wp-content", "wp-includes", "/wp-json/"),
    "shopify": ("cdn.shopify.com", "shopify.com/s/", "Shopify.theme"),
    "duda": ("irp.cdn-website.com", "dudamobile.com", "duda.co"),
    "weebly": ("weebly.com", "cdn2.editmysite.com"),
}

_THEME_SLUG_RE = re.compile(r"/wp-content/themes/([a-zA-Z0-9_-]+)/")
_JQUERY_SRC_RE = re.compile(r"jquery[/\-.]?(\d+)(?:\.\d+)*(?:\.min)?\.js", re.IGNORECASE)
_STYLE_VERSION_RE = re.compile(r"Version:\s*([\d.]+)", re.IGNORECASE)
_STYLE_YEAR_RE = re.compile(r"(19|20)\d{2}")

_THEME_FETCH_TIMEOUT = 8


@dataclass
class TechResult:
    builder: str | None
    theme: str | None
    theme_year: int | None
    has_jquery_legacy: bool | None


def detect_builder(html: str) -> str | None:
    """First matching builder fingerprint (dict declaration order), or None."""
    if not html:
        return None
    lowered = html.lower()
    for builder, needles in BUILDER_FINGERPRINTS.items():
        for needle in needles:
            if needle.lower() in lowered:
                return builder
    return None


def detect_wordpress_theme(html: str) -> str | None:
    """Theme slug from a /wp-content/themes/{slug}/ asset path, or None."""
    if not html:
        return None
    match = _THEME_SLUG_RE.search(html)
    return match.group(1) if match else None


def detect_jquery_legacy(html: str) -> bool | None:
    """True if a jquery-<major>.x script src with major < 3 is found; None if no jQuery src at all."""
    if not html:
        return None
    match = _JQUERY_SRC_RE.search(html)
    if not match:
        return None
    return int(match.group(1)) < 3


def fetch_theme_year(final_url: str, theme: str) -> int | None:
    """Best-effort: fetch the theme's style.css header and extract a year from it.

    Cheap, single request, short timeout; any failure (network, no year in header) -> None.
    Never raises.
    """
    if not final_url or not theme:
        return None
    base = final_url.rstrip("/")
    # final_url may already include a path; theme style.css always lives at the site root.
    scheme_host_match = re.match(r"^(https?://[^/]+)", base)
    if not scheme_host_match:
        return None
    style_url = f"{scheme_host_match.group(1)}/wp-content/themes/{theme}/style.css"
    try:
        resp = http.get(style_url, timeout=_THEME_FETCH_TIMEOUT)
        if resp.status_code >= 400:
            return None
        header = resp.text[:2000]
        year_match = _STYLE_YEAR_RE.search(header)
        return int(year_match.group(0)) if year_match else None
    except Exception:  # noqa: BLE001 — best-effort enrichment, never fails the audit
        return None


def detect_tech(html: str, final_url: str | None = None, *, fetch_theme: bool = True) -> TechResult:
    """Run all local fingerprints and (for WordPress, when `fetch_theme`) attempt a theme-year lookup."""
    builder = detect_builder(html)
    theme = detect_wordpress_theme(html) if builder == "wordpress" else None
    has_jquery_legacy = detect_jquery_legacy(html)

    theme_year: int | None = None
    if builder == "wordpress" and theme and fetch_theme and final_url:
        theme_year = fetch_theme_year(final_url, theme)

    return TechResult(
        builder=builder,
        theme=theme,
        theme_year=theme_year,
        has_jquery_legacy=has_jquery_legacy,
    )
