"""
content_lint.py
description: Content-policy linter over an assembled business.json — forbidden medical/legal terms, any URL
    outside google_maps_url/remove_url, the word "logo", services/tagline/phone/hours shape, watermark exactness.
inputs: Imported by build_preview.py as lint(business_json) -> list[str]. Standalone CLI: --file business.json.
outputs: Pure function, no filesystem/network side effects (aside from the optional CLI's own file read).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Forbidden per CONTRACTS.md content rules + prompts/extract_services.md "Forbidden terms".
# Matched case-insensitively as substrings anywhere in the business.json text.
FORBIDDEN_TERMS = [
    "cure",
    "guaranteed results",
    "permanent",
    "fda approved",
    "safe for everyone",
    "no side effects",
    "clinically proven",
    "before/after",
    "before and after",
    "before & after",
]

_PRICE_RE = re.compile(r"\$\d")
_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_PHONE_RE = re.compile(r"^\(\d{3}\) \d{3}-\d{4}$")
_LOGO_RE = re.compile(r"\blogo\b", re.IGNORECASE)

_DAY_ORDER = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _walk_strings(obj: Any):
    """Yield every string value found anywhere in a nested dict/list structure."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from _walk_strings(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk_strings(value)


def watermark_for(name: str) -> str:
    """The exact watermark text required by CONTRACTS.md for a business named `name`."""
    return f"Concept preview by ProdCraft — not affiliated with or endorsed by {name}. Remove: reply 'remove'."


def lint(business: dict) -> list[str]:
    """Return a list of human-readable violation strings; empty list means the business.json passes."""
    violations: list[str] = []
    all_text = " ".join(_walk_strings(business))
    lowered = all_text.lower()

    for term in FORBIDDEN_TERMS:
        if term in lowered:
            violations.append(f"forbidden term present: '{term}'")

    if _PRICE_RE.search(all_text):
        violations.append("dollar amount present (matches r'\\$\\d')")

    if _LOGO_RE.search(all_text):
        violations.append("word 'logo' present")

    preview = business.get("preview") or {}
    allowed_urls = {u for u in (business.get("google_maps_url"), preview.get("remove_url")) if u}
    for url in _URL_RE.findall(all_text):
        if url not in allowed_urls:
            violations.append(f"disallowed URL present: {url}")

    services = business.get("services")
    n_services = len(services) if isinstance(services, list) else 0
    if not (3 <= n_services <= 8):
        violations.append(f"services count {n_services} not in range 3-8")

    tagline = business.get("tagline") or ""
    tagline_words = tagline.split()
    if len(tagline_words) == 0 or len(tagline_words) > 9:
        violations.append(f"tagline word count {len(tagline_words)} not in range 1-9: '{tagline}'")

    phone = business.get("phone") or ""
    if not _PHONE_RE.match(phone):
        violations.append(f"phone format invalid (expected '(XXX) XXX-XXXX'): '{phone}'")

    hours = business.get("hours")
    n_hours = len(hours) if isinstance(hours, list) else 0
    if n_hours != 7:
        violations.append(f"hours has {n_hours} entries, expected 7")
    elif isinstance(hours, list):
        got_days = tuple(h.get("day") for h in hours if isinstance(h, dict))
        if got_days != _DAY_ORDER:
            violations.append(f"hours days out of order or missing: expected {_DAY_ORDER}, got {got_days}")

    name = business.get("name") or ""
    expected_watermark = watermark_for(name)
    watermark = preview.get("watermark")
    if watermark != expected_watermark:
        violations.append(
            f"watermark text does not match contract exactly: expected '{expected_watermark}', got '{watermark}'"
        )

    return violations


def main() -> None:
    """description: Standalone lint of a business.json file, for ad-hoc checks outside the build pipeline.
    inputs: --file PATH (required) — a business.json file to lint.
    outputs: stdout JSON stat line {"script": "content_lint", "in": 1, "violations": [...]}; exit 1 if any violation.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, type=Path, help="Path to a business.json file to lint")
    args = parser.parse_args()

    try:
        business = json.loads(args.file.read_text(encoding="utf-8"))
    except OSError as exc:
        print(json.dumps({"script": "content_lint", "in": 0, "violations": [], "error": str(exc)}))
        sys.exit(1)

    violations = lint(business)
    print(json.dumps({"script": "content_lint", "in": 1, "violations": violations}))
    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()
