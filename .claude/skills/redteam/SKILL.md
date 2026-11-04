---
name: redteam
description: Mandatory red-team gate before ANY outward text is sent, drafted to Gmail, or handed to the operator as final: emails, negotiation replies, proposals, offers, pitches. Triggers on "red team", /redteam.
user_invocable: true
---

# Red team gate

Script: `G="python3 execution/infrastructure/redteam_gate.py"`. Lenses: counterparty, grounding, downside, reputation.

## Runbook
0. **Save and source.** Write the exact text to send to `.tmp/redteam/drafts/<slug>.txt` (+ `<slug>.html` if an HTML body will be sent). Gather sources: full thread, brief, price sheet, contract, prior commitments, research files, the operator's stated positions (quote them into GOAL). A needed source that is missing is a BLOCKER: name it; never fill the gap from memory.
1. **Ground.** `$G ground --draft D --sources S... --json`. Remove or source every `ungrounded` claim. The script matches values, not context: treat every `overclaim` as a question for the lenses.
2. **Lenses.** `$G sha --draft D`, then fan out all four lenses in ONE message as parallel Agent calls, `subagent_type: redteam-lens`. If that type is not registered this session, use `general-purpose` with the body of `.claude/agents/redteam-lens.md` + the inputs as the brief. Brief = LENS, DRAFT path, DRAFT-SHA, SOURCES paths, GOAL. Never pass your reasoning, earlier verdicts or "why I wrote it this way". Save each returned verdict verbatim to `.tmp/redteam/verdicts/<slug>.<lens>.md`.
3. **Fix loop.** Any FAIL → apply the fixes to the draft file → new sha → rerun `ground` and ALL four lenses (verdicts bind to the sha). Max 3 rounds. Still failing → do not send; tell the operator exactly which findings remain and what decision or source would resolve each.
4. **Record, then send.** `$G record --draft D --sources S... --verdicts V1 V2 V3 V4`, then send or draft the saved text byte for byte (body and htmlBody). The PreToolUse hook denies any Gmail send/reply/forward/draft whose normalised text was not recorded; edit after record = rerun from step 1.
5. **Receipt** (chat only, never inside the deliverable), 3 lines:
   - `Claims grounded N/N against K sources`
   - `Lenses 4/4 PASS in R rounds`
   - `Residual risks:` one per line, or `none`
   No hedging, no apology prose.

Waiver: `$G waive --draft D --reason "operator: <their words>"` only when the operator explicitly said to ship without the gate; add a HANDOFF.md line. Never self-waive for speed.

## When the operator pushes back
Re-verify the challenged point against the source before replying. Answer with evidence:
- `Verified: <claim> — <file:line>`
- `Corrected: <old> → <new> — <file:line>`
Never open with "you're right", praise or apology. Never concede without evidence; never defend without it. A confirmed miss is a system defect, fixed the same turn: add the pattern to the matching lens checklist in `.claude/agents/redteam-lens.md` (or a regression test in `tests/test_redteam_gate.py`) and a `[learned]` line in `.claude/notes/general.md`.

## Scope
Every outward channel. Gmail is hard-gated by the hook; LinkedIn, Slack, docs, decks, proposals and text pasted for the operator to send are gated by this skill. No exemption for "quick" messages. Out of scope: pure internal notes, and code (it has its own audit stack).
