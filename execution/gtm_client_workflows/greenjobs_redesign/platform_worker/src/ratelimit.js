// Rate limiting, same fallback chain as worker/index.js:
//   1. Workers Rate Limiting binding (env.APPLY_LIMITER.limit({key})) when bound, as a burst guard
//      (the binding's period is 10 or 60 s, so it cannot express a 10-minute window by itself);
//   2. the fixed window (RATE_APPLY_PER_10MIN / RATE_ADMIN_PER_MIN) in KV binding RATE when bound,
//   3. else an in-isolate Map (best effort, per instance).
// Keys never carry raw PII: callers pass hashed emails.

export function createRateLimiter() {
  const mem = new Map();
  return async function allow(env, { scope, key, limit, windowSec, nowMs, binding }) {
    if (binding && typeof binding.limit === 'function') {
      try {
        const r = await binding.limit({ key: `${scope}:${key}` });
        if (r && r.success === false) return false;
      } catch {
        // A limiter outage must not block applications; the window below still applies.
      }
    }
    const bucket = Math.floor(nowMs / (windowSec * 1000));
    const k = `rate:${scope}:${key}:${bucket}`;
    if (env.RATE && typeof env.RATE.get === 'function') {
      const n = Number((await env.RATE.get(k)) || 0) + 1;
      await env.RATE.put(k, String(n), { expirationTtl: Math.max(60, windowSec * 2) });
      return n <= limit;
    }
    const n = (mem.get(k) || 0) + 1;
    mem.set(k, n);
    if (mem.size > 5000) mem.clear();
    return n <= limit;
  };
}
