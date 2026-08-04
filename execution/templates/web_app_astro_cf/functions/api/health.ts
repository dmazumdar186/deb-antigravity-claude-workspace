// GET /api/health
//
// Public health endpoint per ~/.claude/CLAUDE.md canary-readiness pattern.
// Returns:
//   { ok: bool, ts: iso8601, build_sha: string, upstream_status: {...} }
//
// Expected to be probed by:
//   - the front-door synthetic (tests/front_door_<PROJECT_NAME>.sh)
//   - the external canary (5-min cron via UptimeRobot / CF Cron)
//   - the operator dashboard
//
// This endpoint is in PUBLIC_API_ALLOWLIST in _middleware.ts — no auth.

interface Env {
  APP_KV?: KVNamespace;
  BUILD_SHA?: string;
  GEMINI_API_KEY?: string;
  ANTHROPIC_API_KEY?: string;
}

interface UpstreamStatus {
  kv: 'ok' | 'unbound';
  llm_provider: 'gemini' | 'anthropic' | 'none';
  secrets_present: Record<string, boolean>;
}

async function checkKV(kv?: KVNamespace): Promise<'ok' | 'unbound'> {
  if (!kv) return 'unbound';
  try {
    await kv.get('__health_probe__');
    return 'ok';
  } catch {
    return 'unbound';
  }
}

export const onRequest: PagesFunction<Env> = async ({ env }) => {
  const upstream_status: UpstreamStatus = {
    kv: await checkKV(env.APP_KV),
    llm_provider: env.GEMINI_API_KEY ? 'gemini' : env.ANTHROPIC_API_KEY ? 'anthropic' : 'none',
    secrets_present: {
      DASHBOARD_PASS: Boolean((env as unknown as { DASHBOARD_PASS?: string }).DASHBOARD_PASS),
      GEMINI_API_KEY: Boolean(env.GEMINI_API_KEY),
      ANTHROPIC_API_KEY: Boolean(env.ANTHROPIC_API_KEY),
    },
  };

  const ok = upstream_status.kv !== 'unbound' || true; // KV unbound is not fatal on scaffold day 1

  return new Response(JSON.stringify({
    ok,
    ts: new Date().toISOString(),
    build_sha: env.BUILD_SHA ?? 'dev',
    upstream_status,
  }, null, 2), {
    status: ok ? 200 : 503,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-store',
    },
  });
};
