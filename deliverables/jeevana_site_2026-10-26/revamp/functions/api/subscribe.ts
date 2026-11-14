// POST /api/subscribe — newsletter opt-in (dialog + footer row). Phone stays optional (operator decision 2026-10-26).
// Body: { email, phone?, consent, website (honeypot), lang, source, source_url }
// 200 { ok:true } · 400 / 413 { ok:false, error } · 429 rate_limited · 503 storage unavailable · 500 internal.
// KV: news:<sha256(email)> -> { email, phone?, lang, source, consent_ts, consent_text, unsubscribe_token }.
// Re-subscribing is idempotent: the original consent_ts and token are kept.
import { Env, EMAIL_RE, PHONE_RE, json, sha256Hex, randomHex, str, consentOk, rateLimited, readBody, badBody, noStore, fail, notify } from './_lib';

export const CONSENT_TEXT = {
  en: "I agree to receive Jeevana's newsletter by email. I can unsubscribe at any time.",
  fr: "J'accepte de recevoir la lettre d'information de Jeevana par e-mail. Je peux me désinscrire à tout moment.",
};

export const onRequestPost: PagesFunction<Env> = async (ctx) => {
  const { request, env } = ctx;
  const b = await readBody(request);
  const bad = badBody(b); if (bad) return bad;
  const body = b as Record<string, unknown>;
  if (str(body.website, 200)) return json({ ok: true }); // honeypot: pretend success, store nothing
  const email = str(body.email, 254).toLowerCase();
  const phone = str(body.phone, 40);
  if (!email || !EMAIL_RE.test(email)) return json({ ok: false, error: 'bad_email' }, 400);
  if (phone && !PHONE_RE.test(phone)) return json({ ok: false, error: 'bad_phone' }, 400);
  if (!consentOk(body.consent)) return json({ ok: false, error: 'consent_required' }, 400);
  if (!env.JEEVANA_KV) return noStore();
  if (await rateLimited(env, request, 'news')) return json({ ok: false, error: 'rate_limited' }, 429, { 'Retry-After': '600' });
  try {
    const key = `news:${await sha256Hex(email)}`;
    const prev = await env.JEEVANA_KV.get(key);
    const old = prev ? (JSON.parse(prev) as Record<string, unknown>) : null;
    const lang = body.lang === 'fr' ? 'fr' : 'en';
    const rec: Record<string, unknown> = {
      email, lang, source: str(body.source, 20), source_url: str(body.source_url, 300),
      consent_ts: (old && old.consent_ts) || new Date().toISOString(),
      consent_text: (old && old.consent_text) || CONSENT_TEXT[lang],
      unsubscribe_token: (old && old.unsubscribe_token) || randomHex(24),
    };
    if (phone) rec.phone = phone; else if (old && old.phone) rec.phone = old.phone;
    await env.JEEVANA_KV.put(key, JSON.stringify(rec));
    await env.JEEVANA_KV.put(`unsub:${rec.unsubscribe_token}`, key);
    if (!old) ctx.waitUntil(notify(env, `Nouvelle inscription — ${email}`, ['Newsletter', `email: ${email}`, `phone: ${rec.phone || '-'}`, `lang: ${lang}`, `source: ${rec.source}`]));
    return json({ ok: true });
  } catch (err) {
    return fail('subscribe', err);
  }
};
