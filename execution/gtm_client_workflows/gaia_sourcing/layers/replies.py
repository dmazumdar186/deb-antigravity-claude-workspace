"""
Reply classification -- client promise 2026-09-10: "candidate replies to
outreach are classified immediately and the pool updated."

Deterministic rules run first and cover the large majority of real replies:
bounce, out-of-office, opt-out/negative, positive, question. Only genuine
ambiguity reaches the LLM (ROLE_JUDGE -- the same role and call pattern as
layers/movability.py's `assess`), and only when `use_llm=True`. Any LLM
failure, or `use_llm=False`, keeps the rule verdict of "unclear" /
"human_review" rather than guessing (I3: deterministic code decides; the
model is an input, never the decision-maker).

I7: this module NEVER drafts or sends anything. `classify_reply` reads one
incoming message and returns a verdict for a human -- or Recruit CRM's Maddie,
or a consultant -- to act on.
"""

from __future__ import annotations

import re
from typing import Optional

from ..core.contracts import ReplyVerdict
from ..core.providers import ROLE_JUDGE, call_role

# label -> next_action. Deterministic (I3): this dict decides, never the
# model -- the LLM path below only ever supplies `label`.
_NEXT_ACTION: dict[str, str] = {
    "interested": "book_call",
    "not_now": "snooze_90d",
    "not_interested": "close",
    "question": "consultant_answers",
    "out_of_office": "retry_later",
    "bounce": "human_review",
    "unclear": "human_review",
}

# Checked in this order: a bounce or an opt-out must win even if the
# remaining text also contains an out-of-office footer or a stray "?".
_BOUNCE_RE = re.compile(
    r"mailer-daemon|undeliverable|address (?:was )?not found|delivery "
    r"(?:has |status notification )?failed|was not delivered|550[ -]5\.\d\.\d|"
    r"user unknown|no such user|permanent failure|message could not be delivered",
    re.I,
)
_OPT_OUT_RE = re.compile(
    r"\bunsubscribe\b|please remove me|remove me from|no longer wish to "
    r"(?:be contacted|hear from)|stop contacting me|take me off (?:your|the) "
    r"list|\bstop\b\s*$",
    re.I,
)
_OOO_RE = re.compile(
    r"out of (?:the )?office|on annual leave|on leave until|away from (?:my "
    r"desk|the office)|currently unavailable until|back in the office on|"
    r"i(?:'m| am) currently out",
    re.I,
)
_NEGATIVE_RE = re.compile(
    r"not interested|no thanks|no thank you|not for me|not (?:currently |)"
    r"looking|happy where i am|not the right time for a move",
    re.I,
)
_NOT_NOW_RE = re.compile(
    r"not (?:right )?now|maybe in the future|reach out again (?:in|later)|"
    r"check back in|circle back (?:in|with me)|touch base (?:in|again)",
    re.I,
)
_POSITIVE_RE = re.compile(
    r"happy to (?:chat|talk|jump on a call)|let'?s talk|let'?s chat|call me|"
    r"send me more|would love to (?:hear|chat|talk)|sounds interesting|"
    r"i(?:'m| am) interested|keen to (?:hear|chat|talk)",
    re.I,
)
_QUESTION_HINTS_RE = re.compile(
    r"what is the salary|what'?s the salary|which company|who is the client|"
    r"day rate|remote or (?:on ?site|hybrid)|is this role|what would the",
    re.I,
)

TOOL = {
    "name": "emit_reply_verdict",
    "description": "Classify one candidate reply to a recruiting outreach message.",
    "input_schema": {
        "type": "object",
        "properties": {
            "label": {
                "type": "string",
                "enum": [
                    "interested", "not_now", "not_interested", "question",
                    "out_of_office", "bounce", "unclear",
                ],
            },
            "evidence": {
                "type": "string",
                "description": "The exact phrase from the reply that decided the label.",
            },
            "confidence": {"type": "string", "enum": ["high", "low"]},
        },
        "required": ["label", "evidence", "confidence"],
    },
}

SYSTEM = """You classify one candidate's reply to a recruiting outreach message.

Choose exactly one label from the allowed set. Quote the specific phrase that
decided your answer as `evidence` -- do not paraphrase it.

Say `confidence: low` whenever the reply is short, sarcastic, ambiguous, or
could plausibly be read two ways. A false "high" here sends a real reply
straight past a human, so under-claim rather than over-claim.

Never draft a reply. Never invent anything about the candidate that is not in
the text you were given."""


def _rule_pass(text: str) -> Optional[ReplyVerdict]:
    t = text or ""

    m = _BOUNCE_RE.search(t)
    if m:
        return ReplyVerdict(
            label="bounce", next_action=_NEXT_ACTION["bounce"], basis="rule",
            evidence=m.group(0), confidence="high", opt_out=False,
        )

    m = _OPT_OUT_RE.search(t)
    if m:
        # opt_out MUST be honoured downstream: close, and a "do not contact"
        # note. Grouped with not_interested's next_action (close) rather than
        # given its own label, per spec -- what distinguishes it is the flag,
        # not a separate state.
        return ReplyVerdict(
            label="not_interested", next_action=_NEXT_ACTION["not_interested"],
            basis="rule", evidence=m.group(0), confidence="high", opt_out=True,
        )

    m = _OOO_RE.search(t)
    if m:
        return ReplyVerdict(
            label="out_of_office", next_action=_NEXT_ACTION["out_of_office"],
            basis="rule", evidence=m.group(0), confidence="high", opt_out=False,
        )

    m = _NEGATIVE_RE.search(t)
    if m:
        return ReplyVerdict(
            label="not_interested", next_action=_NEXT_ACTION["not_interested"],
            basis="rule", evidence=m.group(0), confidence="high", opt_out=False,
        )

    m = _NOT_NOW_RE.search(t)
    if m:
        return ReplyVerdict(
            label="not_now", next_action=_NEXT_ACTION["not_now"], basis="rule",
            evidence=m.group(0), confidence="high", opt_out=False,
        )

    m = _POSITIVE_RE.search(t)
    if m:
        return ReplyVerdict(
            label="interested", next_action=_NEXT_ACTION["interested"],
            basis="rule", evidence=m.group(0), confidence="high", opt_out=False,
        )

    m = _QUESTION_HINTS_RE.search(t)
    if m or t.strip().endswith("?"):
        evidence = m.group(0) if m else t.strip()[-60:]
        return ReplyVerdict(
            label="question", next_action=_NEXT_ACTION["question"], basis="rule",
            evidence=evidence, confidence="high", opt_out=False,
        )

    return None


def classify_reply(text: str, *, use_llm: bool = True) -> ReplyVerdict:
    """Classify one reply. Deterministic rules first; the LLM only sees a
    reply none of the rules matched, and only when `use_llm` is True.
    """
    verdict = _rule_pass(text)
    if verdict is not None:
        return verdict

    if not use_llm:
        return ReplyVerdict(
            label="unclear", next_action=_NEXT_ACTION["unclear"], basis="rule",
            evidence="no rule matched", confidence="low", opt_out=False,
        )

    try:
        out, _meta = call_role(
            role=ROLE_JUDGE, system=SYSTEM,
            user="CANDIDATE REPLY:\n\n" + (text or ""), tool=TOOL, max_tokens=400,
        )
    except Exception as exc:
        print("[replies] LLM classification failed: " + repr(exc)[:120])
        out = None

    if not out:
        return ReplyVerdict(
            label="unclear", next_action=_NEXT_ACTION["unclear"], basis="llm",
            evidence="LLM call failed or returned nothing usable",
            confidence="low", opt_out=False,
        )

    label = str(out.get("label", "unclear")).strip().lower()
    if label not in _NEXT_ACTION:
        label = "unclear"
    confidence = str(out.get("confidence", "low")).strip().lower()
    if confidence not in ("high", "low"):
        confidence = "low"
    evidence = str(out.get("evidence", "")).strip() or "(model gave no evidence quote)"

    # opt_out is never set on the LLM path -- see the ReplyVerdict docstring
    # in core/contracts.py. It is only ever set by the deterministic
    # _OPT_OUT_RE match above, which returns before reaching here.
    return ReplyVerdict(
        label=label, next_action=_NEXT_ACTION[label], basis="llm",
        evidence=evidence, confidence=confidence, opt_out=False,
    )


def crm_note_for_reply(verdict: ReplyVerdict, reply_text_excerpt: str = "") -> str:
    """Text for the Recruit CRM note recording this classification."""
    lines = [
        "Reply classified: " + verdict.label + " (" + verdict.basis + ", "
        + verdict.confidence + " confidence).",
        "Next action: " + verdict.next_action + ".",
        'Evidence: "' + verdict.evidence.strip() + '"',
    ]
    if verdict.opt_out:
        lines.append("OPT-OUT requested -- do not contact again.")
    excerpt = (reply_text_excerpt or "").strip()
    if excerpt:
        lines.append("")
        lines.append('Reply excerpt: "' + excerpt[:300] + '"')
    return "\n".join(lines)
