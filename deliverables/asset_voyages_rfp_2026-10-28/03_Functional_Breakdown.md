# ASSET Voyages RFP: functional breakdown, cell by cell
Internal, for Debanjan only · Wednesday 28 October 2026 · companion to `02_Panel_Debate.md`

**How to read this.** Every requirement in the RFP body (Version 0.4 EN, pages 1-9) is a row in one of the tables below. Each row gives:
- **Requirement:** what the RFP asks, in short.
- **We build:** the user-visible part first, then what happens behind the scenes after "BTS:".
- **Acceptance check:** how ASSET can verify it.
- **Status:** **EXISTS**, **PARTIAL** or **MISSING** in our stack today.
- **Gap and how we close it.**
- **Hours:** "↳" means the work is already counted in another row.
- **Proposal section (§):** which section of the proposal answers it. §01-§08 refer to `proposals/asset-voyages-v1.json`; "NEW" means a section to add.

**Unknowns are marked "UNKNOWN".** Nothing here assumes ASSET's CMS, host, CRM, email provider, traffic or URL count. Site research (`research/facts.md`) is not done yet.

**Hours budget** (panel-reconciled): **238 h core + 48 h contingency (20%) = 286 h.** Section subtotals reconcile in table Y.

Glossary, used throughout:
- **BTS** = behind the scenes.
- **D1** = Cloudflare's hosted SQLite database.
- **R2** = Cloudflare file storage.
- **Worker** = a small server function on Cloudflare.
- **Access** = Cloudflare's login gateway in front of the admin.
- **IdP** = identity provider (e.g. Microsoft 365 or Google Workspace).
- **TOTP** = 6-digit authenticator-app codes.
- **UTM** = campaign tags on a link.

---

## A. Expected outcomes, governance and scope boundaries (pages 1-2)

| # | Requirement | We build | Acceptance check | Status | Gap and how we close it | Hours | § |
|---|---|---|---|---|---|---|---|
| A1 | Generate qualified enquiries for Business Travel, MICE, congress ticketing | Three journeys ending in three purpose-built forms; BTS: enquiry record with type, source, status, owner | Forms T01-T06 pass; monthly report counts enquiries by activity | PARTIAL | Back-office is new (see F, G) | ↳ F, G | §03.1 |
| A2 | Veena and a backup editor publish content and listings without a developer | ASSET Console (see I); 2 named logins; training | T15 | MISSING | Console is the main build (44 h) | ↳ I | §03.3 |
| A3 | Preserve SEO value; keep current site available throughout | Parallel build on staging; current site untouched until DNS cutover; 301 map | T10; cutover log; old site live until written go | PARTIAL | Crawl→redirect tool missing (see S) | ↳ S | §04 SEO, §05 |
| A4 | Prepare integration points; launch not dependent on API/SSO | Connector interfaces (email, CRM webhook, client-area link) as config, no hard dependency | Core passes T01-T15 with all options off | EXISTS (pattern) | Document the interface contract in architecture section | ↳ P | §04 |
| A5 | Responsibilities: management approves; Veena coordinates and does acceptance; supplier audits…deploys; partners confirm | RACI table (who is responsible, accountable, consulted, informed) in the J0 pack | J0 approved | MISSING in proposal | Add RACI to §05 | ↳ J0 | NEW §05 |
| A6 | Each milestone has a deliverable and written approval | Milestone deliverable list + approval email template | Approval email per J0-J6 | EXISTS (our practice) | None | ↳ PM | §05 |
| A7 | Out-of-scope changes assessed for cost, schedule, security, SEO before approval | Change-request form with four impact fields; €70/h HT; quote above 1 day | Signed change request on file | MISSING | Add to §08 | 1 (PM) | §08 |
| A8 | No production work or DNS change without written authorisation from management | Cutover only on written go; pre-cutover checklist | Go email from management before DNS change | EXISTS in draft | None | ↳ J5 | §05, §08 |
| A9 | L0+L1+L2 operate without L3/L4; ticket issuance and booking engine outside the CMS | No booking code anywhere; quote request only | T06: enquiry saved, no ticket issued | EXISTS in draft | None | 0 | §05 out-of-scope |
| A10 | Exclusions: ads, paid CRM, bulk scraping, auto-publication; list every licence, subscription and third party | Exclusions list + third-party services table with cost and who pays | Table present in proposal | PARTIAL | Exclusions exist; **services/cost table missing** | ↳ P8 | §05, NEW §04 |
| A11 | French mandatory at launch; architecture FR+EN; translation and EN activation quoted separately; no machine translation published without approval | `/fr/` routes, i18n string files, hreflang-ready; EN option €750 (translation excluded); "human-approved" flag on EN pages | FR live; EN routes exist and are switched off; no EN page publishable unless approved | EXISTS (Jitendra, Jeevana) | Add the approval flag to the Console | 0 (↳ I) | §06 options |

**Mandatory initial audit (L0, page 2): 12 h**

| # | Requirement | We build / deliver | Acceptance check | Status | Gap and how we close it | Hours | § |
|---|---|---|---|---|---|---|---|
| L0.1 | Inventory CMS, versions, extensions, custom code | Audit sheet from access + crawl fingerprints | Sheet in J1 pack | PARTIAL | Needs current supplier's access (UNKNOWN who) | 1.5 | §05 L0 |
| L0.2 | Hosting, DNS, certificates | DNS/TLS inventory (records, registrar, expiry) | Sheet | PARTIAL | Registrar/owner UNKNOWN (Q3) | 1 | §05 |
| L0.3 | Licences, ownership, backups, access | Account-owner register: who owns what, in whose name | Register signed by ASSET | MISSING | Template to write | 1 | §05 |
| L0.4 | Content, URLs, links | Full crawl inventory (uses S1 tool) | CSV of all URLs with status | MISSING | Tool built in S1 | 2 | §04 SEO |
| L0.5 | Forms, analytics, Search Console | List of forms, destinations, trackers; Search Console export of top pages and queries | Sheet + export | PARTIAL | Search Console access UNKNOWN; trackers UNKNOWN (Q6) | 1.5 | §05 |
| L0.6 | Performance and compliance | Lighthouse lab baseline of 5 key pages; legal pages/cookie check | Baseline report | MISSING (tooling) | Lighthouse CI built in Q2 | 1.5 | §05 |
| L0.7 | Recommend keeping or replacing the CMS, with technical and cost justification | Written recommendation: replace with ASSET Console; Directus as costed alternative | Recommendation approved at J1 | PARTIAL | Alternative must be costed (P9) | 0.5 | §04 |
| L0.8 | Workshops, user journeys, functional discovery | 2 remote workshops × 1.5 h; journey maps for the 5 journeys; backlog | Journey maps approved | EXISTS (practice) | Not in the old estimate; added | 3 | §05 L0 |
| | **Subtotal L0** | | | | | **12** | |

---

## B. Work packages L0-L4 (page 2)

| # | Requirement | We build | Acceptance | Status | Gap and how we close it | Hours | Price HT | § |
|---|---|---|---|---|---|---|---|---|
| L0 | Technical/SEO audit, workshops, journeys, architecture, discovery | Table A (L0.1-L0.8) + architecture doc | J1 approval | PARTIAL | See A | 12 | Included | §05, §06 |
| L1 | Design, CMS, priority French content, BT and MICE pages, forms, measurement, SEO migration, security, training | Tables C-K, P-W (L1 parts) | J3 + J5 approval; T01-T02, T09-T15 | PARTIAL | Console, back-office, tooling missing | ≈ 180 | €2,500 | §03-§05 |
| L2 | Congress catalogue, search, listings, business workflow, permissions, forms, CSV import/export, moderation | Tables L-O | J4 approval; T03-T08 | PARTIAL | Import/dedup, vault, workflows missing | ≈ 46 | €1,500 | §03.2, §05 |
| L3 | Wondermiles feasibility, SSO/API, account creation subject to permissions | L3a study; L3b SSO (SAML or OpenID Connect, if available); L3c after L3a | Written feasibility; SSO success/failure/logout journeys | MISSING | Depends on Wondermiles docs (UNKNOWN) | 4 / 12 / TBD | €400 / €1,200 / TBD | §06 options |
| L4 | Controlled AI ingestion, human approval, monitoring, logs | Source allowlist, scheduled fetch, schema-bound extraction, URL verification, review queue, confidence, quotas, audit log, 30-case eval set | Nothing is published without approval; audit row per candidate | PARTIAL (Jev/OpenRouter exist) | Queue, eval set and pinning are new | 16 | €1,500 | §06 options |

*L1 ≈ 180 h = design 24 + pages 20 + forms 12 + back-office 12 + Console 44 + SEO 12 + GDPR/measurement 8 + infra 12 + QA 14 + handover 10 + PM 12.*
*L2 ≈ 46 h = catalogue 14 + congress admin 18 + QA 8 + PM 6.*

---

## C. Page and section table (page 3): 20 h

Planned page count: **≈ 20 content pages + 3 legal pages**, plus generated congress listing pages. ASSET supplies or approves all copy.

| # | Page | Requirement | We build | Acceptance | Status | Gap and how we close it | Hours | § |
|---|---|---|---|---|---|---|---|---|
| C-1 | Homepage | B2B positioning, three service areas, approved evidence, upcoming congresses, client area | Hero + 3 activity cards (1 click to each); proof strip (only approved claims); "Upcoming congresses" block fed from the catalogue (next 6 published, by date); "Client area" link (configurable) | Each activity 1 click; congress block shows only published, future events | PARTIAL (templates exist) | Congress block is new (↳ L) | 3 | §03.1 |
| C-2 | Business Travel | Advice, online/offline services, support, FAQ, travel review request | Service page template; FAQ block (editable); CTA → F01 with "travel review" preset | F01 within 2 clicks of home | EXISTS (template) | Copy from ASSET | 2 | §03.1 |
| C-3 | SMEs and microbusinesses | Simplified offer, use cases, demo or account request | Audience page; use-case cards; CTA → F01 preset "account/demo request" (tracked as account request) | Account-request event fires | EXISTS (template) | — | 1.5 | §03.1 |
| C-4 | Procurement and travel managers | Travel policy, reporting, expenses, invoicing, travel audit | Audience page with 5 sections; CTA → F01 preset "travel audit" | — | EXISTS (template) | — | 1.5 | §03.1 |
| C-5 | Assistance and expertise | Support, emergencies, ticketing, reflecting services actually available | Service page; emergency contact block. **Only services ASSET confirms in the claims register** | Every claim on the page appears in the signed claims register | PARTIAL | Claims register is new (D6) | 1.5 | §03.1 |
| C-6 | Digital solutions | Approved Wondermiles presentation, authorised images, demo request, client access | Page with Wondermiles section (approved text/images only); demo CTA → F01; client-area button (config URL, click event) | T08; image-rights note per image | PARTIAL | Wondermiles assets and rights UNKNOWN (Q16) | 1.5 | §03.1, §04 |
| C-7 | MICE | Hub, groups and seminars, incentives, conventions; brief and quotation request | Hub + 3 sub-pages (4 pages); CTA → F02 progressive brief | F02 within 2 clicks | EXISTS (template) | — | 3 | §03.1 |
| C-8 | Congresses | Filterable catalogue and listing with source, dates, flight quotation request | Catalogue landing (intro, search); catalogue and listings built in L | T03 | PARTIAL | ↳ L | 0.5 | §03.2 |
| C-9 | Agency and resources | Verified presentation, authorised team details and references, editable articles, guides, FAQ | Agency page; resources hub; article and guide templates (Console-editable); FAQ page; team/references only with authorisation | Veena creates an article (T15) | PARTIAL | Article editing ↳ I | 3 | §03.1 |
| C-10 | Contact and legal | Three distinct commercial journeys, legal notices, privacy, cookies | Contact page with 3 doors (BT/MICE/Congress → F01/F02/F03); mentions légales (French legal notices), privacy, cookie pages from ASSET-approved text | Each door opens the right form; legal pages approved by ASSET | EXISTS (Jitendra pattern) | Legal text approval by ASSET | 2.5 | §03.1, §04 |
| | **Subtotal pages** | | | | | | **20** | |

## D. Priority user journeys and design expectations (page 3)

| # | Requirement | We build | Acceptance | Status | Gap and how we close it | Hours | § |
|---|---|---|---|---|---|---|---|
| J-1 | SME owner: SME page → benefits/FAQ → account/demo request → qualification by ASSET | C-3 → F01 preset → enquiry type "SME account" → owner assigned → status "qualified" | Walk-through recorded in acceptance report | PARTIAL | ↳ C, F, G | ↳ | §03.1 |
| J-2 | Travel manager: Business Travel → approach/evidence → travel review and contact | C-2/C-4 → proof → F01 "travel review" | Same | PARTIAL | ↳ | ↳ | §03.1 |
| J-3 | HR/comms: MICE → services → progressive brief → callback | C-7 → F02 (3-4 steps + summary) → callback request field | Same | PARTIAL | ↳ F02 | ↳ | §03.1 |
| J-4 | Congress participant: search → listing → itinerary and contact → quotation by ASSET | L catalogue → listing → F03 pre-filled → enquiry linked to congress ID → team notified | T03, T06 | PARTIAL | ↳ L, F03 | ↳ | §03.2 |
| J-5 | Existing client: client area → authorised external tool, no password in CMS | "Client area" button → configured Wondermiles URL (new tab); click event; no login fields on our site | T08 | EXISTS (simple link) | URL UNKNOWN (Q16) | ↳ (0.5 in I) | §03.1 |

**Design expectations: 24 h**

| # | Requirement | We build | Acceptance | Status | Gap and how we close it | Hours | § |
|---|---|---|---|---|---|---|---|
| D1 | Key forms in 2-3 clicks; no account needed for prospects | Site map (information architecture) checked per journey; no login anywhere public | Click-count table in J2 pack | EXISTS (practice) | — | 1 | §03.1 |
| D2 | Premium, understated design, readable typography | Typography and colour tokens; concept in `site/` as a starting point | J2 approval | PARTIAL | Concept exists; full system new | ↳ D4 | §03 |
| D3 | Authorised photography | Image brief; rights field per media item in the Console | Every image has a rights note | MISSING | Rights field added in I4 | 1 | §03, NEW content § |
| D4 | Reusable components / design system | ≈ 8 templates, ≈ 15 components, documented on one design-system page | Design-system page delivered | PARTIAL | — | 6 | §03.1 |
| D5 | Wireframes | Low-fidelity wireframes of the 8 templates, desktop and mobile | J2 | PARTIAL | — | 5 | §05 J2 |
| D6 | Desktop and mobile mock-ups | High-fidelity mock-ups at 375 and 1440 | J2 | PARTIAL | — | 7 | §05 J2 |
| D7 | Prototype | Clickable HTML prototype on staging (our medium is code, not Figma) | Link in J2 pack | EXISTS (site-redesign skill) | State that "design files" means the code-based design system + exported PNGs | 3 | §05 J2 |
| D8 | ASSET approves commercial claims, logos, testimonials | Claims register (claim, source, page, ASSET OK + date) | Signed register before J5 | MISSING | New template | 1 | NEW content § |
| | **Subtotal design** | | | | | **24** | |

---

## E. Forms F01-F06 (page 4): 12 h

| # | Requirement | We build | Acceptance | Status | Gap and how we close it | Hours | § |
|---|---|---|---|---|---|---|---|
| F01 | BT: company, name, business email, phone (as appropriate), company category, estimated volume, requirement, comments; save + acknowledge | Single-page form; category and volume as selects; phone optional; on submit: durable save → acknowledgement email + on-screen confirmation | T01 | EXISTS (Jitendra forms) | Fields new; reply-time text UNKNOWN (Q10) | 2 | §03.1 |
| F02 | MICE: event type, destinations, flexible dates, traveller count, services, optional budget, contact; clear summary before submit | 3-4 step progressive form; back button keeps data; review screen; budget optional | T02 incl. summary screen | PARTIAL | Multi-step is new | 3 | §03.1 |
| F03 | Congress: pre-filled event, departure, destination, dates, travellers, class, contact; not restricted to one airport | Opened from a listing with congress ID (hidden) + visible congress name; departure free text with airport suggestions; multiple departures allowed (if Q15 says yes) | T06 | PARTIAL | Multi-departure rule UNKNOWN (Q15) | 2 | §03.2 |
| F04 | Server-side validation, anti-spam, duplicate prevention, privacy info, send log, fallback if notification fails | Worker validation (schema); Turnstile; dedup rule (same email + type + congress within 24 h → event added to the first record); privacy notice + version stored; `send_log` table; email Brevo → fallback Resend → flag + 15-min retry + Console banner; durable write before "thank you" (backup store if D1 fails) | T01-T02 incl. email provider deliberately broken | PARTIAL (validation, Turnstile EXIST; KV save PARTIAL) | Dedup, send log, two-provider fallback new | 3 | §03.1, §04 |
| F05 | Configurable recipients by activity; saved in admin with status, owner, history, CSV export | Recipient table editable in the Console (admin only); inbox ↳ G | T01-T02 routing | PARTIAL | Recipients UNKNOWN (Q9) | 1 | §03.3 |
| F06 | No personal data in URLs or analytics; conversion events respect cookie preferences | POST-only forms; confirmation URL carries no data; event beacon strips query strings; events sent only per consent setting (H) | T09; a crawl of analytics payloads shows no email or phone | EXISTS (pattern) | Verification script ↳ Q | 1 | §04 data protection |
| | **Subtotal forms** | | | | | **12** | |

## F. CRM integration (page 4): option, 6 h, €500

| # | Requirement | We build | Acceptance | Status | Gap and how we close it | Hours | § |
|---|---|---|---|---|---|---|---|
| CRM-1 | API or webhook, quoted separately if the tool is not selected; core forms work without it | Outbound connector fired after the durable save (never before) | Forms pass with the connector off | MISSING | CRM UNKNOWN (Q9) | 6 (option) | §06 options |
| CRM-2 | Describe authentication, data, duplicates, errors, recovery, maintenance | **Auth:** API key/OAuth stored as a Worker secret. **Data:** mapped enquiry fields, no consent-less marketing fields. **Duplicates:** look up by email, then update or create. **Errors:** 3 retries with back-off, then a dead-letter list in the Console + alert. **Recovery:** "resend" button and a bulk replay. **Maintenance:** API version pinned, checked monthly in the plan | Spec in proposal | MISSING | **Add this spec text to the CRM option row** | ↳ | §06 options |

## G. Enquiry data model and back-office (page 4): 12 h

| # | Requirement | We build | Acceptance | Status | Gap and how we close it | Hours | § |
|---|---|---|---|---|---|---|---|
| G1 | Fields: identifier, type, date, source/campaign, contact, congress reference, status, owner, consent record | D1 `enquiry` (ULID, a sortable unique ID; type; created_at; utm_source/medium/campaign; landing page; referrer domain; contact fields; congress_id; status; owner_id; privacy_notice_version; marketing_optin + timestamp) | Schema in documentation | MISSING (D1) | New | 1.5 | NEW data § |
| G2 | Inbox with status, owner, history | Console inbox: filters (type, status, owner, date); detail view; statuses new → contacted → qualified → quoted → won/lost/spam; owner select; `enquiry_event` history (who, what, when) | T01-T02, T06 | PARTIAL (Jitendra approve) | Owner + history new | 7 | §03.3 |
| G3 | CSV export | Role-gated CSV export (commercial viewer and above); export logged | T14 | PARTIAL | Logged export new | 1 | §03.3 |
| G4 | Propose validation, retention and export rules for ASSET approval | **Validation:** schema per form. **Retention (proposal):** prospects 3 years after last contact (CNIL prospect guidance; verify), spam deleted after 30 days, won clients per ASSET's own records policy. Nightly purge job. **Export:** CSV UTF-8, documented columns | Rules approved at J1 | MISSING | **Add the rules to the proposal** | 1.5 | NEW data § |
| G5 | Routing configuration | Recipient-by-activity UI (with F05) | Routing test | MISSING | — | 1 | §03.3 |
| | **Subtotal back-office** | | | | | **12** | |

## H. Conversion measurement (page 4): 4 h (+ GDPR 4 h in V)

| # | Requirement | We build | Acceptance | Status | Gap and how we close it | Hours | § |
|---|---|---|---|---|---|---|---|
| H1 | Track CTA clicks, form starts, submissions, errors, congress searches, listing views, account requests, client-area clicks | First-party event beacon → Worker → D1 `event` table (no cookie, no IP stored); Cloudflare Web Analytics for page views. GA4/LinkedIn only if ASSET keeps them, behind consent | Event test in T09; sample events in acceptance report | MISSING | New beacon; Cloudflare Web Analytics does not cover custom events | 2 | NEW measurement § |
| H2 | Distinguish source, page and activity with no personal data | Dimensions: page path, activity (BT/MICE/CONG), UTM source/medium/campaign, referrer domain; search events store filter values and sanitised query text (dropped if it looks like an email or phone) | Payload check shows no personal data | MISSING | — | 0.5 | same |
| H3 | Baseline in discovery; targets after audit | Baseline from current analytics in L0; monthly comparison table in the plan report | Baseline in J1 pack | PARTIAL | Current trackers UNKNOWN (Q6) | ↳ L0.5 | §05 |
| H4 | (implied) Reporting | Simple Console dashboard: counts by event, activity, week | Visible to commercial viewer | MISSING | — | 1.5 | §03.3 |
| | **Subtotal measurement** | | | | | **4** | |

## I. Administration permissions and ASSET Console (page 4): 44 h

| # | Requirement | We build | Acceptance | Status | Gap and how we close it | Hours | § |
|---|---|---|---|---|---|---|---|
| I1 | Roles: technical admin, editor (Veena), contributor, commercial viewer, Congress/fare approver; least privilege | `role` + permission matrix enforced in every API route. **Contributor:** drafts only. **Editor:** publish. **Viewer:** enquiries read and export. **Approver:** only role that sees the vault and sets "approved for sale". **Admin:** everything | Permission test matrix (role × action) in the acceptance report; T05 | MISSING (only Basic Auth today) | New | 6 | §03.3 |
| I2 | Administrator MFA | Cloudflare Access in front of `/admin`, MFA enforced by ASSET's IdP (Microsoft 365 or Google Workspace). If none: in-app TOTP (+6 h from contingency). Command-line break-glass for the tech admin only | Login without a second factor is refused | MISSING | **IdP UNKNOWN: add to questions**; Access free tier ≤ 50 users (unverified) | 4 | §04 |
| I3 | Page/content editing without a developer | Structured block editor: fixed section types (hero, text, cards, FAQ, CTA, image), fields per block, live preview on staging; publish triggers a rebuild ("live in about N min", N measured) | T15 | MISSING | Largest new build | 14 | §03.3 |
| I4 | (implied) Media | R2 media library: upload, alt text (required), rights note, automatic resizing | Image without alt text cannot be published | MISSING | — | 4 | §03.3 |
| I5 | Content versions and restoration | `revision` snapshot on every save (page, congress); compare and restore (restore creates a new revision) | Edit → restore → content back (T15 dataset) | MISSING | — | 5 | §03.3 |
| I6 | Access logs | `audit_log`: user, action, object, time; Access login logs kept; 12-month retention (proposal) | Log shows a T15 session | MISSING | — | 3 | §03.3, §04 |
| I7 | Protection against accidental deletion | Soft delete (`deleted_at`) + 30-day trash + confirm dialog; hard delete admin-only | Delete → restore from trash | MISSING | — | 2 | §03.3 |
| I8 | Editorial workflow: draft → approval → publication; back to draft without data loss | Status per page/congress; "submit for approval" (contributor) → "approve and publish" (editor); "return to draft" keeps all fields + revision | T04; return-to-draft test | PARTIAL (medspa approval pipeline) | Port the pattern to D1 | 4 | §03.2, §03.3 |
| I9 | (implied) Publish pipeline | Deploy hook with de-duplication (5 presses = 1 build); draft content never in the public build | T04 | PARTIAL (staging previews) | — | 2 | §04 |
| | **Subtotal Console** | | | | | **44** | |

---

## L. Congress catalogue C01-C07 (page 5): public 14 h + admin 18 h

| # | Requirement | We build | Acceptance | Status | Gap and how we close it | Hours | § |
|---|---|---|---|---|---|---|---|
| C01 | Create/edit through the CMS and CSV import; validate fields; detect duplicates | Console congress form with validation (dates ordered, URL valid, required fields); CSV import ↳ N | Invalid record refused; duplicate flagged | PARTIAL (GreenJobs listings) | Form new | 3 (admin) | §03.2 |
| C02 | Text search; filters (discipline, country, period, city, name); ascending date sort; pagination; no-results state | Client-side search over a pre-built index (300 records is small); filter bar (touch and keyboard); date-ascending default; 20 per page; no-results message with "reset filters" + contact link | T03 | PARTIAL (GreenJobs filters) | Search index + period filter new | 6 | §03.2 |
| C03 | Publication status separate from business authorisation; no internal status or evidence on the public listing | Editorial status on `congress`; business workflow only in the private DB (M); public build reads a public view only | T04; HTML scan shows no internal status words | MISSING | Separate DB | 3 (admin) | §03.2, §04 |
| C04 | Protect GM&E codes and evidence; exclude from HTML, scripts, public responses, public exports, browser | Separate D1 database bound only to the admin Worker; code encrypted at rest (key in a Worker secret); evidence files in a private R2 bucket; approver-only API; **leak scanner** ↳ T05 | T05 | MISSING | New | 3 (admin) | §03.2, §04 |
| C05 | Preferential-fare claims only after human approval of the right to sell; no claim of official agency status without authorisation | Public flag `fare_badge` set only by an approver when the stage = "approved for sale"; badge text from approved copy; no "official agency" wording unless ASSET documents authorisation | Badge absent until approved (T05 dataset) | MISSING | Wording UNKNOWN (Q13) | 1 (admin) | §03.2 |
| C06 | Show official source and verification date; approved rule for past events and SEO | Listing shows "Official website" + "Verified on dd/mm/yyyy". **Proposed past rule:** after the end date, "Past edition" banner, quote form off, link to next edition; stays indexable 12 months, then 301 to next edition or the discipline page (for ASSET approval, Q14) | T07 | MISSING | Rule needs approval | 2 (public) | §03.2 |
| C07 | Link each ticket enquiry to the congress ID; notify team; save; no automatic issuance | F03 carries congress_id; enquiry type CONG; routed per F05; no ticket logic anywhere | T06 | PARTIAL | — | ↳ E, G | §03.2 |
| L-pub | (implied) Listing page template, sitemap, homepage block, structured data | One page per published congress (slug); listing sitemap; schema.org `Event` with the real organiser (check Google event policy) | Rich-results test on 3 listings | PARTIAL | — | 3 + 1 + 1 + 1 = 6 (public) | §04 SEO |
| | **Public subtotal:** C02 6 + C06 2 + L-pub 6 = **14** | | | | | | |

## M. Business workflow (8 stages) and editorial workflow (page 5)

All business stages live in the private DB, are visible to the approver and admin only, and record user, time and note.

| # | Stage / requirement | We build | Acceptance | Status | Gap and how we close it | Hours | § |
|---|---|---|---|---|---|---|---|
| M1 | Detected | Created manually, by CSV, or by L4 candidate | Stage history row | MISSING | State machine new | 3 for M1-M8 (admin) | §03.2 |
| M2 | Verified | Requires source URL + verification date | Cannot advance without both | MISSING | ↳ | ↳ | |
| M3 | GM&E application to prepare | Checklist field | — | MISSING | ↳ | ↳ | |
| M4 | Application submitted | Application date + channel | Required fields | MISSING | ↳ | ↳ | |
| M5 | Code received | Encrypted code + evidence upload + validity period | Approver only | MISSING | ↳ | ↳ | |
| M6 | Ticket issuance authorised | Approver sign-off (named) | Only approver role | MISSING | ↳ | ↳ | |
| M7 | Approved for sale | Unlocks the C05 badge option | Badge only after M7 | MISSING | ↳ | ↳ | |
| M8 | Archived | Read-only; code kept until validity ends + retention (proposal) | Archived records not editable | MISSING | ↳ | ↳ | |
| M9 | Editorial: draft → approval → publication; return to draft without loss | ↳ I8 | T04 | PARTIAL | ↳ | ↳ I8 | §03.2 |
| M10 | Management confirms approvers and pre-promotion conditions | Approver list configurable by admin; conditions as a checklist on M7 | Configured at J4 | MISSING | Approvers UNKNOWN (Q12) | 1 (admin) | §03.2 |

## N. Structured data and scalability/import (page 5)

| # | Requirement | We build | Acceptance | Status | Gap and how we close it | Hours | § |
|---|---|---|---|---|---|---|---|
| N1 | Congress fields: ID, title, slug, discipline, country, city, venue, organiser, start/end dates, timezone where useful, official website, verification date, language, status, visibility | D1 `congress` with exactly these columns + created/updated/deleted_at | Schema doc | MISSING (D1) | ↳ C01 | ↳ | NEW data § |
| N2 | Private authorisation: congress ref, application date and channel, protected code, evidence, conditions, status, approver, validity period | `authorisation` in the private DB with these columns; code encrypted | Schema doc; T05 | MISSING | ↳ C04 | ↳ | NEW data § |
| N3 | Document the CSV schema, required fields, errors | Versioned CSV schema (v1): column list, required/optional, formats (ISO dates, ISO country codes), error codes per row | Schema doc in proposal annex | MISSING | **Write the schema into the proposal** | ↳ N5 | NEW § |
| N4 | Duplicate handling | **Hard duplicate** (normalised title + start date + city) → rejected. **Soft duplicate** (same normalised title, same year) → flagged for a human | Import report shows both cases | MISSING | — | ↳ N5 | §03.2 |
| N5 | Process for importing 300 listings | Upload → dry run (writes nothing) → report (OK / rejected / flagged) → confirm → import as drafts → editor publishes in bulk | 300-row test file imported (T03 dataset) | PARTIAL (GreenJobs import scripts) | Dry-run and report new | 5 (admin) | §03.2 |
| N6 | Exports | Public CSV (public fields only) + internal CSV (admin only; no codes ever) | T14; T05 scans the public export | PARTIAL | — | 1 (admin) | §03.2 |
| N7 | Change log | `revision` + `audit_log` rows for every create/edit/import | Log shows the import batch | MISSING | ↳ I5/I6 + batch ID | 1 (admin) | §03.2 |
| N8 | FR and EN versions: URLs, canonicals, hreflang | `/fr/congres/{slug}`, `/en/congresses/{slug}` (EN off until the option); canonical per language; hreflang pairs | hreflang validator on 3 pages | EXISTS | — | ↳ S3 | §04 SEO |
| N9 | AI option: approval queue, source, confidence, quotas, audit trail; human approval | ↳ L4 | — | PARTIAL | Option | ↳ L4 | §06 |
| | **Admin subtotal:** C01 3 + C03 3 + C04 3 + C05 1 + M 3 + M10 1 + N5 5 + N6 1 + N7 1 = **21**. Budget is 18; the 3 h overrun comes from contingency (flagged) | | | | | | |

---

## P. Architecture (page 6): within infrastructure, 12 h total (P + Q)

| # | Requirement | We build | Acceptance | Status | Gap and how we close it | Hours | § |
|---|---|---|---|---|---|---|---|
| P1 | Fast, indexable public frontend | Astro static pages on Cloudflare (CDN, a global network of servers) | Lighthouse lab per template | EXISTS | — | ↳ | §04 |
| P2 | CMS with structured catalogue | ASSET Console (I) + congress model (N) | J3/J4 | MISSING | ↳ | ↳ | §04 |
| P3 | Enquiry management | ↳ G | | MISSING | ↳ | ↳ | §04 |
| P4 | Decoupled third-party interfaces | Email (Brevo/Resend), CRM webhook, client-area URL, optional SSO/AI behind config flags | Options off → core works | EXISTS (pattern) | — | ↳ | §04 |
| P5 | Diagram | One-page diagram: visitor → CDN (static) / Worker (forms) → D1 public + D1 private → R2; Console behind Access; email providers; monitors; backups | Diagram in proposal | MISSING | **Add to the PDF** | 1 | NEW §04 |
| P6 | Data flows | Table: enquiry flow, publish flow, import flow, authorisation flow, backup flow | In proposal | MISSING | Add | ↳ P5 | NEW §04 |
| P7 | Dependencies | List: Cloudflare (Pages, Workers, D1, R2, Access, Turnstile, Web Analytics), Brevo, Resend, UptimeRobot, GitHub, second backup provider (TBD) | In proposal | MISSING | Add | ↳ P5 | NEW §04 |
| P8 | Costs | Tool table: Workers Paid $5 (≈ €4.3) per month; D1/R2/Access/Turnstile/Analytics €0 at this size; Brevo €0 (Starter ≈ €7-9 if the daily cap bites); Resend €0; UptimeRobot €0; total ≈ €5-15/month, all paid by ProdCraft inside the plan | In proposal | MISSING | Add (from `infra_costs_2026.md`) | ↳ | NEW §04 |
| P9 | Reasonable alternative to the recommended CMS | Headless Directus + same Astro front. **Indicative:** extra server ≈ €10-30/month (VPS + Postgres range in research) + ≈ 16 h setup (≈ €1,100 at €70/h); patching load on the supplier | Costed in proposal | PARTIAL ("costed on request") | **Give the indicative cost**; "on request" reads as a partial response | ↳ | §04 |
| P10 | Secrets/business data handled server-side | All writes via Worker; Worker secrets; nothing secret in client JS | Repo + bundle secret scan | EXISTS (SAST hooks) | — | ↳ Q10 | §04 |

## Q. Environments and security (page 6)

| # | Requirement | We build | Acceptance | Status | Gap and how we close it | Hours | § |
|---|---|---|---|---|---|---|---|
| Q1 | Separate dev, staging, production | Local Wrangler (Cloudflare's command-line tool) + local D1; staging (own D1/R2); production; CI deploy | Three URLs/DBs listed | PARTIAL | D1 new | 3 | §04 |
| Q2 | Restrict access to staging; prevent indexing | Access in front of staging + `X-Robots-Tag: noindex` + robots disallow | Anonymous request → login; header present | PARTIAL (staging previews) | Access new | 0.5 | §04 |
| Q3 | HTTPS | Cloudflare TLS, HSTS (forces HTTPS), security headers (CSP etc.) | Header scan | EXISTS | — | 1 | §04 |
| Q4 | CMS hardening | No public admin URL (Access); rate limits on form endpoints; least privilege (I1) | ZAP baseline scan clean of high-severity issues | MISSING | ↳ I | ↳ | §04 |
| Q5 | Updates | Dependabot/Renovate PRs (automated update requests); monthly patch window; critical within 2 business days | Patch log | PARTIAL | — | 1 | §06 plan |
| Q6 | Access control | ↳ I1, I2 | | MISSING | ↳ | ↳ | §04 |
| Q7 | Form protection | Turnstile, validation, rate limit, dedup | T01-T02 | EXISTS/PARTIAL | ↳ F04 | ↳ | §04 |
| Q8 | Proportionate logging | Audit log (I6), send log (F04), Worker error log (no personal data), 12-month retention (proposal) | Log samples | MISSING | ↳ | ↳ | §04 |
| Q9 | Appropriate security testing | SAST pre-push (exists) + dependency audit + OWASP ZAP baseline (a free automated web-security scanner) on staging + leak scanner (T05) + role matrix test | Reports in the acceptance pack | PARTIAL | ZAP new (0.5 h ↳ QA) | ↳ T | §04 |
| Q10 | No secrets in repo or browser | Worker secrets; pre-commit secret scan; bundle scan | Scan report | EXISTS | — | 0.5 | §04 |
| Q11 | (implied, operations) Backups | Nightly cron D1 export → R2; Time Travel 30 days; weekly copy to a second provider (TBD) | T13 | MISSING | Second provider unpriced | 3 | §06 plan |
| Q12 | (implied) Monitoring | 4 UptimeRobot monitors + status page + dead-man alarm on backups + `/api/health` | Alert test | PARTIAL (health endpoint) | New | 1.5 | §06 plan |
| Q13 | (implied) Break-glass | Runbook: deploy/rollback/query via API token from the command line | Runbook step tested | MISSING | — | 0.5 | handover |
| | **Infrastructure subtotal:** P5 1 + Q1 3 + Q2 0.5 + Q3 1 + Q5 1 + Q10 0.5 + Q11 3 + Q12 1.5 + Q13 0.5 = **12** | | | | | | |

## R. Wondermiles and partners (page 6)

| # | Requirement | We build | Acceptance | Status | Gap and how we close it | Hours | § |
|---|---|---|---|---|---|---|---|
| R1 | Core: presentation page, demo/account request, configurable client-area link, click measurement; no client passwords in the CMS | C-6 + J-5 + H1 click event; URL editable by admin | T08 | EXISTS (link) | URL and approved assets UNKNOWN | ↳ C-6 | §03.1, §04 |
| R2 | L3: SSO feasibility on protocols actually available and contractually authorised; success, failure, logout journeys; API and account automation specified separately | L3a written study with the three journeys diagrammed; L3b only if SAML/OIDC is offered; L3c quoted after L3a | Study approved | MISSING | Wondermiles docs UNKNOWN (Q16) | 4 / 12 (option) | §06 options |
| R3 | No assumed Air France-KLM API or autonomous ticketing; partners confirm GM&E | Explicit statement; manual GM&E workflow (M) | Statement in proposal | PARTIAL | **Add the sentence to §04** | 0 | §04 |

## V. Data protection (page 6): 4 h

| # | Requirement | We build | Acceptance | Status | Gap and how we close it | Hours | § |
|---|---|---|---|---|---|---|---|
| V1 | Privacy information and lawful basis per form | Short notice under each form + link; lawful basis stated (pre-contractual steps / legitimate interest; ASSET to confirm) | ASSET approves the wording | EXISTS (Jitendra) | — | 0.5 | §04 |
| V2 | Marketing boxes unticked; opt-out | Unticked checkbox; unsubscribe link in any marketing email; opt-out recorded | Visual check + record | EXISTS | — | 0.5 | §04 |
| V3 | Trackers by purpose; prior choice; refuse/withdraw | Consent banner (exists) gating any non-exempt tracker; "cookie settings" link in the footer | T09 | EXISTS | — | 1 | §04 |
| V4 | Retention and deletion | ↳ G4 purge job | Rules approved | MISSING | ↳ | ↳ | NEW data § |
| V5 | Subprocessors, hosting, transfers | Register: Cloudflare (US parent; EU D1 jurisdiction; DPA with SCCs, the EU's standard contract clauses, and DPF, the EU-US Data Privacy Framework), Brevo (FR), Resend (US), UptimeRobot, GitHub | Register in proposal | MISSING | **Add the table** | 0.5 | §04 |
| V6 | DPA where applicable | ProdCraft as processor; DPA template annexed to the contract | Signed with contract | MISSING | Draft the DPA | 0.5 | §08 |
| V7 | ASSET approves wording and settings before launch | Item on the J5 checklist | Approval email | EXISTS (practice) | — | ↳ J5 | §05 |
| V8 | Do not publish traveller data, bank details, private codes, evidence | No such fields public; leak scanner covers codes; no payment fields at all | T05 | PARTIAL | ↳ | ↳ | §04 |
| V9 | Internal procedure for data subject requests | DSR runbook (find/export/delete by email across tables) + Console action | DSR drill on staging | EXISTS (GDPR DSR flow) | Adapt to D1 | 1 | §04 |
| | **Subtotal GDPR** | | | | | **4** | |

## W. Ownership and supplier handover (page 6) + Maintenance and documentation (page 7): 10 h

| # | Requirement | We build | Acceptance | Status | Gap and how we close it | Hours | § |
|---|---|---|---|---|---|---|---|
| W1 | Domain, hosting, CMS and tool accounts under ASSET control | Cloudflare account, GitHub org, Brevo, UptimeRobot opened with ASSET's email; ProdCraft added as admin member; ProdCraft pays the bills inside the plan | Account register signed (L0.3) | EXISTS (practice) | **State billing transfer at exit** | ↳ | §03.4, §08 |
| W2 | Hand over custom source, Git repo, design files, data, media | Repo in ASSET's GitHub from day one; design system + exports; data and media export | J6 checklist | EXISTS | — | ↳ W4 | §03.4 |
| W3 | Identify non-transferable licences and dependencies | Table: none paid; fonts open licence; photos per ASSET rights; Wondermiles content per its terms | In proposal | MISSING | **Add the table** | 1 | NEW § |
| W4 | Documented full exports, backups, transfer to another supplier | Export script (all tables to JSON/CSV + R2 media zip); restore procedure | T14, T13 | MISSING | ↳ Q11 | 0.5 | §03.4 |
| W5 | Rights, maintenance, DPA, exit agreed in contract | Contract clauses list in §08 | — | PARTIAL | — | ↳ | §08 |
| W6 | Detail security fixes, updates, backups, monitoring, availability, out-of-scope work, optional on-call | Plan table (debate Common ground §2) + exclusions + on-call "available on quote" | In proposal | PARTIAL (99.9% wording wrong) | **Replace with the 99.5% wording** | ↳ | §06 |
| W7 | Illustrated administration guide | Guide with screenshots for every Console task | Veena follows it in T15 | PARTIAL | — | 3 | §05 handover |
| W8 | Deployment, restoration, export procedures | Runbook | A stranger-run test (Brockman) | PARTIAL | — | 2 | §05 |
| W9 | Account/licence inventory | ↳ L0.3, updated at J6 | — | MISSING | — | 1 | §05 |
| W10 | Secure transfer of secrets | Password-manager share; secrets rotated after transfer | Transfer logged | PARTIAL | — | 0.5 | §05 |
| W11 | Train Veena and a backup user | 2 sessions × 1.5 h (remote) + recording | Attendance + T15 | EXISTS (practice) | — | 3 | §05 |
| | **Subtotal handover** | | | | | **10** | |

---

## S. SEO migration plan (page 7): 12 h

| # | Requirement | We build | Acceptance | Status | Gap and how we close it | Hours | § |
|---|---|---|---|---|---|---|---|
| S1 | Crawl; inventory all URLs; decide retain/merge/redirect/remove per page | Crawl-to-inventory tool (status, title, canonical, inlinks, Search Console clicks) → decision sheet | Inventory approved at J1 | MISSING | Build the tool (new script + directive) | 4 | §04 SEO |
| S2 | Map old→new; permanent 301/308; no chains; no blanket redirect to home | Mapping sheet → generated `_redirects` (301); chain detector; ASSET approves priority URLs line by line | T10 | PARTIAL (302 only) | Switch to 301; add chain test | 2 + 2 = 4 | §04 SEO |
| S3 | Editable titles/descriptions, headings, readable URLs, structured data, sitemap, robots, canonicals | SEO fields per page and congress in the Console; one H1 rule; slugs; Organization/BreadcrumbList/Event; XML sitemap; robots; canonicals | SEO lint in CI | EXISTS (hreflang, sitemap, structured data) | Console fields new (↳ I3) | 2 | §04 SEO |
| S4 | Staging not indexable; check production indexing at cutover | ↳ Q2; cutover checklist step "noindex removed on prod" | Cutover log | EXISTS | — | ↳ | §05 J5 |
| S5 | Report broken links, 404s, redirects, indexable pages, analytics, performance; monitor Search Console after launch | Pre-launch report + weekly post-launch report through J6, then monthly | Reports | PARTIAL | — | 2 | §04, §06 |
| | **Subtotal SEO** | | | | | **12** | |

## U. Quality table (page 7) and content and assets

| # | Area | We build / measure | Acceptance | Status | Gap and how we close it | Hours | § |
|---|---|---|---|---|---|---|---|
| U1 | Responsive: 320, 375, 768, 1440 px + real devices; menus, filters, forms with touch and keyboard | Playwright screenshots at the 4 widths per template; real-device pass (devices UNKNOWN; list them) | T12 | EXISTS (Playwright) | Name the devices | ↳ T12 | §03.1 |
| U2 | Performance: LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1 at p75 where field data exists; lab reports per template | Lighthouse CI per template on every build; field data via Chrome UX Report only if published | Lab report per template | MISSING (tooling) | Build the gate; **reword the promise** | ↳ T12 | §04, §06 |
| U3 | Accessibility: WCAG 2.2 AA target; automated + manual on critical templates; defects documented | axe in Playwright; manual keyboard + screen reader (NVDA/VoiceOver) on the 5 journeys; defect log | T11 | MISSING (tooling) | Build the gate | ↳ T11 | §03.1 |
| U4 | Backups: automatic, tested restore; RPO 24 h, RTO 8 business hours; retention and coverage | ↳ Q11; retention 30 days point-in-time + 12 weekly off-platform copies (proposal); coverage: D1 public + private + R2 media | T13 | MISSING | — | ↳ | §06 |
| U5 | Availability: measurable SLA targets, alerts, response and resolution times, support hours, exclusions, cost | 99.5% target + table (debate §2) | Monthly report | PARTIAL (wrong figures) | Replace | ↳ | §06 |
| CA1 | ASSET validates services, identity, legal notices, affiliations, guarantees, evidence, images, rights | Claims register (D8) | Signed | MISSING | ↳ D8 | ↳ | NEW content § |
| CA2 | Supplier states page and listing counts, writing or migration, revisions, translation effort | **20 content + 3 legal pages; 300 listings; migration + light editing; 2 rounds; translation excluded** | In the price table | MISSING ("[25]") | **Fix in §05/§06** | 0 | §05, §06 |
| CA3 | Verify historical claims, contacts, notices from the old site before reuse | Old-site claims checklist in L0 → register | Signed | MISSING | ↳ | ↳ L0 | §05 |

## T. Acceptance tests T01-T15 (page 8): 22 h (L1 14 + L2 8)

| # | Scenario | Test we run (dataset → expected) | Status | Gap and how we close it | Hours | § |
|---|---|---|---|---|---|---|
| T01 | BT form: clear errors, saved once, routed, acknowledged | Invalid fields → inline errors; valid → 1 row; repeat → 0 new rows + event; BT recipient gets email; email provider broken → fallback | PARTIAL | Fallback test new | 1.5 | NEW acceptance § |
| T02 | MICE form: same | Same + summary screen + back-navigation keeps data | PARTIAL | — | 1.5 | same |
| T03 | Congress search, filters, sort, no-results | 300-row dataset; 10 queries with expected result sets; empty query → no-results state | PARTIAL | — | 1.5 | same |
| T04 | Draft not public before approval | Draft slug → 404 on production and absent from sitemap/search index | PARTIAL | — | 1 | same |
| T05 | GM&E code invisible to public and unauthorised roles | Leak scanner across all public output + seeded fake code proves detection; role matrix: only approver/admin read the vault | MISSING | Scanner new | 2.5 | same |
| T06 | Ticket enquiry with pre-filled event saved and notified | F03 from a listing → row with congress_id → CONG recipient email | PARTIAL | — | 1 | same |
| T07 | Past congress under the approved rule | Set end date in the past → banner, form off, link; 12-month redirect rule unit-tested | MISSING | Rule approval | 1 | same |
| T08 | Client-area link, no local password storage | Link goes to the configured URL; no password field or column anywhere (schema check) | EXISTS | — | 0.5 | same |
| T09 | Refusing non-essential trackers works and can be changed | Refuse → no tracker requests (network log); change → takes effect | EXISTS (banner) | Network-log check new | 1 | same |
| T10 | Priority old URLs redirect correctly | Every priority URL → one 301 → 200 | PARTIAL | ↳ S2 tool | 1 | same |
| T11 | Keyboard and screen reader on critical journeys | axe zero serious violations + manual script for 5 journeys | MISSING | ↳ U3 | 3 | same |
| T12 | Responsive + performance targets | 4 widths screenshots + Lighthouse per template within targets (lab) | PARTIAL | ↳ U2 | 2.5 | same |
| T13 | Successful test restoration | Restore staging DB from last night's dump into a fresh DB; timed against RTO | MISSING | ↳ Q11 | 1 | same |
| T14 | Readable, documented export | Export script output opened in a spreadsheet; columns match the doc | MISSING | ↳ W4 | 0.5 | same |
| T15 | Veena publishes then edits content without a developer | Veena, alone, using the guide: creates an article, publishes, edits, restores a revision | MISSING | ↳ I | 1 | same |
| T-x | Security scan + acceptance report compile | ZAP baseline 0.5 + report 0.5 | MISSING | — | 1 | same |
| | Launch blockers (page 8): security defect, data loss, failed form, code exposure, missing critical redirect → no launch; major defects need approval + dated plan; minor → outstanding list | Go/no-go checklist with these 5 blockers | | | ↳ J5 | §05 |
| | **Subtotal QA** | | | | **22** | |

## J. Delivery milestones J0-J6 (page 8): PM 18 h

| # | Deliverable requiring written approval | Planned date (pace A) | Status | Gap and how we close it | Hours | § |
|---|---|---|---|---|---|---|
| J0 | Team, access inventory, schedule, responsibilities | Ready Wed 18 Nov, approved Fri 20 Nov 2026 | PARTIAL | RACI new | 2 | §05 |
| J1 | Architecture, SEO inventory, baseline, backlog, risks | Fri 27 Nov / Wed 2 Dec 2026 | PARTIAL | ↳ L0 | 1 | §05 |
| J2 | Wireframes, mock-ups, design system | Fri 11 Dec / Wed 16 Dec 2026 | PARTIAL | ↳ D | 1 | §05 |
| J3 | Pages, CMS, forms, tracking on staging | Fri 15 Jan / Wed 20 Jan 2027 | MISSING | ↳ | 1 | §05 |
| J4 | Tested catalogue, filters, statuses, listings, enquiries | Fri 22 Jan / Wed 27 Jan 2027 | MISSING | ↳ | 1 | §05 |
| J5 | SEO migration, tests, fixes, training, backup and rollback plan; written go | Fri 5 Feb; go Mon 8 Feb; cutover Tue 9 Feb 2027 | MISSING | Rollback = Pages instant rollback + DNS revert plan | 2 | §05 |
| J6 | Monitoring, fixes, access, source, exports, outstanding items closed | Fri 5 Mar 2027 | PARTIAL | — | 1 | §05 |
| J-x | Realistic schedule with effort, dependencies, availability; payments against accepted milestones | Pace B latest: launch Fri 12 Mar 2027, J6 Fri 2 Apr 2027; payments 30/30/20/20 | PARTIAL | **Add effort-by-role, dependencies, latest date** | weekly updates 6 + change control ↳ A7 + revision coordination 2 = 8 | §05, §06 |
| | **Subtotal PM:** 9 + 8 + A7 1 = **18** | | | | | |

## K. Documents to submit, essential conditions, decisions to confirm (page 9)

| # | Requirement | What we deliver | Status | Gap and how we close it | § |
|---|---|---|---|---|---|
| K1 | Technical proposal in PDF: understanding, architecture and alternative, UX, security, SEO, data, maintenance, handover | PDF from the JSON | PARTIAL | Diagram, data §, costed alternative missing | all |
| K2 | Optional one-page Word form | Fill `form.txt` fields from the proposal (approach, €4,000 HT, €7,200 HT a year, start 16 Nov, ≈ 12 weeks, support summary, questions) | MISSING | 20 min, PM | — |
| K3 | Itemised quotation in EUR: HT, rate, VAT, TTC; core, options, annual costs, licences, third parties | Core table has HT/VAT/TTC | PARTIAL | **Options and plan tables need VAT + TTC columns; add an "annual costs" row and the third-party table** | §06 |
| K4 | Total core cost over 3 years, no double counting | €25,600 HT / €30,720 TTC | EXISTS | Keep; note that tools are inside the plan (not counted twice) | §06 |
| K5 | Verifiable B2B/travel/MICE/editorial references; named lead; effort by role | References + team table | PARTIAL | **Label concept vs commissioned; one named person; days by role** | §07 |
| E1 | ASSET control of accounts and data | ↳ W1 | EXISTS | — | §03.4 |
| E2 | Responsive and editable | ↳ U1, I | PARTIAL | — | §03 |
| E3 | Staging before cutover | ↳ Q2 | EXISTS | — | §04 |
| E4 | Documented SEO migration | ↳ S | PARTIAL | — | §04 |
| E5 | Protection of GM&E codes | ↳ C04, T05 | MISSING | — | §03.2 |
| E6 | Core independent of options; ticketing outside the CMS | ↳ A4, A9 | EXISTS | — | §05 |
| E7 | Transparent recurring costs, licences, handover | ↳ P8, W3 | PARTIAL | — | §06 |
| DC1 | Budget and schedule | Our price + dates; ask budget envelope (Q1-Q2) | — | — | §06 |
| DC2 | Existing technology | Q3-Q4 | UNKNOWN | — | §05 L0 |
| DC3 | Content and languages | Our counts (CA2); Q7-Q8, Q18 | UNKNOWN | — | §05 |
| DC4 | Commercial enquiries | Q9-Q10 | UNKNOWN | — | §03.1 |
| DC5 | Partners | Q13, Q16 | UNKNOWN | — | §04 |
| DC6 | Operations | Our plan table; Q20 | PARTIAL | — | §06 |
| — | Assessment: a partial response must explain the limitation, its impact and a proposed solution | "Known limitations" box: no 100% SLA; field CWV may be unavailable; solo team (continuity plan); MFA depends on the IdP; Wondermiles unknown | MISSING | **Add the box** | NEW §04 |

---

## Y. Hours reconciliation

| Line | Hours | Table |
|---|---|---|
| L0 audit + workshops | 12 | A |
| Design | 24 | D |
| Pages | 20 | C |
| Forms | 12 | E |
| Enquiry back-office | 12 | G |
| Measurement | 4 | H |
| GDPR | 4 | V |
| ASSET Console | 44 | I |
| Congress public | 14 | L |
| Congress admin | 18 (+3 overrun → contingency) | L, M, N |
| SEO | 12 | S |
| Infrastructure | 12 | P, Q |
| QA / acceptance | 22 | T |
| Handover / training | 10 | W |
| Project management | 18 | J, A7 |
| **Core** | **238** | |
| Contingency 20% (known draws: admin +3, in-app TOTP +6 if there is no IdP) | 48 | |
| **Planning figure** | **286** | ≈ €14/h on €4,000 |

Options: English 8 h · CRM 6 h · L3a 4 h · L3b 12 h · L4 16 h. The plan runs ≈ 10 h a month (≈ 5 operations + 5 included changes).

---

## Z1. Gaps not yet addressed in the proposal

1. Availability promise of 99.9% and "4 hours" outage response: unsustainable for one person with no on-call, and above what the research supports. "Zero downtime" isn't worded honestly.
2. Unlimited "content changes… on a rolling basis" inside €600; no change-request rate; a 3-month minimum makes the €4,000 build a loss if ASSET leaves early.
3. Team table has four "[name]" rows; no effort by role; no continuity or holiday answer for a solo supplier.
4. Required architecture diagram, data flows, dependencies and cost table are missing; the alternative is "costed on request" (reads as a partial response).
5. MFA is promised via authenticator app through Access, which needs ASSET's IdP (UNKNOWN). The Access outage dependency and break-glass aren't stated.
6. No CSV schema, duplicate rule, change log or import process; no enquiry data model, retention rules, conversion event list or CRM spec (authentication, data, duplicates, errors, recovery, maintenance).
7. [SITE FINDING] ×3 and [CONCEPT URL] placeholders. Unverified claims about the current site ("today's site does not give them one"; "the Congress catalogue does not exist yet").
8. Quality promises can't be measured as written ("Core Web Vitals targets met on every template"); no T01-T15 mapping table; QA tooling (axe, Lighthouse CI, leak scanner, crawl→redirect tool, restore drill) doesn't exist yet.
9. Content counts: "[25] pages" unsourced; no writing/migration/revision/translation statement; no claims register.
10. Options table lacks VAT/TTC; no annual-cost row; no third-party/licence table; the billing transfer at exit isn't described.
11. Payment schedule 30/30/40 front-loads risk onto the supplier.
12. Past-event rule (C06), fare-badge rule (C05) and approver list (M10) aren't proposed in the text.
13. No "known limitations" box (the RFP asks a partial response to explain limitation, impact and solution).
14. References: GreenJobs, MISB and Gaia URLs are `*-redesign.pages.dev`. If they are concepts rather than commissioned work, the proposal must say so.
15. Veena's surname and title ("Veena Khatri, Office Manager Assistant") don't appear in the RFP; verify them before sending.
16. The questions list lacks: identity provider (Microsoft 365 or Google Workspace?), real devices for testing, Search Console access.

## Z2. Exact edits to `execution/gtm_client_workflows/proposal_system/proposals/asset-voyages-v1.json`

Do not apply here; this is the list for the editor.

**Parties**

1. **`parties.client`:** set name and title only after verifying them (RFP says only "Veena"). Safe fallback: `"name": "Veena"`, `"title": "Operational coordination, ASSET Voyages Management"`.

**§01-§03**

2. **§01 paragraph** "I went through your Developer Brief…":
   - Replace "Developer Brief" with "requirements document (Version 0.4)".
   - Replace "and today's site does not give them one" with "and each needs its own route to the right person". Restore a site-specific claim only once `facts.md` confirms it.
3. **§02 three `[SITE FINDING: …]` paragraphs:** fill from `facts.md`. If it is still absent at send time, delete the bracketed sentence and keep the generic second sentence. Soften "The Congress catalogue does not exist yet" to "A searchable Congress catalogue is a new capability" unless the site research confirms it.
4. **§03 `[CONCEPT URL]`:** insert the deployed concept URL, or remove the sentence.
5. **§03.3 last sentence:** replace "multi-factor login for every administrator" with "multi-factor login for every administrator through ASSET's Microsoft 365 or Google Workspace account (or authenticator-app codes if neither is used)".

**§04 Technical approach**

6. **§04 bullet "Access":** append "If Cloudflare's login service is unavailable, the public site keeps serving; the technical administrator retains command-line access for deployment and rollback."
7. **§04 new h3 "Architecture, data flows and costs":** add after the bullets:
   - a diagram block (or an image reference);
   - the data-flow table (P6);
   - the dependency and cost table (P7-P8), with "≈ €5-15 a month, paid by ProdCraft inside the monthly plan";
   - the sentence "No Air France-KLM API access or automatic ticket issuance is assumed; GM&E arrangements are confirmed by the partners."
8. **§04 bullet "Reasonable alternative":** replace "(costed on request)" with "(indicative: about €1,100 HT extra set-up and €10-30 a month extra hosting)".
9. **§04 new h3 "Data model, import and retention":**
   - the enquiry fields (G1);
   - retention proposals (G4), marked "for ASSET approval";
   - the CSV schema summary, hard/soft duplicate rule, dry-run import process for 300 listings, and change log (N3-N7);
   - the past-event rule (C06) and fare-badge rule (C05), both "for ASSET approval".
10. **§04 new h3 "Conversion measurement":** the event list (H1), dimensions (H2), consent behaviour, and the L0 baseline.
11. **§04 "Data protection" paragraph:** append the subprocessor list (Cloudflare US parent / EU D1 jurisdiction / DPA with SCCs and DPF; Brevo FR; Resend US; UptimeRobot; GitHub) and "ProdCraft acts as processor under a data processing agreement annexed to the contract".
12. **§04 new h3 "Known limitations":**
    - no 100% availability;
    - field Core Web Vitals depend on Google publishing data;
    - single named supplier, with the continuity plan;
    - MFA depends on the IdP;
    - Wondermiles capabilities are unknown until L3a.

**§05 Scope of work**

13. **§05 L1 bullet:** replace "up to [25] pages" with "up to 20 French content pages and 3 legal pages, with copy supplied or approved by ASSET (we migrate and lightly edit it; two revision rounds per milestone)".
14. **§05 new bullet "Acceptance mapping":** add the T01-T15 table (scenario → test → evidence) from table T.
15. **§05 Milestones and Timeline:**
    - add the approval-by dates;
    - add "Contractual latest launch: Friday 12 March 2027";
    - change the "Mock-ups and design system approved" date to Wednesday 16 December 2026 (ready Friday 11 December);
    - add "Launch: Tuesday 9 February 2027 after written go on Monday 8 February".
16. **§05 Out of scope:** add "copywriting from scratch beyond light editing (quoted at the change-request rate)".

**§06 Investment**

17. **§06 note:** replace it with "The build price assumes the 12-month monthly plan below: the build is priced as part of a 12-month managed partnership. Payments are made against accepted milestones."
18. **§06 core table rows:** change 30/30/40 to:

    | Row | Amount |
    |---|---|
    | 30% at J0 approval | €1,200 |
    | 30% at J2 approval | €1,200 |
    | 20% at J4 approval | €800 |
    | 20% at launch acceptance | €800 |

19. **§06 options table:**
    - add the columns "VAT 20%" and "Incl. VAT": €750 → €150 / €900; €500 → €100 / €600; €400 → €80 / €480; €1,200 → €240 / €1,440; €1,500 → €300 / €1,800;
    - append the CRM spec text (CRM-2) to the CRM row.
20. **§06 monthly plan row:**
    - replace "content changes, new pages and congress updates requested by your team, applied on a rolling basis" with "up to 5 hours a month of content changes, new pages from existing templates and congress updates (logged in the monthly report; unused hours do not roll over)";
    - replace "Core Web Vitals and accessibility checks" with "Lighthouse speed and axe accessibility reports on every release and monthly";
    - add the columns VAT €120 / incl. VAT €720.
21. **§06 paragraph after the plan:** replace "Three-month minimum…" with "12-month minimum term from launch, then rolling monthly with 30 days' written notice. If ASSET ends the plan within the first 12 months, the remaining months of the minimum term are due. Accounts, code and data stay yours at all times. Work beyond the included hours is charged at €70 per hour excl. VAT, with a written quote before any change over one day, assessed for cost, schedule, security and SEO impact."
22. **§06 "How the plan is measured" table:**
    - **Availability:** use the EN wording from the debate (Common ground §3): 99.5%, external probe every 5 minutes.
    - **New row "Deployments":** "zero-downtime releases with instant rollback".
    - **Response time:** "Monday-Friday 9:00-18:00 Paris time; outage or failed form acknowledged within 4 business hours; other requests within 1 business day".
    - **Requested changes:** "within 2 business days, within the monthly allowance".
    - **Security:** "critical patches within 2 business days of release".
    - **Page speed:** "lab report per template every month (LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1); field data at the 75th percentile where Google publishes it".
    - **New row "Service credit":** 10% of the month's fee, capped at one month a year.
    - **New row "Exclusions":** maintenance announced 48 h ahead, force majeure, third-party host failures, content supplied by ASSET, weekends unless on-call is agreed.
    - **New row "Backups":** "nightly, 30-day point-in-time, weekly off-platform copy; quarterly timed restore drill".
23. **§06 three-year table:** keep the totals; add the row "Annual recurring cost: €7,200 excl. VAT / €8,640 incl. VAT"; relabel the licences row "€0 (tools paid by ProdCraft inside the plan; not counted twice)".
24. **§06 new short table "Third-party services and licences":** from P8 and W3, with who holds each account (ASSET) and who pays (ProdCraft during the plan; ASSET after exit).

**§07 Relevant work**

25. **§07 bullets:** append "(concept)" or "(client project)" truthfully to each reference. Lead with the live sites (Jitendra) and the closest pattern (GreenJobs listings).
26. **§07 Team table:** replace the four rows with a single named person and days by role (7-hour days):

    | Role | Person | Effort |
    |---|---|---|
    | Project lead, architecture and audit | Debanjan Mazumdar | ≈ 4 days |
    | UX and UI design | Debanjan Mazumdar | ≈ 3.5 days |
    | Full-stack development | Debanjan Mazumdar | ≈ 22 days |
    | Quality assurance and accessibility | Debanjan Mazumdar | ≈ 3 days |
    | Documentation and training | Debanjan Mazumdar | ≈ 1.5 days |
    | Contingency | | ≈ 7 days |
    | **Total** | | **≈ 41 days** |

    - Add: "French copy and claims validated by ASSET."
    - Add the sentence "ProdCraft uses AI-assisted engineering tools; all work is reviewed and accepted by the named lead."
    - Add a continuity sentence: repository in ASSET's name from day one; runbook; standard open-source stack.

**§08 Agreement**

27. **§08 paragraph:**
    - add the change-request clause (A7);
    - add the 12-month minimum term;
    - add that billing for tool accounts transfers to ASSET at exit;
    - add that a DPA is annexed;
    - add "Response time: one business day within the support window".

**Response form**

28. **Form:** fill `form.txt` (K2) from the final figures: core €4,000 HT (TVA 20%, €4,800 TTC); hosting and maintenance €7,200 HT a year; start 16 November 2026; ≈ 12 weeks to launch (latest 16).
