// Usage: node measure.mjs <url-or-file> → JSON metrics (initial scroll height, screens, words, offsets)
import { createRequire } from 'node:module';
const { chromium } = createRequire(import.meta.url)('/opt/node-tools/node_modules/playwright');
const target = process.argv[2];
const b = await chromium.launch(); const out = {};
for (const [name, vp] of [['desktop', { width: 1440, height: 900 }], ['mobile', { width: 390, height: 844 }]]) {
  const p = await b.newPage({ viewport: vp });
  await p.goto(target, { waitUntil: 'networkidle', timeout: 60000 });
  await p.waitForTimeout(500);
  out[name] = await p.evaluate(() => {
    const h = document.documentElement.scrollHeight;
    const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden'; };
    const visibleWords = [...document.querySelectorAll('body *')].filter(e => e.children.length === 0 && vis(e)).map(e => e.textContent).join(' ').split(/\s+/).filter(Boolean).length;
    const allWords = document.body.textContent.split(/\s+/).filter(Boolean).length;
    const find = t => { const el = [...document.querySelectorAll('h1,h2,h3,[data-panel],[id]')].find(e => (e.id || '').includes(t) || e.textContent.toLowerCase().includes(t)); return el ? Math.round(el.getBoundingClientRect().top + scrollY) : null; };
    return { scrollHeight: h, screens: +(h / innerHeight).toFixed(1), visibleWords, allWordsInDOM: allWords, pricingY: find('pricing'), salaryY: find('salar'), contactY: find('contact') };
  });
  await p.close();
}
await b.close(); console.log(JSON.stringify(out, null, 1));
