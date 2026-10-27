# Round 8 critique by openai/gpt-6.1-sol-pro

**Verdict: HOLD.** The supplied gates show solid functionality, not contractual compliance or “wow.” No PNGs were supplied for direct visual review; composition findings below are source-based. Latest operator addenda override stale HANDOFF facts.

1. **[P1] [site/index.html:#classes; site/js/i18n.js:classes copy; research/functional_v4.mjs]** Verified pricing is entirely missing, and tests incorrectly celebrate “no €” → Add €50/one-hour individual and online sessions, 5 hours €250, 10 hours €500, and in-home €25/hour **“after tax credit (crédit d’impôt)”**, in EN/FR. Keep small groups/workshops by arrangement. Replace the obsolete no-price assertions with exact pricing checks.

2. **[P1] [site/index.html:.consent; site/js/i18n.js:registerConsent, subscribeConsent]** All four displayed consent strings differ from the backend contract → Copy the EN/FR strings **verbatim** from each endpoint’s `CONSENT_TEXT` into HTML fallback and dictionaries. Keep `consent:true`; add exact-string assertions. Existing mocked submission passes do not verify informed-consent wording.

3. **[P1] [site/css/styles.css::root, “v5” overrides; site/index.html:.hero-frame, #paris]** The implementation changes the commissioned art direction: yellow manuscript paper, vermilion/gold ornament, lifestyle hero, and substituted Paris image. This risks decorative pastiche rather than the requested editorial confidence → Restore the specified paper/ink/ochre/indigo palette, remove fibres, binding-hole ornaments and inset shading; use `hero@800/1400/2000/2800` in the cover and `paris@800/1200` with “Champ-de-Mars, Paris.” Restore matching bilingual alts and hero-based OG artwork. Do not use AI-upscaled lifestyle assets as substitutes.

4. **[P1] [site/index.html:.twelve; site/css/styles.css:.portrait-art, .twelve--cover, .arc]** Straight sun rays and a filled disc replace twelve unequal arcs; stronger ornament overwhelms the quiet breath concept → Restore twelve curved arcs and three unfilled concentric circles, inactive ink `.14`, active ochre `.5`. Position the 90vmin ring behind-right, 70vmin on phones, visibly beside—not as a pedestal underneath—the frame.

5. **[P1] [site/index.html:section order; site/css/styles.css:.about-image]** A long biography interrupts the practice-to-signature narrative immediately after the cover; its sticky photo also violates “no pinned sections” → Restore `top → practice → twelve → classes → about → contact`; move testimonials into About, remove photo stickiness, and restore nav order. Keep About’s full EN reading content within 180 words.

6. **[P1] [site/js/main.js:EVENT_NAMES]** Frontend aliases contradict the supplied event contract; the gate reports a different backend allowlist → Inspect the retained `event.ts`, reconcile this discrepancy explicitly, then send the agreed exact names. Do not silently rename analytics or modify the retained backend merely to satisfy a stale document. Test all four events, not only registration.

7. **[P2] [site/css/styles.css:.card, .step-frame, .strip-wrap]** Neighbours remain full-size and are faded; edge gradients wash over photographs. Height caps can break the intended frame ratio → Use active scale `1`, neighbours `.96`, equal photo opacity, no gradient overlays. Couple frame width and height through 3:4 sizing; preserve full figures and caption space. This—not extra ornament—is the signature’s missing polish.

8. **[P2] [site/css/styles.css:responsive overrides]** The final ≥3200 rule regresses five cards to four and expands the container to 2600px. At 1024px, later overrides erase the editorial stagger → Restore five cards, 2200px maximum container, specified gutters, and deliberate tablet stagger. Consolidate conflicting media rules; review 390/1024/1440 plus every required orientation, cards 1/6/12, and unclipped Sanskrit captions.

9. **[P2] [site/css/styles.css:@media(max-width:400px); .glass-chip]** Language controls shrink to 40px; caption contrast depends on photography → Restore ≥44×44px touch targets. Measure actual composited text colours, including muted credits and chips, to ≥4.5:1. Keep chips in clear corners, never across a figure. Existing alt/focus hooks are good; verify visible focus in both languages.

10. **[P2] [site/js/main.js:initStrip; site/css/styles.css:.eyebrow]** Play advances immediately before the first four-second interval; pause logic excludes focused Play; breathing-dot CSS has no matching markup → Start advancement after 4000ms, define consistent hover/focus pause behaviour across controls, and add the eyebrow dots. Remove extra ray breathing. Preserve static reduced-motion rings and disabled autoplay.

11. **[P2] [site/js/i18n.js:lineageBody, now; site/index.html:.logo]** “I bring…into every class” invents a personal teaching commitment; “Open now” implies unverified immediate availability; “G1A” is unexplained → Use neutral training-to-teaching language, “Individual classes by request,” and “Jeevana” branding. Preserve verified certification, history and the two authorised testimonials.

12. **[P2] [site/js/main.js:trailing IIFE; site/css/styles.css; gate evidence]** Cascade patches obscure intent; main.js has two IIFEs; “144K total” does not establish transferred fold weight → Consolidate to one IIFE ≤12KB and one authoritative rule set. Preserve lazy loading/srcsets, correct image intrinsic ratios/sizes, and measure cold-load fold transfer ≤600KB. Keep `_headers` unchanged; rerun CSP and exact-contract tests. Restore the hidden designer mail link.

**Already excellent—must not be lost**

13. **[P3] [site/index.html:forms; main.js:submission]** In-place success/error handling, preserved inputs, honeypots and client validation → Retain.

14. **[P3] [site/js/main.js:initStrip]** Native snapping, keyboard/touch/drag support and synchronised arcs/progress → Retain.

15. **[P3] [site/index.html:.frame, .practice-gallery]** Photographs retain their environments, restrained shadows and separated typography—no dark plates or cut-outs → Preserve this foundation.
