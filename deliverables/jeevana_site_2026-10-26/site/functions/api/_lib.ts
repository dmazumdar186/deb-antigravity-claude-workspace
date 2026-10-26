// Shared helpers for the Jeevana Pages Functions (subscribe, register, unsubscribe, event, stats, export).
export interface Env {
  JEEVANA_KV?: KVNamespace;
  EXPORT_USER?: string;
  EXPORT_PASS?: string;
  BREVO_API_KEY?: string;
  NOTIFY_TO?: string;
  NOTIFY_FROM?: string;
}

export const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export const PHONE_RE = /^[+\d][\d\s().-]{5,39}$/;
export const RL_WINDOW_SECONDS = 10 * 60; // 10 minutes
export const RL_MAX = 5;                  // 5 attempts / IP / window
export const BODY_MAX = 8 * 1024;         // 8 KB request cap
export const REG_TTL_SECONDS = 60 * 60 * 24 * 730; // registrations kept 24 months (privacy page)
export const NOTIFY_DEFAULT = 'Jeevana.yogawellness@gmail.com';

export function json(body: unknown, status = 200, extra: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', ...extra },
  });
}

export function logError(route: string, error: unknown): void {
  console.error(JSON.stringify({ service: 'jeevana', route, error: String((error as Error)?.message || error), count: 1 }));
}

export function fail(route: string, error: unknown, status = 500): Response {
  logError(route, error);
  return json({ ok: false, error: 'internal' }, status);
}

export function noStore(): Response {
  return json({ ok: false, error: 'storage unavailable' }, 503);
}

export async function sha256Hex(input: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(input));
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, '0')).join('');
}

export function randomHex(bytes: number): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(bytes))).map((x) => x.toString(16).padStart(2, '0')).join('');
}

export function str(v: unknown, max: number): string {
  return String(v ?? '').trim().slice(0, max);
}

export function consentOk(v: unknown): boolean {
  return v === true || v === 'true' || v === 'on';
}

// Per-IP rate limit in KV (`rl:<scope>:<sha256(ip)>`). KV unbound or failing -> allow (logged), never block a visitor on our fault.
export async function rateLimited(env: Env, request: Request, scope: string, max = RL_MAX, windowS = RL_WINDOW_SECONDS): Promise<boolean> {
  if (!env.JEEVANA_KV) return false;
  try {
    const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
    const key = `rl:${scope}:${await sha256Hex('jv::' + ip)}`;
    const now = Math.floor(Date.now() / 1000);
    const raw = await env.JEEVANA_KV.get(key);
    let e = raw ? (JSON.parse(raw) as { count: number; start: number }) : null;
    if (!e || now - e.start > windowS) e = { count: 0, start: now };
    e.count += 1;
    await env.JEEVANA_KV.put(key, JSON.stringify(e), { expirationTtl: windowS + 60 });
    return e.count > max;
  } catch (err) {
    logError('ratelimit:' + scope, err);
    return false;
  }
}

// JSON body with an 8 KB cap (content-length first, then the real text length).
export async function readBody(request: Request): Promise<Record<string, unknown> | null | 'too_large'> {
  const cl = Number(request.headers.get('content-length') || '0');
  if (cl > BODY_MAX) return 'too_large';
  try {
    const text = await request.text();
    if (text.length > BODY_MAX) return 'too_large';
    const b = JSON.parse(text) as unknown;
    return b && typeof b === 'object' && !Array.isArray(b) ? (b as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

export function badBody(b: unknown): Response | null {
  if (b === 'too_large') return json({ ok: false, error: 'too_large' }, 413);
  if (!b) return json({ ok: false, error: 'bad_body' }, 400);
  return null;
}

// Notification to Jeevana (Brevo transactional email) — never blocks or fails the visitor's request.
export async function notify(env: Env, subject: string, lines: string[]): Promise<void> {
  const to = env.NOTIFY_TO || NOTIFY_DEFAULT;
  if (!env.BREVO_API_KEY) { console.log(JSON.stringify({ service: 'jeevana', notify: subject, to, sent: false, reason: 'BREVO_API_KEY unset' })); return; }
  try {
    const r = await fetch('https://api.brevo.com/v3/smtp/email', {
      method: 'POST',
      headers: { 'api-key': env.BREVO_API_KEY, 'Content-Type': 'application/json', accept: 'application/json' },
      body: JSON.stringify({
        sender: { name: 'Jeevana site', email: env.NOTIFY_FROM || to },
        to: [{ email: to }],
        subject,
        textContent: lines.join('\n'),
      }),
    });
    if (!r.ok) logError('notify', `brevo ${r.status}`);
  } catch (err) {
    logError('notify', err);
  }
}
