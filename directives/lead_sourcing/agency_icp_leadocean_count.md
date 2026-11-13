# Agency ICP LeadOcean sizing

## Goal
Size the LeadOcean pool for a cold email campaign booking calls for a brand + web agency partner
(typical $50k-$200k rebrand + website) before any spend: people and distinct companies per vertical x geography x
decision-maker title group, and what an export of each cell would cost.

**Output contract:** one JSON (`cells`, `totals`, `account`, `config`) and a Markdown table beside it. Counts only;
no rows exported, no Reoon / OpenRouter / Instantly calls.

## Inputs
- env `LEADOCEAN_API_KEY` (never printed).
- ICP (the partner's proven verticals from its public case studies), held in the script: `VERTICALS` (medtech, construction,
  finserv, consumer, profservices), `GEOS` (US, California, San Diego county via `SD_CITIES`), `TITLE_GROUPS`
  (exec: CEO/Founder/President/Owner; marketing: CMO / VP or Head of Marketing), size 20-500 employees.

## Tools/Scripts
`execution/lead_sourcing/agency_icp_leadocean_count.py [--out PATH] [--refresh] [--only v1,v2]` reuses
`leadocean_leads.LeadOcean`. Per cell it makes three free counts: `any` contact, `verified` work email,
`verified_untested` work email (the Reoon-needed wave-2 pool).

## Outputs
- `.tmp/referral/icp_counts.json` (default `--out`, relative to the repo root) and `icp_counts.md`.

## Steps
1. Run the script (about 90 free calls, a few minutes; cached per cell, so a re-run only fills gaps).
2. Read `unsupported` in the table footer; an entry means LeadOcean dropped a filter and that cell is inflated.
3. Pick the cells to export; export cost = the people count of the chosen pool (1 record per row).
4. Exports go through `leadocean_leads.py`-style plans with a budget, never from this script.

## Edge Cases
- `GET /v1/people/search?count=true&limit=1` returns `meta.credits: 0` (free); `facets=true` is also free.
- `industry` is an exact match on LinkedIn industry names; read names from facets. US contractors are mostly
  tagged `Construction` (132k people) and rarely `Specialty Trade Contractors` (566).
- Filter lists are comma-joined in GET params, so a comma inside a value ("Vice President, Marketing") splits it
  into a loose "Marketing" term (22.9k vs ~0.7k people). The script rejects commas in values.
- Title values match as phrases ("CEO" 2,993, "VP Marketing" 103 at US medical-equipment 20-500), but "Owner"
  (5,039) and "President" are loose at non-owner-led firms; treat exec counts as upper bounds and plan rows on the
  `@2/co` column.
- `companyKeywords` without an industry list across the whole US timed out (5xx retries); always pair keywords
  with an industry list.
- Account (2026-11-12): AppSumo tier-2, records ceiling none (`whenOver: never`, fair use), exports 10,000 rows/day
  (was 5,000 on 2026-11-02).
- `hqState=CA` is dropped (`unsupportedFilters`) for the `Construction` industry at every size band; `hqState` +
  `hqCity` works, so CA construction is summed over `CA_CITIES` in chunks (hqCity max 50 values, HTTP 400 above)
  and flagged as a metro lower bound.
- Exports re-bill a person who appears in two overlapping exports (verticals overlap on Pharmaceutical
  Manufacturing and Civil Engineering); export per vertical with `excludeViewed` or dedupe by domain.

## Export (`export` subcommand)
`python3 execution/lead_sourcing/agency_icp_leadocean_count.py export [--plan-only] [--budget 6000] [--rebuild] [--sample N]`

Exports medtech then construction (US, verified work email, exec + marketing title groups) using the SAME
`cell_filters(vertical, "us", group, "verified")` as the count, via the bulk-export endpoint from `leadocean_leads.py`.
- **Flow:** free counts again, print the export quota (`GET /v1/account` -> `exports.day` limit/used), build the
  plan (marketing group first per vertical, medtech first overall; construction gets budget left after medtech),
  `--plan-only` stops there. Otherwise queue jobs, poll, download, then build outputs.
- **Budget:** hard cap `--budget` rows over all ledgered jobs (exports bill 1 record per row; no Reoon/paid verification).
- **Idempotent:** `.tmp/referral/leads/export_ledger.json` keys each job by vertical:group:hash(filters). A re-run reuses
  or downloads ledgered jobs and never re-queues them; only `failed`/`cancelled` jobs (billed 0) are re-queued.
  Outputs are rebuilt deterministically from `.tmp/referral/leads/raw/*.csv`; people deduped by email.
- **Per-company cap:** 2 contacts per domain, ranked CEO/President/Owner/Founder, then CMO/VP Marketing/Marketing
  Director, then other execs. Exports cannot cap per company server-side, so raw rows exceed the post-cap rows.
- **Drops:** `.tmp/referral/leads/drop_list.json` (`{"domains": [...], "names": [...]}`, gitignored; never commit it)
  matched by domain and normalized company name. A company in both verticals stays in medtech.
- **Outputs (`.tmp/referral/leads/`, never committed):** `icp_medtech.csv`, `icp_construction.csv`
  (first_name,last_name,title,email,company,domain,website,city,state,employees,linkedin,vertical),
  `icp_companies.csv` (company,domain,website,city,state,employees,vertical,contacts).
- **Edge cases:** exports can fail server-side with "Looking a person up by person_id is temporarily unavailable"
  (status `failed`, billed 0; observed 2026-11-13, persisted 10+ min) - re-run later. Owner/President titles match
  loosely; CA construction `hqState` filter is dropped (export is US-wide, so unaffected); `--sample N` prints N
  random rows per vertical for a manual mis-vertical read.
