// Cloudflare Pages Function: GET /api/newsletter-count
//
// Admin-only. Returns the count of newsletter:sub:* entries in KV plus a
// 7-day delta (subs created in the last 7 days). Used by the dashboard
// Subscribers hero tile (Slice 5 of 2026-08-05 session 3 plan).
//
// Auth: HTTP Basic. Same DASHBOARD_USER + DASHBOARD_PASS as the rest of
// the dashboard-admin surface. Returns 401 if creds missing / wrong.
//
// KV pagination: KV list() returns up to 1000 keys per call. Follows
// cursor if list_complete === false. Realistically the sub list is
// <1000 for the foreseeable future; the loop is defensive.
//
// Cost: enumerates KV keys — 1 KV list op per 1000 keys. For a 100-sub
// list this is basically free (single list, no gets — we get the ts from
// key metadata written at put-time... except metadata isn't returned by
// list(). So we DO have to get() each value to check ts for the 7-day
// window. That's 100 gets. Cache the whole thing in KV for 5 minutes to
// avoid re-listing on every dashboard page load.

export interface Env {
  DASHBOARD_KV?: KVNamespace;
  DASHBOARD_USER?: string;
  DASHBOARD_PASS?: string;
}

const CACHE_TTL_SECONDS = 300; // 5 min

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
    },
  });
}

function checkBasicAuth(request: Request, env: Env): boolean {
  if (!env.DASHBOARD_USER || !env.DASHBOARD_PASS) return false;
  const header = request.headers.get('Authorization') || '';
  if (!header.startsWith('Basic ')) return false;
  try {
    const decoded = atob(header.slice(6));
    const idx = decoded.indexOf(':');
    if (idx < 0) return false;
    const user = decoded.slice(0, idx);
    const pass = decoded.slice(idx + 1);
    return user === env.DASHBOARD_USER && pass === env.DASHBOARD_PASS;
  } catch {
    return false;
  }
}

interface SubRecord {
  email?: string;
  ts?: string;
  first_seen_ts?: string;   // anchored on first-ever submit; used for the "last 7d" delta
  method?: string;
}

async function computeCounts(kv: KVNamespace): Promise<{ total: number; last_7d: number }> {
  let cursor: string | undefined;
  let total = 0;
  let last7d = 0;
  const sevenDaysAgoMs = Date.now() - 7 * 24 * 60 * 60 * 1000;

  do {
    const page = await kv.list({ prefix: 'newsletter:sub:', cursor, limit: 1000 });
    for (const entry of page.keys) {
      total += 1;
      const raw = await kv.get(entry.name);
      if (!raw) continue;
      try {
        const sub = JSON.parse(raw) as SubRecord;
        // Prefer first_seen_ts (anchored on first submit) so a re-subscribe
        // doesn't inflate the 7-day new-count. Fall back to ts for records
        // written before that field existed.
        const anchor = sub.first_seen_ts || sub.ts;
        if (anchor) {
          const t = Date.parse(anchor);
          if (Number.isFinite(t) && t >= sevenDaysAgoMs) last7d += 1;
        }
      } catch {
        // Skip corrupt record; keep counting.
      }
    }
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);

  return { total, last_7d: last7d };
}

export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
  if (!checkBasicAuth(request, env)) {
    return new Response(JSON.stringify({ ok: false, error: 'unauthorized' }), {
      status: 401,
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'WWW-Authenticate': 'Basic realm="dashboard"',
      },
    });
  }

  if (!env.DASHBOARD_KV) {
    return json({ ok: false, error: 'kv_unbound' }, 500);
  }

  // --- Serve from cache when fresh ---
  const cacheKey = 'newsletter:count:cache';
  const cached = await env.DASHBOARD_KV.get(cacheKey);
  if (cached) {
    try {
      const parsed = JSON.parse(cached) as { total: number; last_7d: number; computed_at: string };
      return json({ ok: true, ...parsed, from_cache: true });
    } catch {
      // Corrupt cache — fall through and recompute.
    }
  }

  const { total, last_7d } = await computeCounts(env.DASHBOARD_KV);
  const payload = { total, last_7d, computed_at: new Date().toISOString() };
  await env.DASHBOARD_KV.put(cacheKey, JSON.stringify(payload), {
    expirationTtl: CACHE_TTL_SECONDS,
  });
  return json({ ok: true, ...payload, from_cache: false });
};
