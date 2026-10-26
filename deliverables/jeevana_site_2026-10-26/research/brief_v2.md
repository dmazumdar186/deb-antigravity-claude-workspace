# Brief v2 — Jeevana site, redesigned cover "Twelve breaths, drawn then real" (2026-10-26)

Operator verdict on v1 (live at https://jeevana-yoga.pages.dev/): "the photos are kept on top, switching, like on a black
table; not what I wanted. Merge her into the layout; bring Jeevana out of her background; the photo quality looks very
low; completely change. Play with a storyboard concept like https://evolution-exhibits-v4.pages.dev/ (a scroll-scrubbed
film with keyframes: cardboard → packed → truck → built → show). Could she be a 3-D pencil sketch?" Operator decision:
newsletter pop-up keeps an optional phone field.

Everything in `brief.md` still applies except the cover and the photo treatment; `review_round2.md` §4, §6, §7, §8 and
all of `panel/00_fix_brief.md` (ops, legal, measurement, lenses 2/9 items) are part of this build. Mechanics of the
scrub engine: `.claude/skills/site-redesign/reference/concept_recipe.md` §1 and the teardown of the Evolution cover in
`deliverables/gaia_redesign_2026-09-17/research/reference_demo_teardown.md` §2.3 (read it: track height = (states+1)·100vh,
eased scrub, 15/70/15 hold-leg-hold windows, state crossfade at 50 % of a leg, per-step rail fill).

## Assets (all real, all hers)
- `_raw_assets/cutouts_v2/<key>.png` — RGBA cut-outs of Jeevana (background removed; person-only mask), 2400 px tall
  source; `cutouts.json` has `ground` (feet/mat contact row as a fraction of the crop height). Keys sn-01…sn-12
  (Sūrya Namaskāra), portrait, photo-01…06, alt-09, alt-09b. If a key is graded unusable in `research/cutout_review.md`
  use the listed alternate.
- `_raw_assets/pencil/<key>.png` — graphite drawings of the same cut-outs (RGBA, tone in alpha) by `research/pencil_render.py`
  (a worker is finishing them; if not there yet, build with cut-outs and wire the pencil layer so dropping the files in
  needs no HTML edit).
- Ingest: extend `research/ingest_photos.py` with `--cutouts DIR --pencil DIR` → `site/assets/fig/<key>@{2400,1600,1000}.webp`
  (lossless-ish: webp quality 92, `method 6`, alpha kept) and `site/assets/fig/<key>-pencil@{…}.webp`; `manifest.json` gains
  `fig:{key:{w,h,ground,srcset}}`. **Quality rule:** the figure is never upscaled; the browser gets ≥ 1.5× the rendered
  CSS height via `srcset` + `sizes` (2400 for ≥ 1200 px tall renders at 2×). No `filter`, no heavy compression.

## The cover (pinned track = 13 states → `height: calc(14 * 100vh)` desktop, 10·100svh phones; sticky stage 100svh)
Paper stage `#F3EEE4` with a faint procedural paper grain (SVG feTurbulence ≤ .05) — **no dark cover, no plate, no box**.
Jeevana is a cut-out figure standing ON the page: feet on a ground line at 86 % of the stage height (desktop) / 80 %
(phones), figure height 72 % of the stage (desktop, landscape poses scale by width to ≤ 56 % of stage width), a soft
contact shadow (blurred ellipse, 18 % ink) under the feet/hands, and a very faint warm "sun" radial gradient behind her
upper body (ochre `#C4731A` at 10 % → transparent, blur, no disc, no lines). Type lives beside her, never over her
(assert: no text box intersects the figure's alpha bbox at any state on any viewport).

States (scrub; each state = one Sūrya Namaskāra position; the rail shows number, Devanagari + IAST, breath, mantra + gloss):
- **S0 — the drawing draws itself** (also runs on its own at load, before any scroll, ~3.5 s): the graphite sn-01 appears
  as a hand drawing: a single simplified outer-contour path (`potrace` of the alpha, ≤ 6 KB, `stroke-dasharray` reveal over
  2.2 s) then the graphite tone fades in (opacity 0→1 over 1.2 s), then the rail's "01" lights. Kicker: "Jeevana — Yoga in
  Paris"; headline (serif, large): "Twelve breaths." ; sub: Yoga Sūtra 1.2 (Devanagari, IAST, English/French).
- **S1–S8 — the drawing moves** (positions 02–09): at each leg the graphite figure of the next position crossfades in
  while the previous one crossfades out **with a 60 ms ink-bleed**: the incoming figure starts 2 % smaller and 1 % lower
  and settles (both figures share the same ground line so she never "jumps"; horizontal centring per figure on its bbox
  centre). Position labels in the rail fill per leg. Headline text switches only at S4 (Sūtra 2.46).
- **S9–S11 — the drawing takes colour** (positions 10–12): the photo cut-out of the same position sits under the graphite;
  a soft wipe (CSS `mask-image: linear-gradient` driven by `--reveal`, from the feet upward) reveals the photograph from
  the ground up across the three legs; by S11 (position 12, Praṇāmāsana profile) she is fully the photograph, in full
  resolution. Beat copy: "The posture is steady and at ease." + CTAs "Register for a class" / "See the classes".
- **S12 — hold**: last state held to p = 1 with CTAs; the next section enters only after p = 1 (negative margin on the next
  section, cover `is-out` when its top < 50 % vh) — the round-2 §1 assertions a–f apply verbatim.
Autoplay before scroll: after S0, the figure advances through S1→S3 by itself (2.6 s per leg, breathing pace) and holds;
scroll takes over from the current state (no fight; one `state` variable drives figure, rail and copy). Reduced motion:
S11 (the photograph) static with all copy. No-JS: same.

Phones (< 800): the figure is 60 % of the stage height, ground line at 78 %; copy block at the top (eyebrow, headline,
sūtra) with the rail reduced to "03 / 12 · Pādahastāsana · exhale" + the mantra line under the figure; CTAs at the bottom
above the safe area; the scroll hint centred; **no text over the figure** (assert).
Wide (≥ 2200): rem scaling (`html{font-size:clamp(16px,.833vw,32px)}`), figure height stays 72 % of the stage.

Kling slot (`assets/film/hero.json ready:false` for now): when `ready:true`, `hero.mp4` (3:4, 12 keyframes at 5 s legs) is
scrubbed exactly like the Evolution film (blob-fetched, eased `currentTime`) instead of the figure crossfades; the rail,
copy and reveal logic stay the same. Build the branch now; it ships dormant.

Header over the cover: monogram + "Jeevana" top-left (the only brand element), language toggle top-right, no chapter
number. Below the cover: "01 — The practice" drum (cut-out figures photo-03 seated, photo-05 cobra, photo-06 child's pose,
on paper with contact shadows — not photos in boxes), then the deck per `review_round2.md` §8, About with the `portrait`
cut-out at full height beside the text, Classes/Register/Contact as already decided, newsletter dialog with email,
optional phone, consent, quiet "No thanks".

## Verify (all previous assertions + new)
- figure bbox height / stage height ≥ .70 desktop, ≥ .58 phones at every state; feet row within 1 % of the ground line at
  every state (compute from `manifest.fig.ground`); no text box intersects the figure bbox; S0 contour animation completes
  within 4 s with no scroll; autoplay reaches S3 within 12 s; scroll takeover; reveal mask at 0 for S ≤ 8, 1 at S11; the
  photograph at S11 is the ≥ 1600 variant on a 1440×900 2× screen (check `currentSrc`); page-full with `?static=1` shows
  S11 + every section at full opacity; 0 console errors desktop / Pixel 7 / iPhone 13; index+css+js ≤ 150 KB; fonts
  self-hosted (no external request except the Cloudflare beacon).
- Screens: cover-s0-0s, cover-s0-3s, cover-s2, cover-s5, cover-s9, cover-s11, cover-hold, plus the 19-viewport matrix at
  s0/s5/s11/hold, and the named deck/dialog/mobile set.
