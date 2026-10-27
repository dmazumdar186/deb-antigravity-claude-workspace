# eye_05_tv: 2560 and 3840 screens

Verdict: NOT YET

Photos are framed, sharp and warm; the problem is that 3840 is the 1440 layout, merely stretched.

## Defects
1. [P1] 3840-01-top, 3840-02-practice, 3840-03-twelve, 3840-04-classes, 3840-05-about, 3840-06-contact — whole system — "From the sofa I cannot read this." Container is about 57% of the width, body about 1.1rem equivalent, nav, labels and form text are tiny, with 20% dead margin each side — fix: scale root font with clamp (html{font-size:clamp(16px,0.55vw+8px,30px)}) and raise container max-width to about 2000px at >=3200px.
2. [P1] 2560-strip-01, 3840-strip-01 — twelve-breaths strip — only 3 cards (the 4th is cropped), and the left 40% is empty rings; the brief says 4 to 5 cards — fix: at >=2200px shrink card basis to about 18vw, start the track at the container edge (not 40% in), show 4.5 cards.
3. [P1] 3840-strip-06, 3840-strip-12, 2560-strip-06 — rings backdrop — hairline circles run through the captions ("Om Khagāya Namaḥ", "Om Arkāya Namaḥ"), i.e. under type — fix: clip the ring layer to the left gutter (width:30%; z-index:-1; mask-image fade) and keep it out of the track area.
4. [P1] 2560-strip-06/12, 3840-strip-06/12 — inactive-card captions (Sanskrit, mantra, translation) — washed out, about 2:1 contrast, minuscule at 4K — fix: inactive opacity .55 (not .3), translation font-size >=1.05rem, colour var(--ink-2).
5. [P2] 2560-strip-12, 3840-strip-12 — last slide — right 40% is a vast empty void and the left neighbours are cut mid-word ("isana", "amaḥ") — fix: add end-padding so the final card centres, or lock scroll-snap-align:center for the last card.
6. [P2] 3840-01-top — hero — headline is small for the canvas, 200px dead below the rule, the ring crosses the hairline footer rule and the photo caption — fix: hero min-height 100svh, vertically centre, fade the ring behind the photo only (right: -8%; width: 70%).
7. [P2] 2560-04-classes-b, 2560-strip-*, 3840 strips — sticky header — translucent bar shows headline ghosts ("a hello.", "Twelve moments.") under the nav — fix: header background:rgba(243,238,227,.94); backdrop-filter:blur(14px).
8. [P2] 2560-04-classes, 3840-04-classes — class cards and form — "Register your interest" links, labels and input text are tiny, cards roomy with 1/3 empty, input borders faint — fix: link 1rem, labels .95rem, input border var(--line-strong), card padding trimmed.
9. [P2] 2560-02-practice, 3840-02-practice — gallery — three photos on a staggered baseline leave a ragged hole at the bottom and a floating orphan ring top right — fix: align tops or bottoms with a shared grid; drop the lone ring or anchor it behind photo 1.
10. [P2] 2560-05-about, 3840-05-about — Eiffel photo — a phone snapshot, more saturated and less graded than the studio-like set; the pill caption sits loose — fix: apply a shared filter (saturate(.9) contrast(.96)) and tuck the pill inside the frame corner.
11. [P2] 2560-03-twelve — eyebrow area — "Swipe or drag..." hint is tiny and floats alone far right of the headline — fix: move it next to the arrows, 1rem.
12. [P3] 3840-06-contact, 2560-06-contact — newsletter — an optional Phone field sits beneath Email with the Subscribe button beside Email only; unbalanced — fix: drop Phone or stack the button full-width.
13. [P3] 3840-06-contact — footer — "Designed by Debanjan Mazumdar · ProdCraft" reads developer voice at 4K — fix: lighten to opacity .6 or remove.
14. [P3] 2560-06-contact — contact rows — arrows sit at the far right, 1700px from the label — fix: cap rows at max-width 1200px or add a hover underline connecting them.

## Excellent, keep:
- Framed photographs: thin cream border, soft shadow, rounded corners, true photos, no dark plate.
- Cormorant display headlines with the italic amber "at a time." and the Sanskrit/IAST pairing: refined, calm.
- Warm paper palette, consistent amber accents, tidy eyebrow numbering (01/ to 05/) and the contact rows in large serif.
