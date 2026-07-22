// Cloudflare Pages Function: /api/reviews-public
//
// PUBLIC read-only endpoint returning approved reviews as JSON. Whitelisted
// in _middleware.ts (bypasses Basic-Auth) because build-time hydration and
// public visitors both need to read it.
//
// Response shape:
//   {
//     count: number,
//     average_rating: number | null,
//     as_of: string (ISO),
//     reviews: [
//       { id, name, rating, body, source, source_url, lang,
//         submitted_at, approved_at, featured, verified }
//     ]
//   }
//
// Reviews are returned newest-first, with `featured=true` items pinned at
// the top. Response is cached for 60s at the edge to protect the KV read
// budget under scrape traffic; sync_reviews.mjs at build time sees fresh
// data via the ?fresh=1 query param.

export interface Env {
  DASHBOARD_KV?: KVNamespace;
}

interface ApprovedReview {
  id: string;
  name: string;
  rating: number;
  body: string;
  source: string;
  source_url: string | null;
  lang: 'fr' | 'en';
  submitted_at: string;
  approved_at: string;
  featured: boolean;
  verified: boolean;
}

const KEY_PREFIX = 'review:approved:';

function jsonResponse(body: unknown, opts: { status?: number; cacheSeconds?: number } = {}): Response {
  const status = opts.status ?? 200;
  const cache = opts.cacheSeconds ?? 60;
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': cache > 0 ? `public, max-age=${cache}, s-maxage=${cache}` : 'no-store',
      'Access-Control-Allow-Origin': '*',
    },
  });
}

export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
  if (!env.DASHBOARD_KV) {
    return jsonResponse(
      { count: 0, average_rating: null, as_of: new Date().toISOString(), reviews: [], warning: 'kv_unbound' },
      { status: 200, cacheSeconds: 0 },
    );
  }

  const url = new URL(request.url);
  const fresh = url.searchParams.get('fresh') === '1';

  // Paginate through the full approved list. Free-tier KV list caps at 1000
  // per call; use cursor-based iteration to be safe.
  const reviews: ApprovedReview[] = [];
  let cursor: string | undefined = undefined;
  let iterations = 0;
  do {
    const listRes: KVNamespaceListResult<unknown, string> = await env.DASHBOARD_KV.list({
      prefix: KEY_PREFIX,
      limit: 1000,
      cursor,
    });
    for (const k of listRes.keys) {
      const raw = await env.DASHBOARD_KV.get(k.name);
      if (!raw) continue;
      try {
        reviews.push(JSON.parse(raw) as ApprovedReview);
      } catch (e) {
        console.error('reviews-public: corrupt entry', k.name, e);
      }
    }
    cursor = listRes.list_complete ? undefined : (listRes as { cursor?: string }).cursor;
    iterations += 1;
    if (iterations > 10) {
      // Same 10-page hard cap as reviews-admin. Log so a real overflow
      // is visible instead of silently dropping items from the public feed.
      console.warn(`reviews-public: list truncated at 10 pages; ${reviews.length} approved items returned, more may exist`);
      break;
    }
  } while (cursor);

  // Sort: featured first, then newest-first by approved_at.
  reviews.sort((a, b) => {
    if (a.featured !== b.featured) return a.featured ? -1 : 1;
    return b.approved_at.localeCompare(a.approved_at);
  });

  const total = reviews.reduce((s, r) => s + (Number(r.rating) || 0), 0);
  const avg = reviews.length ? Math.round((total / reviews.length) * 10) / 10 : null;

  return jsonResponse(
    {
      count: reviews.length,
      average_rating: avg,
      as_of: new Date().toISOString(),
      reviews,
    },
    { cacheSeconds: fresh ? 0 : 60 },
  );
};
