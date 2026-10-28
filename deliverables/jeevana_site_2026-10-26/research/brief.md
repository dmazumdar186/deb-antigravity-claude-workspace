# Build brief — Jeevana Yoga (Paris), production site v1 — 2026-10-26

Absolute root: `/home/user/deb-antigravity-claude-workspace/deliverables/jeevana_site_2026-10-26/`
Site: `site/` · research: `research/` · screens: `screens/`.
Mechanics: `.claude/skills/site-redesign/reference/concept_recipe.md` and every rule in `reference/build_rules.md`
(including the "prodcraft.fyi v2" production block). Reference engineering, read narrowly by grep only:
`deliverables/prodcraft_site_2026-10-19/site/` (production shape: `_headers`, `_redirects`, 404, robots, sitemap,
manifest) and `deliverables/misb_redesign_2026-10-15/site_v3/` (scrub engine, deck). Do not copy prose.

## What this is
A **production** site (indexable, canonical/OG/sitemap/robots/`_headers`/404, no pitch page, no `noindex`) for
Jeevana Gogula, a Paris-based yoga teacher. Purpose: top-of-funnel marketing + class registrations + a voluntary
newsletter opt-in. Operator's verdict standard: "designed by a senior UX/UI designer with 30 years of experience;
could be featured among the top 50 most creative yoga/fitness instructor sites". Final approvers in the brief:
a design jury (Tom Ford / Anna Wintour taste: restraint, one idea per screen, luxury typographic rhythm, no clutter).

**Experience contract (operator, verbatim intent):** people open the URL and, without scrolling, see Jeevana
transitioning through the positions of Surya Namaskar in a fashionable way; then her other photos; then
everything they need **within three scrolls**. Dynamic, not static (the previous Jitendra site was static).

## Brand and language
- `lang="en"` with a French switch: every visible string exists in both languages in the DOM via
  `data-i18n` keys loaded from `js/i18n.js` (one object `{en:{…}, fr:{…}}`); `html[lang]` toggled, choice stored
  in `localStorage`, default from `navigator.language` (fr → fr). Title: "Jeevana — Yoga in Paris".
- Wordmark: **no text wordmark as a logo image**; instead a hand-drawn-feeling monogram "J" inside a
  sun-circle, inline SVG, drawn with strokes (think a brush seal, not a clip-art sun). Favicon = same SVG +
  ico/png 32/48/180 + manifest icons generated with sharp/ffmpeg (real files, not "in the spirit of").
- Palette (traditional, not gym, not temple): paper `#F3EEE4`, card `#FFFFFF`, ink `#1B1A17`, ink-2 `#403C35`,
  muted `#6F685C`, cover ink `#14110E` → `#2A211A` gradient, accent **saffron-ochre `#C4731A`** (contrast on paper
  ≥ 4.5 for text: use `#9A5A12` for text, `#C4731A` for marks only), secondary **indigo `#1F2A44`** for
  small caps; amber small caps `#B07A1C` allowed as in recipe. Display serif: Cormorant Garamond (one Google
  Fonts link, `display=swap`); sans: Inter; Devanagari: Noto Serif Devanagari (same link).
- Register: calm, precise, luxury-editorial. No emoji, no stock photos, no third-party JS, zero deps.
- **Cultural line (operator):** rooted in traditional yoga (Yoga Sūtras, Sanskrit mantras pertinent to yoga)
  but **never** religious symbolism or anything that reads as promoting Hinduism (no deity imagery, no Om as a
  logo, no temple motifs, no "blessings"). Mantras are presented as breath-and-sound tradition of the practice,
  each with a plain translation, framed as "what the tradition says" — never as belief claims.

## Verified facts (only these; everything else is "to wire")
- Name: Jeevana Gogula. Brand: **Jeevana** (spelled J-E-E-V-A-N-A). City: Paris.
- Email: Jeevana.yogawellness@gmail.com. Instagram: https://www.instagram.com/jeevana.gogula/
- Phone, WhatsApp, Facebook, studio address, prices, timetable, custom domain: **not yet supplied** →
  build the slots, label them in `research/to_wire.md`, never invent values. No reviews, no press, no invented
  credentials, no "500 hours" claims. About copy must stay generic-true: she teaches yoga in Paris; describe the
  practice, not her biography (biography = "to wire", one paragraph slot with a `data-i18n` key).
- Footer signature (verbatim, linked): "Designed by Debanjan Mazumdar · ProdCraft" → https://prodcraft.fyi
  (plus `mailto:debanjan@prodcraft.fyi`).

## Photos — REAL photos are in `_raw_assets/` (see `research/photos.md`); operator order: no caricature, no generic placeholder art
Create `research/ingest_photos.py` (python3, Pillow): `--src <folder> --out site/assets/img [--sequence name=file,…]`.
It lists images, writes `site/assets/img/manifest.json` `{frames:{"sn-01":{file,w,h},…}, photos:[…]}`, resizes to
webp ≤ 1600 px long edge (quality 82) plus `-m` ≤ 1000 px variants, and renames by the sequence map. Run it NOW with:
`--sequence sn-01=pranamasana-side.jpg,sn-02=hasta-uttanasana-side.jpg,portrait=pranamasana-front.jpg,photo-01=chakrasana-eiffel.jpg`.
Frames 03–12 are not yet supplied (the operator will paste more). Rule for a missing frame: **never draw a figure**;
the cover keeps the last real frame on screen with a slow 1.04→1.0 breathing scale and a soft crop shift, and the
rail/mantra text for that position changes as usual. When `manifest.json` gains `sn-NN`, the frame appears with
zero HTML edits. Show the real photos large: full-bleed on desktop (object-fit cover, focal point on the body,
keep her face and feet in frame at 16:9 — use `object-position` per frame from manifest `focus`), portrait on
phones. Keep the watch and surroundings as they are; no retouching beyond resize and a subtle warm grade via CSS
(`filter: saturate(.92) contrast(1.03)`), never a heavy overlay — the sky and skyline are part of the brand (Paris).
The Eiffel photo is the signature drum's first plate and the OG image.

## Cover (pinned, scrubbed `400svh` desktop / `250svh` mobile) — "Twelve breaths"
- At scroll 0, **before any scroll**, the sequence runs on its own: an autoplay of the 12 frames
  (cross-dissolve + slight scale, 900 ms each, 1 cycle, then hold on frame 12 breathing slowly), so the
  operator's "without scrolling" requirement is met. Once the user scrolls, scroll takes over the frame index
  (`floor(p*12)`), and the autoplay stops (no fight). Reduced motion: frame 1 static.
- Each frame carries, in the rail, the position's number (01–12), its Sanskrit name in Devanagari + IAST, the
  breath (inhale/exhale/retain) and the traditional **Surya Namaskar mantra** for that step:
  01 Om Mitrāya Namaḥ (to the friend of all) · 02 Om Ravaye Namaḥ (to the shining one) · 03 Om Sūryāya Namaḥ
  (to the one who induces activity) · 04 Om Bhānave Namaḥ (to the one who illumines) · 05 Om Khagāya Namaḥ
  (to the one who moves through the sky) · 06 Om Pūṣṇe Namaḥ (to the giver of strength) · 07 Om
  Hiraṇyagarbhāya Namaḥ (to the golden cosmic self) · 08 Om Marīcaye Namaḥ (to the rays of light) · 09 Om
  Ādityāya Namaḥ (to the son of Aditi) · 10 Om Savitre Namaḥ (to the stimulating power) · 11 Om Arkāya Namaḥ
  (to the one who is fit to be praised) · 12 Om Bhāskarāya Namaḥ (to the one who leads to enlightenment).
  Label the rail "Sūrya Namaskāra — the twelve breaths" with a one-line note "a traditional sequence, taught
  as breath and movement" (both languages).
- Cover text (3 beats, scrubbed): 01 "Jeevana" + "Yoga in Paris / Yoga à Paris" + monogram (brand at scroll 0 is
  mandatory) · 02 Yoga Sūtra 1.2 "योगश्चित्तवृत्तिनिरोधः — yogaś citta-vṛtti-nirodhaḥ — Yoga is the stilling of the
  movements of the mind." · 03 (held) Yoga Sūtra 2.46 "स्थिरसुखमासनम् — sthira-sukham āsanam — The posture is
  steady and at ease." + two CTAs "Register for a class" / "See the classes".
- Backdrop: generate with `python3 .claude/skills/site-redesign/scripts/gen_backdrop.py --brand "Jeevana"
  --palette "#F3EEE4,#C4731A" --motif "slow sunrise: horizon haze lifting, fine cream hairlines like breath,
  a single ochre disc rising over three stages (night → first light → full sun)" --out <abs>/site/js/backdrop.js
  --log <abs>/research/glm_log.md`; review (single global, no fetch/eval/console). Public facts only.
- Then `render_hero_video.mjs` → `assets/hero.*` + `hero.json`; mobile portrait variant. Kling slot in `hero.json`.
- Header logo hidden over the cover; cover shows monogram + "Jeevana". Scroll hint always present.

## 01 — Signature object (pinned `300svh`): "The practice" — a **card drum** of her other photos
Three rotating plates: photo-01 (Eiffel), portrait, and a text plate (Yoga Sūtra 1.2) until more photos arrive with captions: "Hatha", "Vinyasa", "Breath &
stillness" (generic, true descriptions of what a yoga class contains; no claims about her lineage). Overlaps the
cover (−160svh / −25svh). Mobile: horizontal snap-scroll, no 3D. Paper, grain, warm edge.

## 02–05 — Command deck (one panel visible, all in DOM, hash deep links) — this is "scroll three"
02 **About / À propos** — one paragraph slot (to wire) + three true cards: "Traditional roots" (Sūtras, breath,
   sequence), "For every body" (beginners welcome, adaptations), "In Paris" (studio & outdoor, address to wire).
03 **Classes / Cours** — a weekly timetable grid (7 columns), rows "to wire" rendered from `js/schedule.json`
   (empty array ships → shows "Timetable coming — register your interest"), class cards: Group class · Private
   session · Workshop; prices "on request".
04 **Register / S'inscrire** — the registration form: name, email, phone (optional), class choice (select from
   schedule.json or "any"), level, message, consent checkbox (required, GDPR wording FR/EN), honeypot field,
   submits to `/api/register` (Pages Function, below). Success state inline; failure shows a mailto fallback
   to Jeevana.yogawellness@gmail.com with a prefilled subject.
05 **Contact** — email (mailto), Instagram (real link), WhatsApp + phone + Facebook as `[data-wire]` buttons
   hidden until `js/contact.json` carries a value (ship empty values; must never render a dead link).
Each panel ≤ 900 px desktop, ≤ 1,830 px mobile. Header chapter indicator 00 → 01 → active panel.

## Newsletter pop-up (operator requirement) — `<dialog data-news>`
Opens once per visitor (localStorage key), after either 35 s on page or the deck becoming active, never on
the cover; one line "Keep in touch with Jeevana" + "Newsletters, events and workshops in Paris. Voluntary —
close this and nothing happens." Fields: email (required), phone (optional), consent checkbox (required),
honeypot. "No thanks" button is as visible as "Keep me posted". `Esc` closes; focus trapped; restored on close.
Posts to `/api/subscribe`. Also a small inline newsletter row in the footer (same endpoint).

## Backend — Cloudflare Pages Functions, same pattern as
`execution/personal_workflows/yoga_jitendra_site/functions/api/newsletter-subscribe.ts` (read it narrowly):
`site/functions/api/subscribe.ts`, `site/functions/api/register.ts` → validate (email regex, lengths,
honeypot empty, consent true), rate-limit per IP via KV (`rl:` keys, 5/10 min), store
`news:<sha256(email)>` / `reg:<ts>-<rand>` JSON in KV binding `JEEVANA_KV`, return JSON. `wrangler.toml` in
`site/` with `name = "jeevana-yoga"`, `pages_build_output_dir = "."`, KV binding with `id = "TO_WIRE"` (I will
create the namespace at deploy). `_headers`: CSP without inline styles (no `style=""` attributes; the backdrop
and video go through classes/JS), `X-Frame-Options`, `Referrer-Policy`. `/api/export` Basic-auth CSV export
(env `EXPORT_USER`/`EXPORT_PASS`, 401 when unset) so Jeevana can download subscribers/registrations.
Local test: `node research/functional.mjs` mocks `fetch('/api/…')` → 200 so the success state is exercised.

## Page-height targets
Desktop total ≤ 7,000 px (operator: "within three scrolls" = cover track, drum track, deck); mobile ≤ 9,000 px.

## Verify (mandatory before reporting)
1. Copy `.claude/skills/site-redesign/scripts/functional_template.mjs` → `research/functional.mjs`, set
   selectors, keep every assertion name, **add**: autoplay advances the frame index without scrolling (frame
   ≥ 3 after 3 s); scroll takes over; rail mantra text changes with frame; i18n switch flips `html[lang]`
   and ≥ 20 strings; newsletter dialog opens after deck activation, closes on Esc, never reopens after close;
   register form posts and shows success with mocked fetch; dead-link guard: zero `href="#"`/empty `tel:`
   links in DOM; photo swap: frames 01–02 render the real webp; a frame without a manifest entry holds the previous real image (no empty, no drawn figure).
   Run → `research/functional.json`, must be N/N.
2. `node .claude/skills/site-redesign/scripts/site_check.mjs --site <abs>/site --pages /` exit 0.
3. Serve with real `_headers` (see prodcraft `qa_live/serve_csp.mjs` if present; else write
   `research/serve_csp.mjs`), 0 console errors desktop + Pixel 7 + iPhone 13.
4. Screens per `concept_recipe.md` §8 into `screens/` plus `cover-autoplay-0s`, `cover-autoplay-4s`,
   `newsletter-dialog`, `deck-register-success`, `lang-fr-cover`, and the 18-viewport cover matrix at
   0/50/100 % (name files `<viewport>-cover-<p>.png`).
Budgets: index+css+js ≤ 150 KB (backdrop ≤ 12 KB separately), each SVG figure ≤ 3 KB.
Do not deploy, do not commit. Report ≤ 250 words: files + sizes, functional N/N, site_check summary, page
heights, console errors, GLM cost line, the to_wire list, not done.
