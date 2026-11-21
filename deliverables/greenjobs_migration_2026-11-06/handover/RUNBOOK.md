# GreenJobs operations runbook

Handover document (promise P19). Written 2026-11-21 from the repository as it stands. Every command below names the
script that runs it and every script exists in the repo. Anything that is not built, not wired or not set up yet says
**not yet done**. No secret values appear here; secrets are named only.

Paths are relative to the repository root. `GJ` = `execution/gtm_client_workflows/greenjobs_redesign`.

## 1. What runs where

| Piece | What it is | Where it runs | Source |
|---|---|---|---|
| Boards (greenjobs.ie, greenjobs.co.uk) | Static pages, built by `GJ/build_site.py` | Cloudflare Pages: `greenjobs-ie`, `greenjobs-uk` (production); `greenjobs-stg-ie`, `greenjobs-stg-uk` (staging) | `deliverables/greenjobs_redesign_2026-09-22/src/` |
| Platform Worker | Job pages, job API, staff console, apply endpoint, review queue, alerts and newsletter | Cloudflare Workers: `greenjobs-platform` (production), `greenjobs-platform-staging` and `greenjobs-platform-staging-uk` (staging) | `GJ/platform_worker/` |
| Database | D1 `greenjobs` (production), `greenjobs-staging` | Cloudflare D1 | `deliverables/greenjobs_migration_2026-11-06/build/d1/` |
| Staff login | Cloudflare Access in front of `/admin*` and `/api/admin/*`, re-verified inside the Worker | Cloudflare Zero Trust | `GJ/platform_worker/src/auth.js` |
| Mail | Resend, dry-run until go-live | Resend account | `GJ/platform_worker/src/mail.js` |
| Pipeline | CI, deploy to staging, gated promote, weekly audit | GitHub Actions | `.github/workflows/greenjobs_{ci,cd_staging,promote,audit}.yml` |
| Ops scripts | Probe, incidents, backup, DNS watcher, metrics, reports | Run from a machine or scheduler (section 3) | `GJ/ops/` |

Full design: `deliverables/greenjobs_migration_2026-11-06/build/ARCHITECTURE.md`. Names and gates:
`GJ/deploy/ENVIRONMENTS.md`. Worker routes and config: `GJ/platform_worker/README.md`.

State today (21 Nov 2026): staging is live on ProdCraft's Cloudflare account (IE board `https://greenjobs-stg-ie.pages.dev/ie/`,
UK board `https://greenjobs-stg-uk.pages.dev/uk/`); the production Cloudflare account does not exist yet, so production
is **not yet done** (see ACCOUNTS.md). Applications and alerts are dry-run: no email is sent anywhere.

CVs are attached to the application email, not stored (`CV_STORAGE=attach`). R2 is therefore optional.

Operator state directory for the ops scripts: `.tmp/greenjobs_ops/` (scratch, never committed; `GJ/ops/common.py`
`STATE_DIR`). On the handover machine, point `--state-dir` at a folder in GreenJobs' own storage.

## 2. Daily, weekly, monthly

Scheduling: **not yet done.** No workflow or scheduler in the repo runs the ops scripts (only `greenjobs-audit` is
scheduled, see section 12). Until a scheduler is set up, run them by hand at the cadence below. `dns_watcher.py` names
"a GitHub Actions cron or the operator's machine" as the intended host.

| Cadence | Task | Command | Script |
|---|---|---|---|
| Every 5 min | Uptime and posting-outage probe | `python3 GJ/ops/uptime_probe.py --live [--send]` | `GJ/ops/uptime_probe.py` |
| Every 10 min | DNS watcher (only while domains are moving) | `python3 GJ/ops/dns_watcher.py [--send]` | `GJ/ops/dns_watcher.py` |
| Daily, outside 09:00-17:00 UTC | D1 backup to R2 | `python3 GJ/ops/d1_backup.py --live` | `GJ/ops/d1_backup.py` |
| Daily | Status page and measures | `python3 GJ/ops/metrics.py --inputs DIR [--send]` | `GJ/ops/metrics.py` |
| Daily, 3-16 Dec 2026 | Acceptance check | `python3 GJ/ops/acceptance_check.py --date YYYY-MM-DD` | `GJ/ops/acceptance_check.py` |
| Weekly (Mon) | Dependency audit (automatic), Keith's 5-line email draft | `python3 GJ/ops/keith_weekly.py --next-step "TEXT"` | `GJ/ops/keith_weekly.py` |
| Monthly | Monthly report, compat-date check (automatic in the first week) | `python3 GJ/ops/monthly_report.py --month YYYY-MM --changes FILE` | `GJ/ops/monthly_report.py` |
| Quarterly | Restore drill | `python3 GJ/ops/d1_restore_drill.py --live` | `GJ/ops/d1_restore_drill.py` |

`--send` on every script is off by default: the script writes to an outbox in the state directory. Live sending needs
`RESEND_API_KEY`, `OPS_MAIL_FROM` and the recipient variable (`OPS_ALERT_EMAIL` for the operator; `DIANA_EMAIL` for the
DNS "done" email). Client-facing templates additionally need their sha256 in `GJ/ops/approved_templates.json`, which is
empty today, so no client email can go live yet (`GJ/ops/notify.py`).

Daily check by a person (10 minutes): open the status page `status/status.html` in the state directory
(written by `metrics.py`); anything red or UNMEASURED is read before anything else. A figure with no input shows
"UNMEASURED", never a pass.

## 3. Post, edit, close, reopen a job (staff console)

Staff open `https://www.greenjobs.ie/admin/` (or the staging IE host's `/admin/`). Cloudflare Access asks for a
login; the email must be on the Access policy and in the Worker's `STAFF_EMAILS`. Code: `GJ/platform_worker/src/routes/console.js`,
`routes/admin.js`.

1. **Post:** choose IE, UK or both in one form; fill title, employer, location, description, closing date, apply mode
   (email: on-site form, or link: the employer's own https URL), salary. Save. The job is public once the Worker reads it
   from D1 (job pages are rendered by the Worker; there is no rebuild). A posted job gets id `{site}:gj:{uuid}`; a retry
   with the same `Idempotency-Key` never duplicates.
2. **Edit:** every field except the employer. A stale edit (someone else saved first) answers 409: reload and redo it.
3. **Close:** the console asks to confirm; the job leaves the board and its page answers 410. Closing twice is harmless.
4. **Reopen:** edit a closed job, set status back to live and a new closing date in the future, Save. A closing date in
   the past is refused ("The closing date has passed").
5. Jobs imported from Strategies (`source='strategies'`) that are edited in the console are overwritten by the next
   import upsert (`platform_worker/README.md` known limits).

Tested by `tests/greenjobs_redesign/platform/e2e_board.test.mjs` (post, edit, close, reopen) and
`deliverables/greenjobs_migration_2026-11-06/build/features/posting_console.feature`.

## 4. Review queue

`/admin/review` (staff only; `GJ/platform_worker/src/routes/` review routes, README "Routes"). Jobs whose sector the
classifier is unsure of arrive here (feed jobs as drafts that go live on approval; Strategies jobs stay live and only
their sector is confirmed).

- Approve: accepts the suggested sectors. Change and approve: pick 1 to 3 sectors from the frozen vocabulary
  (`GJ/platform_worker/src/taxonomy.json`).
- A decided review is final; a closed job never goes live through review.
- The Gaia feed into the board is **off** and was never promised (RECORD P13): `FEED_IMPORT_ENABLED="0"`. The sync
  script `GJ/gaia_feed_sync.py` and `GJ/gaia_d1_sync.py` exist but nothing runs them on a schedule (not yet done).

## 5. Applications

`POST /api/apply` stores the application and mails it to the site inbox (`APPLY_INBOX_IE`, `APPLY_INBOX_UK`) or the
job's own address. Today `DRY_RUN="1"`: stored, not mailed. Going live is an operator decision, one change:
`DRY_RUN="0"`, `LIVE_CONFIRM="send-applications"`, `MAIL_PROVIDER="resend"`, `MAIL_FROM`, the inboxes, secret
`RESEND_API_KEY`, then deploy through the pipeline (section 7). The cron `*/10 * * * *` retries `pending`/`failed`
deliveries from the last 48 hours. `MAIL_DAILY_CAP` is the spend guard; each live send writes an `audit_log` row `mail.send`.
A failed live send with a CV answers 502 `delivery_failed` and the candidate resends.

## 6. Restore from backup

D1 is backed up daily by `GJ/ops/d1_backup.py --live` to the R2 bucket `greenjobs-backups`
(`GJ_BACKUP_BUCKET`), object `d1/<date>.sql`. This needs R2 enabled on the production account (**not yet done**; R2 is
not enabled on the staging account either, `deploy/environments.json` `_r2_note`). Before every production promote the
pipeline also exports D1 to the same bucket.

1. **Prove a backup restores (quarterly, safe):** `python3 GJ/ops/d1_restore_drill.py --live` restores the newest
   backup into a scratch database `greenjobs-drill-<date>`, compares row counts, deletes only the scratch database.
   Offline check of a downloaded dump: `python3 GJ/ops/d1_restore_drill.py --sqlite DUMP`.
2. **Undo a bad deploy or bad write, up to 30 days back:** D1 Time Travel. The pipeline records a bookmark at each
   promote; the rollback prints the exact command (`GJ/deploy/release.py`, `wrangler d1 time-travel restore <db> --bookmark <id>`).
   A human runs it; D1 is never restored automatically.
3. **Restore from an R2 dump:** download the object with `wrangler r2 object get greenjobs-backups/d1/<date>.sql`, restore it
   first into a scratch database as in step 1, check it, then apply to production with
   `wrangler d1 execute greenjobs --remote --file=<dump>`. Dumps contain personal data: keep them in GreenJobs' storage only.
4. Tell Keith what was restored and what is lost between the backup and the incident.

The first real restore drill has not been run against production (**not yet done**). Whether the drill has ever run live
anywhere is not recorded in the repo.

## 7. Release, promote, roll back

Nothing reaches production unchecked: CI, then staging with smoke tests, then a manual gated promote of that exact commit.
Details: `GJ/deploy/ENVIRONMENTS.md`, directive "Release pipeline".

1. **Change and test:** open a pull request touching GreenJobs paths. `greenjobs-ci` runs the secret scan, SAST,
   `release.py check-config`, then `bash deliverables/greenjobs_migration_2026-11-06/build/run_tests.sh` and
   `python3 -m pytest tests/greenjobs_redesign/smoke` (`.github/workflows/greenjobs_ci.yml`). Locally run the same.
2. **Staging:** merging to `main` triggers `greenjobs-cd-staging`, which deploys that sha (D1 schema, migrations, public
   seed, Worker, both boards) and runs `GJ/deploy/smoke.py --env staging --mode full --sha <sha>`. It only runs when the
   repository variable `GREENJOBS_STAGING_READY` is `true` (`greenjobs_cd_staging.yml`). By hand: `bash GJ/deploy/stage.sh`
   prints the commands; `GREENJOBS_RELEASE_TARGET=staging bash GJ/deploy/stage.sh --execute` runs them.
3. **Promote:** run the `greenjobs-promote` workflow manually (Actions, "Run workflow") with the full 40-character sha.
   The `production` GitHub environment needs a required reviewer. The sha must be on `main` with a passing staging record.
   It records the previous Worker and Pages versions and a D1 bookmark, exports D1 to R2, migrates, deploys, then runs
   `smoke.py --env production --mode read_only`. By hand: `bash GJ/deploy/promote.sh --staging-record <deploy_record.json>`.
   Destructive migrations (DROP, DELETE, RENAME, TRUNCATE) need `--allow-destructive` and a verified backup.
4. **Roll back:** automatic on a failed production smoke (Worker and both Pages projects, then smoke again). By hand:
   `bash GJ/deploy/rollback.sh --record <deploy_record.json>` prints the plan; add `--execute` with
   `GREENJOBS_RELEASE_TARGET=production` to run it. D1 data is restored by a person (section 6, step 2).
5. Placeholders `REPLACE_WITH_STAGING_D1_ID`, `REPLACE_WITH_PRODUCTION_D1_ID` in `platform_worker/wrangler.toml` and
   `environments.json` must be filled before a live run; `--execute` refuses while any `REPLACE_` is present. The
   production D1 id and Pages projects do not exist yet (**not yet done**).
6. Record of every run: `deploy_record.json`, `ledger.jsonl`, `summary.md`, artifact `greenjobs-<env>-ledger-<sha>`.

Domain switch (DNS and mail) is a separate, rehearsed procedure: `deliverables/greenjobs_migration_2026-11-06/build/CUTOVER_RUNBOOK.md`.
It is not yet done; planned switch day is Thu 3 Dec 2026.

## 8. Incident response

Service levels (proposal, RECORD P20): 99.9% monthly uptime; response within 4 hours for a posting outage (severity 1);
within 1 business day for anything else (severity 2); changes in 2 business days.

1. **Detect:** `uptime_probe.py --live` checks 20 hostnames, MX/SPF against the zone inventory, and per board the posting
   checks (`/admin/` not 5xx or 404, `GET /api/jobs` 200, `OPTIONS /api/apply` 2xx). Each failing core check opens one
   incident in the state directory and, with `--send`, alerts `OPS_ALERT_EMAIL` at once. Probe scheduling: **not yet done**.
2. **Acknowledge:** `python3 GJ/ops/incidents.py list`, then `python3 GJ/ops/incidents.py ack <id>`. The ack records the
   response time that SLA2 is graded on.
3. **Triage:** `GET /api/health` on the board host (release sha, Worker version, D1 reachable). Posting outage: check
   Cloudflare status, then the last deploy in the ledger; if it is the cause, roll back (section 7, step 4).
4. **Mail or DNS drift:** `dns_watcher.py` alerts on MX/SPF change and exits 2. Never edit the inventory to silence it;
   an approved mail change goes in `--baseline`.
5. **Data problem:** section 6.
6. **After:** tell Keith in writing what happened and when it was fixed; put the cause in the monthly report
   (`monthly_report.py --changes FILE`). Uptime and response figures come from the probe log and incidents, so a gap in
   probing shows as UNMEASURED, not as good.

Who is paged: `OPS_ALERT_EMAIL` (the address is set by the operator; empty means no alert mail, which is the staging
setting). The on-call arrangement after handover is **not yet done**; it is a contract matter (RECORD P20).

## 9. Rotate every secret (by name)

Values live only in GitHub environment secrets, Cloudflare Worker secrets and the operator's password manager. Never in
the repo, logs or chat. Names and users are from `GJ/deploy/ENVIRONMENTS.md` and `platform_worker/wrangler.toml`.

| Secret | Held in | Rotate by |
|---|---|---|
| `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` | GitHub environment `staging` | Create a new API token in Cloudflare (Workers Scripts Edit, D1 Edit, Pages Edit, R2 Edit), replace the secret, delete the old token |
| `GREENJOBS_PROD_CLOUDFLARE_API_TOKEN`, `GREENJOBS_PROD_CLOUDFLARE_ACCOUNT_ID` | GitHub environment `production` | Same, on the GreenJobs account |
| `GREENJOBS_STAGING_ACCESS_CLIENT_ID`, `GREENJOBS_STAGING_ACCESS_CLIENT_SECRET` | `staging` | Create a new Access service token; update both secrets and `ACCESS_SERVICE_TOKEN_IDS` in `wrangler.toml` `[env.staging.vars]`; deploy; delete the old token |
| `GREENJOBS_PROD_ACCESS_CLIENT_ID`, `GREENJOBS_PROD_ACCESS_CLIENT_SECRET` | `production` (optional) | Same, only if the hidden canary is used |
| `BUILD_TOKEN` (Worker secret) and `GREENJOBS_STAGING_BUILD_TOKEN` / `GREENJOBS_PROD_BUILD_TOKEN` (GitHub) | Worker and GitHub | Generate a long random value; `cd GJ/platform_worker && npx wrangler secret put BUILD_TOKEN --env production` (or `staging`); set the same value in the GitHub secret |
| `RESEND_API_KEY` | Worker secret (and the ops machine environment) | New key in Resend; `npx wrangler secret put RESEND_API_KEY --env production`; revoke the old key |
| `LIST_MAIL_SIGNING_KEY` | Worker secret | `npx wrangler secret put LIST_MAIL_SIGNING_KEY --env production` (32+ characters). Rotating it invalidates outstanding confirm and unsubscribe links |
| Strategies export login | Not stored in the repo | Reset by Strategies after the final export (`GJ/strategies_export_bot.py` directive) |

After any rotation: run `python3 GJ/deploy/release.py scan-secrets <changed files>` (it fails on a committed secret), then a staging
smoke. Staging secrets that are not yet in a GreenJobs-owned account are rotated again at handover (ACCOUNTS.md).

## 10. Add or remove a staff user

Two places must agree, or the user is locked out (fail closed):

1. Cloudflare Zero Trust, Access, the self-hosted application covering `/admin*` and `/api/admin/*` on both domains:
   add the email to the allow policy.
2. `STAFF_EMAILS` (comma list) in the Worker vars, `GJ/platform_worker/wrangler.toml`, `[env.production.vars]` (and
   staging); then deploy through the pipeline (section 7). Remove a user from both.

Employer logins (CHM Recruit, Mattinson) are phase 2 and off (`EMPLOYER_POSTING_ENABLED="0"`). The grant statement is
in `platform_worker/README.md` "Feed import, review queue, employer posting". Production `STAFF_EMAILS`, `ACCESS_AUD`
and `ACCESS_TEAM_DOMAIN` are empty in `wrangler.toml` today: **not yet done** (needs the production Access application).

## 11. Reports

| Report | Command | Notes |
|---|---|---|
| Status page and measures (SLA, M1-M11, backup age, drill) | `python3 GJ/ops/metrics.py --inputs DIR` | Writes `status.json`, `status.html`, `measures_ie.json`, `measures_uk.json` in the state directory. Missing inputs show UNMEASURED |
| Keith's weekly email (5 lines) | `python3 GJ/ops/keith_weekly.py --next-step "TEXT" [--out FILE]` | Renders text only; never sends. Outward text goes through the redteam gate first |
| Monthly report | `python3 GJ/ops/monthly_report.py --month YYYY-MM --changes FILE [--out FILE]` | Same rule; traffic from `traffic_<month>.json` in the inputs |
| Acceptance, 10 working days | `python3 GJ/ops/acceptance_check.py --date YYYY-MM-DD` | Evidence is the operator's dated `acceptance_evidence.json`; list `GJ/ops/acceptance_list.json` must be reconciled with the contract's list before 3 Dec (**not yet done**) |
| Redirect coverage | `python3 GJ/ops/redirects.py build [--live-ids FILE]`, then `python3 GJ/ops/redirects.py crawl --live` | 1,206 old URLs mapped; `crawl --live` measures the real result after the switch |
| Test register | `python3 GJ/ops/test_register.py --run --out deliverables/greenjobs_migration_2026-11-06/handover/TEST_REGISTER.md` | Regenerates TEST_REGISTER.md |
| Release ledger | CI artifact `greenjobs-<env>-ledger-<sha>` | One per deploy |

## 12. Dependency updates and the weekly audit

Inventory and owners: `GJ/deploy/DEPENDENCIES.md`.

- `.github/dependabot.yml`: weekly Monday PRs for npm (`platform_worker`), pip (`requirements-greenjobs.txt`) and
  GitHub Actions. Each PR runs `greenjobs-ci`; after merge, staging deploys and smoke tests; production moves only by the
  manual promote (section 7).
- `greenjobs-audit` (`.github/workflows/greenjobs_audit.yml`, Monday 06:17 UTC and on demand): `npm audit` and `pip-audit`;
  a HIGH/CRITICAL npm finding or any pip advisory fails the job and opens or updates the one issue labelled
  `greenjobs-audit`. That issue is the alert channel: someone must be watching the repository's notifications
  (not yet done for GreenJobs-owned notification settings).
- First week of each month the same workflow runs `GJ/deploy/compat_check.py`; a `compatibility_date` older than 90 days
  fails the job. Bump it in `platform_worker/wrangler.toml` as a normal change.
- Update steps: review the PR, check CI is green, merge, check the staging smoke passed, then promote.

## 13. Not yet done (summary, verified against the repo on 2026-11-21)

- Production Cloudflare account, zones, Pages projects, Worker, D1, Access application, Resend domain: not created.
- Production `wrangler.toml` ids and Access values (`REPLACE_WITH_PRODUCTION_D1_ID`, empty `ACCESS_*`, `STAFF_EMAILS`).
- Scheduling of probe, backup, DNS watcher, metrics, acceptance (no workflow or scheduler runs them).
- R2 on any account (backups need it; CVs do not); first live backup and restore drill.
- Live email (`DRY_RUN` is `"1"` everywhere); approved client email templates (`approved_templates.json` empty).
- Domain switch and the cutover rehearsal; sector-domain forwards (out of scope until Keith answers, P12).
- Move of the repository to a GreenJobs-owned private repository (SOURCE.md).
- Acceptance list reconciliation with the contract; named on-call after handover.
