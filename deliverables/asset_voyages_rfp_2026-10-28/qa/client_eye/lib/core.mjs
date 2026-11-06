// Core of the client-eye gate: browser contexts, the per-state snapshot (collect + rules + screenshot), findings.
import { mkdirSync, writeFileSync, appendFileSync } from 'node:fs';
import { join, dirname, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { INIT_SCRIPT, collectPage, armMutation } from './collect.mjs';
import * as R from './rules.mjs';

export const HERE = join(dirname(fileURLToPath(import.meta.url)), '..');
export const OUT = process.env.CE_OUT ? join(HERE, process.env.CE_OUT) : join(HERE, 'out'); // CE_OUT: dry runs write elsewhere
export const SHOTS = join(OUT, 'shots');
mkdirSync(SHOTS, { recursive: true });
const PW = new URL('../../B/ux/node_modules/playwright/index.mjs', import.meta.url);
export const { chromium } = await import(PW);

export const RUN = { started: new Date().toISOString(), findings: [], states: [], urls: new Map(), coverage: [], logins: 0, writingContexts: new Set(), sandboxes: new Set(), notes: [], words: [], labels: [], styles: [], checks: {} };
const LOG = join(OUT, 'run.log');
export const log = (...a) => { const s = `[${new Date().toISOString().slice(11, 19)}] ` + a.join(' '); console.log(s); appendFileSync(LOG, s + '\n'); };

let shotN = 0;
export function finding(f) {
  const row = { check: f.check, option: f.option, page: f.page, role: f.role || 'visiteur', width: f.width || '', locale: f.locale || 'fr-FR', text: f.text || '', element: f.element || '', note: f.note || '', shot: f.shot || '', state: f.state || '' };
  RUN.findings.push(row);
  return row;
}
export function markCheck(id, status, detail) { RUN.checks[id] = { status, detail }; }

export async function newCtx(browser, { width = 1440, locale = 'fr-FR', tz = 'Europe/Paris', option, label } = {}) {
  const mobile = width < 500;
  const ctx = await browser.newContext({ locale, timezoneId: tz, viewport: { width, height: mobile ? 844 : 900 }, deviceScaleFactor: 1, isMobile: mobile, hasTouch: mobile, acceptDownloads: true, permissions: ['clipboard-read', 'clipboard-write'], extraHTTPHeaders: { 'accept-language': locale === 'fr-FR' ? 'fr-FR,fr;q=0.9' : 'en-GB,en;q=0.9' } });
  await ctx.addInitScript(INIT_SCRIPT);
  const page = await ctx.newPage();
  page.setDefaultTimeout(30000);
  page.__meta = { option, label, width, locale, role: 'visiteur', errors: [], expectErrorDoc: false };
  attachWatch(page);
  page.on('dialog', (d) => d.accept().catch(() => {}));
  return { ctx, page };
}
export function attachWatch(page) {
  const m = page.__meta;
  page.on('pageerror', (e) => m.errors.push({ kind: 'pageerror', text: e.message.split('\n')[0], url: page.url() }));
  // On an error page reached on purpose, Chromium's own « Failed to load resource: 404/410/401 » line for that
  // document is expected; any other console error is still recorded.
  page.on('console', (msg) => { if (msg.type() === 'error' && !(m.expectErrorDoc && /Failed to load resource: the server responded with a status of (401|403|404|410|429)/.test(msg.text()))) m.errors.push({ kind: 'console', text: msg.text().slice(0, 200), url: page.url() }); });
  page.on('response', (r) => {
    const st = r.status();
    const type = r.request().resourceType();
    if (st >= 400) {
      if (type === 'document') { if (!m.expectErrorDoc) m.errors.push({ kind: 'http', text: `${st} document ${r.url()}`, url: r.url() }); }
      else m.errors.push({ kind: 'http', text: `${st} ${type} ${r.url()}`, url: r.url() });
    }
    const u = r.url();
    if (/^http:\/\//.test(u) && /^https:/.test(page.url()) && !/127\.0\.0\.1|localhost/.test(u)) m.errors.push({ kind: 'mixed', text: `mixed content ${u}`, url: page.url() });
  });
}

const safe = (s) => String(s).replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '').slice(0, 60);
export async function settle(page, ms = 1200) {
  try { await page.waitForLoadState('load', { timeout: 30000 }); } catch {}
  try { await page.evaluate(() => document.fonts && document.fonts.ready); } catch {}
  await page.waitForTimeout(ms);
}

// One state = one page as a reader sees it, in one role at one width. Runs every text rule on it.
// opts: { state, option, surface, lang ('fr'|'en'), allowCode, b4, shot (default true), rules: ['A3',...] (default all) }
export async function snap(page, opts) {
  const m = page.__meta;
  await settle(page, opts.wait ?? 1200);
  const width = page.viewportSize().width;
  let data;
  const target = opts.frame || page;
  try { data = await target.evaluate(collectPage, { b4: !!opts.b4 }); } catch (e) { log('collect failed', opts.state, e.message); return null; }
  let html = '';
  try { html = await target.content(); } catch {}
  const name = `${String(++shotN).padStart(4, '0')}-${safe(opts.option)}-${safe(m.role)}-${width}-${safe(opts.state)}.png`;
  let shot = '';
  if (opts.shot !== false) {
    try { await page.screenshot({ path: join(SHOTS, name), fullPage: width <= 1440, timeout: 30000 }); shot = relative(HERE, join(SHOTS, name)); } catch (e) { log('shot failed', name, e.message.split('\n')[0]); }
  }
  const base = { option: opts.option, page: data.url, role: m.role, width, locale: m.locale, shot, state: opts.state };
  const st = { ...base, title: data.title, lang: data.lang, surface: opts.surface, cls: data.cls, overflow: data.overflow, b4: data.b4.length };
  RUN.states.push(st);
  RUN.coverage.push({ option: opts.option, state: opts.state, role: m.role, width, locale: m.locale });
  const add = (arr) => arr.forEach((x) => finding({ ...base, ...x }));
  const on = (id) => !opts.rules || opts.rules.includes(id);
  const lang = opts.lang || (data.lang.startsWith('en') ? 'en' : 'fr');
  const items = data.texts.concat(data.attrs.filter((a) => a.visible || a.a !== 'title').map((a) => ({ ...a })));
  for (const it of items) {
    if (on('A3')) add(R.ruleA3(it));
    if (on('C8')) add(R.ruleC8(it));
    if (on('C9') && opts.demo) add(R.ruleC9(it));
    if (on('B1')) add(lang === 'fr' ? R.ruleB1French(it) : R.ruleB1English(it));
    if (on('B2')) add(R.ruleB2(it));
    if (on('B3') && lang === 'fr') add(R.ruleB3(it));
    // B7 checks French words: the whole text on a French page, only the « » quotes on an English page
    // (« access » and « congress » are English words, not « Accès » without its accent).
    if (on('B7') && lang === 'fr') add(R.ruleB7(it));
    else if (on('B7') && /«/.test(it.t)) for (const q of it.t.match(/«[^»]*»/g) || []) add(R.ruleB7({ ...it, t: q, tNoCode: q }).map((x) => ({ ...x, text: it.t.slice(0, 160) })));
    if (on('D2')) add(R.ruleD2({ ...it, demo: !!opts.demo }, { allowEmails: opts.allowEmails || [] }));
  }
  // D4: the whole DOM (text, attributes, input values, hidden fields) except on an explicit reveal state
  if (on('D4')) {
    const codes = [...new Set(html.match(R.CODE_RE) || [])];
    if (codes.length && !opts.allowCode) finding({ ...base, check: 'D4', text: codes.join(', '), element: 'DOM (text/attributes/inputs)', note: 'GM&E code present without an approved reveal' });
    if (opts.allowCode) RUN.notes.push(`D4 reveal state ${opts.state} (${m.role}) shows ${codes.join(', ') || 'no code'}`);
  }
  // A6: title
  if (on('A6')) {
    if (!data.title.trim() || /^(Document|Vite|React App|Untitled)$/i.test(data.title.trim()) || /WordPress\s*›\s*(Error|Erreur)|Erreur WordPress|Page not found|Not Found/i.test(data.title)) finding({ ...base, check: 'A6', text: data.title || '(empty)', element: '<title>', note: 'meaningless tab title' });
    st.favicons = data.favicons;
  }
  // C4: layout shift
  if (on('C4') && data.cls > 0.02) finding({ ...base, check: 'C4', text: `CLS ${data.cls.toFixed(3)}`, element: data.shifts.map((s) => s.src.join('+') + '@' + s.t + 'ms=' + s.v).join('; ').slice(0, 300), note: 'layout shift above 0.02' });
  // C6: horizontal overflow (phones and all six widths)
  if (on('C6') && data.overflow.scrollWidth > data.overflow.innerWidth + 1) finding({ ...base, check: 'C6', text: `scrollWidth ${data.overflow.scrollWidth} > ${data.overflow.innerWidth}`, element: data.overflow.offenders.map((o) => o.path + ' (right ' + o.right + ')').join('; ').slice(0, 300), note: 'content wider than the screen' });
  // B4: layout probe
  if (on('B4') && opts.b4) {
    const seen = new Set();
    for (const b of data.b4) { const k = b.kind + (b.word || b.text) + b.path; if (seen.has(k)) continue; seen.add(k); finding({ ...base, check: 'B4', text: b.word || b.text, element: b.path, note: b.kind }); }
  }
  // C3: blank boxes
  if (on('C3')) for (const e of data.empties) finding({ ...base, check: 'C3', text: `${e.w}×${e.h} px empty`, element: e.path, note: 'visible container with no text or media' });
  // Inventories for page-independent checks (B5 spelling, B6 glossary, C5 styles, A4 links, A5 videos, C2)
  RUN.words.push({ option: opts.option, page: data.url, state: opts.state, role: m.role, width, lang, texts: data.texts.filter((t) => !t.code && !/column-slug/.test(t.path || '')).map((t) => t.tNoCode || t.t), attrs: data.attrs.filter((a) => a.visible).map((a) => a.t) });
  RUN.labels.push({ option: opts.option, state: opts.state, labels: [...new Set(data.texts.map((t) => t.t).filter((t) => t.length <= 80))], clickables: data.clickables });
  RUN.styles.push({ option: opts.option, surface: opts.surface, state: opts.state, width, styles: data.styles });
  // « #… » links stay on the page (skip link, error summary): their targets are checked by C6, not fetched as URLs
  for (const l of data.links) if (!String(l.raw || '').startsWith('#')) addUrl(l.href, { from: data.url, option: opts.option, kind: 'a', text: l.text, visible: l.visible });
  for (const s of data.media) addUrl(s.url, { from: data.url, option: opts.option, kind: s.kind });
  for (const f of data.favicons) addUrl(f, { from: data.url, option: opts.option, kind: 'favicon' });
  if (!data.favicons.length) addUrl(new URL('/favicon.ico', data.url).href, { from: data.url, option: opts.option, kind: 'favicon-default' });
  st.videos = data.videos; st.clickables = data.clickables; st.sticky = data.sticky;
  return { data, html, shot, base };
}
export function addUrl(u, meta) {
  if (!u || /^(javascript|data|blob|about):/.test(u)) return;
  const key = u.split('#')[0] || u;
  if (!RUN.urls.has(key)) RUN.urls.set(key, { url: key, refs: [] });
  const e = RUN.urls.get(key);
  if (e.refs.length < 5) e.refs.push(meta);
}

// C1: errors captured on a page since the last flush
export function flushErrors(page, opts) {
  const m = page.__meta;
  for (const e of m.errors.splice(0)) finding({ check: 'C1', option: opts.option, page: e.url, role: m.role, width: page.viewportSize().width, locale: m.locale, text: e.text, element: e.kind, note: opts.state ? `during ${opts.state}` : '' });
}

// C2: a non-submit button must change something within 2 s
export async function probeButtons(page, opts) {
  const res = [];
  const btns = page.locator('button:not([type=submit]):visible, [role=button]:visible, summary:visible, [role=tab]:visible');
  const n = Math.min(await btns.count(), 12);
  for (let i = 0; i < n; i++) {
    const b = btns.nth(i);
    let label = '';
    try { label = ((await b.innerText({ timeout: 2000 })) || (await b.getAttribute('aria-label')) || '').trim().replace(/\s+/g, ' ').slice(0, 60); } catch { continue; }
    const t = await b.getAttribute('type');
    const inForm = await b.evaluate((e) => !!e.form && (e.type === 'submit'));
    // a button shown as disabled (disabled / aria-disabled) tells the reader it is unavailable: not a dead button
    if (await b.evaluate((e) => e.disabled || e.getAttribute('aria-disabled') === 'true')) continue;
    if (inForm || t === 'submit') continue;
    const url0 = page.url();
    await page.evaluate(armMutation);
    // A reader scrolls the button into the middle of the screen before tapping it; Playwright's own scroll puts it at
    // the top edge, under a sticky header. Retry once from the centre before calling it unclickable.
    let clickErr = null;
    for (const attempt of [0, 1]) {
      try { if (attempt) { await b.evaluate((e) => e.scrollIntoView({ block: 'center' })); await page.waitForTimeout(700); } await b.click({ timeout: 3000, noWaitAfter: true }); clickErr = null; break; } catch (e) { clickErr = e; }
    }
    if (clickErr) { const why = (clickErr.message.split('\n').find((l) => /intercepts pointer events|not visible|outside of the viewport|not stable|disabled/.test(l)) || clickErr.message.split('\n')[0]).replace(/\x1b\[[0-9;]*m/g, '').trim(); res.push({ label, ok: false, why: 'a reader cannot click it: ' + why.slice(0, 200) }); await page.goto(url0); await settle(page, 300); continue; }
    await page.waitForTimeout(2000);
    const changed = page.url() !== url0 || (await page.evaluate(() => window.__mut || 0).catch(() => 1)) > 0;
    res.push({ label, ok: changed, why: changed ? '' : 'no navigation, no DOM change within 2 s' });
    // every probe starts from the page as first loaded (an opened menu or dialog must not block the next button)
    if (changed) { await page.goto(url0); await settle(page, 300); }
  }
  for (const r of res) if (!r.ok) finding({ check: 'C2', option: opts.option, page: page.url(), role: page.__meta.role, width: page.viewportSize().width, text: r.label, element: 'button', note: r.why, state: opts.state });
  return res;
}

export function rel(p) { return relative(HERE, p); }
export function writeJson(name, obj) { writeFileSync(join(OUT, name), JSON.stringify(obj, null, 1)); }
