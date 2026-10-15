#!/usr/bin/env node
/* measure_live.mjs — measure a LIVE site for the pitch table (Today column).
   usage: node measure_live.mjs <url> [--out research/live_metrics.json] [--help]
   outputs JSON on stdout: { source, measured, desktop1440:{scrollHeight,viewports}, mobile390:{scrollHeight,viewports}, links, words }
   (the shape MISB v3 used in research/live_metrics_v3.json). Desktop = 1440x900, mobile = 390x844 (iPhone 13 class, touch).
   Scrolls the page to the bottom first so lazy sections mount. No secrets, no cookies, identifying User-Agent only. */
import { createRequire } from 'node:module';
import { writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const argv = process.argv.slice(2);
if (!argv[0] || argv.includes('--help') || argv.includes('-h')) {
  console.log('measure_live.mjs <url> [--out research/live_metrics.json] — prints desktop/mobile scrollHeight + viewports, link and word counts as JSON');
  process.exit(argv[0] ? 0 : 2);
}
const url = argv[0];
const oi = argv.indexOf('--out'); const out = oi > -1 ? resolve(argv[oi + 1]) : null;
process.env.PLAYWRIGHT_BROWSERS_PATH ||= '/opt/pw-browsers';
const require = createRequire(import.meta.url);
let pw; for (const p of ['/opt/node-tools/node_modules/playwright', resolve('node_modules/playwright'), '/tmp/pwtest/node_modules/playwright', 'playwright']) { try { pw = require(p); break; } catch {} }
if (!pw) { console.error('playwright not found (npm i playwright@1.56 in /tmp/pwtest or the repo)'); process.exit(2); }
const { chromium } = pw;
const UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36 ProdCraft-measure/1.0';
const b = await chromium.launch();
async function measure(vp, mobile) {
  const p = await b.newPage({ viewport: vp, isMobile: mobile, hasTouch: mobile, userAgent: UA });
  try {
    await p.goto(url, { waitUntil: 'load', timeout: 60000 });
    await p.waitForTimeout(1200);
    await p.evaluate(async () => { for (let y = 0; y < document.documentElement.scrollHeight; y += 700) { window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 120)); } window.scrollTo(0, 0); });
    await p.waitForTimeout(600);
    return await p.evaluate((h) => ({ scrollHeight: document.documentElement.scrollHeight, viewports: +(document.documentElement.scrollHeight / h).toFixed(1),
      links: document.querySelectorAll('a[href]').length, words: (document.body.innerText || '').trim().split(/\s+/).filter(Boolean).length }), vp.height);
  } finally { await p.close(); }
}
const d = await measure({ width: 1440, height: 900 }, false);
const m = await measure({ width: 390, height: 844 }, true);
await b.close();
const res = { source: url, measured: new Date().toISOString().slice(0, 10), desktop1440: { scrollHeight: d.scrollHeight, viewports: d.viewports }, mobile390: { scrollHeight: m.scrollHeight, viewports: m.viewports }, links: d.links, words: d.words };
const json = JSON.stringify(res);
if (out) writeFileSync(out, json + '\n');
console.log(json);
