# Eye review round 7 — four reviewers (Claude Sonnet), second pass. Items marked STILL OPEN or new: fix every P1 and P2; P3 at your judgement.

## phones
NOT YET (portrait 320/390 are ship-quality; landscape strip still has an end void and tiny cards)

Previous items
1. 844-strip-12 end void: STILL OPEN (last card ends at x~490 of 844; right ~58% empty beige)
2. Landscape header/photo/caption fit: PARTLY FIXED (header now ~52px, caption visible with photo) but photo ~150px tall, number chips clipped under header in strip-01/06/12: STILL OPEN (P2)
3. Ghost text through sticky header: FIXED (320-04, 390-04-b, strip-01 clean)
4. 320 email wrap: FIXED (single line)
5. Ring under CTA: FIXED (no ring near buttons at 320/390 top)
6. 320 header two rows ~113px: STILL OPEN (P3, nav tidy but heavy)
7. Register-your-interest hit area: FIXED (full-width ~48px outlined button)
8. Newsletter: PARTLY FIXED (fields stacked equal width, Subscribe full-width); checkbox still ~20px: STILL OPEN (P3)
9. "Bana" caption: FIXED (Bhujangasana now correct)
10. "Price on request" x3: STILL OPEN (P3)
11. About heading 3 ragged lines: STILL OPEN (P3)
12. Footer credit clipped: not visible in captures (only (c) line); cannot confirm, treat STILL OPEN (P3)
13. Dark grass photos mood: STILL OPEN (P3)

New defects
[P1] 844-strip-12.png — twelve-breaths strip end — final card stops mid-screen, right half empty, looks broken — add end spacer / scroll-padding-inline-end so last card snaps right-aligned (or center).
[P2] 844-03-twelve-b.png — strip start — first card begins at x~355, ~40% void left under the intro line — start strip at left margin, or put intro text in a left column intentionally and align heading/strip.
[P2] 844-strip-01/06/12.png — cards ~130px wide, photo ~150px, caption ~11px — figures tiny, captions strain — in landscape make cards ~42vh tall with photo 60vh-equivalent, 12-13px caption.
[P2] 844-strip-06.png — caption block — card heights differ (Bhujangasana 4 lines, others 2-3), baselines ragged — set caption min-height and line-clamp, align tops.
[P2] 844-strip-01/06/12.png — controls — progress/arrows/Play not visible in landscape strip frames — keep controls sticky or visible below strip.
[P3] 844-01-top.png — hero — CTA buttons clipped at bottom of 390px viewport, portrait photo cut at chest — tighten hero vertical rhythm for landscape.
[P3] 320-03-twelve.png — second ring overlaps top-right of heading zone, double rings feel busy — drop the large faint ring at <=340px.

Excellent, keep:
- Framed photographs with white border and soft shadow, never on dark plates (390-03-twelve, 390-05-about).
- Twelve-breaths portrait card: one dominant card, peeking neighbor, clean caption stack, clear progress ring/01-12/Play/arrows with disabled states (390-strip-*).
- Typography and ring signature: Cormorant, saffron italic, navy Devanagari, ring beside headings never under type (390-02-practice, 844-06-contact).

## tablets
VERDICT: NOT YET (0 P1, 4 P2, 5 P3 open). Typos and clipping are gone; the strip still does not read as 2 cards portrait / 3 landscape.

Previous items
1. Card 07 "Bana": FIXED (now Bhujangasana).
2. Card 06 "Asskara": FIXED (Astanga Namaskara with Devanagari, 4-line caption).
3. 768 Format select clipped: FIXED (stacked, "Any format" legible).
4. Portrait strip ~1.5 cards, first card at x=215: STILL OPEN.
5. Landscape strip 2.3 cards, first card offset (x=365 at 1024, x=485 at 1366): STILL OPEN.
6. Final 12/12 slide leaves empty right side: STILL OPEN (all three widths).
7. Neighbour caption blur/baseline: blur gone; baselines still differ (active card caption sits ~18px lower): STILL OPEN (now P3).
8. 768 hero photo below fold: FIXED (face visible at ~y 650, ring clipped right of photo).
9. Three-photo stagger holes: STILL OPEN (768 and 1024 ~230px void under photo 1; 1366 ~150px).
10. 768 Eiffel photo inset/chip: FIXED (left edge on gutter, chip inside photo).
11. Newsletter tops misaligned: FIXED.
12. "care." orphan: FIXED.
13. Hero ring crossing caption: FIXED.
14. Footer "Designed by ... ProdCraft": STILL OPEN.
15. 1366 class CTA small link: FIXED (bordered 48px button).

New defects
[P2] 768-strip-01.png (and 06, 12) — strip — first card still starts at x=215 with a 215px empty left third, only 1 full card + a sliver of the next — start the track at the gutter, card width calc((100% - gap)/2 - peek) so 2 cards show.
[P2] 1024-strip-01.png, 1366-strip-01.png — strip — first card begins at x=365/485, leaving a hole under the heading column and showing 2.3 cards — set card width calc((100% - 2*gap)/3) and padding-inline-start to the gutter.
[P2] 768/1024/1366-strip-12.png — end slide — the 12/12 card ends mid-screen with ~40% void to the right and the next arrow dims — add scroll-padding-end equal to the leading offset, or snap last card right-aligned.
[P2] 768-02-practice-b.png, 1024-02-practice-b.png — three-photo stagger — large dead zones under photo 1 and 2 (about 230px) — cut the translateY offsets below 1100px or use align-items:start.
[P3] 768-04-classes.png — class buttons — "Register your interest" wraps to two lines inside the pill, cramped — shorten label to "Register interest" or drop the arrow below 800px.
[P3] 768-05-about.png, 768-05-about-b.png — Eiffel photo — stops at ~630px, leaving a 140px void to its right, not full-width and not centred — width:100% on the 31px gutter.
[P3] 768-01-top.png, 1024-01-top.png, 1366-01-top.png — hero caption — "A little space to simply be." sits on a faint lighter band whose edge reads as a pasted plate — remove the background or extend it into a full frame caption.
[P3] 768-06-contact-b.png, 1024-06-contact-b.png, 1366-06-contact-b.png — footer credit — "Designed by Debanjan Mazumdar · ProdCraft" still developer voice with an arrow — reduce to muted "Site by ProdCraft" without arrow.
[P3] 768-strip-06.png, 1024-strip-06.png, 1366-strip-06.png — captions — active card caption baseline sits lower than its neighbours because the active frame is taller — align caption tops via a shared grid row.

Excellent, keep:
- Framed, white-bordered prints with soft shadows; rings stay beside photos and never under type at all three widths.
- Cormorant + Inter with the saffron italic accent; hero at 1024/1366 is confident, the 01-05 rhythm and form fields are legible and 44px+.
- Strip controls (progress ring, play, arrows with a clear disabled state) and the corrected Sanskrit captions read cleanly.

## desktops
VERDICT: NOT YET (no P1 left; 8 P2 and 4 P3 open)

Previous items (eye_05)
1. Ghost text through header: FIXED (header opaque in all 1440/1920 strip shots).
2. Strip cards clipped / not 3-4 / not centred: PARTLY. Centre card is now centred (x 510-930 at 1440) with 3 full cards plus slivers, so FIXED for count and centring. STILL OPEN at 1440: photo tops and the 01/12 badges are cut under the header (strip taller than the 900px viewport).
3. Empty void at strip end: STILL OPEN (card 12 centred, but right half is bare beige at 1440 and 1920).
4. 03-twelve hint orphaned far right: FIXED (hint now sits under controls). Photos still run off the bottom at 1440 (natural scroll, accepted).
5. Inactive caption contrast: FIXED.
6. Mid-word chopped captions 1920-strip-06 ("icalanasana", "e Namah"): STILL OPEN.
7. Controls: PARTLY. Arrows are now 48px and the label is larger, but the progress ring is still an empty circle and the disabled arrow is dashed and faint. STILL OPEN (P3).
8. Cover ring/quote: FIXED for quote spacing; ring now sits beside the photo, not under type.
9. 1920 cover dead column (~400px between H1 and photo): STILL OPEN.
10. Name chip muddy: FIXED (light chip, readable).
11. Practice intro void, lone ring, stagger collage: STILL OPEN.
12. Practice body line length: STILL OPEN (~75 chars at 1440, ~80 at 1920).
13. About: chip and "care." orphan FIXED; photo still flush under the header with no top margin, STILL OPEN.
14. Classes cards/links: FIXED (full pill buttons, calm ochre line).
15. Request form labels/selects/left void: STILL OPEN (labels small, select text larger than input text, left column empty).
16. Newsletter alignment: could not verify, both contact shots cut the form off. Re-shoot.
17. Repeated ring icon: STILL OPEN.

New defects
[P2] 1920-03-twelve — intro/strip — a ~630x580px empty block under the intro copy to the left of the first card; strip starts at x=750 so the left reads unfinished — start the strip at the content margin, or put the controls and counter in that column.
[P2] 1920-04-classes-b / 1920-04-classes — section seam — ~170px dead gap between the form and the about photo, and the form heading rides under the header at the capture — halve section padding-block.
[P3] 1440-01-top / 1920-01-top — caption "A little space to simply be." — sits on a faint grey translucent band that reads as a stray rectangle — drop the band and keep the hairline plus text.
[P3] 1440-strip-01/06/12 — controls row — progress ring, Play and arrows fall below the fold at 900px, so the strip has no visible controls — pin the strip or shrink card height to ~60vh.

Open list
P2: strip photo tops under header (1440); strip-12 end void; 1920-strip-06 chopped captions; 1920-01 dead column; 02-practice intro void/collage; practice line length; about photo flush under header; 1920-03 left void.
P3: empty progress ring/faint arrows; form label/select sizing; repeated ring icons; cover caption band.

Excellent, keep:
- The cover portrait in its cream frame: reads as a real photograph, with the ochre italic "at a time." giving an editorial voice.
- The strip's centre-card emphasis (larger frame, bold caption) with the Sanskrit/English caption hierarchy: now legible and rhythmic.
- The contact hairline list with large serif details and the Paris/Eiffel frame in the about section: confident, calm, human.

## tv
# eye_07_tv: 2560 and 3840 screens, round 2

Verdict: NOT YET (P1 open: 4, P2 open: 4, P3 open: 5)

2560 is close to good; 3840 is still the 1440 layout in a 57% column, and new collisions appeared.

## Previous items
1. [P1] 3840 type scale / container 57% — STILL OPEN (nav, body, labels still tiny from the sofa; ~21% dead margin each side)
2. [P1] strip-01 only 3 cards, left 40% empty — STILL OPEN (2560 and 3840 strip-01 unchanged; strip-06 at 3840 does show 5 cards, so mid-strip is fixed)
3. [P1] rings through captions — FIXED (rings now only top right, clear of captions)
4. [P1] inactive caption contrast — FIXED (full-strength, legible)
5. [P2] last slide void / mid-word neighbours — STILL OPEN (right 40% empty at 2560 and 3840 strip-12; "āsana"/"Namaḥ" fragments cut)
6. [P2] 3840 hero — STILL OPEN (headline modest for canvas, bottom ~20% blank; ring now confined behind photo, that part fixed)
7. [P2] translucent header ghosts — STILL OPEN (body text clipped under bar at 2560 strips)
8. [P2] class cards/form tiny, faint borders — STILL OPEN, downgraded to P3 (2560 cards good; links and input borders still faint)
9. [P2] staggered gallery / orphan ring — STILL OPEN
10. [P2] Eiffel photo grading — STILL OPEN (still more saturated than set); caption pill now tucked in: FIXED
11. [P2] swipe hint — FIXED (sits under the controls, readable)
12. [P3] newsletter Phone field — STILL OPEN
13. [P3] "Designed by" footer — STILL OPEN
14. [P3] contact rows arrows far right at 2560 — STILL OPEN (3840 capped, fine)

## New defects
[P1] 3840-06-contact, 3840-05-about — contact rows — labels WHATSAPP and INSTAGRAM touch the value ("WHATSAPP+33", "INSTAGRAM@jeevana"), no gutter — fix: label column min-width 11rem with grid-template-columns: 11rem 1fr.
[P1] 3840-03-twelve, 3840-strip-01/06/12 — sticky header — "Twelve moments." headline slides under and collides with the "Jeevana" wordmark, unreadable overlap — fix: opaque header (rgba(243,238,227,.96)) and scroll-margin-top on the section so the heading never rests under the bar.
[P2] 3840-01-top — hero — 3840 hero leaves ~250px empty below the rule and 250px above the content, headline cramped in the middle — fix: min-height 100svh with centred grid, scale clamp up to 1.6x at >=3200px.
[P2] 3840-03-twelve — strip layout — headline, intro and cards left-offset so left 40% of the strip is blank beside "Twelve moments." — fix: start the track at the container left edge on wide screens, 4.5 cards.
[P3] 3840-strip-01/06/12 — disclaimer line — indented at 677px, aligned to nothing; left-aligned eyebrow above — fix: align to container left, max 70ch.
[P3] 3840-02-practice — gallery captions "01 · Open" tiny at 4K — fix: 1rem min, scaled with root.
[P3] 3840-04-classes — form checkbox — checkbox ~13px, impossible with a TV remote — fix: 24px control and 48px hit area.

## Excellent, keep:
- Sun salutation photo frames: sharp, consistent, soft shadow, active card lift and the readable Sanskrit/IAST/translation hierarchy.
- Cormorant headlines with amber italic "at a time." and calm warm paper palette; hero at 2560 is genuinely premium.
- Progress ring, arrows with disabled dashed state, "Play the sequence" and the contact rows in large serif.
