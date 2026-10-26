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
// cover track = cover height − 1 vh − the drum's overlap (the drum enters only after p = 1; review_round2 §1b)
const trackY = (p, sel, f) => p.evaluate(([s, f]) => { const el = document.querySelector(s); let span = el.offsetHeight - innerHeight; if (el.matches('[data-cover]')) span -= Math.max(0, -parseFloat(getComputedStyle(document.querySelector('[data-fold]')).marginTop) || 0); return el.offsetTop + Math.max(0, span) * f; }, [sel, f]);
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
// ======================= round 3 (review_round2.md) — every item is a numeric assertion over the screens.mjs matrix =======================
const VP19 = { 'mobile': 'Pixel 7', 'iphone-se': [375, 667, 1], 'galaxy-s8': [360, 740, 1], 'iphone-13': [390, 844, 1], 'pixel-7': [412, 915, 1], 'iphone-15-pro-max': [430, 932, 1], 'phone-landscape': [844, 390, 1], 'small-tablet': [600, 960, 1], 'ipad-portrait': [820, 1180, 0], 'ipad-landscape': [1180, 820, 0], 'ipad-pro-portrait': [1024, 1366, 0], 'ipad-pro-landscape': [1366, 1024, 0], 'laptop-1280': [1280, 800, 0], 'laptop-1440': [1440, 900, 0], 'laptop-1536': [1536, 864, 0], 'desktop-1080p': [1920, 1080, 0], 'desktop-1440p': [2560, 1440, 0], 'desktop-4k': [3840, 2160, 0], 'tv-portrait': [1080, 1920, 0] };
const vpOpts = (spec) => Array.isArray(spec) ? { viewport: { width: spec[0], height: spec[1] }, isMobile: !!spec[2], hasTouch: !!spec[2], deviceScaleFactor: 1 } : { ...devices[spec] };
const MAN = await (await fetch(base + 'assets/img/manifest.json')).json();
// in-page probe: every geometry number the review asks for, from real DOM boxes
const probe = (p, man) => p.evaluate((man) => {
  const R = (e) => { if (!e) return null; const r = e.getBoundingClientRect(); return { l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height }; };
  const op = (e) => { let o = 1; while (e && e.nodeType === 1) { const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden') return 0; o *= +cs.opacity; e = e.parentElement; } return o; };
  const inter = (a, b) => !!(a && b && a.l < b.r - 1 && b.l < a.r - 1 && a.t < b.b - 1 && b.t < a.b - 1);
  const union = (els) => els.map(R).filter((x) => x && x.w > 0).reduce((u, x) => u ? { l: Math.min(u.l, x.l), t: Math.min(u.t, x.t), r: Math.max(u.r, x.r), b: Math.max(u.b, x.b) } : x, null);
  const vh = innerHeight, vw = innerWidth, portrait = matchMedia('(orientation: portrait)').matches;
  const cover = document.querySelector('[data-cover]'), fold = document.querySelector('[data-fold]'), frame = document.querySelector('[data-frame]');
  // §2 body box: manifest body bbox mapped through object-fit/object-position of the shown <img> into the plate rect
  const im = frame.querySelector('.cover__img.is-on'); const file = im ? (im.currentSrc || im.src).split('/').pop() : '';
  const rec = Object.values(man.frames).find((f) => f.file === file || f.mfile === file); let body = null, plate = null;
  if (im && rec && im.naturalWidth) {
    const r = im.getBoundingClientRect(), cs = getComputedStyle(im), nw = im.naturalWidth, nh = im.naturalHeight;
    const s = cs.objectFit === 'cover' ? Math.max(r.width / nw, r.height / nh) : cs.objectFit === 'contain' ? Math.min(r.width / nw, r.height / nh) : r.width / nw;
    const cw = nw * s, ch = nh * s, [px, py] = cs.objectPosition.split(' ').map((v, i) => v.endsWith('%') ? (parseFloat(v) / 100) * ((i ? r.height - ch : r.width - cw)) : parseFloat(v));
    const bb = rec.body || rec.box; const ox = r.left + px, oy = r.top + py;
    body = { l: ox + bb[0] * cw, t: oy + bb[1] * ch, r: ox + bb[2] * cw, b: oy + bb[3] * ch };
    const fr = frame.getBoundingClientRect(); plate = { l: Math.max(0, fr.left), t: Math.max(0, fr.top), r: Math.min(vw, fr.right), b: Math.min(vh, fr.bottom) }; plate.h = plate.b - plate.t;
  }
  const bodyVis = body && plate ? Math.max(0, Math.min(body.b, plate.b) - Math.max(body.t, plate.t)) : 0;
  const crop = body && plate ? { file, bodyH: +(bodyVis / plate.h).toFixed(3), feet: +((plate.b - body.b) / plate.h).toFixed(3), head: +((body.t - plate.t) / plate.h).toFixed(3) } : null;
  // §1 cover end
  const ctas = document.querySelector('[data-beat="2"] .ctas'); const cr = R(ctas);
  const hit = [...document.querySelectorAll('[data-beat="2"] .btn')].every((a) => { const q = a.getBoundingClientRect(); const e = document.elementFromPoint(q.left + q.width / 2, q.top + q.height / 2); return !!(e && (e === a || a.contains(e))); });
  const beat = document.querySelector('[data-beat].is-on'); const copy = beat ? union([...beat.children]) : null;
  // §4a/§4d header
  const ch = document.querySelector('[data-chapter-no]'); const chVis = ch && op(ch) > 0.05 && ch.getBoundingClientRect().width > 0 && ch.textContent.trim() === '00';
  const vis = (e) => { if (!e) return false; const r = e.getBoundingClientRect(); return r.width > 0 && r.bottom > 0 && r.top < vh && op(e) > 0.5; };
  const brands = [document.querySelector('[data-beat="0"] .cover__brand'), document.querySelector('.hdr__logo')].filter(vis).length;
  const lang = R(document.querySelector('.hdr .lang')), hdrEl = document.querySelector('.hdr'), padEnd = parseFloat(getComputedStyle(hdrEl).paddingInlineEnd);
  // §3 canvas: alpha at wordmark / sutra / CTA boxes, hard-disc scan, stacking + mask
  const cv = document.querySelector('[data-backdrop]'); let alpha = null, disc = 0;
  if (cv && cv.width && getComputedStyle(cv).display !== 'none') { try {
    const x = cv.getContext('2d'), k = cv.width / cv.clientWidth, cvr = cv.getBoundingClientRect(); alpha = 0;
    const boxes = [...document.querySelectorAll('.cover__brand, [data-beat].is-on .sutra__dev, [data-beat].is-on .sutra__iast, [data-beat].is-on .sutra__tr, [data-beat].is-on .ctas')].filter((e) => op(e) > 0.05).map(R).filter((b) => b && b.w > 0);
    for (const b of boxes) { const x0 = Math.max(0, Math.floor((b.l - cvr.left) * k)), y0 = Math.max(0, Math.floor((b.t - cvr.top) * k)), w = Math.min(cv.width - x0, Math.ceil(b.w * k)), h = Math.min(cv.height - y0, Math.ceil(b.h * k)); if (w < 1 || h < 1) continue; const d = x.getImageData(x0, y0, w, h).data; for (let i = 3; i < d.length; i += 4) if (d[i] > alpha) alpha = d[i]; }
    const all = x.getImageData(0, 0, cv.width, cv.height).data, W = cv.width, H = cv.height;
    for (let cy = 0; cy + 8 <= H; cy += 8) for (let cx = 0; cx + 8 <= W; cx += 8) { let n = 0; for (let yy = 0; yy < 8; yy++) for (let xx = 0; xx < 8; xx++) if (all[((cy + yy) * W + cx + xx) * 4 + 3] > 0.35 * 255) n++; if (n > 40) disc++; }
  } catch (e) { alpha = 'err ' + e.message; } }
  const stage = document.querySelector('[data-stage]'), scs = getComputedStyle(stage);
  const hardCircles = [...cover.querySelectorAll('*')].filter((e) => { if (e.closest('svg')) return false; const r = e.getBoundingClientRect(); if (r.width < 8 || Math.abs(r.width - r.height) > 2 || op(e) === 0) return false; const cs = getComputedStyle(e); if (!(parseFloat(cs.borderRadius) >= r.width / 2 - 1 || /50%/.test(cs.borderRadius))) return false; if (cs.backgroundColor === 'rgba(0, 0, 0, 0)' && cs.backgroundImage === 'none' && cs.borderStyle === 'none') return false; const bl = /blur\((\d+)/.exec(cs.filter); return !(bl && +bl[1] >= 40 && +cs.opacity <= 0.35); }).length;
  // §5 portrait scrim attached to the copy block
  let scrim = null; const cb = document.querySelector('.cover__body'), eyebrow = beat && beat.firstElementChild;
  if (portrait && cb && eyebrow) { const ps = getComputedStyle(cb, '::before'); if (ps.content !== 'none') { const cbr = cb.getBoundingClientRect(); const top = cbr.top + parseFloat(ps.top), bot = cbr.bottom - parseFloat(ps.bottom), h = bot - top; const ey = eyebrow.getBoundingClientRect().top; scrim = { bg: ps.backgroundImage.slice(0, 90), clearPx: Math.round(ey - (bot - 0.75 * h)), darkPx: Math.round(ey - (bot - 0.55 * h)) }; } }
  // hint vs plate (landscape)
  const hint = document.querySelector('.cover__hint'); const hintHit = !portrait && op(hint) > 0.05 && inter(R(hint), R(frame));
  // empty band (screens.mjs rule)
  const BG = /^(cover__pin|cover__grid|cover__stage|cover__canvas|cover__video|cover__echo|cover__body|fold|fold__pin|spread|deck|dp|about|about__text)$/;
  let run = 0, worst = 0; for (let y = vh * 0.01; y < vh; y += vh * 0.02) { const empty = [0.15, 0.5, 0.85].every((fx) => { const e = document.elementFromPoint(vw * fx, y); if (!e) return true; const c = typeof e.className === 'string' ? e.className.split(' ')[0] : ''; return ['MAIN', 'BODY', 'HTML', 'SECTION'].includes(e.tagName) && !c || BG.test(c); }); run = empty ? run + 1 : 0; worst = Math.max(worst, run); }
  // §7 rail card + gloss, §6 4K
  const rail = document.querySelector('[data-rail]'), rcs = getComputedStyle(rail), gloss = document.querySelector('.rail__tr'), grid = document.querySelector('.cover__grid');
  const gcs = getComputedStyle(grid); const colH = grid.clientHeight - parseFloat(gcs.paddingTop) - parseFloat(gcs.paddingBottom);
  const brandR = R(document.querySelector('[data-beat="0"] .cover__brand'));
  return { vw, vh, portrait, file, crop, bodyBox: body, ctaB: cr && Math.round(cr.b), ctaVis: cr ? op(ctas) : 0, hit, foldTop: Math.round(fold.getBoundingClientRect().top), plateOp: +(op(frame) * (im ? op(im) : 0)).toFixed(3), copyHitsBody: !!(portrait && copy && body && inter(copy, { ...body, t: Math.max(body.t, 0), b: Math.min(body.b, vh) })), copy, zz: [scs.zIndex, getComputedStyle(grid).zIndex], mask: scs.maskImage || scs.webkitMaskImage, alpha, disc, hardCircles, chVis, brands, langGap: lang ? Math.round(vw - lang.r - padEnd) : null, scrim, hintHit, band: +(worst * 0.02).toFixed(2), railBg: rcs.backgroundColor, railBlur: rcs.backdropFilter, gloss: gloss ? parseFloat(getComputedStyle(gloss).fontSize) : 0, navFs: parseFloat(getComputedStyle(document.querySelector('.hdr__nav > a')).fontSize), htmlFs: parseFloat(getComputedStyle(document.documentElement).fontSize), railFill: +(rail.getBoundingClientRect().height / colH).toFixed(3), brandTop: brandR && brandR.t, frameIdx: +cover.dataset.frameIndex, railNo: document.querySelector('[data-rail-no]').textContent, railPos: rail.dataset.pos, imgPos: im && im.dataset.pos };
}, man);
const M = {};
for (const [name, spec] of Object.entries(VP19)) {
  const q = await mk(vpOpts(spec)); await q.goto(base + '?canvas=1', { waitUntil: 'load' }); await q.waitForTimeout(500);
  const m = M[name] = { at: {}, frames: [] };
  for (const f of [0, 0.5, 1]) { await scrollTo(q, await trackY(q, '[data-cover]', f)); await q.waitForTimeout(f === 0 ? 900 : 1200); m.at[f] = await probe(q, MAN); }
  for (let k = 0; k < 12; k++) { await scrollTo(q, await trackY(q, '[data-cover]', (k + 0.5) / 12)); await q.waitForTimeout(650); const g = await probe(q, MAN); m.frames.push({ k: k + 1, ...g.crop, portrait: g.portrait, copyHitsBody: g.copyHitsBody, idx: g.frameIdx }); }
  await scrollTo(q, (await trackY(q, '[data-cover]', 1)) + (await q.evaluate(() => innerHeight))); await q.waitForTimeout(700);
  m.after = await q.evaluate(() => { const op = (e) => { let o = 1; while (e && e.nodeType === 1) { const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden') return 0; o *= +cs.opacity; e = e.parentElement; } return o; }; return { head: +op(document.querySelector('#fold-title')).toFixed(3), plates: [...document.querySelectorAll('.plate')].map((e) => +op(e).toFixed(3)) }; });
  m.errs = q._errs.slice(); await close(q);
}
const allAt = (fn) => Object.entries(M).flatMap(([n, m]) => [0, 0.5, 1].map((f) => [n, f, m.at[f]])).filter(([n, f, g]) => !fn(g, f, n));
const fmt = (bad, pick) => bad.length ? bad.slice(0, 6).map(([n, f, g]) => `${n}@${f}:${JSON.stringify(pick(g))}`).join(' ') : 'all 19 ok';
let bad;
bad = allAt((g, f) => f !== 1 || (g.ctaB <= g.vh - 24 && g.ctaVis > 0.95 && g.hit)); t('R3 §1a cover CTAs: bottom ≤ vh−24, opacity 1, hit-testable at p=1 (19 viewports)', !bad.length, fmt(bad, (g) => ({ ctaB: g.ctaB, vh: g.vh, op: g.ctaVis, hit: g.hit })));
bad = allAt((g, f) => f !== 1 || g.foldTop >= g.ctaB + 16); t('R3 §1b drum top ≥ CTA bottom + 16 px at p=1 (19)', !bad.length, fmt(bad, (g) => ({ foldTop: g.foldTop, ctaB: g.ctaB })));
bad = allAt((g, f) => f !== 1 || g.plateOp >= 0.95); t('R3 §1c photo plate opacity ≥ .95 at p=1 (19)', !bad.length, fmt(bad, (g) => g.plateOp));
bad = Object.entries(M).filter(([, m]) => !(m.after.head >= 0.999 && m.after.plates.length === 3 && m.after.plates.every((o) => o >= 0.95))); t('R3 §1d track end + 1 vh: drum heading opacity 1, three plates ≥ .95 (19)', !bad.length, bad.length ? bad.slice(0, 6).map(([n, m]) => n + ':' + JSON.stringify(m.after)).join(' ') : 'all 19 ok');
const crops = Object.entries(M).flatMap(([n, m]) => m.frames.map((c) => ({ n, ...c })));
const cropBad = (c) => !(c.bodyH >= 0.6 && c.feet >= 0.02 && (c.portrait || (c.head >= 0 && c.head <= 0.15)));
bad = crops.filter((c) => !c.portrait && cropBad(c)); t('R3 §2 landscape crop: body ≥ 60 % plate height, feet ≥ 2 % above plate bottom, head 0–15 % from top (12 frames × landscape viewports)', !bad.length, bad.length ? bad.length + ' bad: ' + bad.slice(0, 5).map((c) => `${c.n}#${c.k}:${c.bodyH}/${c.feet}/${c.head}`).join(' ') : `min body ${Math.min(...crops.filter((c) => !c.portrait).map((c) => c.bodyH))}`);
bad = crops.filter((c) => c.portrait && cropBad(c)); t('R3 §2 portrait crop: body ≥ 60 % plate height, feet ≥ 2 % above plate bottom (12 frames × portrait viewports)', !bad.length, bad.length ? bad.length + ' bad; min body ' + Math.min(...bad.map((c) => c.bodyH)) + ': ' + bad.slice(0, 5).map((c) => `${c.n}#${c.k}:${c.bodyH}/${c.feet}`).join(' ') : 'ok');
bad = allAt((g) => g.alpha === null || g.alpha === 0); t('R3 §3 backdrop canvas alpha = 0 under wordmark / sutra / CTA boxes at p 0/.5/1 (19)', !bad.length, fmt(bad, (g) => g.alpha));
bad = allAt((g) => g.disc === 0 && g.hardCircles === 0); t('R3 §3 no hard-edged disc: 0 opaque 8×8 canvas cells, 0 unblurred circle elements in the cover (19)', !bad.length, fmt(bad, (g) => ({ disc: g.disc, el: g.hardCircles })));
bad = allAt((g) => g.portrait ? true : (+g.zz[0] < +g.zz[1] && /gradient/.test(g.mask))); t('R3 §3 backdrop below the plate (z-index) and masked (mask-image) on landscape', !bad.length, fmt(bad, (g) => ({ z: g.zz, m: (g.mask || '').slice(0, 40) })));
bad = allAt((g) => !g.chVis); t('R3 §4a no visible "00" chapter indicator at p ≤ 1 (19)', !bad.length, fmt(bad, () => '00 visible'));
bad = allAt((g) => g.brands === 1 && g.langGap !== null && g.langGap >= -1 && g.langGap <= 1); t('R3 §4d exactly one brand element visible, language toggle at the inline end (19 × p 0/.5/1)', !bad.length, fmt(bad, (g) => ({ brands: g.brands, langGap: g.langGap })));
bad = allAt((g, f) => !g.portrait || f === 0 || !g.copyHitsBody); t('R3 §5 portrait: copy block (eyebrow→CTAs) does not intersect the body bbox at p .5/1', !bad.length, fmt(bad, (g) => ({ copy: g.copy && [Math.round(g.copy.t), Math.round(g.copy.b)], body: g.bodyBox && [Math.round(g.bodyBox.t), Math.round(g.bodyBox.b)] })));
bad = Object.entries(M).flatMap(([n, m]) => m.frames.filter((c) => c.portrait && c.copyHitsBody).map((c) => [n, c.k])); t('R3 §5 portrait: copy block clear of the body for all 12 frames', !bad.length, bad.slice(0, 8).join(' ') || 'ok');
bad = allAt((g, f) => !g.portrait || f === 0 || (g.scrim && g.scrim.clearPx >= 40 && g.scrim.darkPx >= 0)); t('R3 §5 portrait scrim: transparent stop ≥ 40 px above the eyebrow, .92 stop at/above it', !bad.length, fmt(bad, (g) => g.scrim));
bad = allAt((g) => !g.hintHit); t('R3 §5 scroll hint never over the plate (landscape)', !bad.length, fmt(bad, () => 'hint∩plate'));
const k4 = M['desktop-4k'].at[0]; t('R3 §6 4K: nav ≥ 22 px, rail gloss ≥ 20 px, html ≥ 24 px, rail fills ≥ 70 % of its column', k4.navFs >= 22 && k4.gloss >= 20 && k4.htmlFs >= 24 && k4.railFill >= 0.7, JSON.stringify({ nav: k4.navFs, gloss: k4.gloss, html: k4.htmlFs, railFill: k4.railFill }));
const PT = ['ipad-portrait', 'ipad-pro-portrait', 'tv-portrait'];
bad = PT.filter((n) => { const g = M[n].at[0.5]; return !(g.railBg === 'rgba(15, 12, 10, 0.72)' && /blur\(12px\)/.test(g.railBlur) && g.gloss >= Math.max(14, 0.014 * g.vw) - 0.5); }); t('R3 §7 portrait tablets/TV: rail card rgba(15,12,10,.72) + blur(12px), gloss ≥ max(.875rem, 1.4vw)', !bad.length, bad.map((n) => n + ':' + JSON.stringify({ bg: M[n].at[0.5].railBg, bl: M[n].at[0.5].railBlur, gloss: M[n].at[0.5].gloss })).join(' ') || 'ok');
const tv = M['tv-portrait'].at[0]; const tvGap = tv.bodyBox ? (tv.brandTop - tv.bodyBox.b) / tv.vh : null;
t('R3 §7 tv-portrait p=0: wordmark 0–16 svh under the mat edge', tvGap !== null && tvGap >= 0 && tvGap <= 0.16, JSON.stringify({ gapSvh: tvGap && +tvGap.toFixed(3) }));
bad = allAt((g) => g.band <= 0.25); t('R3 §7 empty-band rule ≤ 25 % vh at p 0/.5/1 (19)', !bad.length, fmt(bad, (g) => g.band));
bad = Object.entries(M).filter(([, m]) => m.errs.length); t('R3 matrix: 0 console errors on all 19 viewports', !bad.length, bad.map(([n, m]) => n + ':' + m.errs[0]).join(' | ') || 'ok');
// §1e page-full: no flat dark/cream band > 60 % vh (pixel rows, Pillow), static and scrolled; static panels
const { execFileSync } = await import('node:child_process');
const bandPy = `import sys,json\nfrom PIL import Image\nim=Image.open(sys.argv[1]).convert('L');W,H=im.size;s=200/W;im=im.resize((200,max(1,int(H*s))));px=im.load();sc=1/s\nex=json.loads(sys.argv[2]);res={'dark':0,'cream':0}\ncur=None;run=0\nfor y in range(im.size[1]):\n  Y=y*sc\n  if any(a<=Y<=b for a,b in ex):cur=None;run=0;continue\n  row=[px[x,y] for x in range(200)];m=sum(row)/200;sd=(sum((v-m)**2 for v in row)/200)**.5\n  k='dark' if (sd<5 and m<80) else ('cream' if (sd<5 and m>200) else None)\n  run=run+1 if (k and k==cur) else (1 if k else 0);cur=k\n  if k:res[k]=max(res[k],run*sc)\nprint(json.dumps(res))`;
const bands = async (q, file, excludeCover) => { const path = new URL('../screens/' + file, import.meta.url).pathname; await q.screenshot({ path, fullPage: true }); const ex = excludeCover ? await q.evaluate(() => { const c = document.querySelector('[data-cover]'); return [[c.offsetTop, c.offsetTop + c.offsetHeight]]; }) : []; const r = JSON.parse(execFileSync('python3', ['-I', '-c', bandPy, path, JSON.stringify(ex)]).toString()); const vh = await q.evaluate(() => innerHeight); return { dark: +(r.dark / vh).toFixed(2), cream: +(r.cream / vh).toFixed(2) }; };
const PF = {};
for (const [nm, o] of [['desktop', D], ['mobile', { ...devices['Pixel 7'] }]]) {
  let q = await mk(o); await q.goto(base + '?static=1', { waitUntil: 'load' }); await q.waitForTimeout(900);
  await q.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; scrollTo(0, document.documentElement.scrollHeight); }); await q.waitForTimeout(700); await q.evaluate(() => scrollTo(0, 0)); await q.waitForTimeout(700);
  PF[nm + '-static'] = await bands(q, nm === 'desktop' ? 'page-full-static.png' : 'mobile-page-full-static.png', false);
  PF[nm + '-staticPanels'] = await q.evaluate(() => [...document.querySelectorAll('.dp')].filter((d) => !d.hidden && d.getBoundingClientRect().height > 50).length);
  await close(q);
  q = await mk(o); await q.goto(base, { waitUntil: 'load' }); await q.waitForTimeout(900);
  await q.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; scrollTo(0, document.documentElement.scrollHeight); }); await q.waitForTimeout(900); await q.evaluate(() => scrollTo(0, 0)); await q.waitForTimeout(900);
  PF[nm + '-scrolled'] = await bands(q, nm === 'desktop' ? 'page-full-r3check.png' : 'mobile-page-full-r3check.png', true);
  await close(q);
}
t('R3 §1e page-full ?static=1: no dark or cream band > 60 % vh (desktop + Pixel 7)', ['desktop-static', 'mobile-static'].every((k) => PF[k].dark <= 0.6 && PF[k].cream <= 0.6), JSON.stringify(PF));
t('R3 §1e page-full after scrolling to the end: no band > 60 % vh outside the pinned cover', ['desktop-scrolled', 'mobile-scrolled'].every((k) => PF[k].dark <= 0.6 && PF[k].cream <= 0.6), JSON.stringify(PF));
{ const q = await mk({ ...D, reducedMotion: 'reduce' }); await q.goto(base, { waitUntil: 'load' }); await q.waitForTimeout(600); const rm = await q.evaluate(() => [...document.querySelectorAll('.dp')].filter((d) => !d.hidden && d.getBoundingClientRect().height > 50).length); await close(q);
  t('R3 §1e deck panels render statically (all 4 visible) with ?static=1 and with prefers-reduced-motion', PF['desktop-staticPanels'] === 4 && PF['mobile-staticPanels'] === 4 && rm === 4, JSON.stringify({ static: PF['desktop-staticPanels'], mobileStatic: PF['mobile-staticPanels'], reduced: rm })); }
// §3 video path: the self-rendered footage carries no hairline/disc under the copy column text (sampled at 0 s and 4 s of playback)
{ const q = await mk(D); await q.goto(base, { waitUntil: 'load' }); await q.waitForTimeout(400); const vv = [];
  for (const ms of [0, 4000]) { if (ms) await q.waitForTimeout(ms); vv.push(await q.evaluate(() => { const v = document.querySelector('[data-hero-video]'); if (!v || v.readyState < 2) return { none: true }; const c = document.createElement('canvas'); c.width = v.videoWidth; c.height = v.videoHeight; const x = c.getContext('2d'); x.drawImage(v, 0, 0); const vr = v.getBoundingClientRect(), k = v.videoWidth / vr.width; const sc = getComputedStyle(document.querySelector('[data-stage]')); let mx = 0; [...document.querySelectorAll('.cover__brand, [data-beat].is-on .cover__tag')].forEach((e) => { const r = e.getBoundingClientRect(); const d = x.getImageData(Math.floor((r.left - vr.left) * k), Math.floor((r.top - vr.top) * k), Math.max(1, Math.ceil(r.width * k)), Math.max(1, Math.ceil(r.height * k))).data; for (let i = 0; i < d.length; i += 4) mx = Math.max(mx, (d[i] + d[i + 1] + d[i + 2]) / 3); }); return { t: +v.currentTime.toFixed(1), maxLum: Math.round(mx), mask: (sc.maskImage || '').slice(0, 30) }; })); }
  await close(q); t('R3 §3 hero video: no bright hairline/disc pixel (lum ≤ 90) under the wordmark at autoplay 0 s and 4 s', vv.every((v) => v.none || v.maxLum <= 90), JSON.stringify(vv)); }
// §4b/§4c deck: tab row flush under the header; no text under the header after show(id)
const textUnderHdr = (q) => q.evaluate(() => { const hb = document.querySelector('.hdr').getBoundingClientRect().bottom; const w = document.createTreeWalker(document.querySelector('main'), NodeFilter.SHOW_TEXT); const out = []; let n; while ((n = w.nextNode())) { if (!n.textContent.trim()) continue; const el = n.parentElement; if (el.closest('[hidden],[data-cover],.deck__nav')) continue; const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || cs.display === 'none') continue; const rg = document.createRange(); rg.selectNodeContents(n); for (const r of rg.getClientRects()) if (r.width > 0 && r.bottom > 0 && r.top < hb - 0.5) { out.push(n.textContent.trim().slice(0, 24) + '@' + Math.round(r.top)); break; } } return out; });
const gapTab = (q) => q.evaluate(() => Math.round(document.querySelector('[data-deck-nav]').getBoundingClientRect().top - document.querySelector('.hdr').getBoundingClientRect().bottom));
const DK = {};
for (const [nm, o] of [['desktop', D], ['mobile', { ...devices['Pixel 7'] }]]) {
  const q = await mk(o); await q.goto(base, { waitUntil: 'load' }); await q.waitForTimeout(700); DK[nm] = {};
  if (nm === 'mobile') { await q.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; document.querySelector('#practice').scrollIntoView(); }); await q.waitForTimeout(900); DK.foldGap = await q.evaluate(() => Math.round(document.querySelector('.fold__head').firstElementChild.getBoundingClientRect().top - document.querySelector('.hdr').getBoundingClientRect().bottom)); DK.barAtDrum = await q.evaluate(() => document.querySelector('[data-mbar]').classList.contains('is-on')); }
  for (const id of ['about', 'classes', 'register', 'contact']) { await q.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; document.querySelector('#deck').scrollIntoView(); }); await q.click(`[data-tab="${id}"]`); await q.waitForTimeout(900); await q.evaluate(() => document.querySelector('#deck').scrollIntoView()); await q.waitForTimeout(500); DK[nm][id] = { gap: await gapTab(q), under: await textUnderHdr(q) }; }
  if (nm === 'mobile') { DK.barAtDeck = await q.evaluate(() => document.querySelector('[data-mbar]').classList.contains('is-on')); DK.barH = await q.evaluate(() => Math.round(document.querySelector('[data-mbar]').getBoundingClientRect().height)); }
  await q.click('[data-tab="register"]'); await q.waitForTimeout(300); await q.fill('[data-reg] [name="name"]', 'Test Person'); await q.fill('[data-reg] [name="email"]', 'test@example.com'); await q.check('[data-reg] [name="consent"]'); await q.click('[data-reg] button[type="submit"]'); await q.waitForTimeout(900);
  DK[nm].success = { under: await textUnderHdr(q) };
  await close(q);
}
t('R3 §4b tab row top − header bottom ≤ 8 px on every deck view (desktop + Pixel 7)', ['desktop', 'mobile'].every((nm) => ['about', 'classes', 'register', 'contact'].every((id) => DK[nm][id].gap >= -1 && DK[nm][id].gap <= 8)), JSON.stringify(Object.fromEntries(['desktop', 'mobile'].map((nm) => [nm, Object.fromEntries(['about', 'classes', 'register', 'contact'].map((id) => [id, DK[nm][id].gap]))]))));
t('R3 §4b mobile-foldout: drum first element top − header bottom ≤ 24 px', DK.foldGap >= 0 && DK.foldGap <= 24, String(DK.foldGap));
t('R3 §4c no text box intersects the header after show(id) (classes / contact / register-success, desktop + Pixel 7)', ['desktop', 'mobile'].every((nm) => ['about', 'classes', 'register', 'contact', 'success'].every((id) => !DK[nm][id].under.length)), JSON.stringify(Object.fromEntries(['desktop', 'mobile'].map((nm) => [nm, Object.fromEntries(['classes', 'contact', 'success'].map((id) => [id, DK[nm][id].under.slice(0, 2)]))]))));
t('R3 §8e mobile bar: off while the drum is on screen, on in the deck, ≤ 55 px tall (was 69)', !DK.barAtDrum && DK.barAtDeck && DK.barH <= 55, JSON.stringify({ atDrum: DK.barAtDrum, atDeck: DK.barAtDeck, h: DK.barH }));
// §8 deck finish
{ const q = await mk(D); await q.goto(base + '#classes', { waitUntil: 'load' }); await q.waitForTimeout(700);
  const pr = await q.evaluate(() => { const ps = [...document.querySelectorAll('#classes *')].filter((e) => /^(Price on request)$/.test(e.textContent.trim()) && !e.children.length); const p = ps[0]; if (!p) return { n: 0 }; const r = p.getBoundingClientRect(), cards = document.querySelector('#classes .cards').getBoundingClientRect(), lh = parseFloat(getComputedStyle(p).lineHeight) || parseFloat(getComputedStyle(p).fontSize) * 1.4; return { n: ps.length, page: (document.body.innerText.match(/Price on request/g) || []).length, lines: Math.round(r.height / lh), spanL: Math.round(r.left - cards.left), spanR: Math.round(cards.right - r.right), color: getComputedStyle(p).color }; });
  t('R3 §8a "Price on request" once, one line spanning the three offerings, warm accent', pr.n === 1 && pr.page === 1 && pr.lines === 1 && Math.abs(pr.spanL) <= 2 && Math.abs(pr.spanR) <= 2 && pr.color === 'rgb(154, 90, 18)', JSON.stringify(pr));
  await q.click('[data-tab="contact"]'); await q.waitForTimeout(500);
  const ct = await q.evaluate(() => { const ul = document.querySelector('.contact'); const rows = [...ul.querySelectorAll(':scope > li')].filter((l) => !l.hidden); const cs = getComputedStyle(ul); const row = rows[0]; const rcs = getComputedStyle(row); const a = row.querySelector('.cta-row') || row; const acs = getComputedStyle(a); const num = (s) => (s.match(/\+33 7 54 28 72 10/g) || []).length; const mbar = document.querySelector('[data-mbar]'); return { cols: cs.gridTemplateColumns.split(' ').length, w: Math.round(ul.getBoundingClientRect().width), deckW: Math.round(document.querySelector('#contact').getBoundingClientRect().width), rows: rows.length, hairline: rcs.borderBottomStyle === 'solid' && parseFloat(rcs.borderBottomWidth) <= 1, box: acs.borderTopStyle !== 'none' && acs.borderLeftStyle !== 'none', phoneRow: rows.filter((l) => /call or WhatsApp/.test(l.textContent) && num(l.textContent) === 1).length, footTel: document.querySelectorAll('.foot a[href^="tel:"]').length, footHas: [...document.querySelectorAll('.foot__links a')].map((x) => x.textContent.trim().slice(0, 12)), numOnPage: num(document.body.textContent.replace(mbar ? mbar.textContent : '', '')) }; });
  t('R3 §8b contact: full-width hairline list, phone + WhatsApp in one row, number once (footer: email + Instagram)', ct.cols === 1 && ct.w >= ct.deckW - 2 && ct.rows === 3 && ct.hairline && !ct.box && ct.phoneRow === 1 && ct.footTel === 0 && ct.footHas.length === 2 && ct.numOnPage === 1, JSON.stringify(ct));
  await close(q); }
{ const q = await mk(D); await q.goto(base, { waitUntil: 'load' }); await q.waitForTimeout(600); const dr = [];
  const y0 = await q.evaluate(() => document.querySelector('[data-fold]').offsetTop - innerHeight), y1 = await trackY(q, '[data-fold]', 1);
  for (let i = 0; i <= 10; i++) { await scrollTo(q, y0 + (y1 - y0) * i / 10); await q.waitForTimeout(120); dr.push(await q.evaluate(() => [...document.querySelectorAll('.plate')].map((pl) => { const r = pl.querySelector('.plate__img').getBoundingClientRect(); const visF = Math.max(0, Math.min(r.bottom, innerHeight) - Math.max(r.top, 0)) / r.height; let o = 1, e = pl; while (e && e.nodeType === 1) { o *= +getComputedStyle(e).opacity; e = e.parentElement; } const cap = pl.querySelector('figcaption'); let oc = o * +getComputedStyle(cap).opacity; const m = getComputedStyle(pl).transform; let deg = 0; if (m.startsWith('matrix3d')) { const v = m.slice(9, -1).split(',').map(Number); deg = Math.abs(Math.atan2(-v[2], v[0]) * 180 / Math.PI); } return { visF: +visF.toFixed(2), o: +o.toFixed(2), cap: +oc.toFixed(2), deg: Math.round(deg) }; }))); }
  const capBad = dr.flat().filter((c) => c.visF >= 0.3 && c.cap < 0.999), thirdBad = dr.map((r) => r[2]).filter((c) => c.visF > 0 && c.o < 0.9), degMax = Math.max(...dr.flat().map((c) => c.deg));
  t('R3 §8c drum: captions opacity 1 once a card is ≥ 30 % visible, third card ≥ .9 in view, rotateY ≤ 35°', !capBad.length && !thirdBad.length && degMax <= 35, JSON.stringify({ capBad: capBad.slice(0, 3), thirdBad: thirdBad.slice(0, 3), degMax }));
  const note = await q.evaluate(() => { const e = document.querySelector('.rail__note'); return !e || getComputedStyle(e).display === 'none' ? 0 : 1; }); t('R3 §8d cover rail: no "A traditional sequence…" dek', note === 0, String(note));
  await close(q); }
// §8e mobile details
{ const q = await mk({ ...devices['Pixel 7'] }); await q.goto(base, { waitUntil: 'load' }); await q.waitForTimeout(900);
  const me = await q.evaluate(() => { const b = document.querySelector('.hdr .lang button').getBoundingClientRect(); const rail = getComputedStyle(document.querySelector('[data-rail]')); const h = document.querySelector('.cover__hint').getBoundingClientRect(), br = document.querySelector('.cover__brand').getBoundingClientRect(); return { langH: Math.round(b.height), langFs: parseFloat(getComputedStyle(document.querySelector('.hdr .lang button')).fontSize), railBgColor: rail.backgroundColor, hintDx: Math.round((h.left + h.width / 2) - (br.left + br.width / 2)), hintBelow: h.top >= br.bottom }; });
  const q2 = await mk(D); await q2.goto(base, { waitUntil: 'load' }); await q2.waitForTimeout(300); const de = await q2.evaluate(() => { const b = document.querySelector('.hdr .lang button'); return { langH: Math.round(b.getBoundingClientRect().height), langFs: parseFloat(getComputedStyle(b).fontSize) }; }); await close(q2);
  t('R3 §8e mobile: language toggle at desktop scale, rail without a slab, SCROLL centred under the wordmark', Math.abs(me.langH - de.langH) <= 1 && me.langFs === de.langFs && me.railBgColor === 'rgba(0, 0, 0, 0)' && Math.abs(me.hintDx) <= 4 && me.hintBelow, JSON.stringify({ mobile: me, desktop: de }));
  await close(q); }
// §8f / §8g one frame variable, one gloss table — 12 progress values, EN + FR, desktop + mobile
for (const [lg, o, nm] of [['en', D, 'desktop'], ['fr', D, 'desktop'], ['en', { ...devices['Pixel 7'] }, 'mobile'], ['fr', { ...devices['Pixel 7'] }, 'mobile']]) {
  const q = await mk(o); await q.addInitScript((l) => localStorage.setItem('jv-lang', l), lg); await q.goto(base, { waitUntil: 'load' }); await q.waitForTimeout(700); const rows = [];
  for (let k = 0; k < 12; k++) { await scrollTo(q, await trackY(q, '[data-cover]', (k + 0.5) / 12)); await q.waitForTimeout(500); rows.push(await q.evaluate(([k, man]) => { const im = document.querySelector('[data-frame] .cover__img.is-on'); const file = (im.currentSrc || im.src).split('/').pop(); let want = null; for (let j = k; j >= 0; j--) { const r = man.frames['sn-' + String(j + 1).padStart(2, '0')]; if (r) { want = [r.file, r.mfile]; break; } } const L = document.documentElement.lang; const D = window.JV_I18N[L]; return { k: k + 1, img: +im.dataset.pos, rail: +document.querySelector('[data-rail]').dataset.pos, no: +document.querySelector('[data-rail-no]').textContent, fileOk: !!want && want.includes(file), gloss: document.querySelector('.rail__tr').textContent === D['sn.' + (k + 1) + '.tr'] && document.querySelector('.rail__mantra').textContent === D['sn.' + (k + 1) + '.mantra'], lang: L }; }, [k, MAN])); }
  const badF = rows.filter((r) => !(r.img === r.k && r.rail === r.k && r.no === r.k && r.fileOk)), badG = rows.filter((r) => !r.gloss || r.lang !== lg);
  t(`R3 §8f frame index = rail position at 12 progress values (${nm}, ${lg.toUpperCase()})`, !badF.length, badF.length ? JSON.stringify(badF.slice(0, 3)) : '12/12');
  t(`R3 §8g gloss + mantra from the one i18n table (${nm}, ${lg.toUpperCase()})`, !badG.length, badG.length ? JSON.stringify(badG.slice(0, 3)) : '12/12');
  await close(q);
}
// operator decision 2026-10-26: newsletter dialog keeps an optional phone field
{ const q = await mk(D); await q.goto(base, { waitUntil: 'load' }); await q.waitForTimeout(300);
  const nf = await q.evaluate(() => { const f = document.querySelector('[data-news] form'); const ph = f.querySelector('input[name="phone"]'); return { email: !!f.querySelector('input[name="email"][required]'), phone: !!ph && ph.type === 'tel' && !ph.required, consent: !!f.querySelector('input[name="consent"][required]'), no: !!f.querySelector('[data-news-close]') }; });
  t('newsletter dialog: email required, phone optional (tel), consent required, "No thanks"', nf.email && nf.phone && nf.consent && nf.no, JSON.stringify(nf)); await close(q); }
writeFileSync(new URL('./r3_matrix.json', import.meta.url).pathname, JSON.stringify({ M, PF, DK }, null, 1));
// production page in place of the pitch page
p = await mk(D); await p.goto(base + PITCH_PATH, { waitUntil: 'load' }); await p.waitForTimeout(600);
t('pitch page: 0 console errors, signature present (production: 404.html carries it; no pitch page ships)', p._errs.length === 0 && (await p.evaluate((re) => new RegExp(re).test(document.body.innerHTML), SIGNATURE_RE.source)));
await close(p); await b.close();
const pass = R.filter((r) => r.ok).length; console.log(`\n${pass}/${R.length} passed`);
writeFileSync(new URL('./functional.json', import.meta.url).pathname, JSON.stringify({ date: new Date().toISOString().slice(0, 10), pass, total: R.length, desktopHeight: dh, mobileHeight: mh, panelHeightsDesktop: ph, panelHeightsMobile: mph, sizes, results: R }, null, 2));
process.exit(pass === R.length ? 0 : 1);
