# GreenJobs staging: human-eye review, round 2 (2026-11-20)

**Verdict: FAIL.** 1 blocker, 2 majors, 7 minors (new). Of the 14 defects from round 1, 10 are fixed and 4 minors remain.

- Staging boards: https://greenjobs-staging-ie.pages.dev/ie/ (141 live roles) and https://greenjobs-staging-uk.pages.dev/uk/ (77 live roles). Job pages are now served from pages.dev. The worker hosts (`greenjobs-platform-staging[-uk].debanjan186.workers.dev`) serve the API and an alternative copy of each job page.
- Approved design used for comparison: https://greenjobs-redesign.pages.dev/ie/ and /uk/
- Browsers: Playwright Chromium, with a fresh context for each edition and device. Devices were Pixel 7, iPhone 14 and a 1440x900 laptop, all at deviceScaleFactor 1. Every page was scrolled from top to bottom.
- Pages covered on each edition and device: home, cookie banner, alert sign-up (submitted), jobs list, keyword search, sector filter, 3 or 4 job pages (email-apply and link-apply, with the apply form opened and submitted), sectors, employers, salary explorer, career compass, dashboard and 404. Every job card link (141 IE and 77 UK) and every job page was also fetched over HTTP.
- Screenshots are in /tmp/claude-0/-home-user-deb-antigravity-claude-workspace/2792bc90-e2ed-5c8a-b9c2-eaf4b7567fa4/scratchpad/eye2/. Full-page shots are named `{ed}-{device}-{page}.png`, viewport-by-viewport scroll shots are in `vp/` and the contact sheets I read are in `sheets/` and `vp/sheets/`.
  - Full-page shots leave scroll-reveal sections blank. I checked those against viewport shots and they render correctly, so they are not reported as defects.
- Test data: titles starting "[Test data]" and the dry-run alert email are expected and are not reported as defects.
- Reviewer: independent. I did not read the site's source code or tests.

## Round 1 defects re-checked

| # | Round 1 defect | Status | Evidence |
|---|---|---|---|
| B1 | Every "live" job opened as "This role has closed", with no Apply button | **Fixed** | 0 of 218 job pages say closed, and none has a closing date before 20 Nov. Every page has an Apply control: an in-page form on 88 IE and 77 UK pages, and gaiatalent.com on 53 IE pages. Apply itself fails, though: see N1. |
| B2 | 21 UK cards linked to worker URLs that returned 404 | **Fixed** | All 141 IE and 77 UK card links point to pages.dev and return 200. |
| B3 | Frozen 22 Sep snapshot mixed with live figures, and contradictory counts | **Fixed** | IE shows 141 roles, 27 disclosed (19%) and a median of €61.4k on home, salary explorer, dashboard and footer. UK shows 77 roles, 47 disclosed (61%), a median of £50k and 18 employers on every page. No "22 September" text remains. The bands sum to the disclosed counts (27 and 47). |
| M1 | Every role shown as "Today", and dashboard numbers wrong as a result | **Fixed** | Cards show real ages (4 days ago to 3 mo ago). Only the job actually posted on 20 Nov shows "Today". Dashboard: new this week 15 (IE) / 9 (UK), closing within 7 days 6 / 10, advertised window 44 / 35 days. All of these match the API. |
| M2 | Alert sign-up said "coming soon" | **Fixed** | The form POSTs to `/api/alerts`, which returns 202 `next:check_email`. The page then shows "Check your inbox: we have sent you a link to confirm this alert." This was checked on all 6 runs. |
| M3 | Apply and advertising links went to the old greenjobs .asp pages or Strategies | **Fixed** | No `.asp` or strategies links remain on any page or job page. The logo wall goes to /employers/. The UK "Request advertising rates" button is a mailto link. |
| M4 | Salary explorer degraded, and sterling shown as € | **Fixed** | IE shows 27 roles across 6 bands and 6 sector medians. Sterling roles show £ with "≈ €" alongside. |
| M5 | IE "Similar roles" section was empty | **Fixed** | IE job pages show 4 similar-role cards. |
| M6 | Listing quality score skewed to 1–2 of 4 | **Fixed** | IE scores are 0/0/53/59/29 (0 to 4 of 4). UK scores are 3 of 4: 30, and 4 of 4: 47. |
| m1 | Footer reads "Demo redesign, not the live site." | **Still present** | It is on every page of both editions, the 404 page included (e.g. vp/sheets/ie-pixel7-home-2.png). |
| m2 | Phone tap targets under 44px | **Still present** | The IE/UK switch is 29x40 and 36x40. Breadcrumb links are 23px tall. The apply-form inputs are 32px tall and the consent checkbox is 13x13. |
| m3 | Odd UK locations | **Still present** | Examples: "West Yorkshire, Scotland (nationwide)" (3 roles), "London Central, West Yorkshire, England" (4) and "Gaia Talent · Dublin, United Kingdom (UK)". |
| m4 | Description paragraph broken mid-sentence | **Still present** | IE [Test data] Arborist (/ie/jobs/11498685/) breaks after "…provide joined-up arboricultural and". |
| m5 | Gaia Talent cards on UK showed a "G" initial in place of the logo | **Fixed** | The Gaia logo now shows on UK cards (uk-laptop-home sheet). |

## New defects

| # | Page | Device | Edition | Severity | Observation | Screenshot |
|---|---|---|---|---|---|---|
| N1 | Job page apply form (every email-apply job: 88 IE, 77 UK) | all | IE + UK | **blocker** | I filled in name, email, phone, cover note, CV and consent, then pressed "Send application". The form POSTs to `https://greenjobs-staging-{ie,uk}.pages.dev/api/apply`, which returns **405**, and the form shows "**Not sent (405). Please check the form and try again.**" The worker's copy of the same page posts to the worker `/api/apply` and gets **403 `{"error":"origin_not_allowed"}`**, and the browser is left on a raw JSON page. A candidate cannot apply to any role except the 53 IE Gaia roles, which link out to gaiatalent.com. It is not a dry-run effect: the server rejects the request before any send logic. | ie-laptop-apply-submitted.png, uk-pixel7-apply-submitted.png, sheets/flows-pixel7.png, sheets/flows-laptop-1.png |
| N2 | Job page apply form | all (worst on phones) | IE + UK | major | The form has no layout styling. Labels sit to the right of the previous input, so "Name [input] Email" share one row and "Phone" and "Cover note" float beside the wrong inputs. "CV (PDF or Word)" wraps away from its control. Inputs are browser-default 32px boxes and the consent checkbox is 13px. The core conversion form looks broken next to the rest of the page. | vp/sheets/ie-pixel7-job1-0.png, sheets/ie-laptop-job1-s0.png, sheets/flows-pixel7.png |
| N3 | Job pages (description) | iPhone 14 | IE + UK | major | The `article`/`.prose` block is 394px wide on a 390px viewport. The layout viewport widens to 394px and the right edge of the description text is cut off, e.g. "welcoming ove…", "Avalon Marshe…", "management plan" → "plan" clipped, "ecologica…". It reproduced on all 3 job pages measured. Pixel 7 (412px) is not affected. | vp/sheets/uk-iphone14-job1-0.png |
| N4 | Job page Apply button and sticky phone bar | all | IE + UK | minor | On email-apply jobs the main CTA reads "Apply on greenjobs.ie" / "Apply on greenjobs.co.uk", but it only scrolls to the in-page form. The label suggests a hand-off to the old site. | vp/sheets/ie-pixel7-job1-0.png |
| N5 | Job pages, footer | phones | IE + UK | minor | The sticky "salary + Apply" bar stays over the last ~60px of the footer at the end of the page and covers the social icons and the IE/UK switch. | vp/sheets/ie-pixel7-job1-1.png |
| N6 | Dashboard, "Back to the evidence page" | all | IE + UK | minor | The button links to `/ie/for-keith/`, an internal pitch page addressed to a named person. That page returns 200 on both staging hosts. | vp/sheets/ie-laptop-dashboard-1.png |
| N7 | Job page "Where this role sits" chart | phones | IE + UK | minor | The dot-plot scales down to about 4px labels on a 412px or 390px screen and cannot be read. "As a table" is the only usable view. | vp/sheets/ie-pixel7-job1-0.png |
| N8 | Job descriptions vs page header | all | IE (1) + UK (4) | minor | The body text quotes a past deadline while the header says the role is open. Examples: UK Site Manager – Ham Wall has "Closing date: 23:59, Monday, 19th October 2026" against "closes 17 December 2026". UK Labs Designer has "before 5 October 2026" against "closes 3 December". This looks like test fixtures with shifted dates. Confirm that the live feed's closing dates are not shifted the same way. | vp/sheets/uk-iphone14-job1-0.png |
| N9 | Gaia (link-apply) job page | all | IE | minor | The page says "Description as published by the employer on greenjobs.ie", but the role comes from and applies on gaiatalent.com. "**0** similar roles within Roscommon" is shown as a big-number headline. | vp/sheets/ie-pixel7-job2-0.png |

## Verified fine

- **Overflow:** No horizontal page scroll on any page, device or edition, apart from the 4px job-page overflow on iPhone 14 (N3). The logo marquee overflows by design inside its clipped track.
- **Console and network:** The only console errors are the 405 on apply (N1) and the expected 404 on the 404 page. All API calls return 200 or 202. No images are broken.
- **Cookie banner:** It appears on first visit on every device, says "essential storage only, no tracking" and offers Accept and Settings. It is dismissed after Accept and does not reappear on later pages.
- **Home (IE and UK, all devices):** It matches the approved design: photo hero, search, stats pill, B Corp card, latest roles, sector cards with sparklines, salary insight cards, the UK region map with counts summing correctly (plus 13 UK-wide), Why GreenJobs, the network list, the logo wall with Pause, and the alert form.
- **Jobs list:** The filter rail on laptop and the bottom-sheet Filters drawer on phones both work, with "Show results". Search "ecolog" gives 22 of 141 (IE) and "engineer" gives 16 of 77 (UK). The sector filter gives 41 of 141 (IE) and 20 of 77 (UK). Filters are written to the URL. Salary currency follows the edition (EUR on IE, GBP on UK).
- **Link-apply job (IE Gaia Ecologist):** "Apply on gaiatalent.com" points to https://gaiatalent.com/jobs/ecologist/.
- **Sectors, employers, salary explorer, career compass, dashboard and 404:** They render cleanly on all devices, and the figures agree with each other and with the API. The 404 page returns status 404 and shows "Nothing grows here." with links to both editions.
- **Contrast:** I checked by eye on every sheet and found no low-contrast text. The automated contrast pass could not parse the site's oklch colours, so it gave no usable result.
- **Old hosts:** No link or Apply button anywhere goes to greenjobs.ie/.co.uk `.asp` pages or a Strategies host. The footer links to the plain greenjobs.ie and greenjobs.co.uk home pages only.
