# Baseline Worker Engagement Checklist

Apply on every new `gtm_client_workflows` engagement that uses the Cloudflare-Worker / cron / KV / cold-email shape. Distilled from the Accessory Masters build so the next client doesn't relearn 27 audit rounds' worth of findings.

This is a meta-directive: a static checklist consumed at project kickoff, mid-build, and pre-handoff. Not tied to a single execution script.

## Goal

Ensure every new cold-email / GTM Worker pipeline ships with the operational, security, and quality defaults already proven in production, without rediscovering them through audit rounds.

## When to Use

- **Project kickoff (Day 1):** walk the "Day 1" section before scoping or writing any code.
- **Mid-build, per phase:** consult the "Architecture defaults" and "LLM guardrails" sections when implementing the relevant subsystem.
- **Before deploy / handover:** walk the "Pre-handoff" section to verify nothing was skipped.

## Inputs

| Input | Purpose |
|-------|---------|
| Client transcript / scope doc | Read line-by-line on first pass; extract every concrete scope item verbatim |
| Tenant slug | Used for config keying (`config/<tenant>.json`, `branding.json` entries) |
| Notification preference | Telegram / Slack / both — decided **on Day 1**, not late |
| API credit budget (monthly) | Per provider (Serper, Apollo, Million Verifier, OpenRouter, etc.) — surfaced before model selection |

## Tools/Scripts

| Reference | Purpose |
|-----------|---------|
| `directives/personalization/cold_email_sequences.md` | Cold email copy + sequencing (must include one-and-done + day-N follow-up baseline) |
| `directives/infrastructure/domain_inbox_management.md` | Domains, inboxes, warmup |
| `~/.claude/CLAUDE.md` → "Technical patterns — cloud Worker / cron / KV / cold-email backends" | Cross-workspace baseline for these patterns |
| `C:\Users\deban\dev\anneal\` | Audit loop CLI for hardening the diff |

## Outputs

- A scoped engagement where every item in the Steps below has been satisfied or explicitly waived with the user.
- A `HANDOFF.md` updated incrementally, not at the end.
- An `/api/health` endpoint visible in the dashboard.

## Steps

### Day 1 — before writing code

1. **Budget conversation.** Confirm monthly spend ceiling for LLM + paid APIs. This precedes model selection.
2. **All-credentials checklist.** List every API key / bot token / account the project will need across all phases. Ask the client to provision them now, not when each phase starts.
3. **Notification surface decision.** Ask the operator which channel they actually check (Telegram / Slack / email digest). Build to that, not to the default.
4. **Scope ingestion line-by-line.** Extract every concrete scope item from the client transcript. Mark in-scope or out-of-scope explicitly. Save the in/out list to the project's plan file.
5. **Architecture default: single Cloudflare Worker.** Don't fragment into multiple services unless a concrete constraint forces it.
6. **Config schema.** Define `config/<tenant>.json` shape upfront. Required keys, types, defaults.
7. **Branding registry.** Add tenant to `branding.json` keyed by slug. Every user-facing string references it. Rebrand = one-line config change.
8. **Audit checklist seed.** Copy the "Known bug classes" section below into a project-local `audit_checklist.md` the audit agent reads first on every round.

### Architecture defaults — apply when implementing the relevant subsystem

9. **Worker boot:** call `validateConfig()` first. Fail-fast on missing required keys, wrong types.
10. **Auth:** `X-Worker-Secret` header check on every admin / cron-triggerable endpoint (`/api/run-pipeline`, `/api/process-replies`, `/api/weekly-report`, anything destructive). Separate per-webhook secret tokens for inbound webhooks. `ALLOWED_ORIGINS` env var for CORS.
11. **State:** KV with TTL for cross-run dedup (e.g. 60d for "seen prospect"). Idempotency sentinel keys for retryable cron tasks — write sentinel before action; rollback on failure.
12. **Reply detection:** dual-path — webhook receiver **plus** polling fallback (e.g. cron every 30 min, offset from `:00`). Don't rely on either alone.
13. **Rate-limit math:** before writing any per-item loop, compute `per_item_delay_ms × max_items` and confirm it stays under the platform request cap (CF Workers = 15 min). Document the math in a comment.
14. **`--dry-run` mode:** first-class flag on every cost-incurring endpoint. Returns `would_*` counters. No external calls in dry-run.
15. **`/api/health` endpoint:** surfaces upstream credit balances + secret presence + last cron run timestamps. Dashboard pulls from this — operators see "Serper has 2 credits left" before it bites.
16. **Per-campaign kill switch** surfaced in the operator dashboard. Operator should never need to redeploy to pause a campaign.

### LLM guardrails — apply on every LLM call that lands in user-facing output

17. **Output limits:** max sentences, max words enforced in code (not just prompt-side).
18. **Strip dollar amounts and exclamations** from generated copy before sending.
19. **Voice reference in the system prompt.** Reference `config/tone.json` examples + never-say list.
20. **Empty-response safe fallback.** Never send an empty body; fall back to a templated safe reply.
21. **Pre-classification filter** for auto-reply / OOO / vacation mail. Don't route these to the positive/negative classifier — they'll be misread.

### Cold-email sequencing — baseline behaviors

22. **One-and-done auto-reply gate.** Bot sends one helpful reply, then hands off to human. Don't loop bot replies. Tracked via KV record.
23. **Day-N follow-up** scheduled via KV record + cron scan. Standard, not a bolt-on at the end.
24. **Manual exclusion list** honored before any send.

### Process — apply throughout

25. **One current plan file per project**, updated in place. Don't accumulate.
26. **AskUserQuestion batched (4 per call).** No sequential single-question rounds.
27. **Sonnet for sub-agents.** Opus for orchestration, planning, audit synthesis.
28. **Per-feature audit + commit + deploy.** Not big-bang.
29. **Audit on the diff, not the full file.** `git diff` since last clean round.
30. **Incremental `HANDOFF.md`.** Updated after each milestone with deployed URLs, secrets-set status, outstanding tasks, common ops commands.

### Pre-handoff

31. **All secrets confirmed set** in the Worker (not just `.env`).
32. **`/api/health` returns green** across every upstream.
33. **One full E2E run completed** in dry-run, then once live with a known test lead.
34. **`HANDOFF.md` final pass:** outstanding tasks listed with owner and ETA.
35. **Idempotent setup scripts** committed for any one-time provisioning (webhook registration, secret rotation, DNS setup) — so handover doesn't depend on lost commands in chat history.

## Edge Cases — known bug classes to seed into `audit_checklist.md`

These are the recurring classes that consumed audit rounds 6–27 of the Accessory Masters build. Codify them so they're caught in round 1, not round 21.

- **Auth gap:** new admin/cron endpoint added without `X-Worker-Secret` check.
- **KV delete-before-action:** `KV.delete()` outside the `try` block in retryable handlers → permanent loss on exception.
- **Empty-LLM-response unhandled:** generator returns empty string, downstream uses it as-is.
- **Auto-reply / OOO misclassified:** routed to positive/negative classifier without pre-filter.
- **Config flag silently dropping data:** missing `include_*` flag in tenant config silently halves coverage (e.g. AM lost 83% leads via missing `include_suburbs`).
- **Rate-limit math vs platform timeout:** per-item delay × N items exceeds CF Workers' 15-min cap.
- **Hot-lead signal negation gap:** signal matching that doesn't account for negations ("not interested in growth" matched as "growth").
- **Pause-not-per-campaign:** pausing one campaign accidentally pauses others.
- **Objection-response guardrail missing:** LLM allowed to make commitments / quote prices / commit to meetings in auto-replies.
- **CONFIG drift:** Worker's embedded CONFIG out of sync with `config/<tenant>.json`.
- **Unauthenticated `/api/run-pipeline`:** any cron-triggerable endpoint that runs cost-incurring work without auth.
- **Missing calendar_id / external ID** in CRM endpoint config.
- **Empty-config fields treated as valid** instead of failing validation.

## Changelog

- **2026-05-14** — Initial version. Codifies learnings from Accessory Masters (27 audit rounds, May 5–13 2026 build). See `~/.claude/plans/what-were-your-biggest-parsed-babbage.md` for the retrospective that produced this checklist.
