# GreenJobs (greenjobs.ie + greenjobs.co.uk) redesign demo

## Purpose

A public static demo of both job boards owned by Keith Molony (Gaia Talent Ltd), built on their live
data, to back the €1,875 redesign proposal and to open the "move off the current vendor" conversation.
Companion to `gaia_redesign.md` (same pipeline pattern, different visual lane). Spec, critique and
panel pass: `deliverables/greenjobs_redesign_2026-09-22/research/`.

Live: https://greenjobs-redesign.pages.dev/ (Cloudflare Pages, the only host; github.io is retired and
redirects here). Evidence page: `<base>/ie/for-keith/`
(not linked from the public nav).

## Inputs

- `deliverables/greenjobs_redesign_2026-09-22/src/` — templates, `css/`, `js/`, `assets/` (fonts,
  maps, logos), `data/` (`ie.json`, `uk.json`, `brief.md`, `regions_*.json`, `perf_*.json`).
- Facts on public pages come only from `data/*.json` and `data/brief.md`.

## Process

1. Refresh data (optional, ~14 min): `python3 execution/gtm_client_workflows/greenjobs_redesign/scrape_greenjobs.py --site both`
   (polite: 4 workers, 0.3 s sleep; Mozilla UA; no keys).
2. Maps only when geometry changes: `python3 .../make_maps.py` (Natural Earth admin-1 → `assets/maps/{ie,uk}.svg`).
3. Build: `python3 .../build_site.py --src deliverables/greenjobs_redesign_2026-09-22/src --out deliverables/greenjobs_redesign_2026-09-22/site --edition both`
   (always `both`; a single edition leaves cross-edition links dangling). Runs node tests, validator,
   byte budgets (CSS ≤ 60 KB, JS ≤ 60 KB). `--out` allow-list and `.greenjobs-build` marker as in Gaia.
4. Tests: `python3 tests/greenjobs_redesign/test_build.py`; screenshots: `bash .../screenshot.sh`
   then look at every PNG in `.tmp/greenjobs_redesign_shots/`.
5. Audit stack + panel pass (roster in `.claude/memory/panel_roster.md`); fix; rebuild.
6. Publish: `bash .../deploy_cloudflare.sh` (project `greenjobs-redesign`). `curl -sI` the base URL and
   one job page. `publish_gh_pages.sh` is retired (exits 2); github.io holds redirect stubs only.

## Hero footage (Higgsfield)

`python3 execution/gtm_client_workflows/greenjobs_redesign/generate_hero_footage.py --edition ie --env-file <path to .env> --duration 10`
prints the free estimate; add `--go` to spend (guarded by `--max-usd`, default 1.50). It polls, downloads, and cuts
`src/assets/hero/{ie,uk}.mp4`, `-m.mp4` (portrait) and `-poster.jpg` with ffmpeg; the next build picks them up.
Prompts live in the script (`PROMPTS`) and in `research/hero_footage_brief.md`. Model: Kling 3.0 Standard by
default (2026-09-24 estimate: 10 s 16:9 = 13.44 credits / $0.84; 5 s = $0.42). The key is `HF_API_TOKEN=key_id:secret`
in the operator's `.env`; `api.higgsfield.ai` is behind Cloudflare and blocks non-browser user agents (error 1010),
the script sets one. `not_enough_credits` (HTTP 403) means the **API console** balance, separate from the app plan,
is below the estimate: top up at the Higgsfield API console, then re-run. On 2026-09-24 the balance was below
4.5 credits, so nothing was generated.

## Exit criteria

- Build exits 0; validator green; job pages == dataset length per edition; every apply link is the
  real listing URL; no "(0)" sector, no employer named as "hiring now" without a live role; public
  pages carry no "AI"/"Claude"/vendor names; `noindex` everywhere; 200 on `/`, `/ie/`, `/uk/`,
  `/ie/jobs/`, one job page, `/ie/for-keith/` on Cloudflare.

## Edge cases

- Both boards run the same hosted platform (jQuery 1.11, Bootstrap 3, `sjbimg.com`); the IE home page
  is 190 KB HTML / 1,090 links. The sites name "GreenJobs Ltd, Ennis" as owner, not Keith; the
  B Corp footer mark links to a B Lab explainer that never states GreenJobs' own certification —
  show the mark only, claim nothing.
- UK jobs carry no sector tags: sectors are keyword-derived (the evidence page says so).
- greenjobs.ie shows UK-located roles with € salaries; the demo mirrors the source, never converts.
- Snapshot data goes stale within a week: the hero carries a snapshot date; re-scrape before resending.
- wrangler ≥ 4.136 delegates `pages project create` to Workers and fails: `--force` is required.
- Sticky-footer layout stretches `main` inside a capture window taller than the page; screenshot.sh
  sets per-page heights so this is not mistaken for a layout bug.
- A screenshot "before/after" slider was dropped: greenjobs.ie serves no assets to a headless browser
  (Firecrawl token invalid in cloud), so a capture is unstyled and unfair; the comparison stays data-based.
- The "Ask GreenJobs" / "Your fit" panel is a local TF-IDF matcher. The Cloudflare Worker stub in `worker/` expects
  `OPENROUTER_API_KEY` (or an Anthropic key) as a Worker secret; nothing model-backed is live and no
  key exists in cloud sessions. Cloud sessions have no `.env`.

## Changelog

- 2026-09-22: built, audited (anneal PASS, pipeline PASS 10/10, code review fixed, 16 design items,
  11-lens panel), published on both hosts.
- 2026-09-22 (act two): pinned scroll film hero (canvas; wind → county map → salary bands → sector
  ring → search; map points sampled from the SVG at build time), "Your fit in ten seconds" panel
  (home + jobs, upgraded local matcher, salary position, mini map, shareable hash), "Where this role
  sits" salary strip on job pages, live ad builder on Employers, count-ups/spotlights/magnetic
  buttons/view-transition morphs, evidence page request comparison. Budgets now CSS ≤ 72 KB, JS ≤ 110 KB.
  `capture_states.mjs` scrolls the film for screenshots; `tests/greenjobs_redesign/verify_browser.mjs`
  checks state 4 focus and a fit query in headless Chromium. Still zero API calls, zero third-party requests.
- 2026-09-24 (third pass, client feedback): warm-earth palette (paper `#f6f0e6` / `#efe6d6`, ink
  `#2a2521`, honey `#d99a1c` actions with ink text, terracotta once per section, sage/sky/clay data
  only; warm dark theme), Fraunces headlines + Nunito text (Archivo / Public Sans removed), a
  procedurally drawn living-landscape hero on one canvas (`js/landscape.js`: hills, river, solar
  field, five turbines, hedgerow, clouds, birds, scroll-warmed sun, parallax; ≤ 4 ms/frame, paused
  off-screen, static under reduced motion, CSS gradient without canvas), the film moved onto the
  paper-2 band with 2.4–3 px ink/clay/sage/sky/honey particles, ink label pills and a radial vignette,
  cookie banner + settings dialog and a weekly-email subscribe dialog (`js/popups.js`, localStorage,
  `?popup=` hook for captures), and a no-code hero footage drop-in (`src/assets/hero/<ed>.mp4`,
  `-m.mp4`, `-poster.webp|jpg`; validator checks referenced files exist). Budgets raised to CSS ≤ 80 KB,
  JS ≤ 125 KB (measured 70 / 99). Learned: the validator's checkbox rule needs `<label for>` (a
  wrapping label only counts when `<label>` is immediately followed by `<input>`).
- 2026-09-25 (fourth pass, operator feedback "buttons simple, logo yellow vs favicon green, inner pages
  dense"): one brand mark (deep-green leaf `#1f7a3d` on an ink tile) shared byte-for-byte by favicon,
  header, menu, footer and chooser; honey retired from the brand (`--honey*` now alias the `--brand*`
  tokens; the landscape sun keeps its colour). Button system: gradient primary with inset highlight,
  coloured glow, lift/press/focus states; ink-fill secondary; ghost; circular icon buttons; hairline +
  two-layer shadow on cards. Progressive disclosure: job rows unfold summary/sector/type/age + Apply/Save
  on hover, focus or tap (`.row__more`, `css/disclose.css`); salary explorer is one chart at a time behind
  a tablist (`#chart=` deep link); employer packages are `<details class="reveal">` cards that preview on
  hover (JS in `main.js`: a closed `<details>` hides its body at the UA level, CSS alone cannot show it);
  sector list is an accordion (`sector_rows()` in `build_site.py`); job descriptions fold after the first
  paragraph (`split_description()`). Review: `research/design_review_2026-09-25.md`. Measured CSS 77 / JS 102 KB.
  No Higgsfield/GLM calls: the cloud session holds no keys.
