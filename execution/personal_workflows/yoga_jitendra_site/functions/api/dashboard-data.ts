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
  if (!raw) {
    return jsonResponse(emptyFallbackRollup(range), 200);
  }

  // Return the pre-computed rollup verbatim. The Cache-Control: no-store
  // above ensures we don't serve stale via any intermediary cache.
  return new Response(raw, {
    status: 200,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
};
