# GreenJobs (greenjobs.ie + greenjobs.co.uk) redesign — build spec

Date: 2026-09-22. Client: Keith Molony, Gaia Talent Ltd (owner of both boards).
Purpose: a public, static demo that makes the €1,875 redesign look like the obvious bargain and
shows what the boards become on a modern stack. Hosted on GitHub Pages (`/greenjobs/`) and
Cloudflare Pages. Sister project (same operator, different design lane): `deliverables/gaia_redesign_2026-09-17/`.
Reuse its build/validate/screenshot/publish pattern; do NOT reuse its navy visual identity.

## 1. Design lane — "Living landscape"

The current sites are a 2013 Bootstrap-3 job board (jQuery 1.11, html5shiv, ~190 KB HTML home page,
sector lists with "(0)" counts). The redesign must feel like the best editorial product sites in
Europe: generous type, one strong accent, motion that explains, zero clutter.

Tokens (CSS custom properties, oklch with hex fallbacks):
- `--moss-950 #0c1a12`, `--moss-900 #10241a`, `--moss-800 #173225`, `--moss-700 #21452f` (dark surfaces)
- `--paper-50 #f7f5ef`, `--paper-100 #efebe0`, `--paper-200 #e2dccb` (reading surfaces, warm)
- `--ink-900 #131a15`, `--ink-600 #4a5a50`
- accent `--lime-500 #b4e33d`, `--lime-400 #c9f26a`, `--lime-700 #7fa71c` (CTA, focus, data)
- secondary data hues: `--sky #5aa9e6` (water), `--sun #f2b544` (solar), `--clay #d9774f` (waste), `--teal #2fbf9f` (ecology)
- Fonts: self-hosted Archivo (display, variable width — use `font-stretch` 110-125% for headlines) and
  Public Sans (text). Copy the two woff2 files from the Gaia project's `src/assets/fonts/`.
- Type scale: h1 clamp(2.75rem, 1.4rem + 5vw, 6.5rem); h2 clamp(2rem, 1.2rem + 3vw, 3.75rem).
- Light theme is default (paper). Dark theme via `prefers-color-scheme` AND a toggle (persisted in
  localStorage, no flash: inline script sets `data-theme` before paint).
- Motion: `prefers-reduced-motion` respected everywhere (static fallbacks, never a blank area).
  Scroll reveals via IntersectionObserver; View Transitions API for page navigation with a CSS
  fallback; all animations ≤ 600 ms, ease `cubic-bezier(.2,.72,.2,1)`.
- Breakpoints: fluid; test at 360, 390, 768, 1024, 1280, 1440, 1920. Touch targets ≥ 44 px. iPad
  landscape/portrait both first-class. No horizontal scroll at any width.
- Accessibility: WCAG 2.2 AA contrast, skip link, focus-visible rings (lime on dark, moss on paper),
  `aria-live` for result counts, full keyboard use of every widget, `<dialog>` for modals.

## 2. Editions

One codebase, two editions rendered by the build: `ie` (greenjobs.ie, en-IE, EUR, counties) and
`uk` (greenjobs.co.uk, en-GB, GBP, regions). Output `site/ie/…` and `site/uk/…` plus a root
`site/index.html` that redirects by stored preference else shows a two-tile chooser. Header carries an
edition switch (IE ⇄ UK) that keeps the current page path.

## 3. Pages (each edition)

1. `index.html` — Home.
   - Hero: full-bleed canvas "wind field" (particle flow field, sector-coloured, reacts to pointer and
     touch, devicePixelRatio-aware, pauses when off-screen, static gradient under reduced motion).
     H1 (e.g. "Work that puts the planet on the payroll." — keep it a claim about jobs, not about
     the company). Large search: keyword + location, type-ahead over the local dataset, Enter → jobs
     page with `?q=`. Live count under it ("312 live roles across 41 employers" — rendered from data).
   - Sector tiles (top 8 by count, real counts, each with a tiny inline sparkline of salary presence or
     count; never show a "(0)" sector).
   - "Latest roles" — 8 newest cards, hover lift, salary chip when known, "Save" (localStorage).
   - Map teaser: the SVG map (see §4) with counts; click → jobs page filtered.
   - Employers strip: real logos from `assets/logos/`, marquee that pauses on hover/focus, static
     grid under reduced motion.
   - "Why GreenJobs" three facts from `brief.md` only (network of sites, B Corp, weekly newsletter…).
   - Newsletter/job-alert block (form posts nowhere in the demo: on submit show an inline "Demo —
     wired to your ESP on launch" note; never a fake success).
   - Footer with network sites (from data), social links, B Corp mark, edition switch.
2. `jobs/index.html` — Search & browse.
   - Sticky filter rail (desktop) / bottom-sheet filters (mobile): keyword, location/region, sector,
     job type, salary disclosed only, sort (newest / salary / A-Z). All state in the URL. Result
     count in `aria-live`. Instant client-side filtering over the dataset JSON (embedded, gzip-friendly).
   - Views: list and map toggle; saved jobs tab. Empty state with suggestions.
   - Command palette (Ctrl/⌘+K) that searches jobs, sectors and pages.
3. `jobs/<id>/index.html` — one page per job (real data only): title, employer, logo, location,
   type, salary, posted/closing where known, description HTML, "Apply on greenjobs.ie" button →
   the real job URL, JSON-LD `JobPosting`, share (Web Share API w/ copy fallback), similar roles
   (same sector), save. Print stylesheet.
4. `sectors/index.html` — Sector explorer: every sector with count > 0 as a card; a treemap or
   packed-bubble chart of counts (SVG, in-house, no library) that filters the list.
5. `insights/index.html` — "Green salary explorer": charts from disclosed salaries (histogram by band,
   median by sector where n ≥ 3, disclosure rate, jobs by region). Read `.claude/skills` dataviz
   skill first (`Skill` tool: `dataviz`) and follow it: one system, accessible colours, tooltips,
   keyboard focus on marks, tables as alternatives under each chart.
6. `compass/index.html` — "Green Career Compass": 7-question, one-question-per-screen quiz
   (interests, skills, location, salary floor, work pattern), deterministic scoring → top 3 sectors
   with matched live roles. Result shareable via URL hash. Progress bar, keyboard/tap, back button.
7. `employers/index.html` — Advertise: what the board offers employers (facts only from
   `brief.md`; if no prices are published, do not invent them — say "Packages on request"),
   audience facts (only what the site itself claims), a mock "post a job" form preview (demo note).
8. `for-keith/index.html` — Evidence page, the one page allowed to speak candidly:
   before/after table (page weight, requests, stack, mobile score measured locally with the build's
   own numbers), what was built, what's proposed for phase 2 (migration off the current vendor,
   applicant tracking, employer self-serve, model-backed assistant — see §6), and the offer.
9. `404.html`, `robots.txt` (Disallow all — the demo is noindex), `manifest.webmanifest`, `sitemap.xml`.

## 4. Map

Try to build real geometry: download a public-domain simplified GeoJSON (Natural Earth admin-1 via
a raw GitHub mirror, or `https://raw.githubusercontent.com/…` datasets) for Ireland counties and
UK regions, convert to SVG paths at build time with a small Python script (equirectangular
projection is fine at this scale), and store the result as `src/assets/maps/ie.svg` / `uk.svg`
with `data-region` attributes. Match regions to jobs by the `region`/`location` fields (a mapping
table in `src/data/regions_<ed>.json`). If no reliable source can be fetched, fall back to a
hand-drawn low-poly outline (still real-looking, ≤ 60 points) plus labelled bubbles — never ship
a broken or empty map. Hover/tap shows count tooltip; click filters. Keyboard: regions are buttons.

## 5. Build & quality

- `execution/gtm_client_workflows/greenjobs_redesign/build_site.py --src … --out … --edition both`
  Renders Jinja-free (string templates like the Gaia build), embeds the dataset, generates job pages,
  sitemap, manifest, JSON-LD; measures CSS/JS bytes; runs `node --check` on every shipped JS and
  `node --test` on pure modules; calls `validate_site.py` (port the Gaia one: no leading-slash paths,
  every local asset resolves, every `<img>` has alt+width+height, JSON-LD parses, job page count ==
  dataset length, banned words on public pages: "AI", "Claude", "lorem", "TODO", "Hidden Depth",
  "WordPress"; `for-keith/` exempt; `noindex` meta on every page). Same `--out` allow-list guard
  (`deliverables/`, `.tmp/`, `$CLAUDE_SCRATCHPAD`) and `.greenjobs-build` marker.
- Budgets: CSS ≤ 60 KB, JS ≤ 60 KB total uncompressed (excluding the embedded dataset), no
  third-party requests at all, no framework, no build-time npm deps. Vanilla ES2020, `'use strict'`.
- `screenshot.sh` (port from Gaia): 390 / 768 / 1024 / 1440 widths for home, jobs, one job,
  insights, compass, for-keith, both editions, plus reduced-motion and dark theme.
- `publish_gh_pages.sh` → sub-path `greenjobs/`; `deploy_cloudflare.sh` → project `greenjobs-redesign`.
- Tests: `tests/greenjobs_redesign/test_build.py` (unit + integration on the real data).

## 6. Model-backed assistant (designed, not live)

The demo ships a "Ask GreenJobs" panel on the jobs page that today runs entirely in the browser
(deterministic: tokenised TF-IDF match of a pasted CV or free-text question against titles,
sectors and descriptions; shows top matches with the matching terms highlighted). The UI, prompt
contract and a Cloudflare Worker stub (`execution/gtm_client_workflows/greenjobs_redesign/worker/`)
are written so that phase 2 swaps the local matcher for GLM-5.3 (Z.ai) or Kimi K3 (Moonshot) via
OpenRouter with the key held in the Worker, never in the page. Public pages never use the word
"AI" (validator rule); call it "Ask GreenJobs" / "smart match". `for-keith/` explains the model
choice and the cost per 1,000 queries.

## 7. Honesty rules

Only facts from `src/data/*.json` and `src/data/brief.md` appear on public pages. No invented
audience numbers, prices, testimonials, or employer quotes. Jobs link to the real listing.
