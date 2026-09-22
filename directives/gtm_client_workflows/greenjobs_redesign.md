# GreenJobs (greenjobs.ie + greenjobs.co.uk) redesign demo

## Purpose

A public static demo of both job boards owned by Keith Molony (Gaia Talent Ltd), built on their live
data, to back the €1,875 redesign proposal and to open the "move off the current vendor" conversation.
Companion to `gaia_redesign.md` (same pipeline pattern, different visual lane). Spec, critique and
panel pass: `deliverables/greenjobs_redesign_2026-09-22/research/`.

Live: https://dmazumdar186.github.io/deb-antigravity-claude-workspace/greenjobs/ (GitHub Pages) and
https://greenjobs-redesign.pages.dev/ (Cloudflare Pages). Evidence page: `<base>/ie/for-keith/`
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
6. Publish: `bash .../publish_gh_pages.sh` (sub-path `greenjobs/`, other paths untouched) and
   `bash .../deploy_cloudflare.sh` (project `greenjobs-redesign`). `curl -sI` the base URL and one
   job page on each host.

## Exit criteria

- Build exits 0; validator green; job pages == dataset length per edition; every apply link is the
  real listing URL; no "(0)" sector, no employer named as "hiring now" without a live role; public
  pages carry no "AI"/"Claude"/vendor names; `noindex` everywhere; 200 on `/`, `/ie/`, `/uk/`,
  `/ie/jobs/`, one job page, `/ie/for-keith/` on both hosts.

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
- The "Ask GreenJobs" panel is a local TF-IDF matcher. The Cloudflare Worker stub in `worker/` expects
  `OPENROUTER_API_KEY` (or an Anthropic key) as a Worker secret; nothing model-backed is live and no
  key exists in cloud sessions. Cloud sessions have no `.env`.

## Changelog

- 2026-09-22: built, audited (anneal PASS, pipeline PASS 10/10, code review fixed, 16 design items,
  11-lens panel), published on both hosts.
