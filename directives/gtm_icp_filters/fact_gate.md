# Fact Gate (reliability layer for prospect-trigger claims)

## Goal

Nothing a finder says about a prospect reaches outward text unless the gate has re-proved it from a primary source,
with its own fetch and its own matcher. Every claim is PASS (with evidence URL + quote) or dropped (FALSE /
UNVERIFIABLE / UNSUPPORTED, with reason + evidence quote). Fail closed: unreachable means dropped. Rows render only
from passed claims, and a row needs its trigger claim passed.

Born 2026-11-20: a blind fact check of 48 finder claims scored 43 correct (one-sided 90% Clopper-Pearson lower bound
0.837 < 0.90 bar). Public-record facts were perfect; all 4 errors were "homepage doesn't mention X" claims that were
false because X sat in a registered-mark spelling (`Name(R)-C`), an agency acronym (`USCG`), a product-family name, a
hidden dropdown menu or a linked page. The finder only read the visible homepage text.

## Inputs

`--claims` CSV, one row per claim:
`claim_id,row_id,company,domain,claim_type,k_number,award_id,product,agency,date,year,claim_text`
(`date` ISO `YYYY-MM-DD`; extra columns are carried through). `row_id` groups the claims of one finder row.

| claim_type | needs | re-derived from | PASS when |
|---|---|---|---|
| `fda_clearance` | k_number (K or DEN number; a DEN described as "510(k)"/"clearance" is FALSE), company, product, date | openFDA `device/510k.json?search=k_number:` | applicant name score >= 0.80, device_name covers >= 80% of product tokens and every distinctive one, decision_date == date |
| `federal_award` | award_id, company, agency, date | USAspending `spending_by_award` (award_ids) + `/awards/{generated_id}/` | a recipient of that id scores >= 0.80 (shared PIIDs: best-matching recipient), agency named in toptier/subtier/office (aliases + acronyms), `date_signed` == date ("awarded on") |
| `site_copyright` | domain, year | fresh Chromium render (`fact_gate_render.js`) | newest year in the copyright line (ranges -> newest) == year |
| `site_viewport_missing` | domain | rendered DOM + raw HTML with desktop and mobile UA | no `<meta name=viewport>` anywhere |
| `site_not_mention` | domain, product or agency | home (visible text, hidden menu text, link texts + slugs, image alt/title/src) + sitemap URL slugs + up to `--max-pages` pages (nav/footer links first, then other home links, then sitemap pages ranked by relevance) | no distinctive token found anywhere |

Anything else (e.g. company descriptions) -> UNSUPPORTED, dropped.

**What counts as a mention.** Product: every token that is not a generic category/anatomy word (the `GENERIC` set),
not the company's own name, not a bare number; hyphenated brands also match their stem (`Name-C` -> `Name`), marks
(R)/(TM) are stripped, hyphen/space are interchangeable. So a product-family name counts. Agency: the agency phrase,
its alias list (`AGENCY_ALIASES`, e.g. Coast Guard -> `USCG`, Public Buildings Service -> `GSA`) and its 3+ word
acronym; 2-4 letter acronyms are case-sensitive so `gsap` CSS never matches `GSA`.

**Claim-text consistency.** A K number or `Month D` date in `claim_text` that disagrees with the structured fields ->
FALSE before any fetch (the text is what ships, the fields are what gets checked).

## Tools/Scripts

- `execution/gtm_icp_filters/fact_gate.py` (driver + checks; no LLM, no spend)
- `execution/gtm_icp_filters/fact_gate_render.js` (Node Playwright render; deliberately separate from the finder's
  `site_marker_fetch.js`)
- `tests/test_fact_gate.py` (offline fake-fetcher tests for every failure mode + a live regression test over a
  labelled CSV kept in the client repo, passed via `FACT_GATE_REGRESSION_CSV`)

## Steps

```bash
python3 execution/gtm_icp_filters/fact_gate.py --claims <claims.csv> --out .tmp/fact_gate/<run>
python3 execution/gtm_icp_filters/fact_gate.py --claims <claims.csv> --limit 5        # smoke
python3 execution/gtm_icp_filters/fact_gate.py --claims <claims.csv> --offline        # cache only
python3 -m pytest tests/test_fact_gate.py -q
FACT_GATE_REGRESSION_CSV=<labelled.csv> python3 -m pytest tests/test_fact_gate.py -q -k live
```

Then render outward text ONLY from `<out>/rows.csv` (or `pass.csv`).

## Outputs

`<out>/pass.csv` (claim + `evidence_url` + `evidence_quote`), `<out>/reject.csv` (+ `verdict`, `reason`),
`<out>/rows.csv` (rows built from passed claims; a row whose trigger failed is gone), `<out>/summary.json`.
Fetch cache `.tmp/fact_gate/cache/{http,post,render}/` (failures are never cached, so a re-run retries them).

## Floors and ceilings

- Name match floor 0.80; product token cover floor 0.80; home text floor 200 chars (else UNVERIFIABLE); bot-wall
  pages UNVERIFIABLE.
- `--max-pages` in [1, 40] (default 25); <= 6 sitemap files, <= 5,000 sitemap URLs per site.
- Run alarms (n >= 20 claims): > 50% UNVERIFIABLE -> exit 2 (fetch layer broken); 0 rejects -> exit 3 (a gate that
  drops nothing is not gating).

## Edge Cases

- Shared PIIDs (one task-order id across several IDIQ holders): the recipient that matches the company is used.
- `date_signed` can differ from the finder's Mod-0 `action_date`; the gate checks `date_signed` ("awarded on").
- JS-injected copyright years (`new Date()`) show the current year in the render -> stale-year claim FALSE.
- A product word that is also English (e.g. a brand like `Vantage`) still counts: precision over yield.
- Repo is public: no company names, K numbers or award ids in this directive, the code or the tests. Labelled
  fixtures live in the client repo.

## Output contract

Read-only. Two CSVs + rows CSV + summary JSON. Every reject has a reason; every PASS has an evidence URL and quote.
No sends, no paid calls.

## Learnings

- 2026-11-20: the four historical false "not mention" claims are all caught (regression CSV in the client repo);
  `sources/evidence/2026-11-20/` for the re-run measurement and yield cost.
