// POST /api/admin/import: a classified feed batch (gaia_d1_sync.py --post) -> D1, server to server.
// Auth: bearer BUILD_TOKEN (constant-time compare), not the Access JWT: the caller is a cron, not a person.
//   Cloudflare Access must therefore let exactly this path through with a service token or bypass rule
//   (README "Feed import"); every other /api/admin/* path stays behind Access + STAFF_EMAILS.
// Sandboxed: dry run unless the body says dry_run:false AND the Worker var FEED_IMPORT_ENABLED is "1". A dry run
//   reads D1 and answers the plan (insert / update / close / held / links); it writes nothing.
// Guards (each has a positive test): token, body size, batch ceilings, field floors/ceilings, sectors only from
//   the batch taxonomy, a held (review) job is never live, links only to this site's jobs, an empty batch and
//   a mass close (> IMPORT_MAX_CLOSE_SHARE of the open feed jobs, default 0.5) are refused with 409.
// Writes use the statements of sql_0003.js (= build/d1/upserts_0003.sql, also rendered by the Python emitter),
//   so the SQL file and the API converge on the same rows; every statement is an idempotent upsert.

import { err, json, nowIso, safeEqual, sha256Hex } from '../util.js';
import { cleanText, isValidEmail, normEmail, safeParam, validHttpsUrl } from '../validate.js';
import * as Q from '../sql_0003.js';
import { SQL_AUDIT } from './admin.js';

export const IMPORT_MAX_BYTES = 8 * 1024 * 1024;
export const MAX_JOBS = 500;
export const MAX_LINKS = 2000;
const SOURCES = { gaia: { prefix: 'gaia:%', idRe: /^gaia:\d{1,12}$/, employer: 'Gaia Talent', employerNorm: 'gaia talent', website: 'https://gaiatalent.com' } };
const ISO_TS = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
const WORKPLACES = ['office', 'hybrid', 'remote', 'site', 'unspecified'];
const LOC_CLASSES = ['ie', 'uk', 'ni', 'remote', 'cross', 'intl', 'unspecified'];
const CHUNK = 50;

function strList(v, { max, itemMax, min = 0 }) {
  if (!Array.isArray(v) || v.length < min || v.length > max) return null;
  const out = [];
  for (const x of v) {
    const r = cleanText(x, { min: 1, max: itemMax });
    if (!r.ok) return null;
    out.push(r.value);
  }
  return out;
}

const num01 = (v) => typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 1;

/** Validate one job. Returns {ok, job} or {ok:false, field}. */
export function validateImportJob(j, src, sectorsAllowed) {
  if (!j || typeof j !== 'object' || Array.isArray(j)) return { ok: false, field: 'job' };
  const out = {};
  if (typeof j.source_id !== 'string' || !src.idRe.test(j.source_id)) return { ok: false, field: 'source_id' };
  out.source_id = j.source_id;
  const text = (k, o) => {
    const r = cleanText(j[k], o);
    if (!r.ok) return false;
    out[k] = r.value;
    return true;
  };
  if (!text('title', { min: 3, max: 160 })) return { ok: false, field: 'title' };
  if (!text('location', { min: 1, max: 120 })) return { ok: false, field: 'location' };
  if (!text('region', { max: 80, required: false })) return { ok: false, field: 'region' };
  if (!text('job_type', { max: 40, required: false })) return { ok: false, field: 'job_type' };
  if (!text('sal_text', { max: 120, required: false })) return { ok: false, field: 'sal_text' };
  if (!text('summary', { max: 300, required: false })) return { ok: false, field: 'summary' };
  if (!text('description', { min: 20, max: 20000, multiline: true })) return { ok: false, field: 'description' };
  const sectors = strList(j.sectors ?? [], { max: 10, itemMax: 80 });
  if (!sectors || sectors.some((s) => !sectorsAllowed.has(s))) return { ok: false, field: 'sectors' };
  out.sectors = sectors;
  if (j.apply_mode === 'email') {
    if (j.apply_url != null) return { ok: false, field: 'apply_url' };
    if (j.apply_email != null && !isValidEmail(j.apply_email)) return { ok: false, field: 'apply_email' };
    Object.assign(out, { apply_mode: 'email', apply_email: j.apply_email == null ? null : normEmail(j.apply_email), apply_url: null });
  } else if (j.apply_mode === 'link') {
    const u = validHttpsUrl(j.apply_url);
    if (!u.ok) return { ok: false, field: 'apply_url' };
    if (j.apply_email != null) return { ok: false, field: 'apply_email' };
    Object.assign(out, { apply_mode: 'link', apply_email: null, apply_url: u.value });
  } else return { ok: false, field: 'apply_mode' };
  if (!['draft', 'live'].includes(j.status)) return { ok: false, field: 'status' };
  out.status = j.status;
  for (const k of ['posted_at', 'closing_at']) {
    if (j[k] == null) out[k] = null;
    else if (typeof j[k] === 'string' && ISO_TS.test(j[k])) out[k] = j[k];
    else return { ok: false, field: k };
  }
  if (j.review == null) out.review = null;
  else {
    const r = j.review;
    const reason = cleanText(r?.reason, { min: 1, max: 300 });
    const sug = strList(r?.suggested ?? [], { max: 10, itemMax: 80 });
    if (!reason.ok) return { ok: false, field: 'review.reason' };
    if (!sug || sug.some((s) => !sectorsAllowed.has(s))) return { ok: false, field: 'review.suggested' };
    if (!num01(r.confidence)) return { ok: false, field: 'review.confidence' };
    if (r.hold !== 0 && r.hold !== 1) return { ok: false, field: 'review.hold' };
    out.review = { reason: reason.value, suggested: sug, confidence: r.confidence, hold: r.hold };
  }
  // A job held for review is never published by an import: only a staff approval takes it live.
  if (out.review && out.review.hold === 1 && out.status !== 'draft') return { ok: false, field: 'status' };
  const f = j.facets;
  if (!f || typeof f !== 'object') return { ok: false, field: 'facets' };
  const regions = strList(f.regions ?? [], { max: 20, itemMax: 80 });
  const contract = strList(f.contract ?? [], { max: 6, itemMax: 20 });
  const srcSectors = strList(f.source_sectors ?? [], { max: 20, itemMax: 120 });
  if (!regions) return { ok: false, field: 'facets.regions' };
  if (!contract) return { ok: false, field: 'facets.contract' };
  if (!srcSectors) return { ok: false, field: 'facets.source_sectors' };
  if (f.loc_class != null && !LOC_CLASSES.includes(f.loc_class)) return { ok: false, field: 'facets.loc_class' };
  if (!WORKPLACES.includes(f.workplace)) return { ok: false, field: 'facets.workplace' };
  if (!num01(f.sector_confidence)) return { ok: false, field: 'facets.sector_confidence' };
  const method = cleanText(f.sector_method, { min: 1, max: 40 });
  const tv = cleanText(f.taxonomy_version, { min: 1, max: 64 });
  if (!method.ok) return { ok: false, field: 'facets.sector_method' };
  if (!tv.ok) return { ok: false, field: 'facets.taxonomy_version' };
  out.facets = { regions, loc_class: f.loc_class ?? null, workplace: f.workplace, contract, source_sectors: srcSectors,
    sector_confidence: f.sector_confidence, sector_method: method.value, taxonomy_version: tv.value };
  return { ok: true, job: out };
}

/** Validate the whole batch. Returns {ok, batch} or {ok:false, res}. */
export function validateBatch(body) {
  const bad = (field) => ({ ok: false, res: json({ error: 'invalid_input', field }, 400) });
  if (!body || typeof body !== 'object' || Array.isArray(body)) return bad('body');
  const src = SOURCES[body.source];
  if (!src) return bad('source');
  if (!['ie', 'uk'].includes(body.site)) return bad('site');
  if (body.dry_run !== undefined && typeof body.dry_run !== 'boolean') return bad('dry_run');
  if (body.close_missing !== undefined && typeof body.close_missing !== 'boolean') return bad('close_missing');
  const t = body.taxonomy;
  const tv = cleanText(t?.version, { min: 1, max: 64 });
  const sectors = strList(t?.sectors, { min: 1, max: 100, itemMax: 80 });
  if (!tv.ok || !sectors) return bad('taxonomy');
  const allowed = new Set(sectors);
  if (!Array.isArray(body.jobs) || body.jobs.length > MAX_JOBS) return bad('jobs');
  if (!Array.isArray(body.links ?? []) || (body.links ?? []).length > MAX_LINKS) return bad('links');
  const jobs = [];
  const seen = new Set();
  for (let i = 0; i < body.jobs.length; i++) {
    const v = validateImportJob(body.jobs[i], src, allowed);
    if (!v.ok) return bad(`jobs[${i}].${v.field}`);
    if (seen.has(v.job.source_id)) return bad(`jobs[${i}].source_id`);
    seen.add(v.job.source_id);
    jobs.push(v.job);
  }
  const links = [];
  for (let i = 0; i < (body.links ?? []).length; i++) {
    const l = body.links[i];
    if (!l || typeof l.source_id !== 'string' || !src.idRe.test(l.source_id)) return bad(`links[${i}].source_id`);
    const b = safeParam(l.board_job_id);
    if (!b.ok || !b.value.startsWith(`${body.site}:`)) return bad(`links[${i}].board_job_id`);
    if (!['rule', 'jev'].includes(l.method)) return bad(`links[${i}].method`);
    if (seen.has(l.source_id)) return bad(`links[${i}].source_id`); // a linked duplicate is never also listed
    links.push({ source_id: l.source_id, board_job_id: b.value, method: l.method });
  }
  return {
    ok: true,
    batch: { source: body.source, src, site: body.site, dry_run: body.dry_run !== false, close_missing: body.close_missing !== false,
      allow_mass_close: body.allow_mass_close === true, taxonomy: { version: tv.value, sectors }, jobs, links },
  };
}

function maxCloseShare(env) {
  const n = Number.parseFloat(env.IMPORT_MAX_CLOSE_SHARE ?? '');
  return Number.isFinite(n) && n >= 0 && n <= 1 ? n : 0.5;
}

export function feedJobId(site, sourceId) {
  return `${site}:${sourceId.split(':')[0]}:${sourceId.split(':')[1]}`;
}

/** Statements for one validated batch, in apply order (taxonomy, employer, jobs, links, close, prune). */
export function batchStatements(db, b, ts) {
  const s = [];
  const site = b.site;
  const srcName = b.source;
  s.push(db.prepare(Q.TAXONOMY_DEACTIVATE).bind('sector', JSON.stringify(b.taxonomy.sectors)));
  for (const name of b.taxonomy.sectors) s.push(db.prepare(Q.TAXONOMY_UPSERT).bind('sector', name, b.taxonomy.version));
  const empId = `${site}:feed:${srcName}`;
  s.push(db.prepare(`INSERT INTO employers (id, site, source, source_id, name, name_norm, website, created_at, updated_at)
    VALUES (?1, ?2, 'feed', ?3, ?4, ?5, ?6, ?7, ?7) ON CONFLICT (id) DO NOTHING`)
    .bind(empId, site, srcName, b.src.employer, b.src.employerNorm, b.src.website, ts));
  for (const j of b.jobs) {
    const id = feedJobId(site, j.source_id);
    s.push(db.prepare(Q.FEED_JOB_UPSERT).bind(
      id, site, j.source_id, empId, b.src.employerNorm, j.title, j.location, j.region, j.job_type, j.sal_text,
      JSON.stringify(j.sectors), j.summary, j.description, j.apply_mode, j.apply_email, j.apply_url, j.status,
      j.posted_at, j.closing_at, ts,
    ));
    const f = j.facets;
    s.push(db.prepare(Q.JOB_FACETS_UPSERT).bind(id, site, JSON.stringify(f.regions), f.loc_class, f.workplace,
      JSON.stringify(f.contract), JSON.stringify(f.source_sectors), f.sector_confidence, f.sector_method, f.taxonomy_version, ts));
    if (j.review) {
      s.push(db.prepare(Q.REVIEW_UPSERT).bind(id, site, j.review.reason, JSON.stringify(j.review.suggested), j.review.confidence, j.review.hold, ts));
    } else s.push(db.prepare(Q.REVIEW_CLEAR).bind(id));
  }
  for (const l of b.links) s.push(db.prepare(Q.LINK_UPSERT).bind(site, l.source_id, l.board_job_id, l.method, ts));
  if (b.close_missing) {
    s.push(db.prepare(Q.FEED_CLOSE_MISSING).bind(site, b.src.prefix, ts, JSON.stringify(b.jobs.map((j) => j.source_id).sort())));
    s.push(db.prepare(Q.LINK_PRUNE).bind(site, b.src.prefix, JSON.stringify(b.links.map((l) => `${l.source_id}|${l.board_job_id}`).sort())));
  }
  return s;
}

export async function importBatch({ request, env, now }) {
  if (request.method !== 'POST') return err('method_not_allowed', 405);
  const auth = request.headers.get('Authorization') || '';
  const token = auth.startsWith('Bearer ') ? auth.slice(7) : '';
  if (!env.BUILD_TOKEN || !(await safeEqual(token, env.BUILD_TOKEN))) return err('unauthenticated', 401);
  if (!(request.headers.get('Content-Type') || '').toLowerCase().startsWith('application/json')) return err('unsupported_media_type', 415);
  if (Number(request.headers.get('Content-Length') || 0) > IMPORT_MAX_BYTES) return err('payload_too_large', 413);
  const text = await request.text();
  if (text.length > IMPORT_MAX_BYTES) return err('payload_too_large', 413);
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    return err('invalid_json', 400);
  }
  const v = validateBatch(body);
  if (!v.ok) return v.res;
  const b = v.batch;
  if (!b.dry_run && env.FEED_IMPORT_ENABLED !== '1') return err('import_disabled', 403);

  const db = env.DB;
  const { results: existing } = await db
    .prepare(`SELECT id, source_id, status FROM jobs WHERE site = ?1 AND source = 'feed' AND source_id LIKE ?2`)
    .bind(b.site, b.src.prefix)
    .all();
  const byId = new Map(existing.map((r) => [r.source_id, r]));
  const keep = new Set(b.jobs.map((j) => j.source_id));
  const open = existing.filter((r) => r.status !== 'closed');
  const closing = b.close_missing ? open.filter((r) => !keep.has(r.source_id)).length : 0;
  const plan = {
    insert: b.jobs.filter((j) => !byId.has(j.source_id)).length,
    update: b.jobs.filter((j) => byId.has(j.source_id)).length,
    close: closing,
    held: b.jobs.filter((j) => j.review && j.review.hold === 1).length,
    live: b.jobs.filter((j) => j.status === 'live').length,
    links: b.links.length,
  };
  if (b.close_missing && b.jobs.length === 0 && b.links.length === 0) return json({ error: 'empty_batch', plan }, 409);
  if (open.length && closing / open.length > maxCloseShare(env) && !b.allow_mass_close) {
    return json({ error: 'mass_close_refused', plan, open: open.length, ceiling: maxCloseShare(env) }, 409);
  }
  if (b.dry_run) return json({ dry_run: true, site: b.site, plan, written: false });

  const ts = nowIso(now);
  const stmts = batchStatements(db, b, ts);
  for (let i = 0; i < stmts.length; i += CHUNK) await db.batch(stmts.slice(i, i + CHUNK));
  const digest = await sha256Hex(JSON.stringify({ site: b.site, jobs: b.jobs, links: b.links, taxonomy: b.taxonomy }));
  await db.prepare(SQL_AUDIT).bind(ts, `import:${b.source}`, 'import.batch', 'import', `${b.source}:${b.site}`, `api:${digest}`,
    JSON.stringify({ jobs: b.jobs.length, links: b.links.length, held: plan.held, closed: plan.close })).run();
  return json({ dry_run: false, site: b.site, plan, written: true });
}
