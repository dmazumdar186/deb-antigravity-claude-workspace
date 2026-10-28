# ASSET Voyages — Website Redesign: Clarification Questions
Prepared by Debanjan Mazumdar, Founder, ProdCraft · 28 October 2026
Reference: *ASSET Voyages website redesign requirements*, Version 0.4 EN (28 Oct 2026), and the Supplier Response Form v0.1

> Purpose: to give a firm price and a schedule we will actually meet, we need the answers below. They are grouped by work package (L0–L4) and numbered so Veena can answer inline (for example, "B3: yes, Marie Dupont"). Items marked **★** block the quotation. The rest can be answered at the kickoff workshop.

---

## A. Consultation, budget and decision process

1. **★** What is the proposal submission deadline, and on what date does ASSET intend to choose a supplier?
2. **★** Is there a budget envelope or a cap for the core scope (L0 + L1 + L2)? A range is enough. It decides whether we propose the full catalogue workflow at launch or phase it.
3. Is there a hard launch date (a trade fair, a congress season, the end of a contract with the current host)? Or is the 12–18 week figure only indicative?
4. Who signs off each milestone (J0–J6) for ASSET management: one person or a committee? What turnaround should we plan for written approvals (2, 5 or 10 working days)?
5. Section 8 says scope clarifications "will be shared with all invited suppliers." How many suppliers have been invited? Will there be a shortlist presentation or demo stage?
6. Are payments against milestones expected to follow a fixed split (for example 30 / 40 / 30)? Is there a retention on the balance after J6, and for how long?
7. Should prices be quoted excluding VAT at 20 %, and is ASSET VAT-registered for reverse charge? (ProdCraft invoices from [country/VAT status].)

## B. L0 — Existing technology, access and ownership

1. **★** Which CMS runs asset-voyagesdaffaires.com today, and who built it? Is that agency still under contract, with a notice period?
2. **★** Who holds the accounts today for the domain registrar, DNS, hosting, SSL, email (MX), Google Analytics, Google Search Console, Google Business Profile and any tag manager? Are they in ASSET's name or the previous supplier's?
3. What is the relationship between **asset-voyagesdaffaires.com** and **assetvoyages.com** (shown in the brief footer)? Should the new site live on one domain, with the other redirecting, or must both stay live? Which one carries the email addresses?
4. Are there other domains, subdomains or landing pages (campaign sites, a Selectour-provided page, old microsites) that must be inventoried and redirected?
5. Is there a contractual or technical constraint from **Selectour** (network brand guidelines, mandatory logos, legal mentions, a network-supplied web template, IATA/APST/Atout France registration display)?
6. What backups of the current site exist, and can we receive a full export (database + media) before discovery starts, so the live site is never touched?
7. Are there existing integrations we may not see from outside: newsletter tool, CRM, booking widget, chat, call tracking, Selectour or GDS tools?

## C. L1 — Content, brand and languages

1. **★** How many pages do you expect at launch? Is ASSET writing the new French copy, or should we rewrite or migrate the existing copy (and at what depth)?
2. **★** Who is the content owner for each of the three activities (Business Travel, MICE, Congresses)? Do they each validate their own pages?
3. Do you have brand guidelines (logo files in vector format, colours, fonts) or should the redesign include a light brand refresh? Is the logo fixed?
4. Photography: do you have an authorised image library (events you organised, team photos, client trips)? Are stock images acceptable where nothing exists, and who pays the licence?
5. Which **commercial claims, client logos, references, testimonials, certifications and figures** (years in business, number of clients, volume) are approved for publication? We will not publish any claim without written approval (brief §2, §6).
6. "SMEs and microbusinesses" (TPE/PME): is there a defined simplified offer (pricing, fee model, service level) we can present, or is the page lead-generation only?
7. "Assistance and expertise": which services actually exist today? For example 24/7 emergency line, out-of-hours number, duty-of-care / traveller tracking, visa support. We need the exact service hours and phone numbers to publish.
8. **English activation**: which journeys must be in English first (Congress catalogue only, or the whole site)? Who translates (ASSET, a translation agency, or us with professional review)? Is a third language foreseen (Spanish, German) so we size the language model correctly?
9. Blog / "articles, guides and FAQ": how many pieces exist today, how many are to be migrated, and what is the expected publishing cadence after launch?
10. Team page: which team members may be shown with name, photo and role? We need consent for each (GDPR).

## D. L1 — Forms, enquiries and CRM (F01–F06)

1. **★** For each activity, who should receive enquiries (mailboxes, named owners, backup)? Should routing depend on any field (for example MICE above 50 travellers goes to the head of MICE)?
2. **★** Is there a CRM today (HubSpot, Pipedrive, Salesforce, Zoho, Selectour tool, Excel)? If none is chosen, should the built-in enquiry back-office (status, owner, history, CSV export) be treated as the CRM for year one?
3. What statuses do you use for an enquiry (new → qualified → quote sent → won / lost)? Do you need reminders when an enquiry sits untreated for X hours?
4. What response-time promise can be displayed on the acknowledgement email ("we reply within 4 business hours")?
5. F01 "estimated volume": in what unit (annual travel spend in €, trips per month, travellers)? What bands do you want?
6. F02 MICE: do you want an optional budget field per person or as a total? Is a file upload needed (an RFP, a programme PDF)?
7. F03 Congress quotation: should the form accept several travellers with different departure cities (a lab sending 8 doctors from Lyon, Nantes and Paris)? Must it capture a congress registration/badge number or an organiser reference?
8. Retention: how long may enquiry data be kept (for example 3 years after last contact for prospects, per CNIL guidance)? Who handles access/deletion requests internally?
9. Is phone contact or a callback request preferred over email for MICE leads? Should we include a "book a call" slot picker (it requires a calendar tool)?
10. Which anti-spam approach is acceptable: an invisible challenge (Cloudflare Turnstile, cookie-free) or reCAPTCHA (needs consent)?

## E. L2 — Congress catalogue and GM&E workflow (C01–C07)

1. **★** How many congresses do you expect to list at launch, and per year? The brief mentions importing 300: is that an existing file? Can we see a sample of 10 rows with the real columns?
2. **★** Where do listings come from today (organisers' sites, a medical-congress database, Air France–KLM GM&E event lists, your team's research)? Is any source under licence or copyright that limits republication?
3. Which **disciplines/taxonomy** should the filters use (medical specialities only, or also scientific, engineering, industry fairs)? Is there an existing list?
4. **★** The internal workflow (detected → verified → GM&E application to prepare → submitted → code received → ticket issuance authorised → approved for sale → archived): who performs each step, and who is the "Congress/fare approver" role in practice?
5. GM&E codes: do you receive one code per event from Air France–KLM, or several (per route, per class, per validity window)? Do they expire? Should the system alert before expiry?
6. **★** What may be shown publicly once a congress is "approved for sale": a "preferential fares available" badge, a discount percentage, a fare range, or only "request a quote"? Who approved that wording with Air France–KLM?
7. Past events (C06): after the end date should a listing stay visible as an archive for SEO ("2026 edition — next edition coming"), be hidden (noindex), or redirect to the next edition? Do congresses recur yearly under the same slug?
8. Should each congress page show other airlines, or only Air France–KLM partner programmes? Do you also sell hotel and transfer packages for congress participants?
9. Do you want participants to subscribe to alerts ("notify me when ESC Congress 2027 opens for quotation")? That creates a mailing list with consent obligations.
10. Do pharmaceutical or medical-device clients need group booking for several participants on one congress (a group flow different from the individual flow)?

## F. L3 option — Wondermiles (feasibility, SSO, API, account creation)

*Background for us: Wondermiles is the online booking/travel-management tool your clients log into. "SSO" means a client signs in once (for example with their company Microsoft account) and lands in Wondermiles without a second password. "API integration" means our site exchanges data with Wondermiles automatically, for example to create an account when a demo request is approved.*

1. **★** What is ASSET's contractual relationship with Wondermiles: reseller, white label, or agency partner? Does the contract allow us (a third-party supplier) to access their API or documentation, and under what NDA?
2. **★** Who is the technical contact at Wondermiles, and do they publish API documentation, a sandbox environment and test credentials?
3. Which SSO protocols does Wondermiles support (SAML 2.0, OpenID Connect / OAuth 2.0, none)? Who would be the identity provider: ASSET, each client company's own (Microsoft Entra ID / Google Workspace), or Wondermiles itself?
4. What exact journey do you want in L3? (a) a branded "Client login" link (already in core scope); (b) SSO from the ASSET site into Wondermiles; (c) automatic account creation after ASSET approves an SME; (d) showing client data (trips, invoices) on the ASSET site. Each has a very different cost and risk.
5. For account automation: what data is needed to open a company account (SIRET, billing address, travel policy, traveller list)? Who validates the company before creation?
6. Which Wondermiles images, logos, screenshots and product claims are we authorised to use on the "Digital solutions" page?
7. Are there other client tools to link from the client area (an invoicing portal, expense tool, the Selectour app, a 24/7 assistance app)?

## G. L4 option — AI features

1. **★** What should the AI do, in your words? Options we can price: (a) find and pre-fill new congress listings from official sources into a review queue; (b) draft French/English listing text for human approval; (c) triage and summarise incoming enquiries; (d) an assistant that answers visitor questions from your approved content. The brief describes (a). Do you want any of the others?
2. Which sources may the AI read (official congress websites only, specific databases)? Are any sources off-limits?
3. What daily or monthly volume should we cap (for example 50 candidate listings a week), and what is the acceptable confidence threshold before a human reviews?
4. Do you require all AI processing to stay inside the EU (data residency), and must the model provider be named in the data processing agreement?
5. Who reviews the AI queue, and how quickly? (This decides whether the queue needs notifications.)

## H. Security, compliance and hosting

1. Do you or your clients (pharma, large corporates) have security questionnaires, ISO 27001 or supplier-onboarding requirements we must fill in?
2. MFA for administrators: is an authenticator app acceptable, or do you require hardware keys or login through your Microsoft/Google company accounts?
3. Must hosting and data stay in the EU/France? Is a provider with EU data centres and a DPA (for example Cloudflare, OVHcloud, Scaleway) acceptable?
4. Who is ASSET's data-protection contact (DPO or referent)? Do you have an existing privacy policy and records of processing we should align with?
5. Which cookie/consent tool, if any, is already in use? Which trackers must stay (Google Analytics 4, Meta pixel, LinkedIn Insight)? Would you accept a cookie-free analytics option that needs no banner?
6. SLA expectations: support hours (9:00–18:00 CET on business days?), the maximum acceptable outage, and whether an out-of-hours contact is needed during peak congress periods.
7. Backup targets: are RPO 24 h and RTO 8 business hours final or negotiable? How long must backups be retained (30, 90, 365 days)?

## I. SEO, analytics and measurement

1. Can we get read access to Google Search Console and Analytics for the current site during discovery, to build the baseline and the redirect map from real traffic data?
2. Which pages or keywords bring business today (as far as you know)? Are there pages that must never lose ranking?
3. Do you run paid campaigns (Google Ads, LinkedIn Ads) pointing at specific landing pages that must keep working?
4. Is there a Google Business Profile for the Issy-les-Moulineaux office, and who manages it?

## J. Operations, training and handover

1. Besides Veena, who is the backup editor? What is their comfort level with web tools (we will size training and the admin guide accordingly)?
2. Would you prefer training in person in Issy-les-Moulineaux or by video call, and in French or English?
3. Handover: should the Git repository and all accounts be created in ASSET's name from day one (our recommendation)? Who at ASSET will own them?
4. After launch, what kind of changes do you expect each month (new pages, campaigns, seasonal offers, congress updates)? This sizes the monthly management plan.
5. Is a monthly management plan (hosting, security, monitoring, content changes, reporting) preferred over ad-hoc maintenance billed per intervention?

---

**Proposed next step:** a 45-minute video call with Veena and one member of management to go through the ★ questions. We can then send the full proposal within 5 working days of the call.

Debanjan Mazumdar · Founder, ProdCraft · debanjan@prodcraft.fyi
