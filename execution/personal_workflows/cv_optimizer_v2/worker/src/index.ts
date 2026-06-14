// cv-optimizer-api Worker.
//
// Prompts and schema come from build-time-generated ./embedded.generated.ts.
// To update them, edit prompts/system_prompt.md or prompts/cv_response_schema.json
// and re-run `node scripts/embed-prompts.mjs` (wrangler runs this automatically).

import { optimizeCvGemini } from "./gemini.js";
import { handleScrape } from "./scrape.js";
import { handleRefreshProfile, getCachedProfile } from "./profile.js";
import { SYSTEM_PROMPT, RESPONSE_SCHEMA, PROMPT_FINGERPRINT, SCHEMA_FINGERPRINT } from "./embedded.generated.js";

// Provider note: pivoted from Anthropic Sonnet 4.6 → Gemini 2.5 Flash on 2026-06-14.
// Reason: Anthropic API requires $20 minimum top-up; the user can't afford that for a
// personal tool. Gemini 2.5 Flash has a 1500 req/day free tier that comfortably covers
// ~50 calls/year. anthropic.ts kept on disk for fallback / future use when budget allows.

// ---------------------------------------------------------------------------
// Env bindings
// ---------------------------------------------------------------------------
export interface Env {
  RATE_LIMIT: KVNamespace;
  APP_VERSION: string;
  // Secrets (set via `wrangler secret put`):
  WORKER_SECRET?: string;
  GEMINI_API_KEY?: string;       // active optimizer provider (free tier)
  ANTHROPIC_API_KEY?: string;    // kept for future / fallback; not currently called
  FIRECRAWL_API_KEY?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Constant-time string comparison to prevent timing-based secret leaks.
 * XORs every char position; avoids early return so comparison time is O(max(a,b)).
 */
function safeEqual(a: string, b: string): boolean {
  const la = a.length;
  const lb = b.length;
  let diff = la ^ lb; // length mismatch → diff ≠ 0
  const len = Math.max(la, lb);
  for (let i = 0; i < len; i++) {
    diff |= (a.charCodeAt(i % la) ^ b.charCodeAt(i % lb));
  }
  return diff === 0;
}

/** Current UTC hour bucket string for per-IP rate limiting (e.g. "2024-01-15T13"). */
function hourBucket(): string {
  return new Date().toISOString().slice(0, 13); // "YYYY-MM-DDTHH"
}

// ---------------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------------
export default {
  async fetch(req: Request, env: Env, _ctx: ExecutionContext): Promise<Response> {
    const url = new URL(req.url);

    if (req.method === "GET" && url.pathname === "/api/health") {
      return await handleHealth(env);
    }

    if (req.method === "POST" && url.pathname === "/api/optimize") {
      return await handleOptimize(req, env);
    }

    if (req.method === "POST" && url.pathname === "/api/scrape") {
      // Scrape endpoint shares the same secret as optimize.
      const incomingSecret = req.headers.get("X-Worker-Secret") ?? "";
      const expectedSecret = env.WORKER_SECRET ?? "";
      if (!expectedSecret || !safeEqual(incomingSecret, expectedSecret)) {
        return Response.json({ ok: false, reason: "unauthorized" }, { status: 401 });
      }
      return await handleScrape(req, env);
    }

    if (req.method === "POST" && url.pathname === "/api/refresh-profile") {
      // Profile refresh — same secret. Called manually or by future scheduled cron.
      const incomingSecret = req.headers.get("X-Worker-Secret") ?? "";
      const expectedSecret = env.WORKER_SECRET ?? "";
      if (!expectedSecret || !safeEqual(incomingSecret, expectedSecret)) {
        return Response.json({ ok: false, reason: "unauthorized" }, { status: 401 });
      }
      return await handleRefreshProfile(env);
    }

    return new Response("Not found", { status: 404 });
  },
};

// ---------------------------------------------------------------------------
// GET /api/health
// ---------------------------------------------------------------------------
async function handleHealth(env: Env): Promise<Response> {
  // KV probe: write + read a short key to confirm the binding works.
  let kvOk = false;
  let kvError: string | undefined;
  try {
    await env.RATE_LIMIT.put("health:probe", String(Date.now()), { expirationTtl: 60 });
    const got = await env.RATE_LIMIT.get("health:probe");
    kvOk = got !== null;
  } catch (err) {
    kvError = err instanceof Error ? err.message : String(err);
  }

  // Secret-presence map — booleans only, NEVER values.
  const secretsPresent = {
    worker_secret: Boolean(env.WORKER_SECRET),
    gemini: Boolean(env.GEMINI_API_KEY),
    anthropic: Boolean(env.ANTHROPIC_API_KEY),
    firecrawl: Boolean(env.FIRECRAWL_API_KEY),
  };

  const allSecretsPresent = Object.values(secretsPresent).every(Boolean);
  const status = kvOk && allSecretsPresent ? "ok" : "degraded";

  return Response.json({
    status,
    version: env.APP_VERSION ?? "unknown",
    kv_check: kvOk ? "pass" : `fail: ${kvError ?? "no value"}`,
    secrets_present: secretsPresent,
    prompt_fingerprint: PROMPT_FINGERPRINT,
    schema_fingerprint: SCHEMA_FINGERPRINT,
    timestamp: new Date().toISOString(),
  });
}

// ---------------------------------------------------------------------------
// POST /api/optimize
// ---------------------------------------------------------------------------

// Note: this Worker is called server-side by the Pages Function
// (functions/api/optimize.js), NOT directly by the browser.
// No CORS headers are required — same-origin Pages Function → Worker call only.

async function handleOptimize(req: Request, env: Env): Promise<Response> {
  // 1. Secret auth — constant-time compare.
  const incomingSecret = req.headers.get("X-Worker-Secret") ?? "";
  const expectedSecret = env.WORKER_SECRET ?? "";
  if (!expectedSecret || !safeEqual(incomingSecret, expectedSecret)) {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }

  // 2. Per-IP rate limit: 10 requests per hour via KV.
  const ip = req.headers.get("CF-Connecting-IP") ?? "unknown";
  const rlKey = `rl:${ip}:${hourBucket()}`;
  let currentCount = 0;
  try {
    const existing = await env.RATE_LIMIT.get(rlKey);
    currentCount = existing ? parseInt(existing, 10) : 0;
  } catch (err) {
    // KV read failure — log and allow through rather than hard-blocking all requests.
    // Safe to pass: a momentary KV failure shouldn't deny all users.
    console.error(`[rate-limit] KV read failed for key ${rlKey}: ${err instanceof Error ? err.message : String(err)}`);
  }

  const nowMs = Date.now();
  const nextHourMs = new Date(hourBucket() + ":00:00Z").getTime() + 3600_000;
  // Cloudflare KV requires expirationTtl >= 60s; clamp accordingly.
  const secondsToNextHour = Math.max(60, Math.ceil((nextHourMs - nowMs) / 1000));

  // 50 requests/hr/IP. Test harness needs to be run during quiet windows or with
  // a deliberate bump; do not raise this for development convenience without reverting.
  if (currentCount >= 50) {
    return Response.json(
      { error: "rate_limit", retry_after_seconds: secondsToNextHour },
      { status: 429 },
    );
  }

  // Increment counter; fire-and-forget (no await) to not block the response path.
  // TTL aligned to next hour bucket boundary so counter clears at the same instant the bucket key rolls over.
  env.RATE_LIMIT.put(rlKey, String(currentCount + 1), { expirationTtl: secondsToNextHour }).catch((err: unknown) => {
    console.error(`[rate-limit] KV write failed for key ${rlKey}: ${err instanceof Error ? err.message : String(err)}`);
  });

  // 3. Parse + validate request body.
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return Response.json({ error: "invalid_json" }, { status: 400 });
  }

  if (typeof body !== "object" || body === null) {
    return Response.json({ error: "invalid_body" }, { status: 400 });
  }

  const { cv_text, jd_text, skip_profile } = body as Record<string, unknown>;

  if (typeof cv_text !== "string" || cv_text.trim().length === 0) {
    return Response.json({ error: "cv_text_required" }, { status: 400 });
  }
  if (cv_text.length > 50_000) {
    return Response.json({ error: "cv_text_too_long", max_chars: 50_000 }, { status: 400 });
  }

  if (typeof jd_text !== "string" || jd_text.trim().length === 0) {
    // /api/optimize is LLM-only now. The Pages Function resolves jd_url -> jd_text
    // via /api/scrape before calling here. If jd_text is missing, that's a contract bug.
    return Response.json(
      { error: "jd_text_required", detail: "Caller must resolve jd_url via /api/scrape first." },
      { status: 400 },
    );
  }

  const t0 = Date.now();

  // Profile context: cached external activity (GitHub etc.) injected after CV.
  // Opt-out: { skip_profile: true } in body.
  let profileContext = "";
  if (skip_profile !== true) {
    profileContext = await getCachedProfile(env);
  }

  console.log(`[optimize] cv_chars=${cv_text.length} jd_chars=${jd_text.length} profile_chars=${profileContext.length}`);

  // Optimize via Gemini 2.5 Flash (free tier). See gemini.ts for provider rationale.
  const tLLM = Date.now();
  try {
    const cvSpec = await optimizeCvGemini(
      cv_text,
      jd_text,
      SYSTEM_PROMPT,
      RESPONSE_SCHEMA,
      env.GEMINI_API_KEY ?? "",
      profileContext,
    );
    console.log(`[timing] gemini ${Date.now() - tLLM}ms total ${Date.now() - t0}ms`);
    return Response.json(cvSpec, { status: 200 });
  } catch (err) {
    const detail = err instanceof Error ? err.message.slice(0, 200) : String(err).slice(0, 200);
    console.error(`[optimize] Gemini call failed after ${Date.now() - tLLM}ms: ${detail}`);
    return Response.json({ error: "optimize_failed", detail }, { status: 502 });
  }
}
