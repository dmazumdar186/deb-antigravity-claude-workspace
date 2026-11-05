// Performance: Playwright Chromium, desktop 1440 + Pixel 7 on slow 4G; TTFB/LCP/CLS/weight; 30 concurrent catalogue GETs.
import { writeFileSync } from 'node:fs';
const { chromium, devices } = await import(new URL('../../custom_demo/node_modules/playwright/index.mjs', import.meta.url));
const BASE = process.env.BASE || 'https://asset-voyages-demo.debanjan186.workers.dev';
const out = { base: BASE, pages: [], concurrent: null };
const pages = ['/', '/?discipline=Cardiologie', '/congres/congres-europeen-de-cardiologie-cg-0101'];
const profiles = { desktop1440: { viewport: { width: 1440, height: 900 } }, pixel7_slow4g: { ...devices['Pixel 7'] } };
const SLOW4G = { offline: false, downloadThroughput: (1.6 * 1024 * 1024) / 8, uploadThroughput: (750 * 1024) / 8, latency: 150 }; // Lighthouse slow-4G
const browser = await chromium.launch({ args: ['--no-sandbox'] });
for (const [pname, prof] of Object.entries(profiles)) for (const p of pages) {
  const runs = [];
  for (let i = 0; i < 3; i++) {
    const ctx = await browser.newContext({ ...prof, locale: 'fr-FR' }); const page = await ctx.newPage();
    if (pname !== 'desktop1440') { const c = await ctx.newCDPSession(page); await c.send('Network.enable'); await c.send('Network.emulateNetworkConditions', SLOW4G); await c.send('Emulation.setCPUThrottlingRate', { rate: 4 }); }
    let bytes = 0, reqs = 0; page.on('response', async (r) => { reqs++; try { const l = r.headers()['content-length']; bytes += l ? +l : (await r.body()).length; } catch {} });
    await page.addInitScript(() => { window.__lcp = 0; window.__cls = 0; new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lcp = e.startTime; }).observe({ type: 'largest-contentful-paint', buffered: true }); new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; }).observe({ type: 'layout-shift', buffered: true }); });
    await page.goto(BASE + p, { waitUntil: 'load' }); await page.waitForTimeout(1500);
    const m = await page.evaluate(() => { const n = performance.getEntriesByType('navigation')[0]; return { ttfb: n.responseStart, load: n.loadEventEnd, lcp: window.__lcp, cls: window.__cls }; });
    runs.push({ ...m, kb: Math.round(bytes / 1024), reqs }); await ctx.close();
  }
  const med = (k) => runs.map((r) => r[k]).sort((a, b) => a - b)[1];
  const row = { profile: pname, page: p, ttfb_ms: Math.round(med('ttfb')), lcp_ms: Math.round(med('lcp')), cls: +med('cls').toFixed(4), weight_kb: med('kb'), requests: med('reqs'), runs }; out.pages.push(row); console.log(pname, p, JSON.stringify({ ...row, runs: undefined }));
}
await browser.close();
// 30 concurrent catalogue GETs (single burst, no retries).
const ts = []; const codes = {}; const wall0 = performance.now();
await Promise.all(Array.from({ length: 30 }, async () => { const t = performance.now(); try { const r = await fetch(BASE + '/', { redirect: 'manual' }); await r.text(); codes[r.status] = (codes[r.status] || 0) + 1; } catch (e) { codes.err = (codes.err || 0) + 1; } ts.push(performance.now() - t); }));
ts.sort((a, b) => a - b); const q = (p) => Math.round(ts[Math.min(ts.length - 1, Math.ceil(p * ts.length) - 1)]);
out.concurrent = { n: 30, p50_ms: q(0.5), p95_ms: q(0.95), max_ms: Math.round(ts[ts.length - 1]), codes, wall_ms: Math.round(performance.now() - wall0) }; console.log('concurrent', JSON.stringify(out.concurrent));
// console list pages (sequential, 3 each) as equipe
const jar = {}; async function req(path, o = {}) { const h = { cookie: Object.entries(jar).map(([k, v]) => `${k}=${v}`).join('; ') }; let body; if (o.form) { h['content-type'] = 'application/x-www-form-urlencoded'; h.origin = BASE; body = new URLSearchParams(o.form).toString(); } const t = performance.now(); const r = await fetch(BASE + path, { method: o.method || 'GET', headers: h, body, redirect: 'manual' }); const text = await r.text(); for (const sc of r.headers.getSetCookie()) { const [kv] = sc.split(';'); const i = kv.indexOf('='); jar[kv.slice(0, i)] = kv.slice(i + 1); } return { status: r.status, text, ms: performance.now() - t }; }
const g = await req('/console/connexion'); await req('/console/connexion', { method: 'POST', form: { _token: /name="_token" value="([^"]+)"/.exec(g.text)[1], username: 'equipe', password: 'demo-asset' } });
out.console = {}; for (const u of ['/console', '/console/demandes', '/console/congres', '/console/gme']) { const a = []; let st; for (let i = 0; i < 5; i++) { const r = await req(u); a.push(r.ms); st = r.status; } a.sort((x, y) => x - y); out.console[u] = { status: st, median_ms: Math.round(a[2]), max_ms: Math.round(a[4]) }; } console.log('console', JSON.stringify(out.console));
writeFileSync(new URL('./logs/perf_result.json', import.meta.url), JSON.stringify(out, null, 1));
