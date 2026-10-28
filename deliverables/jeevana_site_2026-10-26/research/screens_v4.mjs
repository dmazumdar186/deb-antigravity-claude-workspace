// v4 screenshots: 1440/1024/390 × light, every section, + strip at cards 1, 6, 12 -> research/screens_v4/
import { createRequire } from 'node:module'; import { mkdirSync, readdirSync, unlinkSync } from 'node:fs';
const req = createRequire('/opt/node22/lib/node_modules/'); const { chromium } = req('playwright');
const BASE = process.argv[2] || 'http://localhost:8794'; const OUT = new URL('./screens_v4/', import.meta.url).pathname;
mkdirSync(OUT, { recursive: true }); for (const f of readdirSync(OUT)) unlinkSync(OUT + f);
const b = await chromium.launch(); const secs = ['top', 'about', 'practice', 'twelve', 'classes', 'paris', 'contact'];
for (const [w, h, mobile] of [[390, 844, true], [844, 390, true], [320, 568, true], [768, 1024, true], [1024, 768, true], [1366, 1024, true], [1440, 900, false], [1920, 1080, false], [2560, 1440, false], [3840, 2160, false]]) {
  const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, isMobile: mobile, hasTouch: mobile });
  const p = await ctx.newPage(); await p.route('**/cloudflareinsights.com/**', (r) => r.fulfill({ status: 200, body: '' }));
  await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  const sh = await p.evaluate(() => document.documentElement.scrollHeight);
  for (let y = 0; y < sh; y += 400) { await p.evaluate((v) => scrollTo(0, v), y); await p.waitForTimeout(80); }
  await p.evaluate(() => scrollTo(0, 0)); await p.waitForTimeout(2200);
  await p.screenshot({ path: `${OUT}${w}-01-top.png` });
  for (const [i, s] of secs.slice(1).entries()) {
    await p.evaluate((id) => { const el = document.getElementById(id); scrollTo(0, el.getBoundingClientRect().top + scrollY - 68); }, s); await p.waitForTimeout(900);
    await p.screenshot({ path: `${OUT}${w}-0${i + 2}-${s}.png` });
    if (mobile || s === 'classes') { await p.evaluate(() => scrollBy(0, innerHeight - 140)); await p.waitForTimeout(700); await p.screenshot({ path: `${OUT}${w}-0${i + 2}-${s}-b.png` }); }
  }
  // phones: the registration form and the footer, so the form and the footer seal are reviewed
  if (w <= 844) {
    for (const [sel, name] of [['#registration', '05-classes-form'], ['.site-footer', '07-contact-footer']]) {
      await p.evaluate((sel) => { const el = document.querySelector(sel); const hh = document.querySelector('header.bar').offsetHeight; const y = el.getBoundingClientRect().top + scrollY; scrollTo({ top: sel === '.site-footer' ? document.documentElement.scrollHeight : y - hh - 8, behavior: 'instant' }); }, sel); await p.waitForTimeout(900);
      await p.screenshot({ path: `${OUT}${w}-${name}.png` });
    }
  }
  // strip: as a visitor lands on it, the strip top just under the header (scrolling down, so a collapsing header is collapsed)
  for (const n of [1, 6, 12]) {
    await p.evaluate((n) => { JV_strip.go(n - 1); const el = document.querySelector('[data-strip]'); scrollTo({ top: el.getBoundingClientRect().top + scrollY - 300, behavior: 'instant' }); }, n); await p.waitForTimeout(250);
    await p.evaluate(() => { const el = document.querySelector('[data-strip]'); const hh = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--hfit')) || document.querySelector('header.bar').offsetHeight; scrollTo({ top: el.getBoundingClientRect().top + scrollY - hh, behavior: 'instant' }); }); await p.waitForTimeout(1300);
    await p.screenshot({ path: `${OUT}${w}-strip-${String(n).padStart(2, '0')}.png` });
  }
  await ctx.close();
}
await b.close(); console.log('screens ->', OUT, readdirSync(OUT).length);
