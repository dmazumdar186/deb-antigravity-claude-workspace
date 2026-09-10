// Pure functions for the daily queue: cap rules, halt (bounce-rate) logic,
// and next_touch_at math. Kept dependency-free (no fetch, no Date.now())
// so test/queue.test.ts can exercise them with fake rows. CONTRACTS.md
// "Outreach state machine" section + PROJECT_SPEC.md §8.2 (touch plan).

import { TOUCH_DAYS } from './state';

export interface Phase0Config {
  passed?: boolean;
  sends?: number;
  calls_booked?: number;
  queue_cap_locked?: number;
  queue_cap_open?: number;
}

/** Queue cap: phase0.passed false -> 5/day, true -> 20/day. */
export function capForPhase0(phase0: Phase0Config | null | undefined): number {
  const locked = phase0?.queue_cap_locked ?? 5;
  const open = phase0?.queue_cap_open ?? 20;
  return phase0?.passed ? open : locked;
}

/**
 * next_touch_at = sent date + (touch_days[touch] - touch_days[touch-1]),
 * touch_days = [0, 3, 7, 12] indexed by the touch NUMBER just sent
 * (touch=1 -> index 1 minus index 0 -> +3d, touch=2 -> +4d, touch=3 -> +5d).
 * Defined only for touch 1-3 — there is no touch 5, so touch 4 has no next
 * scheduled date to compute; its row already carries the next_touch_at set
 * when it was inserted (day 12), and that existing value plus a 5-day grace
 * is what `sent→closed_lost` checks (see touch4GraceExpired below and
 * `sent→closed_lost` in CONTRACTS.md). Callers must not call this for
 * touch === 4 — check touch < 4 first (mirrors "when touch < 4 inserts the
 * next touch row" in CONTRACTS.md).
 */
export function computeNextTouchAt(sentAtIso: string, touch: number): string {
  if (touch < 1 || touch > 3) {
    throw new RangeError(`touch out of range for computeNextTouchAt (must be 1-3, touch 4 has no next touch): ${touch}`);
  }
  const sent = new Date(sentAtIso);
  if (Number.isNaN(sent.getTime())) {
    throw new RangeError(`invalid sentAtIso: ${sentAtIso}`);
  }
  // touch is validated to 1..4 above, so both indices are in range.
  const delta = TOUCH_DAYS[touch]! - TOUCH_DAYS[touch - 1]!;
  const next = new Date(Date.UTC(sent.getUTCFullYear(), sent.getUTCMonth(), sent.getUTCDate()));
  next.setUTCDate(next.getUTCDate() + delta);
  return next.toISOString().slice(0, 10);
}

/** True once touch 4 was sent and (next_touch_at + 5 days) has passed. */
export function touch4GraceExpired(nextTouchAtIso: string, asOfIso: string): boolean {
  const next = new Date(nextTouchAtIso + 'T00:00:00Z');
  const grace = new Date(next);
  grace.setUTCDate(grace.getUTCDate() + 5);
  const asOf = new Date(asOfIso + 'T00:00:00Z');
  return asOf.getTime() >= grace.getTime();
}

export interface SentRowForBounce {
  status: string;
  sent_at: string | null;
  reply_sentiment: string | null;
}

/**
 * Rolling 30-day bounce rate over sent rows: bounces / sends in the window
 * ending at asOfIso (inclusive), 30 days back. Returns 0 when there were no
 * sends in the window (undefined rate treated as "not halted").
 */
export function bounceRate30d(rows: SentRowForBounce[], asOfIso: string): number {
  const asOf = new Date(asOfIso + 'T00:00:00Z');
  const windowStart = new Date(asOf);
  windowStart.setUTCDate(windowStart.getUTCDate() - 30);

  let sends = 0;
  let bounces = 0;
  for (const row of rows) {
    if (!row.sent_at) continue;
    const sentAt = new Date(row.sent_at);
    if (Number.isNaN(sentAt.getTime())) continue;
    if (sentAt < windowStart || sentAt > asOf) continue;
    sends += 1;
    if (row.reply_sentiment === 'bounce') bounces += 1;
  }
  if (sends === 0) return 0;
  return bounces / sends;
}

export const BOUNCE_HALT_THRESHOLD = 0.02;

export function isHalted(rate: number): boolean {
  return rate > BOUNCE_HALT_THRESHOLD;
}

export function haltReason(rate: number): string {
  return `rolling 30-day bounce rate ${(rate * 100).toFixed(2)}% exceeds ${(BOUNCE_HALT_THRESHOLD * 100).toFixed(0)}% — sends paused, protect the domain`;
}

export interface QueueEligibilityRow {
  touch: number;
  business: { do_not_contact?: boolean | null } | null;
  preview: { status?: string | null } | null;
}

/**
 * Excludes do_not_contact businesses (any touch) and, for touch 1 only,
 * previews that are not approved/live (a touch-1 email is not allowed to go
 * out before a human has approved the preview it links to; touches 2-4 for
 * an already-sent touch 1 are not re-gated on preview status).
 */
export function filterEligibleForQueue<T extends QueueEligibilityRow>(rows: T[]): T[] {
  return rows.filter((row) => {
    if (row.business?.do_not_contact) return false;
    if (row.touch === 1) {
      const status = row.preview?.status;
      if (status !== 'approved' && status !== 'live') return false;
    }
    return true;
  });
}

export interface ScoredRow {
  total_score: number | null;
}

/** Order by latest audit total_score desc (nulls last), then cap. */
export function sortAndCapQueue<T extends ScoredRow>(rows: T[], cap: number): T[] {
  const sorted = [...rows].sort((a, b) => {
    const av = a.total_score ?? -Infinity;
    const bv = b.total_score ?? -Infinity;
    return bv - av;
  });
  return sorted.slice(0, Math.max(0, cap));
}
