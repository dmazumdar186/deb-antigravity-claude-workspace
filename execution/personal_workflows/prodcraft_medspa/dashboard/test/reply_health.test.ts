import { describe, expect, it } from 'vitest';
import { replyRateHealthOf, REPLY_RATE_MIN_SENDS } from '../functions/api/stats';

describe('replyRateHealthOf', () => {
  it('needs a minimum sample before judging', () => {
    expect(replyRateHealthOf(REPLY_RATE_MIN_SENDS - 1, 10)).toBe('insufficient_data');
  });
  it('classifies the three bands the panel named', () => {
    expect(replyRateHealthOf(100, 15)).toBe('on_track');
    expect(replyRateHealthOf(100, 6)).toBe('below_target');
    expect(replyRateHealthOf(100, 3)).toBe('below_platform_average');
  });
  it('handles zero replies', () => {
    expect(replyRateHealthOf(50, 0)).toBe('below_platform_average');
  });
});
