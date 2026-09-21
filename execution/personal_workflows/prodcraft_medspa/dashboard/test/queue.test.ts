import { describe, expect, it } from 'vitest';
import {
  BOUNCE_HALT_THRESHOLD,
  bounceRate30d,
  capForPhase0,
  computeNextTouchAt,
  filterEligibleForQueue,
  isHalted,
  sortAndCapQueue,
  touch4GraceExpired,
} from '../functions/_lib/queue';

describe('capForPhase0', () => {
  it('is 5/day when phase0 has not passed', () => {
    expect(capForPhase0({ passed: false })).toBe(5);
    expect(capForPhase0(null)).toBe(5);
    expect(capForPhase0(undefined)).toBe(5);
  });
  it('is 20/day once phase0 has passed', () => {
    expect(capForPhase0({ passed: true })).toBe(20);
  });
  it('honors explicit queue_cap_locked / queue_cap_open overrides', () => {
    expect(capForPhase0({ passed: false, queue_cap_locked: 3 })).toBe(3);
    expect(capForPhase0({ passed: true, queue_cap_open: 25 })).toBe(25);
  });
});

describe('computeNextTouchAt', () => {
  it('touch 1 sent -> +3 days (day 0 to day 3)', () => {
    expect(computeNextTouchAt('2026-09-10T12:00:00Z', 1)).toBe('2026-09-13');
  });
  it('touch 2 sent -> +4 days (day 3 to day 7)', () => {
    expect(computeNextTouchAt('2026-09-10T00:00:00Z', 2)).toBe('2026-09-14');
  });
  it('touch 3 sent -> +5 days (day 7 to day 12)', () => {
    expect(computeNextTouchAt('2026-09-10T00:00:00Z', 3)).toBe('2026-09-15');
  });
  it('touch 4 has no next touch and is rejected (no touch 5 exists)', () => {
    expect(() => computeNextTouchAt('2026-09-10T00:00:00Z', 4)).toThrow(RangeError);
  });
  it('rejects out-of-range touch numbers', () => {
    expect(() => computeNextTouchAt('2026-09-10T00:00:00Z', 0)).toThrow(RangeError);
    expect(() => computeNextTouchAt('2026-09-10T00:00:00Z', 5)).toThrow(RangeError);
  });
  it('rejects an invalid date', () => {
    expect(() => computeNextTouchAt('not-a-date', 1)).toThrow(RangeError);
  });
  it('carries across month boundaries', () => {
    expect(computeNextTouchAt('2026-09-29T00:00:00Z', 3)).toBe('2026-10-04');
  });
});

describe('touch4GraceExpired', () => {
  it('is false before the 5-day grace passes', () => {
    expect(touch4GraceExpired('2026-09-22', '2026-09-26')).toBe(false);
  });
  it('is true once the 5-day grace has passed', () => {
    expect(touch4GraceExpired('2026-09-22', '2026-09-27')).toBe(true);
    expect(touch4GraceExpired('2026-09-22', '2026-10-01')).toBe(true);
  });
});

describe('bounceRate30d / isHalted', () => {
  const asOf = '2026-09-10';
  it('is 0 with no sends in the window', () => {
    expect(bounceRate30d([], asOf)).toBe(0);
  });
  it('computes bounces / sends within the trailing 30-day window', () => {
    const rows = [
      { status: 'sent', sent_at: '2026-09-01T00:00:00Z', reply_sentiment: null },
      { status: 'sent', sent_at: '2026-09-02T00:00:00Z', reply_sentiment: 'bounce' },
      { status: 'sent', sent_at: '2026-08-01T00:00:00Z', reply_sentiment: 'bounce' }, // outside window
      { status: 'sent', sent_at: null, reply_sentiment: null }, // never sent, ignored
    ];
    expect(bounceRate30d(rows, asOf)).toBeCloseTo(0.5, 5);
  });
  it('halts only once the rate exceeds the 2% threshold, not at exactly 2%', () => {
    const rows: { status: string; sent_at: string; reply_sentiment: string | null }[] = Array.from(
      { length: 100 },
      (_, i) => ({
        status: 'sent',
        sent_at: '2026-09-05T00:00:00Z',
        reply_sentiment: i < 2 ? 'bounce' : null,
      }),
    );
    const rate = bounceRate30d(rows, asOf);
    expect(rate).toBeCloseTo(0.02, 5);
    expect(isHalted(rate)).toBe(false);

    rows[2] = { ...rows[2]!, reply_sentiment: 'bounce' };
    const rate2 = bounceRate30d(rows, asOf);
    expect(rate2).toBeGreaterThan(BOUNCE_HALT_THRESHOLD);
    expect(isHalted(rate2)).toBe(true);
  });
});

describe('filterEligibleForQueue', () => {
  it('excludes do_not_contact businesses at any touch', () => {
    const rows = [
      { touch: 2, business: { do_not_contact: true }, preview: { status: 'approved' } },
      { touch: 1, business: { do_not_contact: false }, preview: { status: 'approved' } },
    ];
    const out = filterEligibleForQueue(rows);
    expect(out).toHaveLength(1);
    expect(out[0]!.touch).toBe(1);
  });

  it('excludes touch-1 rows whose preview is not approved/live', () => {
    const rows = [
      { touch: 1, business: {}, preview: { status: 'review' } },
      { touch: 1, business: {}, preview: { status: 'approved' } },
      { touch: 1, business: {}, preview: { status: 'live' } },
      { touch: 1, business: {}, preview: null },
    ];
    const out = filterEligibleForQueue(rows);
    expect(out.map((r) => r.preview?.status)).toEqual(['approved', 'live']);
  });

  it('does not gate touch 2-4 rows on preview status (already-sent touch 1 continues the sequence)', () => {
    const rows = [
      { touch: 3, business: {}, preview: { status: 'review' } },
      { touch: 4, business: {}, preview: null },
    ];
    expect(filterEligibleForQueue(rows)).toHaveLength(2);
  });
});

describe('sortAndCapQueue', () => {
  it('orders by total_score desc and applies the cap', () => {
    const rows = [{ total_score: 10 }, { total_score: 90 }, { total_score: 45 }, { total_score: 70 }];
    const out = sortAndCapQueue(rows, 2);
    expect(out.map((r) => r.total_score)).toEqual([90, 70]);
  });
  it('sorts null scores last', () => {
    const rows = [{ total_score: null }, { total_score: 30 }];
    const out = sortAndCapQueue(rows, 2);
    expect(out.map((r) => r.total_score)).toEqual([30, null]);
  });
  it('cap of 0 returns an empty queue (halted state)', () => {
    expect(sortAndCapQueue([{ total_score: 50 }], 0)).toEqual([]);
  });
});
