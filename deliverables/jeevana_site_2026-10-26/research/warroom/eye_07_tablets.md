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
