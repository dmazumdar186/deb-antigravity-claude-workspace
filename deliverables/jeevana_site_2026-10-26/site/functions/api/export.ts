// GET /api/export — Basic-auth CSV download for Jeevana with both lists (newsletter + registrations).
// ?type=news|reg narrows to one list. Note: KV list reads ~1,000 keys per page; the loop pages through, but
// one request reading > ~1,000 values may hit the Workers subrequest limit (runbook: export per type).
import { Env, logError } from './_lib';
import { guard } from './_auth';

function cell(v: unknown): string {
  let s = String(v ?? '');
  if (/^[=+\-@\t\r]/.test(s)) s = "'" + s; // spreadsheet formula injection guard
  return '"' + s.replace(/"/g, '""') + '"';
}
const COLS: Record<string, string[]> = {
  news: ['consent_ts', 'email', 'phone', 'lang', 'source', 'consent_text'],
  reg: ['ts', 'name', 'email', 'phone', 'class', 'level', 'message', 'lang', 'consent_text'],
};

export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
  const denied = await guard(env, request); if (denied) return denied;
  if (!env.JEEVANA_KV) return new Response('storage unavailable', { status: 503 });
  const q = new URL(request.url).searchParams.get('type');
  const types = q === 'reg' || q === 'news' ? [q] : ['news', 'reg'];
  try {
    const out: string[] = [];
    for (const type of types) {
      const cols = COLS[type];
      out.push(['list', ...cols].join(','));
      let cursor: string | undefined;
      do {
        const page = await env.JEEVANA_KV.list({ prefix: type + ':', cursor });
        for (const k of page.keys) {
          const raw = await env.JEEVANA_KV.get(k.name);
          if (!raw) continue;
          try { const r = JSON.parse(raw) as Record<string, unknown>; out.push([cell(type), ...cols.map((c) => cell(r[c]))].join(',')); } catch { /* skip corrupt */ }
        }
        cursor = page.list_complete ? undefined : page.cursor;
      } while (cursor);
      out.push('');
    }
    return new Response(out.join('\r\n'), {
      headers: { 'Content-Type': 'text/csv; charset=utf-8', 'Content-Disposition': `attachment; filename="jeevana-${types.join('-')}.csv"`, 'Cache-Control': 'no-store' },
    });
  } catch (err) {
    logError('export', err);
    return new Response('internal error', { status: 500 });
  }
};
