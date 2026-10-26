// POST /api/register — class registration.
// Body: { name, email, phone?, class, level, message?, consent, website (honeypot), lang, source_url }
// 200 { ok:true } · 400 { ok:false, error } · 429 rate_limited · 500 internal.
// KV: reg:<ts>-<rand> -> the validated record.
import { Env, EMAIL_RE, json, str, consentOk, rateLimited, readBody } from './_lib';

const LEVELS = new Set(['new', 'some', 'regular']);

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
  const b = await readBody(request);
  if (!b) return json({ ok: false, error: 'bad_body' }, 400);
  if (str(b.website, 200)) return json({ ok: true });
  const name = str(b.name, 120);
  const email = str(b.email, 254).toLowerCase();
  const phone = str(b.phone, 40);
  const klass = str(b.class, 60) || 'any';
  const level = LEVELS.has(str(b.level, 20)) ? str(b.level, 20) : 'new';
  const message = str(b.message, 2000);
  if (name.length < 1) return json({ ok: false, error: 'bad_name' }, 400);
  if (!email || !EMAIL_RE.test(email)) return json({ ok: false, error: 'bad_email' }, 400);
  if (phone && !/^[+\d][\d\s().-]{5,39}$/.test(phone)) return json({ ok: false, error: 'bad_phone' }, 400);
  if (!consentOk(b.consent)) return json({ ok: false, error: 'consent_required' }, 400);
  if (await rateLimited(env, request, 'reg')) return json({ ok: false, error: 'rate_limited' }, 429, { 'Retry-After': '600' });
  if (!env.JEEVANA_KV) return json({ ok: false, error: 'internal' }, 500);
  try {
    const ts = Date.now();
    const rand = Array.from(crypto.getRandomValues(new Uint8Array(4))).map((x) => x.toString(16).padStart(2, '0')).join('');
    const rec = { name, email, phone, class: klass, level, message, ts: new Date(ts).toISOString(), lang: b.lang === 'fr' ? 'fr' : 'en', source_url: str(b.source_url, 300), consent: true };
    await env.JEEVANA_KV.put(`reg:${ts}-${rand}`, JSON.stringify(rec));
    return json({ ok: true });
  } catch {
    return json({ ok: false, error: 'internal' }, 500);
  }
};
