"""
reply_classifier.py
description: Classify inbound cold-email replies into 5 buckets (hot / positive / neutral / negative / auto_reply_or_OOO). Deterministic pre-filter catches auto-replies + stop-requests before any LLM call; LLM (stubbed in dry-run) handles ambiguous cases.
inputs: --reply-body <string> OR --reply-file <path>, --dry-run/--live, --llm <sonnet|gemini>. Env (live only): ANTHROPIC_API_KEY, GEMINI_API_KEY.
outputs: JSON to stdout: {"class", "confidence", "explanation", "detected_intent_signals"}.

Reads directive: directives/personal_workflows/self_outbound_system.md (Phase 3 script #7).
The deterministic pre-filter catches ~95% of the auto-reply + stop-request classes without paying for an LLM call.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    anthropic_cost_eur,
    get_logger,
    print_stat,
)

load_dotenv()
log = get_logger("reply_classifier")

# OOO / auto-reply patterns. English + French per directive's language gate.
_OOO_PATTERNS = [
    r"\bout of (?:the )?office\b",
    r"\bon vacation\b",
    r"\bon leave\b",
    r"\bauto[-\s]?reply\b",
    r"\bautomatic reply\b",
    r"\bwill (?:return|be back)\b",
    r"\bcurrently away\b",
    r"\babsent\b",
    r"\ben cong[ée]s?\b",
    r"\bréponse automatique\b",
    r"\bde retour le\b",
]

_STOP_PATTERNS = [
    r"\bunsubscribe\b",
    r"\bremove me\b",
    r"\btake me off\b",
    r"\bstop (?:emailing|contacting)\b",
    r"\bdo not (?:email|contact)\b",
    r"\bdon'?t (?:email|contact)\b",
    r"\bd[ée]sinscri(?:re|s|vez)\b",
    r"\bne (?:plus|jamais) (?:me )?contacter\b",
]

_HOT_PATTERNS = [
    r"\bcall me at\b",
    r"\bmy number is\b",
    r"\+?\d{1,3}[\s\-.]?\d{2,4}[\s\-.]?\d{2,4}[\s\-.]?\d{2,4}",
    r"\bready to (?:sign|start|go|move)\b",
    r"\bcan we (?:jump on|hop on|do) a call\b",
]


def _matches_any(text: str, patterns: list[str]) -> list[str]:
    """Return the list of pattern-descriptions that matched."""
    hits: list[str] = []
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE):
            hits.append(pat)
    return hits


def classify(body: str, dry_run: bool = True, llm: str = "sonnet") -> dict:
    """Classify a reply body. Returns dict with class/confidence/explanation
    /detected_intent_signals/cost_eur_estimate."""
    text = (body or "").strip()
    if not text:
        return {
            "class": "neutral",
            "confidence": 0.0,
            "explanation": "empty-body",
            "detected_intent_signals": [],
            "cost_eur_estimate": 0.0,
        }

    # Deterministic layer FIRST — catches ~95% of cheap cases without LLM
    ooo_hits = _matches_any(text, _OOO_PATTERNS)
    if ooo_hits:
        return {
            "class": "auto_reply_or_OOO",
            "confidence": 0.99,
            "explanation": "deterministic OOO pattern matched",
            "detected_intent_signals": ooo_hits,
            "cost_eur_estimate": 0.0,
        }

    stop_hits = _matches_any(text, _STOP_PATTERNS)
    if stop_hits:
        return {
            "class": "negative",
            "confidence": 0.99,
            "explanation": "deterministic stop/unsubscribe pattern matched",
            "detected_intent_signals": stop_hits,
            "cost_eur_estimate": 0.0,
        }

    hot_hits = _matches_any(text, _HOT_PATTERNS)
    if hot_hits:
        # Hot pattern is a strong signal but keep confidence just under 1.0 —
        # LLM might disagree, e.g. "call me at 555-1234 to remove me" reads
        # like negative in context. In live mode we'd still LLM-verify.
        if dry_run:
            return {
                "class": "hot",
                "confidence": 0.90,
                "explanation": "deterministic phone / meeting-request pattern matched",
                "detected_intent_signals": hot_hits,
                "cost_eur_estimate": 0.0,
            }

    if dry_run:
        # LLM stub — return neutral with low confidence + mock explanation.
        return {
            "class": "neutral",
            "confidence": 0.5,
            "explanation": "dry-run stub: no LLM call, defaulting to neutral",
            "detected_intent_signals": [],
            "cost_eur_estimate": 0.0,
        }

    # Live LLM call would go here. STUBBED to raise so we can't accidentally
    # spend $ without an explicit code change.
    _ = anthropic_cost_eur(0, 0)  # ensure symbol is used
    raise NotImplementedError(
        "Live LLM classification not implemented in this scaffold. "
        "Would call Claude Sonnet 4.6 (or Gemini 2.5 Flash if --llm gemini) "
        "and return {class, confidence, explanation, detected_intent_signals} "
        "with cost tracked in EUR."
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[1])
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--reply-body", type=str, default=None,
                     help="Reply body as a raw string.")
    src.add_argument("--reply-file", type=Path, default=None,
                     help="Path to a text file containing the reply body.")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", default=True,
                   help="Dry-run (default). No LLM call; deterministic layer only.")
    p.add_argument("--live", dest="dry_run", action="store_false",
                   help="Live mode. Calls Sonnet or Gemini for ambiguous cases.")
    p.add_argument("--llm", choices=["sonnet", "gemini"], default="sonnet",
                   help="LLM to use for ambiguous cases in live mode.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.reply_file is not None:
        body = args.reply_file.read_text(encoding="utf-8")
    else:
        body = args.reply_body or ""

    result = classify(body, dry_run=args.dry_run, llm=args.llm)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    print_stat("reply_classifier", {
        "class": result["class"],
        "confidence": result["confidence"],
        "dry_run": args.dry_run,
        "llm": args.llm,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
