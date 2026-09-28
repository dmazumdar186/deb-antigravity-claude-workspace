// Headless-Chromium check of dashboard.js's DOM code (init, charts, CSV export).
// description: Serves a built site over a python http.server, loads
//   /ie/dashboard/ and /uk/dashboard/, waits for the three GJCharts figures,
//   toggles every "Show as table" <details>, clicks Download CSV and asserts
//   the download name and header row, and that no console error or page error
//   fired. Skips cleanly (exit 0, "SKIP" line) when Chromium or Playwright is
//   absent. node --test cannot attribute coverage to code run inside the
//   browser, so this file complements dashboard.test.js rather than raising
//   its coverage figure.
// inputs: optional site dir argument or SITE env (default: builds the fixture
//   site into .tmp/ via build_site.py); PORT env (default 8761);
//   PW_CHROMIUM env (default /opt/pw-browsers/chromium)
// outputs: PASS/FAIL/SKIP lines on stdout; exit 1 on any failure
// Run: node tests/greenjobs_redesign/dashboard_dom.test.mjs [site-dir]
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, rmSync } from 'node:fs';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, '..', '..');
const SRC = join(REPO, 'deliverables', 'greenjobs_redesign_2026-09-22', 'src');
const CHROMIUM = process.env.PW_CHROMIUM || '/opt/pw-browsers/chromium';
const PORT = Number(process.env.PORT || 8761);
const results = [];
const check = (ok, label) => { results.push([ok, label]); console.log((ok ? 'PASS  ' : 'FAIL  ') + label); };

const require = createRequire(import.meta.url);
let chromium = null;
for (const mod of ['playwright', '/opt/node22/lib/node_modules/playwright']) {
  try { ({ chromium } = require(mod)); break; } catch { /* try the next location */ }
}
if (!chromium || !existsSync(CHROMIUM)) {
  console.log(`SKIP  dashboard DOM: ${!chromium ? 'playwright is not installed' : 'chromium missing at ' + CHROMIUM}`);
  process.exit(0);
}

let site = process.argv[2] || process.env.SITE;
let scratch = null;
if (!site) {
  scratch = mkdtempSync(join(existsSync(join(REPO, '.tmp')) ? join(REPO, '.tmp') : tmpdir(), 'greenjobs_dash_dom_'));
  site = join(scratch, 'site');
  const build = spawnSync('python3', [join(REPO, 'execution', 'gtm_client_workflows', 'greenjobs_redesign', 'build_site.py'), '--src', SRC, '--out', site, '--edition', 'both', '--data-fixture', join(SRC, 'data', '_fixture.json')], { encoding: 'utf8' });
  if (build.status !== 0) { console.log('FAIL  dashboard DOM: scratch build failed\n' + build.stderr); process.exit(1); }
}
site = resolve(site);

const server = spawn('python3', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1', '--directory', site], { stdio: 'ignore' });
const base = `http://127.0.0.1:${PORT}/`;
for (let i = 0; i < 50; i++) {
  try { const r = await fetch(base + 'index.html'); if (r.ok) break; } catch { /* not up yet */ }
  await new Promise((r) => setTimeout(r, 100));
}

const browser = await chromium.launch({ executablePath: CHROMIUM, args: ['--no-sandbox', '--disable-gpu'] });
try {
  for (const ed of ['ie', 'uk']) {
    const errors = [];
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, acceptDownloads: true });
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
    page.on('pageerror', (e) => errors.push(String(e)));
    page.on('requestfailed', (r) => errors.push('request failed: ' + r.url()));
    await page.goto(base + ed + '/dashboard/index.html', { waitUntil: 'load' });
    await page.waitForSelector('[data-fig="quality"] details.tbl', { timeout: 10000 });
    const figs = await page.$$eval('[data-dash] [data-fig]', (els) => els.map((f) => ({ key: f.dataset.fig, chart: f.querySelectorAll('.hbars .hbar, svg').length, tables: f.querySelectorAll('details.tbl table').length })));
    check(figs.length === 3 && figs.every((f) => f.chart >= 1 && f.tables === 1), `${ed}: three figures each with a chart (bars or columns) and a table (${JSON.stringify(figs)})`);
    const k = JSON.parse(await page.$eval('#gj-dash', (s) => s.textContent));
    const sectorRows = await page.$$eval('[data-fig="sectors"] details.tbl tbody tr', (rows) => rows.map((r) => [...r.querySelectorAll('td,th')].map((c) => c.textContent)));
    check(sectorRows.length === k.sectors.length && sectorRows.every((r, i) => r[0] === k.sectors[i].l && r[1] === String(k.sectors[i].v)), `${ed}: sector table rows equal the embedded KPI payload (${sectorRows.length} rows)`);
    // toggle every table open, then closed
    const closedBefore = await page.$$eval('[data-dash] details.tbl', (ds) => ds.every((d) => !d.open));
    for (const s of await page.$$('[data-dash] details.tbl > summary')) await s.click();
    const openAfter = await page.$$eval('[data-dash] details.tbl', (ds) => ds.every((d) => d.open) && ds.every((d) => d.querySelector('table').getBoundingClientRect().height > 0));
    for (const s of await page.$$('[data-dash] details.tbl > summary')) await s.click();
    const closedAgain = await page.$$eval('[data-dash] details.tbl', (ds) => ds.every((d) => !d.open));
    check(closedBefore && openAfter && closedAgain, `${ed}: "Show as table" toggles every table open (visible) and closed again`);
    const [download] = await Promise.all([page.waitForEvent('download', { timeout: 10000 }), page.click('[data-csv]')]);
    const name = download.suggestedFilename();
    const path = await download.path();
    const text = path ? (await import('node:fs/promises')).readFile(path, 'utf8') : Promise.resolve('');
    const csv = await text;
    const lines = csv.split('\r\n');
    check(name === `greenjobs-kpis-${k.asof}.csv`, `${ed}: Download CSV names the file after the snapshot date (${name})`);
    check(lines[0] === 'metric,value,how we measure it' && lines[1] === `Live roles,${k.live},listings with a page on the snapshot date` && lines.filter((l) => l.replace(/^"/, '').startsWith('Sector: ')).length === k.sectors.length && csv.endsWith('\r\n'), `${ed}: CSV has the header, the live-roles row and one row per sector (${lines.length - 1} lines; first: ${JSON.stringify(lines.slice(0, 2))})`);
    const requests = [];
    page.on('request', (r) => requests.push(r.url()));
    await page.click('[data-csv]');
    await page.waitForTimeout(300);
    check(requests.every((u) => u.startsWith('blob:') || u.startsWith(base)), `${ed}: exporting makes no network request beyond the site itself`);
    check(errors.length === 0, `${ed}: no console errors, page errors or failed requests (${errors.slice(0, 3).join(' | ')})`);
    await page.close();
  }
  // a page without the dashboard host: init() returns early without touching the DOM
  const plain = await browser.newPage();
  const errs = [];
  plain.on('pageerror', (e) => errs.push(String(e)));
  await plain.goto(base + 'ie/index.html', { waitUntil: 'load' });
  const r = await plain.evaluate(async () => { await new Promise((res) => { const s = document.createElement('script'); s.src = '../js/dashboard.js'; s.onload = res; document.head.appendChild(s); }); return typeof window.GJDash === 'object' && typeof window.GJDash.toCsv === 'function' && !document.querySelector('[data-dash]'); });
  check(r && errs.length === 0, 'dashboard.js on a page without [data-dash]: exports the helpers and does nothing else');
  await plain.close();
} finally {
  await browser.close();
  server.kill();
  if (scratch) rmSync(scratch, { recursive: true, force: true });
}
const failed = results.filter(([ok]) => !ok);
console.log(`\nDashboard DOM: ${results.length - failed.length} passed, ${failed.length} failed`);
process.exit(failed.length ? 1 : 0);
