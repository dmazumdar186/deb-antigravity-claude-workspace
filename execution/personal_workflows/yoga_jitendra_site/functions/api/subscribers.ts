// Cloudflare Pages Function: GET /api/subscribers
//
// Admin-only. Lists every `newsletter:sub:*` entry in KV as a JSON array
// (or CSV via ?format=csv). Used by /dashboard/subscribers/ to render the
// operator-facing subscriber table + CSV export.
//
// Auth: HTTP Basic (DASHBOARD_USER + DASHBOARD_PASS) — same gate as the
// _middleware.ts already protects /api/* with. Redundant local check kept
// for defense-in-depth so the API still refuses if middleware ever gets
// bypassed (e.g., internal fetch from another Worker).
//
// KV pagination: KV list() returns up to 1000 keys per call. Follows
// cursor if list_complete === false. For a small list this is a single
// list + N gets (100 gets ≈ 3ms).

export interface Env {
  DASHBOARD_KV?: KVNamespace;
  DASHBOARD_USER?: string;
  DASHBOARD_PASS?: string;
}

interface SubRecord {
  email?: string;
  email_sha256?: string;
  first_seen_ts?: string;
  ts?: string;
  ip_hash?: string;
  consent_text_version?: string;
  source_url?: string;
  lang?: string;
  method?: string;
}

interface SubOut {
  email: string;
  first_seen_ts: string | null;
  last_seen_ts: string | null;
  lang: string;
  source_url: string;
  consent_text_version: string;
  method: string;
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
    },
  });
}

// Accept EITHER the session cookie the middleware stamps (yj_dash_sess) OR a
// raw Authorization: Basic header. Browsers do not auto-attach Basic Auth to
// fetch()/XHR — the middleware's cookie is what makes /dashboard/subscribers/
// hydrate without a second password prompt. The Basic-Auth branch remains for
// curl and internal-Worker callers. Signature format matches _middleware.ts.
async function sessionSig(user: string, pass: string): Promise<string> {
  const buf = new TextEncoder().encode(`${user}:${pass}:yj-dash-v1`);
  const digest = await crypto.subtle.digest('SHA-256', buf);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

function readSessionCookie(request: Request): string | null {
  const header = request.headers.get('Cookie') || '';
  const parts = header.split(/;\s*/);
  for (const part of parts) {
    if (part.startsWith('yj_dash_sess=')) {
      return part.slice('yj_dash_sess='.length);
    }
  }
  return null;
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

async function checkAuth(request: Request, env: Env): Promise<boolean> {
  if (!env.DASHBOARD_PASS) return false;
  const user = env.DASHBOARD_USER || 'debanjan';

  const cookie = readSessionCookie(request);
  if (cookie) {
    const expected = await sessionSig(user, env.DASHBOARD_PASS);
    if (timingSafeEqual(cookie, expected)) return true;
  }

  const header = request.headers.get('Authorization') || '';
  if (header.startsWith('Basic ')) {
    try {
      const decoded = atob(header.slice(6));
      const idx = decoded.indexOf(':');
      if (idx > 0) {
        const u = decoded.slice(0, idx);
        const p = decoded.slice(idx + 1);
        if (timingSafeEqual(u, user) && timingSafeEqual(p, env.DASHBOARD_PASS)) return true;
      }
    } catch {
      /* fall through */
    }
  }
  return false;
}

function csvEscape(v: string): string {
  // Only quote if the value contains a character that would break parsing.
  if (/[",\n\r]/.test(v)) {
    return `"${v.replace(/"/g, '""')}"`;
  }
  return v;
}

async function listSubs(kv: KVNamespace): Promise<SubOut[]> {
  const out: SubOut[] = [];
  let cursor: string | undefined;
  do {
    const page = await kv.list({ prefix: 'newsletter:sub:', cursor, limit: 1000 });
    for (const entry of page.keys) {
      const raw = await kv.get(entry.name);
      if (!raw) continue;
      try {
        const sub = JSON.parse(raw) as SubRecord;
        if (!sub.email) continue;
        out.push({
          email: sub.email,
          first_seen_ts: sub.first_seen_ts || sub.ts || null,
          last_seen_ts: sub.ts || sub.first_seen_ts || null,
          lang: sub.lang || 'fr',
          source_url: sub.source_url || '',
          consent_text_version: sub.consent_text_version || '',
          method: sub.method || 'kv-only-fallback',
        });
      } catch {
        // Skip corrupt record.
      }
    }
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);

  // Sort newest first (by first_seen_ts desc, fall back to last_seen).
  out.sort((a, b) => {
    const ta = Date.parse(a.first_seen_ts || a.last_seen_ts || '') || 0;
    const tb = Date.parse(b.first_seen_ts || b.last_seen_ts || '') || 0;
    return tb - ta;
  });
  return out;
}

export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
  if (!(await checkAuth(request, env))) {
    return new Response(JSON.stringify({ ok: false, error: 'unauthorized' }), {
      status: 401,
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'WWW-Authenticate': 'Basic realm="dashboard"',
        'Cache-Control': 'no-store',
      },
    });
  }

  if (!env.DASHBOARD_KV) {
    return json({ ok: false, error: 'kv_unbound' }, 500);
  }

  const url = new URL(request.url);
  const format = (url.searchParams.get('format') || 'json').toLowerCase();

  let subs: SubOut[];
  try {
    subs = await listSubs(env.DASHBOARD_KV);
  } catch (e) {
    console.error('subscribers: list failed', e);
    return json({ ok: false, error: 'kv_list_failed' }, 500);
  }

  if (format === 'csv') {
    const header = 'email,first_seen_ts,last_seen_ts,lang,source_url,consent_text_version,method';
    const rows = subs.map((s) => [
      csvEscape(s.email),
      csvEscape(s.first_seen_ts || ''),
      csvEscape(s.last_seen_ts || ''),
      csvEscape(s.lang),
      csvEscape(s.source_url),
      csvEscape(s.consent_text_version),
      csvEscape(s.method),
    ].join(','));
    const body = [header, ...rows].join('\r\n') + '\r\n';
    const stamp = new Date().toISOString().slice(0, 10);
    return new Response(body, {
      status: 200,
      headers: {
        'Content-Type': 'text/csv; charset=utf-8',
        'Content-Disposition': `attachment; filename="yoga-jitendra-subscribers-${stamp}.csv"`,
        'Cache-Control': 'no-store',
      },
    });
  }

  return json({
    ok: true,
    total: subs.length,
    subscribers: subs,
    computed_at: new Date().toISOString(),
  });
};
