// Bing Webmaster Tools source — Phase C-bing.
//
// Endpoint:
//   GET https://ssl.bing.com/webmaster/api.svc/json/GetRankAndTrafficStats
//   ?siteUrl=<encoded>&apikey=<BING_API_KEY>
// Returns site-wide daily aggregated impressions + clicks. Response shape:
//   { d: [ { __type: "...", Date: "/Date(1721520000000)/", Impressions: N, Clicks: N }, ... ] }
// The "/Date(ms)/" format is Microsoft's SOAP-to-JSON date; parse the ms.
//
// Auth: single apikey query parameter (no OAuth). Key is generated once at
// https://www.bing.com/webmasters/home/api and pasted via wrangler secret put.
//
// Verified 2026-07-21: no official rate-limit doc; unofficial 5 QPS. Our
// 1 call/day is safe.

const API_URL = "https://ssl.bing.com/webmaster/api.svc/json/GetRankAndTrafficStats";

function parseMsDate(msDateStr) {
  // "/Date(1721520000000)/" -> 1721520000000
  const m = /\/Date\((\d+)\)\//.exec(msDateStr || "");
  return m ? parseInt(m[1], 10) : null;
}

function isoDateFromMs(ms) {
  const d = new Date(ms);
  const y = d.getUTCFullYear();
  const mo = String(d.getUTCMonth() + 1).padStart(2, "0");
  const da = String(d.getUTCDate()).padStart(2, "0");
  return `${y}-${mo}-${da}`;
}

export async function fetchBing(env, dateStr) {
  if (!env.BING_API_KEY) {
    throw new Error("BING_API_KEY not set — get one at bing.com/webmasters/home/api");
  }
  if (!env.BING_SITE_URL) {
    throw new Error("BING_SITE_URL not set in wrangler.toml [vars]");
  }

  const url = `${API_URL}?siteUrl=${encodeURIComponent(env.BING_SITE_URL)}&apikey=${encodeURIComponent(env.BING_API_KEY)}`;
  const resp = await fetch(url, {
    headers: { Accept: "application/json" },
  });
  if (!resp.ok) {
    const text = await resp.text();
    console.error(`bing GetRankAndTrafficStats failed: status=${resp.status} body_len=${text.length}`);
    throw new Error(`bing GetRankAndTrafficStats failed: ${resp.status}`);
  }
  const payload = await resp.json();
  const rows = Array.isArray(payload?.d) ? payload.d : [];

  // Find the row matching the requested date. Bing returns a rolling window;
  // we want just the given day. If not present (e.g. request is too recent
  // and Bing hasn't published yet), return zeros with a flag so the aggregator
  // can distinguish "no data yet" from "no traffic."
  const target = rows.find((r) => isoDateFromMs(parseMsDate(r.Date)) === dateStr);
  if (!target) {
    return {
      date: dateStr,
      impressions: 0,
      clicks: 0,
      _no_data: true,
      _note: "Bing has not yet published stats for this date (typically 24-48h lag)",
    };
  }

  return {
    date: dateStr,
    impressions: target.Impressions ?? 0,
    clicks: target.Clicks ?? 0,
  };
}
