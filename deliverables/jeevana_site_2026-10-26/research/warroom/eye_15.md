# eye_15 - classes + about, screens_v4

Verdict: NOT YET (P1: 0, P2: 3, P3: 6)

Coverage note: 320/390 quote blocks and the 1440/1920/2560/3840 about-b frames were not in the capture set. Quotes were judged at 768-2560 only.

## Defects
- [P2] all about frames (320-3840) - training bullet list to "Tapovan, in the pays de Caux..." paragraph - zero gap, the list collides with the next paragraph and the calm rhythm breaks - add margin-top (~1em) after the ul.
- [P2] 320-04-classes-b, 768-04-classes, 1024-04-classes - price line "EUR50 per hour . 5 hours EUR250 . 10 hours EUR500" - wraps mid-tier ("10 / hours EUR500", "5 hours / EUR250"), reads as three loose strings - wrap each tier in a nowrap span, or stack the three tiers on separate lines at <=1100px.
- [P2] 1024/1366/1440/1920-05-about - credential h3 (link) - "Tapovan" stranded alone on line 2 (and "Yoga), Tapovan" at 1024) - text-wrap: balance, or bind "Moniteur de Yoga), Tapovan" with nbsp.
- [P3] 1920-05-about - training paragraph - line 2 starts with "&" - nbsp between "Yoga" and "&".
- [P3] 3840-05-about - intro paragraph - "and stillness." orphan line - text-wrap: pretty.
- [P3] 3840-04/05 (and 2560) - content column ~1360px in a 3840 canvas; price line and bullets are the smallest text (~13px equivalent) - scale root font-size with clamp() above 2200px, or widen max-width.
- [P3] 2560-04-classes - subline "Timetable opens soon" sits ~20px above the cards, much tighter than at 1440/1920 - use the same clamp-based gap.
- [P3] all widths - in-home EUR25 / online EUR50 line - plain paragraph detached from the cards, same weight as the "In French or English" line, easy to miss - style it as a price footnote (ink colour, small rule) directly under the cards.
- [P3] 768-05-about - photo card - right edge stops ~100px short of the text column edge - make the image full column width or centre it.

## Passes
- Price cards: EUR50/h, 5 h EUR250, 10 h EUR500 consistent and legible at 390, 844 (cards), 1366-2560; "By arrangement" baselines align across cards.
- Quotes: serif curly-quoted, with an "Egle/Thomas, via Superprof" attribution and a hairline; they read as quotes, not marketing boxes, at 768-2560.
- About list is a calm bullet list, not a CV. The school line fits the rhythm. No clipped or overlapping text found.
- 844 landscape: the sticky header takes ~50px but nothing is crushed.
