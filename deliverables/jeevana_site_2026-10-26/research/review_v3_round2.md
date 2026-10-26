# v3 jury round 2 (2026-10-26) — REVISE; cover approved in substance ("a cover I'd run"). ► = decided. Assertion per item.
1. Chapter images (01–03, dialog, register-success): the same feathered portrait at the same size in the same left slot =
   stock layout; hard bottom edge at ~y 835. ► Per chapter a different still from the film with a different crop and scale:
   01 a full-bleed lunge (Aśva Sañcālanāsana) bleeding off the left edge; 02 a tight crop on the hands in Praṇāmāsana
   (≤ 40 % width); 03 the standing Praṇāmāsana small in a lot of sky (figure ≤ 35 % height). All four edges feathered to the
   paper (no rectangle: assert edge alpha ≤ .05 on all four sides, 16 points per chapter).
2. page-full-static: ~1,000 px of empty gradient after the cover; chapters far apart. ► Dawn resolves to cream within 30 svh;
   chapters ≈ 1 viewport each; no band between sections taller than 20 svh (assert on the static page and on
   mobile-chapters).
3. Dialog + Contact subscribe: bordered box, black pill = the last template elements. ► Newsletter opens as a bottom sheet
   (phones) / inline sheet (desktop) with no border and no box shadow on a cream scrim; submit is the underlined serif link
   "Keep me posted →"; Contact's SUBSCRIBE pill becomes the same link style. Assert: no `button` with a filled dark background
   anywhere; no element with a 1 px dark border around the newsletter form.
4. Chapter ring: floats empty near the nav. ► Tie it to scroll: it fills (stroke-dasharray) as the chapter is read and sits
   beside the chapter number "01 —" at the chapter's top-left; assert its dash offset changes with scroll inside each
   chapter and that it sits within 24 px of the chapter number.
5. Register-success: remove the stray rule above the confirmation; no faded header text may overlap "Group class" (assert
   no text-box intersections in the chapter after success).
6. Mobile cover: headline + sūtra sit in a flat navy band. ► No band: type sits on the sky with a soft top gradient scrim only
   (max 45 % alpha, 0 by 35 % height); assert no element with a solid background behind the copy on phones.
Re-verify all; fresh screens; report ≤ 200 words.

## Phone/tablet eye review (added)
7. Brand twice at s0/hold on every viewport: eyebrow "JEEVANA — YOGA IN PARIS" under the header wordmark → eyebrow becomes
   "YOGA IN PARIS" / "YOGA À PARIS" (assert exactly one "Jeevana" wordmark visible on the cover).
8. Portrait phones/tablets at s7 (down-dog): her hair and far hand run into the left edge and are cut by the feather →
   on portrait viewports scale the film so the widest pose keeps ≥ 6 % side gutters (assert figure box inside the window
   by ≥ 6 % at s7 on all portrait viewports); short viewports (< 700 px) get 16 px more top margin.
9. ipad-landscape rail caption (italic mantra line ~13 px, reduced opacity on mauve): ≥ 15 px, full cream, local scrim;
   assert contrast ≥ 4.5 on the rail at all tablet viewports.
10. vp-mobile-pixel7-device-s7: a 1 px strip at the far right where the sky does not reach → sky layer `inset:0`, stage
    `overflow-x: clip`; assert the stage's rightmost column matches the sky colour.

## Desktop/pages eye review (added)
11. page-full-static: chapter images not loaded, rings missing, ~900 px empty gradient after the cover, blank cream between
    chapters → eager-load chapter media in static mode, render the rings, collapse scrub space (covered with item 2);
    assert every chapter `img`/`video` has naturalWidth > 0 and opacity 1 in `?static=1`.
12. Chapter film panels: hard bottom edge at y≈835 + cream strip, blurred side columns with a boundary → four-edge feather
    (item 1 covers); assert no luminance step > 6 % along any panel edge.
13. Chapter top air: the panel starts at 0 px under the header → panel top aligns with the text top line (or deliberate
    full-bleed per item 1); assert panel top ≥ text top − 8 px.
14. register-success: page scrolled mid-chapter, heading clipped under the header, 450 px empty below the message →
    after submit scroll the chapter to its top and render the confirmation in the chapter's frame (item 5).
15. laptop-1280 and ipad-pro-landscape: the rail heading wraps to two lines and touches the numerals → shorten to
    "THE TWELVE BREATHS" ≤ 1366 px or add margin; assert no intersection heading/numerals.
16. 4K: nav, eyebrow, numerals, mantra line do not scale (numerals ≈ 9 px display) → clamp on vw ≥ 2560; assert numerals
    ≥ 18 px and nav ≥ 22 px at 3840.
17. 1440p/4K: faint vertical edges of the film's glow column (x≈600 and x≈1400 of 2000) read as the rectangle → widen the
    horizontal feather to ≥ 160 px at ≥ 1920 and blend the film's own background gradient into the stage (the seam
    assertion must sample at 25 %, 50 %, 75 % height on both sides, not only the midline).
18. s7 clipped at tv-portrait, ipad-pro-portrait, slightly laptop-1280 → item 8 extended to all portrait + ≤ 1366 landscape.
19. tv-portrait: phone layout on a TV, empty bands, ring runs off both edges → type scales with the viewport, film pulled up
    under the copy, ring ≤ 85 % width; assert empty area ≤ 25 % and ring inside the viewport.
20. ipad-pro-portrait s7: ring smaller than at s0/hold, quote oversized → ring size constant across states (assert ±2 %),
    quote capped on portrait.
