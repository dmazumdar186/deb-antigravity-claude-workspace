# GreenJobs redesign demo — handoff (2026-09-22)

Client: Keith Molony, Gaia Talent Ltd (owner of greenjobs.ie + greenjobs.co.uk).
Spec: `research/build_spec.md`. Source: `src/`. Built site: `site/` (not committed until reviewed).

## Status (refreshed 2026-09-28)

- Build: `python3 execution/gtm_client_workflows/greenjobs_redesign/build_site.py [--today YYYY-MM-DD]` → exit 0. 165 live roles on the 22 Sept snapshot (88 IE, 77 UK after the UK inclusion rule and the closed-role drop), 195 pages, CSS 76.9 KB, JS 107.5 KB (budgets 80/125), zero third-party requests. 21 of 23 UK-located IE roles get their sterling figure back from the greenjobs.co.uk twin; the 2 without a twin are flagged and kept out of every median. On success the build writes `site/.greenjobs-build-ok` (sha of the tree) — the deploy gate.
- Tests: `python3 tests/greenjobs_redesign/run_all.py` — four tiers: python (`test_build.py` incl. `test_scrape.py` + `test_gaps.py`, 1,010 checks), `node --test` lib + dashboard (40), Playwright dashboard DOM and layout regression (skip with `SKIP` when Chromium is absent; the run then exits 1 unless `--allow-skip`). The runner prints the total (2,797 checks on 2026-09-28: 1,010 + 40 + 15 + 1,732 layout assertions over 202 page loads) and writes it to `tests/greenjobs_redesign/COVERAGE.md` ("Last full run"). All green at the time of writing.
- Pages per edition: home, jobs, job pages, sectors, insights, compass, employers, guides + salary guide, 4 SEO landing pages, dashboard (noindex, linked from for-keith), for-keith.
- Live URL: https://greenjobs-redesign.pages.dev/ (Cloudflare Pages, served at `/`). `deploy_cloudflare.sh` refuses to deploy without a fresh `.greenjobs-build-ok` and re-runs `validate_site.py` first; redeploy after every rebuild. Not committed to the client repo.
- Panel pass (11 lenses) run 2026-09-28; fixes applied (see the directive changelog).

### Launch checklist (needs GreenJobs)

1. Email provider for the weekly newsletter and job alerts (sign-up forms connect at launch).
2. Owner of the advertising-rates inbox and the reply-time promise.
3. Analytics provider (the cookie Analytics toggle and `track()` stub are ready; nothing is sent until one is connected).
4. Client testimonials, verbatim from the GreenJobs testimonials page, with permission to name clients.
5. Confirmation of current B Corp status and permission to use the B Corp, 1% for the Planet and employer logos.
6. DNS change pointing greenjobs.ie / greenjobs.co.uk at the new host.
7. Flip `robots.txt` at launch: the demo ships `Disallow: /` on purpose; the launch build must allow crawling (and the sitemap is already absolute).
8. Weekly refresh routine (not built yet; needs): a cron that runs `scrape_greenjobs.py --site both` then `build_site.py` (the scraper exits 3 and leaves `src/data` untouched when either site falls under 50% of the last snapshot); an alert to Deb on any non-zero exit; the deploy gate (`.greenjobs-build-ok` + `validate_site.py`) before `deploy_cloudflare.sh`; a diff report of roles added / closed / re-priced per edition sent with the deploy.

## What is where

| Piece | Path |
|---|---|
| Build / validate | `execution/gtm_client_workflows/greenjobs_redesign/{build_site,validate_site}.py` |
| Map geometry generator | `execution/gtm_client_workflows/greenjobs_redesign/make_maps.py` (Natural Earth 10m admin-1 → `src/assets/maps/{ie,uk}.svg`) |
| Screenshots / deploy | `execution/gtm_client_workflows/greenjobs_redesign/{screenshot,deploy_cloudflare}.sh` (`publish_gh_pages.sh` retired) |
| Worker stub (phase 2) | `execution/gtm_client_workflows/greenjobs_redesign/worker/` |
| Tests | `tests/greenjobs_redesign/run_all.py` (→ `test_build.py`, `test_scrape.py`, `test_gaps.py`, `dashboard_dom.test.mjs`, `layout.test.mjs`), `src/js/lib.test.js`, `src/js/dashboard.test.js`; manual cases in `tests/greenjobs_redesign/TEST_CASES.md` |

## Data caveats (surface to Keith)

- greenjobs.co.uk listings carry no sector tags; both editions use an eleven-sector taxonomy derived from title/description keywords (`TAXONOMY` in `build_site.py`). Individual roles can be mis-tagged.
- `region` is free text (e.g. "London, North West, Country"); jobs map to one or more regions via `src/data/regions_<ed>.json`. IE has 23 UK-located jobs (bucket "Elsewhere"); UK has 23 Ireland jobs and 11 "Country"/remote.
- IE has few employers (Gaia Talent, Mattinson and Commonland on the 22 Sept snapshot); the IE hero and employers page show no employer count.
- B Corp: the site's own mark is shown with its alt text and a generic one-line definition of B Corp; no certification claim is added in text (brief §3). Status + logo permission are on the launch checklist.
- Prices: none published → "Packages on request".
- Lighthouse was not run (no harness in the build environment); the evidence page says so and shows measured bytes/requests instead.
- Salary figures: one `salary_stats()` in `build_site.py` feeds the home band, insights, salary guide and dashboard, so the four pages always print the same disclosed count, share, median and bands; the two unverified-currency roles are excluded from all of them (`lib.js annual()` mirrors this client-side). Human-eye r1 #3.
- Import normalisation (`sanitise_html`, `tidy_text`): "* ", "- " and "• " lines become real lists, whole-line `<strong>`/`<b>` is unwrapped, empty paragraphs and runs of `<br>` collapse, "UK/ Ireland" → "UK/Ireland"; a job without its own logo file borrows its employer's, else a monogram. Human-eye r1 #4/#19/#32.

## Publish when approved

```bash
python3 execution/gtm_client_workflows/greenjobs_redesign/build_site.py      # writes site/.greenjobs-build-ok after validation
bash execution/gtm_client_workflows/greenjobs_redesign/deploy_cloudflare.sh  # https://greenjobs-redesign.pages.dev/ (gate: marker + validate_site.py)
```
