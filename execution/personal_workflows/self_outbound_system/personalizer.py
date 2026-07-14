"""
personalizer.py
description: Generate per-lead subject + full-body email for cold outreach applying Nick Saraev's 4-step framework (personalization -> who am I -> offer -> CTA). Dry-run uses deterministic mocks drawn from tone.json v2 (with give_first / who_am_i / offer / cta_time_proposals slots). Live mode (STUB) calls Sonnet 4.6 with cached system prompt. Subject/opener are hard-validated against tone.json constraints; leads whose fields fail are refused with a machine-readable reason.
inputs: --input <path> (verified leads json), --config <path> (default: config/tone.json), --dry-run/--live, --llm <sonnet|gemini>, --output <path>. Env (live only): ANTHROPIC_API_KEY, GEMINI_API_KEY, CAL_COM_BOOKING_URL.
outputs: .tmp/self_outbound/personalized_leads_<timestamp>.json with subject/opener/body_html/body_text/variant/cost_eur_estimate per lead.

Reads directive: directives/personal_workflows/self_outbound_system.md (Phase 3 script #4).
Framework source: deliverables/self_outbound_system/nick_saraev_cold_email_full_analysis.md.
Cost tracking is EUR per ~/.claude/rules/currency-eur.md.
"""

from __future__ import annotations

import argparse
import json
import os
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

_TOKEN_RE = re.compile(r"\{([a-z_]+)\}")


def _first_name(full: str) -> str:
    """Nick's first-word trick: split on space, take first token. Handles
    'Sarah Chen' -> 'Sarah'. Also strips scraper cruft like 'Nick Sunrise
    Daily Updates' -> 'Nick'."""
    if not full:
        return "there"
    return full.strip().split()[0]


def _substitute(template: str, lead: dict, cal_com_url: str) -> str:
    """Substitute {first_name}, {company}, {topic}, {role}, {product},
    {source}, {cal_com_url} tokens from lead fields. Missing fields fall back
    to sensible defaults so no {token} leaks through."""
    fills = {
        "first_name": _first_name(lead.get("name", "")),
        "company": lead.get("company") or "your team",
        "topic": lead.get("topic") or lead.get("notes", "").split(".")[0][:40] or "your recent work",
        "role": lead.get("title") or "the role",
        "product": lead.get("product") or lead.get("company") or "the product",
        "source": lead.get("source") or "LinkedIn",
        "cal_com_url": cal_com_url,
    }

    def replace(match: re.Match) -> str:
        return fills.get(match.group(1), match.group(0))

    return _TOKEN_RE.sub(replace, template)


def _subject_ok(subject: str, constraints: dict) -> tuple[bool, str]:
    """Validate a subject line against tone.json.subject_constraints. Returns
    (ok, reason_if_not_ok)."""
    if not subject or not subject.strip():
        return False, "subject-empty"
    words = subject.split()
    if len(words) > constraints.get("max_words", 6):
        return False, "subject-too-long"
    if subject[0].isupper():
        return False, "subject-not-lowercase-first"
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
        if re.search(rf"\b{re.escape(bw.lower())}\b", lower):
            return False, f"opener-buzzword:{bw}"
    if "{" in opener or "}" in opener:
        return False, "opener-unfilled-token"
    return True, ""


def _pick(examples: list[str], lead: dict) -> str:
    """Deterministic pick: hash lead.email into a stable index. Same lead gets
    same variant across re-runs, but leads are spread across all examples."""
    if not examples:
        return ""
    seed = sum(ord(c) for c in (lead.get("email") or "seed")) % len(examples)
    return examples[seed]


def _assemble_body(
    lead: dict,
    variant_cfg: dict,
    tone_cfg: dict,
    cal_com_url: str,
) -> tuple[str, str]:
    """Assemble the full body applying Nick's 4-step framework:
    personalization opener -> give-first -> who I am -> offer -> CTA time proposal.
    Returns (body_text, opener_used_for_validation)."""
    opener_tpl = _pick(variant_cfg.get("opener_examples", []), lead)
    give_tpl = _pick(variant_cfg.get("give_first_examples", []), lead)
    who_tpl = _pick(variant_cfg.get("who_am_i_examples", []), lead)
    offer_tpl = _pick(variant_cfg.get("offer_examples", []), lead)
    cta_tpl = _pick(variant_cfg.get("cta_time_proposals", []), lead)

    # Fallback to global cta.primary if variant has no cta_time_proposals
    if not cta_tpl:
        cta_tpl = tone_cfg.get("cta", {}).get("primary", "")

    opener = _substitute(opener_tpl, lead, cal_com_url)
    give = _substitute(give_tpl, lead, cal_com_url) if give_tpl else ""
    who = _substitute(who_tpl, lead, cal_com_url) if who_tpl else ""
    offer = _substitute(offer_tpl, lead, cal_com_url) if offer_tpl else ""
    cta = _substitute(cta_tpl, lead, cal_com_url)

    signature_lines = []
    sig_cfg = tone_cfg.get("signature", {})
    sender_name = sig_cfg.get("sender_name", "Debanjan")
    sender_line_2 = sig_cfg.get("sender_line_2", "")
    signature_lines.append(f"-- {sender_name}")
    if sender_line_2:
        signature_lines.append(sender_line_2)

    # Body composition — every slot on its own line/paragraph for scannability
    parts = [
        f"Hi {_first_name(lead.get('name', ''))},",
        "",
        opener,
    ]
    if give:
        parts.append("")
        parts.append(give)
    if who:
        parts.append("")
        parts.append(who)
    if offer:
        parts.append("")
        parts.append(offer)
    parts.append("")
    parts.append(cta)
    parts.append("")
    parts.extend(signature_lines)
    parts.append("")
    parts.append("Unsubscribe: {{unsubscribe_link}}")
    parts.append("Postal: {{postal_address}}")

    body_text = "\n".join(parts)
    return body_text, opener


def personalize_dry_run(
    leads: list[dict],
    tone_cfg: dict,
) -> tuple[list[dict], list[dict], float]:
    """Deterministic mocks. Body assembled from tone.json.variants[X] using all
    5 slots (opener/give/who/offer/cta) per Nick's 4-step framework.
    No LLM call, no cost."""
    variants = tone_cfg.get("variants", {})
    banned_buzzwords = tone_cfg.get("voice", {}).get("buzzwords_never_use", [])
    opener_constraints = tone_cfg.get("opener_constraints", {})
    subject_constraints = tone_cfg.get("subject_constraints", {})
    cal_com_url = os.environ.get("CAL_COM_BOOKING_URL", "https://cal.com/debanjanm/30min")

    personalized: list[dict] = []
    refused: list[dict] = []

    for lead in leads:
        segment = lead.get("segment") or lead.get("segment_hint")
        variant_key = _SEGMENT_TO_VARIANT.get(segment or "", "A")
        variant_cfg = variants.get(variant_key, {})

        subject_tpl = _pick(variant_cfg.get("subject_examples", []), lead)
        subject = _substitute(subject_tpl, lead, cal_com_url).lower()

        body_text, opener = _assemble_body(lead, variant_cfg, tone_cfg, cal_com_url)

        subj_ok, subj_reason = _subject_ok(subject, subject_constraints)
        opn_ok, opn_reason = _opener_ok(opener, opener_constraints, banned_buzzwords)
        if not subj_ok or not opn_ok:
            refused.append({"lead": lead, "reason": subj_reason or opn_reason})
            continue

        body_html = body_text.replace("\n", "<br/>")

        personalized.append(
            {
                **lead,
                "subject": subject,
                "opener": opener,
                "body_text": body_text,
                "body_html": body_html,
                "variant": variant_key,
                "word_count": len(body_text.split()),
                "cost_eur_estimate": 0.0,
                "personalizer": "dry_run",
            }
        )

    return personalized, refused, 0.0


_SONNET_MODEL = "claude-sonnet-4-5"  # workspace default per model-tier.md; auto-updates to latest Sonnet

# System prompt applies Nick Saraev's 4-step + 7-principle framework per
# ~/deliverables/self_outbound_system/nick_saraev_cold_email_full_analysis.md.
# Cached (>1024 tokens after tone_cfg dump) so subsequent leads pay 0.1x for
# input tokens. Per Nick's Hour 4 AI doctrine, AI fills ONE variable at a
# time inside a human-written sentence — NEVER writes the whole email.
_LIVE_SYSTEM_INSTRUCTION = """You are helping Debanjan, a senior AI product engineer in Paris, personalize cold outreach emails to prospects. Your ONLY job is to fill a small number of specific variables inside pre-written templates. You do NOT write full emails.

Non-negotiable rules (from Nick Saraev's cold email framework):
1. Never signal selling in the personalization line — it's an observation, not a pitch.
2. Personalization line is ONE sentence, MAX 22 words, based on a real specific fact about the prospect (their post, their company, their launch, their hire).
3. Give-first line is ONE sentence, MAX 25 words, offers a concrete observation or spotted gap. Never asks for their time. Never says "value" or "thoughts".
4. Casualize company names — strip legal suffixes (LLC, Inc, SAS, Technologies), use internal shorthand (Palantir Technologies -> Palantir, Pacific Creative Group LLC -> PCG).
5. Never brand yourself as AI/robot/agent. Sound like a human friend who did research.
6. Use "I" never "we". Casual tone — TLDR, no strings, IMO, IDK allowed. No "hope this finds you well", no "quick chat", no "quick call".
7. No corporate acronyms with hyphens ("AI-driven X-Y-Z"). No hedging ("I could probably", "maybe I can").
8. Match the prospect's language (English or French). Default to English unless the prospect's headline or notes are clearly French.

Output STRICT JSON with exactly these 4 keys (no other keys, no prose):
{
  "personalization_line": "one sentence, max 22 words, observation not pitch",
  "give_first_line": "one sentence, max 25 words, concrete spotted-gap or shared insight",
  "casualized_company": "short internal-shorthand version of company name",
  "first_name_override": "first name only, or empty string if the name field is already just the first name"
}

If the prospect data is too thin to write a specific personalization, use a general-but-plausible cold reading based on their title and company (per Nick's rewrites in Hour 3 — 'Kashif' cold-reading example)."""


def _build_system_blocks(tone_cfg: dict) -> list[dict]:
    """Build Anthropic's structured system prompt with a cache_control breakpoint
    so the tone.json + framework instruction is cached across calls."""
    # Serialize the tone.json v2 slots we actually reference so the model has
    # full context on our voice, banned words, and example content.
    tone_snippet = {
        "voice": tone_cfg.get("voice", {}),
        "opener_constraints": tone_cfg.get("opener_constraints", {}),
        "subject_constraints": tone_cfg.get("subject_constraints", {}),
        "give_first_constraints": tone_cfg.get("give_first_constraints", {}),
        "variants": {
            k: {
                "positioning": v.get("positioning", ""),
                "opener_examples": v.get("opener_examples", []),
                "give_first_examples": v.get("give_first_examples", []),
            }
            for k, v in tone_cfg.get("variants", {}).items()
        },
    }
    system_text = (
        _LIVE_SYSTEM_INSTRUCTION
        + "\n\n---\n\nOur tone + variant reference (do not deviate):\n\n```json\n"
        + json.dumps(tone_snippet, ensure_ascii=False, indent=2)
        + "\n```\n"
    )
    return [
        {
            "type": "text",
            "text": system_text,
            "cache_control": {"type": "ephemeral"},
        }
    ]


def _user_prompt_for_lead(lead: dict, variant_key: str) -> str:
    """Compact per-lead prompt — everything the model needs to fill the 4
    variables, and nothing else."""
    return (
        f"Prospect (segment variant {variant_key}):\n"
        f"- Name: {lead.get('name', '')}\n"
        f"- Title: {lead.get('title', '')}\n"
        f"- Company: {lead.get('company', '')}\n"
        f"- LinkedIn: {lead.get('linkedin_url', '')}\n"
        f"- Notes / research signal: {lead.get('notes', '')}\n"
        f"- Domain: {lead.get('domain', '')}\n\n"
        "Return the 4-key JSON described in the system prompt. STRICT JSON only, "
        "no code fence, no prose."
    )


def _parse_ai_response(text: str) -> dict:
    """Extract the 4-key JSON from the model's response. Tolerant of code
    fences and pre/post whitespace."""
    s = text.strip()
    # Strip a ```json ... ``` fence if the model added one
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```\s*$", "", s)
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        # Last-ditch: find the first {...} block
        m = re.search(r"\{.*\}", s, flags=re.DOTALL)
        if not m:
            raise
        obj = json.loads(m.group(0))
    return obj


def personalize_live(
    leads: list[dict],
    tone_cfg: dict,
    llm: str,
) -> tuple[list[dict], list[dict], float]:
    """Live personalization via Sonnet 4.6 with prompt-cached system prompt.
    Per Nick's Hour 4 AI doctrine: AI fills ONE variable at a time inside a
    human-written sentence — NEVER writes the whole email.

    Cost model: ~1200-1500 cached input tokens (system) + ~300 fresh input
    tokens (per-lead user prompt) + ~200 output tokens. First lead pays
    cache-write on the system; subsequent leads pay cache-read (0.1x).

    Per-lead cost estimate: ~EUR 0.003 (post-cache). 100 leads ~= EUR 0.30-0.50.
    """
    if llm not in {"sonnet", "gemini"}:
        raise NotImplementedError(
            f"live LLM {llm!r} not wired. Supported: 'sonnet' (Anthropic), 'gemini' (Google, free tier)."
        )

    # Client init: pick SDK per llm choice. Per model-tier.md cost-constraint
    # clause, Gemini 2.5 Flash is the free fallback when Anthropic budget
    # is exhausted.
    client = None
    gemini_client = None
    if llm == "sonnet":
        try:
            import anthropic
        except ImportError as e:
            raise RuntimeError("anthropic SDK missing. pip install anthropic") from e
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set in env — required for live sonnet path")
        client = anthropic.Anthropic(api_key=api_key)
    else:  # gemini
        try:
            from google import genai as _genai  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "google-genai SDK missing. pip install google-genai"
            ) from e
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_key:
            raise RuntimeError("GEMINI_API_KEY not set in env — required for live gemini path")
        gemini_client = _genai.Client(api_key=gemini_key)
    variants = tone_cfg.get("variants", {})
    banned_buzzwords = tone_cfg.get("voice", {}).get("buzzwords_never_use", [])
    opener_constraints = tone_cfg.get("opener_constraints", {})
    subject_constraints = tone_cfg.get("subject_constraints", {})
    cal_com_url = os.environ.get("CAL_COM_BOOKING_URL", "https://cal.com/debanjanm/30min")

    system_blocks = _build_system_blocks(tone_cfg)

    personalized: list[dict] = []
    refused: list[dict] = []
    total_cost_eur = 0.0
    total_input = total_output = total_cache_read = total_cache_write = 0

    for i, lead in enumerate(leads):
        segment = lead.get("segment") or lead.get("segment_hint")
        variant_key = _SEGMENT_TO_VARIANT.get(segment or "", "A")
        variant_cfg = variants.get(variant_key, {})

        user_prompt = _user_prompt_for_lead(lead, variant_key)

        text = ""
        try:
            if llm == "sonnet":
                resp = client.messages.create(
                    model=_SONNET_MODEL,
                    max_tokens=400,
                    system=system_blocks,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                usage = resp.usage
                in_tok = getattr(usage, "input_tokens", 0)
                out_tok = getattr(usage, "output_tokens", 0)
                cr_tok = getattr(usage, "cache_read_input_tokens", 0) or 0
                cw_tok = getattr(usage, "cache_creation_input_tokens", 0) or 0
                this_cost = anthropic_cost_eur(in_tok, out_tok, cr_tok, cw_tok)
                text = resp.content[0].text
            else:  # gemini
                # Gemini API: combine system + user in one contents call.
                # Free tier: 250 req/day, 10 req/min — well under the 100-lead budget.
                system_text = system_blocks[0]["text"] if system_blocks else ""
                combined = system_text + "\n\n---\n\n" + user_prompt
                g_resp = gemini_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=combined,
                )
                text = g_resp.text or ""
                # Rough token estimate for stats (Gemini free tier has no cost)
                in_tok = len(combined) // 4
                out_tok = len(text) // 4
                cr_tok = cw_tok = 0
                this_cost = 0.0
        except Exception as e:  # noqa: BLE001
            # Non-swallow: log + refuse the lead, keep going with the batch.
            log.error(f"live {llm} call failed for lead {i} ({lead.get('email')}): {e}")
            refused.append({"lead": lead, "reason": f"{llm}-error:{type(e).__name__}"})
            continue

        total_cost_eur += this_cost
        total_input += in_tok
        total_output += out_tok
        total_cache_read += cr_tok
        total_cache_write += cw_tok

        # Parse the JSON output — tolerant of code fences
        try:
            ai_fields = _parse_ai_response(text)
        except (json.JSONDecodeError, ValueError) as e:
            log.error(f"could not parse {llm} response for lead {i}: {e}. Raw: {text[:200]}")
            refused.append({"lead": lead, "reason": f"parse-error:{type(e).__name__}"})
            continue

        # Enrich the lead with AI variables for downstream substitution
        enriched_lead = {**lead}
        if ai_fields.get("first_name_override"):
            enriched_lead["_first_name_override"] = ai_fields["first_name_override"]
        if ai_fields.get("casualized_company"):
            enriched_lead["_casual_company"] = ai_fields["casualized_company"]

        # Use AI's personalization/give lines in place of the templates
        # (still route through _substitute to fill any remaining tokens)
        personalization = _substitute(
            ai_fields.get("personalization_line", ""), enriched_lead, cal_com_url
        )
        give = _substitute(
            ai_fields.get("give_first_line", ""), enriched_lead, cal_com_url
        )

        # Static templates for the rest (who am I, offer, cta) — AI does NOT touch these
        who = _substitute(
            _pick(variant_cfg.get("who_am_i_examples", []), enriched_lead),
            enriched_lead, cal_com_url,
        )
        offer = _substitute(
            _pick(variant_cfg.get("offer_examples", []), enriched_lead),
            enriched_lead, cal_com_url,
        )
        cta = _substitute(
            _pick(variant_cfg.get("cta_time_proposals", []), enriched_lead),
            enriched_lead, cal_com_url,
        )

        # Subject line (deterministic pick, not AI-generated)
        subject_tpl = _pick(variant_cfg.get("subject_examples", []), enriched_lead)
        subject = _substitute(subject_tpl, enriched_lead, cal_com_url).lower()

        # Validate
        subj_ok, subj_reason = _subject_ok(subject, subject_constraints)
        opn_ok, opn_reason = _opener_ok(personalization, opener_constraints, banned_buzzwords)
        if not subj_ok or not opn_ok:
            refused.append({"lead": lead, "reason": subj_reason or opn_reason,
                            "ai_output": ai_fields})
            continue

        # Assemble body — same shape as dry-run
        signature_lines = []
        sig_cfg = tone_cfg.get("signature", {})
        sender_name = sig_cfg.get("sender_name", "Debanjan")
        sender_line_2 = sig_cfg.get("sender_line_2", "")
        signature_lines.append(f"-- {sender_name}")
        if sender_line_2:
            signature_lines.append(sender_line_2)

        first_name = enriched_lead.get("_first_name_override") or _first_name(lead.get("name", ""))
        parts = [f"Hi {first_name},", "", personalization]
        if give:
            parts.append("")
            parts.append(give)
        if who:
            parts.append("")
            parts.append(who)
        if offer:
            parts.append("")
            parts.append(offer)
        parts.append("")
        parts.append(cta)
        parts.append("")
        parts.extend(signature_lines)
        parts.append("")
        parts.append("Unsubscribe: {{unsubscribe_link}}")
        parts.append("Postal: {{postal_address}}")
        body_text = "\n".join(parts)
        body_html = body_text.replace("\n", "<br/>")

        personalized.append({
            **lead,
            "subject": subject,
            "opener": personalization,
            "body_text": body_text,
            "body_html": body_html,
            "variant": variant_key,
            "word_count": len(body_text.split()),
            "cost_eur_estimate": round(this_cost, 5),
            "ai_fields": ai_fields,
            "personalizer": "live_sonnet",
        })

    log.info(
        f"live {llm}: {len(personalized)} personalized, {len(refused)} refused. "
        f"Tokens: in={total_input} out={total_output} cache_read={total_cache_read} "
        f"cache_write={total_cache_write}. Cost: EUR {total_cost_eur:.4f}"
    )
    return personalized, refused, round(total_cost_eur, 4)


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
