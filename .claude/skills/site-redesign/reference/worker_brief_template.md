# Worker brief template — prospectus renderer (fill every bracket; one worker, foreground, Opus)

Build the concept site at `<abs path>/site/` following
`.claude/skills/site-redesign/reference/concept_recipe.md` (mechanics) and `build_rules.md` (every
rule mandatory). Reference engineering, read narrowly by grep: `deliverables/misb_redesign_2026-10-15/site_v3/`.
Files: `index.html`, `for-<name>/index.html`, `css/styles.css`, `js/main.js`, `js/backdrop.js`
(generated), `assets/` (real logo `logo-<slug>.<ext>`, favicon.svg, `img/*.webp` ≤ 1600 px,
`hero.mp4|webm`, `hero-m.mp4|webm`, `hero.jpg`, `hero.json`).

## Brand and language
- `lang="<xx>"`, register <tone>. Title "<Brand> — <tagline> · Concept". `noindex`.
- Palette: paper #EEECE6, card #fff, ink <hex>, cover ink <brand dark hex>, one accent <brand hex>,
  amber small caps #B07A1C. Display serif <family>, sans <family>, self-hosted or one Fonts link.
- Logo file `<path>`; photos only from `<research/facts.md section>`. No stock, no emoji, no wordmark.

## Verified facts (use only these, verbatim; contradictions footnoted)
<bullets with exact wording, numbers, dates, source URL; placeholders labelled "to wire">

## Cover (pinned 400svh / 250svh, scrubbed)
Beats (3–5), each a verbatim fact + kicker: 01 <…> · 02 <…> · 03 <…> · 04 <…> (held to track end).
Photo plates on beats 02–04 (desktop): <files>. Backdrop motif: <place → journey → place>.
Run `python3 .claude/skills/site-redesign/scripts/gen_backdrop.py --brand "<Brand>" --palette
"<cream>,<accent>" --motif "<motif>" --out <abs>/site/js/backdrop.js --log <abs>/research/glm_log.md`;
hand-review the module (single global, no fetch/eval/console), raise alphas if faint.
Then serve the site and run `node .claude/skills/site-redesign/scripts/render_hero_video.mjs --site
<abs>/site --url http://localhost:8793/` → `assets/hero.*` + `hero.json ready:true`.

## 01 — Signature object (pinned 300svh)
<fold-out | card stack | drum>: <panel 1 content> | <panel 2 content, e.g. real albums → dialog
gallery> | <panel 3>. Paper/crease/grain if print metaphor. Overlaps the cover (−160svh / −25svh).
Mobile: horizontal snap-scroll, no 3D.

## 02–0N — Command deck (one panel visible, all in DOM)
02 <Chapter> — cards: <…> · 03 <…> · 04 <…> (counters `data-count`) · 05 <…> · 06 <…> · 07 <…>.
Each panel ≤ 900 px desktop, ≤ 1,830 px mobile; overflow behind `<details>`. Hash deep links,
back/forward, arrows, header indicator. 0N+1 = pitch teaser linking `for-<name>/`.

## for-<name>/ (pitch, ~700 words)
Cover "Prepared for / by / date". Today/Concept table 6 rows incl. measured heights from
`<abs>/research/live_metrics.json` (run `node .claude/skills/site-redesign/scripts/measure_live.mjs
<url> > <that file>` first) and the concept's own heights from `functional.json`. What does not
exist yet · next · signature "Debanjan, Founder, ProdCraft, debanjan@prodcraft.fyi".

## Verify (mandatory before reporting)
1. Copy `scripts/functional_template.mjs` → `<abs>/research/functional.mjs`, set the selector
   constants, keep every assertion name; run → `functional.json`, must be N/N.
2. `node .claude/skills/site-redesign/scripts/site_check.mjs --site <abs>/site --pages /,/for-<name>/`
   exit 0.
3. Screens per `concept_recipe.md` §8 into `<abs>/screens/` (after settle).
Do not deploy, do not commit. Report ≤ 200 words: files + sizes, functional N/N, site_check
summary, page heights desktop/mobile vs live, console errors, GLM cost line, not done.

## Reviewer rounds (brain spawns after the report; worker fixes)
Round 1 and round 2: reviewer Reads every PNG against §8 checklist → SHIP or numbered defects.
Fix all, re-run 1–3, re-screenshot. Ship only on SHIP.
