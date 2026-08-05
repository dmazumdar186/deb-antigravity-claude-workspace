// Cloudflare Pages Function: /api/dashboard-data
//
// Reads the pre-computed rollup written by the yoga-jitendra-cron Worker
// into DASHBOARD_KV (dashboard:{7d,30d,all}) and serves it back to the
// dashboard frontend. One KV read per request, sub-10 ms.
//
// Query params:
//   ?range=7d   (default)
//   ?range=30d
//   ?range=all
//
// Auth: relies on the existing _middleware.ts Basic-Auth gate. The middleware
// regex `/^\/(dashboard|api)(\/|$)/` already covers /api/dashboard-data.
//
// Failure modes:
//   - KV binding missing        -> 503 with a friendly error body
//   - Unknown range             -> 400
//   - No rollup written yet     -> 200 with an empty-but-valid rollup shape
//                                 and a warning field (bootstrap window)

export interface Env {
  DASHBOARD_KV?: KVNamespace;
}

const VALID_RANGES = new Set(["7d", "30d", "all"]);

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      // no-store: the cron writes daily, but a fresh dashboard load should
      // always get whatever the aggregator wrote most recently.
      "Cache-Control": "no-store",
    },
  });
}

function emptyFallbackRollup(range: string): unknown {
  // Same shape as the aggregator's real output, all fields zeroed. Sent when
  // the KV rollup key doesn't exist yet (bootstrap: cron has not fired) so
  // the frontend has a single code path for parse + render.
  return {
    range,
    as_of: new Date().toISOString(),
    computed_ms: 0,
    sources_healthy: [],
    sources_degraded: ["gsc", "gbp", "bing", "cfwa"],
    hero_tiles: {
      reach: {
        label: "People who found you on Google",
        value: null,
        delta_pct: null,
        sparkline: [],
        top_queries: [],
        source: "Google Search Console",
        as_of: null,
      },
      interest: {
        label: "Clicks on your site and Maps profile",
        value: null,
        delta_pct: null,
        sparkline: [],
        top_pages: [],
        source: "Google Search Console + Business Profile",
        as_of: null,
      },
      conversation: {
        label: "WhatsApp taps from your site",
        value: 0,
        delta_pct: null,
        sparkline: [],
        source: "On-site beacon (/wa-out proxy)",
        as_of: null,
      },
      // Subscribers tile — always locally-sourced (Cloudflare KV, no external
      // dependency). Never "waiting" for a cron; the number is authoritative.
      // Populated post-KV-read in onRequestGet below.
      subscribers: {
        label: "Newsletter subscribers",
        value: 0,
        delta_pct: null,
        sparkline: [],
        source: "Newsletter opt-in popup",
        as_of: null,
      },
    },
    funnel: [
      { label: "Impressions",   value: 0, source: "GSC + Bing + GBP" },
      { label: "Clicks",        value: 0, source: "GSC + GBP + Bing" },
      { label: "WhatsApp taps", value: 0, source: "On-site beacon" },
    ],
    time_series: { labels: [], series: [] },
    // Align labels with the static dashboard-data.json so hydration does NOT
    // replace a labeled zero-donut with an unlabeled empty one (that regression
    // is what makes the tile read as "blank window" on first paint).
    source_split: {
      labels: ["Google Search", "Google Maps", "Bing", "Direct/referrer"],
      values: [0, 0, 0, 0],
      unit: "clicks",
      degraded_source_indices: [0, 1, 2, 3],
    },
    _delta_threshold: 10,
    _warning: "cron has not yet written this rollup; showing empty fallback",
    _pipeline_status: "not_activated",
  };
}

// Subscribers count — enumerated live from KV, cached for 5 min under
// newsletter:count:cache. Same cache key as functions/api/newsletter-count.ts
// so both endpoints share the compute. Cheap for low volumes (<1000 subs);
// re-visit if the list ever crosses 10k.
interface SubRecord { ts?: string; first_seen_ts?: string }
async function computeSubscribers(kv: KVNamespace): Promise<{ total: number; last_7d: number }> {
  const cacheKey = "newsletter:count:cache";
  const cached = await kv.get(cacheKey);
  if (cached) {
    try {
      const parsed = JSON.parse(cached) as { total: number; last_7d: number };
      return { total: parsed.total, last_7d: parsed.last_7d };
    } catch { /* fall through to recompute */ }
  }
  let cursor: string | undefined;
  let total = 0;
  let last7d = 0;
  const sevenDaysAgoMs = Date.now() - 7 * 24 * 60 * 60 * 1000;
  do {
    const page = await kv.list({ prefix: "newsletter:sub:", cursor, limit: 1000 });
    for (const entry of page.keys) {
      total += 1;
      const raw = await kv.get(entry.name);
      if (!raw) continue;
      try {
        const sub = JSON.parse(raw) as SubRecord;
        // Prefer first_seen_ts (anchored on first-ever submit) so a
        // re-subscribe never inflates the 7-day delta. Fall back to ts.
        const anchor = sub.first_seen_ts || sub.ts;
        if (anchor) {
          const t = Date.parse(anchor);
          if (Number.isFinite(t) && t >= sevenDaysAgoMs) last7d += 1;
        }
      } catch { /* skip corrupt */ }
    }
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  const payload = { total, last_7d: last7d };
  await kv.put(cacheKey, JSON.stringify({ ...payload, computed_at: new Date().toISOString() }), {
    expirationTtl: 300,
  });
  return payload;
}

// Inject the subscribers tile into a parsed rollup (or a fallback rollup).
// Idempotent: always overwrites hero_tiles.subscribers with fresh KV counts.
// Guarantees "newsletter" is listed in sources_healthy (it's a local source).
async function withSubscribers(rollup: Record<string, unknown>, kv: KVNamespace): Promise<Record<string, unknown>> {
  const { total, last_7d } = await computeSubscribers(kv);
  const heroTiles = (rollup.hero_tiles ?? {}) as Record<string, unknown>;
  const existing = (heroTiles.subscribers ?? {}) as Record<string, unknown>;
  heroTiles.subscribers = {
    label: existing.label ?? "Newsletter subscribers",
    value: total,
    delta_pct: null,        // absolute count semantics; "delta" surfaced via delta_7d
    delta_7d: last_7d,
    sparkline: [],
    source: existing.source ?? "Newsletter opt-in popup",
    as_of: new Date().toISOString(),
  };
  rollup.hero_tiles = heroTiles;
  // Always mark newsletter as a healthy source — it's local KV, no external dep.
  const healthy = Array.isArray(rollup.sources_healthy) ? (rollup.sources_healthy as string[]) : [];
  if (!healthy.includes("newsletter")) healthy.push("newsletter");
  rollup.sources_healthy = healthy;
  return rollup;
}

export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
  if (!env.DASHBOARD_KV) {
    return jsonResponse({ ok: false, error: "DASHBOARD_KV binding missing on Pages project" }, 503);
  }

  const url = new URL(request.url);
  const range = url.searchParams.get("range") || "7d";
  if (!VALID_RANGES.has(range)) {
    return jsonResponse({ ok: false, error: `unknown range "${range}", expected one of: 7d, 30d, all` }, 400);
  }

  const raw = await env.DASHBOARD_KV.get(`dashboard:${range}`);
  let rollup: Record<string, unknown>;
  if (!raw) {
    rollup = emptyFallbackRollup(range) as Record<string, unknown>;
  } else {
    try {
      rollup = JSON.parse(raw) as Record<string, unknown>;
    } catch {
      rollup = emptyFallbackRollup(range) as Record<string, unknown>;
    }
  }

  // Inject live subscribers count on top of whichever rollup we're serving.
  const withSubs = await withSubscribers(rollup, env.DASHBOARD_KV);

  return jsonResponse(withSubs, 200);
};
