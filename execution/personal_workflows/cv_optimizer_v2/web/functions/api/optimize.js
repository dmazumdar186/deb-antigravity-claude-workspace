// Pages Function: two-phase orchestrator.
// Runs on Cloudflare's edge, NOT in the browser.
// Reads WORKER_URL + WORKER_SECRET from Pages env vars (set via dashboard
// or `wrangler pages secret put`). The browser NEVER sees the secret.
//
// Phase A (this file): split scrape (~3-8s) and LLM (~12-22s) into two Worker
// subrequests. Each has its own bounded timeout, so neither races a hard wall.
// Cloudflare Pages Functions are limited by CPU time (30s on paid), not wall
// time, so the total can comfortably exceed 30s when awaiting fetch().

const SCRAPE_TIMEOUT_MS = 11_000;   // Worker firecrawl cap is 10s; +1s margin
const OPTIMIZE_TIMEOUT_MS = 65_000; // Worker anthropic cap is 60s; +5s margin. Headroom for p99 variance.

async function callWorker(path, payload, env, timeoutMs) {
  const target = `${env.WORKER_URL.replace(/\/$/, "")}${path}`;
  const ctrl = new AbortController();
  const timeoutId = setTimeout(() => ctrl.abort(), timeoutMs);

  let resp;
  try {
    resp = await fetch(target, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Worker-Secret": env.WORKER_SECRET,
      },
      body: JSON.stringify(payload),
      signal: ctrl.signal,
    });
  } catch (err) {
    const aborted = err instanceof Error && err.name === "AbortError";
    return { status: aborted ? 504 : 502, body: { error: aborted ? "worker_timeout" : "worker_fetch_failed", phase: path, detail: err instanceof Error ? err.message : String(err) } };
  } finally {
    clearTimeout(timeoutId);
  }

  const text = await resp.text();
  let json;
  try {
    json = JSON.parse(text);
  } catch {
    return { status: 502, body: { error: "worker_invalid_json", phase: path, detail: text.slice(0, 200) } };
  }
  return { status: resp.status, body: json };
}

export async function onRequestPost({ request, env }) {
  if (!env.WORKER_URL || !env.WORKER_SECRET) {
    return new Response(
      JSON.stringify({
        error: "pages_function_misconfigured",
        detail: "WORKER_URL or WORKER_SECRET not set in Pages env vars.",
      }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }

  let payload;
  try {
    payload = await request.json();
  } catch {
    return new Response(JSON.stringify({ error: "invalid_json" }), { status: 400, headers: { "Content-Type": "application/json" } });
  }

  const cv_text = typeof payload?.cv_text === "string" ? payload.cv_text : "";
  const jd_url = typeof payload?.jd_url === "string" ? payload.jd_url.trim() : "";
  const jd_text_raw = typeof payload?.jd_text === "string" ? payload.jd_text.trim() : "";

  if (!cv_text.trim()) {
    return new Response(JSON.stringify({ error: "cv_text_required" }), { status: 400, headers: { "Content-Type": "application/json" } });
  }
  if (!jd_url && !jd_text_raw) {
    return new Response(
      JSON.stringify({ error: "jd_required", detail: "Provide jd_url and/or jd_text." }),
      { status: 400, headers: { "Content-Type": "application/json" } }
    );
  }

  const t0 = Date.now();
  let resolvedJdText = "";
  let scrapeMeta = null;

  if (jd_url) {
    const scrape = await callWorker("/api/scrape", { url: jd_url }, env, SCRAPE_TIMEOUT_MS);
    scrapeMeta = { status: scrape.status, ok: scrape.body?.ok, reason: scrape.body?.reason, cached: scrape.body?.cached, ms: Date.now() - t0 };

    if (scrape.status === 200 && scrape.body?.ok && typeof scrape.body.markdown === "string") {
      resolvedJdText = scrape.body.markdown;
    } else if (jd_text_raw) {
      // Scrape failed but caller provided text fallback — use it.
      resolvedJdText = jd_text_raw;
    } else {
      // Scrape failed and no fallback. Preserve legacy error shape so E1 test still passes.
      return new Response(
        JSON.stringify({
          error: "jd_scrape_failed",
          reason: scrape.body?.reason ?? "unknown",
          suggestion: "paste the JD text directly",
          scrape_meta: scrapeMeta,
        }),
        { status: 400, headers: { "Content-Type": "application/json" } }
      );
    }
  } else {
    resolvedJdText = jd_text_raw;
  }

  const tOpt = Date.now();
  const optimize = await callWorker(
    "/api/optimize",
    { cv_text, jd_text: resolvedJdText },
    env,
    OPTIMIZE_TIMEOUT_MS,
  );

  const total = Date.now() - t0;
  const optMs = Date.now() - tOpt;

  // On success: pass Worker response through with timing headers.
  // On error: pass through Worker status + body so test harness sees the real error.
  return new Response(JSON.stringify(optimize.body), {
    status: optimize.status,
    headers: {
      "Content-Type": "application/json",
      "X-Phase-Total-Ms": String(total),
      "X-Phase-Optimize-Ms": String(optMs),
      "X-Phase-Scrape-Cached": String(scrapeMeta?.cached ?? false),
    },
  });
}
