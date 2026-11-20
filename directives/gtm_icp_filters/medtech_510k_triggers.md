# Medtech FDA 510(k) Triggers (finder + blind verifier)

## Goal

Give a cold email to a US medtech company one dated, checkable opener (a recent FDA 510(k) clearance) and one hard,
checkable fact about the company's own website. Hard facts only; never interpretive judgements ("looks dated").

## Inputs

- `--companies` CSV: `company,domain,website[,city,state,vertical]`. Rows filtered to `--vertical` (default
  `medtech`) when the column exists. Production file: `.tmp/referral/leads/icp_companies.csv`.
- `--since` (default `2026-08-01`). `--controls <json>`: gitignored fixture `{k_number: label}` of positive
  controls (the repo is public: no company names, K numbers or test CSVs in `execution/` or `directives/`).

## Tools/Scripts

See command below.

## Steps

`python3 execution/gtm_icp_filters/medtech_510k_triggers.py --companies <csv> [--controls .tmp/referral/triggers/controls.json]`
Browser work runs through `execution/gtm_icp_filters/site_marker_fetch.js` (Node Playwright is the installed binding;
the Python package is not).

1. **Pull**: every openFDA 510(k) decision with `decision_date` in [since, today] and `country_code:US`, paged with
   skip/limit 1000; exits if rows != `meta.results.total`. Cached in `.tmp/referral/triggers/fda_510k_<since>.json`.
2. **Match**: normalized name tokens (Inc/LLC/Corp/punctuation stripped), exact or domain-root == applicant, or
   Jaccard >= 0.8 with state agreement. 0.5-0.8 or a state clash goes to one Jev `choice` (with `none`), conf >= 0.7,
   capped by `--max-jev`, ledgered. No Jev key = ambiguous rows dropped (fail closed).
3. **Site check** (finder): homepage at 1440x900 + iPhone 13 screenshots in `shots/`; markers: copyright year,
   generator meta, viewport meta, device name on homepage, site search (WordPress `?s=`, `/search?q=` etc.).
4. **Pick one fact**, strongest first: search for the device returns nothing > homepage does not mention the device >
   footer copyright <= current year - 2 > versioned generator > no viewport meta.
5. **Blind verifier**: given only company, domain, K number and the claim, re-queries openFDA by K number (date,
   device, US, applicant name) and re-fetches the page (plain HTTP; search claims re-run in a fresh browser with its
   own nonsense baseline). Only agreeing rows reach `medtech_triggers.csv`.

## Outputs

- `.tmp/referral/triggers/medtech_triggers.csv`: one row per company (newest verified clearance):
  `company,domain,k_number,device_name,decision_date,trigger_line,site_fact,site_fact_type,evidence_urls,verified`.
- `medtech_triggers_all.csv`: every match with verifier notes. `cache/<K>_<domain>.json`: per-pair result.

## Edge Cases

- "Search returns nothing" means: the result page text equals a nonsense-query page once both queries are blanked
  AND the query is echoed (proves a search ran). No echo = no search claim.
- Device name: first listed variant, catalog codes / sizes / ®™ removed, ALL-CAPS records title-cased. Otherwise
  verbatim from FDA.
- Idempotent: cached per K number + domain; re-run is a no-op. `--refresh` re-pulls and re-checks.
- `--check`: offline, caches only, no network, no Jev spend.
- Generator meta: a page often carries several (`Elementor`, `Site Kit`, `Yoast` plugin tags beside the CMS);
  `page_markers` prefers the CMS tag (`CMS_GENERATOR`: WordPress, Drupal, Wix, Squarespace, Webflow...) and falls
  back to the first tag only when none is a CMS.
- openFDA lags FDA's own database by ~1-2 weeks (`meta.last_updated`).
- Outward copy using these rows still goes through `/redteam`.
