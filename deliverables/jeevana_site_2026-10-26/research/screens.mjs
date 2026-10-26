#!/usr/bin/env node
/* screens.mjs — reviewer screens for the v2 cover (brief_v2 "Verify"): named cover states, the 19-viewport matrix at
   s0/s5/s11/hold, the deck/dialog/mobile set, page-full (static + scrolled).
   usage: node research/serve_csp.mjs site 8794 &  node research/screens.mjs http://localhost:8794/
   outputs: screens/*.png, research/screens.json {files, consoleErrors, geo:{viewport:{state:{figH, ground, textHit}}}} */
import { createRequire } from 'node:module'; import { writeFileSync } from 'node:fs';
process.env.PLAYWRIGHT_BROWSERS_PATH ||= '/opt/pw-browsers';
const { chromium, devices } = createRequire('/opt/node22/lib/node_modules/')('playwright');
const base = (process.argv[2] || 'http://localhost:8794/').replace(/\/?$/, '/');
const out = new URL('../screens/', import.meta.url).pathname; const files = []; const geo = {}; const errs = [];
const VP = { 'mobile': 'Pixel 7', 'iphone-se': [375, 667, 1], 'galaxy-s8': [360, 740, 1], 'iphone-13': [390, 844, 1], 'pixel-7': [412, 915, 1], 'iphone-15-pro-max': [430, 932, 1], 'phone-landscape': [844, 390, 1], 'small-tablet': [600, 960, 1], 'ipad-portrait': [820, 1180, 0], 'ipad-landscape': [1180, 820, 0], 'ipad-pro-portrait': [1024, 1366, 0], 'ipad-pro-landscape': [1366, 1024, 0], 'laptop-1280': [1280, 800, 0], 'laptop-1440': [1440, 900, 0], 'laptop-1536': [1536, 864, 0], 'desktop-1080p': [1920, 1080, 0], 'desktop-1440p': [2560, 1440, 0], 'desktop-4k': [3840, 2160, 0], 'tv-portrait': [1080, 1920, 0] };
const b = await chromium.launch();
async function page(opts, { seen = true, lang = 'en' } = {}) {
  const ctx = await b.newContext(opts); const p = await ctx.newPage();
  p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => { if (m.type() === 'error' && !/cloudflareinsights|ERR_TUNNEL|ERR_PROXY/.test(m.text())) errs.push(m.text()); });
  await p.route('**/api/**', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: '{"ok":true}' }));
  await p.route('https://static.cloudflareinsights.com/**', (r) => r.fulfill({ status: 200, contentType: 'text/javascript', body: '' }));
  await p.addInitScript(([s, l]) => { if (s) localStorage.setItem('jv-news-seen', '1'); localStorage.setItem('jv-lang', l); }, [seen, lang]);
  p._ctx = ctx; return p;
}
const spec = (s) => Array.isArray(s) ? { viewport: { width: s[0], height: s[1] }, isMobile: !!s[2], hasTouch: !!s[2], deviceScaleFactor: 1 } : { ...devices[s] };
const shot = async (p, name, full = false) => { await p.screenshot({ path: out + name + '.png', fullPage: full }); files.push(name + '.png'); };
const y4 = (p, s) => p.evaluate((s) => { const c = document.querySelector('[data-cover]'), f = document.querySelector('[data-fold]'); const span = c.offsetHeight - innerHeight - Math.max(0, -parseFloat(getComputedStyle(f).marginTop) || 0); const pp = s === 'hold' ? 1 : Math.min(1, (s >= 12 ? 12 : s + 0.05) / 12 * 0.92); return Math.round(c.offsetTop + span * pp); }, s);
const goS = async (p, s, wait = 1300) => { await p.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; scrollTo(0, 400); }); await p.waitForTimeout(60); const y = await y4(p, s); await p.evaluate((y) => scrollTo(0, y), y); await p.waitForTimeout(wait); };
const go = async (p, y, wait = 1200) => { await p.evaluate((v) => { document.documentElement.style.scrollBehavior = 'auto'; scrollTo(0, v); }, y); await p.waitForTimeout(wait); };
const fy = (p, f) => p.evaluate((f) => { const e = document.querySelector('[data-fold]'); return e.offsetTop + (e.offsetHeight - innerHeight) * f; }, f);

// desktop named cover states
let p = await page({ viewport: { width: 1440, height: 900 } });
await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(250); await shot(p, 'cover-s0-0s');
await p.waitForTimeout(2750); await shot(p, 'cover-s0-3s');
for (const s of [2, 5, 9, 11]) { await goS(p, s); await shot(p, 'cover-s' + s); }
await goS(p, 'hold'); await shot(p, 'cover-hold');
await go(p, await fy(p, 0.35)); await shot(p, 'foldout-mid');
await go(p, await fy(p, 1)); await shot(p, 'foldout-open');
for (const id of ['about', 'classes', 'register', 'contact']) { await p.evaluate(() => document.querySelector('#deck').scrollIntoView()); await p.click(`[data-tab="${id}"]`); await p.waitForTimeout(1500); await p.evaluate(() => document.querySelector('#deck').scrollIntoView()); await p.waitForTimeout(300); await shot(p, 'deck-' + id); }
await p.click('[data-tab="register"]'); await p.fill('[data-reg] [name="name"]', 'Test'); await p.fill('[data-reg] [name="email"]', 't@example.com'); await p.check('[data-reg] [name="consent"]', { force: true }); await p.click('[data-reg] button[type="submit"]'); await p.waitForTimeout(900); await shot(p, 'deck-register-success');
await p._ctx.close();
p = await page({ viewport: { width: 1440, height: 900 } }, { seen: false });
await p.goto(base + '#about', { waitUntil: 'load' }); await p.evaluate(() => document.querySelector('#deck').scrollIntoView()); await p.waitForTimeout(2200); await shot(p, 'newsletter-dialog'); await p._ctx.close();
p = await page({ viewport: { width: 1440, height: 900 } }, { lang: 'fr' }); await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(4200); await shot(p, 'lang-fr-cover'); await goS(p, 9); await shot(p, 'lang-fr-cover-s9'); await p._ctx.close();
p = await page({ viewport: { width: 1440, height: 900 } }); await p.goto(base + '?static=1', { waitUntil: 'load' }); await p.waitForTimeout(1500); await shot(p, 'page-full-static', true); await p._ctx.close();
p = await page({ viewport: { width: 1440, height: 900 } }); await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(500);
for (let y = 0, H = await p.evaluate(() => document.documentElement.scrollHeight); y < H; y += 700) await go(p, y, 40);
await go(p, 0, 800); await shot(p, 'page-full', true); await p._ctx.close();
p = await page({ viewport: { width: 1440, height: 900 } }); await p.goto(base + 'privacy/', { waitUntil: 'load' }); await p.waitForTimeout(500); await shot(p, 'privacy'); await p._ctx.close();
// mobile named set
p = await page({ ...devices['Pixel 7'] });
await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(300); await shot(p, 'mobile-cover-s0-0s'); await p.waitForTimeout(3200); await shot(p, 'mobile-cover');
await goS(p, 5); await shot(p, 'mobile-cover-s5'); await goS(p, 11); await shot(p, 'mobile-cover-s11');
await p.evaluate(() => document.querySelector('#practice').scrollIntoView()); await p.waitForTimeout(1200); await shot(p, 'mobile-foldout');
await p.evaluate(() => document.querySelector('#deck').scrollIntoView()); await p.waitForTimeout(1500); await shot(p, 'mobile-deck');
await p.click('[data-tab="register"]'); await p.waitForTimeout(600); await p.evaluate(() => document.querySelector('#deck').scrollIntoView()); await p.waitForTimeout(300); await shot(p, 'mobile-deck-register');
await p._ctx.close();
// 19-viewport matrix
for (const [name, sp] of Object.entries(VP)) {
  p = await page(spec(sp)); await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(3800);
  geo[name] = {};
  for (const s of [0, 5, 11, 'hold']) {
    if (s === 0) await goS(p, 0, 1300); else await goS(p, s);
    await shot(p, `${name}-cover-s${s}`.replace('-shold', '-hold'));
    geo[name][s] = await p.evaluate(() => { const st = document.querySelector('[data-stage]').getBoundingClientRect(); const f = document.querySelector('.fig.is-on').getBoundingClientRect(); const g = parseFloat(getComputedStyle(document.querySelector('.fig.is-on')).getPropertyValue('--g')); return { key: document.querySelector('.fig.is-on').dataset.key, figH: +(f.height / st.height).toFixed(3), figW: +(f.width / st.width).toFixed(3), feet: +((f.top + g * f.height - st.top) / st.height).toFixed(3) }; });
  }
  await p._ctx.close();
}
await b.close();
writeFileSync(new URL('./screens.json', import.meta.url).pathname, JSON.stringify({ date: new Date().toISOString().slice(0, 10), files, consoleErrors: errs, geo }, null, 1));
console.log(files.length + ' screens; console errors: ' + errs.length, errs.slice(0, 3));
