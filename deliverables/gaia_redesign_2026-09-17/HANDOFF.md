# Handoff — Gaia Talent website redesign (paused 2026-09-17)

Branch `claude/trusting-galileo-lqnmop` (pushed; last commit before this file: 5ffa58c). Nothing has been
published to `gh-pages` or Cloudflare yet. Keith has NOT been sent anything.

## Model doctrine so far (for the record)
- Judgement on `claude-fable-5-1`: orchestration, spec synthesis, screenshot review, decisions;
  `pipeline-auditor` (pinned to Fable by its definition).
- Execution on `claude-sonnet-5`: 4 research scrapers, 6 panel lenses, jobs-dataset parser,
  test-suite runner, `anneal-reviewer`.
- `code-reviewer` runs on `claude-opus-5` (its definition). The site builder ran on Opus as a
  deliberate escalation (flagship canvas/CSS craft). Next session: run the builder on Sonnet from
  this handoff and compare; keep review/judgement on the top model.

## What exists
- Research: `research/RESEARCH.md` (synthesis), `gaiatalent_com_audit.md`, `reference_demo_teardown.md`,
  `brief.md` (the only source of facts), `build_spec.md` (panel decisions, §0 non-negotiables, §10 data notes).
- Source: `src/` (templates with build markers, `css/styles.css`, `js/{motion,main,flow,jobs}.js`,
  `js/motion.test.js` (22 tests), `assets/` incl. self-hosted fonts and 5 team portraits, `data/*.json`,
  `README.md` = porting guide for Keith).
- Rendered: `site/` (byte-reproducible from `src/` via the build). Pages: `/`, `/jobs/`, `/team/`,
  `/for-keith/` (private note, may mention the tooling), `/404.html`.
- Scripts: `execution/gtm_client_workflows/gaia_redesign/{build_site.py,validate_site.py,check_job_links.py,screenshot.sh,publish_gh_pages.sh,deploy_cloudflare.sh}`.
  Directive: `directives/gtm_client_workflows/gaia_redesign.md`.
- Tests in progress: `tests/gaia_redesign/` (test-suite runner was mid-run at pause; check for
  `run_all.sh`, `test_build.py`, `cdp_smoke.mjs` and `.tmp/gaia_redesign_shots/live/`).
- Screenshots: `.tmp/gaia_redesign_shots/` (round 2, real fonts). Crops in `crops/`.

## Commands
```
python3 execution/gtm_client_workflows/gaia_redesign/build_site.py --src deliverables/gaia_redesign_2026-09-17/src --out deliverables/gaia_redesign_2026-09-17/site
node --test deliverables/gaia_redesign_2026-09-17/src/js/motion.test.js
bash execution/gtm_client_workflows/gaia_redesign/screenshot.sh
bash execution/gtm_client_workflows/gaia_redesign/publish_gh_pages.sh      # -> https://dmazumdar186.github.io/deb-antigravity-claude-workspace/gaia/
bash execution/gtm_client_workflows/gaia_redesign/deploy_cloudflare.sh     # needs CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID (env or .env)
```
Headless Chromium: `/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell`
(no Playwright, no PIL; crop PNGs with a Chromium wrapper page, see session notes). gaiatalent.com blocks
WebFetch/Firecrawl; `curl -A Mozilla` works.

## Audit status (all three lenses have run on the round-2/3 build)
- anneal-reviewer: PASS (3 low notes).
- code-reviewer pass 1: 12 criticals → all fixed and verified by pass 2.
- code-reviewer pass 2: FAIL on 1 new critical + 4 majors (list below).
- pipeline-auditor: WARNINGS (data integrity high; items below).
- test-suite (6 tiers incl. real-browser CDP scroll test): result pending at pause.

## ROUND 4 — open items (do all, rebuild once, re-screenshot, re-run validator + node tests)
build_site.py
1. `run_node_tests` ignores exit code → treat non-zero exit or (0,0) summary as build failure (never print "0 tests, all passing").
2. Write `.gaia-build` marker BEFORE copytree (interrupted build otherwise bricks rebuilds); add recovery hint to the refusal message; drop the blanket `/tmp` allow-list entry.
3. `job.get("summary") or ""` in `_role_row`; reject `|` in sector names and `<`/`>` in titles in `check_dataset`; `check_built_js` must return collected problems on OSError; remove unused `name` param in `sector_map_term`.
check_job_links.py
4. urlopen follows redirects, so the 3xx branch is dead: compare `resp.geturl()` to the requested URL and mark redirected links "inconclusive"; close `HTTPError` responses.
validate_site.py
5. Add `Hidden Depth`, `615983`, `\bCRO\b`, `WordPress` to FORBIDDEN (public pages); require every `gaiatalent.com/jobs/` href on index.html (hero cards + featured) to be in jobs.json; check `?sector=` only against the sector select's options; verify `?q=` sector-map links land on the superscript count.
screenshot.sh
6. `kill "${SERVER:-0}"` in cleanup; `realpath -m` before the rm guard; write scratch `_shot-*` files outside `site/`.
main.js
7. Clear `inert`/`aria-hidden` on process cards when not in desktop-motion mode (else-branch in `update()`); same symmetry in flow.js `start()`; `stackFrozen` flag respected by resize; drop `document.hasFocus()` from the reveal safety net (or raise the timeout).
jobs.js
8. Preserve `location.hash` in `syncUrl`.
flow.js
9. Remove dead `var x` in `drawIntro` and the duplicate `seg()` comment above `poly`.
Copy / content (pipeline audit)
10. `src/team/index.html` line ~59: delete "There is no account manager layer…" (invented). Replace with BRIEF-sourced copy or nothing.
11. Services paragraph: restore Gaia's wording with only the typo fixed: "we truly understand that getting the right person at the right time is crucial to your success" (drop "matters more than filling a seat").
12. 404 footer: add both phone numbers (so the note's sentence is true), or reword the note to "home, roles and team pages".
13. Hero canvas: move the hydro dam glyph right of x≈640 so it never sits under the headline column (wind state).
14. Optional: hero label "Ecology & Environmental" → "Conservation & Environmental" (Ecology is not one of the 23 sectors). Keep "Speed and accuracy…" line (Keith's stated priority) but be aware it is from the call.
Then: pipeline-auditor re-run on the diff (Fable), code-reviewer pass 3 on changed files (Opus), test-suite re-run (Sonnet).

## Publish (only after round 4 is green)
1. `publish_gh_pages.sh` → curl 200 on `/gaia/`, `/gaia/jobs/`, `/gaia/team/`, `/gaia/for-keith/`.
2. `deploy_cloudflare.sh` once the two CLOUDFLARE_* variables exist in the cloud environment (they are
   not in this sandbox; operator has them in the local `.env`).
3. Commit `src/`, `site/`, `tests/`, scripts, directive; push branch; merge to main per standing order.
4. Send Keith the GitHub Pages URL (never an artifact link) with the `/for-keith/` page as the note.

## Non-negotiables (SPEC §0) — do not regress
No invented facts; no AI/Claude/automation words on public pages; no Hidden Depth comparisons; no CRO
number; every job links to its real gaiatalent.com page with the "as of 15 September 2026" stamp; phone-first
contact with "Schedule a confidential one to one chat" verbatim; relative paths only; noindex on all pages;
reduced-motion / no-JS / <800px fallbacks intact.
