// yoga-jitendra-cron — daily snapshot pipeline for the yoga-jitendra
// dashboard V0.1.
//
// Runs once/day at 06:00 Paris local time (DST-safe via Intl.DateTimeFormat),
// pulls each source in parallel, writes snap:<source>:<YYYY-MM-DD> keys, then
// runs the aggregator to refresh dashboard:{7d,30d,all}. Also exposes a
// small fetch() surface with:
//
//   GET /health                     -> secret-presence + KV-binding status
//   POST /run    (X-Worker-Secret) -> manually trigger the same pipeline
//                                     the cron fires (bootstrap / debug)
//   POST /run/<source> (secret)    -> manually trigger a single source
//
// See wrangler.toml for the two-cron DST-split pattern. The scheduled()
// handler below picks the fire that matches 06:00 Paris local and skips
// the other one, so we get exactly one run/day across the year.
//
// Companion Pages project: execution/personal_workflows/yoga_jitendra_site/
// which reads dashboard:<range> from the same DASHBOARD_KV namespace.

// Sources — one module per external API. Each exports `fetch(env, date)`
// that returns a snapshot object OR throws (in which case the source is
// marked degraded for the day; the pipeline keeps running for other sources).
// NOTE: the source modules land in Phases B and C-*. Phase A stubs them
// to a shape the aggregator understands so the skeleton is testable end-to-end.
import { fetchGsc } from "./sources/gsc.js";
import { fetchGbp } from "./sources/gbp.js";
import { fetchBing } from "./sources/bing.js";
import { fetchCfWa } from "./sources/cf_wa.js";
import { fetchGbpReviews } from "./sources/gbp_reviews.js";
import { aggregate } from "./aggregator.js";

const TARGET_PARIS_HOUR = 6; // 06:00 Paris local time — matches DASHBOARD_HANDOFF §4

const SOURCES = [
  { key: "gsc",  label: "Google Search Console",   fetcher: fetchGsc },
  { key: "gbp",  label: "Google Business Profile", fetcher: fetchGbp },
  { key: "bing", label: "Bing Webmaster Tools",    fetcher: fetchBing },
  { key: "cfwa", label: "Cloudflare Web Analytics", fetcher: fetchCfWa },
  // Forward-sync of Google reviews into the public site's review:approved:*
  // records. Writes to KV itself (dedup lives in the module); the snap:/
  // latest: blobs it returns are a run summary. The aggregator's own SOURCES
  // list does not include this key, so dashboard rollups are unaffected.
  { key: "gbp_reviews", label: "GBP Reviews Sync", fetcher: fetchGbpReviews },
];

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8" };

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj, null, 2), { status, headers: JSON_HEADERS });
}

function isoNow() {
  return new Date().toISOString();
}

// Timing-safe constant-time string compare. Same pattern as the Pages
// _middleware.ts. Used for the X-Worker-Secret gate on /run.
function ctEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

// DST-accurate: parse the actual Paris hour at fire-time via the runtime's
// built-in tzdata. This handles the last-Sunday-of-March/October transitions
// exactly, unlike a month-number heuristic (which is 3-7 days wrong at each
// boundary and can silently drop a whole day of the pipeline).
function parisHour(date) {
  return parseInt(
    new Intl.DateTimeFormat("en-US", {
      hour: "numeric",
      hour12: false,
      timeZone: "Europe/Paris",
    }).format(date),
    10,
  );
}

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

// Runs one source, catches any throw, returns a per-source result the
// aggregator can consume without special-casing failures. Never re-throws;
// one broken source cannot poison the whole pipeline.
async function runSource(source, env, dateStr) {
  const startedAt = Date.now();
  try {
    const snap = await source.fetcher(env, dateStr);
    if (!snap || typeof snap !== "object") {
      throw new Error(`source ${source.key} returned non-object: ${typeof snap}`);
    }
    const key = `snap:${source.key}:${dateStr}`;
    await env.DASHBOARD_KV.put(key, JSON.stringify({ ...snap, _fetched_at: isoNow() }), {
      expirationTtl: 90 * 24 * 60 * 60, // 90d, per plan §3.2
    });
    // "latest:<source>" mirrors the most recent snap; no TTL — one key/source.
    await env.DASHBOARD_KV.put(`latest:${source.key}`, JSON.stringify({ ...snap, _fetched_at: isoNow() }));
    return {
      source: source.key,
      status: "healthy",
      duration_ms: Date.now() - startedAt,
      key,
    };
  } catch (err) {
    // Log with source label so wrangler tail is scannable; do not leak the
    // full error to the KV blob because it may contain access-token fragments
    // (the source module should redact before throwing, but defense in depth).
    console.error(`source ${source.key} failed: ${err?.message || err}`);
    return {
      source: source.key,
      status: "degraded",
      duration_ms: Date.now() - startedAt,
      reason: err?.message ?? "unknown error",
    };
  }
}

async function runPipeline(env, opts = {}) {
  const dateStr = opts.dateStr ?? parisDate(new Date());
  const only = opts.only ?? null; // e.g. "gsc" to run one source
  const targets = only ? SOURCES.filter((s) => s.key === only) : SOURCES;
  if (targets.length === 0) {
    return { ok: false, error: `unknown source: ${only}` };
  }

  const startedAt = Date.now();
  // Sources are independent — fire them all in parallel.
  const results = await Promise.all(targets.map((s) => runSource(s, env, dateStr)));

  // Aggregator runs only if this was a full pipeline pass. Single-source
  // manual triggers skip aggregation because rollups would be stale/partial.
  let aggregation = null;
  if (!only) {
    try {
      aggregation = await aggregate(env, dateStr);
    } catch (err) {
      console.error(`aggregator failed: ${err?.message || err}`);
      aggregation = { ok: false, error: err?.message ?? "unknown" };
    }
  }

  const summary = {
    ok: true,
    date: dateStr,
    duration_ms: Date.now() - startedAt,
    sources: results,
    aggregation,
    finished_at: isoNow(),
  };

  // Dead-man surface. The pipeline was silently degrading in prod for weeks
  // (all sources failing on stale OAuth tokens) and no one noticed because
  // errors were swallowed at runSource(). Now we write two KV keys any
  // monitor (or /health) can read to detect the stall:
  //
  //   pipeline:last_run           — always written, even on total failure.
  //                                 Holds date + per-source status + timing.
  //   pipeline:last_full_failure  — written ONLY when 0 sources are healthy.
  //                                 Absence of this key means "at least one
  //                                 source has been healthy since last write".
  //
  // Both keys are best-effort — if KV writes themselves fail (unlikely at
  // this call volume) the pipeline still returns its summary to the caller.
  if (!only && env.DASHBOARD_KV) {
    const healthyCount = results.filter((r) => r.status === "healthy").length;
    const lastRunPayload = {
      date: dateStr,
      finished_at: summary.finished_at,
      duration_ms: summary.duration_ms,
      healthy_count: healthyCount,
      total_count: results.length,
      per_source: results.map((r) => ({
        source: r.source,
        status: r.status,
        duration_ms: r.duration_ms,
        reason: r.reason || null,
      })),
      aggregation_ok: Boolean(aggregation && aggregation.ok !== false),
    };
    try {
      await env.DASHBOARD_KV.put("pipeline:last_run", JSON.stringify(lastRunPayload));
      if (healthyCount === 0) {
        await env.DASHBOARD_KV.put(
          "pipeline:last_full_failure",
          JSON.stringify(lastRunPayload),
        );
      }
    } catch (err) {
      // Never let a KV write failure hide the pipeline result. Log so
      // wrangler tail shows it and the caller still gets `summary`.
      console.error(`pipeline dead-man KV write failed: ${err?.message || err}`);
    }
  }

  return summary;
}

async function handleHealth(env) {
  const secrets = {
    GOOGLE_CLIENT_ID: Boolean(env.GOOGLE_CLIENT_ID),
    GOOGLE_CLIENT_SECRET: Boolean(env.GOOGLE_CLIENT_SECRET),
    GOOGLE_REFRESH_TOKEN_GSC: Boolean(env.GOOGLE_REFRESH_TOKEN_GSC),
    GOOGLE_REFRESH_TOKEN_GBP: Boolean(env.GOOGLE_REFRESH_TOKEN_GBP),
    BING_API_KEY: Boolean(env.BING_API_KEY),
    CF_ANALYTICS_TOKEN: Boolean(env.CF_ANALYTICS_TOKEN),
    CF_ACCOUNT_ID: Boolean(env.CF_ACCOUNT_ID),
    WORKER_SECRET: Boolean(env.WORKER_SECRET),
  };
  const missing = Object.entries(secrets).filter(([, v]) => !v).map(([k]) => k);

  // Read the pipeline dead-man keys so /health surfaces stalled cron runs.
  // Best-effort — a missing key just means the pipeline has never written
  // one (bootstrap state), not necessarily broken.
  let lastRun = null;
  let lastFullFailure = null;
  let staleHours = null;
  if (env.DASHBOARD_KV) {
    try {
      const [runRaw, failRaw] = await Promise.all([
        env.DASHBOARD_KV.get("pipeline:last_run"),
        env.DASHBOARD_KV.get("pipeline:last_full_failure"),
      ]);
      lastRun = runRaw ? JSON.parse(runRaw) : null;
      lastFullFailure = failRaw ? JSON.parse(failRaw) : null;
      if (lastRun && lastRun.finished_at) {
        const ageMs = Date.now() - Date.parse(lastRun.finished_at);
        staleHours = Number.isFinite(ageMs) ? Math.round(ageMs / (60 * 60 * 1000)) : null;
      }
    } catch (err) {
      console.error(`/health dead-man read failed: ${err?.message || err}`);
    }
  }

  // Overall health = secrets present AND at least one healthy source in the
  // last run AND last run is younger than 26h (one full cron cycle + slack).
  const pipelineHealthy =
    lastRun &&
    lastRun.healthy_count > 0 &&
    (staleHours === null || staleHours <= 26);

  return json({
    ok: missing.length === 0 && pipelineHealthy,
    ts: isoNow(),
    paris_hour: parisHour(new Date()),
    paris_date: parisDate(new Date()),
    kv_bound: Boolean(env.DASHBOARD_KV),
    secrets_present: secrets,
    secrets_missing: missing,
    pipeline: {
      last_run: lastRun,
      last_full_failure: lastFullFailure,
      stale_hours: staleHours,
      healthy: pipelineHealthy,
    },
    vars: {
      GSC_SITE_URL: env.GSC_SITE_URL || null,
      CF_ZONE_HOSTNAME: env.CF_ZONE_HOSTNAME || null,
      BING_SITE_URL: env.BING_SITE_URL || null,
      GBP_LOCATION_ID: env.GBP_LOCATION_ID || null,
      GBP_ACCOUNT_ID: env.GBP_ACCOUNT_ID || null,
    },
  });
}

function requireWorkerSecret(request, env) {
  if (!env.WORKER_SECRET) {
    return json({ ok: false, error: "WORKER_SECRET not configured on this Worker" }, 503);
  }
  const presented = request.headers.get("x-worker-secret") || "";
  if (!ctEqual(presented, env.WORKER_SECRET)) {
    return json({ ok: false, error: "unauthorized" }, 401);
  }
  return null;
}

export default {
  async scheduled(event, env, ctx) {
    const now = new Date(event.scheduledTime);
    const hour = parisHour(now);
    if (hour !== TARGET_PARIS_HOUR) {
      // Wrong side of the DST split; the other cron will fire at the right hour.
      console.log(`skip: paris_hour=${hour} target=${TARGET_PARIS_HOUR}`);
      return;
    }
    // The scheduled handler must await the pipeline via ctx.waitUntil so CF
    // does not truncate the Worker mid-fetch when scheduled() returns.
    const promise = runPipeline(env).then((result) => {
      const healthy = result.sources.filter((r) => r.status === "healthy").length;
      const total = result.sources.length;
      console.log(`pipeline complete: ${healthy}/${total} sources healthy in ${result.duration_ms}ms`);
    });
    ctx.waitUntil(promise);
  },

  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const method = request.method.toUpperCase();

    if (method === "GET" && url.pathname === "/health") {
      return handleHealth(env);
    }

    if (method === "POST" && url.pathname === "/run") {
      const denied = requireWorkerSecret(request, env);
      if (denied) return denied;
      const result = await runPipeline(env);
      return json(result);
    }

    if (method === "POST" && url.pathname.startsWith("/run/")) {
      const denied = requireWorkerSecret(request, env);
      if (denied) return denied;
      const only = url.pathname.slice("/run/".length);
      const result = await runPipeline(env, { only });
      return json(result, result.ok ? 200 : 400);
    }

    // GET /debug/kv/<key> — inspect a raw KV value. Requires X-Worker-Secret.
    // Added 2026-08-05 to diagnose the CFWA all-zero-donut bug without
    // requiring a redeploy for every hypothesis test. Read-only; the key
    // pattern is unrestricted because the secret already gates access.
    if (method === "GET" && url.pathname.startsWith("/debug/kv/")) {
      const denied = requireWorkerSecret(request, env);
      if (denied) return denied;
      const key = decodeURIComponent(url.pathname.slice("/debug/kv/".length));
      if (!key) return json({ ok: false, error: "missing key" }, 400);
      try {
        const raw = await env.DASHBOARD_KV.get(key);
        if (raw === null) return json({ ok: true, key, value: null, note: "key not found" });
        try {
          return json({ ok: true, key, value: JSON.parse(raw) });
        } catch {
          return json({ ok: true, key, value: raw, note: "not JSON, returned raw" });
        }
      } catch (err) {
        return json({ ok: false, key, error: err?.message || String(err) }, 500);
      }
    }

    return json({ ok: false, error: "not found", tried: `${method} ${url.pathname}` }, 404);
  },
};
