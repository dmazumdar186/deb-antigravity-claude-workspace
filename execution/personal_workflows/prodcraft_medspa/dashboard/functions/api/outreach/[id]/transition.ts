// POST /api/outreach/:id/transition  body {to, sent_at?, notes?, reply_sentiment?}
//
// Validated by canTransition (functions/_lib/state.ts). Side effects:
//  - to "sent": sets sent_at (body.sent_at or now), computes next_touch_at
//    via computeNextTouchAt(sent_at, touch); when touch < 4 inserts the
//    touch+1 row as queued with the same next_touch_at (unique on
//    business_id,touch — insert ignores the conflict rather than erroring,
//    so retried transitions are idempotent); increments config.phase0.sends
//    when touch === 1.
//  - to "call_booked": increments config.phase0.calls_booked; sets
//    config.phase0.passed = true once calls_booked >= 1.
//  - to "dnc": patches businesses.do_not_contact = true, takes down any
//    preview for the business, and cancels (dnc) every other open touch row
//    for the same business.
// Every accepted transition logs an `events` row (entity=outreach).

import type { Env } from '../../../_middleware';
import { requireSupabase, type SupabaseClient } from '../../../_lib/supabase';
import { BadRequestError, errorJson, json, readJsonBody, withErrorHandling } from '../../../_lib/http';
import { assertTransition, isOutreachState, IllegalTransition, type OutreachState } from '../../../_lib/state';
import { computeNextTouchAt } from '../../../_lib/queue';

interface OutreachRow {
  id: string;
  business_id: string;
  preview_id: string | null;
  audit_id: string | null;
  touch: number;
  status: OutreachState;
  next_touch_at: string | null;
}

interface Phase0 {
  passed?: boolean;
  sends?: number;
  calls_booked?: number;
  queue_cap_locked?: number;
  queue_cap_open?: number;
}

async function cancelOtherTouches(db: SupabaseClient, businessId: string, exceptId: string): Promise<void> {
  const rows = await db.select<{ id: string; status: OutreachState }>('outreach', {
    select: 'id,status',
    filters: [{ column: 'business_id', op: 'eq', value: businessId }],
  });
  for (const row of rows) {
    if (row.id === exceptId) continue;
    if (row.status === 'closed_won' || row.status === 'closed_lost' || row.status === 'dnc') continue;
    await db.patch('outreach', row.id, { status: 'dnc' });
    await db.logEvent('outreach', row.id, `status:${row.status}->dnc`, { reason: 'cascaded from dnc', source_outreach_id: exceptId });
  }
}

export const onRequestPost: PagesFunction<Env> = (context) =>
  withErrorHandling(async () => {
    const id = context.params.id;
    if (typeof id !== 'string') return errorJson(400, 'missing outreach id');

    const body = await readJsonBody<{ to?: string; sent_at?: string; notes?: string; reply_sentiment?: string }>(
      context.request,
    );
    if (!body.to || !isOutreachState(body.to)) {
      throw new BadRequestError('to must be a valid outreach state');
    }
    const to = body.to;

    const db = requireSupabase(context.env);
    const row = await db.getById<OutreachRow>('outreach', id, 'id,business_id,preview_id,audit_id,touch,status,next_touch_at');
    if (!row) return errorJson(404, 'outreach row not found');

    try {
      assertTransition(row.status, to);
    } catch (err) {
      if (err instanceof IllegalTransition) return errorJson(409, err.message);
      throw err;
    }

    const patch: Record<string, unknown> = { status: to };
    if (body.notes !== undefined) patch.notes = body.notes;
    if (body.reply_sentiment !== undefined) patch.reply_sentiment = body.reply_sentiment;

    let nextTouchAt: string | null = null;
    if (to === 'sent') {
      const sentAt = body.sent_at ?? new Date().toISOString();
      patch.sent_at = sentAt;
      // touch 4 has no next touch — computeNextTouchAt is undefined there;
      // its next_touch_at was already set when the row was queued (day 12)
      // and stays as-is for the sent→closed_lost grace check.
      if (row.touch < 4) {
        nextTouchAt = computeNextTouchAt(sentAt, row.touch);
        patch.next_touch_at = nextTouchAt;
      }
    }
    if (to === 'replied') {
      patch.replied_at = body.sent_at ?? new Date().toISOString();
    }

    const updated = await db.patch('outreach', id, patch);
    await db.logEvent('outreach', id, `status:${row.status}->${to}`, { from: row.status, to, notes: body.notes ?? null });

    if (to === 'sent') {
      if (row.touch < 4 && nextTouchAt) {
        await db.insert(
          'outreach',
          {
            business_id: row.business_id,
            preview_id: row.preview_id,
            audit_id: row.audit_id,
            touch: row.touch + 1,
            status: 'queued',
            next_touch_at: nextTouchAt,
          },
          { onConflict: 'business_id,touch', ignoreDuplicates: true },
        );
      }
      if (row.touch === 1) {
        const phase0 = (await db.getConfig<Phase0>('phase0')) ?? {};
        await db.setConfig('phase0', { ...phase0, sends: (phase0.sends ?? 0) + 1 });
      }
    }

    if (to === 'call_booked') {
      const phase0 = (await db.getConfig<Phase0>('phase0')) ?? {};
      const callsBooked = (phase0.calls_booked ?? 0) + 1;
      await db.setConfig('phase0', { ...phase0, calls_booked: callsBooked, passed: callsBooked >= 1 ? true : phase0.passed });
    }

    if (to === 'dnc') {
      await db.patch('businesses', row.business_id, { do_not_contact: true });
      await db.logEvent('business', row.business_id, 'do_not_contact:true', { reason: 'outreach dnc', outreach_id: id });
      if (row.preview_id) {
        await db.patch('previews', row.preview_id, { status: 'takedown', takedown: true, takedown_at: new Date().toISOString() });
        await db.logEvent('preview', row.preview_id, 'status:*->takedown', { reason: 'outreach dnc' });
      }
      await cancelOtherTouches(db, row.business_id, id);
    }

    return json({ outreach: updated });
  });
