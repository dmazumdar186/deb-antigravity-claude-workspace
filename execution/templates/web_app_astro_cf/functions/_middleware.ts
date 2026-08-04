// Global Pages middleware.
//
// - Basic-Auth gate for /dashboard/* and /api/* (except explicit whitelist).
// - Simple KV-backed token-bucket rate limit (per IP, per minute).
// - CORS handled per-endpoint; global default is same-origin only.
//
// Replace/remove any of these blocks that don't apply to your project.

interface Env {
  DASHBOARD_USER?: string;
  DASHBOARD_PASS?: string;
  APP_KV?: KVNamespace;
}

const PROTECTED = /^\/(dashboard|api)(\/|$)/;
const PUBLIC_API_ALLOWLIST = new Set<string>([
  '/api/health',
]);

// Token-bucket per (ip, minute). 60 req / min / ip default.
const RATE_LIMIT = 60;
const RATE_WINDOW_S = 60;

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

async function rateLimitBlocked(kv: KVNamespace | undefined, ip: string, path: string): Promise<boolean> {
  if (!kv) return false;
  const minute = Math.floor(Date.now() / (RATE_WINDOW_S * 1000));
  const key = `rl:${ip}:${minute}`;
  const raw = await kv.get(key);
  const n = raw ? parseInt(raw, 10) : 0;
  if (n >= RATE_LIMIT) return true;
  await kv.put(key, String(n + 1), { expirationTtl: RATE_WINDOW_S * 2 });
  return false;
}

export const onRequest: PagesFunction<Env> = async (context) => {
  const url = new URL(context.request.url);
  const ip = context.request.headers.get('cf-connecting-ip') ?? 'anon';

  // Rate-limit every request (cheap, KV-backed).
  if (await rateLimitBlocked(context.env.APP_KV, ip, url.pathname)) {
    return new Response('Rate limit exceeded', { status: 429, headers: { 'Retry-After': '60' } });
  }

  // Public paths + non-protected paths pass through.
  if (!PROTECTED.test(url.pathname)) return context.next();

  const normalized = url.pathname.endsWith('/') && url.pathname.length > 1
    ? url.pathname.slice(0, -1) : url.pathname;
  if (PUBLIC_API_ALLOWLIST.has(normalized)) return context.next();

  // Basic Auth for the rest.
  const expectedUser = context.env.DASHBOARD_USER ?? 'admin';
  const expectedPass = context.env.DASHBOARD_PASS;
  if (!expectedPass) {
    return new Response('Auth not configured (DASHBOARD_PASS missing).', {
      status: 503, headers: { 'Cache-Control': 'no-store' },
    });
  }
  const authz = context.request.headers.get('authorization') ?? '';
  if (!authz.startsWith('Basic ')) {
    return new Response('Auth required', {
      status: 401,
      headers: { 'WWW-Authenticate': 'Basic realm="<PROJECT_NAME>"' },
    });
  }
  const [u, p] = atob(authz.slice(6)).split(':', 2);
  if (!timingSafeEqual(u ?? '', expectedUser) || !timingSafeEqual(p ?? '', expectedPass)) {
    return new Response('Invalid credentials', {
      status: 401,
      headers: { 'WWW-Authenticate': 'Basic realm="<PROJECT_NAME>"' },
    });
  }

  return context.next();
};
