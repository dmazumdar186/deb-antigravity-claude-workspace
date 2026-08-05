# yoga_jitendra_site — HARDENING

Per-project hardening card. Companion to workspace-level
`HARDENING_BACKLOG_WORKSPACE_2026-08-04.md`. Records shipped state,
known-degraded axes, acceptance-gate coverage, health probes, front-door
synthetic count, and owed follow-ups. Update when state changes.

Last updated: **2026-08-05** (Phase 2 finish-pass — gate discipline + fresh build).

---

## Status

**DEGRADED — VISIBLE DEFECTS PENDING** until:

1. Five consecutive **live** front-door-synthetic green days
   (`front_door_dashboard.sh` PASS × 5, run manually or via cron).
2. Pages project redeployed with the 2026-08-04 apexcharts bare-specifier
   fix. Fresh `dist/` was built in the 2026-08-05 session (chart chunks
   `TimeSeriesChart.astro_*.js` + `SourceDonut.astro_*.js` + `Sparkline.astro_*.js`
   + `apexcharts.esm.*.js` all present; no bare `import ApexCharts` in HTML).
   `wrangler pages deploy dist --project-name=yoga-jitendra` attempted by the
   assistant was **auto-mode-blocked** — operator must run the deploy or
   allow the classifier permission.
3. `DASHBOARD_USER` + `DASHBOARD_PASS` added to workspace `.env` so
   automated acceptance-gate runs can hit the auth-gated APIs (currently
   the gate returns exit 2 = PASS-WITH-SKIPS, or exit 1 under `--strict`).

Per `~/.claude/rules/front-door-synthetic.md`, the language while the
five-consecutive-day count is < 5 is exactly:
`LIVE-PROBATIONARY: day N of 5`.

Current framing: **LIVE-PROBATIONARY day 0 of 5** (unchanged from 2026-08-04:
counter cannot advance until Pages redeploy + DASHBOARD_PASS provisioning).

---

## Known-degraded state (accepted, not a bug)

| Axis | State | Reason | Recovery |
|---|---|---|---|
| Google Business Profile API | Denied | Google case 6-8997000041551 rejected. Source returns 429 on every fetch. | Awaiting Google approval OR manual weekly GBP scrape via `scripts/pull_gbp_reviews.mjs`. |
| `Interest` hero tile | GBP dropped from sourcing | Would perpetually show "GBP pending" caveat otherwise. Now sourced from GSC + Bing only. | Re-add `'gbp'` to `TILE_SOURCES.interest` in `dashboard.astro` (both TypeScript and JS mirror) + `aggregator.js` + `dashboard-data.json` if API access lands. |
| Discovery donut → "Google Maps" slice | Renders as hatched "(pending API approval)" | Post-2026-08-04 SourceDonut labels a permanently-degraded slice with truthful copy instead of "no data yet". | Same as above. |
| Reviews cards (4 of 9) | `date_provenance="unknown"`, date cell omitted from UI | Google Maps historical reviews were silently stamped `submitted_at = now()` at import — real dates unrecoverable without the Google Maps scrape backfill. | Operator runs `node scripts/backfill_review_dates_from_maps.mjs --apply` after reviewing the dry-run output. NOT automated (mutates production KV). |
| Discovery donut all-zero | `source_split.values = [0, 0, 0, 0]` across every range (7d / 30d / all) even though CFWA source is reported healthy | **2026-08-05 evening diagnosis:** site_tag drift RULED OUT (beacon token in production HTML = `9a1473aafbd24daba793995956244a87` = pinned var). `POST /run/cfwa` from workspace-side blocked by WORKER_SECRET mismatch (workspace `.env WORKER_SECRET` ≠ yoga-jitendra-cron's secret). Working theory: CF Analytics `sum { visits }` returns 0 on this account/plan even though `count` (pageviews) does aggregate correctly per beacon event. GSC + Bing 0 clicks is separately plausible for a new low-authority site. | **Fix staged (not deployed):** `src/aggregator.js` `clicksBySource.cfwa` now prefers `cfwa.pageviews ?? cfwa.visits ?? 0`. Debug read endpoint `GET /debug/kv/<key>` added to Worker (requires `X-Worker-Secret`) so raw snap inspection no longer needs a redeploy. **Operator to deploy:** `cd execution/infrastructure/yoga_jitendra_cron && npx wrangler deploy`. After deploy, if donut still zero, `curl -H "X-Worker-Secret: <secret>" https://yoga-jitendra-cron.debanjan186.workers.dev/debug/kv/snap:cfwa:2026-08-05` returns the raw payload to confirm which fields CF is actually populating. |

None of the above make the dashboard "broken" — the charts and trend
line render correctly with the data that arrives. The donut showing
empty is a data-layer bug that needs its own investigation.

---

## Debt list

Ranked by leverage (severity × ease):

| # | Item | Effort | Owner / Trigger |
|---|---|---|---|
| 1 | Add `DASHBOARD_USER=debanjan` + `DASHBOARD_PASS=<secret>` to workspace `.env` (fetch from CF Pages via `wrangler pages secret list --project-name=yoga-jitendra` or the CF dashboard) | 5 min | Operator, next session |
| 2 | Redeploy Pages project with the 2026-08-04 apexcharts fix (commit `b853709`) — `wrangler pages deploy dist --project-name=yoga-jitendra` after `npm run build` | 5 min | Operator, next session |
| 3 | Run `node scripts/backfill_review_dates_from_maps.mjs --apply` to flip the 4 unknown-provenance reviews to real dates | 15 min + review | Operator, after dry-run inspection |
| 4 | Provision Brevo secrets on the Pages project (`BREVO_API_KEY`, `BREVO_LIST_ID`) + wire the newsletter popup into the homepage | 30 min | Deferred — separate workstream |
| 5 | Add scheduled canary that runs `front_door_dashboard.sh` daily and alerts on FAIL (currently the front-door only runs manually) | 1 h | Deferred — workspace_heartbeat Worker (`execution/infrastructure/workspace_heartbeat/`) covers this once seeded with yoga-jitendra endpoints |
| 6 | Design debt: `Inter` is called out as an overused font by the impeccable hook. Consider a distinctive body face across the whole site (not just dashboard) if it becomes a brand ask. | Deferred | Not a bug; taste call |

---

## Acceptance gates

| Gate | Layer | Path | Live vs Fixture | Exit code semantics |
|---|---|---|---|---|
| `tests/front_door_dashboard.sh` | bash + python | LIVE (curl `${BASE_URL}`) | LIVE — hits real production URL + real /api/dashboard-data (auth) + real /wa-out | Exit 0 = all pass; non-zero = one FAIL line per failure on stderr |
| `tests/acceptance_dashboard.py` | Python | LIVE (`SITE_URL`) | LIVE — auth-gated dashboard API + HTML + /wa-out + public reviews. Warn-skips authed checks when `DASHBOARD_PASS` unset. | Exit 0 = full PASS; 2 = PASS-WITH-SKIPS (warn but no fail); 1 = FAIL (or, with `--strict`, ≥1 warning). CI should always pass `--strict`. |
| `tests/acceptance_reviews.py` | Python | LIVE (`SITE_URL`) | LIVE — public reviews API + HTML + date-provenance corpus + JSON-LD leak check | Exit 0 = pass; 1 = any FAIL |
| `tests/dom_acceptance_reviews.mjs` | Node + playwright | LIVE (`SITE_URL`) | LIVE — real headless Chromium, DOM state after augmentation | Exit 0 = pass; 1 = any assertion failure; 2 = unexpected |
| `tests/unit_dashboard.py` | Python | dist/ + src/ | Local (does NOT prove prod) | Exit 0 = pass; 1 = any regression guard fires. Fast pre-deploy check only. |

The 2026-08-04 chart fix added two new regression guards to unit + acceptance:

1. Built `dist/dashboard/index.html` must reference at least one
   `/_astro/(TimeSeriesChart|SourceDonut|Sparkline)*.js` chunk.
2. Built HTML must NOT contain any inline `<script type="module">`
   with a bare `import ApexCharts from 'apexcharts'` statement.

Either alone catches the bare-specifier bug; both together catch it
from two angles.

---

## Health probes

| Probe | URL | Auth | Expected shape |
|---|---|---|---|
| Cron `/health` | https://yoga-jitendra-cron.debanjan186.workers.dev/health | none (public) | JSON: `ok:true` when secrets present + last run has healthy_count≥1 + stale_hours≤26; includes per-source status + `pipeline.stale_hours` |
| Dashboard `/api/dashboard-data?range=7d` | https://yogaavecjitendra.fr/api/dashboard-data?range=7d | Basic (DASHBOARD_USER / DASHBOARD_PASS) | JSON rollup: `sources_healthy`, `sources_degraded`, `hero_tiles`, `time_series`, `source_split`. Non-empty when ≥1 source healthy. |
| Reviews public | https://yogaavecjitendra.fr/api/reviews-public?fresh=1 | none (public, whitelisted) | JSON: `count`, `average_rating`, `reviews[]` each with `date_provenance` |
| Reviews admin | https://yogaavecjitendra.fr/api/reviews-admin?count=1 | Basic (401 without auth) | JSON: `pending`, `approved` counts |
| /dashboard/ page | https://yogaavecjitendra.fr/dashboard/ | Basic | HTML, <1.5s wall-clock, references chart chunks, no inline bare imports |

Current probe readouts (2026-08-04 T15:26 UTC):

- Cron `/health`: **ok=true**, 3/4 sources healthy (GSC, Bing, CFWA), GBP 429 (expected).
- Cron version: `0584eb54-76d0-4ab7-8c72-e506403d9b66` (redeployed 2026-08-04 with `GBP_LOCATION_ID=locations/15110626893429158061` picked up).
- Reviews public API: 9 reviews, avg 5.0, 4 unknown-provenance.

---

## Front-door synthetic count

**LIVE-PROBATIONARY: day 0 of 5** as of 2026-08-04.

Reset trigger: 2026-08-04 apexcharts bare-specifier bug found. Even
though the cron pipeline was healthy, the two flagship visualizations
(trends chart + discovery donut) never rendered for 14 days. That is
a distinct fault class from the ones the previous count was tracking
(hero-tile hydration, review-date provenance, banner FOUC). Per
`~/.claude/rules/live-artifact-acceptance.md`, a new fault class
reappearing = counter reset.

Increment rule: `front_door_dashboard.sh` returns exit 0 against live
prod on N consecutive Paris-timezone days. Count captured in this
file's next revision + committed as `[phase-N] hardening: day M of 5`.

---

## Owed follow-ups

| Item | Trigger | Concrete next step |
|---|---|---|
| Pages redeploy with 2026-08-04 chart fix | Operator approval | `cd execution/personal_workflows/yoga_jitendra_site && npm run build && npx wrangler pages deploy dist --project-name=yoga-jitendra` |
| Provision `DASHBOARD_USER` + `DASHBOARD_PASS` in `.env` | Operator | Fetch from `wrangler pages secret list --project-name=yoga-jitendra` or CF dashboard; append to workspace `.env` |
| Review-date backfill (4 unknown → dated) | Operator dry-run review | `node scripts/backfill_review_dates_from_maps.mjs --dry-run` first, then `--apply` |
| Brevo popup wire-in | Product decision (post V0.1 launch) | Provision `BREVO_API_KEY` / `BREVO_LIST_ID` Pages secrets; add popup component |
| Increment LIVE-PROBATIONARY counter daily | Manual until workspace_heartbeat Worker is seeded with yoga-jitendra endpoints | `bash tests/front_door_dashboard.sh` daily, log result in this file |
| `Inter` overused-font design debt | Brand refresh milestone | Pick a distinctive body face; propagate across `Base.astro` + all dashboard components |
| Unrelated commit-hook blocker: `execution/templates/web_app_astro_cf/functions/*.ts` untracked | Separate workstream | Either `git add` those files or `.gitignore` — not Phase-2 scope |

---

## History

- **2026-08-05 (night, session 3)** — Client asks from Jitendra + dashboard-side subscribers tile. **Nine slices in one commit**, all landing behind a single Pages redeploy. **Slice 0 (personal-IG bug fix):** `Base.astro:91`, `i18n_ui.fr.json:16`, `i18n_ui.en.json:16` all pointed at `instagram.com/jitendrakuma/` (Jitendra's personal handle) instead of `yogaavecjitendra/` (the yoga business handle). All 3 flipped. This is the footer link visitors click AND the JSON-LD `sameAs` Google reads for the knowledge panel — high-impact fix. Regression guard: unit + acceptance gate assert `yogaavecjitendra` present AND `jitendrakuma` literal ABSENT across all 3 files + rendered HTML. **Slice 1 (newsletter KV-only fallback):** the pre-built `newsletter-subscribe.ts` (Brevo DOI) was rewritten to write directly to `newsletter:sub:<sha256(email)>` in Cloudflare KV with a 3-year TTL (no Brevo call). Operator chose this over full Brevo integration because a Brevo account has not been provisioned. `newsletter-count.ts` added as authed helper for the dashboard tile. `NewsletterPopup.astro` thanks-copy rewritten in both languages: was `"Vérifiez votre boîte mail — cliquez sur le lien de confirmation"` / `"Check your inbox — click the confirmation link"`, now `"Votre inscription est enregistrée. Vous recevrez la prochaine newsletter mensuelle."` / `"Your subscription is saved. You'll receive the next monthly newsletter."` — matches reality (no confirmation email in KV-only). Both privacy notice pages (FR + EN) grew a top-of-page "Backend note" aside explaining the KV-only fallback + the Brevo-swap catchup commitment. **KV-plaintext posture (owed follow-up)**: the GDPR assessment (§5 of `docs/gdpr_newsletter_popup_assessment.md`) assumed only `sha256(email)` sits in KV. The fallback stores plaintext email as the sub record (the sub IS the mailing list today). This is a **temporarily-widened exposure that must close at Brevo swap** — the swap step MUST enumerate every `newsletter:sub:*` KV entry, import each into Brevo's DOI flow, and force a re-confirmation click BEFORE any first campaign send, so no un-reconfirmed address receives marketing email. Documented as `// TODO(brevo)` in code. **Slice 2 (popup wired):** `NewsletterPopup` mounted in `Base.astro` after `<slot />`, gated on `!dashboard` so it never nags Jitendra on `/dashboard/*`. Component self-suppresses per-visitor for 30 days via `localStorage.yj_popup_seen`, respects DNT + crawler UAs. **Slice 3 (ClientsCarousel):** operator asked for a reusable JSON-driven carousel (4 per page desktop, 3 tablet, 2 mobile) so future client adds are a one-line JSON edit. New `src/components/ClientsCarousel.astro` (350 LOC) — auto-rotate on 6s pause-on-hover/focus, dot indicators, arrow buttons, arrow-key nav when focused, ARIA-live announces page changes, respects prefers-reduced-motion. Fallback chain per client: `logo` (image) → `monogram` (text pill in Fraunces). Shared canonical list at `src/content/clients.json` — 8 entries today (3 existing SVGs kept: TotalEnergies, SEMMARIS, Emmaüs; 5 new as monograms until real SVGs land: Chloé, FTI Consulting, FIPAM, WeWork, Sick France). `Hero.astro` migrated: was inline `t.clients.map(...)` per-language, now `<ClientsCarousel clients={clients} />` reading the shared JSON. **Slice 4 (ReviewSources):** new `src/components/ReviewSources.astro` chip grid at the bottom of both `/reviews/` and `/en/reviews/`. 7 chips: Google reviews search, Superprof (public teacher URL, NOT the private admin URL Jitendra pasted), Meetup Paris Hatha Yoga, Airbnb Experience, Instagram (@yogaavecjitendra), plus 2 specific Instagram post links Jitendra shared. Inline SVG icons per source (no external image requests). Sources config at `src/content/review_sources.json` — add / re-order = one JSON edit. **Slice 5 (Subscribers hero tile):** 4th tile in the dashboard hero-grid, always-live, sourced from KV. `functions/api/dashboard-data.ts` extended with `withSubscribers()` helper that enumerates `newsletter:sub:*` keys, caches results in KV under `newsletter:count:cache` (5-min TTL, shared with `newsletter-count.ts` endpoint), and injects `hero_tiles.subscribers` into the rollup response on every request. `dashboard-data.json` fallback includes the subscribers skeleton. `dashboard.astro` extends `TILE_SOURCES` + `SOURCE_LABELS` with `subscribers/newsletter`, adds the 4th `<HeroTile>` block (hero-grid CSS is `auto-fit minmax(240px)` — 4 tiles wrap gracefully to 2×2 on tablet), extends hydration `.forEach(['reach', 'interest', 'conversation'])` → `+ 'subscribers'`. **Slice 6 (this entry).** **Slice 7 (acceptance gate + unit checks):** grew both `acceptance_dashboard.py` (live) and `unit_dashboard.py` (dist/src-only) with checks 14-18 covering the personal-IG fix, NewsletterPopup mount + truthful copy, ReviewSources markers, ClientsCarousel markers, and subscribers hero-tile SSR + API shape. **Slices 8-9**: full 6-auditor mandatory-audit-stack + rebuild + Pages deploy + live gate + browser dogfood. **Popup frequency contract**: 30-day rolling per-visitor suppression, defended in `~/.claude/plans/cuddly-knitting-lagoon.md` under "Popup frequency ambiguity" — if Jitendra later wants literal every-visit re-fire, flip `YJ_NL_TTL_MS` from 30d to 0 (one-line change). Plan-skeptic ran two rounds, verdict = CONVINCED_WITH_NOTED_CONCERNS.

- **2026-08-05 (late evening)** — Selective UX-first redesign pass (5 slices, all staged for deploy). **Slice 0 (CFWA fix):** aggregator `clicksBySource.cfwa` now prefers `pageviews ?? visits ?? 0` so the discovery donut works even if CF Analytics `sum { visits }` returns 0 while `count` (pageviews) aggregates cleanly. Debug KV read endpoint `GET /debug/kv/<key>` added to cron Worker so future snap inspection needs no redeploy. **Slice 1:** design-tokens layer at `src/styles/dashboard-tokens.css` — semantic palette (--yj-brand/success/warn/danger/neutral), typography scale (--yj-size-display through --yj-size-caption), spacing, motion tokens, reusable primitives (.yj-card, .yj-eyebrow, .yj-title, .yj-num, .yj-chip, .yj-skeleton). Scoped under `.yj-dashboard` so global.css (public site) is untouched. **Slice 2:** `HeroTile.astro` rewritten to consume tokens — bigger display number, richer delta chip (arrow + %), token-based skeleton stack replacing the "waiting" hourglass pill. DOM contract preserved (hero-tile, hero-tile-bignumber, .delta-up/down/neutral, data-metric) so dashboard.astro's hydration controller keeps working; hydration innerHTML build updated to emit yj-num + arrow spans so hydration-inserted numbers inherit token typography. **Slice 3:** skeleton overlays added to `TimeSeriesChart` and `SourceDonut` (fade out via `.chart-mounted` when ApexCharts render() resolves); `FunnelStrip` shimmer skeleton replaces dashed hourglass. All three charts + funnel restyled with tokens. **Slice 4:** new `ReviewsHub.astro` embedded on the main dashboard — big star rating + count + source filter chips + top 3 reviews with source badges + pending-moderation strip that links to /dashboard/reviews. Hydrates from `/api/reviews-public` (public) + `/api/reviews-admin?type=pending` (authed, degrades silently). **Slice 5:** `ProvenanceFooter.astro` restyled with tokens (grid layout, halo dots on live/pending status). Acceptance gate `tests/acceptance_dashboard.py` extended with 3 new regression guards (checks 11-13): (11) `.yj-dashboard` scope on `<main>` present; (12) `data-rh-list` + `data-rh-sources` ReviewsHub markers in SSR; (13) all live hero-tile bignumbers carry the `yj-num` token class. Full `npm run build` clean (11 pages, 7.64s). All 8 SSR fingerprint checks against fresh `dist/dashboard/index.html` PASS. **Not yet deployed** — waiting on operator to run `wrangler pages deploy dist --project-name=yoga-jitendra` + `cd execution/infrastructure/yoga_jitendra_cron && npx wrangler deploy` (cron redeploy required for the CFWA aggregator fix + debug endpoint).
- **2026-08-05 (evening)** — Phase 2 finish-pass, deploy + investigation. Operator approved `wrangler pages deploy dist` → deployment `439e7bba` live at yogaavecjitendra.fr. DASHBOARD_PASS provisioned to workspace `.env`. Acceptance gate under `--strict`: 4 of 5 auth-gated checks PASS (dashboard-data schema across 3 ranges, dashboard HTML has chart chunks + no bare-specifier import, hero-tiles labeled). **1 FAIL surfaced by --strict:** `source_split.values = [0, 0, 0, 0]` on every range — the discovery donut is genuinely blank because underlying CFWA data is 0 despite the source being reported healthy. Site has traffic (34 WA taps in 7d) so this is a real data-layer bug, NOT an empty-state. Added to known-degraded table above with root-cause suspects + next-step. LIVE-PROBATIONARY counter unchanged (still 0/5, blocked on this data-layer bug).
- **2026-08-05 (afternoon)** — Phase 2 finish-pass prep. Verified chart-fix source is committed + pushed. Fresh `npm run build` confirms dist/ ships `apexcharts.esm.*.js` + all 3 per-chart chunks + zero inline bare `import ApexCharts`. Acceptance-gate discipline hardened: `--strict` flag upgrades WARN → FAIL; PASS-WITH-SKIPS verdict (exit 2) replaces the prior false-PASS-with-WARN-suppressed output; added public `/api/reviews-public` regression guard (per-record `date_provenance` fingerprint from the 2026-08-04 provenance work) so a run without `DASHBOARD_PASS` still exercises SOMETHING beyond `/wa-out`. Added `load_dotenv()` to the gate so it reads workspace `.env` (was silently ignoring it).
- **2026-08-04** — Phase 2 workspace hardening. Root-caused blank trends chart + blank discovery donut: Astro `<script type="module" define:vars>` blocks emit inline scripts with `import ApexCharts from 'apexcharts'` unresolved (bare specifier fails in browsers). Converted all three chart components to hoisted `<script>` + `data-init` JSON attributes. Build now produces `_astro/apexcharts.esm.*.js` + per-chart chunks; charts render on the built HTML. Cron redeployed with GBP_LOCATION_ID picked up from local wrangler.toml modification. Front-door + acceptance test scripts rewritten to hit LIVE URLs, added regression guards for the bare-specifier fingerprint. `unit_dashboard.py` split from `acceptance_dashboard.py` (the old file mixed dist-only checks under a name that implied live coverage — exactly the 2026-08-03 pattern the workspace rule was born from).
- **2026-08-03** — Live-artifact-acceptance rule (`~/.claude/rules/live-artifact-acceptance.md`) born from this project. 13-day stale fallback in prod because two Pages Functions (`dashboard-data.ts`, `wa-out.ts`) were never `git add`ed. Committed six regression guards; SAST rule `pages-functions-untracked` added.
- **2026-07-21** — V0.1 dashboard code landed. Charts never rendered live — this is the fault the 2026-08-04 investigation surfaced.
- **2026-07-11** — V0.01 site launched at yogaavecjitendra.fr.
