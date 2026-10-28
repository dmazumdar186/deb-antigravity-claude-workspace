#!/usr/bin/env node
/* review_shots.mjs <outdir> — eye-review screenshots of the concept (desktop 1440x900, Pixel 7, iPhone 13, reduced). */
import { createRequire } from 'node:module'; import { mkdirSync } from 'node:fs';
const require = createRequire(import.meta.url); process.env.PLAYWRIGHT_BROWSERS_PATH ||= '/opt/pw-browsers';
const { chromium, devices } = require('/opt/node-tools/node_modules/playwright');
const out = process.argv[2] || '../screens'; mkdirSync(out, { recursive: true });
const base = process.argv[3] || 'http://localhost:8794/';
const only = process.argv[4] || '';
const b = await chromium.launch();
const errs = [];
async function shoot(ctxOpts, name, plan) {
  const ctx = await b.newContext({ locale: 'fr-FR', ...ctxOpts }); const p = await ctx.newPage();
  p.on('console', (m) => { if (m.type() === 'error') errs.push(name + ': ' + m.text()); }); p.on('pageerror', (e) => errs.push(name + ': ' + e.message));
  await p.goto(base, { waitUntil: 'load' }); await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(1500);
  for (const [label, fn] of plan) { await p.mouse.move(0, 0); await fn(p); await p.waitForTimeout(900); await p.screenshot({ path: `${out}/${name}-${label}.png` }); if (label.includes('listing')) { await p.keyboard.press('Escape'); await p.waitForTimeout(300); } }
  await ctx.close();
}
const at = (sel, frac = 0) => async (p) => { await p.evaluate(([s, f]) => { const el = document.querySelector(s); const r = el.getBoundingClientRect(); const y = scrollY + r.top + f * Math.max(0, el.offsetHeight - innerHeight); window.scrollTo(0, y); }, [sel, frac]); };
const film = (k) => async (p) => { await p.evaluate((k) => { const el = document.querySelector('[data-film]'); const H = el.offsetHeight - innerHeight; window.scrollTo(0, el.offsetTop + H * Math.min(1, (k / 6) * 0.92)); }, k); await p.waitForTimeout(1200); };
const plan = [
  ['01-film0', film(0)], ['02-film2', film(2)], ['03-film3', film(3)], ['04-film4', film(4)], ['05-film5', film(5)], ['06-film6', film(6)],
  ['07-statement', at('.statement')], ['08-offers1', at('[data-folio]', 0)], ['09-offers2', at('[data-folio]', 0.5)], ['10-offers3', at('[data-folio]', 1)],
  ['11-catalogue', at('#congres')], ['12-catalogue-list', at('.cat__grid')],
  ['13-listing', async (p) => { await at('.cat__grid')(p); await p.click('.row:not([hidden]) [data-open]'); }],
  ['14-method', at('[data-drum]', 0.1)], ['15-method3', at('[data-drum]', 0.55)], ['16-services', at('#services')], ['17-agency', at('#agence')], ['18-contact', at('#contact')], ['19-footer', async (p) => { await p.evaluate(() => scrollTo(0, document.body.scrollHeight)); }],
];
const mobilePlan = [
  ['01-film0', film(0)], ['02-film3', film(3)], ['03-film5', film(5)], ['04-film6', film(6)], ['05-statement', at('.statement')], ['06-offers', at('#offres')], ['07-offers-b', at('.doc--badge')],
  ['08-catalogue', at('.cat__grid')], ['09-listing', async (p) => { await at('.cat__grid')(p); await p.click('.row:not([hidden]) [data-open]'); }],
  ['10-method', at('#methode')], ['11-services', at('#services')], ['12-agency', at('#agence')], ['13-contact', at('#contact')], ['14-contact-form', at('.form')], ['15-footer', async (p) => { await p.evaluate(() => scrollTo(0, document.body.scrollHeight)); }],
  ['16-menu', async (p) => { await p.evaluate(() => scrollTo(0, 0)); await p.click('[data-burger]'); }],
];
if (!only || only === 'd') await shoot({ viewport: { width: 1440, height: 900 } }, 'd', plan);
if (!only || only === 'p') await shoot({ ...devices['Pixel 7'] }, 'p7', mobilePlan);
if (!only || only === 'i') await shoot({ ...devices['iPhone 13'] }, 'i13', mobilePlan.slice(0, 5));
if (!only || only === 'r') await shoot({ ...devices['Pixel 7'], reducedMotion: 'reduce' }, 'p7r', [['01-top', film(0)], ['02-static', at('.film__static')], ['03-offers', at('#offres')], ['04-method', at('#methode')]]);
if (!only || only === 'r') await shoot({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' }, 'dr', [['01-top', film(0)], ['02-static', at('.film__static')]]);
for (const pg of ['pour-asset/', 'console/']) for (const [n, o] of [['d', { viewport: { width: 1440, height: 900 } }], ['p7', { ...devices['Pixel 7'] }]]) {
  if (only && only !== 'x') continue;
  const ctx = await b.newContext({ locale: 'fr-FR', ...o }); const p = await ctx.newPage(); await p.goto(base + pg, { waitUntil: 'load' }); await p.waitForTimeout(600);
  await p.screenshot({ path: `${out}/${pg.replace('/', '')}-${n}-full.png`, fullPage: true }); await ctx.close();
}
await b.close();
console.log(errs.length ? 'CONSOLE ERRORS:\n' + errs.join('\n') : 'no console errors');
