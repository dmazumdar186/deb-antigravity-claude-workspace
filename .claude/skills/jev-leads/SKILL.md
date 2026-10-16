---
name: jev-leads
description: Jev-gated lead pipeline: hygiene, suppression, ICP qualify, signals, reply/inbound triage, LinkedIn diff. Triggers on "generate leads", "enrich leads", "qualify leads", "score leads", "ICP filter", "lead signals", "triage replies", /jev-leads.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---
# jev-leads

Jev makes typed decisions (yes/no, choice, score) on every lead row; deterministic scripts move data; Claude writes copy. Script: `execution/gtm_icp_filters/jev_leads.py`.

## ICP profile (required)
Copy `execution/gtm_icp_filters/icp_profiles/_template.json` to `.tmp/icp_<client>.json` (one-off) or `icp_profiles/<client>.json` (kept). Unknown offer/ICP: ask the operator once, then proceed.

## Pipeline order
source (scrape-leads, gmaps-leads, `lead_sourcing/prospeo_leads.py`, `serper_maps_scraper.py`) → hygiene → suppress → qualify → enrich only `go` rows → signals → push to Instantly / Sheet. Replies, inbound and diff are standalone runs.

```
S=execution/gtm_icp_filters/jev_leads.py; I=--icp .tmp/icp_x.json
python3 $S hygiene  --input leads.json --csv-out .tmp/clean.csv
python3 $S suppress --input .tmp/clean.csv $I --csv-out .tmp/allowed.csv
python3 $S qualify  --input .tmp/allowed.csv $I --only-pass --csv-out .tmp/go.csv --md .tmp/go.md
python3 $S signals  --input .tmp/go.csv $I --csv-out .tmp/signals.csv
python3 $S replies  --input .tmp/replies.json
python3 $S inbound  --input form.json $I
python3 $S diff     --input connections_new.csv --snapshot connections_prev.csv $I
```
Add `--dry-run` first on new data (no network). Enrich go rows with `enrichment/email_mx_verify.py` (keyless), then `casualize_and_city_split.py`. `anymailfinder_lookup.py` and `million_verifier.py` are AM-locked: only with explicit operator go-ahead.

## Rules
- **Confidence gate:** never send a `hold`/`review` row. Do not retry Jev on it; escalate to a person or Claude.
- **Validate first:** until ≥30 labelled rows pass `--validate labels.csv` (or `infrastructure/jev_validate.py` with `jev_specs/lead_qualify.json`), treat `--min-confidence` as untested and review a sample.
- Never judge from a bare title: enrich context before qualify if rows are thin.
- Jev never writes emails, extracts free text or finds addresses.
- Exit 2 = missing `OPENROUTER_API_KEY`. Cost lands in `.tmp/jev_ledger.jsonl`.

Directive: `directives/gtm_icp_filters/jev_leads.md`. Why and when: `docs/reference/jev_leads_playbook.md`.
