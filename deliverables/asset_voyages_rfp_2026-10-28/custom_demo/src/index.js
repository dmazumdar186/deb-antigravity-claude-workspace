// ASSET Voyages, option B demo: one Cloudflare Worker, D1 database, static assets, daily cron reset.
import { htmlResponse, getCookie, randomToken, ipHash } from './lib.js';
import { errorPage } from './views.js';
import { ensureReady, nightly, validSbx, effectiveSbx } from './data.js';

const SBX_COOKIE = '__Host-av_sbx';
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
    if (newSbx) out.headers.append('set-cookie', `${SBX_COOKIE}=${newSbx}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=172800`);
    return out;
  },
  async scheduled(event, env, ctx) {
    ctx.waitUntil(nightly(env));
  },
};
