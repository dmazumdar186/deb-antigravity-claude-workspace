// Headless-Chromium behaviour checks for the GreenJobs demo's second act.
// description: Serves the built site, scrolls the home film with a real
//   wheel-style scroll and asserts it reaches state 2 (three states at every
//   width), checks the hero search and Post a job sit in the first 844px at
//   390 wide, runs the
//   "Your fit" query "ecologist dublin" and asserts Dublin ecology roles come
//   back, checks the ad builder renders the typed title into the card, and
//   that a job page with a salary shows the strip, that Fraunces and Nunito load,
//   the hero landscape canvas draws non-blank pixels, the subscribe dialog opens on
//   its timer and the cookie banner's Accept persists. Uses the globally installed
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

  // ---- fonts, hero canvas, popups
  const hp = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await hp.goto(base + 'ie/index.html', { waitUntil: 'load' });
  await hp.waitForTimeout(400);
  const fonts = await hp.evaluate(async () => { await document.fonts.ready; return { fr: document.fonts.check('600 32px Fraunces'), nu: document.fonts.check('400 16px Nunito'), n: [...document.fonts].filter((f) => f.status === 'loaded').map((f) => f.family) }; });
  check(fonts.fr && fonts.nu, `fonts: Fraunces and Nunito loaded (${fonts.n.join(', ')})`);
  const canvas = await hp.evaluate(() => {
    const c = document.querySelector('.hero__canvas'); if (!c) return { ok: false, why: 'no canvas' };
    const g = c.getContext('2d'), d = g.getImageData(0, 0, c.width, c.height).data; let distinct = new Set(); for (let i = 0; i < d.length; i += 4 * 97) distinct.add((d[i] << 16) | (d[i + 1] << 8) | d[i + 2]);
    return { ok: distinct.size > 12 && window.GJLandscape && window.GJLandscape.running(), distinct: distinct.size, w: c.width, h: c.height };
  });
  check(canvas.ok, `hero: landscape canvas draws non-blank pixels (${canvas.distinct} distinct colours sampled, ${canvas.w}×${canvas.h})`);
  await hp.waitForTimeout(700);
  const ms = await hp.evaluate(() => window.GJLandscape.ms());
  check(ms > 0 && ms <= 12, `hero: average draw ${ms.toFixed(2)} ms/frame in software-rendered headless (budget 4 ms on a laptop GPU, 12 ms here)`);
  check(await hp.evaluate(() => document.querySelector('[data-cookie]').classList.contains('is-on')), 'cookie: banner shows on first visit');
  await hp.click('[data-cookie-accept]');
  await hp.waitForTimeout(100);
  check(await hp.evaluate(() => { const c = JSON.parse(localStorage.getItem('gj-consent')); return c && c.essential === true && c.analytics === false && !document.querySelector('[data-cookie]').classList.contains('is-on'); }), 'cookie: Accept stores the choice and hides the banner');
  await hp.reload({ waitUntil: 'load' }); await hp.waitForTimeout(800);
  check(await hp.evaluate(() => !document.querySelector('[data-cookie]').classList.contains('is-on')), 'cookie: choice persists across a reload');
  await hp.click('[data-cookie-settings]', { force: true }).catch(() => {});
  await hp.evaluate(() => window.GJCookie.open());
  await hp.waitForTimeout(100);
  check(await hp.evaluate(() => document.querySelector('[data-cookie-dialog]').open), 'cookie: settings dialog opens');
  await hp.keyboard.press('Escape'); await hp.waitForTimeout(100);
  check(await hp.evaluate(() => !document.querySelector('[data-cookie-dialog]').open), 'cookie: Escape closes the settings dialog');
  check(await hp.evaluate(() => !document.querySelector('[data-subscribe]').open), 'subscribe: not open before the timer');
  await hp.clock.install().catch(() => {});
  await hp.evaluate(() => { localStorage.removeItem('gj-subscribe'); });
  await hp.reload({ waitUntil: 'load' });
  await hp.clock.runFor(21000).catch(async () => { await hp.evaluate(() => window.GJSubscribe.open()); });
  await hp.waitForTimeout(150);
  check(await hp.evaluate(() => document.querySelector('[data-subscribe]').open && document.activeElement && document.activeElement.id === 'sb-email'), 'subscribe: dialog opens on the 20 s timer with the email field focused');
  await hp.fill('#sb-email', 'keith@example.com'); await hp.click('[data-subscribe] button[type="submit"]');
  check(await hp.$eval('[data-subscribe] [data-demo-note]', (n) => !n.hidden), 'subscribe: submit shows the honest demo note');
  await hp.keyboard.press('Escape'); await hp.waitForTimeout(100);
  check(await hp.evaluate(() => !document.querySelector('[data-subscribe]').open && !!localStorage.getItem('gj-subscribe')), 'subscribe: Escape closes and records the dismissal');
  const layout = await hp.evaluate(() => { const h0 = document.documentElement.scrollHeight, b = document.querySelector('[data-cookie]'), d = document.querySelector('[data-subscribe]'); d.showModal(); const ok = getComputedStyle(b).position === 'fixed' && getComputedStyle(d).position === 'fixed' && document.documentElement.scrollHeight === h0; d.close(); return ok; });
  check(layout, 'popups: banner and dialog are fixed (no layout shift)');
  await hp.close();
  const rmh = await browser.newPage({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
  await rmh.goto(base + 'ie/index.html', { waitUntil: 'load' }); await rmh.waitForTimeout(300);
  check(await rmh.evaluate(() => !!document.querySelector('.hero__canvas') && !window.GJLandscape.running()), 'reduced motion: hero draws one static frame and does not animate');
  await rmh.close();

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
