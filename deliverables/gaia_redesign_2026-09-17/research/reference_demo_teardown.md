# Technical Teardown — evolution-exhibits-v4.pages.dev

Source saved under this folder: `index.html`, `portfolio/index.html`, `css/styles.css`, `css/film.css`, `js/main.js`, `js/motion.js`, `js/film.js`, `js/gallery.js`, `assets/film/film.mp4`, `assets/film/film-m.mp4`, `assets/film/poster.webp`, plus sample images. `robots.txt` disallows all crawling and there is no real `/sitemap.xml` (Cloudflare Pages SPA-fallback serves `index.html` for that path with a 200 — treat it as absent). The site has exactly **two pages**: `/` (home) and `/portfolio/` (full case-study grid). No CMS/JSON data endpoints exist; all copy is static HTML.

**Headline finding: this site uses zero animation libraries.** No GSAP, no ScrollTrigger, no Lenis, no Swiper, no Three.js, no Lottie, no SplitType. Every effect — the scroll-scrubbed hero video, the sticky pinned sections, the card carousel, the rotating-drum step list, the fade-up reveals — is hand-rolled with `IntersectionObserver`, `requestAnimationFrame` + `getBoundingClientRect()`, and CSS custom properties driving `transform`/`opacity`. This is a **from-scratch, no-dependency animation architecture** — very replicable, just needs the exact math ported (given below verbatim).

---

## 1. Page structure (home, in DOM order)

| # | Section (id/class) | Purpose | Headline copy | Layout | Mobile (≤799px) |
|---|---|---|---|---|---|
| 0 | `.site-header[data-header]` (fixed, not in flow) | Sticky nav, shrinks on scroll | Logo, "DESIGNING + BUILDING EXHIBITS / SINCE 2007", nav (Portfolio/Approach/Capabilities/About/CTA), scroll-progress bar | CSS grid `176px minmax(170px,1fr) auto`, floating pill inset 16px from edges | Collapses to hamburger; menu becomes full-screen fixed panel; `.header__context` hidden entirely |
| 1 | `.film#hero[data-film-hero]` | Hero — scroll-scrubbed video walking through 7 process stages | "YOUR BRAND, BUILT FOR THE SHOW FLOOR." → 6 more stage headlines (Design/Fabrication/Crating/Logistics/Installation/Show) | `position:sticky` stage, height = `(--film-span=7 + 1) × 100vh` = 8 viewport-heights tall track | Copy pinned to bottom (`align-items:end`), step labels collapse to only show the active one |
| 2 | `.brief#brief.section-paper` | Statement/mission line | "GIVE THEM A REASON TO WALK IN." + supporting paragraph + "CUSTOM / MODULAR / RENTAL / PORTABLE" | Grid `minmax(160px,1fr) minmax(0,3fr)`, min-height 100svh | Stacks to block layout, headline `clamp(48px,15vw,76px)` |
| 3 | `.work#work` → `.folio[data-folio]` | Portfolio teaser — pinned card-stack "scroll carousel" | "BOOTHS WE HAVE BUILT." + 5 project cards (RecovR, Shine, Shopco USA, Hermes Medical Solutions, Adamson) | `.folio` track is `min-height:500svh`; `.folio__sticky` pins at `top:0, height:100svh`; cards `position:absolute` centered, animated via CSS vars | Becomes a static vertical stack (`display:grid; gap:28px`), no pinning, no transforms |
| 4 | `.approach#approach[data-approach]` | "How we work" — 4-step process, scroll-driven 3D rotating drum | "ONE LEAD. ONE SHOP. ONE CREW." + 4 numbered steps | Track `min-height:400svh`; sticky panel grid `minmax(300px,1fr) minmax(420px,1.15fr)`; step list uses `perspective:1200px` + `rotateX` | Steps become a flat list, `perspective:none`, all steps visible with top-border dividers |
| 5 | `.proof.section-blue` | Testimonial | Kudelski IoT quote from Christopher Schouten | Full-bleed blue section, grid `auto 1fr`, huge blockquote `clamp(42px,7.4vw,122px)` | Footer separator dots hidden, stacks vertically |
| 6 | `.capabilities#capabilities.section-ink` | Services list | "EVERYTHING THE BOOTH NEEDS. ONE VENDOR." + 6-item list (Design/Fabrication/PM/Logistics/Installation/Show services) | `capabilities__top` grid `1fr 3fr`; list rows with hover-driven left accent bar + horizontal text shift | 1-col top grid; list rows `44px 1fr` |
| 7 | `.about#about.section-paper` | Company positioning | "YOU SEE THE BOOTH. WE SEE EVERYTHING BEHIND IT." | Grid `1fr 3fr`, content right-aligned column | Single column block |
| 8 | `.contact#contact.section-ink` | CTA | "YOUR NEXT SHOW IS ALREADY ON THE CALENDAR." + "The design is on us." + CTA link | flex column, `contact__lower` grid `minmax(280px,600px) 1fr` | 1-col grid, gap 44px |
| 9 | `.site-footer` | Footer | Logo, email/phone/address, LinkedIn, back-to-top, copyright | grid `1.2fr 1fr 1fr` | grid `1fr 1fr`, meta row spans full width |

### Portfolio page (`/portfolio/`)
- `.portfolio-hero.section-paper`: "BOOTHS WE BUILT." min-height 74svh.
- `.portfolio-archive#portfolio-grid`: 12-column CSS grid (`portfolio-item` spans 4, `--wide` spans 8, `--narrow/--small/--tall` span 4), 71 images total, `grid-auto-flow: dense`. At 800–980px collapses to 2 columns; at ≤799px collapses to 1 column (all items `grid-column:1`).
- `.portfolio-cta`: grid `1fr 3fr`, big CTA headline + contact link, min-height 88svh.
- `<dialog class="portfolio-viewer" data-portfolio-viewer>` — native `<dialog>` lightbox with prev/next/close and an `IMAGE 01 / 71` counter, uses `showModal()`, CSS `@starting-style` for open/close cross-fade, and `allow-discrete` transitions.

### All media queries found
`css/styles.css`: `(min-width:800px) and (max-width:980px)`, `(max-width:1050px)`, `(max-width:799px)`, `(max-width:480px)`, `(prefers-reduced-motion:reduce)`.
`css/film.css`: `(max-width:799px)`, `(prefers-reduced-motion:reduce)`.
Primary breakpoints to replicate: **1050px** (menu becomes hamburger), **799px** (all pinned/3D sections flatten to static stacks), **480px** (full-width buttons, single-column footer).

---

## 2. Every dynamic/animated element — exact mechanics

### 2.1 Preloader
None. No loading screen/splash. First paint is the header + hero poster frame.

### 2.2 Sticky/shrinking nav
- Selector: `header.site-header[data-header]`.
- Always `position: fixed`, floats 16px from top/sides as a bordered pill.
- On `scroll`, JS (`main.js`) toggles class `is-scrolled` when `window.scrollY > 48`; CSS then sets `top:0` and swaps the translucent background (`rgb(9 10 12 / .92)`) for solid `var(--ink)`.
- A **scroll-progress bar** (`.header__progress i[data-scroll-progress]`) is driven every frame: `header.style.setProperty('--page-progress', pageProgress)` where `pageProgress = scrollY / (documentHeight - viewportHeight)`. CSS: `transform: scaleX(var(--page-progress))`.
- Mobile menu (`≤1050px`): hamburger toggle (`data-menu-toggle`) flips `aria-expanded`, adds `.is-open` to `nav[data-menu]`, sets `menu.inert` when closed, traps focus to first link on open, restores focus to toggle on close, and closes on `Escape`. Uses CSS `visibility` + `opacity` transition (220ms), no JS animation library.

### 2.3 Hero — scroll-scrubbed video ("the flow" mechanic — most important element)
File: `js/film.js`. This is the show-floor "flow" narrative and the exact pattern to reuse for a renewable-energy sector walkthrough.

- Markup: one `<video data-film-video muted playsinline preload="none">`, seven `<div class="film__state" data-film-state="0..6">` overlay panels (each with its own eyebrow/headline/CTA), and an `<ol class="film__steps">` progress rail with 7 `<li data-film-step="0..6">` labels (Brief/Design/Fabrication/Crating/Logistics/Installation/Show).
- Track height: `.film { height: calc(var(--film-span, 7) * 100vh + 100vh) }` → 8 × 100vh scroll distance for 7 states. `.film__stage` is `position: sticky; top:0; height:100svh` — the classic **scroll-pinned video** pattern (no ScrollTrigger needed).
- Video source: **7 keyframes across a 30-second clip**, i.e. states sit at t = 0, 5, 10, 15, 20, 25, 30 seconds ("Seven stills at 0,5,...,30s with six 5s legs between them"). Responsive source: `film-m.mp4` (mobile, <800px, 6.0MB) vs `film.mp4` (desktop, 9.8MB).
- **The video is fetched as a Blob**, not set as `src` directly: `fetch(src).then(r=>r.blob()).then(blob=>{ film.src = URL.createObjectURL(blob); film.load(); })`. Comment in source explains why: *"the mp4 is fetched as a blob because Cloudflare Pages serves no byte ranges, and an unseekable source cannot scrub."* Falls back to setting `src` directly on fetch failure.
- Scroll → time mapping (`frame()` function, run via rAF-throttled scroll/resize listeners):
  ```js
  const rect = hero.getBoundingClientRect();
  const vh = window.innerHeight;
  const p = Math.min(1, Math.max(0, -rect.top / (rect.height - vh)));      // 0..1 section progress
  const t = Math.min(LAST, (p / 0.92) * LAST);                             // LAST = 6 (7 states, 0-indexed)
  const s = Math.floor(Math.min(t, LAST - 0.001));                         // current integer state
  const f = t - s;                                                        // fractional position within state->next leg
  const g = Math.min(1, Math.max(0, (f - 0.15) / 0.7));                   // easing window: state holds first 15%, "leg" plays across the middle 70%, next 15% is next-state hold
  target = (s + g) * LEG;                                                 // LEG = 5 (seconds per leg) -> target video currentTime
  show(f < 0.5 ? s : Math.min(LAST, s + 1));                              // crossfade text state at 50% of the leg
  steps.forEach((el,i)=> el.style.setProperty('--fill', clamp(t - i)));   // per-step progress-bar fill (CSS var, 0..1)
  ```
- Time is **eased toward target**, not snapped, to avoid stutter on fast scroll flicks:
  ```js
  const delta = target - film.currentTime;
  if (Math.abs(delta) < 1/48) return;         // ~1 frame tolerance @48fps
  if (!seeking) { seeking = true; film.currentTime += delta * 0.22; }     // 22%-per-frame lerp
  ```
  Re-entrancy guarded by a `seeked` event listener that clears `seeking`.
- Text-state crossfade (CSS): `.film__state { opacity:0; transform:translateY(18px); transition:opacity 420ms ease, transform 520ms cubic-bezier(.2,.72,.2,1); }` → `.is-on { opacity:1; transform:none; }`. CTA button pop-in: `@keyframes film-cta-in` (`from: opacity:0, translate3d(0,12px,0) scale(.94)` → `to: none`), `640ms cubic-bezier(.2,.72,.2,1) 120ms both`.
- Progress rail fill: `.film__steps li::after { transform: scaleX(var(--fill,0)); transition: color 300ms ease }` (the fill itself is not transitioned — it's set per-frame so it tracks scroll exactly; only the color highlight transitions).
- `prefers-reduced-motion: reduce` → skips scrubbing entirely, shows state 0 only, video track collapses to `min-height:100vh` (no sticky/pin), CTA animation disabled.
- No-JS fallback: `html:not(.has-js) .film { height:auto; min-height:100vh }` — video degrades to a static poster-frame hero.

### 2.4 Scroll-triggered reveals (`data-reveal`)
- `main.js::initReveals()` — plain `IntersectionObserver`, `rootMargin:'0px 0px -10% 0px'`, `threshold:0.06`. On `isIntersecting`, adds `.is-visible` and immediately `unobserve()`s (fires once, never re-hides).
- CSS: `.has-js [data-reveal] { opacity:0; transform:translateY(34px); transition: opacity 750ms cubic-bezier(.2,.72,.2,1), transform 750ms cubic-bezier(.2,.72,.2,1); }` → `.is-visible { opacity:1; transform:none; }`.
- Applied to nearly every headline/paragraph/list-item across sections (`data-reveal` attribute, no stagger logic — CSS transition timing alone creates the fade-up).
- `prefers-reduced-motion` and no-`IntersectionObserver` browsers: all items get `.is-visible` immediately (no animation, content just present).

### 2.5 Pinned/horizontal-feeling card stack ("folio", the portfolio teaser)
- Not truly horizontal scroll — it's a **vertical scroll driving absolutely-positioned overlapping cards** inside a pinned viewport (`.folio__sticky`), giving the effect of one card retiring while the next slides in — visually similar to a horizontal carousel but implemented purely with vertical scroll + z-index + transform.
- Math lives in `js/motion.js::folioCardState(progress, index, count)`:
  ```js
  const position = clamp01(progress) * Math.max(count - 1, 0);
  const offset = index - position;
  const direction = index % 2 === 0 ? 1 : -1;                 // alternates exit direction per card
  const exit = clamp01((-offset - 0.08) / 0.82);               // 0 while a card hasn't started exiting
  const depth = Math.max(0, Math.min(4, offset));              // stacking depth for not-yet-active cards
  return {
    xPercent: exit>0 ? direction*36*exit : direction*depth*2.8,
    yPercent: exit>0 ? -76*exit : depth*3.2,
    rotationDeg: exit>0 ? direction*3.5*exit : direction*depth*0.8,
    scale: exit>0 ? 1-0.03*exit : Math.max(0.9, 1-depth*0.028),
    opacity: exit>0 ? 1-0.96*exit : Math.max(0.58, 1-depth*0.1),
    captionOpacity: exit>0 ? 0 : 1-clamp01(Math.abs(offset)/0.45),
    zIndex: count-index,
  };
  ```
- `progress` itself comes from `motion.sectionProgress(rect, viewportHeight)`: `clamp01(-rect.top / max(rect.height - viewportHeight, 1))` — the standard "how far scrolled through this pinned section" formula (0 at section top hitting viewport top, 1 at section bottom).
- Applied every rAF-throttled scroll tick in `main.js::initScrollMotion()`, only when `desktopMotion.matches` (`min-width:800px`) and motion isn't reduced — sets CSS custom properties `--folio-x/-y/-rotation/-scale/-opacity/-caption-opacity` + `zIndex` per card.
- CSS consumes these vars: `.folio-card { transform: translate3d(calc(-50% + var(--folio-x)), calc(-50% + var(--folio-y)), 0) rotate(var(--folio-rotation)) scale(var(--folio-scale)); opacity: var(--folio-opacity); }`.
- Mobile (`≤799px`) and no-JS: falls back to a plain static `display:grid; gap:28px` vertical list — pinning/transform disabled entirely.

### 2.6 3D rotating "drum" step list (Approach section)
- `js/motion.js::drumStepState(progress, index, count)`:
  ```js
  const position = clamp(0, count-1, clamp01(progress)*count);
  const offset = index - position;
  return {
    isActive: index === activeStepIndex(progress, count),
    rotationX: clamp(-84, 84, offset*62),
    yPercent: clamp(-130, 130, offset*94),
    scale: max(0.78, 1 - abs(offset)*0.12),
    opacity: max(0, 1 - abs(offset)*1.35),
  };
  ```
- `activeStepIndex(progress, count) = min(count-1, floor(clamp01(progress)*count))`.
- CSS: `.approach__steps { transform-style: preserve-3d }`, `.approach__window { perspective:1200px }`, each `li`: `transform: translate3d(0, calc(-50% + var(--drum-y)), 0) rotateX(var(--drum-rotate)) scale(var(--drum-scale)); opacity: var(--drum-opacity)`. This is a literal **rolodex/drum rotation in 3D space** using pure CSS `perspective` + `rotateX`, values fed from JS per scroll frame — same rAF/`getBoundingClientRect` driver as the folio.
- Track: `.approach { min-height:400svh }`, sticky panel pins for that whole scroll distance; a linear progress bar (`--approach-progress`) fills `0→100%` alongside.
- Top/bottom fade masks: `.approach__window::before/::after` — 24%-tall linear-gradients fading to the section background color, giving a "items scroll into/out of a soft-edged window" look — pure CSS, no JS.
- Mobile/no-JS/reduced-motion: `perspective:none`, all `li` become `position:relative`, static stacked list with top-border dividers.

### 2.7 Portfolio lightbox / viewer
- `js/main.js::initPortfolioViewer()` + `js/gallery.js` (tiny helper, exposes only `wrapIndex(index, count)` for modular arithmetic wraparound).
- Uses the **native `<dialog>` element** (`showModal()`/`close()`), not a custom modal framework.
- Image transition on load: `.portfolio-viewer__stage img.is-in { animation: viewer-image-in 520ms cubic-bezier(.2,.72,.2,1) both }`, `@keyframes viewer-image-in { from: opacity:0, scale(.965) translate3d(0,10px,0); to: opacity:1, none }`.
- Open/close cross-fade via `@starting-style` (native CSS, no JS): `.portfolio-viewer { opacity:0; transition:opacity 260ms ease, display 260ms allow-discrete, overlay 260ms allow-discrete }` / `[open]{opacity:1}` / `@starting-style{[open]{opacity:0}}` — same pattern for `::backdrop`.
- Prev/Next wrap via `gallery.wrapIndex`; closing outside the image/buttons closes the dialog (`event.target.closest('img, button')` check); focus returns to the trigger `<a>` on close (accessibility).
- Counter text: `IMAGE 01 / 71` etc., updated on every `render(index)`.

### 2.8 Hover states (CSS-only, no JS)
- Nav links: underline sweeps in via `transform: scaleX(0)→scaleX(1)` with `transform-origin` flip (right→left on hover), 240ms `cubic-bezier(.2,.72,.2,1)`.
- Capabilities list rows: on hover, left accent bar `scaleY(0)→scaleY(1)` (360ms), label text shifts right `translate3d(7px,0,0)`, big number shifts `translate3d(18px,0,0)`, description column shifts left and brightens — all via CSS transitions, staggered only by differing selector transition timings (280–420ms), no JS stagger logic.
- Buttons/CTAs: background/color swap 180ms ease; arrow glyph `translate3d`/`translate` nudge on hover (`.folio__archive-link`, `.contact__cta`, `.site-menu__cta`).
- Portfolio grid item image: `transform:scale(1.001)→scale(1.018)` on hover/focus (420ms `cubic-bezier(.2,.72,.2,1)`), plus a "VIEW" pill fades/slides in.

### 2.9 Marquees, carousels (traditional), parallax, cursor effects, counters, tabs, accordions, image sequences, Three.js
None present. There is no counter/odometer, no marquee/ticker, no cursor-follow effect, no tabbed UI, no accordion, no traditional autoplay carousel, no canvas/WebGL, no image-sequence scrubber (the video *is* the sequence, played natively).

### 2.10 Smooth scroll
`html { scroll-behavior: smooth }` — native CSS smooth scroll only (used for anchor nav links like `#approach`), not Lenis/GSAP ScrollSmoother. Reduced-motion media query overrides it to `scroll-behavior: auto`.

---

## 3. Libraries, loading, byte totals

**No third-party JS/CSS libraries at all.** Everything is hand-written vanilla JS (`'use strict'`, IIFE modules exposing `window.EvolutionMotion` / `window.EvolutionGallery`) and hand-written CSS. No CDN `<script>` tags anywhere in either page's `<head>`.

Script/style load order (home page `<head>`):
```html
<link rel="stylesheet" href="styles.css">
<link rel="stylesheet" href="film.css">
<script src="motion.js" defer></script>
<script src="main.js" defer></script>
<script src="film.js" defer></script>
```
Portfolio page loads `styles.css` + `gallery.js` + `main.js` only (no `film.css`/`motion.js`/`film.js` — hero-specific code isn't shipped there).

Measured byte sizes (downloaded copies in this folder):
| File | Bytes |
|---|---|
| `css/styles.css` | 33,397 |
| `css/film.css` | 3,996 |
| `js/motion.js` | 2,104 |
| `js/main.js` | 7,620 |
| `js/film.js` | 2,901 |
| `js/gallery.js` | 409 |
| **Total CSS** | **37,393 B (~36.5 KB)** |
| **Total JS** | **13,034 B (~12.7 KB)** |
| `index.html` | 17,618 B |
| `portfolio/index.html` | 75,036 B (71 image entries) |
| `assets/film/film.mp4` (desktop hero video) | 9,793,070 B (~9.3 MB) |
| `assets/film/film-m.mp4` (mobile hero video) | 6,004,622 B (~5.7 MB) |
| `assets/film/poster.webp` | 38,664 B |
| `assets/img/evo-logo1-376.webp` (favicon) | 4,480 B |
| sample folio image `img-0568-scaled-1920.avif` | 149,962 B |
| same image as `.webp` | 202,282 B (AVIF ~26% smaller, confirms `<picture>` AVIF-first strategy) |

No fonts are loaded — pure system stack: `"Helvetica Neue", Helvetica, Arial, sans-serif` for body/headings, `ui-monospace, SFMono-Regular, Menlo, monospace` for all eyebrow/label/mono text (labels, nav indices, figcaptions).

---

## 4. Design system

### Custom properties (`:root`, `css/styles.css`)
```css
:root {
  --ink: #090a0c;
  --gallery: #f2efe8;
  --paper: #fcfaf5;
  --steel: #a6adb5;
  --blue: #0c76b7;
  --blue-ink: #075f91;
  --blue-on-dark: #44a9e6;
  --white: #fff;
  --paper-ink: #090a0c;
  --paper-muted: rgb(9 10 12 / .7);
  --paper-rule: rgb(9 10 12 / .2);
  --gallery-clear: rgb(242 239 232 / 0);
  --folio-edge: rgb(255 255 255 / .42);
  --gutter: clamp(20px, 4vw, 72px);
  --max: 1600px;
  --header-h: 112px;
  color-scheme: light;
  font-synthesis: none;
}
```
Section background classes are the theming mechanism: `.section-paper` (`--gallery` bg / `--paper-ink` text), `.section-ink` (`--ink` bg / white text), `.section-blue` (`--blue` bg / white text) — the page alternates these to create rhythm (ink → paper → ink → paper → blue → ink → paper → ink).

### Type scale
All headings use `clamp()` for fluid sizing, weight 500 (never bold), tight negative letter-spacing and tight line-height for a "display" feel:
- Hero/section H2s: `clamp(46-64px, 6.5-11vw, 104-185px)`, `letter-spacing:-0.06em to -0.075em`, `line-height:.78–.86`.
- Body copy: `clamp(14-18px, 1.1-1.6vw, 18-26px)`, `line-height:1.48-1.5`.
- Eyebrow/label/mono text: fixed `9-11px`, `letter-spacing:.1-.15em`, uppercase, monospace.
- Buttons: `12-13px`.

### Container/spacing rhythm
- `--gutter: clamp(20px,4vw,72px)` used as the side padding everywhere (no fixed max-width container div — full-bleed sections with fluid gutters instead of a centered `--max` wrapper for most sections, though `--max: 1600px` exists as a cap).
- Section vertical padding consistently uses `clamp()` pairs like `clamp(90-100px, 9-14vw, 150-210px)` top/bottom — same fluid-clamp rhythm as type.
- `min-height: 100svh` (or `82svh`/`88svh`/`74svh` for shorter ones) on nearly every section — the whole page is designed as full-viewport-height "slides" you scroll through, not a dense content page.

### Buttons
- `.button`: `min-height:50px`, `border:1px solid currentColor`, flex with `justify-content:space-between` (label + arrow glyph pushed to edges), transparent background, transitions `background-color/color 180ms ease`.
- `.button--light`: inverts to white bg on hover.
- `.button--accent`: solid `var(--blue)` bg, white text, `min-height:58px`; hover inverts to white bg / blue text.
- `.text-link`: underline-only style, animated `scaleX` underline reveal on hover.

### Shadows / borders
Minimal — flat design. Only shadow found: `.folio-card { box-shadow: 12px 14px 0 rgb(255 255 255 / .08); }` (a hard offset "sticker" shadow, not a blurred drop shadow — consistent with the flat/graphic aesthetic). Borders are hairline (`1px solid rgb(255 255 255 / .16-.35)` on dark, `rgb(9 10 12 / .2)` on light) used constantly for dividers (header, nav items, capability rows, footer).

---

## 5. The "flow" mechanic — how to re-theme it for renewable-energy sectors

The reusable mechanic is **§2.3 (scroll-scrubbed hero video with discrete text states)** combined with **§2.6 (3D drum stepper)** and **§2.5 (pinned card stack)**. For a solar/wind/hydro/grid/nuclear narrative, the cleanest 1:1 port is the **hero film pattern**, because it already encodes "N sequential stages, each with a label + headline, played back by scroll position across a shared visual":

1. Replace the 7 process states (Brief→Show) with N sector states (Solar→Wind→Hydro→Grid→Nuclear...). Set `--film-span` to `N` on `.film` and add one `.film__state[data-film-state="i"]` + one `.film__steps li[data-film-step="i"]` per sector.
2. Replace the single continuous video with either (a) one continuous video that visually morphs between sector b-roll at `LEG`-second intervals (same blob-fetch + eased-`currentTime` approach — works for any evenly-spaced keyframe video), or (b) swap to a crossfading `<picture>`/`<img>` per state if you don't have a single continuous shoot — the `frame()` scroll-math and `show()` state toggle are agnostic to whether the pinned visual is a video or an image stack.
3. Reuse `motion.sectionProgress` verbatim for any other pinned/sticky section (works for arbitrarily many stages, not just 7).
4. For a step-by-step "how each sector's power gets to the grid" secondary section, reuse **either** the drum (`drumStepState`) for a vertical rolodex of stages, **or** the folio card-stack (`folioCardState`) if you want overlapping full-bleed imagery per stage (e.g., one card per sector: solar panel field → turbine → dam → substation → reactor).
5. Keep the same degrade ladder: `prefers-reduced-motion` → static first state, `<800px` viewport → disable transform math (desktopMotion check), `html:not(.has-js)` → CSS-only static stacked fallback. This 3-tier fallback is already built into every animated section and should be copied as-is.

---

## 6. Key code excerpts (verbatim)

### 6.1 `js/film.js` — full file (hero scroll-scrub engine)
```js
'use strict';
/* Scroll scrubs the hero film. Seven stills at 0,5,...,30s with six 5s legs
   between them. Each integer state holds for 15% of its scroll unit; the leg
   plays across the middle 70%. currentTime is eased toward the target so a
   fast wheel flick does not stutter through keyframes. The mp4 is fetched as
   a blob because Cloudflare Pages serves no byte ranges, and an unseekable
   source cannot scrub. */
(function initFilmHero() {
  const hero = document.querySelector('[data-film-hero]');
  if (!hero) return;
  const film = hero.querySelector('[data-film-video]');
  const states = [...hero.querySelectorAll('[data-film-state]')];
  const steps = [...hero.querySelectorAll('[data-film-step]')];
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const LEG = 5;
  const LAST = states.length - 1;

  let current = -1;
  const show = (index) => {
    if (index === current) return;
    current = index;
    states.forEach((el) => el.classList.toggle('is-on', Number(el.dataset.filmState) === index));
    steps.forEach((el) => el.classList.toggle('is-on', Number(el.dataset.filmStep) === index));
  };

  const src = window.innerWidth < 800 ? 'assets/film/film-m.mp4' : 'assets/film/film.mp4';
  const load = () => fetch(src)
    .then((r) => r.blob())
    .then((blob) => { film.src = URL.createObjectURL(blob); film.load(); })
    .catch(() => { film.src = src; film.load(); });

  if (reduce) { show(0); return; }

  let target = 0;
  let raf = 0;
  let seeking = false;
  film.addEventListener('seeked', () => { seeking = false; });

  const tick = () => {
    if (raf) return;
    raf = requestAnimationFrame(() => {
      raf = 0;
      if (film.readyState < 2) { tick(); return; }
      const delta = target - film.currentTime;
      if (Math.abs(delta) < 1 / 48) return;
      if (!seeking) { seeking = true; film.currentTime += delta * 0.22; }
      tick();
    });
  };

  const frame = () => {
    const rect = hero.getBoundingClientRect();
    const vh = window.innerHeight;
    const p = Math.min(1, Math.max(0, -rect.top / (rect.height - vh)));
    const t = Math.min(LAST, (p / 0.92) * LAST);
    const s = Math.floor(Math.min(t, LAST - 0.001));
    const f = t - s;
    const g = Math.min(1, Math.max(0, (f - 0.15) / 0.7));
    target = (s + g) * LEG;
    show(f < 0.5 ? s : Math.min(LAST, s + 1));
    steps.forEach((el, i) => el.style.setProperty('--fill', Math.min(1, Math.max(0, t - i)).toFixed(3)));
    tick();
  };

  let scheduled = false;
  const schedule = () => {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => { scheduled = false; frame(); });
  };
  window.addEventListener('scroll', schedule, { passive: true });
  window.addEventListener('resize', schedule);
  film.addEventListener('loadedmetadata', frame);
  load();
  frame();
}());
```

### 6.2 `js/motion.js` — full file (pure math module, no DOM access)
```js
'use strict';

(function exposeMotion(root) {
  const clamp01 = (value) => Math.min(1, Math.max(0, Number(value) || 0));

  const sectionProgress = (rect, viewportHeight) => {
    const range = Math.max(rect.height - viewportHeight, 1);
    return clamp01(-rect.top / range);
  };

  const activeStepIndex = (progress, count) => {
    if (count <= 1) return 0;
    return Math.min(count - 1, Math.floor(clamp01(progress) * count));
  };

  const folioCardState = (progress, index, count) => {
    const position = clamp01(progress) * Math.max(count - 1, 0);
    const offset = index - position;
    const direction = index % 2 === 0 ? 1 : -1;
    const exit = clamp01((-offset - 0.08) / 0.82);
    const depth = Math.max(0, Math.min(4, offset));
    const captionDistance = Math.abs(offset);
    return {
      xPercent: exit > 0 ? direction * 36 * exit : direction * depth * 2.8,
      yPercent: exit > 0 ? -76 * exit : depth * 3.2,
      rotationDeg: exit > 0 ? direction * 3.5 * exit : direction * depth * 0.8,
      scale: exit > 0 ? 1 - 0.03 * exit : Math.max(0.9, 1 - depth * 0.028),
      opacity: exit > 0 ? 1 - 0.96 * exit : Math.max(0.58, 1 - depth * 0.1),
      captionOpacity: exit > 0 ? 0 : 1 - clamp01(captionDistance / 0.45),
      zIndex: count - index,
    };
  };

  const drumStepState = (progress, index, count) => {
    const position = Math.min(Math.max(count - 1, 0), clamp01(progress) * count);
    const offset = index - position;
    const activeIndex = activeStepIndex(progress, count);
    return {
      isActive: index === activeIndex,
      rotationX: Math.max(-84, Math.min(84, offset * 62)),
      yPercent: Math.max(-130, Math.min(130, offset * 94)),
      scale: Math.max(0.78, 1 - Math.abs(offset) * 0.12),
      opacity: Math.max(0, 1 - Math.abs(offset) * 1.35),
    };
  };

  const api = { activeStepIndex, clamp01, drumStepState, folioCardState, sectionProgress };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.EvolutionMotion = api;
}(typeof window !== 'undefined' ? window : globalThis));
```

### 6.3 `main.js` — reveal observer + scroll-motion driver (excerpt)
```js
const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (!entry.isIntersecting) return;
    entry.target.classList.add('is-visible');
    observer.unobserve(entry.target);
  });
}, { rootMargin: '0px 0px -10% 0px', threshold: 0.06 });
items.forEach((item) => observer.observe(item));

// per-frame scroll driver (folio + approach + header progress), rAF-batched:
const update = () => {
  scheduled = false;
  const viewport = window.innerHeight;
  if (header) {
    const pageRange = Math.max(document.documentElement.scrollHeight - viewport, 1);
    const pageProgress = Math.min(1, Math.max(0, window.scrollY / pageRange));
    header.classList.toggle('is-scrolled', window.scrollY > 48);
    header.style.setProperty('--page-progress', String(pageProgress));
  }
  if (!reduceMotion && desktopMotion.matches && motion && folio && folioCards.length) {
    const progress = motion.sectionProgress(folio.getBoundingClientRect(), viewport);
    folioCards.forEach((card, index) => {
      const state = motion.folioCardState(progress, index, folioCards.length);
      card.style.setProperty('--folio-y', `${state.yPercent}%`);
      card.style.setProperty('--folio-x', `${state.xPercent}%`);
      card.style.setProperty('--folio-rotation', `${state.rotationDeg}deg`);
      card.style.setProperty('--folio-scale', String(state.scale));
      card.style.setProperty('--folio-opacity', String(state.opacity));
      card.style.setProperty('--folio-caption-opacity', String(state.captionOpacity));
      card.style.zIndex = String(state.zIndex);
    });
  }
  // ...same pattern for .approach drum steps
};
```

### 6.4 Key CSS — hero pin + text crossfade
```css
.film { position: relative; height: calc(var(--film-span, 7) * 100vh + 100vh); background: var(--ink); color: var(--white); }
.film__stage { position: sticky; top: 0; height: 100vh; height: 100svh; overflow: hidden; background: var(--ink); }
.film__video { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; object-position: 62% 50%; }
.film__state { grid-area: 1 / 1; max-width: min(46vw, 680px); opacity: 0; transform: translateY(18px); transition: opacity 420ms ease, transform 520ms cubic-bezier(.2,.72,.2,1); }
.film__state.is-on { opacity: 1; transform: none; pointer-events: auto; }
.film__state.is-on .button--accent { animation: film-cta-in 640ms cubic-bezier(.2,.72,.2,1) 120ms both; }
@keyframes film-cta-in { from { opacity:0; transform:translate3d(0,12px,0) scale(.94); } to { opacity:1; transform:none; } }
```

### 6.5 Key CSS — folio card stack & approach drum
```css
.folio { position: relative; min-height: 500svh; }
.folio__sticky { position: sticky; top: 0; height: 100svh; overflow: hidden; }
.folio-card { position: absolute; top: 50%; left: 50%; width: min(72vw, 1120px); aspect-ratio: 4/3;
  transform: translate3d(calc(-50% + var(--folio-x)), calc(-50% + var(--folio-y)), 0) rotate(var(--folio-rotation)) scale(var(--folio-scale));
  opacity: var(--folio-opacity); will-change: transform, opacity; }

.approach { min-height: 400svh; }
.approach__window { height: min(48vh, 440px); overflow: hidden; perspective: 1200px; }
.approach__steps { position: absolute; inset: 0; transform-style: preserve-3d; }
.approach__steps li { position: absolute; top:50%; right:0; left:0;
  transform: translate3d(0, calc(-50% + var(--drum-y)), 0) rotateX(var(--drum-rotate)) scale(var(--drum-scale));
  opacity: var(--drum-opacity); will-change: transform, opacity; }
```

### 6.6 Reveal CSS
```css
.has-js [data-reveal] { opacity: 0; transform: translateY(34px); transition: opacity 750ms cubic-bezier(.2,.72,.2,1), transform 750ms cubic-bezier(.2,.72,.2,1); }
.has-js [data-reveal].is-visible { opacity: 1; transform: none; }
```

---

## 7. Performance notes

- **Heaviest assets by far**: the two hero videos (`film.mp4` ≈9.3MB desktop / `film-m.mp4` ≈5.7MB mobile). Both are loaded via `fetch()`→blob rather than progressive streaming, meaning the **entire video downloads before scrubbing works at all** — a real trade-off accepted specifically to get scrub-seek behavior on Cloudflare Pages (no HTTP range support). `preload="none"` on the `<video>` tag itself avoids the browser's own eager preload; the JS-driven `fetch` is what actually pulls the bytes, kicked off immediately on script execution (not lazy/deferred by viewport).
- **Poster image** (`poster.webp`, 38.7KB) shows before the video blob resolves — good perceived-performance fallback.
- **Portfolio images**: everywhere uses `<picture>` with AVIF-first, WebP-fallback `<source>`s and responsive `srcset` (960w/1440w/1920w tiers). Home-page folio images are `loading="lazy" decoding="async"`. Portfolio-grid first-row images use `loading="eager" fetchpriority="low"` (visible above the fold but deprioritized relative to critical assets); rest are `loading="lazy"`.
- **No web fonts** — system font stack only, eliminates FOIT/FOUT entirely and saves a full network round-trip class.
- **JS footprint is tiny** (~13KB total, unminified, no bundler artifacts, no library payload) — the entire animation system costs less than a single hero image tier.
- **`prefers-reduced-motion: reduce` is respected thoroughly**: disables the video scrub (shows static first frame/poster), collapses all `min-height:400-500svh` scroll-jacked tracks to normal single-viewport `min-height:100vh`/`auto` sections with `position:relative` (un-pins them), forces `scroll-behavior:auto`, sets a global `animation-duration:1ms !important; transition-duration:1ms !important` safety net, and forces all `[data-reveal]` content to be visible immediately. This is one of the more complete reduced-motion implementations possible — every scroll-jacked section has an explicit static fallback, not just a global animation-duration hack.
- **No-JS fallback** (`html:not(.has-js)`) is also handled explicitly for the folio, approach, and film sections — content remains fully readable/navigable with CSS alone if JS fails to load, via a `document.documentElement.classList.add('has-js')` inline script at the very top of `<head>` (progressive enhancement, not a `<noscript>` block).
- **Accessibility of animations**: reveal/scroll effects are purely visual — no content is hidden from AT (ARIA structure unaffected); the hero's `<video>` has `aria-hidden="true"` since it's decorative and the actual copy is in real DOM text; focus management is correct in both the mobile nav (`inert`, focus-trap-lite) and the portfolio `<dialog>` (focus moves to close button on open, returns to trigger on close); `:focus-visible` gets a clear 2px blue outline site-wide.
- **CLS risk**: all `<img>` have explicit `width`/`height` attributes, and hero copy is absolutely positioned (`grid-area: 1/1`) rather than reflowing — low layout-shift risk despite heavy dynamic content.
