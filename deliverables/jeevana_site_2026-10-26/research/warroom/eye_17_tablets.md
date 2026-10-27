# Eye 17 - tablets (768 portrait, 1024 and 1366 landscape), screens_v4

Verdict: NOT YET. All 48 PNGs were read (768-, 1024-, 1366-). Counts: P1 = 3, P2 = 6, P3 = 6.

What is right: the order is correct (cover with sun photo and "Reserve a session", then About with the diwali photo). Voice is first person, skills are high up, and there is no fee or euro sign anywhere. No Instagram arrows, dots or avatars are visible on any photo.

## Defects
[P1] 1024-07-contact.png, 1024-07-contact-b.png, 1366-07-contact.png, 1366-07-contact-b.png, 1366-07-contact-b2 (footer view) - Email row - the address breaks mid-word ("gma / il.com" at 1024, "gmail.co / m" at 1366), an orphaned letter on a primary contact line - set the value to `overflow-wrap:anywhere` only as a fallback, and size it with clamp() (about 1.5rem) so the whole address fits on one line, or break only after "@".
[P1] 768-04-twelve.png, 768-04-twelve-b.png, 768-strip-01/06/12.png - twelve-breaths strip - portrait shows 1 card plus a faded sliver of the second, not 2 cards - set the card width to about 46% of the track at portrait.
[P1] 1024-strip-01.png, 1024-04-twelve.png, 1366-strip-01.png, 1366-04-twelve-b.png, 1024-strip-12.png, 1366-strip-12.png - strip - at 01 the first card starts about 320-480 px in, leaving a large empty left gutter; at 12 the right half is empty; only 2 full cards show at 01 (brief says 3 landscape) - align the first and last snap to the container edge (scroll-snap-align:start, no centred padding) and use a 3-up width.
[P2] 768-strip-06.png, 768-strip-12.png, 768-04-twelve.png, 768-04-twelve-b.png - strip edge - text fragments of neighbouring cards ("ah", "through the sky", "na", "be praised", a stray "na" beside the arrow) show unfaded in the margin, and "Hasta Uttānāsana" is cut at the right - apply the edge mask to the whole card including captions, or clip the track with overflow:hidden at the container.
[P2] 768-06-paris.png, 768-06-paris-b.png, 1024-06-paris.png, 1366-06-paris.png - saree-eiffel photo - washed-out, low contrast, grey haze, soft focus, and she is small in frame; this does not read as crisp or natural - regrade (levels and contrast toward the paper palette), crop tighter on her, and use a sharper upscale.
[P2] 768-01-top.png - cover sun disc - the disc and rays are cut by a hard horizontal line at y of about 515, beside the Sanskrit line, and the lower-left is empty - remove the clipping from the sun container (overflow:visible), and tighten the cover so the photo and text sit together.
[P2] 1366-04-twelve.png, 1366-strip-01.png, 1024-04-twelve.png - Sūrya motif in the Surya Namaskara header - the disc is chopped by a hard straight edge at its bottom (y of about 345 / 928) and one thick vermilion ray sticks out at the top right - clip with a mask or radial fade, and make the rays uniform.
[P2] 768-05-classes.png - Individual classes card - "Reserve a session" wraps onto two lines while its siblings are one line, so the three cards are uneven - shrink the pill padding or use a shorter label ("Reserve").
[P2] all widths (header) - logo - the G1A mark is about 45 px wide and the gold "1" nearly vanishes, so G1A is only just legible; the footer version is fine - raise the header mark to about 56 px, or heavier strokes at small sizes.
[P3] 768-03-practice.png, 1024-03-practice-b.png, 1366-03-practice.png - practice - the left column is empty under the sutra, and the three photos are staggered at different sizes, which looks ragged - align heights, or drop the stagger.
[P3] 768-06-paris-b.png, 768-07-contact-b.png - portrait photo cards sit left with the right 30 percent empty - make them full width, or centre them.
[P3] 1366-02-about.png - About - void under the photo while the text runs on - make the photo sticky, or add a quote below it.
[P3] 768-04-twelve-b.png, 1024-04-twelve-b.png - strip section - visible band seams (hard background step at about y 413-457) and a lighter rectangle behind the controls - unify the background and remove the control backdrop.
[P3] 1024-07-contact-b.png - lobby photo - orange and saturated, off the parchment palette - warm-grade it down.
[P3] 768-02-about.png - the "Om" ring sits beside the About heading and reads as a stray circle - lower its opacity or align it to the grid.

## Excellent, keep:
- Cover at 1024 and 1366: sun photo crisp and natural, clear "Reserve a session" plus "Get to know me", good hierarchy.
- About with the diwali photo: clean crop, first-person copy, credentials and the 8 training items high up, in a two-column list.
- The compact form (two columns, pill choices, short consent) and the manuscript look: parchment, hairline icons and Devanagari numerals, calm and uncluttered.
