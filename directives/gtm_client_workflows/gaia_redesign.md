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

- `deliverables/gaia_redesign_2026-09-17/site/` — rendered static bundle (relative paths only).
- `gh-pages` branch, sub-path `gaia/` → https://dmazumdar186.github.io/deb-antigravity-claude-workspace/gaia/
- `.tmp/gaia_redesign_shots/*.png` — screenshots at 390/768/1440 (+ reduced motion) for review.
- `src/data/link_check.json` — HEAD results for every real job URL (injected into `for-keith/`).

## Process

1. `python3 execution/gtm_client_workflows/gaia_redesign/build_site.py --src deliverables/gaia_redesign_2026-09-17/src --out deliverables/gaia_redesign_2026-09-17/site`
   (renders jobs, sectors, team roster, flow roles, JSON-LD; measures bytes; validates; non-zero on
   any failure). Add `--skip-links` only when offline.
2. `node --test deliverables/gaia_redesign_2026-09-17/src/js/motion.test.js`
3. `bash execution/gtm_client_workflows/gaia_redesign/screenshot.sh` and look at every PNG.
4. Audit stack (anneal-reviewer, code-reviewer, pipeline-auditor) on the diff; fix; rebuild.
5. `bash execution/gtm_client_workflows/gaia_redesign/publish_gh_pages.sh` (publishes only `gaia/`;
   the POC pages at `/` are untouched). Then `curl -sI` the base URL and one sub-page.
6. Commit `src/`, `site/`, scripts and this directive; push branch and main.

## Exit Criteria (declarative)

- `site/index.html`, `site/jobs/index.html`, `site/team/index.html`, `site/for-keith/index.html`
  exist; the validator passes: no leading-slash paths, every local asset resolves, every `<img>` has
  alt/width/height, all JSON-LD parses, rendered job count equals `jobs.json` length, no
  "TODO"/"lorem", no "AI"/"Claude"/"nuclear" on public pages, `robots` noindex meta on every page.
- Every job link is a real `https://gaiatalent.com/jobs/<slug>/` URL and `link_check.json` shows the
  verified count that `for-keith/` displays.
- Team section shows the five real portraits with verbatim titles; no invented bios.
- Contact CTA reads "Schedule a confidential one to one chat"; both phone numbers present.
- CSS ≤ 45 KB and JS ≤ 30 KB uncompressed (reported by the build).
- The public URL returns 200 for `/gaia/`, `/gaia/jobs/`, `/gaia/team/`, `/gaia/for-keith/`.

## Scripts (Layer 3)

- `execution/gtm_client_workflows/gaia_redesign/build_site.py`
- `execution/gtm_client_workflows/gaia_redesign/screenshot.sh`
- `execution/gtm_client_workflows/gaia_redesign/publish_gh_pages.sh`

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
- Never add AI wording, Hidden Depth comparisons, invented proof or the CRO number to public pages.

## Changelog

- 2026-09-17: created. Research (four scrape agents), six-lens panel, spec, build, publish to
  `gh-pages:/gaia/`.
