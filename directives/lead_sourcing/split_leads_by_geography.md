# Split Leads By Geography SOP

## Goal

Take a single scraped-leads CSV export (Apollo, Prospeo, or any vendor with a `Country` column) and split it into one CSV per geography bucket — `us`, `uk`, `australia`, `singapore`, `europe` — while injecting a ready-to-send personalization line into each row. The per-geography files are what get uploaded to a sending tool (Instantly, Smartlead) so each campaign can carry its own timezone, sending window, and copy angle.

## When to use

- A new leads export lands in `Downloads/` and needs to be broken up by region before campaign upload.
- A campaign needs a single region pulled out of a mixed-geography list.
- Any time a lead list needs a first-touch opener column generated deterministically (no LLM call, no API cost).

## Inputs

### CLI args

| Flag | Required | Default | Purpose |
|------|----------|---------|---------|
| `--src PATH` | Yes | — | Source leads CSV. **Pass the path. Never attach the file** — see Edge cases. |
| `--out-dir PATH` | Yes | — | Output directory; created if absent |
| `--country-col NAME` | No | `Country` | Column used for bucketing |
| `--anchor-col NAME` | No | `Seniority` | New column is inserted immediately after this one |
| `--line-col NAME` | No | `Personal Line` | Name of the injected column |
| `--prefix STR` | No | `leads_` | Output filename prefix |
| `--include-unmatched` | No | off | Write unmatched-country rows to `<prefix>other.csv` instead of dropping |
| `--out-encoding ENC` | No | `utf-8-sig` | Output encoding; BOM makes Excel render accents correctly |
| `--quiet` | No | off | Suppress the dropped-country breakdown |

### Required source columns

`First Name`, `Title`, `Company Name`, `Industry`, plus whatever `--country-col` and `--anchor-col` name. Missing columns produce a readable error listing every column actually present, then exit 2.

## Outputs

- `<out-dir>/<prefix><bucket>.csv` — one file per bucket **that has at least one row**. A bucket with zero matching rows produces no file. This is expected, not a failure (see Edge cases).
- Each output carries the full source header with `--line-col` inserted after `--anchor-col`.
- **stdout:** per-bucket row counts, a dropped-country breakdown with counts, and a reconciliation line.

Example personalization line:

```
Hey Sarah, excited to see your work as the Head of Talent at Kingston Barnes, love what you are doing in Staffing & Recruiting.
```

## How to run

```bash
py execution\lead_sourcing\split_leads_by_geography.py ^
  --src "C:\Users\deban\Downloads\Recruitment and Staffing Scraped Leads 12 Aug 26.csv" ^
  --out-dir "C:\Users\deban\Downloads\Recruitment and Staffing 12 Aug 26 - by location"

# See what would be dropped before committing to a split
py execution\lead_sourcing\split_leads_by_geography.py --src leads.csv --out-dir out --include-unmatched
```

## Tools / dependencies

Standard library only (`csv`, `re`, `argparse`, `collections`, `pathlib`). No API keys, no network, no cost. Safe to re-run.

## Edge cases & gotchas

- **NEVER attach the source CSV to a Claude session.** A 2.3 MB lead CSV inlines as ~1,005,000 prompt tokens (lead exports tokenize at ~2.3 chars/token because of emails, URLs and commas) and hard-fails the request before any work begins. Pass `--src` a path. Full rule and exhibit: `~/.claude/rules/no-large-file-attachments.md`.
- **A missing bucket file is normal.** Buckets are only written when they have rows. The 2026-08-12 run produced no `leads_singapore.csv` because the source contained zero Singapore rows. Check the dropped-country breakdown before assuming a bug.
- **Countries are matched exactly, not fuzzily.** `"USA"`, `"U.S."`, or `"United States of America"` will NOT match `"United States"` and will be dropped. The stdout breakdown lists every unmatched value with a count — read it, then either add the variant to `SINGLE_COUNTRY_BUCKETS` / `EUROPE` in the script or re-run with `--include-unmatched`.
- **EUROPE is a curated set, not "everything else."** Non-listed European countries drop. Adding one is a single line in the script.
- **BOM-safe on input.** Source is read `utf-8-sig`, so an Excel "Save As CSV UTF-8" or a BOM'd vendor export will not corrupt the first column name.
- **BOM-emitting on output.** Default `utf-8-sig` so Excel renders accented European names correctly. Pass `--out-encoding utf-8` if a downstream parser rejects the BOM.
- **Ragged rows are padded, not skipped.** Rows with fewer fields than the header are right-padded with empty strings so index lookups cannot raise.
- **Company-name cleanup is heuristic.** `strip_legal_suffix()` removes legal suffixes, parenthetical asides, `|` segments, and " - Tagline" fragments, looping to fixpoint. It is tuned for readable openers, not legal accuracy — spot-check the `Personal Line` column on a sample before sending.

## Exit Criteria

- Exit code 0.
- **Reconciliation holds: `rows_in == rows_kept + rows_dropped`.** The script hard-fails with exit 2 if it does not. Silent row loss on a paid lead list is the failure this gate exists to catch.
- One CSV per non-empty bucket exists in `--out-dir`, each with the source header plus `--line-col` at the correct position.
- Every dropped country appears in the stdout breakdown with a count — no row disappears unreported.
- Sum of output data rows equals source data rows minus reported drops.

Verified 2026-08-12 against `Recruitment and Staffing Scraped Leads 12 Aug 26.csv`: 994 in = 994 kept + 0 dropped; uk 470, us 230, europe 207, australia 87; output byte-identical to the prior hand-run script.

## Changelog

- 2026-08-12: created. Promoted from a throwaway `.tmp/split_recruitment_leads.py` after a session-loss incident (see `~/.claude/rules/no-large-file-attachments.md`). Hardening over the original: argparse instead of hardcoded absolute paths, `utf-8-sig` input so BOM'd exports do not crash, readable missing-column errors instead of a bare `ValueError`, full dropped-country breakdown instead of a truncated 20-row sample, `--include-unmatched` escape hatch, and a hard-failing reconciliation gate. Removed unreachable dead code in `strip_legal_suffix()`.
