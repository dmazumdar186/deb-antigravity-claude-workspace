# Review round 2 (2026-10-26) — 3 eye reviewers + jury re-sit. Verdict: REVISE. Jury: "fix the pacing and bring it back".
The builder's `screens.json` reported 0 geometry issues while the PNGs show the same defects as round 1. So every item
below ships with a **numeric assertion in `research/functional.mjs`** (Playwright, real DOM boxes), and the fix is
done only when the assertion passes on every viewport in `research/screens.mjs`. No narrated fixes.

## 1. Cover end (UNFIXED round-1 C10, all reviewers, jury #1) — the blocking defect
Symptom: on every portrait viewport at p=1 the cream "01 — The practice" section covers the sutra line and the CTAs;
page-full shows ~2,500 px empty dark after the cover and ~1,000 px empty cream after the drum; on tv-portrait and
ipad-pro-portrait the Devanagari is cut in half.
Required geometry, asserted at p = 1.0 (bottom of the cover track) on all 19 viewports:
  a. `[data-cover] .cta` bottom ≤ viewport height − 24 px and fully visible (`elementFromPoint` on its centre is the CTA).
  b. fold/drum section top ≥ CTA bottom + 16 px (nothing covers the copy) — the drum enters AFTER p=1, i.e. the
     overlap is a negative margin on the **drum**, and the cover's `is-out` only fires once the drum top < 50 % vh.
  c. photo plate still shown at p=1 (opacity ≥ .95).
  d. At scroll = cover track end + 1 viewport, the drum heading is at full opacity and the three plates ≥ .95 opacity.
  e. Page-full capture (`fullPage:true`, after scrolling to the end once): no dark band taller than 60 % vh outside the
     pinned cover, no cream band taller than 60 % vh; deck panels render statically when `prefers-reduced-motion`
     or when `?static=1` (all panels visible, used for the page-full screenshot).
  f. Desktop total height ≤ 7,000, mobile ≤ 9,000 (already true; keep).

## 2. Photo crop (UNFIXED A1; jury "photographs carry the brand")
Assert per frame at cover-0/50/100 on every viewport: body box height (from `manifest.json` `body` bbox mapped
through `object-fit:cover` + `object-position` into the plate's on-screen rect) ≥ 60 % of the plate height; the
mat/feet edge within the plate (body bottom ≤ plate bottom − 2 %); head ≤ 15 % from the top of the plate on
landscape viewports. Specific: frame 12 (closing prayer, `_DAV5300`) currently shows head + torso in the bottom
40 %; frame 03/10 (`_DAV5307`) cuts the feet on laptops; frame 05/08 (down-dog) leaves 500 px of sky. Compute
`object-position` per frame per orientation from the manifest in JS (`focus` → `object-position: X% Y%`, with
`transform: scale()` when needed) — not by hand.

## 3. Sun + constellation artefacts (UNFIXED A4/C12; jury #2)
Assert: no element in the cover with a hard-edged circle (the `.sun`/backdrop disc) is painted without
`filter: blur(≥ 40px)` and opacity ≤ .35; backdrop canvas is `z-index` below the plate and masked out of the plate
and the copy column (`mask-image`); the constellation/hairline layer's painted bounds never intersect the
wordmark, sutra text or CTA boxes (sample canvas pixels at those boxes: alpha must be 0) at p = 0, .5, 1 and
during autoplay at 0 s and 4 s. Simplest compliant approach: constellation only in the left column at p < .25,
fading to 0 by p = .3; sun as a radial-gradient haze, no disc, no streak lines.

## 4. Header / chapter indicator / gaps
  a. "00" alone over the cover (ipad-portrait, ipad-landscape, 4K; jury #3): hide the chapter indicator while over the
     cover (`visibility:hidden`), show "01 — The practice" from the drum on. Assert: no visible text "00" at p ≤ 1.
  b. Gap between header and tab row (desktop ~50 px, mobile-deck ~130 px, mobile-foldout ~300 px): assert tab row
     top − header bottom ≤ 8 px on every deck screenshot and the drum's first element top − header bottom ≤ 24 px
     on mobile-foldout.
  c. Previous panel text cut under the header on deck-classes/contact/register-success: `scroll-margin-top` = header
     height + tab row; assert no text node's box intersects the header box after `show(id)`.
  d. mobile-cover: toggle must sit at the right edge (`inset-inline-end`), header brand lockup visible at p=0 only
     if the cover monogram is not; assert exactly one brand element visible (already asserted on desktop; extend to
     every viewport in the matrix).

## 5. Phones / portrait copy over the body (UNFIXED D13)
At cover-50 and cover-100 on all portrait viewports: assert the copy block box (eyebrow → CTAs) does not intersect
the body bbox (from §2); if it would, shift the frame's `object-position` Y up for portrait until clear, and the
scrim starts ≥ 40 px above the eyebrow (`linear-gradient(to top, rgba(15,12,10,.92) 0 55%, transparent 75%)`).
phone-landscape-0 and ipad-landscape-0: feet clipped → bottom-anchor those frames; scroll hint out of the plate.

## 6. 4K scaling (UNFIXED E20)
Assert at 3840×2160: header nav font-size ≥ 22 px, rail gloss ≥ 20 px, html font-size ≥ 24 px (the clamp is
capped at 16 px now); rail box fills ≥ 70 % of its column height (`align-content:space-between`).

## 7. Portrait tablets / TV
Rail card over the photo: background `rgba(15,12,10,.72)` + `backdrop-filter: blur(12px)`, gloss `max(.875rem,1.4vw)`;
tv-portrait-0: wordmark sits ≤ 16 svh under the mat edge (no 25 % dark grass void); assert empty-band rule.

## 8. Deck finish (jury #4, reviewer minors)
  a. Classes: "Price on request" once, on one line spanning the three offerings, in the warm accent (not navy).
  b. Contact: replace the 2×2 bordered tiles by a full-width hairline-rule list (name left, value + arrow right);
     merge Phone and WhatsApp into one row "+33 7 54 28 72 10 — call or WhatsApp"; the footer keeps email +
     Instagram only (number appears once on the page besides the mobile bar).
  c. Drum (foldout-mid): captions at full opacity once a card is ≥ 30 % visible; third card never below .9 opacity
     when in view; rotateY ≤ 35°.
  d. Cover right rail: remove the "A traditional sequence…" dek (eyebrow already says it); keep eyebrow, numeral,
     Devanagari + IAST name, breath pill, mantra + gloss.
  e. Mobile: toggle at desktop scale; position card without the grey slab (type on a top gradient); mobile bar
     appears only after the drum has passed and ~20 % shorter; SCROLL centred under the wordmark.
  f. Frame/counter agreement (lang-fr-cover showed position 03 with the prayer photo): the frame index and the rail
     index must come from one variable; assert `img[data-frame]` === rail `[data-pos]` at 12 sample progress values,
     in EN and FR.
  g. Gloss mapping: one table `GLOSS[1..12]` used by desktop rail, mobile counter, EN and FR; assert equality.

## Process
Fresh screens for everything (named + 19-viewport matrix × 0/50/100 + page-full with `?static=1` and without).
Report: functional N/N with the new assertion names listed, any assertion you could not make pass and why.
