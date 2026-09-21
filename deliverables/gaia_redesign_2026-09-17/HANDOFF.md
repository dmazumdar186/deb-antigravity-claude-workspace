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

## Audit status
- anneal-reviewer: PASS.
- code-reviewer pass 3: 3 majors fixed in round 5 (guard_output TMPDIR fallback, screenshot.sh scratch-in-site-tree, dam glyph geometry).
- pipeline-auditor: WARNINGS resolved.
- test-suite: 6 tiers, all green.

## Round 4 + 5 done (2026-09-17)
- `guard_output`'s allow-list no longer accepts the blanket `TMPDIR`/`/tmp`; only `CLAUDE_SCRATCHPAD` (if set) and the repo's own `.tmp` are allowed. Test fixtures build under `REPO/.tmp`, not pytest's `tmp_path`.
- `check_job_links.py` tags each inconclusive row with a `reason` ("refused" vs "redirected") and `summary_sentence` reports the two counts separately.
- `validate_site.py` resets its select-tracking state on `</select>` so a sector `<option>` after the jobs-filter select is never misattributed.
- `screenshot.sh` serves its readiness token from `$SCRATCH` via the second (scratch-rooted) HTTP server, never writes it into `$SITE`; `ROOT` is resolved with `realpath -m` so it is a real physical path.
- `publish_gh_pages.sh` and `deploy_cloudflare.sh` both exclude `.gaia-build` and `_shot-*` from what ships (rsync excludes, or a staged copy for wrangler).
- Hero step-rail label "Ecology" → "Conservation" (matches the "Conservation & Environmental" panel eyebrow); `build_site.py`'s matching sector-map entry renamed to match.
- The hero now carries exactly one `<h1>`: the no-JS/reduced-motion fallback heading is a `<p class="flow__fb-h1">` sharing the same visual styling as the pinned-stage `<h1>` (new CSS rule, unchanged appearance).
- `main.js`'s reveal safety net dropped the `document.visibilityState` gate (unreliable in headless/CI runners); the 20s timeout is unchanged.
- `cdp_smoke.mjs` closes every CDP tab it opens (`closeTab()` in each `finally`), and `SHOT_DIR` defaults to a path resolved relative to the repo instead of a hardcoded absolute path.
- `flow.js`'s hydro dam glyph moved to `dx = max(0.52W, 700)`, and the reservoir contour lines now start at the dam wall itself (never left of it), so nothing of the glyph sits under the headline column at 1440 or 1050 wide.
- `research/brief.md` gained a "Verbatim from gaiatalent.com" section quoting Gaia's own Services meta description and About body text, so those facts are traceable to the audit rather than only to derived copy.
- The "63 live roles" stat on index.html now reads "63 live roles across Ireland" (the dataset has 0 UK locations); the other "Ireland and the UK" lines are Gaia's own meta copy and are left as-is.

## Publish (only after round 4 is green)
1. `publish_gh_pages.sh` → curl 200 on `/gaia/`, `/gaia/jobs/`, `/gaia/team/`, `/gaia/for-keith/`.
2. `deploy_cloudflare.sh` → **done 2026-09-17**, live at https://gaia-talent-redesign.pages.dev/ (curl 200
   on `/`, `/jobs/`, `/team/`, `/for-keith/`; the `/for-keith/` page carries the "For the record" opener).
   Reruns are safe: the project-create step tolerates "already exists".
3. Commit `src/`, `site/`, `tests/`, scripts, directive; push branch; merge to main per standing order.
4. Send Keith the Cloudflare Pages URL (never an artifact link) with the `/for-keith/` page as the note.

## Known low-priority deviations
- The hero flow-pick keyword order (`build_site.py`'s sector-map list) differs from `build_spec.md` §10's
  literal order. The roles matched are real, drawn from the actual dataset, and never reused across states —
  only the order the sectors are tried in differs from the spec's listing order.
- `/for-keith/` discusses the build tooling by design (it is Keith's private note, not a public page); the
  public pages carry none of that language.

## Non-negotiables (SPEC §0) — do not regress
No invented facts; no AI/Claude/automation words on public pages; no Hidden Depth comparisons; no CRO
number; every job links to its real gaiatalent.com page with the "as of 15 September 2026" stamp; phone-first
contact with "Schedule a confidential one to one chat" verbatim; relative paths only; noindex on all pages;
reduced-motion / no-JS / <800px fallbacks intact.
