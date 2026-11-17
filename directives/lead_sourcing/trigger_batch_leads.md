# Trigger Batch Leads (trigger-first prospect list, by region)

## Goal

Build one batch of cold-email prospects for an agency referral program where every lead carries a dated, checkable
public trigger, a verified homepage fact, and a decision-maker with a verified work email. Count how many leads are
actually WORKABLE and why the rest drop. Region and verticals are arguments so later batches reuse it unchanged.

## Inputs

- `--region west|east|midwest|south|mountain` or `--states CA,OR`; `--verticals medtech,construction`; `--batch NAME`.
- `--since 2026-08-01` (510(k) decision date floor), `--days 90` (federal award window).
- Size: `--min-emp medtech=20,construction=10` (per-vertical floor), `--max-emp 500`, `--apollo-below 10` (second
  opinion when LinkedIn staff is below this or missing; 0 = never), `--max-apollo 300` (calls per run).
- Discovery: `--discover on|off` (web domain discovery for names LeadOcean cannot match), `--max-serper 300`.
- `--drop-list .tmp/referral/leads/drop_list.json` (`{"domains": [], "names": []}`; gitignored, never committed).
- env `LEADOCEAN_API_KEY`, `OPENROUTER_API_KEY` (Jev), optional `SERPER_API_KEY` (else DuckDuckGo HTML). Apollo
  goes through the proxy (header `X-Api-Key: proxy-injected`). Never Reoon, Prospeo, Instantly or any paid source.

## Tools/Scripts

`python3 execution/lead_sourcing/trigger_batch_leads.py --region west --batch batch1 [--try-export] [--check]`
Reuses `execution/gtm_icp_filters/medtech_510k_triggers.py` (openFDA pull, `clean_device`, `search_queries`,
`pw_fetch` -> `site_marker_fetch.js`), `execution/gtm_icp_filters/construction_award_triggers.py`,
`execution/lead_sourcing/leadocean_leads.py` (`LeadOcean`, caches), `execution/modules/jev_client.py`.

## Steps (a company must pass every one to be WORKABLE)

1. **Triggers in region**: medtech = newest 510(k) per applicant whose FDA address state is in the region; construction
   = newest original federal award per recipient (see `directives/gtm_icp_filters/construction_award_triggers.md`).
2. **Match to a domain**: LeadOcean `GET /v1/companies/search?name=<normalized name>&hqState=<state>` (US-wide
   fallback; d/b/a names tried separately). One exact normalized name in state = auto; several exact in-state
   records where exactly one has staff > 0 (the rest are LeadOcean stubs with 0 staff and odd domains) and no
   staffed same-name record in another state = auto; anything else = one Jev `choice` over up to 8 candidates plus
   `none`, accepted at confidence >= 0.7.
2b. **Web domain discovery** (names still unmatched): one search `"<name minus Inc/LLC>" <city> <state>` (city from
   the openFDA record, or the USAspending recipient address, cached in `recipient_loc.json`); Serper up to
   `--max-serper`, then DuckDuckGo HTML. Directory/aggregator/.gov hits are skipped; a deeper URL is kept only when the
   domain spells a distinctive name word. Up to 3 candidates are fetched (static, rendered fallback) and kept only if
   the page shows the name or the record's street address; one Jev `choice` (+ `none`, conf >= 0.7) picks the
   official site. LeadOcean `companies/search?domain=` then supplies staff/industry when it knows the domain.
3. **Drop list + dedupe**: drop-list domain or normalized name; one trigger per domain (newest wins).
4. **Size + vertical gate**: LeadOcean (LinkedIn) headcount within the vertical's floor-500 (medtech 20, construction
   10). When LinkedIn is < `--apollo-below` or missing, Apollo `GET /api/v1/organizations/enrich?domain=` (the only
   endpoint the free key allows) supplies `estimated_num_employees`, used only for a US record; the companies CSV
   records `size_source` (linkedin/apollo) and `apollo_flipped`. Then Jev `noul` "real independent operating company
   of <floor>-500 staff in this vertical" >= 0.6 (drops shells, subsidiaries, universities, government).
5. **Site fact (finder + blind verifier)**: the rendered homepage must NOT contain any trigger term (medtech: device
   name, distinctive device words, brand word, K number; construction: award id, agency names). Homepage must render
   >= 200 chars and not redirect to another site. The verifier re-queries the public record (openFDA by K number /
   USAspending award detail: date, device or PIID, applicant or UEI) and re-checks a fresh render plus static HTML.
   Fact text: "the <domain> homepage does not mention the <device>" / "... the <agency> award".
6. **Contacts**: `GET /v1/people/search?domain=<d>&emailStatus=verified&emailType=work&seniority=...`, current employer
   only, ranked CEO/President/Owner/Founder > CMO / VP or Director of Marketing > other exec; non-decision-makers drop.
7. **Email**: `GET /v2/people/email/work?contact_id=<person_id>` per chosen contact (max 2 per company), must be at the
   company domain, deduped by email; one person held twice by LeadOcean (two title records) is kept once. A circuit breaker stops after 5 failures; `--try-export` then tries one
   domain-filtered bulk export (<= 50 domains, ledgered in `.tmp/referral/cache/export_ledger.json`).

8. **Size flag** (homepage fetched once per surviving company, cached in `pages.json`): headcount > 500 from LinkedIn
   or cached Apollo, a ticker (`NASDAQ: X` / `NYSE: X`), an investor-relations link, or "publicly traded" in the
   LeadOcean description = dropped (`--size-flag flag` keeps them, flagged). The size gate alone passes small public
   companies, hence this step. `size_flag` column; soft note "near 500 ceiling" at >= 400 LinkedIn staff.
9. **Title allowlist** (before any email reveal): keep CEO, President, Owner, Founder/Co-founder, Managing
   Partner/Principal, General Manager, COO, CMO, VP/Director/Head of Marketing, Brand, Communications/PR, Business
   Development, Sales at VP level or above. Drop HR/People, Finance/CFO/Accounting/Controller, Compliance, Quality,
   Regulatory/Clinical, R&D, Engineering, CTO/IT/Technology, Operations below COO, Product, safety, estimating,
   former/ex/advisor titles, sales below VP. A title with both an allowed and an excluded word, or a senior title
   outside the list (Regional VP, Chairman, "Director - Trade"), is one cached Jev `choice` (chief_exec / growth_lead
   / senior_general / none, conf >= 0.7, keyed by title text).
10. **One chief executive per company**: 2+ CEO/Chief Executive titles -> fetch the about/leadership/team pages once
   (homepage nav links, else /about, /leadership, /team), keep the one the pages name (near "CEO" wins); else keep
   the higher title rank (Chairman/President & CEO > CEO > Chief Executive) and mark `_exec_check` UNVERIFIED.
   LeadOcean people-search rows carry no job start/end dates, so that fallback is not available.
11. **Cap 2 per company**: best chief exec + best marketing/BD lead first, then the rest by rank.
12. **Role inboxes**: an email whose local part is a role address (info, contact, sales, admin, office, hello,
   marketing, support, team, inquiries, estimating, bids ...) is dropped even with a person's name attached; the next
   allowlisted person takes the slot. Every contact-level drop is counted in funnel "Contact gates".
13. **Display columns**: `company_display` = record name (d/b/a part preferred) recased from the company's own pages
   (O'Neill, VII, LGC; vowel-less ALL-CAPS-record acronyms upper-cased); a homepage og:site_name / <title> / logo-alt
   name replaces it only via a cached Jev `choice` that includes `keep_original` (conf >= 0.7). Person names get the
   pages' spelling when it carries inner capitals (DeBartola), initials fixed (D.J.). `device_display` <= 45 chars
   from the FDA name: leading company word dropped before cutting the tail, word-boundary cut never ending on a
   connector, brand casing from the company's pages, all-lowercase records capitalized; `device_raw` kept.

## Rebuild without redoing network work

`--check --allow-net pages,jev,email --end <window end of the original run>`: triggers, matches, size gate, site
facts and people searches come from caches; only new page fetches, Jev title/display calls and LeadOcean email
reveals for newly chosen contacts go online. `--end` pins the construction award window to the cached pull.

## Outputs

`.tmp/referral/<batch>/`: `<batch>_medtech.csv` (first_name,last_name,title,email,linkedin,company,company_display,website,
date,device,device_display,device_raw,k_number,site_fact,evidence_urls,size_flag), `<batch>_construction.csv` (...,
company_display, ..., agency,date,amount,award_id,site_fact,evidence_url,size_flag),
`<batch>_<vertical>_audit.csv` (same + raw device, trigger org, match method, rank), `<batch>_companies.csv` (every
trigger company and its outcome), `funnel.md` (step counts, drop reasons, column fill, LeadOcean usage).
Caches: `.tmp/referral/cache/{match,jev,site,contacts,email,discover,apollo,recipient_loc,pages}.json`. Funnel adds
domains by source, size by source, Apollo flips, and Serper/DuckDuckGo/Apollo call counts.

## Edge Cases

- **LeadOcean billing**: people search, company search and email lookups each bill one "record" per row/call; the
  plan is fair-use with no ceiling (`records.whenOver: never`), so they cost $0. Exports bill rows against the
  10,000/day quota. People-search rows carry only email FLAGS (`has_email`, `email_status`), never the address.
- **Email outage (2026-11-13)**: every person lookup (`/v2/people/email/work`, `/v1/people/enrich` by person_id) and
  every export returned 503 "Looking a person up by person_id is temporarily unavailable"; enrich by `linkedin_url`
  returned 500. Contacts are still written with blank email; email lookups are cached only on success, so a plain
  re-run fills them when the service recovers. Workable = rows with an email.
- **LinkedIn headcount understates field-heavy firms** (construction crews are rarely on LinkedIn): batch 1 lost ~30
  contractors to "size < 20". Fix (2026-11-16): construction floor 10 plus the Apollo second opinion below 10.
- **Apollo org enrich is domain-keyed and can return a namesake abroad** (a US domain mapped to a foreign firm):
  only US (or country-blank) Apollo records decide size; others are shown as "ignored".
- **About half of USAspending construction recipients are not in LeadOcean by name**: domain discovery is the
  recovery path; every discovered domain still passes the homepage name/address check, Jev, the size gate and
  the site fact, and new rows get a hand-read for wrong-company matches.
- Idempotent: every stage cached (name+state, domain, trigger id + domain, person id); re-run = no-op. `--check`
  rebuilds outputs offline from caches.
- `company` column: a mixed-case FDA applicant name minus Inc/LLC (the company's own spelling); ALL-CAPS USAspending
  names take the LeadOcean name only when it is the same name (LeadOcean names can be LinkedIn taglines).
- Repo is public: no company, person or client names in this directive or the script; data stays in `.tmp/`.
- Outward copy built from these rows still goes through `/redteam`.
