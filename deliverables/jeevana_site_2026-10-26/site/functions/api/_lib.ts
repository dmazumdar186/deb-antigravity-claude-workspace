// Shared helpers for the Jeevana Pages Functions (subscribe, register, export).
export interface Env {
  JEEVANA_KV?: KVNamespace;
  EXPORT_USER?: string;
  EXPORT_PASS?: string;
}

export const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export const RL_WINDOW_SECONDS = 10 * 60; // 10 minutes
export const RL_MAX = 5;                  // 5 attempts / IP / window

export function json(body: unknown, status = 200, extra: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', ...extra },
  });
}

export async function sha256Hex(input: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(input));
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, '0')).join('');
}

export function str(v: unknown, max: number): string {
  return String(v ?? '').trim().slice(0, max);
}

export function consentOk(v: unknown): boolean {
  return v === true || v === 'true' || v === 'on';
}

// Per-IP rate limit in KV (`rl:<scope>:<sha256(ip)>`). KV unbound -> fail-open (local preview).
export async function rateLimited(env: Env, request: Request, scope: string): Promise<boolean> {
  if (!env.JEEVANA_KV) return false;
  const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
  const key = `rl:${scope}:${await sha256Hex('jv::' + ip)}`;
  const now = Math.floor(Date.now() / 1000);
  const raw = await env.JEEVANA_KV.get(key);
  let e = raw ? (JSON.parse(raw) as { count: number; start: number }) : null;
  if (!e || now - e.start > RL_WINDOW_SECONDS) e = { count: 0, start: now };
  e.count += 1;
  await env.JEEVANA_KV.put(key, JSON.stringify(e), { expirationTtl: RL_WINDOW_SECONDS + 60 });
  return e.count > RL_MAX;
}

export async function readBody(request: Request): Promise<Record<string, unknown> | null> {
  try {
    const b = (await request.json()) as unknown;
    return b && typeof b === 'object' ? (b as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}
