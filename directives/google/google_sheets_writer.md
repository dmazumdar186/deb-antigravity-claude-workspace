# Google Sheets Writer — Job Search Pipeline SOP

## Prior art pass

Retrospective per `~/.claude/rules/prior-art-first.md`. This directive pre-dates the rule (2026-06-18):

- **Public API exists?** Yes -- Google Sheets API v4 (`sheets.googleapis.com`). Service-account auth via `credentials.json` / `token.json` is already wired into the workspace (existing files in `.gitignore`).
- **Existing GitHub prior art**: `gspread` Python library is the de-facto wrapper around Sheets API v4; well-maintained, used by the workspace's other Google-integration scripts.
- **Why this path**: official API, service-account auth (no OAuth flow per run), `gspread` handles auth + retries + batch updates. No screen-scraping, no headless browser.
- **Architecture**: `execution/google/google_sheets_writer.py` opens a sheet by ID, formats jobs per-tab, applies named ranges + conditional formatting via batched calls (cheaper than per-cell writes).

## Goal

Write daily job-search results from multiple aggregator APIs into a shared Google Sheet
(`Job Applications`) using a service account. One tab per target job title. The module
owns workbook bootstrapping, status/notes preservation across runs, hidden-column
deduplication, and cron-idempotency via a hidden `_meta` tab.

## Required env vars

| Variable | Purpose |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_PATH` | Path to the service account JSON key file (relative to project root or absolute). Default: `credentials/service_account.json`. |
| `SHEETS_SPREADSHEET_ID` | The 44-character ID from the spreadsheet URL: `https://docs.google.com/spreadsheets/d/<ID>/edit`. |

## Required OAuth scope

The service account must have the following scope granted:

```
https://www.googleapis.com/auth/spreadsheets
```

gspread's `service_account()` helper requests this scope automatically. If your GCP project has
a narrow org policy that restricts scopes, add `https://www.googleapis.com/auth/drive` as well
(needed to list/create sheets if Drive API is used alongside Sheets).

## Service-account setup (one-time, Phase 0)

1. **Create or reuse a GCP project.** Use a personal project — not org-managed — to avoid
   mandatory key rotation policies.
2. **Enable APIs.** In the GCP console → APIs & Services → Enable APIs → enable both:
   - Google Sheets API
   - Google Drive API
3. **Create a service account.** IAM & Admin → Service Accounts → Create.
   Name it something memorable (e.g. `job-search-sheet-writer`). No roles needed at the project
   level — sharing the sheet directly (step 5) is enough.
4. **Download the JSON key.** Service Accounts → your account → Keys → Add key → JSON.
   Save to `credentials/service_account.json` (gitignored via `credentials/` in `.gitignore`).
   Set `GOOGLE_SERVICE_ACCOUNT_PATH=credentials/service_account.json` in `.env`.
5. **Share the sheet.** Open the `Job Applications` spreadsheet → Share → paste the
   service account email (looks like `name@project.iam.gserviceaccount.com`) → set to **Editor**.
   Without this share, the writer receives a 403 and cannot read or write.
6. **Copy the spreadsheet ID.** From the URL bar:
   `https://docs.google.com/spreadsheets/d/<COPY-THIS-ID>/edit`.
   Add to `.env`: `SHEETS_SPREADSHEET_ID=<id>`.
7. **Smoke-test the connection.** Run:
   ```
   py execution\google\google_sheets_writer.py
   ```
   Expected output: `[OK] Opened 'Job Applications' — N tab(s)` (or `[--MISSING]` if the
   env var is unset).

## Sheet schema

The workbook is named `Job Applications`. It has **6 visible tabs** (one per target title)
and **1 hidden tab** (`_meta`).

### Visible-tab columns (14 total)

| Col | Header | Notes |
|---|---|---|
| A | `_id` | SHA-1 dedup hash — **hidden** via `hide_columns`. Do not edit manually. |
| B | `First Seen` | UTC ISO timestamp of first discovery across all sources. Sort key (newest-first). |
| C | `Posted` | Job posting date as returned by the source API. May be approximate or `Unknown`. |
| D | `Company` | Normalized company name. |
| E | `Title` | Job title as posted. |
| F | `Country` | Two-letter ISO country code (e.g. `FR`, `DE`, `CA`). |
| G | `Location` | City / region as returned by source. |
| H | `Remote?` | One of: `Yes`, `No`, `Hybrid`, `Unknown`. |
| I | `Contract` | One of: `CDI`, `CDD`, `Freelance`, `Contract`, `Permanent`, `Unknown`. |
| J | `Source` | Originating job board name (e.g. `france_travail`, `adzuna`, `jooble`). |
| K | `Also Seen On` | Comma-separated list of other boards that listed the same role (cross-run accumulation). |
| L | `Link` | Direct application URL. |
| M | `Status` | Dropdown: `New` / `Applied` / `Saved` / `Skip` / `Interview` / `Rejected`. |
| N | `Notes` | Free text. User-editable. Preserved across daily runs. |

Row 1 is the frozen header row. No data is written to row 1 except the column headers.

### Hidden tab: `_meta`

- Tab is hidden via a `updateSheetProperties` batch request (`hidden: true`).
- Cell `A1` holds the ISO 8601 UTC timestamp of the last successful pipeline run
  (written in Stage 6 after all tabs are updated).
- The orchestrator reads `_meta!A1` at Stage 0 — if less than 23 hours ago, it exits cleanly
  (idempotency guard against dual-cron double-writes on DST transition days).
- **Do not edit `_meta` manually.** An accidental clear of A1 is safe — the orchestrator
  treats empty/unparseable as epoch-zero (i.e., "never ran") and proceeds.

## Hidden column A

Column A (`_id`) stores the SHA-1 dedup hash computed from
`SHA1(normalize_company + "|" + normalize_title + "|" + lower(location))`.

It is hidden from the visible grid via a `updateDimensionProperties` batch request
(`hiddenByUser: true`) applied after every `write_tab` call.

**Do not edit column A manually.** If you accidentally clear a value in column A, that row
becomes indistinguishable from a user-added row (see below) and will be preserved as-is at the
bottom of the tab. The pipeline will also write a fresh copy of the same job above it, creating
a visual duplicate. Fix: manually delete the orphaned row.

## Status and Notes preservation across daily runs

The pipeline preserves user edits in the `Status` (M) and `Notes` (N) columns across daily
overwrites:

1. **`read_tab`** is called before writing. For every row where column A is non-empty, it
   indexes `{dedup_hash: {status, notes, also_seen_on}}` into a `carry_forward_map`.
2. **`write_tab`** applies the carry-forward map to the newly computed rows:
   if the same hash exists in `carry_forward_map`, the saved `status` and `notes` values
   are written back into the new row's M and N columns. The user's edits survive the overwrite.
3. `Also Seen On` (column K) is merged across runs:
   `sorted(set(carried_forward_also_seen_on) | set(current_run_also_seen_on))`.

## User-added rows

Rows where column A is empty are treated as user-added rows (manually typed into the sheet).
These rows are **not deduplicated** and **not overwritten** by the pipeline. They are
appended as-is below the computed rows on every run.

Write order per tab:
```
Row 1:       column headers (frozen)
Rows 2..N:   computed rows (sorted by First Seen, newest-first)
Rows N+1..M: user-added rows (order-preserved from the previous read)
```

## Tools / scripts

- `execution/google/google_sheets_writer.py` — the gspread wrapper module.
- Called by `execution/personal_workflows/job_search_sheet.py` (orchestrator).
- Can be run standalone as a connection smoke-test:
  ```
  py execution\google\google_sheets_writer.py [--spreadsheet-id <ID>]
  ```

## Steps

1. **Authenticate.** `get_client()` loads `GOOGLE_SERVICE_ACCOUNT_PATH` from env, opens the JSON key, and returns a `gspread.Client`. Raises `FileNotFoundError` if key is missing; `403` if the service account is not an Editor on the sheet.
2. **Open workbook.** `open_spreadsheet(client, spreadsheet_id)` opens the `Job Applications` workbook by ID. Raises if the ID is wrong or the account lacks access.
3. **Bootstrap tabs.** For each target job title, call `ensure_tab(spreadsheet, title)` — creates the tab if it does not exist and writes the frozen header row (14 columns, row 1).
4. **Bootstrap `_meta` tab.** Create if absent; hide via `updateSheetProperties`. Do not write data here in this step.
5. **Read existing data.** For each tab, call `read_tab(worksheet)` to build the `carry_forward_map` (`{dedup_hash: {status, notes, also_seen_on}}`).
6. **Write new data.** Call `write_tab(worksheet, rows, carry_forward_map)` for each tab:
   - Apply carry-forward to preserve user `Status`/`Notes` edits.
   - Merge `Also Seen On` across runs.
   - `worksheet.clear()` then `worksheet.update()` with the new matrix.
   - Hide column A (`_id`) via `updateDimensionProperties`.
7. **Update `_meta!A1`.** Write the current UTC ISO 8601 timestamp as the last-success marker.
8. **Log.** Emit one log line per tab: rows written, rows carried forward, user-added rows preserved.

## Exit Criteria

- Exit code 0. All target tabs exist in the workbook and contain the correct 14-column header row.
- `_meta!A1` holds a fresh UTC ISO 8601 timestamp (within the last 60 seconds of run completion).
- Each tab's row count = (computed rows) + (user-added rows). No rows lost.
- `Status` and `Notes` values from the previous run are preserved for any row whose `_id` hash appears in both the old and new data.
- `Also Seen On` column is a superset of all previous runs — no source drops out of the history.
- Column A (`_id`) is hidden in every data tab.
- No `403` or `429` errors propagate to the caller; tenacity retries resolve within the run.
- Smoke-test command `py execution\google\google_sheets_writer.py` prints `[OK] Opened 'Job Applications' — N tab(s)` (or `[--MISSING]` per missing env var) and exits 0.

## Edge cases & gotchas

- **Service-account sharing is required.** The Sheets API returns a 403 (`insufficientPermissions`)
  if the service account email is not an Editor on the sheet. The smoke-test surfaces this
  immediately.
- **Tenacity retries on 429 / 5xx.** All public write functions are wrapped with
  `@_retry_on_api_error` (3 attempts, exponential back-off 2–30 s). The Sheets API free quota
  is 300 read/write requests per minute; the pipeline stays well below this with one batch write
  per tab.
- **`worksheet.clear()` before `update`.** Each `write_tab` call clears the sheet before
  writing the new matrix. This removes stale rows that no longer appear in the computed set.
  Any unsaved local edits to cells (other than Status/Notes, which are preserved via
  `carry_forward_map`) will be lost during the ~10-second write window.
- **Editing during the write window.** Avoid editing the sheet between **09:00 and 09:15 Paris
  time** (07:00–07:15 UTC summer, 08:00–08:15 UTC winter). Edits in that window may be
  overwritten by `worksheet.clear()`.
- **Key file not found.** If `credentials/service_account.json` doesn't exist, `get_client()`
  raises `FileNotFoundError` with a message pointing to the download step.
- **Column A accidentally cleared.** See "Do not edit column A manually" above.
- **Key rotation.** GCP org-policy projects may enforce 90-day key rotation. Use a personal
  project to avoid this. If rotation is required: generate a new key → update
  `credentials/service_account.json` locally → update the `GOOGLE_SERVICE_ACCOUNT_JSON_B64`
  GitHub Actions secret → verify with the smoke-test.

## Changelog

- 2026-06-09: created (Batch 1a, Phase 1a build).
