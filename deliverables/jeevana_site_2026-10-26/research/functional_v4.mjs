// v4 functional gate (Playwright). usage: node research/serve_csp.mjs site 8794 & node research/functional_v4.mjs [base]
import { createRequire } from 'node:module';
const req = createRequire('/opt/node22/lib/node_modules/'); const { chromium } = req('playwright');
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
  ok((await p.getAttribute('img.ph', 'alt')).includes('Jeevana assise'), 'alt text switches to FR');
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
  await p.click('[data-next]'); await p.waitForTimeout(900);
  ok(await p.evaluate(() => JV_strip.cur()) === 1 && (await lit()) === 1 && (await litC()) === 1, 'next arrow → card 2, backdrop arcs follow');
  ok((await p.textContent('[data-cur]')) === '02', 'progress shows 02');
  await p.focus('[data-strip]'); await p.keyboard.press('ArrowRight'); await p.waitForTimeout(900);
  ok(await p.evaluate(() => JV_strip.cur()) === 2 && (await lit()) === 2, 'ArrowRight key → card 3');
  await p.keyboard.press('ArrowLeft'); await p.waitForTimeout(900); ok(await p.evaluate(() => JV_strip.cur()) === 1, 'ArrowLeft key → card 2');
  await p.click('[data-prev]'); await p.waitForTimeout(900); ok(await p.evaluate(() => JV_strip.cur()) === 0, 'prev arrow → card 1');
  // snap: scroll manually off-centre, expect it to settle centred
  await p.evaluate(() => { const s = document.querySelector('[data-strip]'); s.scrollBy({ left: 1300, behavior: 'instant' }); }); await p.waitForTimeout(1200);
  const off = await p.evaluate(() => { const s = document.querySelector('[data-strip]'); const c = document.querySelectorAll('.card')[JV_strip.cur()]; return Math.abs(c.offsetLeft + c.offsetWidth / 2 - s.scrollLeft - s.clientWidth / 2); });
  ok(off < 4 && (await lit()) === await p.evaluate(() => JV_strip.cur()), `scroll-snap centres a card (off ${off.toFixed(1)}px) and lights its arc`);
  // drag
  const before = await p.evaluate(() => JV_strip.cur()); const box = await p.locator('[data-strip]').boundingBox();
  await p.mouse.move(box.x + box.width / 2, box.y + 200); await p.mouse.down(); await p.mouse.move(box.x + box.width / 2 - 400, box.y + 200, { steps: 8 }); await p.mouse.up(); await p.waitForTimeout(1000);
  ok(await p.evaluate(() => JV_strip.cur()) > before, 'mouse drag advances');
  // autoplay
  await p.mouse.move(5, 5); const a0 = await p.evaluate(() => JV_strip.cur()); await p.click('[data-play]');
  ok(await p.evaluate(() => JV_strip.playing()), 'play starts autoplay'); await p.mouse.move(5, 5); await p.waitForTimeout(4600);
  ok(await p.evaluate(() => JV_strip.cur()) === (a0 + 2) % 12, 'autoplay advanced after 4 s');
  await p.click('[data-play]'); ok(!(await p.evaluate(() => JV_strip.playing())), 'pause stops autoplay');
  ok(errs.length === 0, 'strip: no console errors ' + errs.join(' | ')); await ctx.close();
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
await b.close();
console.log(`\n${failn ? 'FAILED' : 'PASSED'} — ${pass} pass, ${failn} fail`); process.exit(failn ? 1 : 0);
