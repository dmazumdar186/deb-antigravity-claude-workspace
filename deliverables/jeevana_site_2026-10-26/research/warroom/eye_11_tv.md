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
