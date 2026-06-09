# Adzuna Jobs Scraper

## Purpose

Fetch job listings from Adzuna's free REST API. Used in the job-search-sheet pipeline (Phase 1a: France; Phase 1b: Schengen + CA + US). Returns structured `RawJob` dicts including `contract_type` and `country` fields.

Adzuna aggregates listings from multiple boards including WTTJ, HelloWork, and direct employer postings — so a single Adzuna-FR call captures most French job board coverage without Firecrawl.

---

## Free-Tier Quota

**250 requests/day per app** (app_id + app_key pair).

Phase 1a load calculation:
- 6 title synonyms × 1 page × 1 country (FR) = **6 requests/run**
- 1 run/day → **6 req/day**. Well within quota.

Phase 1b load calculation (all geos):
- 6 synonyms × 1 page × 11 countries = **66 req/run** → still under 250/day.

**Rule: keep `pages=1` (default) per (query, country) pair.** With 50 results per page and 6 queries, you get up to 300 raw results before dedup — more than sufficient.

If you ever need more than 50 results per query, increase `results_per_page` (max 50 per Adzuna free tier) or add a second query synonym rather than bumping `pages`. Multi-page runs multiply quota spend.

---

## Signup

1. Go to [https://developer.adzuna.com/signup](https://developer.adzuna.com/signup)
2. Create an account (no credit card required).
3. Under **My Apps**, create a new app — pick any name (e.g. "job-search-sheet").
4. Copy **App ID** → `.env` as `ADZUNA_APP_ID=<value>`
5. Copy **App Key** → `.env` as `ADZUNA_APP_KEY=<value>`
6. Also add both as GitHub Actions repository secrets for the daily cron.

---

## Supported Countries (ISO2 → Adzuna endpoint name)

| ISO2 | Adzuna endpoint path |
|------|----------------------|
| `fr` | `/jobs/fr/search/` |
| `de` | `/jobs/de/search/` |
| `nl` | `/jobs/nl/search/` |
| `es` | `/jobs/es/search/` |
| `it` | `/jobs/it/search/` |
| `be` | `/jobs/be/search/` |
| `at` | `/jobs/at/search/` |
| `pl` | `/jobs/pl/search/` |
| `pt` | `/jobs/pt/search/` |
| `ca` | `/jobs/ca/search/` |
| `us` | `/jobs/us/search/` |

Pass the ISO2 code (lowercase) as `--country` or as the `country` arg to `scrape()`.

---

## Fields Exposed by Adzuna API

| Adzuna field | Used in RawJob |
|---|---|
| `redirect_url` | `source_url` |
| `title` | `title` |
| `company.display_name` | `company_name` |
| `location.display_name` | `location` |
| `created` | `posted_at` (stripped to YYYY-MM-DD) |
| `description` | `description_snippet` (first 400 chars) |
| `contract_type` | `contract_type` ("permanent" → "Permanent", "contract" → "Contract") |
| `contract_time` | Not used directly; `contract_type` field is more reliable |
| `category.label` | Not captured in RawJob schema (available if needed) |

**FR-specific contract_type extraction:** when `contract_type` is absent/unknown, the scraper scans `description` for French keywords:
- `CDI` → `"CDI"`
- `CDD` → `"CDD"`
- `freelance` / `free-lance` → `"Freelance"`

---

## Failure Modes

| Failure | Behaviour |
|---|---|
| HTTP 429 mid-run | Logs `adzuna_quota_exhausted=true`, returns collected results so far. Does NOT retry — daily quota is over. |
| API response body contains `"exception"` with "rate" or "limit" | Same as HTTP 429: quota-exhausted log + early return. |
| HTTP 4xx (not 429) | Logs `page_fetch_error`, skips that page, continues to next query. |
| HTTP 5xx | `retry_with_backoff` retries up to 3× with exponential backoff, then logs error + skips page. |
| Missing env vars | Logs `missing_credentials`, returns `[]` immediately. |
| Empty results page | Logs `no_results_on_page`, stops pagination for that query. |

---

## CLI Usage

```bash
# Single query, France (default)
py execution/custom_scrapers/adzuna_jobs.py --country fr --query "product manager"

# Multiple synonyms, Germany
py execution/custom_scrapers/adzuna_jobs.py --country de \
  --query "product manager" \
  --query "chef de produit" \
  --query "ai product manager"

# Custom output path
py execution/custom_scrapers/adzuna_jobs.py --country fr \
  --query "product manager" \
  --output .tmp/test_adzuna_fr.json
```

---

## Notes

- Results are written to `.tmp/job_search/<run_id>/raw_adzuna_<country>.json` by default.
- The orchestrator (`job_search_sheet.py`) calls `scrape()` programmatically and passes `run_id` for consistent file layout across all sources in the same run.
- Country config values come from `config/job_search.json` → `geos.<GEO>.adzuna_country`.
