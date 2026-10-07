# Jev Email Gate — put Jev in front of your AI email agent

## Purpose

If an AI agent answers your email, it pays a big model to read every message, spam included.
Jev (TypeSafe, via OpenRouter's Decisions API) reads the inbox first for ~$0.00003/email,
tags each message, and only the emails that need writing go to Claude. The agent reads less;
the token bill drops. (RoboNuggets use case #11: 1,700 emails sorted for ~18 cents.)

## When to invoke

- Before any agent drafts replies to a batch of inbox emails.
- Inbox triage where spam/newsletters should never reach a large model.

Copy-paste operator prompt:

> Gate my inbox with Jev and only hand me what needs a reply

## Flow (three steps)

1. **Fetch**: `python3 .claude/skills/gmail-label/scripts/gmail_label_fetch.py --account <acct> --output .tmp/emails.json` (see `.claude/skills/gmail-label/SKILL.md` for flags).
2. **Gate**: `python3 execution/google/jev_email_gate.py --input .tmp/emails.json --agent-queue .tmp/agent_queue.json --labels-out .tmp/jev_labels.json`
3. **Agent + labels**: the agent reads ONLY `.tmp/agent_queue.json` (sorted context: `jev_bucket`, `jev_urgency`); then `python3 .claude/skills/gmail-label/scripts/gmail_label_apply.py --account <acct> --input .tmp/jev_labels.json` (`--dry-run` first). Emails routed `human` are labelled `Jev/Review` for the operator.

## Inputs

- `--input PATH`: gmail_label_fetch.py output (`id, subject, from, date, snippet`) or flat `{id, from, subject, body, date}` list.
- `--min-confidence 0.6`, `--workers 8`, `--limit N`, `--dry-run` (prints questions, calls nothing).
- Env: `OPENROUTER_API_KEY` (also `OPENROUTER_API_TOKEN` / `OPENROUTER_API_TOEKN`).

## Outputs

- `--output` (default `<input>.gate.json`): summary + per-email `bucket, confidence, reply_urgency, urgency_label, is_scam, human_sent, route, cost_usd, error`.
- `--agent-queue`: JSON list of agent-routed emails only. `--labels-out`: `{"Jev/Needs Reply": [ids], "Jev/Brand Deal": [...], "Jev/Spam": [...], "Jev/Review": [...]}`. `--csv-out`.
- stdout summary: counts per bucket/route, emails and % of input bytes sent to the agent, scam flags, cost, wall time, projected cost for 1,700 emails. Ledger row `caller: jev_email_gate`.

## Routing (code-side, deterministic)

- `agent`: bucket in {needs_reply, brand_deal_or_partnership, customer_or_client}, is_scam < 0.5, confidence ≥ threshold.
- `human`: is_scam ≥ 0.5 AND human_sent ≥ 0.6 (possible targeted phishing), confidence below threshold, or Jev error (fail-safe).
- `archive_or_skip`: everything else (newsletters, bulk spam, fyi, personal).

## Scripts (Layer 3)

- `execution/google/jev_email_gate.py` (shared client `execution/modules/jev_client.py`). Tests: `tests/test_jev_email_gate.py`.

## Edge cases

- gmail_label_fetch snippets are truncated to 120 chars; that is enough for bucketing but lowers confidence on nuanced mails — more go to `human`, never wrongly to `agent`.
- Jev failure fails open to `human`, so nothing is silently dropped.
- Threshold tuning: build a labelled set and run `execution/infrastructure/jev_validate.py` (directive `directives/infrastructure/jev.md`); raise `--min-confidence` if the agent gets junk, lower it if `Jev/Review` overflows.
- Live test 2026-10-07 (15 synthetic emails): podcast invite and a client bug report scored 0.44 confidence → `human`; gift-card CEO-impersonation correctly flagged scam + human-sent → `human`.

## Changelog

- 2026-10-07: Created (use case #11). Live 15-email run: 4 to agent (35% of input bytes), $0.00045 total, projected $0.05 per 1,700 emails.
