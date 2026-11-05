// ASSET Voyages, option B demo: one Cloudflare Worker, D1 database, static assets, daily cron reset.
import { htmlResponse } from './lib.js';
import { errorPage } from './views.js';
import { ensureReady, resetDemo } from './data.js';
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
    if (path.startsWith('/assets/fonts/')) out.headers.set('cache-control', 'public, max-age=31536000, immutable');
    return out;
  }
  await ensureReady(env);
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
    try {
      res = await route(req, env);
    } catch (err) {
      console.error('request failed', err && err.message);
      res = htmlResponse(errorPage({ status: 500, title: 'Erreur temporaire', text: 'Le service n’a pas pu répondre. Réessayez dans un instant ; rien n’a été enregistré en double.' }), 500);
    }
    return secure(res);
  },
  async scheduled(event, env, ctx) {
    ctx.waitUntil(resetDemo(env, { keepSessions: false }));
  },
};
