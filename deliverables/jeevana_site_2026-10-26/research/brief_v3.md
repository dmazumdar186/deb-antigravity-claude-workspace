# Brief v3 — Jeevana, "Twelve breaths": a film-first site (2026-10-26, after the operator rejected v1/v2)

Operator's words: "the super-imposition of her images on the black/brown background is sophomorish; the transition is not
fluid; a 6th-grader would say 1996; I need something very fluid; use Kling, Seedance, GLM; fire the team; re-evaluate every
decision; would a senior animation-and-design UX/UI expert ever build this? Tom Ford and Anna Wintour are the approvers."
Jev routing on. Fresh team: this brief is the only context you get; v1/v2 code is NOT a reference — do not read it.

## 1. What the site is
A production site for Jeevana Gogula, yoga teacher in Paris (facts in `research/brief.md` §"Verified facts"; contact
+33 7 54 28 72 10; Instagram jeevana.gogula; email Jeevana.yogawellness@gmail.com; everything else `research/to_wire.md`).
Purpose: top-of-funnel marketing, class registration, voluntary newsletter (email, optional phone, consent). EN with FR.
Cultural line: traditional yoga (Yoga Sūtras 1.2 and 2.46, the twelve Sūrya Namaskāra mantras with plain glosses, from
`research/content_fixture.json`), never religious symbolism. Footer credit "Designed by Debanjan Mazumdar · ProdCraft"
→ https://prodcraft.fyi. Legal: privacy + mentions légales page, self-hosted fonts, Cloudflare Pages Functions for
register/subscribe/unsubscribe/export/event (KV id in `site/wrangler.toml`, keep), beacon token in `panel/00_fix_brief.md`.

## 2. The idea — a film you scrub, and a page that breathes
The cover is **one continuous film of Jeevana moving through the twelve positions of Sūrya Namaskāra**, generated with
Kling 3.0 (Higgsfield) from her real photographs as the first and last frame of each leg (`research/film/hero.json`
lists the keyframe timestamps; `hero.mp4` 3:4, `hero-m.mp4` 9:16, `poster.jpg`). It is scrubbed by scroll exactly as the
Evolution Exhibits cover is (teardown: `deliverables/gaia_redesign_2026-09-17/research/reference_demo_teardown.md` §2.3:
blob-fetched video, eased `currentTime`, 15/70/15 hold-leg-hold windows, text state crossfade at 50 % of a leg, per-step rail
fill). Before anyone scrolls, the film **plays itself** through the first two legs (muted, 1× speed), then holds; the first
scroll takes over from the current time (one variable drives film time, rail, copy). Nothing is a slideshow; nothing is
a cut-out on a dark plate; nothing is a box.

The page is paper (`#F3EEE4`) with ink type and one accent (`#C4731A`, wash/marks only; text ≥ 4.5:1 uses `#9A5A12`).
The film sits as a 3:4 window on the paper on desktop (its paper-cream background blends into the page edge-to-edge
with a 48 px feathered mask — the film must look like part of the page, not a video rectangle), full-bleed 9:16 on phones.
Type beside her, never over her. The **breath** is the motion language of the whole site: a GLM-written module
(`js/breath.js`, via `.claude/skills/site-redesign/scripts/gen_backdrop.py` with a breath-specific motif prompt: a single
hairline ring + fine particle haze that inhales (expands 4 %) and exhales (contracts) on a 5.5 s cycle, and follows scroll
progress on the cover; public facts only; ≤ 10 KB; reduced-motion = static) that lives behind the film on the cover and
reappears as a quiet mark in the chapters. The inhale/exhale label of the rail is synced to the same clock.

## 3. The twelve states (one per Sūrya Namaskāra position; the film's keyframes)
Rail (desktop right; phone bottom): position number, Devanagari + IAST name, breath (inhale / exhale / retain), the mantra
and its gloss, from the fixture. Copy states: S0 "Jeevana — Yoga in Paris" + "Twelve breaths." + Sūtra 1.2; S4 Sūtra 2.46;
S11 "The posture is steady and at ease." + CTAs (Register for a class / See the classes). Hold S11 to p = 1; the next
chapter enters only after p = 1. Height: 13 states → track = 14 × 100vh desktop, 10 × 100svh phones.

## 4. After the cover — three chapters, no deck tabs, no drum, ≤ 3 scrolls total
Each chapter is one viewport, pinned briefly (150 vh) with a film still (extracted from hero.mp4 at a keyframe, colour-graded
warm, full-bleed with the paper mask) on one side and the chapter on the other; chapters crossfade into each other as you
scroll (opacity + 2 % scale, 600 ms, eased), the breath mark exhales between them.
- **01 — The practice**: what a class is (breath sets the pace; sequence; stillness), beginners welcome, adaptations.
- **02 — Classes & registration**: the three offers as a hairline list (group · private · workshop; "Price on request"
  in ink, once), the timetable line ("The timetable opens soon") or rows from `schedule.json`, and the registration form
  (name, email, phone optional, class, level, message, consent; inline errors; success replaces the form; mailto fallback
  with the typed fields) — the form is the chapter, not a tab.
- **03 — Contact**: hairline list (email · Instagram @jeevana.gogula · +33 7 54 28 72 10 call or WhatsApp), the one
  Eiffel photograph (`_raw_assets/IMG-20260810-WA0005.jpg`, keeps its background, captioned Champ-de-Mars, warm grade),
  newsletter row, footer with the ProdCraft credit and the privacy link.
Newsletter dialog: opens once, after chapter 01 is reached and never while focus is in a form; email, optional phone,
consent, quiet "No thanks"; Esc, focus trap, restore.
Mobile: full-bleed film, copy at the top on a top scrim, rail reduced to "03 / 12 · name · breath", CTAs above the safe
area, chapters stacked (no pin), bottom bar Register + WhatsApp after the cover.

## 5. Engineering
Zero third-party JS (beacon excepted); one IIFE; every selector guarded; `html.has-js`; `window.error` degrades to the
poster; no `style=""`; CSP with self-hosted fonts; index+css+js ≤ 150 KB; film ≤ 6 MB desktop / 4 MB mobile (crf 23/25,
`faststart`; blob-fetched for seeking); `preload` poster; Save-Data/reduced-motion get the poster + static copy.
Assertions (`research/functional.mjs`, real DOM/video values, never loosened): film plays unscrolled (currentTime > 4 s
at 6 s); scroll takeover (currentTime tracks p within 0.4 s after settle at p = .25/.5/.75/1); state ↔ rail ↔ copy from one
variable at 13 samples; the film window's paper matches the page (sample 4 pixels each side of the mask: ΔE < 3); no text
box intersects the film's figure region (use the keyframe bboxes in `research/film/figure_boxes.json`, produced by
`film_produce.py --boxes` from the stitched keyframes); CTAs visible at p = 1 on all 19 viewports; no empty band > 25 %;
chapters ≤ 1 viewport; 0 console errors desktop / Pixel 7 / iPhone 13; sizes; fonts local; privacy page.
Screens: cover-s0-0s, cover-s0-6s (autoplay), cover-s3, cover-s7, cover-s11, cover-hold, chapter-01/02/03, dialog,
register-success, privacy, lang-fr-cover, page-full-static, mobile-cover/-s7/-hold/-chapters, + 19 viewports × s0/s7/hold.

## 6. Team (fresh contexts, briefed only with this file + the files it names)
- Film producer (brain runs `research/film_produce.py`; a reviewer reads frames per leg; retakes ≤ 2 legs).
- Motion director / builder (Opus, `omitClaudeMd`): builds the site from this brief; GLM for `breath.js`.
- Jury (Tom Ford / Anna Wintour + the four house leads) sits BEFORE the eye reviewers; both must pass; then deploy to
  https://jeevana-yoga.pages.dev/ from `site/` (Functions), replacing the rejected build immediately.
