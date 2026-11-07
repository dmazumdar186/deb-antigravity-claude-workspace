// Host -> site resolution and CORS for public endpoints. Unknown Host is a 404 upstream.

import { csvList } from './util.js';

export function siteForHost(env, hostname) {
  let map;
  try {
    map = JSON.parse(env.HOST_SITE_MAP || '{}');
  } catch {
    return null;
  }
  if (!map || typeof map !== 'object') return null;
  const host = String(hostname || '').toLowerCase().replace(/:\d+$/, '').replace(/\.$/, '');
  const site = Object.prototype.hasOwnProperty.call(map, host) ? map[host] : null;
  return site === 'ie' || site === 'uk' ? site : null;
}

export function inboxFor(env, site) {
  return site === 'uk' ? env.APPLY_INBOX_UK : env.APPLY_INBOX_IE;
}

/** CORS headers for a public response, or null when the Origin is not allowed. Same-origin is always allowed. */
export function corsHeaders(request, env) {
  const origin = request.headers.get('Origin');
  if (!origin) return {};
  const self = new URL(request.url).origin;
  if (origin === self) return {};
  if (csvList(env.ALLOWED_ORIGINS).includes(origin)) {
    return { 'Access-Control-Allow-Origin': origin, Vary: 'Origin' };
  }
  return null;
}

export function preflight(request, env) {
  const cors = corsHeaders(request, env);
  if (cors === null) return new Response(null, { status: 403 });
  return new Response(null, {
    status: 204,
    headers: {
      ...cors,
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Access-Control-Max-Age': '600',
    },
  });
}
