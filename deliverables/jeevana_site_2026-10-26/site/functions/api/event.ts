// POST /api/event { name } — first-party counts only, no PII. KV ev:<YYYY-MM-DD>:<name> += 1 (non-atomic, fine for counts).
import { Env, json, readBody, logError, rateLimited } from './_lib';

export const EVENTS = new Set(['cover_complete', 'deck_open', 'register_start', 'register_done', 'newsletter_open', 'newsletter_done', 'wa_tap', 'ig_tap', 'call_tap', 'lang_fr']);

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
  const b = await readBody(request);
  const name = b && b !== 'too_large' ? String(b.name || '') : '';
  if (!EVENTS.has(name)) return json({ ok: false, error: 'unknown_event' }, 400);
  if (!env.JEEVANA_KV) return json({ ok: false, error: 'storage unavailable' }, 503);
  if (await rateLimited(env, request, 'ev', 120)) return json({ ok: false, error: 'rate_limited' }, 429);
  try {
    const key = `ev:${new Date().toISOString().slice(0, 10)}:${name}`;
    const n = parseInt((await env.JEEVANA_KV.get(key)) || '0', 10) || 0;
    await env.JEEVANA_KV.put(key, String(n + 1), { expirationTtl: 60 * 60 * 24 * 400 });
    return json({ ok: true });
  } catch (err) {
    logError('event', err);
    return json({ ok: false, error: 'internal' }, 500);
  }
};
