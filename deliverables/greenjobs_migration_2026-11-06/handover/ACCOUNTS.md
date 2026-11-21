# GreenJobs accounts and services

Handover document (promise P19: everything in GreenJobs-owned accounts). Written 2026-11-21. **Rule:** every account
below is owned by GreenJobs (registered to a GreenJobs email, billed to GreenJobs). ProdCraft holds member access
only, which GreenJobs can remove at any time. Platform costs are as proposed (Cloudflare about $5 and Resend about $20 a
month at cost, billed to GreenJobs; RECORD P14).

"Today" = the repository on 2026-11-21. No credentials, tokens or personal data are recorded here.

## Summary

| # | Account or service | Owner at handover | Today | Done? |
|---|---|---|---|---|
| 1 | Cloudflare account (production) | GreenJobs | Does not exist | **not yet done** |
| 2 | Cloudflare Pages projects `greenjobs-ie`, `greenjobs-uk` | GreenJobs account | Not created | **not yet done** |
| 3 | Cloudflare Workers `greenjobs-platform` | GreenJobs account | Not deployed | **not yet done** |
| 4 | Cloudflare D1 `greenjobs` | GreenJobs account | Not created | **not yet done** |
| 5 | Cloudflare R2 `greenjobs-backups` (and `greenjobs-cvs`, optional) | GreenJobs account | Not created; R2 not enabled on any account | **not yet done** |
| 6 | Cloudflare Access (Zero Trust) | GreenJobs account | Staging only, on ProdCraft's account | **not yet done** for production |
| 7 | Resend (email) | GreenJobs | No sending domain verified; dry-run everywhere | **not yet done** |
| 8 | GA4 and Search Console | GreenJobs (existing) | Existing properties kept; ProdCraft access to be confirmed | partly done |
| 9 | Domain registrars and DNS hosts | GreenJobs | Existing, held by GreenJobs; nameservers not moved | **not yet done** (move) |
| 10 | GitHub repository | GreenJobs organisation | Code is in ProdCraft's workspace repository | **not yet done** |
| 11 | Staging on ProdCraft's account | ProdCraft | Live (test boards, dry-run) | done; to be retired or rebuilt in GreenJobs' account |

## Cloudflare

Source of truth for names: `execution/gtm_client_workflows/greenjobs_redesign/deploy/ENVIRONMENTS.md`,
`deploy/environments.json`, `platform_worker/wrangler.toml`.

### Staging (ProdCraft's Cloudflare account today)

- Workers `greenjobs-platform-staging` (IE) and `greenjobs-platform-staging-uk` (UK), on workers.dev.
- D1 `greenjobs-staging`. Pages `greenjobs-stg-ie`, `greenjobs-stg-uk` (the earlier `greenjobs-staging-ie`/`-uk` are
  retired, left untouched).
- Access: a team domain, application AUD and a smoke-test service token exist on the staging account
  (`wrangler.toml` `[env.staging.vars]`). `ENVIRONMENTS.md` still says Access is not enabled; the `wrangler.toml` values
  are newer.
- R2 is not enabled (API code 10042); the staging Worker needs none.
- Data: public job data and synthetic test applications only. No candidate data on staging.
- At handover: either delete these or leave them with ProdCraft as its own test area; nothing of GreenJobs' is stored
  there. GreenJobs gets a fresh production setup (below). Staging for the long term is **not yet decided**.

### Production (GreenJobs' own account, to be created)

Who creates it was asked of Keith with a default date of Tue 24 Nov 2026 (`rethink_2026-11-20/DECISION.md`); no answer is
recorded in the repo yet.

| Resource | Name | Notes |
|---|---|---|
| Account | (to be created, GreenJobs email) | Two-factor on. ProdCraft invited as a member with only the roles the pipeline needs (Workers, D1, Pages, Access edit); no Billing role |
| Zones | `greenjobs.ie`, `greenjobs.co.uk` | Added to this account before nameservers move (CUTOVER_RUNBOOK path A) |
| Pages | `greenjobs-ie` (greenjobs.ie), `greenjobs-uk` (greenjobs.co.uk) | |
| Worker | `greenjobs-platform`, routes `/api/*` and `/admin*` on both zones | `wrangler.toml` `[env.production]` |
| D1 | `greenjobs` | `REPLACE_WITH_PRODUCTION_D1_ID` still a placeholder |
| R2 | `greenjobs-backups` (daily D1 exports, lifecycle rule); `greenjobs-cvs` only if CV storage is switched on | CVs are attached to the email, not stored (`CV_STORAGE=attach`), so `greenjobs-cvs` is optional. R2 is still needed for backups |
| Access | Self-hosted application on `/admin*` and `/api/admin/*` of both domains; allow policy = staff emails | Free tier, up to 50 users. Production `ACCESS_TEAM_DOMAIN`, `ACCESS_AUD`, `STAFF_EMAILS` are empty today |
| API token | One scoped token for the pipeline (Workers Scripts, D1, Pages, R2 edit on this account) | Stored as GitHub environment secrets, section below |

## Secrets and where they live

Names only (full list with users: `deploy/ENVIRONMENTS.md`). Values are never in the repository.

- GitHub environment `staging`: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `GREENJOBS_STAGING_ACCESS_CLIENT_ID`,
  `GREENJOBS_STAGING_ACCESS_CLIENT_SECRET`, `GREENJOBS_STAGING_BUILD_TOKEN`.
- GitHub environment `production` (required reviewer, branch `main` only): `GREENJOBS_PROD_CLOUDFLARE_API_TOKEN`,
  `GREENJOBS_PROD_CLOUDFLARE_ACCOUNT_ID`, optional `GREENJOBS_PROD_BUILD_TOKEN`, `GREENJOBS_PROD_ACCESS_CLIENT_ID`,
  `GREENJOBS_PROD_ACCESS_CLIENT_SECRET`.
- Worker secrets (set with `wrangler secret put`): `BUILD_TOKEN`, `RESEND_API_KEY`, `LIST_MAIL_SIGNING_KEY`.
- Ops machine environment: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `RESEND_API_KEY`, `OPS_MAIL_FROM`,
  `OPS_ALERT_EMAIL`, `DIANA_EMAIL`, `GJ_BACKUP_BUCKET`.
- State today: the staging set is held by ProdCraft. The production set does not exist. At handover GreenJobs holds the
  production secrets and a password manager entry for each account; ProdCraft's copies of staging secrets are rotated
  (RUNBOOK section 9).

## Resend

- Account owned by GreenJobs; sending domain verified on a sender subdomain (for example `mail.greenjobs.ie`,
  `mail.greenjobs.co.uk`) so the apex SPF for the mailboxes is not edited (CUTOVER_RUNBOOK T-2).
- Today: **not yet done**. All Workers run `MAIL_PROVIDER="none"` or `DRY_RUN="1"`; no mail is sent. Who opens the account
  was asked of Keith with a default date of Tue 24 Nov.
- Used for: application email, job alerts and newsletter (both off), ops alerts.

## GA4 and Search Console

- GA4 properties for both boards exist and are kept (RECORD P24); measurement IDs are in the cutover runbook
  (`build/CUTOVER_RUNBOOK.md` switch-day row 11:30). They are public page tags, not secrets.
- The Worker adds the tag on production hosts only; staging is `analytics: "off"`.
- Search Console properties for both domains: ownership stays with GreenJobs; ProdCraft needs delegated (not owner)
  access to resubmit sitemaps. Access status is the answer to Keith's question Q11 and is **not yet recorded** in the repo.

## Domains, registrars, DNS

From the 2026-11-20 inventory (`build/dns/zone_inventory_2026-11-20.json`, read-only lookups). Registrations and DNS
logins are held by GreenJobs / its current providers; ProdCraft does not hold them.

- `greenjobs.ie`: DNS at Hosting Ireland (nameservers `ns1-ns4.webhostingireland.*`). Registrar not returned by the
  registry lookup (HTTP 404); confirm with Diana. Guide: `deliverables/greenjobs_migration_2026-11-06/guides/hosting_ireland.md`.
- `greenjobs.co.uk`: registrar Team Blue Internet Services IE Limited, nameservers `ns5-ns7.dnsireland.*`.
- Network domains (`conservationjobsuk.com`, `ecologyjobsuk.com`, `environmentaljobsuk.com`, `renewableenergyjobsuk.com`,
  `windjobsuk.com`, `solarjobsuk.com`, `wastejobsuk.com`, `waterjobsuk.com`; `renewablejobsuk.com` does not exist):
  optional and quoted separately (P12). Some are at 123-Reg (guide: `guides/123reg.md`; also `guides/letshost.md`).
- Nameservers move to GreenJobs' Cloudflare account on Mon 30 Nov at the earliest (CUTOVER_RUNBOOK path A):
  **not yet done**. Registrar logins stay with GreenJobs; a recovery address is added first.
- Owner rule: every domain must be registered to GreenJobs. Confirm for each registrar (not yet confirmed in the repo).

## GitHub repository

Owner must be a GreenJobs organisation or account, private. Today the code is in ProdCraft's workspace repository.
Move steps and what is included: SOURCE.md. **not yet done.** GitHub environments `staging`/`production`, the variable
`GREENJOBS_STAGING_READY` and the secrets above are recreated in the new repository.

## Strategies (outgoing)

Strategies' contract ends Sun 6 Dec 2026. Final exports go to GreenJobs' own storage only, never the repository
(`strategies_export_bot.py` directive; a dedicated one-time login, reset afterwards). Export archive in GreenJobs' name
(P16) is **not yet done** (waits for the data-processing agreement).

## Handover checklist

1. GreenJobs creates the Cloudflare account and invites ProdCraft as a member (not owner).
2. GreenJobs creates the Resend account and verifies the sending domain.
3. GreenJobs creates the GitHub organisation and the private repository; ProdCraft pushes the code (SOURCE.md).
4. Production resources created through the pipeline files above; D1 id and Access values written to `wrangler.toml`.
5. Secrets set by name in GitHub and Cloudflare (RUNBOOK section 9).
6. Zones added, nameservers moved (CUTOVER_RUNBOOK), GA4 and Search Console access confirmed.
7. ProdCraft's staging account is separated: its secrets rotated, its copy of data deleted.
