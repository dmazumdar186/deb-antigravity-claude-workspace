#!/usr/bin/env node
/* site_check.mjs — desktop + mobile + reduced-motion gate for static concept sites.
   usage: node site_check.mjs --site <dir> [--port 8787] [--pages /,/pour-x/] [--fling 2600]
   exit 0 = pass. Needs playwright (npm i playwright@1.56) and PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers. */
import { spawn } from 'node:child_process';
import { mkdirSync, existsSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { createRequire } from 'node:module';

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > -1 ? process.argv[i + 1] : d; };
const site = resolve(arg('--site', 'site'));
const port = Number(arg('--port', '8787'));
const pages = arg('--pages', '/').split(',').filter(Boolean);
const fling = Number(arg('--fling', '2600'));
const out = join(site, '..', 'screens'); mkdirSync(out, { recursive: true });
process.env.PLAYWRIGHT_BROWSERS_PATH ||= '/opt/pw-browsers';
const require = createRequire(import.meta.url);
let pw; for (const p of [resolve('node_modules/playwright'), '/tmp/pwtest/node_modules/playwright', 'playwright']) { try { pw = require(p); break; } catch {} }
if (!pw) { console.error('playwright not found: run `npm i playwright@1.56` (in /tmp/pwtest or the repo)'); process.exit(2); }
const { chromium, devices } = pw;

const server = spawn('python3', ['-m', 'http.server', String(port), '--directory', site], { stdio: 'ignore' });
await new Promise((r) => setTimeout(r, 900));
const base = `http://localhost:${port}`;
const fails = []; const notes = [];
const fail = (m) => { fails.push(m); console.log('FAIL ' + m); };
const ok = (m) => console.log('ok   ' + m);

const contexts = [
  { name: 'desktop', opts: { viewport: { width: 1440, height: 900 } } },
  { name: 'pixel7', opts: { ...devices['Pixel 7'] } },
  { name: 'iphone13', opts: { ...devices['iPhone 13'] } },
  { name: 'pixel7-reduced', opts: { ...devices['Pixel 7'], reducedMotion: 'reduce' } },
];
const browser = await chromium.launch();
try {
  for (const c of contexts) {
    const ctx = await browser.newContext(c.opts);
    for (const path of pages) {
      const p = await ctx.newPage(); const errs = []; const hosts = new Set();
      p.on('pageerror', (e) => errs.push(e.message));
      p.on('console', (m) => { if (m.type() === 'error' && !/ERR_CERT|fonts\.g/.test(m.text())) errs.push(m.text()); });
      p.on('request', (r) => { const u = new URL(r.url()); if (!u.host.startsWith('localhost')) hosts.add(u.host); });
      const tag = `${c.name}${path.replace(/\//g, '_') || '_'}`;
      const resp = await p.goto(base + path, { waitUntil: 'load' });
      if (!resp || resp.status() !== 200) { fail(`${tag}: HTTP ${resp && resp.status()}`); continue; }
      await p.waitForTimeout(900);
      const mobile = !!c.opts.isMobile;
      // fling: nothing in view may still be transparent 150ms later
      await p.evaluate((y) => { document.documentElement.style.scrollBehavior = 'auto'; scrollTo(0, y); }, fling);
      await p.waitForTimeout(150);
      const hidden = await p.evaluate(() => [...document.querySelectorAll('.reveal,[data-reveal]')].filter((e) => { const r = e.getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight && r.height > 0 && getComputedStyle(e).opacity === '0'; }).length);
      hidden ? fail(`${tag}: ${hidden} reveal element(s) still invisible 150ms after a ${fling}px fling`) : ok(`${tag}: nothing hidden after fling`);
      await p.screenshot({ path: join(out, `check-${tag}-fling.png`) });
      // walk the page so late observers fire, then full-page metrics
      const sh = await p.evaluate(() => document.documentElement.scrollHeight);
      for (let y = 0; y < sh; y += 500) { await p.evaluate((v) => scrollTo(0, v), y); await p.waitForTimeout(60); }
      await p.evaluate(() => scrollTo(0, 0)); await p.waitForTimeout(400);
      const m = await p.evaluate((mobile) => {
        const vw = innerWidth; const overflow = document.documentElement.scrollWidth - vw;
        const smallTaps = [], smallInputs = [];
        if (mobile) {
          for (const el of document.querySelectorAll('a,button,input,select,[role=button]')) { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); if (cs.display === 'inline' && el.tagName === 'A') continue; /* prose links */
            if (r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && (r.height < 40 || r.width < 40) && !el.closest('.ticker,[data-ticker],footer,nav.legal')) smallTaps.push(`${el.tagName}.${(el.className && el.className.baseVal) ?? el.className} ${Math.round(r.width)}x${Math.round(r.height)}`); }
          for (const el of document.querySelectorAll('input,select,textarea')) { const fs = parseFloat(getComputedStyle(el).fontSize); if (fs < 16) smallInputs.push(`${el.tagName}#${el.id || el.name} ${fs}px`); }
        }
        // fixed bottom bar vs last primary CTA inside forms
        let overlap = null; const bar = [...document.querySelectorAll('*')].find((e) => { const cs = getComputedStyle(e); return cs.position === 'fixed' && cs.display !== 'none' && e.getBoundingClientRect().bottom >= innerHeight - 1 && e.getBoundingClientRect().height > 30 && e.getBoundingClientRect().height < 160; });
        if (bar) { const cta = document.querySelector('form button[type=submit],form .btn'); if (cta) { cta.scrollIntoView({ block: 'end' }); const cr = cta.getBoundingClientRect(), br = bar.getBoundingClientRect(); if (cr.bottom > br.top && cr.top < br.bottom) overlap = `${Math.round(cr.bottom - br.top)}px`; } }
        const stillHidden = [...document.querySelectorAll('.reveal,[data-reveal]')].filter((e) => getComputedStyle(e).opacity === '0' && e.getBoundingClientRect().height > 0).length;
        return { overflow, smallTaps: smallTaps.slice(0, 8), smallInputs, overlap, stillHidden, vw };
      }, mobile);
      m.overflow > 0 ? fail(`${tag}: horizontal overflow ${m.overflow}px at ${m.vw}`) : ok(`${tag}: no overflow`);
      m.stillHidden ? fail(`${tag}: ${m.stillHidden} reveal element(s) never shown after full walk`) : ok(`${tag}: all reveals shown`);
      if (mobile) { m.smallTaps.length ? fail(`${tag}: tap targets <40px: ${m.smallTaps.join(' | ')}`) : ok(`${tag}: tap targets ok`); m.smallInputs.length ? fail(`${tag}: inputs <16px: ${m.smallInputs.join(' | ')}`) : ok(`${tag}: inputs ≥16px`); }
      if (m.overlap) fail(`${tag}: fixed bottom bar overlaps the form CTA by ${m.overlap}`); else ok(`${tag}: bottom bar clear of CTA`);
      errs.length ? fail(`${tag}: ${errs.length} console/page error(s): ${errs[0].slice(0, 140)}`) : ok(`${tag}: console clean`);
      const third = [...hosts].filter((h) => !/fonts\.(googleapis|gstatic)\.com/.test(h)); if (third.length) fail(`${tag}: third-party hosts: ${third.join(', ')}`);
      if (c.name === 'desktop' || c.name === 'pixel7') await p.screenshot({ path: join(out, `check-${tag}-full.png`), fullPage: true });
      await p.screenshot({ path: join(out, `check-${tag}-top.png`) });
      await p.close();
    }
    await ctx.close();
  }
} finally { await browser.close(); server.kill(); }
console.log(`\n${fails.length ? 'FAILED' : 'PASSED'} — ${fails.length} failure(s). Screenshots: ${out}`);
process.exit(fails.length ? 1 : 0);
