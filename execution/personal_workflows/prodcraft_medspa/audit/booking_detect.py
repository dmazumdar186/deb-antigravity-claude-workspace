"""
booking_detect.py
description: Detect online-booking vendor widgets by grepping HTML, script srcs, iframe srcs, and hrefs.
inputs: Imported by audit_site.py; no CLI args (importable module).
outputs: Pure functions over an HTML string — no filesystem or network side effects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Vendor key -> substrings matched against the raw HTML (script src, iframe src, href, or
# any inline text mentioning the vendor's domain/handle). Per PROJECT_SPEC.md §5.1 step 4
# plus the CONTRACTS.md addendum (glossgenius, booker, schedulicity, fresha, setmore,
# jane.app, nextech, weave).
VENDOR_PATTERNS: dict[str, tuple[str, ...]] = {
    "vagaro": ("vagaro.com", "vagaro.",),
    "mindbody": ("mindbodyonline.com", "mindbody.io", "healcode.com"),
    "boulevard": ("blvd.co", "boulevard.io", "joinblvd.com"),
    "zenoti": ("zenoti.com",),
    "acuity": ("acuityscheduling.com", "squarespacescheduling.com"),
    "calendly": ("calendly.com",),
    "square": ("squareup.com/appointments", "square.site"),
    "aesthetic_record": ("aestheticrecord.com",),
    "patientnow": ("patientnow.com",),
    "moxie": ("moxie.app", "joinmoxie.com"),
    "glossgenius": ("glossgenius.com",),
    "booker": ("booker.com", "getbooker.com"),
    "schedulicity": ("schedulicity.com",),
    "fresha": ("fresha.com",),
    "setmore": ("setmore.com",),
    "jane.app": ("jane.app",),
    "nextech": ("nextech.com",),
    "weave": ("getweave.com", "weavehq.com"),
}

_SRC_HREF_RE = re.compile(r'(?:src|href)=["\']([^"\']+)["\']', re.IGNORECASE)


@dataclass
class BookingDetection:
    vendor: str | None
    booking_links: list[str] = field(default_factory=list)


def _matches_vendor(text: str) -> str | None:
    lowered = text.lower()
    for vendor, patterns in VENDOR_PATTERNS.items():
        for pattern in patterns:
            if pattern in lowered:
                return vendor
    return None


def detect_booking(html: str) -> BookingDetection:
    """Grep `html` (script srcs, iframe srcs, hrefs, and raw text) for a known booking vendor.

    Returns the first vendor key matched (dict iteration order = declaration order above)
    plus every src/href that matched any vendor pattern, deduped, in document order.
    """
    if not html:
        return BookingDetection(vendor=None, booking_links=[])

    links = _SRC_HREF_RE.findall(html)
    booking_links: list[str] = []
    seen: set[str] = set()
    vendor: str | None = None

    for link in links:
        matched = _matches_vendor(link)
        if matched:
            if vendor is None:
                vendor = matched
            if link not in seen:
                seen.add(link)
                booking_links.append(link)

    if vendor is None:
        # Fall back to a whole-document scan (vendor widget embedded via inline JS config,
        # not a src/href attribute — e.g. a Boulevard snippet that only sets a data attribute).
        vendor = _matches_vendor(html)

    return BookingDetection(vendor=vendor, booking_links=booking_links)


def booking_widget(html: str) -> str | None:
    """Convenience wrapper: just the vendor key (or None)."""
    return detect_booking(html).vendor
