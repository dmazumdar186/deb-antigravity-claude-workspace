"""
reply_classifier.py
description: Classify inbound cold-email replies into 5 buckets (hot / positive / neutral / negative / auto_reply_or_OOO). A deterministic rule layer runs on the reply text with quoted thread history stripped; the LLM (stubbed) handles whatever no rule catches. Stop requests are written to config/suppression.json via apply_opt_out().
inputs: --reply-body <string> OR --reply-file <path>, --subject <str>, --header "Name: value" (repeatable), --sender <email>, --write-suppression, --dry-run/--live, --llm <sonnet|gemini>. Env (live only): ANTHROPIC_API_KEY, GEMINI_API_KEY.
outputs: JSON to stdout: {"class", "rule_confidence", "rule", "opt_out", "explanation", "detected_intent_signals", "cost_eur_estimate"} (+ "suppression" when --sender/--write-suppression act).

Reads directive: directives/personal_workflows/self_outbound_system.md (Phase 3 script #7).

Rule precedence (first match wins; see the directive for the reasoning):
  1. stop / unsubscribe       -> negative, opt_out=True (always wins)
  2. auto-reply metadata      -> auto_reply_or_OOO (Auto-Submitted / X-Autoreply /
                                 X-Autorespond / Precedence headers, or an
                                 "Automatic reply" / "Out of office" subject)
  3. hot signal               -> hot (dry-run; live mode would LLM-verify)
  4. explicit decline         -> negative, opt_out=False
  5. interest signal          -> positive
  6. OOO wording in the body  -> auto_reply_or_OOO (only when nothing above fired)
  7. otherwise                -> LLM (live, stubbed) / neutral (dry-run)

`rule_confidence` is a fixed per-rule prior, NOT a calibrated probability. The
measured precision/recall of the rule layer on the labelled fixture
(tests/fixtures/reply_labelled.json) is reported by
tests/test_reply_classifier.py::test_labelled_fixture_precision_recall.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping
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

# Execution tier per ~/.claude/rules/model-tier.md: classification into a fixed
# 5-label set is throughput work, not judgement -- the taxonomy is already
# specified, so the model's job is fidelity to it.
#
# Full name pinned deliberately; bare `sonnet` aliases resolve differently per
# provider. OpenRouter callers use DEFAULT_MODEL_OPENROUTER instead.
# Both verified against their catalogs on 2026-08-12.
DEFAULT_MODEL: str = "claude-fable-5-1"
DEFAULT_MODEL_OPENROUTER: str = "anthropic/claude-fable-5.1"

# Per-rule priors. Ordinal labels for downstream routing, not measured
# probabilities -- see the module docstring.
RULE_CONFIDENCE: dict[str, float] = {
    "stop": 0.99,
    "auto_reply_metadata": 0.99,
    "hot": 0.90,
    "decline": 0.90,
    "positive": 0.80,
    "ooo_body": 0.80,
    "fallback": 0.50,
    "empty": 0.0,
}

_I = re.IGNORECASE

# Optional apostrophe (straight or curly) so "don't" / "don’t" / "dont" all match.
_APOS = r"['’]?"

# ---------------------------------------------------------------------------
# Quoted-thread stripping
# ---------------------------------------------------------------------------

# HTML quote containers (Gmail, Outlook web, Apple Mail). Everything from the
# first one onward is thread history.
_HTML_QUOTE_START = re.compile(
    r"<div[^>]*class=[\"'][^\"']*gmail_quote|<blockquote\b|"
    r"<div[^>]*id=[\"'](?:divRplyFwdMsg|appendonsend)[\"']",
    _I,
)
# Attribution lines that introduce a quote.
_ATTRIBUTION = re.compile(
    r"^(?:On\b.{0,300}\bwrote\s*:|Le\b.{0,300}\ba\s+[ée]crit\s*:)\s*$", _I,
)
# Separators after which everything is the previous message.
_SEPARATOR = re.compile(
    r"^(?:-{2,}\s*(?:Original Message|Message d['’]origine|Forwarded message|"
    r"Message transf[ée]r[ée])\s*-{2,}|_{10,}|Begin forwarded message\s*:|"
    r"D[ée]but du message r[ée]exp[ée]di[ée]\s*:)\s*$",
    _I,
)
# Outlook plain-text header block: "From:" followed by Sent/Date/To within 4 lines.
_OUTLOOK_FROM = re.compile(r"^\*?(?:From|De)\s*:\*?\s*\S", _I)
_OUTLOOK_NEXT = re.compile(r"^\*?(?:Sent|Date|To|Envoy[ée]|[ÀA]|Subject|Objet)\s*:", _I)


def strip_quoted(body: str) -> str:
    """Return only the text the replier wrote, without quoted thread history.

    Our own outbound email (and its unsubscribe footer) comes back inside the
    quote, so matching rules against the full body produces false stop hits.

    - HTML quote containers: cut from the first one.
    - "> " prefixed lines: dropped (keeps interleaved / bottom-posted text).
    - "On ... wrote:" / "Le ... a écrit :": if ">" lines follow, only the
      attribution is dropped; otherwise everything from it onward is cut.
      The two-line Gmail form ("On <date>, <name>\\n<email> wrote:") is handled.
    - "-----Original Message-----", Outlook "From:/Sent:" blocks, "____" rules,
      forwarded-message markers: cut from there.
    """
    text = body or ""
    m = _HTML_QUOTE_START.search(text)
    if m:
        text = text[: m.start()]
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        attribution_len = 0
        if _ATTRIBUTION.match(s):
            attribution_len = 1
        elif (
            i + 1 < len(lines)
            and re.match(r"^(?:On|Le)\b", s, _I)
            and _ATTRIBUTION.match(f"{s} {lines[i + 1].strip()}")
        ):
            attribution_len = 2
        if attribution_len:
            nxt = next(
                (ln.strip() for ln in lines[i + attribution_len:] if ln.strip()), ""
            )
            if nxt.startswith(">"):
                i += attribution_len
                continue
            break
        if _SEPARATOR.match(s):
            break
        if _OUTLOOK_FROM.match(s) and any(
            _OUTLOOK_NEXT.match(ln.strip()) for ln in lines[i + 1: i + 5]
        ):
            break
        if s.startswith(">"):
            i += 1
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out).strip()


# ---------------------------------------------------------------------------
# Rule patterns (English + French per the directive's language gate)
# ---------------------------------------------------------------------------

_STOP_PATTERNS = [
    r"\bunsubscribe\b",
    r"\bremove me\b",
    r"\btake me off\b",
    r"\bopt(?:[-\s])?(?:me\s+)?out\b",
    r"\bstop (?:emailing|contacting|messaging|writing to) me\b",
    r"\bdo not (?:email|contact|call|message) me\b",
    r"\bdon" + _APOS + r"t (?:email|contact|call|message) me\b",
    r"\bnever (?:email|contact) me\b",
    r"\bd[ée]sinscri(?:re|s|vez|ption)\b",
    r"\bd[ée]sabonn(?:er|ez|ement)\b",
    r"\bretirez[- ]moi\b",
    r"\bne (?:plus|jamais) (?:me )?(?:contacter|[ée]crire|relancer)\b",
    r"\bne me (?:contactez|[ée]crivez|relancez) plus\b",
    r"\barr[êe]tez de m['’]?(?:[ée]crire|envoyer|contacter)\b",
]

# Auto-reply metadata. Header names are matched case-insensitively.
_AUTO_HEADERS_ANY_VALUE = ("x-autoreply", "x-autorespond")
_AUTO_SUBJECT = re.compile(
    r"^\s*(?:automatic reply|auto(?:matic)?[-\s]?(?:reply|response)|autoreply|"
    r"out of (?:the )?office|r[ée]ponse automatique|absence du bureau|absent(?:e)?\b|"
    r"message d['’]absence)",
    _I,
)

# Phone digits: at least 8 digits with optional separators.
_PHONE = r"\+?\(?\d[\d\s().\-]{6,}\d"
_HOT_PATTERNS = [
    # A phone number only counts with "call me / my number" context, so order
    # numbers, invoice refs and postcodes do not fire.
    r"\b(?:call|ring|reach|text|whatsapp)\s+me\b[^.\n]{0,25}?" + _PHONE,
    r"\b(?:appelez|appelle|joignez|contactez)[- ]moi\b[^.\n]{0,25}?" + _PHONE,
    r"\bmy (?:mobile |cell |phone |direct )?(?:number|line) is\b",
    r"\bmon (?:num[ée]ro|portable|t[ée]l[ée]?(?:phone)?)\b[^.\n]{0,20}?" + _PHONE,
    r"\bcall me (?:at|on|tomorrow|today|this|next|any ?time|whenever)\b",
    r"\bready to (?:sign|start|go|move(?: forward)?)\b",
    r"\b(?:can|could|shall) we (?:jump|hop|get) on a (?:quick )?call\b",
    r"\b(?:can|could|shall) we (?:do|have|set up|schedule|book) a (?:quick )?(?:call|meeting|chat)\b",
    r"\blet" + _APOS + r"s (?:set up|schedule|book|do|have|jump on|hop on) a (?:quick )?(?:call|meeting|chat)\b",
    r"\bsend (?:me |over )?(?:the |a )?(?:contract|proposal|calendar invite|invite)\b",
    r"\bon (?:peut|pourrait) (?:s['’]appeler|se parler|caler un (?:appel|call|rdv|cr[ée]neau))\b",
    r"\b(?:dispo|disponible)s? pour un (?:appel|call|[ée]change)\b",
    r"\bpr[êe]te? [àa] signer\b",
]
# A phone hit preceded by this (e.g. "for urgent matters call me on ...") is an
# auto-reply's fallback contact, not buying intent.
_URGENT_CONTEXT = re.compile(r"\b(?:urgen(?:t|ce|cy|tes?)|emergenc(?:y|ies))\b", _I)

_DECLINE_PATTERNS = [
    r"\b(?:not|no longer|n" + _APOS + r"t)\s+(?:\w+\s+)?interested\b",
    r"\bnot (?:a (?:good )?fit|relevant (?:for|to) us)\b",
    r"\bno,? thanks?\b",
    r"\bno,? thank you\b",
    r"\bwe(?:" + _APOS + r"re| are) (?:all )?(?:set|covered)\b",
    r"\bpas\s+(?:\w+\s+){0,2}int[ée]ress[ée]e?s?\b",
    r"\bne m['’]int[ée]resse pas\b",
    r"\bnon,? merci\b",
    r"\bpas pour (?:nous|moi)\b",
]

_POSITIVE_PATTERNS = [
    # "interested" not preceded by a negation (decline is checked first anyway).
    r"(?<!not )(?<!n't )(?<!longer )\binterested\b",
    r"\btell me more\b",
    r"\b(?:send|share) (?:me )?(?:more )?(?:info|information|details)\b",
    r"\bmore (?:info|information|details)\b",
    r"\bwhat are (?:the )?next steps\b",
    r"\bsounds (?:good|great|interesting)\b",
    r"\bhappy to (?:chat|talk|discuss|connect)\b",
    r"\blet" + _APOS + r"s (?:talk|chat|discuss|connect)\b",
    r"\bopen to (?:a )?(?:chat|call|conversation|discussing)\b",
    r"\bhow does (?:the )?pricing work\b",
    r"(?<!pas )\bint[ée]ress[ée]e?s?\b",
    r"\b(?:ça|cela) m['’]int[ée]resse\b(?! pas)",
    r"\ben savoir plus\b",
    r"\bparlons[- ]en\b",
    r"\b(?:volontiers|avec plaisir)\b",
]

# Body wording that indicates an out-of-office message. These only decide the
# class when no stop / hot / decline / positive rule fired, and each one is
# anchored to OOO phrasing so ordinary buyer replies ("absent a budget", "we
# will return to this in Q3") do not match.
_OOO_BODY_PATTERNS = [
    r"\bautomatic reply\b",
    r"\bauto[-\s]?reply\b",
    r"\bthis is an automated (?:message|response|reply)\b",
    r"\bout of (?:the )?office\b",
    r"\b(?:on|taking) (?:annual |parental |maternity |paternity |sick )?leave\b",
    r"\bon (?:vacation|holiday|holidays)\b",
    r"\b(?:currently|presently) away\b",
    r"\baway from (?:the |my )?(?:office|desk)\b",
    r"\bI(?:" + _APOS + r"ll| will) (?:return|be back)\b[^.\n]{0,30}?"
    r"\b(?:on|until|after)?\s*(?:mon|tues?|wed(?:nes)?|thu(?:rs)?|fri|sat(?:ur)?|sun)(?:day)?\b",
    r"\bI(?:" + _APOS + r"ll| will) (?:return|be back) (?:on|after) (?:the )?\d",
    r"\blimited access to (?:my )?e-?mail\b",
    r"\br[ée]ponse automatique\b",
    r"\bmessage (?:automatique|d['’]absence)\b",
    r"\ben cong[ée]s?\b",
    r"\bde retour (?:le|lundi|mardi|mercredi|jeudi|vendredi|[àa] partir)\b",
    r"\b(?:je suis|actuellement) absente?\b",
    r"\babsente? (?:du bureau|jusqu['’]a)",
]


def _matches_any(text: str, patterns: list[str]) -> list[str]:
    """Return the list of patterns that matched."""
    return [pat for pat in patterns if re.search(pat, text, _I)]


def _hot_hits(text: str) -> list[str]:
    """Hot patterns, skipping phone hits that follow urgent-contact wording."""
    hits: list[str] = []
    for pat in _HOT_PATTERNS:
        for m in re.finditer(pat, text, _I):
            window = text[max(0, m.start() - 60): m.start()]
            if _PHONE in pat and _URGENT_CONTEXT.search(window):
                continue
            hits.append(pat)
            break
    return hits


def _auto_reply_metadata(subject: str | None, headers: Mapping[str, str] | None) -> list[str]:
    """Machine evidence that the message is an auto-reply."""
    hits: list[str] = []
    for name, value in (headers or {}).items():
        key = str(name).strip().lower()
        val = str(value or "").strip().lower()
        if key == "auto-submitted" and val and val != "no":
            hits.append(f"header:Auto-Submitted={val}")
        elif key in _AUTO_HEADERS_ANY_VALUE and val:
            hits.append(f"header:{name}")
        elif key == "precedence" and val == "auto_reply":
            hits.append("header:Precedence=auto_reply")
    if subject and _AUTO_SUBJECT.search(subject):
        hits.append("subject:auto-reply")
    return hits


def _result(cls: str, rule: str, explanation: str, signals: list[str],
            opt_out: bool = False) -> dict:
    return {
        "class": cls,
        "rule": rule,
        "rule_confidence": RULE_CONFIDENCE[rule],
        "opt_out": opt_out,
        "explanation": explanation,
        "detected_intent_signals": signals,
        "cost_eur_estimate": 0.0,
    }


def classify(
    body: str,
    dry_run: bool = True,
    llm: str = "sonnet",
    *,
    subject: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> dict:
    """Classify a reply. Returns dict with class / rule / rule_confidence /
    opt_out / explanation / detected_intent_signals / cost_eur_estimate.

    `rule_confidence` is the fixed prior of the rule that fired, not a
    calibrated probability. `opt_out` is True only for stop requests; pass the
    result to apply_opt_out() to suppress the sender.
    """
    text = strip_quoted(body)
    if not text:
        return _result("neutral", "empty", "empty-body (after stripping quoted text)", [])

    stop = _matches_any(text, _STOP_PATTERNS)
    if stop:
        return _result("negative", "stop", "deterministic stop/unsubscribe pattern matched",
                       stop, opt_out=True)

    meta = _auto_reply_metadata(subject, headers)
    if meta:
        return _result("auto_reply_or_OOO", "auto_reply_metadata",
                       "auto-reply header or subject", meta)

    hot = _hot_hits(text)
    if hot and dry_run:
        # In live mode a hot hit is LLM-verified instead of returned directly.
        return _result("hot", "hot", "deterministic phone / meeting-request pattern matched", hot)

    if not hot:
        decline = _matches_any(text, _DECLINE_PATTERNS)
        if decline:
            return _result("negative", "decline", "deterministic decline pattern matched", decline)

        positive = _matches_any(text, _POSITIVE_PATTERNS)
        if positive:
            return _result("positive", "positive", "deterministic interest pattern matched", positive)

        ooo = _matches_any(text, _OOO_BODY_PATTERNS)
        if ooo:
            return _result("auto_reply_or_OOO", "ooo_body",
                           "OOO wording in body, no human-intent signal", ooo)

    if dry_run:
        return _result("neutral", "fallback",
                       "dry-run stub: no rule matched, no LLM call, defaulting to neutral", [])

    # Live LLM call would go here. STUBBED to raise so we can't accidentally
    # spend $ without an explicit code change.
    _ = anthropic_cost_eur(0, 0)  # ensure symbol is used
    raise NotImplementedError(
        "Live LLM classification not implemented in this scaffold. "
        f"Would call {DEFAULT_MODEL} (or Gemini 2.5 Flash if --llm gemini) "
        "and return {class, rule_confidence, explanation, detected_intent_signals} "
        "with cost tracked in EUR."
    )


def apply_opt_out(result: dict, sender_email: str, *, dry_run: bool = False) -> dict | None:
    """Suppress `sender_email` when `result` is a stop request.

    Writes through suppression_writer.add_suppression (reason negative_reply,
    source reply_classifier), which is idempotent on the email list: replaying
    the same reply leaves exactly one entry (each event is still logged in
    history). icp_filter reads suppression.json, so a suppressed address is
    rejected from every later batch. Returns the writer's summary dict, or None
    when the result is not an opt-out.
    """
    if not result.get("opt_out"):
        return None
    # Local import keeps classify() free of the writer's lock/IO dependencies.
    from suppression_writer import add_suppression

    return add_suppression(
        email=sender_email,
        reason="negative_reply",
        source="reply_classifier",
        alert=False,
        dry_run=dry_run,
    )


def _parse_header(raw: str) -> tuple[str, str]:
    if ":" not in raw:
        raise argparse.ArgumentTypeError(f"header must be 'Name: value', got {raw!r}")
    name, value = raw.split(":", 1)
    return name.strip(), value.strip()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[1])
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--reply-body", type=str, default=None,
                     help="Reply body as a raw string.")
    src.add_argument("--reply-file", type=Path, default=None,
                     help="Path to a text file containing the reply body.")
    p.add_argument("--subject", type=str, default=None,
                   help="Reply subject (used to detect 'Automatic reply' / 'Out of office').")
    p.add_argument("--header", dest="headers", action="append", type=_parse_header, default=[],
                   help="Message header 'Name: value' (repeatable), e.g. 'Auto-Submitted: auto-replied'.")
    p.add_argument("--sender", type=str, default=None,
                   help="Sender address; with --write-suppression a stop request suppresses it.")
    p.add_argument("--write-suppression", action="store_true", default=False,
                   help="Write stop requests to config/suppression.json (requires --sender).")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", default=True,
                   help="Dry-run (default). No LLM call; deterministic layer only.")
    p.add_argument("--live", dest="dry_run", action="store_false",
                   help=f"Live mode. Calls {DEFAULT_MODEL} or Gemini for ambiguous cases.")
    p.add_argument("--llm", choices=["sonnet", "gemini"], default="sonnet",
                   help=f"LLM for ambiguous cases in live mode. "
                        f"'sonnet' resolves to {DEFAULT_MODEL}. Default: sonnet.")
    args = p.parse_args(argv)
    if args.write_suppression and not args.sender:
        p.error("--write-suppression requires --sender")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.reply_file is not None:
        body = args.reply_file.read_text(encoding="utf-8")
    else:
        body = args.reply_body or ""

    result = classify(body, dry_run=args.dry_run, llm=args.llm,
                      subject=args.subject, headers=dict(args.headers))
    if args.sender and result["opt_out"]:
        result["suppression"] = apply_opt_out(
            result, args.sender, dry_run=not args.write_suppression,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    print_stat("reply_classifier", {
        "class": result["class"],
        "rule": result["rule"],
        "rule_confidence": result["rule_confidence"],
        "opt_out": result["opt_out"],
        "dry_run": args.dry_run,
        "llm": args.llm,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
