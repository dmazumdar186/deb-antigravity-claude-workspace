# B. GreenJobs redesign and commercial proposal: factual record (Sept to Nov 2026)

Written 2026-11-20. Internal, read-only reconstruction. Every line cites file:line or a commit. UNCERTAIN = not settled by any written source.

Path shorthand: `RD/` = `deliverables/greenjobs_redesign_2026-09-22/`, `MG/` = `deliverables/greenjobs_migration_2026-11-06/`, `PS/` = `execution/gtm_client_workflows/proposal_system/proposals/`.

**Source caveats**
- The clone is shallow (`git rev-parse --is-shallow-repository` = true); the oldest commit is b233006 (2026-11-16). No September or October commit hashes can be recovered, so dates before 16 Nov rest on file contents.
- `RD/research/brief.md` does not exist. The brief used by the build is `RD/src/data/brief.md`.
- Keith's change document (`Greenjobs_update.docx`) is not in the repo. Its content survives as the checklist (`RD/KEITH_CHANGES_CHECKLIST.md`) and the 114-row matrix (`RD/research/qa_2026-09-28/requirements_matrix_v2.md`).
- **A later proposal version exists that the brief did not list:** `PS/greenjobs-official.official.json` (created_date 2026-10-05, line 28). It is the source of the €1,500 / €600 figures (section 4).

---

## 1. Timeline

| Date | Event | Source |
|---|---|---|
| Before 22 Sep (UNCERTAIN date) | Deb proposed €1,875 for a redesign. Keith replied that he is considering moving the boards off the current vendor (Strategies), that they need an upgrade, and that he is "not yet convinced" €1,875 is value for money. | `RD/research/panel_pass.md:5`; `directives/gtm_client_workflows/greenjobs_redesign.md:6` |
| 22 Sep | Demo of both editions built and audited; live at greenjobs-redesign.pages.dev | `HANDOFF.md:197-199`; directive:181 |
| 24 Sep | "Third pass, client feedback": warm-earth palette, new fonts, landscape hero. The feedback itself is not quoted anywhere (UNCERTAIN what Keith said). | directive:190 |
| 28 Sep, 11:31 | Keith on LinkedIn: "overall feedback is very positive… Can you give me a costing for this and what you can offer?" | `RD/proposal/keith_costing_brief_2026-09-28.md:2` |
| 28 Sep | Keith's change document received. It was split into 114 requests, each verified on the build. | checklist:1; costing brief:94 |
| 28 Sep | Changes applied; panel pass (11 lenses); deployed to greenjobs-redesign.pages.dev | checklist:57-60 |
| 28 Sep (evening) | Internal count: 100 done, 11 need Keith (7 information, 4 decisions). Paste-ready line for LinkedIn drafted. Whether it was sent is UNCERTAIN. | costing brief:94-114 |
| 29 Sep, 12:39 | Keith's email (paraphrased in the brief, not verbatim): "very little work… hosting + integrations, guarantee what Strategies do". The brief reads his ask as: like-for-like Strategies hosting SLA, Broadbean/Idibu/LogicMelon kept, a Gaia posting integration, staff posting the ads, and the approved redesign. | costing brief:116-118 |
| 29 Sep, 17:21 | Keith forwards four site-manager questions: do stats update automatically; do candidates keep CV registration and log-in; compare Premium only (no Standard); can employers paste the full JD. Fixes 3 and 4 made the same day. Draft answer to Q2: "Candidates register once, store their CV, and apply with one click… part of the platform build." | costing brief:154-169; checklist:37,39 |
| 30 Sep | Proposal v1.0: €4,998 build + €999/month (section 2). Whether and how it was sent is UNCERTAIN; the proposal-tracker README names it `greenjobs-keith-v1`. | `RD/proposal/GreenJobs_Proposal_v1.0_2026-09-30.md`; `PS/greenjobs-keith-v1.json:5-6`; `execution/gtm_client_workflows/proposal_system/README.md:23` |
| 5 Oct | "Official" proposal: €1,500 at signing, migration €0 in exchange for publicity, €600/month locked for 6 months, offer held until Fri 10 Oct. Sent: UNCERTAIN (no send record found). | `PS/greenjobs-official.official.json:27-28,86-102` |
| Oct (exact date UNCERTAIN) | Deb asks what the blocker is. Keith: "it's the initial investment of 1500. It may be Q1 next year before the budget is there". Deb offers €600/month starting now, then €1,500 in Q1, written into the contract. | `MG/keith_linkedin_thread_2026-11-06.txt:2-5` |
| 29 Oct | Keith: "I appreciate your offer and yes it should be doable. Let me talk with Strategies". | thread:6 |
| 6 Nov | Keith forwards Strategies' notice: 30-day notice, contract ends **Sun 6 Dec 2026**; data via "Download Reports". He asks "let me know what you need to ensure a smooth transition". | thread:9-13 |
| 6 Nov | Internal feasibility matrix: the LinkedIn deal "replaces the 30 Sep proposal… Nothing is signed yet." (It does not mention the 5 Oct version.) | `MG/FEASIBILITY_MATRIX.md:23-25` |
| 9 Nov | Transition plan (PDF) + email to Keith: switch Thu 3 Dec; 12 questions; €600/month paid upfront. The email does **not** mention the €1,500 Q1 term. | `MG/EMAIL_TO_KEITH.txt:7-11`; `MG/transition_plan.html:20-33`; `MG/REVIEW_2026-11-16_keith_answers.md:41` |
| 10 Nov | Draft letter of intent for the French préfecture, for Keith to sign: €1,500 for rebuild and migration, then €600/month for hosting and maintenance, "starting from the date of his authorisation"; "No work has been carried out or invoiced to date". It is unsigned and has placeholders, so Keith's signature is UNCERTAIN. | `deliverables/titre_sejour_entrepreneur_2026-11-10/lettre_intention_GreenJobs.md:10-24` |
| 10-11 Nov | Rashieda's answers (10 Nov) and Diana's answers (11 Nov), forwarded by Keith 16 Nov. 8 of 12 are firm. | REVIEW:5-7,14-29 |
| 19 Nov | Diana: export headers; DNS at Hosting Ireland / LetsHost / 123 Reg; "Gaia talent is posting jobs by themself - manually"; how to use a password manager. | `MG/replies_2026-11-20/SOURCE_diana_2026-11-19.txt:3-7`; `MG/rethink_2026-11-20/FACTS.md:16-17` |
| 20 Nov | Decision v1 (Cavuno hosted board) committed, then withdrawn by decision v2 (our own build). | commits 519fe91, eff768f; `MG/rethink_2026-11-20/DECISION.md:3` |

**Contract status on 20 Nov:** nothing signed; no contract, DPA or invoice sent (`MG/rethink_2026-11-20/FACTS.md:8`; REVIEW:87; DECISION.md:51).

---

## 2. The scope Keith was sold

### 2a. Proposal v1.0, 30 Sep 2026 (`RD/proposal/GreenJobs_Proposal_v1.0_2026-09-30.md`)

**Commercial lines**
1. Front-end rebuild, both editions: **€1,999** (:117).
2. Platform migration: **€2,999** (:118). Total €4,998; 50% deposit €2,499 at signing, balance €2,499 on go-live; balance due "only upon full satisfaction" (:113,119-121).
3. Maintain plan: **€999/month**, starting when the front end goes live. Three-month minimum, then rolling; 30 days' notice; "No lock-in" (:123-128).
4. Tools billed at cost +3%: Cloudflare Workers Paid $5/month; Resend Pro $20/month. All subscriptions in GreenJobs' name (:142-151).

**Front end (MVP, week 1)**
5. Both editions as demonstrated: filters, list, map, saved views; a page per role with JobPosting data; 14-sector taxonomy; salary insights and salary guide; career quiz; employers page with Premium/Membership comparison and a post-a-job preview; four SEO landing pages; KPI dashboard (:60).
6. "All 100 completed items from your change document… the remaining 11 are applied the day you supply the input" (:60, :82). Two site-manager fixes are included (:82).
7. Sitemaps; redirects for current URLs (:82).
8. Live within 5 working days of signature, once DNS access and logo permissions are in hand: "If it is not live by then for reasons within my control, you do not pay for it" (:89). Indicative date Mon 13 Oct, if signed 6 Oct (:96-98).

**Platform (weeks 2-4, then a parallel run in weeks 5-6)**
9. Admin posting console for GreenJobs staff (:64, :83).
10. Candidate accounts with stored CV, one-click apply, saved roles and **email job alerts** (:64).
11. Newsletter send (:83).
12. **Broadbean, Idibu and LogicMelon posting kept and verified by a daily test job** (:64, :83). Broadbean onboarding runs on Broadbean's timeline (:103).
13. **A recruiter CRM posting integration** (:64, :83).
14. Full export of the current platform's data, plus import (:64, :83).
15. A 301 redirect for every indexed URL (:64, :83); analytics (:83).
16. Two-week parallel run. DNS moves only after every posting route passes **and Keith signs off in writing** (:84, :91).
17. Then 10 working days of daily checks (:91). Indicative go-live Wed 18 Nov (:101).
18. Handover: runbook, test register (3,047 checks), source repository; everything in GreenJobs-owned accounts (:85).
19. Every site figure is computed from the job data on every post, "whether GreenJobs staff or a client uploads the ad" (:72).

**Hosting guarantees and SLAs**
20. 99.9% uptime per month, measured by an independent monitor (:68, :134).
21. Daily backups at 100% success; a restore drill every quarter with a written result (:68, :135).
22. Firewall, DDoS protection, SSL, 24/7 monitoring, EU data region (:68).
23. Posting routes (Broadbean, Idibu, LogicMelon, CRM): a test job every day; 99% daily pass rate (:136). Failures "fixed before your team notices" (:127).
24. Response within 1 business day; 4 hours for a posting outage (:92, :137).
25. Every live role carries valid JobPosting data (:138). Core Web Vitals pass on both editions, checked monthly (:139).
26. Requested changes applied within 2 business days; urgent posting fixes the same day (:140).
27. Content, copy, sector and salary-band changes and small features applied on a rolling basis. First-line support for staff and advertisers on posting issues. Monthly report covering uptime, traffic, applications, posting routes and changes. KPI dashboard and every figure kept accurate (:127).
28. Weekly update throughout the build (:92).

**Explicitly out of scope** (:105, :153, :161)
29. Employer self-service purchasing and card payment ("GreenJobs staff post the ads"); the **other eight network sites**; career-advice articles and market reports; paid advertising; Broadbean/Idibu/LogicMelon/Strategies fees. The monthly plan covers greenjobs.ie and greenjobs.co.uk only; more sites are agreed in writing first.

Not in the 30 Sep proposal: **employer logins**. Payments are excluded (item 29).

### 2b. "Official" version, 5 Oct 2026 (`PS/greenjobs-official.official.json`)
30. Same feature scope, milestones, SLAs and out-of-scope list as v1.0 (:57-84). The Gaia logo is added (:17).
31. Price: **€1,500 at signing** for the front-end rebuild, live within 5 working days (:88-90).
32. **Platform migration €0**, "in exchange for a LinkedIn post about the build, a post on the Gaia Talent and GreenJobs pages at go-live, and a short written testimonial" (:91-93).
33. **Maintain €600/month, locked for 6 months** "from the day the front end goes live", then rolling with 30 days' notice. It covers hosting, backups, 24/7 monitoring, security, daily checks on Broadbean/Idibu/LogicMelon/CRM, Google for Jobs indexing, live figures, and content and change requests "as they come". Two boards only (:94-96, :102).
34. Year one €8,700, then €600/month (:97). Tools at cost +3% (:98-99). Offer held until Fri 10 Oct (:102).

### 2c. Transition plan, 9 Nov 2026 (`MG/transition_plan.html`, sent with `MG/EMAIL_TO_KEITH.txt`)
35. **3 Dec:** both boards on Keith's domains with current jobs; staff post, edit and close through an admin console; applications to the inbox he chooses; **job alert emails**; "the candidate records you choose to keep" (transition_plan.html:30).
36. **Second phase (target December to late January):** candidate log-ins; **employer log-ins for posting and editing their own jobs** (no online purchasing or card payment); feeds from Broadbean, Idibu or LogicMelon; posting from "the one CRM you confirm". Provider fees are Keith's, "not part of the monthly fee" (:31).
37. Trim order if inputs are late: alert emails and the candidate import move first (:33). The 10 working days of daily checks stay (:24).
38. Other domains on the Strategies contract: "I'll quote those separately so this plan and the monthly fee stay as they are" (question 1).
39. Retention suggestion: two years (question 5). Exports go to storage in GreenJobs' name (:33).

---

## 3. Keith's change-document items

The sources disagree on the count. The matrix has 114 rows (96 DONE, 7 PARTIAL, 1 NOT DONE, 7 NEEDS CLIENT INPUT, 3 INTERPRETED DIFFERENTLY: requirements_matrix_v2.md:5-12). The costing brief (:94) and the proposal (:60) say 100 done + 11 remaining = 111. **UNCERTAIN:** how the other 3 rows were counted.

**Done** (checklist [x]): A1-A4 hero and credibility; B1-B7 taxonomy, currency, location classes, hide-UK toggle, NI region; C1-C4 homepage order; D1-D4 filters, similar jobs, "Quick job match"; E1-E6 rates CTA, audience block, logo wall (112 logos), Premium/Membership table, network line, vacancy preview; F1-F3 copy and UK phone wording; G1-G2 JobPosting, hreflang, SEO pages; H1-H2 dashboard; I1-I3 gates (checklist:7-60). The site-manager fixes (Premium only; paste the full JD) are done (checklist:37,39; costing brief:158-159).

**Partial / open on our side**
- E7 UK credibility: testimonials and placements missing (checklist:40).
- G3 content hub: only the salary guide is shipped (checklist:50).
- G4 manual keyboard, reduced-motion and mobile runs not recorded (checklist:51).
- Matrix PARTIAL rows still open on 28 Sep: R010 sector mapping, R011 currency, R041 IE logo tiles, R043 thin products, R051 content, R058 mobile page weight, R072 NI renders as a hole on the map (matrix:22-31). **UNCERTAIN** whether these closed in the later round that reached "100 done".

**Waiting on Keith: information** (costing brief:96-103)
- Audience figure; newsletter reach; LinkedIn/network figures; 2-3 UK testimonials; logo permissions; GB phone number; UK placement examples.

**Waiting on Keith: decisions** (costing brief:105-109)
- "10 sectors" vs live 14; transport merged or split; Membership contents; content-hub topics.

**Waiting on GreenJobs from the launch checklist** (`RD/HANDOFF.md:76-83`)
- Email provider; rates-inbox owner; analytics; B Corp status and logo permission; DNS.
- Partly answered later: logos "OK, I suppose" (Diana, unconfirmed by Keith); GA4 IDs already held; DNS hosts named (REVIEW:26, FACTS.md:28-33).

No written evidence shows Keith ever answered the 11 items. Their status since 28 Sep is UNCERTAIN.

---

## 4. Commercial changes after 30 Sep

| Version | Build | Migration | Monthly | Source |
|---|---|---|---|---|
| Costing brief (internal, 28-29 Sep) | €2,750 | €6,500-7,500 | €350-950 tiers (€450 Care) | costing brief:24-45, 120-128 |
| Proposal v1.0, 30 Sep | €1,999 | €2,999 | €999 | proposal:117-127 |
| Official, 5 Oct | €1,500 at signing | €0 for publicity and a testimonial | €600, 6-month lock | official.json:88-97 |
| LinkedIn deal, Oct to 29 Oct | €1,500 deferred to Q1 2027 | (not stated) | €600 "starting now" | thread:3-6 |
| Letter of intent draft, 10 Nov | €1,500 "for the rebuild and migration" | (included) | €600 hosting and maintenance, from French authorisation | lettre:13,18 |

**What scope the €1,500 + €600 covers in writing**
- In the 5 Oct offer, €1,500 bought the front-end rebuild. The migration was €0 against publicity, and €600 bought the Maintain plan with its full SLA list (items 31-33).
- Keith's "initial investment of 1500" (thread:3) matches that figure. It is an inference, not a record, that he was quoting the 5 Oct proposal.
- The LinkedIn exchange names only the payment terms. It restates no scope, so it does not drop the publicity condition or the 6-month lock.
- The only later written scope sent to Keith is the 9 Nov transition plan (items 35-39). It splits delivery into 3 Dec and a second phase. Internally, phase 2 is "covered by the €600/month" (FEASIBILITY_MATRIX.md:66).
- **Unresolved:**
  - The 9 Nov email omits the €1,500 Q1 term (REVIEW:41).
  - The letter of intent says €600 starts at the French authorisation date and "no work has been carried out". The deal says "starting now" (thread:4), and the build pack has existed since 7 Nov (directive:167).
  - The contracting entity is open: GreenJobs Ltd vs Gaia Talent Ltd (REVIEW:27).
  - Whether the 6-month price lock and the publicity-for-migration swap survive into the contract is UNCERTAIN.

---

## 5. DECISION.md (v2, 20 Nov) against the record

**Drops or contradicts commitments without written client agreement**
1. **Candidate accounts.**
   - DECISION.md:22 says candidates "go to GreenJobs' own raw archive, never into the new site".
   - Earlier written commitments: candidate accounts with stored CV and one-click apply (proposal:64); "Yes, that stays" to the site manager (costing brief:157,166); "candidate records you choose to keep" on 3 Dec and candidate log-ins in phase 2 (transition_plan.html:30-31).
   - No written agreement from Keith to drop them was found.
2. **Job alerts as a delivered feature.**
   - DECISION mentions only importing consented subscribers who re-confirm (:22). It does not commit to sending alerts or the newsletter.
   - Earlier written commitments: alerts and newsletter (proposal:64,83); alert emails on 3 Dec (transition_plan.html:30).
   - The client side sells alerts and the newsletter to advertisers (REVIEW:34; FACTS.md:26).
3. **Broadbean / Idibu / LogicMelon and CRM posting routes.** Absent from DECISION. Sold with daily test jobs and a 99% pass SLA (proposal:64,136; official.json:95), and put in phase 2 on 9 Nov. Diana's statement that no live job comes through Broadbean (FACTS.md:17) supports dropping them, but Keith has not agreed in writing.
4. **"No paid third parties", "Cloudflare's free tier"** (DECISION.md:7). Both proposals list Cloudflare Workers Paid ($5) and Resend Pro ($20), billed at cost +3% (proposal:148-151; official.json:99). DECISION does not name an email sender, but the earlier plan used Resend (FACTS.md:47). The basis "Keith will not pay for a third-party service" is cited only as "the operator's ruling" (DECISION.md:3). No Keith quote was found.
5. **SLAs absent.** DECISION states no 99.9% uptime, daily backups with quarterly restore, 1-day / 4-hour response, 2-day change turnaround, Core Web Vitals or monthly report, all sold in proposal:131-140 and official.json:95. SYNTHESIS sets uptime green at ≥99.5%/week (`MG/rethink_2026-11-20/SYNTHESIS.md:89`), below the sold 99.9%/month.
6. **KPI dashboard and live site figures.** Sold (proposal:42,60,127), not mentioned in DECISION.
7. **Sign-off and parallel run.** Proposal: a two-week parallel run, then DNS moves after written sign-off (:84). DECISION: Keith signs off the test site by Fri 27 Nov (:34); there is no parallel run. The 9 Nov plan already dropped the parallel run, and Keith has not objected in writing.
8. **"The site we designed in September won the contract"** (DECISION.md:3). No signed contract exists (FACTS.md:8), and no Keith statement says this.

**Adds without written client agreement**
9. **The 8 sector network domains forward to `/sectors/<slug>/`** (DECISION.md:23). Both proposals list them as out of scope (proposal:105; official.json:84). The 9 Nov plan promised to quote them separately "so this plan and the monthly fee stay as they are". REVIEW:33 calls forwarding the minimum fix. No priced or agreed scope change is recorded.
10. **Gaia feed sync from gaiatalent.com every 10 minutes, with a review queue for Rashieda** (DECISION.md:20). This is new mechanics. The sold item was a "recruiter CRM posting integration" (proposal:64), and the plan said "posting from the one CRM you confirm" (transition_plan.html:31). Gaia's CRM is Vincere (FACTS.md:31).
11. **CHM Recruit and Mattinson self-posting through their own logins** (DECISION.md:21). Moved forward from phase 2 (transition_plan.html:31). Earlier plans had staff posting for them from 3 Dec (REVIEW:21).
12. **Data minimisation** (DECISION.md:22) is retention policy. Keith's written retention decision is still open (REVIEW:20; DECISION.md:43). The 9 Nov plan suggested two years.
13. **Client asks are "asynchronous, no calls"** (DECISION.md:36). This is our working rule, not a client term, and needs no agreement.

**Consistent with the record:** both boards on Keith's domains; staff console; per-job apply by email or link (REVIEW:23); about 1,200 old URLs 301-redirected (proposal:64); Keith's 27 Nov sign-off; a weekly email to Keith (proposal:92); the contract and DPA before any data download.
