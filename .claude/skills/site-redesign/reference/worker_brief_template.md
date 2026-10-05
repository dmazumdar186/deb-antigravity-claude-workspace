# Worker brief template (fill every bracket; one worker, foreground)

Build a complete, zero-dependency static concept site at `<abs path>/site/`: `index.html`,
`<pitch>/index.html`, `css/styles.css`, `js/main.js`, `assets/` (logo at `assets/logo-<slug>.<ext>`,
favicon.svg). Reference engineering (read narrowly with head/sed): `deliverables/midas_redesign_2026-10-05/site/`.
Read `.claude/skills/site-redesign/reference/build_rules.md` first; every rule is mandatory.

## Language and brand
- `lang="<xx>"`, register: <vouvoiement / tone>. Title: "<Brand> — <tagline> · Concept". `noindex`.
- Palette: <tokens with hex, which surfaces carry the brand colour, which sections may be dark>.
- Font: <one family>, Google Fonts link, display=swap. Headings clamp max 88px, letter-spacing ≥ -.03em.
- Logo: `<file>` in a <pill/plain> in header, footer, pitch page. Never a text wordmark.

## Verified facts (use only these)
<bulleted facts with exact wording, dates, numbers; mark placeholders "à brancher"/"to wire">

## index.html — sections in order
1. Header (fixed glass, logo, nav, tap-to-call, primary CTA; hamburger < 1050 with aria/Escape/inert)
2. Hero (<headline>, <sub>, <working widget: fields + computed results + modal>, <animated brand element>)
3. <Offer band with countdown to YYYY-MM-DDT23:59:59+ZZ>
4. <Ticker>
5. <Services rows, filter chips, pre-select widget>
6. <Proof section with counters>
7–N. <…>
Footer: legal placeholders, "Concept non officiel réalisé par ProdCraft — aucun lien avec <Brand>",
signature "Debanjan, Founder, ProdCraft, debanjan@prodcraft.fyi", link to `<pitch>/`.
Mobile: fixed bottom bar (Call / Book), emergency block first under header.

## <pitch>/index.html
~700 words, same CSS, prose page: what it is · Today/Concept table (6 rows) · what doesn't exist yet ·
next · signature.

## Verify (mandatory before reporting)
`node .claude/skills/site-redesign/scripts/site_check.mjs --site <abs path>/site` must exit 0.
Also test the widget: <inputs → expected outputs>. Screenshots land in `../screens/`.
Do not commit. Report ≤ 200 words: files + sizes, check output summary, console error count, not done.
