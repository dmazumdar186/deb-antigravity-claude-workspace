# GreenJobs source repository

Handover document (promise P19). Written 2026-11-21 from the repository as it stands.

## Where the code is

**Today:** the code lives in ProdCraft's workspace repository, together with ProdCraft's other work. It is not a
GreenJobs repository. **At handover** it moves to a private repository owned by GreenJobs (organisation or account,
ACCOUNTS.md). That move is **not yet done**; there is no GreenJobs repository in the repo's configuration.

Hand over only the GreenJobs paths below, with history if GreenJobs wants it (`git subtree split` or a filtered clone per
path), not the whole workspace. Never hand over: other clients' folders, ProdCraft pitch, proposal and research material
(`deliverables/greenjobs_redesign_2026-09-22/proposal/`, `research/`, `HANDOFF.md`), the engagement record, the `.claude/`
tooling, or any CSV or candidate export (none is in git; `.gitignore` blocks `deliverables/greenjobs_migration_2026-11-06/**/*.csv`).

## What belongs to GreenJobs

| Path | What it is |
|---|---|
| `execution/gtm_client_workflows/greenjobs_redesign/` | Everything that runs: `build_site.py` (static boards), `validate_site.py`, `platform_worker/` (Cloudflare Worker, no npm runtime dependencies), `deploy/` (release pipeline, smoke tests, environment config), `ops/` (probe, incidents, backup, DNS watcher, metrics, reports, redirects, test register), `strategies_import.py`, `strategies_export_bot.py`, `gaia_feed_sync.py`, `gaia_d1_sync.py`, `job_classifier.py`, `requirements-greenjobs.txt` |
| `deliverables/greenjobs_redesign_2026-09-22/src/` | The designed site: pages, CSS, JS (and its JS tests), data snapshots, logos |
| `deliverables/greenjobs_migration_2026-11-06/build/` | D1 schema and migrations (`d1/`), architecture, cutover runbook, BDD features, DNS inventory, redirect inputs, release ledgers, `run_tests.sh` |
| `deliverables/greenjobs_migration_2026-11-06/handover/` | This pack |
| `deliverables/greenjobs_migration_2026-11-06/guides/` | Registrar click guides for GreenJobs' staff |
| `tests/greenjobs_redesign/` | Every test (TEST_REGISTER.md lists them) |
| `.github/workflows/greenjobs_{ci,cd_staging,promote,audit}.yml`, `.github/dependabot.yml` | The pipeline |
| `directives/gtm_client_workflows/greenjobs_redesign.md` | The written procedure for every script (goal, inputs, outputs, edge cases) |

Items under these paths that mention ProdCraft's own tooling are optional and have a stdlib fallback or an off switch: the
Gaia scripts can use ProdCraft's "Jev" classifier (off with `--no-jev`; the board never calls it), and
`.github/dependabot.yml` also scans the other workflows of the shared repository. Review both when the repository is split.
The paths in the workflow `paths:` filters and in several scripts are written relative to the workspace layout; keep the same
folder layout in the new repository, or update those paths in one change.

## Running it from a fresh clone

Prerequisites: Python 3.11 or later, Node 22 (`GJ` = `execution/gtm_client_workflows/greenjobs_redesign`).

```
pip install -r GJ/requirements-greenjobs.txt
npm ci --prefix GJ/platform_worker          # only needed to run wrangler (deploys, backups)
bash deliverables/greenjobs_migration_2026-11-06/build/run_tests.sh   # all offline tiers, no secrets, exit 0 = green
```

Offline means no network and no `.env`. A browser is not needed for `run_tests.sh`.

## Tests

- Full suite: `bash deliverables/greenjobs_migration_2026-11-06/build/run_tests.sh` (six tiers: D1 schema and migrations,
  Python pytest tiers, Worker and BDD tests with Node, ops tests, static-site and pipeline tests, a no-candidate-data
  check).
- Register by promise, with run commands and last result: `TEST_REGISTER.md`; regenerate with
  `python3 GJ/ops/test_register.py --run --out deliverables/greenjobs_migration_2026-11-06/handover/TEST_REGISTER.md`.
- Browser-based layout checks (`tests/greenjobs_redesign/layout.test.mjs`, `phone_layout.mjs`, `r4_layout.mjs`,
  `verify_browser.mjs`) need a headless browser and are not in `run_tests.sh`. Their visual review reports are in
  `deliverables/greenjobs_migration_2026-11-06/qa/` (not part of the pipeline).
- Staging write-flow smoke needs Access service-token secrets (RUNBOOK section 9); it does not run in `run_tests.sh`.

## Pipeline

1. `greenjobs-ci` (`.github/workflows/greenjobs_ci.yml`): push or pull request on the paths above. Secret scan, SAST,
   `node --check`, `release.py check-config`, `run_tests.sh`, `pytest tests/greenjobs_redesign/smoke`.
2. `greenjobs-cd-staging`: CI green on `main` deploys that sha to staging and smoke-tests it. Switched on by the
   repository variable `GREENJOBS_STAGING_READY=true`.
3. `greenjobs-promote`: manual, `production` environment with a required reviewer, one exact sha, backup, deploy, smoke,
   automatic rollback.
4. `greenjobs-audit`: weekly `npm audit` and `pip-audit`, monthly compatibility-date check, one tracking issue.
5. Dependabot: weekly pull requests for npm, pip and Actions.

Settings to recreate in the new repository (names only): environments `staging` and `production` with the secrets listed
in ACCOUNTS.md; `production` with a required reviewer and deployment branch `main`; variable `GREENJOBS_STAGING_READY`;
branch protection on `main` requiring `greenjobs-ci`. Not yet done in any GreenJobs-owned repository.

## Read first

1. `RUNBOOK.md` (this folder) for operations.
2. `directives/gtm_client_workflows/greenjobs_redesign.md` for every script.
3. `deliverables/greenjobs_migration_2026-11-06/build/ARCHITECTURE.md` for the design.
4. `execution/gtm_client_workflows/greenjobs_redesign/deploy/ENVIRONMENTS.md` and `DEPENDENCIES.md`.
5. `execution/gtm_client_workflows/greenjobs_redesign/platform_worker/README.md` for routes and config.

## Not yet done

- The GreenJobs-owned private repository, the code transfer and the recreated environments, secrets and branch protection.
- Production resource ids in `platform_worker/wrangler.toml` and `deploy/environments.json` (placeholders remain).
- Scheduling of the ops scripts (no workflow runs them).
