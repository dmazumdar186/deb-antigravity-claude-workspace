# Google Maps Lead Sourcing

## Goal
Source business listings matching the Accessory Masters ICP from Google Maps via Serper.dev Maps API, with Prospeo as fallback for B2B niches not indexed on Maps.

## When to Use
When sourcing a new batch of leads for a target city + industry combination, or when expanding to a new geography or niche.

## Inputs
- `--query`: Single search query (e.g., "car wash Houston TX")
- `--config`: Path to `config/accessory_masters.json` — runs all ICP niches x cities
- `--limit`: Max results per query (default: 100)
- `--output`: Output file path (default: `.tmp/serper_leads.json`)
- `--mock`: Use hardcoded mock data instead of real API
- Env var: `SERPER_API_KEY` (for Serper.dev), `PROSPEO_API_KEY` (for Prospeo fallback)

## Tools/Scripts
- `execution/lead_sourcing/serper_maps_scraper.py` — Serper.dev Maps API scraper
- `execution/lead_sourcing/prospeo_leads.py` — Prospeo B2B lead database
- `execution/modules/pipeline_utils.py` — shared utilities (dedup, I/O, logging)
- `config/accessory_masters.json` — ICP configuration

## Outputs
- `.tmp/serper_leads.json` — JSON array of lead records
- Each record: `business_name`, `address`, `city`, `state`, `phone`, `website`, `domain`, `industry`, `rating`, `reviews_count`, `source`, `source_query`, `sourced_at`, `dedup_key`, `status`

## Steps
1. Load config or parse CLI `--query` argument
2. For each industry + city combination, POST to Serper Maps API (`https://google.serper.dev/maps`)
3. Parse response: extract business listings from `places` array
4. Normalize fields (strip whitespace, lowercase domain, format phone)
5. Compute `dedup_key` for each record (domain + business name)
6. For B2B niches in `config.sourcing.use_prospeo_for`, query Prospeo instead
7. Merge Serper + Prospeo results
8. Deduplicate across all queries
9. Mark each record with `status="sourced"`
10. Save to output JSON file
11. Log: total records sourced, duplicates removed, records per industry

## Edge Cases
- **Serper API credits**: 2,500 credits to start. Each query = 1 credit. Monitor usage. With 10 niches x 6 cities = 60 queries — well within budget.
- **Maps not returning owner names**: Expected. Owner names come from the enrichment stage (AnymailFinder). Do NOT try to find owners at this stage.
- **Empty results for a niche**: Log a warning, continue to next niche. Some niches (manufacturing) won't appear on Maps — that's what Prospeo is for.
- **Duplicate businesses across niches**: A business might appear under "auto repair" and "car wash". Dedup by domain + business name handles this.
- **Serper returns <100 results**: Normal for niche + suburb combos. The limit parameter is a max, not a guarantee.
- **Rate limiting**: Serper has generous limits, but use `@retry_with_backoff` on all API calls.

## Exit Criteria

- Exit code 0. Output JSON file exists at the specified path and is a valid JSON array.
- At least 1 lead record written (0 leads = log a warning and investigate; do not silently succeed).
- Every record contains at minimum: `business_name`, `dedup_key`, `source`, `status="sourced"`.
- Log line emitted with total records sourced, duplicates removed, and records per industry.
- No uncaught exceptions. Rate-limit retries resolved within the run.

## Changelog
| Date | Change |
|------|--------|
| 2026-04-29 | Created — initial directive for Accessory Masters pipeline |
| 2026-06-12 | Added Exit Criteria (batch 2B) |
