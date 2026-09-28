# Pipeline audit v2 — GreenJobs fix rounds (HEAD 567d353), 2026-09-28

**Verdict: WARN** — 10 of 11 claims verified from source; one claim ("21/23 sterling corrections") is numerically true but one of the 21 restored figures is the WRONG advert's salary (slug-collision bug in `sterling_correction`).

## Claims and evidence (all counted from `deliverables/greenjobs_redesign_2026-09-22/site` and `src/data`)

1. **21/23 sterling** — PASS on count, FAIL on content. Public `site/ie/data/jobs.json` does not carry `currency_source` (stripped for the browser); it carries `cur` and `unverified_cur`. `cur` = {GBP: 21, EUR: 8, None: 59}; `unverified_cur` = {11497629, 11496364} → 21 + 2 = 23, all 23 are `loc_class == "uk"`. All 21 GBP are Mattinson Partnership.
   **Defect:** IE 11495292 "Senior Health & Safety Consultant" (London, posted 02/09) was scraped as €55,000–€60,000 (`src/data/ie.json`), but the site shows **£62,000 to £67,000** (`site/ie/jobs/11495292/index.html`, "paid in sterling, about €72.5k–78.4k"). Cause: `build_site.py:656-683` `sterling_twins` keys by `slug:` with `setdefault`, and `sterling_correction` accepts a slug match **without** the figure-equality check applied to the title+employer path. Three UK roles share slug `senior-health-and-safety-consultant` (11501461 £62–67k Cambridge, 11495291 £55–60k London Central, 11491048 £50–70k Galway); the first won. Correct twin is 11495291 (£55–60k). Other slug collisions in UK GBP set: `sustainability-consultant` (2), `senior-transport-planner` (2), `operations-manager` (2) — the other 20 restored roles' figures do match their IE source numbers (checked all 21; 1 differs). 11501460 (the Cambridge twin) is correct.
   Fix: apply the `(salary_min, salary_max)` equality guard to the slug path too (or drop the slug key and match on id, then title+employer+figures).
2. **2 unverified marked** — PASS. Both pages render "Salary source: Salary as listed on greenjobs.ie; the advertiser may pay in sterling" (11497629 €70–75k, 11496364 €30–40k).
3. **No employer-count sentence on IE home/employers** — PASS. Regex `[0-9]+ (employers|organisations|companies)` → 0 hits in `ie/index.html` and `ie/employers/index.html`; strip lede reads "Organisations with live roles on greenjobs.ie this week."
4. **Commonland "Ireland & UK" both editions** — PASS. IE 11501646/11501648 and UK 11501639/11501644 all `loc_class: cross`; rendered chip "Ireland &amp; UK" on `ie/jobs/11501646` and `uk/jobs/11501639`. Note the IE data still stores `location: "Dublin"`, `regions: ["Dublin"]` while UK stores "United Kingdom (UK), Ireland (nationwide)" — label is right, the underlying location string differs per edition (as scraped).
5. **NI and East Midlands at 0 in UK region list** — PASS. `uk/index.html` data attr `"East Midlands":0,"Northern Ireland":0`, map nodes `data-n="0"` for both; `uk/jobs/index.html` regions JSON `{"name":"East Midlands","n":0,"on_map":true},{"name":"Northern Ireland","n":0,"on_map":true}` and both appear as `<option>`s.
6. **Landing hreflang reciprocal, 4 pairs** — PASS. ecology, environmental-dublin/london, renewable, sustainability: each IE and UK page carries identical en-IE / en-GB / x-default triplets pointing at each other (x-default → IE).
7. **No ISO dates visible on public pages** — PASS with note. Text-node scan of all HTML (scripts/styles/tags stripped): only `ie/for-keith/` and `uk/for-keith/` show `2026-09-22`/`2026-09-28`; both are `noindex,nofollow`, absent from `sitemap.xml`, not linked from home/jobs. Not public; acceptable.
8. **Package table has no buttons in cells** — PASS. `ie/employers` and `uk/employers`: 56 cells each, 0 `<button>` inside any `<table>`.
9. **IE employer strip: 3 logo tiles, no non-hiring names** — PASS. `.marq__track` has 6 `.emp` tiles = 3 unique (Commonland, Gaia Talent, Mattinson Partnership) duplicated for the loop; all three have live IE roles (2/63/23); no other names (EirGrid/Power NI/Veolia absent). Note: hero `.hero__trust` has only the B Corp image, not employer logos — the "strip" is the lower `band--tight` section.
10. **Compass dedupe** — PASS. `js/compass.js:37` `var pool = G.dedupeJobs(jobs.filter(...))`; `dedupeJobs` defined `js/lib.js:285`, exported :431.
11. **900 checks pass** — PASS. `python3 tests/greenjobs_redesign/test_build.py` → "Unit+Integration: 900 passed, 0 failed, 0 skipped", exit 0 (log `.tmp/panel/_audit_v2_testbuild.log`). The two `FAIL` lines in the log are stdout from deliberately-failing fixture builds, each followed by a PASS assertion. Test `r3 R011` only asserts count/source, not figure fidelity — so the slug bug is untested.

## Silent drops
None: 88 IE roles built; 62 ie + 23 uk + 3 cross = 88; 23 uk-located = 21 GBP + 2 unverified.

## Issues
- [HIGH] Wrong salary on IE 11495292 (shows £62–67k, advert is £55–60k). Public, client-visible, and exactly the class of error the sterling fix was meant to remove. Fix guard in `sterling_correction` slug path; add a test asserting each restored role's £ figures equal its IE € figures.
- [LOW] `robots.txt` is `Disallow: /` on the built copy — fine for staging, must not ship to production.
