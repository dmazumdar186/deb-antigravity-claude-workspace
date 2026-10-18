---
name: site-redesign
description: Prospectus-style concept site (scrubbed cover, deck), eye-reviewed, deployed + pitch. Triggers: "redesign <site>", "rebuild their website", "build a site for", "website concept", "mockup website", "design a website", "pitch site", /site-redesign.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, WebSearch, WebFetch
user_invocable: true
---

# Site redesign — the prospectus renderer (standard since MISB v3, 2026-10-15)

One of the operator's main freelance offers. Every redesign is built the way MISB v3 was built
(`deliverables/misb_redesign_2026-10-15/site_v3/`), never the way v2 was (a static page the operator
called "designed in 2015, not sellable"). The reference the operator always gives:
https://proposals.papayalabs.app/evolution-exhibits-6yry74 — a designed document, not a web page.
Recipe with mechanics: `reference/concept_recipe.md`. Rules: `reference/build_rules.md`.

## Inputs
- `$ARGUMENTS`: URL or brand, optional language (`fr`, `en-GB`), prospect name for `for-<name>/`,
  theme hints. Env: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `OPENROUTER_API_KEY` (or the
  `OPENROUTER_API_TOEKN` alias), optional `HF_API_TOKEN`. Chromium at `/opt/pw-browsers`, ffmpeg.

## Outputs
- `deliverables/<slug>_redesign_<date>/site/` (index, `css/`, `js/` incl. `backdrop.js`, `assets/`
  with real logo, photos, `hero.mp4|webm`, `hero-m.*`, `hero.jpg`, `hero.json`), `for-<name>/`
  pitch, `research/` (facts, `glm_log.md`, `live_metrics.json`, `functional.json`), `screens/`,
  `HANDOFF.md`. Live at `https://<slug>-redesign.pages.dev/` (noindex). Optional social set link.

## The standard (non-negotiable)
Build a **prospectus / concept-art renderer**, every element below present:
- **(a) Cover** — pinned, scroll-scrubbed (`400svh` desktop / `250svh` mobile), 3–5 verbatim fact
  beats with a progress rail, photo plates (real photos, desktop), generative backdrop written by GLM
  from public facts only (Kimi K3 fallback), self-rendered to a hosted hero video (Chromium + ffmpeg)
  with canvas fallback and a Kling-ready `hero.json` slot.
- **(b) Signature pinned scroll object** carrying real information — fold-out prospectus, card stack
  or drum, picked per brand. Paper, crease and grain treatment when it is a print metaphor.
  Horizontal snap-scroll under 800 px; **no 3D on phones**.
- **(c) Command deck** — sticky chapter nav switching one panel; every fact in DOM (`hidden` +
  `inert` when inactive); hash deep links, back/forward, arrow keys; ≤ 1 viewport per panel desktop.
- **(d) Designed-document DNA** — numbered chapters "01 —", paper `#EEECE6`, white cards, amber
  small caps, one accent, serif display + one sans.
- **(e) Measured** — live site vs concept scroll height (desktop + mobile) in the pitch table, via
  `scripts/measure_live.mjs` on the live site.
- **(f) Real** — brand's real logo and photos only, verbatim facts, contradictions footnoted.

**Banned:** a long single-column marketing page of stacked sections; timer-driven hero widgets
bolted beside a headline; stock photos; text wordmarks; emoji icons; third-party JS.

## Process (brain: 1, 4 verdict, 6–7; workers: 2, 3, 5)
1. **Research** (one batched message): fetch the site (`curl -A`, WebFetch; 403 → `WebSearch
   site:`, Wikipedia, press), download real logo + photos, collect verbatim facts and
   contradictions, run `measure_live.mjs <url>`, one sector best-practice search. Pick the signature
   object and the 3–5 cover beats. Read `reference/build_rules.md`.
2. **Brief + build** (one worker, `reference/worker_brief_template.md`, complete brief): worker runs
   `gen_backdrop.py` → reviews the module → builds site + pitch → `render_hero_video.mjs` → adapts
   `functional_template.mjs` → `site_check.mjs` → screens. Budget index+css+js ≤ 150 KB,
   backdrop ≤ 12 KB, zero third-party JS.
3. **Pitch page** `for-<name>/`: what it is, Today/Concept table (6 rows incl. measured heights),
   what does not exist yet, next, signature "Debanjan, Founder, ProdCraft, debanjan@prodcraft.fyi".
4. **Two mandatory eye-review rounds**: a reviewer agent (Opus, `omitClaudeMd`) Reads every PNG in
   `screens/` against the checklist in `concept_recipe.md` and returns SHIP or a numbered defect
   list. Fix every item, re-screenshot, round 2. **Ship only on SHIP.** Images never enter the brain.
5. **Deploy**: `bash scripts/deploy.sh <site-dir> <slug>-redesign for-<name>/`. Sandbox Chromium
   cannot open `*.pages.dev`; verification is on identical local files — say so.
6. **Handoff + commit**: `HANDOFF.md` (links, facts + sources, measurements, review rounds, Kling
   slot, not done), commit, push branch, fast-forward and push `main`. `/compact` after deploy.
7. **Reply**: both links first, what changed, how it was verified, caveats, outreach message in the
   prospect's language.

## Models & tools
| Job | Tool |
|---|---|
| Creative modules (backdrop canvas, generative motifs) | GLM 5.3 via OpenRouter (`z-ai/glm-5.3` → `glm-5.2`); fallback `moonshotai/kimi-k3`. Public facts only — no names, emails, phones, client data (`directives/infrastructure/glm_5_2_integration.md`) |
| Hero footage | Kling 3.0 via Higgsfield when `HF_API_TOKEN` exists (`execution/gtm_client_workflows/greenjobs_redesign/generate_hero_footage.py`, estimate first); else self-render with `scripts/render_hero_video.mjs` |
| Judgement (brief, verdicts, handoff) | Fable 5.1 (session) |
| Build worker | Opus 5.5, effort low |
| Eye reviewer | Opus 5.5, reads PNGs, returns text only |
| Component parts bin (React islands only, never for static Astro blocks) | 21st.dev MCP `search` / `get_inspiration` (`directives/infrastructure/twentyfirst_dev.md`) |
| Gates | `scripts/site_check.mjs`, `scripts/functional_template.mjs`, `scripts/measure_live.mjs` |

## Feedback loop
Operator feedback → reproduce under emulation (Pixel 7 / iPhone 13) before touching code → root
cause → fix → functional + site_check + one reviewer round → redeploy → `vN` block in `HANDOFF.md`
→ new rule in `reference/build_rules.md`. A rejected concept is rebuilt from the recipe, not patched.

## Related
`/human-eye-test` (full release gate) · `/impeccable` (polish) · `directives/gtm_client_workflows/
site_redesign_concepts.md` (SOP) · `design-website` (superseded; bulk Sheet runs only).
