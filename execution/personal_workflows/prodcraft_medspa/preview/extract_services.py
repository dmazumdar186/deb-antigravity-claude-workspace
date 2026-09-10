"""
extract_services.py
description: Build business.json's services[] + tagline via common.llm (prompts/extract_services.md),
    validated against the fixed allowed-service/icon lists, falling back to 4 primary_type-keyed default
    services when the LLM returns fewer than 3 valid ones.
inputs: Imported by build_preview.py: extract_services(business, audit, *, mock, model, fixtures_root) -> dict.
    Standalone CLI: --business FILE --audit FILE [--mock] [--model ID].
outputs: {"services": [...], "tagline": str, "model_id", "prompt_sha256", "llm_cost_usd"}.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))  # repo root, for direct-script execution

from execution.personal_workflows.prodcraft_medspa.common import config, llm  # noqa: E402

PKG_ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = PKG_ROOT / "prompts" / "extract_services.md"
DEFAULT_FIXTURES_ROOT = PKG_ROOT / "prompts" / "fixtures"

# Exact fixed lists from prompts/extract_services.md — never emit outside these.
ALLOWED_SERVICES = {
    "Botox / Neuromodulators",
    "Dermal Fillers",
    "Laser Hair Removal",
    "Chemical Peels",
    "Microneedling",
    "HydraFacial",
    "IPL / Photofacial",
    "Body Contouring",
    "Skin Tightening",
    "PRP / PRF",
    "Weight Management",
    "Facials",
    "IV Therapy",
    "Laser Skin Resurfacing",
    "Acne Treatment",
}
ALLOWED_ICONS = {"syringe", "sparkle", "laser", "droplet", "leaf", "sun", "body", "needle", "scale", "flask"}

# Mirrors content_lint.FORBIDDEN_TERMS; duplicated (not imported) so this module has no import-time
# dependency on content_lint's own validation surface — the LLM output is checked at the field level here,
# content_lint re-checks the whole assembled business.json as the final gate.
_FORBIDDEN_TERMS = [
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

MAX_TAGLINE_WORDS = 9
MIN_VALID_SERVICES = 3
MAX_SERVICES = 8

# 4 generic default services per Google Places `primaryType`, used when the LLM returns < 3 valid
# services (missing site, thin site text, or a malformed/empty response). Every entry validates against
# ALLOWED_SERVICES / ALLOWED_ICONS and every blurb is forbidden-term-clean by construction.
_DEFAULT_SERVICES_BY_TYPE: dict[str, list[dict[str, str]]] = {
    "spa": [
        {"name": "Botox / Neuromodulators", "blurb": "Schedule a consultation to see if it's right for you.", "icon": "syringe"},
        {"name": "Dermal Fillers", "blurb": "Book a visit to talk through your options.", "icon": "droplet"},
        {"name": "Facials", "blurb": "Reserve a slot for a relaxing treatment.", "icon": "sparkle"},
        {"name": "Chemical Peels", "blurb": "Come in for a personalized skin assessment.", "icon": "leaf"},
    ],
    "beauty_salon": [
        {"name": "Laser Hair Removal", "blurb": "Ask us if this treatment fits your goals.", "icon": "laser"},
        {"name": "Facials", "blurb": "Reserve a slot for a refreshing treatment.", "icon": "sparkle"},
        {"name": "Chemical Peels", "blurb": "Come in for a personalized skin assessment.", "icon": "leaf"},
        {"name": "Microneedling", "blurb": "Book a visit to talk through your options.", "icon": "needle"},
    ],
    "skin_care_clinic": [
        {"name": "HydraFacial", "blurb": "Reserve a slot for a refreshing treatment.", "icon": "sparkle"},
        {"name": "Chemical Peels", "blurb": "Come in for a personalized skin assessment.", "icon": "leaf"},
        {"name": "Microneedling", "blurb": "Book a visit to talk through your options.", "icon": "needle"},
        {"name": "Laser Skin Resurfacing", "blurb": "Schedule a consultation to see if it's right for you.", "icon": "laser"},
    ],
    "hair_removal_service": [
        {"name": "Laser Hair Removal", "blurb": "Ask us if this treatment fits your goals.", "icon": "laser"},
        {"name": "IPL / Photofacial", "blurb": "Reserve a slot for a refreshing treatment.", "icon": "sun"},
        {"name": "Facials", "blurb": "Book a visit to talk through your options.", "icon": "sparkle"},
        {"name": "Skin Tightening", "blurb": "Come in for a personalized skin assessment.", "icon": "leaf"},
    ],
}
_GENERIC_DEFAULT_SERVICES: list[dict[str, str]] = [
    {"name": "Botox / Neuromodulators", "blurb": "Schedule a consultation to see if it's right for you.", "icon": "syringe"},
    {"name": "Dermal Fillers", "blurb": "Book a visit to talk through your options.", "icon": "droplet"},
    {"name": "HydraFacial", "blurb": "Reserve a slot for a refreshing treatment.", "icon": "sparkle"},
    {"name": "Chemical Peels", "blurb": "Come in for a personalized skin assessment.", "icon": "leaf"},
]
_DEFAULT_TAGLINE = "Book your next visit online, anytime."


def _contains_forbidden(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in _FORBIDDEN_TERMS) or bool(_PRICE_RE.search(text))


def _default_services(primary_type: str | None) -> list[dict[str, str]]:
    key = (primary_type or "").strip().lower()
    return [dict(s) for s in _DEFAULT_SERVICES_BY_TYPE.get(key, _GENERIC_DEFAULT_SERVICES)]


def _validate_services(candidates: Any) -> list[dict[str, str]]:
    if not isinstance(candidates, list):
        return []
    out: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        name = candidate.get("name")
        icon = candidate.get("icon")
        blurb = candidate.get("blurb")
        if name not in ALLOWED_SERVICES or name in seen_names:
            continue
        if icon not in ALLOWED_ICONS:
            continue
        if not isinstance(blurb, str) or not blurb.strip():
            continue
        if _contains_forbidden(blurb):
            continue
        out.append({"name": name, "blurb": blurb.strip(), "icon": icon})
        seen_names.add(name)
        if len(out) == MAX_SERVICES:
            break
    return out


def _validate_tagline(tagline: Any) -> str | None:
    if not isinstance(tagline, str):
        return None
    stripped = tagline.strip()
    if not stripped:
        return None
    words = stripped.split()
    if len(words) > MAX_TAGLINE_WORDS:
        return None
    if _contains_forbidden(stripped):
        return None
    return stripped


def extract_services(
    business: dict,
    audit: dict | None,
    *,
    mock: bool,
    model: str = "claude-sonnet-5",
    fixtures_root: Path | None = None,
    prompt_path: Path | None = None,
) -> dict:
    """Call the extract_services prompt, validate its output, and fall back to defaults when it's too thin.

    Returns {"services": [3-8 valid entries], "tagline": str, "used_fallback": bool, "model_id",
    "prompt_sha256", "llm_cost_usd"}.
    """
    raw = (audit or {}).get("raw") or {}
    site_text = raw.get("site_text") or ""
    primary_type = business.get("primary_type") or "spa"
    business_name = business.get("name") or ""

    result = llm.call(
        "extract_services",
        prompt_path or PROMPT_PATH,
        {"site_text": site_text, "primary_type": primary_type, "business_name": business_name},
        model=model,
        mock=mock,
        fixtures_root=fixtures_root or DEFAULT_FIXTURES_ROOT,
    )

    try:
        parsed = json.loads(result["text"])
    except (json.JSONDecodeError, TypeError):
        parsed = {}

    services = _validate_services(parsed.get("services"))
    used_fallback = len(services) < MIN_VALID_SERVICES
    if used_fallback:
        services = _default_services(primary_type)

    tagline = _validate_tagline(parsed.get("tagline"))
    if tagline is None:
        tagline = _DEFAULT_TAGLINE

    return {
        "services": services,
        "tagline": tagline,
        "used_fallback": used_fallback,
        "model_id": result["model_id"],
        "prompt_sha256": result["prompt_sha256"],
        "llm_cost_usd": result["cost_usd"],
    }


def main() -> None:
    """description: Standalone CLI to run extraction against a business.json/audit.json pair.
    inputs: --business FILE, --audit FILE (optional), --mock, --model ID.
    outputs: stdout JSON {"services": [...], "tagline": ..., ...}.
    """
    config.bootstrap()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business", required=True, type=Path)
    parser.add_argument("--audit", type=Path, default=None)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--model", default="claude-sonnet-5")
    args = parser.parse_args()

    try:
        business = json.loads(args.business.read_text(encoding="utf-8"))
        audit = json.loads(args.audit.read_text(encoding="utf-8")) if args.audit else None
    except OSError as exc:
        print(json.dumps({"script": "extract_services", "in": 0, "out": 0, "error": str(exc)}))
        sys.exit(1)

    result = extract_services(business, audit, mock=args.mock, model=args.model)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
