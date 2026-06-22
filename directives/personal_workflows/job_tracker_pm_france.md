# French PM/PO Job Tracker — Master Orchestrator SOP

## Prior art pass

Retrospective per `~/.claude/rules/prior-art-first.md`. This directive pre-dates the rule (2026-06-18) and was effectively superseded by `directives/personal_workflows/job_search_sheet.md`. Retained for reference and the email-digest pattern it documents.

- **For source/scraper integrations**: see the per-source directives' own Prior art pass sections (Adzuna, Jooble, France Travail).
- **For contact enrichment**: see `directives/enrichment/firecrawl_linkedin_dork.md` -- Firecrawl Google dork pattern, ToS-safe.
- **For INSEE SIRENE company resolution**: French government public API (no scraping), `INSEE_SIRENE_API_KEY` in `.env` (currently empty -- this pipeline no longer runs).
- **For email rendering + delivery**: rendered HTML via Python template, SMTP send. No new service integration in this directive.

**Status**: superseded by `job_search_sheet.md` (operator preference for sheet over email digest, per `memory/project_job_search_sheet.md`). This file remains as historical context.

## Goal

Run a daily ETL pipeline that discovers Product Manager and Product Owner job openings posted at French digital-sector companies, filters out junior/intern/alternance roles and non-FR/EN postings, deduplicates against a 7-day rolling SQLite window, resolves company identity via the INSEE SIRENE API, enriches 3–5 contactable people per company (HR, CPO, VP Product, Head of Product, Senior PM) via Firecrawl Google dorks, and emails a rendered HTML digest to the operator. The pipeline is deterministic — same inputs always produce the same outputs. It is NOT probabilistic or ML-based; every decision (filter, dedup, classification) follows explicit rules in code.

## When to use

- Called daily at 06:00 Europe/Paris by the Modal cron (key: `job_tracker_pm_france` in `execution/webhooks.json`).
- Run manually on-demand to test or backfill: `py execution\personal_workflows\job_tracker_pm_france.py --dry-run`.
- Run in mock mode during development/debugging: `py execution\personal_workflows\job_tracker_pm_france.py --mock --dry-run`.
- Run with a subset of boards to diagnose a failing scraper: `--boards wttj,apec`.

## Architecture — Pipeline DAG (Stages A → H)

This is a strictly sequential, deterministic ETL DAG. There are no probabilistic choices; if any stage fails, it either returns a safe empty value (boards) or halts with exit code 1 (DB init, filter).

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                  job_tracker_pm_france.py  (orchestrator)                            │
│                                                                                      │
│  A ─── Discover ──────────────────────────────────────────────────────────────────── │
│        Per board (wttj, indeed, apec, francetravail, google):                        │
│          scrape(queries, output_path, run_id, max_results) → list[RawJob]            │
│          Board failures silently return [] and mark that board as count=0            │
│          Degraded-board detection: <30% of 7-day median → BOARD_DEGRADED event       │
│                                                                                      │
│  B ─── Normalize + Filter ─────────────────────────────────────────────────────────  │
│        job_filter.filter_jobs(all_raw, config)                                       │
│          normalize title/company → compute job_hash → langdetect → exclude/include   │
│          Outputs: candidates.json (kept), dropped.json (rejected)                    │
│                                                                                      │
│  C ─── Dedupe vs DB ───────────────────────────────────────────────────────────────  │
│        SELECT job_hash FROM jobs — split into new_candidates / existing_jobs         │
│                                                                                      │
│  D ─── Resolve Companies (SIRENE) ─────────────────────────────────────────────────  │
│        sirene_company_lookup.lookup_company(display_name) per distinct company        │
│        Annotates: siren, naf_code, is_digital_sector, website                        │
│        Skipped with --no-resolve; failures logged, pipeline continues                 │
│                                                                                      │
│  F1 ── Persist Companies ──────────────────────────────────────────────────────────  │
│        job_tracker_db.upsert_company() for each new distinct company                 │
│                                                                                      │
│  E ─── Enrich Contacts ────────────────────────────────────────────────────────────  │
│        firecrawl_linkedin_dork.find_contacts_for_company() per new company           │
│        Cache window: contact_cache_days (60) — skips re-enrichment within window     │
│        Skipped with --no-enrich; failures logged, pipeline continues                 │
│                                                                                      │
│  F2 ── Persist Contacts ───────────────────────────────────────────────────────────  │
│        job_tracker_db.upsert_contact() for each contact found                        │
│                                                                                      │
│  F3 ── Persist Jobs ───────────────────────────────────────────────────────────────  │
│        job_tracker_db.upsert_job() for new jobs                                      │
│        UPDATE last_seen_at for existing jobs                                          │
│        mark_expired() purges jobs older than digest_window_days                      │
│                                                                                      │
│  G ─── Compose Digest ─────────────────────────────────────────────────────────────  │
│        job_digest_renderer.render_digest_html(db_path, window_days, ...)             │
│        Output: .tmp/job_tracker/{run_id}/digest.html                                 │
│        Degraded boards surface as a banner at the top of the digest                  │
│                                                                                      │
│  H ─── Send Email ─────────────────────────────────────────────────────────────────  │
│        gmail_send_digest.send_digest(html, subject, recipient)                       │
│        Only executes when --send is passed AND --dry-run is NOT set                  │
│        log_notification() records outcome in DB regardless of send flag              │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

**Module ownership:**
| Stage | Module (absolute path) |
|-------|----------------------|
| A — WttJ | `execution/custom_scrapers/wttj_jobs.py` |
| A — Indeed | `execution/custom_scrapers/indeed_jobs.py` |
| A — APEC | `execution/custom_scrapers/apec_jobs.py` |
| A — France Travail | `execution/custom_scrapers/france_travail_jobs.py` |
| A — Google/Serper | `execution/custom_scrapers/google_jobs_serper.py` |
| B — Filter | `execution/custom_scrapers/job_filter.py` |
| C/F1/F2/F3 — DB | `execution/personal_workflows/job_tracker_db.py` |
| D — SIRENE | `execution/lead_sourcing/sirene_company_lookup.py` |
| E — Contacts | `execution/enrichment/firecrawl_linkedin_dork.py` |
| G — Renderer | `execution/personal_workflows/job_digest_renderer.py` |
| H — Email | `execution/google/gmail_send_digest.py` |
| All — Utils | `execution/personal_workflows/_jt_utils.py` |

## Inputs

### CLI arguments (full argparse spec)

| Flag | Type | Default | Purpose |
|------|------|---------|---------|
| `--boards BOARDS` | str (comma-sep) | all enabled in config | Restrict run to specific boards: `wttj,indeed,apec,francetravail,google` |
| `--mock` | flag | off | Load from `tests/fixtures/raw_{board}.json` instead of live scraping |
| `--dry-run` | flag | on (unless `--send`) | Persist to DB but skip sending the email |
| `--no-enrich` | flag | off | Skip Stage E (contact enrichment via Firecrawl dorks) |
| `--no-resolve` | flag | off | Skip Stage D (SIRENE company resolution) |
| `--send` | flag | off | **Required to actually send email.** Without it the run behaves as `--dry-run` |
| `--db PATH` | str | env/config | Override SQLite DB path |
| `--max-per-board N` | int | 200 | Cap raw results fetched per board |

### Environment variables

| Variable | Purpose |
|----------|---------|
| `FIRECRAWL_API_KEY` | Firecrawl SDK auth — used by all Firecrawl-based scrapers and the LinkedIn dork enricher |
| `SERPER_API_KEY` | Serper.dev /jobs API key — used by `google_jobs_serper.py` |
| `FRANCE_TRAVAIL_CLIENT_ID` | OAuth2 client ID for France Travail REST API |
| `FRANCE_TRAVAIL_CLIENT_SECRET` | OAuth2 client secret for France Travail REST API |
| `INSEE_SIRENE_API_KEY` | Long-lived bearer token for INSEE SIRENE V3.11 (preferred auth path) |
| `GMAIL_SMTP_USER` | Gmail account address used as the SMTP login and From address |
| `GMAIL_SMTP_APP_PASSWORD` | 16-character Gmail App Password (no spaces). Generate at https://myaccount.google.com/apppasswords |
| `JOB_TRACKER_RECIPIENT` | Email address that receives the daily digest |
| `JOB_TRACKER_DB_PATH` | (Optional) Override SQLite DB path; defaults to config `default_db_path` |

### Config keys consumed from `config/job_tracker.json`

| Key | Value (current) | Purpose |
|-----|-----------------|---------|
| `boards` | array of board objects | Which boards to enable, their queries, and country filters |
| `title_keywords_include` | `["product manager","product owner","chef de produit",...]` | At least one must appear in the normalized title |
| `title_keywords_exclude` | `["junior","jr","stage",...]` | Any match rejects the job |
| `languages_allowed` | `["fr","en"]` | Job title+snippet must detect as one of these |
| `digest_window_days` | `7` | Jobs seen within this window appear in the digest |
| `contact_cache_days` | `60` | Skip re-enriching contacts for a company within this window |
| `sirene_naf_digital` | `["58.21Z","58.29A","58.29C",...]` | NAF codes considered "digital sector" |
| `smtp` | `{host, port, use_tls}` | SMTP connection settings (credentials come from env) |
| `db_path_env` | `"JOB_TRACKER_DB_PATH"` | Env var name that overrides the DB path |
| `default_db_path` | `".tmp/job_tracker.db"` | Fallback DB path when env var is unset |
| `tmp_dir` | `".tmp/job_tracker"` | Base directory for per-run intermediates |
| `recipient_email_env` | `"JOB_TRACKER_RECIPIENT"` | Env var name for recipient address |

## Outputs

| Output | Path | Notes |
|--------|------|-------|
| HTML digest | `.tmp/job_tracker/{run_id}/digest.html` | All active jobs within `digest_window_days` |
| Raw board results | `.tmp/job_tracker/{run_id}/raw_{board}.json` | One file per board scraped |
| Filtered candidates | `.tmp/job_tracker/{run_id}/candidates.json` | Jobs that passed all filters |
| Dropped jobs | `.tmp/job_tracker/{run_id}/dropped.json` | Rejected jobs with `filter_reason` |
| Contact files | `.tmp/job_tracker/{run_id}/contacts_{company_slug}.json` | One file per newly enriched company |
| Board count history | `.tmp/job_tracker/board_counts.json` | Rolling 14-entry history for degradation detection |
| SQLite DB | `.tmp/job_tracker.db` (default) | Tables: companies, jobs, contacts, notifications_log |
| Log file | `.tmp/job_tracker_pm_france.log` | Structured JSON events (NDJSON) |
| Email | To `JOB_TRACKER_RECIPIENT` | Only when `--send` is set and `--dry-run` is not |

## How to run

```bash
# Check-only dry run with mock data (no API calls, no email)
py execution\personal_workflows\job_tracker_pm_france.py --mock --dry-run

# Live run, France Travail only, no enrichment, no email
py execution\personal_workflows\job_tracker_pm_france.py --boards francetravail --no-enrich --dry-run

# Full live run with email
py execution\personal_workflows\job_tracker_pm_france.py --send

# Specific boards, higher cap, no company resolution
py execution\personal_workflows\job_tracker_pm_france.py --boards wttj,apec --max-per-board 100 --no-resolve --dry-run
```

## First-time setup (step-by-step)

1. **Validate environment:**
   ```bash
   py execution\personal_workflows\job_tracker_setup.py --check-only
   ```
   Note which env vars and packages are missing.

2. **Register accounts** (free tiers unless noted):
   - France Travail developer portal: https://francetravail.io — create an app to get `FRANCE_TRAVAIL_CLIENT_ID` + `FRANCE_TRAVAIL_CLIENT_SECRET`.
   - INSEE SIRENE: https://api.insee.fr — register and generate an API key for `INSEE_SIRENE_API_KEY`.
   - Firecrawl: https://firecrawl.dev — sign up; Standard plan ($83/mo) recommended for production volume.
   - Serper.dev: https://serper.dev — sign up; $50/mo plan covers ~2,500 searches/day.
   - Gmail App Password: https://myaccount.google.com/apppasswords — requires 2FA enabled on the account.

3. **Fill `.env`** with all 8 required env vars (see the Inputs section above).

4. **Install dependencies and initialize DB:**
   ```bash
   py execution\personal_workflows\job_tracker_setup.py --install-deps --init-db
   ```

5. **First dry run with mock data** — no API calls, verifies the pipeline wiring:
   ```bash
   py execution\personal_workflows\job_tracker_pm_france.py --mock --dry-run
   ```
   Open `.tmp/job_tracker/{run_id}/digest.html` in a browser to inspect the output.

6. **First live dry run** — single board, no enrichment, no email:
   ```bash
   py execution\personal_workflows\job_tracker_pm_france.py --boards francetravail --no-enrich --dry-run
   ```

7. **First full live send:**
   ```bash
   py execution\personal_workflows\job_tracker_pm_france.py --send
   ```

8. **Register the Modal cron** — the entry is already in `execution/webhooks.json` (key: `job_tracker_pm_france`). Follow `directives/add_webhook.md` to deploy:
   ```bash
   modal deploy execution/modal_webhook.py
   ```

## Schedule

- **Cron:** `0 6 * * *` (06:00 Europe/Paris, daily)
- **Runtime:** Modal serverless (`execution/modal_webhook.py`)
- **Timeout:** 900 seconds
- **Args passed by cron:** `["--send"]`
- **Idempotent within a day:** duplicate jobs are suppressed by `job_hash UNIQUE` constraint in SQLite. Running twice in a day is safe (second run upserts `last_seen_at` only).

See `directives/add_webhook.md` for the full Modal deployment procedure.

## Filtering rules

Rules are applied in `execution/custom_scrapers/job_filter.py`. The pipeline is: **exclude check → include check → language check**.

**Exclude patterns** (whole-word regex; first match wins; reject with labelled reason):

| Reject label | Tokens matched |
|-------------|----------------|
| `rejected:junior` | `junior`, `jr` |
| `rejected:stage` | `stage`, `stagiaire` |
| `rejected:alternance` | `alternance`, `alternant`, `alternante` |
| `rejected:apprenti` | `apprenti`, `apprentie`, `apprentissage` |
| `rejected:intern` | `intern`, `internship`, `trainee` |
| `rejected:assistant` | `assistant` |
| `rejected:graduate` | `graduate`, `entry-level`, `entry level` |

**Include keywords** (substring match on normalized title; at least one required):
`product manager`, `product owner`, `chef de produit`, `proprietaire de produit`, `propriétaire de produit`

**Language gate:** `langdetect` on `title + description_snippet[:400]`. Allowed: `fr`, `en`. Jobs with undetectable or other languages are rejected as `rejected:language`.

**Include keywords** are configured in `config/job_tracker.json` under `title_keywords_include` and can be extended without code changes. The exclude patterns in `job_filter.py` are compiled at module load from `_EXCLUDE_RULES` and use whole-word boundary regex.

## Cost

| Service | Plan | Monthly cost | Notes |
|---------|------|-------------|-------|
| Firecrawl | Standard | ~$83 | Recommended for 5 boards × daily runs. Hobby plan (~$29) may suffice if volume is low. |
| Serper.dev | Pro | ~$50 | Covers Google Jobs searches for all query/board combinations. |
| INSEE SIRENE | Free | $0 | API key required; no published rate limit but stay conservative. |
| France Travail API | Free | $0 | OAuth2 client_credentials; 150 results/request. |
| Gmail SMTP | Free | $0 | App Password; 500 recipient emails/day limit (irrelevant for self-email). |
| Modal cron | Free tier | $0 | One lightweight daily function well within free tier compute. |
| **Total** | | **~$133/mo** | Drop to ~$66/mo on Firecrawl Hobby if scrape volume allows. |

## Monthly operator checks

Run these once per month (add a calendar reminder):

1. **Check log for degraded boards:** Open `.tmp/job_tracker_pm_france.log`, filter for `"event": "degraded_boards_detected"`. If any board is firing repeatedly, inspect `raw_{board}.json` for that run and compare to expected HTML structure.
2. **Check Firecrawl dashboard:** https://firecrawl.dev/dashboard — confirm usage is within plan limits; adjust `max_per_board` in the cron args if needed.
3. **Check Serper dashboard:** https://serper.dev — confirm credit usage.
4. **Rotate Gmail App Password every 90 days:** Generate a new one at https://myaccount.google.com/apppasswords, update `GMAIL_SMTP_APP_PASSWORD` in `.env`.
5. **Audit digest quality:** Spot-check 5–10 jobs per digest for relevance. If false positives spike, tighten `title_keywords_include` in `config/job_tracker.json`.

## Failure modes

| Failure | Symptom | Immediate mitigation | Fix |
|---------|---------|---------------------|-----|
| Board HTML change | `BOARD_DEGRADED` event in log; board count drops <30% of 7-day median | Digest still sends with remaining boards; banner shows degraded board | Inspect `.tmp/job_tracker/{run_id}/raw_{board}.json`, update parser in `execution/custom_scrapers/{board}_jobs.py`, add Changelog entry |
| Firecrawl quota exhausted | `scraper_failed` or `page_fetch_error` events; board count → 0 | Boards fall back to empty list; digest still renders from DB | Upgrade Firecrawl plan or reduce `max_per_board`; check dashboard |
| Gmail SMTP fail | `send_done` event with `"status": "failed"` | Digest is still persisted to DB and HTML file | Check `GMAIL_SMTP_APP_PASSWORD`; regenerate if expired; verify 2FA still active |
| SIRENE 503 | `sirene_failed` warning in log; company fields → None | Pipeline continues; company shows without SIREN/NAF in digest | Transient — usually self-resolves next run. If persistent, check https://api.insee.fr status |
| langdetect misclassification | Valid FR/EN jobs rejected as `rejected:language`, or foreign-language jobs passing | Low impact — only affects edge cases | Short titles are most prone; adding `description_snippet` content improves accuracy. If a common pattern emerges, add it to `title_keywords_include` |
| Modal timeout | Run exceeds 900s timeout | Email not sent that day; DB state is consistent (all commits or none per stage) | Reduce `max_per_board`, disable enrichment in cron args (`--no-enrich`), or increase timeout in `webhooks.json` |

## Self-anneal hooks

When a board degrades:
1. The orchestrator **continues** — other boards still run.
2. A `BOARD_DEGRADED` event is logged; the digest renders a banner listing the degraded board(s).
3. **Operator fix loop:**
   a. Find the run's `raw_{board}.json` in `.tmp/job_tracker/{run_id}/`.
   b. Inspect the markdown (or API response) to understand what changed on the board's side.
   c. Update the parser in `execution/custom_scrapers/{board}_jobs.py`.
   d. Re-run with that board only: `py execution\personal_workflows\job_tracker_pm_france.py --boards {board} --dry-run`.
   e. Confirm counts recover to >30% of median.
   f. Add a `## Notes` entry in this directive's Changelog.
4. For API failures (401/429/5xx): check credentials and plan limits before touching code.

## Tools / dependencies

- Python packages: `firecrawl-py`, `langdetect`, `requests`, `python-dotenv`, `freezegun` (tests), `pytest` (tests)
- External services: Firecrawl API, Serper.dev /jobs, France Travail REST API, INSEE SIRENE V3.11, Gmail SMTP
- Runtime: Python 3.14; invoke as `py` on Windows
- Cron host: Modal (`modal deploy execution/modal_webhook.py`)
- DB: SQLite at `.tmp/job_tracker.db`

## Exit Criteria

The pipeline is considered fully operational when ALL of the following are true:

1. **Modal cron deployed** — `modal deploy execution/modal_webhook.py` exits 0 and the `job_tracker_pm_france` key appears in `execution/webhooks.json` with the correct args (`["--send"]`).
2. **All 8 env vars set** — `py execution\personal_workflows\job_tracker_setup.py --check-only` reports `[OK]` for: `FIRECRAWL_API_KEY`, `SERPER_API_KEY`, `FRANCE_TRAVAIL_CLIENT_ID`, `FRANCE_TRAVAIL_CLIENT_SECRET`, `INSEE_SIRENE_API_KEY`, `GMAIL_SMTP_USER`, `GMAIL_SMTP_APP_PASSWORD`, `JOB_TRACKER_RECIPIENT`.
3. **DB initialised** — `.tmp/job_tracker.db` exists and contains the four tables (`companies`, `jobs`, `contacts`, `notifications_log`); verified via `py execution\personal_workflows\job_tracker_setup.py --init-db` (idempotent).
4. **Mock dry-run clean** — `py execution\personal_workflows\job_tracker_pm_france.py --mock --dry-run` exits 0, produces `.tmp/job_tracker/{run_id}/digest.html`, and the log contains no `ERROR` events.
5. **Daily Sheet row appended** — after a live `--send` run, the SQLite `jobs` table has at least one row with `first_seen_at` = today (UTC), and `.tmp/job_tracker_pm_france.log` contains `"event": "send_done"` with `"status": "ok"`.
6. **No API errors in last 24 h** — `.tmp/job_tracker_pm_france.log` (last 24 h) contains zero `ERROR`-level events and no `BOARD_DEGRADED` events for all 5 boards simultaneously (partial degradation is acceptable).
7. **Digest renders** — `.tmp/job_tracker/{run_id}/digest.html` opens in a browser without blank body; at least one job card is visible when at least one board returns results.

## Changelog

- 2026-05-14: created.
