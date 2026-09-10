"""
draft_email.py
description: Render one outreach draft (subject + body) from a human-written template pool
    (prompts/email_touch_{1_a,1_b,1_c,2,3,4}.md) plus hard variables and, for touch 1 only, the
    two LLM-filled fuzzy variables (prompts/fuzzy_variables.md).
inputs: Imported by daily_queue.py: render_draft(store, settings, outreach_row=..., business=...,
    audit_row=..., preview_row=..., variant="auto", mock=bool, fixtures_root=Path). No CLI network
    calls of its own beyond common.llm.call.
outputs: {"subject": str, "body": str, "variant": "a"|"b"|"c"|None, "llm": envelope|None}.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from execution.personal_workflows.prodcraft_medspa.common import llm
from execution.personal_workflows.prodcraft_medspa.outreach import _store_helpers

PKG_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = PKG_ROOT / "prompts"
LLM_FIXTURES_ROOT = PROMPTS_DIR / "fixtures"  # prompts/fixtures/llm/{prompt_name}.txt, per prompts/README.md

_VARIANTS = ("a", "b", "c")
_FALLBACK_PROOF_LINE = "About 78% of med spa bookings still come in by phone."

_VAR_RE = re.compile(r"\{\{(\w+)\}\}")


def _template_path(touch: int, variant: str | None) -> Path:
    if touch == 1:
        return PROMPTS_DIR / f"email_touch_1_{variant}.md"
    return PROMPTS_DIR / f"email_touch_{touch}.md"


def _parse_template(text: str) -> tuple[dict[str, str], str, str]:
    """Split a template file into (front_matter, subject_template, body_template)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("template missing opening '---' front-matter delimiter")

    front_matter: dict[str, str] = {}
    i = 1
    while i < len(lines) and lines[i].strip() != "---":
        key, _, value = lines[i].partition(":")
        if key.strip():
            front_matter[key.strip()] = value.strip()
        i += 1
    if i >= len(lines):
        raise ValueError("template missing closing '---' front-matter delimiter")
    i += 1  # skip closing '---'

    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i >= len(lines) or not lines[i].lower().startswith("subject:"):
        raise ValueError("template missing 'subject:' line")
    subject_template = lines[i].split(":", 1)[1].strip()
    i += 1

    while i < len(lines) and lines[i].strip() == "":
        i += 1
    body_template = "\n".join(lines[i:]).strip("\n")

    return front_matter, subject_template, body_template


def _render(template: str, variables: dict[str, Any]) -> str:
    def _sub(match: re.Match) -> str:
        key = match.group(1)
        if key not in variables or variables[key] is None:
            return match.group(0)  # leave unresolved — lint_draft.py flags this
        return str(variables[key])

    return _VAR_RE.sub(_sub, template)


def pick_variant(store: Any, variant: str) -> str:
    """'a'/'b'/'c' pass through. 'auto' rotates a->b->c by count of touch-1 drafts so far."""
    if variant in _VARIANTS:
        return variant
    if variant != "auto":
        raise ValueError(f"unknown variant {variant!r}")
    touch1_drafted = [
        r
        for r in _store_helpers.list_all(store, "outreach")
        if int(r.get("touch") or 0) == 1 and r.get("template_variant")
    ]
    return _VARIANTS[len(touch1_drafted) % len(_VARIANTS)]


def _expires_on_weekday(expires_at: str | None, today: date | None = None) -> str:
    today = today or date.today()
    if not expires_at:
        return "Friday"
    try:
        expires_date = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00")).date()
    except ValueError:
        return "Friday"
    delta = (expires_date - today).days
    if delta < 0:
        return "Friday"
    if delta <= 6:
        return expires_date.strftime("%A")
    return f"{expires_date.strftime('%B')} {expires_date.day}"


def _proof_line(store: Any, touch: int) -> str:
    proof_lines = store.get_config("proof_lines", []) or []
    if not proof_lines:
        return _FALLBACK_PROOF_LINE
    prior_touch3plus = [
        r
        for r in _store_helpers.list_all(store, "outreach")
        if int(r.get("touch") or 0) >= 3 and r.get("draft_subject")
    ]
    return proof_lines[len(prior_touch3plus) % len(proof_lines)]


def _prev_touch_row(store: Any, business_id: str, touch: int) -> dict | None:
    for row in _store_helpers.outreach_for_business(store, business_id):
        if int(row.get("touch") or 0) == touch - 1:
            return row
    return None


def _loom_url(outreach_row: dict) -> str:
    notes_raw = outreach_row.get("notes")
    if notes_raw:
        try:
            notes = json.loads(notes_raw) if isinstance(notes_raw, str) else notes_raw
            if isinstance(notes, dict) and notes.get("loom_url"):
                return str(notes["loom_url"])
        except (json.JSONDecodeError, TypeError):
            pass
    return "[[LOOM URL]]"


def render_draft(
    store: Any,
    settings: Any,
    *,
    outreach_row: dict,
    business: dict,
    audit_row: dict | None,
    preview_row: dict | None,
    variant: str = "auto",
    mock: bool,
    fixtures_root: Path | None = None,
) -> dict:
    """Render one outreach draft. `fixtures_root` is the fuzzy_variables LLM mock fixtures dir
    (defaults to prompts/fixtures, per prompts/README.md — NOT the top-level fixtures/ dir)."""
    touch = int(outreach_row.get("touch") or 1)
    resolved_variant = pick_variant(store, variant) if touch == 1 else None
    template_path = _template_path(touch, resolved_variant)
    _front_matter, subject_template, body_template = _parse_template(
        template_path.read_text(encoding="utf-8")
    )

    sender = store.get_config("sender", {"name": "", "physical_address": "", "signature": ""}) or {}
    owner_first = business.get("owner_first") or "there"
    preview_url = (preview_row or {}).get("subdomain_url") or ""
    prev_row = _prev_touch_row(store, business["id"], touch) if touch > 1 else None
    prev_subject = (prev_row or {}).get("draft_subject") or ""

    hard_vars: dict[str, Any] = {
        "owner_first": owner_first,
        "business_name": business.get("name") or "",
        "preview_url": preview_url,
        "sender_name": sender.get("name") or "",
        "sender_physical_address": sender.get("physical_address") or "",
        "prev_subject": prev_subject,
        "loom_url": _loom_url(outreach_row),
        "proof_line": _proof_line(store, touch),
        "expires_on_weekday": _expires_on_weekday((preview_row or {}).get("expires_at")),
    }

    llm_envelope: dict | None = None
    if touch == 1:
        audit_row = audit_row or {}
        services = ((preview_row or {}).get("content") or {}).get("services", [])
        variables = {
            "gaps_json": json.dumps(audit_row.get("gaps") or []),
            "booking_widget": audit_row.get("booking_widget") or "null",
            "has_cta_above_fold": audit_row.get("has_cta_above_fold"),
            "psi_mobile": audit_row.get("psi_mobile"),
            "is_mobile_friendly": audit_row.get("is_mobile_friendly"),
            "business_name": business.get("name") or "",
            "services_json": json.dumps(services),
            "suburb": business.get("suburb") or business.get("city") or "",
        }
        llm_envelope = llm.call(
            "fuzzy_variables",
            PROMPTS_DIR / "fuzzy_variables.md",
            variables,
            model="claude-sonnet-5",
            mock=mock,
            fixtures_root=fixtures_root or LLM_FIXTURES_ROOT,
        )
        fuzzy = json.loads(llm_envelope["text"])
        hard_vars["oneSentenceSpecificBookingGapObservedOnTheirSite"] = fuzzy.get(
            "oneSentenceSpecificBookingGapObservedOnTheirSite", ""
        )
        hard_vars["fiveWordPlainDescriptionOfTheirBusiness"] = fuzzy.get(
            "fiveWordPlainDescriptionOfTheirBusiness", ""
        )

    subject = _render(subject_template, hard_vars)
    body = _render(body_template, hard_vars)

    return {
        "subject": subject,
        "body": body,
        "variant": resolved_variant,
        "llm": llm_envelope,
    }
