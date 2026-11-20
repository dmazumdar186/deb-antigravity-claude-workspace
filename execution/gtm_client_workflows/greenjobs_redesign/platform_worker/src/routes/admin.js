// Staff posting console API: create, edit (optimistic lock), close (idempotent), list.
// Callers (index.js) have already verified the Access JWT + allow-list, the same-origin Origin,
// the JSON content type and the Idempotency-Key. Every write adds one audit_log row holding
// field NAMES only; a replayed Idempotency-Key returns the original result without a second write.
// SQL statements are the canonical shapes from build/d1/upserts.sql, always with bound params.

import { err, json, nowIso, todayUtc, uuidFromSeed } from '../util.js';
import { safeParam, validateJob } from '../validate.js';
import { SQL_FACETS_UPSERT, consoleFacets, facetsParams, facetsStmt, validatePicks } from '../facets.js';
import { slugOf } from './board.js';

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
  apply_mode = excluded.apply_mode, apply_email = excluded.apply_email, apply_url = excluded.apply_url,
  status = CASE WHEN jobs.status = 'closed' THEN 'closed' ELSE excluded.status END,
  version = jobs.version + 1, updated_at = excluded.updated_at
WHERE jobs.source = 'strategies'`;

// A console edit takes ownership of the row (source = 'console'), so the import upsert's
// `WHERE jobs.source = 'strategies'` guard stops a later re-import overwriting it (#15).
// UNIQUE (site, source, source_id) cannot collide: an imported row's source_id is the Strategies id,
// which is also in its PRIMARY KEY '{site}:strat:{id}', and console-created rows carry source_id NULL.
// Every create field is editable (panel D #4); reopening (status closed -> live/draft) clears closed_at.
const SQL_JOB_EDIT = `UPDATE jobs SET title = ?3, location = ?4, description = ?5, closing_at = ?6, apply_mode = ?7, apply_email = ?8,
  apply_url = ?9, sal_min = ?10, sal_max = ?11, currency = ?12, sal_text = ?13, status = ?14,
  employer_id = ?16, region = ?17, job_type = ?18, summary = ?19, sectors_json = ?20, period = ?21,
  closed_at = CASE WHEN ?14 = 'closed' THEN closed_at ELSE NULL END,
  posted_at = CASE WHEN ?14 = 'live' AND posted_at IS NULL THEN ?15 ELSE posted_at END,
  source = 'console', version = version + 1, updated_at = ?15
WHERE id = ?1 AND version = ?2`;

const SQL_JOB_CLOSE = `UPDATE jobs SET status = 'closed', closed_at = ?2, version = version + 1, updated_at = ?2
WHERE id = ?1 AND status <> 'closed'`;

export const SQL_AUDIT = `INSERT OR IGNORE INTO audit_log (at, actor, action, entity, entity_id, request_id, detail_json)
VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)`;

const PICKS = ['sectors', 'region', 'job_type', 'workplace'];
const EDITABLE = new Set(['title', 'employer', 'location', 'region', 'job_type', 'workplace', 'description', 'summary', 'sal_min', 'sal_max', 'currency', 'period', 'sal_text', 'sectors',
  'closing', 'apply_mode', 'apply_email', 'apply_url', 'status', 'version']);
const CREATABLE = new Set(['title', 'employer', 'location', 'region', 'region_by_site', 'sites', 'workplace', 'job_type', 'description', 'summary', 'sal_min', 'sal_max', 'currency', 'period', 'sal_text', 'sectors',
  'apply_mode', 'apply_email', 'apply_url', 'closing', 'status']);

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
const parseArr = (s) => {
  try {
    const v = JSON.parse(s || '[]');
    return Array.isArray(v) ? v : [];
  } catch {
    return [];
  }
};

/** Public page of a job (for the console's "View live" link). */
export const publicPath = (id) => `/${id.split(':')[0]}/jobs/${slugOf(id)}/`;

function jobView(r) {
  const facets = r.f_job_id ? { sectors: parseArr(r.f_sectors), region: parseArr(r.f_regions)[0] || '', job_type: r.f_type, workplace: r.f_workplace } : null;
  return {
    id: r.id, title: r.title, employer: r.employer || '', location: r.location,
    region: facets ? facets.region : r.region, job_type: facets ? facets.job_type : r.job_type, workplace: facets ? facets.workplace : 'unspecified',
    sal_min: r.sal_min, sal_max: r.sal_max, currency: r.currency, period: r.period, sal_text: r.sal_text,
    sectors: facets ? facets.sectors : parseArr(r.sectors_json),
    summary: r.summary, description: r.description, apply_mode: r.apply_mode, apply_email: r.apply_email,
    apply_url: r.apply_url, status: r.status, posted: r.posted_at ? r.posted_at.slice(0, 10) : '',
    closing: r.closing_at ? r.closing_at.slice(0, 10) : '', source: r.source, version: r.version, updated_at: r.updated_at,
    facets_set: Boolean(facets), url: publicPath(r.id),
  };
}

const SELECT_JOB = `SELECT j.*, e.name AS employer, f.job_id AS f_job_id, f.sectors_json AS f_sectors, f.regions_json AS f_regions,
  f.job_type AS f_type, f.workplace AS f_workplace
  FROM jobs j LEFT JOIN employers e ON e.id = j.employer_id LEFT JOIN job_facets f ON f.job_id = j.id`;

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

/** Find the employer row by normalised name on a site, or a statement creating it. Returns {id, stmt|null}. */
async function employerFor(db, site, name, ts) {
  const norm = nameNorm(name) || name.toLowerCase();
  const existing = await db.prepare('SELECT id FROM employers WHERE site = ?1 AND name_norm = ?2 ORDER BY id LIMIT 1').bind(site, norm).first();
  if (existing) return { id: existing.id, stmt: null };
  const empUuid = await uuidFromSeed(`employer|${site}|${norm}`);
  const id = `${site}:gj:${empUuid}`;
  return { id, stmt: db.prepare(SQL_EMPLOYER_UPSERT).bind(id, site, 'console', empUuid, name, norm, null, null, null, null, null, ts, ts) };
}

/**
 * Create one job per chosen site (panel D: one form posts to IE, UK or both). Body: the job fields plus
 * `sites` (["ie"], ["uk"] or ["ie","uk"]; default the console's own site) and the taxonomy picks
 * `sectors` (1-3 names), `job_type`, `workplace`, and `region` or `region_by_site` ({ie, uk}).
 * Each site's row and its job_facets row commit in one batch; a replayed Idempotency-Key returns the same ids.
 */
export async function createJob(ctx) {
  const { env, site, now, actor, idemKey } = ctx;
  const db = env.DB;
  const { results: prior } = await db.prepare('SELECT entity_id FROM audit_log WHERE request_id = ?1 AND action = ?2 ORDER BY id').bind(idemKey, 'job.create').all();
  if (prior.length) {
    const ids = prior.map((r) => r.entity_id);
    return json({ id: ids[0], ids, urls: ids.map(publicPath), version: 1, replayed: true }, 200);
  }
  const rb = await readJson(ctx.request);
  if (!rb.ok) return rb.res;
  const body = rb.body;
  const unknown = Object.keys(body).filter((k) => !CREATABLE.has(k));
  if (unknown.length) return json({ error: 'unknown_field', fields: unknown.slice(0, 20).map((k) => String(k).slice(0, 40)) }, 400);
  const sites = body.sites === undefined ? [site] : body.sites;
  if (!Array.isArray(sites) || !sites.length || sites.length > 2 || new Set(sites).size !== sites.length || !sites.every((s) => s === 'ie' || s === 'uk')) {
    return json({ error: 'invalid_input', fields: ['sites'] }, 400);
  }
  const rbs = body.region_by_site;
  if (rbs !== undefined && (rbs === null || typeof rbs !== 'object' || Array.isArray(rbs) || Object.keys(rbs).some((k) => k !== 'ie' && k !== 'uk'))) {
    return json({ error: 'invalid_input', fields: ['region_by_site'] }, 400);
  }
  const today = todayUtc(now);
  const plans = [];
  const errors = new Set();
  for (const s of sites) {
    const input = { ...body, region: rbs && rbs[s] !== undefined ? rbs[s] : body.region };
    delete input.sites;
    delete input.region_by_site;
    const v = validateJob(input, { site: s, today });
    const pk = validatePicks(input, s);
    for (const e of v.ok ? [] : v.errors) errors.add(e);
    for (const e of pk.errors) errors.add(e === 'region' && rbs ? 'region_by_site' : e);
    if (v.ok && pk.ok) plans.push({ s, job: { ...v.value, region: pk.value.region, job_type: pk.value.job_type, sectors: pk.value.sectors }, picks: pk.value, flags: v.flags });
  }
  if (errors.size) return json({ error: 'invalid_input', fields: [...errors] }, 400);

  const ts = nowIso(now);
  const stmts = [];
  const ids = [];
  for (const { s, job, picks, flags } of plans) {
    const id = `${s}:gj:${await uuidFromSeed(`job.create|${s}|${idemKey}`)}`;
    ids.push(id);
    const emp = await employerFor(db, s, job.employer, ts);
    if (emp.stmt) stmts.push(emp.stmt);
    stmts.push(
      db.prepare(SQL_JOB_UPSERT).bind(
        id, s, 'console', null, emp.id, job.title, job.location, job.region, job.job_type, job.sal_min, job.sal_max,
        job.currency, job.period, job.sal_text, JSON.stringify(job.sectors), job.summary, job.description, job.apply_mode,
        job.apply_email, job.apply_url, job.status, job.status === 'live' ? ts : null, closingAt(job.closing), actor, ts,
      ),
    );
    stmts.push(facetsStmt(db, id, consoleFacets(s, job, picks), 'console', ts));
    stmts.push(auditStmt(db, { now, actor, action: 'job.create', entityId: id, requestId: idemKey, detail: { fields: Object.keys(body).sort(), flags, sites } }));
  }
  await db.batch(stmts);
  return json({ id: ids[0], ids, urls: ids.map(publicPath), version: 1 }, 201);
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
  const today = todayUtc(now);
  const v = validateJob(merged, { site, today, provided, allowStatus });
  // Taxonomy picks: validated whenever the job has facets or the edit touches one; an imported job with no
  // facets yet keeps its raw labels until staff pick (or the import classifier writes them).
  const touchPicks = base.facets_set || PICKS.some((k) => provided.has(k));
  const pk = touchPicks ? validatePicks(merged, site) : { ok: true, errors: [], value: null };
  const errors = [...(v.ok ? [] : v.errors), ...pk.errors];
  const j = v.value;
  // Reopening a role whose closing date has passed would leave it invisible: ask for a new date.
  if (v.ok && current.status === 'closed' && j.status === 'live' && j.closing && j.closing < today && !provided.has('closing')) errors.push('closing');
  if (errors.length) return json({ error: 'invalid_input', fields: [...new Set(errors)] }, 400);
  const ts = nowIso(now);
  const stmts = [];
  let employerId = current.employer_id;
  if (provided.has('employer') && nameNorm(j.employer) !== nameNorm(current.employer || '')) {
    const emp = await employerFor(db, site, j.employer, ts);
    if (emp.stmt) stmts.push(emp.stmt);
    employerId = emp.id;
  }
  const picks = pk.value;
  const region = picks ? picks.region : j.region;
  const jobType = picks ? picks.job_type : j.job_type;
  const sectors = picks ? picks.sectors : j.sectors;
  const newVersion = body.version + 1;
  stmts.push(db.prepare(SQL_JOB_EDIT).bind(p.id, body.version, j.title, j.location, j.description, closingAt(j.closing), j.apply_mode, j.apply_email, j.apply_url,
    j.sal_min, j.sal_max, j.currency, j.sal_text, j.status, ts, employerId, region, jobType, j.summary, JSON.stringify(sectors), j.period));
  if (picks) {
    // Guarded on the version the UPDATE above produced, so a stale edit (0 rows) writes no facets either.
    const params = facetsParams(p.id, consoleFacets(site, { ...j, job_type: jobType }, picks), 'console', ts);
    const VALUES = 'VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?17, ?18)';
    if (!SQL_FACETS_UPSERT.includes(VALUES)) throw new Error('facets upsert shape changed');
    stmts.push(db.prepare(SQL_FACETS_UPSERT.replace(VALUES,
      'SELECT ?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?17, ?18 WHERE (SELECT version FROM jobs WHERE id = ?1) = ?19 AND (SELECT updated_at FROM jobs WHERE id = ?1) = ?14'))
      .bind(...params, newVersion));
  }
  const res = await db.batch(stmts);
  const upd = res[stmts.length - (picks ? 2 : 1)];
  if (!upd.meta || upd.meta.changes === 0) {
    const again = await priorAudit(db, idemKey, 'job.update', p.id);
    const now2 = await loadJob(db, site, p.id);
    if (again) return json({ id: p.id, version: now2?.version, replayed: true }, 200);
    return json({ error: 'stale_version', version: now2?.version ?? null }, 409);
  }
  const changed = [...provided].filter((k) => k !== 'version').sort();
  const reopened = current.status === 'closed' && j.status !== 'closed';
  await auditStmt(db, { now, actor, action: 'job.update', entityId: p.id, requestId: idemKey, detail: { fields: changed, flags: v.flags, ...(reopened ? { reopened: true } : {}) } }).run();
  return json({ id: p.id, version: newVersion, url: publicPath(p.id) }, 200);
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
