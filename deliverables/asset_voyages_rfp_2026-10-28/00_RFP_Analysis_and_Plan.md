# ASSET Voyages RFP: what they want, what we have, what we build
Internal, for Debanjan only (not for the client) · 28 October 2026

## 0. Reality check first

- **This is a formal competitive consultation, not a signed client.** The brief says "restricted to invited suppliers", "any clarification … will be shared with all invited suppliers" and "submitting a proposal does not constitute an order". Other agencies are quoting too. Treat it as winnable, not won.
- **They will grade, not just price.** Assessment criteria (brief §8): user journeys, UX, Congress catalogue, scalability, SEO, security, methodology, **team**, overall cost and maintenance. A bid that is far too cheap reads as risk. French agencies typically quote €25k–€60k for this scope. €2,500 total will look like we have not understood it.
- **Their wording is a procurement checklist.** Every ID (F01–F06, C01–C07, T01–T15, J0–J6, L0–L4) needs an explicit answer in the proposal. A missing line counts as "partial response" (§8).

## 1. What they are asking for, in plain English

| Code | What it means | Size |
|---|---|---|
| **L0** Audit (mandatory) | Inventory of the current site: CMS, hosting, DNS, who owns which account, every URL, forms, analytics, legal. Workshops to agree user journeys. Recommend keeping or replacing the CMS. | Small, 1–2 weeks |
| **L1** Core site (mandatory) | New French site: home, Business Travel (+ SME page, travel-manager page, assistance, digital solutions/Wondermiles), MICE, agency/resources, contact, legal. Three enquiry forms with a back-office (status, owner, CSV export). Analytics events, cookie consent, SEO migration with 301 redirects, security, training for Veena. Veena must edit content without a developer. | Medium |
| **L2** Congress catalogue (mandatory) | A searchable, filterable list of international congresses (discipline, country, dates, city). One page per congress with its official source, verification date and a flight-quote form pre-filled with the congress. CSV import of ~300 listings with duplicate detection. Two separate workflows: editorial (draft → approval → published) and internal GM&E (detected → … → approved for sale). **GM&E codes must never reach the browser.** | Medium-large: the real product |
| **L3** Wondermiles (optional) | Wondermiles is the online booking tool ASSET's corporate clients use. Core scope is only a "Client login" link. L3 = feasibility study, then SSO (log in once, land in Wondermiles), then API (auto-create client accounts). Everything depends on what Wondermiles allows. | Unknown until feasibility |
| **L4** AI (optional) | AI finds candidate congresses from official sources and puts them in a review queue with source and confidence. A human approves before anything is published. Quotas and an audit log. | Small-medium |
| English | Architecture must be bilingual from day one; English switched on later, priced separately. Human-reviewed translation only. | Small (we did FR/EN for Jitendra and Jeevana) |

Glossary: **MICE** = Meetings, Incentives, Conferences, Exhibitions (corporate group events). **GM&E** = Air France–KLM *Global Meetings & Events*: the airline gives an event code that unlocks discounted fares for congress attendees; agencies apply per event. **SSO** = single sign-on. **RPO/RTO** = maximum data you can lose (24 h) / maximum time to restore (8 business hours). **INP/LCP/CLS** = Google Core Web Vitals.

## 2. What we already have vs what we must build

| Need | Already have | To build |
|---|---|---|
| Premium design, mock-ups, prototype | Prospectus lens (Evolution Exhibits v4, MISB, Gaia, GreenJobs), `site-redesign` skill, eye-review gates | ASSET concept (mock-up in this folder) + a Figma-free design system page |
| Fast static frontend, FR/EN, hreflang | Astro + Cloudflare Pages (Jitendra, Jeevana live), `web_app_astro_cf` template | ASSET templates |
| Forms → saved → email → back-office | GreenJobs Worker pattern, Resend | D1 tables `enquiry`, `congress`, `authorisation`; status/owner/history UI; CSV export |
| Editable by Veena without a developer | **Nothing productised yet**: this is the main gap | **ASSET Console**: a small custom admin on Cloudflare Workers + D1 + R2 (pages, blocks, media, congresses, enquiries), roles, version history/restore, soft-delete |
| Roles + MFA + access logs | Cloudflare Access (free ≤ 50 users) gives MFA/SSO at the edge | Role table (admin, editor, contributor, viewer, approver), per-route permissions, audit log table |
| CSV import 300 listings | GreenJobs import scripts | Schema doc, validator, duplicate detection (title + start date + city), dry-run report |
| Private GM&E codes | — | Separate D1 table, never joined into public queries; code encrypted at rest; automated test that greps every built HTML/JS/API response for code patterns (T05) |
| SEO migration | Redirect maps on GreenJobs | Crawl → URL map → `_redirects` → post-launch Search Console monitoring |
| Consent + analytics | — | Cookie-free analytics (Cloudflare Web Analytics) by default + optional consent banner if they keep GA4 |
| AI ingestion (L4) | OpenRouter key, Jev for classify/score, GLM | Queue table, source fetcher, Jev confidence gate, human approve button |
| Tests/acceptance report | Playwright, functional templates, test registers (GreenJobs 3,047 checks) | T01–T15 test cases with evidence |

## 3. The CMS decision (your "no CMS" instinct)

**Recommendation: custom-coded, no third-party CMS. Pitch it as "ASSET Console" and be honest that it *is* a CMS we build and hand over.** The brief requires an editable site (T15: Veena publishes and edits without a developer), roles, MFA, versions and restoration. So "no CMS" can't mean "no admin"; it means "no WordPress".

Why it wins for ASSET (the justification they ask for):
1. Security: no plugins, no PHP, no admin login page exposed to the internet (Cloudflare Access in front). WordPress plugin vulnerabilities are the #1 cause of small-business site compromise.
2. GM&E code protection (C04) is enforceable by design: the codes live in a table the public site cannot query.
3. Performance: static pages on a global CDN pass LCP ≤ 2.5 s easily.
4. Cost: no licences; hosting ≈ $5/month.
5. Ownership: Git repo, Cloudflare account and data all in ASSET's name; full JSON/CSV export.

The risk they will raise, and how we answer it: "what if ProdCraft disappears?" Answer: standard open-source stack (Astro, TypeScript, SQLite/D1), documented runbook, export scripts, account inventory, and the repo in their GitHub from day one. **Required alternative** (§5 asks for one): headless Directus or WordPress + ACF for editors, costed as "alternative, not recommended".

Your monthly-fee model fits this: they need hosting, security updates, monitoring, backups, SLA and content support anyway (§6). The fee is justified by an SLA table, not by lock-in. The brief explicitly demands handover rights, so never imply lock-in.

## 4. Pricing (recommended in the proposal draft; adjust before sending)

You suggested €1,500–€2,500 + €600/month. I kept your €2,500 for the site and €600/month, and added what the RFP forces us to itemise:

| Line | HT (excl. VAT) |
|---|---|
| L0 Audit & discovery | Included (€0). Wins goodwill and frames us as thorough. |
| L1 Core website (French) incl. forms, back-office, SEO migration, training | €2,500 |
| L2 Congress catalogue & GM&E workflow | €1,500 |
| **Core total (L0+L1+L2)** | **€4,000** |
| Monthly management plan (hosting, tools, security, backups, monitoring, content changes, report) | €600/month, 3-month minimum |
| English activation (architecture already bilingual; excludes professional translation fees) | €750 |
| CRM connector (once a CRM is chosen) | €500 |
| L3a Wondermiles feasibility study | €400 |
| L3b SSO (if a standard protocol is available) | €1,200 |
| L3c API / account automation | Quoted after L3a |
| L4 AI congress ingestion + approval queue (AI usage included in the monthly plan) | €1,500 |
| **3-year core cost** (asked for in §8): €4,000 + 36 × €600 | **€25,600 HT** (€30,720 TTC) |

My honest view: €4,000 is still very low for this scope. The 3-year figure (€25.6k) puts us in the normal market band, and the recurring fee is where the value is. "All tools on us" is in: hosting, email sending, monitoring and AI usage are covered by the monthly fee. The accounts are still opened **in ASSET's name** (brief §5: accounts must stay under ASSET control); we just pay or absorb the costs.

## 5. Delivery plan (≈ 10 weeks + 4 weeks stabilisation; their indicative 12–18)

| Milestone | Weeks | Deliverable |
|---|---|---|
| J0 Kickoff | 1 | Access inventory, schedule, RACI |
| J1 Audit & discovery | 1–2 | Crawl + URL inventory, tech/SEO audit, baseline, backlog, risks, architecture diagram |
| J2 UX & UI | 2–4 | Wireframes, desktop/mobile mock-ups, clickable prototype, design system (the concept in `site/` is the head start) |
| J3 Core website | 4–7 | All L1 pages on staging (noindex, Access-protected), forms, back-office, tracking |
| J4 Congresses | 6–8 | Catalogue, filters, CSV import of 300, workflows, GM&E vault, enquiries |
| J5 Pre-launch | 9–10 | Redirect map, T01–T15 acceptance report, fixes, training Veena + backup, backup/restore drill, rollback plan; written go from management → DNS cutover |
| J6 Stabilisation | 11–14 | Daily checks, Search Console monitoring, handover pack (repo, accounts, exports, admin guide) |

## 6. What we do next (order)

1. Reply to Veena today: confirm interest and send the 20 questions; answers in writing, no call (`01_Questions_for_Veena.md` (20 questions, written answers by email; the long list is `99_INTERNAL_kickoff_call_checklist.md`)). **No prices in the email** (your rule).
2. Concept mock-up live (`site/`) linked in the reply as "an initial visual direction".
3. After the call: fill in the brackets in `proposal/asset-voyages-v1.json`, rebuild the DOCX and send it as a PDF (the brief asks for a **PDF** technical proposal + itemised quotation, HT/TVA/TTC).
4. Prepare 2–3 references they can verify. We have **no travel/MICE reference**. Lead with GreenJobs (catalogue/listings with filters = the Congress catalogue pattern), Jitendra/Jeevana (live FR/EN), Evolution Exhibits (exhibitions = the "E" in MICE).
5. Name the team and effort by role (§8). Even if it's you + AI: Project lead & full-stack (Debanjan), design, QA, and a named French copy reviewer if you can get one.
