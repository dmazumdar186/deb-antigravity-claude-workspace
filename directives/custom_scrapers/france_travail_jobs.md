# France Travail — Job Scraper SOP

## Goal

Fetch PM/PO job listings from France Travail (formerly Pôle Emploi) via their official REST API, not via web scraping. This is the highest-reliability board in the system — no captchas, no HTML parsing, structured JSON responses. Uses an OAuth2 `client_credentials` flow to obtain a short-lived bearer token, then queries the offers search endpoint filtered to ROME code `M1707` (Conception et développement web et multimédia, which covers most PM/PO roles in the French classification system). Returns a list of `RawJob` dicts.

## When to use

- Called by the orchestrator (`job_tracker_pm_france.py`) at Stage A during every daily run.
- Run standalone to verify API credentials are working or inspect raw offer structure.
- `"francetravail"` must be in the active boards list.

## Inputs

### CLI args

| Flag | Required | Default | Purpose |
|------|----------|---------|---------|
| `--query QUERY` | Yes (repeatable) | — | Keyword query passed as `motsCles`, e.g. `"product manager"`. Repeat for multiple queries. |
| `--output PATH` | No | `.tmp/job_tracker/{run_id}/raw_francetravail.json` | Path to write the output JSON file |
| `--max-results N` | No | 200 | Total cap across all queries |

### Environment variables required

| Variable | Purpose |
|----------|---------|
| `FRANCE_TRAVAIL_CLIENT_ID` | OAuth2 client ID from the France Travail developer portal (https://francetravail.io) |
| `FRANCE_TRAVAIL_CLIENT_SECRET` | OAuth2 client secret — keep this private; it grants API access |

### Config keys consumed from `config/job_tracker.json`

- `boards[name=francetravail].queries` — queries passed by the orchestrator
- `boards[name=francetravail].rome_code` — `"M1707"` is hardcoded in the scraper but is documented here for reference
- `boards[name=francetravail].enabled` — must be `true`

## Outputs

- **File:** `raw_francetravail.json` at the resolved output path — a JSON array of `RawJob` objects.
- **Return value:** `list[dict]` returned in-memory.
- **Logs:**
  - `fetching_page` — one event per API page (includes query and range)
  - `no_offers_returned` — pagination exhausted (204 or empty `resultats`)
  - `page_fetch_error` — HTTP error or network failure on a page
  - `missing_credentials` — env vars absent; returns `[]` immediately
  - `scraper_done` — final count and queries
  - `scraper_failed` — unhandled exception; returns `[]`

### RawJob schema

```json
{
  "board": "francetravail",
  "source_url": "https://candidat.francetravail.fr/offres/recherche/detail/{offre_id}",
  "title": "Chef de Produit Digital",
  "company_name": "Ministère de la Transition Numérique",
  "location": "75001 Paris 1er",
  "posted_at": "2026-05-13",
  "description_snippet": "Nous recherchons un Chef de Produit..."  
}
```

Note: `posted_at` is reliably populated — the API returns `dateCreation` in ISO 8601 format, truncated to `YYYY-MM-DD`. `description_snippet` contains the first 400 characters of the offer's `description` field.

## How to run

```bash
# Standalone test — verify credentials and inspect raw output
py execution\custom_scrapers\france_travail_jobs.py --query "product manager" --query "product owner" --output .tmp\raw_ft_test.json

# Single query, small cap
py execution\custom_scrapers\france_travail_jobs.py --query "chef de produit" --max-results 50
```

## Public interface

```python
from execution.custom_scrapers.france_travail_jobs import scrape

jobs = scrape(
    queries=["product manager", "product owner"],
    output_path=Path(".tmp/raw_francetravail.json"),
    run_id="20260514-060000",
    max_results=200,
)
```

## Tools / dependencies

- Python packages: `requests`, `python-dotenv`
- External services: France Travail API (free; register at https://francetravail.io)
- Token endpoint: `https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire`
- Search endpoint: `https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search`
- Public offer URL template: `https://candidat.francetravail.fr/offres/recherche/detail/{id}`
- ROME code: `M1707` — filtered server-side; reduces noise significantly
- Date filter: `publieeDepuis=7` — only offers posted in the last 7 days

## Edge cases & gotchas

- **Token endpoint is separate from the search endpoint:** A common mistake is using the API domain for the token endpoint. They are different: `entreprise.francetravail.fr` (token) vs `api.francetravail.io` (search). Do not mix them up.
- **Pagination via `range` header, not page number:** The France Travail API uses a `range` query parameter in the format `{start}-{end}` (e.g., `0-149`). Maximum 150 results per request. To get more than 150, increment `range_start` by 150 and request `150-299`, etc. The scraper handles this automatically.
- **HTTP 204 = no results, not an error:** A 204 response means the query returned zero offers. The scraper treats this as a clean pagination termination, not an error.
- **HTTP 206 = partial content, still valid:** France Travail may return 206 when the range exceeds the total result count. This is expected and treated as a success.
- **Token caching:** The module caches the OAuth2 token in `_token_cache` for the life of the Python process (refreshed 30 seconds before expiry). Safe for a single daily run; not thread-safe.
- **Missing credentials:** If either `FRANCE_TRAVAIL_CLIENT_ID` or `FRANCE_TRAVAIL_CLIENT_SECRET` is absent, the scraper logs a warning and returns `[]` without raising — the orchestrator can continue with other boards.
- **ROME code M1707 scope:** This ROME code captures most PM/PO roles, but some creative job titles may use other ROME codes. The filter stage (`job_filter.py`) will still apply keyword matching; ROME is a pre-filter at the API level, not a guarantee.

## Self-anneal hooks

On `401` or `403` (authentication failure):
1. Verify `FRANCE_TRAVAIL_CLIENT_ID` and `FRANCE_TRAVAIL_CLIENT_SECRET` are correctly set in `.env`.
2. Check if the application on https://francetravail.io is still active (apps can expire or be revoked).
3. Regenerate credentials if needed.

On `429` (rate limit) — not publicly documented but watch for it:
1. The scraper uses `@retry_with_backoff` with 3 retries and exponential backoff, which handles transient 429s.
2. If persistent, reduce `max_per_board` or add a per-request sleep between range pages.

On `5xx` errors from the API:
1. The `@retry_with_backoff` decorator handles transient errors.
2. If the France Travail API is down for an extended period, the board will emit `scraper_failed` and return `[]`. Other boards continue normally.

## Exit Criteria

- Output JSON file exists at the resolved output path and is a valid non-empty JSON array containing at least 1 `RawJob` object.
- Each `RawJob` has a non-null `posted_at` in `YYYY-MM-DD` format (France Travail API reliably returns `dateCreation`).
- OAuth2 token is obtained without error — no `401`/`403` from the token endpoint (`entreprise.francetravail.fr`) logged in stderr.
- `scraper_done` log event appears in stderr with `count ≥ 1` for a query of `"product manager"`.
- Standalone run using credentials from `.env` exits code `0` with no `missing_credentials` log entry.

## Changelog

- 2026-05-14: created.
