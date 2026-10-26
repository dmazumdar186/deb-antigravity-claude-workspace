#!/usr/bin/env node
/* screens.mjs — reviewer screens (concept_recipe §8 + brief extras + 18-viewport cover matrix at 0/50/100 %).
   usage: node research/screens.mjs http://localhost:8794/   -> screens/*.png, research/screens.json (cover geometry per viewport). */
import { createRequire } from 'node:module'; import { writeFileSync } from 'node:fs';
process.env.PLAYWRIGHT_BROWSERS_PATH ||= '/opt/pw-browsers';
const { chromium, devices } = createRequire(import.meta.url)('playwright');
const base = (process.argv[2] || 'http://localhost:8794/').replace(/\/?$/, '/');
const out = new URL('../screens/', import.meta.url).pathname; const files = []; const geo = {}; const errs = [];
const b = await chromium.launch();
async function page(opts, seen = true) { const ctx = await b.newContext(opts); const p = await ctx.newPage(); p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => { if (m.type() === 'error' && !/fonts\.g|ERR_/.test(m.text())) errs.push(m.text()); }); await p.route('**/api/**', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: '{"ok":true}' })); if (seen) await p.addInitScript(() => { localStorage.setItem('jv-news-seen', '1'); localStorage.setItem('jv-lang', 'en'); }); p._ctx = ctx; return p; }
const go = async (p, y, wait = 1600) => { await p.evaluate((v) => { document.documentElement.style.scrollBehavior = 'auto'; scrollTo(0, v); }, y); await p.waitForTimeout(wait); };
const tr = (p, sel, f) => p.evaluate(([s, f]) => { const el = document.querySelector(s); return el.offsetTop + (el.offsetHeight - innerHeight) * f; }, [sel, f]);
const shot = async (p, name, full = false) => { await p.screenshot({ path: out + name + '.png', fullPage: full }); files.push(name + '.png'); };
// desktop
let p = await page({ viewport: { width: 1440, height: 900 } });
await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(300); await shot(p, 'cover-autoplay-0s');
await p.waitForTimeout(3700); await shot(p, 'cover-autoplay-4s');
for (const [n, f] of [['cover-0', 0], ['cover-50', 0.5], ['cover-100', 0.79], ['cover-fade', 0.93]]) { await go(p, await tr(p, '[data-cover]', f)); await shot(p, n); }
await go(p, await tr(p, '[data-fold]', 0.5)); await shot(p, 'foldout-mid');
await go(p, await tr(p, '[data-fold]', 1)); await shot(p, 'foldout-open');
for (const id of ['about', 'classes', 'register', 'contact']) { await p.evaluate(() => document.querySelector('#deck').scrollIntoView()); await p.click(`[data-tab="${id}"]`); await p.waitForTimeout(1600); await p.evaluate(() => document.querySelector('#deck').scrollIntoView()); await p.waitForTimeout(400); await shot(p, 'deck-' + id); }
await go(p, 0, 400); await shot(p, 'page-full', true);
await p._ctx.close();
p = await page({ viewport: { width: 1440, height: 900 }, locale: 'fr-FR' }); await p.addInitScript(() => localStorage.setItem('jv-lang', 'fr'));
await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(1600); await shot(p, 'lang-fr-cover'); await p._ctx.close();
// mobile
p = await page({ ...devices['Pixel 7'] });
await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(1600); await shot(p, 'mobile-cover');
await go(p, await tr(p, '[data-cover]', 0.6)); await shot(p, 'mobile-cover-60');
await p.evaluate(() => document.querySelector('#practice').scrollIntoView()); await p.waitForTimeout(1200); await shot(p, 'mobile-foldout');
await p.evaluate(() => document.querySelector('#deck').scrollIntoView()); await p.waitForTimeout(1600); await shot(p, 'mobile-deck');
await p._ctx.close();
// 18-viewport cover matrix
const VP = { 'mobile': 'Pixel 7', 'iphone-se': [375, 667, 1], 'galaxy-s8': [360, 740, 1], 'iphone-13': [390, 844, 1], 'pixel-7': [412, 915, 1], 'iphone-15-pro-max': [430, 932, 1], 'phone-landscape': [844, 390, 1], 'small-tablet': [600, 960, 1], 'ipad-portrait': [820, 1180, 0], 'ipad-landscape': [1180, 820, 0], 'ipad-pro-portrait': [1024, 1366, 0], 'ipad-pro-landscape': [1366, 1024, 0], 'laptop-1280': [1280, 800, 0], 'laptop-1440': [1440, 900, 0], 'laptop-1536': [1536, 864, 0], 'desktop-1080p': [1920, 1080, 0], 'desktop-1440p': [2560, 1440, 0], 'desktop-4k': [3840, 2160, 0], 'tv-portrait': [1080, 1920, 0] };
for (const [name, spec] of Object.entries(VP)) {
  const [w, h, mob] = Array.isArray(spec) ? spec : [];
  p = await page(Array.isArray(spec) ? { viewport: { width: w, height: h }, isMobile: !!mob, hasTouch: !!mob, deviceScaleFactor: 1 } : { ...devices[spec] });
  await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(400);
  geo[name] = {};
  for (const f of [0, 50, 100]) {
    await go(p, await tr(p, '[data-cover]', f / 100), f === 0 ? 1400 : 1500);
    await shot(p, `${name}-cover-${f}`);
    geo[name][f] = await p.evaluate(() => {
      const box = (e) => { if (!e) return null; const r = e.getBoundingClientRect(); return r.width && getComputedStyle(e).visibility !== 'hidden' ? { l: r.left, t: r.top, r: r.right, b: r.bottom } : null; };
      const hit = (a, c) => !!(a && c && a.l < c.r - 1 && c.l < a.r - 1 && a.t < c.b - 1 && c.t < a.b - 1);
      const beat = document.querySelector('[data-beat].is-on'); const kids = beat ? [...beat.children] : [];
      const bb = kids.map(box).filter(Boolean).reduce((u, x) => u ? { l: Math.min(u.l, x.l), t: Math.min(u.t, x.t), r: Math.max(u.r, x.r), b: Math.max(u.b, x.b) } : x, null);
      const rail = [...document.querySelectorAll('.rail > *')].map(box).filter(Boolean).reduce((u, x) => u ? { l: Math.min(u.l, x.l), t: Math.min(u.t, x.t), r: Math.max(u.r, x.r), b: Math.max(u.b, x.b) } : x, null);
      const portrait = matchMedia('(orientation: portrait)').matches; const fr = box(document.querySelector('[data-frame]'));
      const hdr = box(document.querySelector('.hdr__nav'));
      const im = document.querySelector('[data-frame] .cover__img.is-on'); const plateOk = !!(im && im.complete && im.naturalWidth > 0 && getComputedStyle(im).opacity === '1');
      const BG = /^(cover__pin|cover__grid|cover__stage|cover__canvas|cover__video|cover__echo|cover__body|fold|fold__pin|spread|deck|dp|about|about__text)$/;
      let run = 0, worst = 0; for (let y = innerHeight * 0.01; y < innerHeight; y += innerHeight * 0.02) { const empty = [0.15, 0.5, 0.85].every((fx) => { const e = document.elementFromPoint(innerWidth * fx, y); if (!e) return true; const c = typeof e.className === 'string' ? e.className.split(' ')[0] : ''; return ['MAIN', 'BODY', 'HTML', 'SECTION'].includes(e.tagName) && !c || BG.test(c); }); run = empty ? run + 1 : 0; worst = Math.max(worst, run); }
      const emptyBand = +(worst * 0.02).toFixed(2);
      return { portrait, plateOk, emptyBand, textRail: hit(bb, rail), textFrame: portrait ? false : hit(bb, fr), railFrame: portrait ? false : hit(rail, fr), textOff: bb ? bb.t < 0 || bb.b > innerHeight || bb.l < 0 || bb.r > innerWidth : null, textHdr: hit(bb, hdr), railHdr: hit(rail, hdr) };
    });
  }
  await p._ctx.close();
}
await b.close();
const bad = Object.entries(geo).flatMap(([n, g]) => Object.entries(g).filter(([, v]) => v.emptyBand > 0.25 || !v.plateOk || v.textRail || v.textFrame || v.railFrame || v.textOff || v.textHdr || v.railHdr).map(([f, v]) => `${n}@${f}: ${JSON.stringify(v)}`));
writeFileSync(new URL('./screens.json', import.meta.url).pathname, JSON.stringify({ files, geometryIssues: bad, consoleErrors: errs, geo }, null, 1));
console.log(files.length + ' screens; geometry issues: ' + bad.length); bad.forEach((x) => console.log('  ' + x)); console.log('console errors: ' + errs.length, errs.slice(0, 3));
