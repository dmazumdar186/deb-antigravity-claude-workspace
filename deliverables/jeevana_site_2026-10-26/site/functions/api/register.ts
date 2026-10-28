// POST /api/register — class registration.
// Body: { name, email, phone?, class, level, message?, consent, website (honeypot), lang, source_url }
// 200 { ok:true } · 400 / 413 { ok:false, error } · 429 rate_limited · 503 storage unavailable · 500 internal.
// KV: reg:<ts>-<rand> -> the validated record + consent_text verbatim; expires after 24 months (retention policy).
import { Env, EMAIL_RE, PHONE_RE, REG_TTL_SECONDS, json, str, consentOk, rateLimited, readBody, badBody, noStore, fail, notify, randomHex } from './_lib';

const LEVELS = new Set(['new', 'some', 'regular']);
export const CONSENT_TEXT = {
  en: 'I agree that Jeevana stores these details to answer my registration. They are never shared or sold, and I can ask for their deletion at any time by email.',
  fr: "J'accepte que Jeevana conserve ces informations pour répondre à mon inscription. Elles ne sont jamais partagées ni vendues, et je peux demander leur suppression à tout moment par e-mail.",
};

export const onRequestPost: PagesFunction<Env> = async (ctx) => {
  const { request, env } = ctx;
  const b = await readBody(request);
  const bad = badBody(b); if (bad) return bad;
  const body = b as Record<string, unknown>;
  if (str(body.website, 200)) return json({ ok: true });
  const name = str(body.name, 120);
  const email = str(body.email, 254).toLowerCase();
  const phone = str(body.phone, 40);
  const klass = str(body.class, 60) || 'any';
  const level = LEVELS.has(str(body.level, 20)) ? str(body.level, 20) : 'new';
  const message = str(body.message, 2000);
  if (name.length < 1) return json({ ok: false, error: 'bad_name' }, 400);
  if (!email || !EMAIL_RE.test(email)) return json({ ok: false, error: 'bad_email' }, 400);
  if (phone && !PHONE_RE.test(phone)) return json({ ok: false, error: 'bad_phone' }, 400);
  if (!consentOk(body.consent)) return json({ ok: false, error: 'consent_required' }, 400);
  if (!env.JEEVANA_KV) return noStore();
  if (await rateLimited(env, request, 'reg')) return json({ ok: false, error: 'rate_limited' }, 429, { 'Retry-After': '600' });
  try {
    const ts = Date.now();
    const lang = body.lang === 'fr' ? 'fr' : 'en';
    const rec = { name, email, phone, class: klass, level, message, ts: new Date(ts).toISOString(), lang, source_url: str(body.source_url, 300), consent: true, consent_text: CONSENT_TEXT[lang] };
    await env.JEEVANA_KV.put(`reg:${ts}-${randomHex(4)}`, JSON.stringify(rec), { expirationTtl: REG_TTL_SECONDS });
    ctx.waitUntil(notify(env, `Nouvelle inscription — ${name}`, ['Registration', `name: ${name}`, `email: ${email}`, `phone: ${phone || '-'}`, `class: ${klass}`, `level: ${level}`, `message: ${message || '-'}`, `lang: ${lang}`]));
    return json({ ok: true });
  } catch (err) {
    return fail('register', err);
  }
};
