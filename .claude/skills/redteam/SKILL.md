---
name: redteam
description: Mandatory red-team gate before ANY outward text is sent, drafted to Gmail, or handed to the operator as final: emails, negotiation replies, proposals, offers, pitches. Triggers on "red team", /redteam.
user_invocable: true
---

# Red team gate

Script: `G="python3 execution/infrastructure/redteam_gate.py"`. Lenses: counterparty, grounding, downside, reputation. Directive: `directives/infrastructure/redteam_gate.md`.

## What is gated where
- **Hard-gated by hooks:** Gmail send/reply/forward/drafts (every text field + subject, recipients, attachments); Calendar invites (attendees ⊆ recorded `--to/--cc/--bcc`; update_event unless `notificationLevel: NONE`); Bash commands that *execute* something (python/node/curl/sh...) and send email inline, incl. `python -m`, stdin heredocs, `base64 -d |` interpreter. File writes, greps, commits pass; committed unmodified pipeline scripts still run.
- **Ledger:** rows are HMAC-signed (`~/.claude/redteam/hmac.key`) by hooks and a passing `record` only; unsigned/edited rows are ignored.
- **Also hard-gated:** Bash sends to Slack/Teams/Discord/Google Chat, LinkedIn, Instantly/lemlist/Smartlead, X, Meta/WhatsApp, Telegram, Twilio (committed pipelines still run); MCP share/permission tools (recipients ⊆ a recorded `--to/--cc/--bcc`; share message must be passed) and post_message/send_/publish/reply_to_thread/create_post/tweet/create_message/send_dm/comment/schedule_message tools (body/text-like fields passed, ids ignored; channel or public audiences need an operator waiver; get*/list*/read*/... are reads); `wrangler`/`vercel --prod`/`netlify --prod` deploys only from a committed, clean dir.
- **Skill-gated only (you are the gate):** docs, decks, proposals, text handed to the operator, and anything sent by a route the hooks do not name. Same runbook, no "quick" exemption.

## Runbook
0. **Save and source.** Write the exact text to send to `.tmp/redteam/drafts/<slug>.txt` (+ `<slug>.html` if an HTML body will be sent; no `<script>`/`<style>` content, links count as text). Gather sources: full thread, brief, price sheet, contract, prior commitments, the operator's stated positions (quote them into GOAL). A missing source is a BLOCKER: name it; never fill the gap from memory. Never pass an earlier version of the draft as a source (it is skipped as "looks like the draft itself").
1. **Ground.** `$G ground --draft D --sources S... --json`. Every `ungrounded` and `weak` claim must be removed or sourced (weak fails). Names (Title-Case words, emails) must appear in a source: an ungrounded name usually means the thread is missing from SOURCES, so add it rather than rewording. Treat every `overclaim` as a question for the lenses.
2. **Lenses.** `$G sha --draft D`, then fan out all four lenses in ONE message as parallel Agent calls with `subagent_type: redteam-lens` (only those runs are logged by SubagentStop). Brief = LENS, DRAFT path, DRAFT-SHA, SOURCES paths, GOAL; never your reasoning or a desired verdict. Save each returned text **verbatim** to `.tmp/redteam/verdicts/<slug>.<lens>.md`; an edited or hand-written verdict file is refused.
3. **Fix loop.** Any FAIL → fix the draft → new sha → rerun `ground` and ALL four lenses. Max 3 rounds. Still failing → do not send; tell the operator which findings remain and what decision or source resolves each.
4. **Record, then send.** `$G record --draft D --sources S... --verdicts V1 V2 V3 V4 --subject "<exact subject>" --to A... [--cc A...] [--bcc A...] [--attachments FILE...]`, then send or draft the saved text byte for byte with exactly that envelope. Calendar: record the description with `--subject "<event summary>"`. Any edit after record = rerun from step 1.
5. **Receipt** (chat only, never inside the deliverable), 3 lines:
   - `Claims grounded N/N against K sources`
   - `Lenses 4/4 PASS in R rounds`
   - `Residual risks:` one per line, or `none`
   No hedging, no apology prose.

**Waiver: operator only.** If the operator wants to ship without the gate, they type `redteam waive <sha12> <reason>` as their own prompt (give them the sha12). You cannot waive: `$G waive` exits 2, hook subcommands refuse without the hook environment, and signing rows with the key yourself is forgery. Never ask for a waiver to save time.

## When the operator pushes back
Re-verify the challenged point against the source before replying. Answer with evidence:
- `Verified: <claim> — <file:line>`
- `Corrected: <old> → <new> — <file:line>`
No "you're right", praise or apology; never concede or defend without evidence. A confirmed miss is fixed the same turn: add it to the lens checklist (`.claude/agents/redteam-lens.md`) or a test, plus a `[learned]` note.

Out of scope: internal notes and code (own audit stack).
