# Job Search Sheet — Daily Multi-Portal Job Aggregator — Master SOP

## 1. Purpose

This pipeline runs daily at 09:00 Europe/Paris, scrapes free job boards (France Travail, Adzuna, Jooble) for six target titles across configured geographies, deduplicates the results across portals, gates them through an LLM relevance filter, and writes a clean, sorted Google Sheet called **"Job Applications"** — one tab per job title. The sheet is the single place Debanjan reviews new roles and tracks application status. No email digests. No notifications. Just a sheet that is always current when he opens it.

---

## 2. End-User Expectation

Debanjan opens **"Job Applications"** in Google Drive each morning. He sees six tabs: PM, AI PM, AI Automation, AI Mobile, AI Process, AI Consultant. Each tab shows roles sorted newest-first. Column A (`_id`) is hidden. He reads the Title, Company, Location, Remote?, Contract, Source, and Link. He sets `Status` from the dropdown (New / Applied / Saved / Skip / Interview / Rejected) and optionally adds free-text `Notes`. He can also add his own rows anywhere in a tab — they are preserved across daily runs as long as column A stays empty. His `Status` and `Notes` edits on existing rows are also preserved across every run.

**The pipeline writes to the sheet; Debanjan reads and annotates. That is the full interaction model.**

---

## 3. Schedule

| Setting | Value |
|---|---|
| Display time | 09:00 Europe/Paris (daily) |
| GitHub Actions cron #1 (summer — CEST, UTC+2) | `0 7 * * *` |
| GitHub Actions cron #2 (winter — CET, UTC+1) | `0 8 * * *` |
| Idempotency window | 23 hours (checked against `_meta!A1`) |
| Concurrency group | `job-search-daily` (cancel-in-progress: false) |

The dual-cron + 23h idempotency pattern handles DST transitions automatically. If the 07:00 UTC run is still in flight when 08:00 UTC fires, the 08:00 run waits, then reads the fresh `_meta!A1` timestamp and exits cleanly (already ran today).

---

## 4. Phase Status

| Phase | Geos active | Status |
|---|---|---|
| **1a** | France (FR) only | Build & validate first |
| **1b** | Schengen (DE, NL, ES, IT, BE, AT, PL, PT) + Canada + USA (freelance/contract only) | After 3+ successful 1a daily runs |
| 2 | Remote RSS sources (Remotive, Arbeitnow, etc.) | Only if Phase 1 coverage is insufficient |
| 3 | Modal cron migration, /health endpoint | Only if GH Actions reliability becomes an issue |

**CA and US are freelance/contract roles only.** The `contract_filter` field in `config/job_search.json` enforces this. All Schengen geos have no contract filter (all contract types accepted).

---

## 5. Architecture (3-Layer)

### Layer 1 — Directive (this file)
SOP for the pipeline. Human-readable intent. Lives at `directives/personal_workflows/job_search_sheet.md`.

### Layer 2 — Orchestration
Claude reads this directive and calls the execution scripts in the correct order, handles errors, and updates directives with learnings.

### Layer 3 — Execution (Python scripts)

| Script | Status | Role |
|---|---|---|
| `execution/personal_workflows/job_search_sheet.py` | Batch 1d (not built yet) | Main orchestrator: stages 0-6 |
| `execution/personal_workflows/job_search_setup.py` | Batch 1b (this batch) | Phase 0 validator + bootstrap |
| `execution/google/google_sheets_writer.py` | Batch 1a (shipped) | Sheets auth, read/write, _meta tab |
| `execution/custom_scrapers/adzuna_jobs.py` | Batch 1c (not built yet) | Adzuna free-tier scraper |
| `execution/custom_scrapers/jooble_jobs.py` | Batch 1c (not built yet) | Jooble free-tier scraper |
| `execution/custom_scrapers/france_travail_jobs.py` | Reused as-is | France Travail official API scraper |
| `execution/custom_scrapers/job_filter.py` | Reused as-is (config-only extension) | Keyword + language filter |
| `execution/personal_workflows/job_search_llm_gate.py` | Batch 1d (not built yet) | Claude Haiku primary + Gemini Flash failover |
| `config/job_search.json` | Batch 1b (this batch) | Single source of truth: titles, geos, filter, LLM gate config |

---

## 6. Pipeline DAG

```
[GitHub Actions cron -- 07:00 UTC AND 08:00 UTC; concurrency: group: job-search-daily]
        |
[Stage 0: Bootstrap + idempotency]
  - ensure_workbook_initialized() -- create _meta + 6 visible tabs if absent, write headers row 1, hide col A
  - read _meta!A1 -> last_run_at (ISO). If empty / unparseable -> treat as epoch zero (proceed)
  - if (now - last_run_at) < 23h: exit 0 ("already ran today")
        |
[Stage 1: Discover (free sources only)]
  Phase 1a sources: france_travail, adzuna (gl=fr), jooble (gl=fr)
  Phase 1b adds: adzuna + jooble for DE, NL, ES, IT, BE, AT, PL, PT (no contract filter)
                 adzuna + jooble for CA, US (contract_type in {contract, freelance} filter)
  For each (title, geo) in config:
    for each source applicable to geo:
      raw_jobs += source.scrape(queries=[title_synonyms], country=geo, contract_filter=...)
  Per-source try/except; on failure log + continue
        |
[Stage 2: Normalize + keyword-filter]
  use existing job_filter.filter_jobs with expanded config:
    - title_keywords_include: 6 titles x 3 synonyms ~18 phrases
    - exclude: junior/stage/intern/alternance/apprenti/graduate/assistant (existing)
    - language: ["fr", "en"]
    - For US/CA-bucket jobs: drop unless contract_type in {contract, freelance, unknown-but-keyword-match}
        |
[Stage 2.5: LLM relevance gate (Phase 1 -- uses Anthropic Max-plan credits)]
  cap: max 200 jobs/run sent to gate
  for each candidate job:
    classify via Claude Haiku 4.5 (primary) -- if 429/5xx after 2 retries, failover to Gemini 2.0 Flash
    -> {relevance: relevant|borderline|irrelevant, contract_type: ...}
  relevant + borderline -> continue to dedup
  irrelevant -> tag for Archive range (still written, just not in main band)
        |
[Stage 3: Dedup]
  hash = compute_job_hash(normalize_company, normalize_title, location)   # SHA-1
  first-seen wins across all (title, geo, source)
  collision Jaccard-trigram check on description_snippet[:200]:
    < 0.4 -> keep both (different roles)
    >= 0.4 -> append source board to also_seen_on (within current run)
        |
[Stage 4: Read existing sheet -> carry-forward map + preserved user rows]
  for each title tab:
    for each row: if col-A non-empty -> index into {hash: (status, notes, also_seen_on)}
                  if col-A empty -> preserve full row in user_added_rows[title]
        |
[Stage 5: Materialize each title tab]
  filter jobs assignable to this title (a job can match multiple titles via synonym overlap)
  sort by first_seen_at desc
  for each computed row:
    also_seen_on = sorted(set(carried_forward) | set(current_run))   # cross-run merge
    preserve carried-forward status + notes
  batch write: row 1 = header, rows 2..N = computed, rows N+1..M = user_added_rows
  single values().update() per tab
  follow-up batch_update: re-hide col A
        |
[Stage 6: Update _meta + log + exit]
  values().update(range='_meta!A1', body=now_iso)
  append run summary line to .tmp/job_search_runs.jsonl
  print counts: discovered / filtered / deduped / written per tab
```

---

## 7. Sheet Schema

- **Workbook name:** `Job Applications`
- **Visible tabs (6):** `PM`, `AI PM`, `AI Automation`, `AI Mobile`, `AI Process`, `AI Consultant`
- **Hidden tab:** `_meta` (cell A1 = ISO `last_run_at`). Tab is hidden.

| Col | Name | Notes |
|---|---|---|
| A | `_id` | SHA-1 dedup hash. Hidden via `hide_columns`. **Do NOT edit.** |
| B | `First Seen` | ISO date, sort key |
| C | `Posted` | ISO date from source API |
| D | `Company` | Raw company name |
| E | `Title` | Raw job title |
| F | `Country` | ISO 2-letter geo code (FR, DE, etc.) |
| G | `Location` | City or region from source |
| H | `Remote?` | `Yes` / `No` / `Hybrid` / `Unknown` |
| I | `Contract` | `CDI` / `CDD` / `Freelance` / `Contract` / `Permanent` / `Unknown` |
| J | `Source` | Board name (adzuna, jooble, france_travail) |
| K | `Also Seen On` | Comma-separated list of other boards where same role appeared |
| L | `Link` | Apply URL |
| M | `Status` | Dropdown: `New` / `Applied` / `Saved` / `Skip` / `Interview` / `Rejected` |
| N | `Notes` | Free text |

Row 1 is frozen. No data in row 1 except column headers.

---

## 8. Sources and Geos

| Geo | Phase | Free Sources | Contract Filter |
|---|---|---|---|
| France (FR) | 1a | France Travail API + Adzuna-FR + Jooble-FR | All contracts |
| Germany (DE) | 1b | Adzuna-DE + Jooble-DE | All contracts |
| Netherlands (NL) | 1b | Adzuna-NL + Jooble-NL | All contracts |
| Spain (ES) | 1b | Adzuna-ES + Jooble-ES | All contracts |
| Italy (IT) | 1b | Adzuna-IT + Jooble-IT | All contracts |
| Belgium (BE) | 1b | Adzuna-BE + Jooble-BE | All contracts |
| Austria (AT) | 1b | Adzuna-AT + Jooble-AT | All contracts |
| Poland (PL) | 1b | Adzuna-PL + Jooble-PL | All contracts |
| Portugal (PT) | 1b | Adzuna-PT + Jooble-PT | All contracts |
| Canada (CA) | 1b | Adzuna-CA + Jooble-CA | **contract / freelance only** |
| USA (US) | 1b | Adzuna-US + Jooble-US | **contract / freelance only** |

LinkedIn is not scraped directly (career-grade ban risk). LinkedIn-listed jobs appear via Adzuna/Jooble aggregation.

---

## 9. Dedup and Cross-Source Merge Logic

**Dedup key:** `SHA1(normalize_company + "|" + normalize_title + "|" + lower(location))`

Uses the existing `compute_job_hash` function from `execution/personal_workflows/_jt_utils.py:154`.

**First-seen wins.** A job seen on multiple boards on the same run merges into one row. Its `Also Seen On` column accumulates all boards where it appeared — both within the current run and across prior runs (carried forward from the existing sheet).

**Jaccard collision guard:** If two jobs would merge (same dedup key) but their `source_url` differs AND their `description_snippet[:200]` Jaccard-trigram similarity is `< 0.4`, they are treated as different roles and both are kept. This prevents mis-merging two different roles at the same company (e.g. "Senior AI PM" and "AI PM — Platform").

---

## 10. LLM Relevance Gate

Runs at Stage 2.5, after keyword filter, before dedup. Caps at **200 jobs/run** to bound wall-clock time and token spend.

**Primary:** Claude Haiku 4.5 (user's Anthropic Max plan — zero incremental cost).
**Failover:** Gemini 2.0 Flash (user's Gemini paid plan — zero incremental cost). Triggers after 2 failed retries on 429 or 5xx from Haiku.

Each job gets one classification call:
```
{relevance: "relevant" | "borderline" | "irrelevant", contract_type: "CDI" | "CDD" | "Freelance" | "Contract" | "Permanent" | "Unknown"}
```

- `relevant` + `borderline` continue to dedup and sheet write.
- `irrelevant` rows are tagged; in Phase 2 they will be written to an Archive range (not deleted, recoverable). In Phase 1 they are dropped after logging.

**Estimated cost (informational):** ~5,400 jobs/month through gate × ~450 tokens = ~2.4M tokens/month. Well within Anthropic Max plan included credits.

---

## 11. Failure Modes

| # | Failure | Phase-1 response |
|---|---|---|
| a | Adzuna 250/day quota exhausted mid-run | Log `adzuna_quota_exhausted=true`, skip remaining Adzuna calls, continue with other sources |
| b | Jooble key revoked | Per-source try/except; sheet still updates from France Travail + Adzuna |
| c | Google Sheets API 429 (300 reads/min limit) | Exponential backoff via `tenacity`, max 3 retries |
| d | User edits sheet during write | Documented caveat (see Section 12); ~10-second write window |
| e | DST transition | Dual-cron + 23h idempotency check handles it |
| f | Sheet ID changes (user re-creates sheet) | `--check-only` validates ID via live API call |
| g | Service-account creds expired or revoked | `--check-only` calls `spreadsheets().get()`; 401/403 surfaces immediately |
| h | LLM gate falsely rejects a high-value role | Irrelevant rows logged to `.tmp/job_search_runs.jsonl`; recoverable |
| i | Two different roles at same company mis-merged | Jaccard-trigram check on snippets prevents this (threshold 0.4) |
| j | Free API changes terms / shuts down | Per-source try/except; sheet still updates from remaining sources |
| k | User accidentally clears col A on a script row | Row becomes "user-added" -> survives + new fetch also writes same job -> duplicate. Mitigation: see Section 12 caveats. |
| l | First-run empty `_meta!A1` | Stage 0 treats empty/unparseable as epoch-zero and proceeds |

---

## 12. IMPORTANT — User Caveats

> **Read before using the sheet.**

### Do NOT edit column A
Column A (hidden, labeled `_id`) holds the internal dedup hash for each row. If you clear it, the pipeline treats that row as a user-added row. On the next run, the same job is re-fetched and written as a new row — creating a duplicate. Unhide col A to inspect it; do not clear it.

### Do NOT edit the `_meta` tab
The `_meta` tab is hidden. It stores the last-run timestamp in cell A1. Clearing it forces the pipeline to treat the next run as the first-ever run, re-fetching all jobs. Do not unhide or edit this tab.

### Avoid editing the sheet between 09:00 and 09:15 Europe/Paris
That is the write window. The pipeline reads the sheet, computes the new state, and writes back in a single batch. Edits you make during this ~10-second window may be overwritten. Edit before 09:00 or after 09:15.

### User-added rows are safe
Rows you add manually (leaving column A empty) are preserved across all runs. They appear below the pipeline-generated rows in each tab.

### Status and Notes are safe
Your `Status` dropdown value and `Notes` text are preserved per-row across every run, as long as column A (`_id`) for that row is intact.

---

## 13. Setup Checklist (Phase 0 — User Actions, ~30 minutes)

Complete these before running any pipeline scripts.

1. **Google Cloud project:** Create or reuse a personal GCP project (not org-managed). Enable Sheets API + Drive API.
2. **Service account:** Create a service account -> download JSON key -> save to `credentials/service_account.json` (gitignored).
3. **Create the spreadsheet:** Create an empty Google Sheet titled `Job Applications` on your Drive. Share it with the service account email (Editor role). No need to pre-create tabs — the script creates them.
4. **Add spreadsheet ID to .env:** Copy the spreadsheet ID from the URL (the long alphanumeric string). Add to `.env`:
   ```
   SHEETS_SPREADSHEET_ID=<your_spreadsheet_id>
   GOOGLE_SERVICE_ACCOUNT_PATH=credentials/service_account.json
   ```
5. **Register Adzuna app:** Sign up at `https://developer.adzuna.com/signup` (free, no card). Get `app_id` + `app_key`. Add to `.env`:
   ```
   ADZUNA_APP_ID=<your_app_id>
   ADZUNA_APP_KEY=<your_app_key>
   ```
6. **Register Jooble API key:** Fill the form at `https://jooble.org/api/about`. Add to `.env`:
   ```
   JOOBLE_API_KEY=<your_api_key>
   ```
7. **France Travail credentials:** Register at `https://francetravail.io`. Fill the existing empty placeholders in `.env`:
   ```
   FRANCE_TRAVAIL_CLIENT_ID=<your_client_id>
   FRANCE_TRAVAIL_CLIENT_SECRET=<your_client_secret>
   ```
8. **Verify ANTHROPIC_API_KEY and GEMINI_API_KEY** are already present in `.env` (they should be from prior projects).
9. **Install Python deps:** `py -m pip install gspread tenacity` (or `py -m pip install -r requirements.txt`).
10. **GitHub Actions secrets:** Add these 8 secrets to the repo Settings -> Secrets -> Actions:
    - `SHEETS_SPREADSHEET_ID`
    - `GOOGLE_SERVICE_ACCOUNT_JSON_B64` (base64-encode the JSON file: `base64 credentials/service_account.json`)
    - `ADZUNA_APP_ID`
    - `ADZUNA_APP_KEY`
    - `JOOBLE_API_KEY`
    - `FRANCE_TRAVAIL_CLIENT_ID`
    - `FRANCE_TRAVAIL_CLIENT_SECRET`
    - `ANTHROPIC_API_KEY` (if not already present)
    - `GEMINI_API_KEY` (if not already present)

---

## 14. CLI Commands

### Phase 0 — Validate provisioning
```bash
# Check all env vars + live Sheets API (read-only, no sheet writes)
py execution/personal_workflows/job_search_setup.py --check-only

# Validate + create tabs (idempotent — safe to re-run)
py execution/personal_workflows/job_search_setup.py --bootstrap

# With extra detail per check
py execution/personal_workflows/job_search_setup.py --bootstrap --verbose
```

### Phase 1 — Run the pipeline (batch 1d — not built yet)
```bash
# Dry run with mock fixtures (no API calls, no sheet writes)
py execution/personal_workflows/job_search_sheet.py --mock --dry-run

# Live partial run: one title, one geo
py execution/personal_workflows/job_search_sheet.py --title "Product Manager" --geo FR

# Full run (all titles, all active-phase geos)
py execution/personal_workflows/job_search_sheet.py
```

---

## 15. Operational Runbook

### "Sheet hasn't updated today"
1. Check GitHub Actions -> runs for today. Did the workflow trigger?
2. Did it fail? Read the error log. Common causes: API key expired, Sheets quota, network timeout.
3. Check `_meta!A1` — does it show today's date? If yes, the pipeline ran but may have written zero rows (all filtered).
4. Check `.tmp/job_search_runs.jsonl` for the last run summary (discovered / filtered / written counts).
5. Run `py execution/personal_workflows/job_search_setup.py --check-only` locally to validate credentials.

### "Same job appears twice in a tab"
- Most likely cause: column A was cleared for one of the duplicate rows (making it a "user-added" row), then the pipeline wrote the same job again as a fresh row.
- Fix: Unhide column A. Find the row missing its `_id` hash. Either delete that row, or copy the hash from the duplicate row into it, then delete the duplicate.

### "All rows in a tab disappeared"
- Rare. Possible causes: pipeline bug writing zero rows; sheet cleared manually.
- Recovery: check `.tmp/job_search_runs.jsonl` for the last run's output. Check git history for any `.tmp/` run artifacts. Re-run `py execution/personal_workflows/job_search_sheet.py` — it will re-fetch and repopulate (Status/Notes for rows that were in the old carry-forward map are lost if col-A data is gone).

### "LLM gate is filtering out roles I want"
- Check `.tmp/job_search_runs.jsonl` for the run — it logs `irrelevant` verdicts with job titles.
- Adjust the system prompt in `execution/personal_workflows/job_search_llm_gate.py` (batch 1d).

### "Adzuna returning zero results"
- Check the Adzuna developer dashboard for quota usage (250 req/day free tier).
- Verify `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` are correct and not expired.
- Test directly: `py execution/custom_scrapers/adzuna_jobs.py --title "product manager" --geo FR --limit 5`.

### "France Travail returning 401"
- The France Travail OAuth token may have expired. Re-run the OAuth flow:
  `py execution/custom_scrapers/france_travail_jobs.py --refresh-token`
- If that fails, re-register at `https://francetravail.io`.
