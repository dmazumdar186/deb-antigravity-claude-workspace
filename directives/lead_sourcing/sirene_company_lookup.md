# INSEE SIRENE Company Lookup SOP

## Goal

Resolve a French company name to an INSEE SIRENE V3.11 record and confirm whether the company operates in the digital sector by checking its NAF (Nomenclature des Activités Françaises) activity code. Used by the job tracker orchestrator (Stage D) to validate that companies posting PM/PO roles are in the digital-sector target segment. Also useful as a standalone enrichment step for any other pipeline that needs official French company identity data.

## When to use

- Called automatically by the orchestrator at Stage D for each distinct company in `new_candidates`.
- Skipped when `--no-resolve` is passed to the orchestrator.
- Run standalone to verify a specific company name against SIRENE or to test API credentials.
- Called as part of any workflow that needs SIREN number, NAF code, or digital-sector classification for French companies.

## Inputs

### CLI args

| Flag | Required | Default | Purpose |
|------|----------|---------|---------|
| `--name COMPANY_NAME` | Yes (repeatable) | — | Company name to look up. Repeat for batch lookup. |
| `--output PATH` | No | stdout only | Optional path to write results as JSON |

### Environment variables required

Two auth paths are supported. Use the first (long-lived bearer token) whenever possible — it avoids the OAuth2 token fetch on every run.

| Variable | Purpose | Auth path |
|----------|---------|-----------|
| `INSEE_SIRENE_API_KEY` | Long-lived bearer token from https://api.insee.fr — preferred | Primary |
| `INSEE_SIRENE_CLIENT_ID` | OAuth2 client ID — fallback if no static key | Secondary |
| `INSEE_SIRENE_CLIENT_SECRET` | OAuth2 client secret — fallback if no static key | Secondary |

Auth priority: if `INSEE_SIRENE_API_KEY` is present and non-empty, it is used directly as a Bearer token. Otherwise the script attempts an OAuth2 `client_credentials` flow using `CLIENT_ID` + `CLIENT_SECRET`. If neither is configured, `lookup_company()` returns an all-null result with `source='unconfigured'` — the pipeline continues without failing.

### Config keys consumed from `config/job_tracker.json`

- `sirene_naf_digital` — list of NAF codes considered digital sector. Current list: `58.21Z`, `58.29A`, `58.29C`, `62.01Z`, `62.02A`, `62.02B`, `62.03Z`, `62.09Z`, `63.11Z`, `63.12Z`. Add codes here to broaden or narrow the classification without touching code.

## Outputs

- **Return value from `lookup_company()`:**
  ```json
  {
    "siren": "123456789",
    "naf_code": "62.01Z",
    "is_digital_sector": 1,
    "website": null,
    "matched_denomination": "Acme SAS",
    "source": "sirene"
  }
  ```
  `is_digital_sector` is `1` (yes), `0` (no), or `null` (NAF code unknown). `website` is always `null` — SIRENE V3.11 does not reliably expose websites; enrich this downstream with a Firecrawl dork or Clearbit if needed.

- **Return value from `lookup_companies()` (batch):**
  ```json
  {"Acme SAS": {...}, "BlaBlaCar": {...}}
  ```

- **`source` field values:**
  | Value | Meaning |
  |-------|---------|
  | `"sirene"` | API was queried (even if no match found — check `siren` for null) |
  | `"unconfigured"` | No auth env vars set |
  | `"error"` | Auth configured but a network/HTTP error prevented lookup |

- **Logs:** warnings for 401/403/404, request failures, and name-match fallback attempts.
- **stdout (CLI):** JSON with `run_at` and `results` dict.
- **File (CLI `--output`):** Same JSON written to disk.

## How to run

```bash
# Single company lookup
py execution\lead_sourcing\sirene_company_lookup.py --name "BlaBlaCar"

# Batch lookup with output file
py execution\lead_sourcing\sirene_company_lookup.py --name "Qonto" --name "Alma" --name "Pennylane" --output .tmp\sirene_results.json
```

## Public interface

```python
from execution.lead_sourcing.sirene_company_lookup import lookup_company, lookup_companies

# Single
result = lookup_company("BlaBlaCar")
# {'siren': '491904238', 'naf_code': '62.01Z', 'is_digital_sector': 1, ...}

# Batch (uses in-process cache to avoid duplicate queries)
results = lookup_companies(["Qonto", "Alma", "Qonto"])  # "Qonto" only fetched once
```

## Tools / dependencies

- Python packages: `requests`, `python-dotenv`
- External services: INSEE SIRENE V3.11 API (free with API key; register at https://api.insee.fr)
- Base URL: `https://api.insee.fr/entreprises/sirene/V3.11`
- OAuth2 token URL: `https://api.insee.fr/token`
- Endpoint used: `GET /siret?q={query}&nombre=5`

## Edge cases & gotchas

- **Name-match heuristic (3-pass):** The script tries: (1) exact normalized name match among active companies, (2) exact normalized name match regardless of active status, (3) first active result. "Normalized" means accent-stripped, lowercased, punctuation-removed — via `_jt_utils.normalize_company()`. For companies with common names (e.g., "Digital"), pass 3 may return a wrong company. Watch for obviously wrong SIREN numbers in the digest.
- **SIRENE does not expose websites:** `website` is always `null`. Do not depend on this field — enrich it separately.
- **`is_digital_sector` is advisory:** The NAF code reflects a company's primary declared activity. A consulting firm that does heavy tech work may be coded under a non-digital NAF. The filter does not hard-reject non-digital companies — `is_digital_sector` is informational data surfaced in the digest.
- **Rate limits not published:** INSEE does not publicly document a rate limit. The scraper uses `@retry_with_backoff` for transient errors. Stay conservative: the orchestrator already processes one company name at a time (no parallel requests). If you see repeated 429-equivalent errors, add a `time.sleep(0.5)` between calls.
- **401/403 → returns null, does not raise:** Auth failures produce a null record with `source='error'`. The orchestrator logs the warning and continues — companies without SIRENE data still appear in the digest (just without the SIREN/NAF fields).
- **In-process cache:** `lookup_companies()` uses a module-level `_cache` dict keyed by normalized company name. This means calling `lookup_companies()` twice in the same Python process for the same name avoids a second API call. The cache is not persisted across runs.

## Self-anneal hooks

If name-match accuracy drops (obvious wrong SIREN matches in the digest):
1. Review the `matched_denomination` field in the log or `.tmp/job_tracker/{run_id}/` intermediate files.
2. Tighten the matching in `_pick_best_result()` — the current pass 3 (first active result) is the most permissive and can be removed if false matches are frequent.
3. Consider requiring a minimum Levenshtein similarity threshold before accepting a non-exact match (would require adding `python-Levenshtein` to deps).

If the INSEE API endpoint URL changes (SIRENE undergoes periodic versioning):
1. Check https://api.insee.fr for the latest version.
2. Update `SIRENE_BASE` constant in `sirene_company_lookup.py`.
3. Add a Changelog entry here.

## Changelog

- 2026-05-14: created.
