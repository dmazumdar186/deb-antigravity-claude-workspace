// Staff auth: Cloudflare Access sits in front of /admin/* and /api/admin/*, and the Worker
// ALSO verifies the Cf-Access-Jwt-Assertion JWT itself (defence in depth): RS256 only,
// signature against the team JWKS, then aud, iss, exp, nbf, then the STAFF_EMAILS allow-list.
// The JWKS fetcher is injectable so tests sign tokens with a locally generated key pair.

import { csvList } from './util.js';

const LEEWAY_S = 60;
const JWKS_TTL_MS = 10 * 60 * 1000;
const HOST_RE = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$/;

export function teamHost(env) {
  const raw = String(env.ACCESS_TEAM_DOMAIN || '').trim().toLowerCase().replace(/^https:\/\//, '').replace(/\/+$/, '');
  return HOST_RE.test(raw) ? raw : null;
}

export function defaultJwksFetcher(host) {
  return async () => {
    const res = await fetch(`https://${host}/cdn-cgi/access/certs`);
    if (!res.ok) throw new Error('jwks_http');
    return res.json();
  };
}

function b64urlToBytes(s) {
  if (typeof s !== 'string' || !/^[A-Za-z0-9_-]*$/.test(s)) throw new Error('b64');
  const pad = s.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((s.length + 3) % 4);
  const bin = atob(pad);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function b64urlJson(s) {
  return JSON.parse(new TextDecoder().decode(b64urlToBytes(s)));
}

/** Per-handler JWKS cache: {keys, at}. Refetched once when a kid is unknown. */
export function createJwksCache(fetcherFor = defaultJwksFetcher) {
  let cache = null;
  return async function getKey(host, kid, nowMs) {
    const load = async () => {
      const doc = await fetcherFor(host)();
      cache = { host, at: nowMs, keys: Array.isArray(doc?.keys) ? doc.keys : [] };
    };
    if (!cache || cache.host !== host || nowMs - cache.at > JWKS_TTL_MS) await load();
    let jwk = cache.keys.find((k) => k.kid === kid);
    if (!jwk) {
      await load();
      jwk = cache.keys.find((k) => k.kid === kid);
    }
    return jwk || null;
  };
}

/**
 * Verify a Cloudflare Access JWT. Returns {ok:true, email, claims} or {ok:false, reason}.
 * Never throws; reasons are codes, never token contents.
 */
export async function verifyAccessJwt(token, env, { getKey, nowMs }) {
  const host = teamHost(env);
  const aud = String(env.ACCESS_AUD || '').trim();
  if (!host || !aud) return { ok: false, reason: 'not_configured' };
  if (typeof token !== 'string' || !token) return { ok: false, reason: 'missing' };
  const parts = token.split('.');
  if (parts.length !== 3 || token.length > 8192) return { ok: false, reason: 'malformed' };
  let header;
  let claims;
  try {
    header = b64urlJson(parts[0]);
    claims = b64urlJson(parts[1]);
  } catch {
    return { ok: false, reason: 'malformed' };
  }
  if (!header || header.alg !== 'RS256' || typeof header.kid !== 'string') return { ok: false, reason: 'alg' };
  let jwk;
  try {
    jwk = await getKey(host, header.kid, nowMs);
  } catch {
    return { ok: false, reason: 'jwks_unavailable' };
  }
  if (!jwk || jwk.kty !== 'RSA') return { ok: false, reason: 'unknown_kid' };
  let valid = false;
  try {
    const key = await crypto.subtle.importKey(
      'jwk',
      { kty: 'RSA', n: jwk.n, e: jwk.e, alg: 'RS256', ext: true },
      { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' },
      false,
      ['verify'],
    );
    valid = await crypto.subtle.verify(
      'RSASSA-PKCS1-v1_5',
      key,
      b64urlToBytes(parts[2]),
      new TextEncoder().encode(`${parts[0]}.${parts[1]}`),
    );
  } catch {
    return { ok: false, reason: 'signature' };
  }
  if (!valid) return { ok: false, reason: 'signature' };

  const now = Math.floor(nowMs / 1000);
  const auds = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
  if (!auds.includes(aud)) return { ok: false, reason: 'aud' };
  if (claims.iss !== `https://${host}`) return { ok: false, reason: 'iss' };
  if (typeof claims.exp !== 'number' || claims.exp + LEEWAY_S < now) return { ok: false, reason: 'expired' };
  if (claims.nbf !== undefined && (typeof claims.nbf !== 'number' || claims.nbf - LEEWAY_S > now)) {
    return { ok: false, reason: 'nbf' };
  }
  if (typeof claims.email !== 'string' || !claims.email) return { ok: false, reason: 'no_email' };
  return { ok: true, email: claims.email.trim().toLowerCase(), claims };
}

/** Full staff check: valid JWT + email on the STAFF_EMAILS allow-list (empty list = nobody). */
export async function authenticateStaff(request, env, deps) {
  const token = request.headers.get('Cf-Access-Jwt-Assertion');
  if (!token) return { ok: false, status: 401, code: 'unauthenticated' };
  const r = await verifyAccessJwt(token, env, deps);
  if (!r.ok) {
    if (r.reason === 'not_configured' || r.reason === 'jwks_unavailable') return { ok: false, status: 503, code: 'auth_unavailable' };
    return { ok: false, status: 401, code: 'unauthenticated' };
  }
  const allow = csvList(env.STAFF_EMAILS).map((e) => e.toLowerCase());
  if (!allow.includes(r.email)) return { ok: false, status: 403, code: 'forbidden' };
  return { ok: true, email: r.email };
}
