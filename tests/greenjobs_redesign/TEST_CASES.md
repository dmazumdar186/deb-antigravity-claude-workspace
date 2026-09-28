# GreenJobs redesign — manual test cases

Automated coverage: `python3 tests/greenjobs_redesign/test_build.py` (build + validator + KPI recomputation) and `node --test` in `src/js/` (pure helpers). The cases below are the manual checks that need a browser.

## Dashboard (`/{ie,uk}/dashboard/`)

Reach it from the "KPI dashboard" link at the top of `/{ed}/for-keith/`. It is deliberately absent from the primary nav and the sitemap.

1. **Renders per edition.** Open `ie/dashboard/` then click `UK` in the header edition switch: you stay on the dashboard, numbers change, the currency symbol in the salary tile follows the edition (€ / £).
2. **Data as of.** The line under the h1 shows the snapshot date from `data/{ed}.json` (`fetched`), not today's date.
3. **Live-now tiles.** Eight tiles, each with a one-line "how we measure it". "New this week" carries a four-week sparkline. "Top employer share" gets a clay border and "!" only when the share is above 50% (true for IE where Gaia Talent dominates; check UK does not flag when its top employer is under half).
4. **Charts.** Sector and county/region bars plus the quality-score histogram render after load. Tab through the bars: each bar takes focus, shows the tooltip and reads "label: N roles" to a screen reader. "Show as table" under each chart expands a data table.
5. **Download CSV.** Click the button: a file `greenjobs-kpis-<date>.csv` downloads with a header row, the nine headline metrics, one row per sector, region and quality score. Open it in a spreadsheet; commas in labels are quoted. No network request is made (check the Network tab).
6. **Wired at launch.** Every tile in "Measured after launch" shows a dash, an event name in `code`, and a target in bold. No live-looking numbers appear anywhere in this block; the only digits are inside labelled targets (60%, 8%, 2.5 s, 200 ms, 0.1, 99.9%).
7. **No vendor names.** Search the page for "Plausible" and "GA4": none. The copy says "analytics provider".
8. **Dark theme.** Toggle the theme: tiles, bars and the histogram stay readable; the wired tiles keep their dashed border and muted dash.
9. **Reduced motion.** With `prefers-reduced-motion: reduce`, nothing animates and every number is visible immediately.
10. **390 px.** At a 390 px viewport the tiles stack in one column, the bars wrap their labels, and the CSV button sits under the as-of line. No horizontal scroll introduced by the dashboard content.
11. **Validator.** `python3 execution/gtm_client_workflows/greenjobs_redesign/build_site.py` exits 0: the page is noindex, has one h1, relative paths only, and stays inside the CSS/JS budgets.
