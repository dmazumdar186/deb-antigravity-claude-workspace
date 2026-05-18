# Indeed France — Job Scraper SOP

## Goal

Extract PM/PO job listings from Indeed France (`fr.indeed.com`) using the Firecrawl SDK with stealth proxy mode to bypass Indeed's aggressive anti-bot measures. Returns a list of `RawJob` dicts. Indeed has broad coverage including SME postings that don't appear on niche boards, but its anti-bot posture means occasional captcha blocks; the scraper handles these gracefully by returning an empty list for the blocked page rather than crashing.

## When to use

- Called by the orchestrator (`job_tracker_pm_france.py`) at Stage A during every daily run.
- Run standalone to test anti-bot resilience or inspect raw cards for a given query.
- `"indeed"` must be in the active boards list.

## Inputs

### CLI args

| Flag | Required | Default | Purpose |
|------|----------|---------|---------|
| `--query QUERY` | Yes (repeatable) | — | Search query, e.g. `"product manager"`. Repeat the flag for multiple queries. |
| `--output PATH` | No | `.tmp/job_tracker/{run_id}/raw_indeed.json` | Path to write the output JSON file |
| `--max-results N` | No | 200 | Total cap across all queries |

### Environment variables required

| Variable | Purpose |
|----------|---------|
| `FIRECRAWL_API_KEY` | Authenticates the Firecrawl SDK; raises `EnvironmentError` at startup if missing |

### Config keys consumed from `config/job_tracker.json`

- `boards[name=indeed].queries` — queries passed by the orchestrator
- `boards[name=indeed].enabled` — must be `true`

## Outputs

- **File:** `raw_indeed.json` at the resolved output path — a JSON array of `RawJob` objects.
- **Return value:** `list[dict]` returned in-memory.
- **Logs:**
  - `fetching_page` — per page
  - `indeed_blocked` — captcha/empty response detected; scraper stops for that page and query
  - `no_cards_on_page` — natural pagination end
  - `page_fetch_error` — Firecrawl error on a page
  - `scraper_done` — final count
  - `scraper_failed` — unhandled exception; returns `[]`

### RawJob schema

```json
{
  "board": "indeed",
  "source_url": "https://fr.indeed.com/viewjob?jk=abc123",
  "title": "Product Manager",
  "company_name": "BlaBlaCar",
  "location": "Paris, Île-de-France",
  "posted_at": null,
  "description_snippet": "",
  "raw_extracted_at": "2026-05-14T04:00:01Z"
}
```

Note: `posted_at` is `null` — Indeed's listing page markdown does not expose a machine-readable date in the expected location. The field is preserved for potential future extraction from the detail page.

## How to run

```bash
# Standalone test
py execution\custom_scrapers\indeed_jobs.py --query "product manager" --query "product owner" --output .tmp\raw_indeed_test.json

# Single query, small cap for a quick sanity check
py execution\custom_scrapers\indeed_jobs.py --query "product manager" --max-results 30
```

## Public interface

```python
from execution.custom_scrapers.indeed_jobs import scrape

jobs = scrape(
    queries=["product manager", "product owner"],
    output_path=Path(".tmp/raw_indeed.json"),
    run_id="20260514-060000",
    max_results=200,
)
```

## Tools / dependencies

- Python packages: `firecrawl-py`, `python-dotenv`
- External services: Firecrawl (stealth proxy mode burns credits faster than standard mode — check your plan).
- URL pattern: `https://fr.indeed.com/jobs?q={encoded_query}&l=France&fromage=7&start={N*10}`
- Pagination: `start` offset in increments of 10, up to 5 pages (50 results) per query.
- Stealth proxy: passed as `"proxy": "stealth"` in the Firecrawl params. If the SDK version does not support this param, the scraper falls back to a standard scrape and logs `proxy_stealth_unavailable`.

## Edge cases & gotchas

- **Anti-bot / captchas:** Indeed is the most bot-hostile board in this system. Firecrawl stealth proxy handles the majority of blocks, but captchas occasionally slip through. When `_is_blocked()` detects a captcha (markdown < 200 chars, or contains "captcha"/"verify you are human"/"access denied"), the scraper logs `indeed_blocked` and breaks out of the page loop for that query — it does NOT crash. The returned count for this board will be lower than usual, which may trigger `BOARD_DEGRADED` detection if it happens repeatedly.
- **URL variety:** Indeed uses several URL formats for the same job (`viewjob?jk=`, `pagead/clk`, `rc/clk`, `company/.../jobs/`). The parser captures all of them via a broad regex and uses the URL as the dedup key.
- **`posted_at` always null:** Indeed's listing card markdown does not include a parseable date. This is expected.
- **Heading parser sensitivity:** The parser uses heading-level lines (`##`) as card anchors. If Indeed changes their markdown structure (headings removed or different levels), no cards will be parsed. This will surface as a `BOARD_DEGRADED` event.

## Self-anneal hooks

When the captcha block rate increases (frequent `indeed_blocked` events without page recovery):
1. Check whether Firecrawl has released a newer stealth proxy mode or a dedicated Indeed integration.
2. Temporarily reduce `max_per_board` for Indeed to lower the request rate.
3. If blocks persist across multiple days, consider disabling the Indeed board in `config/job_tracker.json` (`"enabled": false`) to stop burning credits.

When the HTML/markdown structure changes (headings or URL patterns differ):
1. Run standalone and inspect raw markdown by temporarily adding a debug `print(markdown)` in `_fetch_markdown`.
2. Update `_parse_markdown()` in `indeed_jobs.py` to match the new card structure.
3. Add a Changelog entry here.

## Changelog

- 2026-05-14: created.
