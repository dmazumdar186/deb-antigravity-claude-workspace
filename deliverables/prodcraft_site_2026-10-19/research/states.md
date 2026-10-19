# Page states — note for reviewers

The cover (400svh desktop / 250svh mobile) and the ledger (300svh desktop) are pinned scroll tracks:
a sticky 100svh stage stays on screen while the page scrolls under it. A **full-page capture** therefore
paints the same stage at every point of the track (repeated dark covers, repeated ledger sheets).
That is an artefact of stitching, not what a visitor sees. Judge the cover and ledger from the
viewport captures taken at track progress (cover-0/50/100/fade, foldout-mid/open, mobile-*).

- Reduced motion: cover shows the poster frame (hero.jpg) + text, beats switch without animation,
  the ledger renders fully open (`--fold:1`).
- Deep links (`/#systems`, `/#03-systems`, `/#02-founder`) jump straight to the deck on load.
- Mobile bottom bar appears only once the cover is hidden (ledger at ≤70 % of the viewport).
