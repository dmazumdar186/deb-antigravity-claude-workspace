# yoga_jitendra_site — HARDENING

Per-project hardening card. Companion to workspace-level
`HARDENING_BACKLOG_WORKSPACE_2026-08-04.md`. Records shipped state,
known-degraded axes, acceptance-gate coverage, health probes, front-door
synthetic count, and owed follow-ups. Update when state changes.

Last updated: **2026-08-04** (Phase 2 workspace hardening pass).

---

## Status

**DEGRADED — VISIBLE DEFECTS PENDING** until:

1. Five consecutive **live** front-door-synthetic green days
   (`front_door_dashboard.sh` PASS × 5, run manually or via cron).
2. Pages project redeployed with the 2026-08-04 apexcharts bare-specifier
   fix (charts render live, not blank).
3. `DASHBOARD_USER` + `DASHBOARD_PASS` added to workspace `.env` so
   automated acceptance-gate runs can hit the auth-gated APIs (currently
   the gate warn-skips those checks).

Per `~/.claude/rules/front-door-synthetic.md`, the language while the
five-consecutive-day count is < 5 is exactly:
`LIVE-PROBATIONARY: day N of 5`.

Current framing: **LIVE-PROBATIONARY day 0 of 5** (reset on 2026-08-04
because the chart-blank defect is a distinct fault class from the ones
previously counted).

---

## Known-degraded state (accepted, not a bug)

| Axis | State | Reason | Recovery |
|---|---|---|---|
| Google Business Profile API | Denied | Google case 6-8997000041551 rejected. Source returns 429 on every fetch. | Awaiting Google approval OR manual weekly GBP scrape via `scripts/pull_gbp_reviews.mjs`. |
| `Interest` hero tile | GBP dropped from sourcing | Would perpetually show "GBP pending" caveat otherwise. Now sourced from GSC + Bing only. | Re-add `'gbp'` to `TILE_SOURCES.interest` in `dashboard.astro` (both TypeScript and JS mirror) + `aggregator.js` + `dashboard-data.json` if API access lands. |
| Discovery donut → "Google Maps" slice | Renders as hatched "(pending API approval)" | Post-2026-08-04 SourceDonut labels a permanently-degraded slice with truthful copy instead of "no data yet". | Same as above. |
| Reviews cards (4 of 9) | `date_provenance="unknown"`, date cell omitted from UI | Google Maps historical reviews were silently stamped `submitted_at = now()` at import — real dates unrecoverable without the Google Maps scrape backfill. | Operator runs `node scripts/backfill_review_dates_from_maps.mjs --apply` after reviewing the dry-run output. NOT automated (mutates production KV). |

None of the above make the dashboard "broken" — they are truthfully
surfaced in the UI so the client reads state correctly.

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
| `tests/acceptance_dashboard.py` | Python | LIVE (`SITE_URL`) | LIVE — auth-gated dashboard API + HTML + /wa-out. Warn-skips authed checks when `DASHBOARD_PASS` unset. | Exit 0 = pass; 1 = any FAIL; 2 = env-config error |
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

- **2026-08-04** — Phase 2 workspace hardening. Root-caused blank trends chart + blank discovery donut: Astro `<script type="module" define:vars>` blocks emit inline scripts with `import ApexCharts from 'apexcharts'` unresolved (bare specifier fails in browsers). Converted all three chart components to hoisted `<script>` + `data-init` JSON attributes. Build now produces `_astro/apexcharts.esm.*.js` + per-chart chunks; charts render on the built HTML. Cron redeployed with GBP_LOCATION_ID picked up from local wrangler.toml modification. Front-door + acceptance test scripts rewritten to hit LIVE URLs, added regression guards for the bare-specifier fingerprint. `unit_dashboard.py` split from `acceptance_dashboard.py` (the old file mixed dist-only checks under a name that implied live coverage — exactly the 2026-08-03 pattern the workspace rule was born from).
- **2026-08-03** — Live-artifact-acceptance rule (`~/.claude/rules/live-artifact-acceptance.md`) born from this project. 13-day stale fallback in prod because two Pages Functions (`dashboard-data.ts`, `wa-out.ts`) were never `git add`ed. Committed six regression guards; SAST rule `pages-functions-untracked` added.
- **2026-07-21** — V0.1 dashboard code landed. Charts never rendered live — this is the fault the 2026-08-04 investigation surfaced.
- **2026-07-11** — V0.01 site launched at yogaavecjitendra.fr.
