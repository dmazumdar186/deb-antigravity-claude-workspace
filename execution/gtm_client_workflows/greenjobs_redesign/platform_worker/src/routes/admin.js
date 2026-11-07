// Staff posting console API: create, edit (optimistic lock), close (idempotent), list.
// Callers (index.js) have already verified the Access JWT + allow-list, the same-origin Origin,
// the JSON content type and the Idempotency-Key. Every write adds one audit_log row holding
// field NAMES only; a replayed Idempotency-Key returns the original result without a second write.
// SQL statements are the canonical shapes from build/d1/upserts.sql, always with bound params.

import { err, json, nowIso, todayUtc, uuidFromSeed } from '../util.js';
import { safeParam, validateJob } from '../validate.js';

const MAX_JSON_BYTES = 64 * 1024;

const SQL_EMPLOYER_UPSERT = `INSERT INTO employers (id, site, source, source_id, name, name_norm, contact_name, contact_email, phone, website, logo_key, last_active_at, created_at, updated_at)
VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?13)
ON CONFLICT (id) DO UPDATE SET
  name = excluded.name, name_norm = excluded.name_norm, contact_name = excluded.contact_name,
  contact_email = excluded.contact_email, phone = excluded.phone, website = excluded.website,
  logo_key = COALESCE(excluded.logo_key, employers.logo_key),
  last_active_at = NULLIF(MAX(COALESCE(employers.last_active_at, ''), COALESCE(excluded.last_active_at, '')), ''),
  updated_at = excluded.updated_at
WHERE employers.name IS NOT excluded.name OR employers.contact_email IS NOT excluded.contact_email
   OR employers.last_active_at IS NOT excluded.last_active_at OR employers.website IS NOT excluded.website`;

const SQL_JOB_UPSERT = `INSERT INTO jobs (id, site, source, source_id, employer_id, title, location, region, job_type, sal_min, sal_max, currency, period, sal_text, sectors_json, summary, description, apply_mode, apply_email, apply_url, status, posted_at, closing_at, created_by, created_at, updated_at)
VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?17, ?18, ?19, ?20, ?21, ?22, ?23, ?24, ?25, ?25)
ON CONFLICT (id) DO UPDATE SET
  title = excluded.title, location = excluded.location, region = excluded.region, job_type = excluded.job_type,
  sal_min = excluded.sal_min, sal_max = excluded.sal_max, currency = excluded.currency, period = excluded.period,
  sal_text = excluded.sal_text, sectors_json = excluded.sectors_json, summary = excluded.summary,
  description = excluded.description, closing_at = excluded.closing_at,
  status = CASE WHEN jobs.status = 'closed' THEN 'closed' ELSE excluded.status END,
  version = jobs.version + 1, updated_at = excluded.updated_at
WHERE jobs.source = 'strategies'`;

const SQL_JOB_EDIT = `UPDATE jobs SET title = ?3, location = ?4, description = ?5, closing_at = ?6, apply_mode = ?7, apply_email = ?8,
  apply_url = ?9, sal_min = ?10, sal_max = ?11, currency = ?12, sal_text = ?13, status = ?14,
  version = version + 1, updated_at = ?15
WHERE id = ?1 AND version = ?2`;

const SQL_JOB_CLOSE = `UPDATE jobs SET status = 'closed', closed_at = ?2, version = version + 1, updated_at = ?2
WHERE id = ?1 AND status <> 'closed'`;

export const SQL_AUDIT = `INSERT OR IGNORE INTO audit_log (at, actor, action, entity, entity_id, request_id, detail_json)
VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)`;

const EDITABLE = new Set(['title', 'location', 'description', 'closing', 'apply_mode', 'apply_email', 'apply_url', 'sal_min', 'sal_max', 'currency', 'sal_text', 'status', 'version']);
const CREATABLE = new Set(['title', 'employer', 'location', 'region', 'job_type', 'description', 'summary', 'sal_min', 'sal_max', 'currency', 'period', 'sal_text', 'sectors', 'apply_mode', 'apply_email', 'apply_url', 'closing', 'status']);

export function nameNorm(name) {
  return String(name)
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .replace(/\b(ltd|limited|plc|llc|inc|dac|uc)\b/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export async function readJson(request) {
  const len = Number(request.headers.get('Content-Length') || 0);
  if (len > MAX_JSON_BYTES) return { ok: false, res: err('payload_too_large', 413) };
  const text = await request.text();
  if (text.length > MAX_JSON_BYTES) return { ok: false, res: err('payload_too_large', 413) };
  try {
    const body = JSON.parse(text || '{}');
    if (!body || typeof body !== 'object' || Array.isArray(body)) return { ok: false, res: err('invalid_json', 400) };
    return { ok: true, body };
  } catch {
    return { ok: false, res: err('invalid_json', 400) };
  }
}

function auditStmt(db, { now, actor, action, entityId, requestId, detail }) {
  return db.prepare(SQL_AUDIT).bind(nowIso(now), actor, action, 'job', entityId, requestId, JSON.stringify(detail));
}

async function priorAudit(db, requestId, action, entityId) {
  return entityId
    ? db.prepare('SELECT entity_id FROM audit_log WHERE request_id = ?1 AND action = ?2 AND entity_id = ?3').bind(requestId, action, entityId).first()
    : db.prepare('SELECT entity_id FROM audit_log WHERE request_id = ?1 AND action = ?2').bind(requestId, action).first();
}

const closingAt = (d) => (d ? `${d}T23:59:59Z` : null);

function jobView(r) {
  let sectors = [];
  try {
    sectors = JSON.parse(r.sectors_json || '[]');
  } catch {
    sectors = [];
  }
  return {
    id: r.id, title: r.title, employer: r.employer || '', location: r.location, region: r.region, job_type: r.job_type,
    sal_min: r.sal_min, sal_max: r.sal_max, currency: r.currency, period: r.period, sal_text: r.sal_text, sectors,
    summary: r.summary, description: r.description, apply_mode: r.apply_mode, apply_email: r.apply_email,
    apply_url: r.apply_url, status: r.status, posted: r.posted_at ? r.posted_at.slice(0, 10) : '',
    closing: r.closing_at ? r.closing_at.slice(0, 10) : '', source: r.source, version: r.version, updated_at: r.updated_at,
  };
}

const SELECT_JOB = `SELECT j.*, e.name AS employer FROM jobs j LEFT JOIN employers e ON e.id = j.employer_id`;

async function loadJob(db, site, id) {
  return db.prepare(`${SELECT_JOB} WHERE j.id = ?1 AND j.site = ?2`).bind(id, site).first();
}

export function parseJobId(raw, site) {
  const r = safeParam(raw);
  if (!r.ok) return { ok: false, res: err('invalid_id', 400) };
  if (!r.value.startsWith(`${site}:`)) return { ok: false, res: err('not_found', 404) };
  return { ok: true, id: r.value };
}

export async function listAdminJobs(ctx) {
  const { env, site, request } = ctx;
  const q = new URL(request.url).searchParams;
  const limit = Math.min(200, Math.max(1, Number.parseInt(q.get('limit') || '100', 10) || 100));
  const offset = Math.min(1_000_000, Math.max(0, Number.parseInt(q.get('offset') || '0', 10) || 0));
  const status = q.get('status');
  if (status && !['draft', 'live', 'closed'].includes(status)) return err('invalid_status', 400);
  const { results } = await env.DB.prepare(
    `${SELECT_JOB} WHERE j.site = ?1 AND (?2 IS NULL OR j.status = ?2) ORDER BY j.updated_at DESC, j.id LIMIT ?3 OFFSET ?4`,
  )
    .bind(site, status || null, limit + 1, offset)
    .all();
  const more = results.length > limit;
  return json({ jobs: results.slice(0, limit).map(jobView), next_offset: more ? offset + limit : null });
}

export async function getAdminJob(ctx, rawId) {
  const p = parseJobId(rawId, ctx.site);
  if (!p.ok) return p.res;
  const r = await loadJob(ctx.env.DB, ctx.site, p.id);
  return r ? json(jobView(r)) : err('not_found', 404);
}

export async function createJob(ctx) {
  const { env, site, now, actor, idemKey } = ctx;
  const db = env.DB;
  const prior = await priorAudit(db, idemKey, 'job.create');
  if (prior) {
    const r = await loadJob(db, site, prior.entity_id);
    if (r) return json({ id: r.id, version: 1, replayed: true }, 200);
  }
  const rb = await readJson(ctx.request);
  if (!rb.ok) return rb.res;
  const unknown = Object.keys(rb.body).filter((k) => !CREATABLE.has(k));
  if (unknown.length) return json({ error: 'unknown_field', fields: unknown.slice(0, 20).map((k) => String(k).slice(0, 40)) }, 400);
  const today = todayUtc(now);
  const v = validateJob(rb.body, { site, today });
  if (!v.ok) return json({ error: 'invalid_input', fields: v.errors }, 400);
  const job = v.value;

  const id = `${site}:gj:${await uuidFromSeed(`job.create|${site}|${idemKey}`)}`;
  const ts = nowIso(now);
  const norm = nameNorm(job.employer) || job.employer.toLowerCase();
  const existing = await db.prepare('SELECT id FROM employers WHERE site = ?1 AND name_norm = ?2 ORDER BY id LIMIT 1').bind(site, norm).first();
  const stmts = [];
  let employerId = existing?.id;
  if (!employerId) {
    const empUuid = await uuidFromSeed(`employer|${site}|${norm}`);
    employerId = `${site}:gj:${empUuid}`;
    stmts.push(db.prepare(SQL_EMPLOYER_UPSERT).bind(employerId, site, 'console', empUuid, job.employer, norm, null, null, null, null, null, ts, ts));
  }
  stmts.push(
    db.prepare(SQL_JOB_UPSERT).bind(
      id, site, 'console', null, employerId, job.title, job.location, job.region, job.job_type, job.sal_min, job.sal_max,
      job.currency, job.period, job.sal_text, JSON.stringify(job.sectors), job.summary, job.description, job.apply_mode,
      job.apply_email, job.apply_url, job.status, job.status === 'live' ? ts : null, closingAt(job.closing), actor, ts,
    ),
  );
  stmts.push(auditStmt(db, { now, actor, action: 'job.create', entityId: id, requestId: idemKey, detail: { fields: Object.keys(rb.body).sort(), flags: v.flags } }));
  await db.batch(stmts);
  return json({ id, version: 1 }, 201);
}

export async function editJob(ctx, rawId) {
  const { env, site, now, actor, idemKey } = ctx;
  const db = env.DB;
  const p = parseJobId(rawId, site);
  if (!p.ok) return p.res;
  const prior = await priorAudit(db, idemKey, 'job.update', p.id);
  const current = await loadJob(db, site, p.id);
  if (!current) return err('not_found', 404);
  if (prior) return json({ id: p.id, version: current.version, replayed: true }, 200);

  const rb = await readJson(ctx.request);
  if (!rb.ok) return rb.res;
  const body = rb.body;
  const bad = Object.keys(body).filter((k) => !EDITABLE.has(k));
  if (bad.length) return json({ error: 'field_not_editable', fields: bad.slice(0, 20).map((k) => String(k).slice(0, 40)) }, 400);
  if (!Number.isInteger(body.version) || body.version < 1) return json({ error: 'invalid_input', fields: ['version'] }, 400);
  if (body.version !== current.version) return json({ error: 'stale_version', version: current.version }, 409);

  const base = jobView(current);
  const merged = { ...base, ...body };
  delete merged.version;
  const provided = new Set(Object.keys(body));
  const allowStatus = current.status === 'closed' && !provided.has('status') ? ['closed'] : ['draft', 'live'];
  const v = validateJob(merged, { site, today: todayUtc(now), provided, allowStatus });
  if (!v.ok) return json({ error: 'invalid_input', fields: v.errors }, 400);
  const j = v.value;
  const ts = nowIso(now);
  const res = await db
    .prepare(SQL_JOB_EDIT)
    .bind(p.id, body.version, j.title, j.location, j.description, closingAt(j.closing), j.apply_mode, j.apply_email, j.apply_url,
      j.sal_min, j.sal_max, j.currency, j.sal_text, j.status, ts)
    .run();
  if (!res.meta || res.meta.changes === 0) {
    const again = await priorAudit(db, idemKey, 'job.update', p.id);
    const now2 = await loadJob(db, site, p.id);
    if (again) return json({ id: p.id, version: now2?.version, replayed: true }, 200);
    return json({ error: 'stale_version', version: now2?.version ?? null }, 409);
  }
  const changed = [...provided].filter((k) => k !== 'version').sort();
  await auditStmt(db, { now, actor, action: 'job.update', entityId: p.id, requestId: idemKey, detail: { fields: changed, flags: v.flags } }).run();
  return json({ id: p.id, version: body.version + 1 }, 200);
}

export async function closeJob(ctx, rawId) {
  const { env, site, now, actor, idemKey } = ctx;
  const db = env.DB;
  const p = parseJobId(rawId, site);
  if (!p.ok) return p.res;
  const ts = nowIso(now);
  const res = await db.prepare(SQL_JOB_CLOSE).bind(p.id, ts).run();
  if (res.meta && res.meta.changes > 0) {
    await auditStmt(db, { now, actor, action: 'job.close', entityId: p.id, requestId: idemKey, detail: { fields: ['status', 'closed_at'] } }).run();
    const r = await loadJob(db, site, p.id);
    return json({ id: p.id, status: 'closed', version: r.version, already_closed: false }, 200);
  }
  const r = await loadJob(db, site, p.id);
  if (!r) return err('not_found', 404);
  return json({ id: p.id, status: 'closed', version: r.version, already_closed: true }, 200);
}
