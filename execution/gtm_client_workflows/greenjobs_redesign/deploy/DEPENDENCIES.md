# GreenJobs dependencies and who patches them

Promise (proposal v1.0 line 127, RECORD.md P25): "security patches and dependency updates applied as they are released".

## Inventory

| Dependency | Pinned | Used by | Patched by |
|---|---|---|---|
| Cloudflare Workers runtime, Pages, D1, R2 | `compatibility_date = "2026-09-01"` (platform_worker/wrangler.toml) | the Worker, boards, database | Cloudflare patches and hosts it; we review the compatibility date monthly (`deploy/compat_check.py`) |
| Worker source (`platform_worker/src`) | no npm dependencies | production Worker | us (own code; CI SAST + tests) |
| wrangler (exact devDependency) | `4.166.0`, `platform_worker/package-lock.json` | `deploy/release.py`, `ops/d1_backup.py`, `deploy_cloudflare.sh`, CD workflows, via `npx --no-install --prefix platform_worker wrangler` (run `npm ci` there first) | us: Dependabot weekly PR, then CI |
| Python 3.11, Node 22 | `setup-python`/`setup-node` in workflows | CI, release | us (bump in a normal change); runner images by GitHub |
| python-dotenv 1.2.3 | `requirements-greenjobs.txt` | release.py, gaia sync, d1_backup, notify, export bot | us (Dependabot) |
| requests 2.34.2 | same | strategies_export_bot.py | us |
| jsonschema 4.26.0 | same | ops tests/validation | us |
| pytest 9.1.1 | same | all Python tests | us |
| pillow 12.3.0 | same | scrape_greenjobs.py (optional), build assets | us |
| imageio-ffmpeg 0.8.1 | same | generate_hero_footage.py (one-off) | us |
| pip-audit 2.10.1 | same and audit workflow | weekly audit | us |
| build_site.py, ops/*, deploy/* | stdlib only | static build, ops | n/a |
| GitHub Actions | major tags (`@v4`, `@v5`, `@v7`), the repo-wide convention: every workflow uses major tags, so we follow it; Dependabot raises the major bumps | all `greenjobs_*.yml` | us (Dependabot); GitHub patches within a major |
| Playwright | not pinned here: no GreenJobs file imports or declares it (only tests that need a browser use the workspace install) | browser tests | workspace-level; add it to requirements-greenjobs.txt if a GreenJobs test starts importing it |

## Automatic updates

- `.github/dependabot.yml`: npm (platform_worker), pip (`requirements-greenjobs.txt` directory), github-actions; weekly Monday, minor/patch grouped, label `greenjobs`. The github-actions ecosystem scans the repo's workflows (Dependabot cannot scope it by file), so non-GreenJobs workflows may receive PRs too.
- Every update PR runs `greenjobs-ci`. After merge to `main`, `greenjobs-cd-staging` deploys to staging and smoke-tests; production moves only through the manual, gated `greenjobs-promote`. Nothing goes straight to production.

## Alerts

- `greenjobs-audit` (weekly Monday, plus manual): `npm audit` (wrangler and any production deps) and `pip-audit` on `requirements-greenjobs.txt`. A HIGH/CRITICAL npm finding (any pip advisory, as pip-audit JSON has no severity) or an unreadable audit output fails the job and opens or updates the single issue labelled `greenjobs-audit`. That issue is the operator alert channel.
- First week of each month the same workflow runs `deploy/compat_check.py`: a `compatibility_date` older than 90 days fails the job with the flags to review. Bump it as a normal change (CI, staging smoke, promote).
- Both write `patches.json` (artifact `greenjobs-patches-<run>`). Drop it into `<state>/inputs/patches.json` and `ops/monthly_report.py` prints a "Patches and updates" section; missing or null values print "not measured yet".
