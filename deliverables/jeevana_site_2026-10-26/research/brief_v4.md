# Brief v4 — Jeevana, "the Jitendra way, done once more and better" (2026-10-27)

Operator, 2026-10-27: "continue Jeevana's website; take inspiration from Yoga avec Jitendra, don't copy, just inspiration;
use her photos but polish them; don't lay them like a photo laid down on a black table cloth; make me go wow — a senior
UX/UI designer from Higgsfield will look at it." End-of-day verdict 2026-10-26: v1/v2/v3 rejected; do not reuse the v3
film cover or the prospectus skeleton. This brief is the only context. Do not read `_rejected_v2/` or v3 `site/index.html`
for design; v3 `site/functions/`, `site/wrangler.toml`, `site/privacy/`, `site/assets/fonts/`, `site/_headers`,
`site/_redirects`, `site/404.html` are kept as-is (backend contract, legal, fonts).

## 1. What was done right once (Jitendra, https://yoga-jitendra.pages.dev, source `execution/personal_workflows/yoga_jitendra_site/src/`)
Read `components/Hero.astro`, `HeroBackdrop.astro`, `About.astro`, `styles/global.css` once, then close them. What works there:
- Warm paper (`--cream #F4EDE1`), ink `#2E2A26`, one warm accent (terracotta) + one cool (sage), serif display + Inter.
- Photos are **photographs**: kept in their own environment, in a rounded `.frame` with a soft long shadow, a quiet
  hover lift, a glass caption chip in the corner. Never a cut-out on a plate.
- A rendered backdrop that lives **behind and beside** the photo, not under it: a hairline SVG mandala, slow rotation,
  breathing centre, 12 petals. Low opacity. It makes the paper feel alive and makes the photo look placed, not pasted.
- Motion vocabulary: fade-up reveals (`[data-reveal]` + IntersectionObserver), word-by-word headline, a breathing dot
  in every eyebrow, reduced-motion respected.
Inspiration, not copy: Jeevana gets her own backdrop (below), her own palette temperature, her own sections.

## 2. Jeevana's version
**Palette.** Paper `#F3EEE4`; ink `#2A2622`; ink-soft `#4A433C`; accent ochre `#C4731A` (text ≥ 4.5:1 → `#9A5A12`);
second accent indigo `#2F3A5C` (cool, for the Sanskrit and the rail); mist `#E7DFD0`. Fonts already in `site/assets/fonts/`:
Cormorant Garamond (400/500/600 + italic) for display, Inter 400/500 for UI. Self-hosted only; CSP in `_headers` stays.

**Backdrop ("twelve breaths").** One SVG, ≤ 6 KB, hairline: a ring of 12 arcs (one per Sūrya Namaskāra position),
each arc a slightly different length, around a centre of 3 concentric circles. Rotates one full turn in 240 s; the
centre scales 1.00→1.04→1.00 on a 5.5 s breath; the arc for the "current" position (set by the sequence strip, default 1)
is ochre at .5, the others ink at .14. On the cover it sits right of centre, behind the hero frame, 90 vmin, clipped by
the section. It returns small (160 px) beside each section heading as a scroll-filled ring (stroke-dashoffset from
IntersectionObserver ratio). Reduced motion: static, filled.

**Photos (`_raw_assets/`, 3240×5760 field set + two 1200×1600 Eiffel shots).** Use the best few, polished:
- `research/polish_photos.py` (write it; PIL + numpy, no network): for each chosen file — auto white balance toward
  warm (target grey ≈ (242,236,226) on the paper-coloured highlights, mild), lift shadows +6 %, S-curve contrast +8 %,
  saturation +6 % on skin tones only is not possible — keep global +4 %, unsharp mask (radius 1.2, 60 %, threshold 3) after
  resize, remove sensor dust if obvious, crop per spec below, export WebP q82 at widths 800/1400/2000 (+ `@2x` for the
  hero) into `site/assets/photos/<key>@<w>.webp` and a 24 px blurred LQIP as inline base64 in HTML. Write `manifest.json`.
- Crops (keys): `hero` = `_DAV5356.jpg` portrait 4:5, eyes level at 38 % height, (seated, gentle smile);
  `practice-01` = `_DAV5340.jpg` cobra 3:2 wide; `practice-02` = `_DAV5325.jpg` child's pose from above, 1:1;
  `practice-03` = `_DAV5352.jpg` seated meditation 4:5; `paris` = `IMG-20260810-WA0005.jpg` Chakrāsana + Eiffel 3:4
  (small source: max width 1200, never upscale, use as a secondary, not the hero);
  the twelve steps `sn-01..sn-12` per the map in `research/photos.md` (repeats allowed: 05/08, 03/10, 02/11), 3:4,
  figure centred with 8 % margin, same horizon line across all twelve (pick the horizon y once, from `_DAV5297`).
  Grade all twelve identically so the strip reads as one session.
- Alt text in EN and FR, descriptive and plain. OG image = `hero@1400` rendered 1200×630 with paper margin.

**Layout (one page + privacy page; EN default, FR toggle persisted in localStorage, `data-i18n` keys in `js/i18n.js`).**
1. **Top bar**: wordmark "Jeevana" (Cormorant 500), links Practice · Twelve breaths · Classes · Contact, EN/FR, a
   small ochre "Register" pill. Transparent on the cover, paper with hairline after 80 px.
2. **Cover**: 12-col grid; copy 7 cols: eyebrow "Yoga in Paris" with breathing dot, H1 word-reveal "Steady. At ease.
   Twelve breaths at a time." (FR: "Stable. À l'aise. Douze souffles à la fois."), sub from Sūtra 2.46 gloss, CTAs
   "Register for a class" (pill) + "See the classes" (ghost). Photo 5 cols: `hero` in `.frame` 4:5, 1.5 s slow
   Ken Burns (scale 1.04→1.00) on load, glass chip "Jeevana Gogula · Paris". Backdrop ring behind-right. Min height
   100svh desktop, natural on phones (photo under copy, full width, ring behind the photo at 70 vmin).
3. **Practice**: Sūtra 1.2 (Devanagari small indigo, IAST, EN/FR line) as a pull-quote; three frames in an editorial
   stagger (wide / square / tall, offsets 0 / 48 px / 96 px, parallax ±12 px on scroll), 90-word generic-true paragraph
   (she teaches yoga in Paris; the practice, not a biography; no credentials, no claims).
4. **Twelve breaths** (the signature): horizontal scroll-snap strip of twelve 3:4 frames (`sn-01..12`), each with the
   number, Devanagari + IAST, breath word, mantra + gloss from `research/content_fixture.json`. Arrow keys and drag;
   the centred card drives the backdrop's lit arc and a 1–12 progress ring; the card scales 1.0 vs .96 neighbours;
   on phones one card per viewport with peek. A small "play" link auto-advances every 4 s (pauses on hover, honours
   reduced motion). This is where the wow lives: it must feel like one breath moving through twelve photographs.
5. **Classes & registration**: three formats as cards (Group · Private · Workshop) with "Price on request" and
   "Timetable opens soon — register your interest"; inline form POST `/api/register` (read `site/functions/api/register.ts`
   for the exact fields and consent text; keep them) with a success state in place, no page reload. Honeypot kept.
6. **About + Paris**: `paris` frame (3:4) + 60-word generic-true text; chip "Champ-de-Mars, Paris".
7. **Contact**: email Jeevana.yogawellness@gmail.com (mailto), WhatsApp `https://wa.me/33754287210` (+33 7 54 28 72 10),
   Instagram https://www.instagram.com/jeevana.gogula/ ; newsletter row POST `/api/subscribe` (fields per `subscribe.ts`,
   consent checkbox verbatim); no popup, no dialog.
8. **Footer**: "Designed by Debanjan Mazumdar · ProdCraft" → https://prodcraft.fyi (+ mailto:debanjan@prodcraft.fyi),
   Privacy & mentions légales → `/privacy/`, © year.
JSON-LD Person + LocalBusiness-free (no address → `Person` with `jobTitle` "Yoga teacher", `url`, `sameAs` Instagram).
Cloudflare beacon token from `panel/00_fix_brief.md` (already in the old `index.html` head — copy only that tag).
`/api/event` beacon calls on CTA clicks as in v3 (`register_open`, `whatsapp`, `instagram`, `subscribe`), allowlist in `event.ts`.

**Motion rules.** Every reveal ≤ 900 ms ease-out, max 14 px travel; no element moves on its own except the backdrop,
the breathing dot, the Ken Burns and the strip autoplay; all honour `prefers-reduced-motion`. No scroll hijack, no
pinned sections, no cut-outs, no dark plates, no gradients behind photos, no drop shadow stronger than Jitendra's.
60 fps: transforms/opacity only, `will-change` on the ring and strip, images `loading="lazy"` below the fold, hero eager.

**Build.** Static: `site/index.html`, `site/css/styles.css`, `site/js/main.js` (one IIFE, ≤ 12 KB), `site/js/i18n.js`,
`site/privacy/` kept. No framework, no CDN, no inline scripts beyond JSON-LD (CSP). Delete old `site/assets/film/`,
`site/js/breath.js`, old stills. Page weight above the fold ≤ 600 KB.

**Gates (all must pass before a preview is shown).**
- `node .claude/skills/site-redesign/scripts/site_check.mjs --site site --pages /,/privacy/ --allow-hosts static.cloudflareinsights.com,cloudflareinsights.com`
- `node research/serve_csp.mjs site 8794 &` then a new `research/functional_v4.mjs` (Playwright): i18n toggle persists;
  strip arrows/keys/snap/autoplay; backdrop arc follows the strip; register + subscribe submit → mocked 200 shows the
  success state, mocked 400 shows the error; no console errors; no layout shift > .05; all images have alt; CSP clean.
- `research/screens_v4.mjs`: 1440 / 1024 / 390 × light, every section, + strip at cards 1, 6, 12 → `research/screens_v4/`.
- Eye review: a reviewer agent on **`model: "sonnet"`, `omitClaudeMd: true`** reads every PNG against: photo looks like
  a photograph in a frame (never pasted), backdrop reads as behind/beside, type never over the figure, alignment,
  clipped text, dark-tablecloth feeling (= fail), "would a senior UX/UI designer at Higgsfield say wow or wince".
  Fix every item, re-screenshot, second round. Ship only on SHIP.
- Deploy a **preview branch**, never production: from `site/`, `npx wrangler@4 pages deploy . --project-name jeevana-yoga
  --branch v4 --commit-dirty=true` → `https://v4.jeevana-yoga.pages.dev`. Production keeps serving deploy 1.

**Record.** Append a `## v4 (2026-10-27)` block to `HANDOFF.md`: what shipped, preview URL, gate results, photos used,
open items; update `research/to_wire.md` only if a slot changed. Commit on the current branch, never `_raw_assets/`.
