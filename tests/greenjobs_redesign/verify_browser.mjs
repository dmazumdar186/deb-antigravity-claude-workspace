// Headless-Chromium behaviour checks for the GreenJobs demo's second act.
// description: Serves the built site, scrolls the home film with a real
//   wheel-style scroll and asserts it reaches state 2 (three states at every
//   width), checks the hero search and Post a job sit in the first 844px at
//   390 wide, runs the
//   "Your fit" query "ecologist dublin" and asserts Dublin ecology roles come
//   back, checks the ad builder renders the typed title into the card, and
//   that a job page with a salary shows the strip. Uses the globally installed
//   Playwright (verification tooling only; the site itself has no packages).
// inputs: optional site dir (default deliverables/greenjobs_redesign_2026-09-22/site), PORT env
// outputs: PASS/FAIL lines on stdout; exit 1 on any failure
// Run: node tests/greenjobs_redesign/verify_browser.mjs
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { extname, join, resolve } from 'node:path';

const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = require('playwright')); } catch { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')); }

const SITE = resolve(process.argv[2] || 'deliverables/greenjobs_redesign_2026-09-22/site');
const PORT = Number(process.env.PORT || 8752);
const MIME = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.png': 'image/png', '.webmanifest': 'application/manifest+json' };
const results = [];
const check = (ok, label) => { results.push([ok, label]); console.log((ok ? 'PASS  ' : 'FAIL  ') + label); };

const server = createServer(async (req, res) => {
  let p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  if (p.endsWith('/')) p += 'index.html';
  const file = join(SITE, p);
  try {
    const s = await stat(file);
    const body = await readFile(s.isDirectory() ? join(file, 'index.html') : file);
    res.writeHead(200, { 'content-type': MIME[extname(file)] || 'application/octet-stream' });
    res.end(body);
  } catch { res.writeHead(404); res.end('not found'); }
});
await new Promise((r) => server.listen(PORT, '127.0.0.1', r));
const base = `http://127.0.0.1:${PORT}/`;

const browser = await chromium.launch({ args: ['--no-sandbox', '--disable-gpu'] });
try {
  // ---- film: desktop, scrolled for real
  for (const [w, h, states] of [[1440, 900, 3], [390, 844, 3]]) {
    const page = await browser.newPage({ viewport: { width: w, height: h } });
    await page.goto(base + 'ie/index.html', { waitUntil: 'load' });
    await page.waitForTimeout(300);
    const seq = await page.evaluate(() => window.GJFilm && window.GJFilm.seq());
    check(Array.isArray(seq) && seq.length === states, `film ${w}px: ${states} states (${JSON.stringify(seq)})`);
    check((await page.evaluate(() => window.GJFilm.state())) === 0, `film ${w}px: starts in state 0`);
    const seen = new Set();
    const film = await page.evaluate(() => { const r = document.querySelector('[data-film]').getBoundingClientRect(); return { top: r.top + scrollY, h: r.height }; });
    for (let y = film.top; y <= film.top + film.h; y += Math.round(h / 3)) {
      await page.evaluate((yy) => window.scrollTo({ top: yy, behavior: 'instant' }), y);
      await page.waitForTimeout(90);
      seen.add(await page.evaluate(() => window.GJFilm.state()));
    }
    check(seen.has(2), `film ${w}px: reaches state 2 by scrolling (saw ${[...seen].sort().join(',')})`);
    check([...seen].every((s) => seq.includes(s)), `film ${w}px: only states in the sequence are shown`);
    const hero = await page.evaluate(() => { const q = document.getElementById('s-q').getBoundingClientRect(); const b = document.querySelector('.hero .btn--post').getBoundingClientRect(); scrollTo({ top: 0, behavior: 'instant' }); const q2 = document.getElementById('s-q').getBoundingClientRect(); const b2 = document.querySelector('.hero .btn--post').getBoundingClientRect(); return { q: q2.bottom, b: b2.bottom, ok: q2.top >= 0 && q2.bottom <= innerHeight && b2.top >= 0 && b2.bottom <= innerHeight && b2.height >= 56 }; });
    check(hero.ok, `hero ${w}px: search input (bottom ${Math.round(hero.q)}) and Post a job (bottom ${Math.round(hero.b)}, ≥56px) inside the first ${h}px`);
    await page.evaluate(() => scrollTo({ top: document.documentElement.scrollHeight, behavior: 'instant' })); await page.waitForTimeout(120);
    const fills = await page.evaluate(() => [...document.querySelectorAll('[data-film-step]')].filter((s) => getComputedStyle(s).display !== 'none').map((s) => s.style.getPropertyValue('--fill')));
    check(fills.length === states && fills.slice(0, -1).every((f) => Number(f) === 1), `film ${w}px: rail fills are complete at the end (${fills.join(' ')})`);
    const particles = await page.evaluate(() => window.GJFilm.particles());
    check(particles <= (w < 900 ? 1200 : 3000) && particles > 0, `film ${w}px: ${particles} particles within budget`);
    // keyboard: from the top, tabbing into a later state's copy scrolls the film there
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
    await page.waitForTimeout(120);
    await page.evaluate(() => document.querySelector('[data-film-state="2"] .btn').focus());
    await page.waitForTimeout(150);
    check((await page.evaluate(() => window.GJFilm.state())) === 2, `film ${w}px: focusing the last state's button moves the film to state 2`);
    await page.close();
  }
  // ---- reduced motion: static film, search visible
  const rm = await browser.newPage({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
  await rm.goto(base + 'ie/index.html', { waitUntil: 'load' });
  check(await rm.evaluate(() => document.querySelector('[data-film]').classList.contains('film--static')), 'reduced motion: film is static');
  check(await rm.evaluate(() => { const q = document.getElementById('s-q').getBoundingClientRect(); const m = document.querySelector('[data-film-state="0"]'); const o = document.querySelector('[data-film-state="1"]'); return q.height > 0 && getComputedStyle(m).display !== 'none' && getComputedStyle(o).display === 'none'; }), 'reduced motion: hero search rendered, film shows the map state only');
  check(await rm.evaluate(() => !document.querySelector('[data-film] canvas')), 'reduced motion: no canvas created');
  await rm.close();

  // ---- your fit: ecologist dublin → Dublin ecology roles
  for (const path of ['ie/jobs/index.html', 'ie/index.html']) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    await page.goto(base + path, { waitUntil: 'load' });
    await page.fill('#fit-q', 'ecologist dublin');
    await page.waitForSelector('[data-fit-out] .hit', { timeout: 5000 });
    const hits = await page.$$eval('[data-fit-out] .hit', (els) => els.map((e) => ({ t: e.querySelector('b').textContent, s: e.querySelector('small').textContent })));
    check(hits.length > 0 && hits.length <= 6, `${path}: fit returns ${hits.length} hits`);
    check(hits.some((x) => /ecolog/i.test(x.t)) && hits.some((x) => /dublin/i.test(x.s)), `${path}: "ecologist dublin" → ecology roles in Dublin (${hits[0].t} — ${hits[0].s})`);
    check(await page.$eval('[data-fit-out]', (o) => !!o.querySelector('.fit__strip') && !!o.querySelector('.fit__map svg') && !!o.querySelector('.fit__caveat')), `${path}: salary strip, mini map and caveat rendered`);
    check(await page.evaluate(() => location.hash.startsWith('#fit=')), `${path}: result is in the URL hash (${await page.evaluate(() => location.hash)})`);
    check(await page.$eval('[data-fit-out] .hit mark', (m) => /ecolog/i.test(m.textContent)), `${path}: matched term highlighted`);
    await page.fill('#fit-q', 'zzzz qqqq');
    await page.waitForSelector('[data-fit-out] .fit__none', { timeout: 3000 });
    check(true, `${path}: no-match state renders`);
    await page.close();
  }
  // ---- ad builder
  const ad = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await ad.goto(base + 'ie/employers/index.html', { waitUntil: 'load' });
  await ad.fill('#p-title', 'Peatland Restoration Officer');
  await ad.fill('#p-smin', '42000'); await ad.fill('#p-smax', '48000');
  check(await ad.$eval('[data-adb-card] h3', (h) => h.textContent === 'Peatland Restoration Officer'), 'ad builder: title renders into the card');
  check(await ad.$eval('[data-adb-card] .tag--sal', (t) => t.textContent === '€42k–48k'), 'ad builder: salary chip renders');
  check(await ad.$eval('[data-adb-reach]', (r) => /Roles in .* this week: \d+/.test(r.textContent)), 'ad builder: reach line computed from data');
  await ad.click('[data-adb] button[type="submit"]');
  check(await ad.$eval('[data-adb] [data-demo-note]', (n) => !n.hidden), 'ad builder: submit shows the honest demo note');
  await ad.close();
  // ---- job salary strip
  const board = await (await fetch(base + 'ie/jobs/index.html')).text();
  const data = JSON.parse(board.match(/id="gj-data">(.*?)<\/script>/s)[1]);
  const withSal = data.jobs.find((j) => j.sal_min != null && j.sal_max != null);
  const noSal = data.jobs.find((j) => j.sal_min == null && j.sal_max == null);
  const jp = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await jp.goto(base + 'ie/jobs/' + withSal.href, { waitUntil: 'load' });
  check(await jp.$eval('.sits', (s) => !!s.querySelector('.sits__svg') && s.querySelectorAll('.sits__mark[tabindex="0"]').length > 0 && !!s.querySelector('.sits__table table')), `job ${withSal.id}: salary strip with focusable marks and a table`);
  await jp.goto(base + 'ie/jobs/' + noSal.href, { waitUntil: 'load' });
  check(await jp.$eval('.sits--none .sits__line', (l) => /hasn't published a salary/.test(l.textContent)), `job ${noSal.id}: no-salary line rendered`);
  await jp.close();
} finally {
  await browser.close();
  server.close();
}
const failed = results.filter(([ok]) => !ok);
console.log(`\nBrowser checks: ${results.length - failed.length} passed, ${failed.length} failed`);
process.exit(failed.length ? 1 : 0);
