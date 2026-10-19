#!/usr/bin/env node
/* functional_template.mjs — the 29-assertion Playwright suite from MISB v3, with every site-specific selector
   and value lifted into the constants below. A worker copies this file to <deliverable>/research/functional.mjs,
   edits ONLY the CONFIG block (≈ 5 minutes), keeps every assertion NAME, and runs:
     python3 -m http.server 8793 --directory <site> &  node functional.mjs http://localhost:8793/
   outputs: functional.json next to the script (pass/total, page heights, panel heights, sizes, results); exit 0 only on N/N.
   usage: node functional_template.mjs <url> | --help */
const argv = process.argv.slice(2);
if (!argv[0] || argv.includes('--help') || argv.includes('-h')) {
  console.log('functional_template.mjs <base-url> — 29-assertion prospectus suite (cover beats, video/canvas, signature object, deck, counters, fade sequencing, heights, sizes, mobile rules, pitch). Edit the CONFIG block first.');
  process.exit(argv[0] ? 0 : 2);
}
// ======================= CONFIG (ProdCraft v2) =======================
const SIGNATURE_RE = /Debanjan, Founder, ProdCraft, <a[^>]*>debanjan@prodcraft\.fyi/;
const COVER = '[data-cover]'; const BEAT = '[data-beat]';
const PROBES = [0.1, 0.3, 0.47, 0.62, 0.85]; const BEATS_EXPECTED = '0,1,2,3,4';
const LAST_BEAT = '[data-beat="4"]'; const LAST_PLATE = '[data-plate="4"]';
const COVER_BODY = '.cover__body';
const HERO_VIDEO = '[data-hero-video]'; const BACKDROP = '[data-backdrop]'; const PORTRAIT_RE = /hero-m/;
const FOLD = '[data-fold]'; const FOLD_PIN = '.fold__pin'; const FOLD_HEAD = '.fold__head'; const SPREAD = '[data-spread]';
const FOLD_PANEL = '.sheet:not([hidden]) .panel--left'; const FOLD_ANCHOR = '#ledger';
const DECK = '#deck'; const DECK_NAV = '[data-deck-nav]'; const PANEL = '.dp'; const TAB = (id) => `[data-tab="${id}"]`;
const TAB_ORDER = ['systems', 'build', 'stack', 'how', 'recs', 'contact', 'who'];
const FIRST_TAB = 'who'; const LAST_TAB = 'contact'; const LAST_TAB_LABEL = /08 Contact/;
const DEEP_LINK = 'stack';
const COUNTER_TAB = 'systems'; const COUNTERS_EXPECTED = '$1M+,+45%,<30 days,$1M+,$200K/yr,+45%,−55%,95%,8 min,14 days,$10K/wk,12+,21,977,1,900,68%';
const GALLERY_BTN = '[data-plate-open="gtm"]'; const GALLERY = '[data-gallery]'; const GAL_GRID = '[data-gal-grid] img'; const GAL_TITLE = '[data-gal-title]'; const GAL_COUNT = 1;
const HDR_LOGO = '.hdr__logo'; const MBAR = '[data-mbar]';
const PAPER_RGB = 'rgb(247, 243, 236)';
const CHAPTER_NO = '[data-chapter-no]'; const CHAPTER_NAME = '[data-chapter-name]';
const FILES = { html: 'index.html', css: 'css/styles.css', js: 'js/main.js', backdrop: 'js/backdrop.js' };
const LIMITS = { desktopH: 9000, mobileH: 12000, panelDesktop: 900, panelMobile: 2 * 915, bundleKB: 150, backdropKB: 12 };
const OUT_JSON = './functional.json';
const SITE_DIR = new URL('../site/', import.meta.url).pathname;
const INIT = `Object.assign(window, ${JSON.stringify({ BEAT, LAST_BEAT, LAST_PLATE, COVER_BODY, HERO_VIDEO, BACKDROP, COVER, FOLD, FOLD_PIN, FOLD_HEAD, SPREAD, FOLD_PANEL, FOLD_ANCHOR, DECK, DECK_NAV, PANEL, GALLERY, GAL_GRID, GAL_TITLE, HDR_LOGO, MBAR, CHAPTER_NO, CHAPTER_NAME, FILES })});`;
// ======================= end CONFIG =======================
// NOTE: selectors inside page.evaluate() callbacks run in the browser and cannot see the constants above;
// pass them as the second argument (see `beat`/`trackY` helpers) — the remaining literal selectors in evaluate bodies
// (.panel--left, [data-spread], .fold__pin, [data-mbar], [data-cover], .dp, [data-beat], [data-plate]) must be edited by hand if renamed.
import { createRequire } from 'node:module'; import { writeFileSync } from 'node:fs';
process.env.PLAYWRIGHT_BROWSERS_PATH ||= '/opt/pw-browsers';
const _req = createRequire(import.meta.url); let _pw; for (const p of ['/opt/node-tools/node_modules/playwright', '/tmp/pwtest/node_modules/playwright', 'playwright']) { try { _pw = _req(p); break; } catch {} }
if (!_pw) { console.error('playwright not found'); process.exit(2); }
const { chromium, devices } = _pw;
const base = argv[0].endsWith('/') ? argv[0] : argv[0] + '/'; const R = []; const t = (name, ok, info) => { R.push({ name, ok: !!ok, info }); console.log((ok ? 'ok   ' : 'FAIL ') + name + (info !== undefined ? ' — ' + info : '')); };
const b = await chromium.launch();
async function mk(opts) { const p = await b.newPage(opts); await p.addInitScript(INIT); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); }); p._errs = errs; return p; }
const scrollTo = async (p, y) => { await p.evaluate((v) => { document.documentElement.style.scrollBehavior = 'auto'; window.scrollTo(0, v); }, y); await p.waitForTimeout(350); };
const trackY = (p, sel, f) => p.evaluate(([s, f]) => { const el = document.querySelector(s); return el.offsetTop + (el.offsetHeight - innerHeight) * f; }, [sel, f]);
const beat = (p) => p.evaluate(() => { const b = [...document.querySelectorAll(BEAT)].find((x) => x.classList.contains('is-on')); return b ? +b.dataset.beat : -1; });
// ---- desktop
let p = await mk({ viewport: { width: 1440, height: 900 } });
await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(1500);
const beats = [];
for (const f of PROBES) { await scrollTo(p, await trackY(p, COVER, f)); beats.push(await beat(p)); }
t('cover beats change at 25/50/75% of the track', beats.join(',') === BEATS_EXPECTED, beats.join(','));
const vs = await p.evaluate(() => { const v = document.querySelector(HERO_VIDEO); const c = document.querySelector(BACKDROP); return { hasVideo: document.querySelector(COVER).classList.contains('has-video'), playing: !!(v && !v.paused && v.readyState >= 2), src: v && v.currentSrc, canvasVisible: c && getComputedStyle(c).display !== 'none' }; });
t('video plays (or canvas fallback runs)', vs.playing || vs.canvasVisible, JSON.stringify(vs));
await scrollTo(p, 0);
const f0 = await p.evaluate(() => getComputedStyle(document.querySelector(FOLD_PANEL)).transform);
await scrollTo(p, await trackY(p, FOLD, 0.5)); const f50 = await p.evaluate(() => getComputedStyle(document.querySelector(FOLD_PANEL)).transform);
await scrollTo(p, await trackY(p, FOLD, 1)); await p.waitForTimeout(300);
const fEnd = await p.evaluate(() => ({ tf: getComputedStyle(document.querySelector(FOLD_PANEL)).transform, fold: getComputedStyle(document.querySelector(SPREAD)).getPropertyValue('--fold').trim(), open: document.querySelector(FOLD).classList.contains('is-open') }));
t('fold-out hinge transform changes with scroll', f0 !== f50 && f50 !== fEnd.tf, `${f0.slice(0, 30)} → ${f50.slice(0, 30)} → ${fEnd.tf.slice(0, 30)}`);
t('fold-out fully open by track end', fEnd.fold === '1.0000' && fEnd.open && /^(none|matrix\(1, 0, 0, 1, 0, 0\))$/.test(fEnd.tf), JSON.stringify(fEnd));
// deck tabs
await p.evaluate(() => document.querySelector(DECK).scrollIntoView()); await p.waitForTimeout(400);
const vis = async () => p.evaluate(() => [...document.querySelectorAll(PANEL)].filter((d) => !d.hidden).map((d) => d.id));
let okTabs = true, info = [];
for (const id of TAB_ORDER) { await p.click(TAB(id)); await p.waitForTimeout(250); const v = await vis(); const h = await p.evaluate(() => location.hash); info.push(id + ':' + v.join('/') + h); if (!(v.length === 1 && v[0] === id && h === '#' + id)) okTabs = false; }
t('each chapter tab switches the panel and updates the hash', okTabs, info.join(' | '));
await p.goBack(); await p.waitForTimeout(400); const back1 = await vis(); const bh = await p.evaluate(() => location.hash);
t('back button restores the previous panel', back1[0] === LAST_TAB && bh === '#' + LAST_TAB, back1.join('/') + ' ' + bh);
const chapterInd = await p.evaluate(() => document.querySelector(CHAPTER_NO).textContent + ' ' + document.querySelector(CHAPTER_NAME).textContent);
t('header chapter indicator follows the deck', LAST_TAB_LABEL.test(chapterInd), chapterInd);
// keyboard
await p.focus(TAB(LAST_TAB)); await p.keyboard.press('ArrowRight'); await p.waitForTimeout(250);
t('keyboard ArrowRight wraps to the first chapter', (await vis())[0] === FIRST_TAB, (await vis()).join());
// deep link fresh load
const p2 = await mk({ viewport: { width: 1440, height: 900 } }); await p2.goto(base + '#' + DEEP_LINK, { waitUntil: 'load' }); await p2.waitForTimeout(900);
t('deep link /#<id> opens the panel', (await p2.evaluate(() => [...document.querySelectorAll(PANEL)].filter((d) => !d.hidden).map((d) => d.id)))[0] === DEEP_LINK);
await p2.close();
// gallery
await scrollTo(p, await trackY(p, FOLD, 1)); await p.click(GALLERY_BTN); await p.waitForTimeout(300);
const gOpen = await p.evaluate(() => ({ open: document.querySelector(GALLERY).open, n: document.querySelectorAll(GAL_GRID).length, title: document.querySelector(GAL_TITLE).textContent }));
await p.keyboard.press('Escape'); await p.waitForTimeout(200); const gClosed = await p.evaluate(() => !document.querySelector(GALLERY).open);
t('gallery dialog opens and closes', gOpen.open && gOpen.n === GAL_COUNT && gClosed, JSON.stringify(gOpen));
await p.click(TAB(COUNTER_TAB)); await p.waitForTimeout(1500);
const cnt = await p.evaluate(() => [...document.querySelectorAll('[data-count]')].map((e) => e.textContent));
t('counters settle on the exact published values', cnt.join() === COUNTERS_EXPECTED, cnt.join());
// 2 cover end state: beat 04 still visible, fold-out already entering (no empty viewport)
await scrollTo(p, await trackY(p, COVER, 0.81)); await p.waitForTimeout(400);
const endState = await p.evaluate(() => { const b = document.querySelector(LAST_BEAT); const fp = document.querySelector(FOLD_PIN); const r = fp.getBoundingClientRect(); return { beatOn: b.classList.contains('is-on'), beatOpacity: getComputedStyle(b).opacity, bodyOpacity: getComputedStyle(document.querySelector(COVER_BODY)).opacity, foldTop: Math.round(r.top), enter: getComputedStyle(document.querySelector(FOLD)).getPropertyValue('--enter').trim(), plate: getComputedStyle(document.querySelector(LAST_PLATE)).opacity }; });
await scrollTo(p, await trackY(p, COVER, 1)); await p.waitForTimeout(400);
endState.enterAtEnd = await p.evaluate(() => getComputedStyle(document.querySelector(FOLD)).getPropertyValue('--enter').trim());
t('cover end: last beat held into the overlap, photo plate shown, fold-out arrived by track end (no empty viewport)', endState.enterAtEnd === '1.000' &&  endState.beatOn && endState.beatOpacity === '1' && +endState.bodyOpacity >= 0.85 && endState.foldTop <= 0 && +endState.enter > 0 && endState.plate === '1', JSON.stringify(endState));
// 2 fade sequencing: fold text may only appear once the cover text is gone
await scrollTo(p, await trackY(p, COVER, 0.92)); await p.waitForTimeout(400);
const seq = await p.evaluate(() => ({ foldText: getComputedStyle(document.querySelector(FOLD_HEAD)).opacity, coverBody: getComputedStyle(document.querySelector(COVER_BODY)).opacity, coverVis: getComputedStyle(document.querySelector(COVER)).visibility, logoHidden: getComputedStyle(document.querySelector(HDR_LOGO)).visibility }));
t('fade sequence: cover text at 0 before chapter headline passes 0.1', +seq.foldText > 0.1 && +seq.coverBody === 0 && seq.coverVis === 'hidden', JSON.stringify(seq));
// panel heights
const ph = await p.evaluate(() => { const o = {}; document.querySelectorAll(PANEL).forEach((d) => { const was = d.hidden; d.hidden = false; o[d.id] = d.offsetHeight; d.hidden = was; }); return o; });
t('deck panels ≤ 1 viewport (900) on desktop', Object.values(ph).every((h) => h <= LIMITS.panelDesktop), JSON.stringify(ph));
const dh = await p.evaluate(() => document.documentElement.scrollHeight);
t('desktop page height ≤ 9,000 px', dh <= LIMITS.desktopH, dh + ' px');
const sizes = await p.evaluate(async () => { const f = async (u) => (await (await fetch(u)).text()).length; return { html: await f(FILES.html), css: await f(FILES.css), js: await f(FILES.js), backdrop: await f(FILES.backdrop) }; });
t('index+css+js ≤ 150 KB (backdrop ≤ 12 KB separately)', sizes.html + sizes.css + sizes.js <= LIMITS.bundleKB * 1024 && sizes.backdrop <= LIMITS.backdropKB * 1024, JSON.stringify(sizes));
t('desktop: 0 console errors', p._errs.length === 0, p._errs.slice(0, 2).join(' | '));
await p.close();
// ---- mobile (Pixel 7)
p = await mk({ ...devices['Pixel 7'] });
await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(1200);
const mb = []; for (const f of PROBES) { await scrollTo(p, await trackY(p, COVER, f)); mb.push(await beat(p)); }
t('mobile cover beats', mb.join(',') === BEATS_EXPECTED, mb.join(','));
const mv = await p.evaluate(() => { const v = document.querySelector(HERO_VIDEO); return { hasVideo: document.querySelector(COVER).classList.contains('has-video'), src: v && v.currentSrc && v.currentSrc.split('/').pop() }; });
t('mobile uses the portrait video (hero-m.mp4) or canvas', !mv.hasVideo || PORTRAIT_RE.test(mv.src), JSON.stringify(mv));
await p.evaluate(() => document.querySelector(FOLD_ANCHOR).scrollIntoView()); await p.waitForTimeout(400);
const snap = await p.evaluate(() => { const s = document.querySelector(SPREAD); const cs = getComputedStyle(s); return { snap: cs.scrollSnapType, overflow: cs.overflowX, scrollW: s.scrollWidth, clientW: s.clientWidth, tf: getComputedStyle(document.querySelector(FOLD_PANEL)).transform }; });
await p.evaluate(() => { const s = document.querySelector(SPREAD); s.scrollBy({ left: 400, behavior: 'auto' }); }); await p.waitForTimeout(400);
const sl = await p.evaluate(() => document.querySelector(SPREAD).scrollLeft);
t('mobile fold-out is a horizontal snap-scroll (no 3D)', /x mandatory/.test(snap.snap) && snap.scrollW > snap.clientW && sl > 100 && snap.tf === 'none', JSON.stringify({ ...snap, scrolledTo: sl }));
const bar = await p.evaluate(() => document.querySelector(MBAR).classList.contains('is-on'));
// 1 (round 2) cover fully clipped at the fold-out position, paper at (20,120)
await p.evaluate(() => document.querySelector(FOLD_ANCHOR).scrollIntoView()); await p.waitForTimeout(500);
const clip = await p.evaluate(() => { const cover = document.querySelector(COVER); const cs = getComputedStyle(cover); const el = document.elementFromPoint(20, 120); const bgOf = (e) => { while (e) { const b = getComputedStyle(e).backgroundColor; if (b && b !== 'rgba(0, 0, 0, 0)' && b !== 'transparent') return b; e = e.parentElement; } return 'none'; }; return { coverVis: cs.visibility, coverPE: cs.pointerEvents, inCover: !!(el && el.closest(COVER)), top: el && (el.className || el.tagName), bg: bgOf(el), hdrBg: getComputedStyle(document.querySelector('.hdr')).backgroundColor }; });
t('mobile fold-out: cover hidden, paper at (20,120), opaque header', clip.coverVis === 'hidden' && clip.coverPE === 'none' && !clip.inCover && clip.bg === PAPER_RGB && clip.hdrBg === PAPER_RGB, JSON.stringify(clip));
// 4 mobile fold-out geometry
const mf = await p.evaluate(() => { const pan = document.querySelector(FOLD_PANEL).getBoundingClientRect(); const g = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--gutter')) || 20; const bar = document.querySelector(MBAR).getBoundingClientRect(); const pin = document.querySelector(FOLD_PIN); const band = (() => { const c = document.querySelector(COVER).getBoundingClientRect(); const f = document.querySelector(FOLD).getBoundingClientRect(); return Math.round(c.bottom - f.top); })(); return { panelW: Math.round(pan.width), vw: innerWidth, docW: document.documentElement.scrollWidth, padB: parseFloat(getComputedStyle(pin).paddingBottom), barH: Math.round(bar.height), overlap: band }; });
t('mobile fold-out: panels fit the viewport, no overflow, padding clears the bar, cover overlaps the fold', mf.panelW <= mf.vw && mf.panelW >= mf.vw - 60 && mf.docW <= mf.vw && mf.padB >= mf.barH + 16 && mf.overlap > 0, JSON.stringify(mf));
t('mobile bottom bar appears after the cover CTA scrolls out', bar);
const mh = await p.evaluate(() => document.documentElement.scrollHeight);
t('mobile page height ≤ 12,000 px', mh <= LIMITS.mobileH, mh + ' px');
const mph = await p.evaluate(() => { const o = {}; document.querySelectorAll(PANEL).forEach((d) => { const was = d.hidden; d.hidden = false; o[d.id] = d.offsetHeight; d.hidden = was; }); return o; });
t('mobile deck panels ≤ 2 viewports (1830)', Object.values(mph).every((h) => h <= LIMITS.panelMobile), JSON.stringify(mph));
// 5 mobile deck: active tab in view, bottom bar clear of panel content
await p.evaluate(() => document.querySelector(DECK).scrollIntoView()); await p.waitForTimeout(300); await p.click(TAB(LAST_TAB)); await p.waitForTimeout(900);
const md = await p.evaluate(() => { const a = document.querySelector('[data-tab="contact"]').getBoundingClientRect(); const ul = document.querySelector(DECK_NAV + ' ul').getBoundingClientRect(); const fade = getComputedStyle(document.querySelector(DECK_NAV), '::after').width; return { tabIn: a.left >= ul.left - 1 && a.right <= ul.right + 1, fade }; });
await p.evaluate(() => { const d = document.querySelector(DECK); window.scrollTo(0, d.offsetTop + d.offsetHeight - innerHeight); }); await p.waitForTimeout(500);
const mb2 = await p.evaluate(() => { const panel = [...document.querySelectorAll(PANEL)].find((d) => !d.hidden); const last = panel.lastElementChild.getBoundingClientRect(); const bar = document.querySelector(MBAR).getBoundingClientRect(); return { lastBottom: Math.round(last.bottom), barTop: Math.round(bar.top) }; });
t('mobile deck: active tab scrolled into view, fade mask present, bar never covers panel content', md.tabIn && md.fade !== 'auto' && parseFloat(md.fade) > 0 && mb2.lastBottom < mb2.barTop, JSON.stringify({ ...md, ...mb2 }));
const ov = await p.evaluate(() => document.documentElement.scrollWidth - innerWidth);
t('Pixel 7: no horizontal overflow', ov <= 0, ov + ' px');
t('mobile: 0 console errors', p._errs.length === 0, p._errs.slice(0, 2).join(' | '));
await p.close();
// production assertions (replace the pitch-page ones)
import { readFileSync } from 'node:fs';
const html = readFileSync(SITE_DIR + 'index.html', 'utf8'), redir = readFileSync(SITE_DIR + '_redirects', 'utf8');
const allText = ['index.html', '404.html', 'css/styles.css', 'js/main.js', '_redirects', '_headers', 'sitemap.xml', 'robots.txt'].map((f) => readFileSync(SITE_DIR + f, 'utf8')).join('\n');
t('/book present in _redirects and no cal.com in HTML', /^\/book https:\/\/cal\.com\/\S+ 302$/m.test(redir) && /^\/call \/book 301$/m.test(redir) && !/cal\.com/.test(html) && /href="\/book"/.test(html));
t('no gmail anywhere in the site', !/gmail/i.test(allText) && SIGNATURE_RE.test(html));
p = await mk({ viewport: { width: 1440, height: 900 } }); await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(600);
await p.evaluate(() => document.querySelector('#deck').scrollIntoView()); await p.click('[data-tab="who"]'); await p.waitForTimeout(200);
const h0 = await p.evaluate(() => document.querySelector('[data-contact-h]').textContent);
await p.click('[data-persona="sales"]'); await p.waitForTimeout(300);
const ps = await p.evaluate(() => ({ h: document.querySelector('[data-contact-h]').textContent, hash: location.hash, q: location.search, pressed: document.querySelector('[data-persona="sales"]').getAttribute('aria-pressed'), first: [...document.querySelectorAll('[data-sys-id]')].sort((a, b) => (+getComputedStyle(a).order) - (+getComputedStyle(b).order))[0].dataset.sysId }));
t('persona switch changes 08 headline and hash', ps.h !== h0 && ps.hash === '#02-sales' && ps.q === '?for=sales' && ps.pressed === 'true' && ps.first === 'outbound', JSON.stringify(ps));
const r404 = await p.goto(base + '404.html'); const t404 = await p.textContent('h1');
t('404 page serves', r404.status() === 200 && /Nothing shipped here/.test(t404) && p._errs.length === 0, t404);
await p.close(); await b.close();
const pass = R.filter((r) => r.ok).length; console.log(`\n${pass}/${R.length} passed`);
writeFileSync(new URL(OUT_JSON, import.meta.url).pathname, JSON.stringify({ date: new Date().toISOString().slice(0, 10), pass, total: R.length, desktopHeight: dh, mobileHeight: mh, panelHeightsDesktop: ph, panelHeightsMobile: mph, sizes, results: R }, null, 2));
process.exit(pass === R.length ? 0 : 1);
