// GET /api/queue?date=YYYY-MM-DD
//
// Today's queue: outreach rows with next_touch_at <= date and status in
// (queued, drafted, sent), ordered by latest audit total_score desc, capped
// by config.phase0 (5 if not passed, else 20). Each row is joined with its
// business, its audit (via outreach.audit_id — the audit that produced the
// gaps/score this touch is drafted against), and its preview.
//
// Assumption (see README "Assumptions"): "latest audit" is read via
// outreach.audit_id (set when the row was created/drafted from a specific
// audit) rather than re-querying businesses' most-recent audit, since the
// schema already carries that FK and it keeps the score a queue card shows
// pinned to the audit the draft was actually written against.
//
// Returns `halted: {reason}` (and an empty queue) when the rolling 30-day
// bounce rate exceeds 2%.

import type { Env } from '../_middleware';
import { requireSupabase } from '../_lib/supabase';
import { json, withErrorHandling } from '../_lib/http';
import { bounceRate30d, capForPhase0, filterEligibleForQueue, haltReason, isHalted, sortAndCapQueue } from '../_lib/queue';

interface OutreachRow {
  id: string;
  business_id: string;
  preview_id: string | null;
  audit_id: string | null;
  touch: number;
  status: string;
  draft_subject: string | null;
  draft_body: string | null;
  next_touch_at: string | null;
  sent_at: string | null;
  business: {
    id: string;
    name: string;
    owner_first: string | null;
    owner_email: string | null;
    email_status: string | null;
    website_url: string | null;
    suburb: string | null;
    do_not_contact: boolean;
  } | null;
  audit: {
    total_score: number | null;
    bucket: string | null;
    gaps: unknown;
    screenshot_mobile_url: string | null;
    screenshot_desktop_url: string | null;
  } | null;
  preview: {
    subdomain_url: string | null;
    status: string | null;
  } | null;
}

export const onRequestGet: PagesFunction<Env> = (context) =>
  withErrorHandling(async () => {
    const url = new URL(context.request.url);
    const date = url.searchParams.get('date') ?? new Date().toISOString().slice(0, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
      return json({ error: 'date must be YYYY-MM-DD' }, { status: 400 });
    }

    const db = requireSupabase(context.env);

    const phase0 = await db.getConfig<{ passed?: boolean }>('phase0');
    const cap = capForPhase0(phase0);

    // Bounce window: pull sent rows from the 35 days before `date` (30-day
    // window + slack) so bounceRate30d has everything it needs.
    const windowStart = new Date(date + 'T00:00:00Z');
    windowStart.setUTCDate(windowStart.getUTCDate() - 35);
    const sentRows = await db.select<{ status: string; sent_at: string | null; reply_sentiment: string | null }>(
      'outreach',
      {
        select: 'status,sent_at,reply_sentiment',
        filters: [
          { column: 'status', op: 'in', value: ['sent', 'replied', 'call_booked', 'closed_won', 'closed_lost'] },
          { column: 'sent_at', op: 'gte', value: windowStart.toISOString() },
        ],
      },
    );
    const rate = bounceRate30d(sentRows, date);
    if (isHalted(rate)) {
      return json({ queue: [], halted: { reason: haltReason(rate) } });
    }

    const rows = await db.select<OutreachRow>('outreach', {
      select:
        'id,business_id,preview_id,audit_id,touch,status,draft_subject,draft_body,next_touch_at,sent_at,' +
        'business:businesses(id,name,owner_first,owner_email,email_status,website_url,suburb,do_not_contact),' +
        'audit:audits(total_score,bucket,gaps,screenshot_mobile_url,screenshot_desktop_url),' +
        'preview:previews(subdomain_url,status)',
      filters: [
        { column: 'next_touch_at', op: 'lte', value: date },
        { column: 'status', op: 'in', value: ['queued', 'drafted', 'sent'] },
      ],
    });

    const eligible = filterEligibleForQueue(
      rows.map((r) => ({ ...r, business: r.business, preview: r.preview })),
    );
    const capped = sortAndCapQueue(
      eligible.map((r) => ({ ...r, total_score: r.audit?.total_score ?? null })),
      cap,
    );

    return json({ queue: capped, cap, date });
  });
