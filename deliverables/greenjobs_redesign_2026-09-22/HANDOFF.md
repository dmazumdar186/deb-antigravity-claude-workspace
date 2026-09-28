# GreenJobs redesign demo — handoff (2026-09-22)

Client: Keith Molony, Gaia Talent Ltd (owner of greenjobs.ie + greenjobs.co.uk).
Spec: `research/build_spec.md`. Source: `src/`. Built site: `site/` (not committed until reviewed).

## Status (refreshed 2026-09-28)

- Build: `python3 execution/gtm_client_workflows/greenjobs_redesign/build_site.py [--today YYYY-MM-DD]` → exit 0. 165 live roles on the 22 Sept snapshot (88 IE, 77 UK after the UK inclusion rule and the closed-role drop), 195 pages, CSS 69.7 KB, JS 96.8 KB (budgets 80/125), zero third-party requests.
- Tests: `python3 tests/greenjobs_redesign/test_build.py` (unit + integration on fixture and real data + injected faults + `# --- panel fixes B ---`), `node --test src/js/lib.test.js` (24 tests) and `node --test src/js/dashboard.test.js` (5 tests). All green at the time of writing.
- Pages per edition: home, jobs, job pages, sectors, insights, compass, employers, guides + salary guide, 4 SEO landing pages, dashboard (noindex, linked from for-keith), for-keith.
- Deployed URL: https://greenjobs-redesign.pages.dev/ (Cloudflare Pages, `deploy_cloudflare.sh`; redeploy after every rebuild). Not committed to the client repo.
- Panel pass (11 lenses) run 2026-09-28; fixes applied (see the directive changelog).

### Launch checklist (needs GreenJobs)

1. Email provider for the weekly newsletter and job alerts (sign-up forms connect at launch).
2. Owner of the advertising-rates inbox and the reply-time promise.
3. Analytics provider (the cookie Analytics toggle and `track()` stub are ready; nothing is sent until one is connected).
4. Client testimonials, verbatim from the GreenJobs testimonials page, with permission to name clients.
5. Confirmation of current B Corp status and permission to use the B Corp, 1% for the Planet and employer logos.
6. DNS change pointing greenjobs.ie / greenjobs.co.uk at the new host.

## What is where

| Piece | Path |
|---|---|
| Build / validate | `execution/gtm_client_workflows/greenjobs_redesign/{build_site,validate_site}.py` |
| Map geometry generator | `execution/gtm_client_workflows/greenjobs_redesign/make_maps.py` (Natural Earth 10m admin-1 → `src/assets/maps/{ie,uk}.svg`) |
| Screenshots / publish / deploy | `execution/gtm_client_workflows/greenjobs_redesign/{screenshot,publish_gh_pages,deploy_cloudflare}.sh` |
| Worker stub (phase 2) | `execution/gtm_client_workflows/greenjobs_redesign/worker/` |
| Tests | `tests/greenjobs_redesign/test_build.py`, `src/js/lib.test.js` |

## Data caveats (surface to Keith)

- greenjobs.co.uk listings carry no sector tags; both editions use an eleven-sector taxonomy derived from title/description keywords (`TAXONOMY` in `build_site.py`). Individual roles can be mis-tagged.
- `region` is free text (e.g. "London, North West, Country"); jobs map to one or more regions via `src/data/regions_<ed>.json`. IE has 23 UK-located jobs (bucket "Elsewhere"); UK has 23 Ireland jobs and 11 "Country"/remote.
- IE has few employers (Gaia Talent, Mattinson and Commonland on the 22 Sept snapshot); the IE hero and employers page show no employer count.
- B Corp: the site's own mark is shown with its alt text and a generic one-line definition of B Corp; no certification claim is added in text (brief §3). Status + logo permission are on the launch checklist.
- Prices: none published → "Packages on request".
- Lighthouse was not run (no harness in the build environment); the evidence page says so and shows measured bytes/requests instead.

## Publish when approved

```bash
bash execution/gtm_client_workflows/greenjobs_redesign/publish_gh_pages.sh   # https://<owner>.github.io/<repo>/greenjobs/
bash execution/gtm_client_workflows/greenjobs_redesign/deploy_cloudflare.sh  # https://greenjobs-redesign.pages.dev/
```
