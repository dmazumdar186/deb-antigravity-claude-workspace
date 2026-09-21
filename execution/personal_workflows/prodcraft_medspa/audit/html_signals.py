"""
html_signals.py
description: Extract viewport/footer-year/analytics/visible-text/title signals from fetched HTML.
inputs: Imported by audit_site.py; no CLI args (importable module).
outputs: Pure functions over an HTML string — no filesystem or network side effects.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from html.parser import HTMLParser

MAX_SITE_TEXT_CHARS = 6000
_CURRENT_YEAR = datetime.now(timezone.utc).year
_MIN_FOOTER_YEAR = 1995

_VIEWPORT_RE = re.compile(r'<meta[^>]+name=["\']viewport["\'][^>]*>', re.IGNORECASE)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)

# GA4 measurement id (G-XXXXXXX), gtag.js, legacy GTM container, Meta Pixel (fbq / connect.facebook.net).
_ANALYTICS_RE = re.compile(
    r"(G-[A-Z0-9]{6,})|gtag\(|GTM-[A-Z0-9]+|fbq\(|connect\.facebook\.net",
    re.IGNORECASE,
)

_COPYRIGHT_CONTEXT_RE = re.compile(
    r"(?:©|&copy;|copyright|all rights reserved)[^\n]{0,80}",
    re.IGNORECASE,
)
_YEAR_RE = re.compile(r"(19|20)\d{2}")


class _VisibleTextParser(HTMLParser):
    """Strips tags, script/style content, and collapses whitespace into visible text."""

    _SKIP_TAGS = {"script", "style", "noscript", "template"}

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001 - stdlib signature
        if tag.lower() in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            stripped = data.strip()
            if stripped:
                self.chunks.append(stripped)


def has_viewport_meta(html: str) -> bool:
    """True if a <meta name="viewport" ...> tag is present."""
    if not html:
        return False
    return bool(_VIEWPORT_RE.search(html))


def footer_year(html: str) -> int | None:
    """Max 4-digit year (1995..current year) found near ©/copyright/'all rights reserved'."""
    if not html:
        return None
    years: list[int] = []
    for match in _COPYRIGHT_CONTEXT_RE.finditer(html):
        context = match.group(0)
        for year_match in _YEAR_RE.finditer(context):
            year = int(year_match.group(0))
            if _MIN_FOOTER_YEAR <= year <= _CURRENT_YEAR:
                years.append(year)
    return max(years) if years else None


def has_analytics(html: str) -> bool:
    """True if GA4 (G-...), gtag(), legacy GTM-..., or Meta Pixel (fbq/connect.facebook.net) is present."""
    if not html:
        return False
    return bool(_ANALYTICS_RE.search(html))


def site_text(html: str) -> str:
    """Visible text (tags/script/style stripped), collapsed, truncated to MAX_SITE_TEXT_CHARS."""
    if not html:
        return ""
    parser = _VisibleTextParser()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001 — malformed HTML must never crash the audit; return what we got
        pass
    text = " ".join(parser.chunks)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_SITE_TEXT_CHARS]


def title(html: str) -> str | None:
    """The <title> text, whitespace-collapsed, or None if absent."""
    if not html:
        return None
    match = _TITLE_RE.search(html)
    if not match:
        return None
    text = re.sub(r"\s+", " ", match.group(1)).strip()
    return text or None
