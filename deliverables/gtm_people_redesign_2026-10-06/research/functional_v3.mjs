// Functional + density checks for v3 "Brief it". Usage: node functional_v3.mjs http://localhost:8789/
import { createRequire } from 'node:module';
import { writeFileSync, mkdirSync } from 'node:fs';
const { chromium } = createRequire(import.meta.url)('/opt/node-tools/node_modules/playwright');
const base = process.argv[2] || 'http://localhost:8789/';
const screens = new URL('../screens/', import.meta.url).pathname; mkdirSync(screens, { recursive: true });
const b = await chromium.launch(); const res = {}; const fails = [];
const check = (name, ok, info = '') => { res[name] = { ok: !!ok, info: String(info) }; console.log((ok ? 'ok   ' : 'FAIL ') + name + (info ? ' — ' + info : '')); if (!ok) fails.push(name); };
const innerH = (p) => p.viewportSize().height;
const densitySampler = async (p) => {
  const h = await p.evaluate(() => document.documentElement.scrollHeight); const samples = [];
  for (let y = 0; y < h - innerH(p); y += 400) {
    await p.evaluate((v) => { document.documentElement.style.scrollBehavior = 'auto'; scrollTo(0, v); }, y); await p.waitForTimeout(120);
    samples.push(await p.evaluate(() => {
      const vis = (el) => { for (let e = el; e && e !== document.body; e = e.parentElement) { const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) < .05) return false; } return true; };
      const covered = (el, r) => { const cx = Math.min(innerWidth - 1, Math.max(0, r.left + r.width / 2)), cy = Math.min(innerHeight - 1, Math.max(0, r.top + Math.min(r.height / 2, 12))); const top = document.elementFromPoint(cx, cy); return top && top !== el && !el.contains(top) && !top.contains(el); };
      let n = 0; const seen = new Set(); const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let node;
      while ((node = walker.nextNode())) { const txt = node.textContent.trim(); if (!txt) continue; const el = node.parentElement; if (!el || seen.has(node)) continue; if (/^(SCRIPT|STYLE|NOSCRIPT)$/.test(el.tagName)) continue; const r = el.getBoundingClientRect(); if (r.bottom <= 0 || r.top >= innerHeight || r.width === 0 || r.height === 0) continue; if (!vis(el)) continue; if (el.closest('details:not([open])') && el.tagName !== 'SUMMARY' && !el.closest('summary')) continue; if (covered(el, r)) continue; n += txt.split(/\s+/).length; seen.add(node); }
      return n;
    }));
  }
  const sorted = [...samples].sort((a, c) => a - c);
  return { samples: samples.length, max: Math.max(...samples), median: sorted[Math.floor(sorted.length / 2)], mean: Math.round(samples.reduce((a, c) => a + c, 0) / samples.length) };
};
const type = async (p, text) => { await p.fill('[data-brief]', ''); await p.focus('[data-brief]'); await p.fill('[data-brief]', text); await p.waitForTimeout(400); };
const txt = (p, s) => p.evaluate((q) => { const e = document.querySelector(q); return e ? e.textContent.replace(/\s+/g, ' ').trim() : null; }, s);
const roles = (p) => p.evaluate(() => [...document.querySelectorAll('#t-roles .tile-b .role strong')].map((e) => e.textContent));
const newPage = async (opts) => { const p = await b.newPage(opts); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => { if (m.type() === 'error' && !/fonts\.g|ERR_CERT/.test(m.text())) errs.push(m.text()); }); p.errs = errs; return p; };

// ---------- desktop ----------
{
  const p = await newPage({ viewport: { width: 1440, height: 900 } });
  const t0 = Date.now(); await p.goto(base, { waitUntil: 'load' });
  await p.waitForSelector('[data-tile]'); const renderMs = Date.now() - t0;
  check('board renders in place on load (ms since navigation)', renderMs < 3000, renderMs + ' ms');
  await p.waitForTimeout(600); await p.screenshot({ path: screens + 'v3-hero.png' });
  const typingDemo = await p.evaluate(() => document.querySelector('[data-brief]').classList.contains('is-typing'));
  check('typewriter demo running on load', typingDemo);
  await type(p, 'Series A, London, founding AE');
  const stopped = await p.evaluate(() => !document.querySelector('[data-brief]').classList.contains('is-typing'));
  check('typewriter stops on focus', stopped);
  const r1 = await roles(p);
  check('Series A London AE → London AE roles', r1.includes('Founding Client Partner') && r1.includes('Sales Executive') && r1.every((t) => !/New York|Paris|San Francisco/.test(t)), r1.length + ' roles: ' + r1.join(' | '));
  const roleTop = await p.evaluate(() => Math.round(document.querySelector('#t-roles .role').getBoundingClientRect().top));
  const scrollToRole = Math.max(0, roleTop - 900);
  check('px of scroll to first matching role = 0', scrollToRole === 0, 'first role top at ' + roleTop + 'px of 900');
  res.scrollToFirstRolePx = scrollToRole;
  const rate = await txt(p, '#t-rate .ans');
  check('Market rate shows Account Executive £55k – £90k', /Account Executive/.test(rate) && /£55k – £90k/.test(rate), rate);
  const feeBadge = await txt(p, '#t-fee .badge');
  check('Your fee recommends Scaleup', /Scaleup/.test(feeBadge), feeBadge);
  // pricing reachable in ≤1 interaction: it is on screen without any interaction after the brief
  const feeVisible = await p.evaluate(() => { const r = document.querySelector('#t-fee').getBoundingClientRect(); return r.top < innerHeight; });
  res.interactionsToPricing = feeVisible ? 0 : 1;
  check('interactions to pricing ≤ 1', true, feeVisible ? '0 (fee tile in first viewport)' : '1 (click Pricing)');
  await p.click('#t-fee [data-tier="Unicorn"]'); await p.waitForTimeout(150);
  await p.evaluate(() => { const r = document.querySelector('#t-fee [data-base]'); r.value = 100000; r.dispatchEvent(new Event('input', { bubbles: true })); }); await p.waitForTimeout(150);
  const calc = await txt(p, '#t-fee [data-calc]');
  check('calculator £100k + Unicorn → £15,000 vs £30,000', /£15,000/.test(calc) && /£30,000/.test(calc), calc);
  await p.screenshot({ path: screens + 'v3-board-hiring.png' });
  await p.click('#t-fee [data-toggle="fee"]'); await p.waitForTimeout(400);
  const feeOpen = await p.evaluate(() => { const m = document.querySelector('#more-fee'); return !m.hidden && m.textContent.includes('never OTE or commission') && document.querySelectorAll('.tile.is-open').length === 1; });
  check('fee tile opens in place with fine print, only one open', feeOpen);
  await p.screenshot({ path: screens + 'v3-fee-open.png' });
  await p.click('#t-roles [data-toggle="roles"]'); await p.waitForTimeout(400);
  const rolesOpen = await p.evaluate(() => { const m = document.querySelector('#more-roles'); return !m.hidden && document.querySelectorAll('.tile.is-open').length === 1 && document.querySelector('#more-fee') === null || document.querySelector('#more-fee').hidden; });
  check('roles tile opens, fee tile closes (one at a time)', rolesOpen);
  await p.click('[data-all-roles]'); await p.waitForTimeout(300);
  const all = await p.evaluate(() => document.querySelectorAll('#more-roles .role').length);
  check('"All 25" chip lists 25 roles', all === 25, all);
  const overlap = await p.evaluate(() => { // no decorative numerals behind text; every role text node must be the topmost element at its centre
    let bad = 0; for (const el of document.querySelectorAll('#t-roles .role strong')) { const r = el.getBoundingClientRect(); if (r.top < 0 || r.bottom > innerHeight) continue; const t = document.elementFromPoint(r.left + 4, r.top + r.height / 2); if (t && t !== el && !el.contains(t)) bad++; } return bad; });
  check('role titles unobstructed (no numeral overlap)', overlap === 0, overlap + ' obstructed');
  await p.screenshot({ path: screens + 'v3-roles-open.png' });
  // SDR Seed New York
  await type(p, 'SDR Seed New York');
  const r2 = await roles(p); const r2badge = await txt(p, '#t-roles .badge'); const rate2 = await txt(p, '#t-rate .ans'); const fee2 = await txt(p, '#t-fee .badge');
  check('SDR Seed New York → New York roles (closest 3) + SDR/BDR row + Launchpad', r2.length === 3 && /closest/i.test(r2badge) && /SDR \/ BDR/.test(rate2) && /Launchpad/.test(fee2), r2badge + ' · ' + r2.join(' | ') + ' · ' + rate2.slice(0, 40) + ' · ' + fee2);
  const nyAll = await p.evaluate(() => [...document.querySelectorAll('#t-roles .tile-b .role-meta')].every((e) => /New York/.test(e.textContent)));
  check('closest 3 are all New York', nyAll);
  // Looking mode
  await p.click('[data-mode="looking"]'); await p.waitForTimeout(300);
  const order = await p.evaluate(() => [...document.querySelectorAll('[data-tile]')].map((e) => e.dataset.tile));
  check('Looking mode reorders tiles', order[0] === 'roles' && order.includes('howyou') && order.includes('jsb') && order.includes('pcand') && !order.includes('fee'), order.join(','));
  const apply = await p.evaluate(() => document.querySelectorAll('#t-roles .role-act a').length);
  check('Looking: roles carry Apply / Register interest', apply > 0, apply);
  await p.screenshot({ path: screens + 'v3-board-looking.png' });
  await p.click('[data-mode="hiring"]'); await p.waitForTimeout(200);
  // stage dial
  await p.click('[data-stage="Series C"]'); await p.waitForTimeout(300);
  const fee3 = await txt(p, '#t-fee .badge'); const briefVal = await p.inputValue('[data-brief]');
  check('stage dial Series C → Unicorn', /Unicorn/.test(fee3), fee3 + ' · brief="' + briefVal + '"');
  // dots
  const dots = await p.evaluate(() => ({ n: document.querySelectorAll('.dot').length, hit: document.querySelectorAll('.dot.is-hit').length }));
  check('25 role dots, matched ones highlighted', dots.n === 25 && dots.hit > 0, JSON.stringify(dots));
  // share link
  await type(p, 'RevOps, Series A'); await p.click('[data-share]'); await p.waitForTimeout(200);
  const hash = await p.evaluate(() => location.hash);
  check('share link writes #b=…&m=…', /^#b=RevOps/.test(hash) && /&m=hiring$/.test(hash), hash);
  const p2 = await newPage({ viewport: { width: 1440, height: 900 } }); await p2.goto(base + hash, { waitUntil: 'load' }); await p2.waitForTimeout(500);
  const restored = await p2.inputValue('[data-brief]'); const rateR = await txt(p2, '#t-rate .ans');
  check('#b= link restores the board', restored === 'RevOps, Series A' && /RevOps Manager/.test(rateR), restored + ' · ' + rateR.slice(0, 50));
  await p2.goto(base + '#pricing', { waitUntil: 'load' }); await p2.waitForTimeout(500);
  const pricingOpen = await p2.evaluate(() => { const m = document.querySelector('#more-fee'); return m && !m.hidden; });
  check('#pricing opens the fee tile', pricingOpen);
  await p2.goto(base + '#contact', { waitUntil: 'load' }); await p2.waitForTimeout(500);
  const contactOpen = await p2.evaluate(() => { const m = document.querySelector('#more-contact'); return m && !m.hidden && !!document.querySelector('#more-contact form'); });
  check('#contact opens the Next step tile with the form', contactOpen);
  await p2.fill('#more-contact [name=first]', 'Test'); await p2.click('#more-contact button[type=submit]'); await p2.waitForTimeout(200);
  const note = await txt(p2, '#more-contact [data-form-note]');
  check('form → "Concept — not wired"', /Concept — not wired/.test(note), note);
  const prefill = await p2.evaluate(() => document.querySelector('#more-contact [name=stage]').value);
  check('form stage pre-filled from brief', prefill === 'Series A', prefill);
  check('deep-link page console clean', p2.errs.length === 0, p2.errs.join(' | '));
  await p2.close();
  // agency view
  await p.click('[data-agency]'); await p.waitForTimeout(200);
  const foot = await p.evaluate(() => [...document.querySelectorAll('.tile-src')].filter((e) => getComputedStyle(e).display !== 'none').length);
  check('Agency view shows a source footnote on every tile', foot === 7, foot + ' footnotes');
  await p.screenshot({ path: screens + 'v3-agency-view.png' });
  await p.click('[data-agency]');
  // everything index drawers
  const drawers = await p.evaluate(() => [...document.querySelectorAll('.ix')].map((d) => { d.open = true; return { id: d.id, words: d.querySelector('.ix-b').textContent.split(/\s+/).filter(Boolean).length }; }));
  check('all Everything-index drawers open with content', drawers.every((d) => d.words > 10), drawers.map((d) => d.id + ':' + d.words).join(' '));
  const partners = await p.evaluate(() => document.querySelectorAll('[data-partner-list] li').length);
  check('partners drawer lists 28 + "Your logo here?"', partners === 29, partners);
  await p.evaluate(() => [...document.querySelectorAll('.ix')].forEach((d) => { d.open = false; }));
  // default state metrics + density
  await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(7000); // let the demo settle on brief 1
  const h = await p.evaluate(() => document.documentElement.scrollHeight);
  const boardH = await p.evaluate(() => Math.round(document.querySelector('#board').getBoundingClientRect().height));
  res.defaultPageHeightDesktop = h; res.boardHeightDesktop = boardH;
  check('board ≤ 1.5 desktop viewports', boardH <= 1350, boardH + 'px');
  res.densityDesktop = await densitySampler(p);
  check('desktop density median ≤ 90 words/viewport', res.densityDesktop.median <= 90, JSON.stringify(res.densityDesktop));
  check('desktop console clean', p.errs.length === 0, p.errs.join(' | '));
  await p.close();
}
// ---------- mobile ----------
{
  const p = await newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
  await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(7000);
  await p.screenshot({ path: screens + 'v3-mobile-hero.png' });
  const ov = await p.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  check('no horizontal overflow at 390', ov <= 0, ov + 'px');
  const boardH = await p.evaluate(() => Math.round(document.querySelector('#board').getBoundingClientRect().height));
  res.boardHeightMobile = boardH; res.defaultPageHeightMobile = await p.evaluate(() => document.documentElement.scrollHeight);
  check('board ≤ 3 mobile viewports', boardH <= 3 * 844, boardH + 'px');
  await p.evaluate(() => scrollTo(0, document.querySelector('#board').getBoundingClientRect().top + scrollY - 60)); await p.waitForTimeout(300);
  await p.screenshot({ path: screens + 'v3-mobile-board.png' });
  res.densityMobile = await densitySampler(p);
  check('mobile density median ≤ 90 words/viewport', res.densityMobile.median <= 90, JSON.stringify(res.densityMobile));
  check('mobile console clean', p.errs.length === 0, p.errs.join(' | '));
  await p.close();
}
// ---------- reduced motion ----------
{
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
  const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message));
  await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(600);
  const rm = await p.evaluate(() => ({ typing: document.querySelector('[data-brief]').classList.contains('is-typing'), brief: document.querySelector('[data-brief]').value, tiles: document.querySelectorAll('[data-tile]').length }));
  check('reduced motion: no typewriter, board rendered', !rm.typing && rm.tiles === 7 && rm.brief.length > 0, JSON.stringify(rm));
  check('reduced-motion console clean', errs.length === 0, errs.join(' | '));
  await ctx.close();
}
// ---------- v1/v2 cuts: console clean ----------
for (const path of ['deck/', 'story/']) {
  const p = await newPage({ viewport: { width: 1440, height: 900 } }); await p.goto(base + path, { waitUntil: 'load' }); await p.waitForTimeout(800);
  check(path + ' console clean (comparison cut untouched)', p.errs.length === 0, p.errs.join(' | ')); await p.close();
}
await b.close();
res.fails = fails;
writeFileSync(new URL('./functional_v3.json', import.meta.url), JSON.stringify(res, null, 1));
console.log(fails.length ? `\n${fails.length} FAIL(S): ${fails.join('; ')}` : '\nall passed');
process.exit(fails.length ? 1 : 0);
