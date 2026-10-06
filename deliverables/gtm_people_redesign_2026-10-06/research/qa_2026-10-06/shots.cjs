/* Human-eye test tier 2/3 shot matrix + geometry probes against the LIVE site. */
const { createRequire } = require('module');
const req = createRequire('/opt/node-tools/node_modules/playwright/package.json');
const { chromium } = req('playwright');
const fs = require('fs'), path = require('path');
process.env.PLAYWRIGHT_BROWSERS_PATH = '/opt/pw-browsers';
const BASE = 'https://gtm-people-redesign.pages.dev';
const OUT = __dirname;
const log = { shots: [], geometry: {}, friction: {}, overlap: [], console: {}, tier2: [] };
const VPS = { d1440: { width: 1440, height: 900 }, d1024: { width: 1024, height: 768 }, m390: { width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 2 } };

async function shot(page, name) { const f = path.join(OUT, name + '.png'); await page.waitForTimeout(350); await page.screenshot({ path: f }); log.shots.push(name); return f; }
async function settle(page) { await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))); await page.waitForTimeout(200); }
async function scrollTo(page, y) { await page.evaluate((y) => scrollTo(0, y), y); await settle(page); await page.waitForTimeout(300); }
async function pinned(page, sel, pct) { // scroll pct through a pinned section
  const y = await page.evaluate(([sel, pct]) => { const el = document.querySelector(sel); const r = el.getBoundingClientRect(); const top = r.top + scrollY; return Math.round(top + pct * (r.height - innerHeight)); }, [sel, pct]);
  await scrollTo(page, y); return y;
}
async function cardIdx(page, idx) { // scroll roles folio so card idx (0-based) is focused
  const y = await page.evaluate((idx) => { const f = document.querySelector('[data-roles-folio]'); const n = f.querySelectorAll('[data-card]').length; const r = f.getBoundingClientRect(); const top = r.top + scrollY; return Math.round(top + (idx / (n - 1)) * (r.height - innerHeight)); }, idx);
  await scrollTo(page, y); return y;
}
async function overlapProbe(page, label) {
  const res = await page.evaluate((label) => {
    const inter = (a, b) => Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) * Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
    const f = document.querySelector('[data-roles-folio]'); const focus = f.dataset.focus;
    return [...f.querySelectorAll('[data-card]')].map((c, i) => {
      const n = c.querySelector('.card__n'), h = c.querySelector('h3'), meta = c.querySelector('.card__meta'), comp = c.querySelector('.card__comp'), body = c.querySelector('.card__body');
      if (!n || !h) return null; const nr = n.getBoundingClientRect(), hr = h.getBoundingClientRect(), cr = c.getBoundingClientRect(), br = body.getBoundingClientRect(), mr = meta.getBoundingClientRect();
      return { label, i: i + 1, focused: String(i) === focus, title: h.textContent, card: { h: Math.round(cr.height), w: Math.round(cr.width) }, numeral: { top: Math.round(nr.top - cr.top), bottom: Math.round(nr.bottom - cr.top), fontSize: getComputedStyle(n).fontSize }, bodyTop: Math.round(br.top - cr.top), bodyH: Math.round(br.height), metaTop: Math.round(mr.top - cr.top), h3Top: Math.round(hr.top - cr.top), h3H: Math.round(hr.height), h3Lines: Math.round(hr.height / parseFloat(getComputedStyle(h).lineHeight)), overlapNumeralVsH3px: Math.round(inter(nr, hr)), overlapNumeralVsMeta: Math.round(inter(nr, mr)), overlapNumeralVsBody: Math.round(inter(nr, br)), bodyOverflowsCard: Math.round((br.bottom) - cr.bottom) };
    }).filter(Boolean);
  }, label);
  log.overlap.push(...res);
}
async function fillForm(page) {
  await page.fill('[data-demo-form] [name=first]', 'Sophie'); await page.fill('[data-demo-form] [name=last]', 'Okafor'); await page.fill('[data-demo-form] [name=company]', 'Lumen Analytics'); await page.fill('[data-demo-form] [name=email]', 'sophie@lumen.io'); await page.selectOption('[data-demo-form] [name=stage]', 'Series A'); await page.fill('[data-demo-form] [name=need]', 'One London-based mid-market AE, start Q1, £70k base / £140k OTE.');
}

async function homeMatrix(browser, key, vp, reduced = false) {
  const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, isMobile: !!vp.isMobile, hasTouch: !!vp.hasTouch, deviceScaleFactor: vp.deviceScaleFactor || 1, reducedMotion: reduced ? 'reduce' : 'no-preference' });
  const page = await ctx.newPage(); const errs = []; page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) errs.push(m.text()); }); page.on('pageerror', (e) => errs.push('pageerror ' + e.message));
  const tag = key + (reduced ? '-rm' : '');
  await page.goto(BASE + '/', { waitUntil: 'networkidle' }); await page.evaluate(() => document.fonts.ready); await page.addStyleTag({ content: 'html{scroll-behavior:auto!important}' }); await page.waitForTimeout(600);
  const isMobile = vp.width < 800;
  // friction numbers (full matrix only on first pass)
  log.friction[tag] = await page.evaluate(() => {
    const top = (s) => { const e = document.querySelector(s); return e ? Math.round(e.getBoundingClientRect().top + scrollY) : null; };
    const f = document.querySelector('[data-roles-folio]'); const fr = f.getBoundingClientRect();
    const filters = document.querySelector('[data-roles-filters]'); const fRect = filters.getBoundingClientRect();
    return { pageHeight: document.documentElement.scrollHeight, vh: innerHeight, heroHeight: Math.round(document.querySelector('[data-film-hero]').getBoundingClientRect().height), specialismsFolioHeight: Math.round(document.querySelector('#specialisms [data-folio]').getBoundingClientRect().height), approachHeight: Math.round(document.querySelector('[data-approach]').getBoundingClientRect().height), rolesSectionTop: top('#roles'), rolesFiltersTop: Math.round(fRect.top + scrollY), rolesFiltersBottom: Math.round(fRect.bottom + scrollY), rolesFolioTop: Math.round(fr.top + scrollY), rolesFolioHeight: Math.round(fr.height), rolesFolioEnd: Math.round(fr.bottom + scrollY), taasTop: top('#taas'), pricingTop: top('#pricing'), calcTop: top('[data-calc]'), salaryTop: top('#salary'), faqTop: top('#faq'), partnersTop: top('#partners'), contactTop: top('#contact'), footerTop: top('.site-footer'), cardCount: f.querySelectorAll('[data-card]').length };
  });
  // hero
  for (const p of [0, .4, .8]) { await pinned(page, '[data-film-hero]', p); await shot(page, `home_${tag}_hero_${p * 100}`); }
  // motion frames of hero canvas while scrolling (desktop only, non-reduced)
  if (!isMobile && !reduced && key === 'd1440') {
    await scrollTo(page, 0); await page.evaluate(() => { let y = 0; const id = setInterval(() => { y += 60; scrollTo(0, y); if (y > 4000) clearInterval(id); }, 50); });
    for (let i = 1; i <= 3; i++) { await page.waitForTimeout(700); const f = path.join(OUT, `motion_hero_f${i}.png`); await page.screenshot({ path: f }); log.shots.push(`motion_hero_f${i}`); }
    await page.waitForTimeout(1500);
  }
  await pinned(page, '#specialisms [data-folio]', .5); await shot(page, `home_${tag}_specialisms_mid`);
  await pinned(page, '[data-approach]', .5); await shot(page, `home_${tag}_drum_mid`);
  await page.evaluate(() => document.querySelector('#about').scrollIntoView()); await settle(page); await page.waitForTimeout(500); await shot(page, `home_${tag}_founder`);
  // roles
  if (isMobile) {
    await page.evaluate(() => document.querySelector('[data-roles-filters]').scrollIntoView({ block: 'start' })); await settle(page); await shot(page, `home_${tag}_roles_filters`);
    await page.evaluate(() => document.querySelector('[data-roles-list]').scrollIntoView({ block: 'center' })); await settle(page); await page.waitForTimeout(400); await shot(page, `home_${tag}_roles_card1_bottombar`);
    await page.evaluate(() => { const l = document.querySelector('[data-roles-list]'); l.scrollLeft = l.children[7].offsetLeft - 30; }); await settle(page); await shot(page, `home_${tag}_roles_card8`);
    await page.evaluate(() => { const l = document.querySelector('[data-roles-list]'); l.scrollLeft = l.children[19].offsetLeft - 30; }); await settle(page); await shot(page, `home_${tag}_roles_card20`);
  } else {
    await cardIdx(page, 0); await overlapProbe(page, tag + '-all-card1'); await shot(page, `home_${tag}_roles_card01`);
    // motion frames of folio while scrolling
    if (!reduced && key === 'd1440') { const y0 = await page.evaluate(() => scrollY); await page.evaluate(() => { window.__folioEnd = scrollY + 5000; let y = scrollY; const id = setInterval(() => { y += 40; scrollTo(0, y); if (y > window.__folioEnd) clearInterval(id); }, 50); }); for (let i = 1; i <= 3; i++) { await page.waitForTimeout(700); const f = path.join(OUT, `motion_folio_f${i}.png`); await page.screenshot({ path: f }); log.shots.push(`motion_folio_f${i}`); } await page.waitForTimeout(1500); await scrollTo(page, y0); }
    await cardIdx(page, 7); await shot(page, `home_${tag}_roles_card08`);
    await cardIdx(page, 19); await overlapProbe(page, tag + '-all-card20'); await shot(page, `home_${tag}_roles_card20`);
  }
  // filters
  await page.click('[data-f-loc="London"]'); await settle(page); await page.waitForTimeout(400);
  if (!isMobile) { await cardIdx(page, 0); await overlapProbe(page, tag + '-london'); } else { await page.evaluate(() => document.querySelector('[data-roles-list]').scrollIntoView({ block: 'center' })); await settle(page); }
  await shot(page, `home_${tag}_roles_filter_london`);
  await page.click('[data-f-loc=""]'); await page.click('[data-f-type="Sales"]'); await settle(page); await page.waitForTimeout(400);
  if (!isMobile) { await cardIdx(page, 0); } else { await page.evaluate(() => document.querySelector('[data-roles-list]').scrollIntoView({ block: 'center' })); await settle(page); }
  await shot(page, `home_${tag}_roles_filter_sales`);
  log.friction[tag + '_afterSalesFilter'] = await page.evaluate(() => ({ count: document.querySelector('[data-roles-count]').textContent, folioHeight: Math.round(document.querySelector('[data-roles-folio]').getBoundingClientRect().height), pageHeight: document.documentElement.scrollHeight }));
  await page.click('[data-f-type=""]'); await settle(page);
  // taas
  await page.evaluate(() => document.querySelector('#taas').scrollIntoView()); await settle(page); await page.waitForTimeout(500); await shot(page, `home_${tag}_taas`);
  // pricing
  await page.evaluate(() => document.querySelector('#pricing').scrollIntoView()); await settle(page); await page.waitForTimeout(600); await shot(page, `home_${tag}_pricing_toggle_off`);
  const tgBtns = await page.$$('[data-toggle] button'); if (tgBtns[1]) { await tgBtns[1].click(); await page.waitForTimeout(500); await shot(page, `home_${tag}_pricing_toggle_on`); await tgBtns[0].click(); }
  log.geometry[tag + '_pricingToggle'] = await page.evaluate(() => [...document.querySelectorAll('[data-toggle] button')].map((b) => b.textContent.trim() + ':' + b.getAttribute('aria-pressed')));
  await page.evaluate(() => document.querySelector('[data-calc]').scrollIntoView({ block: 'center' })); await settle(page); await page.waitForTimeout(500);
  log.geometry[tag + '_calc'] = await page.evaluate(() => ({ base: document.querySelector('[data-calc-base]').value, tier: document.querySelector('[data-calc-tier]').value, fee: document.querySelector('[data-calc-fee]').textContent, trad: document.querySelector('[data-calc-trad]').textContent, note: document.querySelector('[data-calc-note]').textContent }));
  await shot(page, `home_${tag}_pricing_calc_100k_unicorn`);
  await page.evaluate(() => { document.querySelector('[data-fees-details]').open = true; document.querySelector('[data-fees-details]').scrollIntoView({ block: 'center' }); }); await settle(page); await shot(page, `home_${tag}_pricing_fees_open`);
  await page.evaluate(() => document.querySelector('#salary').scrollIntoView()); await settle(page); await page.waitForTimeout(500); await shot(page, `home_${tag}_salary`);
  await page.evaluate(() => document.querySelector('#faq').scrollIntoView()); await settle(page); await page.waitForTimeout(500); await shot(page, `home_${tag}_faq`);
  await page.evaluate(() => document.querySelector('#partners').scrollIntoView()); await settle(page); await page.waitForTimeout(500);
  if (!isMobile) { const li = (await page.$$('[data-partners] li'))[1]; await li.hover(); await page.waitForTimeout(700); }
  await shot(page, `home_${tag}_partners${isMobile ? '' : '_hover'}`);
  await page.evaluate(() => document.querySelector('#contact').scrollIntoView()); await settle(page); await page.waitForTimeout(500); await fillForm(page); await shot(page, `home_${tag}_contact_filled`);
  if (key === 'd1440' && !reduced) { await page.click('[data-demo-form] button[type=submit]'); await page.waitForTimeout(500); log.geometry.formSubmit = await page.evaluate(() => ({ okHidden: document.querySelector('.form__ok').hidden, okText: document.querySelector('.form__ok').textContent, url: location.href })); await shot(page, `home_${tag}_contact_submitted`); }
  await page.evaluate(() => scrollTo(0, document.documentElement.scrollHeight)); await settle(page); await page.waitForTimeout(500); await shot(page, `home_${tag}_footer`);
  log.console[tag] = errs;
  await ctx.close();
}

async function deck(browser, key, vp) {
  const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, isMobile: !!vp.isMobile, hasTouch: !!vp.hasTouch, deviceScaleFactor: vp.deviceScaleFactor || 1 });
  const page = await ctx.newPage(); const errs = []; page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) errs.push(m.text()); }); page.on('pageerror', (e) => errs.push('pageerror ' + e.message));
  await page.goto(BASE + '/deck/', { waitUntil: 'networkidle' }); await page.evaluate(() => document.fonts.ready); await page.waitForTimeout(600);
  await shot(page, `deck_${key}_hero`);
  const tabs = await page.$$('[data-tabs] [role=tab]'); log.geometry[`deck_${key}_tabs`] = tabs.length;
  for (const t of tabs) { const id = await t.getAttribute('aria-controls'); await t.click(); await page.waitForTimeout(500); await page.evaluate(() => document.querySelector('[data-deck]').scrollIntoView({ block: 'start' })); await settle(page); await shot(page, `deck_${key}_tab_${id}`); }
  log.geometry[`deck_${key}_hash`] = await page.evaluate(() => location.hash);
  log.console[`deck_${key}`] = errs; await ctx.close();
}
async function forIan(browser, key, vp) {
  const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, isMobile: !!vp.isMobile, hasTouch: !!vp.hasTouch, deviceScaleFactor: vp.deviceScaleFactor || 1 });
  const page = await ctx.newPage(); const errs = []; page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) errs.push(m.text()); });
  await page.goto(BASE + '/for-ian/', { waitUntil: 'networkidle' }); await page.evaluate(() => document.fonts.ready); await page.waitForTimeout(600);
  await shot(page, `forian_${key}_top`); log.geometry[`forian_${key}_h`] = await page.evaluate(() => document.documentElement.scrollHeight);
  log.console[`forian_${key}`] = errs; await ctx.close();
}

// tier 2: geometry regression probes on live site (desktop + mobile)
async function tier2(browser) {
  for (const [key, vp] of Object.entries(VPS)) {
    const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, isMobile: !!vp.isMobile, hasTouch: !!vp.hasTouch, deviceScaleFactor: vp.deviceScaleFactor || 1 });
    const page = await ctx.newPage(); await page.goto(BASE + '/', { waitUntil: 'networkidle' }); await page.evaluate(() => document.fonts.ready);
    const r = await page.evaluate(() => {
      const out = {}; out.hOverflow = document.documentElement.scrollWidth - innerWidth;
      out.chipHeights = [...new Set([...document.querySelectorAll('[data-roles-filters] button')].map((b) => Math.round(b.getBoundingClientRect().height)))];
      out.tierCardHeights = [...document.querySelectorAll('.tier')].map((t) => Math.round(t.getBoundingClientRect().height));
      out.btnMinH = Math.min(...[...document.querySelectorAll('.btn, .chips button, .bottombar a')].map((b) => b.getBoundingClientRect().height).filter(Boolean));
      out.contrastSamples = ['.card p', '.filters__count', '.eyebrow', '.site-footer p'].map((s) => { const e = document.querySelector(s); return e ? s + ' ' + getComputedStyle(e).color + ' on ' + getComputedStyle(e.closest('section,footer') || document.body).backgroundColor : s + ' none'; });
      out.imgsNoAlt = [...document.images].filter((i) => !i.hasAttribute('alt')).length;
      out.h1 = document.querySelectorAll('h1').length;
      out.cardsOverflowingText = [...document.querySelectorAll('[data-card]')].filter((c) => { const b = c.querySelector('.card__body'); return b && b.scrollHeight > c.clientHeight - 20; }).length;
      return out;
    });
    log.tier2.push({ key, ...r }); await ctx.close();
  }
}

(async () => {
  const browser = await chromium.launch();
  try {
    const only = process.argv[2];
    if (!only) await tier2(browser);
    if (!only || only === 'd1440') await homeMatrix(browser, 'd1440', VPS.d1440);
    if (!only) { await homeMatrix(browser, 'd1440', VPS.d1440, true);
    await homeMatrix(browser, 'd1024', VPS.d1024);
    await homeMatrix(browser, 'm390', VPS.m390);
    await deck(browser, 'd1440', VPS.d1440); await deck(browser, 'm390', VPS.m390);
    await forIan(browser, 'd1440', VPS.d1440); await forIan(browser, 'm390', VPS.m390); }
  } catch (e) { log.error = String(e.stack || e); console.error(e); }
  fs.writeFileSync(path.join(OUT, process.argv[2] ? 'shots_log_' + process.argv[2] + '.json' : 'shots_log.json'), JSON.stringify(log, null, 2));
  console.log('shots', log.shots.length, 'error', log.error || 'none');
  await browser.close();
})();
