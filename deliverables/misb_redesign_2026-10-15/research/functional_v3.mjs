// Functional suite for site_v3. Usage: node functional_v3.mjs http://localhost:8793/  → functional_v3.json
import { createRequire } from 'node:module'; import { writeFileSync } from 'node:fs';
const { chromium, devices } = createRequire(import.meta.url)('/opt/node-tools/node_modules/playwright');
process.env.PLAYWRIGHT_BROWSERS_PATH ||= '/opt/pw-browsers';
const base = process.argv[2] || 'http://localhost:8793/'; const R = []; const t = (name, ok, info) => { R.push({ name, ok: !!ok, info }); console.log((ok ? 'ok   ' : 'FAIL ') + name + (info !== undefined ? ' — ' + info : '')); };
const b = await chromium.launch();
async function mk(opts) { const p = await b.newPage(opts); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); }); p._errs = errs; return p; }
const scrollTo = async (p, y) => { await p.evaluate((v) => { document.documentElement.style.scrollBehavior = 'auto'; window.scrollTo(0, v); }, y); await p.waitForTimeout(350); };
const trackY = (p, sel, f) => p.evaluate(([s, f]) => { const el = document.querySelector(s); return el.offsetTop + (el.offsetHeight - innerHeight) * f; }, [sel, f]);
const beat = (p) => p.evaluate(() => { const b = [...document.querySelectorAll('[data-beat]')].find((x) => x.classList.contains('is-on')); return b ? +b.dataset.beat : -1; });
// ---- desktop
let p = await mk({ viewport: { width: 1440, height: 900 } });
await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(1500);
const beats = [];
for (const f of [0.1, 0.3, 0.55, 0.8]) { await scrollTo(p, await trackY(p, '[data-cover]', f)); beats.push(await beat(p)); }
t('cover beats change at 25/50/75% of the track', beats.join(',') === '0,1,2,3', beats.join(','));
const vs = await p.evaluate(() => { const v = document.querySelector('[data-hero-video]'); const c = document.querySelector('[data-backdrop]'); return { hasVideo: document.querySelector('[data-cover]').classList.contains('has-video'), playing: !!(v && !v.paused && v.readyState >= 2), src: v && v.currentSrc, canvasVisible: c && getComputedStyle(c).display !== 'none' }; });
t('video plays (or canvas fallback runs)', vs.playing || vs.canvasVisible, JSON.stringify(vs));
await scrollTo(p, 0);
const f0 = await p.evaluate(() => getComputedStyle(document.querySelector('.panel--left')).transform);
await scrollTo(p, await trackY(p, '[data-fold]', 0.5)); const f50 = await p.evaluate(() => getComputedStyle(document.querySelector('.panel--left')).transform);
await scrollTo(p, await trackY(p, '[data-fold]', 1)); await p.waitForTimeout(300);
const fEnd = await p.evaluate(() => ({ tf: getComputedStyle(document.querySelector('.panel--left')).transform, fold: getComputedStyle(document.querySelector('[data-spread]')).getPropertyValue('--fold').trim(), open: document.querySelector('[data-fold]').classList.contains('is-open') }));
t('fold-out hinge transform changes with scroll', f0 !== f50 && f50 !== fEnd.tf, `${f0.slice(0, 30)} → ${f50.slice(0, 30)} → ${fEnd.tf.slice(0, 30)}`);
t('fold-out fully open by track end', fEnd.fold === '1.0000' && fEnd.open && /^(none|matrix\(1, 0, 0, 1, 0, 0\))$/.test(fEnd.tf), JSON.stringify(fEnd));
// deck tabs
await p.evaluate(() => document.querySelector('#deck').scrollIntoView()); await p.waitForTimeout(400);
const vis = async () => p.evaluate(() => [...document.querySelectorAll('.dp')].filter((d) => !d.hidden).map((d) => d.id));
let okTabs = true, info = [];
for (const id of ['workstudy', 'career', 'hub', 'admissions', 'contact', 'programs']) { await p.click('[data-tab="' + id + '"]'); await p.waitForTimeout(250); const v = await vis(); const h = await p.evaluate(() => location.hash); info.push(id + ':' + v.join('/') + h); if (!(v.length === 1 && v[0] === id && h === '#' + id)) okTabs = false; }
t('each chapter tab switches the panel and updates the hash', okTabs, info.join(' | '));
await p.goBack(); await p.waitForTimeout(400); const back1 = await vis(); const bh = await p.evaluate(() => location.hash);
t('back button restores the previous panel', back1[0] === 'contact' && bh === '#contact', back1.join('/') + ' ' + bh);
const chapterInd = await p.evaluate(() => document.querySelector('[data-chapter-no]').textContent + ' ' + document.querySelector('[data-chapter-name]').textContent);
t('header chapter indicator follows the deck', /07 Contact/.test(chapterInd), chapterInd);
// keyboard
await p.focus('[data-tab="contact"]'); await p.keyboard.press('ArrowRight'); await p.waitForTimeout(250);
t('keyboard ArrowRight wraps to Programs', (await vis())[0] === 'programs', (await vis()).join());
// deep link fresh load
const p2 = await mk({ viewport: { width: 1440, height: 900 } }); await p2.goto(base + '#hub', { waitUntil: 'load' }); await p2.waitForTimeout(900);
t('deep link /#hub opens Student HUB', (await p2.evaluate(() => [...document.querySelectorAll('.dp')].filter((d) => !d.hidden).map((d) => d.id)))[0] === 'hub');
await p2.close();
// gallery
await scrollTo(p, await trackY(p, '[data-fold]', 1)); await p.click('[data-album="palais"]'); await p.waitForTimeout(300);
const gOpen = await p.evaluate(() => ({ open: document.querySelector('[data-gallery]').open, n: document.querySelectorAll('[data-gal-grid] img').length, title: document.querySelector('[data-gal-title]').textContent }));
await p.keyboard.press('Escape'); await p.waitForTimeout(200); const gClosed = await p.evaluate(() => !document.querySelector('[data-gallery]').open);
t('gallery dialog opens and closes', gOpen.open && gOpen.n === 8 && gClosed, JSON.stringify(gOpen));
await p.click('[data-tab="career"]'); await p.waitForTimeout(1500);
const cnt = await p.evaluate(() => [...document.querySelectorAll('[data-count]')].map((e) => e.textContent));
t('career counters settle on the exact published values', cnt.join() === '+100,+50,100%', cnt.join());
// 2 cover end state: beat 04 still visible, fold-out already entering (no empty viewport)
await scrollTo(p, await trackY(p, '[data-cover]', 0.81)); await p.waitForTimeout(400);
const endState = await p.evaluate(() => { const b = document.querySelector('[data-beat="3"]'); const fp = document.querySelector('.fold__pin'); const r = fp.getBoundingClientRect(); return { beatOn: b.classList.contains('is-on'), beatOpacity: getComputedStyle(b).opacity, bodyOpacity: getComputedStyle(document.querySelector('.cover__body')).opacity, foldTop: Math.round(r.top), enter: getComputedStyle(document.querySelector('[data-fold]')).getPropertyValue('--enter').trim(), plate: getComputedStyle(document.querySelector('[data-plate="3"]')).opacity }; });
await scrollTo(p, await trackY(p, '[data-cover]', 1)); await p.waitForTimeout(400);
endState.enterAtEnd = await p.evaluate(() => getComputedStyle(document.querySelector('[data-fold]')).getPropertyValue('--enter').trim());
t('cover end: beat 04 held into the overlap, photo plate shown, fold-out arrived by track end (no empty viewport)', endState.enterAtEnd === '1.000' &&  endState.beatOn && endState.beatOpacity === '1' && +endState.bodyOpacity >= 0.85 && endState.foldTop <= 0 && +endState.enter > 0 && endState.plate === '1', JSON.stringify(endState));
// 2 fade sequencing: fold text may only appear once the cover text is gone
await scrollTo(p, await trackY(p, '[data-cover]', 0.92)); await p.waitForTimeout(400);
const seq = await p.evaluate(() => ({ foldText: getComputedStyle(document.querySelector('.fold__head')).opacity, coverBody: getComputedStyle(document.querySelector('.cover__body')).opacity, coverVis: getComputedStyle(document.querySelector('[data-cover]')).visibility, logoHidden: getComputedStyle(document.querySelector('.hdr__logo')).visibility }));
t('fade sequence: cover text at 0 before chapter headline passes 0.1', +seq.foldText > 0.1 && +seq.coverBody === 0 && seq.coverVis === 'hidden', JSON.stringify(seq));
// panel heights
const ph = await p.evaluate(() => { const o = {}; document.querySelectorAll('.dp').forEach((d) => { const was = d.hidden; d.hidden = false; o[d.id] = d.offsetHeight; d.hidden = was; }); return o; });
t('deck panels ≤ 1 viewport (900) on desktop', Object.values(ph).every((h) => h <= 900), JSON.stringify(ph));
const dh = await p.evaluate(() => document.documentElement.scrollHeight);
t('desktop page height ≤ 9,000 px', dh <= 9000, dh + ' px');
const sizes = await p.evaluate(async () => { const f = async (u) => (await (await fetch(u)).text()).length; return { html: await f('index.html'), css: await f('css/styles.css'), js: await f('js/main.js'), backdrop: await f('js/backdrop.js') }; });
t('index+css+js ≤ 150 KB (backdrop ≤ 12 KB separately)', sizes.html + sizes.css + sizes.js <= 150 * 1024 && sizes.backdrop <= 12 * 1024, JSON.stringify(sizes));
t('desktop: 0 console errors', p._errs.length === 0, p._errs.slice(0, 2).join(' | '));
await p.close();
// ---- mobile (Pixel 7)
p = await mk({ ...devices['Pixel 7'] });
await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(1200);
const mb = []; for (const f of [0.1, 0.3, 0.55, 0.8]) { await scrollTo(p, await trackY(p, '[data-cover]', f)); mb.push(await beat(p)); }
t('mobile cover beats', mb.join(',') === '0,1,2,3', mb.join(','));
const mv = await p.evaluate(() => { const v = document.querySelector('[data-hero-video]'); return { hasVideo: document.querySelector('[data-cover]').classList.contains('has-video'), src: v && v.currentSrc && v.currentSrc.split('/').pop() }; });
t('mobile uses the portrait video (hero-m.mp4) or canvas', !mv.hasVideo || /hero-m/.test(mv.src), JSON.stringify(mv));
await p.evaluate(() => document.querySelector('#campus').scrollIntoView()); await p.waitForTimeout(400);
const snap = await p.evaluate(() => { const s = document.querySelector('[data-spread]'); const cs = getComputedStyle(s); return { snap: cs.scrollSnapType, overflow: cs.overflowX, scrollW: s.scrollWidth, clientW: s.clientWidth, tf: getComputedStyle(document.querySelector('.panel--left')).transform }; });
await p.evaluate(() => { const s = document.querySelector('[data-spread]'); s.scrollBy({ left: 400, behavior: 'auto' }); }); await p.waitForTimeout(400);
const sl = await p.evaluate(() => document.querySelector('[data-spread]').scrollLeft);
t('mobile fold-out is a horizontal snap-scroll (no 3D)', /x mandatory/.test(snap.snap) && snap.scrollW > snap.clientW && sl > 100 && snap.tf === 'none', JSON.stringify({ ...snap, scrolledTo: sl }));
const bar = await p.evaluate(() => document.querySelector('[data-mbar]').classList.contains('is-on'));
// 1 (round 2) cover fully clipped at the fold-out position, paper at (20,120)
await p.evaluate(() => document.querySelector('#campus').scrollIntoView()); await p.waitForTimeout(500);
const clip = await p.evaluate(() => { const cover = document.querySelector('[data-cover]'); const cs = getComputedStyle(cover); const el = document.elementFromPoint(20, 120); const bgOf = (e) => { while (e) { const b = getComputedStyle(e).backgroundColor; if (b && b !== 'rgba(0, 0, 0, 0)' && b !== 'transparent') return b; e = e.parentElement; } return 'none'; }; return { coverVis: cs.visibility, coverPE: cs.pointerEvents, inCover: !!(el && el.closest('[data-cover]')), top: el && (el.className || el.tagName), bg: bgOf(el), hdrBg: getComputedStyle(document.querySelector('.hdr')).backgroundColor }; });
t('mobile fold-out: cover hidden, paper at (20,120), opaque header', clip.coverVis === 'hidden' && clip.coverPE === 'none' && !clip.inCover && /^rgb\(238, 236, 230\)$/.test(clip.bg) && clip.hdrBg === 'rgb(238, 236, 230)', JSON.stringify(clip));
// 4 mobile fold-out geometry
const mf = await p.evaluate(() => { const pan = document.querySelector('.panel--left').getBoundingClientRect(); const g = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--gutter')) || 20; const bar = document.querySelector('[data-mbar]').getBoundingClientRect(); const pin = document.querySelector('.fold__pin'); const band = (() => { const c = document.querySelector('[data-cover]').getBoundingClientRect(); const f = document.querySelector('[data-fold]').getBoundingClientRect(); return Math.round(c.bottom - f.top); })(); return { panelW: Math.round(pan.width), vw: innerWidth, docW: document.documentElement.scrollWidth, padB: parseFloat(getComputedStyle(pin).paddingBottom), barH: Math.round(bar.height), overlap: band }; });
t('mobile fold-out: panels fit the viewport, no overflow, padding clears the bar, cover overlaps the fold', mf.panelW <= mf.vw && mf.panelW >= mf.vw - 60 && mf.docW <= mf.vw && mf.padB >= mf.barH + 16 && mf.overlap > 0, JSON.stringify(mf));
t('mobile bottom bar appears after the cover CTA scrolls out', bar);
const mh = await p.evaluate(() => document.documentElement.scrollHeight);
t('mobile page height ≤ 12,000 px', mh <= 12000, mh + ' px');
const mph = await p.evaluate(() => { const o = {}; document.querySelectorAll('.dp').forEach((d) => { const was = d.hidden; d.hidden = false; o[d.id] = d.offsetHeight; d.hidden = was; }); return o; });
t('mobile deck panels ≤ 2 viewports (1830)', Object.values(mph).every((h) => h <= 2 * 915), JSON.stringify(mph));
// 5 mobile deck: active tab in view, bottom bar clear of panel content
await p.evaluate(() => document.querySelector('#deck').scrollIntoView()); await p.waitForTimeout(300); await p.click('[data-tab="contact"]'); await p.waitForTimeout(900);
const md = await p.evaluate(() => { const a = document.querySelector('[data-tab="contact"]').getBoundingClientRect(); const ul = document.querySelector('[data-deck-nav] ul').getBoundingClientRect(); const fade = getComputedStyle(document.querySelector('[data-deck-nav]'), '::after').width; return { tabIn: a.left >= ul.left - 1 && a.right <= ul.right + 1, fade }; });
await p.evaluate(() => { const d = document.querySelector('#deck'); window.scrollTo(0, d.offsetTop + d.offsetHeight - innerHeight); }); await p.waitForTimeout(500);
const mb2 = await p.evaluate(() => { const panel = [...document.querySelectorAll('.dp')].find((d) => !d.hidden); const last = panel.lastElementChild.getBoundingClientRect(); const bar = document.querySelector('[data-mbar]').getBoundingClientRect(); return { lastBottom: Math.round(last.bottom), barTop: Math.round(bar.top) }; });
t('mobile deck: active tab scrolled into view, fade mask present, bar never covers panel content', md.tabIn && md.fade !== 'auto' && parseFloat(md.fade) > 0 && mb2.lastBottom < mb2.barTop, JSON.stringify({ ...md, ...mb2 }));
const ov = await p.evaluate(() => document.documentElement.scrollWidth - innerWidth);
t('Pixel 7: no horizontal overflow', ov <= 0, ov + ' px');
t('mobile: 0 console errors', p._errs.length === 0, p._errs.slice(0, 2).join(' | '));
await p.close();
// pitch
p = await mk({ viewport: { width: 1440, height: 900 } }); await p.goto(base + 'for-misb/', { waitUntil: 'load' }); await p.waitForTimeout(600);
t('pitch page: 0 console errors, signature present', p._errs.length === 0 && (await p.evaluate(() => /debanjan@prodcraft\.fyi/.test(document.body.innerHTML))));
await p.close(); await b.close();
const pass = R.filter((r) => r.ok).length; console.log(`\n${pass}/${R.length} passed`);
writeFileSync(new URL('./functional_v3.json', import.meta.url).pathname, JSON.stringify({ date: '2026-10-15', pass, total: R.length, desktopHeight: dh, mobileHeight: mh, panelHeightsDesktop: ph, panelHeightsMobile: mph, sizes, results: R }, null, 2));
process.exit(pass === R.length ? 0 : 1);
