# GreenJobs (greenjobs.ie + greenjobs.co.uk) redesign demo

## Purpose

A public static demo of both job boards owned by Keith Molony (Gaia Talent Ltd), built on their live
data, to back the €1,875 redesign proposal and to open the "move off the current vendor" conversation.
Companion to `gaia_redesign.md` (same pipeline pattern, different visual lane). Spec, critique and
panel pass: `deliverables/greenjobs_redesign_2026-09-22/research/`.

Live: https://greenjobs-redesign.pages.dev/ (Cloudflare Pages, the only host; github.io is retired and
redirects here). Evidence page: `<base>/ie/for-keith/`
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
   byte budgets (CSS ≤ 80 KB, JS ≤ 125 KB). `--out` allow-list and `.greenjobs-build` marker as in Gaia;
   `.greenjobs-build-ok` (sha256 of the tree) is written only after the validator passes and is the deploy gate.
4. Tests: `python3 tests/greenjobs_redesign/run_all.py` (python build/validate/scrape/gaps + `node --test` lib/dashboard +
   Playwright DOM and layout tiers; a skipped browser tier fails the run unless `--allow-skip`; prints the total
   check count and writes it to `tests/greenjobs_redesign/COVERAGE.md`); screenshots: `bash .../screenshot.sh`
   then look at every PNG in `.tmp/greenjobs_redesign_shots/`.
5. Audit stack + panel pass (roster in `.claude/memory/panel_roster.md`); fix; rebuild.
6. Publish: `bash .../deploy_cloudflare.sh` (project `greenjobs-redesign`; refuses without a fresh
   `.greenjobs-build-ok` and re-runs `validate_site.py <site>` first). `curl -sI` the base URL and
   one job page. `publish_gh_pages.sh` is retired (exits 2); github.io holds redirect stubs only.

## Hero footage (Higgsfield)

`python3 execution/gtm_client_workflows/greenjobs_redesign/generate_hero_footage.py --edition ie --env-file <path to .env> --duration 10`
prints the free estimate; add `--go` to spend (guarded by `--max-usd`, default 1.50). It polls, downloads, and cuts
`src/assets/hero/{ie,uk}.mp4`, `-m.mp4` (portrait) and `-poster.jpg` with ffmpeg; the next build picks them up.
Prompts live in the script (`PROMPTS`) and in `research/hero_footage_brief.md`. Model: Kling 3.0 Pro by
default since 2026-09-28 (1080p source; the 2026-09-24 Standard estimate was 10 s 16:9 = 13.44 credits / $0.84; 5 s = $0.42). The key is `HF_API_TOKEN=key_id:secret`
in the operator's `.env`; `api.higgsfield.ai` is behind Cloudflare and blocks non-browser user agents (error 1010),
the script sets one. `not_enough_credits` (HTTP 403) means the **API console** balance, separate from the app plan,
is below the estimate: top up at the Higgsfield API console, then re-run. On 2026-09-24 the balance was below
4.5 credits, so nothing was generated.

## Exit criteria

- Build exits 0; validator green; job pages == dataset length per edition; every apply link is the
  real listing URL; no "(0)" sector, no employer named as "hiring now" without a live role; public
  pages carry no "AI"/"Claude"/vendor names; `noindex` everywhere; 200 on `/`, `/ie/`, `/uk/`,
  `/ie/jobs/`, one job page, `/ie/for-keith/` on Cloudflare.

## Edge cases

- Both boards run the same hosted platform (jQuery 1.11, Bootstrap 3, `sjbimg.com`); the IE home page
  is 190 KB HTML / 1,090 links. The sites name "GreenJobs Ltd, Ennis" as owner, not Keith; the
  B Corp footer mark links to a B Lab explainer that never states GreenJobs' own certification —
  show the mark only, claim nothing.
- UK jobs carry no sector tags: sectors are keyword-derived (the evidence page says so).
- greenjobs.ie shows UK-located roles with sterling figures relabelled as €. Sterling rule: `sterling_correction()`
  restores the greenjobs.co.uk twin's GBP figures when the twin matches by id, slug or title + employer AND the
  (salary_min, salary_max) pair is numerically identical (the source relabels 1:1); several adverts share a slug,
  so the nearest posted date wins among figure-matching twins. Roles without a twin keep the scraped euros,
  are flagged `unverified_cur` (2 on the 22 Sept snapshot) and never enter a median, band, guide or dashboard
  figure; the salary guide says so. Displayed figures are never converted; the bracketed equivalent uses 1.17.
- Snapshot data goes stale within a week: the hero carries a snapshot date; re-scrape before resending.
- wrangler ≥ 4.136 delegates `pages project create` to Workers and fails: `--force` is required.
- Sticky-footer layout stretches `main` inside a capture window taller than the page; screenshot.sh
  sets per-page heights so this is not mistaken for a layout bug.
- A screenshot "before/after" slider was dropped: greenjobs.ie serves no assets to a headless browser
  (Firecrawl token invalid in cloud), so a capture is unstyled and unfair; the comparison stays data-based.
- The "Ask GreenJobs" / "Your fit" panel is a local TF-IDF matcher. The Cloudflare Worker stub in `worker/` expects
  `OPENROUTER_API_KEY` (or an Anthropic key) as a Worker secret; nothing model-backed is live and no
  key exists in cloud sessions. Cloud sessions have no `.env`.

## Changelog

- 2026-09-22: built, audited (anneal PASS, pipeline PASS 10/10, code review fixed, 16 design items,
  11-lens panel), published on both hosts.
- 2026-09-22 (act two): pinned scroll film hero (canvas; wind → county map → salary bands → sector
  ring → search; map points sampled from the SVG at build time), "Your fit in ten seconds" panel
  (home + jobs, upgraded local matcher, salary position, mini map, shareable hash), "Where this role
  sits" salary strip on job pages, live ad builder on Employers, count-ups/spotlights/magnetic
  buttons/view-transition morphs, evidence page request comparison. Budgets now CSS ≤ 72 KB, JS ≤ 110 KB.
  `capture_states.mjs` scrolls the film for screenshots; `tests/greenjobs_redesign/verify_browser.mjs`
  checks state 4 focus and a fit query in headless Chromium. Still zero API calls, zero third-party requests.
- 2026-09-24 (third pass, client feedback): warm-earth palette (paper `#f6f0e6` / `#efe6d6`, ink
  `#2a2521`, honey `#d99a1c` actions with ink text, terracotta once per section, sage/sky/clay data
  only; warm dark theme), Fraunces headlines + Nunito text (Archivo / Public Sans removed), a
  procedurally drawn living-landscape hero on one canvas (`js/landscape.js`: hills, river, solar
  field, five turbines, hedgerow, clouds, birds, scroll-warmed sun, parallax; ≤ 4 ms/frame, paused
  off-screen, static under reduced motion, CSS gradient without canvas), the film moved onto the
  paper-2 band with 2.4–3 px ink/clay/sage/sky/honey particles, ink label pills and a radial vignette,
  cookie banner + settings dialog and a weekly-email subscribe dialog (`js/popups.js`, localStorage,
  `?popup=` hook for captures), and a no-code hero footage drop-in (`src/assets/hero/<ed>.mp4`,
  `-m.mp4`, `-poster.webp|jpg`; validator checks referenced files exist). Budgets raised to CSS ≤ 80 KB,
  JS ≤ 125 KB (measured 70 / 99). Learned: the validator's checkbox rule needs `<label for>` (a
  wrapping label only counts when `<label>` is immediately followed by `<input>`).
- 2026-09-28 (edition rule and sterling fix, per Keith's document): Keith wrote "UK-only roles also appear
  prominently on the Irish board with salaries converted into euros. I would: retain salaries in their
  original advertised currency; clearly label UK, Ireland, remote and cross-border positions; allow users
  to exclude UK opportunities." Final rule: `EDITION_INCLUDES["ie"]` keeps every class (UK-only roles carry
  a "UK" badge and the "Hide UK/abroad-only roles" toggle, checklist B4); `EDITION_INCLUDES["uk"]` excludes
  Ireland-only and international roles (B5). An interim symmetric rule (IE excluding UK-only roles) was
  built and reverted the same day; the document overrides it. The real defect was the currency: the IE
  scrape relabels Mattinson's sterling figures as euros ("Associate Civil Engineer", London, €70,000 to
  €75,000). `sterling_twins()` indexes `src/data/uk.json`; `sterling_correction()` gives an IE role classed
  `uk` and priced in EUR the greenjobs.co.uk twin's GBP figures when the twin matches by id or slug, or by
  title + employer with the same numbers (a looser title match may be a different advert), and stamps
  `currency_source: "greenjobs.co.uk listing"`; the existing label then reads "£70k–75k (paid in sterling,
  about €82k–88k)" and the job page adds a "Salary source" line. Roles without a twin keep the scraped
  euros. The build log counts "sterling salaries restored from greenjobs.co.uk" (21 of 23 on the 22 Sept
  snapshot). The for-keith evidence table states per edition: IE "0 roles excluded; 23 UK-only roles shown
  with a UK label and the hide toggle", UK "20 Ireland-only roles kept off greenjobs.co.uk, 1
  international". `validate_site.py` fails a page carrying a role card outside its edition's class set
  (only the UK board excludes anything).
- 2026-09-28 (Keith's 28 September notes + panel pass): hero footage now defaults to Kling 3.0 Pro (1080p
  source, cut to 1280x720 loops); `FX_GBP_EUR = 1.17` fixed in `build_site.py` and mirrored in `lib.js`, used
  only for salary-range filters, medians, the "Where you sit on pay" strip and the bracketed "(paid in euros,
  about £…)" equivalent, never for the displayed figure; UK edition inclusion rule (a role appears on the UK
  board only if located in the UK incl. NI, fully remote, or explicitly IE+UK; the log line counts
  "excluded by the edition rule"; the IE board's handling of UK-only roles is in the entry above); roles whose closing date is before the build date are dropped at build
  time and the browser shows a "Closed" chip / "This role has closed" for anything that closes after the
  build (`data.today` in the dataset); `--today YYYY-MM-DD` pins the build date (default: the dataset's
  fetched date) so "ago" labels, closed-role drops and the footer year are deterministic; `/dashboard/`
  per edition (live tiles from stored fields + "Event spec for launch" with a consent-gated `track()`
  stub and `data-ev` attributes on apply, search, sign-up, request-rates, post-job and save controls);
  SEO landing pages (4 per edition, only when a role matches); `/guides/` with a data-generated salary
  guide; new facets (workplace, level, contract — the scraped job type and the text-derived tags are one merged
  Contract facet, `contract_facet()` — salary range, closing date, agency vs direct,
  "Hide UK/abroad-only roles"); the pinned film hero and `film.js` removed. Panel pass run 2026-09-28,
  fixes applied (cookie copy lists every stored key; quick-job-match text stays out of the URL until
  "Copy shareable link"; B Corp shown as mark + generic definition only; testimonial slots off the
  public page; launch notes shown before every demo form; employers page single CTA and "Ask us"
  membership cells; tags wrap at 390 px). Tests: `test_build.py` block `# --- panel fixes B ---`,
  `node --test src/js/dashboard.test.js`.
- 2026-09-28 (round 1, trace + QA): functional trace of every page at 1440/390 light/dark (`.tmp/trace3/acceptance.md`),
  numbers on public pages verified against `data/*.json` (88/77 roles, 14 sectors, 10 network sites, 29/47 disclosed
  salaries), 404 in the shell, hreflang pairs only for paths built in both editions (`paired_paths()`), Northern
  Ireland and East Midlands listed at 0 on the UK map so they stay a location option.
- 2026-09-28 (round 2, panel v1): secondary sector tags need `SECONDARY_MIN` and a third of the primary's score
  (R010/R087), Built environment as a secondary needs a title hit or three body keywords, unverified euro roles
  carry `currency_source` (R011), landing intros ≤ 80 words, employer strip lists live employers only (R041),
  contract facet merged, quick-job-match text kept out of the URL, cookie copy lists every stored key.
- 2026-09-28 (round 3, visual + layout suite): warm-earth visual fixes (visual 3–32), footer date rendered
  server-side, `tests/greenjobs_redesign/layout.test.mjs` added — Playwright layout regression (R1–R12: overflow,
  chip geometry, table bands, overlapping text, clipped controls, button rows, hero trust lines, rail scroll,
  console/network, contrast, screenshot baseline in `layout_baseline/`), `dashboard_dom.test.mjs` for the
  dashboard's browser half, `run_all.py` as the one test command, `test_scrape.py` against a recorded corpus,
  `test_gaps.py` branch tests (COVERAGE.md).
- 2026-09-28 (round 4, panel v2 + trace 3, data/build): sterling twin match requires figure equality on every
  path with nearest posted date as tie-break (IE 11495292 £55–60k from 11495291, not the £62–67k namesake);
  figure-fidelity test asserts all 21 restored pairs equal the IE source pairs; secondaries kept when the title,
  the site's own energy label or the energy family (wind/solar/renewable/networks) names them, "coastal" added
  to Water & flood, "enforcement officer" to Policy, golden `expect_secondaries` entries so drops are caught;
  `SITE_WORDS` no longer fire on bare "onsite"/"reserves"; the scraped type wins the permanent/contract axis
  (Bridge Engineer 11493521 → Contract only); `CROSS_RE` accepts ", - –" separators and reads only the title +
  first 300 summary chars; `date_long(None)` → ""; `lib.js dedupeJobs` trims; unverified-currency roles excluded
  from every median/band/guide/dashboard figure with the fx note saying so; `.greenjobs-build-ok` marker +
  `validate_site.py` CLI + deploy gate; scraper `--site both` exits 3 when either site is rejected, `logos.json`
  atomic; `run_all.py` SKIP semantics, total check count into COVERAGE.md; dashboard copy in the visitor voice
  (`DASHBOARD_COPY` / `DASHBOARD_REWRITES` in `build_site.py`); IE hero now reads 15 live sectors (Solar became
  live through the restored secondary). Tests: `test_build.py` block `# --- round 4 ---`.
