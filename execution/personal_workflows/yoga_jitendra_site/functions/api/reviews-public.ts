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
  // Added 2026-08-04. Not stored in KV — computed at read-time from the
  // silent-now fingerprint so historical bad rows are contained without a
  // KV migration. See `date_provenance` block below.
  date_provenance?: 'provided' | 'unknown';
}

// 2026-08-04 — the 5da525b fix stopped the silent-now default at write time,
// but did NOT retroactively repair historical KV records already stamped with
// `submitted_at === approved_at` (to the millisecond). Those still deceive
// public visitors ("juillet 2026" for a Google review that's actually from
// 2024). Rather than mutate KV blind, tag those records at read-time so the
// SSG + client renderer can show "Date pending verification" instead of a
// falsely-precise month. When Jitendra backfills real dates via the
// moderation UI (edit action, or GBP API when the quota approval lands),
// the fingerprint clears itself.
//
// Heuristic: verified imports (verified=true) whose submitted_at and
// approved_at are within 60 seconds of each other. User submissions
// (verified=false) are NOT flagged — for on-site form submissions, a
// moderator who approves within seconds is a valid, correct pattern.
const SILENT_NOW_WINDOW_MS = 60 * 1000;
function computeDateProvenance(r: ApprovedReview): 'provided' | 'unknown' {
  if (!r.verified) return 'provided';
  if (!r.submitted_at || !r.approved_at) return 'provided';
  const s = Date.parse(r.submitted_at);
  const a = Date.parse(r.approved_at);
  if (!Number.isFinite(s) || !Number.isFinite(a)) return 'provided';
  if (Math.abs(a - s) < SILENT_NOW_WINDOW_MS) return 'unknown';
  return 'provided';
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

  // Tag each record with date_provenance BEFORE sorting so records with
  // unknown provenance don't out-rank real ones by a bogus submitted_at.
  for (const r of reviews) {
    r.date_provenance = computeDateProvenance(r);
  }

  // Sort: featured first, then newest-first. Records with unknown provenance
  // sort by approved_at (the only trustworthy timestamp on them). Records
  // with known provenance sort by submitted_at (the actual review date).
  reviews.sort((a, b) => {
    if (a.featured !== b.featured) return a.featured ? -1 : 1;
    const aDate =
      (a.date_provenance === 'unknown' ? a.approved_at : a.submitted_at) ||
      a.approved_at ||
      '';
    const bDate =
      (b.date_provenance === 'unknown' ? b.approved_at : b.submitted_at) ||
      b.approved_at ||
      '';
    return bDate.localeCompare(aDate);
  });

  const total = reviews.reduce((s, r) => s + (Number(r.rating) || 0), 0);
  const avg = reviews.length ? Math.round((total / reviews.length) * 10) / 10 : null;

  const unknownCount = reviews.reduce(
    (n, r) => n + (r.date_provenance === 'unknown' ? 1 : 0),
    0,
  );

  return jsonResponse(
    {
      count: reviews.length,
      average_rating: avg,
      as_of: new Date().toISOString(),
      // Surface so /api/health and the acceptance gate can alarm when this
      // number rises unexpectedly. A backfill run lowers it; a regression
      // in write-side validation raises it.
      unknown_date_count: unknownCount,
      reviews,
    },
    { cacheSeconds: fresh ? 0 : 60 },
  );
};
