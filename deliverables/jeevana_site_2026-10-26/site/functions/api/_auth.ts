// Basic auth shared by /api/export and /api/stats: env EXPORT_USER / EXPORT_PASS; unset -> always 401.
import { Env, rateLimited } from './_lib';

export function unauthorized(): Response {
  return new Response('Authentication required', { status: 401, headers: { 'WWW-Authenticate': 'Basic realm="Jeevana export", charset="UTF-8"', 'Cache-Control': 'no-store' } });
}

// Constant-time compare on equal-length padded strings (length is not leaked by an early return).
export function safeEqual(a: string, b: string): boolean {
  const n = Math.max(a.length, b.length, 64);
  const pa = a.padEnd(n, '\0'), pb = b.padEnd(n, '\0');
  let r = a.length ^ b.length;
  for (let i = 0; i < n; i++) r |= pa.charCodeAt(i) ^ pb.charCodeAt(i);
  return r === 0;
}

// null = authorised; otherwise the response to return (401 or 429). 10 attempts / 10 min / IP.
export async function guard(env: Env, request: Request): Promise<Response | null> {
  if (await rateLimited(env, request, 'export', 10)) return new Response('Too many requests', { status: 429, headers: { 'Retry-After': '600' } });
  if (!env.EXPORT_USER || !env.EXPORT_PASS) return unauthorized();
  const h = request.headers.get('Authorization') || '';
  if (!h.startsWith('Basic ')) return unauthorized();
  let user = '', pass = '';
  try { const dec = atob(h.slice(6)); const i = dec.indexOf(':'); user = dec.slice(0, i); pass = dec.slice(i + 1); } catch { return unauthorized(); }
  const okU = safeEqual(user, env.EXPORT_USER), okP = safeEqual(pass, env.EXPORT_PASS);
  return okU && okP ? null : unauthorized();
}
