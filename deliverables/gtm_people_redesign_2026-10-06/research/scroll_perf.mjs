// Scroll smoothness probe: wheel 0→bottom in ~1.5 s while sampling rAF deltas. Usage: node scroll_perf.mjs http://localhost:8791/ before|after
import { createRequire } from 'node:module'; import { readFileSync, writeFileSync, existsSync } from 'node:fs';
const { chromium } = createRequire(import.meta.url)('/opt/node-tools/node_modules/playwright');
const base = process.argv[2] || 'http://localhost:8789/', label = process.argv[3] || 'after';
const out = new URL('./scroll_perf.json', import.meta.url);
const b = await chromium.launch(); const res = {};
for (const [name, vp, mobile] of [['desktop', { width: 1440, height: 900 }, false], ['mobile', { width: 390, height: 844 }, true]]) {
  const p = await b.newPage({ viewport: vp, isMobile: mobile, hasTouch: mobile, deviceScaleFactor: mobile ? 2 : 1 });
  await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(1500);
  await p.evaluate(() => { window.__d = []; let last = performance.now(); const f = (t) => { window.__d.push(t - last); last = t; if (window.__d.length < 400) requestAnimationFrame(f); }; requestAnimationFrame(f); });
  const total = await p.evaluate(() => document.documentElement.scrollHeight - innerHeight);
  const steps = 30; for (let i = 0; i < steps; i++) { await p.mouse.wheel(0, total / steps); await p.waitForTimeout(50); }
  await p.waitForTimeout(300);
  const d = (await p.evaluate(() => window.__d)).slice(1).sort((a, c) => a - c);
  const p95 = d[Math.floor(d.length * .95)], long = d.filter((x) => x > 33).length, mean = d.reduce((a, c) => a + c, 0) / d.length;
  res[name] = { frames: d.length, p95: +p95.toFixed(1), mean: +mean.toFixed(1), long };
  console.log(label, name, JSON.stringify(res[name])); await p.close();
}
await b.close();
const all = existsSync(out) ? JSON.parse(readFileSync(out, 'utf8')) : {}; all[label] = res; writeFileSync(out, JSON.stringify(all, null, 1));
