#!/usr/bin/env node
/* functional.mjs — Jeevana production site v2 ("Twelve breaths, drawn then real").
   Template assertions kept where their subject still exists (deck, i18n, forms, dialog, drum, budgets), the
   round-2 numeric geometry (§1, §4, §6, §8), the ops/legal/measurement items of panel/00_fix_brief.md and the
   brief_v2 cover assertions. Every geometric check reads real DOM boxes; nothing is narrated.
   usage: node research/serve_csp.mjs site 8794 &  node research/functional.mjs http://localhost:8794/
   outputs: research/functional.json; exit 0 only on N/N. /api/* calls are mocked to 200 {ok:true} unless a test
   says otherwise; the Pages Functions themselves are bundled with esbuild and run against an in-memory KV. */
const argv = process.argv.slice(2);
if (!argv[0] || argv.includes('--help')) { console.log('functional.mjs <base-url>'); process.exit(argv[0] ? 0 : 2); }
// ======================= CONFIG =======================
const KEYS = ['sn-01', 'sn-02', 'sn-03', 'sn-04', 'sn-05', 'sn-06', 'photo-05', 'sn-05', 'alt-09', 'sn-03', 'sn-02', 'sn-12'];
const DESK = { ground: 0.86, height: 0.70, maxW: 0.56 }, PHONE = { ground: 0.78, height: 0.58, maxW: 0.92 };
const END_P = 0.92, LAST = 12;
const TAB_ORDER = ['classes', 'register', 'contact', 'about']; const FIRST_TAB = 'about'; const LAST_TAB = 'contact';
const PAPER_RGB = 'rgb(243, 238, 228)';
const LIMITS = { otherDesktop: 7000 - 4 * 900, otherMobile: 9000 - 2 * 844, panelDesktop: 900, panelMobile: 1830, bundleKB: 150, contourB: 6144 };
const VP = { 'mobile': 'Pixel 7', 'iphone-se': [375, 667, 1], 'galaxy-s8': [360, 740, 1], 'iphone-13': [390, 844, 1], 'pixel-7': [412, 915, 1], 'iphone-15-pro-max': [430, 932, 1], 'phone-landscape': [844, 390, 1], 'small-tablet': [600, 960, 1], 'ipad-portrait': [820, 1180, 0], 'ipad-landscape': [1180, 820, 0], 'ipad-pro-portrait': [1024, 1366, 0], 'ipad-pro-landscape': [1366, 1024, 0], 'laptop-1280': [1280, 800, 0], 'laptop-1440': [1440, 900, 0], 'laptop-1536': [1536, 864, 0], 'desktop-1080p': [1920, 1080, 0], 'desktop-1440p': [2560, 1440, 0], 'desktop-4k': [3840, 2160, 0], 'tv-portrait': [1080, 1920, 0] };
// ======================= end CONFIG =======================
import { createRequire } from 'node:module'; import { writeFileSync, readFileSync, statSync, mkdtempSync, readdirSync } from 'node:fs'; import { execFileSync } from 'node:child_process'; import { join } from 'node:path'; import { tmpdir } from 'node:os';
process.env.PLAYWRIGHT_BROWSERS_PATH ||= '/opt/pw-browsers';
const _req = createRequire(import.meta.url); let _pw; for (const p of ['/opt/node22/lib/node_modules/playwright', '/opt/node-tools/node_modules/playwright', 'playwright']) { try { _pw = _req(p); break; } catch {} }
if (!_pw) { console.error('playwright not found'); process.exit(2); }
const { chromium, devices } = _pw;
const HERE = new URL('.', import.meta.url).pathname, SITE = join(HERE, '../site/');
const base = argv[0].endsWith('/') ? argv[0] : argv[0] + '/'; const R = [];
const t = (name, ok, info) => { R.push({ name, ok: !!ok, info }); process.stdout.write((ok ? 'ok   ' : 'FAIL ') + name + (info !== undefined ? '  ' + JSON.stringify(info).slice(0, 400) : '') + '\n'); };
const b = await chromium.launch();
const IGN = /ERR_CERT|ERR_TUNNEL|ERR_NAME|ERR_PROXY|cloudflareinsights/;
const external = [];
async function mk(opts, { seen = true, lang = 'en', mock = true } = {}) {
  const ctx = await b.newContext(opts); const p = await ctx.newPage(); const errs = [];
  p.on('pageerror', (e) => errs.push(e.message));
  p.on('console', (m) => { if (m.type() === 'error' && !IGN.test(m.text() + (m.location().url || ''))) errs.push(m.text() + ' ' + (m.location().url || '')); });
  p.on('requestfailed', (r) => { if (!IGN.test(r.url() + (r.failure() || {}).errorText) && !/ERR_ABORTED/.test((r.failure() || {}).errorText)) errs.push('requestfailed ' + r.url()); });
  p.on('request', (r) => { const u = new URL(r.url()); if (!/^(localhost|127\.0\.0\.1)$/.test(u.hostname) && u.protocol !== 'data:' && u.protocol !== 'blob:') external.push(u.href); });
  if (mock) await p.route('**/api/**', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: '{"ok":true}' }));
  await p.route('https://static.cloudflareinsights.com/**', (r) => r.fulfill({ status: 200, contentType: 'text/javascript', body: '' }));
  await p.addInitScript(([s, l]) => { try { if (s) localStorage.setItem('jv-news-seen', '1'); localStorage.setItem('jv-lang', l); } catch (e) {} }, [seen, lang]);
  p._errs = errs; p._ctx = ctx; return p;
}
const close = (p) => p._ctx.close();
const spec = (s) => Array.isArray(s) ? { viewport: { width: s[0], height: s[1] }, isMobile: !!s[2], hasTouch: !!s[2], deviceScaleFactor: 1 } : { ...devices[s] };
const scrollTo = async (p, y, wait = 350) => { await p.evaluate((v) => { document.documentElement.style.scrollBehavior = 'auto'; window.scrollTo(0, v); }, y); await p.waitForTimeout(wait); };
// cover track: span = cover height − 1 vh − the drum's overlap (the drum enters only after p = 1)
const coverY = (p, pp) => p.evaluate((pp) => { const c = document.querySelector('[data-cover]'), f = document.querySelector('[data-fold]'); const span = c.offsetHeight - innerHeight - Math.max(0, -parseFloat(getComputedStyle(f).marginTop) || 0); return Math.round(c.offsetTop + span * pp); }, pp);
const stateY = (p, s) => coverY(p, Math.min(1, (s >= LAST ? LAST : s + 0.05) / LAST * END_P));
const goState = async (p, s, wait = 750) => { await scrollTo(p, 400, 60); await scrollTo(p, await stateY(p, s), wait); };
const state = (p) => p.evaluate(() => +document.querySelector('[data-cover]').dataset.state);
const fileKB = (f) => statSync(join(SITE, f)).size / 1024;
// cover geometry probe: figure box, ground line, text boxes (header + cover copy + rail), visibility
const probe = (p) => p.evaluate(() => {
  const st = document.querySelector('[data-stage]').getBoundingClientRect();
  const f = document.querySelector('.fig.is-on'); const fr = f ? f.getBoundingClientRect() : null;
  const g = f ? parseFloat(getComputedStyle(f).getPropertyValue('--g')) : 0;
  const vis = (e) => { const cs = getComputedStyle(e); if (cs.visibility === 'hidden' || cs.display === 'none') return false; let o = 1; for (let x = e; x && x !== document.body; x = x.parentElement) o *= +getComputedStyle(x).opacity; return o > 0.05; };
  const texts = [];
  const walker = document.createTreeWalker(document.querySelector('[data-cover]'), NodeFilter.SHOW_TEXT);
  for (let n; (n = walker.nextNode());) { if (!n.textContent.trim() || !n.parentElement || !vis(n.parentElement) || n.parentElement.closest('noscript,svg')) continue; const rg = document.createRange(); rg.selectNodeContents(n); for (const r of rg.getClientRects()) if (r.width > 1 && r.height > 1) texts.push({ l: r.left, t: r.top, r: r.right, b: r.bottom, s: n.textContent.trim().slice(0, 24) }); }
  document.querySelectorAll('[data-hdr] a, [data-hdr] button').forEach((e) => { if (!vis(e)) return; const r = e.getBoundingClientRect(); if (r.width) texts.push({ l: r.left, t: r.top, r: r.right, b: r.bottom, s: 'hdr:' + e.textContent.trim().slice(0, 12) }); });
  document.querySelectorAll('[data-cover] .btn').forEach((e) => { if (!vis(e)) return; const r = e.getBoundingClientRect(); texts.push({ l: r.left, t: r.top, r: r.right, b: r.bottom, s: 'btn:' + e.textContent.trim().slice(0, 12) }); });
  const box = fr ? { l: fr.left, t: fr.top, r: fr.right, b: fr.bottom } : null;
  const hit = box ? texts.filter((x) => x.l < box.r - 1 && box.l < x.r - 1 && x.t < box.b - 1 && box.t < x.b - 1).map((x) => x.s) : [];
  return { W: st.width, H: st.height, stTop: st.top, fig: box, key: f && f.dataset.key, g, hit, op: f ? +getComputedStyle(f).opacity : 0, state: +document.querySelector('[data-cover]').dataset.state, reveal: parseFloat(getComputedStyle(document.querySelector('[data-stage]')).getPropertyValue('--reveal')) };
});
const isPhoneVp = (w, h) => w < 800 || h >= w;

// ---------------- static source checks ----------------
const html = readFileSync(join(SITE, 'index.html'), 'utf8'), privacy = readFileSync(join(SITE, 'privacy/index.html'), 'utf8'), nf = readFileSync(join(SITE, '404.html'), 'utf8');
const css = readFileSync(join(SITE, 'css/styles.css'), 'utf8'), mainjs = readFileSync(join(SITE, 'js/main.js'), 'utf8');
const MAN = JSON.parse(readFileSync(join(SITE, 'assets/fig/manifest.json'), 'utf8')).fig, CONT = JSON.parse(readFileSync(join(SITE, 'assets/fig/contours.json'), 'utf8'));
{
  const kb = fileKB('index.html') + fileKB('css/styles.css') + fileKB('js/main.js') + fileKB('js/i18n.js');
  t('index+css+js ≤ 150 KB', kb <= LIMITS.bundleKB, { kb: +kb.toFixed(1) });
  const sa = [html, privacy, nf].map((h) => (h.match(/\sstyle\s*=/g) || []).length);
  t('no style="" attributes in shipped HTML (index, privacy, 404)', sa.every((n) => n === 0), sa);
  const ext = [html, privacy, nf, css].flatMap((s) => (s.match(/(?:src|href)=["']https?:\/\/[^"']+|url\(https?:[^)]+/g) || [])).filter((u) => !/static\.cloudflareinsights\.com\/beacon\.min\.js|prodcraft\.fyi|instagram\.com|wa\.me|jeevana-yoga\.pages\.dev|cnil/.test(u));
  t('fonts self-hosted: no Google Fonts link, @font-face from /assets/fonts, CSP font-src self', !/fonts\.(googleapis|gstatic)/.test(html + css + privacy + nf) && /@font-face\{font-family:'Cormorant Garamond'[^}]*url\(\.\.\/assets\/fonts\//.test(css) && /font-src 'self'/.test(readFileSync(join(SITE, '_headers'), 'utf8')) && ext.length === 0, { ext });
  t('Cloudflare beacon present with the supplied token; CSP allows it (script + connect)', /beacon\.min\.js" data-cf-beacon='\{"token":"f7ff129092344aca8fd504fcca79bc05"\}'/.test(html) && /script-src 'self' https:\/\/static\.cloudflareinsights\.com/.test(readFileSync(join(SITE, '_headers'), 'utf8')) && /connect-src 'self' https:\/\/cloudflareinsights\.com/.test(readFileSync(join(SITE, '_headers'), 'utf8')));
  const big = Object.entries(CONT).filter(([, v]) => Buffer.byteLength(v.d) > LIMITS.contourB || !/^M[\d. ]+/.test(v.d) || (v.d.match(/M/g) || []).length !== 1);
  t('contours: one outer path per figure (single M), each ≤ 6 KB', big.length === 0 && KEYS.every((k) => CONT[k]), big.map(([k, v]) => [k, v.d.length]));
  const up = []; for (const [k, r] of Object.entries(MAN)) for (const [n, w, h] of [...r.srcset, ...(r.wash || []), ...(r.pencil || [])]) { if (!/-pencil@/.test(n) && h > r.h + 0.5) up.push(n); }
  t('srcset never upscales: every variant ≤ the figure\'s native height; wash layer for every cover key', up.length === 0 && KEYS.every((k) => MAN[k] && MAN[k].wash && MAN[k].wash.length), up);
  t('phone appears exactly twice in index.html (Contact row + mobile bar); JSON-LD Person without telephone', (html.match(/\+33 7 54 28 72 10/g) || []).length === 2 && /"@type":"Person"/.test(html) && !/"telephone"/.test(html));
  t('named timing constants at the top of main.js', ['AUTO_LEG_MS', 'S0_LINE_MS', 'S0_TONE_MS', 'COVER_END', 'COVER_OUT', 'MBAR_AT', 'FOLD_OPEN', 'REVEAL_FAILSAFE_MS', 'DIALOG_DECK_MS', 'DIALOG_TIME_MS', 'END_P', 'HOLD_IN'].every((k) => new RegExp('var [^;]*\\b' + k + ' = ').test(mainjs.slice(0, 2500))));
  t('backdrop canvas retired (no backdrop.js, no <canvas> in the cover); Kling slot ships dormant (hero.json ready:false)', !/backdrop|<canvas/.test(html) && JSON.parse(readFileSync(join(SITE, 'assets/film/hero.json'), 'utf8')).ready === false);
}
// content fixture (D16): i18n.js matches the 12 triples + 2 sūtras exactly, both languages
{
  const fx = JSON.parse(readFileSync(join(HERE, 'content_fixture.json'), 'utf8'));
  const w = {}; new Function('window', readFileSync(join(SITE, 'js/i18n.js'), 'utf8'))(w); const D = w.JV_I18N;
  const bad = [];
  for (const q of fx.positions) { const n = q.n; for (const [k, v] of [['dev', q.dev], ['iast', q.iast], ['mantra', q.mantra]]) for (const l of ['en', 'fr']) if (D[l][`sn.${n}.${k}`] !== v) bad.push(`${l} sn.${n}.${k}`); if (D.en[`sn.${n}.tr`] !== q.gloss_en) bad.push('en tr ' + n); if (D.fr[`sn.${n}.tr`] !== q.gloss_fr) bad.push('fr tr ' + n); if (D.en[`sn.${n}.breath`] !== q.breath_en || D.fr[`sn.${n}.breath`] !== q.breath_fr) bad.push('breath ' + n); }
  if (D.en['cover.s12.tr'] !== fx.sutras['1.2'].en || D.fr['cover.s12.tr'] !== fx.sutras['1.2'].fr || D.en['cover.s246.tr'] !== fx.sutras['2.46'].en || D.fr['cover.s246.tr'] !== fx.sutras['2.46'].fr) bad.push('sutra tr');
  if (!html.includes(fx.sutras['1.2'].dev) || !html.includes(fx.sutras['2.46'].dev) || !html.includes(fx.sutras['1.2'].iast) || !html.includes(fx.sutras['2.46'].iast)) bad.push('sutra dev/iast in html');
  if (!fx.positions.some((q) => q.iast === 'Aśva Sañcālanāsana') || /Sañcalan/.test(readFileSync(join(SITE, 'js/i18n.js'), 'utf8') + readFileSync(join(HERE, 'photos.md'), 'utf8'))) bad.push('IAST unify');
  const ek = Object.keys(D.en).sort().join(), fk = Object.keys(D.fr).sort().join();
  t('content fixture: i18n.js matches the 12 triples + 2 sūtras (EN + FR); IAST unified; EN/FR key parity', bad.length === 0 && ek === fk, bad.slice(0, 6));
}

// ---------------- backend (Pages Functions bundled with esbuild, in-memory KV) ----------------
{
  const out = mkdtempSync(join(tmpdir(), 'jvfn-')); const esb = join(HERE, 'node_modules/.bin/esbuild');
  const files = ['api/subscribe.ts', 'api/register.ts', 'api/unsubscribe.ts', 'api/event.ts', 'api/stats.ts', 'api/export.ts', '_middleware.ts'];
  execFileSync(esb, [...files.map((f) => join(SITE, 'functions', f)), '--bundle', '--format=esm', '--platform=neutral', '--outdir=' + out, '--out-extension:.js=.mjs', '--log-level=error']);
  const mod = async (f) => import(join(out, f.replace(/^api\//, 'api/').replace(/\.ts$/, '.mjs')).replace(/^/, 'file://'));
  const found = readdirSync(out, { recursive: true }).map(String);
  const load = async (n) => import('file://' + join(out, found.find((x) => x.endsWith(n + '.mjs'))));
  class KV { constructor(fail) { this.m = new Map(); this.fail = fail; } async get(k) { if (this.fail) throw new Error('kv down'); return this.m.has(k) ? this.m.get(k) : null; } async put(k, v, o) { if (this.fail) throw new Error('kv down'); this.m.set(k, v); this.o = o; } async delete(k) { this.m.delete(k); } async list({ prefix }) { return { keys: [...this.m.keys()].filter((k) => k.startsWith(prefix)).map((name) => ({ name })), list_complete: true }; } }
  const ctx = (req, env) => ({ request: req, env, waitUntil: () => {}, next: async () => new Response('next') });
  const postJ = (u, body, raw) => new Request('https://x' + u, { method: 'POST', headers: { 'content-type': 'application/json', 'CF-Connecting-IP': '1.2.3.4' }, body: raw !== undefined ? raw : JSON.stringify(body) });
  const sub = await load('subscribe'), reg = await load('register'), uns = await load('unsubscribe'), evm = await load('event'), mid = await load('_middleware'), stats = await load('stats');
  const origLog = console.log, origErr = console.error; const logs = []; console.log = (...a) => logs.push(a.join(' ')); console.error = (...a) => logs.push('E ' + a.join(' '));
  try {
    const kv = new KV(); const env = { JEEVANA_KV: kv };
    const r1 = await sub.onRequestPost(ctx(postJ('/api/subscribe', { email: 'A@b.co', phone: '+33 6 00 00 00 00', consent: true, lang: 'fr', source: 'dialog' }), env));
    const key = [...kv.m.keys()].find((k) => k.startsWith('news:')); const rec = JSON.parse(kv.m.get(key));
    await new Promise((r) => setTimeout(r, 5));
    const r1b = await sub.onRequestPost(ctx(postJ('/api/subscribe', { email: 'a@b.co', consent: true, lang: 'fr' }), env)); const rec2 = JSON.parse(kv.m.get(key));
    const tok = rec.unsubscribe_token;
    const u1 = await uns.onRequestGet(ctx(new Request('https://x/api/unsubscribe?t=' + tok), env)); const body1 = await u1.text();
    const u2 = await uns.onRequestGet(ctx(new Request('https://x/api/unsubscribe?t=' + tok), env));
    t('unsubscribe flow (mocked KV): token stored (24 bytes hex), re-subscribe keeps consent_ts/token/phone, GET deletes the record, FR page, second use 404', r1.status === 200 && /^[0-9a-f]{48}$/.test(tok) && rec.consent_text && rec.phone && r1b.status === 200 && rec2.consent_ts === rec.consent_ts && rec2.unsubscribe_token === tok && rec2.phone === rec.phone && u1.status === 200 && /désinscrit/.test(body1) && !kv.m.has(key) && u2.status === 404, { s: [r1.status, r1b.status, u1.status, u2.status] });
    const e1 = await evm.onRequestPost(ctx(postJ('/api/event', { name: 'wa_tap' }), env)); await evm.onRequestPost(ctx(postJ('/api/event', { name: 'wa_tap' }), env));
    const e2 = await evm.onRequestPost(ctx(postJ('/api/event', { name: 'email', email: 'x@y.z' }), env));
    const evk = [...kv.m.keys()].filter((k) => k.startsWith('ev:'));
    const st0 = await stats.onRequestGet(ctx(new Request('https://x/api/stats'), env));
    const envA = { JEEVANA_KV: kv, EXPORT_USER: 'j', EXPORT_PASS: 'secret' };
    const st1 = await stats.onRequestGet(ctx(new Request('https://x/api/stats', { headers: { Authorization: 'Basic ' + btoa('j:secret'), 'CF-Connecting-IP': '9.9.9.9' } }), envA)); const sj = await st1.json();
    t('event beacon allowlist: known name counts (ev:<date>:<name> = 2), unknown 400 with nothing stored; /api/stats 401 without auth, 30-day JSON with it', e1.status === 200 && e2.status === 400 && evk.length === 1 && kv.m.get(evk[0]) === '2' && st0.status === 401 && st1.status === 200 && Object.values(sj.days)[0].wa_tap === 2, { evk });
    const big = await reg.onRequestPost(ctx(postJ('/api/register', null, JSON.stringify({ name: 'x'.repeat(9000) })), env));
    const noKv = await reg.onRequestPost(ctx(postJ('/api/register', { name: 'A', email: 'a@b.co', consent: true }), {}));
    const kvDown = await sub.onRequestPost(ctx(postJ('/api/subscribe', { email: 'c@d.co', consent: true }), { JEEVANA_KV: new KV(true) }));
    const kv3 = new KV(); const rg = await reg.onRequestPost(ctx(postJ('/api/register', { name: 'A', email: 'a@b.co', consent: true, lang: 'en' }), { JEEVANA_KV: kv3 })); const rk = [...kv3.m.keys()].find((k) => k.startsWith('reg:'));
    t('backend hardening: 8 KB cap → 413, missing KV → 503 JSON, KV failure → rate limiter allows + 500 logged with {service,route}, reg: records expire in 24 months with consent_text', big.status === 413 && noKv.status === 503 && (await noKv.json()).error === 'storage unavailable' && kvDown.status === 500 && logs.some((l) => /"service":"jeevana","route":"ratelimit:news"/.test(l)) && rg.status === 200 && kv3.o && kv3.o.expirationTtl === 63072000 && JSON.parse(kv3.m.get(rk)).consent_text.length > 40, [big.status, noKv.status, kvDown.status]);
    const mids = await Promise.all(['/wrangler.toml', '/functions/api/_lib.ts', '/research/brief.md', '/x.ts', '/'].map(async (u) => (await mid.onRequest(ctx(new Request('https://x' + u)))).status));
    t('middleware: 404 for /wrangler.toml, /functions/*, /research/*, *.ts; passes /', mids.join() === '404,404,404,404,200', mids);
    t('notify(): BREVO_API_KEY unset → console.log only, visitor still gets 200', logs.some((l) => /"sent":false/.test(l)) && r1.status === 200);
  } finally { console.log = origLog; console.error = origErr; }
}

// ---------------- desktop: S0 drawing, autoplay, scroll takeover ----------------
let p = await mk({ viewport: { width: 1440, height: 900 } });
await p.goto(base, { waitUntil: 'load' });
{
  await p.waitForTimeout(400);
  const a = await p.evaluate(() => ({ intro: document.querySelector('[data-cover]').dataset.intro, off: getComputedStyle(document.querySelector('.fig.is-on .fig__line path')).strokeDashoffset, key: document.querySelector('.fig.is-on').dataset.key, rev: getComputedStyle(document.querySelector('[data-stage]')).getPropertyValue('--reveal').trim(), d: document.querySelector('.fig.is-on .fig__line path').getAttribute('d').length }));
  await p.waitForTimeout(3600);
  const c = await p.evaluate(() => ({ intro: document.querySelector('[data-cover]').dataset.intro, off: parseFloat(getComputedStyle(document.querySelector('.fig.is-on .fig__line path')).strokeDashoffset), tone: +getComputedStyle(document.querySelector('.fig.is-on .fig__draw')).opacity, lit: document.querySelector('[data-rail-item]').classList.contains('is-on'), y: scrollY }));
  t('S0: sn-01 contour draws itself (dashoffset > 0 at 0.4 s → 0 by 4 s), graphite wash fades in, rail 01 lights — no scroll', a.key === 'sn-01' && a.intro === 'drawing' && parseFloat(a.off) > 0.05 && a.d > 200 && c.intro === 'done' && c.off === 0 && c.tone > 0.15 && c.lit && c.y === 0, { a, c });
  t('S0: photograph hidden under the drawing (reveal = 0)', a.rev === '0.000' || a.rev === '0');
  let s3 = -1; for (let i = 0; i < 16 && s3 < 3; i++) { await p.waitForTimeout(500); s3 = await state(p); }
  t('autoplay reaches S3 within 12 s of load (no scroll), then holds', s3 === 3, { s3 });
  await p.waitForTimeout(3000); t('autoplay holds at S3', (await state(p)) === 3);
  await scrollTo(p, await coverY(p, 0.02), 600);
  const kept = await state(p);
  await scrollTo(p, await stateY(p, 6), 700);
  const s6 = await state(p), ap = await p.evaluate(() => document.querySelector('[data-cover]').dataset.autoplay);
  t('scroll takes over from the current state (no jump back to S0), then follows the track', kept === 3 && s6 === 6 && ap === 'off', { kept, s6, ap });
  // beats + rail + state agreement at 13 states in EN and FR
  const seen = [];
  for (const lang of ['en', 'fr']) {
    await p.evaluate((l) => document.querySelector(`[data-lang="${l}"]`).click(), lang);
    for (let s = 0; s <= LAST; s++) {
      await scrollTo(p, await stateY(p, s), 260);
      seen.push(await p.evaluate(([s, KEYS, lang]) => { const c = document.querySelector('[data-cover]'); const pos = Math.min(s, 11) + 1; const D = window.JV_I18N[lang]; const rail = document.querySelector('[data-rail]'), rm = document.querySelector('[data-railm]'); const beat = document.querySelector('[data-beat].is-on'); const k = document.querySelector('[data-fig].is-on, [data-fig][data-key]');
        return { s, st: +c.dataset.state, key: document.querySelector('[data-cover] .fig:last-of-type.is-on, [data-cover] .fig.is-on') ? [...document.querySelectorAll('.fig')].map((f) => f.dataset.key).includes(KEYS[pos - 1]) : false, rail: rail.dataset.pos, railm: rm.dataset.pos, beat: beat ? +beat.dataset.beat : -1, mantra: rail.querySelector('[data-rail-key="mantra"]').textContent, tr: rail.querySelector('[data-rail-key="tr"]').textContent, mtr: rm.querySelector('[data-railm-tr]').textContent, pos, ok: rail.querySelector('[data-rail-key="tr"]').textContent === D['sn.' + pos + '.tr'] && rm.querySelector('[data-railm-tr]').textContent === D['sn.' + pos + '.tr'] && rail.querySelector('[data-rail-key="mantra"]').textContent === D['sn.' + pos + '.mantra'], ctas: c.classList.contains('is-ctas') }; }, [s, KEYS, lang]));
    }
  }
  await p.waitForTimeout(800);
  const keyNow = await p.evaluate(() => document.querySelector('.fig.is-on').dataset.key);
  t('one state drives figure, rail and mobile counter: data-state = s, rail data-pos = railm data-pos = position, at 13 states (EN + FR)', seen.every((x) => x.st === x.s && +x.rail === x.pos && +x.railm === x.pos && x.key) && keyNow === 'sn-12', seen.filter((x) => !(x.st === x.s && +x.rail === x.pos && +x.railm === x.pos && x.key)).slice(0, 3));
  t('GLOSS: desktop rail and mobile counter show the i18n mantra + gloss of the current position (EN + FR)', seen.every((x) => x.ok));
  t('rail mantra text changes with the state', new Set(seen.filter((x) => x.s < 12).slice(0, 12).map((x) => x.mantra)).size === 12);
  t('headline: "Twelve breaths." beat at S0–S3, Sūtra 2.46 from S4; CTAs from S9 (EN + FR)', seen.every((x) => x.beat === (x.s >= 4 ? 1 : 0) && x.ctas === (x.s >= 9)));
  await p.evaluate(() => document.querySelector('[data-lang="en"]').click());
  // reveal mask
  const rv = [];
  for (const s of [1, 4, 8, 9, 10, 11, 12]) { await scrollTo(p, await stateY(p, s), 300); rv.push([s, await p.evaluate(() => { const st = document.querySelector('[data-stage]'); const v = parseFloat(getComputedStyle(st).getPropertyValue('--reveal')); const ph = document.querySelector('.fig.is-on .fig__photo'); return [v, getComputedStyle(ph).maskImage || getComputedStyle(ph).webkitMaskImage]; })]); }
  t('reveal mask: --reveal = 0 for S ≤ 8, rises across S9–S10, = 1 at S11/S12; the photograph carries a linear-gradient mask', rv.filter(([s]) => s <= 8).every(([, v]) => v[0] === 0) && rv.find(([s]) => s === 9)[1][0] > 0 && rv.find(([s]) => s === 10)[1][0] > rv.find(([s]) => s === 9)[1][0] && rv.filter(([s]) => s >= 11).every(([, v]) => v[0] === 1) && rv.every(([, v]) => /linear-gradient/.test(v[1])), rv.map(([s, v]) => [s, v[0]]));
  // stage is paper, no dark plate, sun is a blurred gradient
  const look = await p.evaluate(() => { const pin = getComputedStyle(document.querySelector('[data-stage]')); const sun = getComputedStyle(document.querySelector('.cover__sun')); const round = [...document.querySelectorAll('[data-cover] *')].filter((e) => { const c = getComputedStyle(e); return c.borderRadius === '50%' && c.backgroundImage === 'none' && c.backgroundColor !== 'rgba(0, 0, 0, 0)'; }).length; return { bg: pin.backgroundColor, sunBg: sun.backgroundImage, blur: parseFloat((sun.filter.match(/blur\(([\d.]+)px/) || [0, 0])[1]), round, fig: getComputedStyle(document.querySelector('.fig.is-on .fig__photo')).filter }; });
  t('paper stage (#F3EEE4), no dark plate; sun = radial gradient, blur ≥ 40 px, no hard disc; no CSS filter on the photograph', look.bg === PAPER_RGB && /radial-gradient/.test(look.sunBg) && look.blur >= 40 && look.round === 0 && look.fig === 'none', look);
  t('desktop: 0 console errors', p._errs.length === 0, p._errs.slice(0, 3));
}
await close(p);

// S11 photograph resolution on a 2× screen
{
  const q = await mk({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  await q.goto(base, { waitUntil: 'load' }); await goState(q, 11, 1800);
  const r = await q.evaluate(() => { const im = document.querySelector('.fig.is-on .fig__photo'); const b = im.getBoundingClientRect(); return { src: im.currentSrc, nh: im.naturalHeight, h: b.height, key: im.closest('.fig').dataset.key }; });
  const m = /@(\d+)\.webp/.exec(r.src);
  t('S11 on 1440×900 @2×: the photograph is the ≥ 1600 variant and ≥ 1.5× the rendered height (currentSrc)', r.key === 'sn-12' && m && +m[1] >= 1600 && +m[1] >= 1.5 * r.h, r);
  await close(q);
}

// ---------------- 19-viewport matrix × 13 states: figure height, ground line, no text over the figure ----------------
{
  const H = [], G = [], X = [], E = {}, O = [];
  for (const [name, sp] of Object.entries(VP)) {
    const q = await mk(spec(sp)); await q.goto(base, { waitUntil: 'load' }); await q.waitForTimeout(300);
    for (let s = 0; s <= LAST; s++) {
      await goState(q, s, s === 0 ? 900 : 700);
      const g = await probe(q); const ph = isPhoneVp(g.W, g.H), L = ph ? PHONE : DESK;
      if (!g.fig) { H.push([name, s, 'nofig']); continue; }
      const hr = (g.fig.b - g.fig.t) / g.H, wr = (g.fig.r - g.fig.l) / g.W, capped = wr >= L.maxW - 0.004;
      if (!(hr >= L.height - 0.003 || capped)) H.push([name, s, g.key, +hr.toFixed(3), +wr.toFixed(3)]);
      const feet = g.fig.t + g.g * (g.fig.b - g.fig.t) - g.stTop, line = (ph ? PHONE : DESK).ground * g.H;
      if (Math.abs(feet - line) > 0.01 * g.H) G.push([name, s, +(feet / g.H).toFixed(3)]);
      if (g.hit.length) X.push([name, s, g.hit.slice(0, 3)]);
      if (s === 11 && g.op < 0.95) O.push([name, g.op]);
    }
    E[name] = q._errs.slice(0, 2); await close(q);
  }
  t('figure height ≥ .70 of the stage desktop / ≥ .58 phones at every state, or width-capped at 56 % / 92 % of the stage (19 viewports × 13 states)', H.length === 0, H.slice(0, 8));
  t('feet row within 1 % of the ground line (86 % desktop / 78 % phones) at every state (19 × 13)', G.length === 0, G.slice(0, 8));
  t('no text box intersects the figure bbox at any state (cover copy, rail, counter, CTAs, hint, header) (19 × 13)', X.length === 0, X.slice(0, 8));
  t('R3 matrix: 0 console errors on all 19 viewports', Object.values(E).every((e) => e.length === 0), Object.entries(E).filter(([, e]) => e.length).slice(0, 3));
}

// ---------------- round-2 §1 cover end, §4d, §4a on 19 viewports ----------------
{
  const A = [], B = [], C = [], D = [], BR = [], Z = [];
  for (const [name, sp] of Object.entries(VP)) {
    const q = await mk(spec(sp)); await q.goto(base, { waitUntil: 'load' }); await q.waitForTimeout(300);
    for (const s of [0, 5, 11]) {
      await goState(q, s, 700);
      const r = await q.evaluate(() => { const vis = (e) => { if (!e) return false; const r = e.getBoundingClientRect(); const c = getComputedStyle(e); return r.width > 0 && c.visibility !== 'hidden' && c.display !== 'none' && +c.opacity > 0.05 && r.bottom > 0 && r.top < innerHeight; };
        const brand = [document.querySelector('.hdr__logo')].filter(vis).length; const lang = document.querySelector('.lang').getBoundingClientRect(); const ch = document.querySelector('[data-chapter]');
        return { brand, langEnd: innerWidth - lang.right, chVis: getComputedStyle(ch).visibility !== 'hidden' && getComputedStyle(ch).display !== 'none' && ch.getBoundingClientRect().width > 0 }; });
      if (r.brand !== 1 || r.langEnd > 80) BR.push([name, s, r]);
      if (r.chVis) Z.push([name, s]);
    }
    await scrollTo(q, await coverY(q, 1), 900);
    const e = await q.evaluate(() => { const c = document.querySelector('[data-cover] .ctas'); const r = c.getBoundingClientRect(); const x = r.left + r.width / 2, y = r.top + r.height / 2; const el = document.elementFromPoint(x, y); const f = document.querySelector('[data-fold]').getBoundingClientRect(); const ph = document.querySelector('.fig.is-on .fig__photo');
      return { ctaB: r.bottom, vh: innerHeight, op: +getComputedStyle(c).opacity, hit: !!(el && c.contains(el)), foldT: f.top, fig: +getComputedStyle(document.querySelector('.fig.is-on')).opacity, key: document.querySelector('.fig.is-on').dataset.key, rev: parseFloat(getComputedStyle(document.querySelector('[data-stage]')).getPropertyValue('--reveal')) }; });
    if (!(e.ctaB <= e.vh - 24 && e.op === 1 && e.hit)) A.push([name, e]);
    if (!(e.foldT >= e.ctaB + 16)) B.push([name, e.foldT, e.ctaB]);
    if (!(e.fig >= 0.95 && e.key === 'sn-12' && e.rev === 1)) C.push([name, e.fig, e.key, e.rev]);
    await scrollTo(q, (await coverY(q, 1)) + (await q.evaluate(() => innerHeight)), 1200);
    const f = await q.evaluate(() => { const h = document.querySelector('#fold-title'); let o = 1; for (let x = h; x && x !== document.body; x = x.parentElement) o *= +getComputedStyle(x).opacity; return { h: o, plates: [...document.querySelectorAll('.plate')].map((p) => +getComputedStyle(p).opacity) }; });
    if (!(f.h > 0.99 && f.plates.every((o) => o >= 0.95))) D.push([name, f]);
    await close(q);
  }
  t('R3 §1a cover CTAs: bottom ≤ vh−24, opacity 1, hit-testable at p=1 (19 viewports)', A.length === 0, A.slice(0, 3));
  t('R3 §1b drum top ≥ CTA bottom + 16 px at p=1 (19)', B.length === 0, B.slice(0, 3));
  t('R3 §1c the photograph (sn-12, reveal 1) shown at p=1, opacity ≥ .95 (19)', C.length === 0, C.slice(0, 3));
  t('R3 §1d track end + 1 vh: drum heading opacity 1, three plates ≥ .95 (19)', D.length === 0, D.slice(0, 3));
  t('R3 §4d exactly one brand element visible, language toggle at the inline end (19 × S0/S5/S11)', BR.length === 0, BR.slice(0, 3));
  t('R3 §4a no visible chapter indicator over the cover (19 × S0/S5/S11)', Z.length === 0, Z.slice(0, 3));
}

// ---------------- static / reduced motion / no-JS ----------------
{
  let q = await mk({ viewport: { width: 1440, height: 900 } }); await q.goto(base + '?static=1', { waitUntil: 'load' }); await q.waitForTimeout(1500);
  const s = await q.evaluate(() => ({ st: document.querySelector('[data-cover]').dataset.state, rev: parseFloat(getComputedStyle(document.querySelector('[data-stage]')).getPropertyValue('--reveal')), vis: [...document.querySelectorAll('.dp')].filter((x) => !x.hidden && x.getBoundingClientRect().height > 0).length, ctas: +getComputedStyle(document.querySelector('[data-cover] .ctas')).opacity, beat: document.querySelector('[data-beat].is-on').dataset.beat, h: document.documentElement.scrollHeight }));
  // page-full bands: scan the full page at 2 % vh steps for runs of empty paper / dark
  const band = await q.evaluate(() => { const vh = innerHeight, H = document.documentElement.scrollHeight; let run = 0, worst = 0; const BG = /^(cover|cover__pin|figs|fold|fold__pin|spread|deck|dp|about|about__text|cards|main)$/; for (let y = 0; y < H; y += vh * 0.02) { scrollTo(0, y); const empty = [0.2, 0.5, 0.8].every((fx) => { const e = document.elementFromPoint(innerWidth * fx, vh / 2); return !e || e === document.body || e.tagName === 'MAIN' || [...e.classList].some((c) => BG.test(c)) || e.tagName === 'SECTION' || e.tagName === 'ARTICLE'; }); run = empty ? run + 1 : 0; worst = Math.max(worst, run); } return +(worst * 0.02).toFixed(2); });
  const fullOp = await q.evaluate(() => [...document.querySelectorAll('section, .plate, .dp')].every((e) => +getComputedStyle(e).opacity === 1));
  t('R3 §1e ?static=1: S11 photograph (reveal 1) + Sūtra 2.46 + CTAs, all 4 deck panels visible, every section at full opacity', s.st === '11' && s.rev === 1 && s.vis === 4 && s.ctas === 1 && s.beat === '1' && fullOp, s);
  t('R3 §1e page-full ?static=1: no empty band > 60 % vh', band <= 0.6, { band });
  await close(q);
  q = await mk({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' }); await q.goto(base, { waitUntil: 'load' }); await q.waitForTimeout(1200);
  const rm = await q.evaluate(() => ({ st: document.querySelector('[data-cover]').dataset.state, vis: [...document.querySelectorAll('.dp')].filter((x) => !x.hidden).length, h: document.querySelector('[data-cover]').offsetHeight, ih: innerHeight }));
  t('reduced motion: S11 static (no pinned track), all copy, deck panels static', rm.st === '11' && rm.vis === 4 && rm.h <= rm.ih + 1, rm);
  await close(q);
  q = await mk({ viewport: { width: 1440, height: 900 }, javaScriptEnabled: false }); await q.goto(base, { waitUntil: 'load' }); await q.waitForTimeout(600);
  const nj = await q.evaluate(() => { const im = document.querySelector('.fig-static'); const b1 = document.querySelector('[data-beat="1"]'); return { im: !!(im && im.complete && im.naturalWidth), b1: +getComputedStyle(b1).opacity, cta: +getComputedStyle(document.querySelector('[data-cover] .ctas')).opacity, h: document.querySelector('[data-cover]').offsetHeight }; });
  t('no-JS: the photograph of position 12 + Sūtra 2.46 + CTAs, cover one viewport tall', nj.im && nj.b1 === 1 && nj.cta === 1 && nj.h <= 901, nj);
  await close(q);
}

// ---------------- deck, i18n, forms, dialog (desktop) ----------------
p = await mk({ viewport: { width: 1440, height: 900 } });
await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(500);
{
  const before = await p.evaluate(() => [...document.querySelectorAll('[data-i18n]')].map((e) => e.textContent));
  await p.click('[data-lang="fr"]'); await p.waitForTimeout(200);
  const after = await p.evaluate(() => ({ lang: document.documentElement.lang, txt: [...document.querySelectorAll('[data-i18n]')].map((e) => e.textContent), stored: localStorage.getItem('jv-lang') }));
  const changed = after.txt.filter((x, i) => x !== before[i]).length;
  t('i18n switch flips html[lang] and ≥ 20 strings, choice stored', after.lang === 'fr' && changed >= 20 && after.stored === 'fr', { changed });
  await p.click('[data-lang="en"]');
  await p.evaluate(() => document.querySelector('#deck').scrollIntoView()); await p.waitForTimeout(600);
  let okTabs = true;
  for (const id of TAB_ORDER) { await p.click(`[data-tab="${id}"]`); await p.waitForTimeout(150); const r = await p.evaluate((id) => ({ h: location.hash, vis: [...document.querySelectorAll('.dp')].filter((x) => !x.hidden).map((x) => x.id) }), id); if (r.h !== '#' + id || r.vis.join() !== id) okTabs = false; }
  t('each chapter tab switches the panel and updates the hash', okTabs);
  await p.click(`[data-tab="${LAST_TAB}"]`); await p.focus(`[data-tab="${LAST_TAB}"]`); await p.keyboard.press('ArrowRight'); await p.waitForTimeout(150);
  t('keyboard ArrowRight wraps to the first chapter', (await p.evaluate(() => document.activeElement.dataset.tab)) === FIRST_TAB);
  await p.click('[data-tab="classes"]'); await p.click('[data-tab="register"]'); await p.goBack(); await p.waitForTimeout(250);
  t('back button restores the previous panel', (await p.evaluate(() => [...document.querySelectorAll('.dp')].find((x) => !x.hidden).id)) === 'classes');
  await p.click('[data-tab="about"]'); await p.waitForTimeout(1300);
  t('counters settle on the exact published values', (await p.evaluate(() => [...document.querySelectorAll('[data-count]')].map((e) => e.textContent).join())) === '12,8,4');
  const chap = await p.evaluate(() => ({ no: document.querySelector('[data-chapter-no]').textContent, vis: getComputedStyle(document.querySelector('[data-chapter]')).visibility }));
  t('header chapter indicator follows the deck', chap.no === '02' && chap.vis === 'visible', chap);
  // §4b / §4c
  const gaps = []; const under = [];
  for (const id of ['about', 'classes', 'register', 'contact']) { await p.click(`[data-tab="${id}"]`); await p.evaluate(() => document.querySelector('#deck').scrollIntoView()); await p.waitForTimeout(400);
    gaps.push(await p.evaluate(() => document.querySelector('.deck__nav').getBoundingClientRect().top - document.querySelector('[data-hdr]').getBoundingClientRect().bottom));
    under.push(await p.evaluate(() => { const h = document.querySelector('[data-hdr]').getBoundingClientRect(); const n = document.querySelector('.deck__nav').getBoundingClientRect(); const pn = [...document.querySelectorAll('.dp')].find((x) => !x.hidden); const w = document.createTreeWalker(pn, NodeFilter.SHOW_TEXT); let bad = 0; for (let t; (t = w.nextNode());) { if (!t.textContent.trim()) continue; const r = document.createRange(); r.selectNodeContents(t); for (const b of r.getClientRects()) if (b.bottom > h.top && b.top < n.bottom && b.height) bad++; } return bad; })); }
  t('R3 §4b tab row top − header bottom ≤ 8 px on every deck view (desktop)', gaps.every((g) => g <= 8 && g >= -1), gaps);
  t('R3 §4c no text box under the header/tab row after show(id) (desktop)', under.every((n) => n === 0), under);
  const ph = await p.evaluate(() => ['about', 'classes', 'register', 'contact'].map((id) => { const e = document.getElementById(id); const was = e.hidden; e.hidden = false; const h = e.offsetHeight; e.hidden = was; return h; }));
  t('deck panels ≤ 1 viewport (900) on desktop', ph.every((h) => h <= LIMITS.panelDesktop), ph);
  // §8a, §8b, §8d
  await p.click('[data-tab="classes"]'); await p.waitForTimeout(200);
  const pr = await p.evaluate(() => { const e = [...document.querySelectorAll('[data-i18n="price"]')]; const r = e[0].getBoundingClientRect(); const cards = document.querySelector('#classes .cards').getBoundingClientRect(); const cs = getComputedStyle(e[0]); return { n: e.length, lines: Math.round(r.height / parseFloat(cs.lineHeight)), span: r.width >= cards.width - 2, color: cs.color }; });
  t('R3 §8a "Price on request" once, one line spanning the three offerings, warm accent', pr.n === 1 && pr.lines === 1 && pr.span && pr.color === 'rgb(154, 90, 18)', pr);
  await p.click('[data-tab="contact"]'); await p.waitForTimeout(200);
  const ct = await p.evaluate(() => { const rows = [...document.querySelectorAll('#contact .crow')].filter((r) => !r.hidden); const ul = document.querySelector('#contact .contact').getBoundingClientRect(); const ph = rows.filter((r) => /\+33 7 54 28 72 10/.test(r.textContent)); const foot = document.querySelector('.foot').textContent; return { rows: rows.length, full: rows.every((r) => r.getBoundingClientRect().width >= ul.width - 2), rule: rows.every((r) => getComputedStyle(r).borderBottomStyle === 'solid' && getComputedStyle(r).borderTopWidth === '0px'), phoneRows: ph.length, wa: ph[0] && !!ph[0].querySelector('a[href^="https://wa.me/"]') && !!ph[0].querySelector('a[href^="tel:"]'), footPhone: /\+33/.test(foot), footLinks: [...document.querySelectorAll('.foot__links a')].map((a) => a.getAttribute('href')) }; });
  t('R3 §8b contact: full-width hairline list, phone + WhatsApp in one row, footer = email + Instagram + Privacy (no number)', ct.rows === 3 && ct.full && ct.rule && ct.phoneRows === 1 && ct.wa && !ct.footPhone && ct.footLinks.join() === 'mailto:jeevanagogula.gj22@gmail.com,https://www.instagram.com/jeevana.gogula/,/privacy/', ct);
  t('R3 §8d cover rail: no "A traditional sequence…" dek', !/traditional sequence|séquence traditionnelle/i.test(await p.evaluate(() => document.querySelector('[data-rail]').textContent)));
  t('footer: ProdCraft credit links prodcraft.fyi with rel=noopener, no mailto; Privacy link', await p.evaluate(() => { const a = document.querySelector('.foot__sig a'); return a.href === 'https://prodcraft.fyi/' && a.rel === 'noopener' && !document.querySelector('.foot__sig a[href^="mailto:"]') && !!document.querySelector('.foot a[href="/privacy/"]'); }));
  t('dead-link guard: zero href="#" / empty tel: links in DOM (phone + WhatsApp live)', await p.evaluate(() => document.querySelectorAll('a[href="#"], a[href="tel:"], a[href=""]').length === 0 && !!document.querySelector('a[href="tel:+33754287210"]:not([hidden])') && !!document.querySelector('a[href="https://wa.me/33754287210"]:not([hidden])')));
  // F24 newsletter never opens while focus is in a form / Register active (fresh visitor who has not seen the dialog)
  const pd = p; p = await mk({ viewport: { width: 1440, height: 900 } }, { seen: false }); await p.goto(base, { waitUntil: 'load' }); await p.waitForTimeout(300);
  await p.evaluate(() => { document.querySelector('[data-tab="register"]').click(); document.querySelector('#deck').scrollIntoView(); document.querySelector('[data-reg] [name="name"]').focus({ preventScroll: true }); }); await p.waitForTimeout(1800);
  const closed1 = await p.evaluate(() => !document.querySelector('[data-news]').open);
  await p.evaluate(() => document.activeElement.blur()); await p.waitForTimeout(400);
  const closed2 = await p.evaluate(() => !document.querySelector('[data-news]').open);
  t('F24 newsletter dialog stays closed while focus is in the register form and while Register is active (> delay)', closed1 && closed2);
  // newsletter dialog after deck activation (leave Register first)
  await p.click('[data-tab="about"]'); await p.waitForTimeout(1800);
  const op = await p.evaluate(() => document.querySelector('[data-news]').open);
  const fields = await p.evaluate(() => { const f = document.querySelector('[data-news] form'); return { email: !!f.querySelector('[name="email"][type="email"][required]'), phone: !!f.querySelector('[name="phone"][type="tel"]:not([required])'), consent: !!f.querySelector('[name="consent"][required]'), no: /No thanks/.test(f.querySelector('[data-news-close]').textContent) }; });
  await p.keyboard.press('Escape'); await p.waitForTimeout(200);
  const closed = await p.evaluate(() => !document.querySelector('[data-news]').open);
  await p.evaluate(() => { window.scrollBy(0, -600); }); await p.waitForTimeout(400); await p.evaluate(() => document.querySelector('#deck').scrollIntoView()); await p.waitForTimeout(1600);
  t('newsletter dialog opens after deck activation, closes on Esc, never reopens after close', op && closed && (await p.evaluate(() => !document.querySelector('[data-news]').open)));
  t('newsletter dialog: email required, phone optional (tel), consent required, "No thanks"', Object.values(fields).every(Boolean), fields);
  t('newsletter page: 0 console errors', p._errs.length === 0, p._errs.slice(0, 3));
  await close(p); p = pd;
  await p.click('[data-tab="register"]'); await p.waitForTimeout(200);

  // inline errors
  await p.click('[data-reg] button[type="submit"]'); await p.waitForTimeout(200);
  const er = await p.evaluate(() => [...document.querySelectorAll('[data-reg] .f__err')].map((e) => e.textContent));
  await p.click('[data-lang="fr"]'); await p.waitForTimeout(150);
  const erFr = await p.evaluate(() => [...document.querySelectorAll('[data-reg] .f__err')].map((e) => e.textContent));
  await p.click('[data-lang="en"]');
  t('F26 inline error text under invalid fields (name, email, consent), EN and FR', er.length === 3 && er.includes('Please fill in this field.') && er.includes('Please tick the box to agree.') && erFr.includes('Merci de remplir ce champ.'), { er, erFr });
  // failed submit → mailto carries the typed fields; 429 shows the WhatsApp fallback
  await p.unroute('**/api/**'); await p.route('**/api/register', (r) => r.fulfill({ status: 429, contentType: 'application/json', body: '{"ok":false,"error":"rate_limited"}' }));
  await p.fill('[data-reg] [name="name"]', 'Test Person'); await p.fill('[data-reg] [name="email"]', 'test@example.com'); await p.check('[data-reg] [name="consent"]', { force: true });
  await p.click('[data-reg] button[type="submit"]'); await p.waitForTimeout(500);
  const fb = await p.evaluate(() => ({ err: !document.querySelector('[data-reg-err]').hidden, mail: decodeURIComponent(document.querySelector('[data-reg-mail]').getAttribute('href')), wa: !document.querySelector('[data-fallback]').hidden }));
  t('F26 failed submit: mailto fallback body carries the typed fields; 429 shows the WhatsApp fallback line', fb.err && /name: Test Person/.test(fb.mail) && /email: test@example\.com/.test(fb.mail) && fb.wa, fb);
  await p.unroute('**/api/register'); await p.route('**/api/**', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: '{"ok":true}' }));
  await p.click('[data-reg] button[type="submit"]'); await p.waitForTimeout(500);
  t('register form posts to /api/register and shows success (mocked fetch)', await p.evaluate(() => !document.querySelector('[data-reg-ok]').hidden && document.querySelector('[data-reg]').hidden));
  // page height budget beyond the cover track
  const hh = await p.evaluate(() => ({ H: document.documentElement.scrollHeight, cover: document.querySelector('[data-cover]').offsetHeight, ov: Math.max(0, -parseFloat(getComputedStyle(document.querySelector('[data-fold]')).marginTop)) }));
  t('desktop page height beyond the 14-vh cover track ≤ 3,400 px (v1 budget 7,000 − its 4-vh cover)', hh.H - hh.cover + hh.ov <= LIMITS.otherDesktop, { total: hh.H, rest: hh.H - hh.cover + hh.ov });
  const own = p._errs.filter((e) => !/status of 429 .*\/api\/register/.test(e)); // the 429 was injected by the fallback test above
  t('desktop deck/forms: 0 console errors (besides the injected 429)', own.length === 0, own.slice(0, 3));
}
await close(p);

// deep link
{ const q = await mk({ viewport: { width: 1440, height: 900 } }); await q.goto(base + '#register', { waitUntil: 'load' }); await q.waitForTimeout(500); t('deep link /#register opens the Register panel', await q.evaluate(() => !document.getElementById('register').hidden && document.getElementById('about').hidden)); await close(q); }

// drum (desktop): hinge changes with scroll, open at track end, captions, rotateY ≤ 35°
{
  const q = await mk({ viewport: { width: 1440, height: 900 } }); await q.goto(base, { waitUntil: 'load' }); await q.waitForTimeout(300);
  const at = async (f) => { const y = await q.evaluate((f) => { const e = document.querySelector('[data-fold]'); return e.offsetTop + (e.offsetHeight - innerHeight) * f; }, f); await scrollTo(q, y, 500); return q.evaluate(() => [...document.querySelectorAll('.plate')].map((p) => { const m = new DOMMatrix(getComputedStyle(p).transform); const ang = Math.abs(Math.atan2(m.m13, m.m11) * 180 / Math.PI); const r = p.getBoundingClientRect(); const vis = Math.max(0, Math.min(r.bottom, innerHeight) - Math.max(r.top, 0)) / r.height; return { tr: getComputedStyle(p).transform, ang, op: +getComputedStyle(p).opacity, cap: +getComputedStyle(p.querySelector('figcaption')).opacity, vis }; })); };
  const a0 = await at(-0.3), a1 = await at(0.2), a2 = await at(1);
  t('drum hinge transform changes with scroll', a0[0].tr !== a1[0].tr || a0[2].tr !== a1[2].tr);
  t('drum fully open by track end (rise 1: no transform, opacity 1)', a2.every((x) => x.op === 1 && (x.tr === 'none' || /matrix3d\(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1\)|matrix\(1, 0, 0, 1, 0, 0\)/.test(x.tr))), a2.map((x) => x.tr));
  const all = [...a0, ...a1, ...a2];
  t('R3 §8c drum: captions opacity 1 once a card is ≥ 30 % visible, third card ≥ .9 when in view at track end, rotateY ≤ 35°', all.every((x) => x.ang <= 35.01) && all.every((x) => x.vis < 0.3 || x.cap === 1 || x.op < 0.6) && a2[2].op >= 0.9, all.map((x) => [+x.ang.toFixed(1), x.cap, +x.vis.toFixed(2)]));
  await close(q);
}

// ---------------- mobile ----------------
for (const dev of ['Pixel 7', 'iPhone 13']) {
  const q = await mk({ ...devices[dev] }); await q.goto(base, { waitUntil: 'load' }); await q.waitForTimeout(4200);
  const ov = await q.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  if (dev === 'Pixel 7') {
    await goState(q, 2, 700);
    const m = await q.evaluate(() => { const r = document.querySelector('[data-railm]'); const fig = document.querySelector('.fig.is-on').getBoundingClientRect(); const rr = r.getBoundingClientRect(); return { txt: r.innerText.replace(/\s+/g, ' ').trim(), below: rr.top >= fig.bottom - 2, rail: getComputedStyle(document.querySelector('[data-rail]')).display, copyTop: document.querySelector('.beats').getBoundingClientRect().bottom <= fig.top + 1, cta: document.querySelector('[data-cover] .ctas').getBoundingClientRect().bottom <= innerHeight - 24, hint: Math.abs(document.querySelector('[data-hint]').getBoundingClientRect().left + document.querySelector('[data-hint]').getBoundingClientRect().width / 2 - innerWidth / 2) <= 2 }; });
    t('phones: copy block above the figure, reduced rail "03 / 12 · Pādahastāsana · Exhale" + mantra under it, CTAs above the safe area, scroll hint centred', /^03 \/ 12 · Pādahastāsana · Exhale Om Sūryāya Namaḥ — to the one who induces activity$/.test(m.txt) && m.below && m.rail === 'none' && m.copyTop && m.cta && m.hint, m);
    await q.evaluate(() => document.querySelector('#practice').scrollIntoView()); await q.waitForTimeout(800);
    const fo = await q.evaluate(() => { const s = document.querySelector('[data-spread]'); const cs = getComputedStyle(s); const pl = [...document.querySelectorAll('.plate')]; const hb = document.querySelector('[data-hdr]').getBoundingClientRect().bottom; return { snap: cs.scrollSnapType, ox: cs.overflowX, t3: pl.every((p) => getComputedStyle(p).transform === 'none'), fit: pl.every((p) => p.getBoundingClientRect().width <= innerWidth), first: document.querySelector('.fold__head').getBoundingClientRect().top - hb, coverHidden: getComputedStyle(document.querySelector('.cover__pin')).visibility === 'hidden', bar: document.querySelector('[data-mbar]').classList.contains('is-on'), hdrBg: getComputedStyle(document.querySelector('[data-hdr]')).backgroundColor }; });
    t('mobile drum is a horizontal snap-scroll (no 3D), plates fit the viewport', /x/.test(fo.snap) && fo.ox === 'auto' && fo.t3 && fo.fit, fo);
    t('R3 §4b mobile-foldout: drum first element top − header bottom ≤ 24 px; cover hidden, opaque paper header', fo.first <= 24 && fo.first >= -1 && fo.coverHidden && fo.hdrBg === PAPER_RGB, fo);
    t('R3 §8e mobile bar: off while the drum is on screen', !fo.bar);
    await q.evaluate(() => document.querySelector('#deck').scrollIntoView()); await q.waitForTimeout(700);
    const mb = await q.evaluate(() => { const m = document.querySelector('[data-mbar]'); const r = m.getBoundingClientRect(); return { on: m.classList.contains('is-on'), h: r.height }; });
    t('R3 §8e mobile bar: on in the deck, ≤ 55 px tall', mb.on && mb.h <= 55, mb);
    const tabs = await q.evaluate(() => { const ul = document.querySelector('.deck__nav ul'); return { mask: getComputedStyle(document.querySelector('.deck__nav'), '::after').content !== 'none', gap: document.querySelector('.deck__nav').getBoundingClientRect().top - document.querySelector('[data-hdr]').getBoundingClientRect().bottom }; });
    t('mobile deck: tab fade mask present; tab row under the header (≤ 8 px)', tabs.mask && tabs.gap <= 8, tabs);
    const ph = await q.evaluate(() => ['about', 'classes', 'register', 'contact'].map((id) => { const e = document.getElementById(id); const was = e.hidden; e.hidden = false; const h = e.offsetHeight; e.hidden = was; return h; }));
    t('mobile deck panels ≤ 2 viewports (1830)', ph.every((h) => h <= LIMITS.panelMobile), ph);
    const hh = await q.evaluate(() => ({ H: document.documentElement.scrollHeight, cover: document.querySelector('[data-cover]').offsetHeight, ov: Math.max(0, -parseFloat(getComputedStyle(document.querySelector('[data-fold]')).marginTop)) }));
    t('mobile page height beyond the 10-vh cover track ≤ 7,300 px (v1 budget 9,000 − its cover)', hh.H - hh.cover + hh.ov <= LIMITS.otherMobile, { total: hh.H, rest: hh.H - hh.cover + hh.ov });
    t('Pixel 7: no horizontal overflow', ov <= 0, { ov });
  }
  t(`${dev}: 0 console errors`, q._errs.length === 0 && ov <= 0, q._errs.slice(0, 3));
  await close(q);
}

// ---------------- 4K (§6) ----------------
{
  const q = await mk({ viewport: { width: 3840, height: 2160 } }); await q.goto(base, { waitUntil: 'load' }); await goState(q, 4, 700);
  const k = await q.evaluate(() => { const nav = document.querySelector('.lang button'); const rail = document.querySelector('[data-rail]'); const kids = [...rail.children].map((c) => c.getBoundingClientRect()); const top = Math.min(...kids.map((r) => r.top)), bot = Math.max(...kids.map((r) => r.bottom)); const col = rail.getBoundingClientRect(); return { nav: parseFloat(getComputedStyle(nav).fontSize), gloss: parseFloat(getComputedStyle(rail.querySelector('[data-rail-key="tr"]')).fontSize), html: parseFloat(getComputedStyle(document.documentElement).fontSize), fill: (bot - top) / col.height }; });
  t('R3 §6 4K: nav ≥ 22 px, rail gloss ≥ 20 px, html ≥ 24 px, rail content fills ≥ 70 % of its column', k.nav >= 22 && k.gloss >= 20 && k.html >= 24 && k.fill >= 0.7, k);
  await close(q);
}

// ---------------- privacy + 404 ----------------
for (const [dev, o] of [['desktop', { viewport: { width: 1440, height: 900 } }], ['Pixel 7', { ...devices['Pixel 7'] }]]) {
  const q = await mk(o); await q.goto(base + 'privacy/', { waitUntil: 'load' }); await q.waitForTimeout(500);
  const pv = await q.evaluate(() => ({ en: getComputedStyle(document.querySelector('[data-lang-block="en"]')).display !== 'none', fr: getComputedStyle(document.querySelector('[data-lang-block="fr"]')).display === 'none', txt: document.body.textContent }));
  await q.click('[data-lang="fr"]'); await q.waitForTimeout(150);
  const pf = await q.evaluate(() => getComputedStyle(document.querySelector('[data-lang-block="en"]')).display === 'none' && getComputedStyle(document.querySelector('[data-lang-block="fr"]')).display !== 'none');
  t(`privacy page (${dev}): 0 console errors; publisher, host address, purposes, retention 24 months, processor, rights, no cookies; FR block toggles`, q._errs.length === 0 && pv.en && pv.fr && pf && /Jeevana Gogula/.test(pv.txt) && /101 Townsend St, San Francisco/.test(pv.txt) && /24 months/.test(pv.txt) && /Cloudflare \(hosting and Workers KV/.test(pv.txt) && /rectification, deletion/.test(pv.txt) && /Cookies: none/.test(pv.txt), q._errs.slice(0, 2));
  await close(q);
}
{
  const q = await mk({ viewport: { width: 1440, height: 900 } }, { lang: 'fr' }); await q.goto(base + 'no-such-page/', { waitUntil: 'load' }); await q.waitForTimeout(400);
  const n = await q.evaluate(() => ({ h: document.querySelector('h1').textContent, sig: document.querySelector('.foot__sig a').href, lang: document.documentElement.lang }));
  const own = q._errs.filter((e) => !/status of 404/.test(e)); // the document itself is served with HTTP 404 by design
  t('404 page: 0 console errors (besides its own 404 status), signature present, honours the saved language (fr)', own.length === 0 && n.h === 'Cette page se repose.' && n.sig === 'https://prodcraft.fyi/' && n.lang === 'fr', n);
  await close(q);
}
t('no external request on load except the Cloudflare beacon (all pages, all runs)', external.every((u) => /^https:\/\/static\.cloudflareinsights\.com\/beacon\.min\.js$/.test(u)), [...new Set(external)].slice(0, 5));

await b.close();
let pwv = '?'; try { pwv = JSON.parse(readFileSync('/opt/node22/lib/node_modules/playwright/package.json', 'utf8')).version; } catch {}
let pil = '?'; try { pil = execFileSync('python3', ['-c', 'import PIL;print(PIL.__version__)']).toString().trim(); } catch {}
const pass = R.filter((x) => x.ok).length;
writeFileSync(join(HERE, 'functional.json'), JSON.stringify({ date: new Date().toISOString().slice(0, 10), pass, total: R.length, playwright: pwv, pillow: pil, sizes: { html: statSync(join(SITE, 'index.html')).size, css: statSync(join(SITE, 'css/styles.css')).size, js: statSync(join(SITE, 'js/main.js')).size, i18n: statSync(join(SITE, 'js/i18n.js')).size }, results: R }, null, 1));
console.log(`\n${pass}/${R.length}`);
process.exit(pass === R.length ? 0 : 1);
