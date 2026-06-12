# Jooble Jobs Scraper

## Purpose

Fetch job listings from Jooble's free POST API. Used in the job-search-sheet pipeline alongside Adzuna and France Travail. Jooble aggregates listings from 140,000+ job boards globally and returns a structured `type` field for contract classification. Returns `RawJob` dicts with `contract_type` and `country` fields.

---

## Signup

Jooble API access is **email-form-based** — no credit card, no instant key.

1. Go to [https://jooble.org/api/about](https://jooble.org/api/about)
2. Fill in the contact form: name, email, website or app description.
3. They email back your API key (usually within minutes to a few hours; occasionally 24h).
4. Add the key to `.env` as `JOOBLE_API_KEY=<value>`
5. Also add as a GitHub Actions repository secret for the daily cron.

**If the key stops working:** re-submit the form or email Jooble support. They occasionally revoke keys for inactive apps.

---

## Endpoint

```
POST https://jooble.org/api/<API_KEY>
Content-Type: application/json

{
  "keywords": "product manager",
  "location": "France",
  "page": 1
}
```

Response shape:
```json
{
  "totalCount": 142,
  "jobs": [
    {
      "title": "...",
      "location": "...",
      "snippet": "...",
      "salary": "...",
      "source": "...",
      "type": "Full-time",
      "link": "...",
      "company": "...",
      "updated": "2026-06-08T00:00:00+00:00",
      "id": "..."
    }
  ]
}
```

---

## Country Names and ISO2 Mapping

Jooble uses **full country names** (not ISO2 codes) in the `location` field of the request body. The mapping table in `jooble_jobs.py` is:

| Jooble location string | ISO2 (used in RawJob `country` field) |
|---|---|
| `France` | `FR` |
| `Germany` | `DE` |
| `Netherlands` | `NL` |
| `Spain` | `ES` |
| `Italy` | `IT` |
| `Belgium` | `BE` |
| `Austria` | `AT` |
| `Poland` | `PL` |
| `Portugal` | `PT` |
| `Canada` | `CA` |
| `USA` | `US` |
| `United States` | `US` |
| `United Kingdom` | `GB` |
| `Switzerland` | `CH` |
| `Sweden` | `SE` |
| `Norway` | `NO` |
| `Denmark` | `DK` |
| `Finland` | `FI` |
| `Ireland` | `IE` |
| `Luxembourg` | `LU` |

Country values come from `config/job_search.json` → `geos.<GEO>.jooble_country`.

---

## Contract Type Field

Jooble's `type` field is free-text but consistently uses these values:

| Jooble `type` | Normalised `contract_type` in RawJob |
|---|---|
| `Full-time` | `Permanent` |
| `Part-time` | `Part-time` |
| `Contract` | `Contract` |
| `Temporary` | `Contract` |
| `Freelance` | `Freelance` |
| `Internship` | `Internship` |
| *(empty / absent)* | `None` |

Note: Jooble does not distinguish CDI vs CDD — `Full-time` maps to `Permanent` as the closest equivalent. The LLM relevance gate (Phase 1) can refine this from the description snippet if needed.

---

## Failure Modes

| Failure | Behaviour |
|---|---|
| HTTP 401 | Logs `jooble_bad_api_key` clearly with re-registration link. Returns `[]` immediately — key is dead, no point retrying. |
| HTTP 429 | `retry_with_backoff` retries 2×, then logs `jooble_rate_limited` + returns collected results. |
| HTTP 5xx | `retry_with_backoff` retries 3× with exponential backoff, then logs error + skips query. |
| Missing `JOOBLE_API_KEY` | Logs `missing_credentials`, returns `[]` immediately. |
| Empty `jobs` array | Logs `no_jobs_returned` with `totalCount`, continues to next query. |

---

## CLI Usage

```bash
# Single query, France (default)
py execution/custom_scrapers/jooble_jobs.py --country France --query "product manager"

# Multiple synonyms, Germany
py execution/custom_scrapers/jooble_jobs.py --country Germany \
  --query "product manager" \
  --query "ai product manager"

# Custom output path
py execution/custom_scrapers/jooble_jobs.py --country France \
  --query "product manager" \
  --output .tmp/test_jooble_fr.json
```

---

## Exit Criteria

- Output JSON file exists at the resolved output path and is a valid non-empty JSON array containing at least 1 `RawJob` object.
- Each `RawJob` contains `board`, `source_url`, `title`, `company_name`, and `country` keys — no `__PLACEHOLDER__` values.
- `JOOBLE_API_KEY` is present in `.env`; run exits `0` with no `missing_credentials` or `jooble_bad_api_key` log entry.
- `contract_type` field in each `RawJob` is one of the normalised values (`Permanent`, `Part-time`, `Contract`, `Freelance`, `Internship`) or `None` — no raw Jooble `type` strings leak through.
- Run completes in under 30 seconds for a single query + country combination.

## Notes

- Results are written to `.tmp/job_search/<run_id>/raw_jooble_<iso2>.json` by default.
- The orchestrator (`job_search_sheet.py`) calls `scrape()` programmatically and passes `run_id`.
- Jooble returns up to ~50 results per page; `page=1` (default) is sufficient for Phase 1a/1b given 6 queries per run.
- Unlike Adzuna, Jooble does not expose a hard daily quota number. In practice, free-tier keys support several hundred requests/day without rate-limiting.
