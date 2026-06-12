# Google Jobs via Serper.dev — Job Scraper SOP

## Goal

Fetch PM/PO job listings surfaced by Google's Jobs index for France using the Serper.dev `/jobs` API endpoint. Google Jobs aggregates postings from many sources (company career pages, ATS platforms, smaller boards) that don't appear on the other four boards, giving broad complementary coverage. Uses Serper's structured JSON response rather than scraping Google directly — no Firecrawl credits consumed for this board.

## When to use

- Called by the orchestrator (`job_tracker_pm_france.py`) at Stage A during every daily run.
- Run standalone to inspect the Serper response structure or test a new query.
- `"google"` must be in the active boards list.

## Inputs

### CLI args

| Flag | Required | Default | Purpose |
|------|----------|---------|---------|
| `--query QUERY` | Yes (repeatable) | — | Search query appended with " France" before sending to Serper, e.g. `"product manager France"`. Repeat for multiple queries. |
| `--output PATH` | No | `.tmp/job_tracker/{run_id}/raw_google.json` | Path to write the output JSON file |
| `--max-results N` | No | 200 | Total cap across all queries |

### Environment variables required

| Variable | Purpose |
|----------|---------|
| `SERPER_API_KEY` | API key from https://serper.dev — passed as `X-API-KEY` header |

### Config keys consumed from `config/job_tracker.json`

- `boards[name=google].queries` — queries passed by the orchestrator. Note: the config already includes "France" in the query strings (e.g., `"product manager France"`) to ensure geographic filtering.
- `boards[name=google].enabled` — must be `true`

## Outputs

- **File:** `raw_google.json` at the resolved output path — a JSON array of `RawJob` objects.
- **Return value:** `list[dict]` returned in-memory.
- **Logs:**
  - `fetching_page` — per page (includes query and page number)
  - `no_jobs_on_page` — pagination end (Serper returned empty jobs array)
  - `page_fetch_error` — HTTP error or network failure
  - `missing_credentials` — `SERPER_API_KEY` absent; returns `[]` immediately
  - `scraper_done` — final count and queries
  - `scraper_failed` — unhandled exception; returns `[]`

### RawJob schema

```json
{
  "board": "google",
  "source_url": "https://apply.workable.com/...",
  "title": "Senior Product Manager",
  "company_name": "Qonto",
  "location": "Paris, France",
  "posted_at": "2026-05-12",
  "description_snippet": "We are looking for a Senior Product Manager...",
  "posted_at_raw": "2 days ago"
}
```

Note: `posted_at` is best-effort — parsed from Serper's relative time strings (e.g., "2 days ago", "yesterday", "3 hours ago"). When parsing succeeds, `posted_at_raw` is omitted from the output. When parsing fails (unrecognised format), `posted_at` is `null` and `posted_at_raw` preserves the original string for manual inspection. `description_snippet` contains the first 400 characters of Serper's `description` field (when provided). `source_url` is the job's `applyLink` (preferred) or `shareLink`.

## How to run

```bash
# Standalone test
py execution\custom_scrapers\google_jobs_serper.py --query "product manager France" --query "product owner France" --output .tmp\raw_google_test.json

# Single query, small cap
py execution\custom_scrapers\google_jobs_serper.py --query "chef de produit France" --max-results 30
```

## Public interface

```python
from execution.custom_scrapers.google_jobs_serper import scrape

jobs = scrape(
    queries=["product manager France", "product owner France"],
    output_path=Path(".tmp/raw_google.json"),
    run_id="20260514-060000",
    max_results=200,
)
```

## Tools / dependencies

- Python packages: `requests`, `python-dotenv`
- External services: Serper.dev `/jobs` endpoint (`https://google.serper.dev/jobs`). Each API call = 1 credit. With 2 queries × N pages, credit usage scales with `max_per_board`. At 200 results/2 queries = ~4–6 credits per daily run (Serper paginates at ~10 jobs per call).
- Request payload: `{q: "{query}", gl: "fr", hl: "fr", page: N}` — `gl=fr` restricts to France; `hl=fr` returns French-language meta.

## Edge cases & gotchas

- **Relative-time parsing is best-effort:** Serper returns dates like "2 days ago", "1 week ago", "Posted 3 hours ago". The parser covers the most common English and French patterns. Unusual formats (e.g., "Hace 2 días" in Spanish) will leave `posted_at` as `null` and preserve the raw value in `posted_at_raw`. This is expected — the filter and dedup stages do not require `posted_at` to be populated.
- **`source_url` variety:** Serper may return `applyLink` (direct ATS link), `shareLink` (Google Jobs canonical URL), or neither. Jobs with neither link are skipped (`_map_serper_job` returns `None`). This is the right trade-off — a job without a navigable URL is not useful.
- **Google's index lag:** Google Jobs may show postings that are already closed. The 7-day rolling window in the orchestrator acts as a natural staleness guard, but some closed-role noise is expected.
- **Dedup by `source_url`:** URLs are deduplicated in-memory by lowercased URL within this board's run. Many Google Jobs URLs are ATS links that are stable across days; they'll hit the `job_hash` dedup in Stage C rather than re-appearing in the digest.
- **Query includes "France":** Unlike other boards which filter by country via URL params, Serper geographic filtering is less reliable for `/jobs`. Always append " France" to the query in `config/job_tracker.json` for this board.
- **Credit consumption vs. result quality:** Google Jobs is broad but noisy. If Serper credits are running tight, this is the first board to cap aggressively (`--boards google --max-results 50`) or disable, as the other four boards cover the main French-specific sources.

## Self-anneal hooks

On `401` (invalid API key):
1. Verify `SERPER_API_KEY` in `.env` — the key must exactly match the one in the Serper dashboard.
2. Check if the Serper subscription is active at https://serper.dev.

On `429` (quota exceeded):
1. Check your Serper dashboard for credit usage. The `/jobs` endpoint costs 1 credit per call.
2. Reduce `max_per_board` for the google board, or upgrade the Serper plan.
3. The `@retry_with_backoff` decorator will retry on 429 with backoff — transient spikes self-heal.

When `posted_at_raw` values accumulate in the digest with unparseable formats:
1. Add the new format to `_parse_relative_date()` in `google_jobs_serper.py`.
2. Add a Changelog entry here.

## Exit Criteria

- Output JSON file exists at the resolved output path and is a valid non-empty JSON array containing at least 1 `RawJob` object.
- Each `RawJob` has a non-null `source_url` — jobs without a navigable link are never included (confirmed by absence of `None` values in the `source_url` column).
- `SERPER_API_KEY` is present and recognised — no `missing_credentials` log entry and no HTTP 401 from Serper in stderr.
- `scraper_done` log event appears in stderr with `count ≥ 1` for a query of `"product manager France"`.
- Credit spend for a standard 2-query run is ≤ 10 Serper credits (confirmed by checking Serper dashboard usage delta).

## Changelog

- 2026-05-14: created.
