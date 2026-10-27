Mechanics admired by the operator on evolution-exhibits-v4.pages.dev. Inspiration only: Jeevana's page is paper, photographs and breath, not a video scrub.

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

