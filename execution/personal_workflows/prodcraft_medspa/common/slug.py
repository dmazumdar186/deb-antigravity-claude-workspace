"""
slug.py
description: Slugify business names and build unguessable preview-subdomain hosts.
inputs: Imported by preview/ and discovery/ scripts; no CLI args (importable module).
outputs: Pure functions — no filesystem or network side effects.
"""

from __future__ import annotations

import re
import secrets
import unicodedata

MAX_SLUG_LEN = 40

# Trailing legal-entity noise stripped after slugification. Per CONTRACTS.md,
# other multi-word suffixes ("med spa") are intentionally NOT stripped —
# they're part of what makes the business identifiable.
_STRIP_SUFFIXES = ("llc", "inc")


def slugify(name: str) -> str:
    """ASCII, lowercase, hyphen-separated slug of `name`, max 40 chars.

    Strips a trailing 'llc'/'inc' token (with any separator punctuation before
    it). Non-ASCII characters are transliterated where possible, otherwise
    dropped. Collapses runs of non-alphanumeric characters to a single hyphen.
    """
    normalized = unicodedata.normalize("NFKD", name)
    ascii_bytes = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_bytes.lower()

    # Drop a trailing legal-entity token (e.g. "Glow Aesthetics, LLC" -> "Glow Aesthetics").
    tokens = re.split(r"[\s,\.\-]+", lowered.strip())
    tokens = [t for t in tokens if t]
    while tokens and tokens[-1] in _STRIP_SUFFIXES:
        tokens.pop()

    joined = "-".join(tokens)
    slug = re.sub(r"[^a-z0-9]+", "-", joined).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)

    if not slug:
        slug = "business"

    return slug[:MAX_SLUG_LEN].rstrip("-")


def random_suffix(n: int = 6) -> str:
    """n-character random suffix from lowercase letters + digits, using `secrets`."""
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(n))


def preview_host(slug: str, suffix: str, base_domain: str) -> str:
    """Build the full preview subdomain host, e.g. 'glow-aesthetics-k3x9qa.preview.prodcraft.fyi'."""
    return f"{slug}-{suffix}.{base_domain}"
