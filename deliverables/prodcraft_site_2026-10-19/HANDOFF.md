# prodcraft.fyi v2 — "the build log" — handoff (2026-10-19)

**LIVE on the real domain:** https://prodcraft.fyi/ (Cloudflare Pages project `prodcraft`, deployment `7b948532`, replaces the June Astro site).
Staging copy of the same files: https://prodcraft-site.pages.dev/ (project `prodcraft-site`).
**Rollback (one command):** the previous production deployment is `c06736d0-9a6f-44b4-a68f-fc4935ff6bd3` (https://c06736d0.prodcraft.pages.dev, 2026-06-25). In the Cloudflare dashboard → Pages → prodcraft → Deployments → "Rollback to this deployment", or re-deploy any older build with wrangler. The v1 Astro source is not in this repo.

## What changed for visitors
- **Prospectus renderer, not a static page** (site-redesign standard since MISB v3): pinned, scroll-scrubbed cover with Kling footage and five "receipt" beats ($1M+ · +45% · <30 days · walk-away clause), a tri-fold **ledger** of shipped work (01), then a **command deck** (02–08) where one chapter is visible at a time with hash deep links, back/forward and arrow keys.
- **02 — Who you are**: a persona board (Founder / Sales leader / Recruiter-agency owner / Enterprise product leader). Picking one re-orders the proof in 03 and rewrites the contact headline, so each visitor type sees their own proof first.
- **New projects added** (verbatim numbers from the deliverable handoffs, `research/project_facts.md`): SaaS GTM recruiter concept (10.1× / 12.4× shorter page, 3→0 third-party scripts), GreenJobs (195 pages, 165 live roles, 2,797 checks), Paris business-school prospectus + 20-post social set, French auto-service franchise concept (33/33 iPhone assertions), the Jev decision stack (21 use cases, $0.00099 for 10 routed prompts), lead-list operations (2,501→977 relaunch after a bounce root-cause; 1,900-row 3-metro list; 229→195 studios), and an anonymised 500-member alumni-platform data audit (2→26→49 rows, 11-lens verdict). Prospects that never hired are named by sector only; links go to the public concept URLs.
- All six original systems, three offers, stack, three objections and three recommendations kept verbatim; stack gains Higgsfield/Kling, GLM, Kimi, Jev, Playwright, Astro.
- **Email** everywhere: `debanjan@prodcraft.fyi` (the Gmail address appears nowhere; asserted by functional test and on the live HTML).
- **Booking**: every CTA points to `https://prodcraft.fyi/book` (`_redirects`: `/book` → cal.com 302, `/call` → `/book`). The page never hard-codes cal.com, so moving to the ProdCraft calendar is a one-line edit in `site/_redirects` + redeploy. No Google Calendar for the prodcraft.fyi mailbox is connected to this session (only the three Gmail calendars), so the appointment-schedule URL could not be created here — see Next.
- Production hygiene: indexable, canonical `https://prodcraft.fyi/`, OG image, `robots.txt`, `sitemap.xml`, CSP + HSTS + frame-deny `_headers`, custom 404, zero third-party JS (one Google Fonts link).

## Measured
| | Live v1 (2026-10-19 morning) | v2 (live now) |
|---|---|---|
| Desktop 1440 scroll height | 6,508 px (7.2 screens) | 5,801 px (6.4) incl. pinned tracks |
| Mobile 390 scroll height | 10,360 px (12.3 screens) | 4,465 px (5.3); iPhone 13 emulation 3,212 px |
| Words in DOM | 918 | 595 in the first paint + every panel in DOM |
| index+css+js | Astro bundle | 79 KB; backdrop 5.4 KB |
| Tallest deck panel | — | 822 px desktop / 1,710 px mobile |
Sources: `research/live_metrics.json`, `research/live_metrics_after.json`, `research/functional.json`.

## Media
- **Hero footage**: Kling 3.0 std via Higgsfield, 10 s, $0.71 (`research/kling/prodcraft.json`, `research/gen_kling_hero.py`). Frame review flagged a desk surface in the lower 22 % → cropped and a lower-third gradient added (`hero-kling.*`), re-reviewed PASS. Landscape 1440×632, portrait 720×1280 (upscaled, slightly soft), WebM pairs, poster `hero.jpg`. Self-rendered canvas fallback stays in `js/backdrop.js` (GLM 5.3, one round, $0.011, `research/glm_log.md`).
- Plates: rendered from our own concept builds in this repo (`assets/plates/*.webp`); headshot and logo from the v1 site.

## Verified
- `research/functional.mjs` 32/32 (cover beats, video, fold hinge, deck tabs/hash/back/keys, counters, fade sequencing, heights, budgets, `/book` + no cal.com/gmail in HTML, persona switch, 404, mobile snap-scroll, bar timing, 0 console errors desktop + mobile).
- `site_check.mjs` exit 0 (desktop, Pixel 7, iPhone 13, reduced motion). No horizontal overflow 390–3840 px.
- **Eye review** (Opus reviewer reading 38 PNGs incl. 768 / 1920 / 2560 / 3840): round 1 FIX (3 P1, 4 P2, 2 P3, all fixed), round 2 SHIP + 3 small items (also fixed, re-shot). First-3-seconds test vs v1: desktop "clearly stronger" (brand, face, proof rail), mobile "stronger", 3840 "clearly stronger".
- Live after deploy: CSS md5 matches local, `/` 200, `/book` 302 → cal.com, `/nope` 404, CSP header present, OG + hero 200.
- Known limits: fonts do not load in the sandbox (layout verified, type verified only by the live URL); full-page screenshots of pinned tracks repeat the stage (`research/states.md`).

## Repo
`site/` (deployable as-is), `research/` (brief, facts, functional, GLM/Kling logs, states, build report), `screens/` (38 PNGs, gitignored). `.gitignore` now un-ignores this site's PNGs. Redeploy:
```
npx -y wrangler@4 pages deploy deliverables/prodcraft_site_2026-10-19/site --project-name prodcraft --branch main --commit-dirty=true
```

## Next (not done, by design)
1. Create the Google Workspace appointment schedule on debanjan@prodcraft.fyi and change the `/book` target line in `site/_redirects`; redeploy.
2. Optional: regenerate the portrait Kling clip natively in 9:16 (~$0.70) instead of the upscaled crop.
3. `www.prodcraft.fyi` already resolves to the same project; DNS lives outside this account, nothing to change.
4. Deck-who "SELECT" persona state is not persisted across visits (deliberate: no cookies, no storage).

## v2.1 (2026-10-19, after operator feedback) — LIVE
- **Headshot plate clipped under the fixed header** on wide-short desktops (operator screenshot at ~1882×832): the plate is now capped by `max-height: 100svh − header − rail offset`, width follows the 4:5 ratio; checked at 1280×720, 1366×768, 1440×900, 1882×832, 1920×1080, 2560×1440, 3840×2160 (`research/plate_clip_check.mjs`, all clear the header by ≥ 20 px).
- **Native 9:16 Kling clip** for the mobile cover (`research/kling_portrait/`, $0.71, `KLING_PORTRAIT=1 research/gen_kling_hero.py`), with a light top-down gradient (18 % → 50 %) so cream type stays legible while the gold diagram stays visible; frame-reviewed PASS; iPhone 13 plays `hero-m.webm` 720×1280. hero.json updated. Total media spend this build: $1.42 Kling + $0.01 GLM.
- functional 32/32, site_check 0 failures after both changes; deployed to `prodcraft` (live) and `prodcraft-site` (staging).

## v2.2 (2026-10-19, after operator feedback: brand-image QA, favicon, legal) — LIVE
**Trust gate run on the live domain.** `research/qa_live/matrix.mjs` shoots prodcraft.fyi at 18 viewports × 6 states (phones 360/390/412, landscape phone 844×390, small tablet 600×960 both ways, iPad 820×1180 and iPad Pro 1024×1366 both ways, laptops 1366×768 / 1536×864 / 1440×900 / 1882×832, 1080p, 1440p, 4K 3840×2160, portrait TV 1080×1920). Three Opus reviewers read every PNG by device class, four rounds (FIX → FIX → FIX → **SHIP ×3**), then the live domain was re-shot: 18/18 with 0 console errors, 0 horizontal overflow, video playing; `plate_fill_check.mjs` live: 19/19 (photo frame = photo, below the header, inside the viewport). Final live shots: `research/qa_live/shots_live_final/`, DOM log `matrix_log.json`.
- **Favicon**: the build had replaced the logo with a generic SVG mark. Restored the original real-logo files (`favicon.ico`, `favicon-32/48.png`, `apple-touch-icon.png`, `icon-192/512.png`, `site.webmanifest`); the generic SVG is deleted. Browsers that cached the old icon may need a hard refresh.
- **Photo fills its frame, every screen** (operator: non-negotiable): the plate's width is derived from the available height at a fixed 4:5 (16:10 for receipts) and the image is always 100 % of the frame; caption no longer drives the width; plates hidden on short landscape viewports (≤ 640 px tall) where no plate fits beside the copy. Asserted numerically at 19 viewports, local and live.
- **Legal (operator order)**: all third-party screenshots removed (`assets/plates/` deleted) and replaced by our own typographic receipt plates (`assets/receipts/`); no brand names of unsigned prospects/clients anywhere (functional assertion #33: no GreenJobs / Gaia / MISB / Midas / GTM People strings, no `plates/` images); links to those concept pages removed; sector descriptions + "concept, spec work" labels; numbers verbatim.
- **Layout fixes from the live reviews**: opaque paper header and tab bar on cream at all widths (no bleed-through); deck panels natural height, centred only when short, headings never under the sticky tabs, phone bottom bar never cuts the last card; ledger → deck handoff without blank bands; cover grid reserves the plate column so the plate never overlaps the headline (landscape iPads); landscape phones hide plate + rail and keep CTAs in the first screen; **portrait ≥ 768 (iPads, portrait TV)**: cover body centred with plate beside the headline, ledger rendered as stacked content-sized cards (no pinned track, no horizontal row), portrait video; **≥ 2200 px**: rem scaling and 88 vw container so 4K reads like a studio site, not a phone site in the middle of a TV; header chapter label follows the ledger in landscape; captions on solid dark.
- Accepted P3s: the phone bottom bar overlaps the last deck line as a scroll cue; portrait TV cover keeps a dark band under the content; matrix "deck" state is a scripted scroll position (real users arrive by tab click, where the heading sits 43 px under the bar).
- Heights now: desktop 1440 5,960 px (live v1 6,508), Pixel 7 4,500 px / iPhone 13 ≈ 3,350 px (v1 10,360); larger screens scale with viewport height.
- Spend this round: $0 (no new media). Redeploy command unchanged (`--project-name prodcraft`).
- v2.2.1 (same day): live spot-check with real fonts found the 4K plate caption capped at 13 px (body 28 px) and ledger buttons at 18 px → caption `clamp(10.5px, --s×10.5, 30px)`, ledger controls scale in rem at ≥ 2200 px; the plate's bottom offset is capped at 36vh so it keeps ≥ 6 px under the header on wide-short screens (1882×832). Checks after: functional 33/33, site_check 0, plate_fill 19/19 local and live, live 4K caption 28 px.
