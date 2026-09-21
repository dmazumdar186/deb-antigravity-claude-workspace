// GET  /api/config  → { proof_lines, sender, phase0 }
// POST /api/config  → body { proof_lines?, sender?, phase0? }
//
// phase0 is normally only mutated by transition side effects (sends,
// calls_booked, passed); a manual override here (e.g. operator forces
// `passed: true` before a real call_booked event, or resets it) must carry
// a `reason` in the request body — logged to `events` (entity=config).
// proof_lines / sender writes are logged too, for the same auditability.

import type { Env } from '../_middleware';
import { requireSupabase } from '../_lib/supabase';
import { BadRequestError, json, withErrorHandling, readJsonBody } from '../_lib/http';

// events.entity_id is `uuid not null` (db/schema.sql) — config rows are
// keyed by text, not uuid, so config-level events use this nil-uuid
// sentinel as entity_id and carry the real config key in the payload.
const CONFIG_EVENT_ENTITY_ID = '00000000-0000-0000-0000-000000000000';

interface ConfigBody {
  proof_lines?: string[];
  sender?: { name?: string; physical_address?: string; signature?: string };
  phase0?: { passed?: boolean; sends?: number; calls_booked?: number; queue_cap_locked?: number; queue_cap_open?: number };
  reason?: string;
}

export const onRequestGet: PagesFunction<Env> = (context) =>
  withErrorHandling(async () => {
    const db = requireSupabase(context.env);
    const [proofLines, sender, phase0] = await Promise.all([
      db.getConfig<string[]>('proof_lines'),
      db.getConfig<Record<string, string>>('sender'),
      db.getConfig<Record<string, unknown>>('phase0'),
    ]);
    return json({
      proof_lines: proofLines ?? [],
      sender: sender ?? { name: '', physical_address: '', signature: '' },
      phase0: phase0 ?? { passed: false, sends: 0, calls_booked: 0, queue_cap_locked: 5, queue_cap_open: 20 },
    });
  });

export const onRequestPost: PagesFunction<Env> = (context) =>
  withErrorHandling(async () => {
    const body = await readJsonBody<ConfigBody>(context.request);
    const db = requireSupabase(context.env);

    if (body.phase0 !== undefined && !body.reason) {
      throw new BadRequestError('phase0 override requires a reason');
    }

    if (body.proof_lines !== undefined) {
      if (!Array.isArray(body.proof_lines) || body.proof_lines.some((l) => typeof l !== 'string')) {
        throw new BadRequestError('proof_lines must be an array of strings');
      }
      await db.setConfig('proof_lines', body.proof_lines);
      await db.logEvent('config', CONFIG_EVENT_ENTITY_ID, 'config:updated', { key: 'proof_lines', reason: body.reason ?? null });
    }

    if (body.sender !== undefined) {
      await db.setConfig('sender', body.sender);
      await db.logEvent('config', CONFIG_EVENT_ENTITY_ID, 'config:updated', { key: 'sender', reason: body.reason ?? null });
    }

    if (body.phase0 !== undefined) {
      const existing = (await db.getConfig<Record<string, unknown>>('phase0')) ?? {};
      const merged = { ...existing, ...body.phase0 };
      await db.setConfig('phase0', merged);
      await db.logEvent('config', CONFIG_EVENT_ENTITY_ID, 'config:override', { key: 'phase0', reason: body.reason, patch: body.phase0 });
    }

    return json({ ok: true });
  });
