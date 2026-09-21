"""
vision.py
description: Claude vision pass over the mobile/desktop screenshots -> dated_score + rationale + signals.
inputs: Imported by audit_site.py; prompts/vision_audit.md rendered with business_name/final_url.
outputs: dict of vision_dated_score/vision_rationale/vision_model_id/vision_prompt_sha256 (+ raw signals).
"""

from __future__ import annotations

import json
from pathlib import Path

from execution.personal_workflows.prodcraft_medspa.common import llm

VISION_MODEL = "claude-fable-5-1"
PROMPT_NAME = "vision_audit"
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = PACKAGE_ROOT / "prompts" / "vision_audit.md"
FIXTURES_ROOT = PACKAGE_ROOT / "prompts" / "fixtures"


class VisionParseError(ValueError):
    """The model's response was not the strict JSON object the prompt requires."""


def _parse_response(text: str) -> dict:
    stripped = text.strip()
    # The prompt forbids markdown fences, but tolerate them defensively — a fence around
    # otherwise-valid JSON is a cheap, common failure mode not worth hard-failing the audit on.
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:]
        stripped = stripped.strip()

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise VisionParseError(f"vision_audit response was not valid JSON: {exc}") from exc

    if "dated_score" not in data:
        raise VisionParseError("vision_audit response missing 'dated_score'")

    score = data["dated_score"]
    if not isinstance(score, int) or not (0 <= score <= 10):
        raise VisionParseError(f"dated_score must be an int 0..10, got {score!r}")

    return data


def run_vision_audit(
    business_name: str,
    final_url: str,
    mobile_png: bytes | None,
    desktop_png: bytes | None,
    *,
    mock: bool,
) -> dict:
    """Run the vision_audit prompt over the two screenshots. Returns the parsed envelope + score fields.

    Raises VisionParseError if the model's output isn't the strict JSON the prompt requires
    (caller decides whether that's fatal for the whole audit row or just this signal).
    """
    images = [img for img in (mobile_png, desktop_png) if img]
    envelope = llm.call(
        PROMPT_NAME,
        PROMPT_PATH,
        {"business_name": business_name, "final_url": final_url},
        model=VISION_MODEL,
        mock=mock,
        images=images,
        fixtures_root=FIXTURES_ROOT,
    )
    parsed = _parse_response(envelope["text"])

    return {
        "vision_dated_score": parsed["dated_score"],
        "vision_rationale": parsed.get("rationale"),
        "vision_model_id": envelope["model_id"],
        "vision_prompt_sha256": envelope["prompt_sha256"],
        "vision_signals": parsed.get("signals", []),
        "cost_usd": envelope["cost_usd"],
        "usage": envelope["usage"],
    }
