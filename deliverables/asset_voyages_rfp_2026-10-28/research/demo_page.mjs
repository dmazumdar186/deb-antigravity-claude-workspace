#!/usr/bin/env node
/* demo_page.mjs — functional checks for the demos hub (/demo/), served with the real _headers CSP.
   usage: node research/serve_csp.mjs site 8794 &  node research/demo_page.mjs http://localhost:8794/
   outputs: research/demo_page.json and research/demo_screens/*.png (+ demo.pdf); exit 0 only on N/N. */
import { createRequire } from 'node:module'; import { writeFileSync, readFileSync, mkdirSync, mkdtempSync, cpSync } from 'node:fs'; import { execFileSync } from 'node:child_process'; import { tmpdir } from 'node:os';
const base = (process.argv[2] || 'http://localhost:8794/').replace(/\/?$/, '/');
const url = base + 'demo/';
const SITE = new URL('../site/', import.meta.url).pathname;
const SHOTS = new URL('./demo_screens/', import.meta.url).pathname; mkdirSync(SHOTS, { recursive: true });
process.env.PLAYWRIGHT_BROWSERS_PATH ||= '/opt/pw-browsers';
const req = createRequire(import.meta.url); let pw; for (const p of ['/opt/node-tools/node_modules/playwright', '/tmp/pwtest/node_modules/playwright', 'playwright']) { try { pw = req(p); break; } catch {} }
const { chromium } = pw;
const R = []; const t = (name, ok, info) => { R.push({ name, ok: !!ok, info }); console.log((ok ? 'ok   ' : 'FAIL ') + name + (info !== undefined ? ' — ' + info : '')); };
const URLS = {
  WP_VISITOR_URL: 'https://playground.wordpress.net/?mode=seamless&login=no&blueprint-url=https://asset-voyages-redesign.pages.dev/demo-wordpress/blueprint-visitor.json',
  WP_ADMIN_URL: 'https://playground.wordpress.net/?mode=seamless&blueprint-url=https://asset-voyages-redesign.pages.dev/demo-wordpress/blueprint-admin.json',
  CUSTOM_URL: (readFileSync(SITE + 'js/demo.js', 'utf8').match(/const CUSTOM_URL = '([^']+)'/) || [])[1],
  get CUSTOM_CONSOLE_URL() { return this.CUSTOM_URL + 'console'; },
};
const MAILTO = 'mailto:debanjan@prodcraft.fyi?subject=ASSET%20%E2%80%93%20demonstration%20slot';
const b = await chromium.launch();
const local = new URL(base).host;
async function mk(opts = {}) {
  const ctx = await b.newContext({ locale: 'en-GB', deviceScaleFactor: 1, ...opts }); const p = await ctx.newPage(); const errs = [], hosts = new Set();
  p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
  p.on('request', (r) => { const u = r.url(); if (/^https?:/.test(u)) hosts.add(new URL(u).host); });
  p._errs = errs; p._hosts = hosts; p._ctx = ctx; return p;
}
const settle = async (p) => { await p.evaluate(async () => { document.documentElement.style.scrollBehavior = 'auto'; for (let y = 0; y < document.body.scrollHeight; y += 500) { scrollTo(0, y); await new Promise((r) => setTimeout(r, 60)); } scrollTo(0, 0); }); await p.waitForTimeout(2600); };
const overflow = (p) => p.evaluate(() => { const W = document.documentElement.clientWidth; const bad = []; for (const el of document.querySelectorAll('body *')) { if (el.closest('.mini__in, .vh, svg, [hidden]')) continue; const r = el.getBoundingClientRect(); if (r.width && (r.right > W + 1 || r.left < -1)) bad.push((el.className || el.tagName) + ':' + Math.round(r.right)); } return { sw: document.documentElement.scrollWidth, W, bad: bad.slice(0, 5) }; });

// ================= desktop 1440 =================
let p = await mk({ viewport: { width: 1440, height: 900 } });
await p.goto(url, { waitUntil: 'load' }); await p.waitForTimeout(600);
const fold = await p.evaluate(() => { const h = document.querySelector('.hero h1').getBoundingClientRect(), a = document.querySelector('.hero .btn').getBoundingClientRect(); return { h1: h.bottom, btn: a.bottom }; });
t('desktop: headline, sentence and primary action above the fold at 1440x900', fold.btn < 900, JSON.stringify(fold));
await settle(p);
t('desktop: 0 console errors (served with the real _headers CSP)', p._errs.length === 0, p._errs.slice(0, 3).join(' | '));
t('desktop: 0 third-party requests on load', [...p._hosts].every((h) => h === local), [...p._hosts].join(','));
const ov1 = await overflow(p); t('desktop 1440: no horizontal overflow', ov1.sw <= ov1.W && !ov1.bad.length, JSON.stringify(ov1));
const secOv = (p) => p.evaluate(() => { const W = document.documentElement.clientWidth; const bad = []; for (const el of document.querySelectorAll('#group, #group *')) { if (el.closest('.vh')) continue; const r = el.getBoundingClientRect(); if (r.width && (r.right > W + 1 || r.left < -1 || el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).overflowX !== 'visible')) bad.push((el.className || el.tagName) + ':' + Math.round(r.right)); } return { W, bad: bad.slice(0, 5) }; });
const gov1 = await secOv(p); t('desktop 1440: group section has nothing overflowing', !gov1.bad.length, JSON.stringify(gov1));
const anchors = await p.evaluate(() => [...document.querySelectorAll('a[href^="#"]')].map((a) => a.getAttribute('href')).filter((h) => h.length > 1 && !document.getElementById(h.slice(1))));
t('every in-page anchor resolves to an element', anchors.length === 0, anchors.join(','));
const navIds = await p.evaluate(() => [...document.querySelectorAll('[data-mini] a')].map((a) => a.getAttribute('href')));
t('sticky strip lists the nine sections in page order, group link after "What works" (recordings link hidden until a recording exists)', navIds.join() === '#options,#try,#recordings,#compare,#group,#built,#codes,#plan,#slot' && await p.evaluate((ids) => { const ys = ids.map((h) => document.querySelector(h)).filter((e) => !e.hidden).map((e) => e.getBoundingClientRect().top); return ys.every((y, i) => i === 0 || y > ys[i - 1]); }, navIds), navIds.join());
// relative page links resolve (media files are optional and checked separately)
const rel = await p.evaluate(() => [...new Set([...document.querySelectorAll('a[href]')].map((a) => a.getAttribute('href')).filter((h) => !/^(#|https?:|mailto:)/.test(h) && !/^media\//.test(h)))]);
const relBad = []; for (const h of rel) { const r = await fetch(new URL(h, url)); if (r.status !== 200) relBad.push(h + ':' + r.status); }
t('relative links to the concept pages resolve (200)', relBad.length === 0 && rel.length >= 4, rel.join(',') + (relBad.length ? ' BAD ' + relBad.join(',') : ''));
// « Le lien de groupe »: the unnumbered extra section
const grp = await p.evaluate(() => { const s = document.getElementById('group'); if (!s) return null; const h2s = [...document.querySelectorAll('main h2')]; const pos = (id) => h2s.indexOf(document.querySelector('#' + id + ' h2'));
  return { text: s.innerText.replace(/\s+/g, ' '), numbered: !!s.querySelector('h2 .n'), title: s.querySelector('h2').textContent, order: pos('compare') < pos('group') && pos('group') < pos('built'), nums: [...document.querySelectorAll('main h2 .n')].map((n) => n.textContent).join(),
    links: [...s.querySelectorAll('a[href]')].map((a) => [a.dataset.demoB || '', a.getAttribute('href'), a.target, a.rel]), steps: s.querySelectorAll('.extra__how li').length, tries: s.querySelectorAll('.extra__try .steps li').length }; });
t('group section: present after the table and before "How each one is built", unnumbered, numbering 1 to 7 intact', grp && !grp.numbered && /One more idea: a link for group trips/.test(grp.title) && grp.order && grp.nums === '1,2,3,4,5,6,7', grp && JSON.stringify({ title: grp.title, order: grp.order, nums: grp.nums }));
const need = ['répondus / attendus', 'Exporter pour cotation (CSV)', 'Groupe', 'Lien de groupe', 'equipe', 'demo-asset', 'never shows the other travellers, codes or fares', 'Working in Option B’s demonstration', 'Suggestion only. It is not included in the proposal to come, and the requirements and budget you communicated stay unchanged.', 'email confirmation step', 'It exists in Option B’s demo only. If ASSET wants it, in either option, it would be scoped and quoted separately, after the proposal, and built only on your written agreement.'];
const miss = grp ? need.filter((n) => !grp.text.includes(n)) : need;
t('group section: problem, 3 steps, numbered try-it steps, what the traveller never sees, status and honest limits', grp && grp.steps === 3 && grp.tries >= 3 && !miss.length, 'missing: ' + miss.join(' | '));
const banned = grp ? (grp.text.match(/airline|Air France|KLM|GM&E|threshold|seuil|carrier|compagnie/gi) || []) : ['no section'];
const words = grp ? grp.text.split(' ').length : 0;
t('group section: no airline rules or GM&E thresholds mentioned; under 320 words in total', !banned.length && words < 320, `words=${words}` + (banned.length ? ' BANNED ' + banned.join(',') : ''));
const gl = grp ? grp.links : [];
t('group section: every link is an Option B deep link set from CUSTOM_URL, opening in a new tab', gl.length >= 1 && gl.every(([d, h, tg, rl]) => d && h === URLS.CUSTOM_URL + d && tg === '_blank' && /noopener/.test(rl)), JSON.stringify(gl));
const glBad = []; for (const [d] of gl) { try { const r = await fetch(URLS.CUSTOM_URL + d, { redirect: 'manual' }); const loc = r.headers.get('location') || ''; if (!(r.status === 200 || (r.status === 303 && loc.includes('/console/connexion?next=' + encodeURIComponent('/' + d))))) glBad.push(d + ':' + r.status + ' ' + loc); } catch (e) { glBad.push(d + ':' + e.message); } }
t('group section: its links resolve on the live demo (sign-in page, then back to the enquiry)', gl.length && !glBad.length, glBad.join(',') || gl.map(([d]) => d).join(','));
// constants
const js = readFileSync(SITE + 'js/demo.js', 'utf8'); const html = readFileSync(SITE + 'demo/index.html', 'utf8');
const constOk = js.includes(`const WP_VISITOR_URL = '${URLS.WP_VISITOR_URL}'`) && js.includes(`const WP_ADMIN_URL = '${URLS.WP_ADMIN_URL}'`) && js.includes(`const CUSTOM_URL = '${URLS.CUSTOM_URL}'`) && js.includes("const CUSTOM_CONSOLE_URL = CUSTOM_URL + 'console'");
const live = await p.evaluate(() => [...document.querySelectorAll('a[data-demo]')].map((a) => [a.dataset.demo, a.getAttribute('href'), a.target, a.rel]));
const liveOk = live.length >= 8 && live.every(([k, h, tg, rl]) => h === URLS[k] && tg === '_blank' && /noopener/.test(rl));
const staticOk = Object.values(URLS).every((u) => html.includes(`href="${u.replace(/&/g, '&amp;')}"`));
t('demo constants: four URLs defined once in demo.js, applied to every demo link, same hrefs in the HTML for no-JS', constOk && liveOk && staticOk, `links=${live.length}`);
const cards = await p.evaluate(() => [...document.querySelectorAll('.pass')].map((c) => c.querySelectorAll('a.btn').length));
t('two option cards, two buttons each', cards.join() === '2,2', cards.join());
const logins = await p.evaluate(() => document.querySelector('.logins').innerText);
const boots = await p.evaluate(() => [...document.querySelectorAll('.pass:not(.pass--b) .pass__stub a.btn')].map((a) => { const n = a.nextElementSibling; return n && n.matches('.pass__boot') ? n.textContent : ''; }));
t('logins: direction / equipe / contributeur, password demo-asset; private + 24 h line; Playground start time and reload tip next to each Option A button', /direction/.test(logins) && /equipe/.test(logins) && /contributeur/.test(logins) && /demo-asset/.test(logins) && /In Option B, each person's trial is not shown to other visitors and is cleared after 24 hours without use\. Option A starts fresh each time you open it\./.test(logins) && boots.length === 2 && boots.every((s) => /Takes about 15 to 30 seconds to start\./.test(s) && /reload the page/.test(s)), JSON.stringify(boots));
// C10 + B6: task 5 wording and glossary labels quoted exactly (29_Glossary_Labels.md)
const body = await p.evaluate(() => document.body.textContent.replace(/ /g, ' '));
const gloss = ['« Codes GM&E › Codes »', '« Afficher le code »', '« Approuver pour 24 h »', '« Journal d’accès GM&E »', '« Exporter en CSV »', '« Journal des notifications »', '« Demander un devis vol »', '« Envoyer ma demande »', '« Espace équipe »', 'that click is needed'];
const glMiss = gloss.filter((g) => !body.includes(g));
const stale = (body.match(/five minutes|the code is shown|Accès GM&E|Révéler|Approuver \(24 h\)|Journal GM&E/g) || []);
t('hub quotes the glossary labels exactly; task 5 says the « Afficher le code » click is needed; no stale wording', !glMiss.length && !stale.length, 'missing: ' + glMiss.join(' | ') + (stale.length ? ' STALE ' + stale.join(',') : ''));
// mailto
const mail = await p.evaluate(() => ({ main: document.querySelector('[data-mailto]').getAttribute('href'), slots: [...document.querySelectorAll('.time')].map((a) => a.getAttribute('href')), labels: [...document.querySelectorAll('.days li')].map((li) => li.innerText.replace(/\s+/g, ' ').trim()) }));
const subj = (h) => decodeURIComponent((h.match(/subject=([^&]+)/) || [])[1] || '');
t('mailto: main button exact; every slot mails debanjan@prodcraft.fyi with subject "ASSET – demonstration slot"', mail.main === MAILTO && mail.slots.length === 3 && mail.slots.every((h) => h.startsWith('mailto:debanjan@prodcraft.fyi?') && subj(h) === 'ASSET – demonstration slot'), mail.labels.join(' / '));
t('slots: Thu 12 (10:00), Mon 16 (14:30), Tue 17 (10:00) — no conflict with the operator calendar', mail.labels.join('|') === 'Thursday 12 November 10:00|Monday 16 November 14:30|Tuesday 17 November 10:00', mail.labels.join('|'));
// table
const tbl = await p.evaluate(() => [...document.querySelectorAll('.cmp tbody tr')].map((tr) => [tr.querySelector('th').innerText, ...[...tr.querySelectorAll('td .st')].map((s) => s.innerText)]));
t('comparison: 11 rows, every cell carries one of the statuses; English is « Option, quoted separately » in A and B', tbl.length === 11 && tbl.every((r) => r.length === 3 && r.slice(1).every((s) => s === 'Works in the demo' || s === 'Built during the project' || s === 'Option, quoted separately')) && tbl.filter((r) => r[1] === 'Option, quoted separately' || r[2] === 'Option, quoted separately').map((r) => r.join('|')).join() === 'English version|Option, quoted separately|Option, quoted separately', tbl.length + ' rows');
// signature: the access path draws in
const flow = await p.evaluate(() => { const f = document.querySelector('[data-flow]'); const path = f.querySelector('.flow__wide .flow__path'); return { armed: f.hasAttribute('data-armed'), in: f.classList.contains('is-in'), off: getComputedStyle(path).strokeDashoffset, op: getComputedStyle(f.querySelector('.flow__wide [data-i="5"]')).opacity }; });
t('signature: GM&E access path armed below the fold and fully drawn after scrolling to it', flow.armed && flow.in && parseFloat(flow.off) === 0 && flow.op === '1', JSON.stringify(flow));
const svgA11y = await p.evaluate(() => { const f = document.querySelector('.flow'); const alt = document.getElementById(f.getAttribute('aria-labelledby') || ''); const svgs = [...f.querySelectorAll('svg')]; return svgs.length === 2 && svgs.every((s) => s.getAttribute('aria-hidden') === 'true' && !s.querySelector('title, desc')) && alt && f.contains(alt) && f.querySelectorAll('.vh').length === 1 && alt.textContent.includes('1. Team member sees the code hidden. 2. Asks for access and gives a reason. 3. Direction approves for 24 h, or refuses. 4. Code shown to that person only. 5. Access recorded: who, when, which code, every time.'); });
t('diagram: both drawings hidden from assistive tech, one text alternative for the figure', svgA11y);
// anchor not covered by the sticky strip
for (const id of ['#compare', '#slot']) {
  await p.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; scrollTo(0, 0); });
  await p.click(`[data-mini] a[href="${id}"]`); await p.waitForTimeout(400);
  const g = await p.evaluate((id) => ({ top: document.querySelector(id + ' h2').getBoundingClientRect().top, strip: document.querySelector('[data-mini]').getBoundingClientRect().bottom, cur: document.querySelector('[data-mini] a[aria-current]')?.getAttribute('href') }), id);
  t(`desktop: ${id} heading lands below the sticky strip, strip marks it`, g.top >= g.strip && g.top < 260 && g.cur === id, JSON.stringify(g));
}
// recordings: default fallback
const man = JSON.parse(readFileSync(SITE + 'demo/media/manifest.json', 'utf8')); const anyRec = Object.values(man).some(Boolean);
const rec0 = await p.evaluate(() => ({ fallback: /will appear here|Meanwhile/.test(document.getElementById('recordings').textContent), sec: document.querySelector('#recordings').hidden && getComputedStyle(document.querySelector('#recordings')).display === 'none', nav: getComputedStyle(document.querySelector('[data-rec-nav]')).display === 'none', videos: [...document.querySelectorAll('[data-rec]')].filter((f) => f.querySelector('video')).map((f) => f.dataset.rec) }));
const want = Object.keys(man).filter((k) => man[k]);
t('recordings: follow the real manifest (all false: section and strip link hidden, no video; announced files: those players only)', anyRec ? (!rec0.sec && !rec0.nav && rec0.videos.join() === want.join() && !rec0.fallback) : (rec0.sec && rec0.nav && !rec0.videos.length), JSON.stringify({ man, rec0 }));
// contrast of every visible text node against its painted background
const contrast = await p.evaluate(() => {
  const parse = (c) => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const v = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return { r: v[0], g: v[1], b: v[2], a: v[3] === undefined ? 1 : v[3] }; };
  const lum = ({ r, g, b }) => { const f = (x) => { x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const bgOf = (el) => { for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor); if (c && c.a > 0.5) return c; } return { r: 242, g: 238, b: 229, a: 1 }; };
  const bad = []; let n = 0;
  for (const el of document.querySelectorAll('body *:not(svg *)')) {
    if (![...el.childNodes].some((x) => x.nodeType === 3 && x.textContent.trim())) continue;
    const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || el.closest('.vh,[hidden]') || !el.getClientRects().length) continue;
    const fg = parse(cs.color), bg = bgOf(el); const mix = { r: fg.r * fg.a + bg.r * (1 - fg.a), g: fg.g * fg.a + bg.g * (1 - fg.a), b: fg.b * fg.a + bg.b * (1 - fg.a) };
    const L1 = lum(mix), L2 = lum(bg); const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const big = parseFloat(cs.fontSize) >= 24 || (parseFloat(cs.fontSize) >= 18.66 && +cs.fontWeight >= 700); n++;
    if (ratio < (big ? 3 : 4.5)) bad.push(`${el.className || el.tagName}:${ratio.toFixed(2)}`);
  }
  return { n, bad: bad.slice(0, 6) };
});
t('WCAG AA contrast on every visible text element', contrast.bad.length === 0, `checked ${contrast.n}` + (contrast.bad.length ? ' BAD ' + contrast.bad.join(',') : ''));
await settle(p);
await p.screenshot({ path: SHOTS + 'demo-1440.png', fullPage: true });
// print
await p.emulateMedia({ media: 'print' });
const pr = await p.evaluate(() => ({ mini: getComputedStyle(document.querySelector('[data-mini]')).display, optsB: [...document.querySelectorAll('.task__opt--b')].every((o) => getComputedStyle(o).display !== 'none'), wide: getComputedStyle(document.querySelector('.flow__wide')).display }));
await p.pdf({ path: SHOTS + 'demo.pdf', format: 'A4', printBackground: true });
t('print: strip hidden, both options of every task printed, wide diagram, PDF written', pr.mini === 'none' && pr.optsB && pr.wide === 'block', JSON.stringify(pr));
await p._ctx.close();

// ================= phone 390 =================
p = await mk({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
await p.goto(url, { waitUntil: 'load' }); await settle(p);
t('390: 0 console errors', p._errs.length === 0, p._errs.slice(0, 3).join(' | '));
const ov2 = await overflow(p); t('390: no horizontal overflow', ov2.sw <= ov2.W && !ov2.bad.length, JSON.stringify(ov2));
const gov2 = await secOv(p); t('390: group section has nothing overflowing', !gov2.bad.length, JSON.stringify(gov2));
const small = await p.evaluate(() => { const bad = []; for (const el of document.querySelectorAll('body *:not(svg *)')) { if (![...el.childNodes].some((x) => x.nodeType === 3 && x.textContent.trim())) continue; if (el.closest('.vh,[hidden]') || !el.getClientRects().length) continue; const fs = parseFloat(getComputedStyle(el).fontSize); if (fs < 16) bad.push(el.className || el.tagName); } const svgT = [...document.querySelectorAll('.flow__tall text')].map((x) => x.getBoundingClientRect().height); return { bad: [...new Set(bad)].slice(0, 6), svgMin: Math.min(...svgT) }; });
t('390: all text 16 px or more (diagram text included, as rendered)', small.bad.length === 0 && small.svgMin >= 15, JSON.stringify(small));
const taps = await p.evaluate(() => [...document.querySelectorAll('.btn, .time, [data-mini] a, .switch__b, .top__back, .link-quiet, .skip')].filter((e) => e.getClientRects().length && !e.classList.contains('skip')).map((e) => { const r = e.getBoundingClientRect(); return [e.textContent.trim().slice(0, 20), Math.round(r.height), Math.round(r.width)]; }).filter(([, h, w]) => h < 44 || w < 44));
t('390: every button, slot, strip link and switch is at least 44 px', taps.length === 0, JSON.stringify(taps));
const sw = await p.evaluate(() => ({ shown: !document.querySelector('[data-switch]').hidden, a: [...document.querySelectorAll('.task__opt--a')].every((o) => getComputedStyle(o).display !== 'none'), b: [...document.querySelectorAll('.task__opt--b')].every((o) => getComputedStyle(o).display === 'none') }));
await p.click('[data-switch] [data-show="b"]'); await p.waitForTimeout(150);
const sw2 = await p.evaluate(() => ({ a: [...document.querySelectorAll('.task__opt--a')].every((o) => getComputedStyle(o).display === 'none'), b: [...document.querySelectorAll('.task__opt--b')].every((o) => getComputedStyle(o).display !== 'none'), pressed: document.querySelector('[data-show="b"]').getAttribute('aria-pressed') }));
t('390: A/B switch shows one option at a time, aria-pressed follows', sw.shown && sw.a && sw.b && sw2.a && sw2.b && sw2.pressed === 'true', JSON.stringify({ sw, sw2 }));
await p.click('[data-switch] [data-show="a"]');
await p.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; scrollTo(0, 0); });
await p.click('[data-mini] a[href="#plan"]'); await p.waitForTimeout(500);
const g390 = await p.evaluate(() => ({ top: document.querySelector('#plan h2').getBoundingClientRect().top, strip: document.querySelector('[data-mini]').getBoundingClientRect().bottom }));
t('390: #plan heading lands below the sticky strip', g390.top >= g390.strip, JSON.stringify(g390));
await p.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; scrollTo(0, 0); });
await p.click('[data-mini] a[href="#group"]'); await p.waitForTimeout(500);
const gg = await p.evaluate(() => ({ top: document.querySelector('#group h2').getBoundingClientRect().top, strip: document.querySelector('[data-mini]').getBoundingClientRect().bottom }));
t('390: the strip link to #group scrolls its heading below the sticky strip', gg.top >= gg.strip, JSON.stringify(gg));
const tall = await p.evaluate(() => ({ wide: getComputedStyle(document.querySelector('.flow__wide')).display, tall: getComputedStyle(document.querySelector('.flow__tall')).display }));
t('390: the diagram switches to its vertical drawing', tall.wide === 'none' && tall.tall === 'block', JSON.stringify(tall));
await p.evaluate(() => scrollTo(0, 0)); await p.waitForTimeout(200);
await p.screenshot({ path: SHOTS + 'demo-390.png', fullPage: true });
await p._ctx.close();

// ================= recordings: ready but missing, and ready and present =================
p = await mk({ viewport: { width: 1280, height: 800 } });
await p.route('**/demo/media/manifest.json', (r) => r.fulfill({ contentType: 'application/json', body: '{"wp-walkthrough":true,"custom-walkthrough":true}' }));
const hero = readFileSync(SITE + 'assets/hero.mp4');
await p.route('**/demo/media/custom-walkthrough.mp4', (r) => r.fulfill({ contentType: 'video/mp4', body: hero }));
// the real wp-walkthrough.mp4 now exists in demo/media: force it missing so the fallback path is still tested
await p.route('**/demo/media/wp-walkthrough.mp4', (r) => r.fulfill({ status: 404, contentType: 'text/plain', body: 'not found' }));
await p.goto(url, { waitUntil: 'load' }); await p.waitForTimeout(2500);
const rec1s = await p.evaluate(() => ({ sec: !document.querySelector('#recordings').hidden, nav: !document.querySelector('[data-rec-nav]').hidden }));
const rec1 = await p.evaluate(() => Object.fromEntries([...document.querySelectorAll('[data-rec]')].map((f) => [f.dataset.rec, { v: !!f.querySelector('video'), ready: f.querySelector('video')?.readyState || 0, empty: !f.querySelector('[data-rec-empty]').hidden, msg: f.querySelector('[data-rec-msg]').textContent }])));
t('recordings: once announced, section and strip link appear; a missing file falls back to the message; a present file plays', rec1s.sec && rec1s.nav && rec1['wp-walkthrough'].empty && !rec1['wp-walkthrough'].v && /could not be loaded/.test(rec1['wp-walkthrough'].msg) && rec1['custom-walkthrough'].v && rec1['custom-walkthrough'].ready >= 1 && !rec1['custom-walkthrough'].empty, JSON.stringify(rec1));
await p._ctx.close();

// ================= reduced motion =================
p = await mk({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
await p.goto(url, { waitUntil: 'load' }); await p.waitForTimeout(400);
const rm = await p.evaluate(() => ({ armed: document.querySelector('[data-flow]').hasAttribute('data-armed'), sb: getComputedStyle(document.documentElement).scrollBehavior, off: getComputedStyle(document.querySelector('.flow__wide .flow__path')).strokeDashoffset }));
t('reduced motion: no reveal (diagram drawn from the start), no smooth scroll', !rm.armed && rm.sb === 'auto' && (rm.off === '0px' || rm.off === '0'), JSON.stringify(rm));
await p._ctx.close();

// ================= JavaScript off =================
for (const vp of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
  p = await mk({ viewport: vp, javaScriptEnabled: false });
  await p.goto(url, { waitUntil: 'load' }); await p.waitForTimeout(300);
  const nojs = await p.evaluate((want) => ({ recOk: (() => { const s = document.getElementById('recordings'); const shown = getComputedStyle(s).display !== 'none'; const files = [...s.querySelectorAll('figure [data-rec-file]')].filter((a) => a.getClientRects().length).map((a) => a.getAttribute('href')); const noFallback = !/will appear here|Meanwhile|could not be loaded/.test(s.textContent); return want.length ? shown && noFallback && files.join() === want.map((k) => 'media/' + k + '.mp4').join() : !shown; })(), sections: ['options', 'try', 'compare', 'group', 'built', 'codes', 'plan', 'slot'].every((id) => { const s = document.getElementById(id); return s && s.getBoundingClientRect().height > 100; }), opts: [...document.querySelectorAll('.task__opt')].filter((o) => getComputedStyle(o).display !== 'none').length, sw: document.querySelector('[data-switch]').hidden, path: getComputedStyle(document.querySelector('.flow__path')).strokeDasharray, links: [...document.querySelectorAll('a[data-demo]')].every((a) => /^https:/.test(a.href)), rows: document.querySelectorAll('.cmp tbody tr').length, sw0: document.documentElement.scrollWidth <= innerWidth }), want);
  t(`JS off ${vp.width}: every section, both options of all 5 tasks, demo links, diagram, table, recordings as file links per the manifest (hidden when none) with no fallback text; no overflow`, nojs.sections && nojs.opts === 10 && nojs.sw && nojs.path === 'none' && nojs.recOk && nojs.links && nojs.rows === 11 && nojs.sw0, JSON.stringify(nojs));
  await p._ctx.close();
}

// ================= the discreet links on the other pages =================
p = await mk({ viewport: { width: 390, height: 844 }, isMobile: true });
for (const [path, sel] of [['', '.ftr a[href="demo/"]'], ['pour-asset/', '.doc a[href="../demo/"]'], ['questions/', '.q-foot a[href="../demo/"]']]) {
  await p.goto(base + path, { waitUntil: 'load' }); await p.waitForTimeout(400);
  const r = await p.evaluate((sel) => ({ link: !!document.querySelector(sel), sw: document.documentElement.scrollWidth, W: document.documentElement.clientWidth, hdr: (() => { const n = document.querySelector('.dh__nav'); if (!n) return true; const r = n.getBoundingClientRect(); return r.right <= document.documentElement.clientWidth + 1; })() }), sel);
  t(`/${path}: link to /demo/ present, no overflow at 390`, r.link && r.sw <= r.W && r.hdr, JSON.stringify(r));
}
await p._ctx.close();

// ================= eye-review regressions (round 1) =================
const diagramCheck = (p, sel) => p.evaluate((sel) => {
  const svg = document.querySelector(sel);
  const parse = (c) => { const m = c.match(/rgba?\(([^)]+)\)/); const v = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return { r: v[0], g: v[1], b: v[2], a: v[3] === undefined ? 1 : v[3] }; };
  const lum = ({ r, g, b }) => { const f = (x) => { x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const card = parse(getComputedStyle(svg.closest('.flow')).backgroundColor);
  const low = [], clip = [];
  for (const tx of svg.querySelectorAll('text')) {
    const rect = tx.parentElement.matches('g') ? tx.parentElement.querySelector('rect') : null;
    const bg = rect ? parse(getComputedStyle(rect).fill) : card; const fg = parse(getComputedStyle(tx).fill);
    const mix = { r: fg.r * fg.a + bg.r * (1 - fg.a), g: fg.g * fg.a + bg.g * (1 - fg.a), b: fg.b * fg.a + bg.b * (1 - fg.a) };
    const L1 = lum(mix), L2 = lum(bg); const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    if (ratio < 4.5) low.push(tx.textContent + ':' + ratio.toFixed(2));
    if (rect) { const a = tx.getBoundingClientRect(), r = rect.getBoundingClientRect(); const pad = 6 * r.width / rect.width.baseVal.value; if (a.left < r.left + pad || a.right > r.right - pad || a.top < r.top + 2 || a.bottom > r.bottom - pad) clip.push(tx.textContent); }
  }
  const y = (q) => svg.querySelector(q).getBBox();
  const v = y('.flow__vault rect'), w = y('.flow__wall'), pb = y('.flow__pub rect');
  return { low, clip, order: v.y + v.height < w.y && w.y < pb.y };
}, sel);
for (const w of [320, 390, 1000, 1001, 1440, 1920]) {
  p = await mk({ viewport: { width: w, height: 900 } });
  await p.goto(url, { waitUntil: 'load' }); await settle(p);
  const sel = w > 1000 ? '.flow__wide' : '.flow__tall';
  const d = await diagramCheck(p, sel);
  t(`diagram ${w}: every label ≥ 4.5:1 on its box, no text touching or crossing a box edge, protected store above the public line`, !d.low.length && !d.clip.length && d.order, JSON.stringify(d));
  if (w === 1440 || w === 390) {
    const sw = await p.evaluate(() => getComputedStyle(document.querySelector('[data-switch]')).display);
    t(`A/B switch ${w === 1440 ? 'hidden at desktop (both columns already show)' : 'shown on the phone'}`, w === 1440 ? sw === 'none' : sw !== 'none', sw);
  }
  if (w === 1440 || w === 390) {
    const g = await p.evaluate(() => { const L = (s) => Math.round(document.querySelector(s).getBoundingClientRect().left); const lab = [...document.querySelectorAll('.gantt__weeks span')].map((e) => getComputedStyle(e).display === 'none' ? null : Math.round(e.getBoundingClientRect().left)); const bars = [...document.querySelectorAll('.g')].map((g) => Math.round(g.querySelector('.g__bar').getBoundingClientRect().left)); const track = document.querySelector('.g__track').getBoundingClientRect(); return { lab, bars, track: Math.round(track.left), col: track.width / 17 }; });
    const near = (a, b) => a === null || Math.abs(a - b) <= 1;
    t(`timeline ${w}: bars start on their week tick (week 1, 5, 10, after launch)`, near(g.lab[0], g.bars[0]) && g.bars[0] === g.track && near(g.lab[1], g.bars[2]) && near(g.lab[2], g.bars[3]) && near(g.lab[3], g.bars[6]) && Math.abs(g.bars[1] - (g.track + g.col)) <= 1, JSON.stringify(g));
  }
  if (w === 390 || w === 320) {
    const s0 = await p.evaluate(() => { const s = document.querySelector('.mini__in'); return { left: s.scrollLeft, more: s.dataset.more || '' }; });
    t(`strip ${w}: starts at its first link after a full scroll down and back, with a right-edge fade`, s0.left === 0 && s0.more === 'right', JSON.stringify(s0));
  }
  await p._ctx.close();
}
p = await mk({ viewport: { width: 390, height: 844 }, isMobile: true });
await p.goto(url, { waitUntil: 'load' }); await p.waitForTimeout(300);
const fresh = await p.evaluate(() => document.querySelector('.mini__in').scrollLeft);
const guil = await p.evaluate(() => { const t = document.body.textContent; const bad = []; for (let i = 0; i < t.length; i++) { if (t[i] === '«' && t[i + 1] !== ' ') bad.push(t.slice(i, i + 20)); if (t[i] === '»' && t[i - 1] !== ' ') bad.push(t.slice(i - 20, i + 1)); } return { n: (t.match(/«/g) || []).length, bad }; });
const foot = await p.evaluate(() => /Unlisted page|hidden from search engines/i.test(document.querySelector('footer').innerText));
await p._ctx.close();
t('strip 390: fresh load starts at scrollLeft 0', fresh === 0, String(fresh));
t('French quotes: every « and » bound to its word by a no-break space (no line starts with » or ends with «)', guil.n >= 6 && !guil.bad.length, JSON.stringify(guil));
t('footer: the "Unlisted page" note is gone', !foot);
{ const T = mkdtempSync(tmpdir() + '/demo-urls-'); cpSync(SITE + 'js', T + '/js', { recursive: true }); cpSync(SITE + 'demo', T + '/demo', { recursive: true });
  const out = execFileSync('bash', [new URL('./set_demo_urls.sh', import.meta.url).pathname, 'https://asset-voyages-demo.example.workers.dev', T], { encoding: 'utf8' });
  const j = readFileSync(T + '/js/demo.js', 'utf8'), h = readFileSync(T + '/demo/index.html', 'utf8');
  const again = execFileSync('bash', [new URL('./set_demo_urls.sh', import.meta.url).pathname, 'https://asset-voyages-demo.example.workers.dev/', T], { encoding: 'utf8' });
  let refused = false; try { execFileSync('bash', [new URL('./set_demo_urls.sh', import.meta.url).pathname, 'javascript:alert(1)', T], { stdio: 'pipe' }); } catch { refused = true; }
  t('set_demo_urls.sh: one command updates demo.js and every Option B href, is idempotent, refuses a non-https value', j.includes("const CUSTOM_URL = 'https://asset-voyages-demo.example.workers.dev/'") && (h.match(/href="https:\/\/asset-voyages-demo\.example\.workers\.dev\/(console)?"/g) || []).length === 5 && h.includes('data-demo-b="console/demandes/1" href="https://asset-voyages-demo.example.workers.dev/console/demandes/1"') && !/REPLACE/.test(h) && /already set/.test(again) && refused, out.trim()); }

await b.close();
const pass = R.filter((r) => r.ok).length;
writeFileSync(new URL('./demo_page.json', import.meta.url), JSON.stringify({ url, date: new Date().toISOString(), pass, total: R.length, results: R }, null, 1));
console.log(`\n${pass}/${R.length} passed · screens: ${SHOTS}demo-1440.png, ${SHOTS}demo-390.png`);
process.exit(pass === R.length ? 0 : 1);
