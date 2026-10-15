# Concept recipe — the MISB v3 "prospectus" renderer, step by step (2026-10-15)

Reference build: `deliverables/misb_redesign_2026-10-15/site_v3/` (index.html, css/styles.css,
js/main.js, js/backdrop.js). Read it narrowly (grep the section comments) — do not copy prose.

## 0. Page skeleton (in order)
`header[data-hdr]` (fixed, logo hidden while over the cover, chapter indicator `data-chapter-no` /
`data-chapter-name`) → `section.cover[data-cover]` → `section.fold[data-fold data-chapter="01"]`
(signature object) → `section.deck#deck` (`nav[data-deck-nav]` + panels `.dp[data-chapter]`) →
`section.pitch-teaser#why[data-chapter="08"]` → `footer` → `dialog[data-gallery]` → mobile bar
`[data-mbar]`. Chapters are numbered "01 —" to "0N —"; the pitch page is the last chapter.

## 1. Scrub engine (CSS + JS)
- Pinned track: parent `height: Nsvh` (`400svh` cover desktop, `250svh` mobile; `300svh` fold),
  sticky child `position: sticky; top: 0; height: 100svh; overflow: hidden; isolation: isolate`.
  Always pair `vh` fallback before `svh`.
- Progress: `p = clamp(-rect.top / (offsetHeight - innerHeight), 0, 1)` in one rAF-throttled scroll
  handler (`ticking` flag) that calls `coverScroll(); foldScroll(); syncVideo(); deckChapter()`.
- Beats: `[data-beat]` elements, `is-on` on `floor(p * beats)`, rail items `[data-rail-item]` get
  `is-on` / `is-done` and `--p` = progress inside the current beat. Beat 04 is **held to track end**.
- Overlap, so no empty viewport: cover `margin-bottom: -160svh` desktop (last 20 % of its track),
  `-25svh` mobile; fold has `z-index: 2`. Fold publishes `--enter` = clamp(p / .3) and the cover
  gets `--out` = clamp(enter / .5); `.cover.is-out { visibility: hidden; pointer-events: none }`
  once `--out` ≥ 1 (mobile: when the fold top passes 85 % of the viewport).
- **Fade sequencing rule:** cover text opacity reaches 0 before the next headline passes 0.1.
  Fold headline uses `--tenter` = clamp((enter − .55) / .45) — text starts at 55 % of the overlap.
- Fold hinge: `--fold` = easeInOutQuad(p) on `[data-spread]`; panels `rotateY(calc((1 - var(--fold))
  * -140deg))`; `is-open` at p > .9. Reduced motion: `--fold: 1`, static cover frame.
- Counters: `[data-count]` with `data-prefix` / `data-suffix`; 900 ms cubic ease, **final frame
  writes the exact integer**; screenshots are taken ≥ 1.5 s after the panel opens (settled).
- Deck: `show(id)` sets `hidden` + `inert` on every other `.dp`, `history.pushState('#id')`,
  `popstate` + `hashchange` → `fromHash()`, ArrowLeft/Right/Home/End on tabs, `scrollIntoView` the
  active tab. Header chapter indicator follows cover (00) → fold (01) → active panel → pitch (08).
- Failsafes: one IIFE, every `querySelector` guarded, `window.error` removes `html.has-js`, 2.5 s
  reveal failsafe, `<800px` never gates visibility on JS.

## 2. Mobile rules (< 800 px)
Header opaque paper over fold and deck; header logo hidden over the cover (one logo on screen);
bottom bar `[data-mbar]` hidden until the cover CTA scrolls out (`is-on` when fold top < 50 % vh);
`html { scroll-padding-bottom: 100px }` and 100 px bottom padding on fold and deck; signature object
becomes `display: flex; overflow-x: auto; scroll-snap-type: x mandatory; perspective: none` with
panels `flex: 0 0 calc(100vw - 2 * var(--gutter))` and `transform: none !important`; tab row gets a
right-edge fade mask (`::after` gradient) and the active tab is centred; cover photo plates off.

## 3. Paper treatment tokens
```
--paper:#EEECE6; --card:#FFFFFF; --ink:#141414; --ink-2:#3d3b37; --muted:#6b675f;
--line:rgba(20,20,20,.14); --cream:#F5F1EA; --cream-2:#c9c2b5; --amber:#B07A1C (small caps);
cover gradient #1a1a1a → #2d2620 (or brand ink, e.g. #0b1a2b); one accent (brand);
--display: serif (Cormorant Garamond / brand serif); --sans: Inter / system; --r:6px;
--shadow:0 1px 2px rgba(20,20,20,.06),0 12px 32px -16px rgba(20,20,20,.22)
```
Print metaphor: panel `aspect-ratio 3/4`, crease = 1 px inner gradient at the hinge, grain = SVG
`feTurbulence` overlay at ≤ .06 opacity, warm edge = `inset 0 0 0 1px #d9cfbd`. Papaya reference:
paper #eeece6, white cards, "01 — " marks, amber #d4a574 / #d97706 small caps, cream #f5f1ea.

## 4. GLM backdrop prompt skeleton (public facts only)
System: "senior creative coder, output ONLY one ```js block, vanilla, no network/eval, one global".
User: (1) exact API `window.<Brand>Backdrop = { init(canvas, opts), setProgress(p), render(tMs),
pause(), resume(), destroy() }`; (2) visual: transparent canvas, cream particles + hairlines, one
accent ≤ 3 % of marks; (3) three progress stages tied to the cover beats (place → journey → place),
smooth interpolation, ambient drift; (4) engineering: mulberry32 seed, ResizeObserver, DPR cap,
pause on `document.hidden`, reducedMotion = one static frame, particle count ∝ area, ≤ 11 KB.
Run `scripts/gen_backdrop.py --brand … --palette … --motif … --out js/backdrop.js`; hand-review
(single global, no fetch/eval/console), then raise alphas if faint on dark ink. Log in `glm_log.md`.

## 5. Hero video render
`python3 -m http.server 8793 --directory site &` then
`node scripts/render_hero_video.mjs --site site --url http://localhost:8793/` — the page in
`?record=1` exposes `window.__tick(frame)` and draws the cover stage only; 11 s × 30 fps,
`[data-stage]` screenshots → ffmpeg libx264 crf 31 (+ vp9 webm, poster from frame 30) → writes
`assets/hero.json { ready:true, landscape, portrait, poster, seconds, fps }`. `main.js` plays the
video when `ready:true` (portrait under 800 px), canvas otherwise; `?canvas=1` forces canvas;
reduced-motion / Save-Data get the poster. Kling upgrade = overwrite the mp4/webm pairs only.

## 6. Functional assertions (adapt `scripts/functional_template.mjs`; keep every name)
cover beats change at 25/50/75% of the track · video plays (or canvas fallback runs) · fold-out
hinge transform changes with scroll · fold-out fully open by track end · each chapter tab switches
the panel and updates the hash · back button restores the previous panel · header chapter indicator
follows the deck · keyboard ArrowRight wraps to the first chapter · deep link /#<id> opens the panel ·
gallery dialog opens and closes · counters settle on the exact published values · cover end: last
beat held into the overlap, photo plate shown, fold-out arrived by track end (no empty viewport) ·
fade sequence: cover text at 0 before chapter headline passes 0.1 · deck panels ≤ 1 viewport (900)
on desktop · desktop page height ≤ 9,000 px · index+css+js ≤ 150 KB (backdrop ≤ 12 KB separately) ·
desktop: 0 console errors · mobile cover beats · mobile uses the portrait video (hero-m.mp4) or
canvas · mobile fold-out is a horizontal snap-scroll (no 3D) · mobile fold-out: cover hidden, paper
at (20,120), opaque header · mobile fold-out: panels fit the viewport, no overflow, padding clears
the bar, cover overlaps the fold · mobile bottom bar appears after the cover CTA scrolls out · mobile
page height ≤ 12,000 px · mobile deck panels ≤ 2 viewports (1830) · mobile deck: active tab scrolled
into view, fade mask present, bar never covers panel content · Pixel 7: no horizontal overflow ·
mobile: 0 console errors · pitch page: 0 console errors, signature present.

## 7. Page-height targets
Desktop ≤ 9,000 px and below the live site; mobile ≤ 12,000 px and below the live site; deck
panels ≤ 900 px desktop, ≤ 1,830 px mobile. MISB v3: 6,321 / 5,464 vs live 9,011 / 14,528.

## 8. Screens list (reviewer input, after settle)
cover-0, cover-50, cover-100 (p .79), cover-fade (p .93), foldout-mid, foldout-open, deck-<each>,
pitch (full page); mobile-cover, mobile-cover-60, mobile-foldout, mobile-deck. Reviewer checklist:
no empty dark viewport, no ghosted text over a headline, one logo, no half-empty panel, no cut
sentence, counters on integers, tab row shows a scroll hint, bar never over content, contrast ≥ 4.5,
labels are words not slugs, nothing looks like a 2015 template.

## 9. Pitch page template (`for-<name>/`, ~700 words, same CSS, dark cover + paper body)
Cover: "Prepared for / by / date". Body: what this is (concept on our domain, nothing touched) ·
Today / Concept table — rows: scroll height desktop (measured) · scroll height mobile (measured) ·
first screen · navigation · media/motion · facts & contradictions found · what does not exist yet
(2–3) · next if you want it · signature "Debanjan, Founder, ProdCraft, debanjan@prodcraft.fyi".
