# Import List Leads (operator export -> campaign-ready CSVs)

## Goal
Turn a contact export the operator already owns (Apollo-style CSV) into cold-email CSVs per vertical x state, with
non-personalized merge columns and at most one evidence-backed personalization line per company. Reuses the gates of
`trigger_batch_leads.py` and the triggers of `medtech_510k_triggers.py` / `construction_award_triggers.py`.

**Output contract:** `{vertical}_{STATE}.csv` per target state, `{vertical}_other.csv` (company HQ outside the target
states, incl. non-US HQs), `companies.csv` (every company with its outcome), `funnel.md`. Each CSV < 2 MB (split into
`_partN`). No uploads, no sends.

## Inputs
- `--job VERTICAL:STATES:PATH` (repeatable). Vertical `medtech` or `construction` (industry rules in `INDUSTRY`).
  Required columns: First Name, Last Name, Company Name, Company Domain/Website, Email, Title, Industry, Employees
  Count, Company State/Country/City, Company Market Cap, LinkedIn, Company Short/SEO Description, Keywords, Person ID.
- `--drop-list JSON` `{"domains": [], "names": []}` (gitignored). `--cache-dir` (point at the trigger-batch cache to
  share `jev.json`, `site.json`, `pages.json`).
- env `LEADOCEAN_API_KEY` (people search, fair-use records), `OPENROUTER_API_KEY` (Jev). Nothing paid beyond that.

## Tools/Scripts
`python3 execution/lead_sourcing/import_list_leads.py --job medtech:CA,TX,NY:<csv> --job construction:CA,NY:<csv>
 --out .tmp/<dir> --drop-list <json> --cache-dir <dir> [--copy-to <private repo dir>] [--offline]`
Limits: `--max-fetch` (new homepage fetches), `--max-jev`, `--max-lo` (LeadOcean lookups), `--workers 12`,
`--render-workers 8`. `--offline` rebuilds from caches with zero network (re-run = no-op).
Uses `site_marker_fetch.js` with `no_mobile` + `timeout_ms` (20 s) for rendered confirmation.

## Steps (each drop is counted with its reason in funnel.md)
1. Dedupe by email, then Person ID (else first|last|domain). No company domain -> drop. Drop list (domain or name).
2. Company: `Employees Count` in [min, max] (company-level count); Market Cap present -> public; industry: keep set,
   hard-drop set, everything else one Jev noul on description + keywords (keep >= 0.6; Jev down -> drop, reported).
3. Person: `tb.title_class` (allowlist + Jev for edge titles), `tb.is_role_inbox`, email domain must equal the company
   domain / same root / an address domain printed on the homepage; free-mail dropped. Public listing: ticker on the
   homepage or description, investor-relations link, or a live `investors.`/`ir.` host.
4. Email, verifier mode (default when the input has a `status` column from the operator's email verifier):
   keep `--verifier-keep safe,catch_all` -> `email_check` = status, `email_tier` = safe | catch_all (catch_all goes to a
   separate lower-volume campaign); drop every other status (unknown, invalid, disabled, disposable, role_account,
   spamtrap, inbox_full) and any `is_spamtrap=true`; MX and LeadOcean are skipped. Fallback mode (no verifier column):
   syntax + MX (DNS-over-HTTPS, `has_mx`). Null/undeterminable MX -> drop. Cap 2 per company: best chief exec +
   best growth lead, else next by rank; two CEO titles -> keep the one the company pages name next to "CEO", else the
   higher title rank (`stale second CEO`). Then LeadOcean `GET /v1/people/search?q=<name>&domain=<domain>&limit=5`
   per kept person: `verified` -> `email_check=verified_leadocean`; otherwise `mx_ok`; LeadOcean `catch_all` ->
   `catch_all=yes`. No SMTP probing ever.
5. Personalization per company, first that holds:
   a. Trigger: resolved trigger domain (trigger batch `*_companies.csv`) or exact normalized name + same state; the
      trigger-batch finder + blind verifier must confirm the homepage does not mention it.
   b. Homepage fact, only when the rendered page shows it (and the static page agrees when readable): footer copyright
      year <= `--copyright-max` ("-present" ranges skipped, "2012 2021" reads 2021), CMS generator meta WordPress < 6 /
      Drupal <= 7 / Joomla <= 3, no viewport meta. Evidence = URL + snippet.
   c. Else `personalization_type=none`, `first_line` empty.

## Outputs (columns)
first_name, last_name, email, title, company_display, website, city, state, employees, linkedin, vertical,
email_check, email_tier, personalization_type, first_line, evidence, trigger_date, trigger_subject, trigger_id,
trigger_url. State = company HQ state, else person state.

## Edge Cases
- Titles with a region/territory (EMEA, Middle East, "Western Region", district...) are dropped as regional roles.
- Display: (R)/TM marks dropped, "Acme HG Inc. Acme" merged records cut at the mid legal suffix, O'hara -> O'Hara.
- A homepage that redirects to another domain gives no site fact (the fact would be about another site).
- Bare "Vice President" / "Executive Vice President" / "Senior Vice President" are edge titles; Jev is unsure on them
  (0.25-0.47) so they drop (~730 construction rows on 2026-11-17). Loosen only on the operator's word.
- First run 2026-11-17 (medtech 5,381 rows, construction 6,012): biggest drops are headcount (< 20 and > 500), then
  industry, title and off-domain email. LeadOcean returns `untested` for most of these people; `verified` is rare.
- Copyright years rendered by JS differ from static HTML: a fact is only claimed when the rendered DOM shows it.
- Market cap is blank for some listed companies; the investor-site probe catches them.
- FDA device names can start with "The": stripped before "the {device}".
