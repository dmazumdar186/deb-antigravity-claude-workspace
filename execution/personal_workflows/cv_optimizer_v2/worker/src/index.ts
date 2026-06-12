// cv-optimizer-api Worker — health endpoint stub (Phase 2a)
// Phase 2b adds Firecrawl + Gemini + POST /api/optimize.

export interface Env {
  RATE_LIMIT: KVNamespace;
  APP_VERSION: string;
  // Secrets (set via `wrangler secret put`):
  WORKER_SECRET?: string;
  GEMINI_API_KEY?: string;
  FIRECRAWL_API_KEY?: string;
}

export default {
  async fetch(req: Request, env: Env, _ctx: ExecutionContext): Promise<Response> {
    const url = new URL(req.url);
    if (req.method === "GET" && url.pathname === "/api/health") {
      return await handleHealth(env);
    }
    return new Response("Not found", { status: 404 });
  },
};

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
    firecrawl: Boolean(env.FIRECRAWL_API_KEY),
  };

  const allSecretsPresent = Object.values(secretsPresent).every(Boolean);
  const status = kvOk && allSecretsPresent ? "ok" : "degraded";

  return Response.json({
    status,
    version: env.APP_VERSION ?? "unknown",
    kv_check: kvOk ? "pass" : `fail: ${kvError ?? "no value"}`,
    secrets_present: secretsPresent,
    timestamp: new Date().toISOString(),
  });
}
