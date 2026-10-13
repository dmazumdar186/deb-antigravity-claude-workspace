# Jev recruitment / HR ICP filter

**Script:** `execution/gtm_icp_filters/jev_recruitment_icp_filter.py`

## Goal
Keep only recruitment, staffing, executive-search and HR-consulting companies in a launch list, and flag everything
else (HR software, VCs, operating companies, unrelated consultancies) into a review file instead of deleting it.
The scraper's `Industry` tag is not enough: IT-tagged rows are often IT staffing firms, and "Human Resources"
rows are often HR SaaS.

## Inputs
- `--input` one or more CSVs with `Company Name`, `Industry`, `Keywords`, `Company Short Description`,
  `Company SEO Description`, `Headline`, `Title` (Apollo-style export; missing columns are skipped).
- `--outdir`; `--threshold` noul cut (default 0.5); `--workers` (8); `--limit N` for a test run.
- Env `OPENROUTER_API_KEY` (cloud alias `OPENROUTER_API_TOEKN` picked up automatically).

## Tools/Scripts
`execution/modules/jev_client.py` (`decide_many`). One Jev call per unique company (cached across files).

## Steps
1. Build a state per company from the seven text fields (each capped at 1,200 chars).
2. Ask two questions in one call: `category` (choice: staffing_recruiting / hr_consulting / hr_tech /
   other_consulting / other) and `on_target` (noul: is this a services business paid to find people or run HR).
3. Row is on-target when `on_target >= threshold` AND category is staffing_recruiting or hr_consulting.
4. Write `{stem}.csv` (on-target) and `{stem}__off_target.csv` (flagged), each with `icp_category`,
   `icp_on_target`, `icp_confidence`, `icp_reason` added. `icp_summary.json` has counts and cost.

## Outputs
Per input file two CSVs in `--outdir`, `icp_summary.json`, one row in `.tmp/jev_ledger.jsonl`.

## Edge Cases
- Jev fails open: on an error the row gets `icp_category=jev_error` and falls back to the Industry tag
  (staffing / recruit / human resources → on-target) so nothing is silently dropped. Check `jev_errors` in the summary.
- Borderline rows sit at p 0.4-0.6 (e.g. talent marketplaces tagged Staffing & Recruiting). Lower the threshold
  to 0.4 for a looser list or review the off-target file sorted by `icp_confidence` desc.
- Cost: about $0.04 per 1,000 companies; ~2 min per 1,000 at 8 workers.

## Run log
- 2026-10-13 Bay Area recruitment list, 1,895 rows / 1,731 companies, threshold 0.5. Spot-check of 60 SF rows:
  IT-tagged staffing firms kept, HR SaaS / VC / research flagged out; no obvious misses.
