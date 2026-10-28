# Website Redesign for ASSET Voyages
Version 1.0 · 2026-10-28

Business Travel · MICE · International Congresses

| | |
|---|---|
| **Prepared for** | ASSET Voyages Management, attention Veena Khatri |
| **Prepared by** | Debanjan Mazumdar, Founder, ProdCraft |
| **Date** | 28 October 2026 |
| **In response to** | ASSET Voyages website redesign requirements, Version 0.4 EN, 28 October 2026 |

This proposal contains all of the details and costs regarding the approach, scope of work, investment and terms for the redesign of asset-voyagesdaffaires.com, as requested by ASSET Voyages. Work packages L0, L1 and L2 form the core scope and work without the options L3 and L4. All prices are in euros, excluding VAT unless stated.

---

## 01. The Situation

### ASSET Voyages needs a B2B portal, not a brochure.

Hello Veena,

I went through your requirements document (Version 0.4) and the response form. ASSET Voyages sells three very different things to three very different buyers: managed business travel to SMEs and travel managers, group events (MICE) to HR and communications teams, and flight quotations to congress participants. Each buyer needs their own journey, and each needs its own route to the right person. Here are what I believe to be the core problems:

---

## 02. What It Is Costing You

### Four problems your brief sets out to solve.

#### 1. Enquiries that do not reach the right person

A Business Travel lead, a 200-person seminar brief and a congress flight request need different questions, a different owner and a tracked status. Without that, leads wait in a shared mailbox and nobody can measure which activity brings business.

#### 2. A searchable Congress catalogue is a new capability

Congress participants search by discipline, city and date. Without a searchable catalogue with one page per congress, ASSET cannot rank for those searches, cannot pre-fill a quotation with the event, and cannot protect the GM&E codes the business depends on.

#### 3. Your team depends on a developer

Your brief asks that Veena and a backup editor publish pages and congress listings themselves, with roles, approvals and version history, so content stays current without waiting for a supplier.

#### 4. Search value and trust at risk

Your brief asks that search value is preserved and the current site stays online throughout. The redesign must keep every page that ranks today with a mapped 301 redirect, meet GDPR and cookie rules, and load fast on a phone, where most first visits now happen.

The following pages cover the full scope of the project, including investment. Let me know if you have any questions by emailing me at debanjan@prodcraft.fyi. Your written answers to my 20 questions turn the estimates below into a fixed price.

Thanks,

Debanjan

---

## 03. What You Get

### A fast, secure B2B portal your team runs, with the integrations kept for later.

My proposed solution to the problems above is as follows. An initial visual direction is online at https://asset-voyages-redesign.pages.dev/, with a short note for your team at https://asset-voyages-redesign.pages.dev/pour-asset/. It is a concept built for this response, not the final design.

#### 1. Three journeys, two clicks to a form

A homepage that routes each visitor to Business Travel, MICE or Congresses within one click; dedicated pages for SMEs and microbusinesses, travel and procurement managers, assistance and expertise, and digital solutions (Wondermiles); three enquiry forms (F01 to F03) reachable in two or three clicks, with no account required. Premium, understated design built from reusable components, tested at 320, 375, 768 and 1440 px, targeting WCAG 2.2 AA.

#### 2. A Congress catalogue that scales to hundreds of events

Search and filters by discipline, country, city, period and name, sorted by date, with pagination and a no-results state; one indexable page per congress showing the official source and verification date; a quotation form pre-filled with the congress and open to any departure airport. Behind it, the editorial workflow (draft, approval, publication) is kept separate from the internal GM&E workflow (detected to archived). GM&E codes and evidence sit in a protected store that the public site cannot read, and an automated test checks every page, script and response for leaks before each release.

#### 3. ASSET Console: your own administration, no licence

A custom administration built for ASSET, with no third-party CMS licence or plugins: pages, media, congresses, CSV import and export of listings, and an enquiry inbox with status, owner, history and CSV export. Roles for technical administrator, editor (Veena), contributor, commercial viewer and Congress/fare approver; multi-factor login for every administrator through ASSET's Microsoft 365 or Google Workspace account (or authenticator-app codes if neither is used); version history with restore; soft delete; access log.

#### 4. Built to be handed over

Domain, hosting, repository and every tool account are opened in ASSET's name. Source code, design files, data and media are yours; documented exports, a tested backup restore and a written runbook mean another supplier could take over at any time.

I consider this well within what ProdCraft delivers and am confident I can do an outstanding job here for you. If I was not, I would not have put together this proposal.

---

## 04. Technical Approach

### Why custom-built rather than an off-the-shelf CMS.

- **Public site:** pre-rendered pages (Astro, TypeScript) on Cloudflare's network with EU data handling. Pages are plain HTML on a CDN, built to lab targets per template of LCP 2.5 s or less, INP 200 ms or less and CLS 0.1 or less.
- **ASSET Console and enquiries:** server functions (Cloudflare Workers) with a relational database (Cloudflare D1, SQLite) and media storage (R2). Every exchange involving secrets or business data runs server-side.
- **Access:** the Console sits behind Cloudflare Access, so the login page is not exposed to the internet; multi-factor login through your company Microsoft 365 or Google Workspace account, or authenticator-app codes. If Cloudflare's login service is unavailable, the public site keeps serving; the technical administrator retains command-line access for deployment and rollback.
- **Environments:** separate development, staging and production. Staging is password-protected and marked noindex.
- **Integrations:** decoupled connectors for email notifications, a future CRM (API or webhook), the Wondermiles client-area link and, as options, SSO and AI. Core forms work without any of them.
- **Why not WordPress:** no plugin updates to chase, no exposed admin, no licence fees, and GM&E code protection enforced by the data model rather than by configuration.
- **Reasonable alternative (indicative: about €1,100 HT extra set-up and €10-30 a month extra hosting):** a headless CMS (Directus) for editing with the same public site, if ASSET prefers a packaged editor interface. It adds hosting and maintenance cost and is not recommended.

#### Architecture, data flows and costs

**Diagram.** Visitor → Cloudflare CDN (pre-rendered public pages) and Cloudflare Workers (forms, search events) → public database (D1) and a separate private database (D1) for GM&E records → media storage (R2). ASSET Console → Cloudflare Access login → admin Worker → both databases. Email notifications via Brevo, with Resend as fallback. External monitors and a status page via UptimeRobot. Nightly backups to R2, with a weekly copy to a second provider.

| Flow | What happens |
|---|---|
| Enquiry | Visitor submits a form → Worker validates it and saves one record → the team for that activity is emailed → the enquiry appears in the Console inbox with status, owner and history |
| Publish | Editor saves a draft → approver approves → the public page is rebuilt and published; drafts never reach the public site or the sitemap |
| Import | CSV upload → dry run that writes nothing → report (accepted, rejected, flagged) → editor confirms → listings imported as drafts → published in bulk |
| Authorisation | GM&E application, code and evidence are entered by the approver into the private database only; the public site has no read access to it |
| Backup | Nightly database export to R2 → weekly copy to a second provider → timed restore drill every quarter |

| Dependency | Used for | Expected cost per month |
|---|---|---|
| Cloudflare Workers Paid | Server functions for forms, Console and scheduled jobs | $5 (≈ €4.3) |
| Cloudflare Pages, D1, R2, Access, Turnstile, Web Analytics | Public site, databases, media, admin login, anti-spam, page-view analytics | €0 at this size |
| Brevo | Transactional email (primary) | €0 (Starter ≈ €7-9 if the daily cap is reached) |
| Resend | Transactional email (fallback) | €0 |
| UptimeRobot | External monitors and public status page | €0 |
| GitHub | Source code repository in ASSET's name | €0 |
| Second backup provider | Weekly off-platform backup copy | Chosen at L0, inside the total below |
| **Total** |  | **≈ €5-15 a month, paid by ProdCraft inside the monthly plan** |

No Air France-KLM API access or automatic ticket issuance is assumed; GM&E arrangements are confirmed by the partners.

#### Data protection and compliance

Privacy information and lawful basis per form; marketing boxes unticked; no personal data in URLs or analytics; cookie-free analytics by default, with a consent banner only if ASSET keeps trackers that need it; Cloudflare Turnstile anti-spam (no cookies); retention rules proposed for ASSET approval; data processing agreement; internal procedure for access and deletion requests. Subprocessors: Cloudflare (US parent company; databases held under EU jurisdiction; data processing agreement with standard contractual clauses and the EU-US Data Privacy Framework), Brevo (France), Resend (US), UptimeRobot and GitHub. ProdCraft acts as processor under a data processing agreement annexed to the contract.

#### Data model, import and retention

- **Enquiry record:** unique identifier, type (Business Travel, MICE or Congress), date, source and campaign (UTM tags, landing page, referring site), contact fields, congress reference, status, owner, privacy-notice version, and marketing consent with its timestamp.
- **Retention (proposal, for ASSET approval):** prospects kept 3 years after the last contact; spam deleted after 30 days; won clients kept under ASSET's own records policy. A nightly job applies the rules.
- **CSV schema:** a versioned column list with required and optional fields, formats (ISO dates, ISO country codes) and an error code per rejected row.
- **Duplicates:** a hard duplicate (same normalised title, start date and city) is rejected; a soft duplicate (same normalised title in the same year) is flagged for a person to decide.
- **Import of 300 listings:** upload, dry run that writes nothing, report, confirmation, import as drafts, then bulk publication by the editor.
- **Change log:** every creation, edit and import is recorded with user, time and import batch.
- **Past events (proposal, for ASSET approval):** after the end date the page shows a 'Past edition' banner, the quotation form is switched off and a link points to the next edition; the page stays indexable for 12 months, then redirects to the next edition or the discipline page.
- **Preferential-fare badge (proposal, for ASSET approval):** shown only when an approver has marked the congress 'approved for sale', using approved wording; no 'official agency' wording unless ASSET documents the authorisation. Approvers and pre-promotion conditions are confirmed by ASSET management and configured in the Console.

#### Conversion measurement

- **Events:** CTA clicks, form starts, submissions and errors, congress searches, listing views, account requests and client-area clicks.
- **Dimensions:** page, activity (Business Travel, MICE, Congress), campaign source, medium and name, and referring site. Search text is stored only after removing anything that looks like an email address or phone number. No personal data is collected.
- **Consent:** first-party, cookie-free events by default. Google Analytics or LinkedIn tags run only if ASSET keeps them, and only after consent.
- **Baseline:** taken from your current analytics during L0, then compared month by month in the plan report.

#### SEO migration

Full crawl of the current site, a URL inventory with a keep, merge, redirect or remove decision per page, a one-hop 301 redirect map, editable titles and descriptions, structured data, XML sitemap, robots.txt, canonicals, hreflang ready for English, and Search Console monitoring after launch.

#### Known limitations

| Limitation | Impact | Proposed solution |
|---|---|---|
| No 100% availability | Short outages of the hosting platform can happen | 99.5% monthly target, independent monitoring, status page and service credit (section 06) |
| Field Core Web Vitals depend on Google publishing data | Real-user speed data may not exist for a site of this size | Lab report per template every month; field data reported wherever Google publishes it |
| Single named supplier | Holiday or illness could slow a response | Repository in ASSET's name from day one, written runbook and a standard open-source stack, so another supplier can take over |
| Multi-factor login depends on ASSET's identity provider | The login method follows ASSET's Microsoft 365 or Google Workspace set-up | Authenticator-app codes if neither is used |
| Wondermiles capabilities are unknown | Single sign-on and API scope cannot be fixed yet | L3a feasibility review before L3b or L3c is priced or started |

---

## 05. Scope of Work

### What ProdCraft will build.

- **L0 Audit and discovery:** inventory of CMS, hosting, DNS, certificates, licences, account owners and backups; content, URL, form, analytics, performance and compliance audit; two workshops on user journeys; architecture diagram, data flows, backlog and risks.
- **L1 Core website (French):** design system, wireframes, desktop and mobile mock-ups and a clickable prototype; homepage, Business Travel, SMEs and microbusinesses, procurement and travel managers, assistance and expertise, digital solutions, MICE hub, agency and resources, articles, guides and FAQ, contact and legal pages, up to 20 French content pages and 3 legal pages, with copy supplied or approved by ASSET (we migrate and lightly edit it; two revision rounds per milestone); forms F01, F02 and F04 to F06; ASSET Console; conversion tracking; SEO migration; security hardening; training for Veena and a backup editor.
- **L2 Congress catalogue:** structured congress records, search and filters, listing pages, form F03 linked to the congress ID, the editorial and GM&E workflows, protected authorisation store, CSV schema, import of up to 300 listings with duplicate detection, export, and the approved rule for past events.
- **Acceptance:** documented test cases T01 to T15 with datasets, results and evidence in an acceptance report; no launch with a blocking defect.
- **Acceptance mapping:** each test scenario from your brief is mapped to the test we run and the evidence you receive, in the table below.
- **Handover:** illustrated administration guide, deployment, restore and export procedures, account and licence inventory, secure transfer of secrets, Git repository in ASSET's name.

| Scenario | Test | Evidence |
|---|---|---|
| T01 Business Travel form | Invalid fields show clear errors; a valid form is saved once, routed and acknowledged; a repeat creates no new record; email failure falls back | Database record, routing email and screenshots |
| T02 MICE form | As T01, plus the summary screen and back-navigation keep the data | Database record, routing email and screenshots |
| T03 Congress search | 300-listing dataset; 10 queries with expected results; sort, filters and no-results state | Query results against the expected list |
| T04 Draft not public | A draft returns 404 in production and is absent from the sitemap and search index | HTTP check and sitemap extract |
| T05 GM&E code protection | Scanner checks all public output, including a planted test code; only approver and administrator roles read the private store | Scanner report and role matrix |
| T06 Congress ticket enquiry | A quotation from a listing is saved with the congress ID and the congress team is notified | Database record and notification email |
| T07 Past congress | A past end date shows the banner, switches the form off and links onward under the approved rule | Screenshots and rule test |
| T08 Client-area link | The link goes to the configured address; no password field or column exists anywhere | Link check and schema check |
| T09 Tracker refusal | Refusing non-essential trackers stops their requests; the choice can be changed | Browser network log |
| T10 Priority redirects | Every priority old URL makes one 301 hop to a live page | Redirect check report |
| T11 Keyboard and screen reader | Zero serious axe violations, plus a manual script on 5 critical journeys | axe report and manual checklist |
| T12 Responsive and performance | Screenshots at 4 widths; Lighthouse lab report per template within targets | Screenshots and Lighthouse reports |
| T13 Test restoration | Last night's backup restored into a fresh database, timed against the 8-hour target | Timed restore log |
| T14 Documented export | Export opened in a spreadsheet; columns match the documentation | Export file and column list |
| T15 Veena publishes alone | Using the guide, Veena creates, publishes and edits an article, then restores a revision | Session notes and revision history |

#### Milestones

- **J0 Kickoff:** access inventory, schedule and responsibilities.
- **J1 Audit and discovery:** architecture, SEO inventory, baseline, backlog and risks.
- **J2 UX and UI:** wireframes, desktop and mobile mock-ups, prototype and design system.
- **J3 Core website:** pages, ASSET Console, forms and tracking on staging.
- **J4 Congresses:** tested catalogue, filters, statuses, listings and enquiries.
- **J5 Pre-launch:** SEO migration, acceptance report, fixes, training, restore drill, backup and rollback plan; cutover only on written authorisation from ASSET management.
- **J6 Stabilisation:** monitoring, fixes, access, source code, exports and closure of outstanding items.
- **Throughout:** weekly written update, one business day response, the current website stays online and untouched until cutover.

#### Timeline

My proposed timeline is pragmatic and takes into account past experience building similar systems. Assuming a go-ahead on Monday 16 November 2026, with no work from 24 December to 1 January and no approvals from 21 December to 1 January:

| Milestone | Deliverable ready | ASSET approval by |
|---|---|---|
| J0 Kickoff | Wednesday 18 November 2026 | Friday 20 November 2026 |
| J1 Audit and discovery | Friday 27 November 2026 | Wednesday 2 December 2026 |
| J2 Mock-ups and design system | Friday 11 December 2026 | Wednesday 16 December 2026 |
| J3 Core website on staging | Friday 15 January 2027 | Wednesday 20 January 2027 |
| J4 Congress catalogue on staging | Friday 22 January 2027 | Wednesday 27 January 2027 |
| J5 Pre-launch: acceptance report, training, restore drill | Friday 5 February 2027 | Written go-ahead Monday 8 February 2027 |
| Launch (DNS cutover) | Tuesday 9 February 2027 | After written go on Monday 8 February 2027 |
| J6 Stabilisation closed | Friday 5 March 2027 |  |

**Contractual latest launch: Friday 12 March 2027.** Both the planned date (about 12 weeks) and the latest date (about 16 weeks) sit inside your indicative 12 to 18 weeks.

Dates move day for day with the start date, with the time taken for written approvals (planned at 3 working days per milestone), and with any input from ASSET that arrives late (account access, approved content and images, congress data, recipient mailboxes, partner confirmations).

**Out of scope:** ticket issuance and the flight booking engine (they stay outside the website); advertising campaigns; paid CRM software; bulk scraping and automatic publication; copywriting from scratch beyond light editing (quoted at the change-request rate); professional translation fees; photography and stock image licences; any fees charged by Wondermiles, Air France–KLM or the current hosting provider. Anything else is quoted before it starts.

---

## 06. Investment

### Your investment.

Note: the build price assumes the 12-month monthly plan below: the build is priced as part of a 12-month managed partnership. Payments are made against accepted milestones.

| Work package | Price (excl. VAT) | Qty | Subtotal |
|---|---|---|---|
| L0 Audit and discovery | Included | 1 | €0 |
| L1 Core website, French | €2,500 | 1 | €2,500 |
| L2 Congress catalogue and workflows | €1,500 | 1 | €1,500 |
| Total core investment (excl. VAT) |  |  | €4,000 |
| VAT at 20% |  |  | €800 |
| Total core investment (incl. VAT) |  |  | €4,800 |
| 30% at J0 approval (kickoff) |  |  | €1,200 excl. VAT |
| 30% at J2 approval (mock-ups) |  |  | €1,200 excl. VAT |
| 20% at J4 approval (Congresses on staging) |  |  | €800 excl. VAT |
| 20% at launch acceptance |  |  | €800 excl. VAT |

#### Options (quoted separately, none required for launch)

| Option | What it includes | Price (excl. VAT) | VAT 20% | Incl. VAT |
|---|---|---|---|---|
| English activation | English versions of the templates, language switch, hreflang and URLs; translated text supplied by ASSET or a translation agency | €750 | €150 | €900 |
| CRM connector | API or webhook connection to the CRM ASSET selects. Authentication: API key or OAuth held as a server secret. Data: mapped enquiry fields, no marketing fields without consent. Duplicates: look up by email, then update or create. Errors: 3 retries with back-off, then a failed-items list in the Console and an alert. Recovery: resend button and bulk replay. Maintenance: API version pinned and checked monthly in the plan | €500 | €100 | €600 |
| L3a Wondermiles feasibility | Review of Wondermiles documentation and contract permissions; written recommendation with journeys for login, failure and logout | €400 | €80 | €480 |
| L3b Wondermiles single sign-on | SSO into Wondermiles, if a standard protocol (SAML or OpenID Connect) is available and authorised | €1,200 | €240 | €1,440 |
| L3c Wondermiles API and account creation | Automatic client account creation and data exchange | Quoted after L3a |  |  |
| L4 AI congress ingestion | AI finds candidate congresses from approved official sources into a review queue with source, confidence, quotas and audit trail; nothing is published without human approval | €1,500 | €300 | €1,800 |

#### Monthly management plan (starts at launch)

| Plan | What is included every month | Per month (excl. VAT) | VAT 20% | Incl. VAT |
|---|---|---|---|---|
| Manage | Hosting and delivery on Cloudflare's network; every tool subscription the site needs (hosting, email sending, monitoring, and AI usage if L4 is selected), paid by ProdCraft; SSL renewed automatically; nightly backups with a 30-day point-in-time restore, a weekly off-platform copy and a timed restore drill every quarter; 24/7 automated uptime and security monitoring with a public status page; security patches and dependency updates; Lighthouse speed and axe accessibility reports on every release and monthly; redirects, sitemap and Search Console health kept clean; up to 5 hours a month of content changes, new pages from existing templates and congress updates (logged in the monthly report; unused hours do not roll over); help for Veena and the backup editor; a monthly report on availability, incidents, backups, enquiries by activity, congress searches and hours used | €600 | €120 | €720 |

12-month minimum term from launch, then rolling monthly with 30 days' written notice. If ASSET ends the plan within the first 12 months, the remaining months of the minimum term are due. Accounts, code and data stay yours at all times. Work beyond the included hours is charged at €70 per hour excl. VAT, with a written quote before any change over one day, assessed for cost, schedule, security and SEO impact.

#### How the plan is measured (reported to you every month)

| Metric | Commitment |
|---|---|
| Availability | Site updates are deployed with zero downtime: the public site stays online during every release, and any release can be rolled back instantly. The public site targets 99.5% monthly availability, measured by an independent external probe every 5 minutes and reported monthly, excluding maintenance announced 48 hours ahead, force majeure and third-party host failures. No 100% availability is guaranteed. Recovery targets: at most 24 hours of data loss (RPO) and service restored within 8 business hours (RTO). |
| Deployments | Zero-downtime releases with instant rollback |
| Backups | Nightly, 30-day point-in-time, weekly off-platform copy; quarterly timed restore drill |
| Response time | Monday-Friday 9:00-18:00 Paris time; outage or failed form acknowledged within 4 business hours; other requests within 1 business day |
| Requested changes | Within 2 business days, within the monthly allowance |
| Security | Critical patches within 2 business days of release |
| Page speed | Lab report per template every month (LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1); field data at the 75th percentile where Google publishes it |
| Service credit | 10% of the month's fee if the availability target is missed, capped at one month's fee a year |
| Exclusions | Maintenance announced 48 hours ahead, force majeure, third-party host failures (Cloudflare, Wondermiles), errors in content supplied by ASSET, weekends and holidays unless on-call is agreed and priced |

#### Total core cost over three years

| Item | Excl. VAT | Incl. VAT |
|---|---|---|
| Core website and Congress catalogue (L0 + L1 + L2), once | €4,000 | €4,800 |
| Monthly management plan, 36 months at €600 | €21,600 | €25,920 |
| Licences and third-party subscriptions | €0 (tools paid by ProdCraft inside the plan; not counted twice) | €0 |
| Total over three years, excluding unselected options | €25,600 | €30,720 |
| Annual recurring cost (monthly plan, 12 months) | €7,200 | €8,640 |

#### Third-party services and licences

| Service or licence | Account held by | Paid by |
|---|---|---|
| Cloudflare (Pages, Workers, D1, R2, Access, Turnstile, Web Analytics) | ASSET | ProdCraft during the plan; ASSET after exit |
| Brevo and Resend (email sending) | ASSET | ProdCraft during the plan; ASSET after exit |
| UptimeRobot (monitoring and status page) | ASSET | ProdCraft during the plan; ASSET after exit |
| GitHub (source code) | ASSET | ProdCraft during the plan; ASSET after exit |
| Second backup provider | ASSET | ProdCraft during the plan; ASSET after exit |
| Fonts | Open licence | No cost |
| Photographs and images | ASSET, under its own rights | ASSET |
| Wondermiles content and access | ASSET, under Wondermiles' terms | ASSET |

There are no paid or non-transferable licences in the core scope.

Prices valid for 60 days from the date of this proposal.

---

## 07. Relevant Work

### Recent projects by ProdCraft.

- **Yoga avec Jitendra, yogaavecjitendra.fr (client project, live):** a French and English site in production, on the same static architecture proposed here.
- **GreenJobs (UK and Ireland), greenjobs-redesign.pages.dev/uk (concept):** a listings catalogue with search, filters, list and map views, one indexable page per listing with structured data, and an admin console. The same pattern as the Congress catalogue.
- **Evolution Exhibits, evolution-exhibits-v4.pages.dev (concept):** trade-show and exhibition environments, the 'E' in MICE; a premium, document-style presentation of event services.
- **Jeevana Yoga & Wellness, v4.jeevana-yoga.pages.dev (concept):** bilingual French and English service site with booking enquiries.
- **Gaia Talent, gaia-talent-redesign.pages.dev (concept):** B2B specialist recruitment portal for Ireland's green economy.
- **MISB business school, misb-redesign.pages.dev (concept):** prospectus-style concept for a Paris and Lyon school with programme filters and admissions journeys.
- **ProdCraft, prodcraft.fyi (our own company):** our AI engineering practice, which supports the optional AI features.

#### Team

| Role | Person | Effort |
|---|---|---|
| Project lead, architecture and audit | Debanjan Mazumdar | ≈ 4 days |
| UX and UI design | Debanjan Mazumdar | ≈ 3.5 days |
| Full-stack development | Debanjan Mazumdar | ≈ 22 days |
| Quality assurance and accessibility | Debanjan Mazumdar | ≈ 3 days |
| Documentation and training | Debanjan Mazumdar | ≈ 1.5 days |
| Contingency |  | ≈ 7 days |
| **Total** |  | **≈ 41 days** |

Days are 7-hour working days. French copy and claims are validated by ASSET. ProdCraft uses AI-assisted engineering tools; all work is reviewed and accepted by the named lead. For continuity, the repository is in ASSET's name from day one, the runbook is written as the work proceeds, and the stack is standard open-source software that another supplier can pick up.

---

## 08. Agreement

### Terms and conditions.

ProdCraft will design and build the ASSET Voyages website according to the description laid out in this proposal. The core scope is L0, L1 and L2; options are added only when selected in writing. No production work and no DNS change takes place without written authorisation from ASSET management. Milestone payments are invoiced on written approval of each milestone; the monthly plan is charged at the start of each month from launch. The monthly plan has a 12-month minimum term from launch, then continues monthly and can be cancelled with 30 days' written notice; if ASSET ends it within the first 12 months, the remaining months of the minimum term are due, and anything already paid is not refunded. Any change outside the listed requirements is submitted as a written change request, assessed for cost, schedule, security and SEO impact, and approved by ASSET before work starts; it is charged at €70 per hour excl. VAT, with a written quote for any change over one day. All infrastructure, data, source code and design files belong to ASSET Voyages. Tool accounts are held in ASSET's name throughout; at exit, billing for those accounts transfers to ASSET. A data processing agreement is annexed to the contract; rights, data processing and exit provisions are set out in the contract and that agreement. Response time: one business day within the support window (Monday to Friday, 9:00 to 18:00 Paris time). If you have a question or comment, email debanjan@prodcraft.fyi.

By signing below, both parties indicate their acceptance of this proposal and constitute approval to begin work.

**ProdCraft**
Name: Debanjan Mazumdar
Title: Founder, ProdCraft
Email: debanjan@prodcraft.fyi
Signature: ____________
Date: ____

**ASSET Voyages**
Name: Authorised signatory
Title: ASSET Voyages Management
Email: direction@assetvoyages.com
Signature: ____________
Date: ____
