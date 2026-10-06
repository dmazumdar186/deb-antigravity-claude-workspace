// Functional + density checks for the v2 scroll-story. Usage: node functional_v2.mjs http://localhost:8788/ [live-url]
import { createRequire } from 'node:module';
import { writeFileSync, mkdirSync } from 'node:fs';
const { chromium } = createRequire(import.meta.url)('/opt/node-tools/node_modules/playwright');
const base = process.argv[2], live = process.argv[3];
const screens = new URL('../screens/', import.meta.url).pathname; mkdirSync(screens, { recursive: true });
const b = await chromium.launch(); const res = {}; const fails = [];
const check = (name, ok, info = '') => { res[name] = { ok: !!ok, info }; console.log((ok ? 'ok   ' : 'FAIL ') + name + (info ? ' — ' + info : '')); if (!ok) fails.push(name); };
const scrollTo = async (p, y) => { await p.evaluate((v) => { document.documentElement.style.scrollBehavior = 'auto'; window.scrollTo(0, v); }, y); await p.waitForTimeout(350); };
const secTop = (p, sel) => p.evaluate((s) => { const e = document.querySelector(s); return e ? e.getBoundingClientRect().top + scrollY : null; }, sel);
const secH = (p, sel) => p.evaluate((s) => document.querySelector(s).getBoundingClientRect().height, sel);

// density sampler: visible words in viewport, sampled every 400px
const densitySampler = async (p) => {
  const h = await p.evaluate(() => document.documentElement.scrollHeight);
  const samples = [];
  for (let y = 0; y < h - innerH(p); y += 400) {
    await p.evaluate((v) => { document.documentElement.style.scrollBehavior = 'auto'; scrollTo(0, v); }, y);
    await p.waitForTimeout(120);
    samples.push(await p.evaluate(() => {
      const vis = (el) => { for (let e = el; e && e !== document.body; e = e.parentElement) { const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) < .05) return false; } return true; };
      const covered = (el, r) => { const cx = Math.min(innerWidth - 1, Math.max(0, r.left + r.width / 2)), cy = Math.min(innerHeight - 1, Math.max(0, r.top + Math.min(r.height / 2, 12))); const top = document.elementFromPoint(cx, cy); return top && top !== el && !el.contains(top) && !top.contains(el); };
      let n = 0; const seen = new Set();
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      let node; while ((node = walker.nextNode())) {
        const txt = node.textContent.trim(); if (!txt) continue; const el = node.parentElement; if (!el || seen.has(node)) continue; if (/^(SCRIPT|STYLE|NOSCRIPT)$/.test(el.tagName)) continue;
        const r = el.getBoundingClientRect(); if (r.bottom <= 0 || r.top >= innerHeight || r.width === 0 || r.height === 0) continue;
        if (!vis(el)) continue; if (el.closest('details:not([open])') && el.tagName !== 'SUMMARY' && !el.closest('summary')) continue;
        if (covered(el, r)) continue;
        n += txt.split(/\s+/).length; seen.add(node);
      }
      return n;
    }));
  }
  const sorted = [...samples].sort((a, c) => a - c);
  return { samples: samples.length, max: Math.max(...samples), median: sorted[Math.floor(sorted.length / 2)], mean: Math.round(samples.reduce((a, c) => a + c, 0) / samples.length) };
};
const innerH = (p) => p.viewportSize().height;

// ---------- desktop ----------
{
  const p = await b.newPage({ viewport: { width: 1440, height: 900 } }); const errs = [];
  p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => { if (m.type() === 'error' && !/fonts\.g|ERR_CERT/.test(m.text())) errs.push(m.text()); });
  await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(800);
  await p.screenshot({ path: screens + 'v2-hero-1.png' });
  const heroH = await secH(p, '[data-film-hero]'); const heroTop = await secTop(p, '[data-film-hero]');
  const t0 = await p.evaluate(() => document.querySelector('[data-film-state].is-on').textContent.trim().slice(0, 40));
  await scrollTo(p, heroTop + (heroH - 900) * .4); await p.waitForTimeout(500);
  const t40 = await p.evaluate(() => document.querySelector('[data-film-state].is-on').textContent.trim().slice(0, 40));
  const canvasDrawn = await p.evaluate(() => { const c = document.querySelector('[data-film-canvas]'); const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < d.length; i += 4 * 97) if (d[i] > 0) n++; return n; });
  await scrollTo(p, heroTop + (heroH - 900) * .55); await p.screenshot({ path: screens + 'v2-hero-4.png' });
  await scrollTo(p, heroTop + (heroH - 900) * .8); await p.waitForTimeout(500);
  const t80 = await p.evaluate(() => document.querySelector('[data-film-state].is-on').textContent.trim().slice(0, 40));
  check('hero state changes 0→40%→80%', t0 !== t40 && t40 !== t80, `${t0} | ${t40} | ${t80}`);
  check('hero canvas draws', canvasDrawn > 20, `${canvasDrawn} sampled non-transparent px`);
  // folio: card 5 of 9 in focus at mid scroll
  const fTop = await secTop(p, '#specialisms [data-folio]'), fH = await secH(p, '#specialisms [data-folio]');
  await scrollTo(p, fTop + (fH - 900) * .5); await p.waitForTimeout(300);
  const focus = await p.evaluate(() => document.querySelector('#specialisms [data-folio]').dataset.focus);
  check('folio focuses card 5 of 9 at mid-scroll', focus === '4', `focus index ${focus}`);
  await p.screenshot({ path: screens + 'v2-folio.png' });
  // drum step 4 at ~60%
  const dTop = await secTop(p, '[data-approach]'), dH = await secH(p, '[data-approach]');
  await scrollTo(p, dTop + (dH - 900) * .6); await p.waitForTimeout(600);
  const step = await p.evaluate(() => document.querySelector('[data-approach]').dataset.drumStep);
  const stepVisible = await p.evaluate(() => [...document.querySelectorAll('[data-step]')].findIndex((el) => getComputedStyle(el).opacity === '1') + 1);
  check('drum shows step 4 at ~60%', step === '4' && stepVisible === 4, `step ${step}, visible ${stepVisible}`);
  await p.screenshot({ path: screens + 'v2-drum.png' });
  // roles filter
  await p.click('[data-f-loc="London"]'); await p.waitForTimeout(300);
  const london = await p.evaluate(() => document.querySelectorAll('[data-roles-list] [data-card]').length);
  check('roles filter London → 11', london === 11, `${london}`);
  await p.click('[data-f-loc=""]'); await p.click('[data-f-type="Sales"]'); const sales = await p.evaluate(() => document.querySelectorAll('[data-roles-list] [data-card]').length); check('roles filter Sales count', sales > 0, `${sales}`);
  await p.click('[data-f-type=""]');
  // pricing toggle
  await p.evaluate(() => document.querySelector('#pricing').scrollIntoView()); await p.waitForTimeout(500);
  await p.click('[data-mode="int"]'); await p.waitForTimeout(100);
  const prices = await p.evaluate(() => [...document.querySelectorAll('[data-price]')].map((e) => e.textContent).join(' '));
  check('pricing toggle → £750/£1,500/£3,750/£8,500', prices === '£750 £1,500 £3,750 £8,500', prices);
  await p.click('[data-mode="rec"]');
  await p.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; document.querySelector('#pricing .tiers').scrollIntoView({ block: 'center' }); }); await p.waitForTimeout(600);
  await p.screenshot({ path: screens + 'v2-pricing.png' });
  // calculator
  await p.selectOption('[data-calc-tier]', 'unicorn'); await p.$eval('[data-calc-base]', (el) => { el.value = '100000'; el.dispatchEvent(new Event('input', { bubbles: true })); });
  const fee = await p.evaluate(() => document.querySelector('[data-calc-fee]').textContent + ' vs ' + document.querySelector('[data-calc-trad]').textContent);
  check('calculator £100k + Unicorn → £15,000 vs £30,000', fee === '£15,000 vs £30,000', fee);
  // FAQ
  await p.evaluate(() => document.querySelector('#faq').scrollIntoView());
  const faqOpenBefore = await p.evaluate(() => document.querySelectorAll('#faq details[open]').length);
  await p.click('#faq details:nth-of-type(2) summary'); await p.waitForTimeout(100);
  const faqOpenAfter = await p.evaluate(() => document.querySelectorAll('#faq details[open]').length);
  check('FAQ one open by default, click opens another', faqOpenBefore === 1 && faqOpenAfter === 2, `${faqOpenBefore} → ${faqOpenAfter}`);
  // form
  await p.evaluate(() => document.querySelector('#contact').scrollIntoView()); await p.waitForTimeout(300);
  await p.fill('.form input[name=first]', 'A'); await p.fill('.form input[name=last]', 'B'); await p.fill('.form input[name=company]', 'C'); await p.fill('.form input[name=email]', 'a@b.co');
  await p.click('.form button[type=submit]'); await p.waitForTimeout(100);
  const okTxt = await p.evaluate(() => { const e = document.querySelector('.form .form__ok'); return e && !e.hidden ? e.textContent : ''; });
  check('form shows "Concept — not wired"', okTxt === 'Concept — not wired', okTxt);
  // sections + density
  const sections = await p.evaluate(() => document.querySelectorAll('section').length);
  res.sections = sections; console.log('sections', sections);
  res.densityDesktop = await densitySampler(p); console.log('density desktop', JSON.stringify(res.densityDesktop));
  check('median visible words per viewport ≤ 90', res.densityDesktop.median <= 90, `median ${res.densityDesktop.median}, max ${res.densityDesktop.max}`);
  res.longestParagraphPx = await p.evaluate(() => Math.max(...[...document.querySelectorAll('p')].map((e) => e.getBoundingClientRect().height)));
  check('desktop console clean', errs.length === 0, errs.join(' | ').slice(0, 200));
  await p.close();
}
// ---------- reduced motion ----------
{
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' }); const p = await ctx.newPage(); const errs = [];
  p.on('pageerror', (e) => errs.push(e.message));
  await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(600);
  const r = await p.evaluate(() => { const st = [...document.querySelectorAll('[data-film-state]')]; const readable = st.filter((e) => getComputedStyle(e).opacity === '1' && e.getBoundingClientRect().height > 40); const tops = st.map((e) => Math.round(e.getBoundingClientRect().top)); const stacked = tops.every((t, i) => i === 0 || t > tops[i - 1]); return { readable: readable.length, stacked, pinned: getComputedStyle(document.querySelector('.film__stage')).position }; });
  check('reduced-motion: all 6 hero states stacked + readable', r.readable === 6 && r.stacked && r.pinned !== 'sticky', JSON.stringify(r));
  check('reduced-motion console clean', errs.length === 0, errs.join(' | '));
  await ctx.close();
}
// ---------- mobile ----------
{
  const p = await b.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 }); const errs = [];
  p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => { if (m.type() === 'error' && !/fonts\.g|ERR_CERT/.test(m.text())) errs.push(m.text()); });
  await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(600);
  await p.screenshot({ path: screens + 'v2-mobile-top.png' });
  const ov = await p.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  check('no horizontal overflow at 390', ov <= 0, `${ov}px`);
  await p.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; document.querySelector('#roles').scrollIntoView(); }); await p.waitForTimeout(500);
  await p.screenshot({ path: screens + 'v2-mobile-roles.png' });
  res.densityMobile = await densitySampler(p); console.log('density mobile', JSON.stringify(res.densityMobile));
  check('mobile console clean', errs.length === 0, errs.join(' | '));
  await p.close();
}
// ---------- live site density (optional) ----------
if (live) {
  try { const p = await b.newPage({ viewport: { width: 1440, height: 900 } }); await p.goto(live, { waitUntil: 'load', timeout: 30000 }); await p.waitForTimeout(1200); res.densityLive = await densitySampler(p); res.liveSections = await p.evaluate(() => document.querySelectorAll('section').length); res.liveLongestParagraphPx = await p.evaluate(() => Math.max(...[...document.querySelectorAll('p')].map((e) => e.getBoundingClientRect().height))); console.log('density live', JSON.stringify(res.densityLive), 'sections', res.liveSections); await p.close(); } catch (e) { console.log('live site skipped:', e.message.slice(0, 120)); res.densityLive = null; }
}
// deck (v1) density for comparison
try { const p = await b.newPage({ viewport: { width: 1440, height: 900 } }); await p.goto(base + 'deck/', { waitUntil: 'load' }); await p.waitForTimeout(600); res.densityDeck = await densitySampler(p); console.log('density deck', JSON.stringify(res.densityDeck)); await p.close(); } catch (e) { console.log('deck skipped', e.message); }
await b.close();
writeFileSync(new URL('./functional_v2.json', import.meta.url), JSON.stringify(res, null, 1));
console.log(fails.length ? `FAILED: ${fails.join(', ')}` : 'ALL PASSED');
process.exit(fails.length ? 1 : 0);
