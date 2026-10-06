// v4 brand opening checks. Usage: node functional_opening.mjs http://localhost:8789/
import { createRequire } from 'node:module'; import { writeFileSync, mkdirSync } from 'node:fs';
const { chromium } = createRequire(import.meta.url)('/opt/node-tools/node_modules/playwright');
const base = process.argv[2] || 'http://localhost:8789/';
const screens = new URL('../screens/', import.meta.url).pathname; mkdirSync(screens, { recursive: true });
const b = await chromium.launch(); const res = {}; const fails = [];
const check = (n, ok, info = '') => { res[n] = { ok: !!ok, info: String(info) }; console.log((ok ? 'ok   ' : 'FAIL ') + n + (info ? ' — ' + info : '')); if (!ok) fails.push(n); };
const newPage = async (ctxOpts, pageOpts) => { const ctx = await b.newContext(ctxOpts); const p = await ctx.newPage(pageOpts); const errs = []; const notFound = [];
  p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => { if (m.type() === 'error' && !/fonts\.g|ERR_CERT/.test(m.text())) errs.push(m.text()); });
  p.on('response', (r) => { if (r.status() >= 400) notFound.push(r.status() + ' ' + r.url()); }); p.errs = errs; p.notFound = notFound; return p; };
const beat = (p) => p.evaluate(() => [...document.querySelectorAll('[data-beat]')].findIndex((e) => e.classList.contains('is-on')));
{
  const p = await newPage({ viewport: { width: 1440, height: 900 } });
  await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(500);
  const geo = await p.evaluate(() => { const o = document.querySelector('#top').getBoundingClientRect(), br = document.querySelector('#brief').getBoundingClientRect(); return { top: Math.round(o.top), h: Math.round(o.height), briefTop: Math.round(br.top), vh: innerHeight }; });
  check('opening is exactly one viewport at 1440×900', geo.top === 0 && geo.h === geo.vh, JSON.stringify(geo));
  check('board (brief section) starts right after the opening', geo.briefTop === geo.h, geo.briefTop + ' vs ' + geo.h);
  check('beat 1 on at load', (await beat(p)) === 0);
  await p.mouse.move(5, 895); // off the section? the section fills the viewport; park the mouse outside the window
  await p.mouse.move(-10, -10);
  await p.screenshot({ path: screens + 'v4-open-1.png' });
  await p.waitForTimeout(700); await p.screenshot({ path: screens + 'v4-open-motion-a.png' });
  await p.waitForTimeout(700); await p.screenshot({ path: screens + 'v4-open-motion-b.png' });
  await p.waitForTimeout(700); await p.screenshot({ path: screens + 'v4-open-motion-c.png' });
  await p.waitForTimeout(1600);
  const b2 = await beat(p); check('beats advance by 3.6 s+', b2 === 1, 'beat ' + b2);
  await p.waitForTimeout(900); await p.screenshot({ path: screens + 'v4-open-2.png' });
  const counted = await p.evaluate(() => document.querySelector('[data-count="2000"]').textContent);
  check('counters count up to 2,000+', counted === '2,000+', counted);
  const blank = await p.evaluate(() => { const c = document.querySelector('[data-pipe]'); const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++; return n; });
  check('canvas has non-blank pixels', blank > 500, blank + ' painted px');
  await p.click('[data-pill]:nth-child(3)'); await p.waitForTimeout(600);
  check('pill 3 click → beat 3 + aria-current', (await beat(p)) === 2 && (await p.getAttribute('[data-pill]:nth-child(3)', 'aria-current')) === 'true');
  await p.screenshot({ path: screens + 'v4-open-3.png' });
  await p.keyboard.press('ArrowRight'); await p.waitForTimeout(600);
  check('ArrowRight → beat 4', (await beat(p)) === 3);
  await p.screenshot({ path: screens + 'v4-open-4.png' });
  // hover pauses: mouse is over the section (focus also pauses) — wait longer than a beat
  await p.mouse.move(700, 300); await p.waitForTimeout(4000);
  check('hover pauses the sequence', (await beat(p)) === 3, 'beat ' + (await beat(p)));
  await p.evaluate(() => document.activeElement && document.activeElement.blur()); await p.mouse.move(-10, -10); await p.waitForTimeout(3800);
  check('resumes after hover → beat 1', (await beat(p)) === 0, 'beat ' + (await beat(p)));
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
  await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(600);
  const geo = await p.evaluate(() => { const o = document.querySelector('#top').getBoundingClientRect(), br = document.querySelector('#brief').getBoundingClientRect(); return { top: Math.round(o.top), h: Math.round(o.height), briefTop: Math.round(br.top), vh: innerHeight, ov: document.documentElement.scrollWidth - innerWidth }; });
  check('opening is one viewport at 390×844, board right after', geo.top === 0 && geo.h === geo.vh && geo.briefTop === geo.h, JSON.stringify(geo));
  check('no horizontal overflow at 390', geo.ov <= 0, geo.ov + 'px');
  const fit = await p.evaluate(() => { const f = document.querySelector('.opening__foot').getBoundingClientRect(), bar = document.querySelector('.mbar').getBoundingClientRect(); return { footBottom: Math.round(f.bottom), barTop: Math.round(bar.top) }; });
  check('mobile: CTA row above the fixed bar', fit.footBottom <= fit.barTop, JSON.stringify(fit));
  const taps = await p.evaluate(() => [...document.querySelectorAll('#top a,#top button')].filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && (r.width < 44 || r.height < 44); }).map((e) => e.className));
  check('opening tap targets ≥ 44 px', taps.length === 0, taps.join(','));
  await p.screenshot({ path: screens + 'v4-open-mobile.png' });
  check('mobile console clean', p.errs.length === 0, p.errs.join(' | '));
  await p.context().close();
}
{
  const p = await newPage({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
  await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(3900);
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
await b.close(); res.fails = fails;
writeFileSync(new URL('./functional_opening.json', import.meta.url), JSON.stringify(res, null, 1));
console.log(fails.length ? `\n${fails.length} FAIL(S): ${fails.join('; ')}` : '\nall passed'); process.exit(fails.length ? 1 : 0);
