"""
names.py
description: Shared regex utilities for owner-name and mailbox extraction, used by contact_page.py,
  gbp_reviews.py, and state_registry.py. A capitalized two-word span is only treated as a candidate
  name when it carries a title/credential marker or sits near an ownership keyword — a bare
  capitalized bigram like "Book Now" or "Laser Hair" is never extracted.
inputs: free text (page HTML/text, review text, registry HTML).
outputs: list[str] name candidates; (personal[], generic[]) email address lists.
"""

from __future__ import annotations

import re
from html import unescape

# First [Middle initial] Last — the shape every accepted name must match.
_NAME_CORE = r"[A-Z][a-zA-Z'\-]+(?:\s[A-Z]\.)?\s[A-Z][a-zA-Z'\-]+"

TITLE_PREFIX_RE = re.compile(rf"\bDr\.\s+({_NAME_CORE})")
CREDENTIAL_SUFFIX_RE = re.compile(rf"\b({_NAME_CORE}),?\s+(?:RN|NP|MD|DO|PA-C|PA)\b")
KEYWORD_CONTEXT_RE = re.compile(
    rf"(?:founder|founded by|co-founder|owner|practice owner|medical director)s?\b[^.\n]{{0,60}}?({_NAME_CORE})",
    re.IGNORECASE,
)
KEYWORD_CONTEXT_REVERSE_RE = re.compile(
    rf"({_NAME_CORE})[^.\n]{{0,40}}?,?\s*(?:is the founder|is our founder|is the owner|is our owner|"
    rf"owner|founder|co-founder)\b",
    re.IGNORECASE,
)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
GENERIC_LOCAL_PARTS = {
    "info",
    "hello",
    "contact",
    "admin",
    "frontdesk",
    "office",
    "support",
    "booking",
    "bookings",
    "appointments",
    "reception",
}


def strip_html(html: str) -> str:
    """Crude tag stripper (no bs4 dependency) — good enough for regex-based name/email scanning."""
    text = _TAG_RE.sub(" ", html)
    text = unescape(text)
    return _WS_RE.sub(" ", text).strip()


def extract_name_candidates(text: str) -> list[str]:
    """Return deduped candidate owner names, in the order first matched. Only names near a title,
    credential, or ownership keyword are returned — see module docstring."""
    candidates: list[str] = []
    for pattern in (TITLE_PREFIX_RE, CREDENTIAL_SUFFIX_RE, KEYWORD_CONTEXT_RE, KEYWORD_CONTEXT_REVERSE_RE):
        candidates.extend(m.group(1).strip() for m in pattern.finditer(text))
    seen: set[str] = set()
    out: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def extract_emails(text: str, domain: str | None = None) -> tuple[list[str], list[str]]:
    """Return (personal, generic) email lists found in `text`, restricted to `domain` when given.
    Generic mailboxes (info@, hello@, ...) are ignored as personal but still returned separately."""
    found = list(dict.fromkeys(EMAIL_RE.findall(text)))  # dedupe, preserve order
    if domain:
        needle = f"@{domain}".lower()
        found = [e for e in found if e.lower().endswith(needle)]
    personal: list[str] = []
    generic: list[str] = []
    for email in found:
        local = email.split("@", 1)[0].lower()
        (generic if local in GENERIC_LOCAL_PARTS else personal).append(email)
    return personal, generic


def domain_from_url(url: str | None) -> str | None:
    """netloc of a URL, without a leading www. and without scheme/port."""
    if not url:
        return None
    from urllib.parse import urlparse

    netloc = urlparse(url if "://" in url else f"https://{url}").netloc
    netloc = netloc.split(":")[0]
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc or None
