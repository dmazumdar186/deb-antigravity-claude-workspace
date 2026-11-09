// Perf A. Usage: WP_BASE=http://127.0.0.1:9403 node perf_A.mjs
// Median of 3 runs of TTFB, LCP, CLS: catalogue + one congress page; desktop and Pixel 7 (slow-4G, 4x CPU). Plus 30 concurrent GETs.
import fs from 'fs';
import path from 'path';
import { launch, devices, BASE, LOGS, median, pct, sleep } from './common.mjs';

const lines = [];
const out = (s) => { console.log(s); lines.push(s); };
const browser = await launch();

// Find one congress URL.
const probe = await browser.newPage();
await probe.goto(BASE + '/?q=madrid', { waitUntil: 'load', timeout: 90000 });
const congressPath = new URL(await probe.locator('.asset-card__title a').first().getAttribute('href'), BASE).pathname;
await probe.close();
const PAGES = { catalogue: '/', congress: congressPath };
const SLOW4G = { offline: false, downloadThroughput: (1.6 * 1024 * 1024) / 8, uploadThroughput: (750 * 1024) / 8, latency: 150 };

async function measure(profile, url) {
  const opts = profile === 'mobile' ? { ...devices['Pixel 7'], locale: 'fr-FR' } : { viewport: { width: 1440, height: 900 }, locale: 'fr-FR' };
  const ctx = await browser.newContext(opts);
  const page = await ctx.newPage();
  await page.addInitScript(() => {
    window.__lcp = 0; window.__cls = 0;
    new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lcp = e.startTime; }).observe({ type: 'largest-contentful-paint', buffered: true });
    new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; }).observe({ type: 'layout-shift', buffered: true });
  });
  if (profile === 'mobile') {
    const cdp = await ctx.newCDPSession(page);
    await cdp.send('Network.enable');
    await cdp.send('Network.emulateNetworkConditions', SLOW4G);
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
  }
  await page.goto(BASE + url, { waitUntil: 'load', timeout: 120000 });
  await sleep(1500);
  const m = await page.evaluate(() => ({
    ttfb: performance.getEntriesByType('navigation')[0].responseStart,
    lcp: window.__lcp, cls: window.__cls,
  }));
  await ctx.close();
  return m;
}

const summary = {};
for (const profile of ['desktop', 'mobile']) {
  for (const [name, url] of Object.entries(PAGES)) {
    await measure(profile, url).catch(() => {}); // warm-up, discarded
    const runs = [];
    for (let i = 0; i < 3; i++) runs.push(await measure(profile, url));
    const r = { ttfb: median(runs.map((x) => x.ttfb)), lcp: median(runs.map((x) => x.lcp)), cls: median(runs.map((x) => x.cls)) };
    summary[`${profile}/${name}`] = r;
    out(`PERF ${profile} ${name} ${url} runs=${JSON.stringify(runs.map((x) => ({ ttfb: +x.ttfb.toFixed(0), lcp: +x.lcp.toFixed(0), cls: +x.cls.toFixed(4) })))} median ttfb=${r.ttfb.toFixed(0)}ms lcp=${r.lcp.toFixed(0)}ms cls=${r.cls.toFixed(4)}`);
  }
}
await browser.close();

// 30 concurrent catalogue GETs
const t = [];
let non200 = 0;
await Promise.all(Array.from({ length: 30 }, async () => {
  const s = performance.now();
  const r = await fetch(BASE + '/');
  await r.arrayBuffer();
  if (r.status !== 200) non200++;
  t.push(performance.now() - s);
}));
const p50 = pct(t, 50), p95 = pct(t, 95);
out(`CONC 30 concurrent GET / : p50=${p50.toFixed(0)}ms p95=${p95.toFixed(0)}ms max=${Math.max(...t).toFixed(0)}ms non200=${non200}`);

const verdicts = [];
for (const [k, r] of Object.entries(summary)) {
  verdicts.push(`${r.lcp <= 2500 ? 'PASS' : 'FAIL'} LCP<=2500 ${k} ${r.lcp.toFixed(0)}ms`);
  verdicts.push(`${r.cls <= 0.1 ? 'PASS' : 'FAIL'} CLS<=0.1 ${k} ${r.cls.toFixed(4)}`);
}
verdicts.push(`${p95 <= 800 ? 'PASS' : 'FAIL'} p95<=800 concurrent ${p95.toFixed(0)}ms`);
verdicts.push(`${non200 === 0 ? 'PASS' : 'FAIL'} concurrent non-200 count ${non200}`);
verdicts.forEach(out);
out('NOTE local Playground CLI (PHP-wasm + SQLite, 3 workers, 4 vCPU) is slower than real hosting; numbers are as measured.');
fs.writeFileSync(path.join(LOGS, 'perf.log'), lines.join('\n') + '\n');
process.exit(verdicts.some((v) => v.startsWith('FAIL')) ? 1 : 0);
