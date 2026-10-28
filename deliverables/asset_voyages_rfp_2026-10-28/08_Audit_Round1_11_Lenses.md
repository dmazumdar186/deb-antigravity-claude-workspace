# Audit round 1 of 3: 11 lenses, hostile-client posture (2026-10-28)

**Scope.** The cover email `01_Questions_for_Veena.md` and the four pages under `site/`: `/`, `/pour-asset/`, `/console/` and `/questions/`.

**Checked against:**
- the RFP (`/tmp/rfp/brief.txt`, `/tmp/rfp/form.txt`)
- `07_Question_Coverage_Matrix.md`
- `HANDOFF.md`
- `research/infra_costs_2026.md`
- `research/effort_estimate.md`
- `research/live_metrics.json`

Anything already fixed in audits 05 and 06 is not repeated here. This is an audit only: no site file was edited.

**Posture.** ASSET is treated as the most hostile client possible. On that reading, every sentence is a future claim, every gap is a free extra, and every unbounded word is a liability.

## Fix list (referenced by the lenses)

| # | Sev | File / place | Problem | Replacement / fix |
|---|---|---|---|---|
| 1 | **Blocker** | `/questions/` §8 intro + email | There is no deadline for answers. A late answer can then be claimed to override a proposal that has already been sent. "Change any assumption… before the proposal is signed" lets ASSET change the scope at the same price, and proposals are not signed; contracts are. | "Answers received by **Friday 6 November 2026** are built into the proposal. Anything not answered by then follows the assumption under each question. You can change an assumption by email until the contract is signed; a change may alter the price and dates in the proposal. After signature, changes follow the change process." In the email: "…by email, **by Friday 6 November**?" |
| 2 | **Blocker** | Email, `/pour-asset/` « Ce que c'est », `/questions/` §1 | Nothing says that the concept and the console are not the scope. The film, the card stack, 5 roles, version history "en un clic", reminders and a "nous le cherchons pour vous" search could all be claimed as "shown, therefore included". `/pour-asset/` even says « Le film définitif… peut être repris ». | Add one line, in English in the email and on `/questions/`: "The concept and the console are illustrations, not a list of what is included; what is included is set only in the priced proposal." In French on `/pour-asset/`: « La maquette et la Console illustrent une direction ; seul le devis détaillé fixe ce qui est inclus. » |
| 3 | Major | `/` header `bientôt` + `js/main.js` toast "English version: coming soon" | The header and the toast imply that English is coming as part of the work. Q14's default says French only, with English as a priced option. | Header: `EN` + « option ». Toast: « Version anglaise : option chiffrée séparément ». |
| 4 | Major | `/questions/` Q1 default | "start on Monday 16 November, and launch in February 2027" is a fixed date commitment. The start cannot happen without an order (RFP p9: "does not constitute an order"), and the launch depends on ASSET's approvals, content and access. | "we send the proposal by Friday 13 November 2026. Work starts on the Monday after a signed order and access to today's site (16 November at the earliest), and launch is planned about 12 weeks after that start, plus any approval, content or access delays (see question 3). No launch between 21 December and 1 January." |
| 5 | Major | `/questions/` §4 + §3 "Low running cost. Roughly the price of a lunch each month" | §4, "what it costs you", reads as the total running cost. The maintenance fee (the form asks for "Hosting and maintenance per year") is never mentioned, so "you said €5–15 a month" becomes leverage. "A lunch" is a figure with no source and can be read two ways. | §3: "Low running cost. About €5–15 a month in provider fees (see section 4)." At the end of the §4 note, add: "Our own maintenance and support plan is separate and priced in the proposal." |
| 6 | Major | `/questions/` §3 "You receive the full source and can move to another supplier at any time." | "At any time" lets ASSET demand the source mid-project, before payment. | "At handover you receive the full source, and you can move to another supplier under the exit terms in the contract." |
| 7 | Major | `/questions/` §5 "Updates go live with no interruption to the site, and any update can be undone instantly." + "99.5%" | Both are absolutes. The source (§4) warns that database changes are the real risk and says not to promise atomic deploys. The 99.5% target has no exclusions, although the source's contract wording has them. This was accepted in round 2; under a hostile posture it is no longer acceptable. | "Updates are designed to go live without taking the site offline, and the previous version can be put back within minutes. We would target 99.5% availability each month, excluding announced maintenance and outages at the hosting providers, measured…" |
| 8 | Major | Q30 default + "Where we'll propose…" ("site back within 8 business hours") | "Serious incident" is undefined, and there is no carve-out for an outage at the hosting provider. The 18 Nov 2025 Cloudflare outage alone was about 2 h + recovery, and the target applies to any incident. | "…we aim to have the site back within 8 business hours after a serious incident on our side; outages at the hosting providers are outside this target." The same wording goes in the defaults list. |
| 9 | Major | Q27 default "data is stored in the EU" + §4 row | Only the D1 database is pinned to the EU. Computing runs anywhere, Cloudflare and Resend are US companies, and Resend's EU region is unconfirmed (source §2). Without a fix, ASSET can say "you promised EU-only data". | Q27: "the database is stored in the EU. Some providers (Cloudflare, Resend) are US companies covered by EU data-transfer contracts; the full list is in the proposal…" |
| 10 | Major | Q26 default "authenticator app" | The source says Cloudflare Access does MFA through Google/Microsoft or an emailed one-time PIN, and calls TOTP "confirm in prototype". The default promises something unverified. | "…staff confirm each login with a one-time code sent to their work email." |
| 11 | Major | Q7 default "No trackers… statistics that need no cookies" | The RFP p4 requires CTA, form-start, submit, error, search and listing events. Cloudflare Web Analytics is "not researched" and records page views only, so the default contradicts the RFP. | "…No trackers are carried over. Visitor statistics need no cookies, and the site records the events your brief lists (clicks, form starts and sends, searches) without personal data. Ad campaigns are not included." |
| 12 | Major | Q9 default vs `/pour-asset/` "29 pages internes" | We say we "move today's pages over… up to 20", but our own pitch counts 29. Which 9 are dropped? "29" also has no source in `research/` (live_metrics has 69 links only). "Lightly" is vague, and nothing says who writes the legal pages. | Pitch: « réparti sur de nombreuses pages internes ». Q9: "We move up to 20 of today's pages and edit their wording only (one round of your corrections); other pages are merged or redirected in the plan for old addresses. ASSET supplies or approves the legal pages' wording; we do not give legal advice." |
| 13 | Major | `/questions/` §7 J2/J3 + no question | **MECE gap:** revision rounds are not covered anywhere. The RFP p7 says the supplier "must specify… revisions". This is the classic unpaid-extras vector. | Add to §7: "Each design and content stage includes two rounds of changes; further rounds are quoted first." |
| 14 | Major | Q17 default | "we import one file of up to 300" does not say who builds or cleans the file. ASSET could send a PDF or links and demand data entry. | "…we import one spreadsheet of up to 300 congresses that ASSET provides in our template; finding or cleaning listings is not included." |
| 15 | Major | Q28 vs Q19/Q3 defaults | Q28 says "management can read enquiries but not edit pages", while Q19 says management gives the final approval for sale, which is the Approbateur role in the console. | Q28: "…Management can read enquiries and give final approval for congresses, but not edit pages." |
| 16 | Major | Q13 default "24/7 line… with the same number" | HANDOFF verifies only the « 24h/24, 7 jours/7 » wording. No such number is recorded. | "…we show the 24/7 assistance wording as on today's site, and publish a number only once you confirm it in writing." |
| 17 | Minor | Q3 default | It can be read two ways: is Veena's reply the management approval? The RFP requires approval from management. | "ASSET management approves each stage in writing (directly, or through Veena on its behalf) within 3 working days, in one combined reply for all three activities…" |
| 18 | Minor | Q29 default | "Included in the monthly plan" pre-commits hours in a plan with no price. Rollover is ambiguous. | "the monthly plan in the proposal includes up to 5 hours of changes; unused hours do not carry over; anything more is quoted first." |
| 19 | Minor | Q27 "at our hourly rate" | Implies a rate that has not been disclosed. | "…can be answered later, quoted separately". |
| 20 | Minor | §3 "What stays outside the website" | The list is partial. The RFP p2 also excludes paid CRM software, bulk scraping and automatic publication. | Add: "Also outside: paid CRM software, bulk scraping, automatic publication, photography, and copywriting beyond question 9. The full list comes with the proposal." |
| 21 | Minor | §7 J1 "a workshop with Veena"; defaults "Training… by video call" | Both are unbounded. | "one workshop with Veena (up to 2 hours, by video)"; "two recorded video sessions, in French". |
| 22 | Minor | Defaults list "Enquiry steps (new, qualified, quote sent, won or lost)" vs console (Nouvelle, En cours, Rappel aujourd'hui, Qualifiée) | The two lists are inconsistent. | Align the console sample statuses to Nouvelle / Qualifiée / Devis envoyé / Gagnée ou perdue (with "Rappel" as a reminder flag). |
| 23 | Minor | `/pour-asset/` « routées vers la bonne personne de votre équipe » vs Q15 (one shared mailbox) | The pitch and Q15 contradict each other. | « routées vers l'adresse que vous choisissez pour chaque activité ». |
| 24 | Minor | `/pour-asset/` table, Concept column « Toutes les offres et tous les formulaires… sans quitter la page » | "Toutes" is unbounded and reads as a build commitment. | Prefix with « Dans la maquette : ». |
| 25 | Minor | §5 "reported to you"; §4 "go back to any point" | Both are open-ended. | "in a monthly report"; "to any minute of the last 30 days (database)". |
| 26 | Minor | Q6 default | A redirect sounds like a DNS change that might touch email. | Add "(web address only; your email is not touched)". |
| 27 | Minor | Email "we've already started" | Implies that project work has begun before any order. | "we've already put together a first look." |
| 28 | Minor | Q30 vs Q13 | Non-technical readers may confuse ASSET's 24/7 line with our support hours. | Q30: "What support hours do you need **from us for the website**…" |
| 29 | Minor (internal) | §3 "Your current site runs on WordPress" | HANDOFF never records how this was verified. `HANDOFF.md` still says "There are still 25" questions. | Record the evidence (generator meta or wp-content) in HANDOFF; update the count to 30. |

## 1. Karpathy: measurement
- **Cost figures checked against `infra_costs_2026.md`: all consistent.**
  - Workers $5 ≈ €4.30. The typical total of €5–15 holds: 4.30 + 0–9 ≈ 4.3–13.3, rounded.
  - +€10 monitoring makes €25. UptimeRobot Solo is $12, about €10.3.
  - Domain €9–32 and translation €1,000–1,500 match.
- **One figure has no source:** « 29 pages internes » (#12).
- **"Price of a lunch"** is an unsourced comparison (#5).
- Honest gap: the Brevo paid price, the Access free limit and the Cloudflare Web Analytics capabilities are still unverified. The page flags the first two, but not the third, which drives #11.

## 2. Cherny: tooling craft
- The sample data is consistent between `/` and `/console/`: CG-0112 is 28–30 Jan 2027, CG-0108 is 24–28 Feb, CG-0103 is 23–26 Mar, CG-0109 is 13–14 Apr and CG-0107 is 8–11 May. The verification dates match (12/10/2026).
- The count of 30 is consistent across the email, the pitch and `/questions/`. A grep finds no stale "20" or "25".
- Defects found:
  - the EN toast text (#3)
  - the console status vocabulary does not match the defaults (#22)
  - HANDOFF is stale on the count (#29)

## 3. Dario Amodei: honesty and legal exposure
- **Absolutes still present:**
  - "no interruption", "undone instantly" (#7)
  - the "at any time" source handover (#6)
  - EU data (#9)
  - "8 business hours" with no carve-out (#8)
- An unverified capability is promised as a default: the authenticator app (#10).
- The legal-pages authorship is unassigned, which risks "you wrote our privacy policy" (#12).

## 4. Anthropic research: rigor (MECE)
- **Coverage.** The 07 matrix maps 56 Q-unknowns one to one onto 30 questions, and I found no unasked RFP decision except:
  - **Revision rounds:** the RFP p7 explicitly requires them (#13).
  - **Answer deadline / proposal-cutoff rule:** the email itself creates this unknown (#1).
  - **Who prepares the import file** (#14).
  - **Legal-page wording owner** (#12).
- **Overlaps.** None are material. Q13 and Q30 are a reader-confusion risk only (#28).
- **Default vs default:**
  - Q19 vs Q28 (#15)
  - Q15 vs the pitch (#23)
  - the enquiry steps vs the console (#22)
- **Default vs RFP:**
  - Q7 vs the RFP p4 conversion events (#11)
  - Q3 Veena vs management approval (#17)
- **Default vs the page itself:** Q9 "up to 20" vs the pitch's "29" (#12).

## 5. Hormozi: offer
- The value and risk reversal stay strong.
- Leverage risk: §4 can be read as the whole running cost (#5), which a hostile buyer will anchor on when the maintenance fee arrives.

## 6. Saraev: automation boundaries
- Human-in-the-loop holds for the AI, tickets and publication.
- The new boundary needed is that data entry for 300 congresses is not automation we owe (#14).

## 7. Daniela Amodei: trust
- The written-answers rule holds, but "a workshop with Veena" is unbounded (#21).
- "We've already started" invites "you began work, so…" (#27).

## 8. Sutskever: failure modes
- **The worst failure is quoting back the concept as scope (#2).** It is the single largest leverage point: the concept is rich, and nothing caps it.
- The next worst is a late answer overriding the proposal (#1).

## 9. Murati: phone and readability
- `/questions/` is plain English with no RPO, hreflang or canonical jargon, and CRM is defined.
- The 30 cards are long but numbered. Every default is in the same "If we don't hear back" pattern, which is good.
- The French on `/pour-asset/` and `/console/` reads naturally. I found no faults beyond the content issues listed above.
- The pitch subtitle « film… piloté par le défilement » is slightly technical but acceptable.

## 10. Brockman: reliability
- The 99.5% target, external 5-minute probe and outage citations are sourced.
- The missing exclusions (#7, #8) and the MFA mechanism (#10) are the gaps.
- Still uncosted, accepted earlier: the break-glass admin path and the off-platform backup copy.

## 11. Hassabis: system
- **The funnel works:** concept → why → console → questions → proposal.
- **The missing control loop is time:** answer cutoff → proposal date → start date → launch. As written, each link is a fixed date, not a dependency (#1, #4).

## Honest gaps of this audit
- No live re-fetch of asset-voyagesdaffaires.com. The "29 pages", the WordPress claim and the existence of a 24/7 number are judged from the repo records only.
- No phone screenshots were taken this round. Readability was judged from the extracted text.
- No legal review of the Selectour and ASSET logo reuse, or of the RFP-confidentiality vs unlisted-URL question (carried over).
- The Cloudflare Web Analytics custom-event limitation comes from product knowledge, not from a fetched source. Verify it before you rely on it in the proposal.

## Verdict: FIX
There are 2 blockers (#1, #2) and 14 majors, all text edits of about 1–2 hours. There are no structural or design changes. Re-audit in round 2.
