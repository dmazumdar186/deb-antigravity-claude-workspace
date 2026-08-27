// Lightweight batched telemetry for Cloudflare Pages Functions.
//
// Usage (inside a Function):
//   import { logEvent } from '../../src/lib/telemetry';
//   logEvent(env.APP_KV, 'api.health.hit', { ok: true });
//
// Semantics:
//   - Batched by KV write (one key per event; TTL 30d).
//   - Non-blocking (fire-and-forget via ctx.waitUntil if available).
//   - Never throws; failures are swallowed so telemetry never breaks
//     the request path.
//
// For higher volume, replace with Cloudflare Analytics Engine or an
// external log sink (Axiom, Baselime). Keep the same call signature.

export interface TelemetryEvent {
  name: string;
  ts: number;
  payload?: Record<string, unknown>;
}

const EVENT_TTL_SECONDS = 60 * 60 * 24 * 30; // 30 days

export async function logEvent(
  kv: KVNamespace | undefined,
  name: string,
  payload?: Record<string, unknown>,
): Promise<void> {
  if (!kv) return;
  const ev: TelemetryEvent = { name, ts: Date.now(), payload };
  const key = `event:${ev.ts}:${crypto.randomUUID().slice(0, 8)}`;
  try {
    await kv.put(key, JSON.stringify(ev), { expirationTtl: EVENT_TTL_SECONDS });
  } catch {
    // Swallow: telemetry must never break the request.
  }
}

// Model-cost logging helper. Prices are EUR-normalized per
// ~/.claude/rules/currency-eur.md. Update USD_TO_EUR quarterly.
const USD_TO_EUR = 0.92;

export interface ModelPricingUSD {
  input: number;        // $ per 1M tokens
  cache_read: number;
  cache_write: number;
  output: number;
}

// Cache-aware pricing per ~/.claude/CLAUDE.md rule 4.
// Extend as new models are added.
// Anthropic rates verified against platform.claude.com/docs/en/about-claude/pricing
// on 2026-08-12. The prior claude-opus-4-8 row carried the retired Opus 4.1 rate
// ($15/$75); Opus 4.5 onward are all $5/$25.
export const MODEL_PRICING_USD: Record<string, ModelPricingUSD> = {
  'claude-fable-5':       { input: 10.00, cache_read: 1.00, cache_write: 12.50, output: 50.00 }, // verified 2026-08-27
  'claude-sonnet-5':      { input: 2.00, cache_read: 0.20, cache_write: 2.50, output: 10.00 },
  'claude-opus-5':        { input: 5.00, cache_read: 0.50, cache_write: 6.25, output: 25.00 },
  'claude-sonnet-4-6':    { input: 3.00, cache_read: 0.30, cache_write: 3.75, output: 15.00 },
  'claude-opus-4-8':      { input: 5.00, cache_read: 0.50, cache_write: 6.25, output: 25.00 },
  'gemini-2.5-flash':     { input: 0.075, cache_read: 0.01875, cache_write: 0.09375, output: 0.30 },
  'z-ai/glm-5.2':         { input: 1.00, cache_read: 0.10, cache_write: 1.25, output: 3.00 },
};

export function estimateCostEUR(
  model: string,
  usage: { input_tokens?: number; cache_read_tokens?: number; cache_write_tokens?: number; output_tokens?: number },
): number {
  const p = MODEL_PRICING_USD[model];
  if (!p) return 0;
  const cost_usd = (
    ((usage.input_tokens        ?? 0) * p.input) +
    ((usage.cache_read_tokens   ?? 0) * p.cache_read) +
    ((usage.cache_write_tokens  ?? 0) * p.cache_write) +
    ((usage.output_tokens       ?? 0) * p.output)
  ) / 1_000_000;
  return cost_usd * USD_TO_EUR;
}
