# Import Leads

## Purpose

Convert an arbitrary CSV of contacts into the internal lead format and optionally
upload them to an Instantly campaign. Handles column auto-detection, manual column
mapping overrides, email validation, first+last name concatenation, and multi-encoding
CSVs (UTF-8 BOM, Latin-1). The script is the entry point for any one-off or recurring
lead list that arrives as a CSV rather than through a scraper.

## When to invoke

- A client or vendor sends a CSV of contacts to load into the pipeline.
- A scraper produces a non-standard CSV that needs normalization before Instantly upload.
- Batch-importing contacts from a CRM export into the Accessory Masters campaign.
- Testing a new CSV format before wiring it into an automated pipeline.

## Inputs

| Input | Required | Default | Purpose |
|-------|----------|---------|---------|
| `--csv PATH` | Yes | — | Path to the input CSV file |
| `--mapping "k=V,..."` | No | auto-detect | Manual column mapping, e.g. `"email=Email Address,name=Contact Name,company=Biz Name"` |
| `--config PATH` | No | `config/accessory_masters.json` | Pipeline config (needed only for `--upload`) |
| `--output PATH` | No | `.tmp/imported_leads.json` | Output JSON path |
| `--upload` | No | off | Upload validated leads to Instantly campaign after import |
| `--mock` | No | off | Dry-run — no API calls; logs `MOCK: Would upload N leads` |

**Shorthand mapping keys:** `email` → `owner_email`, `name` → `owner_name`, `company` → `business_name`.

**Auto-detect logic:** if no `--mapping` is given, the script fuzzy-matches CSV headers against
known variants (see `AUTO_DETECT_MAP` in the script). First+last name columns are detected
separately and concatenated into `owner_name`.

**Env vars required (upload path only):**

| Variable | Purpose |
|----------|---------|
| `INSTANTLY_API_KEY` | Instantly API auth — required when `--upload` is set |

## Outputs

- `.tmp/imported_leads.json` — JSON array of validated lead records (or path from `--output`).
- Each record: `business_name`, `owner_name`, `owner_email`, `phone`, `industry`, `city`, `state`, `source="csv_import"`, `personalized_opener=""`.
- Stdout summary: total rows, imported count, skipped count, output path.
- Log warnings: one line per skipped row with reason (missing email, invalid format).
- **On `--upload`:** leads are posted to the Instantly campaign defined in `config.instantly.campaign_id`. Upload result logged as `N/M succeeded`.

## Steps

1. Read CSV with encoding fallback: try `utf-8-sig` → `utf-8` → `latin-1`. Raise `ValueError` if all fail.
2. Build column mapping: use `--mapping` if provided (via `parse_manual_mapping`); otherwise call `auto_detect_columns` against the CSV headers.
3. Warn if `owner_email` cannot be mapped — the pipeline will skip all rows.
4. For each row, call `_build_lead(row, col_map)` to produce a lead dict.
5. Validate each lead with `validate_lead`: skip rows with missing or malformed email (logged as warnings).
6. Save validated leads to output JSON via `save_leads`.
7. If `--upload`: load config → verify `instantly.campaign_id` is set → call `modules.outputs.instantly.upload_leads`. In `--mock` mode, log `MOCK: Would upload N leads` and skip the API call.
8. Print summary table.

## Exit Criteria

- Exit code 0. Output JSON file exists and is a valid JSON array.
- Every row with a valid email appears in the output; every skipped row has a logged warning with row number and reason.
- No row in the output has an empty or malformed `owner_email`.
- `source` field is `"csv_import"` on every record.
- `--upload` path: Instantly upload result logged with `N/M succeeded`; exit 0 even if M > N (partial success is logged, not fatal).
- `--mock` path: no API calls made; mock log line emitted.
- Encoding fallback: Latin-1 CSVs are read without crash.

## Edge cases

- **No email column detected:** script warns and continues; all rows will be skipped at validation. Use `--mapping email=<YourColumnName>` to fix.
- **First+last split:** if the CSV has `First Name` and `Last Name` but no combined name column, auto-detect merges them. If only `First Name` is present, `owner_name` = first name only.
- **Duplicate rows:** no dedup applied at import. Downstream dedup (by `dedup_key`) occurs in the scraper pipeline, not here.
- **`--upload` without `campaign_id`:** exits 1 with a clear error message pointing to the config key.
- **`INSTANTLY_API_KEY` missing:** exits 1 with a clear error; does not crash mid-upload.
- **AM lockdown:** `config/accessory_masters.json` is the default config path. The script itself is generic — it does not call AM-specific APIs directly. The `--upload` path reads `instantly.campaign_id` from config; ensure the config points to the correct non-AM campaign when used outside AM scope.

## Scripts (Layer 3)

- `execution/gtm_client_workflows/import_leads.py`
- Shared: `execution/modules/pipeline_utils.py` (`load_config`, `save_leads`, `setup_logging`)
- Shared: `execution/modules/outputs/instantly.py` (`upload_leads`) — upload path only

## Changelog

- 2026-06-12: Created — filling zero-coverage gap (batch 2B, INDEX row 46). Directive aligned with `import_leads.py` as of this date.
