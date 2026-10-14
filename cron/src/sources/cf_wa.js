// Cloudflare Web Analytics source — Phase C-cfwa.
//
// Queries the CF Analytics GraphQL API for pageview + visit metrics
// aggregated to the given date. Uses the `rumPageloadEventsAdaptiveGroups`
// dataset which is documented (Beta) and exposed on all plans that have
// Web Analytics enabled — including the free tier for zones with a beacon
// token.
//
// Endpoint:
//   POST https://api.cloudflare.com/client/v4/graphql
// Headers:
//   Authorization: Bearer <CF_ANALYTICS_TOKEN>  (Zone:Analytics:Read + Account Analytics:Read)
//   Content-Type: application/json
// Body: { query, variables }
//
// The Zone tag (siteTag for RUM) is looked up from CF_ZONE_HOSTNAME on first
// call and cached in KV to avoid a second round-trip. See resolveSiteTag().
//
// WhatsApp-tap counting: primary path is the /wa-out Pages Function that
// writes event:wa:* keys to KV; those are counted in the aggregator, not
// here. CF WA custom events remain unverified on free tier as of
// 2026-07-21 — layered in only after a Phase-0 spike (plan §3.5).

const API_URL = "https://api.cloudflare.com/client/v4/graphql";
const SITE_TAG_KEY = "cache:cfwa_site_tag";

/**
 * Look up the RUM siteTag (Web Analytics beacon token) for the configured
 * hostname. Three sources tried in order:
 *   1. env.CF_WA_SITE_TAG (wrangler.toml [vars]) — fastest, zero roundtrips
 *   2. KV cache from a prior list() lookup — 24h TTL
 *   3. Fresh /rum/site_info/list call — matches on host substring
 *
 * Returns null only if all three fail; caller degrades cleanly.
 */
async function resolveSiteTag(env) {
  // Path 1: explicit pin. Preferred — matches the token the beacon ships
  // in the frontend, and handles CF's hostname-match quirks (e.g. "www."
  // prefix mismatches, capitalization).
  if (env.CF_WA_SITE_TAG) return env.CF_WA_SITE_TAG;

  const cached = await env.DASHBOARD_KV.get(SITE_TAG_KEY);
  if (cached) return cached;

  if (!env.CF_ACCOUNT_ID) return null;

  const listResp = await fetch(
    `https://api.cloudflare.com/client/v4/accounts/${env.CF_ACCOUNT_ID}/rum/site_info/list`,
    { headers: { Authorization: `Bearer ${env.CF_ANALYTICS_TOKEN}` } },
  );
  if (!listResp.ok) {
    const text = await listResp.text();
    console.error(`cfwa site_info/list failed: status=${listResp.status} body_len=${text.length}`);
    return null;
  }
  const listData = await listResp.json();
  const sites = listData?.result || [];
  // Match on host containing the configured hostname (handles www.-prefix
  // mismatches). Case-insensitive.
  const wanted = env.CF_ZONE_HOSTNAME.toLowerCase();
  const match = sites.find((s) => {
    const h = (s.host || "").toLowerCase();
    return h === wanted || h === `www.${wanted}` || h.endsWith(`.${wanted}`);
  });
  if (!match) return null;

  const siteTag = match.site_tag;
  await env.DASHBOARD_KV.put(SITE_TAG_KEY, siteTag, { expirationTtl: 86400 });
  return siteTag;
}

// GraphQL query: single-day pageview + visit + unique-visitor counts + top
// countries + top referrers for the given date, filtered by siteTag.
//
// Uses `rumPageloadEventsAdaptiveGroups` (Beta but generally available on
// zones with Web Analytics). If CF changes the schema in future, the query
// error is caught and the source is marked degraded.
const QUERY = `
query WebAnalytics($accountTag: String!, $siteTag: String!, $start: String!, $end: String!) {
  viewer {
    accounts(filter: { accountTag: $accountTag }) {
      totals: rumPageloadEventsAdaptiveGroups(
        filter: { siteTag: $siteTag, date_geq: $start, date_leq: $end }
        limit: 1
      ) {
        count
        sum { visits }
      }
      by_country: rumPageloadEventsAdaptiveGroups(
        filter: { siteTag: $siteTag, date_geq: $start, date_leq: $end }
        limit: 5
        orderBy: [count_DESC]
      ) {
        count
        dimensions { countryName }
      }
      by_referrer: rumPageloadEventsAdaptiveGroups(
        filter: { siteTag: $siteTag, date_geq: $start, date_leq: $end }
        limit: 5
        orderBy: [count_DESC]
      ) {
        count
        dimensions { refererHost }
      }
    }
  }
}`;

export async function fetchCfWa(env, dateStr) {
  if (!env.CF_ANALYTICS_TOKEN) {
    throw new Error("CF_ANALYTICS_TOKEN not set (needs Zone:Analytics:Read + Account Analytics:Read)");
  }
  if (!env.CF_ACCOUNT_ID) {
    throw new Error("CF_ACCOUNT_ID not set");
  }
  if (!env.CF_ZONE_HOSTNAME) {
    throw new Error("CF_ZONE_HOSTNAME not set in wrangler.toml [vars]");
  }

  const siteTag = await resolveSiteTag(env);
  if (!siteTag) {
    throw new Error(
      `no Web Analytics site found for hostname "${env.CF_ZONE_HOSTNAME}" in account ${env.CF_ACCOUNT_ID}. ` +
        "Enable Web Analytics for this hostname in the CF dashboard first.",
    );
  }

  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${env.CF_ANALYTICS_TOKEN}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      query: QUERY,
      variables: {
        accountTag: env.CF_ACCOUNT_ID,
        siteTag,
        start: dateStr,
        end: dateStr,
      },
    }),
  });
  if (!resp.ok) {
    const text = await resp.text();
    console.error(`cfwa GraphQL failed: status=${resp.status} body_len=${text.length}`);
    throw new Error(`cfwa GraphQL failed: ${resp.status}`);
  }
  const payload = await resp.json();
  if (payload.errors && payload.errors.length > 0) {
    const first = payload.errors[0];
    console.error(`cfwa GraphQL returned errors: ${first?.message || "unknown"}`);
    throw new Error(`cfwa GraphQL errors: ${first?.message || "unknown"}`);
  }

  const account = payload?.data?.viewer?.accounts?.[0] || {};
  const totals = account.totals?.[0] || { count: 0, sum: { visits: 0 } };
  const pageviews = totals.count ?? 0;
  const visits = totals.sum?.visits ?? 0;

  return {
    date: dateStr,
    pageviews,
    visits,
    top_countries: (account.by_country || []).map((r) => ({
      country: r.dimensions?.countryName || "unknown",
      count: r.count ?? 0,
    })),
    top_referrers: (account.by_referrer || []).map((r) => ({
      referrer: r.dimensions?.refererHost || "direct",
      count: r.count ?? 0,
    })),
  };
}
