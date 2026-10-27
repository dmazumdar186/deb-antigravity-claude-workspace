#!/usr/bin/env node
/* screens.mjs — reviewer screens for brief_v3 §5. Clears screens/ first.
   usage: node research/serve_csp.mjs site 8794 &  node research/screens.mjs http://localhost:8794/
   States are reached by scrolling within 200 ms of load (the scroll takes over before autoplay), pos = s + .05.
   outputs: screens/*.png, research/screens.json {files, consoleErrors} */
import { createRequire } from 'node:module'; import { writeFileSync, rmSync, mkdirSync } from 'node:fs';
process.env.PLAYWRIGHT_BROWSERS_PATH ||= '/opt/pw-browsers';
const { chromium, devices } = createRequire('/opt/node22/lib/node_modules/')('playwright');
const base = (process.argv[2] || 'http://localhost:8794/').replace(/\/?$/, '/');
const only = process.argv[3] ? new RegExp(process.argv[3]) : null;
const out = new URL('../screens/', import.meta.url).pathname; if (!only) rmSync(out, { recursive: true, force: true }); mkdirSync(out, { recursive: true });
export const VP = { 'iphone-se': [375, 667, 1], 'galaxy-s8': [360, 740, 1], 'iphone-13': [390, 844, 1], 'pixel-7': [412, 915, 1], 'iphone-15-pro-max': [430, 932, 1], 'phone-landscape': [844, 390, 1], 'small-tablet': [600, 960, 1], 'ipad-portrait': [820, 1180, 0], 'ipad-landscape': [1180, 820, 0], 'ipad-pro-portrait': [1024, 1366, 0], 'ipad-pro-landscape': [1366, 1024, 0], 'laptop-1280': [1280, 800, 0], 'laptop-1440': [1440, 900, 0], 'laptop-1536': [1536, 864, 0], 'desktop-1080p': [1920, 1080, 0], 'desktop-1440p': [2560, 1440, 0], 'desktop-4k': [3840, 2160, 0], 'tv-portrait': [1080, 1920, 0], 'mobile-pixel7-device': 'Pixel 7' };
const files = []; const errs = [];
const b = await chromium.launch();
const spec = (s) => typeof s === 'string' ? { ...devices[s] } : { viewport: { width: s[0], height: s[1] }, isMobile: !!s[2], hasTouch: !!s[2], deviceScaleFactor: 1 };
async function page(opts, { seen = true, lang = 'en' } = {}) {
  const ctx = await b.newContext(opts); const p = await ctx.newPage();
  p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
  await p.route('**/api/**', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: '{"ok":true}' }));
  await p.route('https://static.cloudflareinsights.com/**', (r) => r.fulfill({ status: 200, contentType: 'text/javascript', body: '' }));
  await p.addInitScript(([s, l]) => { if (s) localStorage.setItem('jv-news-seen', '1'); localStorage.setItem('jv-lang', l); }, [seen, lang]);
  p._ctx = ctx; return p;
}
const shot = async (p, name, full = false) => { if (only && !only.test(name)) return; await p.screenshot({ path: out + name + '.png', fullPage: full }); files.push(name + '.png'); };
const yFor = (p, s) => p.evaluate((s) => { const c = document.querySelector('[data-cover]'); const span = c.offsetHeight - innerHeight; const pp = s === 'hold' ? 1 : (s + 0.05) / 12; return Math.round(c.offsetTop + span * pp); }, s);
const scroll = (p, y) => p.evaluate((y) => { document.documentElement.style.scrollBehavior = 'auto'; scrollTo(0, y); }, y);
const KF = JSON.parse((await import('node:fs')).readFileSync(new URL('../site/assets/film/hero.json', import.meta.url), 'utf8')).keyframes_s;
const settle = (p, s) => p.waitForFunction(([t]) => { const e = window.__jv, v = document.querySelector('[data-film-video]'); return e && e.ready && !e.seeking && Math.abs(v.currentTime - t) <= 0.3; }, [KF[s === 'hold' ? 11 : s]], { timeout: 20000, polling: 100 }).catch(() => {});
const fresh = async (p, s, wait = 700) => { await p.goto(base, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(150); await scroll(p, await yFor(p, s)); await settle(p, s); await p.waitForTimeout(wait); }; // shots only after seeked + within 0.3 s
const toSel = async (p, sel, wait = 1200) => { await p.evaluate((sel) => { document.documentElement.style.scrollBehavior = 'auto'; const e = document.querySelector(sel); scrollTo(0, e.getBoundingClientRect().top + scrollY + (e.offsetHeight > innerHeight * 1.2 ? innerHeight * 0.25 : 0)); }, sel); await p.waitForTimeout(wait); };
const D = { viewport: { width: 1440, height: 900 } };
let p = await page(D);
await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(200); await shot(p, 'cover-s0-0s'); await p.waitForTimeout(5800); await shot(p, 'cover-s0-6s');
for (const s of [3, 7, 11]) { await fresh(p, s); await shot(p, 'cover-s' + s); }
await fresh(p, 'hold'); await shot(p, 'cover-hold');
for (const [i, id] of [[1, 'practice'], [2, 'classes'], [3, 'contact']]) { await toSel(p, '#' + id); await shot(p, 'chapter-0' + i); }
await toSel(p, '#classes'); await p.evaluate(() => document.querySelector('[data-sheet-open]').click()); await p.waitForTimeout(900); await p.fill('[data-reg] [name="name"]', 'Test'); await p.fill('[data-reg] [name="email"]', 't@example.com'); await p.check('[data-reg] [name="consent"]'); await p.click('[data-reg] button[type="submit"]'); await p.waitForTimeout(900); await shot(p, 'register-success');
await p._ctx.close();
p = await page(D, { seen: false }); await p.goto(base, { waitUntil: 'load' }); await toSel(p, '#practice', 2600); await shot(p, 'dialog'); await p._ctx.close();
p = await page(D); await p.goto(base + 'privacy/', { waitUntil: 'load' }); await p.waitForTimeout(400); await shot(p, 'privacy'); await p._ctx.close();
p = await page(D, { lang: 'fr' }); await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(600); await shot(p, 'lang-fr-cover'); await p._ctx.close();
p = await page(D); await p.goto(base + '?static=1', { waitUntil: 'load' }); await p.waitForTimeout(900); await shot(p, 'page-full-static', true); await p._ctx.close();
p = await page(spec('Pixel 7'));
await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(600); await shot(p, 'mobile-cover');
await fresh(p, 7); await shot(p, 'mobile-cover-s7'); await fresh(p, 'hold'); await shot(p, 'mobile-cover-hold');
await toSel(p, '#practice', 800); await p.evaluate(() => { const c = document.querySelector('[data-cover]'); window.__top = c.offsetTop + c.offsetHeight; });
if (!only || only.test('mobile-chapters')) { const top = await p.evaluate(() => window.__top); const h = await p.evaluate(() => document.documentElement.scrollHeight); await p.screenshot({ path: out + 'mobile-chapters.png', fullPage: true, clip: { x: 0, y: top, width: 412, height: h - top } }); files.push('mobile-chapters.png'); }
await p._ctx.close();
for (const [name, s] of Object.entries(VP)) {
  if (only && !only.test('vp-' + name)) continue;
  p = await page(spec(s));
  for (const st of [0, 7, 'hold']) { if (st === 0) { await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(150); await scroll(p, await yFor(p, 0)); await settle(p, 0); await p.waitForTimeout(500); } else await fresh(p, st, 1400); await shot(p, `vp-${name}-${st === 'hold' ? 'hold' : 's' + st}`); }
  await p._ctx.close();
}
await b.close();
writeFileSync(new URL('./screens.json', import.meta.url), JSON.stringify({ files, consoleErrors: errs }, null, 1));
console.log(files.length, 'screens;', errs.length, 'console errors', errs.slice(0, 3));
