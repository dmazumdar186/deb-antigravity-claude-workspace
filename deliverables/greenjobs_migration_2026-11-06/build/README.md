# GreenJobs migration build pack

Written 2026-11-07. Internal engineering pack for moving greenjobs.ie (site `ie`) and greenjobs.co.uk (site `uk`)
off Strategies. Switch Thu 3 Dec 2026, buffer Fri 4 Dec, Strategies off Sun 6 Dec. Plan and scope:
`../FEASIBILITY_MATRIX.md` (§7 and §8 are binding for engineering) and `../transition_plan.html`.

## Files in `build/`

| File | What it is |
|---|---|
| `README.md` | This index |
| `ARCHITECTURE.md` | Components, data flows, trust boundaries, diagram, environments, phase 2, failure modes |
| `CUTOVER_RUNBOOK.md` | Dated DNS and MX cut-over checklist with go/no-go and rollback |
| `DECISION_TABLE.md` | Keith's twelve questions: likely answers, the config change each triggers, Monday-evening triage |
| `REDTEAM_CHECKLIST.md` | Frozen adversarial checklist (25 items); audits run against it only |
| `SAST_REPORT.md` | Static analysis results for the Worker and the import script |
| `run_tests.sh` | One-command offline test run (all tiers) |
| `d1/schema.sql` | D1 schema; idempotent (`IF NOT EXISTS`) |
| `d1/upserts.sql` | Canonical prepared-statement upserts used by the Worker and the import emitter |
| `import/IMPORT_MAPPING.md` | Strategies report columns mapped to D1 fields |
| `features/*.feature` | BDD scenarios for posting, applying, import and auth |

## Code and tests (outside `build/`)

| Path | What it is |
|---|---|
| `execution/gtm_client_workflows/greenjobs_redesign/platform_worker/` | Worker `greenjobs-platform` (API, apply, console, cron rebuild) |
| `execution/gtm_client_workflows/greenjobs_redesign/strategies_import.py` | CSV validator and SQL emitter (dry-run by default) |
| `execution/gtm_client_workflows/greenjobs_redesign/strategies_mapping.json` | Column mapping read by the validator |
| `execution/gtm_client_workflows/greenjobs_redesign/build_site.py`, `deploy_cloudflare.sh` | Static site build and Pages deploy (deploy refuses without `.greenjobs-build-ok` and a passing `validate_site.py`) |
| `tests/greenjobs_redesign/platform/` | Worker unit tests and feature runners (`node --test`) |
| `tests/greenjobs_redesign/test_strategies_import.py` | Import validator tests (pytest) |

## Run the tests (offline, no `.env`, no network)

```bash
bash deliverables/greenjobs_migration_2026-11-06/build/run_tests.sh
```

Tiers: 1 schema applies twice and every upsert compiles; 2 import validator; 3 Worker and features;
4 no CSV under the migration deliverable. Exit 0 and `ALL GREEN` only if every tier passes.

## Rules that apply to every change

- `DRY_RUN="1"` by default. Live sending needs `DRY_RUN="0"` and `LIVE_CONFIRM="send-applications"`, set by the
  operator on switch day.
- No candidate data before the DPA is signed. CSVs live only in GreenJobs' own storage (their R2 bucket or Drive),
  never in git or `.tmp/`. `--emit-sql` writes outside the repo.
- Secrets (`RESEND_API_KEY`, `BUILD_TOKEN`, `DEPLOY_HOOK_URL`) are Worker secrets only.
- Floor for 3 Dec, never trimmed: boards on Keith's domains with current jobs, staff posting console, applications
  to an inbox. Trim order: alert emails, candidate record import, newsletter.

## Day one: Tue 10 Nov, order of work

Starts if Keith's answers arrive Mon 9 Nov evening. Triage first (`DECISION_TABLE.md`, Monday-evening triage).

1. Triage Keith's answers; set the defaults for anything unanswered; note which answers are still owed by
   Wed 11 Nov (DPA, exporter, DNS holder).
2. `bash run_tests.sh` on a clean checkout; must be green before any change.
3. Ask Keith's side for access to GreenJobs' Cloudflare account (password manager, never chat). Create D1
   `greenjobs` and apply `d1/schema.sql`; create the R2 bucket. No data yet.
4. Deploy `greenjobs-platform` with `DRY_RUN="1"` to staging; set up Cloudflare Access with `STAFF_EMAILS`.
5. Front-end refresh: point `build_site.py` at `GET /api/export/jobs?site=` and deploy both boards to `*.pages.dev`.
6. Posting console: post, edit, close end to end on staging, rebuild via the deploy hook.
7. Redirect map: old ASP URLs from the 22 Sep scrape to new paths.
8. Start the zone inventory from public DNS (`dig`) for both domains, ready for `CUTOVER_RUNBOOK.md` T-7.
9. Exports and import wait for the DPA (answer to Q12).
