// ASSET Voyages, option B demo: one Cloudflare Worker, D1 database, static assets, daily cron reset.
import { htmlResponse, getCookie, randomToken, ipHash, sha256hex, safeEqual } from './lib.js';
import { errorPage } from './views.js';
import { ensureReady, nightly, validSbx, effectiveSbx } from './data.js';

const SBX_COOKIE = '__Host-av_sbx';

// Test runs only: count D1 rows written by this request (meta.rows_written) and return it in x-d1-rows-written, so the
// suite can measure what a real session costs against the free-plan write budget.
function meterDb(db, acc) {
  const raw = new WeakMap();
  const add = (meta) => { acc.n += (meta && (meta.rows_written ?? meta.changes)) || 0; };
  const wrap = (st) => {
    const p = new Proxy(st, {
      get(t, k) {
        if (k === 'bind') return (...a) => wrap(t.bind(...a));
        if (k === 'run' || k === 'all') return async (...a) => { const r = await t[k](...a); add(r.meta); return r; };
        if (k === 'first') return async (col) => { const r = await t.all(); add(r.meta); const row = (r.results || [])[0]; return row === undefined ? null : col ? row[col] : row; };
        const v = t[k]; return typeof v === 'function' ? v.bind(t) : v;
      },
    });
    raw.set(p, st);
    return p;
  };
  return new Proxy(db, {
    get(t, k) {
      if (k === 'prepare') return (q) => wrap(t.prepare(q));
      if (k === 'batch') return async (stmts) => { const rs = await t.batch(stmts.map((x) => raw.get(x) || x)); for (const r of rs) add(r.meta); return rs; };
      const v = t[k]; return typeof v === 'function' ? v.bind(t) : v;
    },
  });
}
import { catalogue, congressPage, submitEnquiry, confirmation } from './public.js';
import { consoleRoute } from './console.js';

const SECURITY_HEADERS = {
  'content-security-policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'",
  'x-content-type-options': 'nosniff',
  'x-frame-options': 'DENY',
  'referrer-policy': 'same-origin',
  'x-robots-tag': 'noindex, nofollow',
  'permissions-policy': 'camera=(), microphone=(), geolocation=(), payment=()',
  'cross-origin-opener-policy': 'same-origin',
  'strict-transport-security': 'max-age=31536000',
};
function secure(res) {
  const out = new Response(res.body, res);
  for (const [k, v] of Object.entries(SECURITY_HEADERS)) out.headers.set(k, v);
  return out;
}

async function route(req, env) {
  const url = new URL(req.url);
  const path = url.pathname.replace(/\/{2,}/g, '/');
  const m = req.method;

  if (path.startsWith('/assets/') || path === '/robots.txt' || path === '/favicon.ico') {
    const res = await env.ASSETS.fetch(req);
    const out = new Response(res.body, res);
    if (res.ok && (path.startsWith('/assets/fonts/') || url.searchParams.has('v'))) out.headers.set('cache-control', 'public, max-age=31536000, immutable');
    return out;
  }
  if (path === '/' && (m === 'GET' || m === 'HEAD')) return catalogue(req, env);
  let mm;
  if ((mm = /^\/congres\/([a-z0-9-]{1,120})\/?$/.exec(path)) && (m === 'GET' || m === 'HEAD')) return congressPage(req, env, mm[1]);
  if (path === '/demande' && m === 'POST') return submitEnquiry(req, env);
  if (path === '/demande/confirmation' && m === 'GET') return confirmation(req, env);
  if (path === '/console' || path.startsWith('/console/')) return consoleRoute(req, env, path);
  if (m !== 'GET' && m !== 'HEAD') return new Response('Méthode non autorisée', { status: 405, headers: { allow: 'GET' } });
  return htmlResponse(errorPage({ status: 404, title: 'Page introuvable', text: 'Cette adresse ne correspond à aucune page du site.' }), 404);
}

export default {
  async fetch(req, env) {
    let res;
    let newSbx = null;
    let meterRef = null;
    try {
      const path = new URL(req.url).pathname;
      if (path.startsWith('/assets/') || path === '/robots.txt' || path === '/favicon.ico') {
        res = await route(req, env);
      } else {
        await ensureReady(env);
        // Per-browser sandbox: an HttpOnly cookie names this browser's private copy of the demo data.
        const fromCookie = getCookie(req, SBX_COOKIE);
        const sbx = validSbx(fromCookie) ? fromCookie : (newSbx = randomToken(18));
        const scoped = Object.create(env);
        scoped.SBX = sbx;
        scoped.SBX_EFF = newSbx ? '' : await effectiveSbx(env, sbx);
        scoped.IP_HASH = await ipHash(env, req);
        const testKey = req.headers.get('x-demo-test');
        // Test-run key: a Worker SECRET (DEMO_TEST_KEY, 32+ random bytes, never in code or wrangler.toml). Missing or short
        // secret = no exemption. Compared in constant time on SHA-256 digests (equal length whatever the input).
        const secret = env.DEMO_TEST_KEY;
        const keyOk = !!(testKey && typeof secret === 'string' && secret.length >= 43 && safeEqual(await sha256hex(testKey), await sha256hex(secret)));
        // x-demo-real: 1 keeps the meter but drops the exemption, to measure what a real visitor's session costs.
        scoped.TEST_RUN = keyOk && req.headers.get('x-demo-real') !== '1';
        if (keyOk) { scoped.METER = { n: 0 }; scoped.DB = meterDb(env.DB, scoped.METER); }
        meterRef = scoped;
        res = await route(req, scoped);
      }
    } catch (err) {
      if (err && err.code === 'SBX_LIMIT') {
        // Sandbox caps reached: back to the same page, read-only seed, with a calm banner (never a bare 429).
        const ref = req.headers.get('referer');
        let back = '/';
        try { const u = new URL(ref); if (u.origin === new URL(req.url).origin) back = u.pathname; } catch { back = '/'; }
        res = new Response(null, { status: 303, headers: { location: `${back}?demo=complet` } });
      } else {
        console.error('request failed', err && err.message);
        res = htmlResponse(errorPage({ status: 500, title: 'Erreur temporaire', text: 'Le service n’a pas pu répondre. Réessayez dans un instant ; rien n’a été enregistré en double.' }), 500);
      }
    }
    const out = secure(res);
    if (meterRef && meterRef.METER) out.headers.set('x-d1-rows-written', String(meterRef.METER.n));
    if (newSbx) out.headers.append('set-cookie', `${SBX_COOKIE}=${newSbx}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=172800`);
    return out;
  },
  async scheduled(event, env, ctx) {
    ctx.waitUntil(nightly(env));
  },
};
