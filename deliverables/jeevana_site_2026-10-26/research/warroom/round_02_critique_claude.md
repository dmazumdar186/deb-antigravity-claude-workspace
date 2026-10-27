# Round 2 critique by anthropic/claude-opus-5.5

# Jeevana v4 review: other lab, senior design and front-end pass

**Verdict:** The bones are good, but this cannot ship. Gates are red because the DOM contract was renamed throughout, the privacy page crashes, and the fluid/orientation addendum is mostly unbuilt. The wow is not there yet: the strip has no backdrop of its own, and the micro-type reads like a template.

## Fixes, most important first

1. **[P1] index.html, i18n.js, main.js (global): DOM contract renamed everywhere.** This is why functional_v4 timed out and screens_v4 crashed. Rename verbatim:
   - `.site-header` → `<header class="bar">`
   - `data-language` → `data-lang`
   - ids `#home` → `#top` and `#twelve-breaths` → `#twelve`, with nav hrefs updated
   - `#hero-title` → `id="h1"` plus `aria-label` (i18n via `data-i18n-aria`)
   - `#breath-strip` → add `data-strip`; `.breath-card` → `article.card`
   - `data-position-text` → `data-cur`
   - `data-success` → `data-ok="register|subscribe"`; `data-form-status` → `p[data-err]`
   - every photo `<img>` gets `class="ph"`
   - localStorage `jeevana-language` → `jv_lang`
   - expose `window.JV_strip={cur:()=>active,playing:()=>requested,go}`

2. **[P1] main.js (whole IIFE): privacy page throws 8× "null.classList".** Guard every lookup, for example `if(header) …` and `if(track){…strip block…}`, and split the strip and forms into functions that return early. Add the `data-lang` buttons and `data-lang-block` toggling for `/privacy/`.

3. **[P1] index.html `<svg class='cover-wheel'><use href>`: backdrop structure off-contract.**
   - Inline two real SVGs: `svg.twelve.twelve--cover` and `svg.twelve.twelve--strip`.
   - Each needs `g.spin` and twelve `path.arc[data-n]`, with the lit arc marked `.on`.
   - Styling and animating through `<use>` shadow trees is fragile. It also makes all six mini-wheels rotate and light up together.
   - Mini rings: `svg.mini > circle.mini__f`, set through `style.strokeDashoffset`, set to `"0"` at load under reduced motion.

4. **[P1] #twelve: the signature has no backdrop.** "The centred card drives the backdrop's lit arc" currently lights an arc on the cover, three screens away.
   - Place `twelve--strip` (about 70 vmin) behind-left of the strip on the `--mist` field.
   - Cross-fade the lit arc (`transition: stroke 600ms`).
   - Breathe the ring's centre on the active card's breath word: inhale scales up, exhale scales down, retain holds. Then one breath visibly moves through twelve photographs.

5. **[P1] styles.css `.consent input`: gate fail.** Set `font-size:16px;width:20px;height:20px`.

6. **[P1] styles.css (tap targets).** Gate measured `.wordmark` at 34 px high, nav links at 37–39 px wide, language buttons at 27 px wide, `.button-small` at 38 px and `.cover-foot a` at 31 px. Under `@media(hover:none)`, make all of them `min-height:44px;min-width:44px`.

7. **[P1] main.js reveal observer: fling leaves an element invisible.** Treat elements already passed as revealed:

   ```js
   if (e.isIntersecting || e.boundingClientRect.top < 0) {
     e.target.classList.add('is-visible');
   }
   ```

   Also remove `data-reveal` from `.cover-portrait`. The LCP image must never start at opacity 0.

8. **[P1] i18n.js load: FOUC for FR users.** "Applied before first paint" fails with `defer`.
   - Load `i18n.js` without `defer` in `<head>`.
   - Set `documentElement.lang` and a `.i18n-wait{visibility:hidden}` class synchronously, then swap text on `DOMContentLoaded`.
   - This stays CSP-safe because it uses no inline script.

9. **[P1] styles.css (responsive addendum largely missing).** Add:
   - `--max` of 1680/2200; gutter `clamp(16px,4vw,96px)`
   - display type `clamp(2.2rem,…,7rem)` and body `clamp(1rem,…,1.35rem)`, replacing the fixed 15px
   - `(orientation:portrait)`, `(orientation:landscape) and (max-height:500px)` and `(min-aspect-ratio:21/9){max-height:86svh}` queries
   - `env(safe-area-inset-*)` padding

   At 3840 the page is currently a 1280 px column with 9 px labels.

10. **[P1] `.breath-strip --card-width`: card counts per breakpoint are wrong.** Set the card width as `(100% − gaps)/N`, with N = 1 plus peek on phones, 2 on tablet portrait, 3 on tablet landscape and laptops, 4 at ≥1920, 5 at ≥3200. Cap it with `min(…, 70svh*.75)`. At 844×390 the caption currently falls off-screen.

11. **[P2] styles.css (micro-type).** A designer will wince at the 9–11 px text: eyebrows, chips, footer, `.sequence-note`, consent, `.step-breath`. Set the floor at 12 px for labels and 14 px for legal text, tracking .12em. Keep the hierarchy through contrast and case, not size.

12. **[P2] Contrast.** `--ochre-text #9A5A12` on `--mist #E7DFD0` is about 4.1:1 and fails; it is used for `.step-breath` and the play controls in #twelve. Use `#86500F` on mist. The disabled `.button` at opacity .6 also fails, so use a solid muted colour instead.

13. **[P2] main.js `schedule()`: loop at card 12 → 1.** The smooth scroll rewinds across eleven cards, which looks like a tape rewind. Either stop at 12 and reset the play state, or jump instantly with a 300 ms fade.

14. **[P2] main.js forms.**
   - Add `novalidate`. Native `reportValidity` bubbles bypass `p[data-err]`, so run client checks and show the i18n error instead.
   - The subscribe form is missing the optional `phone` field.
   - Fire the `subscribe` beacon on a 200, not on click.
   - Use `fetch(…,{keepalive:true})` rather than `sendBeacon`, because the contract asserts fetch.

15. **[P2] srcset and sizes.**
   - Strip cards omit 2000w and use a fixed `364px` size; derive `sizes` from N per breakpoint.
   - The hero `sizes` caps at 480px, so 2800 is never chosen on 4K.
   - Practice images use `40vw/25vw` against a 1280 container; match the real columns.

16. **[P2] OG image.** `hero@1400` (4:5) is used as is. The brief requires a 1200×630 render with a paper margin, so create `og.webp` (or a JPG for scrapers).

17. **[P2] Word reveal.** The 30 ms stagger reads as a single fade. Use about 80 ms per word, keeping 620 ms duration and 14 px travel.

18. **[P3] Content tension.** `sequenceNote` says "never … hold the breath", while card 6 says "Retain the breath". Soften the note to "…if retaining feels uncomfortable, breathe freely".

19. **[P3] Wordmark.** Drop the ochre "." because the brief specifies "Jeevana". Move the hardcoded `noscript` and chip strings into i18n.

20. **[P3] Weight gate.** It reports 104 K total, which suggests the photos were not measured or deployed. Verify that `assets/photos/*` exist, then re-run.

**Invented facts:** none found. The Tapovan line, prices, timetable and both consent strings are verbatim and correct.

## Already excellent: do not lose

1. **The strip engine** in main.js:
   - nearest-centre detection
   - mouse-only drag with a 6 px threshold and pointer capture
   - autoplay that pauses on hover, focus, hidden tab and off-screen
   - `aria-live` switched off while playing
   - Home/End keys

   Rename the hooks; keep the logic.
2. **Photo treatment** in `.frame`: the warm `#FBF8F1` mat, 20 px radius, a shadow softer than the reference, a quiet 4 px hover lift and glass chips. These read as photographs placed on paper, with no plates and no gradients.
3. **Copy discipline and i18n.** The texts are generic-true, both consent strings are verbatim in EN and FR, the FR is idiomatic, and server errors map to reassuring "your details are kept" messages.
