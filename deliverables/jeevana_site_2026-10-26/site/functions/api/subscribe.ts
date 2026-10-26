// POST /api/subscribe — newsletter opt-in (dialog + footer row).
// Body: { email, phone?, consent, website (honeypot), lang, source, source_url }
// 200 { ok:true } · 400 { ok:false, error } · 429 rate_limited · 500 internal. Repeat emails return 200 (non-enumerable).
// KV: news:<sha256(email)> -> { email, phone, ts, lang, source, source_url, consent:true }
import { Env, EMAIL_RE, json, sha256Hex, str, consentOk, rateLimited, readBody } from './_lib';

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
  const b = await readBody(request);
  if (!b) return json({ ok: false, error: 'bad_body' }, 400);
  if (str(b.website, 200)) return json({ ok: true }); // honeypot: pretend success, store nothing
  const email = str(b.email, 254).toLowerCase();
  const phone = str(b.phone, 40);
  if (!email || !EMAIL_RE.test(email)) return json({ ok: false, error: 'bad_email' }, 400);
  if (phone && !/^[+\d][\d\s().-]{5,39}$/.test(phone)) return json({ ok: false, error: 'bad_phone' }, 400);
  if (!consentOk(b.consent)) return json({ ok: false, error: 'consent_required' }, 400);
  if (await rateLimited(env, request, 'news')) return json({ ok: false, error: 'rate_limited' }, 429, { 'Retry-After': '600' });
  if (!env.JEEVANA_KV) return json({ ok: false, error: 'internal' }, 500);
  try {
    const rec = {
      email, phone, ts: new Date().toISOString(), lang: b.lang === 'fr' ? 'fr' : 'en',
      source: str(b.source, 20), source_url: str(b.source_url, 300), consent: true,
    };
    await env.JEEVANA_KV.put(`news:${await sha256Hex(email)}`, JSON.stringify(rec));
    return json({ ok: true });
  } catch {
    return json({ ok: false, error: 'internal' }, 500);
  }
};
