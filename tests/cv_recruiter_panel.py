"""
description: Simulate a 6-person recruitment panel scoring a CV PDF with Gemini 2.5 Flash.
inputs:
  --pdf <path>     : CV PDF to evaluate
  --lang {fr,en}   : language for persona prompts (FR personas read FR CVs)
  --model <name>   : Gemini model (default gemini-2.5-flash; falls back to flash-lite on 503)
outputs:
  - stdout: per-persona scores + aggregate verdict (PASS / FAIL + worst-disqualifier)
  - JSON sidecar at .tmp/cv_recruiter_panel/<pdf_stem>.json
  - exit 0 if panel passes (all >=85 AND >=4 personas >=90), else 1

Personas (operating as the hiring committee for a Senior AI PM role in Paris):
  CPO            — strategic positioning, P&L impact, C-suite readiness
  CTO            — technical depth, hands-on code evidence, system design
  CDO            — data products experience, governance, AI/ML evaluation rigor
  CHRO           — leadership, team-building, cross-cultural / bilingual signal
  CMO            — go-to-market, adoption numbers, customer-facing storytelling
  AI Researcher  — technical accuracy of LLM/RAG/MCP claims, research rigor

Each persona returns JSON: {score:0-100, would_callback:bool, top_strengths:[3],
top_concerns:[3], single_disqualifier:str}.

Aggregate rule: panel PASSES when MIN(scores) >= 85 AND count(scores>=90) >= 4.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("cv_recruiter_panel")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TMP_DIR = PROJECT_ROOT / ".tmp" / "cv_recruiter_panel"

PERSONAS = {
    "CPO": (
        "You are the Chief Product Officer at a Paris-based AI scale-up (Series B, ~150 staff). "
        "You hire Senior PMs / Head of Product. You scan a CV in 8 seconds for: clear strategic "
        "positioning, evidence of P&L / adoption impact, ability to operate cross-BU at C-suite "
        "level, GTM track record. You hate vague 'responsible for' bullets."
    ),
    "CTO": (
        "You are the CTO at a Paris-based AI scale-up. When you read a PM candidate's CV you "
        "check: do they actually understand the stack? Hands-on code evidence (GitHub, "
        "personal projects, real systems shipped)? You distrust 'tech-aware' PMs without "
        "shipped code. You appreciate audit-loops, typed contracts, observability."
    ),
    "CDO": (
        "You are the Chief Data Officer. You scan for: AI evaluation frameworks, governance "
        "(GDPR/AI Act, audit trails), data products experience, statistical literacy, ability "
        "to define eval metrics for non-deterministic systems. You reject candidates with "
        "fuzzy GenAI claims."
    ),
    "CHRO": (
        "You are the Chief HR Officer. You assess: leadership signals, team-building scale, "
        "cross-cultural fit, bilingual capability for a Paris HQ + EU/US delivery role, "
        "ability to influence without authority. Long unexplained gaps and job-hopping are "
        "red flags."
    ),
    "CMO": (
        "You are the Chief Marketing Officer. You look for: go-to-market storytelling, "
        "adoption numbers, customer-facing capability, ability to articulate value to "
        "enterprise buyers. You like specific BU-rollout metrics."
    ),
    "AI_Researcher": (
        "You are the top AI researcher in the company (ex-DeepMind / FAIR). You verify "
        "technical credibility: are the LLM/RAG/MCP/A2A claims plausible? Is the evaluation "
        "rigor real or theater? Are the personal projects substantive (audit loops, "
        "fingerprint failure detection, typed contracts) or surface-level demos?"
    ),
}


SCORING_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "would_callback": {"type": "boolean"},
        "top_strengths": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 5},
        "top_concerns": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 5},
        "single_disqualifier": {"type": "string"},
    },
    "required": ["score", "would_callback", "top_strengths", "top_concerns", "single_disqualifier"],
}


def _extract_pdf_text(pdf_path: Path) -> str:
    import pdfplumber  # type: ignore
    with pdfplumber.open(pdf_path) as p:
        return "\n".join((pg.extract_text() or "") for pg in p.pages)


def _build_prompt(persona_name: str, persona_brief: str, lang: str, cv_text: str) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lang_note = "Le CV est en français." if lang == "fr" else "The CV is in English."
    role = "Senior AI Product Manager (CDI, Paris)"
    return (
        f"You are evaluating a CV for a {role} opening. Persona: {persona_name}.\n"
        f"Today's date: {today}. (This is critical: any role with end-date <= {today} is in the PAST, "
        f"not the future. Do NOT flag past roles as 'future-dated'.)\n\n"
        f"Persona brief:\n{persona_brief}\n\n"
        f"{lang_note}\n\n"
        f"--- CV TEXT ---\n{cv_text[:8000]}\n--- END CV ---\n\n"
        "Score 0-100. Output JSON ONLY matching the schema:\n"
        '  {"score": <0-100>, "would_callback": <true|false>, '
        '"top_strengths": [<str>, <str>, <str>], '
        '"top_concerns": [<str>, <str>, <str>], '
        '"single_disqualifier": <str>}\n'
        "Reasoning must be concrete (reference actual CV lines). "
        "single_disqualifier = the ONE thing that, if fixed, would most raise the score; "
        "if score >= 95, write 'none'."
    )


def _call_gemini(client, model: str, prompt: str, fallback_model: str = "gemini-2.5-flash-lite"):
    from google.genai import types  # type: ignore
    cfg = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=SCORING_SCHEMA,
        temperature=0.2,
        max_output_tokens=1500,
    )
    last_exc: Exception | None = None
    for attempt in (1, 2, 3, 4):
        try:
            use = model if attempt < 3 else fallback_model
            resp = client.models.generate_content(model=use, contents=prompt, config=cfg)
            return resp.text or "{}", use
        except Exception as exc:  # noqa: BLE001 — degrade after retries
            last_exc = exc
            msg = str(exc)
            if not any(k in msg for k in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED")):
                logger.warning("Gemini non-retryable error: %s", exc)
                return "", model
            time.sleep(3.0 * attempt)
    logger.warning("Gemini unavailable after retries; returning empty. Last: %s", last_exc)
    return "", model


def score_panel(pdf_path: Path, lang: str, model: str = "gemini-2.5-flash") -> dict:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY missing in .env")
    from google import genai  # type: ignore
    client = genai.Client(api_key=api_key)

    cv_text = _extract_pdf_text(pdf_path)
    results: dict[str, dict] = {}

    import re as _re
    for persona_name, brief in PERSONAS.items():
        prompt = _build_prompt(persona_name, brief, lang, cv_text)
        data = None
        used_model = model
        for parse_attempt in (1, 2, 3):
            raw, used_model = _call_gemini(client, model, prompt)
            try:
                data = json.loads(raw)
                break
            except json.JSONDecodeError as exc:
                # Try to recover JSON via regex extraction (handles wrapper text)
                m = _re.search(r"\{.*\}", raw, _re.DOTALL)
                if m:
                    try:
                        data = json.loads(m.group(0))
                        logger.info("%s: recovered JSON via regex on attempt %d", persona_name, parse_attempt)
                        break
                    except json.JSONDecodeError:
                        pass
                logger.warning("%s [attempt %d]: parse failed (%s); raw len=%d, first 200=%r",
                               persona_name, parse_attempt, exc, len(raw), raw[:200])
                time.sleep(2.0)
        if data is None:
            data = {
                "score": 70, "would_callback": False,
                "top_strengths": ["parse error"], "top_concerns": ["parse error"],
                "single_disqualifier": "ranker JSON parse failure after 3 attempts",
            }
        data["_model"] = used_model
        results[persona_name] = data
        logger.info("%s: score=%d would_callback=%s", persona_name, data.get("score", 0), data.get("would_callback"))
        time.sleep(2.5)  # throttle for 10 RPM with margin

    return results


def aggregate(results: dict[str, dict]) -> dict:
    scores = {n: int(r.get("score", 0)) for n, r in results.items()}
    min_score = min(scores.values()) if scores else 0
    n_ge90 = sum(1 for s in scores.values() if s >= 90)
    n_ge85 = sum(1 for s in scores.values() if s >= 85)
    passes = (min_score >= 85) and (n_ge90 >= 4)

    # Lowest-scorer's disqualifier becomes the mutation hint for the next anneal round
    lowest_persona = min(scores, key=scores.get)
    mutation_hint = results[lowest_persona].get("single_disqualifier", "")

    return {
        "pass": passes,
        "min_score": min_score,
        "n_personas_at_90_or_above": n_ge90,
        "n_personas_at_85_or_above": n_ge85,
        "lowest_persona": lowest_persona,
        "mutation_hint": mutation_hint,
        "all_scores": scores,
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="6-persona Gemini panel scorer for a CV PDF.")
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--lang", choices=["fr", "en"], default="fr")
    parser.add_argument("--model", default="gemini-2.5-flash")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"ERROR: PDF not found at {args.pdf}", file=sys.stderr)
        return 2

    results = score_panel(args.pdf, args.lang, model=args.model)
    summary = aggregate(results)

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    out_path = args.out or (TMP_DIR / f"{args.pdf.stem}.json")
    payload = {
        "pdf": str(args.pdf),
        "lang": args.lang,
        "model": args.model,
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
        "summary": summary,
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Panel report: {out_path}")
    print(f"Pass         : {summary['pass']}")
    print(f"Min score    : {summary['min_score']}")
    print(f"#>=90        : {summary['n_personas_at_90_or_above']}/6")
    print(f"All scores   : {summary['all_scores']}")
    if not summary["pass"]:
        print(f"Lowest       : {summary['lowest_persona']}")
        print(f"Mutation hint: {summary['mutation_hint']}")

    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
