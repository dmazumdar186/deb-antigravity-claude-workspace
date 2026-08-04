// Aggregator — Phase D.
//
// Merges snap:<source>:<YYYY-MM-DD> keys into pre-computed dashboard:<range>
// rollups (7d / 30d / all) that the Pages Function serves to the frontend
// with a single sub-10ms KV read. See plan §3.3 for the target rollup shape.
//
// Inputs read from DASHBOARD_KV:
//   - snap:{gsc,gbp,bing,cfwa}:*   per-day per-source snapshots
//   - event:wa:*                    WhatsApp-tap events from /wa-out proxy
//   - latest:<source>               most-recent snap per source
//
// Outputs written to DASHBOARD_KV:
//   - dashboard:7d, dashboard:30d, dashboard:all
//
// Rules:
//   - _delta_threshold: 10 — delta_pct is null when the prior-window
//     baseline is < 10 events. Prevents "1 -> 3 = +200%" cosmetic inflation.
//   - source_split donut: shows clicks (highest-volume metric all sources
//     contribute to), not WA-taps. Degraded sources are included as a
//     hatched slice with 0 value + "no data" label.
//   - conversation hero value: counted from event:wa:* keys in the range
//     window, NOT from CF WA (which is future work per §3.5).
//   - If a source has no snap for a given day, that day contributes 0
//     (not skipped) — so time_series arrays always have `days` entries.

const RANGES = [
  { key: "7d",  days: 7 },
  { key: "30d", days: 30 },
  { key: "all", days: 3650 }, // effectively "since launch"
];

const DELTA_THRESHOLD = 10;
const SOURCES = ["gsc", "gbp", "bing", "cfwa"];
const LAUNCH_DATE = "2026-07-11"; // yogaavecjitendra.fr V2 launch, per DASHBOARD_HANDOFF.md

// -----------------------------------------------------------------------------
// Date helpers — all in Paris local; DST-safe via Intl.DateTimeFormat.
// -----------------------------------------------------------------------------

function parisDate(date) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: "Europe/Paris",
  }).formatToParts(date);
  const y = parts.find((p) => p.type === "year").value;
  const m = parts.find((p) => p.type === "month").value;
  const d = parts.find((p) => p.type === "day").value;
  return `${y}-${m}-${d}`;
}

function isoDatePlus(dateStr, deltaDays) {
  const [y, m, d] = dateStr.split("-").map((x) => parseInt(x, 10));
  const t = Date.UTC(y, m - 1, d) + deltaDays * 86400_000;
  const dt = new Date(t);
  const yy = dt.getUTCFullYear();
  const mm = String(dt.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(dt.getUTCDate()).padStart(2, "0");
  return `${yy}-${mm}-${dd}`;
}

function daysBetween(a, b) {
  const [ya, ma, da] = a.split("-").map((x) => parseInt(x, 10));
  const [yb, mb, db] = b.split("-").map((x) => parseInt(x, 10));
  return Math.round((Date.UTC(yb, mb - 1, db) - Date.UTC(ya, ma - 1, da)) / 86400_000);
}

function dateRange(endDate, days) {
  // Effective days = min(days, days since launch)+1 so "all" doesn't produce
  // an array of 3651 zeros for a two-week-old dashboard.
  const daysSinceLaunch = Math.max(0, daysBetween(LAUNCH_DATE, endDate));
  const effectiveDays = Math.min(days, daysSinceLaunch + 1);
  const out = [];
  for (let i = effectiveDays - 1; i >= 0; i--) {
    out.push(isoDatePlus(endDate, -i));
  }
  return out;
}

// -----------------------------------------------------------------------------
// KV loaders — cached in-memory per aggregation run so each range doesn't
// re-fetch the same snaps. Aggregation happens in one Worker invocation, so
// per-run cache is enough; no persistent memoization needed.
// -----------------------------------------------------------------------------

async function loadSnapsForSource(env, source, dateStrs) {
  // Batch KV.get is not supported on the free-tier plan; issue in parallel.
  // Use Promise.allSettled so one transient KV read failure (e.g. eventual-
  // consistency hiccup on a fresh key) does not poison the whole aggregation
  // for the day. A rejected read is treated as "no data for that day," which
  // is the same code path a missing snap already takes downstream.
  const promises = dateStrs.map(async (d) => {
    const raw = await env.DASHBOARD_KV.get(`snap:${source}:${d}`, { type: "json" });
    return [d, raw];
  });
  const settled = await Promise.allSettled(promises);
  const entries = [];
  for (let i = 0; i < settled.length; i++) {
    const s = settled[i];
    if (s.status === "fulfilled") {
      entries.push(s.value);
    } else {
      // Log the source+date so a systematic KV read problem is visible in
      // wrangler tail; then continue with `null` so the day contributes 0.
      console.warn(`aggregator: KV read failed for snap:${source}:${dateStrs[i]} — ${s.reason?.message || s.reason}`);
      entries.push([dateStrs[i], null]);
    }
  }
  return Object.fromEntries(entries);
}

async function loadWaEventsInWindow(env, startDate, endDate) {
  // event:wa:* keys have the shape event:wa:<iso-timestamp>:<source>. We
  // list all and filter by ISO prefix — cheaper than trying to construct
  // per-day prefixes.
  //
  // KV.list is O(#keys under prefix). With 90d TTL and ~10-100 taps/day
  // typical, this is at most ~9000 keys — one list call takes <100ms.
  let cursor = undefined;
  const events = [];
  do {
    const page = await env.DASHBOARD_KV.list({ prefix: "event:wa:", limit: 1000, cursor });
    for (const k of page.keys) {
      // key format: event:wa:<iso-timestamp>:<source>[:<random-suffix>]
      // (random suffix added 2026-07-21 to prevent same-ms collisions).
      // Both formats supported for backwards compat with keys written before
      // the fix. We only need the date portion of the timestamp — first 10
      // chars of the segment after "event:wa:".
      if (!k.name.startsWith("event:wa:")) continue;
      const rest = k.name.slice("event:wa:".length);
      const day = rest.slice(0, 10); // YYYY-MM-DD
      if (day < startDate || day > endDate) continue;
      // Source is the second-to-last colon-separated segment on new keys,
      // or the last segment on old keys. Both work as long as we don't
      // rely on source names containing colons.
      const parts = rest.split(":");
      // parts[0..2] = "YYYY-MM-DDTHH", "MM", "SS.sssZ" (ISO timestamp has 2 colons)
      // For new keys: parts.length >= 5, source is parts[3], suffix is parts[4]
      // For old keys: parts.length === 4, source is parts[3]
      const source = parts[3] || "unknown";
      events.push({ day, source });
    }
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  return events;
}

async function detectHealthySources(env) {
  // A source is "healthy" if it has a `latest:<source>` key AND the value
  // parses. Everything else goes to sources_degraded so the frontend can
  // render an honest badge.
  const healthy = [];
  const degraded = [];
  for (const src of SOURCES) {
    const raw = await env.DASHBOARD_KV.get(`latest:${src}`, { type: "json" });
    if (raw) healthy.push(src);
    else degraded.push(src);
  }
  return { healthy, degraded };
}

// -----------------------------------------------------------------------------
// Per-day summation — pulls the right numeric fields out of each source
// shape and normalizes to a single (impressions, clicks, wa_taps) triple.
// -----------------------------------------------------------------------------

function extractDailyMetrics(snapsByDay, waEventsByDay, dateStr) {
  const gsc = snapsByDay.gsc?.[dateStr] || {};
  const gbp = snapsByDay.gbp?.[dateStr] || {};
  const bing = snapsByDay.bing?.[dateStr] || {};
  const cfwa = snapsByDay.cfwa?.[dateStr] || {};

  const impressions =
    (gsc.impressions ?? 0) +
    (bing.impressions ?? 0) +
    (gbp.maps_impressions ?? 0) +
    (gbp.search_impressions ?? 0);

  const clicks =
    (gsc.clicks ?? 0) +
    (bing.clicks ?? 0) +
    (gbp.website_clicks ?? 0);

  const waTaps = (waEventsByDay[dateStr] || []).length;

  // Per-source click contribution for the source_split donut.
  const clicksBySource = {
    gsc: gsc.clicks ?? 0,
    gbp: gbp.website_clicks ?? 0,
    bing: bing.clicks ?? 0,
    // CFWA "clicks" here means direct/referrer-driven visits, approximated
    // by pageviews for lack of a distinct "click" event. It's a rough proxy;
    // the donut label makes clear the metric is "clicks/visits."
    cfwa: cfwa.visits ?? 0,
  };

  return { impressions, clicks, waTaps, clicksBySource };
}

// -----------------------------------------------------------------------------
// Delta calculation with floor guard.
// -----------------------------------------------------------------------------

function computeDeltaPct(current, prior) {
  if (prior === null || prior === undefined || prior < DELTA_THRESHOLD) return null;
  const pct = ((current - prior) / prior) * 100;
  return Math.round(pct * 10) / 10; // one decimal
}

// -----------------------------------------------------------------------------
// Rollup builder — one range at a time.
// -----------------------------------------------------------------------------

function buildRollup(rangeKey, endDate, snapsByDay, waEventsByDay, healthy, degraded, days) {
  const dates = dateRange(endDate, days);
  const dailyMetrics = dates.map((d) => extractDailyMetrics(snapsByDay, waEventsByDay, d));

  // Current-window totals.
  const totalImpressions = dailyMetrics.reduce((a, m) => a + m.impressions, 0);
  const totalClicks = dailyMetrics.reduce((a, m) => a + m.clicks, 0);
  const totalWaTaps = dailyMetrics.reduce((a, m) => a + m.waTaps, 0);

  // Prior-window totals for delta_pct — same length window, immediately preceding.
  const priorDates = dates.length > 0
    ? Array.from({ length: dates.length }, (_, i) => isoDatePlus(dates[0], -(dates.length - i)))
    : [];
  const priorMetrics = priorDates.map((d) => extractDailyMetrics(snapsByDay, waEventsByDay, d));
  const priorImpressions = priorMetrics.reduce((a, m) => a + m.impressions, 0);
  const priorClicks = priorMetrics.reduce((a, m) => a + m.clicks, 0);
  const priorWaTaps = priorMetrics.reduce((a, m) => a + m.waTaps, 0);

  // Per-source click contribution for the donut.
  const clickShareBySource = { gsc: 0, gbp: 0, bing: 0, cfwa: 0 };
  for (const m of dailyMetrics) {
    for (const src of SOURCES) clickShareBySource[src] += m.clicksBySource[src] || 0;
  }

  const sourceLabels = {
    gsc: "Google Search",
    gbp: "Google Maps",
    bing: "Bing",
    cfwa: "Direct/referrer",
  };
  const donutLabels = SOURCES.map((s) => sourceLabels[s]);
  const donutValues = SOURCES.map((s) => clickShareBySource[s]);

  // Top queries / pages from the most recent healthy GSC snap in the window.
  let topQueries = [];
  let topPages = [];
  for (let i = dates.length - 1; i >= 0; i--) {
    const gsc = snapsByDay.gsc?.[dates[i]];
    if (gsc?.top_queries?.length) topQueries = gsc.top_queries;
    if (gsc?.top_pages?.length) topPages = gsc.top_pages;
    if (topQueries.length && topPages.length) break;
  }

  const asOfTs = new Date().toISOString();

  return {
    range: rangeKey,
    as_of: asOfTs,
    computed_ms: 0, // filled in by caller
    sources_healthy: healthy,
    sources_degraded: degraded,
    hero_tiles: {
      reach: {
        label: "People who found you on Google",
        value: totalImpressions,
        delta_pct: computeDeltaPct(totalImpressions, priorImpressions),
        sparkline: dailyMetrics.map((m) => m.impressions),
        top_queries: topQueries,
        source: "Google Search Console",
        as_of: dates[dates.length - 1] || null,
      },
      interest: {
        // 2026-08-04: GBP dropped from Interest signal. Google Business
        // Profile API access denied (case 6-8997000041551). GSC + Bing
        // carry the tile until/unless approval lands; re-add GBP here +
        // in the site-side dashboard.astro TILE_SOURCES + JS mirror + in
        // src/content/dashboard-data.json if that day comes.
        label: "Clicks on your site",
        value: totalClicks,
        delta_pct: computeDeltaPct(totalClicks, priorClicks),
        sparkline: dailyMetrics.map((m) => m.clicks),
        top_pages: topPages,
        source: "Google Search Console + Bing",
        as_of: dates[dates.length - 1] || null,
      },
      conversation: {
        label: "WhatsApp taps from your site",
        value: totalWaTaps,
        delta_pct: computeDeltaPct(totalWaTaps, priorWaTaps),
        sparkline: dailyMetrics.map((m) => m.waTaps),
        source: "On-site beacon (/wa-out proxy)",
        as_of: dates[dates.length - 1] || null,
      },
    },
    funnel: [
      { label: "Impressions",  value: totalImpressions, source: "GSC + Bing" },
      { label: "Clicks",       value: totalClicks,      source: "GSC + Bing" },
      { label: "WhatsApp taps", value: totalWaTaps,     source: "On-site beacon" },
    ],
    time_series: {
      labels: dates,
      series: [
        { name: "Impressions", data: dailyMetrics.map((m) => m.impressions) },
        { name: "Clicks",       data: dailyMetrics.map((m) => m.clicks) },
        { name: "WhatsApp taps", data: dailyMetrics.map((m) => m.waTaps) },
      ],
    },
    source_split: {
      labels: donutLabels,
      values: donutValues,
      unit: "clicks",
      degraded_source_indices: SOURCES.map((s, i) => degraded.includes(s) ? i : null).filter((x) => x !== null),
    },
    _delta_threshold: DELTA_THRESHOLD,
  };
}

// -----------------------------------------------------------------------------
// Public entry point — called from index.js at the end of each scheduled run.
// -----------------------------------------------------------------------------

export async function aggregate(env, endDateStr) {
  const startedAt = Date.now();
  const endDate = endDateStr || parisDate(new Date());

  // Widest window we need is the "all" range = capped at daysSinceLaunch+1.
  const daysSinceLaunch = Math.max(0, daysBetween(LAUNCH_DATE, endDate));
  const widestSpan = Math.min(3650, daysSinceLaunch + 1);
  // We also need `widestSpan` days BEFORE the current window for delta_pct.
  const oldestDate = isoDatePlus(endDate, -(2 * widestSpan));
  const allDates = [];
  for (let d = oldestDate; d <= endDate; d = isoDatePlus(d, 1)) allDates.push(d);

  // Load all snaps for the widest window in parallel per source.
  const snapsByDayEntries = await Promise.all(
    SOURCES.map(async (src) => [src, await loadSnapsForSource(env, src, allDates)]),
  );
  const snapsByDay = Object.fromEntries(snapsByDayEntries);

  // Load WA events, bucket by day.
  const waEvents = await loadWaEventsInWindow(env, oldestDate, endDate);
  const waEventsByDay = {};
  for (const ev of waEvents) {
    (waEventsByDay[ev.day] ||= []).push(ev);
  }

  const { healthy, degraded } = await detectHealthySources(env);

  const results = [];
  for (const range of RANGES) {
    const rollup = buildRollup(range.key, endDate, snapsByDay, waEventsByDay, healthy, degraded, range.days);
    rollup.computed_ms = Date.now() - startedAt;
    await env.DASHBOARD_KV.put(`dashboard:${range.key}`, JSON.stringify(rollup));
    results.push({
      range: range.key,
      sources_healthy: healthy.length,
      sources_degraded: degraded.length,
      impressions: rollup.hero_tiles.reach.value,
      clicks: rollup.hero_tiles.interest.value,
      wa_taps: rollup.hero_tiles.conversation.value,
    });
  }

  return { ok: true, ranges: results, duration_ms: Date.now() - startedAt };
}
