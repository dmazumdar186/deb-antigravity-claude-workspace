# Firecrawl LinkedIn Dork — Contact Enrichment SOP

## Prior art pass

Retrospective per `~/.claude/rules/prior-art-first.md`. This directive pre-dates the rule (2026-06-18):

- **Public LinkedIn API for people search?** No usable public path. LinkedIn's official API gates contact discovery behind partner agreements; the public site rate-limits and bans non-authenticated scrapers fast.
- **Existing tools**: Apollo, ZoomInfo, Hunter.io, Anymailfinder all monetize this exact use case. Workspace already has `ANYMAILFINDER_API_KEY` + `PROSPEO_API_KEY` for email verification once we have profile URLs.
- **Discovery path chosen**: Google dork via Firecrawl `/search` -- queries like `site:linkedin.com/in "Head of Product" "<company>"`. Surfaces LinkedIn profile URLs without scraping LinkedIn directly (ToS-safe), the operator's existing FIRECRAWL_API_KEY covers the search cost, and the URLs feed into Anymailfinder/Prospeo for the email step.
- **Why this path**: stays in compliance with LinkedIn's ToS, reuses existing keys, and the Firecrawl `/search` endpoint is the integration the workspace already pays for.
- **Architecture**: tiered dork batches per seniority level (CPO > VP > Head > Senior PM > HR), dedup by canonical `linkedin.com/in/{slug}`, then handoff to email enrichers.

## Goal

Find 3–5 contactable people per company (CPO, VP Product, Head of Product, Senior PM, HR/Talent) by running Google dork searches via Firecrawl's `/search` endpoint. This approach surfaces LinkedIn profile URLs without scraping LinkedIn directly — which would violate LinkedIn's ToS and trigger rapid blocks. Results are collected by seniority tier, deduplicated by canonical LinkedIn URL, and returned as structured contact records.

## When to use

- Called automatically by the orchestrator at Stage E for each newly seen company (companies already in the DB within `contact_cache_days` are skipped).
- Skipped when `--no-enrich` is passed to the orchestrator.
- Run standalone to find contacts for a list of companies manually.
- Usable in any pipeline that needs product/HR contacts at French companies — not limited to the job tracker.

## Inputs

### CLI args

| Flag | Required | Default | Purpose |
|------|----------|---------|---------|
| `--company COMPANY_NAME` | Yes (repeatable) | — | Company name to find contacts for. Repeat for batch mode. |
| `--output PATH` | No | stdout only | Optional path to write results as JSON |
| `--max N` | No | 5 | Maximum contacts per company |

### Environment variables required

| Variable | Purpose |
|----------|---------|
| `FIRECRAWL_API_KEY` | Firecrawl SDK auth — used for the `/search` endpoint |

### Config keys consumed from `config/job_tracker.json`

- `contact_cache_days` — the orchestrator checks this before calling `find_contacts_for_company()`. If a company was enriched within this window, enrichment is skipped entirely. The module itself does not read config; caching is orchestrator-side.

## Outputs

- **Return value from `find_contacts_for_company()`:**
  ```json
  [
    {
      "full_name": "Marie Dupont",
      "title": "Chief Product Officer at Qonto",
      "seniority": "cpo",
      "linkedin_url": "https://www.linkedin.com/in/marie-dupont-42a1b2",
      "source": "firecrawl_dork"
    }
  ]
  ```
- **Return value from `find_contacts_bulk()`:** `{company_name: [contact, ...], ...}`
- **Logs:**
  - `firecrawl_dork: found N contact(s) for "Company"` — info level per company
  - `firecrawl_dork: search failed for company=... seniority=...` — warning when a dork fails; pipeline continues
- **Side effects:** Each unique company × seniority tier consumes Firecrawl search credits (1 credit per dork query; 5 dorks per company × 2 results per dork = up to 10 credits per company per enrichment cycle).
- **Files (when called by orchestrator):** `.tmp/job_tracker/{run_id}/contacts_{company_slug}.json` — one file per newly enriched company.

## How to run

```bash
# Single company
py execution\enrichment\firecrawl_linkedin_dork.py --company "BlaBlaCar"

# Batch with output file
py execution\enrichment\firecrawl_linkedin_dork.py --company "Qonto" --company "Alma" --company "Payfit" --output .tmp\contacts_batch.json

# With custom max
py execution\enrichment\firecrawl_linkedin_dork.py --company "Doctolib" --max 3
```

## Public interface

```python
from execution.enrichment.firecrawl_linkedin_dork import find_contacts_for_company, find_contacts_bulk

# Single company
contacts = find_contacts_for_company("Qonto", max_total=5)

# Batch (sleeps 1s between companies)
results = find_contacts_bulk(["Qonto", "Alma", "Payfit"], max_total_per_company=5)
```

## Dork templates and seniority priority

Five dorks are run per company, in this priority order:

| Seniority | Dork template |
|-----------|---------------|
| `cpo` | `site:linkedin.com/in "Chief Product Officer" "{company}"` |
| `vp_product` | `site:linkedin.com/in "VP Product" "{company}"` |
| `head_of_product` | `site:linkedin.com/in "Head of Product" "{company}"` |
| `senior_pm` | `site:linkedin.com/in "Senior Product Manager" "{company}"` |
| `hr` | `site:linkedin.com/in ("HR" OR "Talent Acquisition") "{company}"` |

Each dork fetches up to 2 results from Firecrawl (`limit=2`). After all dorks run, results are merged in priority order (CPO first, HR last), deduplicated by canonical LinkedIn URL, and capped at `max_total` (default: 5).

## Tools / dependencies

- Python packages: `firecrawl-py`, `python-dotenv`
- External services: Firecrawl `/search` endpoint — costs 1 credit per dork query. At 5 dorks × 2 results = 5 credits per company per enrichment cycle. With `contact_cache_days=60`, each company is enriched at most once every 60 days, so Firecrawl credit burn is bounded by the rate of new companies entering the tracker.

## Edge cases & gotchas

- **Empty results are common for small startups:** LinkedIn coverage is heavily biased toward larger, well-known companies. Startups with <50 employees may return 0 contacts across all 5 dorks. This is expected — the contact list in the digest will simply be empty for that company.
- **LinkedIn URL canonicalization:** Before storing or deduplicating, URLs are trimmed of query strings and fragments (everything after `?` or `#`). LinkedIn sometimes adds tracking parameters (e.g., `?originalSubdomain=fr`). The canonical form is `https://www.linkedin.com/in/{slug}`. This is handled in `find_contacts_for_company()` before `seen_urls` insertion.
- **Title parsing is heuristic:** LinkedIn search result titles come in several formats: `"Name - Title at Company - LinkedIn"`, `"Name | Title | Company"`, `"Name – Title"`. The `_parse_title_field()` function handles common variants. Falls back to the seniority label if parsing yields nothing meaningful. Do not rely on `title` being perfectly accurate — it is informational only.
- **Dork phrasing drift:** If LinkedIn changes how titles appear in search result metadata (e.g., "VP, Product" instead of "VP Product"), the dork may return fewer or zero results for that tier. Update the dork template string in `_DORKS` in `firecrawl_linkedin_dork.py`.
- **Rate limiting:** `find_contacts_bulk()` adds a 1-second sleep between companies. This is conservative but polite. Do not remove it — Firecrawl's `/search` endpoint has per-second rate limits that vary by plan.
- **`FIRECRAWL_API_KEY` absent:** The function returns `[]` without raising. The orchestrator logs a warning but continues — the digest renders without contacts for that company.

## Self-anneal hooks

When contact yield drops significantly (many companies show 0 contacts where they previously had results):
1. Check if LinkedIn has changed title text patterns in their search snippets. Look at the raw `title` field in Firecrawl search results by temporarily printing the raw response.
2. Update dork templates in `_DORKS` in `firecrawl_linkedin_dork.py` to match the new patterns.
3. Add a Changelog entry here.

When a specific seniority tier consistently returns 0 results:
1. Consider adding alternative title variants to that tier's dork. For example, `vp_product` could be extended with `"VP of Product"` or `"VP, Product"`.
2. Or add a sixth dork for a new seniority tier if needed.

## Exit Criteria

- Exit code 0. Results dict/JSON written to `--output` path (or stdout) without error.
- Every requested company appears as a key in the results dict; value is a list (possibly empty).
- Each contact record contains: `full_name`, `title`, `seniority`, `linkedin_url`, `source="firecrawl_dork"`.
- `linkedin_url` values are canonicalized (no `?` or `#` query parameters).
- Deduplication applied: no two contacts share the same canonical `linkedin_url` within a company.
- Contact count per company is `<= --max` (default 5).
- Firecrawl search failures for individual dork tiers are logged as warnings, not exceptions — pipeline continues for remaining companies.
- 1-second inter-company sleep preserved in bulk mode (not removed or skipped).

## Changelog

- 2026-05-14: created.
- 2026-06-12: Added Exit Criteria (batch 2B).
