/* Tier 5 functional walk + extra probes (reduced-motion folio, form submit, deck/for-ian links). */
const { createRequire } = require('module');
const req = createRequire('/opt/node-tools/node_modules/playwright/package.json');
const { chromium } = req('playwright');
const fs = require('fs'), path = require('path');
process.env.PLAYWRIGHT_BROWSERS_PATH = '/opt/pw-browsers';
const BASE = 'https://gtm-people-redesign.pages.dev'; const OUT = __dirname; const log = {};
const settle = async (p) => { await p.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))); await p.waitForTimeout(250); };
const shot = async (p, n) => { await p.screenshot({ path: path.join(OUT, n + '.png') }); };
(async () => {
  const browser = await chromium.launch();
  // A. Series A founder, desktop 1440: wants a London AE.
  { const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } }); const page = await ctx.newPage(); await page.goto(BASE + '/', { waitUntil: 'networkidle' }); await page.evaluate(() => document.fonts.ready);
    const a = {}; a.heroCtas = await page.evaluate(() => [...document.querySelectorAll('[data-film-hero] a')].map((x) => x.textContent.trim() + ' -> ' + x.getAttribute('href')));
    a.navLinks = await page.evaluate(() => [...document.querySelectorAll('[data-menu] a')].map((x) => x.textContent.trim() + ' -> ' + x.getAttribute('href')));
    // click "Roles"/"Hire" nav link; measure where it lands
    await page.click('[data-menu] a[href="#roles"]').catch(() => {}); await page.waitForTimeout(900); a.afterNavRolesScrollY = await page.evaluate(() => scrollY); a.filtersVisible = await page.evaluate(() => { const r = document.querySelector('[data-roles-filters]').getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight; });
    a.firstCardVisible = await page.evaluate(() => { const r = document.querySelector('[data-roles-list] [data-card]').getBoundingClientRect(); return { top: Math.round(r.top), bottom: Math.round(r.bottom), fully: r.top >= 0 && r.bottom <= innerHeight }; });
    await shot(page, 'walk_a_after_nav_roles');
    await page.click('[data-f-loc="London"]'); await page.click('[data-f-type="Sales"]'); await page.waitForTimeout(600); await settle(page);
    a.londonSales = await page.evaluate(() => ({ count: document.querySelector('[data-roles-count]').textContent, titles: [...document.querySelectorAll('[data-roles-list] h3')].map((h) => h.textContent), folioH: Math.round(document.querySelector('[data-roles-folio]').getBoundingClientRect().height), scrollY, filtersTop: Math.round(document.querySelector('[data-roles-filters]').getBoundingClientRect().top) }));
    await shot(page, 'walk_a_london_sales_card1');
    // after filter, can the founder still see the filters? (scrollIntoView moved folio to top)
    // apply button / CTA on a card?
    a.cardLinks = await page.evaluate(() => [...document.querySelectorAll('[data-roles-list] a')].map((x) => x.href));
    a.pricingFromRoles = await page.evaluate(() => Math.round(document.querySelector('#pricing').getBoundingClientRect().top));
    await page.click('[data-f-type=""]'); await page.click('[data-f-loc=""]'); await page.waitForTimeout(400);
    // contact form
    await page.evaluate(() => document.querySelector('#contact').scrollIntoView()); await page.waitForTimeout(800);
    await page.fill('[data-demo-form] [name=first]', 'Sophie'); await page.fill('[data-demo-form] [name=last]', 'Okafor'); await page.fill('[data-demo-form] [name=company]', 'Lumen'); await page.fill('[data-demo-form] [name=email]', 'sophie@lumen.io');
    await page.evaluate(() => document.querySelector('[data-demo-form] button[type=submit]').scrollIntoView({ block: 'center' })); await page.waitForTimeout(600);
    a.submitBtnVisible = await page.evaluate(() => { const b = document.querySelector('[data-demo-form] button[type=submit]'); const r = b.getBoundingClientRect(); const el = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); return { onTop: el === b || b.contains(el), topEl: el && (el.className || el.tagName) }; });
    await page.click('[data-demo-form] button[type=submit]'); await page.waitForTimeout(600);
    a.afterSubmit = await page.evaluate(() => ({ okHidden: document.querySelector('.form__ok').hidden, btnDisabled: document.querySelector('[data-demo-form] button[type=submit]').disabled, validity: document.querySelector('[data-demo-form]').checkValidity() }));
    await shot(page, 'walk_a_form_submitted');
    a.footerExternal = await page.evaluate(() => [...document.querySelectorAll('a[href^="http"]')].map((x) => x.href).filter((v, i, s) => s.indexOf(v) === i));
    log.founder = a; await ctx.close(); }
  // B. Candidate SDR in New York, mobile 390.
  { const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 }); const page = await ctx.newPage(); await page.goto(BASE + '/', { waitUntil: 'networkidle' }); await page.evaluate(() => document.fonts.ready);
    const b = {}; b.bottombar = await page.evaluate(() => [...document.querySelectorAll('.bottombar a')].map((x) => x.textContent + '->' + x.getAttribute('href')));
    await page.tap('.bottombar a[href="#roles"]'); await page.waitForTimeout(1000); b.scrollYAfterRolesTap = await page.evaluate(() => scrollY); b.rolesHeadTop = await page.evaluate(() => Math.round(document.querySelector('#roles').getBoundingClientRect().top));
    b.filtersInView = await page.evaluate(() => { const r = document.querySelector('[data-roles-filters]').getBoundingClientRect(); return { top: Math.round(r.top), bottom: Math.round(r.bottom), vh: innerHeight }; });
    await shot(page, 'walk_b_after_roles_tap');
    await page.tap('[data-f-type="SDR/BDR"]'); await page.tap('[data-f-loc="New York"]'); await page.waitForTimeout(500);
    b.sdrNY = await page.evaluate(() => ({ count: document.querySelector('[data-roles-count]').textContent, html: document.querySelector('[data-roles-list]').innerText.slice(0, 200) }));
    await page.evaluate(() => document.querySelector('[data-roles-list]').scrollIntoView({ block: 'center' })); await page.waitForTimeout(400); await shot(page, 'walk_b_sdr_ny_empty');
    await page.tap('[data-f-type=""]'); await page.waitForTimeout(400); b.anyNY = await page.evaluate(() => ({ count: document.querySelector('[data-roles-count]').textContent, titles: [...document.querySelectorAll('[data-roles-list] h3')].map((h) => h.textContent) }));
    b.sdrAnywhere = await (async () => { await page.tap('[data-f-loc=""]'); await page.tap('[data-f-type="SDR/BDR"]'); await page.waitForTimeout(400); return page.evaluate(() => ({ count: document.querySelector('[data-roles-count]').textContent, titles: [...document.querySelectorAll('[data-roles-list] h3')].map((h) => h.textContent) })); })();
    b.cardCTA = await page.evaluate(() => document.querySelectorAll('[data-roles-list] a, [data-roles-list] button').length);
    b.registerLink = await page.evaluate(() => { const a = document.querySelector('.stack__foot a'); return a && a.getAttribute('href'); });
    b.contactDistanceFromRoles = await page.evaluate(() => Math.round(document.querySelector('#contact').getBoundingClientRect().top + scrollY - (document.querySelector('#roles').getBoundingClientRect().top + scrollY)));
    b.candidateFormFields = await page.evaluate(() => [...document.querySelectorAll('[data-demo-form] [name]')].map((x) => x.name));
    b.salaryMentionsSDR = await page.evaluate(() => /SDR/.test(document.querySelector('#salary').innerText));
    b.salaryUS = await page.evaluate(() => /\$|US/.test(document.querySelector('#salary').innerText));
    b.salaryText = await page.evaluate(() => document.querySelector('#salary').innerText.slice(0, 600));
    // menu
    await page.evaluate(() => scrollTo(0, 0)); await page.waitForTimeout(400); await page.tap('[data-menu-toggle]'); await page.waitForTimeout(500); await shot(page, 'walk_b_menu_open'); b.menuLinks = await page.evaluate(() => [...document.querySelectorAll('[data-menu] a')].map((x) => x.textContent.trim()));
    log.candidate = b; await ctx.close(); }
  // C. Ian, desktop: /for-ian/ then into the site; plus deck.
  { const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } }); const page = await ctx.newPage(); await page.goto(BASE + '/for-ian/', { waitUntil: 'networkidle' }); await page.evaluate(() => document.fonts.ready);
    const c = {}; c.forIanText = await page.evaluate(() => document.body.innerText.replace(/\s+/g, ' ').slice(0, 2500));
    c.forIanLinks = await page.evaluate(() => [...document.querySelectorAll('a')].map((x) => x.textContent.trim() + ' -> ' + x.getAttribute('href')));
    c.forIanH1 = await page.evaluate(() => document.querySelectorAll('h1').length);
    const links = await page.evaluate(() => [...document.querySelectorAll('a[href]')].map((x) => x.href).filter((v, i, s) => s.indexOf(v) === i));
    c.linkStatus = {}; for (const l of links) { if (!/gtm-people-redesign\.pages\.dev/.test(l)) continue; try { const r = await page.request.get(l.split('#')[0]); c.linkStatus[l] = r.status(); } catch (e) { c.linkStatus[l] = 'ERR'; } }
    await page.evaluate(() => scrollTo(0, document.documentElement.scrollHeight)); await page.waitForTimeout(500); await shot(page, 'walk_c_forian_bottom');
    await page.goto(BASE + '/deck/', { waitUntil: 'networkidle' }); await page.waitForTimeout(500);
    c.deckText = await page.evaluate(() => document.body.innerText.replace(/\s+/g, ' ').slice(0, 1200));
    c.deckPanelsVisibleOnLoad = await page.evaluate(() => [...document.querySelectorAll('.panel[role=tabpanel]')].map((p) => p.id + ':' + !p.hidden + ':' + getComputedStyle(p).display));
    await page.click('#tab-pricing'); await page.waitForTimeout(500); c.deckPricingHash = await page.evaluate(() => location.hash); await page.reload({ waitUntil: 'networkidle' }); await page.waitForTimeout(600); c.deckReloadKeepsTab = await page.evaluate(() => document.querySelector('[role=tab][aria-selected=true]').id);
    c.deckRolesClaims = await page.evaluate(() => { const r = document.querySelector('#roles'); return r ? r.innerText.replace(/\s+/g, ' ').slice(0, 400) : null; });
    c.deckConceptLabel = await page.evaluate(() => /concept|not affiliated/i.test(document.body.innerText));
    // honesty: claims in the main page
    await page.goto(BASE + '/', { waitUntil: 'networkidle' }); await page.waitForTimeout(500);
    c.proofClaims = await page.evaluate(() => document.querySelector('.proof').innerText.replace(/\s+/g, ' '));
    c.conceptDisclosures = await page.evaluate(() => [...document.querySelectorAll('body *')].filter((e) => e.children.length === 0 && /concept|not affiliated|not wired|ProdCraft/i.test(e.textContent)).map((e) => e.textContent.trim()).slice(0, 10));
    c.founderText = await page.evaluate(() => document.querySelector('#about').innerText.replace(/\s+/g, ' ').slice(0, 900));
    c.taasText = await page.evaluate(() => document.querySelector('#taas').innerText.replace(/\s+/g, ' ').slice(0, 900));
    c.pricingTiers = await page.evaluate(() => [...document.querySelectorAll('.tier')].map((t) => t.innerText.replace(/\s+/g, ' ').slice(0, 260)));
    c.insightsText = await page.evaluate(() => document.querySelector('#insights').innerText.replace(/\s+/g, ' ').slice(0, 600));
    c.title = await page.title(); c.metaDesc = await page.evaluate(() => (document.querySelector('meta[name=description]') || {}).content);
    log.ian = c; await ctx.close(); }
  // D. Reduced-motion roles folio check at 1440 — blank space after the stacked cards?
  { const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' }); const page = await ctx.newPage(); await page.goto(BASE + '/', { waitUntil: 'networkidle' }); await page.waitForTimeout(600);
    const d = await page.evaluate(() => { const f = document.querySelector('[data-roles-folio]'); const cards = [...f.querySelectorAll('[data-card]')]; const last = cards[cards.length - 1].getBoundingClientRect(); const fr = f.getBoundingClientRect(); return { folioMinHeightInline: f.style.minHeight, folioH: Math.round(fr.height), lastCardBottomRelFolio: Math.round(last.bottom - fr.top), blankPx: Math.round(fr.bottom - last.bottom), cardWidths: cards.map((c) => Math.round(c.getBoundingClientRect().width)), specFolio: (() => { const s = document.querySelector('#specialisms [data-folio]'); const cs = [...s.querySelectorAll('[data-card]')]; const l = cs[cs.length - 1].getBoundingClientRect(); return { h: Math.round(s.getBoundingClientRect().height), blank: Math.round(s.getBoundingClientRect().bottom - l.bottom), widths: cs.map((c) => Math.round(c.getBoundingClientRect().width)) }; })() }; });
    await page.evaluate(() => { const f = document.querySelector('[data-roles-folio]'); const cards = f.querySelectorAll('[data-card]'); cards[cards.length - 1].scrollIntoView({ block: 'start' }); }); await page.waitForTimeout(500); await shot(page, 'home_d1440-rm_roles_after_last_card');
    await page.evaluate(() => { const f = document.querySelector('[data-roles-folio]'); scrollTo(0, f.getBoundingClientRect().top + scrollY + f.getBoundingClientRect().height / 2); }); await page.waitForTimeout(500); await shot(page, 'home_d1440-rm_roles_folio_middle');
    log.reducedMotion = d; await ctx.close(); }
  fs.writeFileSync(path.join(OUT, 'walk_log.json'), JSON.stringify(log, null, 2)); console.log('walk done'); await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
