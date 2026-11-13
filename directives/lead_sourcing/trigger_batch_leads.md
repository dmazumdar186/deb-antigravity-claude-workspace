# Trigger Batch Leads (trigger-first prospect list, by region)

## Goal

Build one batch of cold-email prospects for an agency referral program where every lead carries a dated, checkable
public trigger, a verified homepage fact, and a decision-maker with a verified work email. Count how many leads are
actually WORKABLE and why the rest drop. Region and verticals are arguments so later batches reuse it unchanged.

## Inputs

- `--region west|east|midwest|south|mountain` or `--states CA,OR`; `--verticals medtech,construction`; `--batch NAME`.
- `--since 2026-08-01` (510(k) decision date floor), `--days 90` (federal award window).
- `--drop-list .tmp/referral/leads/drop_list.json` (`{"domains": [], "names": []}`; gitignored, never committed).
- env `LEADOCEAN_API_KEY`, `OPENROUTER_API_KEY` (Jev). Never Reoon, never Instantly.

## Tools/Scripts

`python3 execution/lead_sourcing/trigger_batch_leads.py --region west --batch batch1 [--try-export] [--check]`
Reuses `execution/gtm_icp_filters/medtech_510k_triggers.py` (openFDA pull, `clean_device`, `search_queries`,
`pw_fetch` -> `site_marker_fetch.js`), `execution/gtm_icp_filters/construction_award_triggers.py`,
`execution/lead_sourcing/leadocean_leads.py` (`LeadOcean`, caches), `execution/modules/jev_client.py`.

## Steps (a company must pass every one to be WORKABLE)

1. **Triggers in region**: medtech = newest 510(k) per applicant whose FDA address state is in the region; construction
   = newest original federal award per recipient (see `directives/gtm_icp_filters/construction_award_triggers.md`).
2. **Match to a domain**: LeadOcean `GET /v1/companies/search?name=<normalized name>&hqState=<state>` (US-wide
   fallback; d/b/a names tried separately). One exact normalized name in state = auto; anything else = one Jev
   `choice` over up to 8 candidates plus `none`, accepted at confidence >= 0.7.
3. **Drop list + dedupe**: drop-list domain or normalized name; one trigger per domain (newest wins).
4. **Size + vertical gate**: LeadOcean headcount 20-500 (hard; unknown = drop), then Jev `noul` "real independent
   operating company of 20-500 staff in this vertical" >= 0.6 (drops shells, subsidiaries, universities, government).
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

## Outputs

`.tmp/referral/<batch>/`: `<batch>_medtech.csv` (first_name,last_name,title,email,linkedin,company,website,date,device,
k_number,site_fact,evidence_urls), `<batch>_construction.csv` (... agency,date,amount,award_id,site_fact,evidence_url),
`<batch>_<vertical>_audit.csv` (same + raw device, trigger org, match method, rank), `<batch>_companies.csv` (every
trigger company and its outcome), `funnel.md` (step counts, drop reasons, column fill, LeadOcean usage).
Caches: `.tmp/referral/cache/{match,jev,site,contacts,email}.json`.

## Edge Cases

- **LeadOcean billing**: people search, company search and email lookups each bill one "record" per row/call; the
  plan is fair-use with no ceiling (`records.whenOver: never`), so they cost $0. Exports bill rows against the
  10,000/day quota. People-search rows carry only email FLAGS (`has_email`, `email_status`), never the address.
- **Email outage (2026-11-13)**: every person lookup (`/v2/people/email/work`, `/v1/people/enrich` by person_id) and
  every export returned 503 "Looking a person up by person_id is temporarily unavailable"; enrich by `linkedin_url`
  returned 500. Contacts are still written with blank email; email lookups are cached only on success, so a plain
  re-run fills them when the service recovers. Workable = rows with an email.
- **LinkedIn headcount understates field-heavy firms** (construction crews are rarely on LinkedIn): the 20-500 gate
  drops many real mid-size contractors as "size < 20". Check the drop-reason count before relaxing `MIN_EMP`.
- Idempotent: every stage cached (name+state, domain, trigger id + domain, person id); re-run = no-op. `--check`
  rebuilds outputs offline from caches.
- `company` column: a mixed-case FDA applicant name minus Inc/LLC (the company's own spelling); ALL-CAPS USAspending
  names take the LeadOcean name only when it is the same name (LeadOcean names can be LinkedIn taglines).
- Repo is public: no company, person or client names in this directive or the script; data stays in `.tmp/`.
- Outward copy built from these rows still goes through `/redteam`.
