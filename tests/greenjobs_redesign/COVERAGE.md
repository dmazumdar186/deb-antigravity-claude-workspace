# GreenJobs redesign — test coverage (2026-09-28)

## Reproduce

```
python3 -m coverage run --include="execution/gtm_client_workflows/greenjobs_redesign/*" tests/greenjobs_redesign/test_build.py && python3 -m coverage report -m
```

`test_build.py`'s `main()` also runs `test_scrape.py` and `test_gaps.py`, so that one command (about 8 minutes) covers everything below. `python3 tests/greenjobs_redesign/run_all.py` adds the two node tiers (`node --test` on `lib.js` + `dashboard.js`, and the Playwright DOM check `dashboard_dom.test.mjs`, which prints `SKIP` and exits 0 when Chromium or Playwright is absent). Every file also runs on its own.

JS: `cd deliverables/greenjobs_redesign_2026-09-22/src/js && node --test --experimental-test-coverage lib.test.js dashboard.test.js`

## Before / after (line coverage)

| File | Before | After |
|---|---|---|
| `build_site.py` | 88% (178 of 1461 missing) | 99% (5 missing) |
| `validate_site.py` | 85% (52 of 344 missing) | 99% (2 missing) |
| `scrape_greenjobs.py` | 18% (240 of 294 missing) | 99% (1 of 296 missing) |
| **Total** | **78%** (470 of 2099) | **99%** (8 of 2101) |
| `lib.js` (node --test) | 97.7% | 97.7% (unchanged) |
| `dashboard.js` (node --test) | 57.1% | 57.1% — the DOM half (lines 35-61) now runs in real Chromium via `dashboard_dom.test.mjs`, but code executed inside the browser cannot be attributed by `node --test`'s coverage, so the figure does not move |

Checks: 319 before → 532 after in the python tier (87 in `test_scrape.py`, 126 in `test_gaps.py`), plus 15 Playwright checks.

## Scraper fixture

`tests/fixtures/greenjobs_scrape/<host>/*.html` — 12 real pages captured 2026-09-28 with curl and a browser User-Agent (raw HTML, nothing stripped, largest 204 KB):

- `www.greenjobs.ie`: `home.html` (204 KB), `jobresults_pg1.html` (81 KB, 10 results of 108), `job_11502675.html`, `job_11502679.html`, `job_11502682.html` (67-94 KB), `about-us.cms.asp.html`, `contact-us.cms.asp.html`, `the-greenjobs-network-of-websites.cms.asp.html` (34-36 KB)
- `www.greenjobs.co.uk`: `home.html` (152 KB), `jobresults_pg1.html` (96 KB, 15 results of 123), `job_11502470.html`, `job_11502481.html` (64-78 KB)

`test_scrape.py` monkeypatches `scrape_greenjobs.fetch` with a URL→file map (unknown URLs return `None`, the crawler's "fetch failed" path) and runs `crawl_site` / `main` end to end into a scratch directory. Small synthetic pages cover what the corpus cannot: a job with a mojibake `Â£` salary, a results page 2 with a ghost job and a link-less result, an info page wrapped in `<div id="main">`, an unwrapped page, and an empty results page. None of the recorded adverts publishes a figure ("Competitive Salary"), so salary parsing is asserted through `parse_salary` directly and the synthetic job.

## Code change made while testing

`scrape_greenjobs.parse_salary` now normalises `Â£` / U+FFFD before matching (`GARBLED_POUND_RE`): the recorded-corpus test showed `"Â£30,000 to Â£35,000"` parsed as `(30000, None)` — the upper bound was lost because only the first currency symbol matched. Existing behaviour for clean text is unchanged (all previous checks still pass).

## Mutation check (2026-09-28)

Every check asserts a concrete property of the output (rendered HTML, validator message, exit code plus stderr text, written files). Verified by running `test_gaps.py` against mutated copies of the scripts (`GJ_SCRIPT_DIR=$PWD/.tmp/mut/<name> python3 tests/greenjobs_redesign/test_gaps.py`; the copy must sit three directories below the repo root):

| Mutation | Result |
|---|---|
| `build_site.esc()` with `quote=False` | 7 checks fail (role_card / home_row / logo_img / select_pairs / esc, the quoted-title job page, the home save button) |
| `validate_site.HERO_BUDGET_FILE = 1` | 8 checks fail (both hero budget checks with the exact byte messages, plus every fixture build, which now fails validation) |
| `landing_pages()` without the zero-role guard | 12 checks fail (the three `landing_pages` expectations, the built-landing set, role-card, sitemap and guides-hub checks, plus every fixture build via the validator's zero-role rule) |

`test_build.py` also catches the second (`HERO_BUDGET_FILE == 2 MB` check) and third (`landing: no roles -> no landing page`).

## Remaining uncovered lines

| Line(s) | Reason |
|---|---|
| `build_site.py` 1084 | `facts_block`: the `break` when three facts are already collected — `derived_facts` returns at most three and the loop only runs when the list is short, so the guard cannot fire. |
| `build_site.py` 2129 | `guard_output`: "filesystem root" refusal — a root path is always rejected two checks earlier (outside the build areas, or overlapping `--src`), so this line is unreachable. |
| `build_site.py` 2142-2143 | `_within`: `except (OSError, ValueError)` around `Path.resolve().is_relative_to()` — neither raises on Python 3.11 for any constructible path (a symlink loop raises `RuntimeError`, which is not caught). |
| `build_site.py` 2309 | `if __name__ == "__main__"` — the CLI is exercised through `main()` with a patched `sys.argv` instead; the module-level guard only runs in a subprocess, which coverage does not trace. |
| `validate_site.py` 151-152 | `_inside`: same `resolve()` exception guard as `_within`. |
| `scrape_greenjobs.py` 482 | `sys.exit(main())` under `__main__`; `main()` itself is covered (exit 0 and the exit-3 floor path). |

## Dead code found (not deleted)

- `build_site.py` `svg_polygons`, `ring_area`, `point_in_rings`, `sample_map_points`, `film_payload` (lines 1245-1382): no caller since the home film was removed on 2026-09-28. Pure and deterministic, so `test_gaps.test_geometry_helpers` covers them; delete together with the film references in `docs`/`HANDOFF.md` when the film is confirmed gone for good.
- `build_site._kb` (line 314): no caller.
- `scrape_greenjobs.clean_html` lower-cases opening tags only; closing tags keep their case (`</P>`). Cosmetic, asserted as-is.

## Latent test failures (pre-existing, not touched)

`test_build.py` defines `test_panel_b_copy_and_consent` and `test_panel_b_dashboard_rules_from_stored_fields` *after* the `__main__` guard, so the script runner never executes them; they only run under pytest or when the module is imported. Three of their checks fail against the current templates/data (tile label `(30d)` is rendered inside a `<span>`, "jQuery" legitimately appears in the evidence table above the appendix, and the synthetic dataset yields `closing7 == 3`, not 1). Left unchanged per the "no weakening" rule; a follow-up task is queued.
