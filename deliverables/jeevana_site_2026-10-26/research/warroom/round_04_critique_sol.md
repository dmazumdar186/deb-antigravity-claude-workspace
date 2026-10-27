# Round 4 critique by openai/gpt-6.1-sol-pro

**Verdict: HOLD—not SHIP.** The visual foundation is promising, but the signature interaction fails and the screenshot gate crashes. A senior-designer “wow” is not yet demonstrated. This review uses the supplied source and logs; no rendered photographs or screenshots were available to inspect.

1. **[P1] [styles.css:.breath-strip; main.js:initStrip/go/readCentre] Broken signature interaction → fix track geometry first.** Next, progress and keyboard navigation fail; Previous remains disabled. Percentage-based `--card-width`, flex-basis and centring padding create interdependent sizing. Measure `track.clientWidth`, calculate card width and end spacers in pixels, and use one track-relative coordinate system for scrolling and centre detection. Recalculate on resize; initially centre card 1. Verify cards 1/6/12, drag, snap, arrows, keys, both backdrops and progress—not merely `JV_strip.go()`.

2. **[P1] [research/functional_v4.mjs; research/screens_v4.mjs; HANDOFF.md] Release evidence is incomplete → repair and rerun every gate.** Screenshot capture dereferences a missing element; functional testing aborts before form outcomes. Use the contracted section selectors and fail with a descriptive missing-selector error. Capture every required viewport/orientation, sections and strip states; complete both eye-review rounds. Record results and unresolved issues honestly. Do not deploy a preview until the required pre-preview gates pass.

3. **[P1] [styles.css:.breath-strip,.card; phone-landscape media query] Landscape strip becomes miniature split cards → retain legible photographic cards.** At 844×390, card width is capped around 205px, then divided into image/copy columns, leaving an extremely narrow photograph and heavily wrapped Sanskrit. Remove that internal two-column layout. Keep captions below 3:4 images; derive image height from the available viewport **minus caption allowance**, capped at 70svh. Test 390, 1024 and 1440, plus the full orientation matrix.

4. **[P1] [styles.css:.consent,.honeypot; site_check tap-target logic] Touch gate fails → separate visible glyph size from hit area.** Preserve the contracted 20×20 checkbox, but give its associated label a reliable ≥44×44 activation region. Make the checker recognize that label-backed target. Identify the reported 28×50 inputs; if these are honeypots, exclude genuinely clipped, noninteractive honeypots from target checks—not real fields. Do not enlarge hidden traps to satisfy the gate.

5. **[P1] [main.js:reveal observer/paintPage; styles.css:[data-reveal]] Fast scrolling exposes invisible content → make fling arrivals immediate.** The iPhone gate confirms a reveal remains hidden after 150ms. The current shortcut handles elements above the viewport, not newly landed content within it. Detect large scroll deltas and immediately reveal intersecting arrivals without transition. Keep ordinary reveals ≤800ms/14px; rerun the fling test.

6. **[P2] [index.html:.frame,.glass-chip; styles.css:.twelve--cover,.twelve--strip] “Placed, not pasted” remains visually unverified → inspect actual compositions.** Paper, environmental photos and restrained shadows are structurally right; no dark plates or gradients appear. Confirm the ring visibly escapes beside the frame rather than disappearing beneath it, including portrait stacking. Move any chip that crosses hands, face or body into clear environmental space or outside the image. Never solve contrast by darkening the photograph.

7. **[P2] [main.js:initStrip/schedule] Autoplay does not pause across the whole control group → scope pause handling to strip plus controls.** Hover/focus listeners cover only the track; focused Play/arrows can leave advancement running. Track hover and focus-within across both areas, resume only after leaving, and preserve reduced-motion disabling and background-tab suspension.

8. **[P2] [styles.css:.section-heading,.mini,.step-copy] Repeated ornamental hierarchy risks template rhythm → strengthen the signature’s distinction.** Most headings repeat the same eyebrow/display/ring composition; fixed caption minimum heights can introduce dead space. Keep the editorial 0/48/96px photo stagger, but size caption rows from content and shared alignment requirements. Judge spacing in EN/FR at 390/1024/1440 before adding decoration.

9. **[P2] [index.html:forms; main.js:submit; i18n.js:consent strings] Contracts look correct, but submission is unproven → finish mocked tests.** Both consent texts match verbatim in EN/FR; fields, honeypots, JSON consent, language and source URL are present. Preserve them. Test empty submission/no request, mocked 200/400, 429, network failure, retained values, inline success and subscribe counting. Associate field errors through `aria-describedby`, not only `aria-invalid`.

10. **[P2] [index.html:img sizes,og:image; assets/photos; research/polish_photos.py] Delivery and grading evidence is missing → verify assets and network weight.** Lazy/eager settings, dimensions and srcsets are good. Match `sizes` to measured columns, especially landscape and capped containers. Generate the required 1200×630 paper-margin OG image instead of linking the portrait. Verify identical strip grading/horizon, crop margins and sharpening. “112K total” does not establish ≤600KB transferred above the fold.

11. **[P2] [i18n.js; privacy/index.html; _headers] Complete accessibility/localization verification → preserve the clean CSP.** Alt switching, persistence, privacy language, console and CSP already pass. Localize `aria-roledescription`; decide explicitly whether the English design-credit wording remains fixed. Verify focus and ≥4.5:1 text contrast over translucent chips and all section backgrounds. Keep scripts/fonts self-hosted and the beacon verbatim; do not weaken CSP.

**Already excellent—must not be lost**

12. **Paper/ink/ochre/indigo, serif–sans pairing and restrained framed-photo treatment.**
13. **Verified Tapovan lineage, correct contacts, Person-only schema and no apparent invented credentials.**
14. **Verbatim bilingual consent, descriptive bilingual alts and successful language persistence.**
