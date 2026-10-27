# eye_17 desktops (1440 + 1920, screens_v4, 22 PNGs read)

**Verdict: NOT YET** — P1: 2, P2: 8, P3: 6

Order, voice, no-fees, cover CTA, diwali About, first person and compact form all pass. The carousel is what blocks release.

## P1
- [P1] 1440-strip-01/06/12.png (also 1440-04) — card caption + pinned controls bar — the bar cuts every card's mantra translation ("to the friend of all" is guillotined at the bar edge) and on 04 it slices the card photo mid-body — a harsh client calls this a broken carousel — fix: reserve bar height in the pinned stage (card photo max-height: calc(100vh - header - bar - caption)) so caption plus translation clear the bar at 1440x900.
- [P1] 1440-04-twelve.png, 1440-strip-01/12.png, 1920-strip-12.png — strip track — at rest only 2 cards show (brief says 3–4) and ~500 px (1920: ~760 px) of dead parchment sits left of card 1. At 12/12 the right half is empty — fix: left-align the first card to the text column, shrink cards so 3–4 fit at 1440, and clamp end scroll so card 12 sits flush right.

## P2
- [P2] 1440-04, 1920-04 — Sūrya disc ornament — hard horizontal clip (y≈360 / 458) and a stray vermilion ray crosses the header rule — fix: overflow-visible with a mask fade, drop the stray ray.
- [P2] 1440-04, 1920-04 — section background — a visible tonal seam band behind the heading block (y≈465 / 543) — fix: make the aged-edge gradient continuous across the section.
- [P2] 1920-01, 1440-01 — sun photo — a ghost remnant of the Instagram multi-photo glyph near the top-right (≈1763,153 at 1920), and the face/hair are soft at 1920 — fix: inpaint the corner, apply sharper upscale + light sharpen.
- [P2] 1440-06, 1920-06 — saree-eiffel — washed-out and soft, she is small in frame, bright white ledge strip along the bottom, feet cut — fix: re-crop tighter on her, raise contrast, and grade warm.
- [P2] 1440-07, 1920-07 — lobby photo — saturated orange/red-yellow and clashes with the parchment ("warm, soft, not orange" was the brief) — fix: pull saturation about 20% and warm-grade to paper.
- [P2] 1440/1920-strip-* — twelve photos — cold, heavy blue/green and crushed grass against warm paper; strongest mismatch on the page — fix: shared warm grade, lift shadows, lower blue saturation.
- [P2] 1440-02-about, 1920-02-about, 1440/1920-03-practice — body paragraphs — about 80 ch per line (limit ~70) — fix: max-width 66ch on `.about p` and the practice intro.
- [P2] all 1440/1920 — header logo — G1A mark is ~30 px tall and "JEEVANA YOGA" ~7 px, so the G1A pun is barely legible — fix: scale the lockup to 44 px height with a heavier wordmark (footer not in these shots; check separately).

## P3
- [P3] 1440-02, 1920-02 — About h1 — orphan "Paris." on its own line, wrapped beside the Om roundel — fix: balance text (`text-wrap: balance`) or narrow the roundel.
- [P3] 1440-02 — training list — the eight items fall below the fold at 1440; the credential line is the only skill above it — fix: tighten the h1 and paragraph spacing so the list starts above 800 px.
- [P3] 1440-05, 1920-05 — card numerals ०१/०२/०३ — about 12 px and read as "o?" — fix: raise to 18 px or use Latin 01–03.
- [P3] 1440-03 — Practice — big void below the Sūtra and a floating lotus roundel with no anchor — fix: pull the roundel beside the heading, add the practice frame.
- [P3] 1440-05-classes-b, 1920-05-classes-b — form — native select chevron/font mismatches the inputs; at 1920 the form's right edge (1550) misses the 1800 grid — fix: style the select, align the form to the container.
- [P3] 1440-01, 1440-06, 1440-07 — floating cream chips on photos ("Jeevana Gogula · Paris", "Paris", "Namaste") read as stickers — fix: smaller, quieter caption below the frame.

## Excellent, keep:
- The cover composition: Cormorant headline, vermilion italic "at a time.", Sūrya disc behind the sun photo, and a clear "Reserve a session" button, with the Sūtra signature below.
- The About page: diwali photo beside a first-person block with credential link and a two-column training list; the parchment grain, ruled margins and Om dividers feel like a manuscript.
- The Classes cards and compact form: three clean cards with a highlighted active one, a 450 px two-column form with pill choices and a consent line, all calm and uncluttered.
