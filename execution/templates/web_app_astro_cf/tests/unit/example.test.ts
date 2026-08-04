import { describe, it, expect } from 'vitest';
import { estimateCostEUR, MODEL_PRICING_USD } from '../../src/lib/telemetry';

describe('telemetry.estimateCostEUR', () => {
  it('returns 0 for unknown models', () => {
    expect(estimateCostEUR('made-up-model', { input_tokens: 1000, output_tokens: 500 })).toBe(0);
  });

  it('computes non-zero cost for known models', () => {
    const cost = estimateCostEUR('gemini-2.5-flash', { input_tokens: 100_000, output_tokens: 10_000 });
    expect(cost).toBeGreaterThan(0);
    expect(cost).toBeLessThan(0.05); // Gemini flash is cheap
  });

  it('includes cache pricing entries per known model', () => {
    for (const model of Object.keys(MODEL_PRICING_USD)) {
      const p = MODEL_PRICING_USD[model];
      expect(p.input).toBeGreaterThan(0);
      expect(p.cache_read).toBeGreaterThan(0);
      expect(p.cache_write).toBeGreaterThan(0);
      expect(p.output).toBeGreaterThan(0);
    }
  });
});
