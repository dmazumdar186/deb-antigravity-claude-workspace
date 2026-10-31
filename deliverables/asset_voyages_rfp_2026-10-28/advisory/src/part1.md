<div class="cover">
<p class="kicker">ProdCraft · Technical Advisory Pack · Restricted</p>
<h1 class="title">ASSET Voyages website and Congress catalogue</h1>
<p class="subtitle">The plan, the design, the gaps and the risk model, prepared for independent review by two senior engineers</p>
<table class="meta">
<tr><td>Version</td><td>1.0 · 31 October 2026</td></tr>
<tr><td>Author</td><td>Debanjan Mazumdar, founder, ProdCraft (sole engineer on this bid)</td></tr>
<tr><td>Reviewers</td><td>Two external senior engineers (weekend review)</td></tr>
<tr><td>Status</td><td>Pre-proposal. No contract is signed. The client is running a competitive consultation.</td></tr>
<tr><td>Source folder</td><td><code>deliverables/asset_voyages_rfp_2026-10-28/</code> (referred to as <code>D/</code>)</td></tr>
<tr><td>Confidentiality</td><td>The client's RFP is restricted to invited suppliers. This pack contains internal pricing. Please do not forward it.</td></tr>
</table>
<p class="note">Conventions used throughout. <b>Estimate</b> marks a figure we derived and have not measured. <b>Verified</b> marks a fact checked against a primary source, with the date. <b>UNKNOWN</b> marks something only the client can tell us. Prices are in euros, excluding VAT (HT), unless stated otherwise.</p>
</div>

<h1 class="toch">Contents</h1>

[TOC]


# 0. How to read this, and what we ask of you

## 0.1 Why you are reading this

ProdCraft is a one-person studio. The founder builds with an AI-assisted workflow (Claude Code plus a set of deterministic scripts, gates and audits described in §3). We have been invited, alongside other suppliers, to bid on a redesign of a French business-travel agency's website, with a structured Congress catalogue, an enquiry back-office and an editor console. The bid is winnable. The build is also larger than anything we have shipped as a single product: roughly 40% of the scope rests on code we have run in production before; the other 60% is new.

We want two people who did not write the plan to try to break it before the client does. You have the weekend. Please be as hard on it as you would be in a design review at work. Comments like "this is fine" don't help us; comments like "your restore drill doesn't prove RTO because X" do.

## 0.2 What we ask you to do

1. Read §1–§2 quickly, for context. They describe the client and the requirement; there is little to grade there except whether we understood it.
2. Read §3–§9 carefully. This is the plan: what exists, what we design, how we build it, what it costs, what can go wrong and how we measure it.
3. For **each numbered section**, give a score from 1 to 10 and a comment. Use the scoring sheet in §10.4. A rubric is below.
4. Answer the **Questions for the reviewers** at the end of each section where you have a view. Skip the ones you don't.
5. In §8.2, **re-score the risk table**: put your own probability next to ours for each risk. That is the single most useful thing you can give us.
6. In §10, tell us which of the open decisions you would take differently, and why.

## 0.3 Scoring rubric

| Score | Meaning |
|---|---|
| 9–10 | You would approve this in a design review at your company with no changes. |
| 7–8 | Sound. Minor gaps, none of which put delivery at risk. |
| 5–6 | Workable, but at least one gap would likely cause a slip, a defect at acceptance, or a cost overrun. |
| 3–4 | A material flaw: you would block it until it is fixed. |
| 1–2 | Wrong approach. Start again. |

Please grade the plan against the client's requirement and a one-person team, not against what a ten-person team at a large company would do. Where the right answer is "hire someone", say so; that is a legitimate finding.

## 0.4 What this pack is not

- It is not the client proposal. The proposal (`D/proposal/ProdCraft_ASSET_Voyages_Proposal_v1.0_2026-10-28.pdf`) is a separate, client-facing document and will be revised after the client answers our 30 questions.
- It is not code. The production system does not exist yet. The concept site exists and is live (links in §1.4); everything in §4–§6 is design.
- It does not contain secrets, credentials or other ProdCraft clients' names. Where we refer to prior builds we describe them anonymously ("a public job-board build", "two live bilingual sites").

## 0.5 Map of the pack

| § | Title | What to grade |
|---|---|---|
| 1 | Business context | Did we understand the client and the competitive position? |
| 2 | Requirements, complete | Is every RFP cell mapped to a function and a test? |
| 3 | What exists today | Is the capability assessment honest? Is the lift path credible? |
| 4 | System design | Domain model, state machines, invariants, permissions, i18n, SEO. |
| 5 | Architecture | Components, trust boundaries, environments, backups, observability, security, failure modes. |
| 6 | Build plan | Sequence, modules, tests, CI gates, definition of done, handover. |
| 7 | Effort, timeline, price | Hours, calendar, price options, TCO. |
| 8 | Risk model and grading | Complexity, confidence model, 11-lens and 5-expert review. |
| 9 | KPIs per stage | Are the measures meaningful, measurable and owned? |
| 10 | Open decisions, scoring sheet | Your calls on the open choices. |
| A–D | Appendices | Questions and defaults, glossary, file index, sources. |

# 1. Business context

## 1.1 The client

**ASSET Voyages** is a business-travel agency based at 58 rue Jean-Pierre Timbaud, 92130 Issy-les-Moulineaux, France (source: RFP letterhead). It is a member of the **Selectour Affaires** network. Its current website says, verbatim (fetched 28 October 2026): « agence de voyages d'Affaires à taille humaine, membre du réseau Selectour Affaires », and « Avec plus de 122 agences et plateaux d'affaires en France, Selectour Affaires constitue le premier réseau dédié aux voyages d'affaires » (the 122 figure is undated on their site).

It runs three activities, which the RFP and the new site keep distinct:

| Activity | What it is | Primary conversion |
|---|---|---|
| Business Travel | Managed corporate travel for SMEs and larger accounts: booking, travel policy, reporting, expenses, invoicing, 24/7 assistance ("disponible 24h/24, 7 jours/7" on today's site). | Travel review request, account/demo request (form F01). |
| MICE | Meetings, Incentives, Conferences and Exhibitions: group travel from 10 people, seminars, incentives, conventions; "un chef de projet dédié". | Progressive brief and quotation request (F02). |
| International congresses | Travel for delegates attending international (often medical/scientific) congresses, including preferential airline fares under Air France–KLM's Global Meetings & Events (GM&E) programme where ASSET holds the event code. | Flight quotation request pre-filled with the congress (F03). |

The client's coordinator is **Veena** (operational coordination; she centralises responses and runs business acceptance). ASSET management approves budget, scope, architecture, mock-ups, milestones and launch.

**What we know about the current site** (verified 28 October 2026 by `curl -sL`):

- It is served at `asset-voyagesdaffaires.com`, while the RFP letterhead cites `www.assetvoyages.com`. Which domain the new site lives on is question Q6.
- It runs **WordPress 6.9.11** with Slider Revolution 6.2.18 (generator meta tags and `wp-content/` paths).
- The homepage is about 661 words and 69 links; 5,014 px tall on desktop and 10,527 px on mobile (`D/research/live_metrics.json`).
- The client area is labelled « Connexion Traveldoo » (plus IRES and a "Smart" app), whereas the RFP talks about **Wondermiles**. This is question Q23.
- The footer shows both ©2020 and © 2026.

We do **not** know: who hosts it, who owns the domain and DNS, the URL count, traffic, current trackers, CRM, or enquiry volumes. All of this is discovered in the L0 audit (J1) or asked in the 30 questions.

## 1.2 The RFP

The RFP (Version 0.4 EN, 28 October 2026, 9 pages) asks for a B2B commercial portal that works on mobile and can be managed by the client's own team. It states four expected outcomes:

1. Generate qualified enquiries for Business Travel, MICE and congress-related ticketing.
2. Enable Veena and a backup editor to publish content and Congress listings without a developer.
3. Preserve existing SEO value and keep the current website available throughout the project.
4. Prepare future integration points without making launch dependent on unconfirmed API or SSO access.

**Work packages.**

| Package | Status | Content |
|---|---|---|
| L0 | Mandatory | Technical and SEO audit, workshops, user journeys, architecture and functional discovery. Recommend keeping or replacing the CMS, with cost justification. |
| L1 | Mandatory | Design, CMS, priority French content, Business Travel and MICE pages, forms, measurement, SEO migration, security and training. |
| L2 | Mandatory | Congress catalogue, search, listings, business workflow, permissions, forms, CSV import/export and moderation. |
| L3 | Optional | Wondermiles feasibility and integrations, SSO/API and account creation, subject to permissions. |
| L4 | Optional | Controlled AI ingestion, human approval, monitoring and logs. |

L0+L1+L2 must work without L3 or L4. Ticket issuance and the flight booking engine stay outside the CMS. Advertising, paid CRM software, bulk scraping and automatic publication are out by default.

**Milestones (each needs written approval).**

| Milestone | Deliverable |
|---|---|
| J0 Kickoff | Team, access inventory, schedule and responsibilities. |
| J1 Audit and discovery | Architecture, SEO inventory, baseline, backlog and risks. |
| J2 UX and UI | Wireframes, desktop/mobile mock-ups and design system. |
| J3 Core website | Pages, CMS, forms and tracking on staging. |
| J4 Congresses | Tested catalogue, filters, statuses, listings and enquiries. |
| J5 Pre-launch | SEO migration, tests, fixes, training, backup and rollback plan. |
| J6 Stabilisation | Monitoring, fixes, access, source code, exports and closure of outstanding items. |

The 12–18 week timeframe is "indicative". Payments are negotiated against accepted milestones; cutover needs written authorisation from ASSET management.

**Acceptance tests T01–T15** (RFP §7, reproduced in full in §2.6). Launch is blocked by any of: a blocking security defect, data loss, a failed form, private-code exposure, or a missing critical redirect. Major defects need express approval and a dated correction plan; minor defects go into an outstanding-items plan.

**Essential conditions** (RFP §8, verbatim list): ASSET control of accounts and data; responsive and editable website; staging before cutover; documented SEO migration; protection of GM&E codes; core functionality independent of options, and flight ticket issuance outside the CMS; transparent recurring costs, licences and supplier handover.

**Assessment criteria** (RFP §8): understanding of user journeys, UX, the Congress catalogue, scalability, SEO, security, methodology, team, overall cost and maintenance. "Any partial response must explain the limitation, its impact and a proposed solution."

## 1.3 The consultation posture

This is a **formal competitive consultation**, not a signed client. The brief says it is "restricted to invited suppliers", that "any clarification that changes the scope will be shared with all invited suppliers", and that "submitting a proposal does not constitute an order". We assume other agencies are quoting. French agencies typically price this scope well above us (market evidence in §7.4).

Consequences we have designed for:

- **Every RFP identifier needs an explicit answer.** F01–F06, C01–C07, T01–T15, J0–J6, L0–L4. A missing line reads as a partial response.
- **Too cheap reads as risk.** A one-person studio at a fraction of market price must over-prove method and handover, or the client's management will (rightly) worry about continuity.
- **"Team" is an assessment criterion** and we are one person plus AI tooling. We answer this with a named lead, effort by role, a documented stack a third party can maintain, and a handover pack treated as a product (§6.7). Whether this is enough is a question for you (§1.6).

**Where the consultation stands (31 October 2026).**

| Date | Event |
|---|---|
| 28 Oct | RFP received. Concept site built and deployed (noindex). 30 questions sent with written defaults. |
| 28 Oct | Three rounds of internal audits on the outgoing pages (11-lens panel + 5 project experts per round). Verdicts moved from FIX FIRST to PASS. |
| 31 Oct | Veena asked seven clarification questions. We replied point by point (`D/01c_Reply_to_clarifications_2026-10-31.md`), with no prices. |
| 6 Nov | Deadline for answers to the 30 questions. Unanswered items follow the stated default. |
| ≤ 10 Nov | Priced proposal sent (24–48 working hours after answers, or by 10 Nov on defaults). |

## 1.4 Links

| What | URL | Notes |
|---|---|---|
| Current client site | http://asset-voyagesdaffaires.com | WordPress 6.9.11 (verified 28 Oct 2026). |
| Our concept (home) | https://asset-voyages-redesign.pages.dev/ | noindex. Scroll-scrubbed film « Du brief au retour », offer cards, live Congress catalogue demo with 12 fictional sample listings, three contact journeys. |
| Pitch page | https://asset-voyages-redesign.pages.dev/pour-asset/ | Why the concept is shaped this way, per-activity benefit table. |
| Console mock-up | https://asset-voyages-redesign.pages.dev/console/ | Static mock of the editor console: tiles, Pages, Congresses, Enquiries, GM&E explanation. Buttons show a toast; nothing persists. |
| Questions page | https://asset-voyages-redesign.pages.dev/questions/ | The 30 questions with defaults, anchors `#q1`…`#q30`, fillable answer sheet. |

The concept was built to show direction and make the Congress journey concrete. It is **not** a feature list; the proposal will carry a table marking every element as included, optional or illustration only (promised in the 31 Oct reply).

## 1.5 Commercial frame (internal; you may see the numbers)

**Price options under consideration** (from `D/20_Internal_Founder_QA.md`; all HT; detail and market evidence in §7):

| Option | Build | Monthly plan | Notes |
|---|---|---|---|
| Lean | €4,000 (L0 included, L1 €2,500, L2 €1,500) | €600/month, 12-month minimum | The founder's original constraint. ≈ €15/hour on the 265 h planning figure. |
| **Recommended** | **€7,500** | **€600/month, 12-month minimum** | ≈ €28/hour on 265 h. Still far below market. |
| Fair solo | €9,500–12,000 | €600–750/month | What a solo senior freelancer at a low market rate would charge. |
| Market | €18,000–25,000 | €750–900/month | Small Paris agency range for this scope (estimate from published ranges, §7.4). |

**Payment terms: 50/50.** 50% at J0, on signature (reserves the build slot and starts the audit); 50% at J5, on acceptance, before cutover. Acceptance = T01–T15 pass on staging and ASSET confirms in writing. Cutover follows management's written authorisation **and** settlement of the acceptance invoice. J6 stabilisation is covered by the build fee. Maintenance invoiced monthly from launch.

**Guardrails being written into the proposal and contract** (`D/18_Payment_Terms_Vetting.md`): deemed acceptance after 5 working days on staging with no written defect list; T01–T15 frozen in an annex at signature; schedule moves day for day with late client inputs, input more than 10 working days late pauses the project; changes are quoted and paid before work starts; IP in new code and design passes on full payment (data and accounts ASSET already owns stay theirs at all times); French statutory late-payment penalties and the €40 recovery indemnity (Code de commerce L441-10 and D441-5, to be verified with an accountant).

**Defaults and deemed answers.** Every one of the 30 questions carries a written default. Answers by Friday 6 November are built in; anything not answered follows the default. Assumptions can change by email until signature, possibly changing price and dates.

**The 12-month plan** is part of the economics: the low build price is presented as "part of a 12-month managed partnership". The plan covers hosting and all tool subscriptions (opened in ASSET's name, paid by ProdCraft), security updates, backups and restore drills, monitoring, up to 5 hours of content changes a month, support Monday–Friday 9:00–18:00 Paris time, and a monthly report.

## 1.6 Questions for the reviewers

1. Given a competitive consultation with a procurement-style grid, does a one-person bid with this method have a realistic chance, or does "team" sink it regardless?
2. Is a deemed-acceptance clause (5 working days) likely to be accepted by a French SME's management, or will it read as hostile? (We return to this in §10.)
3. Is there anything about the client's situation (WordPress today, two domains, Traveldoo vs Wondermiles) that you think we are underweighting?

# 2. Requirements, complete

This section maps every requirement cell in the RFP to what we build and how acceptance is checked. It is condensed from `D/03_Functional_Breakdown.md` (64 KB, every cell, with hours and status). Status: **E** exists in our stack, **P** partial, **M** missing (new code).

## 2.1 Outcomes, governance and scope boundaries

| # | Requirement | We build | Acceptance check | St. |
|---|---|---|---|---|
| A1 | Qualified enquiries in three activities | Three journeys → three purpose-built forms; enquiry record with type, source, status, owner | T01–T06; monthly count by activity | P |
| A2 | Veena + backup publish without a developer | ASSET Console; two named logins; training | T15 | M |
| A3 | Keep SEO value; current site up throughout | Parallel build on staging; old site untouched until DNS cutover; 301 map | T10; cutover log | P |
| A4 | Integration points; launch independent of API/SSO | Connectors (email, CRM webhook, client-area link) as config | T01–T15 pass with all options off | E |
| A5 | RACI: management, Veena, supplier, partners | RACI table in J0 pack | J0 approved | M |
| A6 | Written approval per milestone | Deliverable list + approval email template | One approval per J0–J6 | E |
| A7 | Change control (cost, schedule, security, SEO) | Change-request form with four impact fields; hourly rate | Signed change request on file | M |
| A8 | No production/DNS change without written authorisation | Cutover only on written go; pre-cutover checklist | Go email before DNS change | E |
| A9 | Core independent of L3/L4; no ticketing in CMS | No booking code; quote request only | T06: enquiry saved, no ticket issued | E |
| A10 | Exclusions; every licence, subscription and third party listed | Exclusions + third-party service table with cost and payer | Table in proposal | P |
| A11 | French at launch; FR+EN architecture; no unapproved machine translation | `/fr/` routes, i18n strings, hreflang-ready; EN publishable only with a human-approved flag | EN routes exist, switched off | E |

## 2.2 Mandatory audit (L0)

| # | Requirement | Deliverable | St. |
|---|---|---|---|
| L0.1 | CMS, versions, extensions, custom code | Audit sheet from access + crawl fingerprints | P |
| L0.2 | Hosting, DNS, certificates | DNS/TLS inventory (records, registrar, expiry) | P |
| L0.3 | Licences, ownership, backups, access | Account-owner register signed by ASSET | M |
| L0.4 | Content, URLs, links | Full crawl inventory CSV (crawl→inventory tool, new) | M |
| L0.5 | Forms, analytics, Search Console | Forms/destinations/trackers list; Search Console export | P |
| L0.6 | Performance, compliance | Lighthouse lab baseline on 5 key pages; legal/cookie check | M |
| L0.7 | Keep or replace CMS, with justification | Written recommendation (replace with ASSET Console; Directus as costed alternative) | P |
| L0.8 | Workshops, journeys, discovery | One workshop of up to 2 h; journey maps for 5 journeys; backlog | E |

## 2.3 Pages and journeys

Planned: **about 20 content pages from about 8 templates, plus 3 legal pages**, plus generated congress listing pages. ASSET supplies or approves all copy.

| # | Page | We build | Acceptance |
|---|---|---|---|
| C-1 | Homepage | Hero, 3 activity cards (1 click each), proof strip (approved claims only), "Upcoming congresses" block (next 6 published future events), client-area link | Each activity 1 click; block shows only published future events |
| C-2 | Business Travel | Service template, editable FAQ, CTA → F01 "travel review" | F01 within 2 clicks |
| C-3 | SMEs | Audience page, use cases, CTA → F01 "account/demo" | Account-request event fires |
| C-4 | Procurement / travel managers | Policy, reporting, expenses, invoicing, audit sections; CTA → F01 "travel audit" | — |
| C-5 | Assistance | Only services confirmed in the signed claims register | Every claim in register |
| C-6 | Digital solutions | Approved Wondermiles text/images only; demo CTA; client-area button (config URL, click event) | T08 |
| C-7 | MICE | Hub + 3 sub-pages; CTA → F02 progressive brief | F02 within 2 clicks |
| C-8 | Congresses | Catalogue landing (see §2.5) | T03 |
| C-9 | Agency and resources | Agency page, resources hub, article/guide templates, FAQ; team/references only with authorisation | Veena creates an article (T15) |
| C-10 | Contact and legal | Three doors (BT/MICE/Congress); legal notices, privacy, cookies from ASSET-approved text | Each door opens the right form |

| # | Priority journey (RFP p3) | Path in our design | Test |
|---|---|---|---|
| J-1 | SME owner | C-3 → F01 preset → enquiry type "SME account" → owner assigned → "qualified" | Walk-through in acceptance report |
| J-2 | Travel manager | C-2/C-4 → proof → F01 "travel review" | Same |
| J-3 | HR/comms | C-7 → F02 (3–4 steps + summary) → callback | Same |
| J-4 | Congress participant | Catalogue → listing → F03 pre-filled → enquiry linked to congress ID → team notified | T03, T06 |
| J-5 | Existing client | "Client area" → configured external URL; no login fields on our site | T08 |

Design expectations: key forms within 2–3 clicks, no prospect accounts; premium understated design; authorised photography (rights note per media item); ≈ 8 templates and ≈ 15 components on a documented design-system page; wireframes, desktop and mobile mock-ups (375 and 1440), a clickable HTML prototype (our medium is code, not Figma); a **claims register** (claim, source, page, ASSET OK + date) signed before J5.

## 2.4 Forms, enquiries, measurement, permissions

| # | Requirement | We build | Acceptance |
|---|---|---|---|
| F01 | BT: company, name, business email, phone, category, volume, requirement, comments; save + acknowledge | Single-page form; durable save → acknowledgement email + on-screen confirmation | T01 |
| F02 | MICE: event type, destinations, flexible dates, travellers, services, optional budget, contact; summary before submit | 3–4 step progressive form; back keeps data; review screen | T02 |
| F03 | Congress: pre-filled event, departure, destination, dates, travellers, class, contact; not one airport only | Opened from a listing with hidden congress ID + visible name; free-text departure with suggestions | T06 |
| F04 | Server-side validation, anti-spam, dedup, privacy info, send log, fallback if email fails | Schema validation in the Worker; Turnstile; dedup (same email + type + congress within 24 h → event on first record); privacy notice version stored; `send_log`; Brevo → Resend fallback → flag + retry + Console banner; durable write before "thank you" | T01–T02 with email provider deliberately broken |
| F05 | Recipients by activity; admin with status, owner, history, CSV export | Recipient table (admin only); inbox | Routing test |
| F06 | No personal data in URLs or analytics; events respect consent | POST-only; confirmation URL carries no data; beacon strips query strings | T09; payload crawl shows no email/phone |
| CRM | API/webhook, quoted separately; core works without | Outbound connector after durable save; auth as Worker secret; lookup-by-email upsert; 3 retries + dead-letter list + resend; API version pinned (option, 6 h) | Forms pass with connector off |
| G1–G5 | Enquiry model, inbox, export, retention, routing | `enquiry` + `enquiry_event` tables; statuses; role-gated logged CSV export; proposed retention (prospects 3 years after last contact, spam 30 days; nightly purge; to verify against CNIL guidance) | T01–T02, T06, T14 |
| H1–H4 | Track CTA clicks, form starts/submits/errors, searches, listing views, account requests, client-area clicks; source/page/activity; no PII; baseline | First-party beacon → Worker → `event` table (no cookie, no IP); Cloudflare Web Analytics for page views (verified: no custom events, so the beacon is needed); Console dashboard | Payload check; baseline in J1 |
| I1–I9 | 5 roles, least privilege, admin MFA, versions + restore, access logs, accidental-deletion protection | See §4.5 (permissions), §4.2 (state machines), §5 (Access) | Role × action test matrix; T05, T15 |

## 2.5 Congress catalogue (L2)

| # | Requirement | We build | Acceptance |
|---|---|---|---|
| C01 | Create/edit via CMS and CSV; validate; detect duplicates | Console form (dates ordered, URL valid, required fields); CSV import with dry run (§4.7) | Invalid record refused; duplicate flagged |
| C02 | Text search; filters (discipline, country, period, city, name); ascending date; pagination; no-results | Client-side search over a pre-built JSON index (300 records); 20 per page; reset + contact on no-results | T03 |
| C03 | Publication status separate from business authorisation; nothing internal public | Editorial status on `congress`; business workflow only in the private database; public build reads a public view | T04; HTML scan finds no internal status words |
| C04 | GM&E codes and evidence never in HTML, scripts, public responses, public exports or browser | Separate private D1 database bound only to the admin Worker; code encrypted at rest; evidence in a private R2 bucket; approver-only API; leak scanner | T05 |
| C05 | Preferential-fare claims only after human approval; no "official agency" claim without authorisation | `fare_badge` settable only by an approver at stage "approved for sale" | Badge absent until approved |
| C06 | Official source and verification date; past-event rule and SEO | "Official website" + "Verified on dd/mm/yyyy"; proposed rule: past-edition banner, form off, link to next edition, indexable 12 months, then 301 to next edition or discipline page | T07 |
| C07 | Ticket enquiry linked to congress ID; notify; save; no issuance | F03 carries `congress_id`; type CONG; routed per F05 | T06 |
| Workflow | Detected → verified → GM&E application to prepare → submitted → code received → issuance authorised → approved for sale → archived; internal | State machine in private DB with history (§4.2) | Transition tests |
| Editorial | Draft → approval → publication; return to draft without data loss | Shared editorial machine (§4.2) | T04 + return-to-draft test |
| Data | Congress and private-authorisation field lists (RFP p5) | `congress` and `authorisation` tables with exactly those columns (§4.1) | Schema doc |
| Import | CSV schema, required fields, errors, duplicates, exports, change log, 300 listings | Versioned schema v1; hard/soft duplicate rules; dry run → report → confirm → import as drafts → bulk publish; batch ID in audit log | 300-row dataset imported |
| i18n | FR/EN URLs, canonicals, hreflang | `/fr/congres/{slug}`, `/en/congresses/{slug}` (EN off) | hreflang validator |

## 2.6 Architecture, security, data protection, handover, quality, SEO, acceptance

| Area (RFP) | Requirement summary | Our answer (detail in §) |
|---|---|---|
| Architecture p6 | Fast indexable frontend, CMS with structured catalogue, enquiry management, decoupled interfaces, diagram, data flows, dependencies, costs, reasonable alternative; secrets server-side | §5.1–5.3; Directus alternative costed §5.10 |
| Wondermiles p6 | Core: page, demo request, configurable client-area link, click measurement, no passwords. L3: SSO feasibility; API separately. No assumed Air France–KLM API | Link + event; L3a study (4 h) → L3b SSO (12 h) → L3c after study |
| Environments p6 | Dev/staging/prod; staging restricted and not indexed; HTTPS, hardening, updates, access control, form protection, logging, security testing; no secrets in repo/browser | §5.4, §5.8 |
| Data protection p6 | Privacy info and lawful basis per form; unticked marketing boxes; tracker consent; retention, deletion, subprocessors, transfers, DPA; DSR procedure | §4.6, §5.8 |
| Ownership p6 | Accounts under ASSET control; source, repo, design files, data, media handed over; non-transferable licences listed; exports, backups, transfer | §6.7 |
| Quality p7 | Responsive at 320/375/768/1440 + real devices; LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1 at p75 where field data exists + lab reports; WCAG 2.2 AA; backups RPO 24 h / RTO 8 business hours; measurable SLA | §5.6, §5.7, §9 |
| SEO p7 | Crawl, inventory, decide per URL; 301/308 without chains or blanket-to-home; editable meta, headings, URLs, structured data, sitemap, robots, canonicals; staging not indexable; reports; Search Console after launch | §4.8 |
| Content p7 | ASSET validates services, claims, images and rights; supplier states counts, writing vs migration, revisions, translation | 20 + 3 pages; 300 listings; migration + light edit; 2 rounds per stage; translation excluded |
| Maintenance p7 | Security fixes, updates, backups, monitoring, availability, out-of-scope, on-call; illustrated admin guide; deploy/restore/export procedures; account inventory; secure secret transfer; train Veena + backup | §6.7, §7.6 |

**Acceptance tests (RFP §7) and how we run them.**

| Test | RFP scenario | Our test (dataset → expected) | Automated? |
|---|---|---|---|
| T01 | BT form: clear errors, saved once, routed, acknowledged | Invalid → inline errors; valid → 1 row; repeat → 0 new rows + event; recipient email; email provider broken → fallback | Yes (Playwright + D1 assertions) |
| T02 | MICE form: same | Same + summary screen + back keeps data | Yes |
| T03 | Congress search, filters, sort, no-results | 300-row dataset; 10 queries with expected result sets | Yes |
| T04 | Draft not public before approval | Draft slug → 404 on prod; absent from sitemap and search index | Yes |
| T05 | GM&E code invisible to public and unauthorised roles | Leak scanner over all public output with a seeded fake code (proves detection); role matrix: only approver/admin read the vault | Yes |
| T06 | Ticket enquiry with pre-filled event saved and notified | F03 from listing → row with `congress_id` → CONG recipient email | Yes |
| T07 | Past congress under approved rule | End date in past → banner, form off, link; redirect rule unit-tested | Yes |
| T08 | Client-area link, no local password storage | Link to configured URL; schema check: no password column anywhere | Yes |
| T09 | Refusing trackers works and is changeable | Refuse → no tracker requests in network log; change → takes effect | Yes |
| T10 | Priority old URLs redirect correctly | Every priority URL → exactly one 301 → 200 | Yes |
| T11 | Keyboard and screen reader on critical journeys | axe: 0 serious violations + manual script (NVDA/VoiceOver) on 5 journeys | Partly (manual script) |
| T12 | Responsive + performance | 4 widths screenshots per template + Lighthouse lab within targets | Yes (+ eye review) |
| T13 | Successful test restoration | Restore last night's dump into a fresh D1; timed against RTO | Scripted, run by hand |
| T14 | Readable, documented export | Export opened in a spreadsheet; columns match the doc | Partly |
| T15 | Veena publishes then edits without a developer | Veena alone, with the guide: creates an article, publishes, edits, restores a revision | Manual (observed) |

## 2.7 The 30 questions and their defaults

We sent 30 questions in 7 groups (MECE; coverage proof in `D/07_Question_Coverage_Matrix.md`). Eight are "Answer first" (Q1, 2, 3, 5, 6, 9, 15, 18). Every question has a written default that applies if unanswered by 6 November. The full list with defaults is **Appendix A**. The defaults that most shape the design:

| Q | Default that shapes the build |
|---|---|
| Q3 | Management approves each stage within 3 working days; silence = deemed approval of design/content stages; launch always needs written go; acceptance window 5 working days against T01–T15 only. |
| Q6 | New site on `asset-voyagesdaffaires.com`; `assetvoyages.com` redirects (web only, email untouched). |
| Q7 | No trackers carried over; cookie-free analytics + first-party event beacon. |
| Q9 | ASSET writes new copy; we migrate up to 20 existing pages + 3 legal, light edit only. |
| Q15 | All enquiries to one shared mailbox (direction@assetvoyages.com) until ASSET names others; no reply-time promise. |
| Q17 | One spreadsheet of up to 300 congresses in our template; one import + error report; no research of events. |
| Q18/Q20 | No fare code or fare wording anywhere until ASSET confirms GM&E in writing; only "request a quote". |
| Q21 | Past congress stays online as past edition, quote button off. |
| Q22 | One request = one group, one departure city, flights only; extras in free text. |
| Q23 | One "Client login" button to today's Traveldoo URL, editable in admin. |
| Q26 | One-time code to named work email, then a second factor (authenticator app or security key); or the client's Microsoft 365 / Google Workspace with its own MFA. |
| Q27 | Database in the EU; US providers under DPAs; no security questionnaire included. |
| Q28 | Two editors (Veena + backup); management reads enquiries and gives final congress approval; only Veena and management see GM&E codes. |
| Q30 | Support Mon–Fri 9:00–18:00 Paris; target site back within 8 business hours after a serious incident on our side; hosting-provider outages excluded. |

## 2.8 What the clarifications reply (31 October) promised

The client asked seven clarification questions. Our reply (`D/01c_…`) committed us to the following, all of which the proposal must now carry:

| Promise | Where it lands in this plan |
|---|---|
| Standard open-source stack; no proprietary framework; maintainable by another developer from the repo and docs | §5, §6.7 |
| A fixed list of editable **section types**; what stays with a developer (new section types, design system, integrations, platform) | §4.1 (`block` types), §6.3 |
| Source repo in an organisation in ASSET's name, handed over in full with all rights at completion; admin guide; runbook; full export runnable by ASSET; defined **transfer package** with a stated duration of transfer assistance | §6.7 |
| 2 revision rounds per design stage and per content stage | §7.2 |
| A one-page **prototype table**: every visible element marked included / optional / illustration only | §6.1 (contract C0) |
| A congress **spreadsheet template** with a dry-run validation before the real import; data-quality checks (required fields, dates, duplicates, broken official links) and a rejection report; no event research | §4.7 |
| Fixed price for core; monthly plan with measured commitments; hourly rate and change procedure | §7 |
| 50% at J0, 50% at J5 acceptance before cutover; free correction of any in-scope T01–T15 failure; dated schedule; symmetric lateness rules | §1.5, §7 |
| Wondermiles: link at launch; feasibility study, then integration quoted after | §2.6 |
| Optional asks: "Site by ProdCraft" footer credit; a LinkedIn post after launch (strikable, never a condition) | Proposal clause |

## 2.9 Questions for the reviewers

1. Is any RFP cell missing, or mapped to an acceptance check that would not convince a sceptical client?
2. T11, T13, T14 and T15 are partly manual. Is that acceptable, or would you insist on more automation?
3. Our deemed-approval defaults (Q3) are aggressive. Do they protect the schedule enough to justify the friction?
