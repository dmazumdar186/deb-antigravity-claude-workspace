# Audit round 1 of 3: project experts, hostile-client posture (2026-10-28)

**Scope.** The cover email (`01_Questions_for_Veena.md`) and its 4 links (`site/`: `/`, `/pour-asset/`, `/console/`, `/questions/`), checked against the RFP (`/tmp/rfp/brief.txt`), `07_Question_Coverage_Matrix.md`, and the prior audits 05 and 06. Items already fixed in 05 and 06 are not repeated here.

**Posture.** We assumed the most hostile client possible. Every default, number and demo screen was read as something ASSET could later quote back at us as a promise.

**Method.**
- The site was served locally (python http.server) and driven with Playwright at desktop 1440×900 and on an emulated iPhone 13.
- **/questions/**
  - All 30 questions render, numbered 1–30.
  - 30 of 30 carry "If we don't hear back, we'll assume".
  - All 9 contents links land on their section: header offset 88 px on desktop and 128 px on the phone. §9 sits at the end of the page, as expected.
  - Smooth scrolling to §9 takes about 2 s on the phone, because the page is 22,800 px.
  - There is no horizontal scroll.
- **Cross-links.** All 40 internal links across the 4 pages return 200, and every #anchor exists.
- **Film.** We scrolled it slowly (400 px and 350 px wheel steps) and fast (jumps to 5, 15, 30 and 50 % of the page). No overlaps, no blank stage.
- **Congress demo.** We searched "lyon" (1 result), opened the listing, then submitted the quote form empty. The form is pre-filled with the destination and dates (22/03 to 27/03/2027), and the required-field check blocks sending.
- **Console** on the phone: the label "Maquette" and the "Exemple" tags are visible, and the tab row is one line.
- **Errors.** Zero JS errors and zero console errors in both contexts.
- **axe-core** (WCAG 2.0/2.1/2.2 A+AA), run on 4 pages × 2 viewports: **0 violations**.
- **Screenshots** are in `/tmp/r1p5/` (55 PNGs). The panel looked at the key ones: the top of the questions page, §8 at screens 0, 6 and 13, the listing and quote form, the console, and the film mid-way.

## What holds
- Every question has a written default, the groups are clear, and the answer format is stated ("reply by email with the question numbers").
- The running-cost table is cited and dated, and the money is paid to the providers.
- The concept is labelled throughout: « Données d'exemple », « Exemple » on each listing, « Maquette » on the console, and « Concept non officiel » in the footer.
- The RFP's decisions table maps fully to questions: budget/schedule Q1–2, existing technology Q4–6, content Q9–14, enquiries Q15–16, partners Q18/23/24, operations Q27–30 plus the stated defaults.
- L3 is covered by Q23–24, L4 by Q25, and the CRM by Q16.
- The tests with a client input have one: T07 by Q21, T08 by Q23, T09 by Q7.

## Debate (short)
- **PM:** A hostile client wins on four gaps.
  - No answer deadline: the defaults never "kick in" on a date.
  - No acceptance or deemed-approval rule: ASSET can withhold the balance for ever.
  - "As your brief describes" (Q2): the brief is open-ended ("other pages where applicable").
  - "No loss of Google ranking" (§2): we restate an outcome as a guarantee.
- **Architect:** Three defaults don't match the stack we priced.
  - Cloudflare Web Analytics has no custom events, yet the RFP's conversion measurement (CTA clicks, form starts, errors, searches) is mandatory in L1.
  - Cloudflare Access has no built-in authenticator-app factor, yet Q26 promises one.
  - A 99.5 % monthly target allows about 3.6 h of downtime, while the RTO is 8 business hours. One incident breaks the "target", and nothing says it is non-contractual.
- **Full-stack:** Several defaults commit us to features no one asked for.
  - Q18: "several codes per congress, each with an end date".
  - Q22: several travellers from several departure cities, which the demo form (one departure, one traveller count) does not even show.
  - Q21: an automatic "next edition" link.
  - Each must be bounded, or reduced to what the RFP asks.
- **Product designer:** The pitch lists « Le film définitif » under "what doesn't exist yet", which implies it will be delivered. The demo's public catalogue shows congresses that the console marks Brouillon (CG-0109) and En attente (CG-0107, CG-0108), the opposite of T04. "EN bientôt" reads as a promise of English. There is no sentence saying the concept and console are illustrations and that the signed proposal is the only scope.
- **UX/UI:** The format is clear, but the page is about 35 phone screens, and §8 alone is 17. A manager will stall. Fixes:
  - Mark about 8 questions as "please answer first".
  - Give a one-tap "reply" mailto with 1–30 pre-numbered.
  - Give each question an anchor, so a follow-up email can point at #q18.

## Numbered fixes (file · problem · exact fix · severity)

### PM: scope and hostile-client exposure
1. **No answer deadline**
   - Files: `01_Questions_for_Veena.md`, `questions/index.html` §8 box and §9.
   - Problem: the defaults have no trigger date.
   - Fix:
     - Email, after "Could you reply…": "If possible by Friday 6 November; anything not answered by then follows the assumption shown under each question."
     - §8 box, first sentence: "Anything not answered in writing by Friday 6 November 2026 will follow…"
   - Severity: **Major.**
2. **No acceptance or deemed-approval rule**
   - File: `questions/index.html`, Q3 default.
   - Fix: append "If no written approval or list of blocking defects arrives within that time, the stage is treated as approved. Acceptance testing at J5 lasts 5 working days, against tests T01–T15 only."
   - Severity: **Major.**
3. **Q2 "as your brief describes them" is open-ended**
   - Fix: replace it with "as set out in our proposal, which lists the pages, listings, rounds of changes and exclusions; every option is priced separately, so you can pick."
   - Severity: **Major.**
4. **§2 "No loss of Google ranking" reads as a guarantee**
   - Fix: replace it with "**Keep the value Google already gives you.** Every page Google knows is mapped and redirected to its new address, and today's site stays live until the new one is approved. (No supplier can guarantee rankings.)"
   - Severity: **Major.**
5. **No scope-precedence clause**
   - File: `questions/index.html`, §1, last paragraph.
   - Fix: add "The concept, the console and the assumptions on this page are illustrations to help you answer. What is included is set only by the signed proposal."
   - Severity: **Major.**
6. **Q1 dates slip only for approvals**
   - Fix: replace "Later approvals move the dates…" (Q3) and extend Q1 with: "Work starts within 5 working days of the signed order. Any late input from ASSET (approvals, texts, photos, access, congress file) moves the dates by the same number of days."
   - Severity: **Major.**
7. **Page count conflict (29 vs 20)**
   - Problem: the pitch says today's offers are spread over « 29 pages internes », but the Q9 default migrates "up to 20 pages". "Edit them lightly" is undefined, and no rounds of revision are stated anywhere (the RFP asks for them).
   - Fix, Q9: "We move today's 29 pages into up to 20 new pages plus 3 legal pages; the rest are merged and redirected. Light editing means titles, headings and typos, with one round of changes per page."
   - Fix, under "Where we'll propose a sensible default", add: "Two rounds of design changes at J2; further rounds are quoted first."
   - Severity: **Major.**
8. **Q17: unclear who cleans the congress file**
   - Fix: append "ASSET supplies the file in our template; we import it once and return a list of rows with errors for ASSET to correct. We don't research or rewrite listings."
   - Severity: **Medium.**
9. **No default for the redirect scope** (T10, "priority URLs")
   - Fix, add to the defaults list: "Every address found in our crawl and in Search Console's last 12 months is redirected (301) to its closest new page; addresses outside those two sources are not included."
   - Severity: **Medium.**
10. **Q29 "monthly plan" is undefined**
    - Problem: it also clashes with §3 "Nothing is rented from us".
    - Fix:
      - Q29: "…up to 5 hours of changes a month are included in the optional maintenance plan priced in the proposal (unused hours do not carry over); anything more is quoted first."
      - §3: "Nothing is rented from us; maintenance is an optional monthly plan."
      - "move to another supplier at any time": append "once the delivered work is paid".
    - Severity: **Medium.**
11. **The settling-in period is not bounded**
    - Fix, defaults list: "A 4-week settling-in period after launch, covering defects against the accepted tests only; new requests are quoted."
    - Severity: **Medium.**
12. **No accessibility or performance default**
    - Fix, defaults list: "WCAG 2.2 AA as the design target on the critical journeys, with automated and manual tests and a written report; no third-party certification. Speed targets measured in lab tests per template until field data exists."
    - Severity: **Minor.**

### Architect: consistency with the running-cost table
13. **Conversion measurement has no home in the stack**
    - Fix, §4: add a row "Counts clicks, form starts and sends, errors and congress searches, with no cookies and no personal data · built into the site · included".
    - Fix, Q7 default: append "Enquiry and click counts are recorded by the site itself, without cookies."
    - Severity: **Major.**
14. **99.5 % target vs 8-hour restore**
    - Fix, §5: "We would target 99.5 % availability each month, measured… This is a target, not a contractual guarantee: outages of the hosting provider itself and announced maintenance are excluded, and any service-level commitment is set out in the maintenance contract."
    - Severity: **Major.**
15. **Q26 authenticator app vs Cloudflare Access**
    - Fix, §4 row: "Two-step login for staff… · Cloudflare Access with a code from an authenticator app (built into the admin) · €0".
    - Fix, Q26 default: keep it as is.
    - Severity: **Medium.**
16. **Backups row covers the database only**
    - Fix: append "photos and documents are copied daily too".
    - Fix, §5: change "any update can be undone instantly" to "any update to the site can be undone in minutes".
    - Severity: **Minor.**
17. **UptimeRobot €0**
    - Problem: the free plan's terms for commercial use need re-checking.
    - Fix: add it to the "re-checked before the proposal" sentence.
    - Severity: **Minor.**

### Full-stack: features committed by defaults
18. **Q18 commits to an unrequested feature**
    - Problem: "several codes per congress, each with an end date" is not in the RFP, which asks for one protected code plus a validity period.
    - Fix: "The locked admin holds the code, its evidence and its validity period for each congress, as your brief lists."
    - Severity: **Medium.**
19. **Q22 vs the demo form**
    - Fix: "One request covers one group with a departure city and a number of travellers; extra departure cities, hotel or transfer needs go in a free-text box."
    - Severity: **Medium.**
20. **Q21 implies an automatic "next edition" link**
    - Fix: "…and Veena can add a link to the next edition once it is listed."
    - Fix, Q16: change "spreadsheet export" to "a CSV export that opens in Excel".
    - Severity: **Minor.**

### Product designer: the concept as a future claim
21. **The final film reads as a promised deliverable**
    - File: `pour-asset/index.html`.
    - Problem: « Le film définitif » is listed among things to come.
    - Fix: « Le film. L'animation est un prototype de présentation ; sa reprise éventuelle est chiffrée à part dans la proposition. »
    - Severity: **Major.**
22. **Public catalogue shows draft and pending congresses**
    - Files: `index.html` catalogue and `console/index.html`.
    - Problem: drafts and pending congresses appear publicly, against T04 and C03.
    - Fix: in the console, set CG-0107, CG-0108 and CG-0109 to « Publié » (internal tracking unchanged), or remove those three rows from the public catalogue (12 → 9). The console keeps 1 draft that is not in the catalogue.
    - Severity: **Medium.**
23. **"EN bientôt" promises English**
    - File: `index.html`, language switch.
    - Fix: change « bientôt » to « en option » (aria and tooltip included).
    - Severity: **Medium.**

### UX/UI: answering 30 questions
24. **The page is too long to answer comfortably**
    - Problem: 35 phone screens, no priority and no pre-filled reply.
    - Fix, top of §8, add a button: `mailto:debanjan@prodcraft.fyi?subject=ASSET%20–%20réponses%20aux%2030%20questions&body=1%3A%0A2%3A%0A…30%3A`.
    - Fix: tag Q1, 2, 3, 5, 6, 9, 15 and 18 with « Answer first if you can » (a small badge).
    - Fix: add `id="q1"`…`id="q30"` on each `<li>`.
    - Severity: **Medium.**
25. **Phone sticky stack is tall**
    - Problem: the header plus the contents pills take 18 % of the screen (355 of 1,992 px).
    - Fix: below 600 px, make the contents row `position:static`, or hide it after scrolling past §1.
    - Severity: **Minor.**

## Verdict
**FIX.** There are no technical blockers: axe is clean, links work and the demo works. Items 1–7, 13, 14 and 21 close the openings a hostile client would use (about 1 h of text edits). Items 8–11, 15, 18, 19 and 22–24 should go in the same pass. Re-audit in round 2.
