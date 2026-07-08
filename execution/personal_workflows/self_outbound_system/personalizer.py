"""
personalizer.py
description: Generate per-lead subject + opener + body for cold outreach. Dry-run uses deterministic mocks derived from tone.json; live mode (STUB) would call Claude Sonnet 4.6 with prompt-cached system prompt. Subject/opener are hard-validated against tone.json constraints before write — leads that fail validation are refused with a machine-readable reason.
inputs: --input <path> (verified leads json), --config <path> (default: config/tone.json), --dry-run/--live, --llm <sonnet|gemini>, --output <path>. Env (live only): ANTHROPIC_API_KEY, GEMINI_API_KEY.
outputs: .tmp/self_outbound/personalized_leads_<timestamp>.json with subject/opener/body_html/body_text/variant/cost_eur_estimate per lead.

Reads directive: directives/personal_workflows/self_outbound_system.md (Phase 3 script #4).
Cost tracking is EUR per ~/.claude/rules/currency-eur.md.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    CONFIG_DIR,
    TMP_DIR,
    anthropic_cost_eur,
    ensure_tmp_dir,
    get_logger,
    load_json,
    print_stat,
    timestamp,
    write_json,
)

load_dotenv()
log = get_logger("personalizer")

# Segment -> variant mapping mirrors tone.json.variants[X].audience_segment
_SEGMENT_TO_VARIANT = {
    "founders_seed_to_a": "A",
    "sme_agency_owners": "B",
    "heads_of_product_ops": "C",
}


def _subject_ok(subject: str, constraints: dict) -> tuple[bool, str]:
    """Validate a subject line against tone.json.subject_constraints. Returns
    (ok, reason_if_not_ok)."""
    if not subject or not subject.strip():
        return False, "subject-empty"
    words = subject.split()
    if len(words) > constraints.get("max_words", 6):
        return False, "subject-too-long"
    # lowercase-first-letter
    if subject[0].isupper():
        return False, "subject-not-lowercase-first"
    # no punctuation at end
    if subject.rstrip().endswith(('.', '!', '?', ':', ';')):
        return False, "subject-trailing-punct"
    banned_starts = [s.lower() for s in constraints.get("banned_starts", [])]
    for bs in banned_starts:
        if subject.lower().startswith(bs.lower()):
            return False, f"subject-banned-start:{bs}"
    banned_words = [b.lower() for b in constraints.get("banned_words_case_insensitive", [])]
    lower_subj = subject.lower()
    for bw in banned_words:
        if bw in lower_subj:
            return False, f"subject-banned-word:{bw}"
    return True, ""


def _opener_ok(opener: str, constraints: dict, banned_buzzwords: list[str]) -> tuple[bool, str]:
    """Validate an opener line against tone.json.opener_constraints +
    voice.buzzwords_never_use."""
    if not opener or not opener.strip():
        return False, "opener-empty"
    words = opener.split()
    if len(words) > constraints.get("max_words", 15):
        return False, "opener-too-long"
    lower = opener.lower()
    for bw in banned_buzzwords:
        # word-boundary to avoid false positives like "leverages" inside prose
        if re.search(rf"\b{re.escape(bw.lower())}\b", lower):
            return False, f"opener-buzzword:{bw}"
    # No leaked template tokens
    if "{" in opener or "}" in opener:
        return False, "opener-unfilled-token"
    return True, ""


def personalize_dry_run(
    leads: list[dict],
    tone_cfg: dict,
) -> tuple[list[dict], list[dict], float]:
    """Deterministic mocks. subject = 'quick idea for <company>', opener = the
    first opener example from the matching variant with {company} substituted.
    No LLM call, no cost."""
    variants = tone_cfg.get("variants", {})
    banned_buzzwords = tone_cfg.get("voice", {}).get("buzzwords_never_use", [])
    opener_constraints = tone_cfg.get("opener_constraints", {})
    subject_constraints = tone_cfg.get("subject_constraints", {})

    personalized: list[dict] = []
    refused: list[dict] = []

    for lead in leads:
        segment = lead.get("segment") or lead.get("segment_hint")
        variant_key = _SEGMENT_TO_VARIANT.get(segment or "", "A")
        variant_cfg = variants.get(variant_key, {})
        company = lead.get("company", "the team")

        subject = f"quick idea for {company.lower()}"
        opener_template = (variant_cfg.get("opener_examples") or ["Noticed {company} shipping fast."])[0]
        opener = opener_template.replace("{company}", company).replace("{product}", company).replace("{agency}", company).replace("{role}", lead.get("title", "the role"))

        subj_ok, subj_reason = _subject_ok(subject, subject_constraints)
        opn_ok, opn_reason = _opener_ok(opener, opener_constraints, banned_buzzwords)
        if not subj_ok or not opn_ok:
            refused.append({"lead": lead, "reason": subj_reason or opn_reason})
            continue

        body_text = (
            f"{opener}\n\n"
            f"{tone_cfg.get('cta', {}).get('primary', '')}\n\n"
            "-- Debanjan\n"
            "ProdCraft -- https://prodcraft.fyi\n"
            "Unsubscribe: {{unsubscribe_link}}\n"
            "Postal: {{postal_address}}\n"
        )
        body_html = body_text.replace("\n", "<br/>")

        personalized.append(
            {
                **lead,
                "subject": subject,
                "opener": opener,
                "body_text": body_text,
                "body_html": body_html,
                "variant": variant_key,
                "cost_eur_estimate": 0.0,
                "personalizer": "dry_run",
            }
        )

    return personalized, refused, 0.0


def personalize_live(
    leads: list[dict],
    tone_cfg: dict,
    llm: str,
) -> tuple[list[dict], list[dict], float]:
    """Live personalization via LLM. STUBBED.
    Cost calc uses anthropic_cost_eur (cache-aware, EUR-native)."""
    # Placeholder cost estimate so the shape is right when this stub is filled
    # in: ~1200 input (cache_read after first call), ~200 output per lead.
    _ = anthropic_cost_eur(0, 0, 0, 0)  # ensure symbol used
    raise NotImplementedError(
        "Live personalization not implemented in this scaffold pass. "
        "See directive Phase 3.4: Sonnet 4.6 with 400-token cached system "
        "prompt from tone.json, ~€1.60/mo for 600 leads. Run --dry-run for now."
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[1])
    p.add_argument("--input", type=Path, required=True,
                   help="Path to verified leads JSON (from enricher.py).")
    p.add_argument("--config", type=Path, default=CONFIG_DIR / "tone.json",
                   help="Path to tone.json.")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", default=True,
                   help="Dry-run (default). Deterministic mocks, no LLM.")
    p.add_argument("--live", dest="dry_run", action="store_false",
                   help="Live mode. Calls Sonnet or Gemini per --llm.")
    p.add_argument("--llm", choices=["sonnet", "gemini"], default="sonnet",
                   help="LLM to use in live mode. Default: sonnet.")
    p.add_argument("--output", type=Path, default=None,
                   help="Override output path.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ensure_tmp_dir()

    payload = load_json(args.input)
    verified = payload.get("verified", []) if isinstance(payload, dict) else payload

    tone_cfg = load_json(args.config)

    if args.dry_run:
        personalized, refused, cost_eur = personalize_dry_run(verified, tone_cfg)
    else:
        personalized, refused, cost_eur = personalize_live(verified, tone_cfg, args.llm)

    out_path = args.output or (TMP_DIR / f"personalized_leads_{timestamp()}.json")
    write_json(
        out_path,
        {
            "personalized": personalized,
            "refused": refused,
            "cost_eur_total": round(cost_eur, 4),
            "dry_run": args.dry_run,
            "llm": args.llm,
        },
    )
    print_stat(
        "personalizer",
        {
            "input": len(verified),
            "personalized": len(personalized),
            "refused": len(refused),
            "cost_eur_total": round(cost_eur, 4),
            "dry_run": args.dry_run,
            "llm": args.llm,
            "output": str(out_path),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
