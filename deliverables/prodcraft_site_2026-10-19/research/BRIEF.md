# Build brief — prodcraft.fyi v2 ("the build log"), 2026-10-19

Build the NEW PRODUCTION site for prodcraft.fyi at
`/home/user/deb-antigravity-claude-workspace/deliverables/prodcraft_site_2026-10-19/site/`
following `.claude/skills/site-redesign/reference/concept_recipe.md` (mechanics) and
`reference/build_rules.md` (every rule mandatory). Reference engineering, read narrowly by grep:
`deliverables/misb_redesign_2026-10-15/site_v3/` (index.html, css/styles.css, js/main.js, js/backdrop.js).
This is NOT a concept for a prospect: it is the operator's own live site. Therefore: **indexable**
(no noindex), canonical `https://prodcraft.fyi/`, full OG/Twitter meta (`assets/og.jpg` 1200×630 rendered
by you from the cover), `robots.txt`, `sitemap.xml`, `_headers` (security headers, cache for assets),
`_redirects`, `404.html`. No `for-<name>/` pitch page.

Files: `index.html`, `404.html`, `css/styles.css`, `js/main.js`, `js/backdrop.js` (generated), `assets/`
(logo `logo-prodcraft.png` already there + make `logo.svg`-free: use the PNG; `favicon.svg` derived from
the logo mark colours; `headshot.jpg` already there → make `headshot.webp` ≤ 900 px; `plates/*.webp`;
`hero.mp4|webm`, `hero-m.mp4|webm`, `hero.jpg`, `hero.json`; `og.jpg`), `_headers`, `_redirects`,
`robots.txt`, `sitemap.xml`.

## Brand (keep the live register — it already is the designed-document DNA)
- `lang="en"`. Title: "ProdCraft — AI builds, shipped. The senior AI engineer your roadmap is missing".
- Palette from the live site: ink `#16181c` (cover + header on cover), bone/paper `#f7f3ec`, card `#ffffff`,
  gold accent `#c8a35c` (ONE accent; on bone use `#8a6a2b` for text to pass 4.5:1), ink-2 `#3d4148`,
  muted `#6b675f`, amber small caps `#B07A1C`. Display serif **Newsreader**, sans **Geist**, mono
  **JetBrains Mono** — ONE Google Fonts link (same as live), `font-display: swap`, system fallbacks.
- Logo: `assets/logo-prodcraft.png` (512², RGBA) in header + footer. Headshot: `assets/headshot.jpg`
  (939×1174) → webp. No stock photos, no emoji, no text wordmark instead of the logo.
- Tone: operator voice, short declaratives, numbers first. Copy below is verbatim from the live site
  (`research/live_site_text.txt`) unless marked NEW; do not invent numbers.

## Contact changes (mandatory)
- Every email → `debanjan@prodcraft.fyi` (`mailto:debanjan@prodcraft.fyi?subject=Build%20brief%20%E2%80%94%20ProdCraft`).
  `debanjan186@gmail.com` must not appear anywhere (grep-assert it).
- Every booking CTA → `/book` (same-origin). `_redirects` line:
  `/book https://cal.com/debanjan-mazumdar-ben5rd/30min 302` (target swaps later to the ProdCraft calendar;
  the page never hard-codes cal.com). Also `/call /book 301`.
- Footer links (verbatim targets): LinkedIn https://linkedin.com/in/dmazumdar/ · Malt
  https://www.malt.fr/profile/debanjanmazumdar · Upwork https://www.upwork.com/freelancers/~debanjanmazumdar ·
  YouTube https://www.youtube.com/@prodcraft · GitHub https://github.com/dmazumdar186.
- Footer: "© 2026 ProdCraft · An AI-build studio by Debanjan Mazumdar · Paris". Signature line in
  contact: "Debanjan, Founder, ProdCraft, debanjan@prodcraft.fyi".

## Cover (pinned 400svh desktop / 250svh mobile, scrubbed) — "the receipts"
Beat 00 (p 0–.25): kicker "ProdCraft · Paris · est. by a 15-year product operator" · headline
"AI builds, shipped." · sub "The senior AI engineer your roadmap is missing. Without the FTE, the agency
timeline, or the slide-deck demos. Built with Claude Code. Live in your stack in weeks." · CTAs
"Book a free build session" (/book) + "See what we've shipped" (#01).
Beat 01: "$1M+" — "qualified pipeline generated from 48,000+ cold emails/mo at 4%+ reply, one
fully-automated outbound system".
Beat 02: "+45%" — "feature adoption with −55% latency (p95) · enterprise GenAI/RAG in production".
Beat 03: "<30 days" — "median ship cycle across 5+ live AI products built end-to-end: SaaS · mobile ·
video · agents".
Beat 04 (held to track end): "All code, all credentials — yours. Day one." kicker "Walk-away clause".
Progress rail 00–04. Photo plates (desktop, beats 01–04): headshot on 01; on 02–04 real plates
rendered by you from our own shipped concept sites (see Plates). Counters write exact strings.
Backdrop: run `python3 .claude/skills/site-redesign/scripts/gen_backdrop.py --brand "ProdCraft"
--palette "#f7f3ec,#c8a35c" --motif "a dark ink page where gold hairlines draw a system diagram: inbox
→ pipeline → CRM nodes, then particles stream along the edges, then settle into a calm grid" --out
<site>/js/backdrop.js --log <abs>/research/glm_log.md` (GLM 5.3; Kimi K3 fallback is inside the
script). Hand-review (single global `window.ProdCraftBackdrop`, no fetch/eval/console), raise alphas.
Hero video: serve the site on 8793 and run `node .claude/skills/site-redesign/scripts/render_hero_video.mjs
--site <site> --url http://localhost:8793/` → `assets/hero.*`, `hero.json ready:true`. The brain may
later overwrite the mp4/webm pair with Kling footage; keep the slot.

## 01 — Signature object: "The ledger" (pinned 300svh, overlaps cover −160svh / −25svh)
A fold-out contact sheet of what shipped, newest first — a tri-fold on desktop (rotateY hinges), a
horizontal snap-scroll (no 3D) under 800 px. Panel = white card on paper with crease + grain + warm
edge. Each panel: kicker (category · year), title, one verbatim metric line, a plate (webp), "open ↗"
link where a live URL exists. Panels (left → right):
1. **Outbound engine (US consultancy)** — "$1M+ pipeline · 48,000+ emails/mo · 4%+ reply · $200K/yr SDR
   headcount replaced". Plate: none (type-only card, gold rule).
2. **Enterprise GenAI adoption driver** — "+45% feature adoption · −55% p95 latency".
3. **SaaS GTM recruiter, London (concept, spec work)** — "Page height 17,828 → 1,773 px desktop (10.1×);
   36,490 → 2,941 px mobile (12.4×); 4,373 → 5,003 words, nothing dropped; third-party scripts 3 → 0".
   Link https://gtm-people-redesign.pages.dev/ . Plate: render `deliverables/gtm_people_redesign_2026-10-06/site/`.
4. **GreenJobs (greenjobs.ie / .co.uk, Gaia Talent)** — "195 pages · 165 live roles · 2,797 checks · zero
   third-party requests". Link https://greenjobs-redesign.pages.dev/ . Plate: render
   `deliverables/greenjobs_redesign_2026-09-22/site/`.
5. **Private business school, Paris (prospectus concept + 20-post social set)** — "6,321 px vs 9,011 live
   desktop · 5,464 vs 14,528 mobile · functional 29/29 · 20 posts 1080×1350". Link
   https://misb-redesign.pages.dev/ . Plate: render `deliverables/misb_redesign_2026-10-15/site_v3/`.
6. **Franchise auto-service brand, France (concept)** — "59.6 KB HTML+CSS+JS · 33/33 iPhone 13
   assertions · 0 console errors · working booking widget". Link https://midas-redesign.pages.dev/ .
   Plate: render `deliverables/midas_redesign_2026-10-05/site/`.
Tri-fold = 3 spreads of 2 → use a 3-panel fold with a "turn" (Prev/Next, keys, dots) over 2 sheets, or
a 6-card fan; pick what reads as a designed object at 1440 AND stays content-sized (3:4). Mobile: 6
snap cards. Reduced motion: open.

## 02–08 — Command deck (sticky chapter nav, one panel visible, all in DOM, hash deep links)
**02 — Who you are** (the multi-customer entry; NEW copy, no numbers invented): four persona cards
that switch the deck's spotlight (`?for=` param + hash `#02-founder` etc., `aria-pressed`):
- Founder / CEO — "You need a product shipped, not a roadmap." → proof: <30 days, 5+ live products,
  14-day mobile pipeline; CTA "Scope a first build".
- Sales / RevOps leader — "You need pipeline this quarter." → proof: $1M+, 48,000+/mo, 4%+ reply,
  977-row relaunch list after a bounce root-cause (12 of 18 hard bounces were catch-all rows);
  CTA "Talk outbound".
- Recruiter / agency owner — "You need a site that converts and lists that land." → proof: 10.1× shorter
  page, 195 pages / 165 live roles, 1,900-row 3-metro list de-duplicated and MX-checked; CTA "See the sites".
- Enterprise product leader — "You need GenAI in production, measured." → proof: +45%, −55% p95,
  eval harness, prompt-cache-aware cost model; CTA "Hear how".
Selecting a persona reorders/highlights cards in 03 and changes the contact panel's headline.
**03 — Systems we've shipped**: the six live cards verbatim (Always-On Outbound Engine · Enterprise
Adoption Driver · Multi-Lingual CV Optimizer live ↗ https://cv-optimizer.pages.dev · ProdCraft AI Video
Studio · 14-Day Shipping Pipeline · Claude Code Operator Stack, with their metric pairs and "how it
works" `<details>` text verbatim) PLUS three NEW cards:
- "Decision stack (Jev)" — "21 classify / pick / score use cases, each with script + directive + offline
  test + one live run · router measured: 10 prompts, 6.8 s, $0.00099, all tiers correct · ~600 ms/decision".
- "Lead-list operations" — "2,501 rows → 977 relaunch-ready after bounce root-cause · 1,900-row Bay Area
  export, 5 duplicates removed, 3 metros · 229 → 195 yoga studios, 34 duplicates removed".
- "Data audit for a 500-member alumni platform (concept case)" — "the same filter returned 2, then 26,
  then 49 rows as the logic was normalised · 68% of profiles untouched for 2+ years · 11-lens panel verdict,
  19-page annex". (anonymised; no client name, no password, no link)
Counters `data-count` only where the value is an integer; text metrics otherwise.
**04 — What we build**: three offers verbatim (Cold-email & outbound systems · 24/7 AI sales assistants ·
Custom AI operations) with their 4 bullets each; CTAs to /book.
**05 — The stack**: three columns verbatim (AI models · Build & deploy · Ops & GTM) + add "Higgsfield /
Kling", "GLM", "Kimi", "Jev (TypeSafe)" under AI models, "Playwright", "Astro" under Build.
**06 — How we work**: the three objection/answer pairs verbatim.
**07 — Recommendations**: the three quotes verbatim with names/titles (Jitendra Kumar, InfoTNT ·
Ramesh Babar, Zensar · Siva Devavarapu, Papaya Labs → verify link https://papayalabs.app ; Ramesh verify
https://www.linkedin.com/in/rameshbabar/).
**08 — Contact**: "Stop reading. Start shipping." · "Book 30 minutes. We'll show you what's possible." ·
"No deck. No sales pitch. Grab 30 minutes and we scope a first build on the call." · buttons /book and
mailto · signature line · (persona-aware headline from 02).
Each panel ≤ 900 px at 1440, ≤ 1,830 px at 390; overflow behind `<details>`. Header chapter indicator.

## Responsive range (mandatory, beyond the recipe)
Test and tune at 390, 768, 1024, 1440, 1920, 2560 and 3840 px wide. Rules: fluid type with
`clamp()` whose max is reached at 1920; content max-width 1,480 px at ≥ 1920 and 1,760 px at ≥ 2560
(never full-bleed text); the cover headline must stay ≥ 55 % of viewport width at 3840 (scale the whole
cover stage with `--stage: min(1, vw/1440)`-style vars); plates and cards scale, hairlines stay 1 px;
no element thinner than 44 px tap target on touch; 768 (tablet) uses the desktop deck but a 2-column
grid. No horizontal overflow at any width. `@media (hover:none)` = no hover-only affordances.

## Verify (mandatory before reporting)
1. Copy `scripts/functional_template.mjs` → `research/functional.mjs`; set selectors; keep every
   assertion name except the pitch ones (replace by: `/book` present in `_redirects` and no cal.com in
   HTML; no gmail in HTML; persona switch changes 08 headline and hash; 404 page serves). Run →
   `research/functional.json`, must be N/N.
2. `node .claude/skills/site-redesign/scripts/site_check.mjs --site <site> --pages /` exit 0.
3. Screens per `concept_recipe.md` §8 into `screens/` PLUS `wide-1920-cover.png`, `wide-2560-cover.png`,
   `wide-3840-cover.png`, `wide-2560-deck-03.png`, `tablet-768-cover.png`, `tablet-768-deck-02.png`
   (after settle). Playwright: `import pw from '/opt/node-tools/node_modules/playwright/index.js'`.
4. Budgets: index+css+js ≤ 150 KB, backdrop ≤ 12 KB, zero third-party JS (fonts link only).
Do not deploy, do not commit. Report ≤ 250 words: files + sizes, functional N/N, site_check summary,
page heights desktop/mobile vs live (6,508 / 10,360), console errors, GLM cost, what is not done.
