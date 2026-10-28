# Panel audit: project experts (2026-10-28)

**Scope.** The cover email (`01_Questions_for_Veena.md`) and its 4 links, built from `site/` and served locally (python http.server).

**How we tested.**
- We drove the site with Playwright at desktop 1440×900 and on an emulated iPhone 13.
- The film was scrolled slowly (150 px wheel steps) and fast (jumps to set positions).
- In the catalogue we used search, each filter, combined filters, no-results, reset, the period filter, pagination, the listing, the quote form (empty submit, then filled), and Escape to close.
- We tried the contact form's three journeys, the client pop-up, the EN switch, all 6 nav anchors (after letting the scroll settle), and every cross-page link (HTTP status checked).
- We tabbed through the home page (45 stops) and the console.
- axe-core ran against WCAG 2.2 AA on all 4 pages.
- Screenshots are in `/tmp/panel5/` (92 PNGs; the panel looked at the key ones).
- Quotes on the site were checked against a fresh fetch of asset-voyagesdaffaires.com.

**Panel.**
- UX/UI: Senior UX/UI Designer
- FS: Full-Stack Developer
- SA: Solution Architect
- PM: Product Manager
- PD: Product Designer

## What works (agreed)
- **Film.** It is clean and readable at every stage. Fast scrolling never showed two headlines at once.
- **Wording.** The pochette idea is original and stays in plain French. Every quote we checked matches the live site word for word: « ne soit plus un coût mais un avantage », « 122 agences », « au meilleur prix du marché », the list of services, and « taille humaine ».
- **Catalogue.** It works as a real catalogue would:
  - The search ignores accents.
  - Filters can be combined, and the no-results state has a way out.
  - Results are sorted by date and paginated.
  - The quote form is pre-filled with the congress reference, the destination, and dates one day either side in the dd/mm/yyyy format, so it does not restrict travellers to one airport.
  - Escape closes the listing and returns focus to the button that opened it.
- **Contact form.** It has three journeys, and the MICE journey shows a live summary.
- **Technical health.**
  - Zero JS errors and zero broken internal links.
  - No horizontal scroll on the phone.
  - A visible 2 px orange focus ring on every control.
  - No images without alt text, and one H1 per page except the console.
- **Questions page.** The tone is clear and the costs are cited and honest. There are no fees for our own work, no other client names, and the 25 questions are grouped and easy to answer.

## Debate (short)
- **PM:** Link 2 is supposed to sell the business benefit to management. What it actually does is measure scroll screens, and its own table says the concept takes about 24 screens on desktop where today's site takes 6. A director will read that as "longer". The email promises "how it turns visitors into enquiries for each of your three activities", and no section does that.
- **PD:** Agreed. And link 3 is supposed to be the dashboard Veena would use. Her daily question is "what do I need to deal with today?", but the four KPI tiles count mock-up facts ("5 rôles proposés", "3 activités"). The buttons look greyed out and do nothing. A third of the page is GM&E workflow jargon. The email says she would "publish pages", yet there is no Pages section.
- **SA:** The questions page says "No WordPress … no plugins to patch". The live site is WordPress (22 wp-content references), and the RFP asks the audit to *recommend* keeping or replacing it. Rejecting it before the audit sounds like a dig at a choice management made.
- **UX/UI:** The four pages don't connect into one journey. Only /questions/ links to all the others. The home page and the pitch never link to /questions/, and the console only links back to the home page. The pitch also refers to "la section 8" with no link, and offers "un échange de 30 minutes", while the email says "I prefer to have everything in writing".
- **FS:** The site itself is solid. Polish items:
  - Mid-way through the offer-card stack the cards overlap and the text bleeds through (`d-film-slow-07.png`).
  - The console's sticky tab row takes about 25% of the phone screen.
  - The video blob (3.4–3.9 MB) starts downloading on load on phones.
  - Smooth scrolling across 10,000 px takes more than 1 s.
  - axe flags one contrast failure (4.37:1) and three footer links that are too small to tap.
- **All:** None of this embarrasses us, but the fixes to links 2 and 3 and the cross-linking are cheap and go to the core of what each link is for. **Verdict: FIX FIRST** (about 2 hours of work).

## Agreed findings by expert

### Senior Product Manager
1. **Pitch has no business benefit** (`pour-asset/index.html`, major). Add a « Ce que la refonte change pour ASSET » block before the table. It needs one row per activity: visitor → page → form → what ASSET receives.
   - Voyages d'affaires → audit or account request
   - MICE → step-by-step brief and callback
   - Congrès → quote pre-filled with the congress ID

   Close it with « des demandes qualifiées, routées vers la bonne personne ». This is the promise the email makes.
2. **Scroll comparison works against us** (`pour-asset/index.html`, major). In the « Ce que l'on atteint… » row, drop the « 24 écrans » vs « 6 écrans » comparison, or reframe it as "every offer and form reachable without leaving the page".
3. **Next step contradicts the email** (`pour-asset/index.html`, major). Replace step 1 (the 30-minute call and "section 8") with « Répondre par e-mail aux 25 questions » linked to `../questions/#s8`.

### Senior Product Designer
4. **Console headline numbers are meta** (`console/index.html`, major). Replace the four tiles with:
   - « 1 nouvelle demande à attribuer »
   - « 1 rappel prévu aujourd'hui »
   - « 2 congrès en validation »
   - « 1 brouillon »
5. **No Pages section in the console** (`console/index.html`, major). Add a small « Pages » section: a few rows with title, status and last-edited date, plus a « Modifier » button. This matches the email's "publish pages" and the RFP's need to publish without a developer. Move the GM&E workflow note into a collapsed `<details>` element.
6. **Console buttons look disabled** (`console/index.html`, minor). « Exporter CSV », « Importer un CSV » and « Nouveau congrès » look greyed out. Give them full contrast and a `title="Maquette"`, or a toast on click.

### Senior Solution Architect
7. **Pre-audit "No WordPress" verdict** (`questions/index.html` §03, major). Replace the "No WordPress…" bullet with: "Our recommendation, to be confirmed by the audit of your current site: a site built and owned by you, with its own simple admin, so there are no paid plugins to keep updated."
8. **Quote form lacks privacy information** (`index.html`, quote dialog, minor). RFP F04/F06 require it. Add the same privacy line the contact form has under « Demander le devis ».

### Senior UX/UI Designer
9. **Pages don't link to each other** (`index.html` footer, `pour-asset/index.html` top bar and signature, `console/index.html` sidebar; major). Add a link to « Questions » / « Vos questions » (`questions/`) everywhere, and add « Note pour ASSET » to the console sidebar.
10. **Offer cards bleed through mid-transition** (`js/main.js` card stack, `css/styles.css`; major). Text from the outgoing and incoming cards overlaps mid-scroll. Hide the outgoing card's content before the incoming card passes 50%, and remove the slight rotation so the text stays sharp.
11. **Console tab row too tall on phone** (`console/index.html` / `css`, minor). Make the tab row a non-wrapping, horizontally scrollable row of one line, or not sticky below 600 px.
12. **Contrast** (`css/styles.css` `.cat__head .label`, minor). #a84e06 on #e9e3d6 measures 4.37:1. Darken it to #9a4705 or darker.
13. **Footer tap targets too small** (`css/styles.css`, footer links, minor). They are 17 px tall. Set `padding-block: 4px` so they reach at least 24 px.
14. **« Demander une recherche » doesn't finish the job** (`js/main.js`, minor). Focus the « Congrès (nom, ville, dates) » field after scrolling, and copy the search text into it.

### Senior Full-Stack Developer
15. **Video downloads straight away on phones** (`js/film.js`, minor). Start fetching the video blob only after the first scroll or once the page is idle. Don't load the desktop `hero.jpg` on phones.
16. **Console has no H1** (`console/index.html`, minor). Add a visually hidden `<h1>Console ASSET — maquette</h1>`.
17. **Pitch claims every typo was corrected** (`pour-asset/index.html` / `index.html`, minor). The pitch says « deux coquilles corrigées », but « voyage d'affaire » (statement band) and « d'Affaires » (hero) are still there. Either fix both on the site, or say « coquilles d'origine conservées dans les citations ».

## Verdict
**FIX FIRST.** There are no blockers. Fix items 1–5, 7, 9 and 10 (about 2 hours), then send.

## Round 2 verification (2026-10-28, 16:45 UTC, independent re-check)

Method: Playwright on a local static server (desktop 1440×900, iPhone 13), axe-core WCAG 2.2 AA on 4 pages, `site_check.mjs` re-run on 4 pages × 4 contexts (PASSED, 104 ok / 0 FAIL), file reads and greps, curl on live URLs (all 200, byte-identical to `site/`).

| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | Pitch business benefit | PASS | « Ce que la refonte change pour ASSET » table, 3 activities × visitor/page/form/received, closes with « des demandes qualifiées, routées vers la bonne personne » |
| 2 | 24 vs 6 screens | PASS | comparison rows in plain language; no screen counts, no px |
| 3 | Next step contradicts email | PASS | step 1 = written answers by e-mail to the 25 questions, link `../questions/#s8` resolves |
| 4 | Console tiles meta | PASS | 1 demande à attribuer · 1 rappel · 2 congrès en attente · 4 demandes ce mois-ci |
| 5 | No Pages section | PASS | Pages table (6 rows, status, date, « Modifier »); GM&E note in a closed `<details>` |
| 6 | Buttons look disabled | PASS | full contrast (ink text, opacity 1); click shows toast « Maquette : … sera actif dans la vraie Console » |
| 7 | "No WordPress" verdict | PASS | §3 « Our recommendation: a custom build… The audit (step J1) will confirm whether to keep or replace it » |
| 8 | Quote form privacy | PASS | dialog shows « Vos données servent uniquement à préparer ce devis… » |
| 9 | Pages don't link | PASS | all 4 pages link to the other 3; console sidebar has « Note pour ASSET » and « Questions » |
| 10 | Card bleed-through | PASS | 19 scroll positions sampled: never more than 1 card with visible text, computed rotation 0 at every step; mid-swap screenshot clean |
| 11 | Console tab row on phone | PASS | iPhone 13: one line, `nowrap`, `overflow-x:auto`, 56 px tall (8% of 664 px), `position:static` (scrolls away) |
| 12 | Contrast | PASS | `.cat__head .label` = rgb(154,71,5) (#9A4705); axe 0 contrast violations |
| 13 | Footer tap targets | PASS | 27–30 px tall |
| 14 | « Demander une recherche » | PASS | no-results → click: focus on `#g-name`, value copied from search ("zzqx congrès Lyon") |
| 15 | Video on phone | PASS | before scroll only `hero-m.jpg` requested; `hero-m.webm` after first scroll; desktop `hero.jpg` not loaded |
| 16 | Console H1 | PASS | visually hidden `<h1>Console ASSET — maquette</h1>`; 1 H1 on every page |
| 17 | Typo claim | PASS | « voyage d'affaire » and « d'Affaires » gone; pitch lists the corrected typos |

Fresh screenshots (`screens/check-*`, re-shot this round, plus spot shots): no new visual regression on home, pitch, console (desktop and phone) or questions (§5–§9 on phone).

**New defect (FAIL, minor, text):** `site/pour-asset/index.html` line 27, « il est invisible sur Google et lié d'aucun site public » is incorrect French. Fix: « il n'apparaît pas sur Google et n'est lié depuis aucun site public ».

**Round 2 verdict: FIX FIRST (one line of French, about 1 minute), then SEND.** All 17 items verified fixed.
