// POST /api/previews/:id/status  body {status}
//
// Allowed transitions: review→approved, approved→review, any→takedown.
// On takedown: also patch business.do_not_contact = true and log an
// `events` row (entity=preview, event=takedown). Every accepted transition
// logs an events row (entity=preview, event=`status:<from>-><to>`).

import type { Env } from '../../../_middleware';
import { requireSupabase } from '../../../_lib/supabase';
import { BadRequestError, errorJson, json, readJsonBody, withErrorHandling } from '../../../_lib/http';

type PreviewStatus = 'review' | 'approved' | 'live' | 'expired' | 'takedown';

const ALLOWED: Record<PreviewStatus, PreviewStatus[]> = {
  review: ['approved', 'takedown'],
  approved: ['review', 'takedown'],
  live: ['takedown'],
  expired: ['takedown'],
  takedown: [],
};

function canTransitionPreview(from: PreviewStatus, to: PreviewStatus): boolean {
  if (to === 'takedown') return true;
  return ALLOWED[from]?.includes(to) ?? false;
}

export const onRequestPost: PagesFunction<Env> = (context) =>
  withErrorHandling(async () => {
    const id = context.params.id;
    if (typeof id !== 'string') return errorJson(400, 'missing preview id');

    const body = await readJsonBody<{ status?: string }>(context.request);
    const to = body.status;
    if (!to || !['review', 'approved', 'live', 'expired', 'takedown'].includes(to)) {
      throw new BadRequestError('status must be one of review|approved|live|expired|takedown');
    }

    const db = requireSupabase(context.env);
    const preview = await db.getById<{ id: string; status: PreviewStatus; business_id: string }>('previews', id, 'id,status,business_id');
    if (!preview) return errorJson(404, 'preview not found');

    const from = preview.status;
    const toStatus = to as PreviewStatus;
    if (!canTransitionPreview(from, toStatus)) {
      return errorJson(409, `illegal preview transition: ${from} -> ${toStatus}`);
    }

    const patch: Record<string, unknown> = { status: toStatus };
    if (toStatus === 'takedown') {
      patch.takedown = true;
      patch.takedown_at = new Date().toISOString();
    }
    const updated = await db.patch('previews', id, patch);

    await db.logEvent('preview', id, `status:${from}->${toStatus}`, { from, to: toStatus });

    if (toStatus === 'takedown') {
      await db.patch('businesses', preview.business_id, { do_not_contact: true });
      await db.logEvent('business', preview.business_id, 'do_not_contact:true', { reason: 'preview takedown', preview_id: id });
    }

    return json({ preview: updated });
  });
