# HANDOFF — 2026-08-05 yoga_jitendra dashboard redesign

**Purpose:** the operator shared a PDF (`Dashboard Jitendra.pdf`, dropped into the previous session) proposing a full architectural + UI redesign of `https://yogaavecjitendra.fr/dashboard/`. That session ran out of context before the redesign was scoped. This handoff continues the conversation in a fresh window.

**Ground state as of 2026-08-05 evening Paris:**
- Workspace hardening (Phase 1 + Phase 2 finish-pass) is COMPLETE and PUSHED. `origin/main` HEAD = `e480075`. 35 commits landed today (30 from prior 08-04 pass + 6 new phase-1-followup + audit + phase-2 hardening).
- Dashboard is **technically working** at `https://yogaavecjitendra.fr/dashboard/` (auth-gated, Basic Auth `debanjan / <DASHBOARD_PASS from workspace .env>`). Trends chart renders with real data (7 labels × 3 series). Chart-bundle bug from 2026-08-04 is fixed and deployed.
- **One real data-layer bug remains**: acceptance gate under `--strict` reports `source_split.values = [0, 0, 0, 0]` on every range (discovery donut blank). Site has 34 WA taps in 7 days = definite traffic. Suspect: `CF_WA_SITE_TAG` in `execution/infrastructure/yoga_jitendra_cron/wrangler.toml [vars]` has drifted from the account's actual beacon token, so the CFWA GraphQL query hits the wrong siteTag and returns 0. Diagnostic: `POST /run/cfwa` on the cron worker with `X-Worker-Secret`, compare to CF Web Analytics dashboard for the same date. Fully documented in [execution/personal_workflows/yoga_jitendra_site/HARDENING.md](execution/personal_workflows/yoga_jitendra_site/HARDENING.md) under "Known-degraded state".

---

## The redesign question the operator wants to resume

Operator shared a PDF at ~2026-08-05 late evening. Key excerpts:

> "I want a complete redesign of the dashboard, which makes sense because this dashboard is not at all working. The elements in it are not populated. It doesn't work. It doesn't look like the dashboard. It doesn't provide the necessary data details to the client."

The PDF proposes:
- Stack rewrite: Astro → **Next.js/React + Tailwind + Shadcn UI**
- New DB layer (PostgreSQL or WordPress-style tables — `wp_yj_reviews`, `wp_yj_bookings`, `wp_yj_analytics`)
- 5 new modules:
  1. **Business Overview / KPI Row**: Monthly Revenue (Stripe + studio cash), Weekly Attendance, Reputation (aggregated stars across Google + GetYourGuide + Evendo + Expedia), Pending Actions
  2. **Class Bookings & Attendance Tracker**: Studio (Paris 16 22 rue Eugène Manuel) vs. Home Visits vs. Corporate Workshops, per-session roster with language tags (FR/EN/HI), capacity meters, WhatsApp group messaging
  3. **Universal Reputation Hub**: Google + GetYourGuide + Evendo reviews aggregated with inline AI reply generator
  4. **Financial Streams + CESU Tax Credit**: Studio Group / CESU Eligible Home Classes (50% tax credit) / Corporate Workshops, annual CESU statement PDF export
  5. **Multi-Platform Acquisition**: Direct / Meetup / GetYourGuide / Expedia / Evendo with impression volume + conversion %
- Ingestion via **Zernio / Outscraper** (paid third-party review scrapers) instead of GBP API
- 4-week roadmap: Week 1 backend, Week 2 middleware, Week 3 UI, Week 4 test+deploy

**What the assistant flagged as questionable about the PDF (from the prior turn):**

- **Misdiagnoses the failure mode.** PDF blames "synchronous client-side dependencies on GBP/Places APIs." Wrong. Current dashboard already ingests server-side via a Cloudflare Worker cron writing to KV. It never called Google APIs from the browser. Real failures were untracked Pages Functions (2026-08-03) + Astro bare-specifier bug (2026-08-04). Both fixed.
- **Stack rewrite has no justification** other than aesthetics. Astro + CF Pages works, is deployed, is cheap. Migrating to Next.js is weeks of work for parity.
- **References data that does not exist**: Stripe billing integration, `wp_yj_bookings` roster, CESU payment tracking, class capacity, WhatsApp group messaging, per-platform revenue attribution. None of this flows into the workspace today. Each is a separate integration project.
- **Paid dependencies (Zernio, Outscraper)** — operator budget is €0/mo per `~/.claude/rules/model-tier.md` cost-constraint clause. GBP reviews scrape via Google Maps already exists at `scripts/backfill_review_dates_from_maps.mjs`.

**What the assistant said IS worth taking from the PDF:**

- KPI-summary-row + 32pt typography + color-token semantic system → legitimate UX upgrade
- Unified reviews hub aggregating multiple sources → real value-add over current Google-only reviews
- Class attendance / booking view → the actual thing a small-business client wants
- CESU tax-credit export → France-specific feature Jitendra would use

---

## The 4-option decision the operator was asked to make

Operator MUST pick one before the next session executes. The assistant posed:

1. **Full redesign per PDF spec** (multi-week). Stack rewrite to Next.js + Shadcn UI + new DB + all 5 modules. Realistically 3-4 weeks solo, may require paid APIs (Stripe, Outscraper, Meetup partner). New workstream separate from workspace hardening.
2. **Selective UX-first upgrade on current Astro stack** (~1-2 weeks). Keep Astro + CF Pages + KV. Apply KPI-tile typography + color tokens + unified reviews hub + skeleton loading states. Skip parts needing data we don't have (Stripe, bookings). Preserves the €0/mo cost profile.
3. **Fix CFWA bug only, defer redesign**. Debug `source_split all-zero` (probably `CF_WA_SITE_TAG` drift), close LIVE-PROBATIONARY 5/5, treat redesign as separate operator decision for later. Hours, not weeks. Dashboard stays functionally correct but visually unchanged.
4. **Talk it through first**. PDF may not reflect what the operator actually wants the client to see.

Operator's response to that AskUserQuestion: "give me a handoff prompt for another context window and we continue there with this question." Hence this file.

---

## Ground truth on data availability today

Read this BEFORE promising the client anything the PDF describes. What actually exists in the pipeline today:

| PDF module component | Data source available? | Notes |
|---|---|---|
| Monthly Revenue | **NO** | No Stripe integration. No cash-entry table. Would need net-new build. |
| Weekly Attendance | **NO** | No `wp_yj_bookings` equivalent. Would need booking-source integration (Meetup API? GetYourGuide partner API?). |
| Reputation Rating | **PARTIAL** | Reviews KV exists (10 reviews, avg 5.0, unknown_date_count=1). Currently only Google Maps source, not Evendo / GetYourGuide / Expedia. |
| Pending Actions | **PARTIAL** | Reviews-admin exists at `functions/api/reviews-admin.ts`, so "unanswered reviews" count is derivable. CESU / tax-verification queue does not exist. |
| Class Bookings tracker | **NO** | No source. |
| CESU financial tracking | **NO** | No source. |
| Multi-platform acquisition | **PARTIAL** | GSC + Bing + CFWA in KV via cron. GBP is API-denied. Meetup / GetYourGuide / Expedia / Evendo aren't wired. |
| Existing metrics the dashboard DOES have | | GSC impressions/clicks (currently 0), Bing (currently 0), CFWA visits (currently 0 — bug, actual site has 34-80 WA taps in 7d), WA-taps counter (working: 34 in 7d), reviews-public feed (10 reviews, 1 with unknown date). |

The current dashboard is a **technical SEO/analytics dashboard**. The PDF describes a **business operations platform**. Very different products.

---

## Model policy for the next session

Operator asked in the previous handoff for "OpenAI Sol/Terra" models. Registry search confirmed:
- No `openai` provider entries in `execution/modules/model_registry.py` `LAST_KNOWN_GOOD`
- No `sol` or `terra` aliases anywhere
- No `claude-opus-5` available
- OpenRouter allows `openai/` family — operator can specify a slug if they want

Operator's follow-up answer was "the latest Anthropic or OpenAI model" — meaning "just use whatever's newest." In practice: Opus 4.7 (this session's model, latest in registry) is fine.

**Cap parallel sub-agents at 4** (last session hit Anthropic rate limit at ~7).

---

## Files the next session must read

Absolute-path reads for context:
- `HANDOFF_2026-08-05_yoga_jitendra_redesign.md` (this file)
- `Dashboard Jitendra.pdf` (workspace root — operator will re-share or point to it)
- `execution/personal_workflows/yoga_jitendra_site/HARDENING.md` (current known-degraded state, debt list, health probes)
- `execution/personal_workflows/yoga_jitendra_site/src/pages/dashboard.astro` (the current dashboard entry page — 900+ lines)
- `execution/personal_workflows/yoga_jitendra_site/src/components/dashboard/*.astro` (9 components: HeroTile, TimeSeriesChart, SourceDonut, Sparkline, FunnelStrip, MilestoneStrip, NextMoveCard, ProvenanceFooter, SelfReportTile)
- `execution/personal_workflows/yoga_jitendra_site/functions/api/dashboard-data.ts` (the Pages Function that serves the rollup)
- `execution/infrastructure/yoga_jitendra_cron/src/aggregator.js` (the cron that builds the rollup — lines 180-260 for the field mappings)
- `execution/infrastructure/yoga_jitendra_cron/src/sources/cf_wa.js` (CFWA source suspected of the all-zero-donut bug)

---

## Constraints to respect

- **Budget: €0/mo** per `~/.claude/rules/model-tier.md` cost-constraint clause. No new paid APIs without operator sign-off. No Zernio, no Outscraper, no Stripe onboarding fees, no OpenAI paid tier unless operator explicitly re-authorizes.
- **Current stack:** Astro + Cloudflare Pages + Cloudflare KV. Preserved unless the operator explicitly picks Option 1 (full redesign).
- **AM-locked paths untouched.** See `CLAUDE.local.md`.
- **Do NOT run** `wrangler pages deploy` without operator approval; auto-mode classifier will block it anyway.
- **Do NOT run** `node scripts/backfill_review_dates_from_maps.mjs --apply` (mutates production KV; operator-triggered).
- **Do NOT run** `cd execution/infrastructure/yoga_jitendra_cron && npx wrangler deploy` (mutates production cron; operator-triggered).
- **DASHBOARD_PASS is in workspace `.env`** (38 chars, starts `yo`, ends `21`). Auth verified working from CLI. Operator's browser login issue is separate (probably password-manager cache).
- **LIVE-PROBATIONARY counter is 0/5**. Blocked on CFWA data-layer bug being closed before it can advance.

---

## First 3 tool calls when resuming

1. `git log origin/main --oneline -10` — confirm HEAD is `e480075` (or later if operator pushed something).
2. `py execution/personal_workflows/yoga_jitendra_site/tests/acceptance_dashboard.py --strict` — should reproduce: 4 PASS on auth-gated checks + wa-out + reviews-public, 1 FAIL on `source_split.values = [0,0,0,0]`.
3. Read this file + `Dashboard Jitendra.pdf` (operator re-shares) + `execution/personal_workflows/yoga_jitendra_site/HARDENING.md`.

**Then re-pose the 4-option decision** (Full / Selective UX / Fix-CFWA-only / Talk-it-through) exactly as above. Do NOT start any redesign work without operator explicit pick.

---

## What was accomplished 2026-08-05 in the previous session

- Phase 1 finish-pass: 5 HIGH SAST findings fixed (4 front-door probes + interview_iag SITE_URL). Commits `beaff98`, `479a092`, `ece4d72`, `aa652d0`, `7a6353c`. All 4 live probes PASS against their target Workers.
- Audit report: [HARDENING_BACKLOG_WORKSPACE_2026-08-05.md](HARDENING_BACKLOG_WORKSPACE_2026-08-05.md). Top-10 punch list 10/10 SHIPPED. Phase 3/4a-d all present, video_pipeline pytest 20/20 PASS. Commit `171633e`.
- Phase 2 (yoga_jitendra): Verified chart-fix source is committed + pushed. Fresh `npm run build`; `wrangler pages deploy dist` → deployment `439e7bba` live. Acceptance gate hardened (`--strict` flag, PASS-WITH-SKIPS exit 2, reviews-public regression check, `load_dotenv()` fix). Commits `95777ba`, `c25a95a`, `e480075`.
- DASHBOARD_PASS provisioned to `.env` by operator. Auth verified from CLI. Browser-login issue is on operator's side (cache).
- CFWA all-zero-donut bug found via `--strict`. Root-cause logged in HARDENING.md.

35 commits total, all pushed to `origin/main`.

---

*Handoff written after the previous session ran to natural stop on the "should we redesign the dashboard" decision. Next session picks up with the 4-option AskUserQuestion, informed by the ground-truth data-availability table above.*
