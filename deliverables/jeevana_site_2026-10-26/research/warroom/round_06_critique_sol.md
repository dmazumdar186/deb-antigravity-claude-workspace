# Round 6 critique by openai/gpt-6.1-sol-pro

**Verdict: HOLD.** The design direction is credible, but two required interactions fail and the signature sequence contains corrupted markup/content. “Wow” is not yet demonstrated: screenshots were generated, but no eye-review verdict is supplied. Visual observations below are source-based.

1. **[P1] [site/index.html: cards 4, 6, 7, 9; site/js/i18n.js: positions[5]]** Broken attributes can swallow headings into malformed tags; Sanskrit and alternatives are corrupted → Restore complete `<p lang="sa">…</p>` elements using the fixture: **अश्व सञ्चलनासन** on 4/9, **अष्टाङ्ग नमस्कार** on 6. Restore headings **Aṣṭāṅga Namaskāra** and **Bhujaṅgāsana**, manifest alternatives for 6/7, and replace `Aṣaskāra` in the dictionary. Assert all twelve rendered titles, Devanagari strings and bilingual alternatives against the fixture—not merely “alt exists.”

2. **[P1] [site/js/main.js: initStrip(), pointer handlers, schedule()]** Functional gates explicitly fail **mouse drag** and **autoplay advancement** → Reproduce both with pointer/focus/visibility state logged. Make mouse dragging suppress native selection, release capture reliably and snap to the nearest card. Verify autoplay advances after four seconds **while visible, unhovered and unfocused**, pauses on hover/focus-within, then resumes. Include the play control in the pause-state design without making keyboard-started playback permanently paused. Require both gates green.

3. **[P1] [site/js/main.js: go(), locked, setActive()]** Programmatic navigation lights the destination arc before its photograph reaches centre; the 1.6-second lock suppresses intermediate centre updates → Drive active card, arc, counter and progress from the photograph nearest the viewport centre throughout scrolling. Keep navigation intent separate from displayed position. The signature must read as a breath moving through photographs, not a counter jumping ahead.

4. **[P1] [site/css/styles.css: .step-copy, .step-breath]** Neighbour captions use `opacity:.55`, compositing already-muted colours onto mist and undermining ≥4.5:1 text contrast → Keep caption text fully opaque; distinguish neighbours through the prescribed `.96` scale and framing instead. Measure every text/background pairing, including breath labels and glass chips. Touch-only full opacity does not fix desktop accessibility.

5. **[P1] [research/functional_v4.mjs; research/screens_v4/; HANDOFF.md]** Site-check passes do not override two functional failures. “124 PNGs” does not establish visual approval → Rerun corrected tests, inspect every required viewport/orientation in EN/FR, including strip cards 1/6/12, then obtain the specified reviewer’s first and second-round **SHIP** verdict. Record results and unresolved issues before preview deployment.

6. **[P2] [site/css/styles.css: .twelve--cover, portrait overrides]** Portrait ring placement uses `bottom:40%/42%` of the entire cover, not the photo’s position; translated copy changes that relationship → Anchor the decorative positioning layer to the portrait region while retaining the required SVG hook. Keep arcs visibly behind **and beside** the frame, clipped by the cover—not beneath it as a pedestal. Verify at 390 portrait, tablet portrait and phone landscape.

7. **[P2] [site/css/styles.css: #h1, .section-heading, .practice-gallery, .frame]** The editorial foundation is strong, but source alone cannot certify polish, crops or “wow” → At 390/1024/1440, tune headline wraps, heading-ring clearance and section spacing using actual screenshots. Preserve the 7/5 cover and 0/48/96 gallery rhythm; verify chips never cover the figure and shadows remain quiet. Do not introduce dark plates, gradients or cut-outs.

8. **[P2] [site/js/main.js: layout(); site/index.html: photograph sizes]** Card sizing is calculated in JS, while `sizes` describes different approximations—for example, portrait hero declares 92vw although tablet CSS limits it to 78% → Align `sizes` with actual breakpoint/orientation dimensions. Explicitly cap photograph height at 70svh and verify one-plus-peek/two/three/four/five-card behaviour, with captions accessible on 844×390.

9. **[P2] [site/index.html: og:image; research/photo pipeline]** OG points directly to a portrait rather than the required paper-margined 1200×630 composition; grading/crop compliance is unproven → Generate the dedicated OG asset and update metadata. Inspect exported photographs for warm-neutral balance, consistent strip horizons, figure margins, hero eye level and no Paris upscaling.

10. **[P2] [site/js/main.js: forms/eventCount(); site/js/i18n.js: consent strings]** Payloads, bilingual consent strings and mocked success/error handling match the supplied contract—preserve them. However, `subscribe` is counted only after success, whereas the brief requests CTA-click counts → Count the subscribe CTA activation once; avoid duplicate success counting. Add 429/503/network tests and verify exact consent strings in both languages.

11. **[P2] [site assets; _headers; /privacy/]** Reported CSP cleanliness and 116K weight are encouraging, not complete delivery evidence → Preserve CSP and the verbatim beacon; measure actual above-fold transferred bytes, verify ≤600KB and main.js ≤12KB, confirm legacy asset removal and inspect privacy toggle hooks. Retain lazy below-fold images, eager hero, reserved ratios and reduced-motion overrides.

**Already excellent—must not be lost**

12. **[P3] [styles.css: palette/fonts/frame]** Warm paper, indigo Sanskrit, restrained ochre and softly framed photographs establish the right identity → Preserve this system.

13. **[P3] [index.html: registration/contact/about]** Inline forms, clear interest-not-booking language and verified Tapovan lineage avoid inflated claims → Preserve; no invented credentials or testimonials are evident.

14. **[P3] [i18n.js; main.js; accessibility hooks]** Persisted bilingual UI, descriptive alternatives, visible focus, null-safe initialization and substantial reduced-motion support are excellent foundations → Preserve while repairing the sequence.
