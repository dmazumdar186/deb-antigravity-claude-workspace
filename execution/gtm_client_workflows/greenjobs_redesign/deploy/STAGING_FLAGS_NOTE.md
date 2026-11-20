# Staging changes for the owner of wrangler.toml / release.py (eye review 2026-11-20)

Written by the eye-review fix stream. I did not edit `platform_worker/wrangler.toml`, `deploy/release.py`,
`deploy/stage.sh`, `deploy/smoke.py` or `deploy/environments.json`. These are the changes the fixes need there.

## 1. Alerts on staging, mail still off (M2)

In `platform_worker/wrangler.toml`, `[env.staging.vars]`, change one line:

```toml
ALERTS_ENABLED = "1"       # staging: sign-up testable end to end; DRY_RUN="1" + MAIL_PROVIDER="none" keep every mail unsent
```

Leave `DRY_RUN = "1"`, `MAIL_PROVIDER = "none"` and `NEWSLETTER_ENABLED = "0"` as they are. The staging Worker also
needs the secret `LIST_MAIL_SIGNING_KEY` (32 characters or more: `wrangler secret put LIST_MAIL_SIGNING_KEY --env staging`).
Without it, sign-up answers 503. The test `tests/greenjobs_redesign/platform/staging_flags.test.mjs` runs the committed
staging vars plus this change. It checks for a 202 response, a `pending` row and zero mail sent, including on the cron run.

## 2. Seed staging from `staging_seed.py`, not `release.py build_seed_sql` (B1, B2, B3, M1, M4, M6)

`release.py build_seed_sql` causes most of the review's blockers:
- it writes `closing_at = NULL` and `posted_at = as_of`, so every job is "Today" and the page says closed;
- it keeps only edition-currency salaries, which is where the 6-of-27 explorer comes from;
- it skips the edition rule, so the static board shows 77 UK jobs and D1 holds 98;
- it uses `INSERT OR IGNORE`, so a re-seed never fixes a stale row.

Replace the `seed()` and `deploy_boards()` steps as follows:

```bash
# 1. current public Gaia jobs (network read only; no Jev, no spend)
python3 execution/gtm_client_workflows/greenjobs_redesign/gaia_feed_sync.py --no-jev --out .tmp/gaia_feed
# 2. one normalised set -> seed.sql for D1 + data/{ie,uk}.json for the static build
python3 execution/gtm_client_workflows/greenjobs_redesign/staging_seed.py --env staging \
    --gaia-feed .tmp/gaia_feed/feed.json --out .tmp/staging_seed          # --seed-date defaults to today UTC
# 3. D1
wrangler d1 execute <staging d1> --env staging --remote --file .tmp/staging_seed/seed.sql
# 4. each staging board build gets the same data and date (manifest.json "build_site_args")
python3 .../build_site.py ... --data-dir .tmp/staging_seed/data --today <seed date>
```

- `seed.sql` upserts the rows (`ON CONFLICT DO UPDATE`). It closes earlier `created_by='staging-seed*'` rows that are no
  longer in the set, so the old 22 Sep rows get replaced, not kept. Its own gate (`assert_seed_safe`, `assert_jobs_safe`)
  refuses any other statement form, a personal-data column, a stored apply email, or a link to the old platform.
- If you keep `release.py`'s `assert_seed_safe`, update it to accept upserts, or call `staging_seed.assert_seed_safe`.
  The old check (`INSERT OR IGNORE` only, link mode only) refuses the new file.
- `build_site.py` refuses a production build (`--robots-index` or `--analytics production`) when the dataset is flagged
  `test_data`, so `--data-dir` must never be passed to a production build.
- Re-seed and rebuild together. Seeding D1 without rebuilding the boards brings back the list/page mismatch.

## 3. Templates touched by this stream (so the data-stat work can merge)

These are line-level edits that remove the frozen "Snapshot of …" / "as of …" wording. Each one is a single line:
- `home.html`: the hero `hero__snap` span and the ", {{snapshot_short}}" phrase
- `insights.html`: "as of <time>"
- `guides.html`, `guide_salary.html`, `landing.html`: the `{{updated}}` date
- `_shell.html` footer: now `<span data-live="n_jobs">{{n_jobs}}</span> live roles on {{domain}}.`
- `job.html`: `{{similar_hidden}}` on the Similar roles section

The jobs-page intro "N green roles" and the quick-match "N live roles are indexed" are left to the data-stat markers work.
