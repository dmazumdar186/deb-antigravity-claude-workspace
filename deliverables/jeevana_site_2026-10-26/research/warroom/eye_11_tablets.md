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
