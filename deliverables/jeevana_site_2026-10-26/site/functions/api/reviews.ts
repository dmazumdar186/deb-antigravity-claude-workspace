// GET  /api/reviews?offset=0&limit=10 -> { ok, total, average, counts[1..5], featured[], reviews[], rest_total, offset, limit }
//      featured = 3 newest published reviews rated 4-5; reviews = the other published ones, newest first.
// POST /api/reviews  body { name, rating 1-5, text, consent, website (honeypot), lang }
//      200 { ok:true, status:'published'|'pending' } · 400 { error: bad_name|bad_rating|bad_text|consent_required }
//      413 too_large · 429 rate_limited · 503 storage unavailable · 500 internal.
// Clean reviews publish at once; links, contact details, held words, all-caps text, a name containing "Jeevana",
// or a burst (>= 5 published in the last hour) wait for Jeevana (/api/review-admin).
// Idempotent: id = sha256(name|text), so a double submit or retry upserts the same record and never re-notifies.
import { Env, json, sha256Hex, consentOk, rateLimited, readBody, badBody, noStore, fail, notify } from './_lib';
import { Review, NAME_MIN, NAME_MAX, TEXT_MIN, TEXT_MAX, PAGE_SIZE, PAGE_MAX, REVIEW_CONSENT, clean, holdReason, rebuild, snapshot, view, putReview, burst } from './_reviews';

export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
  if (!env.JEEVANA_KV) return noStore();
  const q = new URL(request.url).searchParams;
  const offset = Math.max(0, Math.min(10000, parseInt(q.get('offset') || '0', 10) || 0));
  const limit = Math.max(1, Math.min(PAGE_MAX, parseInt(q.get('limit') || String(PAGE_SIZE), 10) || PAGE_SIZE));
  try {
    return json({ ok: true, ...view(await snapshot(env), offset, limit) }, 200, { 'Cache-Control': 'public, max-age=15' });
  } catch (err) {
    return fail('reviews:get', err);
  }
};

export const onRequestPost: PagesFunction<Env> = async (ctx) => {
  const { request, env } = ctx;
  const b = await readBody(request);
  const bad = badBody(b); if (bad) return bad;
  const body = b as Record<string, unknown>;
  if (String(body.website ?? '').trim()) return json({ ok: true, status: 'pending' }); // honeypot: pretend success, store nothing
  const name = clean(body.name, NAME_MAX + 1);
  const text = clean(body.text, TEXT_MAX + 1, true);
  const rating = Number(body.rating);
  if (name.length < NAME_MIN || name.length > NAME_MAX || !/^[\p{L}\p{M}][\p{L}\p{M} '’.-]*$/u.test(name)) return json({ ok: false, error: 'bad_name' }, 400);
  if (!Number.isInteger(rating) || rating < 1 || rating > 5) return json({ ok: false, error: 'bad_rating' }, 400);
  if (text.length < TEXT_MIN || text.length > TEXT_MAX) return json({ ok: false, error: 'bad_text' }, 400);
  if (!consentOk(body.consent)) return json({ ok: false, error: 'consent_required' }, 400);
  if (!env.JEEVANA_KV) return noStore();
  if (await rateLimited(env, request, 'review', 3)) return json({ ok: false, error: 'rate_limited' }, 429, { 'Retry-After': '600' });
  try {
    const id = (await sha256Hex('rev::' + name.toLowerCase() + '|' + text.toLowerCase())).slice(0, 20);
    const key = `rev:${id}`;
    const prev = await env.JEEVANA_KV.get(key);
    if (prev) { // same review again: no new record, no new email
      const old = JSON.parse(prev) as Review;
      return json({ ok: true, status: old.status === 'published' ? 'published' : 'pending' });
    }
    const lang = body.lang === 'fr' ? 'fr' : 'en';
    const reason = holdReason(name, text) || (burst(await snapshot(env)) ? 'burst' : '');
    const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
    const rec: Review = {
      id, name, rating, text, lang, ts: new Date().toISOString(),
      status: reason ? 'pending' : 'published', consent_text: REVIEW_CONSENT[lang],
      ip_hash: (await sha256Hex('jv::' + ip)).slice(0, 16),
    };
    if (reason) rec.hold_reason = reason;
    await putReview(env.JEEVANA_KV, rec);
    if (rec.status === 'published') await rebuild(env, rec);
    const stars = '★'.repeat(rating) + '☆'.repeat(5 - rating);
    ctx.waitUntil(notify(env, reason ? `Avis à vérifier — ${name} ${stars}` : `Nouvel avis publié — ${name} ${stars}`, [
      reason ? `En attente de votre validation (raison : ${reason}).` : 'Publié sur le site.',
      `Nom : ${name}`, `Note : ${rating}/5`, `Avis : ${text}`, '',
      'Gérer les avis : https://jeevana-yoga.pages.dev/api/review-admin',
    ]));
    return json({ ok: true, status: rec.status });
  } catch (err) {
    return fail('reviews:post', err);
  }
};
