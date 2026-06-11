---
name: enrich-leads
description: Given a CSV of N leads (name + company + domain), fan out to Apollo + Exa enrichment in parallel, dedupe, and write the enriched rows to a Google Sheet.
inputs:
  - csv_path: string — path to leads.csv with columns name, company, domain
  - sheet_name: string — Google Sheet to write to (created if not exists)
outputs:
  - enriched_count: int — rows successfully enriched
  - skipped_count: int — rows where enrichment failed
  - sheet_url: string — URL of the resulting Google Sheet
---

# Enrich Leads

## When to invoke

- Input CSV has >20 rows (otherwise just run `execution/enrichment/enrich.py` directly).
- Both Apollo and Exa enrichment are desired (parallel sources, dedupe at the end).
- User wants the result in a Google Sheet, not a local CSV.

## Orchestration outline

1. **Fan-out**: read CSV, spawn one Haiku-tier sub-agent per row. Cap concurrency at 12.
2. **Map (per row)**: sub-agent calls Apollo enrichment, then Exa enrichment. Merges dicts. Returns one enriched-row JSON.
3. **Reduce**: collect all rows. Drop duplicates by (email, domain). Sort by enrichment_score desc.
4. **Write**: append to Google Sheet named in `sheet_name` using `execution/google/sheets.py`.

## Prompt template

```
ultracode: enrich every lead in {csv_path} with Apollo + Exa, dedupe by (email, domain), write to Google Sheet "{sheet_name}". Concurrency 12. Skip rows where both Apollo and Exa fail, but log the skip reason.
```

## Notes

- Default worker model: `claude-haiku-4-5` (this job is mostly API-call orchestration, not reasoning).
- Apollo + Exa both have rate limits — Anneal-style backoff inside the worker.
- Failure mode: per-row failures don't halt the batch. Final report includes skipped_count.
- Do NOT use this for AM leads (the AM lockdown rule applies — Apollo+Exa credits for AM are user-controlled only).
