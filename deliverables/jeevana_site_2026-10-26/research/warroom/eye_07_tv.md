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
