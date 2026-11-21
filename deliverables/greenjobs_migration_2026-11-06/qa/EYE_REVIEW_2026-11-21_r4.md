# GreenJobs staging: human-eye review, round 4 (2026-11-21)

**Verdict: PASS.** 0 blockers, 0 majors and 4 minors (new). Of the 30 defects listed in rounds 1 to 3, 27 are fixed. The other 3 are minors that are partly fixed or improved: m2, m3 and R3-7.

- Staging boards: https://greenjobs-stg-ie.pages.dev/ie/ (141 live roles) and https://greenjobs-stg-uk.pages.dev/uk/ (77 live roles).
- Worker hosts, checked for the redirect: https://greenjobs-platform-staging.debanjan186.workers.dev and https://greenjobs-platform-staging-uk.debanjan186.workers.dev
- Approved design used for comparison: https://greenjobs-redesign.pages.dev/ie/ and /uk/
- Browsers: Playwright Chromium, with a fresh context for each edition and device. Devices were Pixel 7, iPhone 14 and a 1440x900 laptop, all at deviceScaleFactor 1. Every page was scrolled from top to bottom before its full-page shot.
- Pages covered on each edition and device: cookie banner, home, alert sign-up (submitted), jobs list with keyword search and sector filter, a sector-filtered list, 3 or 4 job pages, sectors, employers, salary explorer, career compass, dashboard, 404, /for-keith/, the IE/UK switch, and a direct visit to a workers.dev job URL.
  - Job pages: an email-apply page, a second email-apply page, a page reached by clicking a card in the list, and the "Similar roles" link from that page.
  - IE also had a link-apply page. The UK board has no link-apply jobs: all 77 apply in-page.
- Apply tests: every form was submitted with reviewer+test@example.com, once without a CV and once with a small, real PDF CV. Jobs that had never received that address were used so that the server's dedupe did not hide the result.
- HTTP crawl: 274 URLs on the IE host and 253 on the UK host, plus the `/api/jobs` and `/api/stats` endpoints.
- Screenshots are in /tmp/claude-0/-home-user-deb-antigravity-claude-workspace/2792bc90-e2ed-5c8a-b9c2-eaf4b7567fa4/scratchpad/eye4/. Full-page shots are named `{ed}-{device}-{page}.png`. The contact sheets I read are in `sheets/`, and viewport and flow shots are in `vp/`.
- Expected on staging and not reported: "[Test data]" titles, and dry-run delivery (`"delivery":"dry_run"`) with an on-screen success message.
- Reviewer: independent. I did not read the site's source code or tests.

## Previous defects re-checked

| # | Defect (round) | Status | Evidence (r4) |
|---|---|---|---|
| B1 | "Live" jobs opened as "This role has closed" (r1) | Fixed | 0 crawled pages say closed. `/api/jobs` shows 0 closing dates before 21 Nov. |
| B2 | UK cards linked to worker URLs that returned 404 (r1) | Fixed | The crawl found 0 non-200 pages on either host. Every card links to pages.dev. |
| B3 | Frozen snapshot and contradictory counts (r1) | Fixed | IE: 141 roles, 27 disclosed (19%), median €61.4k, 15 sectors, 17 counties. UK: 77 roles, 47 disclosed (61%), median £50k, 14 sectors, 10 regions, 18 employers. These agree across home, list, explorer, dashboard and footer. The salary bands sum to 27 and 47. |
| M1 | Every role shown as "Today" (r1) | Fixed | Cards show real ages (Today to 3 mo ago). Dashboard: new this week 15 / 9, closing within 7 days 6 / 10. |
| M2 | Alert sign-up said "coming soon" (r1) | Fixed | All 6 runs got 202 `{"next":"check_email"}` and the message "Check your inbox: we have sent you a link to confirm this alert." (vp/ie-pixel7-alert.png) |
| M3 | Links to old .asp pages or Strategies (r1) | Fixed | The crawl found 0 `.asp` links and 0 links to a strategies host. External hosts are limited to the network sites, greenjobs.ie/.co.uk, gaiatalent.com, Facebook and X. |
| M4 | Salary explorer degraded, and sterling shown as € (r1) | Fixed | IE has 6 sector medians, and £ roles show "≈ €". UK € roles show "≈ £". |
| M5 | IE "Similar roles" section empty (r1) | Fixed | It shows 4 cards on every job page viewed. A similar-role card opens its job page. |
| M6 | Listing quality score skewed (r1) | Fixed | IE is 53/59/29 at 2, 3 and 4 of 4. UK is 30/47 at 3 and 4 of 4. |
| m1 | Footer reads "Demo redesign, not the live site." (r1) | Fixed | The footer reads "© 2008–2026 GreenJobs Ltd." on every page. |
| m2 | Phone tap targets under 44px (r1) | Mostly fixed | Filters, List, Map and Saved, card Save icons, "Show as table", the footer and employer links all now measure 44px or more. 0 undersized links or buttons inside `main` on the UK jobs and employers pages. Remaining: the filter-chip "×" (32x32), the consent checkboxes (20–24px, but their labels are clickable) and the UK map region shapes (about 32x26; there is a list version beside the map). |
| m3 | Odd UK locations (r1) | Improved, as in r3 | Some multi-region strings from the source feed remain, e.g. "West Yorkshire, anywhere in Scotland". |
| m4 | Arborist description broken mid-sentence (r1) | Fixed | No broken descriptions were seen. |
| m5 | Gaia "G" initial in place of the logo (r1) | Fixed | The logo shows on cards and job pages. |
| N1 | Apply form returned 405/403 (r2) | Fixed | Without a CV: 201 `{"status":"received","delivery":"dry_run"}`. |
| N2 | Apply form had no layout styling (r2) | Fixed | Inputs are 48–51px and the button is full width (vp/*-applyform.png). |
| N3 | Text cut off on iPhone 14 (r2) | Fixed | The page is 390/390 wide on every iPhone page. |
| N4 | Misleading "Apply on greenjobs.ie" label (r2) | Fixed | The button reads "Apply now →". On link-apply jobs it reads "Apply on gaiatalent.com →". |
| N5 | Sticky bar covered the end of the footer (r2) | Fixed | The end of the footer is reachable. |
| N6 | Dashboard linked to /for-keith/ (r2) | Fixed | There is no Keith link on any page. /ie/for-keith/ and /uk/for-keith/ return 404 on pages.dev, and the worker hosts redirect them to that 404. The only "keith" href on those pages is the 404 page's own skip-link (`…/for-keith/#main`). |
| N7 | Dot-plot unreadable on phones (r2) | Fixed | Labels are readable, with "Swipe sideways to see the whole range". |
| N8 | Past deadlines in descriptions (r2) | Fixed | 0 closed or past-dated pages in the crawl. |
| N9 | Gaia "as published on greenjobs.ie" and "0 similar roles" (r2) | Fixed | It says "Description as published on gaiatalent.com" and "No other live roles like this within Roscommon right now." |
| R3-1 | **CV upload returned 503 `cv_storage_unavailable`** (r3, major) | **Fixed** | With a PDF CV attached (multipart POST), the server returned **201 `{"status":"received","delivery":"dry_run"}`** on IE 11501648 (Pixel 7), IE 11501012 (iPhone 14), IE 11501460 (laptop), UK 11501461 (Pixel 7) and UK 11501639 (laptop). The message read "Application received. Thank you: it is on its way to the advertiser." No CV error was shown. (vp/ie-iphone14-p-cv-filled.png, vp/uk-pixel7-p-cv-vp.png) |
| R3-2 | **Worker-hosted job pages unstyled, raw JSON on apply** (r3, major) | **Fixed** | Every worker path tested returns **301 to the matching pages.dev URL**: IE and UK job pages, Gaia job pages, `/ie/jobs/?sector=…` (query kept), the root, unknown IDs (which then 404 on pages.dev) and `/uk/for-keith/`. In the browser, the redirected page arrived styled with its title, on all 6 runs. `/api/*` still answers on the worker (vp/*-worker.png). |
| R3-3 | Form stayed filled after success (r3) | Fixed | After success all fields clear, the consent box unticks, the button reads "Application sent" and is disabled, and the sticky bar changes to "Application sent" (vp/ie-iphone14-after-submit-msg.png). A re-submit gets "We already had it, so nothing was sent twice." See R4-1 for the Pixel 7 fold. |
| R3-4 | Breadcrumb "/" raised above the baseline (r3) | Fixed | The separators are on the baseline (vp/crumbs.png). New spacing and wrap issue: R4-2. |
| R3-5 | Footer "Jobs" indented about 8px (r3) | Fixed | All 5 Explore links are at x=18, 44px tall. |
| R3-6 | Edition switch stayed on the other edition's host (r3) | Fixed | The switch on the IE host goes to greenjobs-stg-uk.pages.dev/uk/, and the reverse on the UK host. The duplicate copies (e.g. stg-ie…/uk/) carry their canonical on the correct host. |
| R3-7 | Ham Wall text told candidates to use a "CHM Recruit form" (r3) | Largely fixed | The CHM form sentence is gone ("please click the apply button"). The text still says "you will be asked to provide a copy of your CV and complete an application form", while the in-page form has an optional CV. This is employer copy, and the client should confirm the apply route for agency jobs. |

## New defects

| # | Page | Device | Edition | Severity | Observation | Screenshot |
|---|---|---|---|---|---|---|
| R4-1 | Job page, after Send application | Pixel 7 | IE + UK | minor | The page does not scroll to the confirmation. On Pixel 7 the "Application received…" box starts at y=831 in an 839px viewport, so only an 8px sliver shows. The button and the sticky bar do change to "Application sent", so the visitor does get feedback. On iPhone 14 the box is in view. | vp/ie-pixel7-after-submit-vp.png |
| R4-2 | Job page breadcrumb | phones (worst on iPhone 14) | IE + UK | minor | The spacing is uneven: "Jobs   /Sector" has a wide gap before the last slash and none after it. On iPhone 14 a long sector name such as "Built environment & energy efficiency" wraps onto its own line, leaving "Home / Jobs /" with a trailing slash. | vp/crumbs.png, sheets/uk-iphone14-job-third-0.png |
| R4-3 | Job page opened by clicking a card in the jobs list | all | IE + UK | minor | Console error: "Unexpected duplicate view-transition-name: job-title" on every card click (6 of 6 runs). No visual breakage was seen, but the page transition may be skipped or jump. | console (p-*.txt) |
| R4-4 | Header on all pages | iPhone 14 (390px) | IE + UK | minor | The IE/UK switch is hidden in the header at 390px. It is still in the menu and the footer. The approved reference shows it in the header at the same width. On Pixel 7 (412px) the header shows it. | vp/menu-stg.png, sheets/ie-iphone14-home-0.png |

Severity counts (new): blocker 0, major 0, minor 4.

## Verified fine

- **Overflow and images:** No page is wider than the viewport on any of the 84 page, device and edition combinations (document width equals viewport width every time). No broken images.
- **Console and network:** The only errors are the intended 404s on the 404 and /for-keith/ pages and R4-3. There were 0 failed requests. The API returned 200, 201 or 202 throughout.
- **Cookie banner:** It shows on first load on all 6 runs ("only essential storage … No tracking", with Accept and Settings) and is dismissed after Accept.
- **Home:** It matches the approved design on all devices: hero, search, stats pill, B Corp card, latest roles, sector cards with medians, salary insight, the UK region map with "UK-wide / remote (13)", Why GreenJobs, network chips, logo wall with Pause, alert form and footer.
- **Jobs list:** Search "ecolog" gives 22 of 141 (IE) and "engineer" gives 16 of 77 (UK), and both write `?q=` to the URL. The sector filter gives 41 of 141 and 18 of 77, which match the sector cards. The phone Filters drawer with "Show results" works, and the filter chip can be removed. The sector link `?sector=` gives the same counts.
- **Link-apply:** On IE Gaia "Ecologist" (gaia-9360), "Apply on gaiatalent.com →" opens https://gaiatalent.com/jobs/ecologist/ on all 3 devices. 53 IE jobs are link-apply.
- **Email-apply:** Both editions and all devices were tested, without a CV and with a CV. The form resets after success, and the dedupe message appears on a repeat submit.
- **Edition switch:** The header switch on Pixel 7 and laptop, the menu switch on iPhone and the footer switch all go to the other edition's own host.
- **workers.dev:** A direct visit to a job URL redirects (301) to the board on every device.
- **404:** "Nothing grows here." with IE and UK edition cards, status 404. /ie/for-keith/ and /uk/for-keith/ return 404.
- **Sectors, employers, salary explorer, career compass, dashboard:** They render cleanly on every device. Charts have "Show as table". The UK employers line "Trusted across the UK – Client testimonials available on request" matches the approved reference.
- **Wording:** No visible demo, Keith, lorem, TODO or staging text. The crawl's "demo" hits are HTML attributes and "demonstrate" in descriptions. The dashboard "Measures to come" section is intentional KPI documentation, as in r3.
- **Contrast:** I checked by eye on every sheet and found no low-contrast text.
