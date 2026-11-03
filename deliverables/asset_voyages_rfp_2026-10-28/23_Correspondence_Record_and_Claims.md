# 23 — Correspondence record and claims register (ASSET Voyages bid)

Internal, audit only. Compiled 3 Nov 2026. Purpose: let the negotiator write the next email from facts only.

**Source conventions.** `brief` = `/tmp/rfp/brief.txt` (RFP v0.4 EN, line numbers). `form` = `/tmp/rfp/form.txt`. `01` / `01c` / `01d` = `D/01_…`, `D/01c_…`, `D/01d_…` (line numbers in each file). `Q-page` = `D/site/questions/index.html` (cited by section §NN or question QN, since the HTML has no stable line numbers). `pour-asset`, `console`, `concept` = the other three live pages.
**Caveat on their emails.** None of ASSET's three emails exists verbatim in the repo. Their 28 Oct and 3 Nov emails are recorded here from the operator's summary (task brief of 3 Nov); their 31 Oct email only survives as the headings of our reply `01c` (7 points; `advisory/src/part1.md:155` says "seven clarification questions"). Before quoting ASSET back to itself, paste from the original email, not from this file.

---

## A. Timeline

| Date | Who → whom | What | File |
|---|---|---|---|
| 27 Oct | ASSET (internal) | "Supplied project requirements document dated 27 October 2026" = source of the RFP (brief 26) | not held |
| 28 Oct | Veena Khatri → suppliers | Email + RFP v0.4 EN ("prepared for management approval before circulation", brief 24) + optional one-page response form. Asked: approach/CMS; costs split core / Congress / options / recurring; timeline, milestones, team; examples; maintenance, hosting, support, handover; assumptions, exclusions, questions. FR at launch, EN separate, Wondermiles API/SSO and AI separate; form optional | `/tmp/rfp/brief.txt`, `/tmp/rfp/form.txt`; email: operator summary only |
| 28 Oct | ProdCraft (internal) | RFP analysis, functional breakdown, market pricing, effort estimate (≈265 h custom stack) | `D/00_…`, `D/03_…`, `D/research/market_pricing_paris_2026.md`, `D/research/effort_estimate.md` |
| 28 Oct | Debanjan → direction@assetvoyages.com | Cover email: 4 unlisted pages, 30 questions, answers by Fri 6 Nov, proposal 24–48 working h after answers | `D/01_Questions_for_Veena.md` |
| 28 Oct | ProdCraft → ASSET (links) | Concept site, "pour-asset" note (FR), console mock-up, questions page (understanding, running costs, availability, project plan, 30 questions + defaults) | `D/site/index.html`, `D/site/pour-asset/`, `D/site/console/`, `D/site/questions/` (+ answer sheet PDF/DOCX) |
| 31 Oct | Veena → ProdCraft | Clarification email: 6 bullets + Wondermiles (technologies/maintainability; what team can change; code, docs, exports, transfer; revisions + prototype at launch; import/check 300 listings; fixed price, milestones, maintenance, change rates; Wondermiles API/SSO separate) | reconstructed from `D/01c_…` headings |
| 31 Oct | Debanjan → Veena | Point-by-point reply, no prices; PDF "Status: clarification, not an offer" | `D/01c_Reply_to_clarifications_2026-10-31.md`, `D/proposal/ProdCraft_ASSET_Voyages_Pre-contract_Clarifications_2026-10-31.pdf` (text matches 01c) |
| 3 Nov | Veena → ProdCraft | Management review: WordPress required; max initial development €3,000 excl. VAT; new scope list; asks (see B); revised proposal by Fri 6 Nov or earliest date; selection subject to management approval | operator summary only |
| 3 Nov | ProdCraft (internal) | WordPress feasibility (≈112 h), pivot audit, self-audit | `D/research/wp_feasibility_2026.md`, `D/21_Pivot_Audit_WordPress.md`, `D/22_Self_Audit_2026-11-03.md` |
| 3 Nov | ProdCraft (draft) | Reply to WordPress pivot — **NOT SENT**; contains errors (see H) | `D/01d_Reply_WordPress_pivot_2026-11-03.md` |

---

## B. What ASSET has put in writing

### B1. Commitments / binding statements (theirs)

| # | Statement | Source |
|---|---|---|
| 1 | "No production work or DNS changes may take place without written authorisation from ASSET management." | brief 73–74 |
| 2 | "The core scope L0 + L1 + L2 must operate without L3 or L4." | brief 97 |
| 3 | "Each milestone requires an identified deliverable and written approval from ASSET as project owner." | brief 72 |
| 4 | "Payments will be negotiated against accepted milestones; the balance depends on acceptance and outstanding items as defined in the contract." | brief 429–430 |
| 5 | "The 12 to 18 week timeframe in the source brief is indicative." | brief 428 |
| 6 | "Any clarification that changes the scope will be shared with all invited suppliers." | brief 485–486 |
| 7 | "Submitting a proposal does not constitute an order or authorise access to or changes on the production website." | brief 486–487 |
| 8 | "ASSET will determine final terms and selection criteria." | brief 458 |
| 9 | Assessment criteria: "user journeys, UX, the Congress catalogue, scalability, SEO, security, methodology, team, overall cost and maintenance." | brief 456–457 |
| 10 | "Initial proposal in your own format; prices in euros. The response form is optional." | brief 28; form 4 |
| 11 | "Confidentiality: restricted to invited suppliers." | brief 42 |
| 12 | 3 Nov: WordPress required; maximum initial development budget €3,000 excl. VAT; hosting/maintenance separate; advanced AI, contract analysis, subscription billing, Wondermiles API/SSO reserved for later; final selection subject to management approval | 3 Nov email (summary) |

Note: nothing they sent commits ASSET to a decision date, a start date or a go-live date.

### B2. Everything they have asked for (deduplicated)

| Ask | First source | Repeated in |
|---|---|---|
| Approach / CMS recommendation with justification and an alternative | brief 104, 286–288; form 11 | 28 Oct email; 31 Oct pt 1 |
| WordPress as the platform | 3 Nov | — |
| Fixed / itemised price in € (HT, VAT rate, TTC); core L0/L1/L2, options L3/L4, annual costs, licences, third parties | brief 448–449 | 28 Oct (core/Congress/options/recurring); 31 Oct pt 6; 3 Nov (final fixed price ≤ €3,000 HT) |
| Total core cost over three years | brief 450 | — |
| Included / excluded features; every exclusion, licence, subscription | brief 99 | 28 Oct; 3 Nov |
| Page and listing allowance, content writing vs migration, revisions | brief 361–362 | 31 Oct pt 4–5; 3 Nov (page allowance, design revisions, content migration, initial Congress import allowance) |
| Schedule, milestones, effort, dependencies | brief 428–429 | 28 Oct; 31 Oct pt 6; 3 Nov |
| Named project lead, effort by role, team | brief 452–453 | 28 Oct |
| References (verifiable B2B / travel / MICE / catalogue) | brief 452 | 28 Oct (examples); form 9; 3 Nov (**completed WordPress references**) |
| Administration demonstration (Congress catalogue + commercial content) | 3 Nov (new) | — |
| Technologies / plugins | 3 Nov | 31 Oct pt 1 |
| Additional charges / rates for future changes | 31 Oct pt 6 | 3 Nov |
| Itemised: hosting, backups, security, WP updates, plugin licences, assistance, bug fixes | brief 366, 449; form 16 | 3 Nov |
| Maintenance, SLA, support hours, response/resolution times | brief 343–344, 366 | 28 Oct; 31 Oct pt 6 |
| Ownership: domain/hosting/CMS/accounts under ASSET; source, Git, design files, data, media; transfer to another supplier | brief 314–317, 461 | 31 Oct pt 3; 3 Nov (full ownership of site/source/data, admin access, documentation, handover) |
| Freedom to self-manage or appoint another developer, no mandatory long-term maintenance | brief 316 (transfer) | 3 Nov |
| What the team can change without a developer | brief 34, 400–401 (T15) | 31 Oct pt 2 |
| Prototype elements included at launch | — | 31 Oct pt 4 |
| Import and checking of 300 listings | brief 271 | 31 Oct pt 5; 3 Nov |
| Wondermiles API/SSO priced separately | brief 13, 89, 294 | 28 Oct; 31 Oct pt 7; 3 Nov (deferred) |
| FR at launch, EN quoted separately | brief 116–117 | 28 Oct; form 17 |
| Earliest start date and duration | form 19 | 3 Nov (earliest delivery date of proposal) |
| Revised proposal by Fri 6 Nov or earliest date | 3 Nov | — |

---

## C. What ProdCraft has committed to in writing (sent items only)

Legend: **CONTRADICTED** = the WordPress / €3,000 pivot makes the statement untrue as sent; **RESTATE** = still deliverable but must be re-numbered or re-worded; **HOLDS**.

| # | Our statement (quote / close paraphrase) | Source | Pivot status |
|---|---|---|---|
| 1 | Answers by Fri 6 Nov; unanswered questions follow the stated assumption | 01:25; Q-page §08 | HOLDS |
| 2 | "We send the full proposal, with costs, within 24–48 working hours of receiving your answers" / "or by Tuesday 10 November if no answers arrive by 6 November" | 01:25; Q-page §08, Q1; pour-asset "Prochaines étapes"; 01c:30 | RESTATE: client now wants it by Fri 6 Nov |
| 3 | "The concept and the console are illustrations, not a list of what is included; what is included is set only by the signed proposal." | 01:23; Q-page §01; pour-asset; console | HOLDS (protects us on the Console) |
| 4 | "Our recommendation: a custom build… with its own admin and no paid plugins to keep updated." | Q-page §03 | **CONTRADICTED** |
| 5 | Alternative = Directus on a rented server | Q-page §03 | **CONTRADICTED** (WordPress mandated) |
| 6 | "Fewer moving parts means less to keep secure"; pages "prepared in advance and served from close to the visitor" | Q-page §03 | **CONTRADICTED** as an argument (implicitly against WordPress) |
| 7 | "Low running cost. About €5–15 a month in provider fees"; Cloudflare/Brevo/Resend/UptimeRobot table; typical total ≈ €5–15, up to ≈ €25 | Q-page §03, §04 | **CONTRADICTED** (WP hosting ~€8–35/mo, U) |
| 8 | "Daily backups kept 30 days: the database can be restored to any minute of the last 30 days" | Q-page §04 and defaults | **CONTRADICTED** (any-minute PITR is Cloudflare D1; WP = daily snapshots) |
| 9 | "We target 99.5% availability each month, measured by an independent outside check every 5 minutes"; monthly report with maintenance plan | Q-page §05 | RESTATE (only via care plan; host SLA governs) |
| 10 | Updates "go live without taking the site offline… previous version… put back within minutes"; enquiry saved through a backup path | Q-page §05 | **CONTRADICTED** as stated (WP architecture differs) |
| 11 | "Ms Khatri publishes directly. The Console lets her edit pages, add or import congresses…" | Q-page §03, J3; pour-asset | RESTATE (WP admin replaces Console; 01:23 caveat helps) |
| 12 | Staff two-step login via Cloudflare Access / M365 / Google Workspace | Q-page §04, Q26 | **CONTRADICTED** (WP 2FA plugin) |
| 13 | DB in the EU; Cloudflare and Resend are US providers under DPAs | Q27 default | RESTATE (provider list changes) |
| 14 | 01c §1: "a static site generator… a small custom administration… running on Cloudflare's platform, with a standard SQL database" | 01c:9 | **CONTRADICTED** |
| 15 | 01c §2: what the team can change "through the console"; "exact list of section types is fixed in the proposal" | 01c:12 | RESTATE (section types = block patterns) |
| 16 | 01c §3: "complete source repository, held in a repository organisation in ASSET's name and handed over in full, with all rights, at completion"; admin guide + runbook; full export; transfer package; all service accounts in ASSET's name | 01c:15 | HOLDS in substance (repo now = custom theme/plugin; GPL caveat). Note "at completion" — keep tied to full payment |
| 17 | 01c §4: "Two revision rounds are included at each design stage (wireframes, then desktop and mobile mock-ups), and two revision rounds at each content stage"; Q-page §07 same | 01c:18; Q-page §07 | RESTATE — at €3,000 this is a cost commitment already in writing; any reduction must be explicit |
| 18 | 01c §4: one-page table of every prototype/console element marked included / optional / illustration, "before you sign" | 01c:18 | HOLDS — owed in the proposal |
| 19 | 01c §5 / Q17: import once, ≤300 rows, our template, dry run, rejection report; no research | 01c:21; Q17 | HOLDS |
| 20 | Q9: migrate up to 20 existing pages + 3 legal pages, wording edits only; ASSET writes new French copy | Q9 | HOLDS (now a cost line at €3,000) |
| 21 | 01c §6: fixed price for core scope; monthly maintenance plan with measured commitments; hourly rate + change procedure | 01c:24 | HOLDS |
| 22 | 01c §6: "50% at J0, on signature… and 50% at J5, on acceptance, before cutover"; acceptance = T01–T15 pass on staging + written confirmation; J6 stabilisation included | 01c:26 | HOLDS |
| 23 | 01c §6: "Maintenance, if you choose the plan, is invoiced at the start of each month from launch" | 01c:26 | HOLDS (optional; no minimum term was never sent — a minimum was only in internal drafts) |
| 24 | 01c §6: "we commit to a dated schedule and correct, at no extra cost, anything in the agreed scope that fails one of the acceptance tests (T01 to T15)" | 01c:28 | HOLDS — cost exposure at €3,000 |
| 25 | 01c §6: "I would rather not put figures in an email ahead of the proposal" | 01c:30 | HOLDS (note: 01d draft puts figures in an email) |
| 26 | 01c §7: launch "client login" link, default today's Traveldoo address, editable; API/SSO in two steps (feasibility, then integration) | 01c:33; Q23 | HOLDS (they now defer API/SSO) |
| 27 | 01c §8: footer credit and LinkedIn post requested, optional | 01c:36 | HOLDS (optional) |
| 28 | Q-page §07: "work starts within 5 working days of the signed proposal, and launch follows about 12 weeks after the start"; no launch 21 Dec–1 Jan | Q-page §07, Q1 | RESTATE (12 weeks sized for the custom build) |
| 29 | Q3: approvals within 3 working days, deemed approval of design/content stages; acceptance testing 5 working days, T01–T15 only | Q3 | HOLDS |
| 30 | J6 "Settling in (4 weeks)", defects against accepted tests only | Q-page §07, defaults | HOLDS / RESTATE if shortened |
| 31 | Training: "two recorded video sessions, in French" | Q-page defaults | HOLDS |
| 32 | Q29/Q30: optional plan with up to 5 h changes/month; support Mon–Fri 9–18; site back within 8 business hours | Q29–Q30 | RESTATE (care plan now optional, priced separately) |
| 33 | Proposal costs split: audit, core site, Congress module, each option, yearly running/maintenance, 3-year total, HT and TTC; project lead + effort by role | Q-page §09; pour-asset | RESTATE — a single €3,000 figure still owes this split and the 3-year total |
| 34 | "Examples of our work come with the proposal, described without naming our clients; we can put you in touch with a client only with that client's permission." | Q-page §09 | HOLDS — collides with their new ask for WordPress references |
| 35 | Cookieless analytics; no trackers carried over (Q7); retention 3 years; WCAG 2.2 AA design target, no certification | Q7; defaults | HOLDS (platform-neutral) |
| 36 | "Rien n'a été touché sur votre site ni sur vos outils"; no prices, GM&E codes, client references or testimonials invented | pour-asset | HOLDS |

Not sent, so not a commitment: everything in `01d` (Options A €3,000 / B €4,000, €8–9k market claim, references wording).

---

## D. Their 3 Nov scope list vs the original brief

| 3 Nov item | Status | Exact brief text |
|---|---|---|
| Business Travel section | **IN** | 125 "Business Travel — Advice, online/offline services, support, FAQ and travel review request"; 83 L1 "Business Travel and MICE pages" |
| MICE section | **IN** | 138 "MICE — Hub, groups and seminars, incentives and conventions; brief and quotation request" |
| International Congress section | **IN** | 141 "Congresses — Filterable catalogue and event listing…" |
| Independently manageable Congress catalogue | **IN** | 34 "publish content and Congress listings without a developer"; 86 L2; 228 C01; 400–401 T15 |
| Consulting page on corporate travel cost optimisation | **PARTIAL** | No "consult"/"optimis"/"saving" in the brief. Nearest: 125 "Advice… travel review request"; 130 "Procurement and travel managers — Travel policy, reporting, expenses, invoicing and travel audit"; 154 "travel review and contact". A dedicated cost-optimisation consulting page is new |
| ASSET Savings Scan enquiry form | **NOT by name** (partial analogue) | Name absent. Brief forms are F01–F03 only (177–184). Functional analogue: "travel review request" (125, 154), within F01 Business Travel. Risk: ASSET may say Savings Scan = the travel review |
| Presentation of future SmartFees subscription offers | **NOT** | Absent. Nearest: 127 "SMEs and microbusinesses — Simplified offer, use cases, demo or account request" |
| Wondermiles presentation page | **IN** | 135 "Digital solutions — Approved Wondermiles presentation, authorised images, demo request and client access"; 292 "Core scope: presentation page…" |
| Corporate account enquiry form | **PARTIAL → mostly IN** | Account requests are in: 127 "demo or account request"; 135 "demo request"; 152 "account or demo request"; 292 "demo or account request"; 207 "account requests" tracked. Not a separate form ID (F01–F03) |
| Link to existing booking platform | **IN** | 292 "configurable external client-area link and click measurement"; 157 "client area → authorised external tool"; 391 T08 |
| Deferred: advanced AI | IN brief as option | 92 L4 optional |
| Deferred: Wondermiles API/SSO | IN brief as option | 89 L3 optional; 294–295 |
| Deferred: automated contract analysis | NOT in brief | absent |
| Deferred: subscription billing | NOT in brief | absent |
| Also asked 3 Nov: admin demonstration | NOT in brief | absent (references only, 452) |
| Also asked 3 Nov: WordPress references | PARTIAL | 452 asks "Verifiable B2B, business travel, MICE or editorial catalogue references"; "WordPress" absent from the brief |
| WordPress | NOT in brief; brief asks for a recommendation | 104 "Recommend retaining or replacing the CMS with technical and cost justification"; 287–288 "a reasonable alternative to the recommended CMS". Current site is WordPress 6.9.11 (curl 28 Oct, `HANDOFF.md` 269) |
| Budget figure | NOT in brief | No € figure anywhere; 469 "Budget envelope, any cap" is listed as a decision to confirm |

Net genuinely new vs brief: consulting page (partial), Savings Scan form (new by name), SmartFees presentation (new). Wondermiles page and booking link are in the brief; corporate-account request is in the brief as an action.

---

## E. Our 30 questions (Q-page §08) — answered by their messages?

| Q | Topic | Status | Their answer |
|---|---|---|---|
| 1 | Proposal due, selection date, go-live date | **PARTLY** | 3 Nov: "revised proposal by Friday 6 November or earliest delivery date"; "final selection subject to management approval". No go-live date |
| 2 | Budget range / cap | **ANSWERED** | 3 Nov: "maximum initial development budget €3,000 excl. VAT"; hosting/maintenance separate |
| 3 | Approvers, approval days | **PARTLY** | 3 Nov: management approval of selection; brief 59 (management approves); no days |
| 4 | Current provider / contract | UNANSWERED | — |
| 5 | Accounts ownership | UNANSWERED (interest stated) | 3 Nov asks full ownership; who owns today's accounts not said |
| 6 | Which domain | UNANSWERED | — |
| 7 | GA/GSC access, trackers | UNANSWERED | — |
| 8 | Selectour requirements | UNANSWERED | — |
| 9 | Who writes copy, page count | UNANSWERED (reversed: they ask us for the page allowance and migration) | — |
| 10 | Brand guidelines | UNANSWERED | — |
| 11 | Photos, logos, testimonials | UNANSWERED | — |
| 12 | SME simplified offer | **PARTLY** | 3 Nov: "presentation of future SmartFees subscription offers"; "corporate account enquiry form" |
| 13 | Assistance services | UNANSWERED | — |
| 14 | English | **PARTLY** (pre-existing) | 28 Oct / brief 116–117: FR at launch, EN quoted separately; translator not named |
| 15 | Enquiry recipients | UNANSWERED | — |
| 16 | CRM / newsletter | UNANSWERED | — |
| 17 | 10 sample congress rows | UNANSWERED (they ask for an "initial Congress import allowance") | — |
| 18 | GM&E arrangement | UNANSWERED | — |
| 19 | Approval chain for congresses | UNANSWERED | — |
| 20 | Public fare wording | UNANSWERED | — |
| 21 | Past congresses | UNANSWERED | — |
| 22 | Scope of a congress quote request | UNANSWERED | — |
| 23 | Wondermiles vs Traveldoo, client login | **PARTLY** | 3 Nov: "link to existing booking platform" (which platform not named); API/SSO later |
| 24 | Wondermiles content permissions | **PARTLY** | 3 Nov: Wondermiles presentation page wanted; no logo/screenshot permission given |
| 25 | AI option | **ANSWERED** (deferred) | 3 Nov: "advanced AI… reserved for later" |
| 26 | M365 / Google Workspace | UNANSWERED | — |
| 27 | EU/France data, questionnaires, DPO | UNANSWERED | — |
| 28 | Admin users | UNANSWERED | — |
| 29 | Monthly change volume | UNANSWERED | 3 Nov only: no mandatory long-term maintenance |
| 30 | Support hours, tolerable outage | UNANSWERED | 3 Nov: hosting/maintenance costed separately |

Count: 2 answered, 7 partly, 21 unanswered. The answer sheet has not been returned (no file in repo). Per our own terms (01:25, Q-page §08), unanswered items follow the published defaults.

---

## F. Negotiation interests map

| Topic | ASSET position (stated) | ASSET likely interest | ProdCraft position | ProdCraft interest |
|---|---|---|---|---|
| Price | ≤ €3,000 HT initial development (3 Nov) | Contain spend; get management sign-off; compare suppliers on a like-for-like cap | Fixed price against a written scope (01c:24) | Paid fairly for hours; no unbounded scope at a fixed fee |
| Platform | WordPress (3 Nov) | Familiarity (current site is WP); replaceable supplier | We recommended custom build (Q-page §03) — now accept WP | Deliver on WP without arguing (22 standing correction) |
| Independence | Self-manage or appoint another developer; no mandatory maintenance (3 Nov) | Avoid lock-in | Care plan optional (01c:26; 21 L14) | Recurring revenue optional; liability ends at handover |
| Ownership | Full ownership of site, source, data; admin access; docs; handover (3 Nov; brief 314–317) | Control | Repo + accounts in ASSET's name (01c:15) | Rights/repo transfer on full payment |
| References | Completed WordPress references (3 Nov) | De-risk an unknown supplier | No client names (Q-page §09) | Confidentiality of clients; no WP portfolio to show (UNVERIFIED in 01d) |
| Demo | Admin demo of Congress catalogue + commercial content (3 Nov) | See the tool before deciding | No work before signature (22 standing correction: demos only after signature) | Avoid free build work for an uncommitted buyer |
| Deadline | Revised proposal by Fri 6 Nov (3 Nov) | Management meeting cycle | We had said 10 Nov fallback (Q1) | Meet 6 Nov |
| Decision | Subject to management approval (3 Nov; brief 24, 59) | Keep options open | — | Price/slot validity limited (21 L24–L25) |
| Payment | Against accepted milestones (brief 429) | Pay for delivered value | 50/50: signature / acceptance before cutover (01c:26) | Cash before work; no cutover before final payment |
| Third-party costs | Itemise hosting, backups, security, updates, licences, assistance, bug fixes (3 Nov) | Transparent TCO | Tool costs paid by ASSET directly, in ASSET's name (operator rule; 01d draft) | Zero pass-through risk |
| Scope additions | Consulting page, Savings Scan, SmartFees, (Wondermiles page, account form, booking link) | More for same cap | Allowances numbered; extras = change requests | Price follows scope |

**Their BATNA.** Other invited suppliers (brief 42 "restricted to invited suppliers"; 485–486 "shared with all invited suppliers" — note this is §8 "Consultation process"). Also: keep the current WordPress site/current provider (Q4 unanswered); low-cost marketplace freelancers (Codeur.com average web project €1,434, VERIFIED fetch Oct 2026). Strength unknown: number and prices of other bidders are not known.
**Our BATNA.** Decline or bid only the scope €3,000 covers; reuse the concept work (ProdCraft IP if not selected, 21 L23). Value of alternative pipeline: not documented (UNVERIFIED).

---

## G. Objective criteria

| Criterion | Figure | Source | Status |
|---|---|---|---|
| Paris/France experienced full-stack freelance day rate | ~€520–600/day (median ~525–560); range €450–650 | market_pricing §1 (Malt, TJMetre, Freeland, Hays…) | Mostly search-engine summaries, primary pages 403 → **UNVERIFIED (secondary)** |
| Codeur.com web dev avg €135/day; avg project €1,434 | market_pricing §1–2 | **VERIFIED** (fetched Oct 2026); low-end marketplace |
| Small agency day rate €550–800; agency €600–1,200 | market_pricing §2 (La Fabrique du Net via summary; AquilApp) | UNVERIFIED (summary) |
| Vitrine site: freelance €1,500–3,000; small agency €2,900–4,500; mid agency €3,000–8,000 (5 pages) | LeLab360 | Published, search-level → UNVERIFIED |
| "Custom site with specific back-office and APIs: from €8,000" | Agence2web | Published "from" price → UNVERIFIED |
| WP maintenance €50–350/month; out-of-contract €60–150/h | market_pricing §3 | UNVERIFIED (summary) |
| "Realistic market price €7–9k" (WP scope) | wp_feasibility l.81 | **Our derivation, no source** = 112 h × ~€65–75/h. Not a published rate |
| "€8,000 to €9,000 from a Paris agency" | 01d:14 (draft) | **UNVERIFIED / unsupported** — no source in research states this |
| WordPress build effort | ≈112 h (incl. 7 h demo) | wp_feasibility §7 | Internal estimate |
| Custom-stack effort | ≈220 h core, 265 h planning | effort_estimate | Internal estimate (superseded by WP) |
| Plugin prices FacetWP $99+, WP All Import $99–1,299, Gravity Forms $59–259, WPML €39–199 | wp_feasibility §1 | **VERIFIED** (vendor pages, 3 Nov) |
| ACF Pro, WP Rocket, hosting (o2switch ~€8–10/mo, Kinsta ~$35/mo) | wp_feasibility §1–2 | **UNVERIFIED** (model memory, marked U) |

**What €3,000 HT buys:** at €520/day ≈ 5.8 days (≈ 40 h); at €65–75/h ≈ 40–46 h; at small-agency €550–800/day ≈ 3.8–5.5 days. Against the 112 h WP estimate: €3,000 ÷ 112 h ≈ €27/h (wp_feasibility l.81). 112 h at €65–75/h = €7,280–8,400. Removing the 7 h demo and 8 h new-page content (consulting/Savings Scan/SmartFees/Wondermiles) still leaves ≈ 97 h → ≈ €31/h.

---

## H. Claims register for the next email

| # | Claim | Source | Status |
|---|---|---|---|
| 1 | The brief contains no budget figure | brief (no €); 469 | VERIFIED |
| 2 | "€3,000 was set before / against the original brief and not against the added items" | 01d:9 | **UNVERIFIED** inference (timing of the budget decision unknown) |
| 3 | Wondermiles presentation page is in the brief | brief 135, 292 | VERIFIED |
| 4 | "Wondermiles page… not in [the brief]" | 01d:9 | **FALSE** |
| 5 | Corporate account form is not in the brief | 01d:9 | **FALSE** as worded — account/demo requests are in brief 127, 135, 152, 292; only a separate form ID is absent |
| 6 | Link to the existing booking/client platform is in the brief | brief 292, 157, 391 | VERIFIED |
| 7 | Savings Scan is not in the brief | brief (absent) | VERIFIED by name; note travel review request 125/154 is an analogue |
| 8 | SmartFees is not in the brief | brief (absent) | VERIFIED |
| 9 | A cost-optimisation consulting page is not in the brief | brief (no "consult"/"optimis") | PARTLY VERIFIED — advice/travel audit content exists (125, 130) |
| 10 | Contract analysis and subscription billing were never in the brief | brief | VERIFIED |
| 11 | AI and Wondermiles API/SSO were optional in the brief | brief 13–14, 89, 92 | VERIFIED |
| 12 | The brief asked suppliers to recommend keeping or replacing the CMS | brief 104 | VERIFIED |
| 13 | Their current site runs WordPress | HANDOFF.md 269 (curl 28 Oct: WordPress 6.9.11) | VERIFIED (as of 28 Oct) |
| 14 | "Market €8–9k for this WP scope from a Paris agency; published rates" | 01d:14 | **UNVERIFIED** (no source; €7–9k is our own derivation) |
| 15 | "Either option is well under half of that" (A €3,000, B €4,000 vs €8–9k) | 01d:14 | **FALSE** for B at €8,000 (exactly half) |
| 16 | Paris experienced freelance ~€520–600/day | market_pricing §1 | UNVERIFIED (secondary summaries) |
| 17 | €3,000 ≈ 40–46 h at Paris freelance rates; our estimate is ≈112 h | G above | VERIFIED arithmetic on UNVERIFIED rates / internal estimate |
| 18 | We committed to two revision rounds per design stage and per content stage | 01c:18; Q-page §07 | VERIFIED (it is ours, sent) |
| 19 | We committed to 50% on signature / 50% on acceptance before cutover | 01c:26 | VERIFIED |
| 20 | We said we would not put figures in an email before the proposal | 01c:30 | VERIFIED |
| 21 | Our 31 Oct reply was "clarification, not an offer" | PDF header | VERIFIED |
| 22 | We said proposal by 10 Nov if no answers by 6 Nov | Q1; 01c:30 | VERIFIED; superseded by their 6 Nov request |
| 23 | We said examples come "described without naming our clients" | Q-page §09 | VERIFIED |
| 24 | "Our recent production work has been on modern static platforms rather than WordPress" | 01d:32 | UNVERIFIED (no portfolio record checked) |
| 25 | "No maintenance contract is required"; any WP developer can take over | 01d:29 | Consistent with brief 316 and 3 Nov ask; design claim, not yet true |
| 26 | Base build "carries no recurring licence fees" | 01d:20; wp_feasibility l.30 ("€0 recurring licence" stack) | Plausible; plugin free-tier capabilities partly U → UNVERIFIED until stack is tested |
| 27 | Hosting ~€10/mo (o2switch) | wp_feasibility §2 | UNVERIFIED (U, price not retrieved) |
| 28 | Any scope clarification goes to all invited suppliers | brief 485–486 | VERIFIED — so their 3 Nov additions may also be sent to competitors |
| 29 | ASSET answered 2 of 30 questions (budget, AI) and 7 partly | E above | VERIFIED against the summaries; no answer sheet received |
| 30 | Their 3 Nov wording (quotes) | operator summary | UNVERIFIED verbatim — check the original email before quoting |
