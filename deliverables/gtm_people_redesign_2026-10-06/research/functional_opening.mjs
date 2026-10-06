// v4 brand opening checks. Usage: node functional_opening.mjs http://localhost:8789/
import { createRequire } from 'node:module'; import { writeFileSync, mkdirSync } from 'node:fs';
const { chromium } = createRequire(import.meta.url)('/opt/node-tools/node_modules/playwright');
const base = process.argv[2] || 'http://localhost:8789/'; const canvas = base + '?canvas=1'; // canvas path for the beat checks; the footage block loads the plain URL
const screens = new URL('../screens/', import.meta.url).pathname; mkdirSync(screens, { recursive: true });
const b = await chromium.launch(); const res = {}; const fails = [];
const check = (n, ok, info = '') => { res[n] = { ok: !!ok, info: String(info) }; console.log((ok ? 'ok   ' : 'FAIL ') + n + (info ? ' — ' + info : '')); if (!ok) fails.push(n); };
const newPage = async (ctxOpts, pageOpts) => { const ctx = await b.newContext(ctxOpts); const p = await ctx.newPage(pageOpts); const errs = []; const notFound = [];
  p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => { if (m.type() === 'error' && !/fonts\.g|ERR_CERT/.test(m.text())) errs.push(m.text()); });
  p.on('response', (r) => { if (r.status() >= 400) notFound.push(r.status() + ' ' + r.url()); }); p.errs = errs; p.notFound = notFound; return p; };
const beat = (p) => p.evaluate(() => [...document.querySelectorAll('[data-beat]')].findIndex((e) => e.classList.contains('is-on')));
{
  const p = await newPage({ viewport: { width: 1440, height: 900 } });
  await p.goto(canvas, { waitUntil: 'load' }); await p.waitForTimeout(500);
  const geo = await p.evaluate(() => { const o = document.querySelector('#top').getBoundingClientRect(), br = document.querySelector('#brief').getBoundingClientRect(); return { top: Math.round(o.top), h: Math.round(o.height), briefTop: Math.round(br.top), vh: innerHeight }; });
  check('opening is exactly one viewport at 1440×900', geo.top === 0 && geo.h === geo.vh, JSON.stringify(geo));
  check('board (brief section) starts right after the opening', geo.briefTop === geo.h, geo.briefTop + ' vs ' + geo.h);
  check('beat 1 on at load', (await beat(p)) === 0);
  await p.mouse.move(-10, -10);
  const lum = () => p.evaluate(() => { const c = document.querySelector('[data-pipe]'); const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0, a = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 0) { n++; a += d[i]; } return { painted: n, alpha: Math.round(a / 1000) }; });
  const heads = () => p.evaluate(() => [...document.querySelectorAll('[data-beat]')].filter((e) => { const cs = getComputedStyle(e); return cs.visibility === 'visible' && +cs.opacity > .05; }).length);
  await p.waitForTimeout(1100); await p.screenshot({ path: screens + 'v4-open-1.png' }); const f1 = await lum(); const h1 = await heads();
  await p.screenshot({ path: screens + 'v4-open-motion-a.png' });
  await p.waitForTimeout(700); const f2 = await lum(); const h2 = await heads(); await p.screenshot({ path: screens + 'v4-open-motion-b.png' });
  await p.waitForTimeout(700); const f3 = await lum(); const h3 = await heads(); await p.screenshot({ path: screens + 'v4-open-motion-c.png' });
  const differs = (x, y) => Math.abs(x.painted - y.painted) / Math.max(x.painted, y.painted) > .04 || Math.abs(x.alpha - y.alpha) / Math.max(x.alpha, y.alpha) > .04;
  check('3 frames 700 ms apart differ (canvas painted px / alpha mass)', differs(f1, f2) && differs(f2, f3), JSON.stringify([f1, f2, f3]));
  check('one headline visible per frame', h1 === 1 && h2 === 1 && h3 === 1, [h1, h2, h3].join(','));
  check('canvas has non-blank pixels', f1.painted > 2000, f1.painted + ' painted px');
  await p.waitForTimeout(2000); const cardsLit = await p.evaluate(() => ({ lit: document.querySelectorAll('.card.is-lit').length, up: document.querySelectorAll('.card.is-up').length, placed: document.querySelector('[data-cards]').classList.contains('is-placed') }));
  check('beat 1 end state: five cards lit, one lifted + placed tag', cardsLit.lit === 5 && cardsLit.up === 1 && cardsLit.placed, JSON.stringify(cardsLit));
  // transition: poll for ghost text while beat 1 -> 2
  const seen = []; const tEnd = Date.now() + 1900; while (Date.now() < tEnd) { seen.push(await heads()); await p.waitForTimeout(40); }
  check('no frame with two headlines during the 1→2 transition', seen.every((n) => n <= 1), 'max ' + Math.max(...seen) + ' over ' + seen.length + ' samples');
  const b2 = await beat(p); check('beats advance after beat 1 (6.5 s)', b2 === 1, 'beat ' + b2);
  await p.waitForTimeout(1900); await p.screenshot({ path: screens + 'v4-open-2.png' });
  const counted = await p.evaluate(() => document.querySelector('[data-count="2000"]').textContent);
  check('counters count up to 2,000+', counted === '2,000+', counted);
  await p.click('[data-pill]:nth-child(3)'); await p.waitForTimeout(900);
  check('pill 3 click → beat 3 + aria-current', (await beat(p)) === 2 && (await p.getAttribute('[data-pill]:nth-child(3)', 'aria-current')) === 'true');
  const tl = await p.evaluate(() => ({ nodes: document.querySelectorAll('.tl circle').length, vis: getComputedStyle(document.querySelector('.vis-tl')).visibility }));
  check('timeline: 6 nodes, visible on beat 3', tl.nodes === 6 && tl.vis === 'visible', JSON.stringify(tl));
  await p.evaluate(() => document.activeElement && document.activeElement.blur()); await p.waitForTimeout(800); await p.screenshot({ path: screens + 'v4-open-3.png' });
  await p.focus('[data-pill]:nth-child(3)'); await p.keyboard.press('ArrowRight'); await p.waitForTimeout(900);
  check('ArrowRight → beat 4', (await beat(p)) === 3);
  const mp = await p.evaluate(() => { const sec = document.querySelector('[data-opening]'), st = document.querySelector('[data-stage]').getBoundingClientRect(), M = sec._map; const exp = (lon, lat) => [M.x + (lon + 180) / 360 * M.w, M.y + (60 - lat) / 120 * M.h];
    const cities = { London: [-0.13, 51.5], Manchester: [-2.2, 53.5], Paris: [2.35, 48.85], 'New York': [-74, 40.7], 'San Francisco': [-122.4, 37.8] };
    const off = Object.entries(cities).map(([n, [lo, la]]) => { const e = exp(lo, la), g = sec._pins[n]; return Math.hypot(e[0] - g[0], e[1] - g[1]); });
    return { maxOff: Math.max(...off), land: { london: sec._land(-0.13, 51.5), tokyo: [-2.2, 0, 2.2].some((a) => [-2.2, 0, 2.2].some((b) => sec._land(139.7 + a, 35.7 + b))), capeTown: sec._land(18.4, -33.9), atlantic: sec._land(-35, 30), sydney: sec._land(151.2, -33.9) }, mapW: M.w, stageW: st.width, cur: sec.dataset.cur }; });
  check('map pins within 2 px of the equirectangular projection', mp.maxOff <= 2, 'max ' + mp.maxOff.toFixed(2) + ' px');
  check('map geography: London/Tokyo/Cape Town/Sydney land, mid-Atlantic sea', mp.land.london && mp.land.tokyo && mp.land.capeTown && mp.land.sydney && !mp.land.atlantic, JSON.stringify(mp.land));
  await p.waitForTimeout(600);
  const mapPainted = await p.evaluate(() => { const c = document.querySelector('[data-pipe]'); const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let mint = 0, n = 0; for (let i = 0; i < d.length; i += 4) if (d[i + 3] > 40) { n++; if (d[i] < 60 && d[i + 1] > 150 && d[i + 2] > 100) mint++; } return { n, mint }; });
  check('beat 4 canvas: dot world painted with mint accents', mapPainted.n > 3000 && mapPainted.mint > 50, JSON.stringify(mapPainted));
  const hc = await p.evaluate(() => { const h = document.querySelector('.hdr'); const lum = (c) => { const [r, g, b] = c.match(/\d+/g).map(Number).map((v) => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }); return .2126 * r + .7152 * g + .0722 * b; };
    const bg = getComputedStyle(h).backgroundColor, m = bg.match(/[\d.]+/g).map(Number), a = m[3] ?? 1, base = [27, 8, 56]; const mix = m.slice(0, 3).map((v, i) => Math.round(v * a + base[i] * (1 - a))); const fg = getComputedStyle(h.querySelector('.nav a')).color; const L1 = lum('rgb(' + mix.join(',') + ')'), L2 = lum(fg); return { over: h.classList.contains('over'), ratio: +((Math.max(L1, L2) + .05) / (Math.min(L1, L2) + .05)).toFixed(2) }; });
  check('header over the dark opening: links contrast ≥ 4.5:1', hc.over && hc.ratio >= 4.5, JSON.stringify(hc));
  await p.evaluate(() => document.activeElement && document.activeElement.blur()); await p.mouse.move(700, 300); await p.waitForTimeout(1200); await p.screenshot({ path: screens + 'v4-open-4.png' });
  await p.waitForTimeout(4200);
  check('hover pauses the sequence', (await beat(p)) === 3, 'beat ' + (await beat(p)));
  await p.mouse.move(-10, -10); await p.waitForTimeout(4800);
  check('resumes after hover → beat 1', (await beat(p)) === 0, 'beat ' + (await beat(p)));
  const two = await p.evaluate(() => [...document.querySelectorAll('.beat .display')].map((e) => Math.round(e.getBoundingClientRect().height / parseFloat(getComputedStyle(e).lineHeight))));
  check('every headline ≤ 2 lines at 1440', two.every((n) => n <= 2), two.join(','));
  const stg = await p.evaluate(() => { const r = document.querySelector('[data-stage]').getBoundingClientRect(); return { top: Math.round(r.top), bottom: Math.round(r.bottom), w: Math.round(r.width) }; });
  check('stage fills the right column (top ≤ 160, bottom ≥ 740)', stg.top <= 160 && stg.bottom >= 740 && stg.w >= 540, JSON.stringify(stg));
  const rail = await p.evaluate(() => { const r = document.querySelector('.pills').getBoundingClientRect(); return Math.round(innerHeight - r.bottom); });
  check('rail 24 px from the bottom edge', rail === 24, rail + 'px');
  await p.click('[data-start-brief]'); await p.waitForTimeout(1200);
  const sb = await p.evaluate(() => { const r = document.querySelector('[data-brief]').getBoundingClientRect(); return { inView: r.top >= 0 && r.bottom <= innerHeight, focused: document.activeElement === document.querySelector('[data-brief]'), top: Math.round(r.top) }; });
  check('"Start a brief ↓" scrolls the input into view and focuses it', sb.inView && sb.focused, JSON.stringify(sb));
  await p.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; scrollTo(0, 0); }); await p.waitForTimeout(300);
  await p.click('[data-browse-roles]'); await p.waitForTimeout(1200);
  const br = await p.evaluate(() => ({ looking: document.querySelector('[data-mode="looking"]').classList.contains('is-on'), y: Math.round(scrollY), briefTop: Math.round(document.querySelector('#brief').getBoundingClientRect().top) }));
  check('"Browse open roles" switches to Looking and scrolls to the brief', br.looking && br.y > 600 && br.briefTop < 120, JSON.stringify(br));
  const whyUs = await p.evaluate(() => !!document.querySelector('.nav a[href="#top"]'));
  check('header has "Why us" → #top', whyUs);
  check('no 4xx responses (incl. hero.mp4)', p.notFound.length === 0, p.notFound.join(' | '));
  check('desktop console clean', p.errs.length === 0, p.errs.join(' | '));
  await p.context().close();
}
{
  const p = await newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
  await p.goto(canvas, { waitUntil: 'load' }); await p.waitForTimeout(600);
  const geo = await p.evaluate(() => { const o = document.querySelector('#top').getBoundingClientRect(), br = document.querySelector('#brief').getBoundingClientRect(); return { top: Math.round(o.top), h: Math.round(o.height), briefTop: Math.round(br.top), vh: innerHeight, ov: document.documentElement.scrollWidth - innerWidth }; });
  check('opening is one viewport at 390×844, board right after', geo.top === 0 && geo.h === geo.vh && geo.briefTop === geo.h, JSON.stringify(geo));
  check('no horizontal overflow at 390', geo.ov <= 0, geo.ov + 'px');
  const fit = await p.evaluate(() => { const f = document.querySelector('.opening__cta').getBoundingClientRect(), bar = document.querySelector('.mbar').getBoundingClientRect(); return { footBottom: Math.round(f.bottom), barTop: Math.round(bar.top) }; });
  check('mobile: CTA row above the fixed bar', fit.footBottom <= fit.barTop, JSON.stringify(fit));
  const taps = await p.evaluate(() => [...document.querySelectorAll('#top a,#top button')].filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && (r.width < 44 || r.height < 44); }).map((e) => e.className));
  check('opening tap targets ≥ 44 px', taps.length === 0, taps.join(','));
  const gap = await p.evaluate(() => Math.round(document.querySelector('[data-pipe]').getBoundingClientRect().top - document.querySelector('.beats').getBoundingClientRect().bottom));
  check('mobile: copy → canvas gap ≤ 80 px', gap >= 0 && gap <= 80, gap + 'px');
  await p.waitForTimeout(4200);
  const btns = await p.evaluate(() => [...document.querySelectorAll('.opening__cta .btn')].map((e) => Math.round(e.getBoundingClientRect().height)));
  check('mobile CTA buttons single line (44–48 px tall)', btns.every((h) => h >= 44 && h <= 50), btns.join(','));
  await p.screenshot({ path: screens + 'v4-open-mobile.png' });
  check('mobile console clean', p.errs.length === 0, p.errs.join(' | '));
  await p.context().close();
}
{
  const p = await newPage({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
  await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(7200);
  const vis = await p.evaluate(() => [...document.querySelectorAll('[data-beat]')].map((e) => getComputedStyle(e).visibility === 'visible' && +getComputedStyle(e).opacity > .9));
  check('reduced motion: beat 1 only, no auto-advance', vis[0] && !vis[1] && !vis[2] && !vis[3], JSON.stringify(vis));
  await p.click('[data-pill]:nth-child(2)'); await p.waitForTimeout(200);
  check('reduced motion: pills still work', (await beat(p)) === 1);
  check('reduced-motion console clean', p.errs.length === 0, p.errs.join(' | '));
  await p.context().close();
}
{ // no JS: beat 1 visible, others hidden
  const p = await newPage({ viewport: { width: 1440, height: 900 }, javaScriptEnabled: false });
  await p.goto(base, { waitUntil: 'load' });
  const vis = await p.evaluate(() => [...document.querySelectorAll('[data-beat]')].map((e) => getComputedStyle(e).display !== 'none'));
  check('no-JS: beat 1 visible, others hidden', vis[0] && !vis[1] && !vis[2] && !vis[3], JSON.stringify(vis));
  await p.context().close();
}
{ // footage path (only when assets/hero.json says ready)
  const p = await newPage({ viewport: { width: 1440, height: 900 } });
  const mf = await (await p.request.get(base + 'assets/hero.json')).json();
  if (mf.ready) {
    await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(2500);
    const v = await p.evaluate(() => { const v = document.querySelector('[data-hero-video]'); return { has: document.querySelector('[data-opening]').classList.contains('has-video'), playing: !v.paused && v.readyState >= 2 && v.currentTime > 0, src: v.currentSrc.split('/').pop(), poster: v.poster.split('/').pop(), vis: getComputedStyle(v).visibility, canvasVis: getComputedStyle(document.querySelector('[data-pipe]')).visibility }; });
    check('video path: hero.mp4 playing, canvas hidden', v.has && v.playing && /^hero\.(mp4|webm)$/.test(v.src) && v.vis === 'visible' && v.canvasVis === 'hidden', JSON.stringify(v));
    const before = await p.evaluate(() => document.querySelector('[data-pipe]').getContext('2d').getImageData(0, 0, 50, 50).data.join('').length);
    await p.waitForTimeout(1200);
    const after = await p.evaluate(() => document.querySelector('[data-pipe]').getContext('2d').getImageData(0, 0, 50, 50).data.join('').length);
    check('video path: canvas not running (no repaint)', before === after, before + ' vs ' + after);
    const b4 = await beat(p); await p.waitForTimeout(4300); const b5 = await beat(p);
    check('video path: beats follow the video timeline', b5 !== b4, b4 + ' → ' + b5);
    await p.mouse.move(-10, -10); await p.screenshot({ path: screens + 'v4-video-frame.png' });
    check('video path console clean', p.errs.length === 0 && p.notFound.length === 0, p.errs.concat(p.notFound).join(' | '));
  } else console.log('skip video path (hero.json ready=false)');
  await p.context().close();
}
await b.close(); res.fails = fails;
writeFileSync(new URL('./functional_opening.json', import.meta.url), JSON.stringify(res, null, 1));
console.log(fails.length ? `\n${fails.length} FAIL(S): ${fails.join('; ')}` : '\nall passed'); process.exit(fails.length ? 1 : 0);
