# GreenJobs release environments

Source of truth: `environments.json` (read by `release.py` and `smoke.py`) and the `[env.staging]` /
`[env.production]` sections of `platform_worker/wrangler.toml`. `release.py check-config` fails CI if they
disagree, or if an env section is missing a var (wrangler does not inherit vars or bindings into envs).

## Staging (our Cloudflare account)

| Resource | Name |
|---|---|
| Worker | `greenjobs-platform-staging` on `greenjobs-platform-staging.debanjan186.workers.dev` (IE), `greenjobs-platform-staging-uk` on `greenjobs-platform-staging-uk.debanjan186.workers.dev` (UK) |
| D1 | `greenjobs-staging` (`database_id` = `REPLACE_WITH_STAGING_D1_ID` in wrangler.toml) |
| R2 (CVs) | `greenjobs-cvs-staging` (smoke applies send no CV, so it stays empty) |
| Pages | `greenjobs-staging-ie` -> `https://greenjobs-staging-ie.pages.dev`, `greenjobs-staging-uk` -> `https://greenjobs-staging-uk.pages.dev` (each hosts the full two-edition build) |
| Mail | `DRY_RUN="1"`, `LIVE_CONFIRM=""`, `MAIL_PROVIDER="none"`, `MAIL_DAILY_CAP="0"`, pinned and checked by `check-config` |
| Data | Public job data only: `release.py` seeds `jobs` + employer names from `deliverables/greenjobs_redesign_2026-09-22/src/data/{ie,uk}.json`, link-mode, no apply email, no contacts (`assert_seed_safe` fails closed). No candidate or application data ever goes to staging; the only applications there are the smoke test's synthetic `smoke-test@example.com`. |

### UK Worker (2026-11-20)

The Worker picks its site from the Host (`HOST_SITE_MAP`), and a workers.dev hostname belongs to one script, so
UK gets a second deployment of the same Worker: wrangler `[env.staging-uk]` (`environments.json`
`extra_workers`), name `greenjobs-platform-staging-uk`, `HOST_SITE_MAP` = only its own host -> `uk`, the same
D1 binding as `[env.staging]`. Chosen over a Worker route on a staging hostname because we own no spare zone
on this account and a route needs one; a second script needs nothing but a second deploy, and production
keeps its single Worker with zone routes (no production config changes).

- No cron (`triggers.crons = []`): the IE Worker's `*/10` cron already drains the shared D1; two would race.
- No Access app and empty `ACCESS_*` vars: `/admin` and `/api/admin` on the UK host answer `not_configured`
  (fail closed). Staff and the smoke write flow use the IE host; the admin payload names the site.
- No `BUILD_TOKEN` secret: export / import answer 503 / 401 on the UK host (the smoke's export check uses IE).
- `release.py stage` deploys it right after the primary (same `RELEASE_SHA`); `check-config` pins name,
  workers_dev, the D1 binding, the mail pins, every var, the single-host `HOST_SITE_MAP` and the empty cron.
- The UK Pages project builds with `--api-base` = the UK Worker host; its IE edition reads it with `?site=ie`.
- First deploy only: if wrangler fails with code 10007, enable workers.dev for the new script once
  (`POST .../workers/scripts/greenjobs-platform-staging-uk/subdomain {"enabled":true}`), as for the IE script.

## Production (GreenJobs' own Cloudflare account)

| Resource | Name |
|---|---|
| Worker | `greenjobs-platform`, routes `greenjobs.ie/api/*`, `/admin*`, same on `greenjobs.co.uk` (zones must be on the client's account first) |
| D1 | `greenjobs` (`database_id` = `REPLACE_WITH_PRODUCTION_D1_ID`) |
| R2 | `greenjobs-cvs` (CVs), `greenjobs-backups` (pre-promote D1 exports; create it with a lifecycle rule) |
| Pages | `greenjobs-ie` -> greenjobs.ie, `greenjobs-uk` -> greenjobs.co.uk |
| Mail | `DRY_RUN="1"` until the operator says go-live (CUTOVER_RUNBOOK); the pipeline never flips it |

## Secrets (names only; values live in GitHub environments, never in the repo or logs)

| Name | GitHub environment | Used by |
|---|---|---|
| `CLOUDFLARE_API_TOKEN` | `staging` | stage: Workers Scripts Edit, D1 Edit, Pages Edit, R2 Edit on OUR account |
| `CLOUDFLARE_ACCOUNT_ID` | `staging` | stage |
| `GREENJOBS_STAGING_ACCESS_CLIENT_ID` / `GREENJOBS_STAGING_ACCESS_CLIENT_SECRET` | `staging` | smoke write flow: Cloudflare Access service token for the staging admin API only |
| `GREENJOBS_STAGING_BUILD_TOKEN` | `staging` | smoke export check; same value as the staging Worker's `BUILD_TOKEN` secret |
| `GREENJOBS_PROD_CLOUDFLARE_API_TOKEN` | `production` | promote / rollback, scoped to the client's account |
| `GREENJOBS_PROD_CLOUDFLARE_ACCOUNT_ID` | `production` | promote / rollback (the client's account id) |
| `GREENJOBS_PROD_BUILD_TOKEN` | `production` | optional: production export check (skipped if unset) |
| `GREENJOBS_PROD_ACCESS_CLIENT_ID` / `_SECRET` | `production` | optional: only when the hidden canary is switched on |

Worker runtime secrets (`RESEND_API_KEY`, `BUILD_TOKEN`) are set per env with
`wrangler secret put NAME --env staging|production`; the pipeline never reads or writes them.
GitHub setup: environment `production` with a required reviewer and deployment branch `main` only.
Repository variable `GREENJOBS_STAGING_READY=true` switches CD to staging on (skipped until then).

## Gates, in order

1. `greenjobs-ci` (push / PR on GreenJobs paths): secret scan, workspace SAST (ruff + semgrep + native rules)
   on changed Python, `node --check` on changed JS, `release.py check-config`, then `run_tests.sh` (all tiers)
   and `pytest tests/greenjobs_redesign/smoke`. SAST failure stops before tests.
2. `greenjobs-cd-staging` (CI green on a push to main): deploys that exact sha: D1 schema, migrations,
   public seed, Worker, both boards; then `smoke.py --mode full`; ledger artifact
   `greenjobs-staging-ledger-<sha>`.
3. `greenjobs-promote` (manual, `production` reviewer): the sha must be on main and its staging record a full
   smoke pass; records the previous Worker version, Pages deployments and D1 Time Travel bookmark; D1 export
   to `greenjobs-backups` (must contain `CREATE TABLE`; the runner copy is deleted); destructive pending
   migrations need `allow_destructive`; migrate, deploy Worker, deploy boards; read-only smoke (canary off by
   default); on failure, automatic rollback of the Worker and both Pages projects, then smoke again.
   D1 is never restored automatically; the rollback prints the Time Travel restore command for a human.

## Smoke checks (`smoke.py`)

health, job list (API, paginated) and board list page, KPI dashboard, security headers (Worker + boards),
`/api/stats` parity with the paginated list and every `data-stat` figure on the board's home page and KPI
dashboard (`data-stat="<path into /api/stats>"`, e.g. `salary.n_jobs`, `kpis.live`; a key the API lacks or a
different value fails, and zero marked figures fails), `job_page[site]` (each Worker host renders its first
board job at `/{site}/jobs/<slug>/` with JobPosting data), 20 sampled
redirects from `redirect_map.json` (deterministic per sha) answering 301 to the mapped target, which
answers 200, export auth (401 anonymous, 200 with token), `live_wiring[site]` (each board's API origin from
`environments.json` `api_base`, "" = the board's own host: `/api/config` answers the board Origin with CORS, and
the paginated `/api/jobs?view=board` set equals `/api/stats` `live_jobs`; the detail line shows the alert /
newsletter flags). Staging adds: create an email-mode and a link-mode
job (Access service token), poll until public (15 min ceiling, 30 s poll), apply in both modes (link: 409
`apply_externally`; email: 201 `dry_run`), close both (always, even after a failed check), expect 410.

## Closed at integration (2026-11-20)

- `GET /api/health` (no auth: release sha, Worker version, D1 reachability) and `/api/stats` `live_jobs` exist.
- A closed job answers 410 from `GET /api/jobs/{id}` (a draft stays 404).
- Access service tokens: a JWT whose `common_name` is on `ACCESS_SERVICE_TOKEN_IDS` reaches only the smoke paths
  (create, read, close a job) and `/api/admin/import`; everything else stays staff-only.
- The boards ship `_redirects` (this board's legacy URLs from `ops/generated/bulk_redirects.json`; the smoke
  samples the same rules) and `_headers` (CSP with inline-script hashes, HSTS, nosniff, Referrer-Policy,
  frame-ancestors; `X-Robots-Tag: noindex` unless `robots_index`). Query-string legacy URLs (`*.asp?...`) are
  the Worker table's job in production; Pages matches paths only.
- Staging is noindex (`robots_index: false`); production builds with `--robots-index --live-api --analytics production`.
- Boards -> Worker (2026-11-20): staging boards build with `--api-base <workers.dev origin>` (`api_base` in
  environments.json; one Worker host serves both editions through `?site=`; the Worker's `ALLOWED_ORIGINS` lists
  both Pages origins; `_headers` `connect-src` adds exactly that origin). Production: same host, no flag. GA4 is
  `analytics: "off"` on staging and `"production"` in production only (the Worker adds the tag only on the
  production hosts in `src/analytics.json`).

## Staging as deployed (2026-11-20, ledger: build/release_ledger/staging_2026-11-20.jsonl)

- Worker `https://greenjobs-platform-staging.debanjan186.workers.dev` (IE host), D1 `greenjobs-staging` (WEUR),
  boards `https://greenjobs-staging-ie.pages.dev`, `https://greenjobs-staging-uk.pages.dev`. Staff console path
  `/admin/` answers 401/503 until Access exists (fail closed).
- First deploy: wrangler 4.166 uploaded the Worker, then failed on a follow-up API call (code 10007) because
  workers.dev was not yet enabled for the new script; enabling it once (`POST .../workers/scripts/<name>/subdomain`
  `{"enabled":true}`) fixed every later run.
- Blocked on operator inputs: Cloudflare Access is not enabled on our account (Zero Trust "Enable Access"), so
  there is no staging team domain, AUD or smoke service token and the smoke `write_flow` fails by design;
  R2 is not enabled (CV uploads answer 503 on staging). Once Access exists: set `ACCESS_TEAM_DOMAIN`,
  `ACCESS_AUD`, `STAFF_EMAILS`, `ACCESS_SERVICE_TOKEN_IDS` (the token's Client ID) in `[env.staging.vars]`,
  export `GREENJOBS_SMOKE_ACCESS_CLIENT_ID/_SECRET`, re-run `stage.sh --execute`.
- The staging BUILD_TOKEN secret is set on the Worker; its value is held outside the repo (pass it to smoke as
  `GREENJOBS_SMOKE_BUILD_TOKEN`).

## Placeholders to fill before the first live run

`REPLACE_WORKERS_SUBDOMAIN` (environments.json + wrangler.toml), `REPLACE_WITH_STAGING_D1_ID`,
`REPLACE_WITH_PRODUCTION_D1_ID`. `release.py --execute` refuses while any is present.

## Local equivalents (dry-run by default; print the exact wrangler commands)

```bash
bash execution/gtm_client_workflows/greenjobs_redesign/deploy/stage.sh
bash execution/gtm_client_workflows/greenjobs_redesign/deploy/promote.sh --staging-record <staging deploy_record.json>
bash execution/gtm_client_workflows/greenjobs_redesign/deploy/rollback.sh --record <deploy_record.json>
# live: GREENJOBS_RELEASE_TARGET=<env> ... --execute (clean tree, HEAD = the sha)
```

## Board figures from /api/stats (staging, 2026-11-20)

The static boards are built from the 2026-09-22 snapshot while D1 holds the seeded live set, so build-time
figures differ from `/api/stats` (seeded `posted_at` = the seed date, no closing dates, different salary
inputs). With `board_stats_from_api: true` (staging only) `release.py` GETs `/api/stats?site=` for each
edition right after the Worker deploy and passes it to `build_site.py --stats-json ie=... --stats-json
uk=...`; the build writes those values into every `data-stat` slot and the dashboard's `gj-dash` payload
(after validation, before `_headers`, so the CSP hashes cover the final HTML). The no-JS page then shows what
the live scripts show, and smoke `stats_parity` re-checks every marked figure. A figure that changes after the
deploy (a job closes, the date rolls over) fails the next smoke until the next deploy: the static fallback is
stale then, which is what the check is for. Production keeps `board_stats_from_api: false` (no behaviour
change); decide at go-live whether its boards take the same step.
