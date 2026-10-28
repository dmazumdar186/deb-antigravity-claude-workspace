// GET /api/stats — behind the export auth: the last 30 days of first-party event counts as JSON.
import { Env, json, logError } from './_lib';
import { guard } from './_auth';
import { EVENTS } from './event';

export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
  const denied = await guard(env, request); if (denied) return denied;
  if (!env.JEEVANA_KV) return json({ ok: false, error: 'storage unavailable' }, 503);
  try {
    const days: Record<string, Record<string, number>> = {};
    const since = new Date(Date.now() - 29 * 864e5).toISOString().slice(0, 10);
    let cursor: string | undefined;
    do {
      const page = await env.JEEVANA_KV.list({ prefix: 'ev:', cursor });
      for (const k of page.keys) {
        const [, day, name] = k.name.split(':');
        if (!day || day < since || !EVENTS.has(name)) continue;
        const v = parseInt((await env.JEEVANA_KV.get(k.name)) || '0', 10) || 0;
        (days[day] ||= {})[name] = v;
      }
      cursor = page.list_complete ? undefined : page.cursor;
    } while (cursor);
    return json({ ok: true, since, days });
  } catch (err) {
    logError('stats', err);
    return json({ ok: false, error: 'internal' }, 500);
  }
};
