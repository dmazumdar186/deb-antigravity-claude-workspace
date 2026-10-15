# MISB (Mash International School of Business) — concept redesign + 20-post social set — handoff (2026-10-15)

Live site concept: https://misb-redesign.pages.dev/  (Cloudflare Pages project `misb-redesign`, noindex)
Pitch page for the school: https://misb-redesign.pages.dev/for-misb/
Live social set (10 Instagram + 10 LinkedIn, captions, 2-week calendar): https://misb-social.pages.dev/  (project `misb-social`, noindex)
Target: https://www.misb.fr/en/career-center — private business school, Paris (145 Avenue de Flandre 75019) + Lyon. Purpose: operator applies for their Social Media Marketing Manager role; the two links are the portfolio piece for the application email.

## Research (`research/facts.md`, 50 KB, 40 EN pages + FR home + 12 sub-pages, all fetched 200 on 2026-10-15)
- All copy, numbers, program names, fees, addresses, album names/dates and six testimonials are verbatim from misb.fr. 119 usable photos downloaded; 46 kept for the site (WebP ≤ 1600 px, 4.2 MB), gallery sets reused for the posts.
- The current site contradicts itself: work-study rhythm stated three ways (1/4, 2/3, 3/2), "+100 partner companies / +50 years" on the Career Center page vs "+3 / +5 years" on the Partner page, Lyon address three ways, Paris 75019 vs 75015, copy left over from another school ("business school in the Yvelines", a mantes-school.com email, a hostingersite.com booking URL), a Blade template route printed on the live Mastère page, typo "Our Acrediation" in the nav, 10 MB hero video. These are listed on the pitch page as opportunities — they are the "I checked your website" material for the email.
- Not published anywhere (never invented): founding year, student counts, employment rate, partner names, intake dates (only "Spring / Autumn" + "admissions open all year"), Qualiopi certificate numbers.

## What was built
- `site/` — one page, zero dependencies, 80.7 KB HTML+CSS+JS, self-hosted Cormorant Garamond + Inter, MISB brand colours from their own style.css (vermillion #e64626 darkened for contrast, navy #003a70). Hero = a leaflet that opens: closed cover (Lyon campus sign photo) swings open into a tri-fold of campus-life photos, then turns pages (Prev/Next, keyboard, swipe, auto-advance, 6 spreads, dots). Mobile bi-fold with swipe; reduced-motion renders open; no-JS shows flat panels. Then: trust strip (Qualiopi · Académie de Paris · RNCP 38666), programs with filter chips and published fees, work-study, Career Center with counters + source footnotes, campus-life photo wall with `<dialog>` lightbox, Student HUB, six testimonials, admissions, news, footer, mobile bottom bar. `for-misb/` pitch page.
- `social/` — 20 posts 1080×1350 rendered from HTML (`src/build.py`, `src/posts.py`, `src/build_index.py`), editorial register (serif headline, small-caps kickers, one accent, same grid on all 20), `captions.md` with calendar, captions, alt text, slot and KPI intent per post, gallery `index.html`.

## Verified
- `site_check.mjs` PASS (desktop 1440, Pixel 7, iPhone 13, reduced motion; `/` and `/for-misb/`): 0 page errors, 0 overflow, tap targets ≥ 44 px. Leaflet Playwright checks 15/15 (opens < 3 s, Next/auto-advance/arrow keys, swipe on Pixel 7, reduced-motion open, lightbox). Console errors 0.
- Human-eye review by a reviewer agent on screenshots: social set FAIL → 10 fixes applied (accents, claims scoped to the school's own wording, Lyon photo, testimonial layout, logo size, single accent) → re-rendered and re-checked; site PASS-with-fixes → v2 below.
- Live CSS md5 matches local after deploy. Sandbox Chromium cannot reach *.pages.dev (proxy), so verification is on identical local files.

## Redeploy
```
bash .claude/skills/site-redesign/scripts/deploy.sh deliverables/misb_redesign_2026-10-15/site misb-redesign for-misb/
D=$(mktemp -d); cp -r deliverables/misb_redesign_2026-10-15/social/{index.html,_headers,captions.md,png,fonts} "$D"/; npx -y wrangler@4 pages deploy "$D" --project-name misb-social --branch main --commit-dirty=true
```
Re-render posts: `cd deliverables/misb_redesign_2026-10-15/social && python3 src/build.py && python3 src/build_index.py`.

## Not done (by design)
No FR version of the concept; no real application form (links to misb.fr); no Lyon photography beyond what MISB publishes (one classroom + the entrance sign); no video; the "exhibit agency" leaflet referenced by the operator is not in this repo, so the leaflet was built from scratch.

## v2 (2026-10-15, after eye review)
Open leaflet fits the hero column at 1440 (panel = column/3, max 230 px) with paper edges and hinge gradients; closed cover 1.32x, centred, navy gradient behind title; mobile bottom bar hidden until the hero CTAs scroll out; tighter mobile hero (leaflet top visible on Pixel 7 first screen); eyebrow on one line; header logo 56/44 px; pitch button solid navy; the Lyon opening is stated via the verbatim blog title "MISB Lyon ouvre ses portes !" (27 Feb 2026). site_check PASS, leaflet suite 17/17, 0 console errors, 82.0 KB.

Note: `social/src/img/` (45 MB raw photo copies from misb.fr) is gitignored; re-create it by copying from `site/assets/img/` or re-downloading per `research/facts.md` section 10 before running `src/build.py`.

## v3 — "the prospectus" (2026-10-15, full rebuild after operator rejected v2; LIVE at the same URL)
v2 kept in `site/` for the record; `site_v3/` is what is deployed. Build notes, measurements and the Kling-ready slot: `research/handoff_v3.md`. Eye review rounds 1–2 fixed 13 defects; final scores 4/5/3→fixed/4; functional 29/29; site_check 0 failures; desktop 6,321 px vs misb.fr 9,011; mobile 5,464 px vs 14,528.
# MISB v3 — "the prospectus" (2026-10-15) — build notes for HANDOFF.md

Site: `site_v3/` (index.html, for-misb/index.html, css/styles.css, js/main.js, js/backdrop.js, assets/). Not deployed, not committed.

**Concept.** Designed-document DNA (Papaya reference): dark ink cover with cream type and "Prepared for / by / date" meta, paper #EEECE6 + white cards, numbered chapters "01 —", amber small caps, one vermillion dot. Cover is pinned (400svh desktop / 250svh mobile) and scroll-scrubbed: 4 fact beats + progress rail over a Paris → Lyon particle journey. Chapter 01 is a pinned tri-fold that opens by scroll (rotateY hinges, −140° → 0°), Paris | five real albums (dialog gallery) | Lyon; under 800 px it is a horizontal snap-scroll, no 3D. Chapters 02–07 are one tabbed panel area (every panel in DOM, `hidden` + `inert` when inactive, hash deep links, back/forward, arrow keys). Chapter 08 = `for-misb/`.

**Kling-ready slot.** `assets/hero.mp4` (1440×900, 318 KB; webm 311 KB) / `hero-m.mp4` (390×844, 149 KB; webm 201 KB) + WebM pairs + `hero.jpg` poster, 11 s at 30 fps, self-rendered from the GLM canvas by `research/render_hero_video.mjs` (`?record=1`, `window.__tick`). `assets/hero.json` `ready:true`. To upgrade: overwrite the mp4/webm pairs with generated footage of the same length, keep `ready:true`; `?canvas=1` forces the live canvas (QA); reduced-motion and Save-Data get the poster.

**Backdrop.** `js/backdrop.js` written by z-ai/glm-5.3 via OpenRouter in one round ($0.026, `research/glm_log.md`), hand-reviewed (single global, no network/eval, seeded PRNG), alphas raised by hand.

**Measured.** Live misb.fr home: 9,011 px desktop / 14,528 px mobile (`research/live_metrics_v3.json`). Concept: 6,177 / 5,484 px (pinned tracks included; the fold-out overlaps the last 20 % of the cover track). Deck panels desktop max ≈ 856 px, mobile max ≈ 1,747 px. index+css+js ≈ 78 KB; backdrop 5.1 KB.

**Verified.** `site_check` PASSED (/, /for-misb/; desktop, Pixel 7, iPhone 13, reduced motion). `research/functional_v3.mjs` 27/27 (incl. eye-review assertions: counters settle on +100, cover end state with fold overlap, mobile fold geometry, mobile deck tab/bar) (`functional_v3.json`). Screens in `screens_v3/` (+ `site_check/`).

**Not done / open.** Fonts render only on a live URL (sandbox). No deploy. Programs fees sit behind a `<details>` "Fees & details" per card to keep the panel to one viewport (still in DOM, painted when opened). Lyon has one interior + entrance photo only. Contradictions (rhythm, partner counters, addresses) are footnoted, not resolved.

**Eye review round 1 (applied):** counters settle exactly; beat 04 held to track end + cover photo plates (Paris frontage / Petit Palais / Lyon classroom) on beats 02–04, desktop only; backdrop density ×1.6; fold panels 3:4 content-sized with creases, grain and warm edge; fold-out overlaps the cover (desktop −160svh = last 20 % of the track, mobile −25svh); mobile fold panels = 100vw − gutters, 100 px bottom padding; mobile deck fade mask + active tab centred + 100 px bottom padding; full verbatim intro sentences; pitch cover contrast fixed (`.doc p` override); Programs grid fits one viewport (panel ≈ 775 px); link labels renamed; "Jews Memorial" kicker "Memorial visit · 24 Oct".

**Eye review round 2 (applied):** cover layer gets `visibility:hidden; pointer-events:none` (`.is-out`) once the fold-out has entered (desktop: at 50 % of the overlap; mobile: when the fold top passes 85 % of the viewport), header is opaque paper over fold/deck on mobile; fold text (`--tenter`) starts at 55 % of the overlap, after the cover text reaches 0; header logo hidden while over the cover (one logo on screen); deck top padding removed. New assertions: fade sequencing, mobile cover clipped + paper at (20,120) + opaque header.
