# Audit round 3 of 3 (final): project experts, hostile-client posture (2026-10-28)

**Panel:** Senior UX/UI Designer, Full-Stack Developer, Solution Architect, Product Manager, Product Designer.
**Posture:** as in `09_…` and `12_…`. We assume a hostile client. Only the signed proposal defines scope. Answers are due Fri 6 Nov 2026. There are at most 30 questions, each with a default. No fees, no client names, plain language.
**Scope:** the cover email (`01_…`), the four live pages, the RFP (`/tmp/rfp/brief.txt`), the round-2 audits (`11_…`, `12_…`) and the fix log (`13_…`).

## Method

- **Live, not local.** Chromium reached https://asset-voyages-redesign.pages.dev/ through the proxy, so every check ran on the live site.
- **Live matches local, byte for byte.** We downloaded the 4 pages and compared them with `site/`: all 4 HTML files are identical. So are the 9 CSS/JS assets (`styles`, `questions`, `doc`, `main`, `questions.js`, `console`, `film`, `hero`, `boot`). The downloads are in `/tmp/r3p5/diff/`.
- **Script:** Playwright `/tmp/r3p5/run.js`, which adapts round 2's script. It ran at 1440×900 and on an emulated iPhone 13, with `bypassCSP` set so axe could be injected. The live CSP `script-src 'self'` blocks inline injection otherwise; that is correct behaviour.
- **Outputs:** 81 screenshots and `results.json` in `/tmp/r3p5/`.
- **Screenshots we read ourselves:** the questions hero, the "Go straight" landing on the phone, Q18 reached by anchor on the phone, the quote dialog with « Précisions » on the phone, the toast on desktop, the top of the console on the phone, and two film frames.

| Check | Result |
|---|---|
| Live and local are the same | 4 of 4 pages and 9 of 9 assets identical (`cmp`). |
| Questions | 30 of 30 present, with ids q1–q30. All 30 carry "If we don't hear back". There are 8 "Answer first" badges (Q1, 2, 3, 5, 6, 9, 15, 18), matching the email's "eight". |
| Reply mailto (both buttons) | **Address:** `debanjan@prodcraft.fyi`. **Subject:** « ASSET – réponses aux questions ». **Body:** "Write OK to accept our assumption, or your answer.", a blank line, then 30 labelled lines from "1. Dates — " to "30. Support hours — ". The href is 1,267 characters. The labels match the question topics. |
| "Go straight to the 30 questions ↓" | §8 heading lands at 145 px on desktop and 125 px on the phone, below the 64 px header. |
| TOC #s1–#s9 | All land below the header. §9 sits at 214 px on desktop because it is at the end of the page. |
| #q1–#q30 on a fresh load | All 30 are in place within 500 ms in both contexts; none failed. A hashchange to #q18 lands at 96 px on desktop and 84 px on the phone. |
| Cross-links | 39 internal links, all return 200, and every #anchor exists. |
| Film | Slow wheel scroll and fast jumps to 5, 15 and 30 %: no blank stage. The split-flap board shows mid-flip letters in one frame, and one phone frame catches the stage between cards. Both are transitions, not defects. |
| Congress demo | All 6 listings show. "lyon" gives 1. "zzzz" gives 0, with « Aucun congrès ne correspond » and the « Demander une recherche » CTA. Cardiologie gives 2. Période 1 gives 3. The quote form is pre-filled with CG-0103, Lyon, 22/03 to 27/03/2027. Submitting it empty blocks on départ, nom and e-mail. **The « Précisions (autres villes de départ, hôtel, transferts) » field is present, labelled and full width on the phone.** Once filled, the toast ends « … · Économique · précisions notées. Rien n'a été envoyé … ». |
| Consent banner | The demo sets **0 cookies and 0 localStorage keys** (`ctx.cookies()`). No banner is needed, which matches §04 "statistics that use no cookies". The T09 default (a built-in banner if any tracker is kept under Q7) is in the defaults list. |
| Console on the phone | The « Maquette » chip and the illustration disclaimer are present. Tiles are readable, the tab row scrolls, and there is no overflow. |
| axe-core (WCAG 2.0/2.1/2.2 A+AA) | **0 violations** on 4 pages × 2 contexts. |
| JS and console errors | **0 page errors and 0 console errors.** The home page logs 2 browser *warnings*: `Inter.woff2` and `EBGaramond.woff2` are "preloaded but not used within a few seconds". That is cosmetic; see note N1. |
| Horizontal overflow | None on any page in either context. |

## Part 1: verification of the round-2 fixes

**`11_` (11 lenses), items 1–21: 21 PASS.**

- **#1:** Q26 and the §04 row offer a work email account with its own two-step check, or an email code plus an authenticator app or security key. The "second login step" source link is present.
- **#2 and #19:** pitch steps 1–3 read « Après signature… (J1) ». « Points relevés, à confirmer avec vous » is present.
- **#3:** Q30, the defaults list, §05 and J6 all say "optional maintenance plan".
- **#4:** §02 goal 3 has the scan plus Search Console mapping.
- **#5:** Q3 limits deemed approval to the design and content stages; launch needs management's written go-ahead.
- **#6:** Q9 and J3 say "French text for new pages".
- **#7:** §07 has one rule for rounds; there are 0 occurrences of "one round".
- **#8:** "The proposal, once signed, is our contract." appears in §01, and "signed proposal" in the email, §03, §05, §08 and Q1.
- **#9:** Q1 states access is due at kickoff.
- **#10:** the defaults list has Search Console "if you give access (question 7)".
- **#11:** §09 and the pitch carry the 6 Nov 2026 deadline.
- **#12:** §09 has the full cost split and the three-year total.
- **#13:** the pitch says « envoi à l'adresse choisie pour chaque activité ».
- **#14:** §06 says "Statistics without cookies.".
- **#15:** §03 says the site, code, data and accounts go with you under the exit terms.
- **#16:** Q22 says "one departure city or airport".
- **#17:** the references wording follows the operator; "verifiable" has been removed (0 hits).
- **#18:** §05 has the "What this means" box.
- **#20:** §03 says an audit change is agreed in writing.
- **#21:** `01b_Questions_source.md` exists.

**`12_` (project experts), items 1–13: 13 PASS.**

- **#1:** Q9 says "within the two rounds of changes of the content stage (section 07)".
- **#2:** the email link to `#s8` and the hero link both work live.
- **#3:** the pitch adds « dans le périmètre fixé par la proposition signée (rôles : voir la question 28) ». The console note says « Exemple de répartition… question 28 ».
- **#4:** the « Précisions » field and the toast are verified live. Voyageurs still defaults to 1, as accepted in `13_`.
- **#5:** the cookie-banner default is present.
- **#6:** the mailto is decoded above. The §8 intro says "Write OK to accept our assumption as it is, or your answer."
- **#7:** §09 includes the three-year total.
- **#8:** the warmer Q3, Q5 and §8 box lines are present verbatim.
- **#9:** « Double authentification obligatoire » is on cards 01, 02 and 05. The note says « Connexion en deux étapes pour tous les comptes ».
- **#10:** backups read "any minute of the last 30 days; photos and documents to the previous day" in both §04 and the defaults list.
- **#11:** §05 says "With the optional maintenance plan, you get this measure in a monthly report".
- **#12:** below 600 px the number sits inline before the badge (seen in the Q18 phone screenshot). The phone page is still 26,300 px against 26,274 px in round 2, because round 2 added about 190 words to §8. Accepted.
- **#13:** all 30 #q anchors land within 500 ms on a fresh load (round 2 needed 1–2.5 s).

**Sync:** all 30 default texts on the page appear verbatim, on their first 120 characters, in both `01b_Questions_source.md` and `07_Question_Coverage_Matrix.md`.

**Regressions from round 2:** none found. The only new console output is the font-preload warning (N1), which comes from the network and not from a code change; live and local are identical.

**Verification verdict: PASS (34 of 34).**

## Part 2: final judgement

### Can Veena answer in 20 minutes or less?
**Yes.**
- §8 is 2,628 words on desktop, about 12 minutes of reading.
- The mailto now arrives labelled, so on a phone she can type "OK" on most lines without scrolling back.
- If she does the eight "Answer first" questions properly and writes OK on the other 22, the work fits comfortably in 20 minutes.
- On the phone, "Go straight to the 30 questions" removes the 19 screens of preamble.

### Anything still unbounded or contradictory
**One Medium contradiction (fix 1).** It is about who can see the GM&E codes, and it bears on acceptance test T05 ("GM&E code invisible to … unauthorised roles").

- The console note (`console/index.html` line 96) says « Le suivi interne et les codes tarifaires ne sont visibles que par la personne qui valide les congrès ». Card 05 says « Seul rôle à voir les codes ».
- But Q19 makes **Veena** move each congress through the internal steps, which include « demande de code envoyée » and « code reçu ».
- The console's own Congrès table, which is « l'administration proposée pour Veena », shows the « Suivi interne » column to her.
- Q28 never says who the "authorised roles" are. A hostile client can therefore fail T05 at will, or demand an extra role.

**Two Minor wording risks:**
- §05: "the previous version can be put back within minutes" reads as a firm promise.
- §03 says the Console lets Veena « import congresses from a spreadsheet ». Q17 says "We import it once … Veena adds new ones in the admin afterwards". Is ongoing import hers or not? The RFP's L2 mandates CSV import, so the fix is to say so.

### MECE check against the RFP
- **L0–L4:** L0 is covered by the audit (J1) and the single workshop, which is bounded (one workshop of up to 2 hours). L1 is covered in §03, §04, Q9–Q16 and the defaults. L2 is covered in Q17–Q22 and Q28. L3 is covered in Q23–Q24 and listed as optional. L4 is covered in Q25 and listed as optional.
- **J0–J6:** all seven are in §07, each with ASSET's input.
- **T01–T15:**
  - T01–02: Q15 and the enquiry steps.
  - T03–04: the congress filters default and Q19.
  - T05–06: Q18 and the quote request. **T05 roles are ambiguous; see fix 1.**
  - T07–08: Q21 and Q23.
  - T09: cookie-banner default. T10: old-addresses default.
  - T11–12: accessibility and speed defaults.
  - T13–15: backups default, Q16 export, training and Q28.
- **Decisions table:**
  - Budget and schedule: Q1–2.
  - Existing technology: Q4–6, plus the self-check list.
  - Content and languages: Q9–11 and Q14.
  - Commercial enquiries: Q15–16.
  - Partners: Q18 and Q23–24.
  - Operations: Q27, Q29, Q30 and the defaults (backups, retention, settling-in).
  - All complete.
- **Documents to submit:** §09 covers the cost split, VAT, the three-year total and the project lead. **"Effort by role" is not mentioned (fix 4, Minor).** For "verifiable references", the operator's wording stands (examples without client names, plus contact with permission). This is an accepted, documented deviation; the proposal must explain it, as the RFP asks for "any partial response".

## Remaining fixes (file · problem · exact fix · severity)

1. **Who sees the GM&E codes is undefined and self-contradictory.** Severity: **Medium**.
   - **`site/questions/index.html` Q28 default:** append "Only Veena and management can see the GM&E fare codes and their evidence; the backup editor cannot." Mirror the same text in `01b_Questions_source.md` and `07_Question_Coverage_Matrix.md`, in the Q28 row and the U63 line.
   - **`site/console/index.html` line 96:** replace « Le suivi interne et les codes tarifaires ne sont visibles que par la personne qui valide les congrès ; ils n'apparaissent jamais sur le site public. » with « Le suivi interne n'est visible que dans la Console ; les codes tarifaires GM&E et leurs justificatifs ne sont visibles que par les personnes autorisées (question 28). Ni l'un ni l'autre n'apparaît sur le site public. »
   - **`site/console/index.html` line 107, card 05:** replace « Seul rôle à voir les codes tarifaires GM&amp;E et leurs justificatifs. » with « Voit les codes tarifaires GM&amp;E et leurs justificatifs. »
2. **§05 "within minutes" reads as a firm promise.** Severity: **Minor**.
   - File: `site/questions/index.html` line 172.
   - Fix: "the previous version can be put back within minutes" becomes "the previous version can usually be put back within minutes".
3. **Q17 against §03 on spreadsheet import.** Severity: **Minor**.
   - File: Q17 default, mirrored in `01b` and `07`.
   - Fix: "Veena adds new ones in the admin afterwards." becomes "Veena adds new ones in the admin afterwards, one by one or by spreadsheet import."
4. **§09 omits "effort by role", which the RFP lists under documents to submit.** Severity: **Minor**.
   - File: `site/questions/index.html` §09.
   - Fix: "The name of the project lead comes with the proposal." becomes "The name of the project lead and the effort by role come with the proposal."

**N1 (note, no fix required):** on the home page, the `Inter.woff2` and `EBGaramond.woff2` preloads trigger an "unused within a few seconds" warning over a slow link. If you want a clean console, give the preload `<link>` the same `crossorigin` as the `@font-face` fetch, or drop the preload. These are warnings, not errors.

After fixes 1–4: re-run `site_check`, redeploy, and repeat the live-vs-local `cmp`. No fourth audit round is needed.

## Per-expert sign-off

| Expert | Verdict | Reason |
|---|---|---|
| Senior UX/UI Designer | **SIGN** | Labelled mailto, instant anchors, inline numbers on the phone, axe clean, no overflow. A 20-minute reply is realistic. |
| Full-Stack Developer | **SIGN** | Live and local byte-identical; 0 errors; CSP enforced; 39 of 39 links good; the demo sets no cookies or storage; « Précisions » wired into the toast. N1 is cosmetic. |
| Solution Architect | **NO-SIGN until fix 1** | T05 needs a defined set of authorised roles for the GM&E codes. Today the console says "approver only" while Q19 has Veena running the code steps. A 5-minute fix, then SIGN. |
| Product Manager | **SIGN (fixes 2–4 recommended)** | All 34 round-2 items pass. L, J, T and the decisions table are fully covered. The deadline, the scope rule and the defaults are consistent across the email, the 4 pages, `01b` and `07`. |
| Product Designer | **SIGN** | Precisions field and toast match Q22. The console's illustration framing and its role note match Q28. The tone is warmer, with the protections kept. |

## Verdict

**FIX, then SEND.** Make fix 1 (Medium, about 5 minutes). Make fixes 2–4 (Minor, about 5 minutes) in the same pass. Redeploy and run the `cmp` once more, then send. Nothing else blocks.

## Round 3 fixes + architect re-check (28 Oct 2026)

**Applied** (from `14_` fixes 1–3 and this file's fixes 1–4):
- `14_` #1: Q7 default now lists "(button clicks, form starts and sends, errors, congress searches, congress page views, account requests and client-login clicks)"; the §04 row is widened the same way.
- `14_` #2: « Budget indicatif (facultatif) » field added to the MICE form (`site/index.html`) and shown in the recap (`js/main.js`); the MICE row on `/pour-asset/` adds « budget indicatif ».
- `14_` #3: the consent-banner default now starts "Only if a tracker is kept (question 7): …".
- Experts #1: Q28 default adds "Only Veena and management can see the GM&E fare codes and their evidence; the backup editor cannot." Console note (l.96) now reads « … ne sont visibles que par les personnes autorisées (question 28) ». Card 05 reads « Voit les codes tarifaires GM&E et leurs justificatifs. » Card 02 (Veena) gains « Voit les codes tarifaires GM&E », so the cards match Q28.
- Experts #2: §05 "can usually be put back within minutes".
- Experts #3: Q17 "…afterwards, one by one or by spreadsheet import."
- Experts #4: §09 "The name of the project lead and the effort by role come with the proposal."
- `01b_` and `07_` re-synced: the Q7, Q17 and Q28 defaults, plus the U61, U63 and U114 rows; `07_` has a round-3 change note. `14_` fixes 4–5 are recorded as must-do items in `16_Proposal_Carryover.md`, not applied to the pages.

**Gates:**
- Functional: 62/62. One r2 assertion was updated to the new cookie-banner wording, and one r3 assertion was added covering all fixes.
- site_check: PASSED, 0 failures, on 4 pages × 4 contexts.
- Screenshots: the changed parts were shot at desktop and on iPhone 13 (`/tmp/r3fix/`) and looked at. The MICE budget field and recap, the role cards, the GM&E note and the §04 row are clean. In the tall phone capture, the skip link looks like it overlaps a card. This comes from how a capture taller than the screen is stitched together: in the real viewport the link sits at top −60 px, off-screen.
- Redeployed. Live and local have the same sha1 for all 4 pages and all 9 CSS/JS files.

**Solution Architect re-check: is the GM&E visibility rule now identical everywhere?**
- Q28 (page, `01b_`, `07_` ×2): "Only Veena and management can see the GM&E fare codes and their evidence; the backup editor cannot." The text is verbatim in all four places.
- Q19: Veena moves each congress through the steps (including « demande de code envoyée » and « code reçu ») and management gives the final approval. This agrees: the two people who handle the codes are exactly the two who can see them.
- Console: the note points to "authorised people (question 28)". Card 02 (Veena) and card 05 (approver = management) both see the codes. Card 03 (contributor) and card 04 (sales reader) do not. The Congrès table shows « Suivi interne » to Veena, which is now allowed. No "only role", "seul rôle" or "personne qui valide" wording is left anywhere in `site/`, `01_`, `01b_` or `07_`.
- Public pages: home and pitch still say the codes never reach the public site or the browser. This agrees with the console.
- T05 ("invisible to unauthorised roles") now has a defined set of authorised roles: Veena and management. Everyone else is unauthorised.

**Solution Architect: SIGN.**
