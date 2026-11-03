# 21 — Pivot audit: WordPress at €3,000 HT fixed (client email of 3 Nov 2026)

Internal. Audit only, no client-facing text yet. Sources: client email 3 Nov (Veena Khatri), operator decisions, `01_Questions_for_Veena.md`, live pages (`site/`, esp. `questions/` §3–§8), `01c_Reply_to_clarifications_2026-10-31.md`, `18_Payment_Terms_Vetting.md`, `16_Proposal_Carryover.md`, RFP `/tmp/rfp/brief.txt` (v0.4, still governing: T01–T15, essential conditions, GM&E, data protection, handover, SEO migration).

Headline risk: the RFP scope (audit J1, SEO migration, 300-congress import, GM&E protection, WCAG 2.2 AA, acceptance report, training, J6 stabilisation) plus four new items (consulting page, Savings Scan form, SmartFees presentation, Wondermiles page + corporate-account form) at €3,000 HT is only viable if every allowance is numbered and everything else is an exclusion or a change request. Anything left unbounded below is a margin leak.

---

## A. Technical auditor

**T1. Scope delta vs RFP.** New: consulting/cost-optimisation page, "ASSET Savings Scan" form, SmartFees presentation, Wondermiles page, corporate-account form, booking-platform link. Dropped to later: AI, contract analysis, billing, Wondermiles API/SSO. *Why:* our 31 Oct reply and §3 listed AI/Wondermiles as options; the new forms were never scoped. *Write:* a scope annex listing each template and form by name; options moved to "Phase 2, quoted separately, not part of this price".

**T2. Page allowance and what a "page" is.** Q9 default: up to 20 existing pages migrated + 3 legal pages, ASSET writes new copy. *Why:* "page" is the main unbounded item. *Write:* N templates (home, activity ×3, consulting, Wondermiles, SmartFees, contact/forms, congress list, congress single, legal, 404) + max X content pages total at launch built from those templates; a page = one URL built from existing templates and blocks; new template/new block type = change request. Copy supplied by ASSET final, in French; we paste, light edit only.

**T3. Forms count and routing.** Now at least 5: Business Travel, MICE, Congress ticket enquiry (prefilled event, T06), Savings Scan, corporate account (+ generic contact?). *Why:* T01–T02 require no duplication, routing, acknowledgement. *Write:* fixed list of N forms, max fields each, one recipient + one backup per form (Q19 default: one shared mailbox), acknowledgement email per form, field list supplied by ASSET by date X; Savings Scan fields unknown — assume ≤12 fields, no file upload (uploads = exclusion or bounded: PDF ≤10 MB, stored privately).

**T4. Congress catalogue data model.** Custom post type `congress` (+ taxonomies: specialty, city/country, month), ACF (free or Pro — decide) fields per RFP list: dates, venue, official URL, verification date, edition, status workflow (detected → verified → GM&E to prepare → submitted → code received → ticket). *Write:* the field list as annex; filters/sort/no-results (T03); one page per edition (Q22-area default); past-edition rule (Q22 default: stays online without quote button, T07).

**T5. "Independently manageable" catalogue.** Must mean: Veena creates, edits, imports, schedules, unpublishes, archives congresses and edits filter terms without a developer (T15); drafts not public (T04). *Write:* define it in those words; exclude new fields/filters (change request).

**T6. Import, dedup, allowance.** 01c point 5 / Q17 promised: template supplied with proposal, dry run, one import of ≤300 rows, rejection report, no research. *Write:* same on WP (WP All Import free/Pro or a custom WP-CLI importer — decide; Pro licence = client cost); dedup key = name + edition start date + city; re-imports after the first = ASSET self-service via the importer or change request.

**T7. Private GM&E meta.** RFP C04/T05: code + evidence never in HTML, REST API, feeds, search, sitemaps, exports to unauthorised roles. *Why:* WP exposes post meta via REST and ACF "show in REST"; media uploads are public by URL. *Write:* GM&E fields stored in a non-REST meta/separate table, capability-gated (custom capability `view_gme`), evidence files outside public uploads (protected directory or no file storage — just a reference), automated test proving absence from public responses.

**T8. Roles, MFA, logs, revisions.** Q27 default: 2 editors (Veena + backup), management reads enquiries and approves congresses, only Veena + management see GM&E. *Write:* custom roles (Editor-ASSET, Approver, Admin), 2FA plugin (e.g. WP 2FA / Two Factor, TOTP or security key — Q25 default), activity log plugin with retention (e.g. 12 months), post revisions limited (e.g. 20), approval = "Pending review" → Approver publishes.

**T9. Theme approach and concept reuse.** *Why:* concept is static HTML/CSS; reuse saves budget but needs conversion. *Write:* lightweight block theme (or child of a free base theme such as GeneratePress/Kadence free) carrying the concept's design tokens; Gutenberg block patterns = the "fixed list of section types" promised in 01c §2; no page builder (Elementor/Divi) to avoid lock-in and licences. Name it in the proposal.

**T10. Plugin list and licences.** *Write:* table: plugin, purpose, free/paid, annual cost, licence holder (ASSET), renewal date, who renews (ASSET unless care plan). Prefer free: ACF free, a free form plugin vs Gravity Forms/WPForms Pro (entries + CSV + routing usually paid) — decide; SMTP, 2FA, security, backup, cache, cookie consent, redirects, SEO (Yoast/Rank Math free), Polylang (only if EN). Operator: all licences billed to client; ProdCraft may set them up, in ASSET's name.

**T11. Hosting prerequisites.** PHP ≥ 8.2, MySQL 8 / MariaDB 10.6+, HTTPS (Let's Encrypt), SSH/WP-CLI, staging environment (RFP essential condition: staging before cutover), daily off-site backups ≥30 days (Q29 default promised 30 days — PITR "any minute" no longer true), EU data centre (Q26 default), PHP mail disabled in favour of SMTP. *Write:* minimum host spec + 2–3 recommended French/EU hosts (e.g. o2switch, OVH, Infomaniak, Kinsta) with indicative monthly prices; hosting contract direct between ASSET and host.

**T12. Email deliverability.** Form notifications must arrive (T01). *Write:* SMTP plugin via a transactional provider (Brevo, as in our cost table) or the host; SPF, DKIM, DMARC records on the sending domain — requires DNS access and ASSET's mail admin; we don't touch their mailbox (Q6 default). Exclude mailbox configuration.

**T13. Enquiry storage, CSV, statuses.** Q20 default: enquiries in the site's own list with Excel export; Q29-area default: statuses new/qualified/quote sent/won/lost + reminder flag. *Why:* most WP form plugins store entries but statuses/owner/notes need Pro or custom code. *Write:* entries stored in WP, CSV export, statuses + owner + note fields (state how), duplicate prevention (token + server-side hash within N minutes), spam (Turnstile or honeypot; Q default "no picture puzzles"), consent text per form, retention 3 years with automatic purge (Q default), DSR procedure (WP export/erase personal data tools + documented procedure).

**T14. Existing site migration.** Current site is WordPress (§3). *Write:* WXR export + media copy for up to 20 pages, slug inventory from our crawl + Search Console 12 months (Q7/Q default), 301 map via Redirection plugin or server rules, no chains, no blanket-to-home (RFP SEO), sitemap submission, Search Console change-of-address not needed if same domain (Q6 default: asset-voyagesdaffaires.com; assetvoyages.com forwards web only).

**T15. Old host access and DNS cutover.** Q4/Q5 defaults: ASSET arranges handover from current provider, gives access at kickoff. *Write:* prerequisites list (registrar login, DNS zone, current host panel/SFTP/DB, GA/GSC access) by date X; cutover = DNS change by ASSET or by us with their authorisation, TTL lowered 48 h before, old site kept available read-only ≥30 days (RFP: keep current site available throughout); rollback plan (RFP J5).

**T16. Performance, CWV, accessibility on WP.** Our pages promised "served from close to the visitor" (static/CDN). *Write:* page cache + optional free CDN (Cloudflare free in front of host), image optimisation, targets measured in lab (Lighthouse mobile ≥ X, LCP ≤2.5 s on key templates) — as the Q default; WCAG 2.2 AA as design target on main journeys, no certification (Q default kept).

**T17. Security hardening.** *Write:* auto-updates policy, file editing disabled, XML-RPC off, REST user enumeration off, login rate limit, least-privilege DB user, WAF (host or plugin), uptime monitor (UptimeRobot), security headers, no nulled plugins, inventory of all plugins with versions in handover pack.

**T18. Update responsibility after handover with no contract.** WP core/plugin updates are continuous. *Write:* without care plan, ASSET (or its appointed developer) is responsible for updates, backups checks, licence renewals and security from acceptance + J6 end; we deliver an update runbook; auto-updates for minor core + security releases enabled by default.

**T19. Acceptance tests T01–T15 mapped to WP.** *Write:* annex table: each T-test → WP feature → test case → evidence (screenshots/video, curl proving GM&E absent from REST, restore from backup on staging for T13, CSV export for T14, Veena publishes then edits for T15, consent refusal effective for T09, redirect list check for T10). Acceptance report per RFP §7.

**T20. SmartFees.** "Presentation of future subscription offers" = static content only. *Write:* no prices engine, no checkout, no billing, no account area; optional interest/waitlist via the Savings Scan or contact form. Note Q14 default said "no prices or service levels" for the small-business page — SmartFees may show indicative prices if ASSET supplies them.

**T21. Wondermiles link vs Traveldoo (Q23).** Client now wants a Wondermiles page + "link to existing booking platform". *Write:* "Client login" button URL editable by Veena (default today's Traveldoo URL until ASSET says otherwise); Wondermiles page text-only, no logo/screenshots until Wondermiles approves in writing (Q24 default); no SSO, no stored passwords (T08).

**T22. English later.** *Write:* French only at launch (Q18 default); theme built translation-ready (strings in .pot, no hardcoded FR in templates); Polylang installed only when EN is ordered (change request). Avoid installing it now (adds URL/SEO complexity).

**T23. Analytics and consent.** Our pages promised cookieless Cloudflare Web Analytics (no banner). *Write:* keep cookieless analytics (Cloudflare WA or Matomo cookieless) unless ASSET keeps GA4/LinkedIn/Meta (Q7); if so, consent plugin (Complianz/CookieYes free tier) with refuse-as-easy-as-accept, changeable from footer (T09); paid CMP excluded.

**T24. Admin accounts and our access.** *Write:* WP administrator account(s) in ASSET's name created first (owner: management, Veena admin); ProdCraft uses a named personal account during build; at handover we delete our accounts, rotate salts, SFTP/DB and hosting passwords, revoke API keys, and ASSET confirms in writing.

**T25. Demo requirements.** Client asks: admin demo of congress catalogue + commercial content. *Do:* this week, on a ProdCraft-owned throwaway WP staging with sample data only (fake congresses, fake GM&E code "DEMO-XXXX"), shown live by screen share; no client credentials, no real data, no production access; demo is not a deliverable and not transferred.

**T26. Unbounded items in €3,000 (flag).** Design revisions; number of pages; form fields/logic; Savings Scan content; import re-runs; redirect count; training sessions; J6 duration (Q default 4 weeks); SEO audit depth (J1); browser/device matrix; content entry of new copy; image sourcing (Q11 default: illustrations); meetings; email/DNS troubleshooting with their IT; accessibility fixes in third-party plugins. Each needs a number or an exclusion.

---

## B. Legal / commercial auditor (France, B2B)

**L1. Fixed price tied to a scope annex.** Forfait (art. 1710/1787 C. civ., contrat d'entreprise) holds only against a written scope. *Write:* "Prix global et forfaitaire de 3 000 € HT pour le périmètre de l'annexe 1"; anything outside = written change order, quoted, accepted before work.

**L2. Change procedure.** *Write:* written request → quote within 3 working days (hours × rate) → written acceptance → schedule shift stated. Hourly rate stated (01c §6 promised it).

**L3. Acceptance and deemed acceptance.** 18 already drafted: tests T01–T15 on staging, written acceptance or deemed acceptance if no written defect list within 5 working days; blocking vs major vs minor as RFP §7. *Write:* same; one correction round per defect list (18 C2).

**L4. Cutover authorisation.** *Write:* cutover only after (a) acceptance, (b) cleared second 50%, (c) management's written go-live; DNS change performed by ASSET or by us on written instruction.

**L5. Payment 50/50 and late payment.** Operator: 50% on signature, 50% on acceptance before cutover. *Write:* invoices in € HT + VAT if applicable, due 7 days (lawful by agreement; cap 60 days, art. L441-10 I C. com.); late penalties at ECB rate +10 pts and €40 fixed recovery indemnity (L441-10 II, D441-5); these mentions must appear on invoices (L441-9). Deposit acquired, pays for work done.

**L6. Retention/guarantee.** No retenue de garantie (not a public/construction contract). *Write:* "garantie de conformité" = correction free of charge of defects against T01–T15 during J6 (state duration, e.g. 30 days); no other warranty; legal garantie des vices cachés limited to what B2B law permits.

**L7. Liability cap.** *Write:* liability limited to direct damages, capped at the amount paid (€3,000 HT); excluded: indirect losses, lost business, data loss where ASSET did not keep backups after handover, third-party platform failures. Not applicable to gross negligence/wilful misconduct (Fr. case law voids caps there and for obligations essentielles, art. 1170 C. civ.) — keep cap reasonable.

**L8. IP: GPL and client ownership.** WordPress and most plugins/themes are GPL v2+: ASSET receives them under GPL, not by assignment. Custom code (theme, plugin, importer, blocks) and the design: *write* assignment of patrimonial rights (cession de droits, art. L131-3 CPI requires listing rights, scope, territory, duration) on full payment; custom PHP in a WP theme is a derivative of GPL so distribute under GPL to ASSET + assignment of copyright. Content, data, media = ASSET's throughout. Note 18 B5: rights transfer on full payment — consistent.

**L9. Licences in client's name; third-party terms pass-through.** *Write:* all paid licences (plugins, hosting, SMTP, CDN, domain) bought in ASSET's name with ASSET's card/billing, under the vendor's terms which ASSET accepts directly; ProdCraft not liable for third-party pricing changes, outages or end-of-life. Operator decision: billed separately to client.

**L10. Hosting contract.** *Write:* between ASSET and the host directly; we may set it up as ASSET's agent with their payment method; no resale, no margin.

**L11. GDPR art. 28 DPA.** During build (we touch enquiries, accounts, possibly migrated personal data) and any care plan we are a sous-traitant. *Write:* annexed DPA (art. 28(3) clauses: instructions, confidentiality, security, sub-processors list — host, SMTP, CDN, analytics —, assistance with DSR, breach notification ≤48 h, deletion/return at end, audit). Host/SMTP are ASSET's own processors if contracted directly; say so.

**L12. Mentions légales / LCEN.** Art. 6-III LCEN: editor identity (ASSET: raison sociale, siège, RCS, capital, publication director, contact), host identity (name, address, phone). Plus Atout France registration and garantie financière/RC Pro for the travel agency (Code du tourisme L211-18) — ASSET supplies. *Write:* we lay out the legal pages; content and accuracy = ASSET.

**L13. Cookies/CNIL.** Art. 82 Loi Informatique et Libertés + CNIL guidelines 2020: prior consent for non-essential trackers, refuse as easy as accept, withdrawal possible, consent proof kept ≤6 months guidance on re-asking (13 months max cookie life). *Write:* cookieless analytics default; if trackers kept, CMP configured, ASSET approves wording (RFP).

**L14. No-contract maintenance disclaimer.** *Write:* care plan optional, no minimum term; without it, from end of J6 ASSET is solely responsible for updates, security, backups, licences; ProdCraft not liable for incidents arising from unapplied updates or third-party changes after handover.

**L15. References clause.** Operator: never name clients. *Write:* we offer anonymised WP case studies (sector, scope, screenshots with names removed) and a live admin demo; references by phone only with prior consent of that client, if any. Note 01c §8 asked ASSET to let us credit/LinkedIn-post — make that opt-in and consistent with our own no-names rule (asymmetry may read oddly; keep it optional).

**L16. Demo data.** *Write in demo invitation:* sample data only, no access to ASSET systems, demo and concept remain ProdCraft IP.

**L17. ProdCraft VAT status (flag).** Unknown: if micro-entrepreneur under franchise en base, invoices state "TVA non applicable, art. 293 B du CGI" and price is €3,000 net; if VAT-registered, €3,000 HT + 20% = €3,600 TTC. Client said "excl. VAT" — must be resolved before quoting.

**L18. Invoicing entity / SIRET (flag).** Proposal and invoices need legal name, legal form, SIREN/SIRET, RCS/RNE, address, VAT number if any (art. L441-9 C. com., art. 242 nonies A annexe II CGI). Currently unstated in our deliverables.

**L19. RC Pro insurance (flag).** French buyers often ask. *Do:* confirm whether ProdCraft holds RC Professionnelle; state insurer + cover, or don't claim it.

**L20. Non-solicitation / no exclusivity.** *Write:* no exclusivity either way; optional mutual non-solicitation of staff 12 months (keep light, it can look heavy for a €3k job — optional).

**L21. Force majeure / platform outages.** Art. 1218 C. civ. *Write:* FM clause + hosting/third-party outages excluded from any availability target; 99.5% target from §5 no longer measured by us without care plan.

**L22. Domain/DNS ownership.** RFP: ASSET controls domain, hosting, CMS, tool accounts. *Write:* domain stays with ASSET's registrar account; we never register in our name.

**L23. Concept IP if not selected.** *Write:* the concept site, console mock-up, texts and designs are ProdCraft's IP; no licence granted unless a contract is signed and paid; ASSET may not hand them to another supplier. Keep pages unlisted; take them down at decision if not selected.

**L24. Deadline vs proposal validity.** Client wants revised proposal by Fri 6 Nov; Q1 default said proposal within 24–48 h of answers or by 10 Nov. *Write:* send by 6 Nov; offer valid 30 days; start date subject to slot availability at signature.

**L25. "Subject to management approval" = no commitment.** *Do:* no further free build work; demo on sample data; no production access, no audit of their site before signature (J1 audit is paid work). State that the price is valid only for the scope and start window.

---

## C. Contradictions with what we already said (to resolve in the proposal)

| # | What we said | Where | Now | Resolution |
|---|---|---|---|---|
| C1 | "Recommendation: a custom build… no paid plugins to keep updated"; Cloudflare/static stack; "the alternative: Directus" | questions §3, 01c §1 | WordPress | Say plainly: "You prefer WordPress, which your team already knows; we adapt. Same principles kept: ownership, GM&E protection, staging, export." Don't argue. Update the live page §3 or add a dated note so the links don't contradict the proposal. |
| C2 | Running costs ≈ €5–15/month, Cloudflare table, PITR 30 days, 99.5% target measured every 5 min | questions §4–§5, Q29 default | WP hosting + licences, client-paid | Issue a new itemised WP running-cost table (hosting, backups, SMTP, licences, domain, monitoring); restate backups as "daily, 30 days"; availability = host's SLA; our 99.5% report only in care plan. |
| C3 | Console with own admin; repository organisation in ASSET's name; "fixed list of section types"; prototype table (included/optional/illustration) | questions §3, 01c §2–§4, 16 | WP admin; theme/plugin code | Console = illustration of workflows now delivered in WP admin; Git repo of custom theme/plugin still handed over in ASSET's GitHub org; section types = named block patterns list; deliver the promised prototype table, re-marked for WP. |
| C4 | Two revision rounds per design stage (wireframes + mock-ups) and per content stage; 12-week launch; 4-week settling-in; maintenance invoiced monthly from launch, minimum-term remainder (18 D2) | 01c §4, Q1, defaults, 18 | €3,000, optional care plan | State: design = adaptation of the approved concept; 2 rounds on 1 home mock-up + 1 inner template; content rounds 1–2 bounded; shorter schedule with dated milestones; J6 settling-in period stated (keep 4 weeks or shorten, explicitly); care plan optional, monthly, no minimum term, cancel with 1 month's notice. |
| C5 | Client-login link to Traveldoo by default; Wondermiles text only; SME page no prices; AI/Wondermiles as priced options; footer credit + LinkedIn request | Q14, Q23–Q25, 01c §7–§8 | Wondermiles page + booking link; SmartFees offers; options deferred to phase 2 | Button URL editable, default Traveldoo until ASSET names the booking platform; Wondermiles page text-only until approval; SmartFees presentational, prices only if ASSET supplies them; phase-2 items "quoted when requested". Keep credit/LinkedIn optional. |
| C6 | Proposal by 10 Nov if no answers by 6 Nov | Q1 default, 01c §6 | Client deadline 6 Nov | Deliver 6 Nov. |

---

## D. MECE checklist — everything the revised proposal must state

**Price & payment**
- [ ] €3,000 HT global fixed price; VAT treatment (293 B or 20%) resolved
- [ ] 50% on signature (acquired, starts work on cleared funds) / 50% on acceptance before cutover
- [ ] 7-day terms, SEPA, L441-10 penalties + €40 indemnity, invoice mentions
- [ ] Hourly rate and change-order procedure
- [ ] Optional care plan price, contents, response/resolution times (16 carryover item 1), no minimum term
- [ ] Third-party costs itemised separately, paid by ASSET: hosting, backups, security, SMTP, plugin licences, domain, CDN; assistance and bug-fix rates
- [ ] Proposal validity (30 days) and start window

**Scope & allowances**
- [ ] Template list and page allowance; definition of a page
- [ ] Sections: Business Travel, MICE, International Congress, consulting, SmartFees presentation, Wondermiles page, legal pages
- [ ] Forms: list, max fields, routing, acknowledgement, storage, export
- [ ] Congress catalogue: fields, filters, workflow, roles, past-edition rule, one import ≤300 rows via template, dedup key, rejection report
- [ ] Content migration: ≤20 pages + 3 legal, wording edits only
- [ ] Design revisions: number, on what deliverables
- [ ] Training: sessions, format, language; admin guide
- [ ] J1 audit depth; SEO migration (redirect sources, count)
- [ ] J6 stabilisation duration; acceptance report
- [ ] Phase 2 list (AI, contract analysis, billing, Wondermiles API/SSO, EN) — excluded
- [ ] Prototype table: included / optional / illustration

**Technology**
- [ ] WordPress version policy, PHP/DB minimums
- [ ] Theme approach (block theme from concept, no page builder)
- [ ] Plugin table: name, purpose, free/paid, cost, licence holder, renewal
- [ ] GM&E protection design (no REST/HTML exposure), roles, 2FA, activity log
- [ ] Analytics (cookieless default) and consent tool if trackers
- [ ] Performance and accessibility targets and how measured
- [ ] Translation-ready, EN later

**Hosting & ops**
- [ ] Host requirements + recommended hosts with indicative prices; contract ASSET ↔ host
- [ ] Staging environment
- [ ] Backups (frequency, retention, off-site, restore test T13)
- [ ] SSL, WAF, uptime monitoring
- [ ] SMTP + SPF/DKIM/DMARC (needs DNS access)
- [ ] DNS cutover plan, rollback, old site kept available
- [ ] Update responsibility with and without care plan

**Ownership & handover**
- [ ] All accounts (domain, host, WP admin, SMTP, licences, GA/GSC) in ASSET's name
- [ ] Custom code + Git repo + design files + data + media delivered; rights assigned on full payment; GPL components identified
- [ ] Documentation: admin guide, runbook, plugin inventory, credentials list
- [ ] Removal of ProdCraft access and password rotation, confirmed in writing
- [ ] Freedom to self-manage or appoint another developer; no mandatory maintenance
- [ ] Exports (WXR, CSV of congresses and enquiries, media)

**Legal**
- [ ] ProdCraft legal identity, SIRET, VAT status, RC Pro (or silence)
- [ ] Scope annex governs; change procedure; acceptance + deemed acceptance (5 working days); cutover authorisation
- [ ] Liability cap; warranty = T01–T15 conformity during J6
- [ ] DPA art. 28 for build and care plan; sub-processor list; data in EU
- [ ] Retention (3 years), DSR procedure, consent texts approved by ASSET
- [ ] Mentions légales/LCEN + tourism mentions supplied by ASSET
- [ ] Force majeure; third-party terms; no exclusivity
- [ ] Concept IP retained if not selected
- [ ] Late inputs → schedule shift / pause (18 B1)

**Demo & references**
- [ ] Admin demo this week: congress catalogue + commercial content, sample data, ProdCraft staging
- [ ] Anonymised WordPress case studies; no client names
- [ ] Footer credit / LinkedIn post optional

**Assumptions & exclusions**
- [ ] ASSET supplies final French copy, Savings Scan fields, SmartFees text, congress spreadsheet, logos, legal mentions, access, by dates
- [ ] Excluded: copywriting beyond edits, photography/stock, translation, congress research, paid CMP, CRM integration, billing/subscriptions, SSO/API, AI, email mailbox setup, ongoing SEO, ad campaigns, third-party costs
- [ ] Current provider handover arranged by ASSET; no contract blocks the project
- [ ] Management approval: price and slot held until validity date only
