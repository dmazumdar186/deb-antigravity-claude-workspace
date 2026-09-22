# GreenJobs redesign — design critique (2026-09-22)

⚠️ DEGRADED: single-context (no sub-agent tool exposed to this worker; Assessment A and detector run inline, detector first-pass hits reviewed after the visual pass).

Scope: 26 screenshots in `.tmp/greenjobs_redesign_shots/`, `src/css/styles.css`, `src/templates/*.html`, `src/js/{main,compass,charts}.js`. Detector (`impeccable detect.mjs`) on `site/`: 2× `layout-transition` (width), em-dash overuse on home/insights/for-keith, numbered-marker advisories (false positives from job IDs and "01 912 5247" phone strings; ignore).

Overall verdict: not AI-slop. Committed moss/lime strategy, one display family (Archivo wide) + one text family, a real choropleth, sparklines, a working quiz and a command palette are far beyond a template. The gap to "top 0.1%" is craft, not concept: three rendering bugs, illegible small text on every data surface, and a page rhythm that collapses on mobile.

Heuristic scores (0-4): visibility of status 4 · match to world 3 · control/freedom 3 · consistency 3 · error prevention 3 · recognition 3 · flexibility 4 · aesthetic/minimal 3 · error recovery 3 · help 2.

---

## Ranked fix list

### 1. BLOCKER — Compass result page renders blank
**Seen in:** `ie-compass-result-390.png` (progress bar at 100 %, nothing below it, 2,000 px of paper).
**Wrong:** `compass.js` `results()` builds the whole result via one `innerHTML` string; any exception (a job with no `regions`, `G.annual()` returning null on `.hi`, empty `jobs` before data resolves) leaves `host` empty. The state is reachable from a shared link, so a candidate who saved their result sees nothing.
**Change:** in `compass.js` wrap `results()` in `try { … } catch (e) { host.innerHTML = fallback; }` where `fallback` is the three top sectors with a plain "See live roles" link; guard `(G.annual(j) || {}).hi`; call `render()` only after `GJData()` resolves. Add a server-rendered `<noscript>`/pre-JS block in `templates/compass.html` under `.prog`: `<p class="muted">Loading your compass…</p>` so the region never ships empty. Add a Playwright check that `#a=` URLs render `.res`.

### 2. BLOCKER — Home choropleth is flat until JS runs; region numbers illegible
**Seen in:** `ie-index-1440-tall.png`, `dark-ie-index-1440.png` (every county the same moss, ~8 px grey numerals); `rm-ie-index-1440.png` (correct fills, proving the data exists).
**Wrong:** `data-lvl`/`data-n` are set only by `GJMap()` in `main.js:183`; the `.reveal` IntersectionObserver plus the canvas init delay the paint, so the first screenshot (and any crawler, print, or slow device) shows a monochrome map. Count labels inherit a 12 px `Archivo` at a ~0.45 SVG scale, so they render ~6 px on screen.
**Change:** (a) emit `data-n` and `data-lvl` in the build step into `templates/home.html` `{{map}}` so CSS lines 273-276 colour it at first paint; JS only re-labels. (b) In `styles.css` line 280 replace `font:600 12px` with `font:700 clamp(11px,1.1vw,14px)` and set `.gmap{max-height:none}` on `<1024px`; or drop in-region numerals below 900 px and rely on the `.maplist` (which is already the accessible path). (c) Add `.gmap__r[data-n="0"] text{display:none}`.

### 3. BLOCKER — Titles truncate with ellipsis on mobile
**Seen in:** `ie-jobs-390-tall.png` ("Senior Engineer – Transmission & Distributio…", "Senior Sustainability Lead" clipped), `uk-jobs-map-390.png` ("Site Manager - Ham W").
**Wrong:** `.row h3` sits in a grid track next to the 36 px `.save` button with `white-space`/overflow inherited from the `.row` grid and `padding-right:44px` only on `.row__r`; job titles are the product and must never be cut.
**Change:** `.row__body{min-width:0}` is present but `.row h3{overflow-wrap:anywhere;text-wrap:balance}` is missing; add it, and on `<640px` set `.row{padding-right:56px}` so the save button never overlaps. Same for `.role h3` on the home cards.

### 4. SHOULD — Chart labels are unreadable on every breakpoint
**Seen in:** `ie-insights-1440-tall.png` (category labels clipped with "…" at 26 chars: "Built environment & energ…", "Energy networks & utiliti…"; value labels 11 px), `ie-insights-390-tall.png` and `dark-ie-insights-390.png` (labels ≈ 6-7 px), `ie-sectors-390.png` (treemap text ≈ 6 px, counts invisible).
**Wrong:** `charts.js:31` hard-truncates at 26 chars; SVG scales with width so 11-13 px fonts shrink on mobile; `.fig svg{width:100%;height:auto}` has no minimum.
**Change:** (a) Horizontal bars: put the label *above* the bar as an HTML row (`<div class="hbar"><span>label</span><i style="--w:76%"></i><b>76%</b></div>`), not inside the SVG; remove the `short()` truncation. (b) Vertical bars: `viewBox` height fixed, `preserveAspectRatio="none"` only for the bar layer, and `.fig .axis text{font-size:12px}`, `.fig .lbl{font-size:12px}`. (c) Treemap: below 720 px hide the treemap (`@media (max-width:719px){.treemap{display:none}}`) and show the `secrow` list already on the page; at desktop set `.treemap text{font-size:14px}` and hide labels when `rect.width < 90`. (d) Add `min-height:220px` to `.fig svg` on mobile.

### 5. SHOULD — Sector grid leaves an empty cell; hero-metric stat row
**Seen in:** `ie-index-1440-tall.png`, `dark-ie-index-1440.png`: row 2 of "Where the work is" ends one column short. `ie-insights-1440-tall.png`: four stat tiles where the fourth ("€ — all figures in € per year") is not a metric.
**Wrong:** 1 lead tile (span 2) + 7 tiles = 9 cells in a 5-column auto-fit grid. The stat tiles are the banned big-number/small-label template, and one of them is a footnote dressed as a KPI.
**Change:** show all 10 sectors (lead + 9 = 11 cells → use `grid-template-columns:repeat(5,1fr)`, lead `grid-column:span 2;grid-row:span 2`, 9 tiles fill 3 rows exactly), or cap at lead + 8. On insights, delete the `€` tile and put its sentence as the `.lede`'s second line; render the remaining three as one inline sentence with `<strong>` numbers (`88 live roles · 33 % disclose a salary · median €52.5k`) styled `font-size:var(--h3)`.

### 6. SHOULD — Contrast failures on meta text, both themes
**Seen in:** `ie-jobs-1440-tall.png` ("5 days ago / Permanent" in `--fg-3 #7a877e` on white ≈ 3.6:1 at 13 px), `dark-uk-jobs-1440.png` (`#84958a` on moss-800 ≈ 3.9:1), `.fig .axis text` (`--fg-2` at 11 px), hero legend (`.78rem` on moss).
**Change:** `--ink-400:#5f6d64` (≈ 5.2:1 on white) and dark `--fg-3:#9fb0a4` (≈ 5.1:1 on `#173225`); raise `--tiny` from `.8125rem` to `.85rem`; `.hero__legend{font-size:.85rem}`. Keep `--fg-3` only for decorative separators.

### 7. SHOULD — Hero pushes content below the fold on tablet/mobile
**Seen in:** `ie-index-768.png`, `ie-index-390-tall.png`: `min-height:min(92vh,880px)` with `align-items:end` yields ~400 px of empty particle field above the headline; the search box is off-screen on a 390×844 phone.
**Change:** `@media (max-width:899px){.hero{min-height:auto;align-items:start}.hero__in{padding-block:clamp(56px,10vw,96px) 48px}}`. Keep the tall hero at ≥900 px where the legend and wind field earn the space.

### 8. SHOULD — Mobile page rhythm: everything becomes one long column
**Seen in:** `ie-index-390-tall.png` (8 full-height sector tiles then 8 role cards, ~5,000 px before the map), `ie-insights-390-tall.png` (4 stat tiles stacked).
**Change:** `.sectors` on `<560px`: `grid-template-columns:1fr 1fr;gap:10px` with `.sect{min-height:140px;padding:16px}` and the sparkline hidden (`.sect svg{display:none}`); `.roles` on mobile: show 4 (`.role:nth-child(n+5){display:none}`) with the "All 88 roles" button under them; stat tiles `grid-template-columns:repeat(2,1fr)`.

### 9. SHOULD — Light-theme dark band map and marquee are two different treatments of the same idea
**Seen in:** `ie-index-1440-tall.png` vs `ie-jobs-map-1440.png`: the home map is dark-on-moss with lime fills, the jobs map is lime-on-paper; the marquee's first logo is half-faded by the mask (`Mattinson` at x≈40).
**Change:** keep one map language: use the `.on-paper` ramp on both, or give the jobs `.mapview` the moss band. Marquee: `mask-image:linear-gradient(90deg,transparent,#000 8%,#000 92%,transparent)` → start the track with `padding-inline-start:8%` so the first logo is never under the fade.

### 10. SHOULD — Ellipsis and copy tells
**Seen in:** home lede, insights lede, employers lede; detector flags 6-8 em-dashes per page.
**Change:** rewrite the three ledes with full stops; keep at most one dash per page. Home lede: "88 live green roles across Ireland. Wind, water, waste, wildlife, and the people who make the numbers add up. Search in a second, filter by county, save what fits."

### 11. POLISH — Empty state and error prevention
**Seen in:** `ie-jobs-empty-768.png`: good recovery chips, but the dashed border reads as a drop zone and the chip labels omit counts.
**Change:** `.empty{border:1px solid var(--line)}`, chips show counts ("Environmental science & consulting · 65"), and put "Clear all filters" as `btn--lime` since it's the most likely action.

### 12. POLISH — Touch targets
**Seen in:** `ie-jobs-390-tall.png` bookmark icons (36 px, 8 px from card edge), `.chip button` remove (34 px), `.edsw a` (32 px), `.seg button` (38 px).
**Change:** `.row .save{width:44px;height:44px;right:8px;top:8px}`, `.chip{min-height:40px}`, `.chip button{width:32px;height:32px;margin:-4px}`, `.edsw a,.seg button{min-height:40px}`; footer links `min-height:40px`.

### 13. POLISH — Job page
**Seen in:** `ie-job-1440.png`, `ie-job-768.png`: 80 px dead space above the breadcrumb; body line length ~95 ch at 1440; "Apply on greenjobs.ie" is a secondary-looking pill for the primary action.
**Change:** `.job__head{padding-top:clamp(24px,4vw,48px)}`, `.job__body{max-width:70ch}`, `.job__actions .btn--lime{min-height:56px;font-size:1.05rem}` and duplicate the apply CTA as a sticky bottom bar on `<960px` (`position:sticky;bottom:0;padding:12px var(--gutter);background:var(--bg)`).

### 14. POLISH — Motion that would raise "wow" at ~zero cost
All transform/opacity or SVG stroke; all already gated by the `prefers-reduced-motion` block at line 564.
- Sparklines draw in: `.sect path{stroke-dasharray:1;stroke-dashoffset:1;pathLength:1}` and `.reveal:not(.pre) .sect path{animation:draw .9s var(--ease) forwards}` with `@keyframes draw{to{stroke-dashoffset:0}}`.
- Choropleth stagger: `.gmap__r path{transition-delay:calc(var(--i)*18ms)}` and set `--i` per region in the build; fills sweep across the island on reveal.
- Count-up on hero numbers: 600 ms `requestAnimationFrame` tween on `.hero__count b` (text only, no layout).
- Bars grow with `transform:scaleX()` + `transform-origin:left` instead of `width` (also fixes the two detector `layout-transition` hits at `.prog i` and `.res__sec .barw i`).
- Header: `.hdr.is-stuck{border-color:var(--line);box-shadow:0 1px 0 var(--line)}` is defined but there is no visible tint change; add `background:color-mix(in srgb,var(--bg) 92%,transparent)`.
- Row hover uses `translateX(3px)`; the whole list shifts. Prefer `box-shadow` + `border-color` only (`transform:none`).
- View transitions are on (`@view-transition{navigation:auto}`) but nothing is named; add `view-transition-name:job-title` on `.row h3` → `.job h1` for a shared-element morph on the most-used path.

### 15. POLISH — Dark theme specifics
**Seen in:** `dark-uk-jobs-1440.png` (rows sit on `--card:moss-800` against `moss-950`, border almost invisible), `dark-ie-insights-390.png` (stat tiles with no border; charts lime-on-moss fine).
**Change:** `[data-theme="dark"]{--line:oklch(.34 .045 158)}`; `.tag--sal` dark text `--moss-950` on `--lime-500` (already) but `.tag` default text `--dark-fg-2` on `moss-700` needs `--dark-fg`.

### 16. POLISH — Chooser page
**Seen in:** `chooser-1440.png`: 1,000 px block centred, right 40 % empty; `chooser-390.png` fine.
**Change:** `.choose__in{max-width:1100px}`, tiles `grid-template-columns:1fr 1fr` with a faint outline of each island (`assets/ie.svg`, `assets/uk.svg`) as `.tile::after` at 12 % opacity. Cheap, on-brand, memorable.

---

## What would make a managing director feel this is worth far more than €1,875

1. **The data is real and it moves.** Every number on the home page is computed from live listings; state that in one line under the hero ("Every figure on this site is computed from today's listings, not typed in"). Fix items 1-2 so the two showpieces (map, compass) never show blank.
2. **Shareable everything.** Filters live in the URL, the compass result is a link, the map deep-links to a county. Add "Copy link" affordances (toast exists) on the jobs page header and on each sector page so the MD sees it.
3. **An employer story.** `ie-employers-1440.png` is honest but flat: add a mock "Featured employer" band with a real logo, three live roles and a "Your logo here" state; MDs buy postings, not candidates.
4. **Perceived speed.** No framework, self-hosted fonts, ~46 KB CSS. Put a Lighthouse 100/100/100/100 card in the handoff; it is the cheapest "premium" signal.
5. **Print and a11y.** Print stylesheet and keyboard map navigation exist; demonstrate them in the walkthrough video.

## Honest gaps

- No browser injection or live detector overlay was run (headless only via screenshots); hover, focus, tooltip, palette and view-transition behaviour are judged from CSS, not observed.
- Compass blank-result root cause is inferred from code shape, not from a captured console error.
- Contrast ratios are estimates from the hex tokens, not measured against the rendered OKLCH overrides (`@supports (color:oklch(...))` block at line 40 changes several values).
- Sector detail pages, 404, `for-keith`, and the command palette were not screenshotted and are not critiqued.
- No performance trace: the hero `canvas` wind field and the 40 s marquee are the only likely CPU costs and were not profiled.
- Copy was not checked for IE/UK spelling consistency or for Irish county completeness (map lists 14 counties with roles; tooltip strings only spot-checked).
