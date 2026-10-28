# Audit round 2 of 3: project experts, hostile-client posture (2026-10-28)

**Panel:** Senior UX/UI Designer, Full-Stack Developer, Solution Architect, Product Manager, Product Designer.
**Posture:** the same as in `09_…`. We assume a hostile client. Everything must be written down, bounded and unambiguous. Only the signed proposal defines scope. Answers are due Fri 6 Nov 2026. There are at most 30 questions, each with a default. No ProdCraft fees appear, no client names, and the language is plain.
**Scope:** the cover email (`01_…`), the four pages in `site/`, the RFP (`/tmp/rfp/brief.txt`) and the fix log (`10_…`).

## Method

We served `site/` locally (python http.server, port 8812) and drove it with Playwright at 1440×900 and on an emulated iPhone 13. The script is `/tmp/r2p5/run.js` plus `anch.js`. The 79 screenshots and `results.json` are in `/tmp/r2p5/`. We read the key screenshots ourselves: the top of the questions page, the start of §8, Q1, Q18 reached by anchor, the console on the phone, the quote form, the film (slow and fast) and the desktop TOC.

| Check | Result |
|---|---|
| Questions | 30 of 30 present, with `id` q1–q30. All 30 carry "If we don't hear back". **8 "Answer first" badges:** Q1, 2, 3, 5, 6, 9, 15, 18. These match the email. |
| Reply mailto | 2 buttons, in §8 and §9. **Address:** `debanjan@prodcraft.fyi`. **Subject:** « ASSET – réponses aux questions ». **Body:** `1. ` … `30. ` on 30 lines. The URL is 356 characters (safe). The signature mailto is also correct. |
| #q1–#q30 on a fresh load | All 30 land at 96 px on desktop and 84 px on the phone, under a 64 px header, once the smooth scroll ends (~1–2.5 s). The heading is visible in every case. A hashchange to #q18 lands at 96/84. |
| TOC #s1–#s9 | All land below the header: 145 px on desktop, 125 px on the phone. §9 sits at the end of the page on desktop (299 px), as expected. |
| Cross-links | 40 internal links return 200, and every #anchor exists. |
| Film | Slow scroll in 400/350 px steps and fast jumps to 5, 15 and 30 %: no overlap, no blank stage. One frame catches card 07 as it leaves, with the top half of the stage empty. That is a transition, not a defect. |
| Congress demo | 6 listings shown. "lyon" gives 1. "zzzz" gives 0, with the message « Aucun congrès ne correspond » and a CTA. Cardiologie gives 2. Période 1 gives 3. The quote form is pre-filled (event, Lyon, 22/03–27/03/2027). Submitting it empty blocks on: départ, nom, e-mail. |
| Console on the phone | « Maquette » banner present, tiles visible, tab row on one line. |
| Errors | 0 JS errors and 0 console errors in both contexts. |
| axe-core | WCAG 2.0/2.1/2.2 A+AA on 4 pages × 2 viewports: **0 violations**. |
| Overflow | No horizontal scroll on any page in either context. |

## Part 1: round-1 fixes

**08 (11 lenses), items 1–29:** all **PASS**.

Spot evidence:
- Deadline in the email, the §8 box and §9.
- Scope rule in the email, §1, the console banner, the pitch and the home footer.
- Toast « Version anglaise : option chiffrée séparément ».
- Q1 start rule; Q26 email code; §4 "Built into the site" row.
- Q9: 20 pages plus 3 legal pages.
- §07: two rounds.
- Q17 template; Q28 management; Q29 optional plan.
- Console: Nouvelle / Qualifiée + rappel / Devis envoyé / Gagnée.
- Pitch: « routées vers l'adresse que vous choisissez pour chaque activité ».
- HANDOFF line 269 records the WordPress 6.9.11 evidence.

**09 (project experts), items 1–25:** **PASS on 24.**
- **#15** is accepted as superseded: the email one-time code is the documented Cloudflare Access factor.
- **#7** passes, but it created a new conflict (see fix 1).
- **#22:** CG-0107, CG-0108 and CG-0109 are « Publié ». CG-0113 is a draft and does not appear in `index.html` or `main.js`.
- **#23:** the label reads « OPTION ».
- **#24:** the mailto, the badges and the anchors work.
- **#25:** the TOC is static below 600 px.

**Verification verdict: PASS.**

## Part 2: fresh audit

### Is it answerable in 20 minutes or less?
- §8 is 2,436 words, about 11 minutes of reading. On the phone the page is 26,274 px (about 40 screens). Q1 starts on screen 20 and Q30 is on screen 35.
- The eight "Answer first" questions plus the defaults make a 20-minute pass realistic, but only if Veena knows she can simply accept a default. Today she has to retype or remember what each number means, because the mailto body is bare numbers on a phone where she cannot see the questions while typing.
- Adding a short label per line and an "OK = assumption accepted" convention is the biggest single gain (fix 6).

### Did the round-1 caveats make it cold or legalistic?
Mostly no: the caveats are short and stated once. Three lines read curt in a first letter to a prospect:
- Q3: "counts as approved".
- Q5: "Getting back accounts held by others is up to ASSET".
- §8 box: "After signature, changes follow the change process".

Each keeps its protection but gains a reason (fix 8).

### Defaults that are unbounded or go beyond the RFP
None is open-ended any more. Two contradictions remain (fixes 1 and 4), and one sentence in the pitch implies the full console will be built (fix 3).

### Defaults that contradict the console or the demo
- Q22 against the quote form.
- Q28 against the console's 5 roles and the pitch.
- Q26 against the console role card.

### MECE check against the RFP
- **Work packages L0–L4:** all covered.
- **Milestones J0–J6:** all in §07.
- **Decisions table:** fully mapped.
- **Tests T01–T15:** one gap. T09 (refusing non-essential trackers works and the choice can be changed) has no default for the consent banner if ASSET keeps trackers under Q7 (fix 5).
- **Documents to submit:** the RFP asks for the "total core cost over three years", and §9 does not mention it (fix 7).

**Process note, no fix needed:** the RFP says any clarification that changes the scope is shared with all invited suppliers. Our questions and defaults may reach competitors. The pages are already unlisted. Accept this risk.

## Numbered new fixes (file · problem · exact fix · severity)

1. **Rounds of changes conflict**
   - Files: `site/questions/index.html` Q9, `01b_…`, `07_…`.
   - Problem: Q9 gives "one round of your corrections per page", but §07 gives "two rounds of changes per design and content stage". A hostile client will pick two.
   - Fix, Q9: replace "with one round of your corrections per page" with "with corrections within the two rounds of changes of the content stage (section 7)".
   - Severity: **Major.**
2. **Phone reader starts 19 screens above Q1**
   - Files: `01_Questions_for_Veena.md` link 4, and `site/questions/index.html` hero.
   - Fix:
     - Email, after the link 4 URL, add "(the questions start here: https://asset-voyages-redesign.pages.dev/questions/#s8)".
     - Hero, under the lead paragraph, add the link `<a href="#s8">Go straight to the 30 questions ↓</a>`.
   - Severity: **Medium.**
3. **The pitch implies the full console will be built**
   - File: `site/pour-asset/index.html`.
   - Problem: « gestion des pages, rôles, import de tableur, versions et journal d'accès restent à construire » reads as a commitment to the 5 console roles. Q28 assumes 2 editors plus a management read access.
   - Fix: append « , dans le périmètre fixé par la proposition signée (rôles : voir la question 28) ».
   - Fix, `console/index.html` Rôles intro: add « Exemple de répartition ; les rôles retenus sont fixés à la question 28. »
   - Severity: **Medium.**
4. **Q22 default against the demo quote form**
   - Files: `site/index.html` quote dialog, after Classe.
   - Problem: Q22 says extra departure cities, hotel or transfers "go in a free-text box", but the form has no such box.
   - Fix: add `<div class="field"><label for="d-notes">Précisions (autres villes de départ, hôtel, transferts)</label><textarea id="d-notes" name="notes" rows="2"></textarea></div>`.
   - Also change the « Voyageurs » default from 1 to empty, with min 1. Optional.
   - Severity: **Medium.**
5. **T09 gap: no default for the consent banner**
   - Files: questions defaults list, `01b_…`, `07_…`.
   - Fix: add "Cookie banner: a simple built-in consent banner. If any tracker is kept (question 7), it loads only after consent, and visitors can change their choice from the footer. A paid consent tool is not included."
   - Severity: **Medium.**
6. **The mailto body has bare numbers**
   - Files: both `.q-reply` links.
   - Problem: on a phone Veena cannot see the questions while typing her reply.
   - Fix, body lines: `1. Dates: ` / `2. Budget: ` / `3. Approvals: ` / `4. Current provider: ` / `5. Accounts: ` / `6. Domain: ` / `7. Analytics, trackers: ` / `8. Selectour: ` / `9. Texts, pages: ` / `10. Brand: ` / `11. Photos, logos: ` / `12. Small-business offer: ` / `13. Assistance: ` / `14. English: ` / `15. Enquiry recipients: ` / `16. CRM: ` / `17. Congress file: ` / `18. GM&E codes: ` / `19. Congress approval: ` / `20. Fare wording: ` / `21. Past congresses: ` / `22. Quote request: ` / `23. Client login: ` / `24. Wondermiles: ` / `25. AI option: ` / `26. Staff login: ` / `27. Data location: ` / `28. Admin users: ` / `29. Monthly changes: ` / `30. Support hours: `. The URL stays under 1,500 characters.
   - Fix, §8 intro: add "Write OK to accept the assumption as it is."
   - Severity: **Medium.**
7. **§9 omits the 3-year total the RFP asks for**
   - Fix: replace "optional extras and running costs" with "optional extras, running costs, and the total core cost over three years".
   - Severity: **Minor.**
8. **Three lines read cold**
   - Q3: "If neither… the stage counts as approved" becomes "To keep the dates on track, if neither… arrives in that time, the stage counts as approved."
   - Q5: "Getting back accounts held by others is up to ASSET" becomes "If an account is held by someone else, ASSET asks them to transfer it; we can tell you exactly what to ask for."
   - §8 box: "After signature, changes follow the change process" becomes "After signature, changes are agreed in writing with their effect on price and dates."
   - Severity: **Minor.**
9. **Q26 against the console's two-step login**
   - Problem: the console shows « Double authentification obligatoire » on the Administrateur card only, while Q26 covers all staff.
   - Fix: add the same chip to card 02 (Éditrice) and card 05 (Approbateur), or change the Rôles intro to « Connexion en deux étapes pour tous les comptes ».
   - Severity: **Minor.**
10. **Backups: "one day" against "any minute"**
    - Problem: the defaults list says "at most one day of data is lost", while §4 says the database restores to any minute.
    - Fix: "Daily backups kept 30 days: the database can be restored to any minute of the last 30 days; photos and documents to the previous day."
    - Severity: **Minor.**
11. **§5 monthly report has no owner**
    - Fix: "shared with you in a monthly report" becomes "shared with you in a monthly report under the optional maintenance plan".
    - Severity: **Minor.**
12. **Phone layout wastes width**
    - File: `css/questions.css`, @media (max-width:599px).
    - Problem: the number column takes about 32 % of the card width, which adds length to a 40-screen page.
    - Fix: below 600 px, use `.qs li{display:block}` with the number inline before the badge, or set the number column to 2.2em. Expected result: about 15–20 % shorter.
    - Severity: **Minor.**
13. **Anchor visibly scrolls on every #q link**
    - File: `js/questions.js`.
    - Problem: on a fresh load the page visibly smooth-scrolls from the top for 1–2.5 s.
    - Fix: before `fix()`, set `document.documentElement.style.scrollBehavior='auto'`, and restore it after.
    - Severity: **Minor.**

## Verdict
**FIX.** No technical blockers: axe is clean, there are no errors, every anchor and link works, and the mailto is correct. Fix 1 (the conflicting rounds) is the only Major item. Fixes 2–6 close the remaining contradictions with the demo and the console, the T09 gap, and the 20-minute usability target. That is about 45 minutes of edits. Fixes 7–13 should go in the same pass. Re-audit in round 3.
