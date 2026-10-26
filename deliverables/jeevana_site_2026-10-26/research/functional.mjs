#!/usr/bin/env node
/* functional.mjs — brief_v3 §5 assertions, real DOM / video / pixel measurements only. Never loosen a threshold.
   usage: node research/serve_csp.mjs site 8794 &  node research/functional.mjs http://localhost:8794/
   output: research/functional.json {pass, total, results:[{name, ok, detail}], measurements, versions} ; exit 1 on any failure. */
import { createRequire } from 'node:module'; import { readFileSync, writeFileSync, statSync, mkdirSync } from 'node:fs'; import { execFileSync } from 'node:child_process';
process.env.PLAYWRIGHT_BROWSERS_PATH ||= '/opt/pw-browsers';
const req = createRequire('/opt/node22/lib/node_modules/'); const { chromium, devices } = req('playwright');
const base = (process.argv[2] || 'http://localhost:8794/').replace(/\/?$/, '/');
const R = new URL('./', import.meta.url).pathname, SITE = R + '../site/';
const hero = JSON.parse(readFileSync(SITE + 'assets/film/hero.json', 'utf8'));
const boxes = JSON.parse(readFileSync(R + 'film/figure_boxes.json', 'utf8'));
const fx = JSON.parse(readFileSync(R + 'content_fixture.json', 'utf8'));
const results = []; const M = {};
const T = (name, ok, detail = '') => { results.push({ name, ok: !!ok, detail }); console.log((ok ? 'ok   ' : 'FAIL ') + name + (detail ? ' — ' + (typeof detail === 'string' ? detail : JSON.stringify(detail)) : '')); };
// independent re-implementation of the documented mapping (brief §3/§2: 13 units, 15/70/15, stand-in scaled to 12 keyframes)
const K = hero.keyframes_s.length >= 12 ? hero.keyframes_s.slice(0, 12) : Array.from({ length: 12 }, (_, i) => hero.seconds * i / 11);
const posToTime = (x) => { x = Math.min(11, Math.max(0, x)); const s = Math.min(Math.floor(x), 10), f = x - s, g = Math.min(1, Math.max(0, (f - 0.15) / 0.7)); return K[s] + g * (K[s + 1] - K[s]); };
const VP = { 'iphone-se': [375, 667, 1], 'galaxy-s8': [360, 740, 1], 'iphone-13': [390, 844, 1], 'pixel-7': [412, 915, 1], 'iphone-15-pro-max': [430, 932, 1], 'phone-landscape': [844, 390, 1], 'small-tablet': [600, 960, 1], 'ipad-portrait': [820, 1180, 0], 'ipad-landscape': [1180, 820, 0], 'ipad-pro-portrait': [1024, 1366, 0], 'ipad-pro-landscape': [1366, 1024, 0], 'laptop-1280': [1280, 800, 0], 'laptop-1440': [1440, 900, 0], 'laptop-1536': [1536, 864, 0], 'desktop-1080p': [1920, 1080, 0], 'desktop-1440p': [2560, 1440, 0], 'desktop-4k': [3840, 2160, 0], 'tv-portrait': [1080, 1920, 0], 'pixel-7-device': 'Pixel 7' };
const spec = (s) => typeof s === 'string' ? { ...devices[s] } : { viewport: { width: s[0], height: s[1] }, isMobile: !!s[2], hasTouch: !!s[2], deviceScaleFactor: 1 };
const b = await chromium.launch();
async function page(opts, { seen = true, lang = 'en', api = 200 } = {}) {
  const ctx = await b.newContext(opts); const p = await ctx.newPage(); p.errs = []; p.ext = new Set(); p.posts = [];
  p.on('pageerror', (e) => p.errs.push(e.message)); p.on('console', (m) => { if (m.type() === 'error') p.errs.push(m.text()); });
  p.on('request', (r) => { const u = new URL(r.url()); if (!/^localhost/.test(u.host) && u.protocol.startsWith('http')) p.ext.add(u.host + u.pathname); });
  await p.route('**/api/**', (r) => { p.posts.push([r.request().url(), r.request().postData()]); return r.fulfill({ status: api, contentType: 'application/json', body: api === 200 ? '{"ok":true}' : '{"ok":false}' }); });
  await p.route('https://static.cloudflareinsights.com/**', (r) => r.fulfill({ status: 200, contentType: 'text/javascript', body: '' }));
  await p.addInitScript(([s, l]) => { if (s) localStorage.setItem('jv-news-seen', '1'); localStorage.setItem('jv-lang', l); }, [seen, lang]);
  p._ctx = ctx; return p;
}
const scrollP = (p, pp) => p.evaluate((pp) => { document.documentElement.style.scrollBehavior = 'auto'; const c = document.querySelector('[data-cover]'); scrollTo(0, Math.round(c.offsetTop + (c.offsetHeight - innerHeight) * pp)); }, pp);
const ct = (p) => p.evaluate(() => document.querySelector('[data-film-video]').currentTime);
// geometry probe: figure box (keyframe k) on screen + visible text rects
const geo = (p, k) => p.evaluate(([k, boxes]) => {
  const v = document.querySelector('[data-film-video]'), r = v.getBoundingClientRect(); const vw = v.videoWidth || 3, vh = v.videoHeight || 4;
  const sc = Math.max(r.width / vw, r.height / vh), cw = vw * sc, chh = vh * sc, ox = r.left + (r.width - cw) / 2, oy = r.top + (r.height - chh) / 2;
  const set = vw / vh < 0.6 ? boxes.portrait : boxes.landscape; const bx = set[k].box;
  const fig = { l: Math.max(r.left, ox + bx[0] * cw), t: Math.max(r.top, oy + bx[1] * chh), r: Math.min(r.right, ox + bx[2] * cw), b: Math.min(r.bottom, oy + bx[3] * chh) };
  const vis = (el) => { for (let e = el; e && e !== document; e = e.parentElement) { const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) < 0.05) return false; } return true; };
  const texts = []; const w = document.createTreeWalker(document.querySelector('[data-stage]'), NodeFilter.SHOW_TEXT);
  for (let n; (n = w.nextNode());) { if (!n.textContent.trim() || !vis(n.parentElement)) continue; const rg = document.createRange(); rg.selectNodeContents(n); for (const q of rg.getClientRects()) if (q.width > 0 && q.bottom > 0 && q.top < innerHeight) texts.push({ l: q.left, t: q.top, r: q.right, b: q.bottom, s: n.textContent.trim().slice(0, 24) }); }
  for (const el of document.querySelectorAll('.hdr a, .hdr button')) { const q = el.getBoundingClientRect(); texts.push({ l: q.left, t: q.top, r: q.right, b: q.bottom, s: 'hdr' }); }
  const hit = texts.filter((q) => q.l < fig.r && q.r > fig.l && q.t < fig.b && q.b > fig.t).map((q) => q.s);
  const iv = texts.concat([fig]).map((q) => [Math.max(0, q.t), Math.min(innerHeight, q.b)]).filter((x) => x[1] > x[0]).sort((a, b) => a[0] - b[0]);
  let gap = 0, end = 0; for (const [a, z] of iv) { gap = Math.max(gap, a - end); end = Math.max(end, z); } gap = Math.max(gap, innerHeight - end);
  return { fig, hit, band: gap / innerHeight };
}, [k, boxes]);

// 1 autoplay
let p = await page({ viewport: { width: 1440, height: 900 } });
await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(6000);
const t6 = await ct(p); M.autoplay_ct_at_6s = +t6.toFixed(3); T('film_plays_unscrolled (currentTime > 4 s at 6 s)', t6 > 4, `ct=${t6.toFixed(2)}`);
await p._ctx.close();
// 2 scroll takeover, both viewports
for (const [tag, o] of [['1440x900', { viewport: { width: 1440, height: 900 } }], ['390x844', spec([390, 844, 1])]]) {
  p = await page(o); await p.goto(base, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(150); M['scrub_' + tag] = {};
  let worst = 0;
  for (const pp of [0.25, 0.5, 0.75, 1]) { await scrollP(p, pp); await p.waitForTimeout(1800); const c = await ct(p), e = posToTime(Math.min(11, pp * 12)); M['scrub_' + tag][pp] = { currentTime: +c.toFixed(3), expected: +e.toFixed(3) }; worst = Math.max(worst, Math.abs(c - e)); }
  T(`scroll_takeover_${tag} (|currentTime − f(p)| < 0.4 s at p=.25/.5/.75/1)`, worst < 0.4, M['scrub_' + tag]);
  await p._ctx.close();
}
// 3 one variable -> state, rail, copy, film at 13 samples; 5 no text over figure (desktop, Pixel 7, iPhone 13)
for (const [tag, o] of [['desktop', { viewport: { width: 1440, height: 900 } }], ['pixel7', { ...devices['Pixel 7'] }], ['iphone13', { ...devices['iPhone 13'] }]]) {
  p = await page(o); await p.goto(base, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(150);
  const bad = [], hits = [];
  for (let i = 0; i < 13; i++) {
    const pp = i < 12 ? (i + 0.05) / 12 : 1, s = Math.min(11, i); await scrollP(p, pp); await p.waitForTimeout(1300);
    const d = await p.evaluate(() => ({ rail: [...document.querySelectorAll('.rail__item')].findIndex((e) => e.classList.contains('is-on')), copy: Number((document.querySelector('.copy__state.is-on') || {}).dataset?.copyState), count: document.querySelector('[data-rail-count]').textContent, ct: document.querySelector('[data-film-video]').currentTime }));
    const ec = s >= 11 ? 11 : s >= 4 ? 4 : 0;
    if (d.rail !== s || d.copy !== ec || d.count !== String(s + 1).padStart(2, '0') + ' / 12' || Math.abs(d.ct - posToTime(i < 12 ? i + 0.05 : 11)) > 0.4) bad.push({ i, ...d });
    const g = await geo(p, s); if (g.hit.length) hits.push({ i, hit: g.hit.slice(0, 3) });
  }
  T(`state_rail_copy_film_one_variable_${tag} (13 samples)`, !bad.length, bad.slice(0, 2));
  T(`no_text_over_figure_${tag} (13 samples, figure_boxes.json)`, !hits.length, hits.slice(0, 2));
  if (tag === 'desktop') {
    await scrollP(p, 7.05 / 12); await p.waitForTimeout(1300); mkdirSync('/tmp/jvfx', { recursive: true }); await p.screenshot({ path: '/tmp/jvfx/pm.png' });
    const r = await p.evaluate(() => { const q = document.querySelector('[data-film]').getBoundingClientRect(); return [q.left, q.top, q.right, q.bottom]; });
    const out = execFileSync('python3', ['-c', `
import sys,json
from PIL import Image
import numpy as np
im=np.asarray(Image.open('/tmp/jvfx/pm.png').convert('RGB')).astype(float)
l,t,r,b=${JSON.stringify(r)}
H,W,_=im.shape
def lab(c):
  c=c/255; c=np.where(c>0.04045,((c+0.055)/1.055)**2.4,c/12.92)
  x,y,z=np.dot([[0.4124,0.3576,0.1805],[0.2126,0.7152,0.0722],[0.0193,0.1192,0.9505]],c)/np.array([0.95047,1,1.08883])
  f=lambda v: v**(1/3) if v>0.008856 else 7.787*v+16/116
  return np.array([116*f(y)-16,500*(f(x)-f(y)),200*(f(y)-f(z))])
def px(x,y):
  x=int(min(W-3,max(2,x)));y=int(min(H-3,max(2,y))); return np.median(im[y-2:y+3,x-2:x+3].reshape(-1,3),axis=0)
res=[]
for fr in (0.15,0.35,0.65,0.85):
  for side in 'LRTB':
    if side=='L': o,i=(l-4,t+(b-t)*fr),(l+56,t+(b-t)*fr)
    if side=='R': o,i=(r+4,t+(b-t)*fr),(r-56,t+(b-t)*fr)
    if side=='T': o,i=(l+(r-l)*fr,t+4 if t<=0 else t-4),(l+(r-l)*fr,t+56)
    if side=='B': o,i=(l+(r-l)*fr,b-4 if b>=H else b+4),(l+(r-l)*fr,b-56)
    res.append(float(np.linalg.norm(lab(px(*o))-lab(px(*i)))))
print(json.dumps({'max':max(res),'mean':sum(res)/len(res),'n':len(res)}))`]).toString();
    const dE = JSON.parse(out); M.paper_match_dE = dE; T('film_paper_matches_page (16 samples, 4 per side, ΔE76 < 3)', dE.max < 3, dE);
  }
  T(`console_clean_cover_${tag}`, !p.errs.length, p.errs.slice(0, 2));
  await p._ctx.close();
}
// 6/7 CTAs at p=1 + empty band, 19 viewports
const ctaBad = [], bandBad = [], chBad = []; M.bands = {};
for (const [name, s] of Object.entries(VP)) {
  p = await page(spec(s)); await p.goto(base, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(150); M.bands[name] = {};
  for (const [st, pp] of [['s0', 0.05 / 12], ['s7', 7.05 / 12], ['hold', 1]]) {
    await scrollP(p, pp); await p.waitForTimeout(1200); const g = await geo(p, st === 's0' ? 0 : st === 's7' ? 7 : 11); M.bands[name][st] = +g.band.toFixed(3);
    if (g.band > 0.25) bandBad.push(`${name}/${st}=${g.band.toFixed(2)}`);
  }
  const c = await p.evaluate(() => [...document.querySelectorAll('[data-cover-ctas] a')].map((a) => { const r = a.getBoundingClientRect(); let o = 1; for (let e = a; e; e = e.parentElement) o *= parseFloat(getComputedStyle(e).opacity); return r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth && r.height >= 40 && o > 0.95 && getComputedStyle(a).visibility === 'visible'; }));
  await p.waitForTimeout(500); if (c.length !== 2 || !c.every(Boolean)) ctaBad.push(name);
  const vw = typeof s === 'string' ? 412 : s[0], vh = typeof s === 'string' ? 915 : s[1];
  if (vw >= 1024 && vw > vh) { const f = await p.evaluate(() => [...document.querySelectorAll('.chapter__body')].map((e) => Math.ceil(e.scrollHeight) <= innerHeight && e.getBoundingClientRect().height <= innerHeight)); if (!f.every(Boolean)) chBad.push(name); }
  if (p.errs.length) chBad.push(name + ' errors: ' + p.errs[0]);
  await p._ctx.close();
}
T('ctas_visible_at_p1 (19 viewports)', !ctaBad.length, ctaBad);
T('no_empty_band_over_25pct (19 viewports × s0/s7/hold)', !bandBad.length, bandBad);
T('chapters_fit_one_viewport (landscape viewports ≥ 1024 px)', !chBad.length, chBad);
// 9 console clean on a full walk + dialog + forms (desktop)
p = await page({ viewport: { width: 1440, height: 900 } }, { seen: false });
await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(300);
await p.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; scrollTo(0, document.querySelector('#practice').offsetTop + 10); }); await p.waitForTimeout(2200);
const dOpen = await p.evaluate(() => document.querySelector('[data-news]').open); T('dialog_opens_after_chapter_01', dOpen);
await p.keyboard.press('Escape'); await p.waitForTimeout(200); T('dialog_esc_closes', !(await p.evaluate(() => document.querySelector('[data-news]').open)));
await p._ctx.close();
p = await page({ viewport: { width: 1440, height: 900 } }, { seen: false });
await p.goto(base, { waitUntil: 'load' }); await p.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; scrollTo(0, document.querySelector('#classes').offsetTop + 10); }); await p.waitForTimeout(150);
await p.focus('[data-reg] [name="name"]'); await p.waitForTimeout(2600);
T('dialog_never_opens_while_focus_in_form', !(await p.evaluate(() => document.querySelector('[data-news]').open)));
await p.click('[data-reg] button[type="submit"]'); await p.waitForTimeout(200);
const inl = await p.evaluate(() => [...document.querySelectorAll('[data-reg] .err')].filter((e) => e.textContent.trim()).length);
T('register_inline_errors', inl >= 3, `errors shown=${inl}`);
await p.fill('[data-reg] [name="name"]', 'Test'); await p.fill('[data-reg] [name="email"]', 't@example.com'); await p.check('[data-reg] [name="consent"]'); await p.click('[data-reg] button[type="submit"]'); await p.waitForTimeout(700);
T('register_success_replaces_form', await p.evaluate(() => document.querySelector('[data-reg]').hidden && !document.querySelector('#register [data-ok]').hidden));
T('register_posts_api', p.posts.some(([u, d]) => /api\/register/.test(u) && /"consent":true/.test(d || '')));
T('console_clean_desktop_walk', !p.errs.length, p.errs.slice(0, 2));
await p._ctx.close();
p = await page({ viewport: { width: 1440, height: 900 } }, { api: 500 }); await p.goto(base, { waitUntil: 'load' });
await p.evaluate(() => scrollTo(0, document.querySelector('#classes').offsetTop + 10)); await p.fill('[data-reg] [name="name"]', 'Ana'); await p.fill('[data-reg] [name="email"]', 'ana@example.com'); await p.check('[data-reg] [name="consent"]'); await p.click('[data-reg] button[type="submit"]'); await p.waitForTimeout(700);
const mh = await p.evaluate(() => document.querySelector('[data-reg] [data-mailto]').href);
T('register_failure_mailto_carries_fields', /Ana/.test(decodeURIComponent(mh)) && /ana@example\.com/.test(decodeURIComponent(mh)) && await p.isVisible('[data-wa-fallback]'));
await p._ctx.close();
// phones: console + walk
for (const [tag, o] of [['pixel7', devices['Pixel 7']], ['iphone13', devices['iPhone 13']]]) {
  p = await page({ ...o }); await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(400);
  const H = await p.evaluate(() => document.documentElement.scrollHeight); for (let y = 0; y < H; y += 600) { await p.evaluate((y) => scrollTo(0, y), y); await p.waitForTimeout(40); }
  await p.waitForTimeout(600); T(`console_clean_walk_${tag}`, !p.errs.length, p.errs.slice(0, 2)); await p._ctx.close();
}
// reduced motion
p = await page({ ...devices['Pixel 7'], reducedMotion: 'reduce' }); await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(1200);
T('reduced_motion_poster_and_static_copy', await p.evaluate(() => !document.querySelector('[data-film-video]').getAttribute('src') && document.documentElement.classList.contains('is-static') && getComputedStyle(document.querySelector('[data-cover-ctas]').closest('.copy__state')).visibility === 'visible'));
await p._ctx.close();
// breath label synced to the module clock
p = await page({ viewport: { width: 1440, height: 900 } }); await p.goto(base, { waitUntil: 'load' });
const sync = []; for (let i = 0; i < 8; i++) { await p.waitForTimeout(700); sync.push(await p.evaluate(() => { const t = performance.now(), b1 = window.JeevanaBackdrop.breath(t), b0 = window.JeevanaBackdrop.breath(t - 40); return { rising: b1 >= b0, label: document.querySelector('[data-breath-live]').dataset.phase, mid: Math.abs((t % 2750) - 1375) > 1300 }; })); }
T('rail_breath_label_synced_to_breath_clock', sync.filter((x) => !x.mid).every((x) => (x.label === 'in') === x.rising), sync.filter((x) => !x.mid).length + ' samples');
// fonts local + third-party JS
T('fonts_local_and_no_external_requests (beacon only)', [...p.ext].every((h) => h === 'static.cloudflareinsights.com/beacon.min.js'), [...p.ext]);
const html = await (await p.request.get(base)).text();
const scripts = [...html.matchAll(/<script[^>]*src="([^"]+)"/g)].map((m) => m[1]);
T('zero_third_party_js_except_beacon', scripts.filter((s) => /^https?:/.test(s)).every((s) => s === 'https://static.cloudflareinsights.com/beacon.min.js'), scripts);
T('no_style_attributes', !/\sstyle=/.test(html));
T('phone_appears_exactly_twice', (html.match(/\+33 7 54 28 72 10/g) || []).length === 2 && !/"telephone"/.test(html));
let old = 0; for (const u of ['', 'privacy/', '404.html', 'js/main.js', 'js/i18n.js', 'js/breath.js']) old += ((await (await p.request.get(base + u)).text()).match(/jeevanagogula\.gj22@gmail\.com/gi) || []).length;
T('old_email_absent_everywhere (served HTML/JS)', old === 0 && /Jeevana\.yogawellness@gmail\.com/.test(html), `occurrences=${old}`);
// content fixture
const I = await p.evaluate(() => window.JV_I18N);
const fxBad = []; for (const q of fx.positions) { const n = q.n; for (const [k, v] of [[`sn.${n}.dev`, q.dev], [`sn.${n}.iast`, q.iast], [`sn.${n}.mantra`, q.mantra]]) if (I.en[k] !== v || I.fr[k] !== v) fxBad.push(k); if (I.en[`sn.${n}.tr`] !== q.gloss_en) fxBad.push(n + 'en'); if (I.fr[`sn.${n}.tr`] !== q.gloss_fr) fxBad.push(n + 'fr'); if (I.en[`sn.${n}.breath`] !== q.breath_en || I.fr[`sn.${n}.breath`] !== q.breath_fr) fxBad.push(n + 'br'); if (!html.includes(q.dev) || !html.includes(q.iast) || !html.includes(q.mantra)) fxBad.push(n + 'rail'); }
if (I.en['cover.s12.tr'] !== fx.sutras['1.2'].en || I.fr['cover.s12.tr'] !== fx.sutras['1.2'].fr || I.en['cover.s246.tr'] !== fx.sutras['2.46'].en || I.fr['cover.s246.tr'] !== fx.sutras['2.46'].fr || !html.includes(fx.sutras['1.2'].dev) || !html.includes(fx.sutras['2.46'].dev)) fxBad.push('sutras');
T('content_fixture_matches (12 positions + 2 sutras, EN/FR, rail)', !fxBad.length, fxBad);
const ke = Object.keys(I.en), kf = Object.keys(I.fr); T('en_fr_parity', ke.length === kf.length && ke.every((k) => kf.includes(k) && I.fr[k]), `${ke.length}/${kf.length}`);
await p._ctx.close();
// privacy
p = await page({ viewport: { width: 1440, height: 900 } }); const pr = await p.goto(base + 'privacy/', { waitUntil: 'load' }); await p.waitForTimeout(400);
T('privacy_page (200, mentions légales, 0 console errors)', pr.status() === 200 && /Mentions légales/.test(await p.content()) && !p.errs.length, p.errs.slice(0, 1)); await p._ctx.close();
// sizes
const sz = (f) => statSync(SITE + f).size; const page_kb = (sz('index.html') + sz('css/styles.css') + sz('js/main.js') + sz('js/i18n.js') + sz('js/breath.js')) / 1024;
M.sizes = { index_css_js_kb: +page_kb.toFixed(1), breath_kb: +(sz('js/breath.js') / 1024).toFixed(1), film_mb: +(sz('assets/film/' + hero.landscape) / 1048576).toFixed(2), film_m_mb: +(sz('assets/film/' + hero.phone) / 1048576).toFixed(2) };
T('sizes (index+css+js ≤ 150 KB, breath.js ≤ 10 KB, film ≤ 6 MB / 4 MB)', page_kb <= 150 && sz('js/breath.js') <= 10240 && sz('assets/film/' + hero.landscape) <= 6 * 1048576 && sz('assets/film/' + hero.phone) <= 4 * 1048576, M.sizes);
const faststart = (f) => { const buf = readFileSync(SITE + 'assets/film/' + f); return buf.indexOf('moov') < buf.indexOf('mdat'); };
T('film_faststart', faststart(hero.landscape) && faststart(hero.phone));
await b.close();
const pass = results.filter((r) => r.ok).length;
const versions = { playwright: req('playwright/package.json').version, node: process.version, pillow: execFileSync('python3', ['-c', 'import PIL;print(PIL.__version__)']).toString().trim() };
writeFileSync(R + 'functional.json', JSON.stringify({ date: new Date().toISOString(), film: { standin: !!hero.standin, seconds: hero.seconds, keyframes: hero.keyframes_s.length }, pass, total: results.length, results, measurements: M, versions }, null, 1));
console.log(`\n${pass}/${results.length}`); process.exit(pass === results.length ? 0 : 1);
