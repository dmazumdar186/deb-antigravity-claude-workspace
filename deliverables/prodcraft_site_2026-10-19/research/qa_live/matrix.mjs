// Live human-eye matrix: prodcraft.fyi across device classes, 16:9 and 9:16, several scroll states.
import pw from '/opt/node-tools/node_modules/playwright/index.js'; const { chromium } = pw;
import { mkdirSync, writeFileSync } from 'node:fs';
const BASE = process.argv[2] || 'https://prodcraft.fyi/'; const OUT = process.argv[3] || 'deliverables/prodcraft_site_2026-10-19/research/qa_live/shots';
mkdirSync(OUT, { recursive: true });
const VP = [
  ['phone-390x844', 390, 844, true], ['phone-412x915', 412, 915, true], ['phone-360x640', 360, 640, true],
  ['phone-land-844x390', 844, 390, true],
  ['tablet-s-600x960', 600, 960, true], ['tablet-s-land-960x600', 960, 600, true],
  ['ipad-820x1180', 820, 1180, true], ['ipad-land-1180x820', 1180, 820, true],
  ['ipadpro-1024x1366', 1024, 1366, true], ['ipadpro-land-1366x1024', 1366, 1024, true],
  ['laptop-1366x768', 1366, 768, false], ['laptop-1536x864', 1536, 864, false], ['mac-1440x900', 1440, 900, false], ['wide-1882x832', 1882, 832, false],
  ['fhd-1920x1080', 1920, 1080, false], ['qhd-2560x1440', 2560, 1440, false], ['uhd-3840x2160', 3840, 2160, false],
  ['portrait-tv-1080x1920', 1080, 1920, false],
];
const b = await chromium.launch(); const log = [];
for (const [tag, w, h, touch] of VP) {
  const c = await b.newContext({ viewport: { width: w, height: h }, isMobile: touch && w < 1000, hasTouch: touch, deviceScaleFactor: 1, ignoreHTTPSErrors: true });
  const p = await c.newPage(); const errs = []; p.on('pageerror', e => errs.push(String(e))); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await p.goto(BASE, { waitUntil: 'networkidle', timeout: 60000 }).catch(e => errs.push('nav ' + e.message));
  await p.waitForTimeout(1800);
  const info = await p.evaluate(() => {
    const f = document.querySelector('[data-plate="1"]'); const i = f && f.querySelector('img'); const hdr = document.querySelector('.hdr');
    const fr = f ? f.getBoundingClientRect() : null, ir = i ? i.getBoundingClientRect() : null;
    const icon = [...document.querySelectorAll('link[rel~="icon"]')].map(l => l.href);
    const v = document.querySelector('video');
    return { overflowX: document.documentElement.scrollWidth > innerWidth, plate: fr && { top: fr.top, bottom: fr.bottom, w: fr.width, imgW: ir.width, imgTop: ir.top, visible: getComputedStyle(f).opacity !== '0' }, hdrBottom: hdr ? hdr.getBoundingClientRect().bottom : null, icon, video: v ? { src: v.currentSrc.split('/').pop(), w: v.videoWidth, h: v.videoHeight, playing: !v.paused } : null, h: document.documentElement.scrollHeight };
  });
  await p.screenshot({ path: `${OUT}/${tag}-1-cover0.png` });
  const H = await p.evaluate(() => document.documentElement.scrollHeight);
  const cover = await p.evaluate(() => { const c = document.querySelector('[data-cover]'); return c ? c.offsetHeight : 0; });
  await p.evaluate(y => scrollTo(0, y), Math.round(cover * 0.55)); await p.waitForTimeout(900); await p.screenshot({ path: `${OUT}/${tag}-2-cover55.png` });
  const fy = (f) => p.evaluate((f) => { const l = document.querySelector('#ledger'); return Math.round(l.offsetTop + Math.max(0, l.offsetHeight - innerHeight) * f); }, f);
  await p.evaluate(y => scrollTo(0, y), await fy(0.6)); await p.waitForTimeout(900); await p.screenshot({ path: `${OUT}/${tag}-3-ledger.png` });
  await p.evaluate(y => scrollTo(0, y), await fy(0.95)); await p.waitForTimeout(900); await p.screenshot({ path: `${OUT}/${tag}-6-ledger95.png` });
  const deck = await p.evaluate(() => { const d = document.querySelector('#deck'); return d ? d.getBoundingClientRect().top + scrollY : 0; });
  await p.evaluate(y => scrollTo(0, y), Math.round(deck)); await p.waitForTimeout(900); await p.screenshot({ path: `${OUT}/${tag}-4-deck.png` });
  const tabs = await p.$$('[data-deck-nav] button, [data-deck-nav] a'); if (tabs[1]) { await tabs[1].click().catch(() => {}); await p.waitForTimeout(900); await p.screenshot({ path: `${OUT}/${tag}-5-deck-systems.png` }); }
  log.push({ tag, w, h, ...info, errors: errs }); console.log(tag, JSON.stringify({ ...info, errors: errs.length }));
  await c.close();
}
await b.close(); writeFileSync(`${OUT}/../matrix_log.json`, JSON.stringify(log, null, 1));
