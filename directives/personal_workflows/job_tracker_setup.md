# Job Tracker — Setup Helper SOP

## Goal

One-shot setup script that validates the environment before the first production run of the French PM/PO Job Tracker. It checks required env vars, verifies pip package availability, optionally installs missing packages, and optionally initialises the SQLite database schema. Run once after first checkout and again whenever the environment is re-provisioned.

## When to use

- First time setting up the tracker on a new machine or environment.
- After adding a new required env var or dependency (re-run to confirm).
- When the DB file is missing or corrupted and needs to be recreated.
- Called from step 1 of the first-time setup flow in `directives/personal_workflows/job_tracker_pm_france.md`.

## Inputs

### CLI flags

| Flag | Purpose |
|------|---------|
| `--check-only` | Print env/package/DB status and exit. This is the default when no action flags are given. |
| `--install-deps` | Pip-install any missing packages from the required list. Does nothing if all packages are present. |
| `--init-db` | Create (or migrate) the SQLite database schema via `job_tracker_db.init_db()`. |

Flags can be combined: `--install-deps --init-db` runs both actions in sequence.

### Environment variables required

These must be present in `.env` before running the tracker in production. The setup script reports their status but does NOT validate values — only that the variable is set and non-empty.

| Variable | Where to get it |
|----------|----------------|
| `FIRECRAWL_API_KEY` | https://firecrawl.dev — dashboard → API Keys |
| `SERPER_API_KEY` | https://serper.dev — dashboard → API Key |
| `FRANCE_TRAVAIL_CLIENT_ID` | https://francetravail.io — create an app, copy Client ID |
| `FRANCE_TRAVAIL_CLIENT_SECRET` | https://francetravail.io — same app, copy Client Secret |
| `INSEE_SIRENE_API_KEY` | https://api.insee.fr — register and generate a token |
| `GMAIL_SMTP_USER` | Your Gmail address (e.g. `you@gmail.com`) |
| `GMAIL_SMTP_APP_PASSWORD` | https://myaccount.google.com/apppasswords — 16 chars, no spaces |
| `JOB_TRACKER_RECIPIENT` | Email address to receive the daily digest |

`JOB_TRACKER_DB_PATH` is optional — omit it to use the config default (`.tmp/job_tracker.db`).

### Config keys consumed from `config/job_tracker.json`

- `db_path_env` — env var name to check for a DB path override
- `default_db_path` — fallback DB path used when the env var is not set

## Outputs

- **stdout:** A formatted status report showing `[✓ set]` / `[✗ MISSING]` for each env var, `[✓ found]` / `[✗ MISSING]` for each package, and DB existence + size. Followed by an actionable Next Steps list.
- **DB file (if `--init-db`):** SQLite schema created at the resolved DB path. Tables: `companies`, `jobs`, `contacts`, `notifications_log`.
- **Pip installs (if `--install-deps`):** Packages installed into the current Python environment. Exit code 1 if any install fails.

## How to run

```bash
# Check env/packages/DB status only (no changes)
py execution\personal_workflows\job_tracker_setup.py --check-only

# Install missing packages
py execution\personal_workflows\job_tracker_setup.py --install-deps

# Create/migrate the SQLite database schema
py execution\personal_workflows\job_tracker_setup.py --init-db

# Install deps + init DB in one step
py execution\personal_workflows\job_tracker_setup.py --install-deps --init-db
```

## Tools / dependencies

- Python packages: `firecrawl-py`, `langdetect`, `requests`, `python-dotenv`, `freezegun`, `pytest`
- These 6 packages are the complete required set. The script pip-installs them by their PyPI names.
- Package-to-module name mapping (where they differ): `firecrawl-py` → `firecrawl`, `python-dotenv` → `dotenv`.
- Internal imports: `execution.personal_workflows._jt_utils.load_jt_config`, `execution.personal_workflows.job_tracker_db.init_db`.

## Edge cases & gotchas

- Running `--check-only` never exits with code 1 — it is purely informational.
- Running `--install-deps` when all packages are present is a no-op and exits 0.
- `--init-db` is idempotent: `CREATE TABLE IF NOT EXISTS` is used throughout `job_tracker_db.py`, so re-running it is safe.
- If `FIRECRAWL_API_KEY` is set but invalid, the setup script will report it as `[✓ set]` — credential validity is only caught at scrape time.
- On Windows, the script must be invoked with `py`, not `python3`.

## Self-anneal hooks

This script has no API calls and cannot fail in a recoverable way. If `--init-db` fails, it prints the exception and exits 1. Common causes: the `.tmp/` directory does not exist (create it manually or let the orchestrator create it on first run), or a permissions issue with OneDrive sync locking the file.

## Exit Criteria

- `py execution\personal_workflows\job_tracker_setup.py --check-only` exits `0` and prints a status report with `[✓ set]` for all 7 required env vars (no `[✗ MISSING]` lines).
- `py execution\personal_workflows\job_tracker_setup.py --check-only` prints `[✓ found]` for all 6 required packages (`firecrawl-py`, `langdetect`, `requests`, `python-dotenv`, `freezegun`, `pytest`).
- `py execution\personal_workflows\job_tracker_setup.py --init-db` exits `0` and creates the SQLite file at the configured path with tables `companies`, `jobs`, `contacts`, and `notifications_log` (confirmed via `sqlite3 <db_path> ".tables"`).
- Re-running `--init-db` on an already-initialised DB exits `0` without error (idempotency confirmed by the `CREATE TABLE IF NOT EXISTS` pattern).
- `--check-only` exits `0` (not `1`) regardless of missing vars — purely informational.

## Changelog

- 2026-05-14: created.
