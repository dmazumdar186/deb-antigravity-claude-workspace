// Screens for site_v3 → ../screens_v3/. Usage: node screens_v3.mjs http://localhost:8793/
import { createRequire } from 'node:module'; import { mkdirSync } from 'node:fs';
const { chromium, devices } = createRequire(import.meta.url)('/opt/node-tools/node_modules/playwright');
process.env.PLAYWRIGHT_BROWSERS_PATH ||= '/opt/pw-browsers';
const base = process.argv[2] || 'http://localhost:8793/'; const out = new URL('../screens_v3/', import.meta.url).pathname; mkdirSync(out, { recursive: true });
const b = await chromium.launch();
const errs = [];
async function page(opts) { const p = await b.newPage(opts); p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); }); return p; }
const scrollTo = async (p, y) => { await p.evaluate((v) => { document.documentElement.style.scrollBehavior = 'auto'; window.scrollTo(0, v); }, y); await p.waitForTimeout(500); };
const trackY = async (p, sel, frac) => p.evaluate(([s, f]) => { const el = document.querySelector(s); return el.offsetTop + (el.offsetHeight - innerHeight) * f; }, [sel, frac]);
// desktop
let p = await page({ viewport: { width: 1440, height: 900 } });
await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(1200);
await p.screenshot({ path: out + 'cover-0.png' });
await scrollTo(p, await trackY(p, '[data-cover]', 0.5)); await p.waitForTimeout(400); await p.screenshot({ path: out + 'cover-50.png' });
await scrollTo(p, await trackY(p, '[data-cover]', 0.79)); await p.waitForTimeout(400); await p.screenshot({ path: out + 'cover-100.png' });
await scrollTo(p, await trackY(p, '[data-cover]', 0.93)); await p.waitForTimeout(400); await p.screenshot({ path: out + 'cover-fade.png' });
await scrollTo(p, await trackY(p, '[data-fold]', 0.45)); await p.screenshot({ path: out + 'foldout-mid.png' });
await scrollTo(p, await trackY(p, '[data-fold]', 1)); await p.screenshot({ path: out + 'foldout-open.png' });
await p.evaluate(() => document.querySelector('#deck').scrollIntoView()); await p.waitForTimeout(600); await p.screenshot({ path: out + 'deck-programs.png' });
for (const t of ['workstudy', 'career', 'hub', 'admissions', 'contact']) { await p.click('[data-tab="' + t + '"]'); await p.waitForTimeout(t === 'career' ? 1600 : 700); await p.screenshot({ path: out + 'deck-' + t + '.png' }); }
await p.goto(base + 'for-misb/', { waitUntil: 'load' }); await p.waitForTimeout(600); await p.screenshot({ path: out + 'pitch.png', fullPage: true });
await p.close();
// mobile
p = await page({ ...devices['Pixel 7'] });
await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(1000);
await p.screenshot({ path: out + 'mobile-cover.png' });
await scrollTo(p, await trackY(p, '[data-cover]', 0.6)); await p.screenshot({ path: out + 'mobile-cover-60.png' });
await p.evaluate(() => document.querySelector('#campus').scrollIntoView()); await p.waitForTimeout(600); await p.screenshot({ path: out + 'mobile-foldout.png' });
await p.evaluate(() => document.querySelector('#deck').scrollIntoView()); await p.waitForTimeout(600); await p.screenshot({ path: out + 'mobile-deck.png' });
await p.close(); await b.close();
console.log('screens written; console errors:', errs.length, errs.slice(0, 3));
