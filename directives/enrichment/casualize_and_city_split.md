# Casualize company names + split a lead CSV by city

**Script:** `execution/enrichment/casualize_and_city_split.py`

## Goal
Turn one scraped lead export (Apollo-style columns) into launch-ready per-city CSVs with two extra
columns for personalization. Run `email_mx_verify.py` (or `million_verifier.py` locally) on the file first so
`email_status` is carried into every output.

## Inputs
- `--input` CSV with `Email`, `Company Name`, `City`, `State`, `Company City`, `Company State`.
- `--outdir` output folder. `--model` (default `anthropic/claude-sonnet-5.5`, bulk tier). `--no-llm` skips the
  personalized-name call. `--batch` (40) and `--workers` (6) tune the fan-out.
- Env `OPENROUTER_API_KEY` (cloud alias `OPENROUTER_API_TOEKN` is picked up automatically).

## What it does
1. Dedupes by email (case-insensitive, first row wins).
2. `Short Company Name`: deterministic. Drops parentheticals, anything after ` | ` / ` - `, a leading "The",
   and trailing legal/corporate suffixes only (LLC, Inc, Ltd, Limited, Corp, Co, Group, Holdings, Technologies,
   International, Company, and/&…). Descriptive words (Staffing, Search, Consulting) are kept so the column is a
   safe formal reference.
3. `Personalized Name`: one friendly brand word/phrase ("Grayson Healthcare Recruitment and Staffing" → "Grayson").
   Sonnet via OpenRouter, batches of 40 unique names, JSON in / JSON out. **Hallucination guard:** every token of
   the nickname must occur in the original name (or be "you guys" for all-generic names); otherwise the row falls
   back to the short name. Batch failures also fall back. Counts are in `summary.json`.
4. Splits by the person `City`. Within a city, a row whose `Company City`/`Company State` lies outside that city's
   metro (lists in `METROS`) goes to `{city}__hq_outside_metro.csv`, so no city file contains another market's
   companies. Blank company location counts as consistent.

## Outputs
`{outdir}/{city_slug}.csv`, `{outdir}/{city_slug}__hq_outside_metro.csv`, `{outdir}/summary.json`
(row counts, per-file city set, `email_status` counts, guard fallbacks, failed batches).

## Edge cases / learnings
- Free-text fields (Headline, SEO description) can still mention other cities; only structured columns are checked.
- Add new suburbs to `METROS` when the `__hq_outside_metro` file shows same-metro cities (check its Company City
  counts after each run).
- Cloud sessions lack `openai` by default: `pip install openai` before running.

## Run log
- 2026-10-13 Bay Area recruitment list (1,900 rows → 1,895 after dedupe, 1,731 companies, cities SF / Seattle /
  San Diego). Sonnet, 44 batches, ~2 min.
