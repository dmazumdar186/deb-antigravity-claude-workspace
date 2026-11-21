// Phone layout checks in a real Chromium (eye review r2 N2, N3, N5, N7, m2), against a built board tree.
// description: serves the tree on 127.0.0.1, opens job pages (email-apply and link-apply), the home page and the jobs
//   list at every phone width from 360 to 430 px (isMobile, so an overflow widens the layout viewport as on an iPhone)
//   and asserts: no horizontal overflow and no description wider than the viewport (N3); the apply form's labels
//   sit above their inputs, inputs/button >= 44 px, the consent box >= 24 px in a >= 44 px row, and an empty submit
//   marks name, email and consent with visible errors (N2); breadcrumbs, footer links and the edition switch >= 44 px
//   (m2); at the end of the page the sticky apply bar covers nothing in the footer (N5); the "Where this role sits"
//   labels render at >= 11 px (N7); no "Demo redesign" wording (m1).
// inputs: argv[2] = the built site dir (a board build: build_site.py --board-site ...)
// outputs: PASS/FAIL lines; exit 1 on any FAIL, 2 when Playwright/Chromium cannot start (never a silent pass)
// Run: node tests/greenjobs_redesign/phone_layout.mjs .tmp/some_board_build
import { createServer } from 'node:http';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { createRequire } from 'node:module';
import { extname, join, normalize, resolve, sep } from 'node:path';

const require = createRequire(import.meta.url);
let pw = null;
for (const m of ['playwright', '/opt/node22/lib/node_modules/playwright']) {
  try { pw = require(m); break; } catch { /* next location */ }
}
const SITE = resolve(process.argv[2] || '');
if (!process.argv[2] || !existsSync(join(SITE, 'ie', 'index.html'))) { console.log(`FAIL  no built site at ${SITE}`); process.exit(1); }
if (!pw) { console.log('FAIL  playwright is not installed'); process.exit(2); }

export const WIDTHS = [360, 375, 390, 414, 430];
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

function jobPages(ed) {
  const dir = join(SITE, ed, 'jobs');
  const email = [];
  let link = null;
  for (const id of readdirSync(dir)) {
    const f = join(dir, id, 'index.html');
    if (!existsSync(f)) continue;
    const html = readFileSync(f, 'utf8');
    if (html.includes('data-apply-form')) email.push({ path: `/${ed}/jobs/${id}/`, len: html.length, sits: html.includes('class="sits__svg"') });
    else if (!link && html.includes('data-ev="apply_click"')) link = `/${ed}/jobs/${id}/`;
  }
  email.sort((a, b) => b.len - a.len); // the longest adverts are the likeliest to overflow
  const withChart = email.find((e) => e.sits);
  return { email: [...new Set([...email.slice(0, 3).map((e) => e.path), ...(withChart ? [withChart.path] : [])])], link };
}

const results = [];
const check = (ok, label) => { results.push(ok); console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}`); };

let browser;
try {
  browser = await pw.chromium.launch();
} catch (e) {
  console.log(`FAIL  chromium did not start: ${e.message.split('\n')[0]}`);
  server.close();
  process.exit(2);
}
try {
  for (const ed of ['ie', 'uk']) {
    const { email, link } = jobPages(ed);
    check(email.length > 0, `${ed}: at least one email-apply job page`);
    const pages = [...email, ...(link ? [link] : []), `/${ed}/`, `/${ed}/jobs/`];
    for (const w of WIDTHS) {
      const ctx = await browser.newContext({ viewport: { width: w, height: 800 }, isMobile: true, hasTouch: true, deviceScaleFactor: 1 });
      await ctx.addInitScript(() => { try { localStorage.setItem('gj-consent', '{"essential":true,"analytics":false,"marketing":false}'); } catch { /* storage off */ } });
      const page = await ctx.newPage();
      for (const path of pages) {
        await page.goto(BASE + path, { waitUntil: 'load' });
        const m = await page.evaluate(() => {
          const vw = window.innerWidth;
          const prose = [...document.querySelectorAll('.prose, article')].map((e) => Math.round(e.getBoundingClientRect().right));
          return { vw, sw: document.documentElement.scrollWidth, prose: Math.max(0, ...prose), demo: /Demo redesign/.test(document.body.innerText) };
        });
        check(m.sw <= m.vw && m.vw === w, `N3 ${ed} ${path} @${w}: no horizontal overflow (scrollWidth ${m.sw}, viewport ${m.vw})`);
        check(m.prose <= m.vw, `N3 ${ed} ${path} @${w}: description inside the viewport (right edge ${m.prose})`);
        if (w === 390) check(!m.demo, `m1 ${ed} ${path}: no "Demo redesign" wording`);
      }
      if (w === 390 || w === 360) {
        await page.goto(BASE + email[0], { waitUntil: 'load' });
        const f = await page.evaluate(() => {
          const form = document.querySelector('form[data-apply-form]');
          const fields = [...form.querySelectorAll('.field')].map((d) => {
            const l = d.querySelector('label').getBoundingClientRect(), i = d.querySelector('input,textarea').getBoundingClientRect();
            return { id: d.querySelector('input,textarea').id, above: l.bottom <= i.top + 1, h: Math.round(i.height), sameLeft: Math.abs(l.left - i.left) < 2 };
          });
          const box = form.querySelector('#ap-consent').getBoundingClientRect(), row = form.querySelector('label[for="ap-consent"]').getBoundingClientRect();
          const btn = form.querySelector('[type="submit"]').getBoundingClientRect();
          return { fields, box: Math.round(Math.min(box.width, box.height)), row: Math.round(row.height), btn: Math.round(btn.height) };
        });
        for (const x of f.fields) {
          check(x.above && x.sameLeft, `N2 ${ed} @${w}: label of #${x.id} sits above its input`);
          check(x.h >= 44, `N2 ${ed} @${w}: #${x.id} is ${x.h}px tall (>= 44)`);
        }
        check(f.box >= 24 && f.row >= 44, `N2 ${ed} @${w}: consent box ${f.box}px in a ${f.row}px row`);
        check(f.btn >= 44, `N2 ${ed} @${w}: send button ${f.btn}px`);
        // empty submit: per-field errors, nothing sent
        await page.click('form[data-apply-form] [type="submit"]');
        const errs = await page.evaluate(() => ['name', 'email', 'consent'].map((k) => {
          const el = document.querySelector(`form[data-apply-form] [name="${k}"]`), p = document.querySelector(`[data-apply-err="${k}"]`);
          return el.getAttribute('aria-invalid') === 'true' && !p.hidden && p.textContent.length > 5;
        }));
        check(errs.every(Boolean), `N2 ${ed} @${w}: empty submit marks name, email, consent (${errs})`);
        // tap targets (m2)
        const taps = await page.evaluate(() => {
          const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden'; };
          const out = [];
          for (const [sel, wMin] of [['.crumbs a', 0], ['.edsw a', 44], ['.ftr a', 0], ['.sits__table summary', 0]]) {
            for (const e of document.querySelectorAll(sel)) {
              if (!vis(e)) continue;
              const r = e.getBoundingClientRect();
              if (r.height < 44 || r.width < wMin) out.push(`${sel} "${(e.textContent || '').trim().slice(0, 20)}" ${Math.round(r.width)}x${Math.round(r.height)}`);
            }
          }
          return out;
        });
        check(taps.length === 0, `m2 ${ed} @${w}: phone tap targets >= 44px${taps.length ? ` (${taps.slice(0, 3).join('; ')})` : ''}`);
        // sticky bar vs footer at the end of the page (N5)
        await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
        await page.waitForTimeout(400);
        const cover = await page.evaluate(() => {
          const bar = document.querySelector('.job__sticky');
          if (!bar || getComputedStyle(bar).display === 'none') return [];
          const b = bar.getBoundingClientRect();
          if (b.top >= window.innerHeight) return [];
          return [...document.querySelectorAll('.ftr__bottom a, .ftr__bottom span, .ftr__social a')].filter((e) => {
            const r = e.getBoundingClientRect();
            return r.height > 0 && r.bottom > b.top + 1 && r.top < b.bottom;
          }).map((e) => (e.textContent || e.getAttribute('aria-label') || '').trim().slice(0, 20));
        });
        check(cover.length === 0, `N5 ${ed} @${w}: the sticky apply bar covers nothing in the footer${cover.length ? ` (${cover.join(', ')})` : ''}`);
        // the salary chart's labels stay readable (N7)
        let charted = false;
        for (const path of email) {
          await page.goto(BASE + path, { waitUntil: 'load' });
          const px = await page.evaluate(() => {
            const t = [...document.querySelectorAll('.sits__lbl, .sits__tick')];
            return t.length ? Math.min(...t.map((e) => e.getBoundingClientRect().height)) : null;
          });
          if (px === null) continue;
          check(px >= 11, `N7 ${ed} ${path} @${w}: chart labels ${px.toFixed(1)}px tall (>= 11)`);
          const doc = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
          check(doc, `N7 ${ed} ${path} @${w}: the chart scrolls inside its box, not the page`);
          charted = true;
          break;
        }
        check(charted, `N7 ${ed} @${w}: a job page with the salary chart was measured`);
      }
      await ctx.close();
    }
  }
} finally {
  await browser.close();
  server.close();
}
const fails = results.filter((x) => !x).length;
console.log(`phone layout: ${results.length - fails} pass, ${fails} fail`);
process.exit(fails ? 1 : 0);
