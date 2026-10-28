# Panel lens 8 — Sutskever (capability & failure modes)

**Verdict: PASS with caveats.** The one model-written file that runs in the browser (backdrop.js) is small, has nothing to fetch or reach, and is guarded. The risk sits in the content: the copy and photo labels came from models, and nothing re-checks them automatically.

## Findings
1. **Backdrop is bounded.** It sets one global (`window.JeevanaBackdrop`, site/js/backdrop.js:89). It has no fetch, eval, network or console calls. The particle count is fixed at 90–260 (:11), so a 4K canvas still gets 260 particles. The hairline pass compares about 34k pairs per frame and draws only 1/3 of them (:46). The DPR cap is `min(1.5, devicePixelRatio)` (:21). No unbounded loops.
2. **Lifecycle is correct.** ResizeObserver is disconnected in destroy (:86). Animation pauses on `visibilitychange` (:73). Reduced motion draws one still frame and never starts rAF (:80, :82).
3. **Throw path is guarded.** main.js wraps init and setProgress in try/catch and sets `bdOn=false` (site/js/main.js:163,167). `getContext` failure returns early (backdrop.js:75). The global `error` handler removes `has-js` (main.js:13). Broad: any uncaught error drops the page to no-JS layout.
4. **Cost hotspot.** `shadowBlur=max(40, cw*.04)` comes to about 150 px at 4K (backdrop.js:60). Redrawn every frame; measure it.
5. **The log does not match the code.** glm_log.md says "sun disc moved to x .34", but the code has `cw*.16` (backdrop.js:59, also :67). So the review record cannot prove what shipped. Fix: log a hash of the reviewed file.
6. **Photo map can be checked by a person.** research/photos.md:6-19 is a step→file table. The worst plausible mislabel is a mirror-pose swap, e.g. 04 vs 09 (Aśva Sañcalanāsana, leg forward) or 03 vs 05 (forward fold vs inverted V). A teacher would spot it at once. Jeevana's sign-off is not recorded.
7. **Spelling drift in the copy.** photos.md:10 has "Sañcālanāsana", while i18n.js:9 has "Sañcalanāsana" (the usual spelling). No check catches model-written diacritics.
8. **Mantras.** The 12 names in i18n.js:6-17 follow the standard order (Mitra → Bhāskara), and the Devanagari matches the IAST for the asanas. No file records a source or a native-reader check. functional.mjs only checks that the rail text exists, not that it is correct.

## Honest gaps
- I did not run the page or profile it at 4K. Findings 1 and 4 come from reading the code.
- I checked the mantras and diacritics against my own knowledge, not a cited source. Recommend Jeevana signs off on the copy and the photo map before go-live, plus a fixture test that pins the 12 (dev, iast, mantra) triples.
- Glosses in i18n.js beyond lines 1-17, 45 and 50-51 not read.
- No regression check would show a weaker model's output: a later backdrop regeneration has no bundle limits or forbidden-API grep in CI.
