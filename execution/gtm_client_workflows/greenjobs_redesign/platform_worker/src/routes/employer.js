// Employer self-posting (PHASE 2 per the 9 Nov plan: CHM Recruit, Mattinson Partnership until their Jan 2027
// contracts end). Behind EMPLOYER_POSTING_ENABLED (default "0" = every /employer and /api/employer path is 404;
// staff post for them in /admin/ on 3 Dec).
//
// Auth: the same Cloudflare Access JWT check as staff (verifyAccessJwt: RS256, JWKS, aud, iss, exp, nbf).
// Authorisation: staff (STAFF_EMAILS) see and edit everything on the site; anyone else must have an active,
// unexpired employer_accounts row mapping their email to an employer row OF THIS SITE (the board allow-list).
// Scope: list / create / edit / close only jobs whose employer_id is in that set; another employer's job -> 403.
//   GET  /employer/                       posting page (the staff console's page, pointed at /api/employer)
//   GET  /api/employer/jobs               own jobs on this site
//   POST /api/employer/jobs               create ({employer_id} needed only when the email maps to several)
//   PUT  /api/employer/jobs/:id           edit (admin.js editJob after the scope check: version lock, audit)
//   POST /api/employer/jobs/:id/close     close (admin.js closeJob after the scope check)
// Writes need the same CSRF (same-origin Origin), JSON content type and Idempotency-Key as the staff console.

import { verifyAccessJwt } from '../auth.js';
import { clientIp, csvList, err, intVar, json, nowIso, todayUtc, UUID_RE, uuidFromSeed } from '../util.js';
import { safeParam, validateJob } from '../validate.js';
import * as Q from '../sql_0003.js';
import { closeJob, editJob, parseJobId, readJson, SQL_AUDIT } from './admin.js';
import { consoleAsset, consoleHtml } from './console.js';

const JOB_PATH = /^\/api\/employer\/jobs\/([^/]+)$/;
const CLOSE_PATH = /^\/api\/employer\/jobs\/([^/]+)\/close$/;
const CREATABLE = new Set(['title', 'employer', 'employer_id', 'location', 'region', 'job_type', 'description', 'summary', 'sal_min', 'sal_max', 'currency', 'period', 'sal_text', 'sectors', 'apply_mode', 'apply_email', 'apply_url', 'closing', 'status']);

export function employerPostingEnabled(env) {
  return env.EMPLOYER_POSTING_ENABLED === '1';
}

/** {ok, email, staff, employers: [{employer_id, name}]} or {ok:false, status, code}. */
export async function authenticateEmployer(request, env, { getKey, nowMs, site }) {
  const token = request.headers.get('Cf-Access-Jwt-Assertion');
  if (!token) return { ok: false, status: 401, code: 'unauthenticated' };
  const r = await verifyAccessJwt(token, env, { getKey, nowMs });
  if (!r.ok) {
    if (r.reason === 'not_configured' || r.reason === 'jwks_unavailable') return { ok: false, status: 503, code: 'auth_unavailable' };
    return { ok: false, status: 401, code: 'unauthenticated' };
  }
  if (r.service || !r.email) return { ok: false, status: 403, code: 'forbidden' }; // service tokens never post as an employer
  const staff = csvList(env.STAFF_EMAILS).map((e) => e.toLowerCase()).includes(r.email);
  if (staff) return { ok: true, email: r.email, staff: true, employers: [] };
  const { results } = await env.DB.prepare(Q.EMPLOYER_SCOPE).bind(r.email, nowIso(new Date(nowMs)), site).all();
  if (!results.length) return { ok: false, status: 403, code: 'forbidden' };
  return { ok: true, email: r.email, staff: false, employers: results };
}

async function jobInScope(db, site, id, who) {
  const row = await db.prepare('SELECT id, employer_id FROM jobs WHERE id = ?1 AND site = ?2').bind(id, site).first();
  if (!row) return { ok: false, res: err('not_found', 404) };
  if (!who.staff && !who.employers.some((e) => e.employer_id === row.employer_id)) return { ok: false, res: err('forbidden', 403) };
  return { ok: true };
}

async function listOwn(ctx, who) {
  const { env, site } = ctx;
  const ids = who.staff ? null : JSON.stringify(who.employers.map((e) => e.employer_id));
  const { results } = await env.DB.prepare(
    `SELECT j.id, j.title, e.name AS employer, j.location, j.status, j.closing_at, j.version, j.apply_mode, j.apply_url,
            j.job_type, j.sal_text, j.summary, j.description, j.sectors_json
       FROM jobs j LEFT JOIN employers e ON e.id = j.employer_id
      WHERE j.site = ?1 AND (?2 IS NULL OR j.employer_id IN (SELECT value FROM json_each(?2)))
      ORDER BY j.updated_at DESC, j.id LIMIT 200`,
  )
    .bind(site, ids)
    .all();
  return json({
    jobs: results.map((r) => ({
      id: r.id, title: r.title, employer: r.employer || '', location: r.location, status: r.status, version: r.version,
      closing: r.closing_at ? r.closing_at.slice(0, 10) : '', apply_mode: r.apply_mode, apply_url: r.apply_url,
      job_type: r.job_type, sal_text: r.sal_text, summary: r.summary, description: r.description,
      sectors: (() => { try { return JSON.parse(r.sectors_json || '[]'); } catch { return []; } })(),
    })),
    employers: who.staff ? null : who.employers.map((e) => ({ id: e.employer_id, name: e.name })),
  });
}

async function createOwn(ctx, who) {
  const { env, site, now, idemKey } = ctx;
  const db = env.DB;
  const rb = await readJson(ctx.request);
  if (!rb.ok) return rb.res;
  const body = rb.body;
  const unknown = Object.keys(body).filter((k) => !CREATABLE.has(k));
  if (unknown.length) return json({ error: 'unknown_field', fields: unknown.slice(0, 20).map((k) => String(k).slice(0, 40)) }, 400);
  let emp;
  if (body.employer_id !== undefined) {
    const p = safeParam(body.employer_id, /^(ie|uk):[a-z]{1,12}:[A-Za-z0-9-]{1,64}$/);
    if (!p.ok) return json({ error: 'invalid_input', fields: ['employer_id'] }, 400);
    if (who.staff) {
      emp = await db.prepare('SELECT id AS employer_id, name FROM employers WHERE id = ?1 AND site = ?2').bind(p.value, site).first();
      if (!emp) return json({ error: 'invalid_input', fields: ['employer_id'] }, 400);
    } else {
      emp = who.employers.find((e) => e.employer_id === p.value);
      if (!emp) return err('forbidden', 403); // another employer, or an employer row of another board
    }
  } else if (!who.staff && who.employers.length === 1) {
    emp = who.employers[0];
  } else {
    return json({ error: 'invalid_input', fields: ['employer_id'] }, 400);
  }
  const input = { ...body, employer: emp.name };
  delete input.employer_id;
  const v = validateJob(input, { site, today: todayUtc(now) });
  if (!v.ok) return json({ error: 'invalid_input', fields: v.errors }, 400);
  const j = v.value;
  const id = `${site}:gj:${await uuidFromSeed(`employer.job.create|${site}|${who.email}|${idemKey}`)}`;
  const ts = nowIso(now);
  const res = await db.batch([
    db.prepare(Q.EMPLOYER_JOB_INSERT).bind(
      id, site, emp.employer_id, j.title, j.location, j.region, j.job_type, j.sal_min, j.sal_max, j.currency, j.period, j.sal_text,
      JSON.stringify(j.sectors), j.summary, j.description, j.apply_mode, j.apply_email, j.apply_url, j.status,
      j.status === 'live' ? ts : null, j.closing ? `${j.closing}T23:59:59Z` : null, who.email, ts,
    ),
    db.prepare(SQL_AUDIT).bind(ts, who.email, 'job.create', 'job', id, idemKey,
      JSON.stringify({ fields: Object.keys(body).sort(), employer_id: emp.employer_id, via: who.staff ? 'staff' : 'employer', flags: v.flags })),
  ]);
  const created = (res[0].meta?.changes ?? 0) > 0;
  return json({ id, version: 1, employer_id: emp.employer_id, replayed: !created }, created ? 201 : 200);
}

export async function employerRoute({ request, env, site, path, now, getKey, rate }) {
  if (!employerPostingEnabled(env)) return err('not_found', 404);
  const allowed = await rate(env, {
    scope: 'employer', key: clientIp(request), limit: intVar(env, 'RATE_ADMIN_PER_MIN', 60), windowSec: 60, nowMs: now.getTime(),
  });
  if (!allowed) return err('rate_limited', 429, { 'Retry-After': '60' });
  const who = await authenticateEmployer(request, env, { getKey, nowMs: now.getTime(), site });
  if (!who.ok) return err(who.code, who.status);
  const method = request.method;
  const ctx = { env, site, now, request, actor: who.email };

  if (method === 'GET') {
    if (path === '/employer') return new Response(null, { status: 301, headers: { Location: '/employer/' } });
    if (path === '/employer/') {
      const page = await consoleHtml(site, who.email).text();
      const html = page.replace('/admin/console.js', '/employer/console.js').replace('/admin/console.css', '/employer/console.css')
        .replace(/GreenJobs posting console/g, 'GreenJobs employer posting');
      return new Response(html, { status: 200, headers: consoleHtml(site, who.email).headers });
    }
    if (path === '/employer/console.js') {
      const a = consoleAsset('console.js');
      const js = (await a.text()).replaceAll('/api/admin/jobs', '/api/employer/jobs');
      return new Response(js, { status: 200, headers: a.headers });
    }
    if (path === '/employer/console.css') return consoleAsset('console.css');
    if (path === '/api/employer/jobs') return listOwn(ctx, who);
    return err('not_found', 404);
  }
  if (method !== 'POST' && method !== 'PUT') return err('method_not_allowed', 405);
  if (request.headers.get('Origin') !== new URL(request.url).origin) return err('csrf', 403);
  if (!(request.headers.get('Content-Type') || '').toLowerCase().startsWith('application/json')) return err('unsupported_media_type', 415);
  const idemKey = request.headers.get('Idempotency-Key') || '';
  if (!UUID_RE.test(idemKey)) return err('idempotency_key_required', 400);
  ctx.idemKey = idemKey.toLowerCase();

  if (method === 'POST' && path === '/api/employer/jobs') return createOwn(ctx, who);
  const close = CLOSE_PATH.exec(path);
  const edit = JOB_PATH.exec(path);
  const raw = method === 'POST' && close ? close[1] : method === 'PUT' && edit ? edit[1] : null;
  if (!raw) return err('not_found', 404);
  const p = parseJobId(raw, site);
  if (!p.ok) return p.res;
  const scope = await jobInScope(env.DB, site, p.id, who);
  if (!scope.ok) return scope.res;
  return close ? closeJob(ctx, raw) : editJob(ctx, raw);
}
