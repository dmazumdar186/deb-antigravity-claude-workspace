# Gaia Talent website redesign (static demo site)

## Purpose

A free, no-strings redesign of gaiatalent.com, built and hosted on the operator's GitHub Pages so
Keith Molony (Managing Director, Gaia Talent) can review it with no risk to his live site. It is a
credibility play alongside the Radar sourcing engagement (`gaia_sourcing.md`): proof that the
operator ships serious, accurate, fast work. Research and the panel decisions live in
`deliverables/gaia_redesign_2026-09-17/research/`.

## When to invoke

- The operator asks to rebuild, update, re-publish or re-audit the Gaia demo site.
- Gaia's live roles change and the demo should be refreshed (weekly is enough; the sitemap is
  updated roughly weekly).
- Keith supplies new facts (bios, logos, contact email, placement numbers) that must be reflected.

## Inputs

- `deliverables/gaia_redesign_2026-09-17/src/` — page templates, CSS, JS, assets, README. Edit here,
  never in `site/`.
- `src/data/jobs.json`, `sectors.json`, `consultants.json` — parsed from gaiatalent.com job pages
  (63 roles on 2026-09-17). Regenerate with the parser kept in the research scratch (`build_jobs.py`
  logic is documented in `research/RESEARCH.md` §6); a Vincere export can replace it later with the
  same field contract (`slug,title,url,location,sectors[],type,salary,consultant,consultant_title,summary,posted`).
- `src/config.json` (optional) — `contact_email` for the form's mailto link (empty by default; the
  public form falls back to a copy-the-message panel plus the two phone numbers).
- Facts: only `research/brief.md` and the data files. Nothing else may appear as a claim.

## Outputs

- `deliverables/gaia_redesign_2026-09-17/site/` — rendered static bundle (relative paths only), tagged
  internally with a `.gaia-build` marker file (written before `copytree`, so an interrupted build still
  leaves the marker and the next run can recover instead of being refused by the empty-dir guard).
- `gh-pages` branch, sub-path `gaia/` → **live**: https://dmazumdar186.github.io/deb-antigravity-claude-workspace/gaia/
  (published 2026-09-17).
- `.tmp/gaia_redesign_shots/*.png` — screenshots at 390/768/1440 (+ reduced motion) for review; all
  scratch (token file, click-simulation HTML copies) stays under `.tmp/gaia_redesign_shots/_scratch/`,
  never inside `site/`.
- `src/data/link_check.json` — HEAD/ranged-GET results for every real job URL (injected into `for-keith/`),
  now with `ok` / `inconclusive` (403s and silent redirects, reason `refused` or `redirected`) / `failed`
  counted separately; the summary sentence reports each bucket.
- `deliverables/gaia_redesign_2026-09-17/site/assets/*.png` (and `src/assets/*.png`) — the site's own
  logo/portrait/B-Corp PNGs are explicitly un-ignored in `.gitignore` (repo default is `*.png` gitignored
  globally for screenshot scratch).

## Process

1. `python3 execution/gtm_client_workflows/gaia_redesign/build_site.py --src deliverables/gaia_redesign_2026-09-17/src --out deliverables/gaia_redesign_2026-09-17/site`
   (renders jobs, sectors, team roster, flow roles, JSON-LD; measures bytes; runs `node --test
   js/motion.test.js` and `node --check` on every shipped JS file; validates; non-zero on any failure —
   including a node-test crash with no `# fail` line, or a clean-looking `(0, 0)` pass/fail summary,
   both of which are now treated as build failures, never a silent "0 tests, all passing"). Add
   `--skip-links` only when offline (reuses the stored `link_check.json`).
   `--out` is restricted to an allow-list: under this repo's `deliverables/`, `.tmp/`, or
   `$CLAUDE_SCRATCHPAD` (no bare `/tmp` — dropped from the allow-list; a target outside it, one that
   overlaps `--src`, or a non-empty dir without a `.gaia-build` marker is refused rather than deleted).
2. `bash execution/gtm_client_workflows/gaia_redesign/screenshot.sh` and look at every PNG.
3. Test suite: `python3 tests/gaia_redesign/test_build.py` (unit + integration, builds into fresh dirs
   under this repo's `.tmp/`, never `/tmp`) and `node tests/gaia_redesign/cdp_smoke.mjs` (CDP E2E —
   serve the built site on port 8899 and run `headless_shell --remote-debugging-port=9222` first; env
   `SITE_PORT`/`CDP_PORT`/`SHOT_DIR` override the defaults).
4. Audit stack (anneal-reviewer, code-reviewer, pipeline-auditor) on the diff; fix; rebuild.
5. `bash execution/gtm_client_workflows/gaia_redesign/publish_gh_pages.sh` (publishes only `gaia/`;
   the POC pages at `/` are untouched; excludes `.gaia-build` and `_shot-*` from the pushed tree).
   Then `curl -sI` the base URL and one sub-page.
   Optionally `bash execution/gtm_client_workflows/gaia_redesign/deploy_cloudflare.sh` for the
   `pages.dev` mirror (same `.gaia-build`/`_shot-*` exclusion; token permissions: Account > Cloudflare
   Pages > Edit; in a **cloud session** the env vars must already exist in the container — a var added
   mid-session is invisible, so use a fresh session after adding `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID`).
6. Commit `src/`, `site/`, scripts and this directive; push branch and main.

## Exit Criteria (declarative)

- `site/index.html`, `site/jobs/index.html`, `site/team/index.html`, `site/for-keith/index.html`
  exist; the validator passes: no leading-slash paths, every local asset resolves, every `<img>` has
  alt/width/height, all JSON-LD parses, rendered job count equals `jobs.json` length, no
  "TODO"/"lorem", no "AI"/"Claude"/"nuclear"/"Hidden Depth"/"615983"/"CRO"/"WordPress" on public pages
  (`for-keith/` is the one exempt page), `robots` noindex meta on every page. Each Sectors-map
  superscript count must equal the number of job rows its `?q=` term actually matches, and every
  `jobs/index.html` job link must resolve to a URL present in `jobs.json` (and vice versa).
- Every job link is a real `https://gaiatalent.com/jobs/<slug>/` URL and `link_check.json` shows the
  verified count that `for-keith/` displays; a role that returned a silent redirect or a 403/405 is
  reported as "inconclusive" (reason `redirected` or `refused`), never silently folded into "verified".
- Team section shows the five real portraits with verbatim titles; no invented bios.
- Contact CTA reads "Schedule a confidential one to one chat"; both phone numbers present.
- CSS ≤ 45 KB and JS ≤ 30 KB uncompressed (reported by the build).
- The public URL returns 200 for `/gaia/`, `/gaia/jobs/`, `/gaia/team/`, `/gaia/for-keith/`.

## Scripts (Layer 3)

- `execution/gtm_client_workflows/gaia_redesign/build_site.py` — orchestrates the render, calls
  `validate_site.py` and `check_job_links.py` in-process.
- `execution/gtm_client_workflows/gaia_redesign/validate_site.py` — structural/accessibility/honesty
  checks; not normally invoked standalone.
- `execution/gtm_client_workflows/gaia_redesign/check_job_links.py` — can also run standalone:
  `python3 check_job_links.py --jobs <jobs.json> --out <link_check.json> [--workers N]`.
- `execution/gtm_client_workflows/gaia_redesign/screenshot.sh`
- `execution/gtm_client_workflows/gaia_redesign/publish_gh_pages.sh`
- `execution/gtm_client_workflows/gaia_redesign/deploy_cloudflare.sh` — same bundle to Cloudflare Pages
  (`https://gaia-talent-redesign.pages.dev/`); needs `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID`
  (env or `.env`; in cloud sessions add them to the environment's variables, `.env` does not exist there,
  and env vars added after the container started are not visible — re-run from a fresh cloud session).

## Tests

- `python3 tests/gaia_redesign/test_build.py` — unit tests over `build_site.py` helpers plus
  integration tests that build/validate/link-check against the real dataset and injected faults; every
  build target is a fresh dir under this repo's `.tmp/` (never `/tmp` — `guard_output`'s allow-list
  excludes it).
- `node tests/gaia_redesign/cdp_smoke.mjs` — CDP-driven E2E smoke test; requires the built site served
  on `SITE_PORT` (default 8899) and a `headless_shell` listening on `CDP_PORT` (default 9222,
  `--remote-debugging-port=9222`) before running.

## Edge cases

- gaiatalent.com blocks WebFetch/Firecrawl (Cloudflare 403); `curl` with a Mozilla UA works.
- Google PageSpeed API is quota-blocked from the sandbox: never quote a Lighthouse score that was
  not run locally.
- Sitemap "posted" dates are bulk-touch dates, not posting dates: show only the page-level
  "as of" date.
- Only 7 of 63 roles disclose salary: salaries are not shown.
- Keith cannot open claude.ai artifact links: always send the GitHub Pages URL.
- The demo duplicates Gaia's content under another domain: keep `noindex` until it moves to
  gaiatalent.com, then remove it and the `robots.txt` disallow.
- Never add AI wording, Hidden Depth comparisons, invented proof or the CRO number to public pages —
  the validator enforces this by blocking "Hidden Depth", "615983", "CRO" and "WordPress" outright
  (in addition to AI/Claude/automation/nuclear/TODO/lorem-ipsum wording).
- `node --test` can exit non-zero with no `# fail` line (a crash before any test ran), or print a
  clean `(0, 0)` pass/fail summary if the test file loaded but matched nothing: `build_site.py` treats
  both as a build failure rather than a silent pass.
- `--out` for `build_site.py` only accepts this repo's `deliverables/`, `.tmp/`, or
  `$CLAUDE_SCRATCHPAD` — no bare `/tmp` (removed after round 4/5 hardening); a target that overlaps
  `--src`, is a filesystem root, or is a non-empty dir without the `.gaia-build` marker is refused.
- `check_job_links.py` treats a silent redirect (final URL differs from the published URL) or a
  403/405 response as "inconclusive" (reason `redirected` or `refused`), never as verified or dead;
  `for-keith/`'s summary sentence counts these separately from the "N of M verified" figure.
- `screenshot.sh` keeps all interaction-simulation scratch (token file, click-simulation HTML copies)
  under `.tmp/gaia_redesign_shots/_scratch/`, served from a second HTTP server — never written into
  `site/`.
- `publish_gh_pages.sh` and `deploy_cloudflare.sh` both exclude `.gaia-build` and `_shot-*` from what
  they ship, so build markers and screenshot scratch never land in a live deployment.
- `*.png` is gitignored globally; `deliverables/gaia_redesign_2026-09-17/{src,site}/assets/*.png` are
  explicitly un-ignored so the site's own logo/portrait/B-Corp images stay tracked.
- Cloud sessions do not see environment variables added after the container started —
  `deploy_cloudflare.sh` needs `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID` set before the session
  starts, or a fresh session after adding them.

## Changelog

- 2026-09-17: created. Research (four scrape agents), six-lens panel, spec, build, publish to
  `gh-pages:/gaia/` (now **live**: https://dmazumdar186.github.io/deb-antigravity-claude-workspace/gaia/).
- 2026-09-17 (rounds 4-5): build now fails on a node-test crash or a clean `(0,0)` summary; `.gaia-build`
  marker written before `copytree` with a recovery hint on interrupted builds; `--out` allow-list
  tightened to repo `.tmp/` + `CLAUDE_SCRATCHPAD` only (bare `/tmp` removed); validator's forbidden-term
  list grew "Hidden Depth"/"615983"/"CRO"/"WordPress"; sector-map superscript counts and jobs-index
  hrefs are now cross-checked against the dataset; `check_job_links.py` marks silent redirects and
  403/405s as "inconclusive" (reason `refused`/`redirected`), counted separately in the summary
  sentence; `screenshot.sh` scratch fully isolated from `site/`; publish/deploy scripts exclude
  `.gaia-build` and `_shot-*`; added `tests/gaia_redesign/test_build.py` and `cdp_smoke.mjs`; `*.png`
  un-ignored for `src/assets`/`site/assets`.
