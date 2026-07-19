# Self-Outbound System — Cold Outreach + Reply Routing (v2 / Blueprint A2)

> **Status (2026-07-19):** v2 rearchitected from 1-mailbox / 1-domain / 14-day-warmup to **30 mailboxes on 10 domains** (Primeforge 25 + Litemail Pro 5, Nick Abraham rotation model). Pre-warmed 4-12wk history via vendor pools — no 21-day organic wait. **See canonical execution plan at `~/.claude/plans/eventual-meandering-tarjan.md`** for full architecture, cost breakdown, timeline, vendor tier list, KPI thresholds, panel-pass audit, and Phase 3 research (scale math + realistic reply-rate benchmarks + exhaustive vendor deep-dive).
>
> Sending platform: **Instantly Hyper Growth Outreach** (€89/mo, 125k emails/mo, unlimited connected mailboxes + unlimited warmup slots). Confirmed via 2026-07-19 billing screenshot — NOT SuperSonic Credits as Lenore initially indicated.
>
> **Historical status (2026-07-08):** v2 active. v1 (Cloudflare Worker + raw SMTP × 6–9 inboxes on 3 domains, referenced repo `github.com/dmazumdar186/outbound-engine`) was **deprecated** — repo scaffolded but never deployed, no live domain reputation at stake. v2 originally scoped to 1 warmed inbox on 1 secondary domain for validation; scaled to 30 on 2026-07-19 per operator decision + Phase 3 research (Nick Saraev's 500-1000 sends/variant/week statistical floor + realistic 0.3% reply rate for FR fractional PM ICP × solo-serving ceiling of 3-4 concurrent engagements).

## Goal

Run a self-sustaining cold-outreach engine that finds founder-led SaaS / DTC / agency prospects and Heads of Product / Ops at scaleups, sends ~450 personalized emails/day (30 mailboxes × 15/day week 1, ramping to 30/day steady state) from **30 pre-warmed Google Workspace mailboxes on 10 secondary domains**, classifies replies via LLM, auto-responds to positives with a Cal.com link, pages Debanjan on Telegram + Gmail label for hot leads, and books discovery calls. **Sole purpose: surface fractional PM engagements (€5-15k/mo × 3-month typical), target €15-30k MRR band at 3-4 concurrent clients per solo-serving ceiling.**

The system MUST NOT fail like `job_search_v2` did in June 2026 (fixture-only synthetics green while live pipeline produced 0 jobs/day for 3 days). Every phase gate is a LIVE assertion against real infrastructure, not a mock. Front-door synthetic + output-acceptance gate + 6-auditor mandatory stack apply.

## Inputs

### Environment Variables (in `.env`)

| Variable | Purpose | Phase gated |
|---|---|---|
| `INSTANTLY_API_KEY` | Instantly Growth tier API access | Phase 1 |
| `INSTANTLY_WEBHOOK_SECRET` | HMAC secret on inbound reply webhook | Phase 1 |
| `INSTANTLY_CAMPAIGN_ID` | ID of the primary cold campaign (set after Phase 1) | Phase 1 |
| `INSTANTLY_INBOX_EMAILS` | Comma-separated list of ALL 30 warmed inbox addresses across 10 domains (`debanjan@d1.com,debanjan@d2.co,...`). Legacy `INSTANTLY_INBOX_EMAIL` (singular) preserved as first-of-list fallback for canary probes only. | Phase 1 |
| `ANTHROPIC_API_KEY` | Claude Sonnet 4.6 for personalization + reply classification | already present |
| `APIFY_API_TOKEN` | Free-tier $5/mo credit — Google Maps + LinkedIn Actors | Phase 1 |
| `MILLION_VERIFIER_API_KEY` | Email verification (~€0.005/hit) | already present |
| `TELEGRAM_BOT_TOKEN` | NEW bot, distinct from any AM-tied bot | Phase 1 |
| `TELEGRAM_CHAT_ID` | Debanjan's personal chat ID | Phase 1 |
| `GMAIL_OAUTH_REFRESH_TOKEN` | OAuth for Gmail Push API on `debolshop@gmail.com` (destination) | Phase 1 |
| `CAL_COM_BOOKING_URL` | Public booking page URL | Phase 1 |
| `MAILTESTER_EMAIL` | The mail-tester.com email address (rotates per test) | Phase 1 |
| `SECONDARY_DOMAINS` | Comma-separated list of all 10 secondary domains (`prodcraft-outreach.com,prodcraft.co,prodcraft.io,...`). Legacy `SECONDARY_DOMAIN` (singular) preserved as first-of-list fallback for canary probes only. | Phase 1 |
| `KILL_SWITCH` | `1` to pause all sends without touching Instantly UI (safety valve) | ongoing |

### Config Files (in `execution/personal_workflows/self_outbound_system/config/`)

- `icp.json` — ICP definition, mirrors `execution/personal_workflows/personal_brand/icp_and_positioning.md` (Founders / SMEs / VCs-as-referrers / Heads of Product). Segment → daily-send-cap → variant map.
- `tone.json` — Email voice (from `personal_brand/icp_and_positioning.md` Outcomes-not-tech table + Proof spine), never-say list, opener templates (Variants A/B/C).
- `suppression.json` — Permanent opt-outs (GDPR-compliant, 30d minimum retention proof).
- `.env.template` — All variables above, sanitized.

## Tools / Scripts

Implementation lives IN THIS WORKSPACE under `execution/personal_workflows/self_outbound_system/`:

| Script | Purpose | Phase |
|---|---|---|
| `run.py` | Daily entrypoint. Orchestrates source → enrich → filter → personalize → upload → digest. Reads `KILL_SWITCH`; halts if `1`. | Phase 3 |
| `sourcer.py` | Apify Google Maps Actor + LinkedIn public-profile Actor. Stays under $5 CU/mo. Fallback: Hunter free 25/mo, or manual list from Crunchbase/PH/IH. | Phase 3 |
| `enricher.py` | Reuses `execution/enrichment/anymailfinder_lookup.py` + `execution/enrichment/million_verifier.py` for email find + verify. | Phase 3 |
| `icp_filter.py` | Reads `icp.json`. Filters raw leads by the 3-signal rule (outcome + budget + urgency). Rejects anti-ICP (equity-only, junior-dev-by-hour, enterprise procurement). | Phase 3 |
| `personalizer.py` | Sonnet 4.6 with prompt caching. Generates: 1 subject line + 1 opener line (≤15 words, outcome-oriented per `tone.json`). ~€1.60/mo for 600 leads. | Phase 3 |
| `instantly_client.py` | Wraps Instantly Growth API. Uploads leads to campaign, reads campaign stats, pauses/resumes. Reuses `execution/modules/outputs/instantly.py` as base. | Phase 3 |
| `webhook_receiver.py` | Cloudflare Worker (deployed separately) receives Instantly reply webhook, HMAC-verifies, classifies via Sonnet, routes hot leads to Telegram + Gmail label. | Phase 3 |
| `reply_classifier.py` | Sonnet 4.6 classifies replies into 5 buckets: `hot` / `positive` / `neutral` / `negative` / `auto_reply_or_OOO`. | Phase 3 |
| `digest.py` | Nightly digest to Telegram + `debolshop@gmail.com`: `sent N / opened O / replied R / positive P / hot H / bounced B / canary=OK\|FAIL / warmup day X of 14`. | Phase 3 |
| `canary.py` | Front-door synthetic. Sends 1 real email/day to a monitored inbox, asserts inbox placement (not spam) via mail-tester.com scoring + IMAP check of the destination. Hard-fails the daily run if placement fails. | Phase 3 |
| `acceptance.py` | Output-acceptance gate. Reads Instantly campaign stats at end of day; asserts sends>0, bounce_rate<5%, unsubscribe_rate<0.3%, complaints=0. Hard-fails if any breach. | Phase 3 |
| `killswitch.py` | One-shot: sets `KILL_SWITCH=1` in `.env` and pauses Instantly campaign via API. | Phase 3 |

### Related directives

- [`directives/personal_workflows/personal_brand/icp_and_positioning.md`](../personal_brand/icp_and_positioning.md) — ICP + wedge + proof spine. **Source of truth** for `icp.json` + `tone.json`.
- [`directives/infrastructure/setup_instantly_webhook.md`](../../infrastructure/setup_instantly_webhook.md) — Cloudflare Worker webhook receiver pattern.
- [`directives/infrastructure/domain_inbox_management.md`](../../infrastructure/domain_inbox_management.md) — Secondary-domain DNS + inbox provisioning patterns.
- [`directives/infrastructure/canary_monitoring.md`](../../infrastructure/canary_monitoring.md) — `/api/health` + dry-run + scheduled probe pattern.
- [`directives/gtm_client_workflows/_baseline_worker_checklist.md`](../../gtm_client_workflows/_baseline_worker_checklist.md) — Day-1, Architecture, LLM-guardrail, Pre-handoff checks.
- **AM-locked, do NOT edit or copy from:** `directives/personalization/cold_email_sequences.md`, `directives/gtm_client_workflows/accessory_masters_*`, `execution/infrastructure/api-proxy/`.

## Outputs

- ~450 personalized cold emails/day (week 1: 30 mailboxes × 15/day; steady state from week 2: 30 mailboxes × 30/day = ~900/day), all sent from 30 pre-warmed GWS mailboxes on 10 secondary domains (Primeforge 25 + Litemail Pro 5).
- Replies classified into 5 buckets; hot leads route to Telegram within 3 minutes + Gmail "Interested" label.
- Auto-replies to `positive` leads with 2–7 min human-timing delay + Cal.com link.
- Day-2 auto-follow-up on non-openers via Instantly sequence step.
- Nightly digest to Telegram + email: `sent / opened / replied / positive / hot / bounced / canary`.
- Weekly Monday 08:00 Paris digest with 7-day rollup.
- Suppression list synced daily (GDPR opt-outs, hard bounces).

## Steps

### Phase 1 — Provisioning (operator-driven, ~1 day of clock time, ~€10 immediate spend)

**Order matters.** Each step blocks the next. Expected total: 2–3 hours of hands-on time + up to 24h DNS propagation.

#### 1.1 Register secondary domain (Porkbun, ~€10/yr = €0.85/mo)

- Go to [porkbun.com](https://porkbun.com), search a domain that is:
  - Related to the brand (`prodcraft-outreach.com`, `prodcraft-mail.com`, `prodcraft-connect.com`) but **NOT** the primary `prodcraft.fyi` — cold outreach must never touch the primary domain's reputation.
  - `.com` preferred (best deliverability). `.io` acceptable. Avoid new gTLDs (`.xyz`, `.click`, `.online`) — Gmail treats them harshly.
- Enable free WHOIS privacy at checkout (Porkbun default).
- Cost: ~$11.06/yr for `.com`. Pay from personal card.

#### 1.2 Google Workspace Business Starter seat (~€8.28/mo TTC)

- Go to [workspace.google.com/pricing](https://workspace.google.com/pricing), pick **Business Starter**.
- During signup, use the secondary domain from 1.1 as the primary Workspace domain.
- Verify domain ownership via TXT record (Google walks you through it).
- Create ONE user: `debanjan@<secondary-domain>.com` (or similar first-name-only, professional).
- **Do not** connect to primary `prodcraft.fyi` Google account — this is a standalone tenant.

#### 1.3 DNS records: SPF + DKIM + DMARC (all set at Porkbun)

At Porkbun DNS panel, add:

- **SPF (TXT on root `@`):** `v=spf1 include:_spf.google.com ~all`
- **DKIM:** Google generates in Workspace Admin → Apps → Google Workspace → Gmail → Authenticate email. Copy the TXT record + host into Porkbun. Wait for propagation, then click "Start authentication" in Google.
- **DMARC (TXT on `_dmarc.<domain>`):** `v=DMARC1; p=quarantine; rua=mailto:debanjan@<secondary-domain>.com; adkim=s; aspf=s`
- Wait 24h for propagation. Verify at [mxtoolbox.com/emailhealth](https://mxtoolbox.com/emailhealth) — all three should be green.

#### 1.4 Baseline deliverability test (mail-tester)

- Send a plain test email from the new inbox to a fresh mail-tester.com address.
- Score MUST be ≥9/10 before proceeding. If <9, fix flagged issues (usually DKIM alignment).

#### 1.5 Instantly.ai Growth signup (~$37/mo ≈ €34)

- Go to [instantly.ai/pricing](https://instantly.ai/pricing), pick **Growth** (or the current entry tier that includes API + webhooks — verify at signup).
- **Choose EU data-center** during signup (GDPR-friendlier for a France-based operator).
- Connect the GWS inbox via Google OAuth.
- Enable Instantly's native warmup pool on the inbox. Do NOT start any campaign yet.
- Generate API key + webhook secret. Store in `.env` as `INSTANTLY_API_KEY` and `INSTANTLY_WEBHOOK_SECRET`.

#### 1.6 Cal.com booking link + Telegram bot

- Cal.com: create a 30-minute "Free Build Session" event, no payment, min-notice 12h. URL → `.env` as `CAL_COM_BOOKING_URL`.
- Telegram: create a new bot via @BotFather (name: e.g. `ProdCraftOutboundBot`). Get chat ID by messaging the bot then hitting `https://api.telegram.org/bot<TOKEN>/getUpdates`. Store token + chat ID in `.env`.

#### 1.7 Apify free-tier account + API token

- Sign up at [apify.com](https://apify.com), free tier gives $5/mo credit.
- Generate API token → `.env` as `APIFY_API_TOKEN`.

**Phase 1 exit criteria:**
- MXToolbox emailhealth = green on all 3 records
- mail-tester = ≥9/10
- Instantly inbox connected + warmup enabled
- All env vars in `.env`
- Total monthly commitment starts: ~€48/mo TTC (€34 Instantly + €8 GWS + €1 domain amortized + Sonnet variable + Million Verifier variable). **This is the point of no return on the €48/mo budget — confirm before proceeding to Phase 2.**

### Phase 2 — Warmup (14 days, passive, no operator action)

- Instantly's warmup pool auto-exchanges positive signals with other Instantly warmup inboxes.
- Daily warmup volume ramps from ~10/day to ~40/day over 14 days.
- **NO COLD EMAIL SEND during warmup.** Zero exceptions.
- Monitor daily: check Instantly warmup score at the end of each day.

**Phase 2 exit criteria:**
- Day 14 elapsed
- Instantly warmup score ≥85
- Second mail-tester test still ≥9/10
- No spam-folder placement on any warmup exchange (Instantly reports this)

### Phase 3 — Build pipeline (behind kill switch, dry-run only)

Scaffold `execution/personal_workflows/self_outbound_system/` per the Tools/Scripts table above. Every script MUST:

- Have module-level docstring with `description:`, `inputs:`, `outputs:` per workspace `python-execution.md` rule.
- Load `.env` via `dotenv` at top.
- Follow the 6 Python hardening rules (`~/.claude/rules/python-hardening.md`): utf-8 subprocess encoding, threading locks on shared state, LLM-supplied path validation, cache-aware Sonnet pricing, no bare-except, `dict(os.environ)` not `copy.copy(os.environ)`.
- Support `--dry-run` mode: makes zero paid API calls, returns `would_*` counters.

Build order (each committed independently):
1. `sourcer.py` — Apify Google Maps Actor wrapper. Dry-run returns fixture leads.
2. `icp_filter.py` — reads `icp.json`, rejects anti-ICP. Test corpus: 10 known-bad leads (equity-only, junior gigs, enterprise) MUST all reject; 10 known-good MUST all pass.
3. `enricher.py` — wraps existing `anymailfinder_lookup.py` + `million_verifier.py`.
4. `personalizer.py` — Sonnet with prompt caching. System prompt (400 tokens from `tone.json`) cached across the day.
5. `instantly_client.py` — Instantly API wrapper. Dry-run uses `would_upload` counter.
6. `webhook_receiver.py` — Cloudflare Worker. Deploy separately via `wrangler`. HMAC-verifies Instantly signature.
7. `reply_classifier.py` — Sonnet classifier. Fixture: 20 known replies (5 per class × 4 non-`auto_reply` classes + 5 auto-replies) MUST route correctly.
8. `digest.py` — Nightly digest.
9. `canary.py` — front-door synthetic (see below).
10. `acceptance.py` — output-acceptance gate (see below).
11. `killswitch.py` — one-shot pause.
12. `run.py` — orchestrator that calls 1→9 in order; reads `KILL_SWITCH` first and halts if `1`.

**Front-door synthetic (`canary.py`, mandatory):**
- Sends 1 real email/day from the warmed inbox to a monitored address I control (Gmail).
- Reads inbox 5 min later, asserts email arrived in PRIMARY (not Spam / Promotions).
- Uses mail-tester.com's programmatic email address (rotates per test) as a cross-check.
- Runs BEFORE `run.py` fires the daily send. If canary FAILS, `run.py` halts the day, digests `canary=FAIL`, no cold sends.
- Independent — does NOT reuse the pipeline's own filters/classifiers to check itself.

**Output-acceptance gate (`acceptance.py`, mandatory):**
- Runs at end of day AFTER Instantly has sent.
- Reads Instantly campaign stats via API: `sends`, `bounces`, `unsubscribes`, `complaints`, `hard_bounces`.
- Hard-fails the day if: `sends == 0` OR `bounce_rate > 5%` OR `unsubscribe_rate > 0.3%` OR `complaints > 0`.
- **Frozen regression corpus** at `tests/acceptance_corpus.json`: 20 known-bad leads (wrong-language, wrong-ICP, junk domain, catchall) that MUST be rejected upstream, 12 known-good that MUST be kept. Runs after every code change; corpus catches the shared-oracle blind spot (per `~/.claude/rules/output-acceptance-gate.md` Exhibit B).

**Phase 3 exit criteria (front-door + acceptance MUST hold 5 consecutive days IN DRY-RUN MODE):**
- All 12 scripts committed, docstring'd, hardening rules pass
- Front-door canary PASS × 5 consecutive days (still against monitored inbox; no cold sends)
- Output-acceptance gate PASS × 5 consecutive days
- Frozen corpus 32/32 PASS
- 6-auditor mandatory audit stack fires and all report PASS (per `~/.claude/rules/mandatory-audit-stack.md`)

### Phase 4 — Go-live canary week (15 emails/day for 7 days)

- Enable `KILL_SWITCH=0`.
- Cap daily send in Instantly campaign at 15/day (below the eventual 20).
- Monitor: canary daily, acceptance daily, digest daily.
- Any single day of FAIL → auto-halt via `killswitch.py`, digest to Telegram, root-cause required before resume.

**Phase 4 exit criteria:**
- 7 consecutive days green
- Inbox placement ≥90% (measured via GlockApps 2 tests over the week — free tier)
- Bounce rate <3%
- Zero spam complaints
- Kill-switch tested (fire it once mid-week, verify sends stop within 1 hour)

### Phase 5 — Steady state (20 emails/day, weekly review)

- Ramp Instantly cap to 20/day.
- Monday 08:00 Paris weekly digest reviewed by operator.
- Anomaly (sends dropped, replies dropped, opens dropped) → check `/api/health` on webhook Worker, check mail-tester score, page operator via Telegram.

### Day-to-day (Phases 4–5, passive)

1. Worker runs unattended. Operator does nothing unless a hot-lead Telegram ping arrives.
2. **Hot-lead ping**: read reply → check prospect's LinkedIn (~2 min) → the auto-reply already sent the Cal.com link → prep 15 min before the call.
3. **Booked call**: add to calendar; prep 15 min; close at €1–2.5k fixed-price, 1–3 weeks delivery; send brief written scope.
4. **Monday morning**: read weekly Telegram digest. If anomalous → check `/api/health` + mail-tester + `canary.py` last 7 runs.

### Adding a new ICP segment / vertical

1. Edit `execution/personal_workflows/self_outbound_system/config/icp.json` — add new segment.
2. Add matching entry to `tone.json` if voice differs by segment.
3. Update Apify Actor query if source list differs.
4. Run `py execution/personal_workflows/self_outbound_system/run.py --dry-run --segment=<new>`. Verify `would_send > 0` + rejection reasons are sane.
5. Add 5+ known-good and 5+ known-bad leads for the new segment to `tests/acceptance_corpus.json`.
6. Live for 48h before scaling.

### Onboarding a new domain (Phase 6+ future scaling — NOT in v2 initial scope)

Same as v1 process: register + DNS + Workspace seat + 4-week warmup + flip to active. v2 stays on 1 domain until first paid project banks; v3 can scale to 3 domains × 3 inboxes if volume needs demand it.

## Edge Cases

- **Domain cold-start quarantine**: some ESPs quarantine newly-registered domains for 30–90 days regardless of warmup. Phase 2 (warmup) MUST run in parallel with the cold-start clock; don't shortcut. If placement stays <90% at end of Phase 2, extend warmup another 7 days.
- **GDPR / CNIL B2B cold email in France**: legitimate-interest basis is legal in 2026 with three hard requirements enforced in the pipeline:
  1. **LIA (Legitimate Interest Assessment)** document on file. Template in `execution/personal_workflows/self_outbound_system/legal/lia_template.md`. Reviewed once, filed.
  2. **Unsubscribe link + physical postal address** in EVERY mail footer. Instantly template MUST include both. Acceptance gate asserts footer regex on every outbound draft.
  3. **30-day suppression retention** minimum. Opt-outs stored in `suppression.json` with timestamp; hard-delete only after 30 days. `run.py` reads suppression at top; refuses to send to any suppressed email or domain.
  Non-compliant B2B still gets fined — SOLOCAL €900k+ in 2025 for missing these.
- **Instantly free-tier warmup exhausted or account restricted**: no fallback path built-in. Manual intervention required. Suspend campaign, contact Instantly support, re-warm if needed.
- **Apify $5 credit exhausted mid-month**: fallback = manual list from Crunchbase Advanced Search (limited free) or LinkedIn Sales Nav free trial. Digest MUST flag "Apify credit exhausted, running on manual seed" so operator knows.
- **Sonnet 4.6 rate-limited**: fallback to Gemini 2.5 Flash free (already `GEMINI_API_KEY` in `.env` per project memory). Personalizer accepts a `--llm` flag.
- **Reply classifier confuses auto-reply/OOO for positive**: refine classifier prompt; add explicit OOO-text patterns to a hard-rule pre-filter BEFORE hitting the LLM (deterministic layer catches 95% of OOO).
- **Gmail Push API silence**: Instantly webhook is primary; Gmail Push is a redundant path for the "Interested" label. If both silent, canary + acceptance still work.
- **Cal.com double-booking**: Cal.com blocks natively.
- **AM lockdown**: this system uses entirely separate accounts, domain, inbox, credentials, Cloudflare account (if used), and Telegram bot. Do NOT import code or copy paths from `execution/infrastructure/api-proxy/`. See `CLAUDE.local.md` "ACCESSORY MASTERS — LOCKDOWN" for the no-touch list.
- **GDPR opt-out received via reply (not link)**: classifier routes to `negative`; contact + domain lands in `suppression.json` permanently.
- **Front-door synthetic FAIL**: `run.py` halts the day. Digest to Telegram. No cold sends. Root-cause: DNS drift? DKIM broken? Warmup score collapsed? Instantly account flag? Fix before next-day resume.
- **Output-acceptance gate FAIL**: `killswitch.py` fires. Campaign paused. Root-cause before resume.
- **Kill-switch state**: `KILL_SWITCH=1` in `.env` halts `run.py` at line 1. Also pauses Instantly campaign via API. To resume: set to `0`, resume in Instantly UI, verify canary green.
- **Prompt cache miss due to system-prompt edit**: expect a one-day Sonnet cost spike (~2× normal). Not a bug.
- **First month reality check**: expect ~1–3% reply rate, 0.2–0.5% positive rate. At 20/day × 30 days = 600 sends → 6–18 replies, 1–3 positives, 0–1 hot. **This is NOT enough to book a project every month** — Phase 5 is a signal-gathering month; if positive rate < 0.2% after 30 days, ICP or copy needs tuning BEFORE scaling volume.

## Exit criteria (system-wide "live and healthy")

- Phase 4 completed with 7 consecutive green days.
- Front-door canary green × 5 consecutive live days.
- Output-acceptance gate green × 5 consecutive live days.
- 6-auditor mandatory audit stack: all PASS in one parallel batch, verdict table in wrap-up.
- At least 1 real reply received, correctly classified, correctly routed (test with a friendly outreach to a friend if needed to force the loop).
- Kill-switch fire-drilled once.
- Weekly digest fired for at least 1 full week.
- LIA document filed. Suppression retention verified working.

## Changelog

- **2026-07-08 — v2 (Blueprint A2, ACTIVE).** Pivoted from Cloudflare Worker + raw SMTP × 6–9 inboxes to Instantly.ai Growth API + 1 warmed inbox × 1 secondary domain. Root cause of pivot: (a) Smartlead Basic (paste's original recommendation) has NO API/webhook in 2026 — moved to Unlimited Smart at $174/mo, killing the €36/mo assumption; Instantly Growth exposes API + webhook at ~$37/mo entry tier. (b) Apollo free tier cut from 10k → 100 credits/mo in late 2025, killing the free-sourcing assumption; replaced with Apify $5 credit for Google Maps + LinkedIn Actors. (c) Reliability bar raised: operator explicitly flagged that this must NOT fail like `job_search_v2` did — mandatory front-door synthetic + output-acceptance gate + 6-auditor stack now hard-gated. Cost: ~€48/mo TTC (€34 Instantly + €8.28 GWS + €0.85 Porkbun + €1.60 Sonnet + €4 Million Verifier variable). €3 over the €45 target, well within the €100 hard ceiling. Implementation now IN this workspace at `execution/personal_workflows/self_outbound_system/`, not in a separate repo. Phase 0 (research) complete 2026-07-08.

- **2026-05-16 — v1 (DEPRECATED, never deployed).** Cloudflare Worker + raw SMTP × 6–9 inboxes on 3 owned domains, 180–270 emails/day. Implementation was scaffolded at `github.com/dmazumdar186/outbound-engine` but the Worker was never deployed to Cloudflare and no domain reputation was consumed. Design was correct-in-principle but overshot the reliability budget for a solo operator: too many moving parts (3 domains × 6–9 inboxes × 28-day warmup × own DNS/deliverability discipline) for the operator's stated "must not fail like job_cron" bar. Preserved here as design reference for a future v3 scale-out once v2 books its first paid project.
