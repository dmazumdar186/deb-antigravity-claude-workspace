# HANDOFF — 2026-08-05 yoga_jitendra deploy + verify

**Purpose:** the prior session shipped the "Selective UX-first" redesign of
the yoga-jitendra dashboard (5 slices, commit `518413f`, pushed to
`origin/main`). This handoff continues in a fresh context window to actually
deploy the change to production and verify it against Jitendra's live URL.

**Ground state as of 2026-08-05 late evening Paris:**

- `origin/main` HEAD = `518413f` [phase-3-redesign] yoga_jitendra dashboard.
  Prior HEAD `e480075` (hardening) is the pre-redesign baseline.
- Astro build clean (11 pages, 7.64s). All 8 SSR fingerprints in
  `dist/dashboard/index.html` PASS locally.
- **Nothing deployed yet.** Two deploys owed — one for Pages (slices 1-5),
  one for the cron Worker (slice 0 CFWA fix + debug endpoint).
- LIVE-PROBATIONARY counter: **day 0 of 5**, still blocked on (a) the CFWA
  all-zero-donut bug (source_split.values = [0,0,0,0]) and (b) 5 consecutive
  green days after this deploy lands.

---

## What was shipped in `518413f` (5 slices)

**Slice 0 — CFWA all-zero-donut defensive fix**
- `execution/infrastructure/yoga_jitendra_cron/src/aggregator.js` —
  `clicksBySource.cfwa` now prefers `cfwa.pageviews ?? cfwa.visits ?? 0`
  (was `cfwa.visits ?? 0`). CF adaptive-group `count` always populates
  pageviews; `sum { visits }` inconsistently returns 0 on some plans.
- `execution/infrastructure/yoga_jitendra_cron/src/index.js` — added
  `GET /debug/kv/<key>` (X-Worker-Secret gated) so future snap
  inspection needs no redeploy.

Diagnosis for the record: site_tag drift RULED OUT (beacon token in
production HTML = `9a1473aafbd24daba793995956244a87` = wrangler.toml
pin). GSC + Bing 0 clicks is plausible for a low-authority new site.
CFWA showing 0 visits when there are 34 WA taps in 7d = definite bug,
hence the pageviews-first fix.

**Slice 1 — design tokens**
- New `src/styles/dashboard-tokens.css` with semantic palette (--yj-brand,
  --yj-success, --yj-warn, --yj-danger, --yj-neutral), fluid type scale
  (--yj-size-display through --yj-size-caption), spacing, motion, and
  primitives (`.yj-card`, `.yj-eyebrow`, `.yj-title`, `.yj-num`, `.yj-chip`,
  `.yj-skeleton`).
- Scoped under `.yj-dashboard` so `global.css` (public site) is untouched.
  `<main>` on the dashboard now carries the scope class.

**Slice 2 — HeroTile rework**
- `HeroTile.astro` — bigger display number, delta chip with arrow (↗ ↘ –)
  + %, token-based skeleton stack, source-footer with subtle top rule.
- DOM contract preserved (`.hero-tile-bignumber[data-metric]`, `.delta-up/
  down/neutral`, `.hero-tile-caveat[data-metric-caveat]`) so the
  hydration controller in `dashboard.astro` keeps working. Hydration
  innerHTML build (`numberRow.innerHTML = ...`) updated to emit
  `yj-num` + arrow spans so hydration-inserted numbers inherit token
  typography.

**Slice 3 — chart skeleton loading states**
- `TimeSeriesChart.astro` + `SourceDonut.astro` get shimmer overlays that
  fade out via `.chart-mounted` when ApexCharts `render()` resolves.
- `FunnelStrip.astro` shimmer pill replaces the alarming dashed hourglass.
- All three restyled with tokens.

**Slice 4 — ReviewsHub on main dashboard**
- New `src/components/dashboard/ReviewsHub.astro`. Big star rating +
  approved-count + per-source filter chips + top 3 recent reviews with
  source badges + pending-moderation strip that links to /dashboard/reviews.
- Hydrates from `/api/reviews-public` (public) + `/api/reviews-admin?type=
  pending` (authed, degrades silently on 401).
- UI is future-proof for GetYourGuide / Evendo / Expedia — those
  integrations do NOT exist yet; badges will show current sources only
  (google, superprof, meetup, trainme, instagram, email, other).

**Slice 5 — ProvenanceFooter + acceptance-gate regression guards**
- `ProvenanceFooter.astro` restyled with tokens (grid layout, halo dots on
  live/pending status).
- `tests/acceptance_dashboard.py` grows 3 new SSR checks (11, 12, 13):
  11. `.yj-dashboard` scope on `<main>` present
  12. `data-rh-list` + `data-rh-sources` ReviewsHub markers in SSR
  13. All live hero-tile bignumbers carry the `yj-num` token class

---

## First 4 tool calls when resuming

1. `git log origin/main --oneline -3` — confirm HEAD is `518413f`.
2. `cd execution/personal_workflows/yoga_jitendra_site && npm run build`
   — regenerate `dist/` (5 min operator convenience; previous session's
   dist may be older than the last edits).
3. Verify the SSR fingerprint checks against fresh `dist/`:
   ```
   py -c "import re; h=open('execution/personal_workflows/yoga_jitendra_site/dist/dashboard/index.html',encoding='utf-8').read(); print({name:bool(re.search(pat,h)) for name,pat in {'yj-dashboard scope':r'<main[^>]*yj-dashboard','ReviewsHub':r'data-rh-list','yj-num on bignumber':r'hero-tile-bignumber[^\"]*yj-num','chart-skeleton':r'chart-skeleton','yj-skeleton':r'yj-skeleton'}.items()})"
   ```
   All 5 keys must be True. Blocks the deploy if any are False.
4. Re-pose the deploy plan (see next section) and ask operator to confirm
   before invoking wrangler.

---

## Deploy plan (BOTH deploys needed, in this order)

### 1. Pages deploy (slices 1-5, visual redesign)

```
cd execution/personal_workflows/yoga_jitendra_site
wrangler pages deploy dist --project-name=yoga-jitendra
```

Auto-mode classifier WILL block this. Operator must approve or run it
themselves. Post-deploy verify:

```
# From workspace root:
py execution/personal_workflows/yoga_jitendra_site/tests/acceptance_dashboard.py --strict
```

Expected: PASS on all 13 checks (up from 12 checks in the prior gate;
checks 11-13 are the Slice-1/2/4 fingerprints).

If check 3 (`source_split.values all-zero`) still FAILS — that's the CFWA
bug and it's not resolved until the cron redeploy in step 2 propagates.

### 2. Cron Worker deploy (slice 0, CFWA fix + debug endpoint)

```
cd execution/infrastructure/yoga_jitendra_cron
npx wrangler deploy
```

Post-deploy the next 06:00 Paris cron run (or a manual `POST /run` if the
operator has the yoga-jitendra WORKER_SECRET) will populate
`snap:cfwa:<date>` snaps with the new `pageviews` field being the primary
metric.

**Critical caveat on the WORKER_SECRET:** the workspace `.env`
`WORKER_SECRET` does NOT match the yoga-jitendra-cron worker's secret
(prior session confirmed with a `POST /run/cfwa` that returned 401
unauthorized). Options if the operator wants to test the debug endpoint
before waiting for the next cron:
- (a) Regenerate on the cron: `npx wrangler secret put WORKER_SECRET`,
  paste the workspace `.env` value → they'll match.
- (b) Retrieve current secret from Cloudflare dashboard (Workers →
  yoga-jitendra-cron → Settings → Variables) and update workspace `.env`.
  Not visible in dash for security; option (a) is the practical path.

Once secrets match, diagnostic curl:
```
curl -H "X-Worker-Secret: $WORKER_SECRET" \
     https://yoga-jitendra-cron.debanjan186.workers.dev/debug/kv/snap:cfwa:2026-08-06
```
Returns the raw CF Analytics snapshot. If `pageviews > 0` there → the
Slice-0 fix works and the donut will populate. If `pageviews = 0` too →
CF Web Analytics beacon isn't firing at all (deeper investigation).

### 3. Verify against live and start the LIVE-PROBATIONARY counter

After BOTH deploys and one cron fire (next 06:00 Paris = ~2026-08-06 06:00):

```
py execution/personal_workflows/yoga_jitendra_site/tests/acceptance_dashboard.py --strict
```

Full PASS = LIVE-PROBATIONARY day 1 of 5. Then run daily for 4 more days;
5 consecutive PASSes closes the LIVE-PROBATIONARY status. Any DEGRADED
day resets the counter to 0.

---

## Ground truth on data availability (unchanged from prior handoff)

| PDF module | Data available? | Notes |
|---|---|---|
| Monthly Revenue        | NO      | No Stripe / no cash table. |
| Weekly Attendance      | NO      | No bookings source. |
| Reputation Rating      | PARTIAL | Google only; ReviewsHub UI is future-proof for GetYourGuide/Evendo/Expedia when integrations land. |
| Pending Actions        | PARTIAL | reviews-admin pending count works; CESU / tax queue does not exist. |
| Class Bookings tracker | NO      | No source. |
| CESU financial tracking| NO      | No source. |
| Multi-platform acquisition | PARTIAL | GSC + Bing + CFWA (post-fix); GBP API-denied; Meetup / GYG / Expedia / Evendo unwired. |
| WA taps (existing)     | YES     | 34 in 7d, working. |

---

## Constraints to respect

- **Budget: €0/mo.** No paid API additions without operator sign-off.
- **Current stack:** Astro + Cloudflare Pages + Cloudflare KV — preserved.
- **AM-locked paths untouched.** See `CLAUDE.local.md`.
- **DO NOT run** `wrangler pages deploy` / `npx wrangler deploy` without
  operator approval; auto-mode classifier will block.
- **DO NOT run** `node scripts/backfill_review_dates_from_maps.mjs --apply`
  (mutates production KV; operator-triggered).
- **DASHBOARD_PASS** is in workspace `.env` (auth verified from CLI).
- **Cap parallel sub-agents at 4** (prior session hit rate limit at ~7).
- **Model policy:** Opus 4.7 (latest in registry) for orchestration;
  Sonnet 4.6 for sub-agents. Fable 5 / Opus 5 unavailable.
- **Impeccable hook — Inter font finding.** Repeated `overused-font Inter`
  findings on chart components are EXPECTED — Inter is the site-wide body
  face per `global.css`, acknowledged as design debt in `HARDENING.md`
  row #6 pending a brand-refresh decision. Do NOT silence with inline
  ignore comments; the debt row is the persisted acknowledgement. If the
  operator wants to promote it to a workspace-level ignore, that's their
  call — until then, acknowledge and move on.

---

## Files to read for context

Absolute-path reads for a fresh session:

- `HANDOFF_2026-08-05_yoga_jitendra_deploy.md` (this file)
- `HANDOFF_2026-08-05_yoga_jitendra_redesign.md` (prior handoff — the
  decision + option context)
- `execution/personal_workflows/yoga_jitendra_site/HARDENING.md` (state of
  degraded axes, debt list, health probes, acceptance-gate coverage; the
  bottom of the History table now includes the redesign entry)
- `execution/personal_workflows/yoga_jitendra_site/tests/acceptance_dashboard.py`
  (updated with checks 11-13)
- `execution/personal_workflows/yoga_jitendra_site/src/styles/dashboard-tokens.css`
  (the token layer — every component's styles reference these)
- `execution/personal_workflows/yoga_jitendra_site/src/components/dashboard/ReviewsHub.astro`
  (new component, the biggest client-value addition)

---

## Honest gaps carried forward

1. **CFWA fix is defensive.** If deploy shows pageviews also 0, we have a
   beacon-not-firing bug and need to check the browser Network tab on the
   live site + read raw KV via the new /debug endpoint.
2. **Filter chips today = Google + Other only.** GetYourGuide / Evendo /
   Expedia badges will only appear when someone integrates those sources.
   Each is its own project (paid scrape via Outscraper OR unofficial
   scrape — needs prior-art pass per `~/.claude/rules/prior-art-first.md`).
3. **LIVE-PROBATIONARY counter still 0 of 5.** No amount of local code
   verification advances this — only 5 consecutive daily PASSes of the
   live gate.
4. **Two secrets not synced.** Workspace `.env WORKER_SECRET` ≠
   yoga-jitendra-cron `WORKER_SECRET`. Not blocking the deploy, but blocks
   local diagnostic curls until reconciled (see deploy plan step 2).
5. **Freshness monitor DEGRADED on job_search_v2.** Advisory-only, but
   worth flagging — job_search_v2 GH Actions cron is 49h stale.
   Unrelated to yoga_jitendra work.

---

## What was accomplished 2026-08-05 in the previous session

- Selected Option 2 (Selective UX-first on Astro) from the 4-option redesign
  decision menu after presenting ground-truth data availability against
  PDF spec.
- Shipped 5 slices in commit `518413f` (+1377 / −253 across 12 files).
- HARDENING.md history entry added.
- Push to `origin/main` succeeded (`e480075..518413f`). Pre-push SAST clean.
- No deploy commands invoked — operator to approve.

---

*Handoff written after committing + pushing the redesign. Next session
picks up at the deploy plan above.*
