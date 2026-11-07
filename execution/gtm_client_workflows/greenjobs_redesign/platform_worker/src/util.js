// Shared helpers: JSON responses, security headers, hashing, constant-time compare.
// Nothing here logs request data; errors leave the Worker as {error: code} only.

export const SECURITY_HEADERS = {
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'no-referrer',
  'X-Frame-Options': 'DENY',
};

export const CONSOLE_CSP =
  "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'";

export function json(body, status = 200, extra = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', ...SECURITY_HEADERS, ...extra },
  });
}

export function err(code, status, extra = {}) {
  return json({ error: code }, status, extra);
}

export function nowIso(date) {
  return date.toISOString().replace(/\.\d{3}Z$/, 'Z');
}

export function todayUtc(date) {
  return date.toISOString().slice(0, 10);
}

const enc = new TextEncoder();

export async function sha256Hex(text) {
  const buf = await crypto.subtle.digest('SHA-256', enc.encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

// Constant-time string compare: hash both sides so length differences do not leak timing.
export async function safeEqual(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || !a || !b) return false;
  const [ha, hb] = await Promise.all([sha256Hex(a), sha256Hex(b)]);
  let diff = 0;
  for (let i = 0; i < ha.length; i++) diff |= ha.charCodeAt(i) ^ hb.charCodeAt(i);
  return diff === 0;
}

// A uuid-v4-shaped id derived from a seed, so a replayed Idempotency-Key converges on one row.
export async function uuidFromSeed(seed) {
  const h = await sha256Hex(seed);
  const v = h.slice(0, 32).split('');
  v[12] = '4';
  v[16] = '89ab'[parseInt(v[16], 16) & 3];
  const s = v.join('');
  return `${s.slice(0, 8)}-${s.slice(8, 12)}-${s.slice(12, 16)}-${s.slice(16, 20)}-${s.slice(20, 32)}`;
}

export const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function clientIp(request) {
  return request.headers.get('CF-Connecting-IP') || 'unknown';
}

export function intVar(env, name, fallback) {
  const n = Number.parseInt(env[name] ?? '', 10);
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

export function csvList(value) {
  return String(value || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}
