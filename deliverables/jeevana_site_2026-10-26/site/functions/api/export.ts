// GET /api/export?type=news|reg — Basic-auth CSV download for Jeevana.
// Credentials from env EXPORT_USER / EXPORT_PASS; when either is unset every request is 401.
import { Env } from './_lib';

function unauthorized(): Response {
  return new Response('Authentication required', { status: 401, headers: { 'WWW-Authenticate': 'Basic realm="Jeevana export", charset="UTF-8"', 'Cache-Control': 'no-store' } });
}

function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}

function cell(v: unknown): string {
  let s = String(v ?? '');
  if (/^[=+\-@\t\r]/.test(s)) s = "'" + s; // spreadsheet formula injection guard
  return '"' + s.replace(/"/g, '""') + '"';
}

export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
  if (!env.EXPORT_USER || !env.EXPORT_PASS) return unauthorized();
  const h = request.headers.get('Authorization') || '';
  if (!h.startsWith('Basic ')) return unauthorized();
  let user = '', pass = '';
  try { const dec = atob(h.slice(6)); const i = dec.indexOf(':'); user = dec.slice(0, i); pass = dec.slice(i + 1); } catch { return unauthorized(); }
  if (!safeEqual(user, env.EXPORT_USER) || !safeEqual(pass, env.EXPORT_PASS)) return unauthorized();
  if (!env.JEEVANA_KV) return new Response('KV not bound', { status: 500 });
  const type = new URL(request.url).searchParams.get('type') === 'reg' ? 'reg' : 'news';
  const cols = type === 'reg' ? ['ts', 'name', 'email', 'phone', 'class', 'level', 'message', 'lang'] : ['ts', 'email', 'phone', 'lang', 'source'];
  const rows: string[] = [cols.join(',')];
  let cursor: string | undefined;
  do {
    const page = await env.JEEVANA_KV.list({ prefix: type + ':', cursor });
    for (const k of page.keys) {
      const raw = await env.JEEVANA_KV.get(k.name);
      if (!raw) continue;
      try { const r = JSON.parse(raw) as Record<string, unknown>; rows.push(cols.map((c) => cell(r[c])).join(',')); } catch { /* skip corrupt */ }
    }
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  return new Response(rows.join('\r\n') + '\r\n', {
    headers: { 'Content-Type': 'text/csv; charset=utf-8', 'Content-Disposition': `attachment; filename="jeevana-${type}.csv"`, 'Cache-Control': 'no-store' },
  });
};
