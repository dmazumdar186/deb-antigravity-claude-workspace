// POST /api/outreach/:id/draft  body {draft_subject, draft_body}
//
// Saves operator edits to the draft. Does not change status (that's what
// the queued→drafted transition is for) — this endpoint may be called
// repeatedly while an operator is editing before hitting "mark sent".

import type { Env } from '../../../_middleware';
import { requireSupabase } from '../../../_lib/supabase';
import { BadRequestError, errorJson, json, readJsonBody, withErrorHandling } from '../../../_lib/http';

export const onRequestPost: PagesFunction<Env> = (context) =>
  withErrorHandling(async () => {
    const id = context.params.id;
    if (typeof id !== 'string') return errorJson(400, 'missing outreach id');

    const body = await readJsonBody<{ draft_subject?: string; draft_body?: string }>(context.request);
    if (typeof body.draft_subject !== 'string' || typeof body.draft_body !== 'string') {
      throw new BadRequestError('draft_subject and draft_body are required strings');
    }

    const db = requireSupabase(context.env);
    const existing = await db.getById<{ id: string; status: string }>('outreach', id, 'id,status');
    if (!existing) return errorJson(404, 'outreach row not found');

    const patch: Record<string, unknown> = { draft_subject: body.draft_subject, draft_body: body.draft_body };
    if (existing.status === 'queued') patch.status = 'drafted';

    const updated = await db.patch('outreach', id, patch);
    await db.logEvent('outreach', id, 'draft:saved', {});
    return json({ outreach: updated });
  });
