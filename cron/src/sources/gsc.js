// GSC (Google Search Console) source — Phase B.
//
// Calls the Search Analytics API twice: once grouped by [query] and once
// grouped by [page], for the given date (single day, startDate === endDate).
// Sums the totals across rows to get impressions + clicks + ctr + avg
// position, then keeps the top-5 queries and top-5 pages for the
// drill-down UI planned in V0.5.
//
// Endpoint:
//   POST https://www.googleapis.com/webmasters/v3/sites/{siteUrl}/searchAnalytics/query
// Body: { startDate, endDate, dimensions: ["query"|"page"], rowLimit: 5 }
// Auth: Bearer <access_token from oauth.js>
//
// Verified 2026-07-21 rate limits (developers.google.com/webmaster-tools/limits):
//   20 QPS/user, 200 QPM/user, 1200 QPM/project, 100M QPD/project, 25k rows/req
// Our 1 call/day * 2 dimensions = 2 QPD — 8 orders of magnitude below ceiling.
//
// Site URL encoding: sc-domain: properties (Domain-verified) use the exact
// string "sc-domain:example.com" URL-encoded. wrangler.toml sets GSC_SITE_URL
// to the pre-encoded string.

import { getAccessToken } from "../oauth.js";

const API_BASE = "https://www.googleapis.com/webmasters/v3/sites";

async function queryDimension(env, accessToken, dateStr, dimension) {
  const siteUrl = encodeURIComponent(env.GSC_SITE_URL);
  const url = `${API_BASE}/${siteUrl}/searchAnalytics/query`;
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      startDate: dateStr,
      endDate: dateStr,
      dimensions: [dimension],
      rowLimit: 5,
      dataState: "final", // exclude the last ~2 days of provisional data
    }),
  });
  if (!resp.ok) {
    const text = await resp.text();
    console.error(`gsc ${dimension} query failed: status=${resp.status} body_len=${text.length}`);
    throw new Error(`gsc ${dimension} query failed: ${resp.status}`);
  }
  return resp.json();
}

export async function fetchGsc(env, dateStr) {
  if (!env.GSC_SITE_URL) {
    throw new Error("GSC_SITE_URL not set in wrangler.toml [vars]");
  }
  const accessToken = await getAccessToken(env, "gsc");

  // Two dimensions in parallel — no ordering dependency; each is a separate quota unit.
  const [queryResp, pageResp] = await Promise.all([
    queryDimension(env, accessToken, dateStr, "query"),
    queryDimension(env, accessToken, dateStr, "page"),
  ]);

  // GSC returns per-row impressions/clicks/ctr/position. Sum across returned
  // rows for totals. Rate-limited to rowLimit=5 above, so the "total" is
  // technically top-5 sum, not global-total. For a full site-wide total we'd
  // need a separate query with no dimensions:
  const totalResp = await fetch(
    `${API_BASE}/${encodeURIComponent(env.GSC_SITE_URL)}/searchAnalytics/query`,
    {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        startDate: dateStr,
        endDate: dateStr,
        dimensions: [],
        rowLimit: 1,
        dataState: "final",
      }),
    },
  );
  if (!totalResp.ok) {
    const text = await totalResp.text();
    console.error(`gsc totals query failed: status=${totalResp.status} body_len=${text.length}`);
    throw new Error(`gsc totals query failed: ${totalResp.status}`);
  }
  const totals = await totalResp.json();
  const t = totals.rows?.[0] || { impressions: 0, clicks: 0, ctr: 0, position: 0 };

  return {
    date: dateStr,
    impressions: t.impressions ?? 0,
    clicks: t.clicks ?? 0,
    ctr: t.ctr ?? 0,
    position: t.position ?? 0,
    top_queries: (queryResp.rows || []).map((r) => ({
      q: r.keys?.[0] ?? "",
      impressions: r.impressions ?? 0,
      clicks: r.clicks ?? 0,
    })),
    top_pages: (pageResp.rows || []).map((r) => ({
      p: r.keys?.[0] ?? "",
      impressions: r.impressions ?? 0,
      clicks: r.clicks ?? 0,
    })),
  };
}
