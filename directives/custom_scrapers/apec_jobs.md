# APEC — Job Scraper SOP

## Goal

Extract PM/PO job listings from APEC (`apec.fr`), the French job board for cadres (managers and executives). Targeted at senior-level roles and particularly strong for established French companies. Uses the Firecrawl SDK with a JavaScript wait action because APEC's search results page is client-side rendered and requires a pause for the card list to hydrate before the markdown is extractable.

## When to use

- Called by the orchestrator (`job_tracker_pm_france.py`) at Stage A during every daily run.
- Run standalone to debug the JS-render wait or inspect raw card structure.
- `"apec"` must be in the active boards list.

## Inputs

### CLI args

| Flag | Required | Default | Purpose |
|------|----------|---------|---------|
| `--query QUERY` | Yes (repeatable) | — | Search query, e.g. `"product manager"`. Repeat for multiple queries. |
| `--output PATH` | No | `.tmp/job_tracker/{run_id}/raw_apec.json` | Path to write the output JSON file |
| `--max-results N` | No | 200 | Total cap across all queries |

### Environment variables required

| Variable | Purpose |
|----------|---------|
| `FIRECRAWL_API_KEY` | Authenticates the Firecrawl SDK; raises `EnvironmentError` at startup if missing |

### Config keys consumed from `config/job_tracker.json`

- `boards[name=apec].queries` — queries passed by the orchestrator
- `boards[name=apec].enabled` — must be `true`

## Outputs

- **File:** `raw_apec.json` at the resolved output path — a JSON array of `RawJob` objects.
- **Return value:** `list[dict]` returned in-memory.
- **Logs:**
  - `fetching_page` — per page fetched (includes query and page number)
  - `no_cards_on_page` — natural pagination end or all-empty page (stop condition)
  - `page_fetch_error` — Firecrawl error on a specific page
  - `scraper_done` — final count and queries
  - `scraper_failed` — unhandled exception; returns `[]`

### RawJob schema

```json
{
  "board": "apec",
  "source_url": "https://www.apec.fr/candidat/offre-emploi-detail/...?id=...",
  "title": "Product Owner — Fintech",
  "company_name": "Société Générale",
  "location": "Paris, 75",
  "posted_at": "2026-05-12",
  "description_snippet": "",
  "raw_extracted_at": "2026-05-14T04:00:02Z"
}
```

Note: `posted_at` is parseable for APEC — the listing cards include a "Publiée le DD/MM/YYYY" line which `_parse_french_date()` converts to ISO `YYYY-MM-DD`.

## How to run

```bash
# Standalone test
py execution\custom_scrapers\apec_jobs.py --query "product manager" --query "product owner" --output .tmp\raw_apec_test.json

# Single query, capped
py execution\custom_scrapers\apec_jobs.py --query "chef de produit" --max-results 50
```

## Public interface

```python
from execution.custom_scrapers.apec_jobs import scrape

jobs = scrape(
    queries=["product manager", "product owner"],
    output_path=Path(".tmp/raw_apec.json"),
    run_id="20260514-060000",
    max_results=200,
)
```

## Tools / dependencies

- Python packages: `firecrawl-py`, `python-dotenv`
- External services: Firecrawl — each page fetch uses 1 credit + the JS wait action may increase credit cost depending on the plan tier.
- URL pattern: `https://www.apec.fr/candidat/recherche-emploi.html/emploi?motsCles={encoded_query}&page={N}`
- JS wait: `{"type": "wait", "milliseconds": 2000}` — APEC's card list loads asynchronously. Without this wait the markdown often comes back as a loading skeleton with no job cards.
- Pagination: pages 1–5 per query (5 pages × ~20 cards/page = ~100 results per query max).

## Edge cases & gotchas

- **JS render requirement:** APEC is the slowest board to scrape because every page requires a 2-second wait. At 5 pages × 2 queries, this adds ~20 seconds of wait time per run. Do not remove the wait action — doing so will result in empty pages that look like pagination exhaustion.
- **`posted_at` is parseable:** APEC is the only board that reliably exposes a publish date in their listing markdown. The parser extracts "Publiée le DD/MM/YYYY" from within an 8-line window after each job link. If APEC changes the date label (e.g., "Mise en ligne le" or "Date de parution"), `_parse_french_date()` will return `null` for the field — this is not a crash, just a data gap.
- **URL format:** APEC job detail URLs follow `https://www.apec.fr/candidat/offre-emploi-detail/...`. If APEC restructures their URL pattern, the `job_link_re` regex in `_parse_markdown` will fail to match cards. Check `raw_apec.json` if count drops to zero.
- **Company and location are heuristic:** The parser scans 8 lines after the job link for company and location. APEC sometimes places a contract type line (e.g., "CDI") before the company name — this can cause the contract type to be captured as the company name. If you see "CDI" or "CDD" appearing as company names, update the parser to skip known contract-type tokens.
- **Dedup within run:** URLs are deduplicated by lowercased URL within this board's run. Cross-board dedup happens in Stage C.

## Self-anneal hooks

When card count drops unexpectedly:
1. Check `.tmp/job_tracker/{run_id}/raw_apec.json` — if the array is empty or very small, the JS wait may need increasing or the URL/regex has drifted.
2. Run standalone and print the raw markdown to see what Firecrawl is receiving.
3. If the wait is insufficient, increase `milliseconds` in `_fetch_markdown()`. If the URL pattern changed, update `job_link_re` in `_parse_markdown()`.
4. If the date label changed, update `date_re` in `_parse_markdown()`.
5. Add a Changelog entry here after fixing.

## Exit Criteria

- Output JSON file exists at the resolved output path and is a valid non-empty JSON array containing at least 1 `RawJob` object.
- Each `RawJob` in the array has a non-null `source_url` matching the pattern `https://www.apec.fr/candidat/offre-emploi-detail/`.
- `FIRECRAWL_API_KEY` is recognised (no `EnvironmentError` on startup and no HTTP 401 from Firecrawl in stderr).
- `scraper_done` log event is present in stderr with a `count` ≥ 1 for a query of `"product manager"`.
- Standalone run completes in under 90 seconds for 1 query × 1 page (accounting for the 2-second JS wait).

## Changelog

- 2026-05-14: created.
