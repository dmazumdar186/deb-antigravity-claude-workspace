# LeadOcean Leads (AI Proposal Engine campaign)

## Goal
Build a cold-email-ready list for the "AI Proposal Engine" offer (turn briefs/RFPs/takeoffs into client-ready
proposals fast) across three niches: event production/AV, commercial interior fit-out, incentive travel/DMC.
Bounce rate is the top priority: only LeadOcean-`verified` work emails on the company's own domain with a live MX
record reach the main CSV. Each lead gets a Jev ICP check, a scraped company summary/fact list and, where the site
supports it, a checkable one-line icebreaker.

**Output contract:** one Instantly-ready CSV (columns below), a rejects CSV with a `reject_reason`, and a short
`summary.json`. No uploads to Instantly, no campaign creation.

## Inputs
- `.env` / environment: `LEADOCEAN_API_KEY` (never print it), `OPENROUTER_API_KEY` (cloud alias
  `OPENROUTER_API_TOEKN`), `SERPER_API_KEY` (optional site fallback).
- Targeting lives in the script (`NICHES`, `M`): allocation AV 1,350 / fit-out 1,050 / DMC 600; headcount 11-200
  (DMC 5-200); 2 contacts max per company; playbook metros per niche (London capped at 10% AV, 15% fit-out).
- Python deps: `requests`, `python-dotenv`, `beautifulsoup4`, `openai` (llm_client). No dnspython needed.

## Tools/Scripts
`execution/lead_sourcing/leadocean_leads.py` — subcommands, each idempotent and resumable (caches in `.tmp/leadocean/`):

| Step | Command | What it does | Cost |
|---|---|---|---|
| 1 | `count` | free sizing per niche x metro (`count=true&limit=1`) -> `counts.json` | free |
| 2 | `export [--plan-only] [--budget N] [--only k] [--sample N]` | plan rows per cell (`export_plan.json`), POST /v1/exports, poll, download to `raw/` | 1 record/row |
| 2b | `topup [--budget N] [--plan-only]` | leftover rows, company-first: company search (keywords + HQ + size + `hasMailableContacts`), Jev on the company DESCRIPTION, free per-domain count, export the ICP domains with the fewest contacts first | company search bills records (paced); export 1/row |
| 3+4 | `gate [--limit N]` | hygiene (status, free-mail, role, domain match, MX via DoH, dedupe, 2/company) then Jev ICP check per company -> `gate.json` | Jev ~$0.00003/company |
| 5 | `enrich [--limit N]` | homepage + up to 4 of about/projects/work/portfolio/case-studies/services; Serper `site:` fallback -> `sites/`, `enrich.json` | Serper only on empty sites |
| 6 | `icebreak [--limit N]` | Sonnet 5.5 (effort low) JSON line per person, deterministic validator -> `icebreak.json` | ~$0.0035/lead |
| 7 | `build` | `prodcraft_leads_YYYY-MM-DD.csv`, `rejects.csv`, `summary.json` | free |

Always run a step with `--limit 20` (or `export --sample 30`) before scaling.

## Outputs
- `.tmp/leadocean/prodcraft_leads_YYYY-MM-DD.csv`: email, first_name, last_name, title, company_name,
  company_domain, website, niche, metro, city, state, country, employees, linkedin_url, email_status,
  email_verified_date, jev_niche_conf, jev_fit_score, company_summary, site_facts, project_reference, icebreaker,
  personalization_status, source.
- `.tmp/leadocean/rejects.csv`, `.tmp/leadocean/summary.json`. Lead data is never committed.

## Steps
1. `count` — size every niche x metro for free; read `unsupported` and adjust filters until it is empty.
2. `export --plan-only` — review `export_plan.json` (rows per cell vs. budget).
3. `export --only <one cell> --sample 30` — inspect the sample CSV (statuses, domains, off-niche share).
4. `gate --limit 20`, `enrich --limit 20`, `icebreak --limit 20` — eyeball the outputs and failure counters.
5. `export --budget <rows left today>` — run the rest of the plan (background; it polls and downloads).
6. `topup` — if rows are left today, spend them company-first (step 2b).
7. `gate` — hygiene + Jev over everything downloaded.
8. `enrich` — scrape every kept company.
9. `icebreak` — one line per kept person.
10. `build` — write the CSVs and summary; report counts, rejects by reason, cost.

### Gates
- **Email:** primary = first numbered email of type `work`. Accept status `verified` only. `catch_all`,
  `catch_all_valid` (search filter returns 0 of them anyway), `untested`, `unknown`, `risky`, `role`, `derived` -> rejects.
  Email domain must equal the company domain (or subdomain / same base label); free-mail and role locals
  (info@, sales@, events2@ ...) rejected. MX must exist (null MX "0 ." counts as none). No SMTP probing.
- **Jev:** one `decide` per company: `niche` choice {av, fitout, dmc, none} + `fit` noul (B2B, writes custom
  proposals/bids for corporate projects). Drop when Jev picks another niche with confidence >= 0.6 or fit < 0.4;
  keep but flag `jev_borderline` when the niche disagrees at lower confidence or fit < 0.6; Jev error -> keep,
  flag `jev_unchecked`. Flags ride in the `source` column.
- **Site veto (Jev pass 2):** `enrich` re-asks the same Jev questions with the scraped site summary + facts.
  `build` drops the company (`jev_site_offniche`) when that pass says `none` at confidence >= 0.7 with fit < 0.5,
  or fit < 0.25. Catches wedding florists, home builders, venues and limo firms that LinkedIn data hid.
- **Icebreaker validator:** <= 20 words, conf >= 0.7, no dashes/questions/banned filler, and `project_reference`
  must appear verbatim in the scraped text AND inside the line. One repair call on format slips (length, dash,
  filler, reference missing from the line). Otherwise blank + `template_only`. Low confidence is never repaired:
  a site with only service-line copy stays `template_only` by design.

## Edge Cases
### API limits learned (2026-11-02)
- Sizing is free and fast (~0.6 s); `facets=true` on a sizing call is also free and shows the industry mix,
  which is how the noise industries were found.
- `companyKeywords` is dropped (listed in `meta.unsupportedFilters`) when the employer set after HQ/size/industry
  filters exceeds 50,000 companies, e.g. AV keywords US-wide. Always check `unsupported` before trusting a count.
- Multiple values inside a filter OR; filters AND. People `excludeKeywords` is the PERSON's profile text, not the
  employer's; use `excludeIndustry` / `excludeCompanyName` to cut employers.
- `emailStatus=verified` in search is an upper bound (search applies the older wide rule); the export's
  `email_N_status` is the per-address truth. Sample: 30/30 exported rows had `email_1_status=verified`.
- `catch_all_valid` as a search filter returned 0 everywhere.
- Exports are NOT deduplicated in practice: the 2026-11-02 DMC export held 1,578 rows for 1,270 person_ids
  (the same person repeated up to 8x), all billed. Expect ~20% duplicate rows; hygiene dedupes by email + person.
- Yield on 2026-11-02 (keyword-first exports, 4,344 rows): 1,157 duplicate rows, 1,144 over the 2-per-company
  cap, ~470 non-verified per-address status, 423 email domain != company domain, then Jev dropped ~1,140 off-niche
  rows (breweries, schools, limo firms, hotels matched by "staging"/"corporate events"/"group travel"). ~460 leads
  survived (~11%). Company-first (`topup`) gates on the description before spending export rows.
- Company search is fair-use paced once the 5-hour search window is spent: ~1 page/min, so `topup` over
  ~20 metro cells takes ~45 min. Run it in the background.
- Exports: 5,000 rows/day, `maxRows` 5,000, run one at a time per account (others queue), bill per row written.
  Rows are deduplicated per export only, so overlapping exports re-bill the same person.
- Verified-work pools are small: decision-makers (seniority owner/founder/c_suite/partner/vp/director) with a
  verified work email in the playbook metros were ~1,300 AV rows (~420 companies incl. London), ~1,250 fit-out
  (~400 companies), ~310 DMC in metros (~117 companies) / ~1,580 DMC US-wide (~570 companies). The 2-per-company
  cap is the biggest attrition after the Jev gate.
- Bare "fit out"/"fit-out" keywords match fitness and apparel brands; use construction phrases plus a construction
  industry list. AV keywords ("staging", "experiential", "corporate events") pull in restaurants, schools and
  breweries; the `NOISE_INDUSTRIES` exclude list plus Jev handle it.

### Other
- Cloud sandbox: the local DNS resolver answers NoAnswer for real MX records, so MX uses DNS-over-HTTPS
  (Google, then Cloudflare). Plain-HTTP fetches time out through the proxy; sites are fetched over HTTPS only.
- JS-only sites return no text: Serper `site:<domain>` snippets (same-domain hits only) are the fallback; source
  column gets `site_serper`.
- DMC is exported US-wide (playbook metros too thin) and labelled back to a playbook metro by the contact's
  city/state; everything else is "US (other)".
- London share caps are applied against the niche ALLOCATION (AV <= 135, fit-out <= 157), not the final count.
- Jev reassigns (flag `jev_reassigned`) when it picks another target niche with confidence >= 0.6 and fit >= 0.6,
  e.g. "Ladidadi Events & Incentives" found by AV keywords becomes a DMC lead instead of a reject.
- Re-running a step only processes new items. To redo a step, delete its cache file (`gate.json`/`jev_cache.json`,
  `enrich.json` + `sites/`, `icebreak.json`).

## Exit Criteria
- `summary.json` written; every exported row is either in the leads CSV or in `rejects.csv` with a reason.
- Leads CSV holds only `email_status=verified` work emails on the company domain with a live MX, max 2 per company.
- Report: counts per niche/metro vs. allocation, rejects by reason, % with icebreaker, LeadOcean rows used,
  Jev + LLM cost, and why any shortfall against ~3,000 happened (pool sizes, verified yield).
