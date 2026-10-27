# v5 review — four eye audits (Sonnet) + Sol and GLM critiques. Fix every P1 and P2; P3 where one line.

## eye: phones
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

## eye: tablets
# Eye 17 - tablets (768 portrait; 1024, 1366 landscape), screens_v4

Verdict: NOT YET. All 48 PNGs read. P1 = 3, P2 = 6, P3 = 5.
Compliant: order, sun cover with "Reserve a session", diwali About, first person, no fees or euro signs, no Instagram arrows, dots or avatars.

## Defects
[P1] 1024-07-contact(-b).png, 1366-07-contact(-b).png - email row - address breaks mid-word ("gma/il.com", "gmail.co/m"), an orphaned letter on the main contact line - clamp() the font size so it fits on one line, or allow a break only after "@".
[P1] 768-04-twelve(-b).png, 768-strip-01/06/12.png - strip - portrait shows 1 card plus a faded sliver, not 2 - set card width to about 46% of the track.
[P1] 1024-strip-01/12.png, 1366-strip-01/12.png, 1024-04-twelve.png, 1366-04-twelve-b.png - strip - at 01 the first card starts 320-480 px in (big empty left gutter), at 12 the right half is empty, and only 2 cards are fully visible (brief: 3) - snap-align start at the container edge, 3-up width.
[P2] 768-strip-06/12.png, 768-04-twelve(-b).png - strip edge - caption fragments of neighbouring cards ("ah", "through the sky", "na", "be praised") show unfaded in the margin, and "Hasta Uttānāsana" is cut - mask or clip the whole card, captions included, at the container.
[P2] 768-06-paris(-b).png, 1024-06-paris.png, 1366-06-paris(-b).png - saree-eiffel - washed out, grey haze, soft, and she is small in frame; not crisp or natural - regrade contrast, crop tighter on her, sharper upscale.
[P2] 768-01-top.png - cover sun disc - cut by a hard horizontal edge at about y 515 beside the Sanskrit line, lower-left empty - overflow:visible on the sun layer, tighten the cover.
[P2] 1366-04-twelve.png, 1366-strip-01.png, 1024-04-twelve.png - Surya motif - disc chopped by a hard straight edge at its bottom, and one thick vermilion ray sticks out at the top right - radial mask, uniform rays.
[P2] 768-05-classes.png - Individual card - "Reserve a session" wraps to two lines while its siblings stay on one - shrink the pill padding or shorten the label.
[P2] all widths, header - logo - the mark is about 45 px wide and the gold "1" nearly vanishes, so G1A is barely legible (the footer is fine) - enlarge to about 56 px, heavier strokes at small sizes.
[P3] 768-03-practice.png, 1024-03-practice-b.png, 1366-03-practice.png - practice - empty left column under the sutra, and the staggered mismatched photo sizes look ragged - align heights.
[P3] 768-06-paris-b.png, 768-07-contact-b.png - photo cards sit left with about 30 percent empty on the right - full width or centre.
[P3] 768-04-twelve-b.png, 1024-04-twelve-b.png - strip section - visible band seams and a lighter rectangle behind the controls - unify the background.
[P3] 1024-07-contact-b.png - lobby photo - saturated orange, off the parchment palette - warm-grade it down.
[P3] 1366-02-about.png - void under the diwali photo while the text runs long - sticky photo or add a pull quote.

## Excellent, keep:
- Cover at 1024 and 1366: crisp, natural sun photo, clear primary and secondary buttons, strong headline hierarchy.
- About: clean diwali crop, first-person copy, credential and the 8 training items high up in two columns.
- Compact form (two columns, pill choices, short consent) and the calm parchment manuscript look with hairline icons and Devanagari numerals.

## eye: desktops
# eye_17 desktops (1440 + 1920, screens_v4, 22 PNGs read)

**Verdict: NOT YET** — P1: 2, P2: 8, P3: 4

Order, voice, no-fees, cover CTA, About and form pass. The carousel blocks release.

## P1
- [P1] 1440-strip-01/06/12.png — card caption + pinned controls bar — the bar cuts every card's mantra translation ("to the friend of all" is guillotined at the bar edge) and on 04 it slices the card photo mid-body — fix: reserve bar height in the pinned stage (card photo max-height: calc(100vh - header - bar - caption)) so caption plus translation clear the bar at 1440x900.
- [P1] 1440-04-twelve.png, 1920-strip-12.png — strip track — at rest only 2 cards show (brief says 3–4) and ~500 px (1920: ~760 px) of dead parchment sits left of card 1. At 12/12 the right half is empty — fix: left-align the first card to the text column, shrink cards so 3–4 fit at 1440, and clamp end scroll so card 12 sits flush right.

## P2
- [P2] 1440-04, 1920-04 — Sūrya disc ornament — hard horizontal clip (y≈360 / 458) and a stray vermilion ray crosses the header rule — fix: overflow-visible with a mask fade, drop the stray ray.
- [P2] 1440-04, 1920-04 — section background — visible tonal seam band (y≈465 / 543) — fix: continuous aged-edge gradient.
- [P2] 1920-01, 1440-01 — sun photo — a ghost remnant of the Instagram multi-photo glyph near the top-right (≈1763,153 at 1920), and the face/hair are soft at 1920 — fix: inpaint the corner, apply sharper upscale + light sharpen.
- [P2] 1440-06, 1920-06 — saree-eiffel — washed-out and soft, she is small in frame, bright white ledge strip along the bottom, feet cut — fix: re-crop tighter on her, raise contrast, and grade warm.
- [P2] 1440-07, 1920-07 — lobby photo — saturated orange/red-yellow and clashes with the parchment ("warm, soft, not orange" was the brief) — fix: pull saturation about 20% and warm-grade to paper.
- [P2] 1440/1920-strip-* — twelve photos — cold, heavy blue/green and crushed grass against warm paper; strongest mismatch on the page — fix: shared warm grade, lift shadows, lower blue saturation.
- [P2] 1440-02-about, 1920-02-about, 1440/1920-03-practice — body paragraphs — about 80 ch per line (limit ~70) — fix: max-width 66ch on `.about p` and the practice intro.
- [P2] all 1440/1920 — header logo — G1A mark is ~30 px tall and "JEEVANA YOGA" ~7 px, so the G1A pun is barely legible — fix: scale the lockup to 44 px height with a heavier wordmark.

## P3
- [P3] 1440-02, 1920-02 — About h1 — orphan "Paris." on its own line, wrapped beside the Om roundel — fix: balance text (`text-wrap: balance`) or narrow the roundel.
- [P3] 1440-05, 1920-05 — card numerals ०१/०२/०३ — about 12 px and read as "o?" — fix: raise to 18 px or use Latin 01–03.
- [P3] 1440-03 — Practice — big void below the Sūtra and a floating lotus roundel with no anchor — fix: pull the roundel beside the heading, add the practice frame.
- [P3] 1440-05-classes-b, 1920-05-classes-b — form — native select chevron/font mismatches the inputs; at 1920 the form's right edge (1550) misses the 1800 grid — fix: style the select, align the form to the container.

## Excellent, keep:
- The cover composition: Cormorant headline, vermilion italic "at a time.", Sūrya disc behind the sun photo, and a clear "Reserve a session" button, with the Sūtra signature below.
- The About page: diwali photo beside a first-person block with credential link and a two-column training list; the parchment grain, ruled margins and Om dividers feel like a manuscript.
- The Classes cards and compact form: three clean cards with a highlighted active one, a 450 px two-column form with pill choices and a consent line, all calm and uncluttered.

## eye: tv
# eye_17_tv: 2560 and 3840 screens (22 PNGs read)

**Verdict: NOT YET**

Order, first-person voice, no fees/EUR and no Instagram UI are fine. The 4K layout and the strip hold it back.

## Defects
- [P1] 3840-07-contact.png — email row — ".com" drops to line 2 — clamp the size or use nowrap so the address stays on one line.
- [P1] 2560-strip-01.png, 2560-strip-12.png, 3840-strip-12.png (and 3840-strip-01.png) — carousel track — at the ends only 2.5-3 cards show and about 40% of the width is empty, against the 4-5 card brief — show 4-5 cards at 2560 and above and clamp the end positions.
- [P2] 3840-05-classes.png, 3840-07-contact.png — forms — labels and consent text are about 15 CSS px at 4K, unreadable from a sofa — apply the brief's 1.25x form scale.
- [P2] 3840-01-top.png — Sūrya rays — they cross the headline at "ease." and "breaths" — clip the rays short of the text.
- [P2] 3840-05-classes-b.png, 3840-strip-01.png — header — the logo crest fills the 48 px header, and body text and "Twelve moments." glyphs sit against it — raise the header to about 72 px and the logo to about 40 px.
- [P2] 3840-02-about.png — diwali photo — about 415 px wide, with about 480 px of dead space beneath it — enlarge it or make it sticky.
- [P2] 2560-07-contact.png, 3840-07-contact.png — lobby photo — small, floating at the lower right, with a void above — align it with the heading and enlarge it.
- [P2] 2560-07-contact.png, 3840-07-contact.png — phone number — old-style numerals make "10" read as "IO" — use lining-nums.
- [P2] 2560-06-paris.png, 3840-06-paris.png — Eiffel photo — soft, milky and low-contrast (upscale), figure about 15% of the frame — crop tight, add contrast and light sharpening, or swap the source.
- [P2] 2560-04-twelve.png, 3840-04-twelve.png — strip entry — the sun disc is clipped by a hard rectangle, a seam shows in the left gutter, and captions hide under the control bar — feather the disc and move the bar below the captions.
- [P2] 2560-02-about.png — training list and Tapovan paragraph — about 17 px, small beside the lead — raise to 20 px or more.
- [P2] 2560-01-top.png, 3840-01-top.png — cover at 4K — photo about 27% of the width, CTA small, 16% empty margins each side — scale the hero up at 3000 px and above.
- [P2] all sections — paper — reads as flat tan with no leaf edges or fibre, and the icons are faint 60 px circles pushed to the right — strengthen the aged-edge vignette and the icon opacity.
- [P3] header (2560 and 3840) — logo — looks raster, with soft thin strokes — ship an SVG.
- [P3] 2560-02-about.png — diwali photo — green speck near her face — retouch it.
- [P3] 3840-02-about.png — headline — orphan "Paris." — balance the wrap.
- [P3] 2560-02-about.png — training heading — the arrow sits far from its text — place it inline.
- [P3] 2560-strip-06.png — cards — blank band of about 60 px between title and mantra — tighten it.
- [P3] 3840-05-classes.png — cards — the text measure fills only about 45% of the card — raise max-width.
- [P3] 2560-06-paris.png — Paris photo — saree hem touches the bottom edge — adjust the crop.

## Excellent, keep:
- Cover: the sun-lit portrait is crisp, the Cormorant headline with the vermilion italic is strong, "Reserve a session" is clear, and About follows straight away in first person.
- Strip cards (2560-strip-06, 3840-strip-06): sharp, no halos, no waxy skin, with Devanagari, IAST title, mantra and breath cue well set.
- Classes cards and kind-words quotes: tidy and readable, with no fees or EUR anywhere.

## critique: Sol
# Round 8 critique by openai/gpt-6.1-sol-pro

**Verdict: HOLD.** The supplied gates show solid functionality, not contractual compliance or “wow.” No PNGs were supplied for direct visual review; composition findings below are source-based. Latest operator addenda override stale HANDOFF facts.

1. **[P1] [site/index.html:#classes; site/js/i18n.js:classes copy; research/functional_v4.mjs]** Verified pricing is entirely missing, and tests incorrectly celebrate “no €” → Add €50/one-hour individual and online sessions, 5 hours €250, 10 hours €500, and in-home €25/hour **“after tax credit (crédit d’impôt)”**, in EN/FR. Keep small groups/workshops by arrangement. Replace the obsolete no-price assertions with exact pricing checks.

2. **[P1] [site/index.html:.consent; site/js/i18n.js:registerConsent, subscribeConsent]** All four displayed consent strings differ from the backend contract → Copy the EN/FR strings **verbatim** from each endpoint’s `CONSENT_TEXT` into HTML fallback and dictionaries. Keep `consent:true`; add exact-string assertions. Existing mocked submission passes do not verify informed-consent wording.

3. **[P1] [site/css/styles.css::root, “v5” overrides; site/index.html:.hero-frame, #paris]** The implementation changes the commissioned art direction: yellow manuscript paper, vermilion/gold ornament, lifestyle hero, and substituted Paris image. This risks decorative pastiche rather than the requested editorial confidence → Restore the specified paper/ink/ochre/indigo palette, remove fibres, binding-hole ornaments and inset shading; use `hero@800/1400/2000/2800` in the cover and `paris@800/1200` with “Champ-de-Mars, Paris.” Restore matching bilingual alts and hero-based OG artwork. Do not use AI-upscaled lifestyle assets as substitutes.

4. **[P1] [site/index.html:.twelve; site/css/styles.css:.portrait-art, .twelve--cover, .arc]** Straight sun rays and a filled disc replace twelve unequal arcs; stronger ornament overwhelms the quiet breath concept → Restore twelve curved arcs and three unfilled concentric circles, inactive ink `.14`, active ochre `.5`. Position the 90vmin ring behind-right, 70vmin on phones, visibly beside—not as a pedestal underneath—the frame.

5. **[P1] [site/index.html:section order; site/css/styles.css:.about-image]** A long biography interrupts the practice-to-signature narrative immediately after the cover; its sticky photo also violates “no pinned sections” → Restore `top → practice → twelve → classes → about → contact`; move testimonials into About, remove photo stickiness, and restore nav order. Keep About’s full EN reading content within 180 words.

6. **[P1] [site/js/main.js:EVENT_NAMES]** Frontend aliases contradict the supplied event contract; the gate reports a different backend allowlist → Inspect the retained `event.ts`, reconcile this discrepancy explicitly, then send the agreed exact names. Do not silently rename analytics or modify the retained backend merely to satisfy a stale document. Test all four events, not only registration.

7. **[P2] [site/css/styles.css:.card, .step-frame, .strip-wrap]** Neighbours remain full-size and are faded; edge gradients wash over photographs. Height caps can break the intended frame ratio → Use active scale `1`, neighbours `.96`, equal photo opacity, no gradient overlays. Couple frame width and height through 3:4 sizing; preserve full figures and caption space. This—not extra ornament—is the signature’s missing polish.

8. **[P2] [site/css/styles.css:responsive overrides]** The final ≥3200 rule regresses five cards to four and expands the container to 2600px. At 1024px, later overrides erase the editorial stagger → Restore five cards, 2200px maximum container, specified gutters, and deliberate tablet stagger. Consolidate conflicting media rules; review 390/1024/1440 plus every required orientation, cards 1/6/12, and unclipped Sanskrit captions.

9. **[P2] [site/css/styles.css:@media(max-width:400px); .glass-chip]** Language controls shrink to 40px; caption contrast depends on photography → Restore ≥44×44px touch targets. Measure actual composited text colours, including muted credits and chips, to ≥4.5:1. Keep chips in clear corners, never across a figure. Existing alt/focus hooks are good; verify visible focus in both languages.

10. **[P2] [site/js/main.js:initStrip; site/css/styles.css:.eyebrow]** Play advances immediately before the first four-second interval; pause logic excludes focused Play; breathing-dot CSS has no matching markup → Start advancement after 4000ms, define consistent hover/focus pause behaviour across controls, and add the eyebrow dots. Remove extra ray breathing. Preserve static reduced-motion rings and disabled autoplay.

11. **[P2] [site/js/i18n.js:lineageBody, now; site/index.html:.logo]** “I bring…into every class” invents a personal teaching commitment; “Open now” implies unverified immediate availability; “G1A” is unexplained → Use neutral training-to-teaching language, “Individual classes by request,” and “Jeevana” branding. Preserve verified certification, history and the two authorised testimonials.

12. **[P2] [site/js/main.js:trailing IIFE; site/css/styles.css; gate evidence]** Cascade patches obscure intent; main.js has two IIFEs; “144K total” does not establish transferred fold weight → Consolidate to one IIFE ≤12KB and one authoritative rule set. Preserve lazy loading/srcsets, correct image intrinsic ratios/sizes, and measure cold-load fold transfer ≤600KB. Keep `_headers` unchanged; rerun CSP and exact-contract tests. Restore the hidden designer mail link.

**Already excellent—must not be lost**

13. **[P3] [site/index.html:forms; main.js:submission]** In-place success/error handling, preserved inputs, honeypots and client validation → Retain.

14. **[P3] [site/js/main.js:initStrip]** Native snapping, keyboard/touch/drag support and synchronised arcs/progress → Retain.

15. **[P3] [site/index.html:.frame, .practice-gallery]** Photographs retain their environments, restrained shadows and separated typography—no dark plates or cut-outs → Preserve this foundation.

## critique: GLM 5.3
# Round 8 critique by z-ai/glm-5.3

## Review — picky pass, P1 first

1. **[P1] js/main.js `EVENT_NAMES`** — Beacon names were silently renamed: `register_open→register_start`, `whatsapp→wa_tap`, `instagram→ig_tap`, `subscribe→newsletter_open`. The brief and handoff are explicit: send the four allowlist names verbatim (`register_open`, `whatsapp`, `instagram`, `subscribe`). If `event.ts` keeps the v3 allowlist, three of your four beacons will 400 silently (`.catch(()=>{})` hides it). → Delete the `EVENT_NAMES` map; send `JSON.stringify({name})` with `el.dataset.event` unchanged. The functional gate only checked one name — widen it to all four.

2. **[P1] index.html cover + i18n.js `heroAlt`** — The hero is the `sun` key (an AI-upscaled 600×800 source run through realesrgan ×4/×2 — the manifest says so itself). The brief: hero = `_DAV5356.jpg`, portrait 4:5, seated, gentle smile, and the DOM contract asserts FR hero alt starts with **"Jeevana assise"**. Your FR alt ("Jeevana, les yeux fermés… en robe noire") describes a different photograph — the contract check would fail, and an upscaled 600px-wide image will look soft on any 4K screen. → Use the polished `hero@800/1400/2000/2800` set (which exists and is unused), 4:5, and restore the seated alt strings.

3. **[P1] Classes section / i18n `individualBody`, `timetable`** — Prices are missing entirely. The Superprof addendum supersedes "Price on request": Classes must carry **€50/h, packages 5 h €250 / 10 h €500, €25/h in-home *after the French tax credit (crédit d'impôt)***, €50/h online. Your own gate asserts "no fee or € anywhere" — that gate is now wrong and enforces the omission. → Add a small price block per format (individual / small group on request), the tax-credit line, and keep "timetable on request" as the slot wording. Update the gate.

4. **[P1] i18n.js `registerConsent` / `subscribeConsent`** — Consent strings are paraphrased, not verbatim. Register must read *"I agree that **Jeevana stores these details to answer my registration**…"*; subscribe *"I agree to receive **Jeevana's** newsletter…"*. The API stores `CONSENT_TEXT[lang]` verbatim in KV while the visitor ticked different words — that's a legal mismatch. → Paste the two CONSENT_TEXT blocks character-for-character (EN and FR) from the handoff.

5. **[P1] index.html section order** — DOM contract: ids in order `#top, #practice, #twelve, #classes, #about, #contact`. You ship `#about` *before* `#practice` (nav order matches markup, so the gates pass) and add an unlisted `#paris` section. → Move About after Classes; fold the Paris/testimonial content into About or Contact and drop the stray id (or rename it) so the contract holds and the narrative reads practice → breaths → classes → person → contact.

6. **[P2] css/styles.css `:root`** — Palette drifts from the brief: paper `#E8D6B3` (spec `#F3EEE4`), ink `#2B1E14` (`#2A2622`), plus invented `--verm #A63A22` and `--gold #B8862B` doing accent duty everywhere (arcs, mini rings, section hairlines, ornamental "holes"). The brief's Jeevana temperature is warm paper + one ochre + one cool indigo; you have three hot accents and the indigo has nearly vanished from the system. → Reset to the spec tokens; vermilion only as a whisper (folio numerals at most). Also `.twelve .arc` should be ink at .14 with the lit arc ochre at .5 — currently everything is gold at .55.

7. **[P2] index.html `#paris` figure** — Uses `saree-eiffel@2000` (upscaled) instead of the manifest's `paris` key — the genuine Chakrāsana/Eiffel shot, max 1200, which the brief explicitly wants as the secondary Paris image. → Swap to `paris@800/1200`, never upscale, restore chip "Champ-de-Mars, Paris".

8. **[P2] css `.card` (strip)** — Brief: centred card scales 1.0 vs .96 neighbours. You only dim to opacity .88. → Add `transform:scale(.96)` on `.card:not(.is-active)` (transform/opacity only, already transitioned), and make sure `prefers-reduced-motion` keeps `.card{transform:none}` as you do.

9. **[P3] index.html hero `sizes`** — `sizes` uses `34svh`, `34.5svh` etc. — non-standard in `sizes`; browsers drop the whole value and pick the last candidate. → Replace `svh` with `vh`/`vw` in every `sizes` attribute (strip cards too).

10. **[P3] styles.css `.twelve .rays`** — A second 9 s breathing animation on the ray group plus the 5.5 s centre breath plus 240 s orbit is three concurrent motions on the backdrop; the spec allows the 240 s rotation and one 5.5 s centre breath. → Drop `rays-breathe` (keep your reduced-motion override anyway).

11. **[P3] `.section::before/::after` ornaments** — Vermilion margin rules + the "binding holes" strip on every section reads as a second, competing motif (and the holes sit behind headings on tablets — check 1024 screenshots). → Keep the fibre texture, retire or halve the holes.

12. **[P3] JSON-LD / meta** — `jobTitle` is "Hatha Yoga teacher" (spec says "Yoga teacher"), and you add an `Organization` node with `areaServed`/`email` the brief didn't ask for. Harmless, but align jobTitle and trim the Organization to name/url/logo. `og:locale` toggles to `fr_FR` — good.

## Three things that are already excellent — do not lose them

- **The strip mechanics.** Keyboard, drag with snap-recovery, 4 s autoplay with hover/focus/visibility pausing, reduced-motion disabling with an honest label, `JV_strip` exposed — 56/56 functional passes. This is the "wow" and it's solid.
- **Performance discipline.** 144 K page weight, zero layout shift, lazy below the fold, eager+`fetchpriority` hero, self-hosted fonts with `unicode-range` splits. Keep exactly this budget.
- **The frame language.** Rounded frames, mist placeholders reserving ratio, glass chips, soft long shadow, backdrop living *behind and beside* the photo — no dark plates, no pasted cut-outs. The photographs feel placed. Preserve this treatment while fixing the palette and the hero image.
