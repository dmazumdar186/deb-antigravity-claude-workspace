---
name: aso-research
description: App Store Optimization research for a new mobile app. Given a list of competitor app names + stores (iOS/Android), fan out to scrape each app's search results page, parse screenshots/description/ratings/features, then synthesize into a competitive matrix JSON.
inputs:
  - competitors_file: string — path to CSV with columns: name, ios_id (optional), android_id (optional)
  - stores: list[string] — which stores to query; default both (ios, android); aliases: ios=appstore, android=playstore
outputs:
  - matrix_path: string — path to generated competitive matrix JSON (written to .tmp/aso_matrix_<slug>.json)
  - scraped_count: int — successfully scraped (competitor × store) cells
  - skipped_count: int — failed cells logged with reasons
---

# ASO Research Workflow

## When to invoke

- New app preflight (Phase 0 / app_design.md) — competitive landscape needed before spec.
- 5 or more competitors to research across both stores (otherwise call the script directly — no fan-out benefit below 5 cells).
- Both iOS and Android stores needed (single-store + single competitor = just use `--query` directly).

For < 5 competitors or single-store, call the script directly:

```
py execution/mobile_apps/app_store_research.py --query "Headspace" --store appstore
```

## Orchestration outline

1. Read CSV → list of competitor names.
2. Fan-out via `ultracode:` keyword: spawn one Haiku-tier sub-agent per (competitor, store) cell. Cap concurrency at 8 (Firecrawl rate limit).
3. Per cell: sub-agent invokes `execution/mobile_apps/app_store_research.py --query <competitor> --store <store> --single`.
4. Collect JSON blobs from each cell into a flat results list.
5. Merge into `{competitor_matrix: [...], scraped_count, skipped_count}` shape.
6. Write to `.tmp/aso_matrix_<slug>.json`.

Alternatively, use the script's built-in batch mode (simpler for < 16 competitors):

```
py execution/mobile_apps/app_store_research.py \
  --competitors-file competitors.csv \
  --stores ios android \
  --max-workers 8
```

The `--max-workers` flag controls ThreadPoolExecutor concurrency inside the script. Default is 8.

## Prompt template

```
ultracode: research ASO for every competitor in {competitors_file} across stores {stores}, write competitive matrix to .tmp/aso_matrix_{slug}.json. Concurrency 8. Skip cells where Firecrawl fails after 2 retries. Worker model: haiku.
```

## Notes

- Default worker model: `claude-haiku-4-5` (scraping + markdown extraction, no deep reasoning needed).
- Firecrawl rate limit: keep `--max-workers` <= 8 to avoid 429 errors.
- Per-cell failure isolation: `skipped_count` in output tells you how many cells failed and why; the batch never halts on a single failure.
- The script returns exit code 0 (all cells scraped), 1 (fatal error), or 2 (some cells skipped — still useful output).
- Use only for non-AM apps — AM is locked per `CLAUDE.local.md`.
- Wall-clock improvement: 20 serial Firecrawl calls at ~30s each ≈ 10 min serial vs ~75s parallel at 8 workers.

## Reference

- Script: `execution/mobile_apps/app_store_research.py`
- Directive: `directives/mobile_apps/app_design.md` (invoked at Step 0 — before Phase 1)
- Dynamic Workflow rules: `.claude/rules/dynamic-workflows.md`
- Hardening rules: `.claude/rules/python-hardening.md`
