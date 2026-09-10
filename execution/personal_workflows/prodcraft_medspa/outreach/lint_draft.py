"""
lint_draft.py
description: CAN-SPAM linter implementing prompts/can_spam_checklist.md exactly, fail-closed.
inputs: Imported by daily_queue.py (lint(subject, body, touch=..., sender_name=..., sender_physical_address=...));
    CLI: --subject --body --touch --sender-name --sender-address for ad-hoc checks.
outputs: {"violations": [...], "needs_operator_input": bool, "word_count": int}; stdout JSON via CLI.
"""

from __future__ import annotations

import argparse
import json
import re

# Verbatim per can_spam_checklist.md rule 4 — must appear exactly, not paraphrased.
OPT_OUT_LINE = "Reply 'no' and I won't follow up."

# can_spam_checklist.md doesn't list these, but CONTRACTS.md's build note for this package adds
# them explicitly: "blocks ... if the body contains 'outdated', 'bad', 'ugly', 'unprofessional'"
# (the same forbidden-word list fuzzy_variables.md enforces on the LLM's own output — belt and
# suspenders in case a human-edited draft reintroduces one).
BANNED_WORDS = ("outdated", "bad", "ugly", "unprofessional")

_URL_RE = re.compile(r"https?://\S+")
_ALLCAPS_WORD_RE = re.compile(r"\b[A-Z]{3,}\b")
_UNRESOLVED_VAR_RE = re.compile(r"\{\{\s*\w+\s*\}\}")
_LEADING_RE_RE = re.compile(r"^\s*re\s*:", re.IGNORECASE)
_LOOM_PLACEHOLDER = "[[LOOM URL]]"
_BANNED_WORD_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in BANNED_WORDS) + r")\b", re.IGNORECASE)


def lint(
    subject: str,
    body: str,
    *,
    touch: int,
    sender_name: str | None,
    sender_physical_address: str | None,
) -> dict:
    """Run every can_spam_checklist.md rule (numbered #1-#8) plus the banned-word check.

    Fails closed: an empty sender_name or sender_physical_address is itself a violation
    (rules #1 / #3), never silently skipped.
    """
    violations: list[str] = []
    full_text = f"{subject}\n{body}"

    # Unresolved {{var}} tokens are always a bug (a variable the caller forgot to render) —
    # except the deliberate "[[LOOM URL]]" operator placeholder, which is flagged separately
    # per CONTRACTS.md ("the linter flags as needs_operator_input rather than fail").
    needs_operator_input = _LOOM_PLACEHOLDER in full_text
    text_without_loom_placeholder = full_text.replace(_LOOM_PLACEHOLDER, "")
    if _UNRESOLVED_VAR_RE.search(text_without_loom_placeholder):
        violations.append("render:unresolved_variable")

    # Rule 1 — From name present and resolved.
    if not sender_name or not sender_name.strip():
        violations.append("can_spam:1")

    # Rule 2 — no false-urgency "Re:" on touch 1 (touches 2-4 legitimately use it).
    if touch == 1 and _LEADING_RE_RE.match(subject or ""):
        violations.append("can_spam:2")

    # Rule 3 — physical postal address present, resolved, and in the signature block.
    if not sender_physical_address or not sender_physical_address.strip():
        violations.append("can_spam:3")
    elif sender_physical_address not in body:
        violations.append("can_spam:3")

    # Rule 4 — opt-out line present, verbatim.
    if OPT_OUT_LINE not in body:
        violations.append("can_spam:4")

    # Rule 5 — link cap by touch: 1-2 -> at most 1 URL; 3-4 -> zero.
    urls = _URL_RE.findall(body)
    max_links = 1 if touch in (1, 2) else 0
    if len(urls) > max_links:
        violations.append("can_spam:5")

    # Rule 6 — no ALL-CAPS words (3+ letters) anywhere in subject or body.
    if _ALLCAPS_WORD_RE.search(full_text):
        violations.append("can_spam:6")

    # Rule 7 — no "free" in the subject line.
    if "free" in (subject or "").lower():
        violations.append("can_spam:7")

    # Rule 8 — body word count <= 120 (hard ceiling across all touches).
    word_count = len(body.split())
    if word_count > 120:
        violations.append("can_spam:8")

    # Extra content guard (not a can_spam_checklist.md rule, but required by this build).
    for match in _BANNED_WORD_RE.finditer(body):
        violations.append(f"content:banned_word:{match.group(1).lower()}")

    return {
        "violations": violations,
        "needs_operator_input": needs_operator_input,
        "word_count": word_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Lint one draft email against can_spam_checklist.md")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--body", required=True)
    parser.add_argument("--touch", type=int, required=True)
    parser.add_argument("--sender-name", default="")
    parser.add_argument("--sender-address", default="")
    args = parser.parse_args()

    result = lint(
        args.subject,
        args.body,
        touch=args.touch,
        sender_name=args.sender_name,
        sender_physical_address=args.sender_address,
    )
    print(json.dumps({"script": "lint_draft", **result}))


if __name__ == "__main__":
    main()
