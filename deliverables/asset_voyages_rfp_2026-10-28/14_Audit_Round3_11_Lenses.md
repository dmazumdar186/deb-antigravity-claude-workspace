# Audit round 3 (final): 11 lenses, 28 Oct 2026

Scope: verify round-2 fixes (`11_`, `12_`, log `13_`), then do a full end-to-end read as the last check before sending: the email `01_Questions_for_Veena.md` and the 4 pages in order. Posture: hostile client; only the signed proposal defines scope; answers by Fri 6 Nov 2026; 30 questions with defaults; no ProdCraft fees; no client names.

Method: page text extracted from local HTML (tags stripped). Live pages: sha1 of all 4 live URLs equals the local files (deployed = audited). The 30 defaults were compared by script against `01b_Questions_source.md` and `07_Question_Coverage_Matrix.md` (start and end of each default): 30/30 match in both. Mailto decoded (1,267 chars, 30 labelled lines). Brief re-read in full (`/tmp/rfp/brief.txt`, 9 pp.) and form. One phone screenshot read (`screens/r2-iph-q-s8.png`).

## Part A: round-2 fixes verified (34 of 34 PASS)

| Fix | Result | Evidence |
|---|---|---|
| 11 #1 two-step login | PASS | §04 row: "Two-step login for staff… work email account (Microsoft 365 or Google Workspace, with its own two-step check switched on), or a one-time code… plus an authenticator app or security key"; Q26 default matches; console note « Connexion en deux étapes pour tous les comptes ». Source in `research/infra_costs_2026.md` + HANDOFF l.281 |
| 11 #2 pitch order | PASS | Pitch steps: 1 answers → 2 proposal « envoyée séparément » → 3 « Après signature de la proposition, l’audit… (étape J1) » |
| 11 #3 maintenance conditional | PASS | Q30 "with the optional maintenance plan…"; defaults backups "With the maintenance plan, we aim…"; §05 "With the optional maintenance plan, you get this measure"; J6 "After these 4 weeks, support and fixes are covered by the optional maintenance plan or quoted per request" |
| 11 #4 §02 redirects | PASS | "addresses found in our scan and in Search Console are mapped and redirected to their closest new page" |
| 11 #5 deemed approval | PASS | Q3: design or content stage only; "Launch always needs management’s written go-ahead (section 07)" |
| 11 #6 French text | PASS | Q9 "ASSET writes the French text for new pages"; J3 "French texts for new pages" |
| 11 #7 one rounds rule | PASS | §07 "two per design stage and two per content stage (page wording included, see question 9)"; Q9 refers back |
| 11 #8 signed proposal | PASS | §01 "The proposal, once signed, is our contract."; email "set only by the signed proposal"; §03, §05, §08, Q1 |
| 11 #9 Q1 circularity | PASS | "Work starts within 5 working days of a signed proposal…; access to today’s site is due at kickoff" |
| 11 #10 Search Console | PASS | Defaults: "if you give access (question 7)" |
| 11 #11 date | PASS | §09 "(by Friday 6 November 2026)"; pitch « avant le vendredi 6 novembre 2026 » |
| 11 #12 cost split | PASS | §09 lists audit, core, Congress module, each option, running, maintenance, 3-year core total, excl./incl. VAT; pitch step 2 same |
| 11 #13 routing | PASS | Pitch « envoi à l’adresse choisie pour chaque activité » (agrees with Q15) |
| 11 #14 | PASS | §06 "Statistics without cookies." |
| 11 #15 | PASS | §03 "your site, code, data and accounts go with you, under the exit terms" |
| 11 #16 | PASS | Q22 "one departure city or airport of the traveller’s choice" |
| 11 #17 references | PASS | §09 "described without naming our clients; … only with that client’s permission" |
| 11 #18 §05 box | PASS | "What this means" list: target, report with plan, exclusions/firm terms, nobody promises 100% |
| 11 #19 | PASS | Pitch « Points relevés, à confirmer avec vous » |
| 11 #20 | PASS | §03 "If the audit changes the approach, the change is agreed in writing with its effect on price and dates." |
| 11 #21 rename | PASS | `01b_Questions_source.md` exists; no stale name in pages |
| 12 #1 | PASS | Q9 "within the two rounds of changes of the content stage (section 07)" |
| 12 #2 | PASS | Email "(the questions start here: …/questions/#s8)"; `id="s8"` present; hero "Go straight to the 30 questions ↓" |
| 12 #3 | PASS | Pitch « (rôles : voir la question 28) »; console « Exemple de répartition ; les rôles retenus sont fixés à la question 28. » |
| 12 #4 | PASS | Quote dialog « Précisions (autres villes de départ, hôtel, transferts) »; `main.js` toast « précisions notées » |
| 12 #5 | PASS | Defaults: "Cookie banner: a simple built-in consent banner…" |
| 12 #6 mailto | PASS | Subject « ASSET – réponses aux questions »; body "Write OK to accept our assumption, or your answer." + "1. Dates — … 30. Support hours — " (both buttons) |
| 12 #7 | PASS | = 11 #12 |
| 12 #8 | PASS | Q3 "To keep the dates on track…"; Q5 transfer sentence; §08 box "After signature, changes are agreed in writing…" |
| 12 #9 | PASS | « Double authentification obligatoire » on Administrateur, Éditrice, Approbateur cards + note for all accounts |
| 12 #10 | PASS | §04 row + defaults: database to any minute of last 30 days, photos/documents to previous day (D1 Time Travel 30 days, research l.12) |
| 12 #11 | PASS | = 11 #3 |
| 12 #12 phone list | PASS | `questions.css` l.95 `@media (max-width:599px){.qs li{display:block…}`; screenshot r2-iph-q-s8 readable, no overflow |
| 12 #13 jumps | PASS | `questions.js` hashchange handler; CSS `html:has(.qs li:target){scroll-behavior:auto}` |

## Part B: end-to-end read

**Email.** Does its job: four links, unlisted warning, scope sentence, deadline Fri 6 Nov (a Friday: 28 Oct 2026 is a Wednesday), reply method, 8 "Answer first" (counted: Q1, 2, 3, 5, 6, 9, 15, 18), default rule. No fees, no client names. Nothing usable against us.

**Concept (`/`).** Every quote marked as from today's site; sample data labelled « exemple » on every congress; footer « seule la proposition signée fixe ce qui est inclus »; 122-agences figure flagged « à revérifier ». One gap (cosmetic): the MICE form has no "indicative budget (optional)" field that brief F02 lists; covered by the illustration disclaimer.

**Pitch (`/pour-asset/`).** Steps in the right order; « dans le périmètre fixé par la proposition signée »; « Aucun prix… n’est inventé » is true. The MICE row of the table repeats the form fields without budget (same cosmetic gap).

**Console.** Banner and lead say it is a mock-up; roles tied to Q28; GM&E codes never public; 2FA wording agrees with §04/Q26. No contradiction.

**Questions.** Defaults identical across 3 files (script). Dates consistent: answers 6 Nov → proposal 13 Nov → start Mon 16 Nov at the earliest → no launch 21 Dec–1 Jan. Running-cost figures trace to `research/infra_costs_2026.md` ($5 × 0.86 = €4.30; Brevo 300/day; D1 EU jurisdiction; DPA; outage dates 12 Jun ~2h28, 18 Nov ~2h10, 5 Dec ~25 min: "outages lasting hours" is true for two of three).

**MECE sample: 33 cells from `03_Functional_Breakdown.md` traced.** A1→§02/pitch; A6→§07; A11→Q14; L0.3→J0+Q5; L0.8→J1; C-5→Q13; C-10→Q9 + cookie default; J-2→§02; D5→J2; F04→§04 email/spam rows; G1→defaults enquiry steps; H3→Q7 + pitch J1; I1→Q28/console; I6→console (proposal); C04→§03+Q18; M3→Q19/console; N1→Q17; N6→Q16; P9→§03 Directus; Q2→§04 test copy; Q12→§04 UptimeRobot; R1→Q23/Q24; V1→Q27 + form notices; V6→Q27; W4→§03 exit; S5→J6; U2→defaults speed; CA2→Q9/Q17; T07→Q21; J6→§07; K1→§09; launch blockers→Q3 (T01–T15); DC4→Q15. All 33 have a question, default or section. Two brief items are only partly carried (see fixes 1 and 4).

## Part C: regression check (round-2 edits)

No new contradiction found. Wording checked on every round-2 sentence: no broken grammar, no double punctuation (the pitch double colon was fixed in r2). Tone: firm and polite; no "we're done" claims. The mailto subject is French and the body English; acceptable since the brief and page are English.

## Part D: remaining fixes (none blocking)

| # | Sev | File / place | Problem | Exact fix |
|---|---|---|---|---|
| 1 | Minor | `site/questions/` Q7 default and §04 row "Counts clicks, form starts and sends, errors and congress searches"; mirror in `01b_` and `07_` (U-row + defaults register) | Q7 says "the actions your brief lists (clicks, form starts and sends, errors and congress searches)". The brief (p4) also lists listing views, account requests and client-area clicks. The parenthesis reads as a full list, so a hostile reader can say we left out three. | Q7: "(button clicks, form starts and sends, errors, congress searches, congress page views, account requests and client-login clicks)". §04 row: "Counts button clicks, form starts and sends, errors, congress searches and page views, and client-login clicks, with no cookies and no personal data". Re-sync 01b/07 and re-run functional tests. |
| 2 | Cosmetic (optional) | `site/index.html` MICE form; `site/pour-asset/` table, MICE row | No "indicative budget (optional)" field, which brief F02 lists. | Add field « Budget indicatif (facultatif) » after « Services souhaités »; pitch MICE cell « (type, destination, dates, participants, services, budget indicatif) ». |
| 3 | Cosmetic (optional) | `site/questions/` defaults, cookie banner line | With the Q7 default (no trackers), a consent banner is not strictly needed, yet the line states one unconditionally. | "Cookie banner: only if a tracker is kept (question 7): a simple built-in consent banner; the tracker loads only after consent, and visitors can change their choice from the footer. A paid consent tool is not included." |
| 4 | Internal (proposal) | Proposal, not the pages | Brief p7 asks for "response and resolution times". Q30 gives only a restore aim. | Put the support response time in the maintenance plan of the proposal. No page change. |
| 5 | Internal (proposal) | `03_` L0.8 vs page J1 | 03 says 2 workshops × 1.5 h; the page says one workshop up to 2 h. | Proposal JSON must say one workshop up to 2 h (the page is what ASSET will hold us to). |
| 6 | Note | §05 outage links | All three examples are Cloudflare, the provider we recommend. This is honest, but a hostile reader will notice. | No change. Be ready to answer on the kickoff call: Pages and static delivery were less affected than Access/KV; the backup path covers enquiries. |

## Part E: per-lens sign-off

1. **Karpathy (measurement): SIGN.** All costs and outage dates trace to research rows with URLs and a check date. 30/30 defaults were checked by script, not by eye. Gaps: Brevo paid price and UptimeRobot business use are still UNVERIFIED (the page says so); fix 1 lists measurement events.
2. **Cherny (craft): SIGN.** Deployed = local (sha1 on 4 pages). Defaults synced across 3 files. Gaps: the sync relies on `.tmp/asset_cov/gen_md.py`, which is not committed; fix 1 needs a re-sync.
3. **Dario Amodei (honesty/legal): SIGN.** No invented fact found. The 2FA claim is now true. Quotes are marked, sample data is labelled, no client names, no fees. Gap: none blocking.
4. **Anthropic research (rigor): SIGN.** Definitions are bounded: rounds, hours, 30-day restore, T01–T15, "on our side". Gap: no response time defined (fix 4).
5. **Hormozi (offer): SIGN.** The value is clear. The free-value leaks from round 2 are closed (maintenance, audit after signature). Gap: references without client names are weaker proof; the operator accepted this.
6. **Saraev (boundaries): SIGN.** Human approval holds for launch, congress sale, AI publishing and deemed approval (design/content only). Gap: none.
7. **Daniela Amodei (trust): SIGN.** The tone is respectful; "don't know yet" is welcome; the operator's name and address appear only as signature. Gap: the outage links could feel self-defeating (note 6).
8. **Sutskever (failure modes): SIGN.** Worst-case hostile readings checked: free audit, unlimited support, deemed launch, single airport, fake 2FA. All are closed. Gap: fix 1 (measurement list read as exhaustive).
9. **Murati (UX/phone): SIGN.** The phone layout of the questions page is readable (screenshot); 44 px reply button; instant #q jumps; numbered mailto. Gap: only one screenshot re-read in this round (r2 reviewed all 20).
10. **Brockman (execution): SIGN.** Live = local; noindex on headers, meta and robots; CSP strict. Gap: the 2026 Cloudflare incidents are unverified (not cited on the page).
11. **Hassabis (system): SIGN.** The time loop is consistent across email, pitch, §07, §09 and Q1. MECE: 33/33 sampled cells covered. Gaps: fixes 4–5 must be carried into the proposal.

## Verdict

**SEND.** No blocking or major issue. Fix 1 (minor, about 5 minutes plus re-sync) is recommended before sending. Fixes 2–3 are optional. Fixes 4–5 belong in the proposal.
