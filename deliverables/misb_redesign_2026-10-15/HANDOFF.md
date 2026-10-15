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
