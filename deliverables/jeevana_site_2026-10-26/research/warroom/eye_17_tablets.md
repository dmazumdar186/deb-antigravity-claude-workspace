# Eye 17 - tablets (768 portrait; 1024, 1366 landscape), screens_v4

Verdict: NOT YET. All 48 PNGs read. P1 = 3, P2 = 6, P3 = 5.
Compliant: order, sun cover with "Reserve a session", diwali About, first person, no fees or euro signs, no Instagram arrows, dots or avatars.

## Defects
[P1] 1024-07-contact(-b).png, 1366-07-contact(-b).png - email row - address breaks mid-word ("gma/il.com", "gmail.co/m"), an orphaned letter on the main contact line - clamp() the font size so it fits on one line, or allow a break only after "@".
[P1] 768-04-twelve(-b).png, 768-strip-01/06/12.png - strip - portrait shows 1 card plus a faded sliver, not 2 - set card width to about 46% of the track.
[P1] 1024-strip-01/12.png, 1366-strip-01/12.png, 1024-04-twelve.png, 1366-04-twelve-b.png - strip - at 01 the first card starts 320-480 px in (big empty left gutter), at 12 the right half is empty, and only 2 cards are fully visible (brief: 3) - snap-align start at the container edge, 3-up width.
[P2] 768-strip-06/12.png, 768-04-twelve(-b).png - strip edge - caption fragments of neighbouring cards ("ah", "through the sky", "na", "be praised") show unfaded in the margin, and "Hasta Uttānāsana" is cut - mask or clip the whole card, captions included, at the container.
[P2] 768-06-paris(-b).png, 1024-06-paris.png, 1366-06-paris(-b).png - saree-eiffel - washed out, grey haze, soft, and she is small in frame; not crisp or natural - regrade contrast, crop tighter on her, sharper upscale.
[P2] 768-01-top.png - cover sun disc - cut by a hard horizontal edge at about y 515 beside the Sanskrit line, lower-left empty - overflow:visible on the sun layer, tighten the cover.
[P2] 1366-04-twelve.png, 1366-strip-01.png, 1024-04-twelve.png - Surya motif - disc chopped by a hard straight edge at its bottom, and one thick vermilion ray sticks out at the top right - radial mask, uniform rays.
[P2] 768-05-classes.png - Individual card - "Reserve a session" wraps to two lines while its siblings stay on one - shrink the pill padding or shorten the label.
[P2] all widths, header - logo - the mark is about 45 px wide and the gold "1" nearly vanishes, so G1A is barely legible (the footer is fine) - enlarge to about 56 px, heavier strokes at small sizes.
[P3] 768-03-practice.png, 1024-03-practice-b.png, 1366-03-practice.png - practice - empty left column under the sutra, and the staggered mismatched photo sizes look ragged - align heights.
[P3] 768-06-paris-b.png, 768-07-contact-b.png - photo cards sit left with about 30 percent empty on the right - full width or centre.
[P3] 768-04-twelve-b.png, 1024-04-twelve-b.png - strip section - visible band seams and a lighter rectangle behind the controls - unify the background.
[P3] 1024-07-contact-b.png - lobby photo - saturated orange, off the parchment palette - warm-grade it down.
[P3] 1366-02-about.png - void under the diwali photo while the text runs long - sticky photo or add a pull quote.

## Excellent, keep:
- Cover at 1024 and 1366: crisp, natural sun photo, clear primary and secondary buttons, strong headline hierarchy.
- About: clean diwali crop, first-person copy, credential and the 8 training items high up in two columns.
- Compact form (two columns, pill choices, short consent) and the calm parchment manuscript look with hairline icons and Devanagari numerals.
