# GreenJobs staging seed

**Goal.** Staging D1 and the static staging boards show the same current public jobs, built from one normalised
set. A list then never shows a job whose page says it has closed, and every figure matches /api/stats at build time.
This was written after the eye review of 2026-11-20 failed staging (`deliverables/greenjobs_migration_2026-11-06/qa/EYE_REVIEW_2026-11-20.md`).

## Inputs

- `--env staging` (required; any other value refuses)
- `--seed-date YYYY-MM-DD` (default: today UTC)
- `--gaia-feed .tmp/gaia_feed/feed.json` (the output of `gaia_feed_sync.py --no-jev`)
- `--september-dir` (default: `deliverables/greenjobs_redesign_2026-09-22/src/data`)
- `--out` (default `.tmp/staging_seed`; must be under `.tmp/` or `deliverables/`)

## Tools/Scripts

- `execution/gtm_client_workflows/greenjobs_redesign/gaia_feed_sync.py` (public read only; no Jev, no spend)
- `execution/gtm_client_workflows/greenjobs_redesign/staging_seed.py`
- `build_site.py --data-dir <out>/data --today <seed date>`

## Outputs

- `<out>/data/{ie,uk}.json`: the dataset the static board is built from
- `<out>/seed.sql`: for `wrangler d1 execute --file`
- `<out>/manifest.json`: counts, the static ids and salary figures, and the build_site args

## Steps

1. `python3 execution/gtm_client_workflows/greenjobs_redesign/gaia_feed_sync.py --no-jev --out .tmp/gaia_feed`
2. `python3 execution/gtm_client_workflows/greenjobs_redesign/staging_seed.py --env staging --gaia-feed .tmp/gaia_feed/feed.json`
3. Apply `.tmp/staging_seed/seed.sql` to the staging D1 (`wrangler d1 execute ... --env staging --remote --file`).
4. Build each staging board with `--data-dir .tmp/staging_seed/data --today <seed date>`, then deploy it.
   Never seed without rebuilding the boards.

The release wiring is in `execution/gtm_client_workflows/greenjobs_redesign/deploy/STAGING_FLAGS_NOTE.md` §2.
`release.py` belongs to the release owner.

## Data choice: Gaia feed plus September test data

| Source | What it is | Why |
|---|---|---|
| Gaia Talent feed (`gaiatalent.com/wp-json/wp/v2/jobs`, status `ready`) | Real, current public jobs with their real posted dates and apply links on gaiatalent.com (83 in the feed on 2026-11-20, 53 ready, all IE) | The only current public source we can read without the Strategies export |
| September board jobs (`src/data/{ie,uk}.json`), re-based | Dates moved forward by (seed date − 22 Sep). Titles get the prefix "[Test data] ". The dataset is marked `test_data: true` and the rows `created_by='staging-seed-test'` | Gives the filters, maps and salary charts real volume. Gaia alone has no UK roles and few salaries |

Rejected options:
- Gaia only: the UK board would be empty and the explorer would have no data.
- The 22 Sep snapshot as it was: that is the bug this fixes.
- A live scrape of greenjobs.ie: that platform is being retired and it would be a third source.

## Rules (each one has a test)

- **Staging only.** `prepare()` and `seed_sql()` refuse any other env. `build_site.py` refuses a `test_data`
  dataset in a production build (`--robots-index` or `--analytics production`). Test data never reaches production.
- **One live rule.** Status `live` and the closing date not passed, compared as UTC calendar days. It lives in
  `build_site.is_live`, `platform_worker/src/live.js` (`isLive` and `liveWhere`) and `jobs.js` `isClosed`.
  Closing dates are seeded; they are never set to NULL.
- **Posted date.** The source's date (Gaia `date_gmt`; for the September jobs, `posted` + shift) is the posted date.
  The seed time is never used. The Worker shows no posted date at all rather than `created_at`.
- **Currency.** Each role keeps the currency it was advertised in. Sterling roles on the IE board stay GBP
  (the build_site twin correction), so they show £ with a ≈ € note.
- **Apply.** A URL on the old platform (`*.asp`, `/browse-jobs/`, `/jobboard/` on greenjobs.*, or a strategies host)
  is switched to email mode. No address is seeded, so applications go to the site's default inbox.
- **Safety.** `assert_jobs_safe` and `assert_seed_safe` allow only upserts into employers/jobs/job_facets plus one close
  scoped to earlier seed rows. They refuse any personal-data column and any stored apply email.
- **Idempotent.** Running the seed again with the same inputs gives byte-identical files and converges D1.

Tests: `tests/greenjobs_redesign/test_eye_review_fixes.py` and
`tests/greenjobs_redesign/platform/live_consistency.test.mjs`. The second loads the seed into D1 and checks the D1
live set against the static set, the salary figures and every card's job page.

## Edge cases

- **Empty or failed Gaia fetch.** `gaia_feed_sync` exits with a gate code. Do not seed without it.
  `staging_seed --gaia-feed` refuses a feed with no jobs.
- **Seed date.** Re-seeding on a later day moves the test data forward again and closes rows that are no longer in the
  set. Always rebuild the boards together with the seed.
- **Production.** Production data comes only from the Strategies import, the Gaia D1 sync and the console.
  `release.py` refuses `--data-dir` on any non-staging build, and `build_site.py` refuses a `test_data` dataset in a
  production build. The Strategies import applies the same sterling rule on the IE board: a UK role whose salary text
  shows £ stays GBP, and `--uk-jobs-csv <UK jobs report>` restores its greenjobs.co.uk twin's GBP figures
  (`build_site.sterling_correction`); without a twin the euros stay and the summary counts it (`sterling.eur_unverified`).

## Release wiring (done 2026-11-20)

`release.py stage` runs steps 1-4 itself: `gaia_feed_sync.py --no-jev`, `staging_seed.py --seed-date <today UTC>`
(override with `GREENJOBS_SEED_DATE`), `assert_seed_safe` (accepts the upsert file), `wrangler d1 execute`, then both
board builds with `--data-dir <workdir>/staging_seed/data --today <seed date>`. Both staging Workers run
`ALERTS_ENABLED="1"` with `DRY_RUN="1"` and a staging-only `LIST_MAIL_SIGNING_KEY` secret (set with
`wrangler secret put`, never committed). The smoke checks the alert sign-up answers 2xx on both boards, that no
rendered page links into the retired platform, and compares the jobs-page intro and quick-match counts with /api/stats.
