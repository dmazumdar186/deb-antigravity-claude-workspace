# Import List Leads (operator export -> campaign-ready CSVs)

## Goal
Turn a contact export the operator already owns (Apollo-style CSV) into cold-email CSVs per vertical x state, with
non-personalized merge columns and at most one evidence-backed personalization line per company. Reuses the gates of
`trigger_batch_leads.py` and the triggers of `medtech_510k_triggers.py` / `construction_award_triggers.py`.

**Output contract:** `{vertical}_{STATE}.csv` per target state, `{vertical}_other.csv` (US company HQ outside the target
states; non-US HQs are dropped), `companies.csv` (every company with its outcome), `funnel.md`. Each CSV < 2 MB (split into
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
`--render-workers 8`, `--max-usd 5` (first-line generation guard). `--offline` rebuilds from caches with zero network (re-run = no-op).
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
4c. US headquarters only (operator 2026-11-17): `Company Country` set and not United States (Puerto Rico counts as
   US) -> dropped from every output, `_other.csv` included. Blank country keeps the row.
4d. Maker / builder fit (operator hand-read 2026-11-17): one Jev call per company on its own description: noul
   (`FIT[vertical]`: medtech = designs/makes its own medical products incl. contract manufacturers, reprocessors,
   O&P fabricators, medical software; construction = builds or manufactures building products) + choice `kind`
   (`FIT_KIND`). Drop when noul < `FIT_MIN` 0.5 unless kind = maker_or_builder (conf >= 0.6), or noul < `FIT_SOFT`
   0.65 and kind names a non-maker (incubator, sales rep / distributor, consultancy / engineering / design / CM,
   VC/PE, union / association, service provider) at conf >= 0.6. Funnel reason = `not a maker / builder: {kind}`.
   Jev down -> company kept (helper fails open), not cached, re-run retries. Cache key `fit2|{vertical}|{domain}`.
4e. `company_casual` (operator 2026-11-17: "Brandon Lever LLC has to be referred to as Brandon Lever only in mails
   and communication"): `casual_candidates()` from the record name: tagline cut ("X - tagline", "X | tagline",
   "X / tagline"; initials before a spelled-out name take the spelled-out name: "BCI (Berkeley Cement, Inc.)" ->
   Berkeley Cement), "X by Parent" -> X, leading "The", legal suffixes (LLC, Inc, Corp, Co., Ltd, LP, PLLC, GmbH,
   AB...) and trailing "&" fragments; generic tail words (Group, Holdings, Services, Solutions, Associates,
   Industries, International, USA, America(s), Technologies) only when the rest stays distinctive (not initials, not
   one plain word); industry words (Construction, Electric, Medical...) are never removed. Bare initials keep
   "& Company" / "Corp" ("MG & Company", "CM Corp"). Casing: the homepage's own spelling of the same letters
   (L.C. -> LC), acronyms the record and site both write upper (WHPM, IBEW), lowercase URL slugs ignored. When the
   rule, the aggressive short form, a homepage name and the display disagree, one Jev choice ("how the company refers
   to itself in short form") picks at conf >= 0.6, never to bare initials or a bare-word short form; else the rule.
   Never a generic fallback. `casual_source` in companies.csv says which won. First names are not casualized.
5. Personalization per company, first that holds (every line names the company as `company_casual`):
   a. Trigger: resolved trigger domain (trigger batch `*_companies.csv`) or exact normalized name + same state; the
      trigger-batch finder + blind verifier must confirm the homepage does not mention it.
   b. Homepage fact, only when the rendered page shows it (and the static page agrees when readable): footer copyright
      year <= `--copyright-max` ("-present" ranges skipped, "2012 2021" reads 2021), CMS generator meta WordPress < 6 /
      Drupal <= 7 / Joomla <= 3, no viewport meta. Evidence = URL + snippet.
   c. Company description (operator decision 2026-11-17, option a): the company's OWN description (export Company
      Short + SEO Description + Keywords; else homepage meta description / og:description, fetched once and cached as
      `home.json[dom].meta`). Generator: subscription bulk tier `claude-sonnet-5-5` effort low (`llm_client.
      _claude_cli_completion(chain=...)`), 25 companies per call, JSON in/out, cached in `desc_line.json` by domain +
      hash(prompt version, display name, description, keywords), so re-runs cost 0. Line: one sentence, 8-22 words,
      opens "Saw that {company_display}" or "Noticed {company_display}" (picked by domain hash), only what the
      company does / makes / builds / where. Gates, in order: deterministic (opener, ASCII, no ?/!, word count,
      one sentence, banned words leading/innovative/premier/top/best/great/impressive/amazing/world-class/trusted/
      need/struggle/grow/scale, every number present in the description), then an independent Jev check (two nouls:
      "every fact is stated in description" >= 0.7, "praise / needs / intent / opinion" <= 0.3). Any fail -> empty +
      `none`. Evidence = source + best-matching description sentence + Jev scores. The generator and Jev see
      `company_display` (cache keys unchanged); the kept line then swaps `company_display` -> `company_casual`
      (substitution only, re-checked by the deterministic rules; a fail is counted `casual swap: ...`). Budget guard `--max-usd` (default 5,
      notional USD the CLI reports; subscription is not billed); one summary row per run in `.tmp/cost_ledger.jsonl`,
      per-call rows in `.tmp/llm_ledger.jsonl`.
   d. Else `personalization_type=none`, `first_line` empty.

## Outputs (columns)
first_name, last_name, email, title, company_display, company_casual, website, city, state, employees, linkedin, vertical,
email_check, email_tier, personalization_type, first_line, evidence, trigger_date, trigger_subject, trigger_id,
trigger_url. State = company HQ state, else person state.

## Edge Cases
- Titles with a region/territory (EMEA, Middle East, "Western Region", district...) are dropped as regional roles.
- Display: (R)/TM marks dropped, "Acme HG Inc. Acme" merged records cut at the mid legal suffix, O'hara -> O'Hara.
- A homepage that redirects to another domain gives no site fact (the fact would be about another site).
- Construction only (operator decision 2026-11-17): bare "Vice President" / "Senior (Sr.) Vice President" / "Executive
  Vice President" / VP / SVP / EVP are kept as `vp_general`, ranked after chief exec and growth leads in the cap-2
  order. A VP title that names a function goes through the normal rule (excluded functions drop; others are edge ->
  Jev). Medtech keeps them as edge titles (Jev unsure 0.25-0.47 -> drop).
- First run 2026-11-17 (medtech 5,381 rows, construction 6,012): biggest drops are headcount (< 20 and > 500), then
  industry, title and off-domain email. LeadOcean returns `untested` for most of these people; `verified` is rare.
- Copyright years rendered by JS differ from static HTML: a fact is only claimed when the rendered DOM shows it.
- Market cap is blank for some listed companies; the investor-site probe catches them.
- FDA device names can start with "The": stripped before "the {device}".
