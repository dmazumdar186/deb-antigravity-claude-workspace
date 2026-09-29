#!/usr/bin/env node
/**
 * description: Screenshot matrix for human-eye QA. Loads every page in a plan JSON at each viewport/theme,
 *              performs optional actions (click/fill/scroll/emulate), captures PNGs + a DOM health record
 *              (console errors, failed requests, horizontal overflow, hidden-but-present controls), and writes
 *              an index.json the reviewer agents read one image at a time.
 * inputs:  --plan <plan.json> --base <http://host:port/> --out <dir> [--only <substr>] [--quick]
 *          plan.json: {"viewports":[{"name":"1440","w":1440,"h":900},...],"themes":["light","dark"],
 *                      "pages":[{"key":"ie/employers","path":"ie/employers/","actions":[{"click":"[data-adb-fill]"},{"scroll":"[data-adb-preview]"},{"fill":{"sel":"#p-desc","text":"..."}}],"reduced":true}]}
 * outputs: <out>/<key>_<viewport>_<theme>.png, <out>/index.json (per shot: file, health), exit 1 on any page error.
 * Requires: NODE_PATH=/opt/node22/lib/node_modules (playwright), Chromium at /opt/pw-browsers/chromium (override PW_CHROMIUM).
 */
const fs = require('fs'); const path = require('path');
const { chromium } = require('playwright');
const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const PLAN = JSON.parse(fs.readFileSync(arg('--plan'), 'utf8'));
const BASE = arg('--base', 'http://localhost:8831/'); const OUT = arg('--out', '.tmp/human_eye'); const ONLY = arg('--only', ''); const QUICK = process.argv.includes('--quick');
fs.mkdirSync(OUT, { recursive: true });
(async () => {
  const br = await chromium.launch({ executablePath: process.env.PW_CHROMIUM || '/opt/pw-browsers/chromium' });
  const index = []; let bad = 0;
  const vps = QUICK ? PLAN.viewports.slice(0, 1) : PLAN.viewports; const themes = QUICK ? ['light'] : PLAN.themes;
  for (const pg of PLAN.pages) {
    if (ONLY && !pg.key.includes(ONLY)) continue;
    for (const vp of vps) for (const theme of themes) {
      const ctx = await br.newContext({ viewport: { width: vp.w, height: vp.h }, reducedMotion: pg.reduced ? 'reduce' : 'no-preference' });
      const p = await ctx.newPage(); const errs = [], fails = [];
      p.on('pageerror', e => errs.push(String(e))); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
      p.on('requestfailed', r => { if (!/ERR_ABORTED/.test(r.failure()?.errorText || '')) fails.push(r.url()); });
      const url = BASE + pg.path + (pg.path.includes('?') ? '&' : '?') + 'theme=' + theme;
      try {
        await p.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
        await p.evaluate(() => { const b = document.querySelector('[data-cookie-accept]'); if (b) b.click(); });
        for (const a of pg.actions || []) {
          if (a.click) { if (a.optional) { const el = await p.$(a.click); if (el && await el.isVisible()) { await el.click(); await p.waitForTimeout(400); } } else { await p.click(a.click); await p.waitForTimeout(400); } }
          if (a.fill) {
            /* A hidden target (phone preview behind the Preview toggle, filters inside the sheet) is opened first, as a user would. */
            const target = p.locator(a.fill.sel).first();
            if (!(await target.isVisible().catch(() => false))) {
              for (const opener of ['[data-adb-toggle]', '[data-sheet-open]']) { const o = p.locator(opener).first(); if (await o.isVisible().catch(() => false)) { await o.click(); await p.waitForTimeout(400); if (await target.isVisible().catch(() => false)) break; } }
            }
            await p.fill(a.fill.sel, a.fill.text); await p.waitForTimeout(300);
          }
          if (a.scroll) { try { await p.locator(a.scroll).first().scrollIntoViewIfNeeded(); await p.waitForTimeout(500); } catch (e) { errs.push('scroll target missing: ' + a.scroll); } }
          if (a.wait) await p.waitForTimeout(a.wait);
        }
        const health = await p.evaluate(() => ({
          overflow: document.documentElement.scrollWidth > innerWidth || document.body.scrollWidth > innerWidth
            || [...document.querySelectorAll('main, main > *, .wrap, dialog[open]')].some(e => { const cs = getComputedStyle(e); return cs.overflowX === 'visible' && e.scrollWidth > e.clientWidth + 1 && e.getBoundingClientRect().right > innerWidth + 1; }),
          title: document.title,
          h1: document.querySelectorAll('h1').length,
          clipped: [...document.querySelectorAll('button,a,input,select,textarea')].filter(e => !e.closest('[data-marq],.marq,[data-marquee]')).filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && (r.right > innerWidth + 1 || r.left < -1); }).length,
        }));
        const file = `${pg.key.replace(/\//g, '_')}_${vp.name}_${theme}.png`;
        await p.screenshot({ path: path.join(OUT, file), fullPage: !!pg.full });
        const rec = { key: pg.key, viewport: vp.name, theme, file, url, errors: errs, failedRequests: fails, ...health };
        if (errs.length || fails.length || health.overflow || health.clipped || health.h1 !== 1) bad++;
        index.push(rec); console.log((errs.length || fails.length || health.overflow || health.clipped ? 'WARN ' : 'OK   ') + file + (health.overflow ? ' overflow' : '') + (health.clipped ? ` clipped=${health.clipped}` : '') + (errs.length ? ` errors=${errs.length}` : '') + (health.h1 !== 1 ? ` h1=${health.h1}` : ''));
      } catch (e) { bad++; index.push({ key: pg.key, viewport: vp.name, theme, url, fatal: String(e) }); console.log('FAIL ' + pg.key + ' ' + vp.name + ' ' + theme + ': ' + e); }
      await ctx.close();
    }
  }
  await br.close();
  fs.writeFileSync(path.join(OUT, 'index.json'), JSON.stringify(index, null, 1));
  console.log(`shots: ${index.length}, with warnings: ${bad}; index at ${path.join(OUT, 'index.json')}`);
  process.exit(bad ? 1 : 0);
})();
