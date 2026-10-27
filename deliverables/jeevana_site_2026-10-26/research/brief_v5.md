# Brief v5 — Jeevana (2026-10-27, operator review of the v4 preview)

Operator: "the layout looks fine, but…" — 13 changes. The v4 layout, gates, DOM contract (`research/sol_handoff.md`), functions,
privacy page and fonts stay. Never mention any other teacher on the site. Footer credit stays "Designed by Debanjan Mazumdar · ProdCraft".

## Photos (sources in `_raw_assets/v5/`, gitignored; Instagram screenshots, ~640 px wide)
| key | file | use |
|---|---|---|
| `sun` | sun.png — eyes closed, face in the sun, black dress, grey wall | **cover / hero photo** (replaces the seated portrait) |
| `diwali` | diwali.webp — sitting on the floor in a blue saree, lighting a diya beside a rangoli | **About me** photo ("her sitting") |
| `saree-eiffel` | saree-eiffel.png — red saree in front of the Eiffel Tower | Paris section (replaces the back-bend at the Eiffel Tower, which is removed from the site) |
| `lobby` | lobby.webp — green and yellow lehenga, orchids, hotel lobby | a closing spot (Contact / "Namaste" block) |
| keep | sn-01…12, practice-01…03 | the twelve-breaths strip and practice frames stay |
Every image must be clean: **no Instagram UI** (the `‹` arrow on sun's left edge, the carousel dots at sun's bottom centre, the avatar
circle at saree-eiffel's bottom-left and the partial circle on its right edge, the `›` arrow on diwali's right edge). Crop first;
inpaint only if cropping would cut her. Then the best available upscale (target ≥ 1600 px on the long edge for `sun`, ≥ 1400 for
the others), gentle denoise, no plastic skin, no change to her face. Grade all to the new paper palette (warm, soft, not orange).
The operator will be asked for originals; the site must still look clean with these.

## Brand (from `_raw_assets/v5/logo-concepts.jpg`, **Concept 3**: brush-stroke figure arching back, crescent moon, "JEEVANA YOGA")
Rebuild it as clean vector art (SVG): the brush figure + crescent moon as the **mark**; "JEEVANA YOGA" set in Cormorant as the
**wordmark**. Omit the "G1A" letters (they read as a generator artefact); keep the lockup so they can be restored if the operator
asks. Outputs in `site/assets/brand/`: `logo.svg` (mark + wordmark, horizontal), `logo-stacked.svg`, `mark.svg`, `favicon.svg`,
`favicon-32.png`, `favicon-16.png`, `apple-touch-icon.png` (180, paper background), `icon-512.png`, `og.jpg` (1200×630: `sun`
photo + logo on paper). Use them in the header, footer, `<link rel=icon>`, apple-touch-icon, OG/Twitter tags, JSON-LD `logo`.

## Voice
**First person throughout** ("I teach…", "I trained…", FR "J'enseigne…"), from her own Superprof text. No third-person "Jeevana is…"
anywhere except the page title, alt text and JSON-LD.

## Order (the visitor finds what she came for at once; scrolling tells the story)
1. **Cover**: `sun` photo; headline + one line; primary button **"Reserve a session"** (FR "Réserver une séance") → smooth-scrolls to
   the registration form (`#registration`), focuses the first field; secondary "Get to know me" → `#about`.
2. **About me** (immediately next): `diwali` photo; who I am, how I teach (first person), credential line, what my training covered
   (the 8 items), the Tapovan school line, where I have taught. Her skills are here, high up, not at the bottom.
3. Practice — what a session is like (session shape, aims, levels, languages, formats: at mine Paris 19e, at yours within 10 km,
   online; individual and small group).
4. Twelve breaths — the Sūrya Namaskāra strip (must work: see Carousel).
5. Classes + registration form (compact).
6. Paris + kind words: `saree-eiffel` photo, the two quotes (Egle, Thomas, "via Superprof").
7. Contact (email, WhatsApp, Instagram, Superprof) with `lobby` photo; newsletter row; footer.

## Remove
- **All fees**: no prices, packages, tax-credit line or "€" anywhere on the site (HTML, i18n, JSON-LD offers). Formats stay.
- The back-bend at the Eiffel Tower photo (`paris`) and the seated portrait `hero` as cover.

## Look: an ancient manuscript, calm and Vedic
- Paper: not Jitendra's cream. A **palm-leaf / bhojpatra manuscript** feel: warm parchment `#EAD9B8`–`#E4CFA6` with a very fine
  fibre/grain (SVG feTurbulence or a tiny tiled WebP ≤ 30 KB, opacity ≤ .08), faint darker edges per section like aged leaf, thin
  ruled margin lines in faded vermilion. Ink: lamp-black brown `#2B1E14`. Accents: **sindoor vermilion** `#A63A22` (marks, rules,
  small labels; text uses a ≥ 4.5:1 shade), **turmeric gold** `#B8862B` (hairlines, the sun), **indigo** `#2F3A5C` kept for Sanskrit.
  Check every text/background pair ≥ 4.5:1.
- **Iconography (yogic, calming, hairline, low opacity, never under body text)**: ॐ (Om) as a small section mark, a lotus line
  drawing, the Sūrya disc with rays (cover, behind-beside the photo, replacing the plain ring), a simple yantra/mandala line figure,
  a diya flame, palm-leaf string-hole motif (two small circles like a manuscript's binding holes) on section edges, Devanagari
  section numbers (१ २ ३ …). No deities, no swastika, nothing that reads as a temple ad. Draft the SVG motifs with **GLM 5.3**
  (`z-ai/glm-5.3` via OpenRouter, public brief only, ≤ $0.05 total), then hand-clean them.
- Motion stays restrained: the sun's rays breathe slowly; reveals as before; reduced motion honoured.

## Carousel (broken on the live preview — fix and prove)
Probe on https://v4.jeevana-yoga.pages.dev: desktop 1440, the next arrow sets the counter to 02 but `scrollLeft` stays 0 (cards never
move); iPhone 13 touch swipe does not move the strip either. Fix: the scroll container must actually scroll (check overflow,
widths, `scroll-snap`, `touch-action: pan-x pan-y` / no `preventDefault` on touch, no transform fighting `scrollLeft`). Arrows,
keyboard, mouse drag, touch swipe and autoplay must all visibly move the cards on desktop, tablet and phone. Add functional checks
that assert `scrollLeft` changes (not only the counter) and a touch-swipe check via CDP `Input.dispatchTouchEvent` on an
iPhone 13 context.

## Form
Too big. Compact it: inputs 44 px tall (touch minimum) with 16 px text, labels 13–14 px, two columns for name/email and
phone/format on ≥ 768 px, message 3 rows, consent text small, the whole form ≤ 520 px tall on desktop and ≤ 760 px on a phone.
No 4K over-scaling of the form beyond 1.25×. Also find and fix the 400 response seen on iPhone page load.

## Models
Use GLM 5.3 for the motif drafts and a critique round; Sol (`openai/gpt-6.1-sol-pro`) for one critique round; Fable via OpenRouter
only if credit allows (balance was $0.83 on 2026-10-27; the operator will top up). Implementation and fixes: Claude Opus 5.5
sub-agents (subscription). Screenshot review: Claude Sonnet 5.5.
