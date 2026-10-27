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
