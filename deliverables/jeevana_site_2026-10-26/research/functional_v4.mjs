// v4 functional gate (Playwright). usage: node research/serve_csp.mjs site 8794 & node research/functional_v4.mjs [base]
import { createRequire } from 'node:module';
const req = createRequire('/opt/node22/lib/node_modules/'); const { chromium, devices } = req('playwright');
const BASE = process.argv[2] || 'http://localhost:8794';
let pass = 0, failn = 0; const ok = (c, m) => { if (c) { pass++; console.log('ok  ', m); } else { failn++; console.log('FAIL', m); } };
const b = await chromium.launch();
async function page(opts = {}) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, ...opts }); const p = await ctx.newPage();
  const errs = []; p.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); }); p.on('pageerror', (e) => errs.push(String(e)));
  await p.route('**/cloudflareinsights.com/**', (r) => r.fulfill({ status: 200, body: '' }));
  await p.route('**/api/event', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: '{"ok":true}' }));
  return { ctx, p, errs };
}
// CLS observer
const clsInit = () => { window.__cls = 0; new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; }).observe({ type: 'layout-shift', buffered: true }); };

{ // load, CLS, alt, CSP, i18n
  const { ctx, p, errs } = await page(); await p.addInitScript(clsInit);
  await p.goto(BASE + '/', { waitUntil: 'networkidle' }); await p.waitForTimeout(1500);
  for (let y = 0; y < 12000; y += 600) { await p.evaluate((v) => scrollTo(0, v), y); await p.waitForTimeout(50); }
  const cls = await p.evaluate(() => window.__cls); ok(cls < 0.05, `layout shift ${cls.toFixed(3)} < .05`);
  const noAlt = await p.evaluate(() => [...document.images].filter((i) => !i.hasAttribute('alt')).length); ok(noAlt === 0, 'all images have alt');
  const altEmptyPh = await p.evaluate(() => [...document.querySelectorAll('img.ph')].filter((i) => !i.alt.trim()).length); ok(altEmptyPh === 0, 'every photo has descriptive alt');
  await p.click('.bar [data-lang="fr"]'); await p.waitForTimeout(200);
  ok((await p.textContent('#h1')).trim().startsWith('Stable.') || (await p.getAttribute('#h1', 'aria-label')).startsWith('Stable.'), 'FR toggle switches the headline');
  ok(await p.evaluate(() => document.documentElement.lang === 'fr'), 'html lang=fr');
  await p.reload({ waitUntil: 'networkidle' });
  ok((await p.getAttribute('#h1', 'aria-label')).startsWith('Stable.'), 'FR persists after reload');
  ok((await p.getAttribute('img.ph', 'alt')).includes('les yeux fermés'), 'alt text switches to FR');
  await p.goto(BASE + '/privacy/'); ok(await p.evaluate(() => document.querySelector('[data-lang-block="fr"]') && !document.querySelector('[data-lang-block="fr"]').hidden), 'privacy page honours FR');
  await p.click('[data-lang="en"]');
  const csp = errs.filter((e) => /Content Security Policy|Refused/.test(e)); ok(csp.length === 0, 'CSP clean ' + csp.join(' | '));
  ok(errs.length === 0, 'no console errors ' + errs.join(' | '));
  await ctx.close();
}
{ // strip
  const { ctx, p, errs } = await page(); await p.goto(BASE + '/#twelve', { waitUntil: 'networkidle' }); await p.waitForTimeout(600);
  const lit = () => p.evaluate(() => [...document.querySelectorAll('svg.twelve--strip .arc')].findIndex((a) => a.classList.contains('on')));
  const litC = () => p.evaluate(() => [...document.querySelectorAll('svg.twelve--cover .arc')].findIndex((a) => a.classList.contains('on')));
  ok((await lit()) === 0, 'arc 1 lit by default');
  const sl = () => p.evaluate(() => document.querySelector('[data-strip]').scrollLeft);
  // start alignment: the active card rests on the left gutter (or the strip is clamped at its end)
  const aligned = () => p.evaluate(() => { const s = document.querySelector('[data-strip]'), c = document.querySelectorAll('.card')[JV_strip.cur()], pad = parseFloat(getComputedStyle(s).paddingLeft), max = s.scrollWidth - s.clientWidth; return Math.abs(Math.min(c.offsetLeft - pad, max) - s.scrollLeft); });
  const view = () => p.evaluate(() => { const s = document.querySelector('[data-strip]'), pad = parseFloat(getComputedStyle(s).paddingLeft), a = s.getBoundingClientRect(), cs = [...document.querySelectorAll('.card')].map((c) => c.getBoundingClientRect()); return { pad, first: cs[0].left - a.left, full: cs.filter((r) => r.left >= a.left + pad - 2 && r.right <= a.right - pad + 2).length, lastGap: a.right - pad - cs[cs.length - 1].right, sl: s.scrollLeft, max: s.scrollWidth - s.clientWidth }; });
  const v0 = await view(); ok(Math.abs(v0.first - v0.pad) < 2 && v0.full === 3, `1440: card 1 starts on the gutter (${v0.first.toFixed(0)} vs ${v0.pad}px) and 3 cards are fully in view (${v0.full})`);
  const sl0 = await sl();
  await p.click('[data-next]'); await p.waitForTimeout(900);
  ok((await sl()) > sl0 + 20 && (await aligned()) < 4, `next arrow moves the cards (scrollLeft ${sl0} → ${await sl()}) and aligns card 2 to the gutter`);
  ok(await p.evaluate(() => JV_strip.cur()) === 1 && (await lit()) === 1 && (await litC()) === 1, 'next arrow → card 2, backdrop arcs follow');
  ok((await p.textContent('[data-cur]')) === '02', 'progress shows 02');
  const sl1 = await sl(); await p.focus('[data-strip]'); await p.keyboard.press('ArrowRight'); await p.waitForTimeout(900);
  ok((await sl()) > sl1 + 20, 'ArrowRight moves the cards (scrollLeft changes)');
  ok(await p.evaluate(() => JV_strip.cur()) === 2 && (await lit()) === 2, 'ArrowRight key → card 3');
  await p.keyboard.press('ArrowLeft'); await p.waitForTimeout(900); ok(await p.evaluate(() => JV_strip.cur()) === 1, 'ArrowLeft key → card 2');
  await p.click('[data-prev]'); await p.waitForTimeout(900); ok(await p.evaluate(() => JV_strip.cur()) === 0 && (await aligned()) < 4 && (await sl()) < 2, 'prev arrow → card 1, back on the gutter');
  // snap: scroll manually off a card edge, expect it to settle start-aligned
  await p.evaluate(() => { const s = document.querySelector('[data-strip]'); s.scrollBy({ left: 1300, behavior: 'instant' }); }); await p.waitForTimeout(1200);
  const off = await aligned();
  ok(off < 4 && (await lit()) === await p.evaluate(() => JV_strip.cur()), `scroll-snap start-aligns a card (off ${off.toFixed(1)}px) and lights its arc`);
  // the end: card 12 flush with the right gutter (no void), and the clamped last cards still activate one by one
  await p.evaluate(() => JV_strip.go(11)); await p.waitForTimeout(1200); const ve = await view();
  ok(Math.abs(ve.sl - ve.max) < 2 && Math.abs(ve.lastGap) < 2 && ve.full === 3 && (await p.evaluate(() => JV_strip.cur())) === 11, `go(11): scroll clamped at the end, card 12 flush right (gap ${ve.lastGap.toFixed(1)}px), card 12 active`);
  await p.click('[data-prev]'); await p.waitForTimeout(700); const c10 = await p.evaluate(() => JV_strip.cur());
  await p.click('[data-next]'); await p.waitForTimeout(700); const c11 = await p.evaluate(() => JV_strip.cur());
  ok(c10 === 10 && c11 === 11 && Math.abs((await sl()) - ve.max) < 2, `at the end, prev/next still step the active card (${c10 + 1}, ${c11 + 1}) while scrollLeft stays clamped`);
  await p.evaluate(() => JV_strip.go(4)); await p.waitForTimeout(1200);
  // drag
  const before = await p.evaluate(() => JV_strip.cur()), slD = await sl(); const box = await p.locator('[data-strip]').boundingBox();
  await p.mouse.move(box.x + box.width / 2, box.y + 200); await p.mouse.down(); await p.mouse.move(box.x + box.width / 2 - 400, box.y + 200, { steps: 8 }); await p.mouse.up(); await p.waitForTimeout(1000);
  ok(await p.evaluate(() => JV_strip.cur()) > before && (await sl()) > slD + 20, 'mouse drag advances (scrollLeft changes)');
  // autoplay
  await p.mouse.move(5, 5); const a0 = await p.evaluate(() => JV_strip.cur()), slA = await sl(); await p.click('[data-play]');
  ok(await p.evaluate(() => JV_strip.playing()), 'play starts autoplay'); await p.mouse.move(5, 5); await p.waitForTimeout(4600);
  ok(await p.evaluate(() => JV_strip.cur()) === (a0 + 1) % 12 && (await sl()) !== slA, 'autoplay waits 4 s, then advances one card (scrollLeft changes)');
  await p.click('[data-play]'); ok(!(await p.evaluate(() => JV_strip.playing())), 'pause stops autoplay');
  ok(errs.length === 0, 'strip: no console errors ' + errs.join(' | ')); await ctx.close();
}
for (const [label, dev] of [['iPhone 13', devices['iPhone 13']], ['iPad Mini', devices['iPad Mini']], ['iPad landscape', devices['iPad Mini landscape']]]) { // touch: CDP swipe + arrows on phone/tablet
  const { ctx, p, errs } = await page({ ...dev }); await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  await p.evaluate(() => { const s = document.querySelector('[data-strip]'); scrollTo({ top: s.getBoundingClientRect().top + scrollY - Math.max(0, (innerHeight - s.offsetHeight) / 2) - 40, behavior: 'instant' }); }); await p.waitForTimeout(700);
  const st = () => p.evaluate(() => ({ sl: document.querySelector('[data-strip]').scrollLeft, cur: JV_strip.cur() }));
  const box = await p.evaluate(() => { const r = document.querySelector('[data-strip] .card img').getBoundingClientRect(); return { x: Math.round(innerWidth * 0.75), y: Math.round(Math.max(r.top + 30, Math.min(r.top + r.height / 2, innerHeight - 30))) }; });
  const s0 = await st(); const c = await ctx.newCDPSession(p);
  await c.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: box.x, y: box.y }] });
  for (let i = 1; i <= 12; i++) { await c.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: box.x - i * 20, y: box.y }] }); await p.waitForTimeout(16); }
  await c.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] }); await p.waitForTimeout(1400);
  const s1 = await st(); ok(s1.sl > s0.sl + 20 && s1.cur > s0.cur, `${label}: touch swipe moves the strip (scrollLeft ${s0.sl} → ${s1.sl}, card ${s0.cur + 1} → ${s1.cur + 1})`);
  await p.tap('[data-next]'); await p.waitForTimeout(1000); const s2 = await st();
  ok(s2.sl > s1.sl + 20 && s2.cur === s1.cur + 1, `${label}: next arrow moves the strip (scrollLeft ${s1.sl} → ${s2.sl})`);
  ok(errs.length === 0, `${label}: console clean ` + errs.join(' | ')); await ctx.close();
}
{ // Reserve CTA: smooth-scroll to the form and focus its first field; no 4xx on load; beacons use allowlisted names
  const { ctx, p } = await page(); const bad = [], names = [];
  p.on('response', (r) => { if (r.status() >= 400 && !/cloudflareinsights/.test(r.url())) bad.push(r.status() + ' ' + r.url()); });
  await p.route('**/api/event', (r) => { names.push(r.request().postDataJSON().name); r.fulfill({ status: 200, contentType: 'application/json', body: '{"ok":true}' }); });
  await p.goto(BASE + '/', { waitUntil: 'networkidle' }); await p.waitForTimeout(500);
  ok(bad.length === 0, 'no 4xx/5xx responses on load ' + bad.join(' | '));
  await p.click('.cover [data-reserve]'); await p.waitForTimeout(1600);
  ok(await p.evaluate(() => document.activeElement && document.activeElement.id === 'reg-name'), 'Reserve a session focuses the first form field');
  ok(await p.evaluate(() => { const r = document.getElementById('registration').getBoundingClientRect(); return r.top >= -2 && r.top < innerHeight / 2; }), 'Reserve a session scrolls to the form');
  const allow = ['cover_complete', 'deck_open', 'register_start', 'register_done', 'newsletter_open', 'newsletter_done', 'wa_tap', 'ig_tap', 'call_tap', 'lang_fr'];
  ok(names.length > 0 && names.every((n) => allow.includes(n)), 'beacon names are on the event.ts allowlist: ' + names.join(','));
  const h = await p.evaluate(() => document.querySelector('form[data-form=register]').getBoundingClientRect().height); ok(h <= 520, `register form compact on desktop (${Math.round(h)}px ≤ 520)`);
  ok(await p.evaluate(() => !/€/.test(document.body.innerText) && !/€/.test(document.querySelector('script[type="application/ld+json"]').textContent)), 'no fee or € anywhere on the page');
  await ctx.close();
  const m = await page({ ...devices['iPhone 13'] }); await m.p.goto(BASE + '/', { waitUntil: 'networkidle' });
  const hm = await m.p.evaluate(() => document.querySelector('form[data-form=register]').getBoundingClientRect().height); ok(hm <= 760, `register form compact on iPhone 13 (${Math.round(hm)}px ≤ 760)`);
  await m.p.click('[data-lang="fr"]'); await m.p.waitForTimeout(200);
  ok(!/€/.test(await m.p.evaluate(() => document.body.innerText)), 'no € in French either'); await m.ctx.close();
}
{ // consent wording beside each checkbox = the CONSENT_TEXT the API stores with the record (EN + FR, verbatim)
  const { readFileSync } = await import('node:fs');
  const ct = (f) => { const m = readFileSync(new URL(`../site/functions/api/${f}.ts`, import.meta.url), 'utf8').match(/en:\s*(['"])(.*?)\1,\s*fr:\s*(['"])(.*?)\3/s); return { en: m[2], fr: m[4] }; };
  const want = { register: ct('register'), subscribe: ct('subscribe') };
  const { ctx, p } = await page(); await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  const shown = () => p.evaluate(() => ({ register: document.querySelector('#reg-consent + span').textContent.trim(), subscribe: document.querySelector('#news-consent + span').textContent.trim() }));
  const en = await shown(); await p.click('.bar [data-lang="fr"]'); await p.waitForTimeout(200); const fr = await shown();
  for (const k of ['register', 'subscribe']) ok(en[k] === want[k].en && fr[k] === want[k].fr, `${k}: consent text matches ${k}.ts CONSENT_TEXT verbatim (EN + FR)`);
  await ctx.close();
}
{ // reduced motion: autoplay honours it (instant scroll), rings filled
  const { ctx, p } = await page({ reducedMotion: 'reduce' }); await p.goto(BASE + '/', { waitUntil: 'networkidle' });
  ok(await p.evaluate(() => getComputedStyle(document.querySelector('.twelve .spin')).animationName === 'none'), 'reduced motion: backdrop static');
  ok(await p.evaluate(() => document.querySelector('.mini__f').style.strokeDashoffset === '0'), 'reduced motion: rings filled'); await ctx.close();
}
for (const [kind, sel, fill] of [['register', 'form[data-form=register]', async (p) => { await p.fill('form[data-form=register] [name=name]', 'Test'); }], ['subscribe', 'form[data-form=subscribe]', async () => {}]]) {
  for (const status of [200, 400]) {
    const { ctx, p, errs } = await page(); let body = null;
    await p.route('**/api/' + kind, (r) => { body = r.request().postDataJSON(); r.fulfill({ status, contentType: 'application/json', body: status === 200 ? '{"ok":true}' : '{"ok":false,"error":"bad_email"}' }); });
    await p.goto(BASE + '/', { waitUntil: 'networkidle' }); await fill(p);
    await p.fill(sel + ' [name=email]', 'a@example.com'); await p.check(sel + ' [name=consent]');
    await p.click(sel + ' button[type=submit]'); await p.waitForTimeout(600);
    if (status === 200) ok(await p.isVisible(`[data-ok=${kind}]`) && body && body.consent === true && body.lang === 'en' && 'website' in body, `${kind}: 200 → success state in place, body has consent/lang/honeypot`);
    else ok(await p.isVisible(sel + ' [data-err]') && !(await p.isVisible(`[data-ok=${kind}]`)), `${kind}: 400 → error shown`);
    ok(p.url().startsWith(BASE + '/') && !p.url().includes('/api/'), `${kind}: no page reload`);
    ok(errs.filter((e) => !/status of 400/.test(e)).length === 0, `${kind} ${status}: console clean`); await ctx.close();
  }
}
{ const { ctx, p } = await page(); await p.goto(BASE + '/', { waitUntil: 'networkidle' }); let hit = false;
  await p.route('**/api/register', (r) => { hit = true; r.fulfill({ status: 200, body: '{}' }); });
  await p.click('form[data-form=register] button[type=submit]'); await p.waitForTimeout(300);
  ok(!hit && await p.isVisible('form[data-form=register] [data-err]'), 'register: empty submit blocked client-side'); await ctx.close(); }
{ // v5.1: strip (photo + caption + controls) fits the viewport under the header; header seal legible; phone nav stays reachable
  for (const [w, h, m] of [[320, 568, true], [390, 844, true], [1024, 768, true], [1440, 900, false], [1920, 1080, false], [3840, 2160, false]]) {
    const { ctx, p } = await page({ viewport: { width: w, height: h }, isMobile: m, hasTouch: m });
    await p.goto(BASE + '/', { waitUntil: 'networkidle' }); await p.waitForTimeout(400);
    await p.evaluate(() => { const el = document.querySelector('[data-strip]'); scrollTo({ top: el.getBoundingClientRect().top + scrollY - 300, behavior: 'instant' }); }); await p.waitForTimeout(250);
    await p.evaluate(() => { const el = document.querySelector('[data-strip]'); const hh = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--hfit')) || document.querySelector('header.bar').offsetHeight; scrollTo({ top: el.getBoundingClientRect().top + scrollY - hh, behavior: 'instant' }); }); await p.waitForTimeout(500);
    const r = await p.evaluate(() => { const R = (s) => document.querySelector(s).getBoundingClientRect(); const cards = [...document.querySelectorAll('.card')].filter((c) => { const b = c.getBoundingClientRect(); return b.left >= -2 && b.right <= innerWidth + 2; }).length;
      return { hdr: R('header.bar').bottom, frameTop: R('.card .step-frame').top, ctl: R('.sequence-controls').bottom, cards, seal: R('.bar .logo').height }; });
    ok(r.frameTop >= r.hdr - 1 && r.ctl <= h + 1, `${w}x${h}: strip photo, caption and controls fit under the header (photo top ${Math.round(r.frameTop)} ≥ ${Math.round(r.hdr)}, controls end ${Math.round(r.ctl)} ≤ ${h})`);
    if (w >= 3200) ok(r.cards === 5, `${w}: five whole cards in view (${r.cards})`);
    ok(r.seal >= (w <= 760 ? 48 : 56) - 0.5, `${w}: header seal ${Math.round(r.seal)} px tall`);
    if (w <= 360) { await p.evaluate(() => scrollBy({ top: -200, behavior: 'instant' })); await p.waitForTimeout(400); ok(await p.isVisible('.primary-nav a[href="#contact"]'), `${w}: navigation returns on scroll up`); }
    await ctx.close();
  }
}
await b.close();
console.log(`\n${failn ? 'FAILED' : 'PASSED'} — ${pass} pass, ${failn} fail`); process.exit(failn ? 1 : 0);
