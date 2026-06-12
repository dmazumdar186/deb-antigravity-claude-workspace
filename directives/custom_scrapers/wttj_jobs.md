# Welcome to the Jungle — Job Scraper SOP

## Goal

Extract PM/PO job listings from Welcome to the Jungle (wttj.com), filtered to France, using the Firecrawl SDK. Returns a list of `RawJob` dicts which are then passed to the orchestrator's filter + dedup stages. WttJ is a high-signal source for French digital-sector companies and often has the most structured listings of any French board.

## When to use

- Called by the orchestrator (`job_tracker_pm_france.py`) at Stage A during every daily run.
- Run standalone to debug the scraper or inspect raw output for a specific query.
- `"wttj"` must be in the active boards list (either via `--boards wttj` or enabled in `config/job_tracker.json`).

## Inputs

### CLI args

| Flag | Required | Default | Purpose |
|------|----------|---------|---------|
| `--query QUERY` | Yes (repeatable) | — | Search query, e.g. `"product manager"`. Repeat the flag for multiple queries. |
| `--output PATH` | No | `.tmp/job_tracker/{run_id}/raw_wttj.json` | Path to write the output JSON file |
| `--max-results N` | No | 200 | Total cap across all queries |

### Environment variables required

| Variable | Purpose |
|----------|---------|
| `FIRECRAWL_API_KEY` | Authenticates the Firecrawl SDK; raises `EnvironmentError` at startup if missing |

### Config keys consumed from `config/job_tracker.json`

- `boards[name=wttj].queries` — list of queries passed when called by the orchestrator
- `boards[name=wttj].enabled` — must be `true` for the orchestrator to invoke this module

## Outputs

- **File:** `raw_wttj.json` at the resolved output path — a JSON array of `RawJob` objects.
- **Return value:** `list[dict]` returned in-memory to the orchestrator.
- **Logs:** Structured JSON events to the module logger:
  - `fetching_page` — one event per page fetched (includes board, query, page, URL)
  - `no_cards_on_page` — pagination stops here
  - `page_fetch_error` — Firecrawl error on a specific page
  - `scraper_done` — final count and queries
  - `scraper_failed` — unhandled exception; returns `[]`

### RawJob schema

```json
{
  "board": "wttj",
  "source_url": "https://www.welcometothejungle.com/.../jobs/{slug}",
  "title": "Product Manager — Payments",
  "company_name": "Alma",
  "location": "Paris",
  "posted_at": null,
  "description_snippet": "",
  "raw_extracted_at": "2026-05-14T04:00:00Z"
}
```

Note: `posted_at` is always `null` for WttJ because the listing page markdown does not expose a parseable date without loading the detail page.

## How to run

```bash
# Standalone test — two queries, write to specific file
py execution\custom_scrapers\wttj_jobs.py --query "product manager" --query "product owner" --output .tmp\raw_wttj_test.json

# Single query with cap
py execution\custom_scrapers\wttj_jobs.py --query "chef de produit" --max-results 50
```

## Public interface

```python
from execution.custom_scrapers.wttj_jobs import scrape

jobs = scrape(
    queries=["product manager", "product owner"],
    output_path=Path(".tmp/raw_wttj.json"),   # optional
    run_id="20260514-060000",                  # optional
    max_results=200,
)
# Returns list[RawJob dict]
```

## Tools / dependencies

- Python packages: `firecrawl-py`, `python-dotenv`
- External services: Firecrawl (counts against your plan's page credits). Each page fetch = 1 credit. With 2 queries × 10 pages max = 20 credits/run worst case per board.
- URL pattern: `https://www.welcometothejungle.com/fr/jobs?query={encoded_query}&refinementList[offices.country_code][]=FR&page={N}`

## Edge cases & gotchas

- **Bracketed URL params:** WttJ uses `refinementList[offices.country_code][]=FR` — the brackets are kept literal in the URL (not percent-encoded) because WttJ's server expects them this way. `urllib.parse.quote_plus` encodes the `query` param only.
- **`posted_at` always null:** WttJ listing pages do not expose publish dates in their markdown summary. The field is set to `null` and the filter/dedup stages handle this gracefully (no date-based filtering is applied at the RawJob stage).
- **Pagination stops automatically:** If a page returns zero job cards, the loop breaks for that query. WttJ caps at roughly 5–7 pages of real results for typical queries.
- **Company name heuristic:** The parser scans the 6 lines following a job link for the company name. If WttJ restructures their card layout, the company field may go blank or pick up the wrong text. Check `raw_wttj.json` if company names look wrong.
- **Dedup within run:** URLs are deduplicated in-memory by lowercased URL across all pages and queries for this board. Cross-board dedup happens in Stage C via `job_hash`.

## Self-anneal hooks

When WttJ changes their HTML/markdown structure:
1. The `scraper_done` count will drop significantly (check against the 7-day median in `board_counts.json`).
2. The orchestrator will emit a `BOARD_DEGRADED` event if count < 30% of median.
3. Fix-loop:
   a. Run standalone with one query: `py execution\custom_scrapers\wttj_jobs.py --query "product manager" --output .tmp\debug_wttj.json`
   b. Inspect the raw markdown Firecrawl returned by temporarily logging it (add a `print(markdown)` in `_fetch_markdown`).
   c. Update `_parse_markdown()` in `wttj_jobs.py` to match the new card structure.
   d. Re-run, confirm counts recover.
   e. Add a Changelog entry here with the date and what changed.

## Exit Criteria

- Output JSON file exists at the resolved output path and is a valid non-empty JSON array containing at least 1 `RawJob` object.
- Each `RawJob` has a non-null `source_url` matching `welcometothejungle.com` and `board == "wttj"`.
- `FIRECRAWL_API_KEY` is present — no `EnvironmentError` on startup and no HTTP 401 from Firecrawl in stderr.
- `scraper_done` log event appears in stderr with `count ≥ 1` for a query of `"product manager"`.
- URLs in the output are unique within the result set (dedup confirmed by checking for duplicate `source_url` values in the array).

## Changelog

- 2026-05-14: created.
