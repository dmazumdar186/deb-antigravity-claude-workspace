# eye_17 phones (320 / 390 / 844 landscape), screens_v4, 48 PNGs read

Verdict: NOT YET (P1 1, P2 6, P3 6)

Order, voice, no-fee/no-€, parchment look, Om/lotus/sun/yantra/diya icons, and the cover/diwali/lobby photos are right. No Instagram arrows, dots or avatars found. Strip cards render cleanly and the carousel visibly changes card across 01, 06 and 12 on all three widths. The blockers are one photo and the phone chrome around the strip.

## Defects

[P1] 390-06-paris-b.png (also 320-06-paris-b, 390-06-paris) — saree-eiffel photo — washed-out, hazy and soft. The tower is a pale ghost, she is small in frame, and a bleached band under her feet gives a cut-out, pasted-on-a-plate look. Every other photo is saturated, so this one is the odd one out. — Re-grade levels/contrast to the paper palette, crop tighter on her, and remove the white band at the bottom edge.

[P2] 320-01-top.png, 390-01-top.png (all phone shots) — header logo — "JEEVANA YOGA" is about 6 px and the G1A letters are hard to read at about 80 px wide; at 320 it reads "GIA". — Use a larger mark (at least 110 px wide) and a minimum 9 px wordmark, or the stacked lockup on phones.

[P2] 390-04-twelve.png — sticky control bar — on entering the section the bar sits over the lower part of the 01/12 card, so feet and caption are cut off and it looks broken. — Place the controls in flow under the caption, or stick them only once the full card is in view.

[P2] 844-strip-01.png, 844-strip-06.png, 844-strip-12.png — landscape strip — the arrow and play controls are clipped at the bottom edge (circles show about 5 px). The card is only about 220x270 px, with half the width empty on the right. — Size card and caption to (viewport height − 53 px header − controls) so the controls sit fully inside the view.

[P2] 844-strip-06.png — stray text — an orphan fragment "sky" at the far left (x≈8, y≈179). — Clip or hide off-card alt/caption text (`overflow:hidden` on the track, or `sr-only`).

[P2] 320-04-twelve-b.png, 320-strip-01.png, 320-strip-06.png, 320-strip-12.png — 320 header — the two-row sticky header takes about 113 of 568 px (20%). No strip controls are visible in any of the 320 strip shots. — Collapse the nav row on ≤360 px (scroll-hide, or a single row), and keep the controls on screen with the card.

[P2] screens_v4 (all widths) — registration form — no screenshot shows the form, so the ≤760 px / 44 px compactness claim is unproven. The 05-classes-b shots stop at the "Reserve a session" label. Also unseen: the 844 saree-eiffel and lobby photos, the newsletter row and the footer. — Add form, footer and landscape-photo shots and re-audit.

[P3] 390-04-twelve-b.png, 320-04-twelve-b.png — peeking next card — its caption is cut mid-glyph ("INH", "H", "Om"). — Fade or mask the peek, or hide the caption of the non-active card.

[P3] 320-01-top.png — cover — no sun photo on the first screen at 320, and at 390 it starts at y≈640 with only hair and the chip showing. — Tighten cover padding or reorder so the face appears with the button on first view.

[P3] 844-01-top.png — cover landscape — "Reserve a session" bottoms out at y≈383 of 390, and the "Jeevana Gogula · Paris" chip crowds the top of her head. — Reduce headline size or padding so the button has air above the fold, and move the chip to the lower-left.

[P3] 844-02-about.png, 844-02-about-b.png — About landscape — the diwali photo (about 550 px wide) fills more than one screen height and the right half is empty. — Cap photo height to about 75vh and place the text beside it.

[P3] 844-02-about.png (door handle at ≈105,257; 390-02-about at ≈65,205) — diwali photo — a small "◂"-shaped door handle could read as a leftover Instagram arrow to a harsh client. — Confirm it is the handle; if not, retouch it out.

[P3] 390-02-about-b.png — credential — "Certified yoga instructor (Moniteur de Yoga), Tapovan" is a large underlined display link that competes with the section heading. — Set it at body-plus size with the arrow inline.

## Excellent, keep:
- Cover to About order, first-person voice and the "Reserve a session" button: clear, vermilion, and nothing in it hides the call to action.
- Parchment grain, margin rules, binding-hole dividers (o—ॐ—o), Devanagari numerals and the hairline discs (Om, lotus, sun, yantra, diya): calm and not cluttered; none sits under body text.
- The strip cards: crisp photos with an index chip, Sanskrit/IAST/mantra captions, an active ring, and the counter and play control. The 06 and 12 states prove it moves.
