# Audit round 2 of 3: 11 lenses, hostile-client posture (2026-10-28)

**Scope.** The cover email `01_Questions_for_Veena.md` and the four pages under `site/` (`/`, `/pour-asset/`, `/console/`, `/questions/`), cross-checked against `01b_20_Questions_source.md`, `07_Question_Coverage_Matrix.md`, `HANDOFF.md`, `research/infra_costs_2026.md`, `/tmp/rfp/brief.txt` and `/tmp/rfp/form.txt`. Audit only: no site file was edited.

**Posture and rules (same as round 1).** ASSET is the most hostile client possible: it answers late, vaguely or not at all, disputes scope and exploits every ambiguity. Checked rules: no ProdCraft fees; no other client names; plain language; no invented facts; no more than 30 MECE questions, each with a bounded written default; answers by Fri 6 Nov 2026; only the signed proposal defines scope.

**Method.** Text was extracted from all four pages and the JS toast. The 30 defaults were compared programmatically across the page, `01b` and the `07` register. The calendar was checked (28 Oct 2026 is a Wednesday, 6 and 13 Nov are Fridays, 16 Nov is a Monday). Leaks were checked by grep (other client names, rates). Every page sentence was then read against the brief, page by page.

## Part A: round-1 fixes verified

**Result: 54 of 54 applied.** Fixes 08 #1–29 and 09 #1–14 and #16–25 pass. 09 #15 was superseded as logged. Two applied fixes create new problems: 09 #2 (deemed approval) gives new fix #5, and 08 #10 (email code) gives new fix #1.

| Fix | Result | Evidence |
|---|---|---|
| 08 #1 / 09 #1 deadline | PASS | Email "by Friday 6 November". §08 box. §09. Pitch « avant le vendredi 6 novembre 2026 ». (Softness of the wording: new #11.) |
| 08 #2 / 09 #5 scope rule | PASS | Email ¶3, `/questions/` §01 "What is included", pitch « Ce que c'est », console banner, home footer « seule la proposition signée fixe ce qui est inclus » |
| 08 #3 / 09 #23 EN | PASS | Header label `option`. `main.js:37` toast « Version anglaise : option chiffrée séparément ». |
| 08 #4 Q1 dates | PASS | "within 5 working days of a signed order and access… about 12 weeks… late input moves the dates". (Circularity: new #9.) |
| 08 #5 running cost | PASS | §03 "About €5–15 a month in provider fees". The §04 note ends "Our own maintenance and support plan is separate". |
| 08 #6 handover | PASS | §03 "once the delivered work is paid… under the exit terms in the contract" |
| 08 #7 / 09 #14 availability | PASS | §05 "designed to… within minutes… target, not a guarantee… exclusions… monthly report" |
| 08 #8 Q30 carve-out | PASS | Q30 and the defaults list both say "on our side; outages at the hosting providers are outside this target" |
| 08 #9 EU data | PASS | Q27 says "the database is stored in the EU… US companies… data-processing agreements" |
| 08 #10 MFA | PASS (text applied) | Q26 and the §04 row say "one-time code sent to their work email". (Not truly two-step: new #1.) |
| 08 #11 / 09 #13 events | PASS | Q7, plus the §04 row "Built into the site" |
| 08 #12 / 09 #7 pages | PASS | Pitch « de nombreuses pages internes ». Q9: 20 + 3 legal pages, wording only, no legal advice. |
| 08 #13 revision rounds | PASS | §07 "two rounds of changes". (Conflicts with Q9: new #7.) |
| 08 #14 / 09 #8 import | PASS | Q17: "in our template… import it once… error rows… not included" |
| 08 #15 Q28 | PASS | "read enquiries and give the final approval for congresses" |
| 08 #16 Q13 | PASS | "publish a phone number only once you confirm it in writing" |
| 08 #17 Q3 Veena | PASS | "(directly, or through Veena on its behalf)" |
| 08 #18 / 09 #10 Q29 | PASS | "optional maintenance plan… unused hours do not carry over" |
| 08 #19 Q27 rate | PASS | "quoted separately". A grep finds no rate anywhere. |
| 08 #20 exclusions | PASS | The "Also outside:" line is in §03 |
| 08 #21 workshop/training | PASS | J1 "up to 2 hours, by video". Training is "two recorded video sessions". |
| 08 #22 console statuses | PASS | Nouvelle / Devis envoyé / Qualifiée + « rappel aujourd'hui » / Gagnée |
| 08 #23 routing | PASS | Pitch table footnote « l'adresse que vous choisissez ». (One leftover line: new #13.) |
| 08 #24 « Dans la maquette » | PASS | Pitch comparison row |
| 08 #25 report / backups | PASS | §05 "monthly report". §04 "any minute of the last 30 days". |
| 08 #26 Q6 email | PASS | "(web address only; your email is not touched)" |
| 08 #27 "first look" | PASS | Email ¶1 |
| 08 #28 Q30 "from us" | PASS | Q30 wording |
| 08 #29 HANDOFF | PASS | v2.3 section: WordPress 6.9.11 generator, wp-content, count 30 |
| 09 #2 deemed approval | PASS (applied) | Q3. (Contradicts the RFP and §07: new #5.) |
| 09 #3 Q2 | PASS | "as set out in our proposal, which lists the pages…" |
| 09 #4 rankings | PASS | §02 "(No supplier can guarantee rankings.)" (The sentence before it is still unbounded: new #4.) |
| 09 #6 late input | PASS | Q1 last sentence |
| 09 #9 redirect scope | PASS | Defaults list "our scan + Search Console last 12 months". (Depends on Q7: new #10.) |
| 09 #11 J6 | PASS | J6 and the defaults list: 4 weeks, defects against the accepted tests only |
| 09 #12 WCAG / speed | PASS | Defaults list |
| 09 #15 authenticator | Superseded | As logged |
| 09 #16 media backups | PASS | §04 backups row |
| 09 #17 UptimeRobot | PASS | §04 note "whether UptimeRobot's free plan allows business use will be re-checked" |
| 09 #18–20 | PASS | Q18 validity period. Q22 one group. Q21 "Veena can add a link". Q16 "opens in Excel". |
| 09 #21 film | PASS | Pitch « sa reprise éventuelle est chiffrée à part » |
| 09 #22 catalogue/console | PASS | CG-0107/0108/0109 are « Publié ». CG-0113 is a draft and does not appear in the home list of 12. The tile reads « 1 congrès en brouillon, hors du site ». |
| 09 #24 mailto / badges / anchors | PASS | `mailto:` subject « ASSET – réponses aux questions », body 1.–30. Eight "Answer first" badges (Q1, 2, 3, 5, 6, 9, 15, 18). `questions.js` handles `#q\d{1,2}`. |
| 09 #25 contents row | PASS | `questions.css:89`: `@media (max-width:599px){.toc{position:static}}` |

**Cross-file consistency.** All 30 defaults are byte-identical (after quote normalisation) across `/questions/`, `01b` and the `07` register. The count of 30 is consistent everywhere. A grep across `site/` and the email finds no other client names and no ProdCraft fee or rate.

## Part B: new fix list

| # | Sev | File / place | Problem (hostile reading) | Exact fix |
|---|---|---|---|---|
| 1 | **Major** | `/questions/` Q26 default + §04 row "Two-step login for staff… so a stolen password alone can't open the admin" | This was introduced by round-1 fix 08 #10. With a Cloudflare Access one-time PIN there is no password: the emailed code *is* the login. That is one factor (access to the mailbox), not two. The RFP p4 requires "administrator MFA". As written, the claim "two-step" is untrue, and the default may fail the RFP. | §04 row: "Staff login: access only for named work email addresses, each login confirmed with a one-time code sent to that address; with Microsoft 365 or Google Workspace (question 26), their own two-step login is used." Q26 default: "staff log in with a one-time code sent to their named work email. For the technical administrator, a second step is added as required by your brief; the method is set out in the proposal." Internal: the proposal must show how admin MFA is met: either the IdP's MFA, or an app password plus the Access PIN. |
| 2 | **Major** | `/pour-asset/` « Prochaines étapes » | The order is answers → **audit of your current site (J1)** → proposal. This reads as a free audit before any order. It also contradicts `/questions/` §07, where J1 starts only after the signed order (Q1). | Reorder and reword: 1. « Vos réponses écrites… » 2. « Notre proposition détaillée… envoyée séparément. » 3. « Après signature : l'audit de votre site actuel (étape J1)… » |
| 3 | **Major** | Q30 default, defaults list (backups line), §05 "monthly report", §03 "maintenance is an optional monthly plan" | Maintenance is optional, but support hours, the 8-business-hour restore aim and the monthly availability report are stated as unconditional defaults. If ASSET declines the plan, it can still claim weekday support and an 8-hour restore for free and indefinitely. Nothing says what happens after J6. | Q30: "**With the optional maintenance plan:** support Monday to Friday, 9:00–18:00 Paris time…". Defaults list, backups line: "…With the maintenance plan, we aim to have the site back…". §05: "…shared with you in a monthly report **as part of the maintenance plan**." J6 (end): "After these 4 weeks, support and fixes are covered by the optional maintenance plan or quoted per request." |
| 4 | **Major** | `/questions/` §02 goal 3 "Every page Google knows is mapped and redirected to its new address" | This is unbounded and unknowable. It contradicts the defaults list (scan + Search Console only, nothing outside them) and Q9 ("merged or redirected"). | "Today's addresses found in our scan and in Search Console are mapped and redirected to their closest new page, and today's site stays live until the new one is approved. (No supplier can guarantee rankings.)" |
| 5 | **Major** | Q3 default "If neither an approval nor a written list of blocking problems arrives in that time, the stage counts as approved" | The RFP p2 says each milestone needs "written approval from ASSET". p8 says cutover needs written authorisation from management. Our own §06 and §07 also say "nothing goes live without written approval". A deemed approval contradicts all three, is unenforceable for launch, and will offend a procurement reader. | "…within 3 working days, in one combined reply for all three activities. Without a reply, design and content stages count as approved so work can continue; **launch always needs management's written go-ahead** (section 07). Acceptance testing…" |
| 6 | **Major** | Q9 default "ASSET writes **or approves** the French text"; J3 "French texts (written or approved)" | ASSET can pick "approves": you write, we approve. That turns every new page the brief lists (procurement, assistance, digital solutions, SME) into free copywriting. It contradicts §03 "copywriting beyond question 9" being excluded. | Q9: "ASSET writes the French text for new pages. We move up to 20 of today's pages plus 3 legal pages, editing wording only…". J3: "From you: French texts for new pages, and who receives each type of enquiry." |
| 7 | **Major** | Q9 "one round of your corrections per page" vs §07 "Each design and content stage includes two rounds of changes" | The two contradict each other on revision rounds, the classic route to unpaid extras. A hostile client takes the higher number. | §07: "Each design stage includes two rounds of changes, and page wording follows question 9; further rounds are quoted first." Mirror the change in matrix U107. |
| 8 | **Major** | Scope instrument: email/§01/footer "proposal you sign"; §08 "until the contract is signed"; Q1 "signed order"; §03 "exit terms in the contract"; §05 "maintenance contract" | There are three different documents. A hostile client argues that the contract omitted X but the proposal listed it, or the reverse. The operator rule is that only the signed proposal defines scope. | Add to §01 box: "The proposal, once signed, is our contract." Then use "signed proposal" in §08 ("until the proposal is signed"), Q1 ("a signed proposal"), §03 ("under the exit terms in the signed proposal") and §05 ("set out in the maintenance plan of the signed proposal"). Mirror in `01b` and `07`. |
| 9 | Minor | Q1 default "within 5 working days of a signed order **and access to today's site**" vs J0 and Q5 "access at kickoff" | The logic is circular: the start needs access, but access is given at the kickoff, which is the start. | "Work starts within 5 working days of a signed proposal (Monday 16 November at the earliest); access to today's site is due at kickoff." |
| 10 | Minor | Defaults list "redirected… Search Console's last 12 months" vs Q7 default "from our own scan of the site" | If Q7 is unanswered there is no Search Console access, so the redirect default cites data we won't have. | Defaults list: "…found in our scan of today's site and, if you give access (question 7), in Search Console's last 12 months…" |
| 11 | Minor | §09 "(ideally by Friday 6 November 2026)"; pitch « si possible avant le vendredi 6 novembre » | This softens the cutoff that §08 and the email make firm. A hostile client reads "ideally" as optional. | §09: "Once we have your answers (by Friday 6 November 2026)…". Pitch: « avant le vendredi 6 novembre 2026 ». |
| 12 | Minor | §09 "costs split the way you asked: core site, Congress module, optional extras and running costs" | The RFP p9 also asks for L0 separately, a three-year core total, and amounts with and without VAT. "The way you asked" overclaims. | "…with costs split as your brief asks: audit, core site, Congress module, each option, yearly running and maintenance costs, and the three-year total, excluding and including VAT." |
| 13 | Minor | `/pour-asset/` « Ce qui n'existe pas encore » « envoi à la bonne équipe » | A leftover of round-1 fix 08 #23. It contradicts Q15 (one shared mailbox). | « envoi à l'adresse choisie pour chaque activité » |
| 14 | Minor | `/questions/` §06 heading "Statistics without a cookie banner." | The text says "the banner shorter", but the heading promises no banner. | Heading: "Statistics without cookies." |
| 15 | Minor | §03 "If you change supplier, everything goes with you." | "Everything" is unbounded: our tooling, non-transferable licences. It undoes the bounded handover sentence above it. | "If you change supplier, your site, code, data and accounts go with you, under the exit terms." |
| 16 | Minor | Q22 default "one departure city" vs RFP F03 "Do not restrict the enquiry to a single airport" | A hostile client claims non-compliance with F03. | "…with one departure city or airport of the traveller's choice and a number of travellers…" |
| 17 | Minor | §09 "Verifiable references… come with the proposal" | References name other clients, which clashes with the operator's rule. Is it deliverable for business-travel, MICE or catalogue work? | "Examples of similar work (shared with those clients' permission) and the name of the project lead come with the proposal." Operator to confirm. |
| 18 | Minor (readability) | §05 single paragraph (5 sentences, 4 hedges) | It reads as a wall of caveats on a phone. | Split into 3 short lines: what we design for / the 99.5 % target and how it is measured / what is excluded and where firm terms live. |
| 19 | Minor (French tone) | Pitch « Faits et contradictions relevés » | "Contradictions" sounds accusatory to the client's management. | « Points relevés, à confirmer avec vous » |
| 20 | Minor | §03 "The audit… will confirm whether to keep or replace it, with the costs of each option" | If J1 recommends keeping WordPress, the client may demand a re-price of a signed custom build at no cost. | Add: "If the audit changes the approach, the change process applies." |
| 21 | Minor (internal) | Filename `01b_20_Questions_source.md` holds 30 questions | The filename is stale. | Rename to `01b_Questions_source.md`, or note it in HANDOFF. |

## Part C: lenses

1. **Karpathy (measurement).** Every €-figure ties to `infra_costs_2026.md` (Workers $5 ≈ €4.30, Brevo Starter €7–9, UptimeRobot Solo ≈ €10, D1 Time Travel 30 days). The calendar is correct. The "two-step" claim (#1) is the only factual claim that fails.
2. **Cherny (craft).** The 30 defaults are identical across 3 files (programmatic check). Leftovers from round-1 fixes: #13, #21.
3. **Dario Amodei (honesty and legal).** False MFA claim (#1). Free-audit and free-support implications (#2, #3). A deemed approval that conflicts with the client's written-approval rule (#5). Unbounded "every page" and "everything" (#4, #15).
4. **Anthropic research (MECE).** Her email's asks are all covered:
   - approach and CMS (§03)
   - costs split (§04, §09)
   - timeline (Q1)
   - team (J0, plus lead named in proposal)
   - examples (concept + proposal, #17)
   - maintenance, hosting, support and handover (§03, §04, Q29, Q30, J6)
   - assumptions and exclusions (§03)
   - French at launch, English separate (Q14)
   - Wondermiles and AI separate (§03 options, Q23–25)

   No uncovered client unknown. Contradictions: #6, #7, #8, #10.
5. **Hormozi (offer).** The value is clear. Leakage of free value is the risk (#2, #3, #6). Fixing these protects the price anchor.
6. **Saraev (boundaries).** The human-approval boundaries hold (AI, fares, publication). The copywriting boundary leaks (#6).
7. **Daniela Amodei (trust).** The deemed approval and « contradictions » wording risk offending management (#5, #19). Otherwise the tone is respectful.
8. **Sutskever (failure modes).** The worst plausible failure: ASSET declines maintenance, then cites Q30 and §05 during an outage (#3). The next worst: a dispute over which document governs (#8).
9. **Murati (phone and readability).** The §05 wall (#18). The §08 box is acceptable. The French on the pitch and console reads naturally. Only tone (#19) and the jargon « CSV » in the home catalogue note were flagged; leave that as is, since it is the brief's own term.
10. **Brockman (reliability).** The restore aim, report and support need an owner and a paid vehicle (#3). The break-glass admin path and the off-platform backup are still uncosted (carried over).
11. **Hassabis (system).** The time loop (answers → proposal → signature → start → audit → launch) is correct on `/questions/` but broken on the pitch (#2) and circular in Q1 (#9).

## Honest gaps
- No live re-fetch of the client site. No phone screenshots this round: readability was judged from extracted text (the token rule keeps images out of context).
- The Cloudflare Access free 50-user limit and Brevo's hosting location are still UNVERIFIED, as the page flags.
- Whether an Access PIN plus an IdP satisfies "administrator MFA" for ASSET is a judgement call. It needs an explicit line in the proposal.
- No legal review of the deemed-approval wording under French contract practice.

## Verdict: FIX
No blockers. 8 majors (#1–#8) and 13 minors, all text edits (about 1 h). Mirror every default change in `01b` and `07`. Re-audit in round 3.
