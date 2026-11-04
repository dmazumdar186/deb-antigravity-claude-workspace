---
name: redteam
description: Mandatory red-team gate before ANY outward text is sent, drafted to Gmail, or handed to the operator as final: emails, negotiation replies, proposals, offers, pitches. Triggers on "red team", /redteam.
user_invocable: true
---

# Red team gate

Script: `G="python3 execution/infrastructure/redteam_gate.py"`. Lenses: counterparty, grounding, downside, reputation. Directive: `directives/infrastructure/redteam_gate.md`.

## What is gated where
- **Hard-gated by hooks:** Gmail send/reply/forward/drafts (body, htmlBody, any unknown text field, subject, to/cc/bcc, attachments), Calendar invites (create/update_event with attendees, or update_event unless `notificationLevel: NONE`), and Bash commands that send email inline (smtplib, sendmail, Gmail/Instantly/SendGrid/Resend/Postmark APIs). Committed, unmodified pipeline scripts run directly still work.
- **Skill-gated only (no hook, you are the gate):** LinkedIn, Slack, docs, decks, proposals, and text handed to the operator in chat for them to send. Same runbook, no exemption for "quick" messages.

## Runbook
0. **Save and source.** Write the exact text to send to `.tmp/redteam/drafts/<slug>.txt` (+ `<slug>.html` if an HTML body will be sent; no `<script>`/`<style>` content, links count as text). Gather sources: full thread, brief, price sheet, contract, prior commitments, the operator's stated positions (quote them into GOAL). A missing source is a BLOCKER: name it; never fill the gap from memory. Never pass an earlier version of the draft as a source (it is skipped as "looks like the draft itself").
1. **Ground.** `$G ground --draft D --sources S... --json`. Every `ungrounded` and `weak` claim must be removed or sourced (weak fails). Names (Title-Case words, emails) must appear in a source: an ungrounded name usually means the thread is missing from SOURCES, so add it rather than rewording. Treat every `overclaim` as a question for the lenses.
2. **Lenses.** `$G sha --draft D`, then fan out all four lenses in ONE message as parallel Agent calls with `subagent_type: redteam-lens` (no other type counts: the SubagentStop hook logs only real `redteam-lens` runs, and `record` checks that log). Brief = LENS, DRAFT path, DRAFT-SHA, SOURCES paths, GOAL. Never pass your reasoning, earlier verdicts or a desired verdict. Save each returned text **verbatim** to `.tmp/redteam/verdicts/<slug>.<lens>.md`; an edited or hand-written verdict file is refused.
3. **Fix loop.** Any FAIL → fix the draft → new sha → rerun `ground` and ALL four lenses. Max 3 rounds. Still failing → do not send; tell the operator which findings remain and what decision or source resolves each.
4. **Record, then send.** `$G record --draft D --sources S... --verdicts V1 V2 V3 V4 --subject "<exact subject>" --to A... [--cc A...] [--bcc A...] [--attachments FILE...]`, then send or draft the saved text byte for byte with exactly that envelope. Calendar: record the description with `--subject "<event summary>"`. Any edit after record = rerun from step 1.
5. **Receipt** (chat only, never inside the deliverable), 3 lines:
   - `Claims grounded N/N against K sources`
   - `Lenses 4/4 PASS in R rounds`
   - `Residual risks:` one per line, or `none`
   No hedging, no apology prose.

**Waiver: operator only.** If the operator wants to ship without the gate, they type `redteam waive <sha12> <reason>` as their own prompt (give them the sha12). You cannot waive: `$G waive` exits 2, and writing the ledgers yourself is forgery. Never ask for a waiver to save time.

## When the operator pushes back
Re-verify the challenged point against the source before replying. Answer with evidence:
- `Verified: <claim> — <file:line>`
- `Corrected: <old> → <new> — <file:line>`
Never open with "you're right", praise or apology. Never concede without evidence; never defend without it. A confirmed miss is a system defect, fixed the same turn: add the pattern to the matching lens checklist in `.claude/agents/redteam-lens.md` (or a regression test in `tests/test_redteam_gate.py`) and a `[learned]` line in `.claude/notes/general.md`.

## Scope
Every outward channel (see "What is gated where"). Out of scope: pure internal notes, and code (it has its own audit stack).
