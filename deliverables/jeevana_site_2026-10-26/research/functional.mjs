#!/usr/bin/env node
/* functional.mjs — Jeevana production site. Adapted from .claude/skills/site-redesign/scripts/functional_template.mjs:
   every template assertion kept (selectors set for this build), plus the brief's additions (autoplay, scroll takeover,
   rail mantra, i18n, newsletter dialog, register success, dead-link guard, photo swap, missing-frame hold).
   usage: node research/serve_csp.mjs site 8794 &  node research/functional.mjs http://localhost:8794/
   outputs: research/functional.json; exit 0 only on N/N. All /api/* calls are mocked to 200 {ok:true}. */
const argv = process.argv.slice(2);
if (!argv[0] || argv.includes('--help')) { console.log('functional.mjs <base-url>'); process.exit(argv[0] ? 0 : 2); }
// ======================= CONFIG =======================
const PITCH_PATH = '404.html';             // production build: no pitch page; the 404 carries the signature instead
const SIGNATURE_RE = /debanjan@prodcraft\.fyi/;
const BEATS_EXPECTED = '0,1,2'; const BEAT_PROBES = [0.05, 0.3, 0.7];
const TAB_ORDER = ['classes', 'register', 'contact', 'about']; const FIRST_TAB = 'about'; const LAST_TAB = 'contact'; const LAST_TAB_LABEL = /05 Contact/;
const DEEP_LINK = 'register'; const COUNTER_TAB = 'about'; const COUNTERS_EXPECTED = '12,8,4'; const GAL_COUNT = 11; // tree + twist + the 9 distinct cover photos (round-1 decision A5)
const PAPER_RGB = 'rgb(243, 238, 228)';
const FILES = { html: 'index.html', css: 'css/styles.css', js: 'js/main.js', i18n: 'js/i18n.js', backdrop: 'js/backdrop.js' };
const LIMITS = { desktopH: 7000, mobileH: 9000, panelDesktop: 900, panelMobile: 1830, bundleKB: 150, backdropKB: 12 };
// ======================= end CONFIG =======================
import { createRequire } from 'node:module'; import { writeFileSync } from 'node:fs';
process.env.PLAYWRIGHT_BROWSERS_PATH ||= '/opt/pw-browsers';
const _req = createRequire(import.meta.url); let _pw; for (const p of ['/opt/node-tools/node_modules/playwright', 'playwright']) { try { _pw = _req(p); break; } catch {} }
if (!_pw) { console.error('playwright not found'); process.exit(2); }
const { chromium, devices } = _pw;
const base = argv[0].endsWith('/') ? argv[0] : argv[0] + '/'; const R = []; const t = (name, ok, info) => { R.push({ name, ok: !!ok, info }); console.log((ok ? 'ok   ' : 'FAIL ') + name + (info !== undefined ? ' — ' + info : '')); };
const b = await chromium.launch();
const IGN = /fonts\.g|ERR_CERT|ERR_TUNNEL|ERR_NAME|ERR_PROXY/;
async function mk(opts, { seen = true } = {}) {
  const ctx = await b.newContext(opts); const p = await ctx.newPage(); const errs = [];
  p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => { if (m.type() === 'error' && !IGN.test(m.text() + (m.location().url || ''))) errs.push(m.text() + ' ' + (m.location().url || '')); });
  p.on('requestfailed', (r) => { if (!IGN.test(r.url() + (r.failure() || {}).errorText) && !/ERR_ABORTED/.test((r.failure() || {}).errorText)) errs.push('requestfailed ' + r.url()); });
  await p.route('**/api/**', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: '{"ok":true}' }));
  if (seen) await p.addInitScript(() => { try { localStorage.setItem('jv-news-seen', '1'); localStorage.setItem('jv-lang', 'en'); } catch (e) {} });
  else await p.addInitScript(() => { try { localStorage.setItem('jv-lang', 'en'); } catch (e) {} });
  p._errs = errs; p._ctx = ctx; return p;
}
const close = (p) => p._ctx.close();
const scrollTo = async (p, y) => { await p.evaluate((v) => { document.documentElement.style.scrollBehavior = 'auto'; window.scrollTo(0, v); }, y); await p.waitForTimeout(350); };
const trackY = (p, sel, f) => p.evaluate(([s, f]) => { const el = document.querySelector(s); return el.offsetTop + (el.offsetHeight - innerHeight) * f; }, [sel, f]);
const beat = (p) => p.evaluate(() => { const x = [...document.querySelectorAll('[data-beat]')].find((e) => e.classList.contains('is-on')); return x ? +x.dataset.beat : -1; });
const frameIdx = (p) => p.evaluate(() => +document.querySelector('[data-cover]').dataset.frameIndex);
const onImg = (p) => p.evaluate(() => { const i = document.querySelector('[data-frame] .cover__img.is-on'); return i ? { src: (i.currentSrc || i.src).split('/').pop(), nw: i.naturalWidth, op: getComputedStyle(i).opacity } : null; });
const visPanels = (p) => p.evaluate(() => [...document.querySelectorAll('.dp')].filter((d) => !d.hidden).map((d) => d.id));
const D = { viewport: { width: 1440, height: 900 } };

// ---- autoplay before any scroll (fresh page, at scroll 0)
let p = await mk(D);
await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(3100);
const ap = await p.evaluate(() => ({ i: +document.querySelector('[data-cover]').dataset.frameIndex, mode: document.querySelector('[data-cover]').dataset.autoplay, y: scrollY }));
t('autoplay advances the frame index without scrolling (frame ≥ 3 after 3 s)', ap.i >= 3 && ap.y === 0, JSON.stringify(ap));
await scrollTo(p, await trackY(p, '[data-cover]', 0.5)); await p.waitForTimeout(300);
const tk = await p.evaluate(() => ({ i: +document.querySelector('[data-cover]').dataset.frameIndex, mode: document.querySelector('[data-cover]').dataset.autoplay }));
await p.waitForTimeout(1000); const tk2 = await frameIdx(p);
t('scroll takes over (autoplay stops, frame = floor(p*12))', tk.mode === 'off' && tk.i === 6 && tk2 === 6, JSON.stringify({ ...tk, after1s: tk2 }));
const m6 = await p.evaluate(() => document.querySelector('[data-rail-key="mantra"]').textContent);
await scrollTo(p, await trackY(p, '[data-cover]', 0.76)); const m9 = await p.evaluate(() => ({ m: document.querySelector('[data-rail-key="mantra"]').textContent, tr: document.querySelector('[data-rail-key="tr"]').textContent, no: document.querySelector('[data-rail-no]').textContent }));
t('rail mantra text changes with frame', m6 === 'Om Hiraṇyagarbhāya Namaḥ' && m9.m === 'Om Savitre Namaḥ' && m9.no === '10' && m9.tr === 'to the stimulating power', JSON.stringify({ m6, ...m9 }));
// photo swap: frames 01-02 are the real webp
await scrollTo(p, await trackY(p, '[data-cover]', 0.01)); await p.waitForTimeout(1000); const ph0 = { i: await frameIdx(p), ...(await onImg(p)) };
await scrollTo(p, await trackY(p, '[data-cover]', 0.1)); await p.waitForTimeout(1000); const ph1 = { i: await frameIdx(p), ...(await onImg(p)) };
t('photo swap: frames 01–02 render the real webp', ph0.i === 0 && /^sn-01(-m)?\.webp$/.test(ph0.src) && ph0.nw > 0 && ph1.i === 1 && /^sn-02(-m)?\.webp$/.test(ph1.src) && ph1.nw > 0 && ph1.op === '1', JSON.stringify([ph0, ph1]));
await close(p);
// missing frame: manifest without sn-03 holds sn-02 (no empty frame, no drawn figure)
p = await mk(D);
await p.route('**/assets/img/manifest.json', async (r) => { const res = await r.fetch(); const j = await res.json(); delete j.frames['sn-03']; r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(j) }); });
await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(600);
await scrollTo(p, await trackY(p, '[data-cover]', 0.18)); await p.waitForTimeout(1000);
const mf3 = await p.evaluate(() => { const f = document.querySelector('[data-frame]'); const i = f.querySelector('.cover__img.is-on'); return { i: +document.querySelector('[data-cover]').dataset.frameIndex, src: i && (i.currentSrc || i.src).split('/').pop(), nw: i && i.naturalWidth, hold: f.classList.contains('is-hold'), drawn: f.querySelectorAll('svg,canvas').length, rail: document.querySelector('[data-rail-key="iast"]').textContent }; });
t('a frame without a manifest entry holds the previous real image (no empty, no drawn figure)', mf3.i === 2 && /^sn-02(-m)?\.webp$/.test(mf3.src) && mf3.nw > 0 && mf3.hold && mf3.drawn === 0 && mf3.rail === 'Pādahastāsana', JSON.stringify(mf3));
await close(p);

// ---- desktop (template suite)
p = await mk(D);
await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(1500);
const beats = []; for (const f of BEAT_PROBES) { await scrollTo(p, await trackY(p, '[data-cover]', f)); beats.push(await beat(p)); }
t('cover beats change at 25/50/75% of the track', beats.join(',') === BEATS_EXPECTED, beats.join(','));
await p.waitForTimeout(1200);
const vs = await p.evaluate(() => { const v = document.querySelector('[data-hero-video]'); const c = document.querySelector('[data-backdrop]'); return { hasVideo: document.querySelector('[data-cover]').classList.contains('has-video'), playing: !!(v && !v.paused && v.readyState >= 2), src: v && v.currentSrc.split('/').pop(), canvasVisible: !!c && getComputedStyle(c).display !== 'none' }; });
t('video plays (or canvas fallback runs)', vs.playing || vs.canvasVisible, JSON.stringify(vs));
await scrollTo(p, 0);
const f0 = await p.evaluate(() => getComputedStyle(document.querySelector('.panel--left')).transform);
await scrollTo(p, await trackY(p, '[data-fold]', 0.5)); const f50 = await p.evaluate(() => getComputedStyle(document.querySelector('.panel--left')).transform);
await scrollTo(p, await trackY(p, '[data-fold]', 1)); await p.waitForTimeout(300);
const fEnd = await p.evaluate(() => ({ tf: getComputedStyle(document.querySelector('.panel--left')).transform, fold: getComputedStyle(document.querySelector('[data-spread]')).getPropertyValue('--fold').trim(), open: document.querySelector('[data-fold]').classList.contains('is-open') }));
t('fold-out hinge transform changes with scroll', f0 !== f50 && f50 !== fEnd.tf, `${f0.slice(0, 30)} → ${f50.slice(0, 30)} → ${fEnd.tf.slice(0, 30)}`);
t('fold-out fully open by track end', fEnd.fold === '1.0000' && fEnd.open && /^(none|matrix\(1, 0, 0, 1, 0, 0\))$/.test(fEnd.tf), JSON.stringify(fEnd));
await p.evaluate(() => document.querySelector('#deck').scrollIntoView()); await p.waitForTimeout(400);
let okTabs = true; const info = [];
for (const id of TAB_ORDER) { await p.click(`[data-tab="${id}"]`); await p.waitForTimeout(250); const v = await visPanels(p); const h = await p.evaluate(() => location.hash); info.push(id + ':' + v.join('/') + h); if (!(v.length === 1 && v[0] === id && h === '#' + id)) okTabs = false; }
t('each chapter tab switches the panel and updates the hash', okTabs, info.join(' | '));
await p.goBack(); await p.waitForTimeout(400); const back1 = await visPanels(p); const bh = await p.evaluate(() => location.hash);
t('back button restores the previous panel', back1[0] === LAST_TAB && bh === '#' + LAST_TAB, back1.join('/') + ' ' + bh);
const chapterInd = await p.evaluate(() => document.querySelector('[data-chapter-no]').textContent + ' ' + document.querySelector('[data-chapter-name]').textContent);
t('header chapter indicator follows the deck', LAST_TAB_LABEL.test(chapterInd), chapterInd);
await p.focus(`[data-tab="${LAST_TAB}"]`); await p.keyboard.press('ArrowRight'); await p.waitForTimeout(250);
t('keyboard ArrowRight wraps to the first chapter', (await visPanels(p))[0] === FIRST_TAB, (await visPanels(p)).join());
const p2 = await mk(D); await p2.goto(base + '#' + DEEP_LINK, { waitUntil: 'load' }); await p2.waitForTimeout(900);
t('deep link /#register opens the Register panel', (await visPanels(p2))[0] === DEEP_LINK, (await visPanels(p2)).join());
await close(p2);
await scrollTo(p, await trackY(p, '[data-fold]', 1)); await p.click('[data-album]'); await p.waitForTimeout(400);
const gOpen = await p.evaluate(() => ({ open: document.querySelector('[data-gallery]').open, n: [...document.querySelectorAll('[data-gal-grid] img')].filter((i) => /assets\/img\/(photo|sn)-\d+/.test(i.src)).length, title: document.querySelector('[data-gal-title]').textContent }));
await p.keyboard.press('Escape'); await p.waitForTimeout(200); const gClosed = await p.evaluate(() => !document.querySelector('[data-gallery]').open);
t('gallery dialog opens and closes', gOpen.open && gOpen.n === GAL_COUNT && gClosed, JSON.stringify(gOpen));
await p.evaluate(() => document.querySelector('#deck').scrollIntoView()); await p.click('[data-tab="classes"]'); await p.waitForTimeout(200); await p.click(`[data-tab="${COUNTER_TAB}"]`); await p.waitForTimeout(1500);
const cnt = await p.evaluate(() => [...document.querySelectorAll('#about [data-count]')].map((e) => e.textContent));
t('counters settle on the exact published values', cnt.join() === COUNTERS_EXPECTED, cnt.join());
// round-1 geometry: last beat + CTAs held to p=1, plate shown, fold enters only in the last 20 %
await scrollTo(p, await trackY(p, '[data-cover]', 1)); await p.waitForTimeout(500);
const endState = await p.evaluate(() => { const bt = document.querySelector('[data-beat="2"]'); const fr = document.querySelector('[data-fold]').getBoundingClientRect(); const ctas = [...bt.querySelectorAll('.btn')].map((a) => { const r = a.getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight && getComputedStyle(a).visibility !== 'hidden'; }); return { beatOn: bt.classList.contains('is-on'), beatOpacity: getComputedStyle(bt).opacity, bodyOpacity: getComputedStyle(document.querySelector('.cover__body')).opacity, ctas, foldTopVh: +(fr.top / innerHeight).toFixed(3), plate: getComputedStyle(document.querySelector('[data-plate="2"]')).opacity }; });
t('cover end: last beat + CTAs held to p=1, photo plate shown, fold entering in the last 20 % (no empty viewport)', endState.beatOn && endState.beatOpacity === '1' && +endState.bodyOpacity >= 0.85 && endState.ctas.length === 2 && endState.ctas.every(Boolean) && endState.plate === '1' && endState.foldTopVh >= 0.7 && endState.foldTopVh < 1, JSON.stringify(endState));
await p.evaluate(() => { const h = document.querySelector('.fold__head').getBoundingClientRect(); scrollBy(0, h.top - innerHeight * 0.5); }); await p.waitForTimeout(400);
const seq = await p.evaluate(() => ({ foldText: getComputedStyle(document.querySelector('.fold__head')).opacity, headTopVh: +(document.querySelector('.fold__head').getBoundingClientRect().top / innerHeight).toFixed(2), coverBody: getComputedStyle(document.querySelector('.cover__body')).opacity }));
t('fade sequence: cover text at 0 before chapter headline passes 0.1', +seq.foldText > 0.1 && +seq.coverBody === 0, JSON.stringify(seq));
// one brand on screen at p = 0 / .5 / 1; no cover element intersects the plate
const brandAt = []; const hits = [];
for (const f of [0, 0.5, 1]) { await scrollTo(p, await trackY(p, '[data-cover]', f)); await p.waitForTimeout(600);
  brandAt.push(await p.evaluate(() => { const vis = (e) => { if (!e) return false; const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return r.width > 0 && cs.display !== 'none' && cs.visibility !== 'hidden' && r.bottom > 0 && r.top < innerHeight && +getComputedStyle(e.closest('[data-beat]') || e).opacity > 0.5; }; return [document.querySelector('[data-beat="0"].is-on .cover__brand'), document.querySelector('.hdr__logo')].filter(vis).length; }));
  hits.push(await p.evaluate(() => { const fr = document.querySelector('[data-frame]').getBoundingClientRect(); const els = [...document.querySelectorAll('[data-beat].is-on > *, .rail > *, .cover__hint')]; return els.filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && getComputedStyle(e).opacity !== '0' && r.left < fr.right - 1 && fr.left < r.right - 1 && r.top < fr.bottom - 1 && fr.top < r.bottom - 1; }).map((e) => e.className || e.tagName); })); }
t('one brand element visible at p = 0 / .5 / 1', brandAt.every((n) => n === 1), brandAt.join(','));
t('no cover text or rail element intersects the plate (1440, p 0/.5/1)', hits.every((h) => h.length === 0), JSON.stringify(hits));
const ph = await p.evaluate(() => { const o = {}; document.querySelectorAll('.dp').forEach((d) => { const was = d.hidden; d.hidden = false; o[d.id] = d.offsetHeight; d.hidden = was; }); return o; });
t('deck panels ≤ 1 viewport (900) on desktop', Object.values(ph).every((h) => h <= LIMITS.panelDesktop), JSON.stringify(ph));
const dh = await p.evaluate(() => document.documentElement.scrollHeight);
t('desktop page height ≤ 7,000 px', dh <= LIMITS.desktopH, dh + ' px');
const sizes = await p.evaluate(async (F) => { const f = async (u) => (await (await fetch(u)).arrayBuffer()).byteLength; const o = {}; for (const k of Object.keys(F)) o[k] = await f(F[k]); return o; }, FILES);
t('index+css+js ≤ 150 KB (backdrop ≤ 12 KB separately)', sizes.html + sizes.css + sizes.js + sizes.i18n <= LIMITS.bundleKB * 1024 && sizes.backdrop <= LIMITS.backdropKB * 1024, JSON.stringify(sizes));
// dead-link guard
const dl = await p.evaluate(() => { const bad = [...document.querySelectorAll('a')].filter((a) => { const h = a.getAttribute('href'); if (h === null) return !a.hidden && !a.closest('[hidden]'); return h === '#' || h === '' || /^tel:\s*$/.test(h) || /^https?:\/\/\s*$/.test(h); }); return { bad: bad.map((a) => a.outerHTML.slice(0, 80)), tel: [...document.querySelectorAll('a[href^="tel:"]')].map((a) => a.getAttribute('href')), wa: [...document.querySelectorAll('a[href*="wa.me"]')].length }; });
t('dead-link guard: zero href="#" / empty tel: links in DOM (phone + WhatsApp live)', dl.bad.length === 0 && dl.tel.length >= 2 && dl.tel.every((h) => h === 'tel:+33754287210') && dl.wa >= 2, JSON.stringify(dl));
// i18n
await scrollTo(p, 0); await p.waitForTimeout(300);
const before = await p.evaluate(() => [...document.querySelectorAll('[data-i18n]')].map((e) => e.textContent));
await p.click('[data-lang="fr"]'); await p.waitForTimeout(300);
const fr = await p.evaluate((bef) => { const now = [...document.querySelectorAll('[data-i18n]')].map((e) => e.textContent); return { lang: document.documentElement.lang, changed: now.filter((x, i) => x !== bef[i]).length, title: document.title, stored: localStorage.getItem('jv-lang'), tag: document.querySelector('.cover__tag').textContent }; }, before);
await p.click('[data-lang="en"]'); await p.waitForTimeout(200); const backEn = await p.evaluate(() => document.documentElement.lang);
t('i18n switch flips html[lang] and ≥ 20 strings', fr.lang === 'fr' && fr.changed >= 20 && fr.tag === 'Yoga à Paris' && fr.stored === 'fr' && backEn === 'en', JSON.stringify(fr));
// register form
await p.evaluate(() => document.querySelector('#deck').scrollIntoView()); await p.click('[data-tab="register"]'); await p.waitForTimeout(300);
let posted = null; p.on('request', (r) => { if (r.url().includes('/api/register')) posted = r.postDataJSON(); });
await p.fill('[data-reg] [name="name"]', 'Test Person'); await p.fill('[data-reg] [name="email"]', 'test@example.com'); await p.check('[data-reg] [name="consent"]');
await p.click('[data-reg] button[type="submit"]'); await p.waitForTimeout(800);
const reg = await p.evaluate(() => ({ ok: !document.querySelector('[data-reg-ok]').hidden, err: !document.querySelector('[data-reg-err]').hidden }));
t('register form posts to /api/register and shows success (mocked fetch)', reg.ok && !reg.err && posted && posted.email === 'test@example.com' && posted.consent === true && posted.website === '', JSON.stringify({ ...reg, posted }));
await p.screenshot({ path: new URL('../screens/deck-register-success.png', import.meta.url).pathname });
t('desktop: 0 console errors', p._errs.length === 0, p._errs.slice(0, 2).join(' | '));
await close(p);

// ---- newsletter dialog (fresh visitor)
p = await mk(D, { seen: false });
await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(1500);
const onCoverOpen = await p.evaluate(() => document.querySelector('[data-news]').open);
await p.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; document.querySelector('#deck').scrollIntoView(); }); await p.waitForTimeout(400); await p.evaluate(() => scrollBy(0, 1)); await p.waitForTimeout(2600);
const nOpen = await p.evaluate(() => ({ open: document.querySelector('[data-news]').open, focusIn: document.querySelector('[data-news]').contains(document.activeElement), seen: !!localStorage.getItem('jv-news-seen') }));
await p.screenshot({ path: new URL('../screens/newsletter-dialog.png', import.meta.url).pathname });
await p.keyboard.press('Escape'); await p.waitForTimeout(300); const nClosed = await p.evaluate(() => !document.querySelector('[data-news]').open);
await p.reload({ waitUntil: 'load' }); await p.waitForTimeout(600); await p.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; document.querySelector('#deck').scrollIntoView(); }); await p.waitForTimeout(400); await p.evaluate(() => scrollBy(0, 1)); await p.waitForTimeout(2600);
const reopen = await p.evaluate(() => document.querySelector('[data-news]').open);
t('newsletter dialog opens after deck activation, closes on Esc, never reopens after close', !onCoverOpen && nOpen.open && nOpen.focusIn && nOpen.seen && nClosed && !reopen, JSON.stringify({ onCoverOpen, ...nOpen, nClosed, reopen }));
t('newsletter page: 0 console errors', p._errs.length === 0, p._errs.slice(0, 2).join(' | '));
await close(p);

// ---- mobile (Pixel 7)
p = await mk({ ...devices['Pixel 7'] });
await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(1200);
const mb = []; for (const f of BEAT_PROBES) { await scrollTo(p, await trackY(p, '[data-cover]', f)); mb.push(await beat(p)); }
t('mobile cover beats', mb.join(',') === BEATS_EXPECTED, mb.join(','));
await p.waitForTimeout(800);
const mv = await p.evaluate(() => { const v = document.querySelector('[data-hero-video]'); return { hasVideo: document.querySelector('[data-cover]').classList.contains('has-video'), src: v && v.currentSrc && v.currentSrc.split('/').pop() }; });
t('mobile uses the portrait video (hero-m.mp4) or canvas', !mv.hasVideo || /hero-m/.test(mv.src), JSON.stringify(mv));
await p.evaluate(() => document.querySelector('#practice').scrollIntoView()); await p.waitForTimeout(400);
const snap = await p.evaluate(() => { const s = document.querySelector('[data-spread]'); const cs = getComputedStyle(s); return { snap: cs.scrollSnapType, overflow: cs.overflowX, scrollW: s.scrollWidth, clientW: s.clientWidth, tf: getComputedStyle(document.querySelector('.panel--left')).transform }; });
await p.evaluate(() => { document.querySelector('[data-spread]').scrollBy({ left: 400, behavior: 'auto' }); }); await p.waitForTimeout(400);
const sl = await p.evaluate(() => document.querySelector('[data-spread]').scrollLeft);
t('mobile fold-out is a horizontal snap-scroll (no 3D)', /x mandatory/.test(snap.snap) && snap.scrollW > snap.clientW && sl > 100 && snap.tf === 'none', JSON.stringify({ ...snap, scrolledTo: sl }));
const bar = await p.evaluate(() => document.querySelector('[data-mbar]').classList.contains('is-on'));
await p.evaluate(() => document.querySelector('#practice').scrollIntoView()); await p.waitForTimeout(500);
const clip = await p.evaluate((PAPER) => { const cover = document.querySelector('[data-cover]'); const cs = getComputedStyle(cover); const el = document.elementFromPoint(20, 120); const bgOf = (e) => { while (e) { const bg = getComputedStyle(e).backgroundColor; if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') return bg; e = e.parentElement; } return 'none'; }; return { coverVis: cs.visibility, coverPE: cs.pointerEvents, inCover: !!(el && el.closest('[data-cover]')), top: el && (el.className || el.tagName), bg: bgOf(el), hdrBg: getComputedStyle(document.querySelector('.hdr')).backgroundColor }; });
t('mobile fold-out: cover hidden, paper at (20,120), opaque header', clip.coverVis === 'hidden' && clip.coverPE === 'none' && !clip.inCover && clip.bg === PAPER_RGB && clip.hdrBg === PAPER_RGB, JSON.stringify(clip));
const mf = await p.evaluate(() => { const pan = document.querySelector('.panel--left').getBoundingClientRect(); const bar = document.querySelector('[data-mbar]').getBoundingClientRect(); const pin = document.querySelector('.fold__pin'); const c = document.querySelector('[data-cover]').getBoundingClientRect(); const f = document.querySelector('[data-fold]').getBoundingClientRect(); return { panelW: Math.round(pan.width), vw: innerWidth, docW: document.documentElement.scrollWidth, padB: parseFloat(getComputedStyle(pin).paddingBottom), barH: Math.round(bar.height), overlap: Math.round(c.bottom - f.top) }; });
t('mobile fold-out: panels fit the viewport, no overflow, padding clears the bar, cover overlaps the fold', mf.panelW <= mf.vw && mf.panelW >= mf.vw - 60 && mf.docW <= mf.vw && mf.padB >= mf.barH + 16 && mf.overlap > 0, JSON.stringify(mf));
t('mobile bottom bar appears after the cover CTA scrolls out', bar);
const mh = await p.evaluate(() => document.documentElement.scrollHeight);
t('mobile page height ≤ 9,000 px', mh <= LIMITS.mobileH, mh + ' px');
const mph = await p.evaluate(() => { const o = {}; document.querySelectorAll('.dp').forEach((d) => { const was = d.hidden; d.hidden = false; o[d.id] = d.offsetHeight; d.hidden = was; }); return o; });
t('mobile deck panels ≤ 2 viewports (1830)', Object.values(mph).every((h) => h <= LIMITS.panelMobile), JSON.stringify(mph));
await p.evaluate(() => document.querySelector('#deck').scrollIntoView()); await p.waitForTimeout(300); await p.click(`[data-tab="${LAST_TAB}"]`); await p.waitForTimeout(900);
const md = await p.evaluate(() => { const a = document.querySelector('[data-tab="contact"]').getBoundingClientRect(); const ul = document.querySelector('[data-deck-nav] ul').getBoundingClientRect(); const fade = getComputedStyle(document.querySelector('[data-deck-nav]'), '::after').width; return { tabIn: a.left >= ul.left - 1 && a.right <= ul.right + 1, fade }; });
await p.evaluate(() => { const d = document.querySelector('#deck'); window.scrollTo(0, d.offsetTop + d.offsetHeight - innerHeight); }); await p.waitForTimeout(500);
const mb2 = await p.evaluate(() => { const panel = [...document.querySelectorAll('.dp')].find((d) => !d.hidden); const last = panel.lastElementChild.getBoundingClientRect(); const bar = document.querySelector('[data-mbar]').getBoundingClientRect(); return { lastBottom: Math.round(last.bottom), barTop: Math.round(bar.top) }; });
t('mobile deck: active tab scrolled into view, fade mask present, bar never covers panel content', md.tabIn && md.fade !== 'auto' && parseFloat(md.fade) > 0 && mb2.lastBottom < mb2.barTop, JSON.stringify({ ...md, ...mb2 }));
const ov = await p.evaluate(() => document.documentElement.scrollWidth - innerWidth);
t('Pixel 7: no horizontal overflow', ov <= 0, ov + ' px');
t('mobile: 0 console errors', p._errs.length === 0, p._errs.slice(0, 2).join(' | '));
await close(p);
// iPhone 13 console
p = await mk({ ...devices['iPhone 13'] }); await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(1500);
await scrollTo(p, await trackY(p, '[data-cover]', 1)); await p.waitForTimeout(500);
const c390 = await p.evaluate(() => [...document.querySelectorAll('[data-beat="2"] .btn')].map((a) => { const r = a.getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight; }));
t('CTAs visible at p = 1 on 390 px (iPhone 13)', c390.length === 2 && c390.every(Boolean), JSON.stringify(c390));
for (const f of [0.3, 0.7, 1]) { await scrollTo(p, await p.evaluate((f) => (document.documentElement.scrollHeight - innerHeight) * f, f)); }
t('iPhone 13: 0 console errors', p._errs.length === 0, p._errs.slice(0, 2).join(' | '));
await close(p);
// production page in place of the pitch page
p = await mk(D); await p.goto(base + PITCH_PATH, { waitUntil: 'load' }); await p.waitForTimeout(600);
t('pitch page: 0 console errors, signature present (production: 404.html carries it; no pitch page ships)', p._errs.length === 0 && (await p.evaluate((re) => new RegExp(re).test(document.body.innerHTML), SIGNATURE_RE.source)));
await close(p); await b.close();
const pass = R.filter((r) => r.ok).length; console.log(`\n${pass}/${R.length} passed`);
writeFileSync(new URL('./functional.json', import.meta.url).pathname, JSON.stringify({ date: new Date().toISOString().slice(0, 10), pass, total: R.length, desktopHeight: dh, mobileHeight: mh, panelHeightsDesktop: ph, panelHeightsMobile: mph, sizes, results: R }, null, 2));
process.exit(pass === R.length ? 0 : 1);
