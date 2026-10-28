# Infra costs 2026 - French B2B travel agency site (Astro + small admin)

Date checked: 2026-10-28. Prices in USD as published; EUR shown at an assumed ~0.86 EUR/USD (assumption, not sourced). Excl. VAT. "UNVERIFIED" = taken from third-party/aggregator pages, re-check before quoting.

## 1. Recommended stack

| Component | Provider / plan | Monthly cost | Limits relevant to us | Source | Checked |
|---|---|---|---|---|---|
| Static public site | Cloudflare Workers static assets (or Pages Free) | 0 | Static asset requests free and unlimited; Pages Free: 500 builds/mo, 20,000 files, 25 MiB/file, 100 custom domains | https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/ ; https://developers.cloudflare.com/pages/platform/limits/ | 2026-10-28 |
| Admin/API compute (prod + staging) | Cloudflare Workers Paid | $5 (~EUR 4.3) per account | 10M req/mo + 30M CPU-ms included; then $0.30/M req; Free plan = 100k req/day, 10 ms CPU | https://developers.cloudflare.com/workers/platform/pricing/ | 2026-10-28 |
| Database (prod + staging, separate DBs) | Cloudflare D1, jurisdiction EU | included in Workers Paid | Paid: 25B rows read, 50M written, 5 GB incl. Free: 5M reads/day, 100k writes/day, 5 GB. No egress fee | https://developers.cloudflare.com/d1/platform/pricing/ | 2026-10-28 |
| DB point-in-time restore | D1 Time Travel | 0 | 30 days (Paid), 7 days (Free) | https://developers.cloudflare.com/d1/reference/time-travel/ | 2026-10-28 |
| Media + daily dump storage | Cloudflare R2 Standard | 0 at our size (then $0.015/GB-mo) | Free: 10 GB-mo, 1M Class A, 10M Class B ops; egress free | https://developers.cloudflare.com/r2/pricing/ | 2026-10-28 |
| Admin login + MFA, 5 roles | Cloudflare Access (Zero Trust Free) in front of /admin + roles enforced in app | 0 | Free up to 50 users (third-party sources, UNVERIFIED on Cloudflare page); Access limits: 500 apps, 50 IdPs. MFA is enforced via IdP (e.g. Google/Microsoft) or one-time PIN; confirm TOTP requirement in prototype | https://developers.cloudflare.com/cloudflare-one/account-limits/ ; https://zerotrustcost.com/cloudflare-zero-trust-pricing | 2026-10-28 |
| Anti-spam | Cloudflare Turnstile Free | 0 | 20 widgets, unlimited verifications, 10 hostnames/widget | https://developers.cloudflare.com/turnstile/plans/ | 2026-10-28 |
| Analytics | Cloudflare Web Analytics | 0 | Listed as free (cookie-less); not detailed on page fetched | https://www.cloudflare.com/plans/free/ | 2026-10-28 |
| Transactional email (primary) | Brevo Free (Paris) | 0 | 300 emails/day (~9,000/mo), Brevo logo on free plan; Starter ~EUR 7-9/mo removes daily cap; hosting FR/EU (UNVERIFIED, third-party). Check sub-processor list | https://www.brevo.com/products/transactional-email/ | 2026-10-28 |
| Email fallback | Resend Free | 0 | 3,000/mo, 100/day; Pro $20 for 50k. Region choice stated, EU not confirmed on page | https://resend.com/pricing | 2026-10-28 |
| Uptime monitoring | UptimeRobot Free | 0 | 50 monitors, 5-min interval, commercial use allowed, 1 status page; SMS only via paid credits (10 for $3). Solo $12/mo annual | https://uptimerobot.com/pricing/ | 2026-10-28 |
| Backups | Worker cron: D1 export -> R2 (daily) + Time Travel | 0 at our size | Cron triggers run up to 15 min on Workers (see Workers pricing page). Store dumps in a second place (see risks) | https://developers.cloudflare.com/workers/platform/pricing/ | 2026-10-28 |
| DPA / GDPR | Cloudflare Customer DPA | 0 | Includes EU SCCs (Module 2/3) and DPF reliance | https://www.cloudflare.com/cloudflare-customer-dpa/ | 2026-10-28 |
| OpenRouter AI (optional) | pay-per-use | usage-based, est. EUR 5-20/month (own estimate, no published price: ~50 congress pages checked a week, ~200 pages read a month at a few cents each incl. retries, capped monthly; aligned with /questions/ 2026-10-28) | Not researched | n/a | n/a |

Not in table: domain name (~EUR 10-15/year, not researched); Cloudflare Email Routing (free per https://www.cloudflare.com/plans/free/, only for inbound alias forwarding, not for sending).

### Total monthly tool cost
- Low: EUR 0 (everything on free plans; D1 free gives 7-day Time Travel, 100k writes/day; Workers Free 10 ms CPU is tight for an admin app and staging+prod would share limits).
- Expected: about EUR 4.5 (Workers Paid $5) + EUR 0-9 email (Brevo Starter only if the daily cap bites) = EUR 5-15/month; with optional UptimeRobot Solo (~EUR 10): up to ~EUR 25 (the optional AI helper, EUR 5-20, is listed separately on /questions/).
- Staging: a second Worker + D1 + R2 bucket in the same account adds no fixed fee.

## 2. D1 location and GDPR
- Create D1 with `--jurisdiction=eu`: DB runs and stores data only in the EU; must be set at creation, cannot change later; location hints (weur/eeur) are only preferences. Workers (compute) can still execute anywhere unless Regional Services is bought. Source: https://developers.cloudflare.com/d1/configuration/data-location/
- Cloudflare DPA with SCCs and DPF: https://www.cloudflare.com/cloudflare-customer-dpa/ . Cloudflare is a US company (transfer risk is covered by DPF/SCCs, not by EU-only ownership).
- Brevo is a French company; Resend and Postmark are US companies (Postmark free: 100 emails/mo, $15/mo for 10k - https://postmarkapp.com/pricing). Amazon SES: $0.10 per 1,000 outbound (a la carte), eu-* regions selectable; free tier is $200 credits for 6 months - https://aws.amazon.com/ses/pricing/ . At 1,000 mails/mo: Resend free, Brevo free, Postmark about $15, SES about $0.10-0.20.

## 3. Cloudflare SLA and outages
- SLA: the published SLA covers the Business plan only (100% uptime promise, credits capped at one month of fees per 12 months, credits are sole remedy, claim within 5 business days). Enterprise has a separate SLA. Free/Pro: no SLA stated. Workers/D1/R2/Pages on Free/Paid plans: no SLA found in what I fetched (not verified on a dedicated page). Source: https://www.cloudflare.com/business-sla/ ; third-party: https://devhelm.io/sla/cloudflare
- Business plan ~$200-250/mo - not recommended for this budget.
- Major incidents (dates):
  - 2025-06-12: Workers KV / Access / Turnstile / WARP outage ~2h28 (storage backend failure); Access logins failed 100%. https://blog.cloudflare.com/cloudflare-service-outage-june-12-2025/
  - 2025-11-18: Bot Management config file bug, network failed to deliver core traffic ~2h10 (11:20-14:30 UTC), full recovery 17:06 UTC. https://blog.cloudflare.com/fail-small-resilience-plan/
  - 2025-12-05: WAF change, ~25 min (08:47-09:12 UTC), ~28% of HTTP traffic. https://blog.cloudflare.com/5-december-2025-outage/
  - 2026 (UNVERIFIED, aggregator pages; check status page before citing): 2026-02-20 BYOIP prefix withdrawal; 2026-08-07..14 13 incidents incl. R2/DO/KV; 2026-10-20 and 2026-10-22 incidents. https://postmortem.io/companies/cloudflare/ ; https://uptimerobot.com/is-it-down/cloudflare/2026-10-22/
- Takeaway: realistic Cloudflare availability on a shared global platform is below 100%; several multi-hour incidents hit Access (admin login) and KV-dependent products.

## 4. "Zero downtime": what can be promised
(a) Zero-downtime deployments (change management, honest): Pages rollback is instant to any previous successful production deployment, and you can roll forward again (https://developers.cloudflare.com/pages/configuration/rollbacks/). The docs I fetched do not use the word "atomic"; do not promise atomic deploys citing that page. Preview/staging deployments are separate. DB migrations are the real risk: use backward-compatible (expand/contract) migrations, and take a Time Travel bookmark before each.
(b) Availability SLA (outcome, cannot be zero): provider-level SLAs are 100% only on Cloudflare Business with credits as sole remedy; Clever Cloud lists 99.9% standard / 99.99% premium (third-party/competitor page, UNVERIFIED: https://www.clever.cloud/clever-cloud-vs-heroku/); OVHcloud VPS ~99.9% (third-party, UNVERIFIED), managed PostgreSQL up to 99.99% only multi-AZ. Typical French small-provider commitments: 99.5% (~3h39/month allowed) for shared/solo, 99.9% (~43 min/month) for VPS-class; a solo vendor with no on-call and single provider per function commonly commits 99.5%; chained services multiply (five at 99.9% ~ 99.5%) and a margin below measured is advised (https://www.oncoide.fr/sla ; https://www.pandiheberge.com/blog/uptime-99-9-hebergement-web/).

### Recommended contract wording (French original and English)
FR: "Les deploiements de mises a jour sont realises sans interruption de service du site public, avec retour arriere immediat possible. Le site public vitrine vise une disponibilite mensuelle de 99,5 % (objectif de moyens, mesuree par sonde externe toutes les 5 minutes, hors maintenance annoncee 48 h a l'avance, force majeure et defaillance des hebergeurs tiers). Le back-office d'administration et les formulaires visent 99,5 % dans les memes conditions. Aucune garantie de disponibilite de 100 % n'est donnee. Prise en compte des incidents en jours ouvres sous 4 h, restauration a partir de sauvegarde sous 8 h ouvrees (RTO), perte de donnees maximale 24 h (RPO). Remedes en cas de non-atteinte : avoir plafonne, sans autre indemnisation."
EN: "Updates are deployed without interruption of the public site, with instant rollback. Public site: 99.5% monthly availability target, measured by external probe every 5 min, excluding announced maintenance, force majeure and third-party host failures. No 100% guarantee. RPO 24 h, RTO 8 business hours. Remedy: capped service credit."
(Do not commit to 99.9% or "zero downtime" as an outcome.) The 4 h incident-acknowledgement figure is my suggestion, not sourced.

### Architecture measures
1. Static pages on CDN keep serving when D1/Worker/admin is down (the public site has no runtime dependency on the DB; build-time content from DB export).
2. Form fallback: on DB or email failure, enquiry handler writes to a second store (R2 object / Cloudflare Queue, or direct email) and retries via cron; show success only after durable write.
3. Multi-provider email: Brevo primary, Resend fallback (both free), SPF/DKIM/DMARC on both; automatic failover in code.
4. Status page: UptimeRobot free status page (1 page) plus external probes of site, form endpoint and admin.
5. Backups: nightly cron D1 export to R2 (same account), plus weekly copy to a second provider (e.g. Scaleway or Backblaze, not priced here); documented restore drill each quarter, timed against the 8 h RTO.
6. Admin lockout fallback: keep a break-glass local admin path independent of Access (Access failed 100% during 2025-06-12).

## 5. EU alternatives (comparison, indicative)
| Provider | Entry cost | SLA | Notes / source |
|---|---|---|---|
| Clever Cloud | smallest app ~EUR 5-16/mo + Postgres XXS from EUR 4.90/30 days; realistic app+Postgres ~EUR 26/30 days | 99.9% standard, 99.99% premium (comparison page, UNVERIFIED) | French PaaS; per-second billing; free DEV DBs have no backups. https://www.clever.cloud/clever-cloud-vs-heroku/ (third-party figures conflict; check clever.cloud/pricing) |
| OVHcloud | VPS-1 EUR 6.49/mo, VPS-2 EUR 9.99/mo monthly billing (post March 2026 increase); managed Postgres Discovery ~$64/mo/node, no SLA | VPS ~99.9% (third-party); Postgres up to 99.99% multi-AZ | https://blog.ovhcloud.com/en/posts/pricing-evolution-of-public-cloud-bare-metal-and-vps-at-ovhcloud/ ; https://www.ovhcloud.com/en/public-cloud/postgresql/ |
| Scaleway | pricing pages not retrievable in this run (Dedibox from EUR 4.99/mo only) | see https://www.scaleway.com/en/terms/sla/ | Not priced; fetch instances/managed DB pages manually |
A single VPS + self-managed Postgres + object storage + backup is EUR 10-30/mo but needs OS patching, monitoring and on-call by the freelancer; a Cloudflare-managed stack removes that work but has global-platform blast radius. EU-only data residency is stronger on French/EU providers.

## 6. Risks
- Single-vendor concentration (Cloudflare serves site, DB, auth, DNS): Nov/Dec 2025 incidents show global config failures; mitigate with off-platform backup copy, second email provider, status page, wording above.
- Cloudflare Access depended on KV in the June 2025 outage; admin unavailable during such events.
- D1: EU jurisdiction fixed at creation; Workers execute anywhere (data-in-transit outside EU possible); US-parent transfer questions for strict clients - DPA/SCC/DPF cover, but disclose.
- D1 Free daily caps cause hard failures (queries fail until 00:00 UTC); use Paid.
- Free email plans: Brevo 300/day cap and logo; Resend 100/day cap - enough for 200-1000/mo but bursts after a congress campaign can hit it.
- UptimeRobot free = 5-min checks and no SMS; Better Stack free has 10 monitors but no phone-call alerts (https://betterstack.com/pricing). Add paid SMS/call (~EUR 3 for 10 SMS credits) if the client demands it. Cloudflare health checks were not researched (a Business/Pro/Enterprise load-balancing feature; unverified).
- Several figures come from third-party pages (marked UNVERIFIED); Zero Trust 50-user free limit and Brevo hosting location need confirmation on official pages before the quote is signed.
- Not researched: Cloudflare Web Analytics details, Scaleway prices, OpenRouter pricing, Better Stack paid phone-call price, domain cost.
