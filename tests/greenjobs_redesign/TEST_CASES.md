# GreenJobs redesign — manual test cases

Automated coverage: `python3 tests/greenjobs_redesign/test_build.py` (build + validator + KPI recomputation) and `node --test` in `src/js/` (pure helpers). The cases below are the manual checks that need a browser.

## Dashboard (`/{ie,uk}/dashboard/`)

Reach it from the "KPI dashboard" link at the top of `/{ed}/for-keith/`. It is deliberately absent from the primary nav and the sitemap.

1. **Renders per edition.** Open `ie/dashboard/` then click `UK` in the header edition switch: you stay on the dashboard, numbers change, the currency symbol in the salary tile follows the edition (€ / £).
2. **Data as of.** The line under the h1 shows the snapshot date from `data/{ed}.json` (`fetched`), not today's date.
3. **Live-now tiles.** Eight tiles, each with a one-line "how we measure it". "New this week" carries a four-week sparkline. "Top employer share" gets a clay border and "!" only when the share is above 50% (true for IE where Gaia Talent dominates; check UK does not flag when its top employer is under half).
4. **Charts.** Sector and county/region bars plus the quality-score histogram render after load. Tab through the bars: each bar takes focus, shows the tooltip and reads "label: N roles" to a screen reader. "Show as table" under each chart expands a data table.
5. **Download CSV.** Click the button: a file `greenjobs-kpis-<date>.csv` downloads with a header row, the nine headline metrics, one row per sector, region and quality score. Open it in a spreadsheet; commas in labels are quoted. No network request is made (check the Network tab).
6. **Wired at launch.** Every tile in "Measured after launch" shows a dash, an event name in `code`, and a target in bold. No live-looking numbers appear anywhere in this block; the only digits are inside labelled targets (60%, 8%, 2.5 s, 200 ms, 0.1, 99.9%).
7. **No vendor names.** Search the page for "Plausible" and "GA4": none. The copy says "analytics provider".
8. **Dark theme.** Toggle the theme: tiles, bars and the histogram stay readable; the wired tiles keep their dashed border and muted dash.
9. **Reduced motion.** With `prefers-reduced-motion: reduce`, nothing animates and every number is visible immediately.
10. **390 px.** At a 390 px viewport the tiles stack in one column, the bars wrap their labels, and the CSV button sits under the as-of line. No horizontal scroll introduced by the dashboard content.
11. **Validator.** `python3 execution/gtm_client_workflows/greenjobs_redesign/build_site.py` exits 0: the page is noindex, has one h1, relative paths only, and stays inside the CSS/JS budgets.

## Pages & copy (Keith A / C / E / F, 2026-09-28)

### PC-1 Home hero, keyboard
1. Open `/ie/index.html`, press Tab from the address bar.
2. Expected: first stop is "Skip to content"; then header links, edition switch, theme toggle, "Post a job", then the search field "Role, skill or employer", "Where", "Search". No stop lands on the wind canvas or the legend.
3. Type "ecolog" in the search field; Down arrow moves through suggestions, Enter opens the jobs page with `?q=`.
4. Repeat on `/uk/index.html`; the hero count row shows "employers hiring now" on UK and does **not** on IE.

### PC-2 Home hero, reduced motion
1. Enable "Reduce motion" in the OS (Windows: Settings → Accessibility → Visual effects → Animation effects off; macOS: Accessibility → Display → Reduce motion).
2. Reload the home page. Expected: no particle canvas is drawn (gradient background only), numbers in the count row render at their final value without counting up, nothing moves on scroll.
3. The h1 reads "Work that works for the planet." with the edition sub-line underneath; the B Corp mark and its one-line explainer sit under the count row.

### PC-3 Home hero, mobile 390 px
1. DevTools device toolbar, 390 × 844 (iPhone 14 class), both editions.
2. Expected: h1 wraps on at most three lines, no horizontal scroll, the search stacks to one column with the button full width, the count row wraps onto multiple lines with the snapshot pill last, the B Corp mark stays 56 px tall beside its text.
3. Tap targets: each header control and the Search button measure at least 44 px tall.

### PC-4 Home section order and duplicates
1. Scroll the IE home. Expected order: hero + search → Latest roles → Browse by sector → Salary insight → Why GreenJobs → Employer proposition → Email alerts. No map band, no CV-match panel.
2. Scroll the UK home. Expected order: hero + search → Latest UK roles → Browse by sector → "See where green employers are hiring" (map) → Salary insight → Why GreenJobs → Employers and advertising → Job alerts.
3. The sector tiles appear once; the county/region list appears once (UK map band only); the salary figures appear once (insight band).

### PC-5 Salary insight band
1. Three tiles: disclosed-salary count with share and median; sectors with live work; counties/regions with live roles.
2. Keyboard: each tile is one Tab stop with a visible focus ring; Enter opens Salary explorer, Sectors and the jobs map view (`jobs/index.html?view=map`) respectively.
3. Reduced motion: tiles do not lift on hover and numbers do not count up.
4. Mobile 390 px: tiles stack one per row; the note about multi-county roles reads in full.

### PC-6 Employers page: rate CTA and comparison table
1. `/ie/employers/index.html` and `/uk/employers/index.html`. The h1 is the network line; directly under the lede sits "Request advertising rates" (a `mailto:` to the edition's contact address with the subject "Advertising rates request") and "Or send your details" (jumps to the form).
2. "Audience and reach" shows three tiles; where no figure exists the tile says "figure supplied at launch". No invented numbers.
3. "Organisations recruiting through GreenJobs" shows only employers with a live role (hover a logo: it links to the employer site where known). The Pause button stops the strip and is keyboard operable.
4. Comparison table: columns Standard / Premium / Membership; unconfirmed cells read "Ask us", never a tick. At 390 px the table scrolls horizontally inside its wrapper without breaking the page width; row headers stay readable.
5. UK only: "Trusted across the UK" with three slots labelled "Testimonial supplied at launch", the network coverage line and a second rate CTA. IE has no such block.
6. Post a job: the explanation is the single line "Preview exactly how your vacancy will appear to candidates." Submitting shows the launch note and sends nothing.

### PC-7 Footer contact order
1. UK footer: "Calling from the UK: +44 28 4303 2055" is listed before "Calling from Ireland: (01) 912 5247". IE footer: Ireland first. Both numbers are `tel:` links.
2. Footer B Corp mark carries the explainer sentence and a `title` tooltip.

### PC-8 Copy sweep
1. On every public page (not `/for-keith/`), search the rendered text for: "honest", "actually says", "read from the title", "Demo:", "this demo", "not estimates", "competitive" (outside employer-written salary text). Expected: none.
2. Salary framing on home and Salary explorer reads "Compare disclosed salaries and identify employers committed to greater pay transparency."

### PC-9 Evidence page
1. `/ie/for-keith/index.html` → "Changes from your 28 September notes" lists every checklist item with Done / Partial / Open / Not done, read from `KEITH_CHANGES_CHECKLIST.md` at build time.

## Board & data (agent A — Keith B, D, G)

| # | Area | Steps | Expected | Result |
|---|------|-------|----------|--------|
| BD-1 | Filter rail, keyboard | On `/ie/jobs/`, press Tab from the page heading. Move through Keyword, County, Sector, Workplace, Career level, Contract (the scraped job type and the text-derived tags are one merged facet), Salary min/max, "Salary disclosed only", "Ireland only", Closing date, Advertised by, Sort, Clear. | Every control receives a visible focus ring; each has a label read by a screen reader (test with NVDA/VoiceOver); Space toggles the checkboxes; Enter in a text field submits without leaving the page. | |
| BD-2 | Filters persist in the URL | Set Workplace = Hybrid, Career level = Senior, Min salary 40000, tick "Ireland only". Copy the address bar, open it in a private window. | The same filters are set, the same count shows, and the active-filter chips list each one. "Clear" empties every control and the query string. | |
| BD-3 | Salary range compares fairly | On `/uk/jobs/` set Min salary 60000 with no Max. | Only roles whose annualised range reaches £60k (euro roles converted at 1.17) appear; every card still shows the salary in its advertised currency, with "(paid in euros, about £…)" on euro roles. | |
| BD-4 | Location badge | Open `/uk/jobs/` and `/uk/` home rows. | Each card carries one badge: UK, Northern Ireland, Remote, Ireland & UK (no Ireland-only or International badge on the UK edition). On `/ie/jobs/` UK-located roles show "UK" and disappear when "Ireland only" is ticked. | |
| BD-5 | Closing-date facet | Set Closing date = "Closing within 7 days", then "Hide closed roles". | The first shows only roles with a closing date in the next 7 days; the second removes roles whose closing date has passed and keeps roles with no date. | |
| BD-6 | Agency vs direct | Set Advertised by = Recruitment agency, then Direct employer. | Gaia Talent, Mattinson Partnership and CHM Recruit roles appear only under agency; Arup, Jacobs, councils only under direct. The rule is on the job page ("Advertised by"). | |
| BD-7 | Map view, keyboard | Switch to Map, Tab into the map, use Enter/Space on a region. | Regions are focusable buttons with the count in their accessible name; activating one filters the list; "Show all" restores it; the sentence about multi-county counting is visible under the map. | |
| BD-8 | Reduced motion | Enable "Reduce motion" in the OS, reload `/ie/jobs/` and a job page. | No card reveal animation, no sparkline draw-in, no view-transition on the title; filters and map still work; salary strip dots are static. | |
| BD-9 | Mobile filters (390 px wide) | Open `/ie/jobs/` at 390 px. Tap "Filters". | A sheet opens with every facet (scrollable), focus moves into it, "Show results" closes it and applies; the salary min/max sit side by side without overflow; the sheet closes on Escape. | |
| BD-10 | Job page facts | Open any job page with a euro salary on `/uk/`. | The salary line reads in € with "paid in euros, about £…" in brackets; "Where", "Workplace", "Contract", "Level", "Advertised by" rows are present; JSON-LD (view source) has `baseSalary.currency: "EUR"` and, when a closing date exists, `validThrough`. | |
| BD-11 | Similar roles | Open a job page in a busy sector (e.g. water). | Up to four cards under "Similar roles": same sector first, then same county/region, then similar pay; never the same role. | |
| BD-12 | Landing pages | Open `/ie/ecology-jobs-ireland/`, `/uk/environmental-jobs-london/`. | One h1, an intro with live counts and median, the filtered cards, related links, a canonical link; a landing page with no live role does not exist (404). | |
| BD-13 | Guides | Open `/ie/guides/` and `/ie/guides/salary-guide/`. | Bands and sector medians match the salary explorer; "Last updated" shows the snapshot date; page is noindex. | |
| BD-14 | Quick job match | On `/uk/jobs/` scroll to "Quick job match". | The two disclosure lines sit beside the input; UK examples read "ecologist Bristol", "sustainability consultant London", "flood risk engineer Manchester", "renewable energy Scotland"; no "ecologist dublin". | |

## Data rules (round 4, 2026-09-28) — automated in `test_build.py` block `# --- round 4 ---`

| ID | Case | Steps | Expected | Result |
|---|---|---|---|---|
| R4-1 | Sterling restoration | Open `/ie/jobs/11495292/` (Senior Health & Safety Consultant, Mattinson). | Salary reads "£55k–60k (paid in sterling, about €…)" with "Advertised in sterling on the greenjobs.co.uk listing"; never the £62–67k namesake. Build log: "21 sterling salaries restored". | auto |
| R4-2 | Unverified roles | Open `/ie/jobs/11497629/` and `/ie/jobs/11496364/`, then `/ie/guides/salary-guide/`. | Both pages say "Salary as listed on greenjobs.ie; the advertiser may pay in sterling"; the guide's note ends "2 UK-located roles with unconfirmed currency are excluded from medians."; the IE median/bands ignore them. | auto |
| R4-3 | Secondary sector tags | Open `/uk/jobs/11493046/` (Coastal Engineering PM), `/uk/jobs/11496303/` (Solar PV Designer), `/ie/jobs/11493440/` (EIA – Energy). | Chips: Infrastructure + Water & flood; Solar + Renewable; Environmental science + Energy networks. `/uk/jobs/11499784/` Marine Enforcement Officer is Policy first. | auto (golden `expect_secondaries`) |
| R4-4 | Workplace / contract | Open `/ie/jobs/11493521/` (Senior Bridge Engineer, type Contract, body says "permanent"). | Contract row reads "Contract" only. Roles mentioning "energy market reserves" or a "supplier onsite audit" carry no Site-based tag. | auto |
| R4-5 | NI at 0 | Open `/uk/jobs/?view=map` and the County select. | Northern Ireland (and East Midlands) appear with 0 roles rather than vanishing; the map region is still focusable. | auto (`test_ni_region_and_facets`) |
| R4-6 | hreflang | View source of `/ie/jobs/` and `/ie/ecology-jobs-ireland/`. | `en-IE`, `en-GB` and `x-default` alternates, absolute, pointing at the same path in the other edition; landing pages pair with their twin slug only when both exist. | auto (`test_pf_a_hreflang_pairs`) |
| R4-7 | Cross-border phrases | Search "UK, Ireland" / "Ireland/UK" titles. | Badge "Ireland & UK"; an employer's "offices in the UK and Ireland" boilerplate deep in the description does not trigger it. | auto |
| R4-8 | Deploy gate | Edit any file in `site/` then run `deploy_cloudflare.sh`. | Refuses: marker missing/stale or `validate_site.py` fails; rebuild restores the gate. | auto (CLI) |

## Panel fixes B (2026-09-28) — automated in `test_build.py` block `# --- panel fixes B ---` and `node --test src/js/dashboard.test.js`

| ID | Case | Steps | Expected | Result |
|---|------|-------|----------|--------|
| PB-1 | Cookie copy | Open cookie Settings on any page. | Lists theme, edition, saved roles, weekly-email prompt dismissal, dashboard view and the choice itself; no "nothing else". | auto |
| PB-2 | Quick job match privacy | Type in the box on `/ie/jobs/`; watch the address bar; click "Copy shareable link". | Nothing is written to the URL while typing; after the click the `#fit=` hash appears with the note "The link contains your text." | auto + manual |
| PB-3 | B Corp | View source of home, header, footer. | "Certified B Corporation" only as the mark's `alt`; the text is the generic B Corp definition. | auto |
| PB-4 | UK employers testimonials | Open `/uk/employers/`. | No placeholder slots; one line "Client testimonials are being collected for launch". | auto |
| PB-5 | Demo forms | Home alerts, subscribe dialog, employers form before typing. | Launch note visible above the button; alert/subscribe show "Meanwhile, browse all roles →". | auto |
| PB-6 | Employers page | Open `/ie/employers/` and `/uk/employers/`. | IE lede has no employer count; every CTA reads "Request advertising rates"; done-for-you line; Membership column "Ask us" except discounts and self-management; swipe hint at ≤ 700 px. | auto |
| PB-7 | 390 px overflow | Open `/uk/` and `/ie/jobs/` at 390 px. | No horizontal scroll; salary and sector tags wrap. | auto (CSS) + QA harness |
| PB-8 | Toggle label | Open the filter rail on both editions. | "Hide UK/abroad-only roles" (IE) / "Hide Ireland/abroad-only roles" (UK) with the helper text. | auto |
| PB-9 | Closed roles | Set the system clock past a role's closing date (or `data.today`). | Card shows a "Closed" chip; job page Apply becomes "This role has closed". | auto (hooks) + manual |
| PB-10 | Dashboard | Open `/ie/dashboard/`. | "Event spec for launch" group; new tiles; agency tile states the real rule; CSV cells starting with = + - @ are prefixed with a quote; every apply link carries `data-ev`. | auto |
| PB-11 | for-keith | Open `/ie/for-keith/`. | Benefit-led copy; technical appendix collapsed; launch checklist with six items; H1/H2/I1/I2 done; full footer address. | auto |

## Layout regression (automated) — `node tests/greenjobs_redesign/layout.test.mjs` (2026-09-28)

Headless Chromium loads 17 page types per edition (home, jobs list, jobs map view, jobs with facets incl. Sustainable infrastructure, job page IE `/ie/jobs/11500760/` and UK `/uk/jobs/11501639/`, sectors, insights, compass and a compass result, employers, dashboard, one landing page, guides, salary guide, cookie dialog open, subscribe dialog open, mobile filter sheet open) plus `404.html`, at 1440×900, 1024×768 and 390×844, light and dark (202 page loads), and asserts from DOM geometry. One PASS/FAIL line per rule per page/viewport/theme; exit 1 on any FAIL. Real defects that are documented but unfixed live in `KNOWN_DEFECTS` inside the script, print as `KNOWN` and do not fail the run; delete the entry once fixed. Part of `run_all.py`; skips with a message when Chromium/Playwright is absent.

| # | Rule | Assertion |
|---|------|-----------|
| R1 | No horizontal overflow | `document.scrollWidth` and `body.scrollWidth` ≤ viewport width. |
| R2 | Chips | Every visible `.tag`: content box ≤ 2 line-heights; the dot `<i>` (if present) has its centre within the first text line's box; chip width ≥ dot + 4 px. |
| R3 | Chip rows | Within each `.row__meta`, chips on the same flex line (overlapping vertical extent) have tops within 4 px. |
| R4 | Comparison tables | `.cmpwrap table`: in tabular layout every cell sits inside its header column band and row heights are equal ±2 px; in the ≤700 px card layout no cell is hidden or outside the viewport; no cell contains a `button`/pill/chip; at ≥701 px `.cmpwrap` has no inner scroll (scrollHeight = clientHeight, scrollWidth = clientWidth). |
| R5 | No overlapping text | Headings, paragraphs, buttons, links, labels, chips, list items and table cells in the same section (`dialog`, `.cookie`, `.sheet`, `section`, `article`, `header`, `footer`, `nav`, `aside`, `form`, `main`) have no overlapping text rects; parent/child and `[data-marq]` ignored. |
| R6 | No clipped controls | Every visible `button`/`a`/`input`/`select`/`textarea` lies inside the viewport and inside the client box of its nearest scroll/clip container (horizontal always; vertical for `overflow:hidden/clip`); button labels not wider than the button; input placeholders fit the input's content width. `[data-marq]` carousels and the ≤700 px `.cmpwrap` horizontal scroll are exempt. |
| R7 | Button rows | `.btn` elements sharing a parent and a line have heights within 2 px. |
| R8 | Hero trust block | `.hero__trust p` renders ≤ 2 lines at ≥1024 px and ≤ 3 lines at 390 px. |
| R9 | Filter rail | The last control of `.rail` (in the sheet at 390 px) is visible after `scrollIntoView`, inside the rail/sheet and the viewport. |
| R10 | Console and network | Zero console errors, page errors, failed requests or HTTP ≥ 400 responses per page load. |
| R11 | Contrast | Text with a solid composited background (gradients/images and translucent dialogs skipped): ≥ 4.5:1, or ≥ 3:1 for large text (≥ 24 px, or ≥ 18.66 px bold). Colours normalised through canvas so `oklch()` values are handled. |
| R12 | Screenshot baseline | A viewport PNG per page/viewport/theme goes to `.tmp/layout_baseline/`; for the 1440-light and 390-dark sets of 10 page keys per edition (40 JPEGs, quality 40, in `tests/greenjobs_redesign/layout_baseline/`) the current shot is compared in-page via canvas (pixelmatch-style YIQ distance) and fails when > 1.5 % of pixels differ. Refresh with `--update-baseline`. |

Known defects on the 2026-09-28 build (printed as `KNOWN`): R2 map-view side list sector chips wrap to three lines at 1024/390 (visual_issues #5); R6 employers "Post a job" title placeholder "Senior Hydrogeologist" is wider than the input at 1024 (visual_issues #20 class); R11 home "Salary insight" numerals (`.insight__n`, lime on cream, light theme) measure 1.78:1.

Flags: `--quick` (1440 light only), `--only=<key substring>`, `--update-baseline`, positional site dir, `PORT`, `PW_CHROMIUM`.
