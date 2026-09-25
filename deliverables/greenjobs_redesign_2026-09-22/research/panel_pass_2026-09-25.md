# Panel pass — GreenJobs redesign demo (2026-09-25, pre-delivery)

Roster: `.claude/memory/panel_roster.md` plus chair Steve Jobs, Mira Murati, Nick Saraev, Alex Hormozi as briefed. Findings only; no site files were edited.

## Method (what was actually measured)

- Served `site/` on `:8743`; headless Chromium (Playwright 1194) captured **both editions** (IE, UK) × {index, jobs, one job page, insights, employers, sectors, compass} × {1440, 390} × {light, `?theme=dark`} = 56 page captures, plus job-row hover (1440) and tap (390), JS-off (6 pages), `prefers-reduced-motion`, empty search state, scrolled home film frames. All PNGs in `/tmp/gj/` (session-local).
- Static: link/asset crawl of all 202 HTML files; grep for `#d99a1c`/honey, banned vocabulary, B Corp usage; byte counts; contrast ratios from the tokens in `src/css/styles.css`; `tests/greenjobs_redesign/test_build.py` (86 pass) and `src/js/lib.test.js` (19 pass).
- GLM 5.3 lens via Baseten (`zai-org/GLM-5.3`, 200 OK; token read from the upload `.env` and not recorded).

### Brand-mark and honey check (asked explicitly)

- **Mark**: header, footer and menu use one inline SVG, bare leaf `#1f7a3d` with `#d6efdb` veins; `assets/favicon.svg` is the identical path set; `manifest.webmanifest` points at the same favicon. Consistent in all 56 captures. Pass.
- **Honey `#d99a1c`**: zero occurrences in `src/templates`, `src/css`, `src/js`, built HTML, favicon or manifest. `--honey*` names survive only as aliases of `--brand*` (`styles.css` line 11) — 18 selectors still reference them. Cosmetic debt, not a colour leak. The only warm-yellow left is the hero sun (`--sun`-like `#e8b04a` disc) — allowed by the review brief.

### Numbers (Karpathy's table, both editions)

| Metric | IE | UK | Note |
|---|---|---|---|
| Home requests / transfer, 1440 | 15 / 1.84 MB | 17 / 1.87 MB | 1.5 MB is `hero/*.mp4`; without video ≈ 330 KB |
| Home requests / transfer, 390 light | 16 / 1.94 MB | 18 / 1.79 MB | desktop `ie.mp4` is *also* requested then aborted (`REQ-FAIL`) — double fetch on phones |
| Home transfer, 390 dark | **3.33 MB** | **3.19 MB** | both mp4 sources fully downloaded on the second visit |
| Jobs page transfer | 535 KB (HTML 283 KB, embedded dataset) | 589 KB | HTML alone is 1.5× the whole old home page budget |
| Job page transfer | 260 KB | 260 KB | — |
| CSS shipped | 73,630 + 5,589 = 79,219 B | | spec §5 said ≤ 60 KB; validator raised to 80 KB — 1 KB headroom |
| JS shipped (all files) | 183,482 B | | validator budget 125 KB; per-page load is lower but the aggregate is over the spec's 60 KB by 3× |
| Broken internal links / assets | 0 / 202 pages | 0 | crawl of every `href/src/poster` |
| Horizontal overflow at 390 | none (scrollW 390/390 on all 14 pages) | none | |
| `<h1>` count | 1 on every page | 1 | |
| JS errors / console errors | 0 | 0 | |
| Pages with a failing check (this pass) | 5 of 7 page types (home: video under reduced motion + double mp4; jobs: JS-off blank, subscribe dialog clipped at 390; job: "Comphensive" salary text; employers: stray space, empty social icons; all: cookie banner) | same | see fix list |

Contrast (WCAG 2.x, computed): ink/paper 13.4; ink-2/paper 6.8; ink-3/paper 5.3; brand link on paper 4.7; white on `--brand` 5.4; **white on `--brand-2` 3.85** (top of the primary button gradient — below 4.5 for the 15 px label; passes only as "large/bold"); terracotta italic on paper 3.7 (display size, OK); dark theme fg-2 on dark-2 8.4. One real AA risk: the primary button top half.

---

## Chair — Steve Jobs (beauty, taste, gasp test)

What gasps: the home film. Map → Pay → Sectors pinned sequence at 1440 (`ie-home-scroll-2400/4800.png`) is the best thing here — dot-field Ireland lighting up county by county, then 88 dots reforming into a sector cloud. Fraunces headlines with one terracotta italic word is a real voice. The jobs empty state ("No roles match" + four live sector chips) is better than most shipping boards. Dark mode is coherent, not inverted.

What is mid, and therefore not allowed:
1. **A cookie banner on a demo with no cookies.** Black bar, 80 px, on every page, in every screenshot the client will see, saying "No tracking." If there is nothing to consent to, there is nothing to show. It sits on top of the treemap, the salary chart, the compass answers and the job rail. Kill it, or fire it once on the root chooser only.
2. **The header carries "Certified B Corporation" as a nav item.** A certification badge sitting between "Employers" and the edition switch reads like a fifth menu entry. The footer has it. The hero card has it. Three times on one page is one less than clutter.
3. **The lockup "GreenJobs ᴵᴱ"** — a 10 px "IE"/"UK" floating subscript after the wordmark, then the same IE/UK pill 800 px to the right. Two edition signals in one header line. The pill is the real one; drop the subscript.
4. **Footer social links are empty circles** (`○ ○`) — the SVG is a placeholder ring with no glyph, on 202 pages. Unfinished on the one row every client looks at.
5. **Mobile hero stacks three green pills**: "Find jobs", "Post a job", "Find a job ↓" within 600 px (`ie-home-390-top.png`). Two of them say the same thing. One primary per screen.
6. **Mobile hero sun disc sits behind "payroll"**, half-eclipsed by the italic — reads as an accident at 390, deliberate at 1440. Move it off the type on narrow widths.
7. Job page fact rail shows **"Salary — Comphensive benefits package"** (employer's typo, rendered as a fact). Either normalise to "Not disclosed" when no number parses, or show the text under a "Notes" label, never under "Salary".
8. Salary chips mix units on one list: "€5.1k–6k/mo" beside "€62k–67k". Annualise at the chip; keep the monthly on the job page.

**Honest gaps**: I judged from screenshots, not on a retina phone in hand; the film sequence was seen only at 1440; no client has seen this pass.

## Greg Brockman — reliability, unattended, every link works

- Crawl: 0 broken hrefs/assets across 202 pages, both editions; edition switch preserves path on all seven page types; job pages exist for all 88 IE + 98 UK entries. Zero JS or console errors in 56 captures.
- Build reproducibility: `build_site.py --edition both` + validator + 86 Python and 19 node tests, all green on this checkout.
- Failure found: **`?theme=dark` writes to localStorage** (`_shell.html` inline script). Any shared link carrying `?theme=dark` silently flips the recipient's theme for good. Capture-only parameters must not persist.
- Mobile fetches both hero sources: `<source media="(max-width:799px)">` ordering is right, but the log shows `ie.mp4` requested and aborted at 390 and both files fully loaded on the dark repeat (3.3 MB). Preload metadata on two sources is triggering the double fetch; `preload="none"` + JS `load()` after viewport check would fix.
- Subscribe dialog fired on `/ie/jobs/` at 390 within ~10 s (`ie-jobs-390-filters.png`) although `README` says never on jobs pages; the condition is "while typing", which a browsing user is not doing. It covers the list.
- `.cookie` banner reappears on every context (expected — no consent stored), but it means every fresh visitor sees it before the product.

**Honest gaps**: no 30-day unattended run (static site, so the risk is deploy scripts, which were not executed here); `publish_gh_pages.sh` / `deploy_cloudflare.sh` unverified this pass; the Filters bottom-sheet at 390 could not be opened by the probe (ambiguous "Filters" text match) so it is unverified.

## Dario Amodei — honesty and legal exposure

- Banned words on public pages: "Claude", "lorem", "TODO", "WordPress", "GLM", "Kimi", "OpenRouter" — 0 hits. **"AI" appears on 2 UK pages** (`uk/jobs/index.html`, `uk/jobs/11498645/`) and **"Strategies" on 4 UK job pages** — all inside employer-written descriptions ("AI-driven technology", "Decarbonisation Strategies"). Not the demo's own copy; the validator exempts quoted descriptions. Acceptable, but say so in the evidence page so nobody greps and panics.
- **B Corp**: the mark is shown with the live site's alt text only ("Certified B Corporation"); the hero card adds "A job board wholly dedicated to the green industry sector, a Certified B Corporation and a member of 1% for the Planet." `brief.md` §3 notes the live B Corp page never states GreenJobs itself is certified; the only source is the footer alt text. The demo now asserts it in a sentence, twice, plus the header. Reduce to the mark + alt text as the brief advised, or get Keith to confirm certification in writing before it ships wider.
- "88 live green roles across Ireland" (title, hero pill, footer) — **24 of the 88 IE roles carry UK-only locations** (London, East of England, Scotland…), and 21 of 98 UK roles are Dublin/Ireland. That is the live data (cross-posted network roles), so the count is honest, "across Ireland" is not. "88 live roles on greenjobs.ie" is exact and stronger.
- Employer log tiles show initials in beige squares for 2 of 3 IE employers (no logo scraped). Fine, but "Employers hiring now" strip on the home page must stay limited to employers with a live role (D1 from the earlier pass — the test `faults: non-live employer under 'hiring now' caught` now covers it; good).
- Salary chips use `€` for a Mattinson role located "East of England": source `salary_text` is "€62,000 to €67,000 per annum", so the data is faithful. No conversion happening. Pass.

**Honest gaps**: I did not re-scrape the live sites to confirm the 88/98 counts are still current on 2026-09-25 (snapshot says 2026-09-22); no legal review of republishing 186 employer descriptions (same gap as the first pass).

## Daniela Amodei — how Keith and a job-seeker feel; footer/contact

- Footer contact matches `brief.md` §contact exactly: "(01) 912 5247", "+44 28 4303 2055", `info@greenjobs.ie` / `.co.uk`, Ennis Digital Hub address. `tel:019125247` should be `tel:+35319125247` so it dials from a UK phone. UK edition shows the same Ennis address (correct — one company).
- Keith's first 10 seconds on the home page: leaf, his wordmark, his B Corp badge, a live count that is true. Good. Then a cookie banner apologising for cookies he does not have. Then, on mobile, a subscribe modal over the jobs list. Two interruptions before value. He will feel the demo is defensive (GLM says the same: "the page reads like it's defending itself").
- Job-seeker: the job page "Where this role sits" panel — "This employer hasn't published a salary. Environmental science & consulting roles that do: €35k–€85k (15)" — is genuinely respectful; it gives the candidate leverage without shaming the employer. Keep.
- "49 similar roles within Cork" on a Galway/Mayo/Sligo/Dublin/Cork role is technically true and feels random; say "49 more roles in these counties".
- "Demo: this form is wired to your email provider on launch. Nothing was sent." appears under every form. One honest line per form is right; the same sentence six times reads as a disclaimer, not a promise.

**Honest gaps**: no real candidate or Keith has used it; tone judgments are mine.

## Ilya Sutskever — failure modes

- **JS off**: jobs page renders 0 rows and no `<noscript>` (`jsoff__ie_jobs_.png` shows only the "Your fit" panel with the number 88 and nothing to click). Insights and sectors render heads with no charts, no table. The spec promise "everything works without JS (details/summary)" holds only for the disclosure widgets, not for the board. Minimum: a `<noscript>` line "Enable JavaScript or browse by sector →" plus a static top-20 list in the HTML (the data is already embedded).
- **Reduced motion**: the hero `<video>` keeps playing (`paused:false`) under `prefers-reduced-motion: reduce`. `main.js` line 242 handles the *employers* footage band; the home hero handler in `landscape.js` only covers the canvas hand-over. README claims the poster is shown. False today.
- **Slow network**: `preload="metadata"` on two sources means a phone still pulls the 1080p file's headers, then both bodies on revisit (see Brockman). Poster JPEGs are present so the hero never blanks.
- **Empty states**: jobs empty state is good; compass with zero matching roles and sectors with n<3 both have copy paths (`explore.js` line 50). Saved tab with 0 shows "Saved 0" — untested click.
- **Edition data mismatch**: `home` sparklines and film use 8-week windows over 88 rows; weeks with n<5 read as trend (carried from first pass, still true).

**Honest gaps**: no throttled-network run (Playwright CDP throttling not set up here); reduced motion checked on home only; keyboard-only traversal of the row disclosure not exercised (CSS `:focus-within` exists, so it should work).

## Mira Murati — job-seeker on a phone at 11pm

- Rest-state rows at 390 (`ie-jobs-390-light.png`): title, employer · place, salary chip. Calm, scannable. Good.
- **Reveal on tap**: works when the tap lands off the title (`AFTER-TAP open=true`), but the title link is 190 × 42 px in a 354 × 112 px row — the natural tap target on a two-line title *navigates*. My first IE tap did exactly that. On touch, either make the whole rest-state row expand (title navigates only inside the expanded state via the Apply button) or add a visible chevron target ≥ 44 px on the right.
- Expanded mobile row is 310–323 px tall with the description excerpt, chip, age, and full-width Apply/Save (`uk-jobrow-390-light.png`). Thumb-reachable; Apply is the first button. Good.
- **Subscribe dialog at 390**: the "Subscribe" button is clipped to "ubscrib" inside the input group (`ie-jobs-390-filters.png`). Visible bug in the very modal that interrupts the list.
- Cookie banner takes 130 px of an 844 px viewport on every page until accepted.
- Sticky "Apply on greenjobs.ie →" at the bottom of the mobile job page: right call, one obvious action.
- Header at 390: leaf + wordmark + tiny "IE" + IE/UK pill + theme + burger — six objects in 390 px. Drop the subscript.

**Honest gaps**: emulated 390 × 844 with `hasTouch`, not a device; no test of the Filters bottom sheet or the ⌘K palette on touch.

## Andrej Karpathy — measure

See the table above. Three claims to correct with numbers: (a) "across Ireland" — 24/88 are UK-located; (b) reduced-motion video — measured playing; (c) mobile home weight — 1.9 MB first visit, 3.3 MB on dark revisit, i.e. **heavier than the live site's ~1.06 MB assets the evidence page beats**. The evidence page's before/after table must exclude the hero video or state it explicitly, or Keith's first Lighthouse run on a phone contradicts the page.
CLS risk: every `<img>` carries width/height (validator); hero has a poster; fonts are self-hosted with `font-display: swap` (Fraunces swap will reflow headlines once — measure `font-display: optional` as an alternative). Charts render after JS with fixed-height containers — no shift observed in captures.
Contrast: 1 failing pair (white on `--brand-2`, 3.85) at the top half of every primary button. Everything else ≥ 4.7.

**Honest gaps**: no Lighthouse/CLS instrument run (headless shell lacks the audit harness here); transfer sizes are Playwright `transferSize`, uncompressed from `http.server` (real hosts gzip HTML ~4×).

## Boris Cherny — reproducible from the directive; tests cover the disclosure code

- `directives/gtm_client_workflows/greenjobs_redesign.md` changelog line ~100 documents the disclosure work (`.row__more`, `css/disclose.css`, one-chart-at-a-time). Build, test and screenshot commands are all in `src/README.md`. A fresh session reproduces the build.
- **No test touches the disclosure code**: `grep` for `disclose|row__more|secrow|reveal|details` in `tests/greenjobs_redesign/test_build.py` and `verify_browser.mjs` returns nothing. `lib.test.js` covers pure helpers only. The `is-open` toggle (`jobs.js` line 116–119), the `details.reveal` employer cards, the `secrow` accordion and the job-description `<details>` ship untested. Add: (1) integration assertion that built jobs HTML contains no `.row__more` in static markup but `jobs.js` renders it; (2) `verify_browser.mjs` step: hover row → `.row__more` height > 0; tap row (touch context) → `is-open`; tap title → navigates; (3) employers page has 4 `<details class="reveal">`, sectors has 10 `secrow` after JS.
- Validator budgets were raised (60→80 KB CSS, 60→125 KB JS) without a changelog line in the directive; record it.
- `?theme=` persistence is a test fixture leaking into product behaviour (see Brockman).

**Honest gaps**: I ran the tests but not the full build (site was prebuilt); `screenshot.sh` not executed (own Playwright script used).

## Nick Saraev — what the client buys; proof-of-work on the evidence page

- Keith buys a migration story: JSON in → 202 static pages out → free hosting, plus a board that looks like 2026. The demo proves the second; the first is stated on `for-keith/` (not re-audited this pass; see 2026-09-22 pass D3/D4/D6 for what still needs fixing there).
- Proof-of-work that is real and visible: live counts, disclosed-salary explorer with n shown, JobPosting JSON-LD on 186 job pages, working IE⇄UK switch, one codebase. Proof that is *claimed* rather than shown: mobile performance (heavier than live on first visit, see Karpathy).
- The manual output (this build) has been reviewed four times; automation (nightly rebuild from the vendor feed) is the correct next rung and is not yet scripted — say so as phase 2, not as done.

**Honest gaps**: did not re-read `for-keith/` in full this pass; commercial numbers (traffic, applications) still unbaselined.

## Alex Hormozi — does the Employers page sell?

`ie-employers-1440-light.png`: headline "Reach people who only want green work" — dream outcome named. Proof: "88 live roles from 3 employers" — **"3 employers" is anti-proof** (GLM ranked this #1 too). Lead with the network: "One posting, ten sites, 186 live roles across both boards." Risk reversal: none — no guarantee, no "we post it for you within one working day" (which `brief.md` supports: "send us your job description and logo and we will post the job for you"). CTA: four identical "Post a job →" buttons in four cards plus the header pill — five of the same CTA, all leading to the same demo form that ends "Nothing was sent." One CTA, one form, and a mailto fallback ("Email the job to info@greenjobs.ie — posted within one working day") that *does* work today. Pricing: "Packages on request; no prices are published" is honest per §7; the sentence currently renders as "Packages on request ; no prices" (stray space before the semicolon, `templates/employers.html`).

**Honest gaps**: Hormozi's value equation needs a baseline (applications per posting) that only Keith holds; no employer has seen the page.

## GLM 5.3 lens

Model `zai-org/GLM-5.3` via `https://inference.baseten.co/v1/chat/completions`, 200 OK, `max_tokens` 1800 (the reply hit the cap mid-sentence; reproduced verbatim, including the truncation). Input: tag-stripped text of `/ie/index.html`, `/ie/jobs/index.html`, `/ie/employers/index.html`, 4,000 chars each.

> # Design Review: GreenJobs IE Redesign
>
> Overall: the copy voice is distinctive and the data-first approach (live counts, disclosed salaries) is a genuine differentiator. But verbosity is crowding out conversion, and a few credibility gaps are actively working against you. Here are the 10 changes I'd make, ranked by impact.
>
> ---
>
> **1. Don't lead with "3 employers" — it's your weakest number.**
> The hero and employers page both surface "88 live roles from 3 employers." Eighty-eight roles is impressive; three employers reads as "nobody trusts this board." Lead with 88 roles, 14 counties, 29 disclosed salaries, and the 10-site network. Move employer count behind the employers page entirely, and replace it with network reach ("one posting, ten sites") as the headline stat there.
>
> **2. Publish pricing, or at least a range, on the employers page.**
> "Packages on request; no prices are published" is the single biggest conversion leak for the paying side of the business. Self-serve buyers bounce at gated pricing. Even a "from €X per posting" anchor, or a visible Standard/Premium price with "volume rates on request," removes the friction. If pricing genuinely must stay opaque, replace the dead end with a one-field "email me rates" capture.
>
> **3. Cut homepage copy by ~40%.**
> The voice is charming but every section over-explains itself: "the career level read from the title," "the numbers are live counts, not estimates," "so nothing is a black box." Trust is shown by the interface, not asserted in prose. Keep the personality in headlines ("Work that puts the planet on the payroll" is excellent); strip the justifying sub-clauses. The page currently reads like it's defending itself.
>
> **4. Fix the job-type filter taxonomy.**
> "Permanent / Full Time / Contract / Home Based" mixes contract type, hours, and work arrangement in one list. "Home Based" is not a type — it's a location/arrangement filter. Split into two filters (Contract type: Permanent/Contract/Fixed term; Working pattern: Full time/Part time/Home based). This also fixes the job cards, where "Home Based" appears as a type badge.
>
> **5. Standardize salary units on job cards.**
> "€62k–67k" next to "€5.1k–6k/mo" forces mental math and looks inconsistent. Normalize everything to annual (€61k–72k for the monthly one), with monthly only on the detail page if the employer specified it. Also: 29 of 88 disclosing pay is a strength — but the salary section currently leads with the shortfall ("The rest say 'competitive'"). Reframe: "A third of roles tell you the pay up front — here's the picture," and let the gap be a quiet nudge to employers instead.
>
> **6. Make the hero search do more work.**
> The search bar is the primary conversion path but has no scaffolding. Add 4–6 tappable example chips directly under it ("Ecologist · Dublin · Wind energy · Policy"), and live autocomplete on the keyword field. The "Try:" examples currently live in the CV-match widget — surface them where 90% of users actually start.
>
> **7. Unify the ⌘K story.**
> The jobs page says "Press Ctrl K," the command palette says "⌘K," and the feature is mentioned twice with different framing. Pick one notation (detect platform), mention it once, and make sure the palette is discoverable on the homepage too — it's your best navigation asset and it's buried.
>
> **8. Solve the "saved on this device" problem, or soften the claim.**
> "Bookmark any of them and they wait for you on this device" is honest, but device-local bookmarks silently evaporate when a user switches phone/laptop — a retention killer for a weekly-checking audience. Minimum: add "email my saved roles" in the newsletter flow. Better: tie saves to the alert email that already exists.
>
> **9. Add employer social proof to the employers page.**
> The pitch is all features, no evidence. One testimonial, one case study ("Commonland filled their Landscape Developer role in 9 days"), or even honest network metrics ("X applications per posting last month") would do more than the four repeated "Post a job →" CTAs. Also, those four CTAs all presumably go to the same place — differentiate them (Standard → post form, Packages → enquiry, Branding → enquiry).
>
> **10. Clean up the demo seams before showing this to stakeholders.**
> "Demo: this form is wired to your email provider on launch. Nothing was sent," "Demo redesign, not the live site," "the send button is honest" — these appear on every page and undercut the polish of everything else. Fine for an internal build, but for any external demo, collapse them into a single dismissible "Demo mode" banner and remove the per-form confessions. The employers page especially reads like it's apologizing for its own CTA.
>
> ---
>
> **Two things to keep exactly as they are:** the shareable-filter-URL design ("a filtered list is a link you can share") and the CV-match widget showing matched words — both are genuinely differentiated, honest mechanics that most job boards fake. The redesign's instinct to show its work is right; it just needs t

Panel note on GLM #2 and #9: publishing prices or inventing a case study would break spec §7 (facts only from `brief.md`). Use the honest variants: "Email the job; posted within one working day" and the network-reach stat.

---

## Ranked fix list

Severity: blocker = do not send without it; should = fix inside the 3 h if at all possible; nice = after delivery. Minutes are single-implementer estimates including rebuild + rerun tests.

1. **blocker** — Remove the cookie banner from the demo (no non-essential storage exists) or show it once on the root chooser only: `src/js/popups.js`, `src/css/styles.css` `.cookie`, `_shell.html` — 15 min.
2. **blocker** — Subscribe dialog: stop it firing on `/jobs/` and job pages at all, and fix the clipped "Subscribe" button at 390 (`ie-jobs-390-filters.png`): `src/js/popups.js` (route check), `styles.css` dialog input-group `min-width`/`flex-wrap` — 20 min.
3. **blocker** — Footer social links render as empty circles: replace the placeholder ring SVGs with real Facebook/X glyphs or drop the links: `src/templates/_shell.html` footer, `.ftr__bottom` — 10 min.
4. **should** — Hero video must obey `prefers-reduced-motion` and Save-Data (pause, poster only) and must not double-fetch on phones (`preload="none"`, pick one `<source>` in JS): `src/js/landscape.js` ~line 174, `src/templates/home.html` `<video>` — 25 min.
5. **should** — Header: drop the "Certified B Corporation" nav item and the "IE"/"UK" subscript after the wordmark (the pill already carries edition): `_shell.html`, `.logo small`, `.nav__bcorp` in `styles.css` — 15 min.
6. **should** — Touch row disclosure: expand on any tap of the rest-state row (title navigates only from the expanded Apply / a small inline link) or add a ≥44 px chevron target: `src/js/jobs.js` lines 116–119, `disclose.css` — 25 min.
7. **should** — "across Ireland / across the UK" → "on greenjobs.ie / greenjobs.co.uk" in `<title>`, hero pill and footer (24/88 IE roles are UK-located): `build_site.py` strings, `home.html`, `_shell.html` — 15 min.
8. **should** — Salary fact rail: when no number parses, label "Not disclosed" and move free text ("Comphensive benefits package") under "Employer note"; annualise monthly chips ("€5.1k–6k/mo" → "€61k–72k"): `build_site.py` `salary_label`, `lib.js` chip formatter — 30 min.
9. **should** — B Corp claim: keep the mark + alt text; cut the two sentences asserting certification (hero card, footer blurb) until Keith confirms in writing: `home.html`, `_shell.html` — 10 min.
10. **should** — Employers page: one CTA (form) plus a working `mailto:info@greenjobs.ie` fallback "posted within one working day" (brief-supported); lead stat "one posting, ten sites"; fix "request ;" spacing: `src/templates/employers.html` — 25 min.
11. **should** — `?theme=` must not persist to localStorage (capture-only): `_shell.html` inline script line 19 — 5 min.
12. **should** — Mobile hero: one primary ("Find jobs"); make "Post a job" secondary and remove "Find a job ↓"; nudge the sun off the headline under 480 px: `home.html`, `styles.css` `.hero__cta`, `.hero__sun` — 20 min.
13. **should** — Primary button gradient top `--brand-2` gives 3.85:1 on white text; darken `--brand-2` to ≈`#25843f` or drop the label into the darker half: `styles.css` line 196 — 10 min.
14. **should** — Tests for the disclosure code: hover/tap/keyboard assertions in `tests/greenjobs_redesign/verify_browser.mjs`; markup counts (`details.reveal` ×4, `secrow` ×10, `.row__more` rendered) in `test_build.py`; directive changelog line for the budget raise — 40 min.
15. **should** — `<noscript>` fallback on jobs/insights/sectors ("Enable JavaScript or browse by sector") + static top-20 list in jobs HTML: `jobs.html`, `build_site.py` — 30 min.
16. **nice** — `tel:019125247` → `tel:+35319125247`: `_shell.html` footer — 2 min.
17. **nice** — Retire the 18 `--honey*` alias references to `--brand*` in `styles.css` — 10 min.
18. **nice** — Evidence page: state that hero footage (1.5 MB) is excluded from, or included in, the before/after weights; note that "AI"/"Strategies" hits are inside employer descriptions: `for-keith.html` — 15 min.
19. **nice** — "49 similar roles within Cork" → "in these counties" on multi-county roles: `build_site.py` similar-roles copy — 10 min.
20. **nice** — Consolidate six "Demo: … Nothing was sent" lines into one style of note per form (GLM #10): templates — 15 min.

Blockers total ≈ 45 min; blockers + shoulds ≈ 5 h, so within the 3 h window take 1–3, then 4, 5, 7, 9, 11, 13 (≈ 2 h 20 min) and leave 6, 8, 10, 12, 14, 15 for the post-delivery iteration.
