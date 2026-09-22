# GreenJobs redesign demo — handoff (2026-09-22)

Client: Keith Molony, Gaia Talent Ltd (owner of greenjobs.ie + greenjobs.co.uk).
Spec: `research/build_spec.md`. Source: `src/`. Built site: `site/` (not committed until reviewed).

## Status

- Build: `python3 execution/gtm_client_workflows/greenjobs_redesign/build_site.py` → exit 0. 186 real roles (88 IE, 98 UK), 204 pages, CSS 43.8 KB, JS 52.0 KB (budgets 60/60), zero third-party requests.
- Tests: `python3 tests/greenjobs_redesign/test_build.py` (unit + integration on fixture and real data + injected faults) and `node --test src/js/lib.test.js` (11 tests).
- Screenshots: `bash execution/gtm_client_workflows/greenjobs_redesign/screenshot.sh` → `.tmp/greenjobs_redesign_shots/` (87 PNGs: 390/768/1024/1440, both editions, reduced-motion, dark, map/filtered/empty/compass-result states). Three look-and-fix rounds done.
- Not published, not deployed, not committed (per brief).

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
- Only 3 employers on IE (Gaia Talent 63, Mattinson 23, Commonland 2) — the home page says so honestly.
- B Corp: the site's own footer mark is shown with its alt text; no certification claim is added (brief §3).
- Prices: none published → "Packages on request".
- Lighthouse was not run (no harness in the build environment); the evidence page says so and shows measured bytes/requests instead.

## Publish when approved

```bash
bash execution/gtm_client_workflows/greenjobs_redesign/publish_gh_pages.sh   # https://<owner>.github.io/<repo>/greenjobs/
bash execution/gtm_client_workflows/greenjobs_redesign/deploy_cloudflare.sh  # https://greenjobs-redesign.pages.dev/
```
