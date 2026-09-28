# GreenJobs redesign — final acceptance (trace3), 2026-09-28

Target: https://greenjobs-redesign.pages.dev/ (live host answers 200 to curl, but Chromium behind the proxy fails TLS on it — `ERR_CERT_AUTHORITY_INVALID`; the identical build in `deliverables/greenjobs_redesign_2026-09-22/site` was served on http://127.0.0.1:8805 and tested there). Playwright/Chromium 1194, viewports 1440×900 and 390×844, light and dark. Screenshots in `.tmp/trace3/shots/` (70 files); readable crops in `.tmp/trace3/crops/`; raw functional log in `.tmp/trace3/func.log`.

Note on full-page shots: the cookie bar appears mid-page in every full-page capture. That is a capture artefact (the bar is `position:fixed; transform:translateY(110%)`, class `cookie` without `is-on`, so it is off-screen in a real viewport — verified in `f_reducedmotion_home_1440.png` and `home_390_l.png`). Not logged as a defect.

## Part 1 — Visual

| Page | Viewport / theme | Sev | Description | Screenshot |
|---|---|---|---|---|
| Mobile nav menu (all pages) | 390 light+dark | P2 | The IE/UK edition switch inside the slide-in menu inherits `.menu a` (Fraunces 1.6rem, padding, border) so the active pill is a tall black oval overlapping "IE" with "UK" jammed against it; the wordmark in the menu also renders as serif "Green Jobs" instead of the header wordmark. Looks broken on the very first tap a phone user makes. | f_menu_390.png |
| Footer (every page) | 1440/390, both | P2 | Two empty circle buttons where social icons should be (no glyph, no label visible). Reads as unfinished. | insights_1440_l.png (crop _1), employers_1440_l.png |
| Employers (IE + UK) | 1440/390, both | P2 | "Audience and reach" has three placeholder lines: "Monthly visitor figures are published at launch", "Subscriber numbers are published at launch", "Network and follower numbers are published at launch"; UK adds "Client testimonials are being collected for launch". Whole section is a promise, not a proposition. | employers_1440_l.png, uk_employers_1440_l.png, employers_390_d.png |
| Subscribe dialog + home/employers alert forms | 1440/390, both | P2 | Info box "Alerts open when the new site launches." shown before the user does anything, and again after submit. Placeholder wording on a public page. | subscribe_1440_l.png, subscribe_390_d.png, f_subscribe_submitted_1440.png |
| Employers (IE) | 1440 light | P3 | "Organisations recruiting through GreenJobs" marquee has only 3 logos (Commonland, Gaia Talent, Mattinson) repeated twice in view — duplication is obvious. UK strip is fine. | employers_1440_l.png |
| Sectors | 1440 light | P3 | Treemap: five small tiles carry no label at all (Waste, Renewable, Climate, Wind, and the Energy networks tile is truncated "Energy networks…", "Sustaina… & ESG"). Legend below saves it, but the tiles themselves are mute. | sectors_1440_l.png |
| Home | 390 light+dark | P3 | Hero sun/moon disc sits behind the right edge of the "88 live green roles…" pill; the pill clips the disc. | home_390_l.png, home_390_d.png |
| Home (reduced motion) | 1440 light | P3 | With `prefers-reduced-motion` the illustrated hero is replaced by a photographic wind-farm background — a different brand look for those users, not just a stiller one. | f_reducedmotion_home_1440.png |
| Job page (all) | 1440/390 | P3 | Tag says "Full Time" (from the listing) while the aside says "Contract: Full-time"; "Type" chip on lists uses "Full Time"/"Permanent" mix. Minor but visible side by side. | job_ie_gbp_1440_l.png |
| Jobs list vs cards | 1440 vs 390 | P3 | Level chip ("Mid-level") shows on home/mobile cards but not on the desktop list rows for the same roles (e.g. Labs Designer). | jobs_1440_l.png vs jobs_390_d.png |
| Compass result | 1440/390 | P3 | "100% match" for Wind energy driven by a single role; all three results are energy sectors for an all-A answer set — fine, but the "Your result lives in this link" line prints the raw URL in monospace, which looks like debug output. | compass_result_1440_l.png |
| 404 | 1440 light | — | OK: "Nothing grows here." with edition picker. (Local http.server serves its own 404; on Pages `404.html` is used.) | notfound_1440_l.png |
| Dark theme | 1440/390 | — | OK across home, jobs, map, job pages, employers, dashboard, insights, compass, landing. Cookie bar and dialogs adapt. | *_d.png |
| Map view + side list | 1440/390 | — | OK: counts on regions at 1440, count table at 390, "Not on the map: Elsewhere (UK & abroad) (23)" link. | jobsmap_1440_l.png, jobsmap_390_d.png |
| Filter sheet | 390 dark | — | OK: rail moves into the sheet, "Show results" sticky, closes and returns rail. | filtersheet_390_d.png |
| Cookie bar/settings | 1440/390 | — | OK. | cookie_1440_l.png, cookiesettings_390_d.png |
| Package table + ad preview | 1440/390 | — | OK; at 390 the table stacks per row. Preview card and page-top preview update live. | employers_1440_l.png (crop _1), adpreview_*.png, f_adpreview_filled_1440.png |

**Verdict (visual): not accepted as-is.** 0×P1, 4×P2 (mobile menu switch, empty social icons, "at launch" placeholders on Employers, subscribe placeholder), 7×P3. Fix the four P2s and it passes.

## Part 2 — Functional

| Flow | Viewport / theme | Sev | Description | Screenshot / evidence |
|---|---|---|---|---|
| Hero search "ecologist" + "Galway" | 1440 light | P3 | Works: 3 roles (Senior Ecologist ×3 variants), chips "Search: ecologist", "Where: Galway". But the form action is `jobs/index.html`, so the URL becomes `/ie/jobs/index.html?q=ecologist&loc=Galway` rather than `/ie/jobs/?…` — ugly to share and depends on the host redirecting. | func.log SEARCH |
| Edition switch keeps the page | 1440 light | P2 | The header IE/UK links are static: on `/ie/jobs/?sector=Water%20%26%20flood` the switch goes to `/uk/jobs/index.html` and drops the filters; on a job page it goes to the UK jobs list (acceptable). Dashboard, employers, sectors keep the page. "Keeps the page" is only true for unfiltered pages. | func.log EDSWITCH |
| Three facets → reload → clear | 1440 light | — | OK: `?sector=…&wp=hybrid&ct=permanent`, 2 of 88, chips persist after reload, form controls restored; Clear resets URL to `/ie/jobs/` and count to 88. (Note: "Type" is a hidden input with no control in the rail; it only exists via URL/chips.) | f_facets_1440.png |
| Save role → reload → Saved tab | 1440 light | — | OK: toast "Saved — find it under Saved on the jobs page", count badge 1, `gj-saved-ie` in localStorage, Saved tab lists the role, URL `?view=saved`. | f_saved_1440.png |
| Map region → filtered list → Show all | 1440 light | — | OK: Cork → "Cork · 24 roles" + 24 cards; Show all restores "65 of 88 roles sit in 14 mapped regions". URL stays `?view=map` (region pick is not in the URL — arguably fine). | f_map_cork_1440.png |
| Quick job match IE "ecologist dublin" | 1440 light | — | OK: 6 of 88, matched on ecologist/dublin, hits are Principal/Senior Ecologist ×4, Clerk of Works, Arborist. Hash stays empty until "Copy shareable link" → `#fit=ecologist.dublin`, toast "Link copied", share note shown. | f_fit_ie_1440.png |
| Quick job match UK "flood risk engineer Manchester" | 1440 light | — | OK: 6 of 77, all flood-risk/hydraulic roles, first hit in Manchester; pay strip "£39k–£90k; 50% of matches disclose (3 of 6)". Hash untouched. | f_fit_uk_1440.png |
| Job → similar roles → Apply | 1440 light | — | OK: "Similar roles — same sector first, then the same area, then similar pay" (4 cards, relative links). Apply (top and aside) → `https://www.greenjobs.ie/jobs/11500760/cdm-advisor.asp`, `rel=noopener`, `data-ev=apply_click`. | job_ie_gbp_1440_l.png |
| Employers: Request advertising rates | 1440 light | — | OK: `mailto:info@greenjobs.ie?subject=Advertising%20rates%20request` on all three buttons; "Or send your details" is an in-page anchor to the form. | func.log EMP |
| Employers: Preview your vacancy | 1440 light | — | OK: fill title/org/location/salary/bullet → board card and page-top preview update live ("Senior Hydrogeologist test · Acme Water · Cork · €55k–65k"). Submit shows "Preview only. Rates and posting are handled by the GreenJobs team: email info@greenjobs.ie…" — no false "sent". Logo stays on device. | f_adpreview_filled_1440.png |
| Theme toggle persists | 1440 | — | OK: `gj-theme=dark` in localStorage, held across /ie/sectors and /uk/jobs; inline head script prevents flash. | func.log THEME |
| Keyboard-only, jobs page | 1440 light | — | OK: first Tab = "Skip to content"; visible 2px focus ring on links/buttons, box-shadow ring on inputs; rail order is q→loc→sector→wp→smin→smax→level→ct→sal→only→close→emp→sort; Enter in keyword filters (`?q=hydro`, 3 roles). Map regions are `role=button tabindex=0`; Enter on Carlow filters the side list ("Carlow · 11 roles") and the region is highlighted with a tooltip. | f_kbd_map_1440.png |
| Keyboard: reaching the map | 1440 | P3 | 31 Tab presses from page top to the first map region (whole rail first); no "skip to results" landmark link after the rail. | func.log KEYS |
| Reduced-motion emulation, home | 1440 light | — | OK: no `.reveal.pre` gating, marquee `animation: none`, 0 running animations. (See visual P3 on hero swap.) | f_reducedmotion_home_1440.png |
| Cookie bar (fresh profile) | 1440 | — | OK: appears after ~600 ms, Accept stores `gj-consent` with timestamp, hidden after reload; Settings dialog toggles analytics/marketing; `?popup=cookie/settings/subscribe` force switches exist (harmless). | cookie_1440_l.png |
| Subscribe dialog | 1440/390 | P2 (copy) | Submitting an address does not fake a success: note says "Alerts open when the new site launches. Your address has not been stored." — honest, but see Part 1/3 on the wording. Dialog stays open after submit with no close affordance other than × / "Meanwhile, browse all roles". | f_subscribe_submitted_1440.png |
| Jump to… palette (⌘K) | 1440 | — | OK: opens, "hydro" lists role/sector/page matches, Enter navigates. | f_palette_1440.png |
| Mobile filter sheet apply | 390 dark | — | OK: pick sector in sheet → "Show results" → sheet closes, rail returns home, URL `?sector=Environmental%20science%20%26%20consulting`, 23 of 88. | filtersheet_390_d.png |
| Console | all | — | No page errors from the site (the only `localStorage` error is from the test harness on `about:blank`). | shoot.out |

**Verdict (functional): accepted with one P2.** 0×P1, 1×P2 (edition switch drops filters), 2×P3. Everything a jobseeker or employer would actually try works and nothing lies to them.

## Part 3 — Copy (read as Keith)

| Page | Where | Sev | Description | Screenshot |
|---|---|---|---|---|
| Dashboard (IE + UK, public, in nav footer? no — reachable via /dashboard/) | whole page | P2 | Written by the developer: "computed from the live listings at build time", "the analytics provider will report once it is switched on through the cookie consent's Analytics toggle", "Event spec for launch — WIRED AT LAUNCH", "carries a `data-ev` attribute", event names `apply_click`, `job_id`, "(target we propose)". Fine for Keith, not for a public URL; either gate it or rewrite. Also links to the "For Keith" evidence page (noindex, but linked from a public page). | dashboard_1440_l.png (crops _0/_1) |
| Employers (IE + UK) | Audience and reach | P2 | "Thousands of visitors every month" — a number nothing on the site can back; the three "…published at launch" lines and UK "testimonials are being collected for launch" are placeholders. | employers_1440_l.png |
| Home / Employers / Compass / every page | Subscribe + alert forms | P2 | "Alerts open when the new site launches." — reads as a build note. Say what happens instead (e.g. "Alerts are on the current site; sign up there") or drop the box until it works. | subscribe_1440_l.png |
| Salary guide (IE) | How to read these figures | P3 | "21 of the disclosed salaries are advertised in another currency… fixed rate of 1 GBP = 1.17 EUR (set 28 September 2026)" while every other date on the site is the 22 September snapshot; two dates for one dataset. Also 21 of 29 disclosed IE salaries being sterling is worth a plainer sentence — it changes what "median €61.4k for Ireland" means. | salary_1440_l.png (crop _1) |
| Employers ad builder vs salary guide | sector note | P3 | Builder says "Roles in Sustainable infrastructure & transport this week: 33; median disclosed: €72.5k (1 of 33 publish one)" — a "median" of one salary; the salary guide shows "—" for the same sector because it needs 3+. Same number, two rules. (Same for Environmental engineering €75k, Waste €75k, Climate €77.5k from 1 role each in the builder's `data-reach`.) | adpreview_1440_l.png (crop _2), salary_1440_l.png |
| Landing "Ecology jobs in Ireland" | intro + cards | P3 | Title says Ireland; 5 of the 12 cards are London / West Midlands / Scotland roles in sterling (CDM Advisor, Principal Designer, Landscape Planning Director, BNG Consultant). Intro says "Roles span 6 counties, led by Dublin, Cork". Keith's rule keeps UK roles on the board, but on a page called "…in Ireland" it jars; a CDM Advisor tagged as ecology is also a classification miss. | landing_1440_l.png |
| Job page (all) | closing line | P3 | "Posted 16 September 2026 · closes 28 October 2026 Description as published by the employer on greenjobs.ie; reference 11500760." — missing full stop/separator before "Description". | job_ie_gbp_1440_l.png |
| Job page 11500760 | similar roles lead-in | P3 | "12 similar roles with the same location tag (Elsewhere (UK & abroad)) — see them" — nested brackets, "location tag" is system vocabulary. | job_ie_gbp_1440_l.png (crop _0 bottom) |
| Guides (IE + UK) | intro | P3 | "Last updated: Snapshot of 22 September 2026." — two labels for one date. "More guides follow as the data grows." is fine. | guides_1440_l.png |
| Home IE vs UK | section headings | P3 | Same section is "Employer proposition" / "Employers on the GreenJobs network" (IE) and "Employers and advertising" / "Employers hiring now" (UK); nav says "Salary explorer", page h1 "Green salary explorer", home card "Salary insight", guides "Green salary guide". Pick one name per thing. | home_1440_l.png, uk_home_1440_l.png |
| Jobs list / job page | contract wording | P3 | "Full Time" (tag) vs "Full-time" (aside) vs "Permanent"; "Home Based" vs "Remote" as workplace values. | jobs_1440_l.png, job_ie_gbp_1440_l.png |
| Compass result | footer line | P3 | "Your result lives in this link: http://…/#a=0.0.0.0.0.0.0" — the raw hash reads like debug; "Loosened the career-stage filter to find these." is developer phrasing. | compass_result_1440_l.png |
| Footer | strap | P3 | "© 2008–2026 GreenJobs Ltd. Demo redesign, not the live site." — correct for a demo; must go before launch (listed so it is not forgotten). | any footer |
| Dashboard IE | Top employer share | P3 | "Gaia Talent holds this share of live roles across 3 employers" — true to data but the IE board having 3 employers is a fact Keith will read as a bug; consider suppressing the tile below a threshold. | dashboard_1440_l.png |
| Numbers that trace | — | — | Verified against data/HTML: 88/77 live roles, 14 sectors (14 with ≥1 role), 10 network sites (10 domains listed), 14 counties / 10 regions on maps, 29/47 disclosed, medians €61.4k/£50k, 18 UK employers, landing counts 12/48/4/7 and 17/32/8/9, snapshot 22 Sept. "Up to ten job alerts", "since 2008", "1% for the Planet", B Corp, phone numbers and Ennis address are carried over from the live site. | — |

**Verdict (copy): not accepted as-is.** 0×P1, 3×P2 (developer-voiced dashboard on a public URL, unbacked "thousands of visitors" + "at launch" placeholders, "Alerts open when the new site launches"), 11×P3.

## Overall

P1: 0 · P2: 8 · P3: 20. No blocker; the P2s are a day's work (mobile-menu CSS scope, footer social icons, edition switch carrying the query, and four pieces of placeholder/developer copy). Recommend fixing the P2s and re-running `func.js` + a 390 menu shot before sign-off.
