// POST /api/apply (multipart/form-data). Order of gates:
//   origin -> content type/size -> IP rate limit -> parse -> honeypot -> render ts -> fields
//   -> job live + apply mode -> email rate limit -> dedupe -> routing -> CV sniff + R2 -> insert
//   -> audit -> mail (dry by default) -> delivery_status.
// A duplicate (same site|job|email) returns 200 "already_received" and sends nothing.

import { buildApplicationEmail } from '../mail.js';
import { inboxFor } from '../site.js';
import { err, intVar, json, nowIso, sha256Hex, todayUtc, clientIp } from '../util.js';
import { cvKey, checkRenderTs, isValidEmail, normEmail, safeParam, sniffCv, validateApplication } from '../validate.js';
import { SQL_AUDIT } from './admin.js';

const SQL_APP_INSERT = `INSERT INTO applications (id, site, source, source_id, job_id, candidate_id, applicant_name, applicant_email, phone, cover_note, cv_key, routed_to, delivery_status, dedupe_key, submitted_at, created_at, updated_at)
VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?16)
ON CONFLICT (dedupe_key) DO NOTHING`;

const FORM_OVERHEAD = 256 * 1024;

export function dedupeKey(site, jobId, emailNorm) {
  return sha256Hex(`${site}|${jobId}|${emailNorm}`);
}

/** Pick the inbox for an application. Returns {to, fallback: null|reason}. */
export function routeApplication(env, site, job) {
  const inbox = inboxFor(env, site);
  const mode = env.APPLY_ROUTING || 'inbox';
  if (mode === 'consultant' || mode === 'advertiser') {
    if (job.apply_email && isValidEmail(job.apply_email)) return { to: normEmail(job.apply_email), fallback: null };
    return { to: inbox, fallback: job.apply_email ? 'apply_email_invalid' : 'apply_email_missing' };
  }
  return { to: inbox, fallback: mode === 'inbox' ? null : 'unknown_routing' };
}

function field(form, name) {
  const v = form.get(name);
  return typeof v === 'string' ? v : v === null ? undefined : '';
}

export async function apply(ctx) {
  const { env, site, now, request, cors, rate, mailer } = ctx;
  const ct = request.headers.get('Content-Type') || '';
  if (!ct.toLowerCase().startsWith('multipart/form-data')) return err('unsupported_media_type', 415, cors);
  const maxCv = intVar(env, 'MAX_CV_BYTES', 5 * 1024 * 1024);
  const len = Number(request.headers.get('Content-Length') || 0);
  if (len > maxCv + FORM_OVERHEAD) return err('cv_too_large', 413, cors);

  const limit = intVar(env, 'RATE_APPLY_PER_10MIN', 5);
  const nowMs = now.getTime();
  const ipKey = await sha256Hex(clientIp(request));
  if (!(await rate(env, { scope: 'apply-ip', key: ipKey, limit, windowSec: 600, nowMs, binding: env.APPLY_LIMITER }))) {
    return err('rate_limited', 429, { ...cors, 'Retry-After': '600' });
  }

  let form;
  try {
    form = await request.formData();
  } catch {
    return err('invalid_form', 400, cors);
  }
  if ((field(form, 'website') || '') !== '') return err('rejected', 400, cors);
  const ts = checkRenderTs(field(form, 'ts'), nowMs);
  if (!ts.ok) return err(ts.error, 400, cors);

  const v = validateApplication({
    name: field(form, 'name'),
    email: field(form, 'email'),
    phone: field(form, 'phone'),
    cover_note: field(form, 'cover_note'),
    consent: field(form, 'consent'),
  });
  if (!v.ok) return json({ error: 'invalid_input', fields: v.errors }, 400, cors);

  const jid = safeParam(field(form, 'job_id') || '');
  if (!jid.ok) return err('invalid_id', 400, cors);
  const job = await env.DB.prepare(
    `SELECT id, site, title, apply_mode, apply_email, apply_url FROM jobs
     WHERE id = ?1 AND site = ?2 AND status = 'live' AND (closing_at IS NULL OR closing_at >= ?3)`,
  )
    .bind(jid.value, site, todayUtc(now))
    .first();
  if (!job) return err('job_not_found', 404, cors);
  if (job.apply_mode === 'url') return json({ error: 'apply_externally', apply_url: job.apply_url }, 409, cors);

  const emailKey = await sha256Hex(v.value.email);
  if (!(await rate(env, { scope: 'apply-email', key: emailKey, limit, windowSec: 600, nowMs, binding: env.APPLY_LIMITER }))) {
    return err('rate_limited', 429, { ...cors, 'Retry-After': '600' });
  }

  const dkey = await dedupeKey(site, job.id, v.value.email);
  const dup = await env.DB.prepare('SELECT id FROM applications WHERE dedupe_key = ?1').bind(dkey).first();
  if (dup) return json({ ok: true, status: 'already_received' }, 200, cors);

  const route = routeApplication(env, site, job);
  if (!route.to || !isValidEmail(route.to)) {
    console.error('apply: routing_not_configured', site);
    return err('routing_not_configured', 503, cors);
  }

  // CV: optional; sniffed by magic bytes; key built from site/date/uuid only (never the client file name).
  let cv = null;
  const file = form.get('cv');
  if (file && typeof file === 'object' && typeof file.arrayBuffer === 'function' && file.size > 0) {
    if (file.size > maxCv) return err('cv_too_large', 413, cors);
    const bytes = new Uint8Array(await file.arrayBuffer());
    if (bytes.length > maxCv) return err('cv_too_large', 413, cors);
    const kind = sniffCv(bytes);
    if (!kind) return err('cv_type', 415, cors);
    cv = { ...kind, bytes, key: cvKey(site, now, crypto.randomUUID(), kind.ext) };
    await env.CVS.put(cv.key, bytes, { httpMetadata: { contentType: kind.type } });
  }

  const appId = `${site}:apply:${crypto.randomUUID()}`;
  const ts2 = nowIso(now);
  const res = await env.DB.prepare(SQL_APP_INSERT)
    .bind(appId, site, 'apply', null, job.id, null, v.value.name, v.value.email, v.value.phone, v.value.cover_note,
      cv ? cv.key : null, route.to, 'pending', dkey, ts2, ts2)
    .run();
  if (!res.meta || res.meta.changes === 0) {
    // Lost a race with an identical submit: keep the first, drop this CV.
    if (cv) await env.CVS.delete(cv.key);
    return json({ ok: true, status: 'already_received' }, 200, cors);
  }

  const requestId = request.headers.get('cf-ray') || appId;
  const present = ['job_id', 'name', 'email', 'phone', 'cover_note', 'consent'].filter((k) => field(form, k));
  if (cv) present.push('cv');
  const audits = [
    env.DB.prepare(SQL_AUDIT).bind(ts2, 'public', 'application.create', 'application', appId, requestId, JSON.stringify({ fields: present, flags: v.flags })),
  ];
  if (route.fallback) {
    audits.push(env.DB.prepare(SQL_AUDIT).bind(ts2, 'public', 'application.route_fallback', 'application', appId, requestId, JSON.stringify({ reason: route.fallback, routing: env.APPLY_ROUTING || 'inbox' })));
  }
  await env.DB.batch(audits);

  const status = await deliverApplication(ctx.env, mailer, appId, job, cv, now);
  return json({ ok: true, status: 'received', delivery: status === 'failed' ? 'queued' : status }, 201, cors);
}

/** Send one stored application and record its delivery_status. Used by POST /api/apply and the cron retry. */
export async function deliverApplication(env, mailer, appId, job, cv, now) {
  const app = await env.DB.prepare('SELECT id, applicant_name, applicant_email, phone, cover_note, routed_to FROM applications WHERE id = ?1').bind(appId).first();
  if (!app) return 'failed';
  const payload = buildApplicationEmail(env, { app, job, cv });
  const r = await mailer.deliver(env, env.DB, payload, { idempotencyKey: appId, now });
  await env.DB.prepare("UPDATE applications SET delivery_status = ?2, updated_at = ?3 WHERE id = ?1 AND delivery_status IN ('pending','failed')")
    .bind(appId, r.status, nowIso(now))
    .run();
  if (r.status === 'failed') console.error('apply: delivery_failed', appId, r.reason || '');
  return r.status;
}
