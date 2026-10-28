# v5.1 review — four eye audits (Sonnet) + Sol critique. Fix every P1 and P2; P3 where one line.

## eye: phones
# eye_21 phones (320 / 390 / 844 landscape), screens_v4, 48 PNGs read

Verdict: NOT YET (P1 1, P2 5, P3 5)

Order, voice, no fees or euro signs, parchment look and calm iconography are right. Cover shows the sun photo and "Reserve a session". About comes next with the diwali photo, in first person. No Instagram UI anywhere. The strip is clean at 390 and 844: no gap before card 1 or after card 12, controls below the captions. One photo and a few edge cases block release.

## Previous items (eye_17)
- P1 saree-eiffel photo: STILL OPEN (saree now saturated, but see below)
- P2 header logo too small: STILL OPEN (wordmark now readable; seal is about 30 px, G1A unreadable)
- P2 390 sticky bar over card: FIXED (controls sit in flow, under the caption)
- P2 844 strip controls clipped: FIXED (circles fully visible, two cards per view)
- P2 844 stray "sky" text: FIXED
- P2 320 header 20% and no controls: PARTLY (header collapses to one row on scroll; controls still not visible at 320, see below)
- P2 form, footer, landscape photos unseen: STILL OPEN (no form or footer in any shot; newsletter stops at "Your email")
- P3 peeking card caption cut: FIXED (only an image sliver shows)
- P3 320 cover has no photo on first screen: STILL OPEN (button is visible, photo is not)
- P3 844 cover: FIXED (button fully in view, chip clear of head)
- P3 844 About photo fills the screen with the right half empty: STILL OPEN
- P3 door handle: FIXED (zoomed, it is a real handle)
- P3 credential link too large: FIXED

## New defects
[P1] 390-06-paris-b.png, 320-06-paris-b.png, 390-06-paris.png — saree-eiffel photo — still a hard cut-out: the subject sits on a blurred, ghostly tower with a pale ledge band under the hem, a bleached strip across the top at 320, and a halo at the feet. It reads as pasted-on, and every other photo is natural. — Replace with the original uncomposited frame, or re-key with a soft edge and remove the ledge and top strip.

[P2] 390-01-top.png — cover quote — a vermilion diagonal ray cuts through "sthira-sukham āsanam", so decoration sits over text. — Move the sun-ray decoration behind the photo only, or clip it away from the caption.

[P2] 320-strip-01.png, 320-strip-06.png, 320-strip-12.png, 320-04-twelve-b.png — 320 strip — the card top and the "01 / 12" chip slide under the header, and the controls row is off-screen in every shot. — Increase the scroll-margin-top to the header height and keep the controls on screen with the card.

[P2] 390-07-contact.png — Superprof row — "My Superprof profile" fills the line, so the arrow orphans onto a second line. The rows are also inconsistent: email is stacked, the others are inline. — Use one layout for all rows (label above value) and keep the arrow on the same line.

[P2] 320-01-top.png / 390-01-top.png — header seal — about 30 px, wordmark about 10 px. G1A and the arc text are illegible. — Make the seal at least 44 px, or the cover seal larger. Capture the footer seal as well.

[P3] 390-01-top.png — cover — an unexplained "2.46" label with a vertical rule beside the Sanskrit quote. — Remove it or explain what it is.

[P3] 320-01-top.png — nav — "Contact" touches the right screen edge with no margin. — Tighten the nav gap or the font size.

[P3] 390-04-twelve-b.png, 320-04-twelve-b.png — strip panel — hard-edged tonal bands above and below the strip look like a layering seam. — Feather the panel gradient into the page.

[P3] 844-04-twelve-b.png (and the 844 strip shots) — card 3 shows a clipped sliver at the right edge, chip fragment included. — Fade the peek mask.

[P3] 844-02-about.png — About — the photo is still tall, with the right half empty. — Cap the photo at about 75vh and place the text beside it.

## Keep
Seat of calm: the yantra, lotus, sun and diya discs, the margin rules and the strip captions. Email now sits on one line at all widths. The 844 strip is now well proportioned.

## eye: tablets
# Eye 21 - tablets (768, 1024, 1366), screens_v4

Verdict: NOT YET. All 48 PNGs read. Open P1 = 0, open P2 = 2 (P3 = 8).
Compliant: sun-photo cover with "Reserve a session", diwali About next (first person), no fees or euro, no Instagram UI, parchment look with icons clear of body text, compact form, email on one line, no clipped body text.

## Previous items (eye_17)
- P1 email mid-word break: FIXED.
- P1 768 strip 1 card plus sliver: FIXED (2 portrait).
- P1 strip gutters, only 2 of 3 visible: FIXED (flush at 01 and 12, 3 landscape, controls below captions).
- P2 768 caption fragments: FIXED.
- P2 saree-eiffel soft and hazy: STILL OPEN.
- P2 768 cover sun disc edge: FIXED.
- P2 Surya disc chop: FIXED; thick vermilion ray cut at section top STILL OPEN (now P3).
- P2 768 Individual "Reserve a session" wrap: FIXED.
- P2 header logo too small, G1A illegible: STILL OPEN.
- P3 practice empty left column and ragged photos: STILL OPEN.
- P3 768 photo cards left with empty right: STILL OPEN.
- P3 band seams behind strip: STILL OPEN.
- P3 orange lobby photo: STILL OPEN.
- P3 1366 void under diwali photo: FIXED (sticky).

## Defects
[P2] 768-06-paris-b.png, 1024-06-paris.png, 1366-06-paris(-b).png - saree photo - hazy, soft, pasted-looking cut-out, pale unfilled band under her feet inside the frame - regrade, tighter crop that fills the frame, sharper source.
[P2] all widths, header (768-01-top.png, 1366-01-top.png) - seal - about 44 px, "G1A" reads "QIA", arc text is noise - enlarge to about 60 px, heavier strokes at small size.
[P3] 768-01-top.png - cover - about 380x450 px empty parchment left of the photo - centre the photo or add the quote there.
[P3] 768-02-about.png - diwali photo - 560 px wide, void right, heading pushed below the fold - full width, shorter crop.
[P3] 1024-04-twelve.png, 768-04-twelve.png, 1366-04-twelve-b.png - Surya motif - vermilion ring overlaps the pale disc, thick ray cut at section top - separate them, remove the cut ray.
[P3] 1024-strip-01.png, 1366-strip-01.png - strip edge - fragment of the next counter pill shows in the sliver - mask pills in slivers.
[P3] all 04-twelve screens - safety note - indented differently from the "Swipe or drag" line - align left.
[P3] 1024-06-paris.png - "Read them on Superprof" - arrow floats detached - keep it adjacent.
[P3] 1024-07-contact-b.png, 1366-07-contact-b.png - footer seal - about 50 px with microscopic wordmark - drop the wordmark or enlarge.

## Keep
Covers, strip (edge-aligned, captions then controls), classes cards, compact form, contact rows.

## eye: desktops
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

## eye: tv
# eye_21_tv: 2560 and 3840 screens (22 PNGs read)

**Verdict: NOT YET** (0 open P1, 6 open P2)

Both P1s from eye_17 are fixed. The email is on one line, the strip ends have no gap, the controls sit below the captions, and there are no fees, EUR or Instagram UI. What is left is 4K scale and polish.

## Previous items (eye_17)
- FIXED: P1 email wrap (one line at 2560 and 3840).
- FIXED: P1 strip end gaps. Card 1 and card 12 sit flush with the container, with no empty band.
- FIXED: header height and logo size, and the header no longer overlaps content.
- FIXED: Sūrya rays no longer cross the headline.
- FIXED: lobby photo is enlarged and aligned with the heading.
- FIXED: phone numerals are lining.
- FIXED: strip controls sit below the captions.
- FIXED: training heading arrow is inline.
- FIXED: the about-page lists are readable at 3840 (about 29 px). At 2560 they are borderline, about 19 px.
- STILL OPEN: P2 form labels and consent text at 3840 (3840-05-classes, 3840-07-contact), about 13-14 px.
- STILL OPEN: P2 cover at 3840. The photo is 27% of the width, the CTA is small, and each side has 16% empty margin.
- STILL OPEN: P2 seam. Tone steps show in the left and right gutters (2560-04 at y 515; 3840-04 and 3840-strip-* at the section bands).
- STILL OPEN: P2 diwali photo at 3840-02, with about 260 px of dead space under it. It is larger than before.
- STILL OPEN: P2 Eiffel photo, soft and milky (see the new defect below).
- STILL OPEN: P3 diwali green speck by her face (2560-02, 3840-02).
- STILL OPEN: P3 "Paris." orphan (3840-02).
- STILL OPEN: P3 blank band between title and mantra (2560-strip-06; at 3840 it is uneven because titles wrap to one or two lines).
- STILL OPEN: P3 card text measure fills about 60% of the card (2560 and 3840 classes).
- STILL OPEN: P3 paper still reads flat tan, and the icon circles float alone at the right.
- STILL OPEN: P3 logo ring text is illegible and soft at header size.

## New defects
- [P2] 3840-strip-01/06/12 — carousel — 6 cards plus a peek at 3840, against the brief's 5, so cards are about 490 px and the type is small — cap the card count at 5, or raise the card width.
- [P2] 2560-06-paris.png, 3840-06-paris.png — Eiffel photo — a pale band is baked into the bottom, the saree hem spills past the image edge, and the source is soft with a low-contrast figure — re-crop above the band and add contrast and light sharpening.
- [P3] 3840-07-contact.png — contact rows — the email value stacks under its label while the other rows run inline, so the left edges are inconsistent — use one row layout.
- [P3] 3840-05-classes.png — reservation form — about 480 px wide with about 340 px empty to its right — widen it to the container.
- [P3] 3840-01-top.png — hero portrait — the skin and hair look slightly smooth and soft from the upscale — use a larger source or a mild unsharp.
- [P3] 2560-03-practice.png — header — a large void between the headline and the paragraph, with the icon alone at the far right — tighten the grid.
- [P3] 3840 header — nav labels — about 25 px, small for a sofa — scale nav and Reserve by about 1.25x at 3000 px and above.

## Checks that pass
- Photos: no Instagram UI, no halos, no waxy skin in the strip, and the cover is crisp at 2560.
- Strip: 4 cards at 2560, with controls below the captions.
- Logo: the seal has a gold ring and reads clean.
- Icons: the calm iconography never sits under body text.
- Copy: no fees or EUR anywhere.
- Container: not stretched. It is about 2200 px at 2560 and 2600 px at 3840.

## critique: Sol
# Round 9 critique by openai/gpt-6.1-sol-pro

**Verdict: HOLD.** The supplied code has a strong foundation, but does not yet deliver the contracted design. Passing gates are useful evidence—not SHIP: several assertions now endorse deviations. I reviewed code and logs; the PNGs themselves were not supplied.

1. **[P1] [site/index.html:#classes; site/js/i18n.js:class copy; research/functional_v4.mjs]** Verified prices are completely missing; the gate explicitly rewards “no €,” contradicting the latest addendum → Show **€50/hour**, online €50/hour, **5 hours €250 / 10 hours €500**, and in-home **€25/hour after tax credit (crédit d’impôt)** in EN/FR. Distinguish individual sessions at hers/at yours/online; retain small groups and workshops by arrangement. Replace the no-price assertions with exact-content checks.

2. **[P1] [site/css/styles.css::root, “v5” decoration, final overrides]** Ochre parchment, inset shading, manuscript borders, seals and saturated rays compete with the photographs. This reads as ornamental theming rather than a singular senior-level idea → Restore paper `#F3EEE4`, ink `#2A2622`, ink-soft `#4A433C`, mist `#E7DFD0`, ochre `#C4731A`/text `#9A5A12`; remove fibre, holes and section vignettes. Let the twelve-photograph sequence provide the wow.

3. **[P1] [site/index.html:.hero-frame, .about-frame, .paris-frame; metadata]** The specified photographic story has been replaced with AI-upscaled lifestyle assets → Restore seated `hero` with 800/1400/2000/2800 candidates, the supplied Paris Chakrāsana secondary photograph, and hero-derived OG artwork with paper margin. Update EN/FR alts and OG descriptions; FR hero alt must begin “Jeevana assise.” Preserve environments, rounded frames and soft shadows—no cut-outs or dark plates.

4. **[P1] [site/css/styles.css:.card; site/js/main.js:initStrip; functional_v4 assertions]** Start alignment replaces the required centred-card mechanic; several end cards share one scroll position, so the counter changes without photographic movement. Neighbours never scale `.96` → Use centre snapping, sufficient leading/trailing space to centre cards 1 and 12, centre-distance active detection, and `1/.96` scaling. Remove caption-hiding `.is-out` and photo-edge gradient overlays. Rewrite tests around actual centring and distinct movement through all twelve.

5. **[P1] [site/index.html:.twelve; site/css/styles.css:.portrait-art, .twelve]** Straight rays, filled disc and extra breathing rays replace the twelve-arcs signature; accumulated positioning rules make placement fragile → Use twelve unequal-length arcs around three unfilled circles, ink `.14`, active ochre `.5`; retain 240-second rotation and 5.5-second centre breath only. Position behind-right at 90vmin desktop/70vmin phone; ensure visible geometry extends beside the frame, never across copy or figure.

6. **[P1] [site/js/main.js:EVENT_NAMES; functions/api/event.ts; HANDOFF]** Front-end aliases conflict with the supplied contractual event names, while logs claim the aliases match the backend → Inspect the retained allowlist and reconcile this discrepancy explicitly before shipping. Send the approved names unchanged; test all four events, not just registration. Do not silently modify the retained API to accommodate aliases.

7. **[P1] [site/css/styles.css:responsive overrides; research/screens_v4]** At 1024 portrait the hero is pulled upward and restricted to `34svh`; 4K overrides exceed the 2200px container and 96px gutter caps. At ≤360px navigation disappears after scrolling → Remove negative overlap, restore the specified container/gutter limits and keep navigation accessible. Review 390/1024/1440 plus every required orientation, especially 320px header fit and landscape captions; do not truncate mantra glosses.

8. **[P2] [site/index.html:section order, .cover-ctas; styles.css:.about-image]** A long About/training block interrupts the introduction before the signature experience; its sticky image contradicts motion restraint → Restore `top → practice → twelve → classes → about → contact`, consolidate Paris/testimonials with About, and remove stickiness. Restore “Register for a class” and “See the classes”; maintain distinct editorial offsets at 1024.

9. **[P2] [site/css/styles.css:contrast, .contact-value, .design-credit]** Contact text can shrink through container arithmetic; credit opacity weakens contrast, and the designer email link is hidden → Set readable minimum sizes, allow deliberate address wrapping, remove credit opacity/hiding, and measure every text/background pairing at ≥4.5:1. Retain visible focus rings and ≥44px touch targets; test keyboard focus throughout.

10. **[P2] [site/js/i18n.js; site/privacy/index.html]** Translation coverage is broad, but logo alternatives and no-JS messaging remain English; privacy source was not supplied → Localize meaningful logo alternatives and fallback messaging; verify both privacy blocks and every accessible label. Preserve all four consent strings **byte-for-byte**: current supplied strings match.

11. **[P2] [site/index.html:JSON-LD, .diwaliChip; i18n.js:lineageBody]** `G1A` organization/founder metadata and “lit at home” lack supplied factual verification; a personal attachment to the school maxim is invented → Remove unsupported claims. Use the specified Person schema with `jobTitle: "Yoga teacher"`; attribute the maxim to Sri Aurobindo without inventing Jeevana’s feelings.

12. **[P2] [research gates; assets/photos; styles.css]** “144K total” does not establish above-fold transfer weight; image dimensions also mismatch several manifest ratios → Measure cold-cache transfers at each DPR, enforce ≤600KB above fold, correct intrinsic dimensions and `sizes`, and verify no source upscaling. Consolidate the cascading overrides. Preserve CSP: logs report clean execution; do not loosen `_headers`.

**Already excellent—must not be lost**

13. **[P3] [main.js:forms]** Robust inline submission, retained inputs on failure, focus management, honeypots and verbatim consent.

14. **[P3] [index.html:.practice-gallery]** Wide/square/tall environmental photographs with restrained frames and editorial rhythm.

15. **[P3] [main.js; i18n.js]** Framework-free interaction, persistent bilingual content, reduced-motion handling and substantial functional coverage.
