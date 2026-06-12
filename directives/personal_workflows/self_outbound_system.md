# Self-Outbound System — Cold Outreach + Reply Routing

## Goal

Run a self-sustaining cold-outreach engine that finds founder-led SaaS / DTC / agency prospects in US/CA/UK/AU/EU, sends 180–270 personalized emails/day across 6–9 warmed inboxes on 3 owned domains, classifies replies via LLM, auto-responds to positives with a Cal.com link, pages Debanjan on Telegram + Gmail label for hot leads, and books discovery calls. Sole purpose: surface paid project opportunities ($1–2.5K fixed-price builds across the full Claude-Code-buildable category).

The implementation (Cloudflare Worker + config + tests) lives in a **separate public repo**: `github.com/dmazumdar186/outbound-engine`. This directive is the operating SOP — it describes *what* the system does, *how to run it day-to-day*, *what to do when it breaks*, not the code itself.

## When to Use

- **Daily background:** the Worker runs its own crons; you do nothing unless a hot-lead Telegram ping arrives.
- **Hot-lead ping:** book the meeting, do prep, close the deal.
- **Weekly Monday morning:** read the Telegram weekly report; decide if A/B test winners need promoting, if a new ICP segment needs onboarding, if any inbox's mail-tester score has slipped.
- **When you want to add a new tenant / niche / vertical:** edit `config/outbound.json` in the outbound-engine repo, redeploy.
- **When a domain gets blacklisted:** retire the domain, register a new one, run the 4-week warmup, swap in via config.

## Inputs

### Environment Variables (Cloudflare Worker secrets)

| Variable | Purpose |
|---|---|
| `WORKER_SECRET` | `X-Worker-Secret` header on admin/cron endpoints |
| `INSTANTLY_WEBHOOK_SECRET` *(if using Instantly fallback)* | Per-webhook auth for inbound reply notifications |
| `GEMINI_API_KEY` | Google AI Studio — personalization + reply classification (free tier 1,500 RPD) |
| `ANTHROPIC_API_KEY` | Claude Haiku for hot-lead auto-replies only (low volume, pennies/mo) |
| `APOLLO_API_KEY` | Lead sourcing (free tier ~10K emails/mo) |
| `TELEGRAM_BOT_TOKEN` | New bot, distinct from any AM-tied bot |
| `TELEGRAM_CHAT_ID` | Debanjan's personal chat ID |
| `GMAIL_OAUTH_REFRESH_TOKEN` | OAuth for Gmail Push API on the destination Gmail |
| `SMTP_HOST_*`, `SMTP_USER_*`, `SMTP_PASS_*` per inbox | One set per of 6–9 inboxes; provider-agnostic (Hostinger / Migadu / Zoho) |

### Config Files (in outbound-engine repo)

- `config/outbound.json` — ICP definition, geos, thresholds, API URLs, suppression list, inbox roster, daily send caps
- `config/tone.json` — Email voice, never-say list, opener templates (Variants A/B/C from plan)

## Tools / Scripts

### Implementation repo

- `github.com/dmazumdar186/outbound-engine` — Cloudflare Worker, single-file monolith at `src/index.js`. See repo README for build + deploy.

### Related directives in this workspace

- [`directives/gtm_client_workflows/_baseline_worker_checklist.md`](../gtm_client_workflows/_baseline_worker_checklist.md) — every Day-1, Architecture, LLM-guardrail, and Pre-handoff step that this system follows.
- [`directives/infrastructure/canary_monitoring.md`](../infrastructure/canary_monitoring.md) — the `/api/health` + dry-run + scheduled probe pattern, applied verbatim.
- [`directives/personalization/cold_email_sequences.md`](../personalization/cold_email_sequences.md) — *AM-coupled, DO NOT EDIT per AM lockdown.* Reference only for cold-email copy patterns when designing new variants here.

## Outputs

- Live emails sent from 6–9 inboxes at 30/inbox/day (after warmup).
- Replies classified into 5 categories: `hot` / `positive` / `neutral` / `negative` / `auto_reply_or_OOO`.
- Auto-replies to positives with 2–7 min human-timing delay + Cal.com link.
- Telegram pings on hot leads, fired immediately.
- "Interested" label applied to hot replies in `debolshop@gmail.com`.
- Day-2 follow-ups via KV record + cron.
- Weekly Monday 8am Telegram report: `sent / opened / replied / positive / hot / booked`.

## Steps

### Day-to-day (passive)
1. Worker runs unattended via Cloudflare Cron Triggers. No daily intervention.
2. On hot-lead Telegram ping: read the reply, look up the prospect on LinkedIn (~2 min), tailor the discovery-call prep, take the meeting at the booked time.
3. On booked-call Cal.com email: add to calendar, prep 15 min before.
4. Every Monday morning: read weekly Telegram report. If anomalous (sent dropped, replies dropped, opens dropped) → check `/api/health`, check mail-tester scores per domain.

### Adding a new ICP segment / vertical
1. In outbound-engine repo, edit `config/outbound.json` → add new `icp_segment` entry.
2. Update sourcing query (Apollo filters or manual list).
3. Update `config/tone.json` with variant-specific opener if needed.
4. Run `npm run dry-run -- --segment=new_segment` locally. Verify `would_send` is non-zero and rejection reasons are sane.
5. `wrangler deploy` to your personal Cloudflare account.
6. Monitor for 48h before scaling.

### Onboarding a new domain (when one gets blacklisted or volume grows)
1. Register at Cloudflare (.com) or Porkbun (alt-TLD).
2. DNS: SPF, DKIM, DMARC `p=quarantine`.
3. Provision 3 inboxes at chosen mailbox provider.
4. Forward to `debolshop@gmail.com`.
5. Add inbox credentials to Worker secrets: `SMTP_HOST_N`, `SMTP_USER_N`, `SMTP_PASS_N`.
6. Mark inboxes as `warmup` in `config/outbound.json` for 28 days. Worker auto-runs warmup cron.
7. After 28 days + mail-tester score ≥9, flip to `active`. Redeploy.

### Handling a hot-lead Telegram ping
1. Open the reply in your Gmail (filtered "Interested" label).
2. Read the prospect's LinkedIn / company site (~3 min).
3. Reply manually from the booking confirmation email if needed, or let the auto-reply Cal.com link do the work.
4. Prep 15 min before the call — review their company, their probable backlog, your most relevant proof points.
5. After the call: close at $1–2.5K fixed-price, 1–3 weeks delivery. Send a brief written scope.

## Edge Cases

- **Domain blacklisting** — biggest single risk. Check Spamhaus + MXToolbox weekly via `/api/health`. If reputation drops, pull the domain from `active` to `paused` in config, register a replacement, run warmup.
- **Apollo free-tier exhausted** — supplement with Snov.io ($29/mo), LinkedIn Sales Nav free trial, or manual list-building from Crunchbase / ProductHunt / IndieHackers.
- **Gemini free tier hit** — switch to Gemini Pro paid (~$0.15/1M tokens) temporarily or rotate to Claude Haiku ($0.25/1M).
- **Reply classifier confuses auto-reply/OOO for positive** — refine classifier prompt; add explicit OOO-text patterns to a hard-rule pre-filter.
- **Gmail Push API silence** — polling fallback runs every 30 min. If both go silent, the canary will alert. Re-auth OAuth refresh token.
- **Cal.com double-booking** — Cal.com handles this natively; if it ever happens, the Cal.com booking flow will block the conflicting slot.
- **AM lockdown** — this system uses entirely separate accounts, domains, inboxes, credentials, and a separate Cloudflare account. Do not import code or copy paths from `execution/infrastructure/api-proxy/`. See `CLAUDE.local.md` "ACCESSORY MASTERS — LOCKDOWN" for the no-touch list.
- **GDPR opt-out received** — Worker honors automatically (suppression KV). If a recipient explicitly emails "unsubscribe" without using the link, the classifier routes to `negative` and the contact lands in suppression permanently.

## Exit Criteria

- `GET <worker-url>/api/health` returns HTTP 200 with `status` field — confirms the Worker is deployed and reachable.
- `npm run dry-run -- --segment=<segment>` (run locally from the outbound-engine repo) exits `0` and prints `would_send > 0` with non-zero `rejection_reasons` breakdown — confirms the pipeline would process real inputs without paying credits.
- At least one inbox in `config/outbound.json` has `"state": "active"` (warmup complete) and `mail-tester.com` score ≥ 9 for that domain.
- A hot-lead Telegram ping arrives within 5 minutes of manually triggering the reply-classification path with a "ready to sell" sample reply (confirms Telegram bot credentials are valid and chat ID is correct).
- `GEMINI_API_KEY` or `ANTHROPIC_API_KEY` is set as a Cloudflare Worker secret (`wrangler secret list` shows it present) — no `missing key` errors in Worker logs.

## Changelog

- **2026-05-16** — Initial version. Codifies the self-outbound build for Debanjan's personal outreach. Implementation in `github.com/dmazumdar186/outbound-engine`. Plan trace: `~/.claude/plans/what-were-your-biggest-parsed-babbage.md` (v2/v3 sections under "Self-Outbound System").
