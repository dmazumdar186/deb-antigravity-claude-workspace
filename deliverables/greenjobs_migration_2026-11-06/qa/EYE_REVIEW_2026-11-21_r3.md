# GreenJobs staging: human-eye review, round 3 (2026-11-21)

**Verdict: FAIL.** 0 blockers, 2 majors, 5 minors (new). Of the 23 defects listed in rounds 1 and 2, 21 are fixed. The remaining 2 are minors, 1 partly fixed and 1 improved.

- Staging boards: https://greenjobs-stg-ie.pages.dev/ie/ (141 live roles) and https://greenjobs-stg-uk.pages.dev/uk/ (77 live roles).
- API, and an alternative copy of each job page: https://greenjobs-platform-staging.debanjan186.workers.dev and https://greenjobs-platform-staging-uk.debanjan186.workers.dev
- Approved design used for comparison: https://greenjobs-redesign.pages.dev/ie/ and /uk/
- Browsers: Playwright Chromium, with a fresh context for each edition and device. Devices were Pixel 7, iPhone 14 and a 1440x900 laptop, all at deviceScaleFactor 1. Every page was scrolled from top to bottom before its full-page shot.
- Pages covered on each edition and device: cookie banner, home, alert sign-up (submitted), jobs list with keyword search and sector filter, 3 job pages, sectors, employers, salary explorer, career compass, dashboard, 404 and /for-keith/.
  - The 3 job pages were an email-apply page (form filled and submitted with reviewer+test@example.com, with and without a CV), a second email-apply page, and a page reached by clicking a card in the list.
  - Link-apply was tested on the IE Gaia page. The UK board has no link-apply jobs: all 77 apply in-page.
- HTTP sweep: 394 URLs on each host, all 218 job pages, every job page's JSON-LD, and the past-deadline text in every job description.
- Screenshots are in /tmp/claude-0/-home-user-deb-antigravity-claude-workspace/2792bc90-e2ed-5c8a-b9c2-eaf4b7567fa4/scratchpad/eye3/. Full-page shots are named `{ed}-{device}-{page}.png`. The contact sheets I read are in `sheets/`, and viewport and flow shots are in `vp/`.
- Expected on staging and not reported: "[Test data]" titles, and dry-run delivery (`"delivery":"dry_run"`) with an on-screen success message.
- Reviewer: independent. I did not read the site's source code or tests.

## Previous defects re-checked

| # | Defect (round) | Status | Evidence |
|---|---|---|---|
| B1 | "Live" jobs opened as "This role has closed" (r1) | Fixed | 0 of 218 job pages say closed. No closing date is before 21 Nov, and the API shows 0 past closing dates. |
| B2 | UK cards linked to worker URLs that returned 404 (r1) | Fixed | 394 URLs crawled on each host, 0 non-200 except the intended 404s. Every card links to pages.dev. |
| B3 | Frozen snapshot and contradictory counts (r1) | Fixed | IE shows 141 roles, 27 disclosed (19%) and a median of €61.4k on home, salary explorer, dashboard and footer. UK shows 77 roles, 47 disclosed (61%), a median of £50k and 18 employers. The bands sum to 27 and 47, and the sector cards match the explorer medians. |
| M1 | Every role shown as "Today" (r1) | Fixed | Cards show real ages (Today to 1 mo ago). Dashboard: new this week 15 / 9, closing within 7 days 6 / 10. |
| M2 | Alert sign-up said "coming soon" (r1) | Fixed | All 6 runs got 202 and the message "Check your inbox: we have sent you a link to confirm this alert. Nothing is sent until you confirm." (vp/*-alert-done.png) |
| M3 | Links to old .asp pages or Strategies (r1) | Fixed | There are 0 `.asp` or strategies links on either host. External hosts are limited to the network sites, gaiatalent.com, Facebook and X. |
| M4 | Salary explorer degraded, and sterling shown as € (r1) | Fixed | IE has 6 sector medians, and £ roles show "≈ €" alongside. UK € roles show "≈ £". |
| M5 | IE "Similar roles" section empty (r1) | Fixed | It shows 4 cards on every job page viewed. |
| M6 | Listing quality score skewed to 1–2 of 4 (r1) | Fixed | IE is 0/0/53/59/29 and UK has 30 at 3 of 4 and 47 at 4 of 4. |
| m1 | Footer reads "Demo redesign, not the live site." (r1) | Fixed | The footer now reads "© 2008–2026 GreenJobs Ltd." on every page, the 404 page included. |
| m2 | Phone tap targets under 44px (r1) | Partly fixed | Breadcrumbs are now 44px tall, form inputs 48px, the consent box 24x24 and region rows 40px. Still under 44px: Filters/List/Map/Saved (40px tall), card Save icons (40x40), job title links (21–42px), "Show as table" (92x36) and the network links on employers (20px). |
| m3 | Odd UK locations (r1) | Improved | Locations are now plain lists, e.g. "Central London, Manchester". A few multi-region strings from the source feed remain, e.g. "West Yorkshire, Scotland". |
| m4 | Arborist description broken mid-sentence (r1) | Fixed | /ie/jobs/11498685/ reads continuously. JSON-LD is valid on all 218 pages. |
| m5 | Gaia "G" initial in place of the logo (r1) | Fixed | The logo shows on cards in both editions. |
| N1 | Apply form returned 405/403, so nobody could apply (r2) | Fixed, without a CV | The POST to the worker `/api/apply` returned 201 `{"status":"received","delivery":"dry_run"}`. The message was "Application received. Thank you: it is on its way to the advertiser." Re-submitting returned 200 `already_received` with "We already had it, so nothing was sent twice." Attaching a CV still fails: see R3-1. |
| N2 | Apply form had no layout styling (r2) | Fixed | Labels sit above full-width inputs, inputs are 48px and the submit button is full width (vp/*-applyform.png). |
| N3 | Text cut off on iPhone 14 (r2) | Fixed | The page is 390/390 wide on every iPhone page, job pages included. |
| N4 | "Apply on greenjobs.ie" label scrolled to the in-page form (r2) | Fixed | The button now reads "Apply now →". |
| N5 | Sticky bar covered the end of the footer (r2) | Fixed | The footer's IE/UK switch and social icons sit above the bar at the end of the page (vp/S3.png). |
| N6 | Dashboard linked to /for-keith/, which returned 200 (r2) | Fixed | The dashboard has no Keith link. /ie/for-keith/ and /uk/for-keith/ return 404 on both pages.dev hosts and both worker hosts. |
| N7 | Dot-plot unreadable on phones (r2) | Fixed | Labels are readable now, with "Swipe sideways to see the whole range" (vp/uk-iphone14-dotplot.png). |
| N8 | Past deadlines in descriptions contradicted the header (r2) | Fixed | 0 of 218 descriptions quote a 2026 date before 21 Nov. Ham Wall no longer has "19th October". |
| N9 | Gaia page said "as published on greenjobs.ie", and "0 similar roles" was a headline (r2) | Fixed | It now says "Description as published on gaiatalent.com" and "No other live roles like this within Roscommon right now." |

## New defects

| # | Page | Device | Edition | Severity | Observation | Screenshot |
|---|---|---|---|---|---|---|
| R3-1 | Job page apply form (all 165 email-apply jobs) | all | IE + UK | **major** | The form offers "CV (optional, PDF or Word, up to 5 MB)". When a PDF is attached, the server returns **503 `{"error":"cv_storage_unavailable"}`**. The field turns red with "CV uploads are not available yet." and the form says "Remove the CV and send again." Most candidates attach a CV, so the first attempt fails for them. The site advertises "one-tap applications", but those candidates have to retry without their CV. Fix: switch CV storage on, or hide the field until it works. | vp/ie-pixel7-apply-submitted-form.png, vp/*-apply-submitted.png |
| R3-2 | Worker-hosted job pages (`…workers.dev/ie/jobs/<id>/`, `…-uk…/uk/jobs/<id>/`) | all | IE + UK | **major** | These pages return 200 but have no styles and no scripts. Every CSS and JS file 404s or is served as `application/json`, which causes 15 console errors. Submitting the apply form there leaves the visitor on a raw JSON page reading `{"error":"invalid_ts"}` (400). Each page's canonical tag points to itself. No pages.dev page links to them, but the brief says job pages are served via these hosts, and anyone with an old or shared link sees a broken page. Fix: redirect them to the pages.dev URL, or return 404. | vp/ie-worker-apply.png, vp/uk-worker-apply.png |
| R3-3 | Job page, after a successful application | phones + laptop | IE + UK | minor | After "Application received" the form stays filled and "Send application" is still active. The sticky bar still says "Apply now". A second press is caught by the server ("already_received"), but nothing on the page shows that the job is done. | vp/uk-iphone14-apply-after-submit.png |
| R3-4 | Job page breadcrumb | phones | IE + UK | minor | The "/" separators in "Home / Jobs / Sector" sit raised above the text baseline. | sheets/ie-iphone14-job-email-0.png, sheets/ie-pixel7-job-link-0.png |
| R3-5 | Footer "Explore" list, every page | all | IE + UK | minor | "Jobs" is indented about 8px compared with Sectors, Salary explorer, Career compass and Employers. | sheets/ie-pixel7-home-1.png, sheets/uk-pixel7-compass-0.png |
| R3-6 | Edition switch, cross-host | all | IE + UK | minor | Each pages.dev host serves both editions. The IE/UK switch on greenjobs-stg-ie.pages.dev goes to greenjobs-stg-ie.pages.dev/uk/, which has its canonical on the IE host, and the reverse happens on the UK host. Visitors switching edition stay on the other edition's host, so there are two URLs for every page. Staging is noindex, so this needs confirming only for the production domains. | crawl output |
| R3-7 | UK job description, Ham Wall (/uk/jobs/11502133/) | all | UK | minor | The published text says "click the apply button. You will be taken to a simple CHM Recruit form", but Apply opens the in-page GreenJobs form. This is employer copy that conflicts with the flow. Confirm which apply route the client wants for agency jobs. | sheets/uk-laptop-job-email-1.png |

Severity counts (new): blocker 0, major 2, minor 5.

## Verified fine

- **Overflow and images:** No page is wider than the viewport on any page, device or edition (document width equals viewport width in every run). No broken images.
- **Console and network:** The only errors on pages.dev are the expected 404s on the 404 and /for-keith/ pages and the CV 503 (R3-1). No failed requests, and the API returns 200, 201 or 202.
- **Cookie banner:** It shows on first load on all 6 runs ("essential storage only… No tracking", with Accept and Settings) and is dismissed after Accept. On iPhone 14 it covers the stats pill until dismissed, which is expected.
- **Home:** It matches the approved design on all devices: photo or video hero, search, stats pill, B Corp card, latest roles, sector cards with sparklines, salary insight, UK region map, Why GreenJobs, network chips, logo wall with Pause, alert form and footer. The "Hiring this week" badges match employers with live roles (UK: Arup, Mattinson, NRW, Ofwat, Welsh Government).
- **Jobs list:** Search "ecolog" gives 22 of 141 (IE) and "engineer" gives 16 of 77 (UK), and both write `?q=` to the URL. The sector filter gives 41 of 141 (Environmental science) and 18 of 77 (Policy). It matches the sector cards and works through the phone Filters drawer with "Show results". The filter chip can be removed.
- **Link-apply:** On IE Gaia "Ecologist" (/ie/jobs/gaia-9360/), "Apply on gaiatalent.com" opens https://gaiatalent.com/jobs/ecologist/.
- **Email-apply without a CV:** It works on both editions and all devices. The success message is visible on phones above the sticky bar, and a second submit does not send twice.
- **Numbers between pages:** IE: 141 / 27 / 19% / €61.4k / 15 sectors / 17 counties, and Gaia 116 of 141 = 82%. UK: 77 / 47 / 61% / £50k / 14 sectors / 18 employers, and Mattinson 32 of 77 = 42%. Home, list, explorer, dashboard, employers and footer agree with each other and with `/api/stats`.
- **Sectors, employers, salary explorer, career compass, dashboard:** They render cleanly on every device. Charts have "Show as table".
- **404:** "Nothing grows here." with IE and UK edition cards, status 404. /ie/for-keith/ and /uk/for-keith/ return 404 everywhere.
- **Wording:** No demo, Keith, lorem, TODO or staging text is visible on any page. The dashboard "Measures to come" section is intentional KPI documentation.
- **Contrast:** I checked by eye on every sheet and found no low-contrast text.
