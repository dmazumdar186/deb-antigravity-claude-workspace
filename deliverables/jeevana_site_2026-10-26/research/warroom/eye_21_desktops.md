# eye_21 desktops (1440 + 1920, screens_v4, 22 PNGs read)

**Verdict: NOT YET** - open P1: 1, open P2: 6, P3: 7

Big progress on the strip (3 cards at 1440, 4 at 1920, flush at both ends). Photo grade, a pinned-bar overflow at 1440 and ornament artifacts still block "wow".

## Previous items (eye_17)
- P1 caption cut by controls bar: FIXED (captions and translations clear the bar; controls sit below). New issue below: bar clipped at 1440.
- P1 dead gap before card 1 / after card 12 / card count: FIXED (card 1 on text column, card 12 flush right, 3 at 1440, 4 at 1920).
- P2 Surya disc clip + stray vermilion ray crossing header rule/frame rule: STILL OPEN (ray at ~1410,120 and 1880,130).
- P2 tonal seam band on section 04: STILL OPEN (y~435 at 1440, y~510 at 1920).
- P2 sun photo Instagram glyph remnant / softness: STILL OPEN but now a tiny speck (1440 ~1352,150; 1920 ~1762,153); face slightly soft at 1920.
- P2 saree-eiffel: STILL OPEN (small, soft/plasticky, white ledge strip at bottom, bright blown blobs top-left).
- P2 lobby photo orange: STILL OPEN.
- P2 strip photos cold blue/green: STILL OPEN.
- P2 line length ~80ch: STILL OPEN on About (~78 ch at 1440, ~83 at 1920); Practice now ~70, OK.
- P2 header logo: FIXED (seal 47 px at 1440, 58 px at 1920, reads as a seal; arc text still not legible at 1440). Footer not in these screens, unverified.
- P3 About orphan "Paris.": STILL OPEN.
- P3 Devanagari card numerals: STILL OPEN (still read as "o?").
- P3 Practice void + floating lotus: STILL OPEN at 1440.
- P3 native select chevron/form edge: STILL OPEN (select bg/chevron native; 1920 form ends 1550 vs 1800 grid).

## New defects
- [P1] 1440-strip-01/06/12 - pinned controls bar - bar (ring, "Play the sequence", arrows) sits at y 873-900+, half cut by the 900 viewport; arrows/disabled ring look broken - fix: size the stage so photo + caption + bar fit 100vh minus header (photo max-height calc(100vh - 340px)).
- [P2] 1920-strip-01/06/12 - ornament rays - rays leak under the header at top right, over the carousel stage - fix: clip the ornament to its section.
- [P3] all strips - caption block - ~50 px dead gap between asana name and mantra - fix: collapse the reserved second-line height.
- [P3] 1920-07-contact - lotus roundel - floats mid-page between heading and photo, unanchored - fix: align to heading baseline right edge of the list column.

## Contract: cover, About order, first person, no fees, parchment, form PASS.

## Wow?
Not yet: a senior designer would stop at the cold, saturated strip photos, the soft saree portrait and the orange lobby shot against the warm manuscript paper.
