# Eye review round 5 — four reviewers (Claude Sonnet), 124 screenshots, ten viewports. Fix every P1 and P2; P3 at your judgement.

## phones
NOT YET (close: portrait phones are strong; landscape strip and a few polish items hold it back)

Defects
1. [P1] 844-strip-12.png — last card ends mid-screen, right ~40% of the strip is empty beige; reads as unfinished/broken carousel — keep the last card snapped to end with `scroll-padding-inline-end` and trailing spacer sized so the final card aligns right, or snap-align:center.
2. [P2] 844-strip-01/06/12.png, 844-03-twelve-b.png — landscape strip: 72px sticky header + card (photo ~150px) + caption exceed 390px; photo and caption never visible together, heads cut under header — in `@media (orientation:landscape) and (max-height:480px)` shrink header to ~52px, cap card photo to `max-height:46vh`, tighten caption.
3. [P2] 320-04-classes.png, 390-04-classes-b.png, 844-strip-06.png, 320-strip-01.png — headline/photo text ghosts through the translucent sticky header ("Group", "Private" visible blurred) — raise header bg to opaque `rgba(243,238,228,.96)` and add `backdrop-filter:blur(12px)`.
4. [P2] 320-06-contact.png — email wraps to "…@gmail / .com", ugly orphan — `font-size:clamp(17px,5.4vw,24px)` plus `overflow-wrap:anywhere` only as fallback, or drop to 16px at <=340px.
5. [P2] 320-01-top.png, 390-01-top.png — hairline ring passes behind/under the "See the classes" button outline and beside the sutra line; button looks scratched — move ring to `z-index:-1` with `right:-40%; top:auto` below the CTA row or mask it with `mask-image` fade near buttons.
6. [P2] 320-01-top.png — header (logo, EN/FR, Register pill, then nav row) eats ~113px of 568 and nav items nearly touch — at <=340px reduce nav gap/size or hide the second row after first scroll.
7. [P2] 390-04-classes.png, 390-04-classes-b.png, 320-04-classes.png — "Register your interest" text links ~13px, ~28px tall hit area, identical three times — `min-height:44px; display:inline-flex; align-items:center`, ideally full-width ghost button.
8. [P2] 390-06-contact-b.png — newsletter: checkbox ~20px target, email field and phone field different widths (email shares row with Subscribe) — enlarge checkbox to 24px with 44px label row; stack Subscribe full-width under both fields on <=420px.
9. [P2] 844-strip-06.png — second card caption reads "Bana" for the Sanskrit "भुजङ्गासन" — likely a truncated name (Bhujaṅgāsana); fix the string.
10. [P3] 390-04-classes-b.png, 320-04-classes.png — three cards all say "Price on request" + same link; feels templated/filler — drop price line until real, or vary copy.
11. [P3] 320-05-about.png, 390-05-about.png — heading breaks "Rooted in / practice. / Here in Paris." three ragged lines — `text-wrap:balance` and shorter max-width, or a deliberate break after "practice."
12. [P3] 390-06-contact-b.png — footer "Designed by … ProdCraft" credit is cramped at the bottom and clipped in capture; reads as developer voice — soften/small caps, add bottom padding `env(safe-area-inset-bottom)`.
13. [P3] 390-02-practice-b.png, 844-strip-*.png — dark-green grass photos in white frames sit heavily on pale page; framing works but mood skews dark — slightly lift photo brightness or add warmer caption tone; keep frames.

Checks passed: type never over figure; chips sit on sky/background, not bodies; ring sits beside headings; no placeholder text; 390 strip controls (progress ring, 01/12, Play, arrows with disabled state) legible and touch-sized.

Excellent, keep:
- Framed photographs with white border and soft shadow (390-03-twelve, 390-01-top): they read as prints in frames, not cut-outs.
- Twelve-breaths card at 390/320: one dominant card, next card peeking, tidy Exhale/Sanskrit/mantra/translation caption stack and clear control row.
- Typography system: Cormorant headings, saffron italic accent, Devanagari in navy; ring beside headings gives a calm signature (390-02-practice, 844-06-contact rows are excellent).

## tablets
VERDICT: NOT YET

1. [P1] 768-strip-06.png, 1024-strip-06.png, 1366-strip-06.png — card 07 title reads "Bana" (Devanagari says Bhujangasana) — "That is not a pose name; it looks truncated" — fix the title string to "Bhujangasana" in the data/i18n source.
2. [P1] 768-strip-06.png (+1024, 1366) — card 06 reads "Asskara" with no Devanagari line, and the other cards have one — "Typo, and the card is out of rhythm" — correct to "Ashtanga Namaskara" with its Devanagari line; keep the 4-line caption structure.
3. [P2] 768-04-classes-b.png — Format select — "Open to any forma" is clipped — select{text-overflow:ellipsis;padding-right:2.5rem} or shorten the option to "Any format"; or stack Format/Experience to one column below 800px.
4. [P2] 768-strip-01/06/12.png — strip — the portrait view shows ~1.5 cards, not 2; the first card is pushed to x=230 so the left third is empty ring — set card width to ~46vw with scroll-padding-inline:var(--gutter) and align the first card to the gutter.
5. [P2] 1024-strip-01.png, 1366-strip-01.png — strip — landscape shows 2.3-2.5 cards, not 3, and the first card is offset from the heading column — card width calc((100% - 2*gap)/3), align the first card to the 55px gutter.
6. [P2] 768/1024/1366-strip-12.png — final slide — the 12/12 card leaves the right half empty, and the next arrow is dimmed with nothing after it — add end padding or snap the last card to the right, or loop the strip.
7. [P2] 768-strip-01.png, 1024-strip-01.png, 1366-strip-01.png — neighbouring cards — captions and text look blurred or faded (Hasta Uttanasana) and sit on a different baseline from the active card — drop filter:blur on text, opacity >=.85, fix a shared caption top via grid rows.
8. [P2] 768-01-top.png — hero — in portrait the photo is below the fold, the first screen has only text, and the ring sits in dead space right of the copy — reduce hero text block, set the photo margin-top:0 with max-height 45vh so the face shows above 1024px height; centre the ring behind the photo.
9. [P2] 768-02-practice.png, 768-02-practice-b.png, 1024-02-practice-b.png, 1366-02-practice-b.png — three-photo stagger — large empty holes under photos 1 and 2 (about 250px) — reduce the stagger offsets below 1100px or use align-items:start with a smaller translateY.
10. [P2] 768-05-about.png, 768-05-about-b.png — Eiffel photo — inset about 85px from the left edge while text and the "Champ-de-Mars" chip sit on different left edges — make the figure full-width on the 31px gutter, chip aligned to the photo edge.
11. [P3] 768-06-contact-b.png, 1024-06-contact-b.png, 1366-06-contact-b.png — newsletter block — the left label and heading sit mid-height, the form is higher; tops don't align — align-items:start on the grid.
12. [P3] 768-05-about.png, 1024-05-about.png, 1366-05-about.png — lineage line — "care." orphaned on its own line — max-width:none or text-wrap:balance.
13. [P3] 1024-01-top.png, 1366-01-top.png — hero ring — a hairline crosses the caption "A little space to simply be" — z-index below the caption, or clip the ring at the photo bottom.
14. [P3] 768-06-contact-b.png, 1024-06-contact-b.png — footer — "Designed by ... ProdCraft" is developer voice — move it into smaller muted type or drop it; restyle the arrow.
15. [P3] 1366-04-classes.png — class cards — empty space under "Register your interest" and the CTA is a small underlined link (about 14px) — min-height:44px tap area, make it a bordered button.

Excellent, keep:
- Framed, white-bordered photographs with soft shadows read as prints, never cut-outs; the hairline rings sit behind and beside the images and never behind type.
- Type pairing (Cormorant display + Inter, saffron italic accent) and the 01-05 section rhythm are calm and consistent across all three widths.
- The strip controls (progress ring, play, arrows with disabled state) are clear and legible, and the 1024/1366 hero is a confident composition.

## desktops
VERDICT: NOT YET

1. [P1] 1440-strip-01/06/12, 1920-strip-* — sticky header — faint ghost text (intro copy, "Swipe or drag" note) bleeds through the translucent header bar over the logo and nav; looks like a rendering bug — give header an opaque background (or backdrop-filter blur with >=0.96 alpha) and keep the page content z-index below it.
2. [P1] 1440-strip-01/06/12 — strip cards — photo tops are clipped under the header and the whole card is cut by the viewport; at 1440 only 2 full cards + slivers show, not 3-4, and the centred card is not centred (sits at x~520-920, left of centre) — scale card width to ~26vw at 1440 and centre-snap the active card (scroll-padding-inline:calc(50% - w/2)).
3. [P1] 1440-strip-12, 1920-strip-12 — end of strip — card 12 leaves a large empty right half (over-wide void), and the ring backdrop shows bare — add trailing spacer so last card centres, or loop; keep arrows at the same visual weight.
4. [P1] 1440-03-twelve, 1920-03-twelve — hero of section — card photos run off the bottom of the viewport and the intro leaves a large dead gap between right-aligned hint and cards; the hint text is orphaned far right, tiny and low-contrast — move hint under the strip controls, and tighten section top padding (padding-block 96px).
5. [P2] 1440-strip-*, 1920-strip-* — inactive captions — Sanskrit/English lines at ~40% opacity are barely legible (grey on beige, fails contrast); lift inactive opacity to 0.7 and keep the active card's caption bold.
6. [P2] 1920-strip-06 — left partial card — caption is chopped mid-word ("ancalanasana", "ave Namah") — mask edges with a linear-gradient fade (mask-image) on the strip so cut text dissolves.
7. [P2] 1440-strip-* , 1920-strip-* — controls — progress ring is empty/unreadable, arrows are near-invisible at the prev/next disabled state, and "Play the sequence" is small and floating — enlarge to 48px buttons, 1.5px solid border, label 14px.
8. [P2] 1440-01-top — cover — ring arcs hit the right edge and run behind the caption "A little space to simply be." and under the photo's bottom edge; the 2.46 Sanskrit quote sits close to the viewport bottom — clip ring with overflow hidden on the media wrapper and push it beyond the caption; add 24px bottom breathing.
9. [P2] 1920-01-top — cover — a 400px dead column between headline and photo; headline H1 is only ~600px wide at 1920 so the left feels light, and the photo is narrower than it could be — widen photo column (7fr/5fr) or bump H1 to clamp(72px, 6vw, 120px).
10. [P2] 1440-01-top — name chip "Jeevana Gogula · Paris" — grey translucent pill over the dark blue sky looks muddy — use solid cream (#f4efe6) with 0.9 alpha and 13px type.
11. [P2] 1440-02-practice, 1920-02-practice — intro — a long empty band on the right above body copy, ring ornament floats alone, and the three-photo collage starts below the fold with staggered offsets that read as accidental — align collage tops to a baseline or commit to an intentional 24/48/72px stagger.
12. [P2] 1920-02-practice — body paragraph — ~75 characters per line and wide left gutter vs headline — set max-width 60ch.
13. [P2] 1440-05-about, 1920-05-about — caption chip "Champ-de-Mars, Paris" is cut by the viewport and photo is flush under the sticky header with no top margin; lineage text "care." is a one-word orphan — add margin-top 32px, max-width 44ch with text-wrap:balance on the lineage text.
14. [P3] 1440-04-classes, 1920-04-classes — cards — tall empty space in each card and "Register your interest" links are tiny with a short underline stub that looks like a bug; the "Timetable opens soon" line reads as a placeholder — make link 15px with full-width underline, tighten card min-height, rephrase as a calm sentence.
15. [P3] 1440-04-classes-b, 1920-04-classes-b — form — field labels are tiny (12-13px) and fields have no visible focus/hover state shown; select text is larger than input text; left column has a big void below the link — unify to 16px, add hover border colour and focus ring, make the left column sticky.
16. [P3] 1440-06-contact, 1920-06-contact — headline ring and subscribe — email row links are large serif but arrows are small; newsletter email and phone fields stack unevenly beside the Subscribe pill (button aligned to the first field only) — put Subscribe below as full-width or align to a grid.
17. [P3] All — decorative ring in each section header is the same icon repeated and floats in space; reads as a sticker — vary or remove, or tie it to the heading baseline.

Excellent, keep:
- The cover portrait in its cream frame with soft shadow: it reads as a real photograph, with no plate or cut-out feel, and the italic ochre "at a time." gives an editorial voice.
- Cormorant display type with Inter body, the ochre accent and the warm cream palette: calm, consistent and premium throughout.
- The contact list with hairline rows and large serif details, and the Paris/Eiffel frame in the about section: confident and human.

## tv
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
