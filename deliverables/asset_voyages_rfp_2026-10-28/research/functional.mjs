#!/usr/bin/env node
/* functional.mjs — ASSET Voyages concept v2 (« Du brief au retour »). Adapted from
   .claude/skills/site-redesign/scripts/functional_template.mjs for the film / card-stack / drum architecture.
   usage: node research/serve_csp.mjs site 8794 &  node research/functional.mjs http://localhost:8794/
   outputs: research/functional.json; exit 0 only on N/N. */
import { createRequire } from 'node:module'; import { writeFileSync, readFileSync, readdirSync, statSync } from 'node:fs'; import { join } from 'node:path';
const base = (process.argv[2] || 'http://localhost:8794/').replace(/\/?$/, '/');
const SITE = new URL('../site/', import.meta.url).pathname;
process.env.PLAYWRIGHT_BROWSERS_PATH ||= '/opt/pw-browsers';
const req = createRequire(import.meta.url); let pw; for (const p of ['/opt/node-tools/node_modules/playwright', '/tmp/pwtest/node_modules/playwright', 'playwright']) { try { pw = req(p); break; } catch {} }
const { chromium, devices } = pw;
const R = []; const t = (name, ok, info) => { R.push({ name, ok: !!ok, info }); console.log((ok ? 'ok   ' : 'FAIL ') + name + (info !== undefined ? ' — ' + info : '')); };
const b = await chromium.launch();
async function mk(opts) {
  const ctx = await b.newContext({ locale: 'fr-FR', ...opts }); const p = await ctx.newPage(); const errs = [], hosts = new Set();
  p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
  p.on('request', (r) => { const u = r.url(); if (/^https?:/.test(u)) hosts.add(new URL(u).host); });
  p._errs = errs; p._hosts = hosts; return p;
}
const go = async (p, y) => { await p.evaluate((v) => { document.documentElement.style.scrollBehavior = 'auto'; window.scrollTo(0, v); }, y); await p.waitForTimeout(450); };
const trackY = (p, sel, f) => p.evaluate(([s, f]) => { const el = document.querySelector(s); return el.getBoundingClientRect().top + scrollY + (el.offsetHeight - innerHeight) * f; }, [sel, f]);
const filmY = (p, k) => p.evaluate((k) => { const el = document.querySelector('[data-film]'); return el.offsetTop + (el.offsetHeight - innerHeight) * Math.min(1, (k / 6) * 0.92); }, k);
const onState = (p) => p.evaluate(() => { const s = document.querySelector('[data-film-state].is-on'); return s ? +s.dataset.filmState : -1; });

// ================= desktop =================
let p = await mk({ viewport: { width: 1440, height: 900 } });
await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(2500);
const seen = []; for (let k = 0; k <= 6; k++) { await go(p, await filmY(p, k)); seen.push(await onState(p)); }
t('film: seven states in order across the scroll track', seen.join() === '0,1,2,3,4,5,6', seen.join());
const fills = await p.evaluate(() => [...document.querySelectorAll('[data-film-step]')].map((li) => li.style.getPropertyValue('--fill')));
t('film: step rail fills to the last stage', fills.every((f) => +f >= 0.99), fills.join());
const vid = await p.evaluate(() => { const v = document.querySelector('[data-film-video]'); const c = document.querySelector('.film__canvas'); return { blob: /^blob:/.test(v.currentSrc || v.src), ready: v.readyState, dur: v.duration, canvas: !!c }; });
t('film: video fetched as a blob (seekable) or canvas fallback', (vid.blob && vid.ready >= 1 && Math.abs(vid.dur - 30) < 0.2) || vid.canvas, JSON.stringify(vid));
await go(p, await filmY(p, 3)); await p.waitForTimeout(2000);
const t3 = await p.evaluate(() => document.querySelector('[data-film-video]').currentTime);
await go(p, await filmY(p, 1)); await p.waitForTimeout(2000);
const t1 = await p.evaluate(() => document.querySelector('[data-film-video]').currentTime);
t('film: scroll scrubs currentTime to the keyframe (15 s), and back (5 s)', Math.abs(t3 - 15) < 0.6 && Math.abs(t1 - 5) < 0.6, `${t3.toFixed(2)} → ${t1.toFixed(2)}`);
await go(p, await filmY(p, 0)); await p.waitForTimeout(1500);
await p.evaluate((y) => { document.documentElement.style.scrollBehavior = 'auto'; window.scrollTo(0, y); }, await filmY(p, 5)); await p.waitForTimeout(60);
const fling = await p.evaluate(() => { const vis = [...document.querySelectorAll('[data-film-state]')].filter((el) => getComputedStyle(el).visibility === 'visible' && +getComputedStyle(el).opacity > 0); const v = document.querySelector('[data-film-video]'); return { n: vis.length, on: vis.map((e) => +e.dataset.filmState), shown: Math.round(v.currentTime / 5) }; });
await p.waitForTimeout(2500); const settled = await onState(p);
t('film fling: exactly one text layer visible (hard swap), matching the frame on screen, settles on 05', fling.n === 1 && Math.abs(fling.on[0] - fling.shown) <= 1 && settled === 5, JSON.stringify({ ...fling, settled }));
const hdr = await p.evaluate(() => ({ sc: document.querySelector('[data-header]').classList.contains('is-scrolled'), prog: +document.querySelector('[data-header]').style.getPropertyValue('--page-progress') }));
t('header: shrinks on scroll, progress bar advances', hdr.sc && hdr.prog > 0, JSON.stringify(hdr));
// card stack
const card = (i) => p.evaluate((i) => { const c = document.querySelectorAll('[data-card]')[i]; const cs = getComputedStyle(c); return { tf: cs.transform, o: +cs.opacity }; }, i);
await go(p, await trackY(p, '[data-folio]', 0)); const c0 = await card(0), c2a = await card(2);
await go(p, await trackY(p, '[data-folio]', 0.5)); const c0m = await card(0), c1m = await card(1);
await go(p, await trackY(p, '[data-folio]', 1)); const c0e = await card(0), c2e = await card(2);
const idx = await p.evaluate(() => document.querySelector('[data-folio-idx]').textContent);
const rot = await p.evaluate(() => [...document.querySelectorAll('[data-card]')].every((c) => { const m = getComputedStyle(c).transform; if (m === 'none') return true; const v = m.match(/matrix\(([^)]+)\)/)[1].split(',').map(Number); return Math.abs(v[1]) < 1e-6; }));
t('card stack: no rotation (text stays sharp)', rot);
t('card stack: first card retires as the next slides in', c0.o === 1 && c0.tf !== c0m.tf && c0m.o < 0.2 && c1m.o > 0.95, JSON.stringify({ c0: c0.o, c0m: c0m.o, c1m: c1m.o }));
t('card stack: third card on top at the end, counter 03', c2e.o > 0.95 && c0e.o < 0.1 && c2a.o < c2e.o && idx === '03', JSON.stringify({ c2a: c2a.o, c2e: c2e.o, idx }));
// drum
const drum = () => p.evaluate(() => [...document.querySelectorAll('[data-step]')].map((li) => ({ o: +getComputedStyle(li).opacity, r: li.style.getPropertyValue('--dr'), on: li.classList.contains('is-on') })));
await go(p, await trackY(p, '[data-drum]', 0)); const d0 = await drum();
await go(p, await trackY(p, '[data-drum]', 0.5)); const d5 = await drum();
const prog = await p.evaluate(() => +document.querySelector('[data-drum]').style.getPropertyValue('--approach-progress'));
t('drum: step 01 faces the reader at the start', d0[0].o > 0.98 && d0[0].on && d0[1].o < 0.5, JSON.stringify(d0.map((x) => x.o)));
t('drum: rotates to step 03 at mid-track (rotateX on neighbours, progress bar)', d5[2].on && d5[2].o > 0.95 && d5[1].o < 0.05 && d5[0].r !== '0deg' && prog > 0.45 && prog < 0.55, JSON.stringify({ on: d5.findIndex((x) => x.on), o: d5.map((x) => x.o.toFixed(2)), prog }));
// catalogue
await p.evaluate(() => document.querySelector('#congres').scrollIntoView()); await p.waitForTimeout(400);
const cat = () => p.evaluate(() => ({ n: document.querySelector('[data-count-label]').textContent, vis: [...document.querySelectorAll('.row')].filter((r) => !r.hidden).map((r) => r.dataset.id), empty: !document.querySelector('[data-empty]').hidden, dates: [...document.querySelectorAll('.row')].filter((r) => !r.hidden).map((r) => r.dataset.start) }));
let c = await cat();
t('catalogue: 12 congresses, 6 per page, ascending date sort', c.n === '12 congrès · page 1/2' && c.vis.length === 6 && c.dates.join() === [...c.dates].sort().join() && !c.empty, c.n + ' ' + c.dates.join());
await p.click('[data-pager] button[aria-label="Page 2"]'); await p.waitForTimeout(200); const pg2 = await cat();
t('catalogue: pagination shows page 2', pg2.vis.length === 6 && pg2.vis[0] !== c.vis[0] && pg2.dates[0] >= c.dates[5], pg2.n);
await p.fill('#q', 'vienne'); await p.waitForTimeout(200); c = await cat();
t('catalogue: text search (accent-insensitive, city)', c.vis.length === 2 && /2 congrès/.test(c.n), c.vis.join());
await p.fill('#q', ''); await p.selectOption('#f-disc', 'Oncologie'); await p.waitForTimeout(200); c = await cat();
t('catalogue: discipline filter', c.vis.length === 2, c.vis.join());
await p.selectOption('#f-country', 'France'); await p.selectOption('#f-per', '1'); await p.waitForTimeout(200); c = await cat();
t('catalogue: combined country + period filter', c.vis.join() === 'CG-0112', c.vis.join());
await p.fill('#q', 'zzzz'); await p.waitForTimeout(200); c = await cat();
t('catalogue: no-results state', c.vis.length === 0 && c.empty && /^0 congrès/.test(c.n), c.n);
await p.click('.cat__filters button[type=reset]'); await p.waitForTimeout(250); c = await cat();
t('catalogue: reset restores the full list', c.n === '12 congrès · page 1/2' && !c.empty, c.n);
// listing + prefilled quote
await p.click('.row[data-id="CG-0103"] [data-open]'); await p.waitForTimeout(300);
const lst = await p.evaluate(() => { const f = document.querySelector('[data-form="f03"]').elements; return { open: document.querySelector('[data-listing]').open, title: document.querySelector('[data-l-title]').textContent, ev: f.event.value, to: f.to.value, out: f.out.value, back: f.back.value, from: f.from.value }; });
t('listing: dialog opens with the congress, source and verification date', lst.open && /diabétologie/.test(lst.title), lst.title);
t('quote (F03): prefilled event + ID, destination, fr-FR dates, departure open to any airport', /CG-0103/.test(lst.ev) && lst.to === 'Lyon, France' && lst.out === '22/03/2027' && lst.back === '27/03/2027' && lst.from === '', JSON.stringify(lst));
await p.click('[data-form="f03"] button[type=submit]'); await p.waitForTimeout(200);
const inv = await p.evaluate(() => document.querySelector('[data-form="f03"] [data-ok]').hidden);
await p.fill('#d-from', 'Nantes'); await p.fill('#d-name', 'Test'); await p.fill('#d-mail', 'test@example.com'); await p.click('[data-form="f03"] button[type=submit]'); await p.waitForTimeout(200);
const okq = await p.evaluate(() => document.querySelector('[data-form="f03"] [data-ok]').textContent);
t('quote (F03): blocks an incomplete request, confirms a valid one without sending', inv && /CG-0103/.test(okq) && /Nantes/.test(okq) && /Rien n’a été envoyé/.test(okq), okq.slice(0, 80));
await p.keyboard.press('Escape'); await p.waitForTimeout(200);
t('listing: Escape closes the dialog', await p.evaluate(() => !document.querySelector('[data-listing]').open));
// contact journeys
await p.evaluate(() => document.querySelector('[data-film-state="5"] [data-journey]').click()); await p.waitForTimeout(500);
const j = await p.evaluate(() => ({ ev: !document.querySelector('[data-part="evenement"]').hidden, en: document.querySelector('[data-part="entreprise"]').hidden, radio: document.querySelector('[data-j][value="evenement"]').checked }));
t('contact: "Préparer un événement" opens the MICE journey', j.ev && j.en && j.radio, JSON.stringify(j));
await p.fill('#m-dest', 'Lisbonne'); await p.fill('#m-pax', '40');
const recap = await p.evaluate(() => document.querySelector('[data-recap]').textContent);
t('contact (F02): live summary before submission', /Lisbonne/.test(recap) && /40 participants/.test(recap), recap);
await p.fill('#m-pax', '4'); await p.fill('#c-name', 'Test'); await p.fill('#c-mail', 'test@example.com'); await p.click('[data-form="contact"] button[type=submit]'); await p.waitForTimeout(200);
const blocked = await p.evaluate(() => document.querySelector('[data-form="contact"] [data-ok]').hidden);
await p.fill('#m-pax', '40'); await p.click('[data-form="contact"] button[type=submit]'); await p.waitForTimeout(200);
const okc = await p.evaluate(() => document.querySelector('[data-form="contact"] [data-ok]').textContent);
t('contact (F02): groups start at 10 people; valid brief confirmed without sending', blocked && /MICE/.test(okc) && /rien n’a été envoyé/.test(okc), okc.slice(0, 70));
await p.evaluate(() => document.querySelector('[data-folio] [data-need="Audit de vos voyages"]').click()); await p.waitForTimeout(300);
const f01 = await p.evaluate(() => ({ j: document.querySelector('[data-j][value="entreprise"]').checked, need: document.querySelector('[data-need-select]').value, req: document.querySelector('#c-co').required }));
t('contact (F01): "Demander un audit" preselects the business journey and need', f01.j && f01.need === 'Audit de vos voyages' && f01.req, JSON.stringify(f01));
// header tools
await go(p, 0); await p.click('[data-en]'); await p.waitForTimeout(150);
const toast = await p.evaluate(() => { const tt = document.querySelector('[data-toast]'); return !tt.hidden && /option chiffrée/.test(tt.textContent) && !/bientôt|coming soon/i.test(tt.textContent); });
await p.click('[data-client]'); await p.waitForTimeout(100);
const pop = await p.evaluate(() => !document.querySelector('[data-client-pop]').hidden && document.querySelector('[data-client]').getAttribute('aria-expanded') === 'true');
t('header: EN switch says "option" (not "bientôt"), client-area note opens', toast && pop, JSON.stringify({ toast, pop }));
const fonts = await p.evaluate(() => document.fonts.check('500 40px "EB Garamond"') && [...document.fonts].some((f) => f.family.includes('EB Garamond') && f.status === 'loaded'));
t('fonts: EB Garamond self-hosted and loaded (no Cormorant)', fonts && !/Cormorant/.test(readFileSync(SITE + 'css/styles.css', 'utf8')), String(fonts));
const dh = await p.evaluate(() => document.documentElement.scrollHeight);
t('desktop: 0 console errors (served with the real _headers CSP)', p._errs.length === 0, p._errs.slice(0, 2).join(' | '));
t('zero third-party requests', [...p._hosts].every((h) => /^localhost/.test(h)), [...p._hosts].join());
await p.close();

// ================= static checks =================
const kb = (f) => statSync(SITE + f).size;
const jsFiles = readdirSync(SITE + 'js').map((f) => 'js/' + f);
const sizes = { html: kb('index.html'), css: kb('css/styles.css'), js: jsFiles.reduce((a, f) => a + kb(f), 0) };
t('budget: index + css + all js ≤ 150 KB (video excluded)', sizes.html + sizes.css + sizes.js <= 150 * 1024, JSON.stringify(sizes) + ' = ' + ((sizes.html + sizes.css + sizes.js) / 1024).toFixed(1) + ' KB');
const walk = (d) => readdirSync(d).flatMap((f) => { const q = join(d, f); return statSync(q).isDirectory() ? walk(q) : [q]; });
const textFiles = walk(SITE).filter((f) => /\.(html|css|js|json|txt|_headers)$|_headers$/.test(f));
const BANNED = /evolution|\bexhibits?\b|misb|greenjobs|green jobs|gaia|jitendra|jeevana|midas|papaya|gtm people/i;
const hits = textFiles.filter((f) => BANNED.test(readFileSync(f, 'utf8'))).map((f) => f.replace(SITE, ''));
t('confidentiality: no other client or project named anywhere in the built site', hits.length === 0, hits.join() || textFiles.length + ' files clean');
const html = readFileSync(SITE + 'index.html', 'utf8');
t('third-party claim: Selectour Affaires sentence verbatim + real logo file', html.includes('Avec plus de 122 agences et plateaux d’affaires en France, Selectour Affaires constitue le premier réseau dédié aux voyages d’affaires.') && kb('assets/img/selectour-affaires.png') > 1000);
t('no invented figures: no €, %, prices or GM&E codes in the public page', !/\d\s?€|\d\s?%|GME-\d/.test(html.replace(/<[^>]+>/g, ' ')));
t('lang fr + no English UI strings in the home page', /<html lang="fr">/.test(html) && !/\b(Search|Submit|Contact us|Read more|Learn more)\b/.test(html));

// ================= mobile =================
p = await mk({ ...devices['Pixel 7'] });
await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(2000);
const ms = []; for (const k of [0, 3, 6]) { await go(p, await filmY(p, k)); ms.push(await onState(p)); }
const msrc = await p.evaluate(() => { const v = document.querySelector('[data-film-video]'); return { poster: v.poster.split('/').pop(), canvas: !!document.querySelector('.film__canvas'), dur: v.duration }; });
t('Pixel 7: film scrubs (states 0/3/6) on the portrait cut', ms.join() === '0,3,6' && msrc.poster === 'hero-m.jpg', ms.join() + ' ' + JSON.stringify(msrc));
const geo = await p.evaluate(() => { const h = document.querySelector('[data-header]').getBoundingClientRect(); const s = document.querySelector('[data-film-state].is-on .eyebrow').getBoundingClientRect(); const m = document.querySelector('.film__media').getBoundingClientRect(); const hb = getComputedStyle(document.querySelector('[data-header]')).backgroundColor; return { hBottom: Math.round(h.bottom), mediaTop: Math.round(m.top), copyTop: Math.round(s.top), hb }; });
t('Pixel 7: opaque header never covers the film or its copy', geo.mediaTop >= geo.hBottom && geo.copyTop > geo.hBottom && geo.hb === 'rgb(10, 31, 48)', JSON.stringify(geo));
const flat = await p.evaluate(() => ({ card: getComputedStyle(document.querySelector('[data-card]')).transform, step: getComputedStyle(document.querySelector('[data-step]')).transform, sticky: getComputedStyle(document.querySelector('.offers__sticky')).position }));
t('Pixel 7: card stack and drum flatten (no 3D, no pin)', flat.card === 'none' && flat.step === 'none' && flat.sticky === 'relative', JSON.stringify(flat));
let anchorsOk = true; const ai = [];
for (const id of ['offres', 'congres', 'methode', 'services', 'agence', 'contact']) {
  await p.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; }); await p.click('[data-burger]'); await p.waitForTimeout(300); await p.click(`[data-menu] a[href="#${id}"]`); await p.waitForTimeout(500);
  const r = await p.evaluate((id) => { const h = document.querySelector('[data-header]').getBoundingClientRect().bottom; const first = document.querySelector('#' + id + ' .label, #' + id + ' h2'); return { h: Math.round(h), top: Math.round(first.getBoundingClientRect().top) }; }, id);
  ai.push(id + ':' + r.top + '/' + r.h); if (r.top < r.h) anchorsOk = false;
}
t('Pixel 7: menu anchors land below the fixed header (no overlap)', anchorsOk, ai.join(' '));
const tel = await p.evaluate(() => { const a = document.querySelector('.contact__tel'); return a.getBoundingClientRect().height < parseFloat(getComputedStyle(a).fontSize) * 1.6; });
t('Pixel 7: phone number on one line', tel);
const ov = await p.evaluate(() => document.documentElement.scrollWidth - innerWidth);
t('Pixel 7: no horizontal overflow', ov <= 0, ov + ' px');
const inputs = await p.evaluate(() => [...document.querySelectorAll('.field input,.field select')].every((i) => parseFloat(getComputedStyle(i).fontSize) >= 16));
t('Pixel 7: form fields ≥ 16 px (no iOS zoom)', inputs);
const mh = await p.evaluate(() => document.documentElement.scrollHeight);
t('Pixel 7: 0 console errors', p._errs.length === 0, p._errs.slice(0, 2).join(' | '));
await p.close();
p = await mk({ ...devices['iPhone 13'] }); await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(1200);
let fit = true; const fitInfo = [];
for (const k of [0, 3, 5]) { await go(p, await filmY(p, k)); await p.waitForTimeout(700); const r = await p.evaluate(() => { const m = document.querySelector('.film__media').getBoundingClientRect(); const c = document.querySelector('[data-film-state].is-on').getBoundingClientRect(); return { subjBottom: Math.round(m.top + m.height * 0.78), copyTop: Math.round(c.top) }; }); fitInfo.push(k + ':' + r.subjBottom + '<=' + r.copyTop); if (r.subjBottom > r.copyTop) fit = false; }
t('iPhone 13: film subject never covered by the copy (states 01/04/06)', fit, fitInfo.join(' '));
const ovi = await p.evaluate(() => document.documentElement.scrollWidth - innerWidth);
const mh390 = await p.evaluate(() => document.documentElement.scrollHeight);
t('iPhone 13: no horizontal overflow, 0 errors', ovi <= 0 && p._errs.length === 0, ovi + ' px');
await p.close();
// reduced motion
p = await mk({ ...devices['Pixel 7'], reducedMotion: 'reduce' }); await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(1200);
const rm = await p.evaluate(() => ({ src: document.querySelector('[data-film-video]').currentSrc, list: document.querySelectorAll('.film__static li').length, film: document.querySelector('[data-film]').offsetHeight, vh: innerHeight }));
t('reduced motion: poster + static list of the six other stages, no scrub track, no video download', !rm.src && rm.list === 6 && rm.film < rm.vh * 3, JSON.stringify(rm));
await p.close();
// pitch + console
p = await mk({ viewport: { width: 1440, height: 900 } }); await p.goto(base + 'pour-asset/', { waitUntil: 'load' }); await p.waitForTimeout(500);
const pitch = await p.evaluate(() => document.body.innerText);
t('pitch: signature, business benefit per activity, written-answers next step (no call, no lot codes, no px), 0 errors', /Debanjan/.test(pitch) && /Fondateur, ProdCraft/.test(pitch) && /debanjan@prodcraft\.fyi/.test(pitch) && /Ce que la refonte change pour ASSET/.test(pitch) && /routées vers l’adresse que vous choisissez/.test(pitch) && /seule la proposition détaillée, une fois signée/.test(pitch) && /vendredi 6 novembre 2026/.test(pitch) && !/29 pages|film définitif|bonne personne/.test(pitch) && /Vos réponses écrites/.test(pitch) && /en un seul PDF/.test(pitch) && /24 à 48 heures/.test(pitch) && /Mme Veena Khatri/.test(pitch) && !/Veena(?! Khatri)/.test(pitch) && !/30 minutes|section 8|\bL[0-4]\b|trentaine|\{\{|\d px|hébergé sur notre domaine|mot pour mot de votre site actuel \(/.test(pitch) && p._errs.length === 0);
const q8 = await p.evaluate(() => { const a = document.querySelector('a[href="../questions/#s8"]'); return !!a; });
t('pitch: next step links to the 30 questions (#s8)', q8);
await p.goto(base + 'questions/', { waitUntil: 'load' }); await p.waitForTimeout(300);
const qp = await p.evaluate(() => ({ txt: document.body.innerText, n: document.querySelectorAll('#s8 .qs li').length, s8: !!document.getElementById('s8') }));
t('questions: 30 questions, unlisted (not "private") wording, no absolute "never lost", work examples without client names, 0 errors', qp.n === 30 && qp.s8 && /unlisted/.test(qp.txt) && !/\bprivate\b/i.test(qp.txt.replace(/private event codes/i, '')) && !/never lost/i.test(qp.txt) && /Examples of our work come with the proposal, described without naming our clients/.test(qp.txt) && !/Verifiable references/.test(qp.txt) && /€4\.30/.test(qp.txt) && p._errs.length === 0, 'questions=' + qp.n);
const r1 = await p.evaluate(() => { const ids = [...document.querySelectorAll('#s8 .qs li')].map((li) => li.id); const af = [...document.querySelectorAll('#s8 .qs li .af')].map((x) => x.closest('li').id); const m = [...document.querySelectorAll('a.q-reply')].map((a) => a.getAttribute('href')); const alts = [...new Set([...document.querySelectorAll('a.q-alt')].map((a) => a.getAttribute('href')))]; return { ids: ids.join() === Array.from({ length: 30 }, (_, i) => 'q' + (i + 1)).join(), af: af.join(), m, alt: alts.join(), txt: document.body.innerText }; });
t('questions r1: ids q1-q30, 8 answer-first badges, answer-sheet PDF + Word links (no mailto reply), 6 Nov deadline, 24–48 h proposal, scope rule', r1.ids && r1.af === 'q1,q2,q3,q5,q6,q9,q15,q18' && r1.m.length >= 2 && r1.m.every((h) => h === 'ASSET_Answer_Sheet.pdf') && r1.alt === 'ASSET_Answer_Sheet.docx' && /Please return your answers as one PDF to debanjan@prodcraft\.fyi by Friday 6 November/.test(r1.txt) && /Fill in the PDF directly, or use the Word version and save it as PDF/.test(r1.txt) && /within 24–48 hours of receiving your answers, or by 10 November if no answers arrive by 6 November/.test(r1.txt) && !/13 November|16 November/.test(r1.txt) && /Friday 6 November 2026/.test(r1.txt) && /set only by the signed proposal\. The proposal, once signed, is our contract/.test(r1.txt), JSON.stringify({ ids: r1.ids, af: r1.af, m: r1.m, alt: r1.alt }));
{ const [pdf, docx] = await Promise.all(['questions/ASSET_Answer_Sheet.pdf', 'questions/ASSET_Answer_Sheet.docx'].map((u) => fetch(base + u))); const pb = Buffer.from(await pdf.arrayBuffer()); const db = Buffer.from(await docx.arrayBuffer());
  t('answer sheet: PDF (AcroForm) and DOCX served', pdf.status === 200 && pb.subarray(0, 5).toString() === '%PDF-' && /\/AcroForm/.test(pb.toString('latin1')) && docx.status === 200 && db.subarray(0, 2).toString() === 'PK', pdf.status + ' ' + docx.status); }
t('tone + name: no plain-English framing, no bare first name, Ms Khatri / Mme Khatri used', !/plain[- ]English|easiest way|honest alternative|needs some plumbing/i.test(r1.txt) && !/Veena(?! Khatri)/.test(r1.txt) && /Ms Veena Khatri/.test(r1.txt) && /Ms Khatri’s console/.test(r1.txt));
t('questions r1: hostile-client absolutes removed (any time, instantly, lunch, 29 pages, "as your brief describes")', !/at any time|instantly|price of a lunch|29 pages|as your brief describes|No loss of Google ranking|with the same number|our hourly rate/i.test(r1.txt) && /two rounds of changes/i.test(r1.txt) && /outages at the hosting providers are outside this target/.test(r1.txt) && /Built into the site/.test(r1.txt) && /one-time code sent to their named work email, then confirm with a second step/.test(r1.txt));
const r2 = await p.evaluate(() => { const t = document.body.innerText; const j = document.querySelector('.q-cover a[href="#s8"]'); return { t, jump: !!j && /Go straight to the 30 questions/.test(j.textContent) }; });
t('questions r2: jump link, launch needs written go-ahead, one rounds rule, plan-bound support, consent default, 3-year total, firm deadline, no "contract is signed"', r2.jump && /launch always needs management’s written go-ahead/i.test(r2.t) && /two per design stage and two per content stage/.test(r2.t) && /within the two rounds of changes of the content stage/.test(r2.t) && !/one round of your corrections|written or approved|ASSET writes or approves|ideally by|the way you asked|contract is signed|signed order|everything goes with you|Every page Google knows|Statistics without a cookie banner/.test(r2.t) && /with the optional maintenance plan, support Monday to Friday/.test(r2.t) && /After these 4 weeks, support and fixes are covered by the optional maintenance plan/.test(r2.t) && /Cookie banner: only if a tracker is kept \(question 7\): a built-in consent banner/.test(r2.t) && /total core cost over three years/.test(r2.t) && /in the maintenance plan of the signed proposal/.test(r2.t) && /What this means/.test(r2.t));
{ const g = async (u) => (await (await fetch(base + u)).text()).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
  const [qt, ct, ht, pt] = await Promise.all([g('questions/'), g('console/'), g(''), g('pour-asset/')]);
  t('r3: full brief event list (Q7 + §04), conditional consent banner, GM&E rule (Q28 + console), Q17 import, "usually" within minutes, effort by role, MICE budget field',
    /button clicks, form starts and sends, errors, congress searches, congress page views, account requests and client-login clicks/.test(qt) && /Counts button clicks, form starts and sends, errors, congress searches and page views, account requests and client-login clicks/.test(qt)
    && /Only Ms Khatri and management can see the GM&(amp;)?E fare codes and their evidence; the backup editor cannot/.test(qt) && /one by one or by spreadsheet import/.test(qt)
    && /can usually be put back within minutes/.test(qt) && /project lead and the effort by role come with the proposal/.test(qt)
    && /personnes autorisées \(question 28\)/.test(ct) && !/Seul rôle à voir|que par la personne qui valide/.test(ct)
    && /Budget indicatif \(facultatif\)/.test(ht) && /services, budget indicatif\)/.test(pt)); }
await p.goto(base + 'questions/#q18', { waitUntil: 'load' }); await p.waitForTimeout(250);
const qy = await p.evaluate(() => Math.round(document.getElementById('q18').getBoundingClientRect().top));
t('questions r2: #q18 deep link lands instantly below the header (no smooth scroll)', qy > 40 && qy < 200, 'top=' + qy);
await p.goto(base + 'pour-asset/', { waitUntil: 'load' });
const pr2 = await p.evaluate(() => { const li = [...document.querySelectorAll('ol li')].map((x) => x.textContent); const iP = li.findIndex((x) => /^Notre proposition détaillée/.test(x)); const iA = li.findIndex((x) => /^Après signature de la proposition, l’audit/.test(x)); return { ok: iP >= 0 && iA > iP, t: document.body.innerText }; });
t('pitch r2: audit only after signature, no "contradictions"/"bonne équipe"/"si possible", roles bounded by Q28', pr2.ok && !/contradictions|bonne équipe|si possible avant/.test(pr2.t) && /Points relevés, à confirmer avec vous/.test(pr2.t) && /rôles : voir la question 28/.test(pr2.t));
await p.goto(base + 'console/', { waitUntil: 'load' });
const cr2 = await p.evaluate(() => ({ t: document.body.innerText, mfa: document.querySelectorAll('.role li').length && [...document.querySelectorAll('.role')].filter((r) => /Double authentification obligatoire/.test(r.textContent)).length }));
t('console r2: roles example tied to Q28, two-step for all accounts', /les rôles retenus sont fixés à la question 28/.test(cr2.t) && /Connexion en deux étapes pour tous les comptes/.test(cr2.t) && cr2.mfa >= 3);
await p.goto(base, { waitUntil: 'load' });
const nt = await p.evaluate(() => { const n = document.getElementById('d-notes'); return !!n && n.tagName === 'TEXTAREA' && /Précisions/.test(document.querySelector('label[for=d-notes]').textContent); });
t('home r2: quote form has a « Précisions » free-text box (Q22)', nt);
let links = true; const linkInfo = [];
for (const [pg, need] of [['', ['pour-asset/', 'console/', 'questions/']], ['pour-asset/', ['../', '../console/', '../questions/']], ['console/', ['../', '../pour-asset/', '../questions/']], ['questions/', ['../', '../pour-asset/', '../console/']]]) {
  await p.goto(base + pg, { waitUntil: 'load' }); const hrefs = await p.evaluate(() => [...document.querySelectorAll('a')].map((a) => a.getAttribute('href')));
  const miss = need.filter((h) => !hrefs.some((x) => x === h || x.startsWith(h + '#'))); if (miss.length) { links = false; linkInfo.push((pg || '/') + ' missing ' + miss.join()); }
}
t('cross-links: each of the 4 pages links to the 3 others', links, linkInfo.join(' | ') || 'all linked');
await p.goto(base + 'console/', { waitUntil: 'load' }); await p.waitForTimeout(300);
const con = await p.evaluate(() => [...document.querySelectorAll('.role h3')].map((h) => h.textContent));
{ const ct = await p.evaluate(() => document.body.innerText); t('console: Mme Veena Khatri first, then Mme Khatri; no bare first name', /proposée pour Mme Veena Khatri/.test(ct) && /Éditrice \(Mme Khatri\)/.test(ct) && !/Veena(?! Khatri)/.test(ct)); }
const cdash = await p.evaluate(() => ({ tiles: [...document.querySelectorAll('.stats p')].map((x) => x.textContent), pages: document.querySelectorAll('#pages tbody tr').length, details: !!document.querySelector('#congres details:not([open])'), h1: !!document.querySelector('h1'), jargon: /MFA|moindre privilège|côté serveur|navigateur|Workflow interne/.test(document.body.innerText), disabled: document.querySelectorAll('button[disabled]').length }));
await p.click('#pages [data-mock]'); await p.waitForTimeout(150); const toastC = await p.evaluate(() => { const t = document.querySelector('.mtoast'); return !!t && !t.hidden && /Maquette/.test(t.textContent); });
t('console: work-to-do tiles, Pages section, GM&E detail folded, plain French, live buttons with mock toast, H1', /à attribuer/.test(cdash.tiles[0]) && /rappel/.test(cdash.tiles[1]) && /brouillon/.test(cdash.tiles[2]) && cdash.pages >= 5 && cdash.details && cdash.h1 && !cdash.jargon && cdash.disabled === 0 && toastC, JSON.stringify({ ...cdash, toastC }));
const pubOnly = await p.evaluate(() => [...document.querySelectorAll('#congres tbody tr')].map((tr) => [tr.cells[0].textContent, tr.cells[3].textContent]));
const statuses = await p.evaluate(() => [...document.querySelectorAll('#demandes tbody .st')].map((x) => x.textContent));
await p.goto(base, { waitUntil: 'load' }); const pubIds = await p.evaluate(() => [...new Set((document.body.innerHTML.match(/CG-0\d{3}/g) || []))]);
const leak = pubOnly.filter(([id, st]) => pubIds.includes(id) && !/Publié/.test(st)).map(([id]) => id);
t('console r1: enquiry statuses use the agreed steps; no draft or pending congress appears in the public catalogue', statuses.every((x) => /^(Nouvelle|Qualifiée|Devis envoyé|Gagnée|Perdue)$/.test(x)) && leak.length === 0 && pubOnly.some(([, st]) => /Brouillon/.test(st)), JSON.stringify({ statuses, leak }));
await p.goto(base + 'console/', { waitUntil: 'load' });
t('console: five RFP roles', con.length === 5 && /Administrateur technique/.test(con[0]) && /Éditrice/.test(con[1]) && /Contributeur/.test(con[2]) && /Lecteur commercial/.test(con[3]) && /Approbateur/.test(con[4]), con.join(' | '));
await p.close();
p = await mk({ ...devices['Pixel 7'] }); await p.goto(base + 'console/', { waitUntil: 'load' }); await p.waitForTimeout(300);
const cm = await p.evaluate(() => { const w = document.querySelector('.wrap'); return { hint: getComputedStyle(document.querySelector('.hint-scroll')).display !== 'none', scroll: w.scrollWidth > w.clientWidth, ov: document.documentElement.scrollWidth - innerWidth }; });
t('console mobile: tables scroll inside their frame with a visible hint', cm.hint && cm.scroll && cm.ov <= 0, JSON.stringify(cm));
await p.close(); await b.close();
const pass = R.filter((r) => r.ok).length; console.log(`\n${pass}/${R.length} passed`);
writeFileSync(new URL('./functional.json', import.meta.url).pathname, JSON.stringify({ date: new Date().toISOString().slice(0, 10), pass, total: R.length, desktopHeight: dh, mobileHeightPixel7: mh, mobileHeight390: mh390, sizes, results: R }, null, 2));
process.exit(pass === R.length ? 0 : 1);
