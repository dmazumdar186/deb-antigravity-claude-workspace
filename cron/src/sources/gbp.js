// GBP (Google Business Profile) source — Phase C-gbp.
//
// Guarded on external access approval per plan §7.2b. When GBP_LOCATION_ID
// is empty (default), throws a "degraded" reason immediately — V0.1 ships
// with the other 3 sources healthy and this one honestly labeled as
// pending. Fill in GBP_LOCATION_ID (wrangler.toml [vars]) after Google
// approves the API access request.
//
// Endpoint (once unblocked):
//   GET https://businessprofileperformance.googleapis.com/v1/{locationId}:fetchMultiDailyMetricsTimeSeries
//   ?dailyMetrics=BUSINESS_IMPRESSIONS_DESKTOP_MAPS
//   &dailyMetrics=BUSINESS_IMPRESSIONS_MOBILE_MAPS
//   &dailyMetrics=BUSINESS_IMPRESSIONS_DESKTOP_SEARCH
//   &dailyMetrics=BUSINESS_IMPRESSIONS_MOBILE_SEARCH
//   &dailyMetrics=WEBSITE_CLICKS
//   &dailyMetrics=CALL_CLICKS
//   &dailyMetrics=BUSINESS_DIRECTION_REQUESTS
//   &dailyRange.startDate.year=YYYY&dailyRange.startDate.month=M&dailyRange.startDate.day=D
//   &dailyRange.endDate.year=YYYY&dailyRange.endDate.month=M&dailyRange.endDate.day=D
// Auth: Bearer <access token from oauth.js scope=gbp>
//
// Verified 2026-07-21: new Cloud projects start at ZERO quota. Approval
// takes days-to-weeks. Once approved, per-project rate limits are
// generous for this call volume (1/day).

import { getAccessToken } from "../oauth.js";

const API_BASE = "https://businessprofileperformance.googleapis.com/v1";

// Which metrics to pull. Order matches how we sum them in the aggregator.
const DAILY_METRICS = [
  "BUSINESS_IMPRESSIONS_DESKTOP_MAPS",
  "BUSINESS_IMPRESSIONS_MOBILE_MAPS",
  "BUSINESS_IMPRESSIONS_DESKTOP_SEARCH",
  "BUSINESS_IMPRESSIONS_MOBILE_SEARCH",
  "WEBSITE_CLICKS",
  "CALL_CLICKS",
  "BUSINESS_DIRECTION_REQUESTS",
];

function isoDateToParts(dateStr) {
  const [y, m, d] = dateStr.split("-").map((x) => parseInt(x, 10));
  return { year: y, month: m, day: d };
}

// Sum a metric's time-series entries — GBP returns an array of
// { date: {...}, value: "N" } and we want the total for the requested
// single-day window. `value` is a string per GBP's REST convention.
function sumMetricSeries(entry) {
  if (!entry || !Array.isArray(entry.timeSeries?.datedValues)) return 0;
  return entry.timeSeries.datedValues.reduce((acc, dv) => acc + (parseInt(dv.value, 10) || 0), 0);
}

export async function fetchGbp(env, dateStr) {
  if (!env.GBP_LOCATION_ID) {
    throw new Error(
      "GBP_LOCATION_ID empty — Google Business Profile API access approval pending (plan §7.2b)",
    );
  }
  if (!env.GOOGLE_REFRESH_TOKEN_GBP) {
    throw new Error("GOOGLE_REFRESH_TOKEN_GBP not set — run scripts/get_google_refresh_token.py");
  }

  const accessToken = await getAccessToken(env, "gbp");
  const { year, month, day } = isoDateToParts(dateStr);

  const params = new URLSearchParams();
  for (const m of DAILY_METRICS) params.append("dailyMetrics", m);
  params.set("dailyRange.startDate.year", String(year));
  params.set("dailyRange.startDate.month", String(month));
  params.set("dailyRange.startDate.day", String(day));
  params.set("dailyRange.endDate.year", String(year));
  params.set("dailyRange.endDate.month", String(month));
  params.set("dailyRange.endDate.day", String(day));

  // env.GBP_LOCATION_ID may be either the bare id (e.g. "12345") or the
  // full resource name ("locations/12345"). Normalize.
  const locName = env.GBP_LOCATION_ID.startsWith("locations/")
    ? env.GBP_LOCATION_ID
    : `locations/${env.GBP_LOCATION_ID}`;
  const url = `${API_BASE}/${locName}:fetchMultiDailyMetricsTimeSeries?${params.toString()}`;

  const resp = await fetch(url, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!resp.ok) {
    const text = await resp.text();
    console.error(`gbp fetchMultiDailyMetricsTimeSeries failed: status=${resp.status} body_len=${text.length}`);
    throw new Error(`gbp fetchMultiDailyMetricsTimeSeries failed: ${resp.status}`);
  }
  const payload = await resp.json();
  const series = payload?.multiDailyMetricTimeSeries?.[0]?.dailyMetricTimeSeries || [];

  // Map back into a flat metric->total object.
  const byMetric = {};
  for (const entry of series) {
    byMetric[entry.dailyMetric] = sumMetricSeries(entry);
  }

  const desktopMaps = byMetric.BUSINESS_IMPRESSIONS_DESKTOP_MAPS ?? 0;
  const mobileMaps = byMetric.BUSINESS_IMPRESSIONS_MOBILE_MAPS ?? 0;
  const desktopSearch = byMetric.BUSINESS_IMPRESSIONS_DESKTOP_SEARCH ?? 0;
  const mobileSearch = byMetric.BUSINESS_IMPRESSIONS_MOBILE_SEARCH ?? 0;

  return {
    date: dateStr,
    maps_impressions: desktopMaps + mobileMaps,
    search_impressions: desktopSearch + mobileSearch,
    website_clicks: byMetric.WEBSITE_CLICKS ?? 0,
    call_clicks: byMetric.CALL_CLICKS ?? 0,
    direction_requests: byMetric.BUSINESS_DIRECTION_REQUESTS ?? 0,
    // Raw breakdown for future drill-down UI.
    raw_by_metric: byMetric,
  };
}
