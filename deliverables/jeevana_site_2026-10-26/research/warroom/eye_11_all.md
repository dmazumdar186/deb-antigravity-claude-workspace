# Eye review round 11 — third pass. Fix every item marked STILL OPEN or new at P1/P2; P3 where one line.

## phones
NOT YET (portrait 320/390 ship-quality; landscape strip photographs are crushed to ~20px chips, a P1)

Previous items (from eye_07)
1. 844-strip-12 end void: FIXED (last card right-aligned, 12/12 fills to margin)
2. Landscape header/photo/caption: PARTLY FIXED (header ~52px, chips no longer clipped, controls visible) but photo now a ~20px chip: STILL OPEN (escalated to P1)
3. Ghost text through header: FIXED
4. 320 email wrap: FIXED
5. Ring under CTA: FIXED
6. 320 header two rows (~113px): STILL OPEN (P3)
7. Register-your-interest hit area: FIXED
8. Newsletter: fields/Subscribe FIXED; checkbox ~24px: STILL OPEN (P3)
9. Bana caption: FIXED (Bhujangasana)
10. "Price on request" x3: STILL OPEN (P3)
11. About heading 3 ragged lines (320/390): STILL OPEN (P3)
12. Footer credit clipped: only (c) line visible, unconfirmed: STILL OPEN (P3)
13. Dark grass photos mood: STILL OPEN (P3)
Also fixed vs eye_07: 844 strip start void (strip now starts at left margin); controls (progress, Play, arrows) visible in all 844 strip frames; caption block heights aligned.

New defects
[P1] 844-strip-01/06/12.png, 844-03-twelve-b.png — strip photographs — images are ~20px thumbnails, the figure is unreadable; the strip is now type-only with specks — in landscape give each card a real photo frame (min ~45vh tall, 3:4) and let the strip scroll vertically-contained, or drop to a one-card-at-a-time layout like portrait.
[P2] 320-strip-01/06/12.png, 320-03-twelve-b.png — caption title — "Praṇāmāsana"/"Aṣṭāṅga Namaskāra" is cut in half by the sticky controls bar; Sanskrit name and mantra never visible — reduce photo height at <=340px or raise card bottom padding so title clears the controls.
[P2] 844-strip-01/06/12.png — caption text — "activity" and "through the sky" touch/cross the rule above controls; "Khagāya Namaḥ" runs off the right edge — clamp caption to 2 lines and set card min-width so text wraps inside the card.
[P3] 320-strip-01/12.png — photo crop — head cropped at top of frame, feet only in 320-03-twelve-b — object-position top for portrait cards.
[P3] 390-03-twelve.png — controls bar overlaps bottom of first photo on entry (covers the mat/feet) — start the sticky bar below the card or add scroll-margin.
[P3] 844-01-top.png — hero CTAs still clipped at viewport bottom — tighten landscape hero rhythm.

Excellent, keep:
- Framed photographs with white border and soft shadow, never on dark plates (390-02-practice-b, 390-05-about-b).
- 390 twelve-breaths card: dominant frame, peeking neighbour, clean caption stack, readable controls with disabled states (390-strip-*).
- Cormorant plus saffron italic plus navy Devanagari; ring beside headings, never under type (390-02-practice, 844-06-contact).

## tablets
VERDICT: NOT YET (1 P1, 1 P2, 4 P3 open). Strip geometry is now right at all three widths; the 1024x768 pinned strip clips its captions.

Previous items (eye_07)
4. Portrait strip ~1.5 cards, first card at x=215: FIXED (2 cards from gutter, peek of third).
5. Landscape strip 2.3 cards, offset first card: FIXED (3 cards from gutter at 1024/1366, peek of 4th).
6. Final 12/12 slide void: FIXED (10-11-12 / 11-12 fill the row, next arrow dashed).
7. Active caption baseline: FIXED (shared row, all aligned).
9. Three-photo stagger holes: STILL OPEN, reduced (~95px 768, ~130px 1024, ~190px 1366) now P3.
13/hero caption band: FIXED (plain caption, no plate).
14. Footer credit: FIXED ("Site by ProdCraft", no arrow).
Class CTA wrap at 768 (P3): STILL OPEN.
768 Eiffel photo width (P3): STILL OPEN (600 of 706px, 100px void right).
Earlier FIXED items (Sanskrit typos, select clipping, newsletter, orphan, hero ring) remain fixed.

New defects
[P1] 1024-strip-01.png, 1024-strip-06.png, 1024-strip-12.png — caption row — the pinned bottom controls bar covers the translation line ("to the friend of all" is sliced in half) so captions are not legible at iPad landscape — pin height at 100vh minus header, shrink card media to ~60vh (aspect-ratio) so card + full caption + controls fit in 768.
[P2] 1024-02-practice-b.png, 768-03-twelve.png, 1024-03-twelve.png, 1366-03-twelve.png — controls bar — it appears at viewport bottom as the section enters, cutting through "One breath." and the card photos with a hairline — only unstick/show the bar once the strip is pinned, or keep it in flow.
[P3] 768-01-top.png — hero — ~450px empty void left/below the sutra beside the offset photo — pull the photo up/left or centre it below the CTAs.
[P3] 768-04-classes.png — buttons — "Register your interest" wraps to two lines — shorten to "Register interest" under 800px.
[P3] 768-05-about.png — Eiffel frame — stops at ~630px, 100px void right — width:100% of the gutter.
[P3] 768/1024/1366-02-practice-b.png — stagger — 95-190px dead zones under photos 1-2 — reduce translateY or align-items:start.

Excellent, keep:
- Strip: 2 up portrait / 3 up landscape, aligned captions, clear controls, dashed disabled arrows, correct Sanskrit.
- Framed white-border prints with soft shadows; rings stay beside photos and headings, never under type.
- Cormorant plus Inter with the saffron italic accent; 1366 hero and the 04 about spread feel editorial and confident; forms and buttons are 48px.

## desktops
VERDICT: NOT YET (no P1; 5 P2 and 5 P3 open)

Previous items (eye_07)
1. Ghost text through header: FIXED (header opaque in every shot).
2. Strip photo tops / 01-12 badges cut under header at 1440: STILL OPEN. Badges at y~95 are sliced by the header; the 1440 strip is taller than the 900px viewport.
3. Strip-12 end void: FIXED (1920: card 12 sits on the right margin, 4 full cards; 1440: 3 cards plus a modest end margin).
4. Mid-word chopped captions 1920-strip-06 ("nave Namah", "Sancalanasana"): STILL OPEN, but only at the faded edge cards (P3).
5. Controls: PARTLY. Visible in every strip shot. The progress ring is still an empty circle with a tiny arc and the disabled arrow is dashed and faint (P3).
6. 1920 cover dead column (~410px between H1 and photo): STILL OPEN.
7. Practice intro void, lone ring, stagger collage: STILL OPEN.
8. Practice line length: PARTLY. 1440 is ~72 ch, 1920 ~75 ch. Close, not under 70.
9. About photo flush under header: STILL OPEN (photo top y=105, header ends 92, at 1440 and 1920).
10. Request form: STILL OPEN (labels small, select text larger than inputs, left column empty below the link at both widths).
11. Newsletter alignment: STILL UNVERIFIED. Both contact shots cut off before the submit row. Fields shown are aligned.
12. Repeated ring icon: STILL OPEN (a ring in every section header).
13. 1920-03 left void: FIXED (strip starts at the content margin).
14. Classes/form seam gap: PARTLY (~140px at 1920 now, acceptable).
15. Cover caption band: FIXED (hairline plus text only).
16. Name chip, classes cards, about chip/orphan, header ghosting: remain FIXED.

New defects
[P2] 1440-03-twelve / 1440-strip-01/06/12 — strip — the controls bar overlays the card bottoms: the photo is cut at y=819 and the translation lines ("to the friend of all") are hidden, with "Om ... Namah" touching the rule — cap card height to ~62vh so photo, captions and controls all fit in 900px.
[P2] 1440-strip-01/06/12 — card tops — badges sliced by the header after scroll-snap — add scroll-margin-top >= 110px so the whole card clears the header.
[P3] 1920-strip-06 — edge cards — the fade mask cuts translations and names mid-word at both ends — fade only the image, keep captions at full opacity or hide partial captions.
[P3] 1920-04-classes-b — form heading sits under the header at capture — scroll-margin on section anchors.
[P3] 1920-02-practice — right paragraph — starts ~60px lower than the Sanskrit column and ends 120px short of the right margin — align its top with the Sanskrit line and widen to the grid.

Open list
P2: strip fit at 1440 (photo/caption/controls); strip tops under header; 1920 cover dead column; practice intro void/lone ring/collage; about photo flush under header; form left void (1440 and 1920).
P3: edge-card chopped captions; empty progress ring and dashed arrows; form label/select sizing; repeated rings; practice line length ~75.

Excellent, keep:
- The cover portrait in its cream frame with the ochre italic "at a time." and the clean hairline caption: editorial and calm.
- 1920 strip: four full cards, centred hierarchy, Devanagari / IAST / mantra / translation stack reads rhythmic and scholarly.
- Contact hairline list with large serif details, and the Paris/Eiffel framed photo with its chip.

## tv
# eye_11_tv: 2560 and 3840 screens, round 3

Verdict: NOT YET (P1 open: 3, P2 open: 4, P3 open: 4)

2560 is near-ship. 3840 still renders a 1146px-equivalent column (57% of canvas, ~21% dead margin each side) and the strip has regressed into word-breaking.

## Previous items (eye_07)
1. [P1] 3840 type scale / container 57% — STILL OPEN (nav, labels, body unchanged from sofa distance)
2. [P1] strip-01 only 3 cards / void — FIXED (2560 strip-01 shows 4 + peek, left aligned; 3840 shows 7)
3. [P1] rings through captions — FIXED
4. [P1] inactive caption contrast — FIXED
5. [P2] last slide void — FIXED at 2560 (4 cards, no right void); 3840-strip-12 ends at container edge, ~21% empty right (container issue, see 1)
6. [P2] 3840 hero — STILL OPEN (now 5-line wrapped headline, small photo, bottom rule cut off)
7. [P2] translucent header ghosts — STILL OPEN (2560-04-classes-b, all strips)
8. [P3] class cards/form faint — STILL OPEN (3840 form/links tiny)
9. [P2] staggered gallery / orphan ring — STILL OPEN (3840-02 uneven tops, cropped)
10. [P2] Eiffel grading — STILL OPEN
11. [P2] swipe hint — FIXED
12. [P3] newsletter Phone field — STILL OPEN
13. [P3] "Designed by" footer — not visible in shots, treat as STILL OPEN
14. [P3] contact arrows far right at 2560 — STILL OPEN (minor)
New from eye_07: contact label gutter — FIXED (3840-06 clear gutter). 3840 header vs headline collision — STILL OPEN.

## New defects
[P1] 3840-strip-01/06/12 — card titles — Sanskrit names break mid-word ("Praṇāmāsan/a", "Pādahastāsa/na", "Sañcālanāsa/na") because 215px cards carry 2560-scale type — fix: 4.5 cards, title clamp so longest word fits, hyphens:none, overflow-wrap:normal.
[P1] 3840-strip-01 — captions — mantra/translation runs into the divider and controls ("Om Bhānave" over rule), cards unequal height — fix: reserve caption min-height for 3 lines, controls below.
[P1] 3840-strip-06/12 — header — "Twelve moments." sits under/over the "Jeevana" wordmark — fix: opaque header, scroll-margin-top on section.
[P2] 3840-01-top — hero — headline wraps "Steady. At / ease. / Twelve / breaths", photo ~460px wide on a 4K canvas, footer rule cut — fix: widen headline column, scale photo to 40%, fit to 100svh.
[P2] 2560-04-classes-b, 2560-strips — header — body text visible through bar — fix: rgba .96 + backdrop blur.
[P3] 3840-strip — disclaimer — indented at 679px aligned to nothing — fix: align to container left.
[P3] 3840-04-classes — checkbox/inputs ~14px — fix: 24px control, 48px hit area.

## Excellent, keep:
- Sun-salutation photo frames at 2560: sharp, consistent, readable Sanskrit/IAST/translation hierarchy.
- Cormorant headlines, amber italic accent, warm paper palette; 2560 hero is premium.
- Contact rows in large serif with proper label gutter and clear arrows.
