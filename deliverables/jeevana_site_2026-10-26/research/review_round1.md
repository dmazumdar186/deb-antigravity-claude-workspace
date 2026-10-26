# Review round 1 (2026-10-26) — 4 reviewers (main screens, phone/tablet matrix, desktop/TV matrix, design jury). Verdict: REVISE.
Decisions by the brain are marked ►. Fix every item; items are grouped so one CSS/JS change closes several.

## A. Cover photo = the brand (jury KEEP + reviewer defects)
1. Photo too small / slideshow feel: per-frame crop from `manifest.focus` so her body fills ≥ 60 % of the plate height, bottom-anchored to the mat (crop empty grass); Ken Burns 1.04 drift per frame; on standing poses let the plate bleed wider (≥ 45 % of viewport on desktop). Reviewer: "every frame centred the same, identical scale, empty floor".
2. Plate blank at scroll 0 on desktop-4k and ipad-pro-landscape: first frame `loading=eager fetchpriority=high`, `<link rel=preload>`, opacity 1 at p=0, low-res background placeholder on the plate; check srcset resolves at 3840 and 1366.
3. Frame 03 (`_DAV5307`) shows a dark blob bottom-left: crop it out via `focus`/zoom for that frame (no retouching).
4. Stray orange disc + hairline streaks (backdrop sun) on the column boundary and through the rail label: blur the sun `filter:blur(clamp(40px,4vw,160px))`, opacity ≤ .35, keep it behind the plate; stop the streak lines at the plate edge; mask the backdrop under the rail.
5. ► Eiffel photos: jury calls them souvenirs; operator pasted one himself. Decision: stadium series is the house look everywhere (cover, drum, About). The Eiffel wheel appears ONCE, in the "In Paris" About card (small, captioned "Champ-de-Mars"), and stays the OG image. Tree-at-Eiffel goes to the gallery dialog only.

## B. Brand/header
6. Brand twice at scroll 0 (header "00 JEEVANA" + cover monogram): header shows only the chapter number over the cover; monogram + wordmark pinned top-left for the WHOLE cover scrub (they vanished at 50/100). One brand on screen at all times, never zero.
7. Header opaque over fold and deck (text bleeding through the translucent header); remove the grey noise gap between header and tab row (tab row sits directly under the header). Jury: "either it's a photograph or it's nothing".
8. Narrow phones (iphone-se 375, galaxy-s8 360): language toggle runs off the right edge → `inset-inline-end:max(12px,env(safe-area-inset-right))`, `html,body{overflow-x:clip}`.
9. ipad-portrait: "00 JEEVANA" floats mid-left → align to the content edge.

## C. Cover end / overlap (the biggest geometry defect)
10. All `-cover-100` frames: CTAs gone, the drum already fills the screen; on phones a 500–650 px empty cream band under the header; ipad-portrait/tv-portrait 300–620 px empty haze; `page-full` shows ~1,500 px empty dark + ~1,300 px empty cream. Fix the track math: last beat (sutra 2.46 + CTAs) held to p=1 with the plate still shown; the fold enters only in the last 20 % overlap; mobile pin ~200svh; no end-of-scrub fade to cream; first section `margin-top` negative per recipe; deck panels render statically in a full-page capture.
11. cover-100: "Vinyasa" caption ghosts over SCROLL; Eiffel card floats over the photo as a collage → hide SCROLL once p > .8; drum captions hidden until the fold's `--tenter` > 0; no card over the cover photo.
12. Fade rule: cover text at 0 before the drum headline passes .1 (horizontal ornament lines currently cross "SŪRYA NAMASKĀRA — THE TWELVE BREATHS").

## D. Phones (≤ 820)
13. cover-50 on iphone-13/se/s8: sutra eyebrow + Devanagari over her torso/face → `@media (max-height:760px)` photo `object-position:50% 30%` + scrim `linear-gradient(to top, rgba(15,12,10,.92) 55%, transparent)` up to the eyebrow.
14. SCROLL hint: centred (`left:50%;translateX(-50%)`), above the safe area, hidden once CTAs are on; never beside "Yoga in Paris"; CTA row `margin-bottom:calc(64px + env(safe-area-inset-bottom))`.
15. mobile-cover: gloss text on the sky without scrim → top gradient scrim (ink .6 → transparent) behind the counter + gloss.
16. Phone landscape (`orientation:landscape and max-height:500px`): header in its own row, columns `padding-top:56px`, scroll hint visible, first section `padding-top:72px`, cards `--card-h:60svh` so captions stay on screen.
17. Mobile bottom bar: ► keep Register (primary) + WhatsApp (icon); drop the Phone button (WhatsApp opens the same number). Bottom padding = bar height on every section so the drum's face is never hidden.
18. mobile-foldout: remove the empty cream band between header and section (y 145–285).
19. Missing captures: `mobile-cover-60.png` and the `mobile-*` viewport files were never written — fix `screens.mjs` and capture them.

## E. Wide screens (≥ 2200)
20. 4K looks like a 1080p site in a TV: `html{font-size:clamp(16px,.833vw,32px)}` at ≥ 2200 plus clamp() on wordmark (`clamp(5rem,9vw,16rem)`), copy width (`clamp(28rem,30vw,60rem)`), rail labels (`clamp(.75rem,.6vw,1.4rem)`), mantra (`clamp(1.25rem,1.3vw,2.6rem)`); rail fills its column (bottom half currently empty).
21. Portrait ≥ 768 (ipad-pro-portrait, tv-portrait): breath pill `width:max-content`; rail gets a top scrim or text-shadow (mantra over a cloud is unreadable); drum section `padding-top:clamp(4rem,8vh,8rem)`, `align-content:start`, cards sized in vh so no third-of-screen void.

## F. Signature object (drum)
22. foldout-mid: heading ghosted behind a skewed card, right card a thin sliver; foldout-open: blank grey viewport (cards not laid out) → heading full opacity throughout; cap rotateY ≈ 35°; staggered rise instead of a heavy 3D hinge; cards laid out at the capture scroll position (check the reveal trigger and `is-open` threshold).
23. laptop/ipad-landscape -100: card stack overlaps the lede ("movement and breath." cut) → stage `margin-top:clamp(3rem,6vh,6rem)`, intro z-index above the stage.
24. ► Drum plates: 01 `_DAV5352` seated meditation, 02 `_DAV5340` cobra front, 03 `_DAV5325` child's pose from above (stadium series only, per A5). Captions: Hatha · Vinyasa · Breath & stillness.

## G. Deck (jury: "below the fold it falls back to a template")
25. Remove the three white bordered drop-shadow cards in About/Classes/Register: open editorial columns on cream with a hairline rule and generous leading; panels lose their shadows too. Keep white only for form fields.
26. About: portrait (`_DAV5356`) runs full-height across ~half the panel; headline + 12/8/4 numerals breathe beside it; numeral captions larger and darker (contrast ≥ 4.5); `font-variant-numeric:lining-nums tabular-nums` (the "4" sat low); mobile: recrop so the eyes stay clear under the sticky bar, never cropped at the chest.
27. Classes: no empty 7-day grid. One confident line: "The timetable opens soon." + a single quiet "Register your interest" link; "Price on request" once, under the three offerings. Keep `schedule.json` rendering for when rows exist (grid appears only with ≥ 1 row).
28. "The studio address will be published here." → "Studio address shared on registration." (EN/FR).
29. Navigation layers: ► keep the top bar (Classes · Register · EN/FR) and the deck tab row (it IS the deck's navigation); remove the duplicate "02 — ABOUT" eyebrow inside each panel (the header chapter indicator already says it); mobile bar per D17. Add a chevron affordance on the mobile tab row.
30. Footer "Instagram" bare word → "@jeevana.gogula" with underline + arrow; Contact tiles get an arrow/hover affordance so they read as links.
31. Register success: replace the form with the confirmation panel (scrolled into view), submit disabled; success never below the fold.
32. Gloss strings: unify per position in EN and FR between desktop rail and mobile counter (e.g. 03 "to the one who induces activity" vs "to the stimulating power" are different positions' glosses — check the mapping 01–12 against the brief list).

## H. Newsletter dialog (jury)
33. Copy: "A few letters a year: workshops, new classes, a sūtra." (FR equivalent). Drop the phone field (email + consent only). "No thanks" = quiet text link (still ≥ 44 px tap target, still keyboard reachable, still an equally easy exit). ► Operator asked for phone in the pop-up: keep phone as an optional field on the Register form only; note this in HANDOFF for the operator to overrule.

## Re-verify
functional N/N (add: one brand element visible at p=0/.5/1; CTAs visible at p=1 on 1440 and 390; no element intersects the plate; no viewport has an empty band > 25 % at -100), site_check 0, 0 console errors (desktop, Pixel 7, iPhone 13), full 18-viewport matrix + the named screens + mobile-cover-60 + the `mobile` viewport. Then report ≤ 250 words.
