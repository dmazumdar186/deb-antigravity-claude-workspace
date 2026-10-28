# ASSET Voyages — question coverage matrix (MECE proof)

Prepared 28 October 2026. Final list: **30 questions in 7 groups**, each with a written default. Inputs: the RFP (`/tmp/rfp/brief.txt`, 9 pages), the response form, ASSET's email, `03_Functional_Breakdown.md`, `99_INTERNAL_kickoff_call_checklist.md` (72 questions; the brief to this task said 75, the file holds 72), `HANDOFF.md` (facts already verified) and `02_Panel_Debate.md` (Common ground, Honest gaps).

**Status key.** **Q** ask ASSET now · **A** we find it ourselves in the J1 audit (how stated) · **D** we propose a default ASSET can override (default stated) · **K** already known (source cited).

**Defensive rule (operator, 28 Oct; tightened in audit round 1).** Every question carries a written default. Answers received by **Friday 6 November 2026** are built into the proposal; anything not answered in writing by then follows that default. ASSET can change an assumption by email until the proposal is signed, and a change may alter price and dates; after signature, changes are agreed in writing with their effect on price and dates. The proposal, once signed, is our contract. The concept, the console and the assumptions are illustrations; only the signed proposal defines scope. So every Q-unknown is also bounded by a D-style fallback.

## Pass 1 — top-down: every unknown in the brief, form and email

106 unknowns: **56 Q · 16 A · 26 D · 8 K**. Walked in brief order: consultation and governance (p1-2, p8-9), L0 audit (p2), site structure and journeys (p3), forms, CRM, data model, measurement, permissions (p4), Congress catalogue and workflow (p5), architecture, partners, security, data protection, ownership (p6), quality, SEO, content, maintenance (p7), acceptance and milestones (p8), decisions to confirm (p9), the form's five boxes and the email's asks.

| ID | Area | Unknown | Status | Final question / how handled |
|---|---|---|---|---|
| U01 | Consultation | Proposal submission deadline | Q | Q1 |
| U02 | Consultation | Supplier selection date and stages (shortlist, demo) | Q | Q1 |
| U03 | Schedule | Hard go-live date, or periods when launch must be avoided | Q | Q1 |
| U04 | Budget | Budget envelope or cap for core L0+L1+L2 | Q | Q2 |
| U05 | Governance | Who approves each milestone and the turnaround in working days | Q | Q3 |
| U06 | Governance | Content owner per activity who validates its pages | Q | Q3 |
| U07 | Commercial | Payment split against milestones | D | 30/30/20/20 against accepted milestones; ASSET may change |
| U08 | Commercial | Tax presentation | K | Brief p9: HT, rate, amount, TTC |
| U09 | Schedule | Earliest start date | D | Within 5 working days of the signed proposal; proposal sent within 24–48 working hours of the answers, or by Tue 10 Nov 2026 if none by 6 Nov; access to today's site due at kickoff (Q1 default, J0) |
| U10 | Governance | Change-request process | K | Brief p2: assessed for cost, schedule, security, SEO |
| U11 | Commercial | Managed monthly plan vs ad-hoc maintenance; minimum term | D | Optional monthly maintenance plan priced in the proposal (term stated there); up to 5 h of changes, no rollover (Q29) |
| U12 | Operations | Stabilisation period length | D | 4 weeks after launch (J6), defects against the accepted tests only; new requests quoted. After J6, support comes from the optional maintenance plan or is quoted per request |
| U13 | L0 audit | Current CMS | K | WordPress 6.9.11: `<meta name="generator">` and `wp-content/` paths in the live homepage HTML, fetched 28 Oct 2026 (HANDOFF) |
| U14 | L0 audit | CMS version, plugins, custom code | A | J1 audit: admin access + fingerprinting |
| U15 | L0 audit | Who maintains current site; contract or notice period | Q | Q4 |
| U16 | L0 audit | Account holders: registrar, DNS, hosting, SSL, email, GA, GSC, Google Business Profile, tag manager | Q | Q5 |
| U17 | Ownership | Who at ASSET owns the new accounts | Q | Q5 |
| U18 | L0 audit | Primary domain for the new site | Q | Q6 |
| U19 | L0 audit | Other domains, subdomains, campaign or microsite pages | Q | Q6 |
| U20 | L0 audit | Which domain carries email (MX records) | A | DNS lookup |
| U21 | L0 audit | DNS records, certificates and expiry dates | A | DNS/TLS inventory |
| U22 | L0 audit | Backups and full export of current site | A | Taken at J0 once hosting access is given (Q5) |
| U23 | L0 audit | Hidden integrations (chat, call tracking, widgets) | A | Page-source inspection; CRM/newsletter asked in Q16 |
| U24 | SEO | Read access to Analytics and Search Console | Q | Q7 |
| U25 | Measurement | Trackers that must stay (LinkedIn, Meta) | Q | Q7 |
| U26 | SEO | Paid campaigns pointing at landing pages that must keep working | Q | Q7 |
| U27 | SEO | Full URL inventory and redirect candidates | A | Crawl of live site |
| U28 | SEO | Pages and keywords that bring business | A | Search Console export (access via Q7) |
| U29 | Measurement | Traffic and enquiry baseline | A | Analytics + form inventory in J1 |
| U30 | Performance | Current speed and Core Web Vitals | A | Lighthouse + Chrome UX Report |
| U31 | Compliance | Consent tool and trackers installed today | A | Inspect live site |
| U32 | Compliance | Existing legal notices and privacy page | A | Read live pages; ASSET validates at J3 |
| U33 | Brand | Selectour network requirements (logos, mentions, brand rules) | Q | Q8 |
| U34 | Content | Who writes French copy vs migration depth | Q | Q9 |
| U35 | Content | Page count at launch, incl. articles, guides, FAQ | Q | Q9 |
| U36 | Brand | Brand guidelines, vector logo, fonts; logo fixed or refresh | Q | Q10 |
| U37 | Content | Authorised photos; stock acceptable | Q | Q11 |
| U38 | Content | Approved claims, client logos, testimonials, figures | Q | Q11 |
| U39 | Content | Team members shown by name/photo (consent) | Q | Q11 |
| U40 | Content | Facts on today's site still true (122 agences, copyright year) | A | Re-verify on Selectour public sources; ASSET approves via Q11 |
| U41 | Content | Services listed today | K | 13 services fetched from live site (HANDOFF) |
| U42 | Content | SME simplified offer: defined or lead-generation only | Q | Q12 |
| U43 | Content | Assistance services actually available, hours, numbers | Q | Q13 |
| U44 | Languages | English: which journeys first | Q | Q14 |
| U45 | Languages | English: launch or later | Q | Q14 |
| U46 | Languages | Who translates | Q | Q14 |
| U47 | Languages | Third language foreseen | D | Architecture supports N languages; FR+EN sized |
| U48 | Design | Visual preferences, sites admired | D | Premium, understated direction shown in concept; reviewed at J2 |
| U49 | QA | Real devices and browsers used by visitors | A | Analytics device report + our device set |
| U50 | Forms | Recipients per activity, backup person | Q | Q15 |
| U51 | Forms | Reply-time promise in the acknowledgement | Q | Q15 |
| U52 | Forms | CRM in use | Q | Q16 |
| U53 | Forms | Newsletter/email marketing tool (marketing consent box) | Q | Q16 |
| U54 | Forms | Enquiry statuses and reminder rules | D | New, qualified, quote sent, won/lost, plus a reminder flag (console sample aligned in round 1); reminder after 1 business day |
| U55 | Forms | F01 volume unit and bands; company categories | D | Annual travel spend bands; SME / mid-size / large |
| U56 | Forms | F02 budget as total or per person; file upload | D | Optional total budget; optional PDF upload |
| U57 | Forms | Phone/callback preference, booking slots | D | Callback request field; no calendar tool |
| U58 | Forms | Anti-spam method | D | Cookie-free invisible challenge (Turnstile) |
| U59 | Data | Retention of enquiry data | D | Brief asks supplier to propose: 3 years after last contact for prospects (CNIL) |
| U60 | Data | Who handles personal-data requests (DPO or referent) | Q | Q27 |
| U61 | Measurement | Conversion events | K+D | Brief p4 lists them (button clicks, form starts and sends, errors, congress searches, congress page views, account requests, client-login clicks). Counted by the site itself, no cookies, no personal data; Cloudflare Web Analytics does page views only (its FAQ: custom events "Not yet", checked 28 Oct) |
| U62 | Measurement | Commercial targets | K | Brief p4: agreed after the audit |
| U63 | Admin | Who holds each role: backup editor, contributors, commercial viewers; who sees GM&E codes | Q | Q28 (default: only Ms Khatri and management see GM&E codes and evidence) |
| U64 | Admin | Company sign-in (Microsoft 365 / Google Workspace) for MFA | Q | Q26 (default: one-time code to the named work email plus a second step, an authenticator app or security key (Cloudflare Access independent MFA, docs checked 28 Oct); with Microsoft 365 or Google Workspace, that account with its own two-step check) |
| U65 | Training | Training format and language | D | Two recorded video sessions in French |
| U66 | Congress | Existing list of 300, real columns (sample) | Q | Q17 |
| U67 | Congress | Source of listings and any licence limits | Q | Q17 |
| U68 | Congress | Yearly volume of new congresses | Q | Q17 |
| U69 | Congress | Discipline taxonomy for filters | D | Derived from the sample rows (Q17); ASSET edits the list |
| U70 | Congress | GM&E agreement with Air France-KLM in place | Q | Q18 |
| U71 | Congress | GM&E code structure and expiry | Q | Q18 |
| U72 | Congress | Who performs each workflow step | Q | Q19 |
| U73 | Congress | Who approves for sale; conditions before promotion | Q | Q19 |
| U74 | Congress | Public fare wording allowed | Q | Q20 |
| U75 | Congress | Past-event rule | Q | Q21 |
| U76 | Congress | Recurring congresses: slug per edition | D | One page per edition, linked to the next |
| U77 | Congress | Quote covers multiple departure cities | Q | Q22 |
| U78 | Congress | Quote covers hotel/transfers | Q | Q22 |
| U79 | Congress | Congress alert subscriptions | D | Not in core; optional later |
| U80 | Congress | CSV schema, duplicate rule | D | Proposed in proposal, adjusted to Q17 sample |
| U81 | Partners | Wondermiles replacing Traveldoo | Q | Q23 |
| U82 | Partners | Is a client-login link enough at launch, or a single login wanted | Q | Q23 |
| U83 | Partners | Other client tools to link (IRES, Smart app, invoicing) | Q | Q23 |
| U84 | Partners | Wondermiles technical contact | Q | Q24 |
| U85 | Partners | Approved Wondermiles images, logos, product text | Q | Q24 |
| U86 | Partners | Contract allows third-party supplier access to Wondermiles documentation | Q | Q24 |
| U87 | Partners | SSO protocols Wondermiles supports | A | L3a feasibility study with their contact (Q23) |
| U88 | Partners | Data needed for account automation | A | L3a study |
| U89 | Partners | Client-area URL | A | Taken from live site link; confirmed via Q23 |
| U90 | AI | What the AI should do first | Q | Q25 |
| U91 | AI | Sources AI may read | D | Official congress websites only |
| U92 | AI | Volume cap and confidence threshold | D | About 50 candidates a week, monthly spend cap set by ASSET |
| U93 | AI | Who reviews the AI queue | D | The congress approver named in Q19 |
| U94 | Hosting | EU or France data residency | Q | Q27 |
| U95 | Security | Client security questionnaires / ISO | Q | Q27 |
| U96 | Hosting | Subprocessors acceptable (EU data centres, DPA) | D | Database in the EU; US providers (Cloudflare, Resend) under data-processing agreements; full list in the proposal (Q27) |
| U97 | Security | Staging access list | D | ASSET team only, behind two-step login |
| U98 | Security | Secret transfer method | D | Shared password manager |
| U99 | Operations | Support hours, out-of-hours in congress season | Q | Q30 |
| U100 | Operations | Maximum acceptable outage | Q | Q30 |
| U101 | Operations | Backup targets and retention | D | Database restorable to any minute of the last 30 days; photos and documents to the previous day; 30-day retention. With the optional maintenance plan: aim of 8 business hours to restore after a serious incident on our side, hosting-provider outages excluded |
| U102 | Operations | Monthly change volume | Q | Q29 |
| U103 | Quality | Accessibility and performance targets | K+D | Brief p7: WCAG 2.2 AA; LCP/INP/CLS. Default: design target on main journeys, automated + manual tests, written report, no third-party certification; lab speed tests until field data exists |
| U104 | Launch | Cutover authority | K | Brief p8: written authorisation from management |
| U106 | Congress | Other airlines named on congress pages | D | No airline or partner named publicly until ASSET approves in writing (see Q20) |
| U105 | Scope | Exclusions and assumptions | D | On the page (§03) and in the proposal: ticketing, booking engine, ads, paid CRM software, bulk scraping, automatic publication, photography, copywriting beyond Q9, translation |
| U107 | Scope | Revision rounds (brief p7: supplier must specify) | D | One rule: two rounds of changes per design stage and two per content stage (page wording included; Q9 refers to it); further rounds quoted first (§07 on the page) |
| U108 | Governance | Deadline for answers; what late answers do | D | Friday 6 November 2026, returned as one PDF answer sheet; proposal within 24–48 working hours of the answers (by 10 Nov if none); later answers by email until signature, may change price and dates (§08 box) |
| U109 | Congress | Who prepares and cleans the import file | D | ASSET, in our template; one import, error rows returned; no research or rewriting (Q17 default) |
| U110 | Compliance | Who writes the legal pages | D | ASSET supplies or approves the wording of the legal pages; no legal advice from us (Q9 default). ASSET writes the French text for new pages |
| U111 | Governance | Acceptance and deemed approval | D | 3 working days per stage; silence = approved for design and content stages only, unless blocking problems are listed; launch always needs management's written go-ahead; acceptance testing 5 working days against T01-T15 only (Q3 default) |
| U112 | SEO | Redirect scope ("priority URLs", T10) | D | Every address in our crawl and, if access is given (Q7), Search Console's last 12 months, redirected to its closest new page; nothing outside those sources (defaults list, §02 goal 3) |
| U113 | Scope | Concept/console vs contract scope | D | Illustrations only; only the signed proposal defines what is included, and the proposal, once signed, is the contract (§01, email, pitch, console) |
| U114 | Compliance | Consent banner default (brief T09: refusing non-essential trackers works and the choice can be changed) | D | Only if a tracker is kept (Q7): built-in consent banner; the tracker loads only after consent; choice changeable from the footer; no paid consent tool (defaults list, audit round 2) |

Brief's "Decisions to confirm before contract" (p9) cross-check: budget and schedule → Q1-Q2; existing technology → Q4-Q6; content and languages → Q9-Q14 (page counts Q9, brand guidelines Q10, images Q11, English Q14); commercial enquiries → Q15-Q16 (handling rules: D, U54); partners → Q18, Q23-Q24; operations → Q27, Q29-Q30 (backups, retention, stabilisation: D). The email's asks that are ours to answer (approach, costs, timeline, team, examples, exclusions) are not client unknowns; their client-side inputs are U01-U12 and U105.

## Pass 2 — bottom-up: the previous 25 questions

The HTML §08 and `01b` agreed on all 25 except small wording trims in Q4, Q6, Q12, Q19, Q22, Q25 (HTML was current).

| Old # | Question (short) | Q-unknowns resolved |
|---|---|---|
| 1 | When is the proposal due, and is there a date the new site has to be live by? | U01, U03(partly) |
| 2 | Is there a budget range for the core site and the Congress catalogue? A rough bracket is e… | U04 |
| 3 | Who at ASSET approves each stage (design, launch), and how many working days should we pla… | U05 |
| 4 | Who manages the current site today (the site software, hosting, domain), and are those acc… | U15(partly), U16 |
| 5 | Should the new site be on asset-voyagesdaffaires.com, assetvoyages.com, or both? | U18 |
| 6 | Could you give us read-only access to Google Analytics and Search Console, with a list of … | U24, U25 |
| 7 | Does Selectour ask for anything on your website (logos, legal mentions, brand rules)? | U33 |
| 8 | Will your team write the new French copy, or do you want us to rewrite the existing pages?… | U34, U35(partly) |
| 9 | Do you have approved photos, client logos, testimonials and figures we can publish? | U37, U38 |
| 10 | For small businesses, is there a defined simplified offer to present? And which assistance… | U42, U43 |
| 11 | Which journeys should be in English first, and who will translate? | U44, U46 |
| 12 | Who should receive each type of enquiry (Business Travel, MICE, Congresses), and in which … | U50(partly), U52 |
| 13 | How long may we keep enquiry data, and who handles personal-data requests at ASSET? | U60 |
| 14 | Could you share 10 sample rows from your list of events (the 300 in the brief), with where… | U66, U67 |
| 15 | Who at ASSET approves a congress for sale? Is it one person or several? | U73 |
| 16 | Once a congress is approved for sale, what can we show publicly about Air France-KLM fares… | U74 |
| 17 | When a congress is over, should its page stay online as an archive, or come down? | U75 |
| 18 | Should one quote request cover several travellers leaving from different cities (for examp… | U77 |
| 19 | Is Wondermiles replacing Connexion Traveldoo, and is a single Client login link enough at … | U81, U82, U84(partly) |
| 20 | For the AI option, what should it do first? Find new congresses for your team to review, o… | U90 |
| 21 | Does your team sign in with Microsoft 365 or Google Workspace? We'd use it for a secure tw… | U64 |
| 22 | Must the site and its data stay in the EU or in France, for example because of your client… | U94, U95(partly) |
| 23 | Who besides Ms Khatri will edit the site day to day? We need to know so we can plan the traini… | U63(partly) |
| 24 | What kind of changes do you expect each month (new pages, offers, congress updates)? | U102 |
| 25 | What support hours do you need (office hours, or also evenings and weekends in congress se… | U99, U100 |

**Gaps in the old list:** 18 Q-unknowns not asked at all (U02, U06, U17, U19, U26, U36, U39, U45, U51, U53, U68, U70, U71, U72, U78, U83, U85, U86) and 7 only partly asked (U03, U15, U35, U50, U63, U84, U95).

**Overlaps and problems found:**
- Old Q3 (approves each stage) and old Q15 (approves a congress for sale) both asked "who approves". Resolved: Q3 is the site's stages and content owners; Q19 is the congress workflow only.
- Old Q4 bundled two decisions (who runs the site; whose name the accounts are in). Split into Q4 and Q5 so the account-ownership answer can't be lost in the first.
- Old Q10 joined two unrelated decisions (SME offer; assistance services). Split into Q12 and Q13.
- Old Q13 asked retention, but the brief (p4) tells the supplier to *propose* retention for approval. Moved to D (U59); the remaining ask (who handles data requests) joined Q27.
- Old Q19's technical-contact remark was a parenthesis, not a question. Moved into Q24 as a real ask, so Q23 (what clients see) and Q24 (what Wondermiles permits) don't overlap.
- Old Q22 mentioned security questionnaires only as a reason. Now asked directly in Q27.

**Jev on the old list** (`typesafe/jev-1.13`, one `choice` over q1-q25 + none per item): bank 72 items → 35 none, 17 below 0.6; Q-unknowns 56 → 12 none, 16 below 0.6. Jev's "none" Q-unknowns (U02, U06, U19, U26, U45, U50, U51, U53, U63, U68, U83, U86) are all inside the judgement gap list above.

## Pass 3 — reconcile: the final 30 questions

Rules applied: every Q-unknown maps to exactly one question; no two questions resolve the same unknown; ≤30 questions (operator raised the cap from 25 to 30 mid-task; multi-part allowed when one topic); plain English; groups partition the project (decision → today's site → content → enquiries → congresses → partners/options → running it).

**1. Timing, budget and decisions**

1. When is the proposal due, and when do you plan to choose a supplier? Is there a date the new site has to be live by, or a busy period when it should not launch?  
   *Resolves:* U01, U02, U03 · *Default if unanswered:* we send the proposal within 24–48 working hours of receiving your answers, or by 10 November if no answers arrive by 6 November; work starts within 5 working days of the signed proposal; launch about 12 weeks after the start, moving day for day with any late input; no launch between 21 December and 1 January.

2. Is there a budget range or a cap for the core site and the Congress catalogue? A rough bracket is enough.  
   *Resolves:* U04 · *Default if unanswered:* we quote the core site and the Congress catalogue as set out in our proposal, which lists the pages, listings, rounds of changes and exclusions. Every option is priced separately, so you can pick.

3. Who at ASSET approves each stage (design, content, launch), and does each activity (Business Travel, MICE, Congresses) sign off its own pages? How many working days should we plan for each approval?  
   *Resolves:* U05, U06 · *Default if unanswered:* ASSET management approves each stage in writing (directly, or through Ms Khatri on its behalf) within 3 working days, in one combined reply for all three activities. To keep the dates on track, if neither an approval nor a written list of blocking problems arrives in that time, a design or content stage counts as approved so work can continue. Launch always needs management's written go-ahead (section 07). Acceptance testing before launch lasts 5 working days, against the tests in your brief (T01–T15) only.

**2. Today's website and accounts**

4. Who looks after the current site today (an agency, a freelancer, your team), and is there a contract or notice period with them?  
   *Resolves:* U15 · *Default if unanswered:* nothing in a current contract limits the project, and ASSET arranges any handover from today's provider.

5. Are the domain, hosting, email, Google Analytics, Search Console and Google Business Profile accounts in ASSET's name? Who at ASSET should own the accounts of the new site?  
   *Resolves:* U16, U17 · *Default if unanswered:* ASSET gives us access at kickoff. Every new account is opened in ASSET's name, owned by management, with Ms Khatri as day-to-day administrator. If an account is held by someone else, ASSET asks them to transfer it; we can tell you exactly what to ask for.

6. Should the new site be on asset-voyagesdaffaires.com, assetvoyages.com, or both? Are there other web addresses or campaign pages we should know about?  
   *Resolves:* U18, U19 · *Default if unanswered:* the new site lives on asset-voyagesdaffaires.com, the address Google knows today, and assetvoyages.com points to it (web address only; your email is not touched). No other addresses are included.

7. Could you give us read-only access to Google Analytics and Search Console? Which trackers (LinkedIn, Meta) and ad campaigns (Google Ads, LinkedIn Ads) must keep working?  
   *Resolves:* U24, U25, U26 · *Default if unanswered:* we plan the move of old pages from our own scan of the site. No trackers are carried over. Visitor statistics need no cookies, and the site itself counts the actions your brief lists (button clicks, form starts and sends, errors, congress searches, congress page views, account requests and client-login clicks) without cookies or personal data. Ad campaigns are not included.

8. Does Selectour ask for anything on your website (logos, legal mentions, brand rules)?  
   *Resolves:* U33 · *Default if unanswered:* we show the Selectour Affaires logo and membership line as they appear on today's site, and nothing more.

**3. Content, brand and languages**

9. Will your team write the new French copy, or do you want us to rewrite the existing pages? Roughly how many pages, articles and FAQ entries do you expect at launch?  
   *Resolves:* U34, U35 · *Default if unanswered:* ASSET writes the French text for new pages. We move up to 20 of today's pages plus 3 legal pages, editing wording only (titles, headings, clarity and typos), with your corrections made within the two rounds of changes of the content stage (section 07); other pages are merged or redirected. ASSET supplies or approves the wording of the legal pages; we do not give legal advice. Ms Khatri adds further articles and FAQ herself.

10. Do you have brand guidelines (logo files, colours, fonts)? Is the logo fixed, or is a light refresh welcome?  
   *Resolves:* U36 · *Default if unanswered:* we keep today's logo and colours exactly as they are and build a short style guide from them.

11. Do you have approved photos, client logos, testimonials and figures we can publish? Which team members may appear by name and photo?  
   *Resolves:* U37, U38, U39 · *Default if unanswered:* we publish only what is on today's site and what you confirm in writing: no client logos, testimonials or new figures, illustrations instead of photos, and no named team members.

12. For small businesses, is there a defined simplified offer (service level, fees) to present, or is the page there to collect account and demo requests?  
   *Resolves:* U42 · *Default if unanswered:* the small-business page explains the service and collects account and demo requests, with no prices or service levels.

13. Which assistance services exist today (for example an emergency line), with their hours and phone numbers, so we only publish what is real?  
   *Resolves:* U43 · *Default if unanswered:* we show the 24/7 assistance wording as it appears on today's site, and publish a phone number only once you confirm it in writing.

14. Which journeys should be in English first, from when (launch or later), and who will translate?  
   *Resolves:* U44, U45, U46 · *Default if unanswered:* the site is in French only at launch. English is a separate option, and ASSET arranges and pays for professional translation.

**4. Enquiries and sales tools**

15. Who should receive each type of enquiry (Business Travel, MICE, Congresses), with a backup person, and how quickly can you promise a reply?  
   *Resolves:* U50, U51 · *Default if unanswered:* every enquiry goes to one shared mailbox (direction@assetvoyages.com until you name another), and the confirmation email says you will reply shortly, with no time promised.

16. Which sales tools do you use today: a CRM, a newsletter or email-marketing tool, or email only?  
   *Resolves:* U52, U53 · *Default if unanswered:* you use no CRM or newsletter tool. Enquiries are followed in the site's own enquiry list with an export that opens in Excel, and forms carry no marketing tick box.

**5. Congress catalogue**

17. Could you share 10 sample rows from your list of events (the 300 in the brief), with where the listings come from and roughly how many you add each year?  
   *Resolves:* U66, U67, U68 · *Default if unanswered:* ASSET provides one spreadsheet of up to 300 congresses in our template, using the fields listed in your brief. We import it once and send back a list of any rows with errors for ASSET to correct. Finding, researching or rewriting listings is not included. Ms Khatri adds new ones in the admin afterwards, one by one or by spreadsheet import.

18. Does ASSET already work with Air France-KLM's Global Meetings and Events programme? How do the event codes work: one per congress or several, and do they expire?  
   *Resolves:* U70, U71 · *Default if unanswered:* no fare code and no special-fare wording appears anywhere until ASSET confirms the arrangement in writing. The locked admin holds the code, its evidence and its validity period for each congress, as your brief lists.

19. Who at ASSET does each step from spotting a congress to approving it for sale? Who gives the final approval: one person or several?  
   *Resolves:* U72, U73 · *Default if unanswered:* Ms Khatri moves each congress through the steps and ASSET management gives the final approval for sale.

20. Once a congress is approved for sale, what can we show publicly about Air France-KLM fares? A preferential fares badge, or only request a quote?  
   *Resolves:* U74 · *Default if unanswered:* only “request a quote”: no fare badge, no discount and no partner claim.

21. When a congress is over, should its page stay online as an archive, or come down?  
   *Resolves:* U75 · *Default if unanswered:* the page stays online as a past edition, without the quote button, and Ms Khatri can add a link to the next edition once it is listed.

22. What should one congress quote request cover: several travellers leaving from different cities (for example, a lab sending doctors from Lyon and Paris), and hotel or transfers as well as flights?  
   *Resolves:* U77, U78 · *Default if unanswered:* one request covers one group, with one departure city or airport of the traveller's choice and a number of travellers, for flights only. Extra departure cities, hotel or transfer needs go in a free-text « Précisions » box.

**6. Partners and options**

23. Is Wondermiles replacing Connexion Traveldoo, and is a single Client login link enough at launch? Should the client area also link to your other client tools (IRES, the Smart app)?  
   *Resolves:* U81, U82, U83 · *Default if unanswered:* one “Client login” button to today's Traveldoo address, which Ms Khatri can change in the admin. No single login, and no other tools linked.

24. Who is your contact at Wondermiles? What may we show about Wondermiles on the Digital solutions page (logo, screenshots, product text), and does your agreement with them let a supplier like us read their technical documentation?  
   *Resolves:* U84, U85, U86 · *Default if unanswered:* Wondermiles is named in text only, with no logo or screenshots, until Wondermiles approves them in writing. No technical link-up is assumed.

25. For the AI option, what should it do first? Find new congresses for your team to review, or something else?  
   *Resolves:* U90 · *Default if unanswered:* the AI option is priced as a helper that finds new congresses on official websites for your team to check. Nothing is published without a person approving it.

**7. Security, data and running the site**

26. Does your team sign in with Microsoft 365 or Google Workspace? We'd use it for a secure two-step login to the admin area.  
   *Resolves:* U64 · *Default if unanswered:* staff sign in with a one-time code sent to their named work email, then confirm with a second step: an authenticator app on their phone or a security key. If you use Microsoft 365 or Google Workspace, staff sign in with that account instead, with its own two-step check switched on.

27. Must the site and its data stay in the EU or in France, do your clients send security questionnaires, and who at ASSET handles personal-data questions?  
   *Resolves:* U60, U94, U95 · *Default if unanswered:* the database is stored in the EU. Some providers (such as Cloudflare and Resend) are US companies, used under data-processing agreements as EU rules require; the full list of providers comes with the proposal. No security questionnaire is included (one can be answered later, quoted separately), and ASSET management handles personal-data requests using the written procedure we provide.

28. Who besides Ms Khatri will use the admin: a backup editor, other contributors, sales staff who only read enquiries? We need to know to set access and plan training.  
   *Resolves:* U63 · *Default if unanswered:* two people edit the site, Ms Khatri and one backup editor, both trained. Management can read enquiries and give the final approval for congresses, but not edit pages. Only Ms Khatri and management can see the GM&E fare codes and their evidence; the backup editor cannot.

29. What kind of changes do you expect each month (new pages, offers, articles, congress updates)?  
   *Resolves:* U102 · *Default if unanswered:* up to 5 hours of changes a month are included in the optional maintenance plan priced in the proposal; unused hours do not carry over, and anything more is quoted first.

30. What support hours do you need from us for the website (office hours, or also evenings and weekends in congress season), and how long an interruption can your business accept?  
   *Resolves:* U99, U100 · *Default if unanswered:* with the optional maintenance plan, support Monday to Friday, 9:00–18:00 Paris time, with no evening or weekend cover, and we aim to have the site back within 8 business hours after a serious incident on our side; outages at the hosting providers are outside this target. After the 4-week settling-in period (J6), support comes from the plan or is quoted per request.

**Changes from 25 to 30:** added Q4/Q5 split, Q10 brand guidelines (brief p9 names it; old list only had Selectour's rules), Q13 split from SME offer, Q16 sales tools (CRM moved out of routing; newsletter added: it decides the marketing tick box), Q18 GM&E arrangement and code structure (brief p6: partners must confirm GM&E; code structure shapes the private data model), Q24 Wondermiles permissions and contact (brief p3: "approved Wondermiles presentation, authorised images"). Widened without new overlap: Q1 (+selection date, blackout period), Q3 (+content owners), Q5 (+Google Business Profile, owner of new accounts), Q6 (+other addresses), Q7 (+ad campaigns), Q9 (+articles, FAQ), Q11 (+team members), Q14 (+timing), Q15 (+backup, reply time), Q17 (+yearly volume), Q19 (+each workflow step), Q22 (+hotel/transfers), Q23 (+other client tools), Q27 (+questionnaires, data contact), Q28 (+all admin roles). Removed as a question: retention (now D).

## Jev cross-check (deterministic)

| Run | Calls | Cost (USD) | Bank: none / <0.6 | Q-unknowns: none / <0.6 |
|---|---|---|---|---|
| Old 25, `choice` | 128 | ≈0.0069 | 35 / 17 | 12 / 16 |
| Final 30, `choice` (2 runs, last shown) | 128 | ≈0.0090 + 0.0091 | 25 / 16 | 4 / 12 |
| Final 30, `noul` matrix (each Q-unknown × each question) | 1680 | 0.0244 | — | assigned question scored < 0.5: 2 (U74 0.48, U95 0.46) |
| Calibration probes | 2 | < 0.0001 | — | positive 0.71, negative 0.06 |

Total Jev spend ≈ $0.05, zero errors.

**Final-list `choice` run, judgement review of every disagreement:**
- U66 (Existing list of 300, real columns (sample)): Jev `none` (0.41). Judgement: covered by Q17, whose text names it directly. Jev wrong (it scores low on the congress group generally).
- U67 (Source of listings and any licence limits): Jev `none` (0.45). Judgement: covered by Q17, whose text names it directly. Jev wrong (it scores low on the congress group generally).
- U72 (Who performs each workflow step): Jev `none` (0.29). Judgement: covered by Q19, whose text names it directly. Jev wrong (it scores low on the congress group generally).
- U77 (Quote covers multiple departure cities): Jev `none` (0.66). Judgement: covered by Q22, whose text names it directly. Jev wrong (it scores low on the congress group generally).
- The other 52 of 56 Q-unknowns: Jev picked the assigned question.
- Bank items: 25 "none" answers. Every one was reviewed: they are either A/D/K items by design (payment split, VAT, current-site backups, statuses, form field details, anti-spam, taxonomy, alerts, SSO protocols, account-automation data, AI sources/caps/reviewer, backup targets, keyword data, training format, plan type) or Jev misses on items the final list covers by name (D7→Q22, E1→Q17, E8→Q22 hotels (other airlines: D, U106), G1→Q25, I4→Q5, H5→Q7 trackers, consent tool A). A5 (how many suppliers were invited) is deliberately not asked: it changes nothing in our price or scope; its selection-date half is in Q1. D8 (retention) is D; its data-contact half is Q27. E9 and G2 were mapped by Jev to Q27 (hosting); judgement: both are D (alerts not in core; AI reads official sites only).
- The `noul` matrix is noisy for overlap (many unrelated pairs score 0.5-0.8; e.g. U95 security questionnaires scored 0.89 against Q4), so it is used only as a coverage signal, not an overlap test. Overlap was decided by judgement from the one-to-one Q-unknown → question table above: each Q-unknown is assigned once, each question resolves at least one Q-unknown, and no unknown appears under two questions.

## Final statement of coverage

- 56 Q-unknowns → 30 questions, one-to-one (each unknown in exactly one question; every question resolves 1-3 unknowns). Zero uncovered by judgement; Jev agrees on 52 of 56 and its 4 misses were checked and rejected.
- 16 A-unknowns are found by us in J1 (crawl, DNS, page source, Search Console once Q7 grants access, Lighthouse, L3a study).
- 34 D-unknowns carry a stated default (26 original + 7 added in audit round 1: U107-U113 + 1 added in audit round 2: U114); 8 K-unknowns are already settled by the brief or the live site (U61 and U103 also carry a default).
- Round 1 added no question: each new topic was folded into an existing default or a section of the page, so the list stays at 30 and MECE.
- Every one of the 30 questions also carries a written default, shown on the page, so a late, vague or missing answer still leaves a defined scope.
- Every row of the brief's "Decisions to confirm before contract" table maps to at least one question or a stated default.

## Defaults register (as published under each question)

| # | If we don't hear back, we'll assume |
|---|---|
| 1 | we send the proposal within 24–48 working hours of receiving your answers, or by 10 November if no answers arrive by 6 November; work starts within 5 working days of the signed proposal; launch about 12 weeks after the start, moving day for day with any late input; no launch between 21 December and 1 January. |
| 2 | we quote the core site and the Congress catalogue as set out in our proposal, which lists the pages, listings, rounds of changes and exclusions. Every option is priced separately, so you can pick. |
| 3 | ASSET management approves each stage in writing (directly, or through Ms Khatri on its behalf) within 3 working days, in one combined reply for all three activities. To keep the dates on track, if neither an approval nor a written list of blocking problems arrives in that time, a design or content stage counts as approved so work can continue. Launch always needs management's written go-ahead (section 07). Acceptance testing before launch lasts 5 working days, against the tests in your brief (T01–T15) only. |
| 4 | nothing in a current contract limits the project, and ASSET arranges any handover from today's provider. |
| 5 | ASSET gives us access at kickoff. Every new account is opened in ASSET's name, owned by management, with Ms Khatri as day-to-day administrator. If an account is held by someone else, ASSET asks them to transfer it; we can tell you exactly what to ask for. |
| 6 | the new site lives on asset-voyagesdaffaires.com, the address Google knows today, and assetvoyages.com points to it (web address only; your email is not touched). No other addresses are included. |
| 7 | we plan the move of old pages from our own scan of the site. No trackers are carried over. Visitor statistics need no cookies, and the site itself counts the actions your brief lists (button clicks, form starts and sends, errors, congress searches, congress page views, account requests and client-login clicks) without cookies or personal data. Ad campaigns are not included. |
| 8 | we show the Selectour Affaires logo and membership line as they appear on today's site, and nothing more. |
| 9 | ASSET writes the French text for new pages. We move up to 20 of today's pages plus 3 legal pages, editing wording only (titles, headings, clarity and typos), with your corrections made within the two rounds of changes of the content stage (section 07); other pages are merged or redirected. ASSET supplies or approves the wording of the legal pages; we do not give legal advice. Ms Khatri adds further articles and FAQ herself. |
| 10 | we keep today's logo and colours exactly as they are and build a short style guide from them. |
| 11 | we publish only what is on today's site and what you confirm in writing: no client logos, testimonials or new figures, illustrations instead of photos, and no named team members. |
| 12 | the small-business page explains the service and collects account and demo requests, with no prices or service levels. |
| 13 | we show the 24/7 assistance wording as it appears on today's site, and publish a phone number only once you confirm it in writing. |
| 14 | the site is in French only at launch. English is a separate option, and ASSET arranges and pays for professional translation. |
| 15 | every enquiry goes to one shared mailbox (direction@assetvoyages.com until you name another), and the confirmation email says you will reply shortly, with no time promised. |
| 16 | you use no CRM or newsletter tool. Enquiries are followed in the site's own enquiry list with an export that opens in Excel, and forms carry no marketing tick box. |
| 17 | ASSET provides one spreadsheet of up to 300 congresses in our template, using the fields listed in your brief. We import it once and send back a list of any rows with errors for ASSET to correct. Finding, researching or rewriting listings is not included. Ms Khatri adds new ones in the admin afterwards, one by one or by spreadsheet import. |
| 18 | no fare code and no special-fare wording appears anywhere until ASSET confirms the arrangement in writing. The locked admin holds the code, its evidence and its validity period for each congress, as your brief lists. |
| 19 | Ms Khatri moves each congress through the steps and ASSET management gives the final approval for sale. |
| 20 | only “request a quote”: no fare badge, no discount and no partner claim. |
| 21 | the page stays online as a past edition, without the quote button, and Ms Khatri can add a link to the next edition once it is listed. |
| 22 | one request covers one group, with one departure city or airport of the traveller's choice and a number of travellers, for flights only. Extra departure cities, hotel or transfer needs go in a free-text « Précisions » box. |
| 23 | one “Client login” button to today's Traveldoo address, which Ms Khatri can change in the admin. No single login, and no other tools linked. |
| 24 | Wondermiles is named in text only, with no logo or screenshots, until Wondermiles approves them in writing. No technical link-up is assumed. |
| 25 | the AI option is priced as a helper that finds new congresses on official websites for your team to check. Nothing is published without a person approving it. |
| 26 | staff sign in with a one-time code sent to their named work email, then confirm with a second step: an authenticator app on their phone or a security key. If you use Microsoft 365 or Google Workspace, staff sign in with that account instead, with its own two-step check switched on. |
| 27 | the database is stored in the EU. Some providers (such as Cloudflare and Resend) are US companies, used under data-processing agreements as EU rules require; the full list of providers comes with the proposal. No security questionnaire is included (one can be answered later, quoted separately), and ASSET management handles personal-data requests using the written procedure we provide. |
| 28 | two people edit the site, Ms Khatri and one backup editor, both trained. Management can read enquiries and give the final approval for congresses, but not edit pages. Only Ms Khatri and management can see the GM&E fare codes and their evidence; the backup editor cannot. |
| 29 | up to 5 hours of changes a month are included in the optional maintenance plan priced in the proposal; unused hours do not carry over, and anything more is quoted first. |
| 30 | with the optional maintenance plan, support Monday to Friday, 9:00–18:00 Paris time, with no evening or weekend cover, and we aim to have the site back within 8 business hours after a serious incident on our side; outages at the hosting providers are outside this target. After the 4-week settling-in period (J6), support comes from the plan or is quoted per request. |

## Audit round 1 changes (28 Oct)

Applied from `08_Audit_Round1_11_Lenses.md` and `09_Audit_Round1_Project_Experts.md` (log: `10_Round1_Fix_Log.md`). Defaults changed: Q1, Q2, Q3, Q6, Q7, Q9, Q13, Q16, Q17, Q18, Q21, Q22, Q26, Q27, Q28, Q29, Q30 (question text now "from us for the website"). Answer-first questions: Q1, Q2, Q3, Q5, Q6, Q9, Q15, Q18. New D rows U107-U113; updated U09, U11, U12, U13, U54, U61, U64, U65, U96, U101, U103, U105.

## Audit round 2 changes (28 Oct)

Applied from `11_Audit_Round2_11_Lenses.md` and `12_Audit_Round2_Project_Experts.md` (log: `13_Round2_Fix_Log.md`). Still 30 questions; no new question. Defaults changed: Q1 (signed proposal; access due at kickoff), Q3 (deemed approval for design and content stages only; launch needs management's written go-ahead), Q5 (account transfer wording), Q9 (ASSET writes new-page text; corrections within the content stage's two rounds), Q22 (departure city or airport; « Précisions » box), Q26 (genuine two-step login), Q30 (with the optional maintenance plan; after J6, plan or quoted). New default U114 (consent banner, T09). Rows updated: U09, U12, U64, U101, U107, U110, U111, U112, U113. `01b_20_Questions_source.md` renamed `01b_Questions_source.md`.

## Round 3 fixes (28 Oct 2026)

Applied from `14_Audit_Round3_11_Lenses.md` (fixes 1–3) and `15_Audit_Round3_Project_Experts.md` (fixes 1–4). Still 30 questions. Defaults changed: Q7 (full brief p4 event list), Q17 (new congresses one by one or by spreadsheet import), Q28 (only Ms Khatri and management see GM&E fare codes and evidence; the backup editor cannot); consent-banner default made conditional on a kept tracker (U114). Fixes 4–5 of `14_` carried to `16_Proposal_Carryover.md`.
