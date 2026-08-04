import { describe, it, expect, beforeEach } from 'vitest';
import { recordCall, getAllEvents, clearTelemetry, estimateCostEur, rollup } from '../../src/lib/telemetry.ts';

// vitest environment: 'node' — no window/localStorage. That's fine; the module
// degrades gracefully to in-memory only.

beforeEach(() => { clearTelemetry(); });

describe('estimateCostEur', () => {
  it('anthropic sonnet 4.6 → non-zero cost proportional to tokens', () => {
    const c = estimateCostEur('anthropic', 'claude-sonnet-4-6', 1_000_000, 1_000_000);
    // 3 USD in + 15 USD out = 18 USD ≈ 16.56 EUR
    expect(c).toBeCloseTo(18 * 0.92, 2);
  });
  it('gemini free tier → 0', () => {
    expect(estimateCostEur('gemini', 'gemini-2.5-flash', 100_000, 100_000)).toBe(0);
    expect(estimateCostEur('gemini', 'gemini-2.5-flash-lite', 100_000, 100_000)).toBe(0);
  });
  it('unknown model → 0 (safe default)', () => {
    expect(estimateCostEur('unknown', 'some-model', 100_000, 100_000)).toBe(0);
    expect(estimateCostEur('anthropic', undefined, 1000, 1000)).toBe(0);
  });
});

describe('recordCall + getAllEvents', () => {
  it('appends and returns events', () => {
    recordCall({ mode: 'roleplay', provider: 'anthropic', latencyMs: 800, inputTokens: 1000, outputTokens: 50, costEur: 0.001, ok: true });
    recordCall({ mode: 'score',    provider: 'gemini',    latencyMs: 1500, inputTokens: 2000, outputTokens: 300, costEur: 0,     ok: true });
    const evs = getAllEvents();
    expect(evs).toHaveLength(2);
    expect(evs[0].mode).toBe('roleplay');
    expect(evs[1].provider).toBe('gemini');
  });

  it('caps at 200 events (rolling window)', () => {
    for (let i = 0; i < 250; i++) {
      recordCall({ mode: 'roleplay', provider: 'anthropic', latencyMs: 1, inputTokens: 1, outputTokens: 1, costEur: 0, ok: true });
    }
    expect(getAllEvents().length).toBe(200);
  });
});

describe('rollup', () => {
  it('empty events → all zeros', () => {
    const r = rollup([]);
    expect(r.totalCalls).toBe(0);
    expect(r.totalCostEur).toBe(0);
    expect(r.p50LatencyMs).toBe(0);
  });

  it('sums cost, tokens, groups by provider', () => {
    recordCall({ mode: 'roleplay', provider: 'anthropic', latencyMs: 800, inputTokens: 1000, outputTokens: 100, costEur: 0.005, ok: true });
    recordCall({ mode: 'roleplay', provider: 'anthropic', latencyMs: 900, inputTokens: 1200, outputTokens: 120, costEur: 0.006, ok: true });
    recordCall({ mode: 'score',    provider: 'gemini',    latencyMs: 2000, inputTokens: 3000, outputTokens: 400, costEur: 0,    ok: true });
    const r = rollup();
    expect(r.totalCalls).toBe(3);
    expect(r.totalCostEur).toBeCloseTo(0.011, 5);
    expect(r.byProvider.anthropic.calls).toBe(2);
    expect(r.byProvider.gemini.calls).toBe(1);
    expect(r.byProvider.anthropic.tokensIn).toBe(2200);
    expect(r.p50LatencyMs).toBeGreaterThan(0);
    expect(r.p95LatencyMs).toBeGreaterThanOrEqual(r.p50LatencyMs);
  });

  it('projects perSession + perMonth from average', () => {
    for (let i = 0; i < 4; i++) {
      recordCall({ mode: 'roleplay', provider: 'anthropic', latencyMs: 500, inputTokens: 1000, outputTokens: 50, costEur: 0.01, ok: true });
    }
    const r = rollup();
    // avg per call = 0.01; × 15 calls/session = 0.15; × 30 sessions = 4.5
    expect(r.perSessionEur).toBeCloseTo(0.15, 5);
    expect(r.perMonthEur).toBeCloseTo(4.5, 5);
  });

  it('failed calls do not count toward latency percentiles', () => {
    recordCall({ mode: 'roleplay', provider: 'anthropic', latencyMs: 10000, inputTokens: 0, outputTokens: 0, costEur: 0, ok: false, errorCode: 'upstream_failure' });
    recordCall({ mode: 'roleplay', provider: 'anthropic', latencyMs: 500,   inputTokens: 1000, outputTokens: 50, costEur: 0.005, ok: true });
    const r = rollup();
    expect(r.totalCalls).toBe(2);
    expect(r.p50LatencyMs).toBe(500); // only the one successful measurement
  });
});
