# v2 review round 1 (2026-10-26) — jury REVISE + eye reviewers. ► = decided by the brain. Every item gets a DOM/asset assertion.

## A. The drawing (jury #1, phone #2/#3) — "a thick black outline around a grey photo" is not a drawing
1. Drop the grey wash entirely. Contour = one warm-ink line `#2A2420`, 0.75–1 px at 1440 (`vector-effect:non-scaling-stroke`,
   width from a `--ink-w` clamp .75–1.1 px), with slight weight variation (two overlapping strokes: 1 px at .9 opacity + 1.6 px
   at .18). Add 2–3 interior lines per figure, derived in ingest as the longest 2–3 interior Canny edge paths inside the
   alpha (min length 12 % of figure height; potrace them; if none qualify, ship none). No face detail before the colour phase.
2. Wash = pale ochre `#C4731A` at 10–14 % opacity, filled from the alpha mask **offset 6–10 px down-right** and blurred 3 px
   (a brush wash that does not register with the line), not the photo.
3. Clean masks before tracing: threshold → morphological open/close 3 px → erode 3 px at the base rows (mat strip) → drop
   components < 0.2 % → feather 1.5 px → potrace `turdsize 40, alphamax 1.2, opttolerance .5` (kills the stair-stepped hair
   on s5, the lumpy hood on s0, the stray tick on the shoulder). Assert: contour path point count per figure ≤ 1,200 and no
   sub-path shorter than 2 % of the figure height.

## B. The closing frame (jury #2, Tom Ford)
4. s11/hold photograph = **sn-01, frontal Praṇāmāsana** (meets the viewer; the circle closes on the opening pose). s0 drawing
   = sn-01 too. Position 12's rail text unchanged. The profile sn-12 moves to position 01's photo? No: 01–11 are drawings; only
   S9–S11 show photographs (positions 10, 11, 12 = sn-03, sn-02, sn-01 photos revealed under their drawings).
5. Warm grade in ingest (Pillow, deterministic, photos only): white balance +6 % red/−4 % blue, saturation .94, lift blacks
   2 %; no CSS filter. Assert the ingested photo's mean colour temperature is warmer than the source (R/B ratio up).
6. Ground: one hairline (`1px`, ink at .35) edge to edge at the ground line, and a real contact shadow = an ellipse under
   the feet only (width 60 % of the foot span, height 2 % of the figure, ink .22, blur 6 px), not a blob under the body.

## C. Page faults (jury #3, Anna Wintour) — "two missing photographs"
7. `page-full-static` (`?static=1` and reduced-motion): About portrait and the "Breath & stillness" figure missing (only
   their shadows). Root-cause the lazy-load / reveal gating; assert every `img` in the static page has `naturalWidth > 0` and
   opacity 1.
8. Section air: 160–200 px top padding at 1440 on drum, deck and About; the drum must not run into the sticky tab row.

## D. About and drum (jury #4, #5)
9. About: ► **colour photograph**, not the pencil render (`portrait`, cropped at the sternum, hands fully inside the frame or
   deliberately bled; no hard cut at a wrist). Remove the pencil pipeline from the site; keep the script in research.
10. Drum: three **full figures** (photo-03 seated, photo-05 cobra, sn-06) on one ground line, one scale (figure heights equalised
    to the tallest at 60 % of the card height), identical card rectangles; assert equal baselines (±2 px) and equal scale.

## E. Phones and tablets (phone reviewer #1, #4; jury #6)
11. Portrait viewports at s5 (and any low pose: s4, s5, s6, s7): the empty cream band between the sūtra and the short figure
    (45–55 % of the height). ► Fix with text, not scale: on `(orientation:portrait)` the cover grid is `auto 1fr auto`; the
    pose block (counter, Devanagari name, breath, mantra) sits centred in the 1fr row above the figure, and the sūtra stays at
    the top. Assert: at every state on every portrait viewport, no empty band > 25 % of the height.
12. phone-landscape s5: figure runs into the "retain the breath" pill → `.cover-figure{max-width:calc(100% - 2*var(--rail-w) - 32px)}`
    in `(orientation:landscape) and (max-height:500px)`; assert no intersection figure/rail.
13. mobile s5: ~300 px dead space between sūtra and figure → covered by 11.
14. ► Remove the "Scroll" label (jury): the autoplay motion is the cue. (Build-rule "scroll hint always present" is overridden
    for this concept; note it in HANDOFF.)

## F. Chrome and accents (jury #6)
15. Classes: "Price on request" in ink, not the accent. Progress ticks: hairlines in ink, not orange. The accent stays for the
    wash and one CTA only.
16. Capture `cover-s0.png` (missing; only -0s/-3s exist) and the real `newsletter-dialog.png` (currently a copy of deck-about).

## Re-verify
All functional assertions + the new ones above; fresh screens (named + 19 viewports × s0/s5/s11/hold). Report ≤ 250 words.

## G. Desktop / pages reviewer (added)
17. Register success: 70 px gap appears between header and tab row after the swap → keep the tab row at `top: var(--header-h)`,
    scroll to the panel top after swapping; assert gap ≤ 8 px in both states.
18. About portrait clipped (hard edges at the right hand and bottom) → column `overflow: visible` or scale-to-fit with margin;
    assert the image box is fully inside the panel (covered by D9: colour photo, hands inside the frame).
19. Rail at 1440p/4K stretches apart (`space-between`) → `justify-content:flex-start` + `gap: clamp(.6rem, 1vh, 1.6rem)`;
    assert the rail block height ≤ 70 % of its column and gaps ≤ 2.5 rem.
20. 4K chrome: logo, wordmark, toggle, eyebrow keep 1080p sizes (eyebrow ≈ 6 px on a TV) → clamp()/root step at ≥ 2560; assert
    eyebrow ≥ 18 px and nav ≥ 22 px at 3840.
21. s5 (and other wide poses) nearly touches the rail on laptops/desktops → figure `max-width: calc(railLeft − 64px)`; assert
    figure right edge ≤ rail left − 48 px at every state and viewport.
22. Portrait tablets/TV at s5: figure edge to edge + 40–50 % empty band → cap width at 85 vw and the E11 text layout; TV
    empty band at y 1570–1840 → compose the caption/CTAs with `auto 1fr auto` rows.
23. Classes: one hairline-list row per class (name · description · price), not a card grid; Contact: content vertically
    centred in the panel (or newsletter row follows); assert no panel has an empty area > 35 % of the viewport.
24. s0 toes: doubled/squiggly contour → mask smoothing per A3; assert no sub-path < 2 % height.
