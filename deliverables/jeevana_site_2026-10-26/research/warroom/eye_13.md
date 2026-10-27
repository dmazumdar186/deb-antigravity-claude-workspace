# eye_13 - final verification (3840, 1024, 844, 390; 54 PNGs read)

VERDICT: SHIP (open P1: 0, open P2: 0)

## Previous P1/P2 (eye_11)
tv
- [P1] 3840 type scale / 57% container: FIXED (container now ~68% of canvas, hero headline 3 lines, photo ~40%, bottom rule visible)
- [P1] 3840 strip titles break mid-word: FIXED (5 full cards, all Sanskrit names whole)
- [P1] 3840 strip caption runs into divider/controls, unequal heights: FIXED (aligned caption rows, rule and controls clear)
- [P1] 3840 "Twelve moments." under wordmark: FIXED (header opaque; only a scroll-state touch remains, P3)
- [P2] 3840 hero wrap/small photo/cut rule: FIXED
phones
- [P1] 844 strip photos ~20px chips: FIXED (real ~220x270 framed photo per card, caption beside it, header ~52px)
- [P2] 844 caption crossing rule / "Khagaya Namah" off edge: FIXED (captions fit; strip-06/12 clean)
- [P2] 320 caption under controls: not in scope of this round's files (320 not supplied); 390 equivalent is clean
tablets
- [P1] 1024 pinned bar covers translation: FIXED (strip no longer pinned; full caption visible, controls below on 1024-03-twelve-b with dashed disabled arrow and progress ring)
- [P2] controls bar cutting "One breath." on entry: FIXED at 1024 (1024-03-twelve and 02-practice-b clean). Persists only at 390 as P3 (see below).

## New defects
[P3] 390-03-twelve.png - sticky controls bar - on entry it covers the bottom of photo 01 (mat/feet) - start bar below the card or add scroll-margin.
[P3] 3840-strip-06/12 - heading - "Twelve moments." top sits flush under the header, J descender touches the T - add scroll-margin-top ~120px.
[P3] 844-strip-06/12 - left edge - stray faded caption fragments ("sky", "is fit to be praised") from the previous card - fade or clip the off-card caption.
[P3] 1024-strip-01/06/12 - controls fall just below the 768 fold with captions in view - acceptable, shorten media slightly if wanted.
[P3] 3840-02-practice - collage - uneven photo tops and lone ring; 3840-04-classes - checkbox still small (~14px).
[P3] 844-01-top - hero photo still cropped by viewport bottom (page scrolls; acceptable).

No new P1/P2 regressions: no overlaps, clipping, crushed photos, broken strips or unreadable type found.
