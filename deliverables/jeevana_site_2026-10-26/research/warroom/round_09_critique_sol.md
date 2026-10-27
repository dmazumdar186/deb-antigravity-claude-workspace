# Round 9 critique by openai/gpt-6.1-sol-pro

**Verdict: HOLD.** The supplied code has a strong foundation, but does not yet deliver the contracted design. Passing gates are useful evidence—not SHIP: several assertions now endorse deviations. I reviewed code and logs; the PNGs themselves were not supplied.

1. **[P1] [site/index.html:#classes; site/js/i18n.js:class copy; research/functional_v4.mjs]** Verified prices are completely missing; the gate explicitly rewards “no €,” contradicting the latest addendum → Show **€50/hour**, online €50/hour, **5 hours €250 / 10 hours €500**, and in-home **€25/hour after tax credit (crédit d’impôt)** in EN/FR. Distinguish individual sessions at hers/at yours/online; retain small groups and workshops by arrangement. Replace the no-price assertions with exact-content checks.

2. **[P1] [site/css/styles.css::root, “v5” decoration, final overrides]** Ochre parchment, inset shading, manuscript borders, seals and saturated rays compete with the photographs. This reads as ornamental theming rather than a singular senior-level idea → Restore paper `#F3EEE4`, ink `#2A2622`, ink-soft `#4A433C`, mist `#E7DFD0`, ochre `#C4731A`/text `#9A5A12`; remove fibre, holes and section vignettes. Let the twelve-photograph sequence provide the wow.

3. **[P1] [site/index.html:.hero-frame, .about-frame, .paris-frame; metadata]** The specified photographic story has been replaced with AI-upscaled lifestyle assets → Restore seated `hero` with 800/1400/2000/2800 candidates, the supplied Paris Chakrāsana secondary photograph, and hero-derived OG artwork with paper margin. Update EN/FR alts and OG descriptions; FR hero alt must begin “Jeevana assise.” Preserve environments, rounded frames and soft shadows—no cut-outs or dark plates.

4. **[P1] [site/css/styles.css:.card; site/js/main.js:initStrip; functional_v4 assertions]** Start alignment replaces the required centred-card mechanic; several end cards share one scroll position, so the counter changes without photographic movement. Neighbours never scale `.96` → Use centre snapping, sufficient leading/trailing space to centre cards 1 and 12, centre-distance active detection, and `1/.96` scaling. Remove caption-hiding `.is-out` and photo-edge gradient overlays. Rewrite tests around actual centring and distinct movement through all twelve.

5. **[P1] [site/index.html:.twelve; site/css/styles.css:.portrait-art, .twelve]** Straight rays, filled disc and extra breathing rays replace the twelve-arcs signature; accumulated positioning rules make placement fragile → Use twelve unequal-length arcs around three unfilled circles, ink `.14`, active ochre `.5`; retain 240-second rotation and 5.5-second centre breath only. Position behind-right at 90vmin desktop/70vmin phone; ensure visible geometry extends beside the frame, never across copy or figure.

6. **[P1] [site/js/main.js:EVENT_NAMES; functions/api/event.ts; HANDOFF]** Front-end aliases conflict with the supplied contractual event names, while logs claim the aliases match the backend → Inspect the retained allowlist and reconcile this discrepancy explicitly before shipping. Send the approved names unchanged; test all four events, not just registration. Do not silently modify the retained API to accommodate aliases.

7. **[P1] [site/css/styles.css:responsive overrides; research/screens_v4]** At 1024 portrait the hero is pulled upward and restricted to `34svh`; 4K overrides exceed the 2200px container and 96px gutter caps. At ≤360px navigation disappears after scrolling → Remove negative overlap, restore the specified container/gutter limits and keep navigation accessible. Review 390/1024/1440 plus every required orientation, especially 320px header fit and landscape captions; do not truncate mantra glosses.

8. **[P2] [site/index.html:section order, .cover-ctas; styles.css:.about-image]** A long About/training block interrupts the introduction before the signature experience; its sticky image contradicts motion restraint → Restore `top → practice → twelve → classes → about → contact`, consolidate Paris/testimonials with About, and remove stickiness. Restore “Register for a class” and “See the classes”; maintain distinct editorial offsets at 1024.

9. **[P2] [site/css/styles.css:contrast, .contact-value, .design-credit]** Contact text can shrink through container arithmetic; credit opacity weakens contrast, and the designer email link is hidden → Set readable minimum sizes, allow deliberate address wrapping, remove credit opacity/hiding, and measure every text/background pairing at ≥4.5:1. Retain visible focus rings and ≥44px touch targets; test keyboard focus throughout.

10. **[P2] [site/js/i18n.js; site/privacy/index.html]** Translation coverage is broad, but logo alternatives and no-JS messaging remain English; privacy source was not supplied → Localize meaningful logo alternatives and fallback messaging; verify both privacy blocks and every accessible label. Preserve all four consent strings **byte-for-byte**: current supplied strings match.

11. **[P2] [site/index.html:JSON-LD, .diwaliChip; i18n.js:lineageBody]** `G1A` organization/founder metadata and “lit at home” lack supplied factual verification; a personal attachment to the school maxim is invented → Remove unsupported claims. Use the specified Person schema with `jobTitle: "Yoga teacher"`; attribute the maxim to Sri Aurobindo without inventing Jeevana’s feelings.

12. **[P2] [research gates; assets/photos; styles.css]** “144K total” does not establish above-fold transfer weight; image dimensions also mismatch several manifest ratios → Measure cold-cache transfers at each DPR, enforce ≤600KB above fold, correct intrinsic dimensions and `sizes`, and verify no source upscaling. Consolidate the cascading overrides. Preserve CSP: logs report clean execution; do not loosen `_headers`.

**Already excellent—must not be lost**

13. **[P3] [main.js:forms]** Robust inline submission, retained inputs on failure, focus management, honeypots and verbatim consent.

14. **[P3] [index.html:.practice-gallery]** Wide/square/tall environmental photographs with restrained frames and editorial rhythm.

15. **[P3] [main.js; i18n.js]** Framework-free interaction, persistent bilingual content, reduced-motion handling and substantial functional coverage.
