#!/usr/bin/env node
/* demo_page.mjs — functional checks for the demos hub (/demo/), served with the real _headers CSP.
   usage: node research/serve_csp.mjs site 8794 &  node research/demo_page.mjs http://localhost:8794/
   outputs: research/demo_page.json and research/demo_screens/*.png (+ demo.pdf); exit 0 only on N/N. */
import { createRequire } from 'node:module'; import { writeFileSync, readFileSync, mkdirSync } from 'node:fs';
const base = (process.argv[2] || 'http://localhost:8794/').replace(/\/?$/, '/');
const url = base + 'demo/';
const SITE = new URL('../site/', import.meta.url).pathname;
const SHOTS = new URL('./demo_screens/', import.meta.url).pathname; mkdirSync(SHOTS, { recursive: true });
process.env.PLAYWRIGHT_BROWSERS_PATH ||= '/opt/pw-browsers';
const req = createRequire(import.meta.url); let pw; for (const p of ['/opt/node-tools/node_modules/playwright', '/tmp/pwtest/node_modules/playwright', 'playwright']) { try { pw = req(p); break; } catch {} }
const { chromium } = pw;
const R = []; const t = (name, ok, info) => { R.push({ name, ok: !!ok, info }); console.log((ok ? 'ok   ' : 'FAIL ') + name + (info !== undefined ? ' — ' + info : '')); };
const URLS = {
  WP_VISITOR_URL: 'https://playground.wordpress.net/?blueprint-url=https://asset-voyages-redesign.pages.dev/demo-wordpress/blueprint-visitor.json',
  WP_ADMIN_URL: 'https://playground.wordpress.net/?blueprint-url=https://asset-voyages-redesign.pages.dev/demo-wordpress/blueprint-admin.json',
  CUSTOM_URL: 'https://asset-voyages-demo.REPLACE.workers.dev/',
  CUSTOM_CONSOLE_URL: 'https://asset-voyages-demo.REPLACE.workers.dev/console',
};
const MAILTO = 'mailto:debanjan@prodcraft.fyi?subject=ASSET%20%E2%80%93%20demonstration%20slot';
const b = await chromium.launch();
const local = new URL(base).host;
async function mk(opts = {}) {
  const ctx = await b.newContext({ locale: 'en-GB', deviceScaleFactor: 1, ...opts }); const p = await ctx.newPage(); const errs = [], hosts = new Set();
  p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
  p.on('request', (r) => { const u = r.url(); if (/^https?:/.test(u)) hosts.add(new URL(u).host); });
  p._errs = errs; p._hosts = hosts; p._ctx = ctx; return p;
}
const settle = async (p) => { await p.evaluate(async () => { document.documentElement.style.scrollBehavior = 'auto'; for (let y = 0; y < document.body.scrollHeight; y += 500) { scrollTo(0, y); await new Promise((r) => setTimeout(r, 60)); } scrollTo(0, 0); }); await p.waitForTimeout(2600); };
const overflow = (p) => p.evaluate(() => { const W = document.documentElement.clientWidth; const bad = []; for (const el of document.querySelectorAll('body *')) { if (el.closest('.mini__in, .vh, svg, [hidden]')) continue; const r = el.getBoundingClientRect(); if (r.width && (r.right > W + 1 || r.left < -1)) bad.push((el.className || el.tagName) + ':' + Math.round(r.right)); } return { sw: document.documentElement.scrollWidth, W, bad: bad.slice(0, 5) }; });

// ================= desktop 1440 =================
let p = await mk({ viewport: { width: 1440, height: 900 } });
await p.goto(url, { waitUntil: 'load' }); await p.waitForTimeout(600);
const fold = await p.evaluate(() => { const h = document.querySelector('.hero h1').getBoundingClientRect(), a = document.querySelector('.hero .btn').getBoundingClientRect(); return { h1: h.bottom, btn: a.bottom }; });
t('desktop: headline, sentence and primary action above the fold at 1440x900', fold.btn < 900, JSON.stringify(fold));
await settle(p);
t('desktop: 0 console errors (served with the real _headers CSP)', p._errs.length === 0, p._errs.slice(0, 3).join(' | '));
t('desktop: 0 third-party requests on load', [...p._hosts].every((h) => h === local), [...p._hosts].join(','));
const ov1 = await overflow(p); t('desktop 1440: no horizontal overflow', ov1.sw <= ov1.W && !ov1.bad.length, JSON.stringify(ov1));
const anchors = await p.evaluate(() => [...document.querySelectorAll('a[href^="#"]')].map((a) => a.getAttribute('href')).filter((h) => h.length > 1 && !document.getElementById(h.slice(1))));
t('every in-page anchor resolves to an element', anchors.length === 0, anchors.join(','));
const navIds = await p.evaluate(() => [...document.querySelectorAll('[data-mini] a')].map((a) => a.getAttribute('href')));
t('sticky strip lists the eight sections in page order', navIds.join() === '#options,#try,#recordings,#compare,#built,#codes,#plan,#slot' && await p.evaluate((ids) => { const ys = ids.map((h) => document.querySelector(h).getBoundingClientRect().top); return ys.every((y, i) => i === 0 || y > ys[i - 1]); }, navIds), navIds.join());
// relative page links resolve (media files are optional and checked separately)
const rel = await p.evaluate(() => [...new Set([...document.querySelectorAll('a[href]')].map((a) => a.getAttribute('href')).filter((h) => !/^(#|https?:|mailto:)/.test(h) && !/^media\//.test(h)))]);
const relBad = []; for (const h of rel) { const r = await fetch(new URL(h, url)); if (r.status !== 200) relBad.push(h + ':' + r.status); }
t('relative links to the concept pages resolve (200)', relBad.length === 0 && rel.length >= 4, rel.join(',') + (relBad.length ? ' BAD ' + relBad.join(',') : ''));
// constants
const js = readFileSync(SITE + 'js/demo.js', 'utf8'); const html = readFileSync(SITE + 'demo/index.html', 'utf8');
const constOk = js.includes(`const WP_VISITOR_URL = '${URLS.WP_VISITOR_URL}'`) && js.includes(`const WP_ADMIN_URL = '${URLS.WP_ADMIN_URL}'`) && js.includes(`const CUSTOM_URL = '${URLS.CUSTOM_URL}'`) && js.includes("const CUSTOM_CONSOLE_URL = CUSTOM_URL + 'console'");
const live = await p.evaluate(() => [...document.querySelectorAll('a[data-demo]')].map((a) => [a.dataset.demo, a.getAttribute('href'), a.target, a.rel]));
const liveOk = live.length >= 8 && live.every(([k, h, tg, rl]) => h === ({ WP_VISITOR_URL: 'https://playground.wordpress.net/?blueprint-url=https://asset-voyages-redesign.pages.dev/demo-wordpress/blueprint-visitor.json', WP_ADMIN_URL: 'https://playground.wordpress.net/?blueprint-url=https://asset-voyages-redesign.pages.dev/demo-wordpress/blueprint-admin.json', CUSTOM_URL: 'https://asset-voyages-demo.REPLACE.workers.dev/', CUSTOM_CONSOLE_URL: 'https://asset-voyages-demo.REPLACE.workers.dev/console' })[k] && tg === '_blank' && /noopener/.test(rl));
const staticOk = Object.values(URLS).every((u) => html.includes(`href="${u}"`));
t('demo constants: four URLs defined once in demo.js, applied to every demo link, same hrefs in the HTML for no-JS', constOk && liveOk && staticOk, `links=${live.length}`);
const cards = await p.evaluate(() => [...document.querySelectorAll('.pass')].map((c) => c.querySelectorAll('a.btn').length));
t('two option cards, two buttons each', cards.join() === '2,2', cards.join());
const logins = await p.evaluate(() => document.querySelector('.logins').innerText);
t('logins: direction / equipe / contributeur, password demo-asset; Playground start time stated', /direction/.test(logins) && /equipe/.test(logins) && /contributeur/.test(logins) && /demo-asset/.test(logins) && /20 to 40 seconds/.test(await p.evaluate(() => document.body.innerText)));
// mailto
const mail = await p.evaluate(() => ({ main: document.querySelector('[data-mailto]').getAttribute('href'), slots: [...document.querySelectorAll('.time')].map((a) => a.getAttribute('href')), labels: [...document.querySelectorAll('.days li')].map((li) => li.innerText.replace(/\s+/g, ' ').trim()) }));
const subj = (h) => decodeURIComponent((h.match(/subject=([^&]+)/) || [])[1] || '');
t('mailto: main button exact; every slot mails debanjan@prodcraft.fyi with subject "ASSET – demonstration slot"', mail.main === MAILTO && mail.slots.length === 7 && mail.slots.every((h) => h.startsWith('mailto:debanjan@prodcraft.fyi?') && subj(h) === 'ASSET – demonstration slot'), mail.labels.join(' / '));
t('slots: Thu 12 (10:00, 14:30), Fri 13 (10:00), Mon 16 (10:00, 14:30), Tue 17 (10:00, 14:30)', mail.labels.join('|') === 'Thursday 12 November 10:00 14:30|Friday 13 November 10:00|Monday 16 November 10:00 14:30|Tuesday 17 November 10:00 14:30', mail.labels.join('|'));
// table
const tbl = await p.evaluate(() => [...document.querySelectorAll('.cmp tbody tr')].map((tr) => [tr.querySelector('th').innerText, ...[...tr.querySelectorAll('td .st')].map((s) => s.innerText)]));
t('comparison: 11 rows, every cell carries one of the two statuses', tbl.length === 11 && tbl.every((r) => r.length === 3 && r.slice(1).every((s) => s === 'Works in the demo' || s === 'Built during the project')), tbl.length + ' rows');
// signature: the access path draws in
const flow = await p.evaluate(() => { const f = document.querySelector('[data-flow]'); const path = f.querySelector('.flow__wide .flow__path'); return { armed: f.hasAttribute('data-armed'), in: f.classList.contains('is-in'), off: getComputedStyle(path).strokeDashoffset, op: getComputedStyle(f.querySelector('.flow__wide [data-i="5"]')).opacity }; });
t('signature: GM&E access path armed below the fold and fully drawn after scrolling to it', flow.armed && flow.in && parseFloat(flow.off) === 0 && flow.op === '1', JSON.stringify(flow));
const svgA11y = await p.evaluate(() => [...document.querySelectorAll('.flow svg')].every((s) => s.getAttribute('role') === 'img' && s.querySelector('title') && s.querySelector('desc') && /never the code/.test(s.querySelector('desc').textContent)));
t('diagram: role=img with title and full text description', svgA11y);
// anchor not covered by the sticky strip
for (const id of ['#compare', '#slot']) {
  await p.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; scrollTo(0, 0); });
  await p.click(`[data-mini] a[href="${id}"]`); await p.waitForTimeout(400);
  const g = await p.evaluate((id) => ({ top: document.querySelector(id + ' h2').getBoundingClientRect().top, strip: document.querySelector('[data-mini]').getBoundingClientRect().bottom, cur: document.querySelector('[data-mini] a[aria-current]')?.getAttribute('href') }), id);
  t(`desktop: ${id} heading lands below the sticky strip, strip marks it`, g.top >= g.strip && g.top < 260 && g.cur === id, JSON.stringify(g));
}
// recordings: default fallback
const rec0 = await p.evaluate(() => [...document.querySelectorAll('[data-rec]')].map((f) => ({ v: !!f.querySelector('video'), empty: !f.querySelector('[data-rec-empty]').hidden && f.querySelector('[data-rec-empty]').getBoundingClientRect().height > 40 })));
t('recordings: manifest says not ready, so both slots show the designed fallback (no video, no 404)', rec0.every((r) => !r.v && r.empty), JSON.stringify(rec0));
// contrast of every visible text node against its painted background
const contrast = await p.evaluate(() => {
  const parse = (c) => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const v = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return { r: v[0], g: v[1], b: v[2], a: v[3] === undefined ? 1 : v[3] }; };
  const lum = ({ r, g, b }) => { const f = (x) => { x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const bgOf = (el) => { for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor); if (c && c.a > 0.5) return c; } return { r: 242, g: 238, b: 229, a: 1 }; };
  const bad = []; let n = 0;
  for (const el of document.querySelectorAll('body *:not(svg *)')) {
    if (![...el.childNodes].some((x) => x.nodeType === 3 && x.textContent.trim())) continue;
    const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || el.closest('.vh,[hidden]') || !el.getClientRects().length) continue;
    const fg = parse(cs.color), bg = bgOf(el); const mix = { r: fg.r * fg.a + bg.r * (1 - fg.a), g: fg.g * fg.a + bg.g * (1 - fg.a), b: fg.b * fg.a + bg.b * (1 - fg.a) };
    const L1 = lum(mix), L2 = lum(bg); const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const big = parseFloat(cs.fontSize) >= 24 || (parseFloat(cs.fontSize) >= 18.66 && +cs.fontWeight >= 700); n++;
    if (ratio < (big ? 3 : 4.5)) bad.push(`${el.className || el.tagName}:${ratio.toFixed(2)}`);
  }
  return { n, bad: bad.slice(0, 6) };
});
t('WCAG AA contrast on every visible text element', contrast.bad.length === 0, `checked ${contrast.n}` + (contrast.bad.length ? ' BAD ' + contrast.bad.join(',') : ''));
await settle(p);
await p.screenshot({ path: SHOTS + 'demo-1440.png', fullPage: true });
// print
await p.emulateMedia({ media: 'print' });
const pr = await p.evaluate(() => ({ mini: getComputedStyle(document.querySelector('[data-mini]')).display, optsB: [...document.querySelectorAll('.task__opt--b')].every((o) => getComputedStyle(o).display !== 'none'), wide: getComputedStyle(document.querySelector('.flow__wide')).display }));
await p.pdf({ path: SHOTS + 'demo.pdf', format: 'A4', printBackground: true });
t('print: strip hidden, both options of every task printed, wide diagram, PDF written', pr.mini === 'none' && pr.optsB && pr.wide === 'block', JSON.stringify(pr));
await p._ctx.close();

// ================= phone 390 =================
p = await mk({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
await p.goto(url, { waitUntil: 'load' }); await settle(p);
t('390: 0 console errors', p._errs.length === 0, p._errs.slice(0, 3).join(' | '));
const ov2 = await overflow(p); t('390: no horizontal overflow', ov2.sw <= ov2.W && !ov2.bad.length, JSON.stringify(ov2));
const small = await p.evaluate(() => { const bad = []; for (const el of document.querySelectorAll('body *:not(svg *)')) { if (![...el.childNodes].some((x) => x.nodeType === 3 && x.textContent.trim())) continue; if (el.closest('.vh,[hidden]') || !el.getClientRects().length) continue; const fs = parseFloat(getComputedStyle(el).fontSize); if (fs < 16) bad.push(el.className || el.tagName); } const svgT = [...document.querySelectorAll('.flow__tall text')].map((x) => x.getBoundingClientRect().height); return { bad: [...new Set(bad)].slice(0, 6), svgMin: Math.min(...svgT) }; });
t('390: all text 16 px or more (diagram text included, as rendered)', small.bad.length === 0 && small.svgMin >= 15, JSON.stringify(small));
const taps = await p.evaluate(() => [...document.querySelectorAll('.btn, .time, [data-mini] a, .switch__b, .top__back, .link-quiet, .skip')].filter((e) => e.getClientRects().length && !e.classList.contains('skip')).map((e) => { const r = e.getBoundingClientRect(); return [e.textContent.trim().slice(0, 20), Math.round(r.height), Math.round(r.width)]; }).filter(([, h, w]) => h < 44 || w < 44));
t('390: every button, slot, strip link and switch is at least 44 px', taps.length === 0, JSON.stringify(taps));
const sw = await p.evaluate(() => ({ shown: !document.querySelector('[data-switch]').hidden, a: [...document.querySelectorAll('.task__opt--a')].every((o) => getComputedStyle(o).display !== 'none'), b: [...document.querySelectorAll('.task__opt--b')].every((o) => getComputedStyle(o).display === 'none') }));
await p.click('[data-switch] [data-show="b"]'); await p.waitForTimeout(150);
const sw2 = await p.evaluate(() => ({ a: [...document.querySelectorAll('.task__opt--a')].every((o) => getComputedStyle(o).display === 'none'), b: [...document.querySelectorAll('.task__opt--b')].every((o) => getComputedStyle(o).display !== 'none'), pressed: document.querySelector('[data-show="b"]').getAttribute('aria-pressed') }));
t('390: A/B switch shows one option at a time, aria-pressed follows', sw.shown && sw.a && sw.b && sw2.a && sw2.b && sw2.pressed === 'true', JSON.stringify({ sw, sw2 }));
await p.click('[data-switch] [data-show="a"]');
await p.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; scrollTo(0, 0); });
await p.click('[data-mini] a[href="#plan"]'); await p.waitForTimeout(500);
const g390 = await p.evaluate(() => ({ top: document.querySelector('#plan h2').getBoundingClientRect().top, strip: document.querySelector('[data-mini]').getBoundingClientRect().bottom }));
t('390: #plan heading lands below the sticky strip', g390.top >= g390.strip, JSON.stringify(g390));
const tall = await p.evaluate(() => ({ wide: getComputedStyle(document.querySelector('.flow__wide')).display, tall: getComputedStyle(document.querySelector('.flow__tall')).display }));
t('390: the diagram switches to its vertical drawing', tall.wide === 'none' && tall.tall === 'block', JSON.stringify(tall));
await p.evaluate(() => scrollTo(0, 0)); await p.waitForTimeout(200);
await p.screenshot({ path: SHOTS + 'demo-390.png', fullPage: true });
await p._ctx.close();

// ================= recordings: ready but missing, and ready and present =================
p = await mk({ viewport: { width: 1280, height: 800 } });
await p.route('**/demo/media/manifest.json', (r) => r.fulfill({ contentType: 'application/json', body: '{"wp-walkthrough":true,"custom-walkthrough":true}' }));
const hero = readFileSync(SITE + 'assets/hero.mp4');
await p.route('**/demo/media/custom-walkthrough.mp4', (r) => r.fulfill({ contentType: 'video/mp4', body: hero }));
await p.goto(url, { waitUntil: 'load' }); await p.waitForTimeout(2500);
const rec1 = await p.evaluate(() => Object.fromEntries([...document.querySelectorAll('[data-rec]')].map((f) => [f.dataset.rec, { v: !!f.querySelector('video'), ready: f.querySelector('video')?.readyState || 0, empty: !f.querySelector('[data-rec-empty]').hidden, msg: f.querySelector('[data-rec-msg]').textContent }])));
t('recordings: a file announced but missing falls back to the message; a present file plays in the slot', rec1['wp-walkthrough'].empty && !rec1['wp-walkthrough'].v && /could not be loaded/.test(rec1['wp-walkthrough'].msg) && rec1['custom-walkthrough'].v && rec1['custom-walkthrough'].ready >= 1 && !rec1['custom-walkthrough'].empty, JSON.stringify(rec1));
await p._ctx.close();

// ================= reduced motion =================
p = await mk({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
await p.goto(url, { waitUntil: 'load' }); await p.waitForTimeout(400);
const rm = await p.evaluate(() => ({ armed: document.querySelector('[data-flow]').hasAttribute('data-armed'), sb: getComputedStyle(document.documentElement).scrollBehavior, off: getComputedStyle(document.querySelector('.flow__wide .flow__path')).strokeDashoffset }));
t('reduced motion: no reveal (diagram drawn from the start), no smooth scroll', !rm.armed && rm.sb === 'auto' && (rm.off === '0px' || rm.off === '0'), JSON.stringify(rm));
await p._ctx.close();

// ================= JavaScript off =================
for (const vp of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
  p = await mk({ viewport: vp, javaScriptEnabled: false });
  await p.goto(url, { waitUntil: 'load' }); await p.waitForTimeout(300);
  const nojs = await p.evaluate(() => ({ sections: ['options', 'try', 'recordings', 'compare', 'built', 'codes', 'plan', 'slot'].every((id) => { const s = document.getElementById(id); return s && s.getBoundingClientRect().height > 100; }), opts: [...document.querySelectorAll('.task__opt')].filter((o) => getComputedStyle(o).display !== 'none').length, sw: document.querySelector('[data-switch]').hidden, path: getComputedStyle(document.querySelector('.flow__path')).strokeDasharray, rec: [...document.querySelectorAll('[data-rec-empty]')].every((e) => e.getBoundingClientRect().height > 40), links: [...document.querySelectorAll('a[data-demo]')].every((a) => /^https:/.test(a.href)), rows: document.querySelectorAll('.cmp tbody tr').length, sw0: document.documentElement.scrollWidth <= innerWidth }));
  t(`JS off ${vp.width}: every section, both options of all 5 tasks, demo links, diagram, fallbacks, table; no overflow`, nojs.sections && nojs.opts === 10 && nojs.sw && nojs.path === 'none' && nojs.rec && nojs.links && nojs.rows === 11 && nojs.sw0, JSON.stringify(nojs));
  await p._ctx.close();
}

// ================= the discreet links on the other pages =================
p = await mk({ viewport: { width: 390, height: 844 }, isMobile: true });
for (const [path, sel] of [['', '.ftr a[href="demo/"]'], ['pour-asset/', '.doc a[href="../demo/"]'], ['questions/', '.q-foot a[href="../demo/"]']]) {
  await p.goto(base + path, { waitUntil: 'load' }); await p.waitForTimeout(400);
  const r = await p.evaluate((sel) => ({ link: !!document.querySelector(sel), sw: document.documentElement.scrollWidth, W: document.documentElement.clientWidth, hdr: (() => { const n = document.querySelector('.dh__nav'); if (!n) return true; const r = n.getBoundingClientRect(); return r.right <= document.documentElement.clientWidth + 1; })() }), sel);
  t(`/${path}: link to /demo/ present, no overflow at 390`, r.link && r.sw <= r.W && r.hdr, JSON.stringify(r));
}
await p._ctx.close();

await b.close();
const pass = R.filter((r) => r.ok).length;
writeFileSync(new URL('./demo_page.json', import.meta.url), JSON.stringify({ url, date: new Date().toISOString(), pass, total: R.length, results: R }, null, 1));
console.log(`\n${pass}/${R.length} passed · screens: ${SHOTS}demo-1440.png, ${SHOTS}demo-390.png`);
process.exit(pass === R.length ? 0 : 1);
