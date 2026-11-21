// Eye review r4 layout checks in a real Chromium (360, 390 = iPhone 14, 412 = Pixel 7), against a built board tree.
// description: R4-4 the IE/UK switch is visible in the header at 390 px; chip "x" and consent checkbox elements are
//   >= 44 x 44 (hit area, glyph unchanged); every UK map region has a >= 44 px tap disc on a touch screen and the
//   region list links are >= 44 px tall; R4-2 the job breadcrumb never wraps (no trailing slash) and its slashes have
//   equal space either side; R4-1 after a successful send the confirmation is inside the viewport; R4-3 no two
//   elements share a view-transition-name and a card click logs no duplicate-name error.
// inputs: argv[2] = the built site dir (a board build)
// outputs: PASS/FAIL lines; exit 1 on any FAIL, 2 when Playwright/Chromium cannot start
// Run: node tests/greenjobs_redesign/r4_layout.mjs .tmp/some_board_build
import { createServer } from 'node:http';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { createRequire } from 'node:module';
import { extname, join, normalize, resolve, sep } from 'node:path';

const require = createRequire(import.meta.url);
let pw = null;
for (const m of ['playwright', '/opt/node22/lib/node_modules/playwright']) {
  try { pw = require(m); break; } catch { /* next */ }
}
const SITE = resolve(process.argv[2] || '');
if (!process.argv[2] || !existsSync(join(SITE, 'ie', 'index.html'))) { console.log(`FAIL  no built site at ${SITE}`); process.exit(1); }
if (!pw) { console.log('FAIL  playwright is not installed'); process.exit(2); }
const TYPES = { '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp', '.woff2': 'font/woff2', '.mp4': 'video/mp4' };
const server = createServer((req, res) => {
  let p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  if (p.endsWith('/')) p += 'index.html';
  const f = normalize(join(SITE, p));
  if (!f.startsWith(SITE + sep) || !existsSync(f) || statSync(f).isDirectory()) { res.writeHead(404); res.end('nf'); return; }
  res.writeHead(200, { 'Content-Type': TYPES[extname(f)] || 'application/octet-stream' });
  res.end(readFileSync(f));
});
await new Promise((ok) => server.listen(0, '127.0.0.1', ok));
const BASE = `http://127.0.0.1:${server.address().port}`;
const results = [];
const check = (ok, label) => { results.push(ok); console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}`); };

function emailJobs(ed) {
  const dir = join(SITE, ed, 'jobs');
  const out = [];
  for (const id of readdirSync(dir)) {
    const f = join(dir, id, 'index.html');
    if (existsSync(f)) {
      const h = readFileSync(f, 'utf8');
      if (h.includes('data-apply-form')) out.push({ id, len: h.length });
    }
  }
  out.sort((a, b) => b.len - a.len);
  return out.map((o) => `/${ed}/jobs/${o.id}/`);
}

let browser;
try { browser = await pw.chromium.launch(); } catch (e) { console.log(`FAIL  chromium did not start: ${e.message.split('\n')[0]}`); server.close(); process.exit(2); }
try {
  for (const w of [360, 390, 412]) {
    for (const ed of ['ie', 'uk']) {
      const ctx = await browser.newContext({ viewport: { width: w, height: 800 }, isMobile: true, hasTouch: true, deviceScaleFactor: 1 });
      await ctx.addInitScript(() => { try { localStorage.setItem('gj-consent', '{"essential":true,"analytics":false,"marketing":false}'); } catch { /* off */ } });
      const page = await ctx.newPage();
      const errors = [];
      page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
      const jobs = emailJobs(ed);
      // R4-4 + R4-2 on a job page
      await page.goto(BASE + jobs[0], { waitUntil: 'load' });
      const hdr = await page.evaluate(() => {
        const a = [...document.querySelectorAll('.hdr .edsw a')].filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
        const sw = document.querySelector('.hdr .edsw');
        const r = sw ? sw.getBoundingClientRect() : null;
        return { n: a.length, inside: !!r && r.left >= 0 && r.right <= window.innerWidth, sw: document.documentElement.scrollWidth };
      });
      check(hdr.n === 2 && hdr.inside && hdr.sw <= w, `R4-4 ${ed} @${w}: IE/UK switch visible inside the header (${hdr.n} links, inside ${hdr.inside}, scrollWidth ${hdr.sw})`);
      const crumb = await page.evaluate(() => {
        const nav = document.querySelector('.crumbs');
        const kids = [...nav.children];
        const tops = new Set(kids.map((k) => Math.round(k.getBoundingClientRect().top)));
        const last = kids[kids.length - 1];
        const tr = (e) => { const g = document.createRange(); g.selectNodeContents(e); return g.getBoundingClientRect(); };
        const gaps = kids.filter((k) => k.tagName === 'SPAN').map((s) => {
          const i = kids.indexOf(s);
          const l = tr(kids[i - 1]), m = tr(s), r = tr(kids[i + 1]);
          return Math.abs((m.left - l.right) - (r.left - m.right));
        });
        return { lines: tops.size, endsWithSep: last.tagName === 'SPAN', maxGapDiff: Math.max(0, ...gaps), ow: nav.scrollWidth <= nav.clientWidth + 1 };
      });
      check(crumb.lines === 1 && !crumb.endsWithSep && crumb.ow, `R4-2 ${ed} @${w}: breadcrumb on one line, no trailing slash (${crumb.lines} line(s))`);
      check(crumb.maxGapDiff <= 3, `R4-2 ${ed} @${w}: breadcrumb slashes have equal space either side (diff ${crumb.maxGapDiff.toFixed(1)}px)`);
      // consent checkbox element
      const box = await page.evaluate(() => { const r = document.querySelector('#ap-consent').getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; });
      check(box[0] >= 44 && box[1] >= 44, `m2 ${ed} @${w}: consent checkbox hit area ${box.join('x')} (>= 44x44)`);
      const glyph = await page.evaluate(() => parseFloat(getComputedStyle(document.querySelector('#ap-consent'), '::before').width));
      check(glyph >= 20 && glyph <= 26, `m2 ${ed} @${w}: consent glyph stays ${glyph}px`);
      // R4-1 scroll the confirmation into view
      await page.route('**/api/apply**', (r) => r.fulfill({ status: 201, contentType: 'application/json', body: '{"status":"received","delivery":"dry_run"}' }));
      await page.fill('#ap-name', 'Test Person');
      await page.fill('#ap-email', 'reviewer+test@example.com');
      await page.check('#ap-consent');
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.click('form[data-apply-form] [type="submit"]');
      await page.waitForFunction(() => /Application received/.test(document.body.innerText), null, { timeout: 5000 }).catch(() => {});
      await page.waitForTimeout(1200);
      const st = await page.evaluate(() => {
        const el = [...document.querySelectorAll('form[data-apply-form] *')].filter((e) => e.children.length === 0 && /Application received/.test(e.textContent))[0];
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return { top: Math.round(r.top), bottom: Math.round(r.bottom), vh: window.innerHeight };
      });
      check(st !== null && st.top >= 0 && st.bottom <= st.vh - 40, `R4-1 ${ed} @${w}: confirmation fully inside the viewport after send (${st ? `${st.top}..${st.bottom} of ${st.vh}` : 'not found'})`);
      // jobs list: chips, card click view-transition names
      await page.goto(BASE + `/${ed}/jobs/?q=a`, { waitUntil: 'load' });
      await page.waitForTimeout(300);
      const chips = await page.evaluate(() => [...document.querySelectorAll('.chip button')].map((b) => { const r = b.getBoundingClientRect(); return Math.round(r.width) + 'x' + Math.round(r.height); }));
      check(chips.length > 0 && chips.every((c) => { const [a, b] = c.split('x').map(Number); return a >= 44 && b >= 44; }), `m2 ${ed} @${w}: filter chip x is >= 44x44 (${chips.join(',') || 'no chip'})`);
      errors.length = 0;
      await page.click('.role h3 a, .row h3 a');
      await page.waitForLoadState('load');
      await page.waitForTimeout(500);
      check(!errors.some((e) => /duplicate view-transition-name/i.test(e)), `R4-3 ${ed} @${w}: card click logs no duplicate view-transition-name error`);
      const names = await page.evaluate(() => {
        const n = [...document.querySelectorAll('*')].map((e) => getComputedStyle(e).viewTransitionName).filter((x) => x && x !== 'none');
        return { total: n.length, unique: new Set(n).size, h1: getComputedStyle(document.querySelector('h1.vt-title')).viewTransitionName };
      });
      check(names.total === names.unique && /^jt-/.test(names.h1), `R4-3 ${ed} @${w}: job page names are unique and the title has its own (${names.h1})`);
      // map: tap discs (home page)
      await page.goto(BASE + `/${ed}/`, { waitUntil: 'load' });
      const map = await page.evaluate(() => {
        const svg = document.querySelector('svg.gmap');
        if (!svg) return null;
        const hits = [...svg.querySelectorAll('.gmap__r .gmap__hit')];
        const regions = svg.querySelectorAll('.gmap__r').length;
        const min = Math.min(...hits.map((h) => { const r = h.getBoundingClientRect(); return Math.min(r.width, r.height); }));
        const pe = hits.length ? getComputedStyle(hits[0]).pointerEvents : 'none';
        return { hits: hits.length, regions, min: Math.round(min), pe, list: [...document.querySelectorAll('.maplist a')].filter((a) => a.getBoundingClientRect().height > 0).map((a) => Math.round(a.getBoundingClientRect().height)) };
      });
      if (ed === 'uk') {
        check(map !== null && map.hits === map.regions && map.min >= 44 && map.pe === 'all', `m2 uk @${w}: every map region has a >= 44px tap disc on touch (${map ? `${map.hits}/${map.regions}, min ${map.min}px, ${map.pe}` : 'no map'})`);
      }
      if (map && map.list.length) check(Math.min(...map.list) >= 44, `m2 ${ed} @${w}: map region list links >= 44px tall (min ${Math.min(...map.list)})`);
      await ctx.close();
    }
  }
} finally {
  await browser.close();
  server.close();
}
const fails = results.filter((x) => !x).length;
console.log(`r4 layout: ${results.length - fails} pass, ${fails} fail`);
process.exit(fails ? 1 : 0);
